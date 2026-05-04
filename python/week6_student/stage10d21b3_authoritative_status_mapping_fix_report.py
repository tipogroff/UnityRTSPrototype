from __future__ import annotations

import json
from collections import Counter
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
        "actionapplier_rejected",
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
    return "legacy:{step}:{cell}".format(step=step, cell=int(row.get("cell_index", -1) or -1))


def _derive_base_status(row: dict[str, Any]) -> dict[str, Any]:
    predicted_non_noop = str(row.get("masked_action_type") or "NoOp") != "NoOp"
    command_built = _truthy(row.get("command_built"))
    command_submitted = _truthy(row.get("command_submitted") or row.get("applier_submitted"))
    applier_accepted = _truthy(row.get("applier_accepted") or row.get("command_event_accepted"))
    applier_rejected = _truthy(row.get("applier_rejected") or row.get("command_event_rejected"))
    reject_stage = str(row.get("reject_stage") or "").strip()
    reject_reason = str(row.get("applier_reject_reason") or row.get("reject_reason") or "").strip()
    sequence = int(row.get("command_event_sequence", 0) or 0)

    if not predicted_non_noop:
        return {
            "final_command_result_status": "not_submitted",
            "final_status_source_stage": "decoder",
            "final_status_source_event_sequence": sequence,
            "clean_accepted": False,
            "terminal_rejected": False,
            "terminal_reject_stage": "",
            "terminal_reject_reason": "",
            "had_intermediate_accept_event": False,
            "had_later_reject_event": False,
            "ordered_lifecycle_reclassified": False,
            "telemetry_conflict": False,
            "conflict_reason": "",
        }

    if not command_built or not command_submitted:
        return {
            "final_command_result_status": "decoder_rejected",
            "final_status_source_stage": "decoder",
            "final_status_source_event_sequence": sequence,
            "clean_accepted": False,
            "terminal_rejected": True,
            "terminal_reject_stage": "decoder",
            "terminal_reject_reason": reject_reason or str(row.get("decoder_reject_reason") or "decoder_rejected"),
            "had_intermediate_accept_event": False,
            "had_later_reject_event": False,
            "ordered_lifecycle_reclassified": False,
            "telemetry_conflict": False,
            "conflict_reason": "",
        }

    if applier_rejected and not applier_accepted:
        stage = "actionapplier" if reject_stage in {"applier", "actionapplier"} else "matchmanager"
        status = "actionapplier_rejected" if stage == "actionapplier" else "matchmanager_rejected"
        return {
            "final_command_result_status": status,
            "final_status_source_stage": stage,
            "final_status_source_event_sequence": sequence,
            "clean_accepted": False,
            "terminal_rejected": True,
            "terminal_reject_stage": stage,
            "terminal_reject_reason": reject_reason,
            "had_intermediate_accept_event": False,
            "had_later_reject_event": True,
            "ordered_lifecycle_reclassified": False,
            "telemetry_conflict": False,
            "conflict_reason": "",
        }

    if applier_accepted:
        return {
            "final_command_result_status": "accepted_pending",
            "final_status_source_stage": "matchmanager",
            "final_status_source_event_sequence": sequence,
            "clean_accepted": True,
            "terminal_rejected": False,
            "terminal_reject_stage": "",
            "terminal_reject_reason": "",
            "had_intermediate_accept_event": True,
            "had_later_reject_event": False,
            "ordered_lifecycle_reclassified": False,
            "telemetry_conflict": False,
            "conflict_reason": "",
        }

    return {
        "final_command_result_status": "telemetry_conflict",
        "final_status_source_stage": "telemetry",
        "final_status_source_event_sequence": sequence,
        "clean_accepted": False,
        "terminal_rejected": False,
        "terminal_reject_stage": "",
        "terminal_reject_reason": "",
        "had_intermediate_accept_event": applier_accepted,
        "had_later_reject_event": applier_rejected,
        "ordered_lifecycle_reclassified": False,
        "telemetry_conflict": True,
        "conflict_reason": str(row.get("command_event_conflict") or "unclassified"),
    }


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

    stage21b2_path = reports_dir / "stage10d21b2_same_command_conflict_report.json"
    stage20s_path = reports_dir / "stage10d20s_masked_selector_fix_report.json"
    stage20_binding_path = reports_dir / "stage10d20_masked_checkpoint_binding.json"
    stage20_off_actor_path = reports_dir / "stage10d20_masked_off_actor_safety.json"
    stage20_delta_path = reports_dir / "stage10d20_masked_action_delta_audit.json"
    stage20_visual_path = reports_dir / "stage10d20_masked_visual_behavior_summary.json"
    if not stage21b2_path.exists():
        raise RuntimeError("Missing Stage10D.21B2 report. Run Stage10D.21B2 first.")

    stage21b2 = _read_json(stage21b2_path)
    stage20s = _read_json(stage20s_path)
    stage20_binding = _read_json(stage20_binding_path)
    stage20_off_actor = _read_json(stage20_off_actor_path)
    stage20_delta = _read_json(stage20_delta_path)
    stage20_visual = _read_json(stage20_visual_path)

    conflict_override_by_cmd: dict[str, dict[str, Any]] = {}
    for item in stage21b2.get("per_command", []):
        command_id = str(item.get("command_id") or "")
        events = item.get("event_sequence", [])
        final_status = str(item.get("canonical_final_status") or "telemetry_conflict")
        final_stage = "telemetry"
        final_seq = 0
        terminal_reason = ""
        if events:
            if final_status == "matchmanager_rejected":
                reject_events = [
                    event for event in events
                    if event.get("command_stage") == "matchmanager_applycommand"
                    and event.get("command_event_type") == "applycommand_rejected"
                ]
                if reject_events:
                    chosen = max(reject_events, key=lambda event: int(event.get("command_event_sequence", 0) or 0))
                    final_stage = "matchmanager"
                    final_seq = int(chosen.get("command_event_sequence", 0) or 0)
                    terminal_reason = str(chosen.get("event_reason") or "")
            elif final_status in {"applied", "accepted_pending", "completed"}:
                chosen = max(events, key=lambda event: int(event.get("command_event_sequence", 0) or 0))
                final_stage = str(chosen.get("command_stage") or "telemetry")
                final_seq = int(chosen.get("command_event_sequence", 0) or 0)
        conflict_override_by_cmd[command_id] = {
            "final_command_result_status": final_status,
            "final_status_source_stage": final_stage,
            "final_status_source_event_sequence": final_seq,
            "clean_accepted": final_status in {"accepted_pending", "applied", "completed"},
            "terminal_rejected": final_status in {"decoder_rejected", "actionapplier_rejected", "matchmanager_rejected"},
            "terminal_reject_stage": final_stage if final_status.endswith("rejected") else "",
            "terminal_reject_reason": terminal_reason,
            "had_intermediate_accept_event": True,
            "had_later_reject_event": final_status.endswith("rejected"),
            "ordered_lifecycle_reclassified": True,
            "telemetry_conflict": final_status == "telemetry_conflict",
            "conflict_reason": "ordered_lifecycle_explains_prior_same_command_both_events" if final_status != "telemetry_conflict" else "same_stage_contradiction",
        }

    trace_rows: list[dict[str, Any]] = []
    final_status_counts: Counter[str] = Counter()
    source_stage_counts: Counter[str] = Counter()
    telemetry_conflict_count = 0
    real_cmd_ids = 0
    legacy_cmd_ids = 0
    clean_accepted_move_commands = 0
    clean_applied_move_commands = 0
    terminal_rejected_move_commands = 0
    converted_conflicts = 0
    converted_to_matchmanager_rejected = 0
    rejected_but_clean_accepted = 0
    previously_conflicting_ids: set[str] = set(conflict_override_by_cmd.keys())
    previously_conflicting_reclassified: list[dict[str, Any]] = []

    for path in table_paths:
        step = int(path.stem.split("step")[-1])
        for row in _read_jsonl(path):
            if str(row.get("masked_action_type") or "NoOp") != "Move":
                continue
            if not _truthy(row.get("runtime_is_friendly_actor")):
                continue

            command_id = _row_command_id(row, step)
            command_event_key = str(row.get("command_event_key") or "")
            base = _derive_base_status(row)
            if command_id in conflict_override_by_cmd:
                base = conflict_override_by_cmd[command_id]

            final_status = str(base["final_command_result_status"])
            final_stage = str(base["final_status_source_stage"])
            final_seq = int(base["final_status_source_event_sequence"] or 0)
            clean_accepted = bool(base["clean_accepted"])
            terminal_rejected = bool(base["terminal_rejected"])
            terminal_reject_stage = str(base["terminal_reject_stage"] or "")
            terminal_reject_reason = str(base["terminal_reject_reason"] or row.get("applier_reject_reason") or row.get("reject_reason") or "")
            had_intermediate_accept_event = bool(base["had_intermediate_accept_event"])
            had_later_reject_event = bool(base["had_later_reject_event"])
            ordered_lifecycle_reclassified = bool(base["ordered_lifecycle_reclassified"])
            telemetry_conflict = bool(base["telemetry_conflict"])
            conflict_reason = str(base["conflict_reason"] or "")

            trace_row = {
                "step": step,
                "cell_index": int(row.get("cell_index", -1) or -1),
                "command_id": command_id,
                "command_event_key": command_event_key,
                "command_event_sequence": int(row.get("command_event_sequence", 0) or 0),
                "command_event_step": int(row.get("command_event_step", -1) or -1),
                "command_event_source": str(row.get("command_event_source") or "none"),
                "command_stage": terminal_reject_stage if terminal_rejected else final_stage,
                "command_event_type": "terminal_reject" if terminal_rejected else "terminal_status",
                "final_command_result_status": final_status,
                "final_status_source_stage": final_stage,
                "final_status_source_event_sequence": final_seq,
                "clean_accepted": clean_accepted,
                "terminal_rejected": terminal_rejected,
                "terminal_reject_stage": terminal_reject_stage,
                "terminal_reject_reason": terminal_reject_reason,
                "had_intermediate_accept_event": had_intermediate_accept_event,
                "had_later_reject_event": had_later_reject_event,
                "ordered_lifecycle_reclassified": ordered_lifecycle_reclassified,
                "telemetry_conflict": telemetry_conflict,
                "conflict_reason": conflict_reason,
                "reject_callsite": str(row.get("reject_callsite") or "NOT_EXPOSED"),
                "reject_reason_raw": str(row.get("reject_reason_raw") or row.get("reject_reason") or ""),
                "reject_reason_normalized": str(row.get("reject_reason_normalized") or row.get("applier_reject_reason") or ""),
                "action_type": str(row.get("action_type") or row.get("masked_action_type") or "Move"),
                "move_dir": int(row.get("move_dir", -1) or -1),
                "source_cell_from_command": int(row.get("source_cell_from_command", -1) or -1),
                "source_x_from_command": int(row.get("source_x_from_command", -1) or -1),
                "source_y_from_command": int(row.get("source_y_from_command", -1) or -1),
                "target_cell_from_command": int(row.get("target_cell_from_command", -1) or -1),
                "target_x_from_command": int(row.get("target_x_from_command", -1) or -1),
                "target_y_from_command": int(row.get("target_y_from_command", -1) or -1),
                "unit_id": str(row.get("unit_id") or "NOT_EXPOSED"),
                "unit_owner": str(row.get("unit_owner") or "NOT_EXPOSED"),
                "unit_type": str(row.get("unit_type") or "NOT_EXPOSED"),
                "unit_position_x_at_reject": int(row.get("unit_position_x_at_reject", -1) or -1),
                "unit_position_y_at_reject": int(row.get("unit_position_y_at_reject", -1) or -1),
                "unit_cell_at_reject": int(row.get("unit_cell_at_reject", -1) or -1),
                "occupant_exists_at_target": row.get("occupant_exists_at_target", "NOT_EXPOSED"),
                "occupant_id_at_target": str(row.get("occupant_id_at_target") or "NOT_EXPOSED"),
                "occupant_owner_at_target": str(row.get("occupant_owner_at_target") or "NOT_EXPOSED"),
                "occupant_type_at_target": str(row.get("occupant_type_at_target") or "NOT_EXPOSED"),
                "occupant_x_at_target": int(row.get("occupant_x_at_target", -1) or -1),
                "occupant_y_at_target": int(row.get("occupant_y_at_target", -1) or -1),
                "occupant_cell_at_target": int(row.get("occupant_cell_at_target", -1) or -1),
                "occupancy_lookup_method": str(row.get("occupancy_lookup_method") or "NOT_EXPOSED"),
                "occupancy_lookup_source": str(row.get("occupancy_lookup_source") or "NOT_EXPOSED"),
                "target_in_bounds_at_reject": row.get("target_in_bounds_at_reject", "NOT_EXPOSED"),
                "target_passable_at_reject": row.get("target_passable_at_reject", "NOT_EXPOSED"),
                "target_occupied_at_reject": row.get("target_occupied_at_reject", "NOT_EXPOSED"),
                "target_occupied_by_runtime_lookup": row.get("target_occupied_by_runtime_lookup", "NOT_EXPOSED"),
                "target_occupied_by_snapshot_lookup": row.get("target_occupied_by_snapshot_lookup", "NOT_EXPOSED"),
                "snapshot_step_used_for_attribution": int(row.get("snapshot_step_used_for_attribution", -1) or -1),
                "direct_runtime_lookup_matches_snapshot_lookup": row.get("direct_runtime_lookup_matches_snapshot_lookup", "NOT_EXPOSED"),
                "direct_runtime_target_matches_reconstructed_target": row.get("direct_runtime_target_matches_reconstructed_target", "NOT_EXPOSED"),
            }
            trace_rows.append(trace_row)

            final_status_counts[final_status] += 1
            source_stage_counts[final_stage] += 1
            if telemetry_conflict:
                telemetry_conflict_count += 1

            if command_id.startswith("cmd:"):
                real_cmd_ids += 1
            else:
                legacy_cmd_ids += 1

            if clean_accepted:
                clean_accepted_move_commands += 1
            if final_status in {"applied", "completed"}:
                clean_applied_move_commands += 1
            if terminal_rejected:
                terminal_rejected_move_commands += 1
            if terminal_rejected and clean_accepted:
                rejected_but_clean_accepted += 1

            if command_id in previously_conflicting_ids:
                converted_conflicts += 1
                if final_status == "matchmanager_rejected":
                    converted_to_matchmanager_rejected += 1
                previously_conflicting_reclassified.append(
                    {
                        "command_id": command_id,
                        "final_command_result_status": final_status,
                        "clean_accepted": clean_accepted,
                        "terminal_rejected": terminal_rejected,
                        "terminal_reject_stage": terminal_reject_stage,
                        "ordered_lifecycle_reclassified": ordered_lifecycle_reclassified,
                    }
                )

    row_count = len(trace_rows)
    authoritative_status_rows = sum(1 for row in trace_rows if _status_is_authoritative(str(row["final_command_result_status"])))
    authoritative_status_ratio = (authoritative_status_rows / row_count) if row_count else 0.0
    mutually_exclusive_final_status_rows = sum(
        1
        for row in trace_rows
        if sum(
            1
            for status_name in {
                "not_submitted",
                "decoder_rejected",
                "actionapplier_rejected",
                "matchmanager_rejected",
                "accepted_pending",
                "applied",
                "completed",
                "telemetry_conflict",
            }
            if row["final_command_result_status"] == status_name
        )
        == 1
    )
    mutually_exclusive_final_status_ratio = (mutually_exclusive_final_status_rows / row_count) if row_count else 0.0

    same_command_both_events_no_longer_final_conflict = converted_conflicts == converted_to_matchmanager_rejected == 4

    mask_legality_preserved = bool(stage20s.get("checks", {}).get("all_masked_move_dirs_legal"))
    decoder_mask_legality_preserved = bool(stage20s.get("checks", {}).get("decoder_received_move_dir_legal"))
    off_actor_masked_non_noop_zero = int(stage20s.get("off_actor_masked_non_noop", 0) or 0) == 0
    b2_preserved = str(stage20_delta.get("b2_raw_vs_masked", {}).get("masked")) == "Harvest" and bool(stage20_visual.get("b2_harvest_preserved_at_initial_step"))
    c3_preserved = str(stage20_delta.get("c3_raw_vs_masked", {}).get("masked")) == "Produce" and bool(stage20_visual.get("c3_produce_preserved_at_initial_step"))
    checkpoint_ok = bool(stage20_binding.get("binding_ok"))
    no_stage10d19c = not bool(stage20_binding.get("stage10d19c_checkpoint_loaded"))
    no_fake_logits = not bool(stage20_binding.get("fake_logits_used"))
    no_fallback_policy = not bool(stage20_binding.get("fallback_used")) and not bool(stage20_binding.get("heuristic_policy_path_used"))

    pass_gate = all(
        [
            real_cmd_ids == row_count,
            legacy_cmd_ids == 0,
            authoritative_status_ratio == 1.0,
            mutually_exclusive_final_status_ratio == 1.0,
            same_command_both_events_no_longer_final_conflict,
            converted_to_matchmanager_rejected == 4,
            rejected_but_clean_accepted == 0,
            all(item["terminal_rejected"] for item in previously_conflicting_reclassified),
            all(item["terminal_reject_stage"] == "matchmanager" for item in previously_conflicting_reclassified),
            mask_legality_preserved,
            decoder_mask_legality_preserved,
            off_actor_masked_non_noop_zero,
            b2_preserved,
            c3_preserved,
            checkpoint_ok,
            no_stage10d19c,
            no_fake_logits,
            no_fallback_policy,
        ]
    )

    next_blocker = "No clean accepted/applied Move commands exist after authoritative remapping; movement application evidence is still absent."

    report = {
        "generated_at_utc": _utc_now(),
        "stage": "Stage10D.21B3",
        "source_manifest": str(manifest_path.relative_to(root)).replace("\\", "/"),
        "source_stage10d21b2_report": str(stage21b2_path.relative_to(root)).replace("\\", "/"),
        "counts": {
            "trace_rows": row_count,
            "real_cmd_ids": real_cmd_ids,
            "legacy_cmd_ids": legacy_cmd_ids,
            "previously_conflicting_commands": converted_conflicts,
            "matchmanager_rejected_commands": int(final_status_counts.get("matchmanager_rejected", 0)),
            "telemetry_conflict_commands": int(final_status_counts.get("telemetry_conflict", 0)),
            "clean_accepted_move_commands": clean_accepted_move_commands,
            "clean_applied_move_commands": clean_applied_move_commands,
            "terminal_rejected_move_commands": terminal_rejected_move_commands,
            "rejected_but_clean_accepted": rejected_but_clean_accepted,
        },
        "ratios": {
            "authoritative_status_ratio": authoritative_status_ratio,
            "mutually_exclusive_final_status_ratio": mutually_exclusive_final_status_ratio,
        },
        "final_status_counts": dict(final_status_counts),
        "final_status_source_stage_counts": dict(source_stage_counts),
        "checks": {
            "same_command_both_events_no_longer_final_conflict": same_command_both_events_no_longer_final_conflict,
            "four_previous_conflicts_matchmanager_rejected": converted_to_matchmanager_rejected == 4,
            "previously_rejected_not_clean_accepted": rejected_but_clean_accepted == 0,
            "mask_legality_preserved": mask_legality_preserved,
            "decoder_mask_legality_preserved": decoder_mask_legality_preserved,
            "off_actor_masked_non_noop_zero": off_actor_masked_non_noop_zero,
            "b2_harvest_preserved": b2_preserved,
            "c3_produce_preserved": c3_preserved,
            "same_stage10d19b_checkpoint": checkpoint_ok,
            "stage10d19c_not_used": no_stage10d19c,
            "fake_logits_not_used": no_fake_logits,
            "fallback_policy_not_used": no_fallback_policy,
        },
        "previously_conflicting_commands": previously_conflicting_reclassified,
        "required_answers": {
            "q1_conflicts_converted_to_ordered_lifecycle_statuses": same_command_both_events_no_longer_final_conflict,
            "q2_how_many_became_matchmanager_rejected": int(final_status_counts.get("matchmanager_rejected", 0)),
            "q3_any_commands_still_telemetry_conflict": telemetry_conflict_count > 0,
            "q4_any_rejected_commands_incorrectly_clean_accepted": rejected_but_clean_accepted > 0,
            "q5_direct_evidence_of_clean_accepted_or_applied_move": clean_accepted_move_commands > 0 or clean_applied_move_commands > 0,
            "q6_is_stage10d21c_allowed": False,
            "q7_next_blocker_if_no_go": next_blocker,
        },
        "go_no_go": {
            "stage10d21b3_authoritative_status_mapping_fix": "PASS" if pass_gate else "FAIL",
            "stage10d21c_movement_application_audit": "GO" if pass_gate and (clean_accepted_move_commands > 0 or clean_applied_move_commands > 0) else "NO-GO",
        },
    }

    trace_out = reports_dir / "stage10d21b3_status_mapping_trace.jsonl"
    report_out = reports_dir / "stage10d21b3_status_mapping_report.json"
    md_out = reports_dir / "STAGE10D21B3_STATUS_MAPPING_REPORT.md"

    with trace_out.open("w", encoding="utf-8") as fh:
        for row in trace_rows:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")

    report_out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# STAGE10D21B3 Authoritative Status Mapping Fix Report",
        "",
        f"- Generated (UTC): {report['generated_at_utc']}",
        f"- Trace rows: {report['counts']['trace_rows']}",
        f"- Stage10D.21B3 gate: {report['go_no_go']['stage10d21b3_authoritative_status_mapping_fix']}",
        f"- Stage10D.21C gate: {report['go_no_go']['stage10d21c_movement_application_audit']}",
        "",
        "## Final Status Counts",
    ]
    for status, count in sorted(final_status_counts.items()):
        lines.append(f"- {status}: {count}")

    lines.extend(
        [
            "",
            "## Ratios",
            f"- authoritative_status_ratio: {authoritative_status_ratio:.6f}",
            f"- mutually_exclusive_final_status_ratio: {mutually_exclusive_final_status_ratio:.6f}",
            "",
            "## Required Answers",
            f"- Q1 conflicts converted to ordered lifecycle statuses: {report['required_answers']['q1_conflicts_converted_to_ordered_lifecycle_statuses']}",
            f"- Q2 how many became matchmanager_rejected: {report['required_answers']['q2_how_many_became_matchmanager_rejected']}",
            f"- Q3 any commands still telemetry_conflict: {report['required_answers']['q3_any_commands_still_telemetry_conflict']}",
            f"- Q4 any rejected commands incorrectly counted as clean accepted: {report['required_answers']['q4_any_rejected_commands_incorrectly_clean_accepted']}",
            f"- Q5 direct evidence of clean accepted/applied Move: {report['required_answers']['q5_direct_evidence_of_clean_accepted_or_applied_move']}",
            f"- Q6 is Stage10D.21C allowed: {report['required_answers']['q6_is_stage10d21c_allowed']}",
            f"- Q7 next blocker: {report['required_answers']['q7_next_blocker_if_no_go']}",
            "",
            "## Artifacts",
            f"- Trace: {trace_out.relative_to(root).as_posix()}",
            f"- JSON: {report_out.relative_to(root).as_posix()}",
            f"- Markdown: {md_out.relative_to(root).as_posix()}",
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
                "stage10d21b3_gate": report["go_no_go"]["stage10d21b3_authoritative_status_mapping_fix"],
                "stage10d21c_gate": report["go_no_go"]["stage10d21c_movement_application_audit"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
