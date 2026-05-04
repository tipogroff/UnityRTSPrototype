from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        text = line.strip()
        if text:
            rows.append(json.loads(text))
    return rows


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)


def _status_is_authoritative(status: str) -> bool:
    return status in {
        "not_submitted",
        "decoder_rejected",
        "applier_rejected",
        "matchmanager_rejected",
        "accepted_pending",
        "applied",
        "completed",
        "telemetry_conflict",
    }


def _row_command_id(row: dict[str, Any], step: int) -> str:
    command_id = int(row.get("command_id", 0) or 0)
    if command_id > 0:
        return f"cmd:{command_id}"

    # Legacy fallback for pre-21B artifacts that do not expose command_id.
    return "legacy:{step}:{cell}:{atype}:{mdir}:{actor}".format(
        step=step,
        cell=int(row.get("cell_index", -1) or -1),
        atype=str(row.get("decoder_received_action_type") or str(row.get("masked_action_type") or "Unknown")),
        mdir=int(row.get("decoder_received_move_dir", int(row.get("masked_move_dir", -1) or -1)) or -1),
        actor=int(row.get("runtime_is_friendly_actor", 0) or 0),
    )


def _normalize_conflict(row: dict[str, Any]) -> str:
    conflict = str(row.get("command_event_conflict") or "").strip()
    if conflict:
        return conflict

    if _truthy(row.get("legacy_status_conflict")):
        return "legacy_status_conflict"

    accepted = _truthy(row.get("applier_accepted") or row.get("command_event_accepted"))
    rejected = _truthy(row.get("applier_rejected") or row.get("command_event_rejected"))
    if accepted and rejected:
        return "same_command_both_events"

    return ""


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    reports_dir = root / "python/week6_student/reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    tmp_dir = root / "python/week6_student/tmp/stage10d20_masked_runtime_rerun"
    manifest_path = tmp_dir / "stage10d20_run_manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Missing manifest: {manifest_path}")

    table_paths = sorted(tmp_dir.glob("stage10d10_global_runtime_cell_table_step*.jsonl"))
    if not table_paths:
        raise RuntimeError("Missing stage10d10_global_runtime_cell_table_step*.jsonl artifacts")

    rows_by_step: dict[int, list[dict[str, Any]]] = {}
    for path in table_paths:
        step = int(path.stem.split("step")[-1])
        rows_by_step[step] = _read_jsonl(path)

    steps = sorted(rows_by_step.keys())

    trace_rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    conflict_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()

    per_command_statuses: dict[str, set[str]] = defaultdict(set)
    per_command_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    flat_step_to_command_ids: dict[tuple[int, int], set[str]] = defaultdict(set)

    move_candidate_rows = 0
    authoritative_status_rows = 0
    mutually_exclusive_rows = 0

    for step in steps:
        for row in rows_by_step[step]:
            if str(row.get("masked_action_type") or "NoOp") != "Move":
                continue
            if not _truthy(row.get("runtime_is_friendly_actor")):
                continue

            move_candidate_rows += 1

            status = str(row.get("command_result_status") or "").strip() or "missing"
            conflict = _normalize_conflict(row)
            command_id = _row_command_id(row, step)
            event_source = str(row.get("command_event_source") or "legacy")
            event_step = int(row.get("command_event_step", -1) or -1)
            event_seq = int(row.get("command_event_sequence", 0) or 0)

            accepted = _truthy(row.get("command_event_accepted") or row.get("applier_accepted"))
            rejected = _truthy(row.get("command_event_rejected") or row.get("applier_rejected"))
            is_exclusive = (accepted and not rejected) or (rejected and not accepted) or (not accepted and not rejected)

            if _status_is_authoritative(status):
                authoritative_status_rows += 1
            if is_exclusive:
                mutually_exclusive_rows += 1

            status_counts[status] += 1
            source_counts[event_source] += 1
            if conflict:
                conflict_counts[conflict] += 1

            per_command_statuses[command_id].add(status)
            per_command_rows[command_id].append(
                {
                    "step": step,
                    "cell_index": int(row.get("cell_index", -1) or -1),
                    "status": status,
                    "accepted": accepted,
                    "rejected": rejected,
                    "event_step": event_step,
                    "event_sequence": event_seq,
                    "event_source": event_source,
                    "conflict": conflict,
                }
            )

            flat = int(row.get("cell_index", -1) or -1)
            flat_step_to_command_ids[(step, flat)].add(command_id)

            trace_rows.append(
                {
                    "step": step,
                    "cell_index": flat,
                    "command_id": command_id,
                    "command_result_status": status,
                    "command_event_source": event_source,
                    "command_event_step": event_step,
                    "command_event_sequence": event_seq,
                    "command_event_accepted": accepted,
                    "command_event_rejected": rejected,
                    "command_event_conflict": conflict,
                    "legacy_status_conflict": _truthy(row.get("legacy_status_conflict")),
                    "applier_reject_reason": str(row.get("applier_reject_reason") or ""),
                }
            )

    command_level_conflicts = 0
    command_level_nonexclusive = 0
    command_status_cardinality: Counter[str] = Counter()
    sample_problem_commands: list[dict[str, Any]] = []

    for command_id, statuses in per_command_statuses.items():
        command_status_cardinality[str(len(statuses))] += 1
        rows = sorted(per_command_rows[command_id], key=lambda r: (r["step"], r["event_sequence"], r["cell_index"]))

        has_conflict = any(bool(r["conflict"]) for r in rows)
        if has_conflict:
            command_level_conflicts += 1

        has_nonexclusive = any(r["accepted"] and r["rejected"] for r in rows)
        if has_nonexclusive:
            command_level_nonexclusive += 1

        if (has_conflict or has_nonexclusive or len(statuses) > 1) and len(sample_problem_commands) < 12:
            sample_problem_commands.append(
                {
                    "command_id": command_id,
                    "statuses": sorted(statuses),
                    "rows": rows,
                }
            )

    same_flat_multi_command_count = 0
    same_flat_examples: list[dict[str, Any]] = []
    for (step, flat), command_ids in flat_step_to_command_ids.items():
        if len(command_ids) <= 1:
            continue
        same_flat_multi_command_count += 1
        if len(same_flat_examples) < 12:
            same_flat_examples.append(
                {
                    "step": step,
                    "cell_index": flat,
                    "command_ids": sorted(command_ids),
                }
            )

    row_count = len(trace_rows)
    authoritative_status_ratio = (authoritative_status_rows / row_count) if row_count else 0.0
    mutually_exclusive_ratio = (mutually_exclusive_rows / row_count) if row_count else 0.0

    q1 = "Per-command IDs are present" if any(cid.startswith("cmd:") for cid in per_command_statuses) else "Per-command IDs missing (legacy fallback used)"
    q2 = "Statuses are authoritative" if authoritative_status_ratio == 1.0 else "Some rows still use non-authoritative statuses"
    q3 = "Accepted/rejected telemetry is mutually exclusive" if mutually_exclusive_ratio == 1.0 else "Rows exist with both accepted and rejected true"
    q4 = "No same-command conflicts" if command_level_conflicts == 0 else "Conflicts remain on command-level telemetry"
    q5 = "No same-flat multi-command merges" if same_flat_multi_command_count == 0 else "Same-flat multi-command overlap detected"
    q6 = "Event provenance fields populated" if source_counts and "none" not in source_counts else "Event provenance incomplete"
    q7 = "Cleanup GO" if (authoritative_status_ratio == 1.0 and mutually_exclusive_ratio == 1.0 and command_level_conflicts == 0) else "Cleanup NO-GO"

    report = {
        "generated_at_utc": _utc_now(),
        "stage": "Stage10D.21B",
        "source_manifest": str(manifest_path.relative_to(root)).replace("\\", "/"),
        "steps_analyzed": len(steps),
        "last_step": steps[-1] if steps else -1,
        "counts": {
            "move_candidate_rows": move_candidate_rows,
            "trace_rows": row_count,
            "unique_command_ids": len(per_command_statuses),
            "same_flat_multi_command_pairs": same_flat_multi_command_count,
            "command_level_conflicts": command_level_conflicts,
            "command_level_nonexclusive": command_level_nonexclusive,
            "authoritative_status_rows": authoritative_status_rows,
            "mutually_exclusive_rows": mutually_exclusive_rows,
        },
        "ratios": {
            "authoritative_status_ratio": authoritative_status_ratio,
            "mutually_exclusive_ratio": mutually_exclusive_ratio,
        },
        "status_counts": dict(status_counts),
        "event_source_counts": dict(source_counts),
        "conflict_counts": dict(conflict_counts),
        "command_status_cardinality": dict(command_status_cardinality),
        "required_questions": {
            "q1_command_id_present": q1,
            "q2_authoritative_status_only": q2,
            "q3_accepted_rejected_mutually_exclusive": q3,
            "q4_same_command_conflicts_removed": q4,
            "q5_same_flat_multi_command_merge_removed": q5,
            "q6_event_provenance_present": q6,
            "q7_stage10d21c_gate": q7,
        },
        "go_no_go": {
            "stage10d21b_command_status_telemetry_cleanup": "GO" if q7 == "Cleanup GO" else "NO-GO",
        },
        "samples": {
            "problem_commands": sample_problem_commands,
            "same_flat_examples": same_flat_examples,
        },
    }

    trace_path = reports_dir / "stage10d21b_command_status_trace.jsonl"
    report_path = reports_dir / "stage10d21b_command_status_report.json"
    markdown_path = reports_dir / "STAGE10D21B_COMMAND_STATUS_REPORT.md"

    with trace_path.open("w", encoding="utf-8") as fh:
        for item in trace_rows:
            fh.write(json.dumps(item, ensure_ascii=True) + "\n")

    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# STAGE10D21B Authoritative Command Result Telemetry Cleanup Report",
        "",
        f"- Generated (UTC): {report['generated_at_utc']}",
        f"- Steps analyzed: {report['steps_analyzed']} (last={report['last_step']})",
        f"- Unique command IDs: {report['counts']['unique_command_ids']}",
        f"- Cleanup gate: {report['go_no_go']['stage10d21b_command_status_telemetry_cleanup']}",
        "",
        "## Required Questions",
        f"- Q1 command_id present: {q1}",
        f"- Q2 authoritative status only: {q2}",
        f"- Q3 accepted/rejected mutually exclusive: {q3}",
        f"- Q4 same-command conflicts removed: {q4}",
        f"- Q5 same-flat multi-command merge removed: {q5}",
        f"- Q6 event provenance present: {q6}",
        f"- Q7 Stage10D.21C gate: {q7}",
        "",
        "## Key Counts",
        f"- move_candidate_rows: {report['counts']['move_candidate_rows']}",
        f"- trace_rows: {report['counts']['trace_rows']}",
        f"- authoritative_status_rows: {report['counts']['authoritative_status_rows']}",
        f"- mutually_exclusive_rows: {report['counts']['mutually_exclusive_rows']}",
        f"- command_level_conflicts: {report['counts']['command_level_conflicts']}",
        f"- same_flat_multi_command_pairs: {report['counts']['same_flat_multi_command_pairs']}",
        "",
        "## Ratios",
        f"- authoritative_status_ratio: {report['ratios']['authoritative_status_ratio']:.6f}",
        f"- mutually_exclusive_ratio: {report['ratios']['mutually_exclusive_ratio']:.6f}",
        "",
        "## Artifacts",
        f"- Trace JSONL: {trace_path.relative_to(root).as_posix()}",
        f"- Report JSON: {report_path.relative_to(root).as_posix()}",
        f"- Report MD: {markdown_path.relative_to(root).as_posix()}",
    ]
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "trace": trace_path.as_posix(),
                "report": report_path.as_posix(),
                "markdown": markdown_path.as_posix(),
                "gate": report["go_no_go"]["stage10d21b_command_status_telemetry_cleanup"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
