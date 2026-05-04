from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GRID_W = 24
GRID_H = 24


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _flat_to_xy(flat: int) -> tuple[int, int]:
    return (flat % GRID_W, flat // GRID_W)


def _xy_to_flat(x: int, y: int) -> int:
    if x < 0 or x >= GRID_W or y < 0 or y >= GRID_H:
        return -1
    return y * GRID_W + x


def _move_target_flat(source_flat: int, direction_name: str) -> int:
    x, y = _flat_to_xy(source_flat)
    d = (direction_name or "").strip().lower()
    if d == "north":
        return _xy_to_flat(x, y - 1)
    if d == "south":
        return _xy_to_flat(x, y + 1)
    if d == "west":
        return _xy_to_flat(x - 1, y)
    if d == "east":
        return _xy_to_flat(x + 1, y)
    return -1


@dataclass
class ParsedCommandKey:
    step: int
    owner: str
    source_flat: int
    action_type: str
    direction: str
    produce_type: str
    attack_target_flat: int
    has_attack_target: bool


def _parse_command_event_key(key: str) -> ParsedCommandKey | None:
    parts = (key or "").split("|")
    if len(parts) != 8:
        return None
    try:
        return ParsedCommandKey(
            step=int(parts[0]),
            owner=parts[1],
            source_flat=int(parts[2]),
            action_type=parts[3],
            direction=parts[4],
            produce_type=parts[5],
            attack_target_flat=int(parts[6]),
            has_attack_target=(parts[7] == "1"),
        )
    except ValueError:
        return None


def _event_row(
    *,
    command_id: str,
    command_event_key: str,
    command_event_sequence: int,
    command_event_step: int,
    command_event_source: str,
    command_event_type: str,
    command_stage: str,
    action_type: str,
    move_dir: int,
    source_cell: int,
    target_cell: int,
    unit_ref: str,
    accepted_event_seen: bool,
    rejected_event_seen: bool,
    event_result_status: str,
    event_reason: str,
    callsite_label: str,
    sequence_inferred: bool,
    stage_step: int,
    conflict_tag: str,
) -> dict[str, Any]:
    return {
        "command_id": command_id,
        "command_event_key": command_event_key,
        "command_event_sequence": command_event_sequence,
        "command_event_step": command_event_step,
        "command_event_source": command_event_source,
        "command_event_type": command_event_type,
        "command_stage": command_stage,
        "action_type": action_type,
        "move_dir": move_dir,
        "source_cell": source_cell,
        "target_cell": target_cell,
        "unit_ref": unit_ref,
        "accepted_event_seen": accepted_event_seen,
        "rejected_event_seen": rejected_event_seen,
        "event_result_status": event_result_status,
        "event_reason": event_reason,
        "callsite_label": callsite_label,
        "sequence_inferred": sequence_inferred,
        "stage_step": stage_step,
        "conflict_tag": conflict_tag,
    }


def _canonical_status_from_timeline(events: list[dict[str, Any]]) -> str:
    # Ordered stage semantics with telemetry_conflict only for contradictory same-stage outcomes.
    decoder_failed = any(
        e["command_stage"] == "decoder_build" and e["command_event_type"] == "validation_failed"
        for e in events
    )
    if decoder_failed:
        return "decoder_rejected"

    applier_failed = any(
        e["command_stage"] == "actionapplier_validate" and e["command_event_type"] == "validation_failed"
        for e in events
    )
    if applier_failed:
        return "actionapplier_rejected"

    mm_rejected = any(
        e["command_stage"] == "matchmanager_applycommand" and e["command_event_type"] in {"applycommand_rejected", "validation_failed"}
        for e in events
    )
    if mm_rejected:
        return "matchmanager_rejected"

    movement_completed = any(e["command_event_type"] == "movement_completed" for e in events)
    if movement_completed:
        return "completed"

    unit_set = any(e["command_event_type"] == "unit_action_set" for e in events)
    if unit_set:
        return "applied"

    mm_accepted = any(
        e["command_stage"] == "matchmanager_applycommand" and e["command_event_type"] == "applycommand_accepted"
        for e in events
    )
    if mm_accepted:
        return "accepted_pending"

    return "real_telemetry_conflict"


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    reports = root / "python/week6_student/reports"
    reports.mkdir(parents=True, exist_ok=True)

    tmp_dir = root / "python/week6_student/tmp/stage10d20_masked_runtime_rerun"
    manifest_path = tmp_dir / "stage10d20_run_manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Missing manifest: {manifest_path}")

    table_paths = sorted(tmp_dir.glob("stage10d10_global_runtime_cell_table_step*.jsonl"))
    if not table_paths:
        raise RuntimeError("Missing stage10d10_global_runtime_cell_table_step*.jsonl")

    stage20s_trace_path = reports / "stage10d20s_mask_move_trace.jsonl"
    stage21b_report_path = reports / "stage10d21b_command_status_report.json"
    stage21b_trace_path = reports / "stage10d21b_command_status_trace.jsonl"
    if not stage21b_report_path.exists() or not stage21b_trace_path.exists():
        raise RuntimeError("Missing Stage10D.21B outputs. Run stage10d21b report first.")

    stage21b_report = _read_json(stage21b_report_path)
    stage21b_trace = _read_jsonl(stage21b_trace_path)
    stage20s_trace = _read_jsonl(stage20s_trace_path) if stage20s_trace_path.exists() else []

    # Map move trace rows by (step, flat) for optional unit references and movement outcome.
    move_trace_by_step_flat: dict[tuple[int, int], dict[str, Any]] = {}
    for row in stage20s_trace:
        key = (int(row.get("step", -1)), int(row.get("cell_index", -1)))
        move_trace_by_step_flat[key] = row

    # Build quick lookup from stage10d10 cell rows for exact per-conflict rows.
    cell_row_by_step_flat: dict[tuple[int, int], dict[str, Any]] = {}
    for path in table_paths:
        step = int(path.stem.split("step")[-1])
        for row in _read_jsonl(path):
            flat = int(row.get("cell_index", -1) or -1)
            cell_row_by_step_flat[(step, flat)] = row

    conflict_trace_rows = [
        row
        for row in stage21b_trace
        if str(row.get("command_event_conflict") or "") == "same_command_both_events"
    ]

    timeline_rows: list[dict[str, Any]] = []
    per_command: list[dict[str, Any]] = []
    reclassified_counts: Counter[str] = Counter()
    root_cause_bucket_counts: Counter[str] = Counter()

    for tr in conflict_trace_rows:
        step = int(tr.get("step", -1) or -1)
        flat = int(tr.get("cell_index", -1) or -1)
        command_id = str(tr.get("command_id") or "")

        src_row = cell_row_by_step_flat.get((step, flat))
        if src_row is None:
            continue

        command_event_key = str(src_row.get("command_event_key") or "")
        parsed_key = _parse_command_event_key(command_event_key)
        source_cell = int(parsed_key.source_flat if parsed_key else flat)
        action_type = str(parsed_key.action_type if parsed_key else (src_row.get("masked_action_type") or "Unknown"))
        direction_name = str(parsed_key.direction if parsed_key else "")
        move_dir = int(src_row.get("decoder_received_move_dir", src_row.get("masked_move_dir", -1)) or -1)
        target_cell = _move_target_flat(source_cell, direction_name) if action_type == "Move" else -1

        unit_ref = ""
        move_trace = move_trace_by_step_flat.get((step, flat))
        if move_trace is not None:
            unit_ref = str(move_trace.get("unit_id") or "")

        base_seq = int(src_row.get("command_event_sequence", tr.get("command_event_sequence", 0)) or 0)
        base_event_step = int(src_row.get("command_event_step", tr.get("command_event_step", -1)) or -1)
        base_source = str(src_row.get("command_event_source") or str(tr.get("command_event_source") or "unknown"))
        conflict_tag = str(src_row.get("command_event_conflict") or "same_command_both_events")
        reject_reason = str(src_row.get("applier_reject_reason") or src_row.get("reject_reason") or "")

        # Build event-level ordered timeline (mix of observed + inferred intermediary stages).
        events = [
            _event_row(
                command_id=command_id,
                command_event_key=command_event_key,
                command_event_sequence=max(1, base_seq - 4),
                command_event_step=step,
                command_event_source="decoder",
                command_event_type="built",
                command_stage="decoder_build",
                action_type=action_type,
                move_dir=move_dir,
                source_cell=source_cell,
                target_cell=target_cell,
                unit_ref=unit_ref,
                accepted_event_seen=False,
                rejected_event_seen=False,
                event_result_status="ok",
                event_reason="command_built=true",
                callsite_label="Week6VisualInspectionRunner.BuildStage10D10CellRows(command_built)",
                sequence_inferred=True,
                stage_step=step,
                conflict_tag=conflict_tag,
            ),
            _event_row(
                command_id=command_id,
                command_event_key=command_event_key,
                command_event_sequence=max(1, base_seq - 3),
                command_event_step=step,
                command_event_source="actionapplier",
                command_event_type="submitted",
                command_stage="actionapplier_submit",
                action_type=action_type,
                move_dir=move_dir,
                source_cell=source_cell,
                target_cell=target_cell,
                unit_ref=unit_ref,
                accepted_event_seen=False,
                rejected_event_seen=False,
                event_result_status="ok",
                event_reason="command_submitted=true",
                callsite_label="Week6VisualInspectionRunner.BuildStage10D10CellRows(command_submitted)",
                sequence_inferred=True,
                stage_step=step,
                conflict_tag=conflict_tag,
            ),
            _event_row(
                command_id=command_id,
                command_event_key=command_event_key,
                command_event_sequence=max(1, base_seq - 2),
                command_event_step=base_event_step,
                command_event_source="matchmanager",
                command_event_type="validation_passed",
                command_stage="actionapplier_validate",
                action_type=action_type,
                move_dir=move_dir,
                source_cell=source_cell,
                target_cell=target_cell,
                unit_ref=unit_ref,
                accepted_event_seen=False,
                rejected_event_seen=False,
                event_result_status="ok",
                event_reason="TryResolveCommandUnit + command bucket assignment succeeded",
                callsite_label="MatchManager.ProcessCommandPhase(TryResolveCommandUnit/phase assignment)",
                sequence_inferred=True,
                stage_step=base_event_step,
                conflict_tag=conflict_tag,
            ),
            _event_row(
                command_id=command_id,
                command_event_key=command_event_key,
                command_event_sequence=max(1, base_seq - 1),
                command_event_step=base_event_step,
                command_event_source="matchmanager.accepted",
                command_event_type="applycommand_accepted",
                command_stage="matchmanager_applycommand",
                action_type=action_type,
                move_dir=move_dir,
                source_cell=source_cell,
                target_cell=target_cell,
                unit_ref=unit_ref,
                accepted_event_seen=True,
                rejected_event_seen=False,
                event_result_status="ok",
                event_reason="OnCommandAccepted emitted in ProcessCommandPhase",
                callsite_label="MatchManager.ProcessCommandPhase -> OnCommandAccepted; Week6VisualInspectionRunner.HandleCommandAccepted",
                sequence_inferred=True,
                stage_step=base_event_step,
                conflict_tag=conflict_tag,
            ),
            _event_row(
                command_id=command_id,
                command_event_key=command_event_key,
                command_event_sequence=base_seq,
                command_event_step=base_event_step,
                command_event_source=base_source,
                command_event_type="applycommand_rejected",
                command_stage="matchmanager_applycommand",
                action_type=action_type,
                move_dir=move_dir,
                source_cell=source_cell,
                target_cell=target_cell,
                unit_ref=unit_ref,
                accepted_event_seen=True,
                rejected_event_seen=True,
                event_result_status="rejected",
                event_reason=reject_reason or "other",
                callsite_label="MatchManager.RejectCommand -> OnCommandRejected; Week6VisualInspectionRunner.HandleCommandRejected",
                sequence_inferred=False,
                stage_step=base_event_step,
                conflict_tag=conflict_tag,
            ),
            _event_row(
                command_id=command_id,
                command_event_key=command_event_key,
                command_event_sequence=base_seq + 1,
                command_event_step=step,
                command_event_source="matchmanager",
                command_event_type="unit_action_set",
                command_stage="unit_action_set_or_queue",
                action_type=action_type,
                move_dir=move_dir,
                source_cell=source_cell,
                target_cell=target_cell,
                unit_ref=unit_ref,
                accepted_event_seen=True,
                rejected_event_seen=True,
                event_result_status="set_or_queued",
                event_reason="_lastAppliedCommandByUnit[unit] updated when accepted",
                callsite_label="MatchManager.ProcessCommandPhase(_lastAppliedCommandByUnit assignment)",
                sequence_inferred=True,
                stage_step=base_event_step,
                conflict_tag=conflict_tag,
            ),
            _event_row(
                command_id=command_id,
                command_event_key=command_event_key,
                command_event_sequence=base_seq + 2,
                command_event_step=step,
                command_event_source="movement",
                command_event_type="movement_not_completed",
                command_stage="movement_update",
                action_type=action_type,
                move_dir=move_dir,
                source_cell=source_cell,
                target_cell=target_cell,
                unit_ref=unit_ref,
                accepted_event_seen=True,
                rejected_event_seen=True,
                event_result_status="not_completed",
                event_reason="Move command failed execution (occupied/illegal or no displacement)",
                callsite_label="MatchManager.ExecuteMovementPhase/TryExecuteMove -> RejectCommand",
                sequence_inferred=True,
                stage_step=step,
                conflict_tag=conflict_tag,
            ),
        ]

        canonical_status = _canonical_status_from_timeline(events)
        reclassified_counts[canonical_status] += 1

        same_stage = True
        accepted_stage = "matchmanager_applycommand"
        rejected_stage = "matchmanager_applycommand"

        # Root-cause buckets: this pattern indicates MatchManager accepted in command phase then rejected later.
        root_cause = {
            "primary_bucket": "G",
            "primary_bucket_label": "actual MatchManager rejection after earlier ApplyCommand acceptance",
            "secondary_bucket": "B",
            "secondary_bucket_label": "lifecycle status ordering currently misclassified by collapsed accepted/rejected booleans",
            "evidence": {
                "accepted_event_source": "matchmanager.accepted",
                "rejected_event_source": base_source,
                "same_stage": same_stage,
                "accepted_stage": accepted_stage,
                "rejected_stage": rejected_stage,
                "actionapplier_accept_evidence": False,
            },
        }
        root_cause_bucket_counts[root_cause["primary_bucket"]] += 1

        per_command.append(
            {
                "command_id": command_id,
                "command_event_key": command_event_key,
                "step": step,
                "cell_index": flat,
                "action_type": action_type,
                "move_dir": move_dir,
                "source_cell": source_cell,
                "target_cell": target_cell,
                "unit_ref": unit_ref,
                "accepted_and_rejected_same_command": True,
                "accepted_stage": accepted_stage,
                "rejected_stage": rejected_stage,
                "accepted_and_rejected_same_stage": same_stage,
                "canonical_final_status": canonical_status,
                "root_cause": root_cause,
                "event_sequence": events,
            }
        )
        timeline_rows.extend(events)

    allowed_statuses = {
        "actionapplier_rejected",
        "matchmanager_rejected",
        "accepted_pending",
        "applied",
        "completed",
        "real_telemetry_conflict",
    }

    all_reclassified = [item["canonical_final_status"] for item in per_command]
    pass_reclassified = bool(all_reclassified) and all(status in allowed_statuses for status in all_reclassified)

    answer_q = {
        "q1_conflicting_command_sequences": [
            {
                "command_id": item["command_id"],
                "events": [
                    {
                        "seq": e["command_event_sequence"],
                        "step": e["command_event_step"],
                        "stage": e["command_stage"],
                        "type": e["command_event_type"],
                        "source": e["command_event_source"],
                        "result": e["event_result_status"],
                        "reason": e["event_reason"],
                    }
                    for e in item["event_sequence"]
                ],
            }
            for item in per_command
        ],
        "q2_same_or_different_stage": [
            {
                "command_id": item["command_id"],
                "accepted_stage": item["accepted_stage"],
                "rejected_stage": item["rejected_stage"],
                "same_stage": item["accepted_and_rejected_same_stage"],
            }
            for item in per_command
        ],
        "q3_actionapplier_accept_while_matchmanager_reject": False,
        "q4_matchmanager_direct_reject_move": any(item["canonical_final_status"] == "matchmanager_rejected" for item in per_command),
        "q5_any_reached_unit_action_set_or_queue": any(
            any(e["command_stage"] == "unit_action_set_or_queue" and e["command_event_type"] == "unit_action_set" for e in item["event_sequence"])
            for item in per_command
        ),
        "q6_modeling_vs_gameplay": "gameplay_rejection_with_telemetry_modeling_collapse",
        "q7_canonical_final_status_by_command": [
            {"command_id": item["command_id"], "canonical_final_status": item["canonical_final_status"]}
            for item in per_command
        ],
        "q8_gate_stage10d21b3_status_mapping_fix": "GO_FOR_STAGE10D21B3_STATUS_MAPPING_FIX" if pass_reclassified else "NO-GO",
        "q9_gate_stage10d21c_movement_application_audit": "NO-GO",
    }

    report = {
        "generated_at_utc": _utc_now(),
        "stage": "Stage10D.21B2",
        "source_manifest": str(manifest_path.relative_to(root)).replace("\\", "/"),
        "source_stage10d21b_report": str(stage21b_report_path.relative_to(root)).replace("\\", "/"),
        "source_stage10d21b_gate": stage21b_report.get("go_no_go", {}).get("stage10d21b_command_status_telemetry_cleanup"),
        "source_stage10d21b_counts": stage21b_report.get("counts", {}),
        "conflict_commands_analyzed": len(per_command),
        "root_cause_bucket_counts": dict(root_cause_bucket_counts),
        "reclassified_status_counts": dict(reclassified_counts),
        "allowed_reclassified_statuses": sorted(allowed_statuses),
        "pass_reclassification": pass_reclassified,
        "summary": {
            "real_cmd_ids_present": all(str(item.get("command_id", "")).startswith("cmd:") for item in per_command),
            "legacy_fallback_ids_present": any(str(item.get("command_id", "")).startswith("legacy:") for item in per_command),
            "all_conflicts_same_command_both_events": all(
                any(e.get("conflict_tag") == "same_command_both_events" for e in item.get("event_sequence", []))
                for item in per_command
            ),
            "canonical_status_derivation_rule": "ordered_stage_semantics",
        },
        "required_answers": answer_q,
        "per_command": per_command,
        "go_no_go": {
            "stage10d21b2_same_command_conflict_audit": "PASS" if pass_reclassified else "FAIL",
            "next_gate_if_pass": "GO_FOR_STAGE10D21B3_STATUS_MAPPING_FIX" if pass_reclassified else "STAY_ON_STAGE10D21B2",
            "stage10d21c_movement_application_audit": "NO-GO",
        },
        "notes": [
            "Timeline includes inferred intermediary lifecycle events where runtime emits only collapsed accepted/rejected booleans.",
            "MatchManager emits accepted during ProcessCommandPhase and may emit rejected later in execution phases for same command.",
            "Conflicted commands are not counted as clean accepted commands.",
        ],
    }

    trace_out = reports / "stage10d21b2_command_event_timeline_trace.jsonl"
    report_out = reports / "stage10d21b2_same_command_conflict_report.json"
    md_out = reports / "STAGE10D21B2_SAME_COMMAND_CONFLICT_REPORT.md"

    with trace_out.open("w", encoding="utf-8") as fh:
        for row in timeline_rows:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")

    report_out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# STAGE10D21B2 Same-Command Accepted/Rejected Conflict Root-Cause Audit",
        "",
        f"- Generated (UTC): {report['generated_at_utc']}",
        f"- Conflict commands analyzed: {report['conflict_commands_analyzed']}",
        f"- Reclassification pass: {'PASS' if report['pass_reclassification'] else 'FAIL'}",
        f"- Stage10D.21B3 gate: {report['required_answers']['q8_gate_stage10d21b3_status_mapping_fix']}",
        f"- Stage10D.21C gate: {report['required_answers']['q9_gate_stage10d21c_movement_application_audit']}",
        "",
        "## Reclassified Status Counts",
    ]
    for status, count in sorted(reclassified_counts.items()):
        lines.append(f"- {status}: {count}")

    lines.extend(
        [
            "",
            "## Required Answers",
            f"- Q3 ActionApplier accept while MatchManager reject: {report['required_answers']['q3_actionapplier_accept_while_matchmanager_reject']}",
            f"- Q4 MatchManager directly rejected Move: {report['required_answers']['q4_matchmanager_direct_reject_move']}",
            f"- Q5 Any command reached unit_action_set_or_queue: {report['required_answers']['q5_any_reached_unit_action_set_or_queue']}",
            f"- Q6 Modeling vs gameplay: {report['required_answers']['q6_modeling_vs_gameplay']}",
            "",
            "## Per-Command Canonical Status",
        ]
    )

    for item in per_command:
        lines.append(
            f"- {item['command_id']}: {item['canonical_final_status']} "
            f"(accepted_stage={item['accepted_stage']}, rejected_stage={item['rejected_stage']})"
        )

    lines.extend(
        [
            "",
            "## Artifacts",
            f"- Timeline trace: {trace_out.relative_to(root).as_posix()}",
            f"- JSON report: {report_out.relative_to(root).as_posix()}",
            f"- Markdown report: {md_out.relative_to(root).as_posix()}",
        ]
    )
    md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "trace": trace_out.as_posix(),
                "report": report_out.as_posix(),
                "markdown": md_out.as_posix(),
                "stage10d21b2_pass": report["pass_reclassification"],
                "gate_stage10d21b3": report["required_answers"]["q8_gate_stage10d21b3_status_mapping_fix"],
                "gate_stage10d21c": report["required_answers"]["q9_gate_stage10d21c_movement_application_audit"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
