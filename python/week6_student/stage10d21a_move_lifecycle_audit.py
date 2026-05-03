from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MOVE_DELTAS = {
    0: (0, -1),
    1: (1, 0),
    2: (0, 1),
    3: (-1, 0),
}

CANONICAL_STATUSES = {
    "not_submitted",
    "decoder_rejected",
    "applier_rejected",
    "matchmanager_rejected",
    "accepted_pending",
    "applied",
    "completed",
}


@dataclass
class UnitState:
    unit_id: str
    unit_type: str
    x: int
    y: int


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


def _bool_mask(mask: Any) -> list[bool]:
    if not isinstance(mask, list):
        return []
    return [bool(v) for v in mask]


def _assign_units(friendly_units: list[dict[str, Any]], active: dict[str, UnitState], serial: dict[str, int]) -> dict[int, str]:
    by_index: dict[int, str] = {}
    matched: set[str] = set()

    for idx, unit in enumerate(friendly_units):
        x = int(unit.get("x", -1))
        y = int(unit.get("y", -1))
        ut = str(unit.get("unit_type") or "Unknown")

        exact = None
        nearest = None
        nearest_d = 999
        for uid, s in active.items():
            if uid in matched or s.unit_type != ut:
                continue
            if s.x == x and s.y == y:
                exact = uid
                break
            d = abs(s.x - x) + abs(s.y - y)
            if d < nearest_d:
                nearest_d = d
                nearest = uid

        chosen = exact
        if chosen is None and nearest is not None and nearest_d <= 1:
            chosen = nearest
        if chosen is None:
            serial[ut] += 1
            chosen = f"{ut}_{serial[ut]:03d}"
            active[chosen] = UnitState(chosen, ut, x, y)
        else:
            s = active[chosen]
            s.x = x
            s.y = y

        matched.add(chosen)
        by_index[idx] = chosen

    present = set(by_index.values())
    for uid in list(active.keys()):
        if uid not in present:
            del active[uid]

    return by_index


def _target_from_move(x: int, y: int, move_dir: int) -> tuple[int, int, int]:
    dx, dy = MOVE_DELTAS.get(move_dir, (0, 0))
    tx, ty = x + dx, y + dy
    flat = ty * 24 + tx if 0 <= tx < 24 and 0 <= ty < 24 else -1
    return tx, ty, flat


def _occupancy_payload(occupancy_by_xy: dict[tuple[int, int], dict[str, Any]], x: int, y: int) -> dict[str, Any]:
    in_bounds = 0 <= x < 24 and 0 <= y < 24
    occ = occupancy_by_xy.get((x, y)) if in_bounds else None
    return {
        "in_bounds": bool(in_bounds),
        "occupied": bool(in_bounds and occ is not None),
        "free": bool(in_bounds and occ is None),
        "occupied_by": (dict(occ) if occ is not None else None),
    }


def _canonical_status(
    command_built: bool,
    command_submitted: bool,
    decoder_reject_reason: str,
    applier_submitted: bool,
    applier_accepted: bool,
    applier_rejected: bool,
    applier_reject_reason: str,
    has_displacement: bool,
) -> tuple[str, bool, bool, str]:
    legacy_conflict = bool(applier_accepted and applier_rejected)
    clean_accepted = bool(applier_submitted and applier_accepted and not applier_rejected)

    conflict_reason = ""
    if legacy_conflict:
        conflict_reason = "applier_accepted_and_applier_rejected_are_both_true"

    if not command_submitted:
        return "not_submitted", clean_accepted, legacy_conflict, conflict_reason
    if decoder_reject_reason and not command_built:
        return "decoder_rejected", clean_accepted, legacy_conflict, conflict_reason
    if applier_rejected and not applier_accepted:
        rej = applier_reject_reason.lower()
        if "matchmanager" in rej:
            return "matchmanager_rejected", clean_accepted, legacy_conflict, conflict_reason
        return "applier_rejected", clean_accepted, legacy_conflict, conflict_reason

    if clean_accepted:
        if has_displacement:
            return "completed", clean_accepted, legacy_conflict, conflict_reason
        return "accepted_pending", clean_accepted, legacy_conflict, conflict_reason

    if legacy_conflict:
        if has_displacement:
            return "applied", clean_accepted, legacy_conflict, conflict_reason
        return "accepted_pending", clean_accepted, legacy_conflict, conflict_reason

    return "not_submitted", clean_accepted, legacy_conflict, conflict_reason


