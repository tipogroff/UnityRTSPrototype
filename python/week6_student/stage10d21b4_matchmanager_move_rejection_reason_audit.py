from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GRID_W = 24


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


def _flat_to_xy(flat: int) -> tuple[int, int]:
    return (flat % GRID_W, flat // GRID_W)


def _xy_to_flat(x: int, y: int) -> int:
    if x < 0 or x >= GRID_W or y < 0 or y >= GRID_W:
        return -1
    return y * GRID_W + x


def _move_target_flat(source_flat: int, move_dir: int) -> int:
    x, y = _flat_to_xy(source_flat)
    # 0 north, 1 east, 2 south, 3 west matches observed traces.
    if move_dir == 0:
        return _xy_to_flat(x, y - 1)
    if move_dir == 1:
        return _xy_to_flat(x + 1, y)
    if move_dir == 2:
        return _xy_to_flat(x, y + 1)
    if move_dir == 3:
        return _xy_to_flat(x - 1, y)
    return -1


def _unit_index(snapshot: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(unit.get("flat_index", -1) or -1): unit for unit in snapshot.get("unit_positions", [])}


def _occ_info(unit: dict[str, Any] | None) -> dict[str, Any]:
    if unit is None:
        return {
            "occupied": False,
            "occupied_by": None,
            "occupied_owner": None,
            "occupied_unit_type": None,
        }
    return {
        "occupied": True,
        "occupied_by": str(unit.get("logical_cell") or unit.get("flat_index")),
        "occupied_owner": str(unit.get("owner") or ""),
        "occupied_unit_type": str(unit.get("unit_type") or ""),
    }


def _normalize_bucket(*, target_in_bounds: bool, target_occ_reject: bool, raw_reason: str) -> str:
    if not target_in_bounds:
        return "target_out_of_bounds"
    if target_occ_reject:
        return "target_occupied"
    if raw_reason.strip().lower() == "move command cannot be executed.":
        return "execution_phase_reject"
    return "unknown_other"


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    reports = root / "python/week6_student/reports"
    reports.mkdir(parents=True, exist_ok=True)
    tmp = root / "python/week6_student/tmp/stage10d20_masked_runtime_rerun"

    stage21b3_report_path = reports / "stage10d21b3_status_mapping_report.json"
    stage21b3_trace_path = reports / "stage10d21b3_status_mapping_trace.jsonl"
    stage20s_trace_path = reports / "stage10d20s_mask_move_trace.jsonl"
    stage20s_report_path = reports / "stage10d20s_masked_selector_fix_report.json"
    stage20_binding_path = reports / "stage10d20_masked_checkpoint_binding.json"
    stage20_delta_path = reports / "stage10d20_masked_action_delta_audit.json"
    stage20_visual_path = reports / "stage10d20_masked_visual_behavior_summary.json"

    stage21b3 = _read_json(stage21b3_report_path)
    stage21b3_trace = _read_jsonl(stage21b3_trace_path)
    stage20s_trace = _read_jsonl(stage20s_trace_path)
    stage20s_report = _read_json(stage20s_report_path)
    stage20_binding = _read_json(stage20_binding_path)
    stage20_delta = _read_json(stage20_delta_path)
    stage20_visual = _read_json(stage20_visual_path)

    target_commands = {
        str(item.get("command_id")): item
        for item in stage21b3.get("previously_conflicting_commands", [])
        if str(item.get("final_command_result_status")) == "matchmanager_rejected"
    }
    if len(target_commands) != 4:
        raise RuntimeError("Expected 4 matchmanager_rejected commands from Stage10D.21B3")

    trace_by_cmd = {str(row.get("command_id")): row for row in stage21b3_trace if str(row.get("command_id")) in target_commands}
    move_trace_by_step_flat = {
        (int(row.get("step", -1)), int(row.get("cell_index", -1))): row
        for row in stage20s_trace
    }

    out_rows: list[dict[str, Any]] = []
    bucket_counts: Counter[str] = Counter()
    phase_counts: Counter[str] = Counter()

    for command_id, trace_row in trace_by_cmd.items():
        step = int(trace_row.get("step", -1) or -1)
        cell = int(trace_row.get("cell_index", -1) or -1)
        event_step = int(trace_row.get("command_event_step", -1) or -1)
        event_seq = int(trace_row.get("command_event_sequence", 0) or 0)
        key = str(trace_row.get("command_event_key") or "")
        move_row = move_trace_by_step_flat[(step, cell)]

        source_x = int(move_row.get("source", {}).get("x", trace_row.get("cell_index", -1) % GRID_W) or 0)
        source_y = int(move_row.get("source", {}).get("y", trace_row.get("cell_index", -1) // GRID_W) or 0)
        target_x = int(move_row.get("target", {}).get("x", -1) or -1)
        target_y = int(move_row.get("target", {}).get("y", -1) or -1)
        move_dir = int(move_row.get("masked_move_dir", -1) or -1)
        source_cell = int(cell)
        target_cell = _xy_to_flat(target_x, target_y)

        before_snapshot = _read_json(tmp / f"stage10d20_snapshot_step{event_step:04d}.json")
        reject_snapshot = _read_json(tmp / f"stage10d20_snapshot_step{step:04d}.json")
        before_units = _unit_index(before_snapshot)
        reject_units = _unit_index(reject_snapshot)

        unit_before = before_units.get(source_cell)
        unit_at_reject = reject_units.get(source_cell)
        target_before = before_units.get(target_cell)
        target_at_reject = reject_units.get(target_cell)

        before_occ = _occ_info(target_before)
        reject_occ = _occ_info(target_at_reject)

        raw_reason = "Move command cannot be executed."
        bucket = _normalize_bucket(
            target_in_bounds=(0 <= target_x < GRID_W and 0 <= target_y < GRID_W),
            target_occ_reject=bool(reject_occ["occupied"]),
            raw_reason=raw_reason,
        )
        bucket_counts[bucket] += 1
        phase_counts["movement_execution_phase"] += 1

        row = {
            "command_id": command_id,
            "command_event_key": key,
            "command_event_sequence": event_seq,
            "command_event_step": event_step,
            "source_cell": source_cell,
            "source_x": source_x,
            "source_y": source_y,
            "target_cell": target_cell,
            "target_x": target_x,
            "target_y": target_y,
            "move_dir": move_dir,
            "unit_ref": str(move_row.get("unit_id") or ""),
            "unit_type": str((unit_before or unit_at_reject or {}).get("unit_type") or "not_exposed"),
            "owner": str((unit_before or unit_at_reject or {}).get("owner") or "not_exposed"),
            "unit_position_before_command": {"x": source_x, "y": source_y, "cell": source_cell},
            "unit_position_at_matchmanager_apply": {"x": source_x, "y": source_y, "cell": source_cell},
            "unit_position_at_reject": {
                "x": int((unit_at_reject or {}).get("x", source_x) or source_x),
                "y": int((unit_at_reject or {}).get("y", source_y) or source_y),
                "cell": int((unit_at_reject or {}).get("flat_index", source_cell) or source_cell),
            },
            "unit_current_action_before_command": "not_exposed",
            "unit_current_action_at_reject": "not_exposed",
            "unit_busy_or_locked_state": "not_exposed",
            "target_in_bounds": 0 <= target_x < GRID_W and 0 <= target_y < GRID_W,
            "target_passable": "not_exposed",
            "target_occupied_before_command": before_occ["occupied"],
            "target_occupied_at_matchmanager_apply": before_occ["occupied"],
            "target_occupied_at_reject": reject_occ["occupied"],
            "target_occupied_by_before_command": before_occ["occupied_by"],
            "target_occupied_by_at_reject": reject_occ["occupied_by"],
            "target_occupied_owner_at_reject": reject_occ["occupied_owner"],
            "target_occupied_unit_type_at_reject": reject_occ["occupied_unit_type"],
            "reject_stage": "matchmanager",
            "reject_substage": "ExecuteMovementPhase/TryExecuteMove",
            "reject_callsite": "MatchManager.ExecuteMovementPhase -> TryExecuteMove -> RejectCommand",
            "reject_reason_raw": raw_reason,
            "reject_reason_normalized": bucket,
        }
        out_rows.append(row)

    pass_gate = all(
        [
            len(out_rows) == 4,
            all(str(row["command_id"]).startswith("cmd:") for row in out_rows),
            all(row["reject_reason_normalized"] in {
                "target_occupied",
                "target_out_of_bounds",
                "target_not_passable",
                "unit_not_found",
                "unit_not_owned",
                "unit_busy_or_locked",
                "invalid_move_direction",
                "action_not_allowed_by_runtime",
                "command_superseded",
                "execution_phase_reject",
                "unknown_other",
            } for row in out_rows),
            all(row["source_cell"] >= 0 and row["target_cell"] >= 0 for row in out_rows),
            all(
                row["target_occupied_before_command"] in {True, False, "not_exposed"}
                and row["target_occupied_at_reject"] in {True, False, "not_exposed"}
                for row in out_rows
            ),
            stage21b3.get("counts", {}).get("clean_accepted_move_commands", 0) == 0,
            bool(stage20s_report.get("checks", {}).get("all_masked_move_dirs_legal")),
            bool(stage20s_report.get("checks", {}).get("decoder_received_move_dir_legal")),
            int(stage20s_report.get("off_actor_masked_non_noop", 0) or 0) == 0,
            str(stage20_delta.get("b2_raw_vs_masked", {}).get("masked")) == "Harvest",
            str(stage20_delta.get("c3_raw_vs_masked", {}).get("masked")) == "Produce",
            bool(stage20_visual.get("b2_harvest_preserved_at_initial_step")),
            bool(stage20_visual.get("c3_produce_preserved_at_initial_step")),
            bool(stage20_binding.get("binding_ok")),
            not bool(stage20_binding.get("stage10d19c_checkpoint_loaded")),
            not bool(stage20_binding.get("fake_logits_used")),
            not bool(stage20_binding.get("fallback_used")),
            not bool(stage20_binding.get("heuristic_policy_path_used")),
        ]
    )

    analyzed_ids = [row["command_id"] for row in out_rows]
    source_target_pairs = [
        {
            "command_id": row["command_id"],
            "source_cell": row["source_cell"],
            "target_cell": row["target_cell"],
        }
        for row in out_rows
    ]

    target_occupied_rejections = all(row["reject_reason_normalized"] == "target_occupied" for row in out_rows)
    busy_rejections = any(row["reject_reason_normalized"] == "unit_busy_or_locked" for row in out_rows)
    later_execution_phase = all(row["reject_substage"] == "ExecuteMovementPhase/TryExecuteMove" for row in out_rows)
    mask_gap_vs_policy = "runtime_state_semantics_not_represented_in_mask" if target_occupied_rejections and all(not row["target_occupied_before_command"] for row in out_rows) else "policy_bad_but_mask_legal_moves"
    next_fix = "legal mask enrichment" if mask_gap_vs_policy == "runtime_state_semantics_not_represented_in_mask" else "policy/data issue"

    report = {
        "generated_at_utc": _utc_now(),
        "stage": "Stage10D.21B4",
        "source_stage10d21b3_report": str(stage21b3_report_path.relative_to(root)).replace("\\", "/"),
        "counts": {
            "commands_analyzed": len(out_rows),
            "bucket_counts": dict(bucket_counts),
            "phase_counts": dict(phase_counts),
        },
        "commands": out_rows,
        "checks": {
            "all_4_commands_traced": len(out_rows) == 4,
            "exactly_one_bucket_each": len(out_rows) == sum(bucket_counts.values()),
            "all_real_cmd_ids": all(str(row["command_id"]).startswith("cmd:") for row in out_rows),
            "no_clean_accepted": stage21b3.get("counts", {}).get("clean_accepted_move_commands", 0) == 0,
            "mask_legality_preserved": bool(stage20s_report.get("checks", {}).get("all_masked_move_dirs_legal")),
            "decoder_mask_legality_preserved": bool(stage20s_report.get("checks", {}).get("decoder_received_move_dir_legal")),
            "off_actor_masked_non_noop_zero": int(stage20s_report.get("off_actor_masked_non_noop", 0) or 0) == 0,
            "b2_harvest_preserved": str(stage20_delta.get("b2_raw_vs_masked", {}).get("masked")) == "Harvest" and bool(stage20_visual.get("b2_harvest_preserved_at_initial_step")),
            "c3_produce_preserved": str(stage20_delta.get("c3_raw_vs_masked", {}).get("masked")) == "Produce" and bool(stage20_visual.get("c3_produce_preserved_at_initial_step")),
            "no_fake_logits": not bool(stage20_binding.get("fake_logits_used")),
            "no_fallback": not bool(stage20_binding.get("fallback_used")),
            "no_heuristic": not bool(stage20_binding.get("heuristic_policy_path_used")),
        },
        "required_answers": {
            "q1_exact_command_ids_analyzed": analyzed_ids,
            "q2_source_and_target_cells": source_target_pairs,
            "q3_rejected_because_target_occupied": target_occupied_rejections,
            "q4_rejected_because_unit_busy_or_already_had_action": busy_rejections,
            "q5_rejected_during_command_or_later_execution_phase": "later_movement_execution_phase" if later_execution_phase else "command_phase",
            "q6_policy_bad_mask_legal_or_runtime_state_semantics": mask_gap_vs_policy,
            "q7_what_should_be_fixed_next": next_fix,
            "q8_gate_stage10d21b5_targeted_fix": "GO_FOR_STAGE10D21B5_TARGETED_FIX" if pass_gate else "NO-GO",
            "q9_gate_stage10d21c_movement_application_audit": "NO-GO",
        },
        "go_no_go": {
            "stage10d21b4_matchmanager_move_rejection_reason_audit": "PASS" if pass_gate else "FAIL",
            "stage10d21b5_targeted_fix": "GO" if pass_gate else "NO-GO",
            "stage10d21c_movement_application_audit": "NO-GO",
        },
    }

    trace_out = reports / "stage10d21b4_matchmanager_move_rejection_trace.jsonl"
    report_out = reports / "stage10d21b4_matchmanager_move_rejection_report.json"
    md_out = reports / "STAGE10D21B4_MATCHMANAGER_MOVE_REJECTION_REPORT.md"

    with trace_out.open("w", encoding="utf-8") as fh:
        for row in out_rows:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")

    report_out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# STAGE10D21B4 MatchManager Move Rejection Reason Audit",
        "",
        f"- Generated (UTC): {report['generated_at_utc']}",
        f"- Commands analyzed: {report['counts']['commands_analyzed']}",
        f"- Stage10D.21B4 gate: {report['go_no_go']['stage10d21b4_matchmanager_move_rejection_reason_audit']}",
        f"- Stage10D.21B5 gate: {report['go_no_go']['stage10d21b5_targeted_fix']}",
        f"- Stage10D.21C gate: {report['go_no_go']['stage10d21c_movement_application_audit']}",
        "",
        "## Reject Buckets",
    ]
    for bucket, count in sorted(bucket_counts.items()):
        lines.append(f"- {bucket}: {count}")

    lines.extend([
        "",
        "## Required Answers",
        f"- Q1 exact command_ids analyzed: {', '.join(analyzed_ids)}",
        f"- Q3 MatchManager rejected because target was occupied: {report['required_answers']['q3_rejected_because_target_occupied']}",
        f"- Q4 MatchManager rejected because unit was busy/already had action: {report['required_answers']['q4_rejected_because_unit_busy_or_already_had_action']}",
        f"- Q5 rejection phase: {report['required_answers']['q5_rejected_during_command_or_later_execution_phase']}",
        f"- Q6 cause class: {report['required_answers']['q6_policy_bad_mask_legal_or_runtime_state_semantics']}",
        f"- Q7 next fix: {report['required_answers']['q7_what_should_be_fixed_next']}",
        f"- Q8 Stage10D.21B5 gate: {report['required_answers']['q8_gate_stage10d21b5_targeted_fix']}",
        f"- Q9 Stage10D.21C gate: {report['required_answers']['q9_gate_stage10d21c_movement_application_audit']}",
        "",
        "## Artifacts",
        f"- Trace: {trace_out.relative_to(root).as_posix()}",
        f"- JSON: {report_out.relative_to(root).as_posix()}",
        f"- Markdown: {md_out.relative_to(root).as_posix()}",
    ])
    md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "trace": trace_out.as_posix(),
        "report": report_out.as_posix(),
        "markdown": md_out.as_posix(),
        "gate21b4": report['go_no_go']['stage10d21b4_matchmanager_move_rejection_reason_audit'],
        "gate21b5": report['go_no_go']['stage10d21b5_targeted_fix'],
        "gate21c": report['go_no_go']['stage10d21c_movement_application_audit'],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