def _classify_a_to_i(
    *,
    legacy_conflict: bool,
    clean_accepted: bool,
    canonical_status: str,
    command_built: bool,
    decoder_reject_reason: str,
    applier_rejected: bool,
    applier_reject_reason: str,
    mm_accepted: bool,
    displacement_offset: int | None,
    tracking_failed_but_movement_evidence: bool,
    window_has_full_lookahead: bool,
    blocked_by_target_occupancy_window: bool,
) -> tuple[str, str]:
    if legacy_conflict and not clean_accepted:
        return "H", "legacy_conflict_without_clean_acceptance"

    if decoder_reject_reason and not command_built:
        return "A", "decoder_rejected"

    if applier_rejected and ("matchmanager" not in applier_reject_reason.lower()):
        return "B", "applier_rejected"

    if applier_rejected and ("matchmanager" in applier_reject_reason.lower()):
        return "C", "matchmanager_rejected"

    if tracking_failed_but_movement_evidence:
        return "I", "movement_evidence_but_identity_tracking_failed"

    if clean_accepted and displacement_offset is not None:
        return "E", "movement_completed"

    if clean_accepted and mm_accepted and blocked_by_target_occupancy_window:
        return "F", "accepted_but_target_occupied_or_state_blocked"

    if clean_accepted and mm_accepted and (not window_has_full_lookahead):
        return "G", "accepted_but_insufficient_tick_window"

    if clean_accepted and mm_accepted and canonical_status in {"accepted_pending", "applied"}:
        return "D", "accepted_pending_movement"

    if clean_accepted and mm_accepted:
        return "G", "accepted_but_no_movement_within_window"

    return "H", "telemetry_conflict_or_inconclusive_acceptance"


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    reports = root / "python/week6_student/reports"
    reports.mkdir(parents=True, exist_ok=True)

    tmp_dir = root / "python/week6_student/tmp/stage10d20_masked_runtime_rerun"
    manifest_path = tmp_dir / "stage10d20_run_manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Missing manifest: {manifest_path}")

    snapshots = sorted(tmp_dir.glob("stage10d20_snapshot_step*.json"))
    cell_tables = sorted(tmp_dir.glob("stage10d10_global_runtime_cell_table_step*.jsonl"))
    if not snapshots or not cell_tables:
        raise RuntimeError("Missing Stage10D20 snapshot/cell-table artifacts")

    snapshot_by_step = {int(p.stem.split("step")[-1]): p for p in snapshots}
    cells_by_step = {int(p.stem.split("step")[-1]): p for p in cell_tables}
    steps = sorted(set(snapshot_by_step.keys()) & set(cells_by_step.keys()))
    if not steps:
        raise RuntimeError("No aligned snapshot/cell-table pairs")

    step_rows: dict[int, list[dict[str, Any]]] = {step: _read_jsonl(cells_by_step[step]) for step in steps}
    step_snap: dict[int, dict[str, Any]] = {step: _read_json(snapshot_by_step[step]) for step in steps}

    active_units: dict[str, UnitState] = {}
    serial: dict[str, int] = defaultdict(int)
    positions_by_step: dict[int, dict[str, tuple[int, int]]] = {}
    uid_by_cell_step: dict[int, dict[tuple[int, int, str], str]] = {}
    occupancy_by_step: dict[int, dict[tuple[int, int], dict[str, Any]]] = {}

    for step in steps:
        unit_positions = step_snap[step].get("unit_positions") or []
        friendly_units = [u for u in unit_positions if u.get("owner") == "Player1" and u.get("unit_type") != "Resource"]
        friendly_units = sorted(
            friendly_units,
            key=lambda u: (int(u.get("x", -1)), int(u.get("y", -1)), str(u.get("unit_type") or "")),
        )
        idx_to_uid = _assign_units(friendly_units, active_units, serial)

        positions_by_step[step] = {}
        uid_by_cell_step[step] = {}
        for i, u in enumerate(friendly_units):
            uid = idx_to_uid[i]
            x = int(u.get("x", -1))
            y = int(u.get("y", -1))
            ut = str(u.get("unit_type") or "Unknown")
            positions_by_step[step][uid] = (x, y)
            uid_by_cell_step[step][(x, y, ut)] = uid

        occupancy_by_step[step] = {}
        for u in unit_positions:
            x = int(u.get("x", -1))
            y = int(u.get("y", -1))
            occupancy_by_step[step][(x, y)] = {
                "owner": str(u.get("owner") or "Unknown"),
                "unit_type": str(u.get("unit_type") or "Unknown"),
            }

    trace_rows: list[dict[str, Any]] = []
    category_counts = Counter({k: 0 for k in "ABCDEFGHI"})
    canonical_counts = Counter({k: 0 for k in sorted(CANONICAL_STATUSES)})
    first_failure_counts = Counter()

    legal_masked_move_events = 0
    clean_accepted_count = 0
    legacy_conflict_count = 0
    matchmanager_accepted_count = 0
    command_set_or_queued_count = 0
    displacement_within_1_count = 0
    displacement_within_2_5_count = 0

    for step in steps:
        rows = step_rows[step]
        for row in rows:
            if str(row.get("masked_action_type") or "NoOp") != "Move":
                continue

            x = int(row.get("x", -1))
            y = int(row.get("y", -1))
            flat = int(row.get("cell_index", -1))
            unit_type = str(row.get("decoded_observation_unit_type") or "Unknown")
            owner = str(row.get("decoded_observation_owner") or "Unknown")
            uid = uid_by_cell_step.get(step, {}).get((x, y, unit_type), f"{unit_type}_{flat}")

            masked_move_dir = int(row.get("masked_move_dir", -1))
            decoder_received_move_dir = int(row.get("decoder_received_move_dir", -1))
            decoder_received_move_dir_legal = bool(row.get("decoder_received_move_dir_legal"))
            masked_move_dir_legal = bool(row.get("masked_move_dir_legal"))
            legal_move_dir_mask = _bool_mask(row.get("legal_move_dir_mask"))

            tx, ty, tflat = _target_from_move(x, y, masked_move_dir)
            source_before = positions_by_step.get(step, {}).get(uid)
            target_occ_before = _occupancy_payload(occupancy_by_step.get(step, {}), tx, ty)

            command_built = bool(row.get("command_built"))
            command_submitted = bool(row.get("command_submitted"))
            applier_submitted = bool(row.get("applier_submission_reached"))
            applier_accepted = bool(row.get("applier_accepted"))
            applier_rejected = bool(row.get("applier_rejected"))
            decoder_reject_reason = str(row.get("decoder_reject_reason") or "")
            applier_reject_reason = str(row.get("applier_reject_reason") or "")

            position_series: dict[int, dict[str, Any] | None] = {}
            action_series: dict[int, dict[str, Any]] = {}
            target_occ_series: dict[int, dict[str, Any]] = {}
            displacement_offset: int | None = None
            tracked_any = False

            for offset in range(1, 6):
                st = step + offset
                if st not in positions_by_step:
                    position_series[offset] = None
                    action_series[offset] = {
                        "value": None,
                        "availability": "step_not_available_in_artifacts",
                    }
                    target_occ_series[offset] = {
                        "in_bounds": None,
                        "occupied": None,
                        "free": None,
                        "occupied_by": None,
                        "availability": "step_not_available_in_artifacts",
                    }
                    continue

                pos = positions_by_step[st].get(uid)
                tracked_any = tracked_any or (pos is not None)
                position_series[offset] = {"x": pos[0], "y": pos[1]} if pos is not None else None
                action_series[offset] = {
                    "value": None,
                    "availability": "unit_action_state_not_exposed_in_snapshot",
                }
                target_occ_series[offset] = _occupancy_payload(occupancy_by_step[st], tx, ty)

                if displacement_offset is None and source_before is not None and pos is not None and pos != source_before:
                    displacement_offset = offset

            has_displacement = displacement_offset is not None

            canonical_status, clean_accepted, legacy_conflict, conflict_reason = _canonical_status(
                command_built=command_built,
                command_submitted=command_submitted,
                decoder_reject_reason=decoder_reject_reason,
                applier_submitted=applier_submitted,
                applier_accepted=applier_accepted,
                applier_rejected=applier_rejected,
                applier_reject_reason=applier_reject_reason,
                has_displacement=has_displacement,
            )
            if canonical_status not in CANONICAL_STATUSES:
                canonical_status = "not_submitted"
            canonical_counts[canonical_status] += 1

            mm_apply_called = applier_submitted
            mm_accepted = bool(applier_submitted and applier_accepted)
            mm_rejected = bool(applier_submitted and applier_rejected)
            mm_reject_reason = applier_reject_reason
            mm_enqueued_or_set = bool(mm_apply_called and mm_accepted)
            mm_existing_replaced = {
                "value": None,
                "availability": "existing_unit_action_not_exposed_in_artifacts",
            }

            source_after_apply = {
                "value": None,
                "availability": "position_immediately_after_applycommand_not_exposed_in_artifacts",
            }
            action_after_apply = {
                "value": None,
                "availability": "unit_action_immediately_after_applycommand_not_exposed_in_artifacts",
            }
            target_after_apply = {
                "in_bounds": None,
                "occupied": None,
                "free": None,
                "occupied_by": None,
                "availability": "target_occupancy_immediately_after_applycommand_not_exposed_in_artifacts",
            }

            window_has_full_lookahead = (step + 5) in positions_by_step
            blocked_by_target_occupancy_window = False
            for off in range(1, 6):
                occ = target_occ_series.get(off)
                if occ and occ.get("occupied"):
                    blocked_by_target_occupancy_window = True
                    break

            tracking_failed_but_movement_evidence = bool(
                not tracked_any
                and source_before is not None
                and any(
                    bool(t_occ.get("occupied"))
                    and isinstance(t_occ.get("occupied_by"), dict)
                    and t_occ["occupied_by"].get("owner") == owner
                    and t_occ["occupied_by"].get("unit_type") == unit_type
                    for t_occ in target_occ_series.values()
                    if isinstance(t_occ, dict)
                )
            )

            category_key, category_reason = _classify_a_to_i(
                legacy_conflict=legacy_conflict,
                clean_accepted=clean_accepted,
                canonical_status=canonical_status,
                command_built=command_built,
                decoder_reject_reason=decoder_reject_reason,
                applier_rejected=applier_rejected,
                applier_reject_reason=applier_reject_reason,
                mm_accepted=mm_accepted,
                displacement_offset=displacement_offset,
                tracking_failed_but_movement_evidence=tracking_failed_but_movement_evidence,
                window_has_full_lookahead=window_has_full_lookahead,
                blocked_by_target_occupancy_window=blocked_by_target_occupancy_window,
            )
            category_counts[category_key] += 1

            first_failure = "none"
            if category_key == "A":
                first_failure = "decoder"
            elif category_key == "B":
                first_failure = "action_applier"
            elif category_key == "C":
                first_failure = "match_manager"
            elif category_key == "H":
                first_failure = "telemetry_conflict"
            elif category_key in {"D", "F", "G"}:
                first_failure = "runtime_movement_window"
            elif category_key == "I":
                first_failure = "tracking"
            first_failure_counts[first_failure] += 1

            legal_masked_move_events += 1 if masked_move_dir_legal else 0
            clean_accepted_count += 1 if clean_accepted else 0
            legacy_conflict_count += 1 if legacy_conflict else 0
            matchmanager_accepted_count += 1 if mm_accepted else 0
            command_set_or_queued_count += 1 if mm_enqueued_or_set else 0
            displacement_within_1_count += 1 if displacement_offset == 1 else 0
            displacement_within_2_5_count += 1 if (displacement_offset is not None and 2 <= displacement_offset <= 5) else 0

            trace_rows.append(
                {
                    "step": step,
                    "unit_id": uid,
                    "source": {"x": x, "y": y, "flat": flat},
                    "target": {"x": tx, "y": ty, "flat": tflat},
                    "masked_move_dir": masked_move_dir,
                    "decoder_received_move_dir": decoder_received_move_dir,
                    "decoder_received_move_dir_legal": decoder_received_move_dir_legal,
                    "before_actionapplier": {
                        "unit_position": ({"x": source_before[0], "y": source_before[1]} if source_before is not None else None),
                        "unit_type": unit_type,
                        "owner": owner,
                        "unit_action_state": {
                            "value": None,
                            "availability": "unit_action_state_not_exposed_in_artifacts",
                        },
                        "busy_cooldown_remaining": {
                            "value": None,
                            "availability": "busy_cooldown_not_exposed_in_artifacts",
                        },
                        "target_occupancy": target_occ_before,
                        "target_passability": bool(target_occ_before.get("free")),
                        "target_in_bounds": bool(target_occ_before.get("in_bounds")),
                    },
                    "actionapplier": {
                        "received_command": applier_submitted,
                        "validation_result": {
                            "accepted": applier_accepted,
                            "rejected": applier_rejected,
                            "reject_reason": applier_reject_reason,
                        },
                        "accepted_flag": applier_accepted,
                        "rejected_flag": applier_rejected,
                        "reject_reason": applier_reject_reason,
                        "normalized_result_status": canonical_status,
                    },
                    "matchmanager": {
                        "applycommand_called": mm_apply_called,
                        "applycommand_return_status": ("accepted" if mm_accepted else ("rejected" if mm_rejected else "not_called")),
                        "command_accepted": mm_accepted,
                        "command_rejected": mm_rejected,
                        "reject_reason": mm_reject_reason,
                        "command_enqueued_or_set_on_unit": mm_enqueued_or_set,
                        "existing_unit_action_replaced": mm_existing_replaced,
                        "ignored_reason": (mm_reject_reason if mm_rejected else ""),
                    },
                    "after_command_application": {
                        "unit_position_immediately_after_applycommand": source_after_apply,
                        "unit_action_immediately_after_applycommand": action_after_apply,
                        "target_occupancy_immediately_after_applycommand": target_after_apply,
                    },
                    "after_simulation_advances": {
                        "position_by_tick_offset": position_series,
                        "action_by_tick_offset": action_series,
                        "target_occupancy_by_tick_offset": target_occ_series,
                        "movement_completed": bool(displacement_offset is not None),
                        "movement_completed_tick_offset": displacement_offset,
                    },
                    "telemetry_semantics": {
                        "canonical_status": canonical_status,
                        "clean_accepted": clean_accepted,
                        "legacy_status_conflict": legacy_conflict,
                        "conflict_reason": conflict_reason,
                        "legacy_fields": {
                            "command_built": command_built,
                            "command_submitted": command_submitted,
                            "applier_submitted": applier_submitted,
                            "applier_accepted": applier_accepted,
                            "applier_rejected": applier_rejected,
                            "decoder_reject_reason": decoder_reject_reason,
                            "applier_reject_reason": applier_reject_reason,
                            "command_result_status_legacy": str(row.get("command_result_status") or ""),
                            "legacy_status_conflict_field": bool(row.get("legacy_status_conflict")),
                        },
                    },
                    "classification": {
                        "category": category_key,
                        "category_reason": category_reason,
                        "first_failure_point": first_failure,
                    },
                }
            )

    if not trace_rows:
        raise RuntimeError("No masked Move events found in Stage10D.20S rerun artifacts")

    categories_present = {row["classification"]["category"] for row in trace_rows}
    all_classified_exactly_once = len(trace_rows) == sum(category_counts.values())

    movement_fix_go = bool(
        category_counts["E"] > 0 and category_counts["H"] == 0 and category_counts["I"] == 0 and category_counts["G"] == 0
    )
    telemetry_cleanup_go = bool(category_counts["H"] == 0 and legacy_conflict_count == 0)
    full_map_rerun_go = bool(movement_fix_go and telemetry_cleanup_go)

    report = {
        "generated_at_utc": _utc_now(),
        "stage": "Stage10D.21A",
        "source_stage": "Stage10D.20S rerun artifacts",
        "source_manifest": str(manifest_path.relative_to(root)).replace("\\", "/"),
        "steps_analyzed": len(steps),
        "last_step": steps[-1],
        "acceptance": {
            "all_events_classified_exactly_once": all_classified_exactly_once,
            "categories_present": sorted(categories_present),
            "pass": all_classified_exactly_once,
        },
        "counts": {
            "legal_masked_move_events_traced": legal_masked_move_events,
            "clean_accepted_move_commands": clean_accepted_count,
            "legacy_conflict_move_commands": legacy_conflict_count,
            "matchmanager_accepted_commands": matchmanager_accepted_count,
            "commands_set_or_queued_on_unit": command_set_or_queued_count,
            "commands_with_displacement_within_plus1": displacement_within_1_count,
            "commands_with_displacement_within_plus2_to_plus5": displacement_within_2_5_count,
        },
        "canonical_status_counts": dict(canonical_counts),
        "category_counts": dict(category_counts),
        "first_failure_point_counts": dict(first_failure_counts),
        "go_no_go": {
            "movement_application_fix": "GO" if movement_fix_go else "NO-GO",
            "command_status_telemetry_cleanup": "GO" if telemetry_cleanup_go else "NO-GO",
            "full_map_stage10d21_behavior_rerun": "GO" if full_map_rerun_go else "NO-GO",
        },
    }

    jsonl_path = reports / "stage10d21a_move_lifecycle_trace.jsonl"
    json_path = reports / "stage10d21a_move_lifecycle_report.json"
    md_path = reports / "STAGE10D21A_MOVE_LIFECYCLE_REPORT.md"

    with jsonl_path.open("w", encoding="utf-8") as f:
        for item in trace_rows:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# STAGE10D21A Move Lifecycle Report",
        "",
        f"- Generated (UTC): {report['generated_at_utc']}",
        f"- Source: {report['source_stage']}",
        f"- Steps analyzed: {report['steps_analyzed']} (last={report['last_step']})",
        f"- Acceptance pass: {report['acceptance']['pass']}",
        "",
        "## Classification Coverage (A..I)",
        f"- all_events_classified_exactly_once: {report['acceptance']['all_events_classified_exactly_once']}",
    ]
    for key in sorted("ABCDEFGHI"):
        lines.append(f"- category_{key}_count: {report['category_counts'].get(key, 0)}")

    lines.extend(
        [
            "",
            "## Required Counts",
            f"- legal_masked_move_events_traced: {report['counts']['legal_masked_move_events_traced']}",
            f"- clean_accepted_move_commands: {report['counts']['clean_accepted_move_commands']}",
            f"- legacy_conflict_move_commands: {report['counts']['legacy_conflict_move_commands']}",
            f"- matchmanager_accepted_commands: {report['counts']['matchmanager_accepted_commands']}",
            f"- commands_set_or_queued_on_unit: {report['counts']['commands_set_or_queued_on_unit']}",
            f"- commands_with_displacement_within_plus1: {report['counts']['commands_with_displacement_within_plus1']}",
            f"- commands_with_displacement_within_plus2_to_plus5: {report['counts']['commands_with_displacement_within_plus2_to_plus5']}",
            "",
            "## Canonical Status Counts",
        ]
    )
    for status in sorted(CANONICAL_STATUSES):
        lines.append(f"- {status}: {report['canonical_status_counts'].get(status, 0)}")

    lines.extend(
        [
            "",
            "## First Failure Points",
        ]
    )
    for k, v in sorted(report["first_failure_point_counts"].items()):
        lines.append(f"- {k}: {v}")

    lines.extend(
        [
            "",
            "## GO/NO-GO",
            f"- movement_application_fix: {report['go_no_go']['movement_application_fix']}",
            f"- command_status_telemetry_cleanup: {report['go_no_go']['command_status_telemetry_cleanup']}",
            f"- full_map_stage10d21_behavior_rerun: {report['go_no_go']['full_map_stage10d21_behavior_rerun']}",
            "",
            "## Artifacts",
            f"- Trace JSONL: {jsonl_path.relative_to(root).as_posix()}",
            f"- Report JSON: {json_path.relative_to(root).as_posix()}",
            f"- Report MD: {md_path.relative_to(root).as_posix()}",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "trace": jsonl_path.as_posix(),
                "report": json_path.as_posix(),
                "markdown": md_path.as_posix(),
                "pass": report["acceptance"]["pass"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
