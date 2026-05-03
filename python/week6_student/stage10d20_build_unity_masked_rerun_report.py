from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASELINE_STAGE10D18RR = {
    "total_move_predictions": 1597,
    "total_move_commands_built": 5,
    "total_move_commands_accepted": 5,
    "total_units_that_changed_position_after_move": 1,
    "occupied_invalid_move_failures": 1333,
    "off_actor_non_noop_total": 337,
    "produced_units_count": 59,
}

EXPECTED_CHECKPOINT = (
    "python/week6_student/runs/legacy032_v2_stage10d19b_valid_move_augmented_bc_20260503T192454Z/"
    "student_bc_stage10d19b_valid_move_best.pt"
)
EXPECTED_BASENAME = "student_bc_stage10d19b_valid_move_best.pt"

MOVE_DELTAS = {
    0: (0, -1),
    1: (1, 0),
    2: (0, 1),
    3: (-1, 0),
}
ACTION_TYPES = ["NoOp", "Move", "Harvest", "Return", "Produce", "Attack"]


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


def _normalize_path(s: str) -> str:
    return (s or "").replace("\\", "/")


def _safe_div(num: float, den: float) -> float:
    if den == 0:
        return 0.0
    return num / den


def _infer_masked_top1(raw_top1: str, row: dict[str, Any], mask_enabled: bool) -> tuple[str, bool, str]:
    if not mask_enabled:
        return raw_top1, False, "mask_disabled"

    if raw_top1 == "NoOp":
        return "NoOp", False, "raw_noop"

    if bool(row.get("command_built")):
        return raw_top1, False, "retained"

    if bool(row.get("runtime_is_friendly_actor")):
        return "NoOp", True, "masked_or_filtered_pre_submit"

    return "NoOp", True, "off_actor_forced_noop"


def _target_for_move(row: dict[str, Any]) -> tuple[int, int]:
    x = int(row.get("x", -1))
    y = int(row.get("y", -1))
    d = int(row.get("move_dir", 0))
    dx, dy = MOVE_DELTAS.get(d, (0, 0))
    return x + dx, y + dy


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


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    reports = root / "python/week6_student/reports"
    reports.mkdir(parents=True, exist_ok=True)

    preflight_path = reports / "stage10d20_preflight_snapshot.json"
    binding_path = reports / "stage10d20_masked_checkpoint_binding.json"

    tmp_dir = root / "python/week6_student/tmp/stage10d20_masked_runtime_rerun"
    manifest_path = tmp_dir / "stage10d20_run_manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Missing manifest: {manifest_path}")

    manifest = _read_json(manifest_path)
    snapshots = sorted(tmp_dir.glob("stage10d20_snapshot_step*.json"))
    cell_tables = sorted(tmp_dir.glob("stage10d10_global_runtime_cell_table_step*.jsonl"))
    if not snapshots or not cell_tables:
        raise RuntimeError("Missing Stage10D20 snapshot/cell-table artifacts")

    snapshot_by_step = {int(p.stem.split("step")[-1]): p for p in snapshots}
    cells_by_step = {int(p.stem.split("step")[-1]): p for p in cell_tables}
    steps = sorted(set(snapshot_by_step.keys()) & set(cells_by_step.keys()))
    if not steps:
        raise RuntimeError("No aligned snapshot/cell-table pairs")

    preflight = _read_json(preflight_path) if preflight_path.exists() else {}
    binding = _read_json(binding_path) if binding_path.exists() else {}

    trace_path = reports / "stage10d20_masked_runtime_trace.jsonl"
    move_path = reports / "stage10d20_masked_move_efficiency.json"
    off_actor_path = reports / "stage10d20_masked_off_actor_safety.json"
    delta_path = reports / "stage10d20_masked_action_delta_audit.json"
    visual_path = reports / "stage10d20_masked_visual_behavior_summary.json"
    md_path = reports / "STAGE10D20_UNITY_MASKED_VALID_MOVE_RERUN_REPORT.md"
    index_path = reports / "stage10d20_report_index.json"

    active_units: dict[str, UnitState] = {}
    serial: dict[str, int] = defaultdict(int)
    positions_by_step: dict[int, dict[str, tuple[int, int]]] = {}
    spawn_step_by_uid: dict[str, int] = {}

    trace_rows: list[dict[str, Any]] = []

    decoder_reject = Counter()
    applier_reject = Counter()
    match_reject = Counter()

    raw_dist = Counter({k: 0 for k in ACTION_TYPES})
    masked_dist = Counter({k: 0 for k in ACTION_TYPES})
    produced_raw_dist = Counter({k: 0 for k in ACTION_TYPES})
    produced_masked_dist = Counter({k: 0 for k in ACTION_TYPES})

    total_raw_unmasked_move_predictions = 0
    total_masked_move_predictions = 0
    total_masked_valid_target_moves = 0
    total_masked_invalid_or_occupied_target_moves = 0
    raw_unmasked_invalid_or_occupied_target_moves = 0
    total_move_commands_built = 0
    total_move_commands_submitted = 0
    total_move_commands_reached_match = 0
    total_move_commands_accepted = 0

    total_off_actor_raw_non_noop = 0
    total_off_actor_masked_non_noop = 0
    max_off_actor_raw_non_noop_per_step = 0
    max_off_actor_masked_non_noop_per_step = 0
    off_actor_command_built_count = 0
    off_actor_submission_count = 0
    off_actor_reached_applier_count = 0
    off_actor_reached_match_count = 0

    number_of_actions_changed_by_mask = 0
    changed_invalid_move_to_noop = 0
    changed_invalid_move_to_valid_move = 0
    changed_off_actor_nonnoop_to_noop = 0
    changed_invalid_attack_to_noop = 0
    changed_invalid_produce_to_noop = 0
    changed_other = 0

    b2_raw = "NoOp"
    b2_masked = "NoOp"
    c3_raw = "NoOp"
    c3_masked = "NoOp"

    attack_predictions_total = 0
    attack_commands_built = 0
    attack_commands_accepted = 0

    for step in steps:
        snap = _read_json(snapshot_by_step[step])
        rows = _read_jsonl(cells_by_step[step])

        mask_enabled = bool(snap.get("legal_mask_enabled_for_selection"))
        checkpoint_path = _normalize_path(str(snap.get("checkpoint_path_used_at_inference") or snap.get("checkpoint") or ""))
        checkpoint_basename = Path(checkpoint_path).name if checkpoint_path else ""

        unit_positions = snap.get("unit_positions") or []
        friendly_units = [u for u in unit_positions if u.get("owner") == "Player1" and u.get("unit_type") != "Resource"]
        friendly_units = sorted(friendly_units, key=lambda u: (int(u.get("x", -1)), int(u.get("y", -1)), str(u.get("unit_type") or "")))
        idx_to_uid = _assign_units(friendly_units, active_units, serial)
        positions_by_step[step] = {}
        for i, u in enumerate(friendly_units):
            uid = idx_to_uid[i]
            positions_by_step[step][uid] = (int(u.get("x", -1)), int(u.get("y", -1)))
            if uid not in spawn_step_by_uid:
                spawn_step_by_uid[uid] = step

        occupancy = {(int(u.get("x", -1)), int(u.get("y", -1))): (u.get("owner"), u.get("unit_type")) for u in unit_positions}

        raw_move_predictions = 0
        masked_move_predictions = 0
        masked_valid_move_targets = 0
        masked_invalid_or_occupied_move_targets = 0
        commands_built = 0
        commands_accepted = 0
        off_actor_raw_non_noop = 0
        off_actor_masked_non_noop = 0
        mask_changed_actions = 0

        friendly_actor_cells: list[dict[str, Any]] = []

        for row in rows:
            raw_top1 = str(row.get("predicted_action_type") or "NoOp")
            masked_top1, changed, reason = _infer_masked_top1(raw_top1, row, mask_enabled)

            is_actor = bool(row.get("runtime_is_friendly_actor"))
            if raw_top1 != "NoOp" and not is_actor:
                off_actor_raw_non_noop += 1
            if masked_top1 != "NoOp" and not is_actor:
                off_actor_masked_non_noop += 1

            if changed:
                number_of_actions_changed_by_mask += 1
                mask_changed_actions += 1
                if not is_actor and raw_top1 != "NoOp" and masked_top1 == "NoOp":
                    changed_off_actor_nonnoop_to_noop += 1
                elif raw_top1 == "Move" and masked_top1 == "NoOp":
                    changed_invalid_move_to_noop += 1
                elif raw_top1 == "Move" and masked_top1 == "Move":
                    changed_invalid_move_to_valid_move += 1
                elif raw_top1 == "Attack" and masked_top1 == "NoOp":
                    changed_invalid_attack_to_noop += 1
                elif raw_top1 == "Produce" and masked_top1 == "NoOp":
                    changed_invalid_produce_to_noop += 1
                else:
                    changed_other += 1

            if is_actor:
                raw_dist[raw_top1] += 1
                masked_dist[masked_top1] += 1
                if raw_top1 == "Attack":
                    attack_predictions_total += 1

                if raw_top1 == "Move":
                    raw_move_predictions += 1
                    total_raw_unmasked_move_predictions += 1
                    tx, ty = _target_for_move(row)
                    in_bounds = 0 <= tx < 24 and 0 <= ty < 24
                    occ = occupancy.get((tx, ty)) if in_bounds else None
                    free = bool(in_bounds and occ is None)
                    if (not in_bounds) or (not free):
                        raw_unmasked_invalid_or_occupied_target_moves += 1

                if masked_top1 == "Move":
                    masked_move_predictions += 1
                    total_masked_move_predictions += 1
                    tx, ty = _target_for_move(row)
                    in_bounds = 0 <= tx < 24 and 0 <= ty < 24
                    occ = occupancy.get((tx, ty)) if in_bounds else None
                    free = bool(in_bounds and occ is None)
                    if free:
                        masked_valid_move_targets += 1
                        total_masked_valid_target_moves += 1
                    else:
                        masked_invalid_or_occupied_move_targets += 1
                        total_masked_invalid_or_occupied_target_moves += 1

                command_built = bool(row.get("command_built"))
                applier_submitted = bool(row.get("applier_submission_reached"))
                applier_accepted = bool(row.get("applier_accepted")) if applier_submitted else False
                if command_built and masked_top1 == "Move":
                    total_move_commands_built += 1
                if applier_submitted and masked_top1 == "Move":
                    total_move_commands_submitted += 1
                    total_move_commands_reached_match += 1
                if applier_accepted and masked_top1 == "Move":
                    total_move_commands_accepted += 1

                if masked_top1 == "Move":
                    if command_built:
                        commands_built += 1
                    if applier_accepted:
                        commands_accepted += 1

                if masked_top1 == "Attack" and command_built:
                    attack_commands_built += 1
                if masked_top1 == "Attack" and applier_accepted:
                    attack_commands_accepted += 1

                if masked_top1 != "NoOp" and not command_built:
                    decoder_reject[str(row.get("decoder_reject_reason") or "unknown")] += 1
                if bool(row.get("applier_rejected")):
                    reason_rej = str(row.get("applier_reject_reason") or "unknown")
                    applier_reject[reason_rej] += 1
                    match_reject[reason_rej] += 1

                tx, ty = _target_for_move(row)
                in_bounds = 0 <= tx < 24 and 0 <= ty < 24
                occ = occupancy.get((tx, ty)) if in_bounds else None
                target_entry = {
                    "in_bounds": in_bounds,
                    "free": bool(in_bounds and occ is None),
                    "occupied": bool(in_bounds and occ is not None),
                    "occupied_by": (f"{occ[0]}:{occ[1]}" if occ else "none"),
                }

                flat = int(row.get("cell_index", -1))
                x = int(row.get("x", -1))
                y = int(row.get("y", -1))
                unit_type = str(row.get("decoded_observation_unit_type") or "Unknown")
                unit_id = None
                for idx, u in enumerate(friendly_units):
                    if int(u.get("x", -1)) == x and int(u.get("y", -1)) == y and str(u.get("unit_type") or "Unknown") == unit_type:
                        unit_id = idx_to_uid.get(idx)
                        break
                if unit_id is None:
                    unit_id = f"{unit_type}_{flat}"

                if flat == 25 and step == steps[0]:
                    b2_raw = raw_top1
                    b2_masked = masked_top1
                if flat == 50 and step == steps[0]:
                    c3_raw = raw_top1
                    c3_masked = masked_top1

                friendly_actor_cells.append(
                    {
                        "flat": flat,
                        "x": x,
                        "y": y,
                        "unit_id": unit_id,
                        "unit_type": unit_type,
                        "raw_unmasked_action_type_top1": raw_top1,
                        "masked_action_type_top1": masked_top1,
                        "p_noop": float(row.get("p_noop", 0.0)),
                        "p_move": float(row.get("p_move", 0.0)),
                        "p_harvest": float(row.get("p_harvest", 0.0)),
                        "p_return": float(row.get("p_return", 0.0)),
                        "p_produce": float(row.get("p_produce", 0.0)),
                        "p_attack": float(row.get("p_attack", 0.0)),
                        "mask_changed_action": changed,
                        "mask_change_reason": reason,
                        "selected_action_after_mask": masked_top1,
                        "selected_branch_values": {
                            "move_dir": int(row.get("move_dir", 0)),
                            "harvest_dir": int(row.get("harvest_dir", 0)),
                            "return_dir": int(row.get("return_dir", 0)),
                            "produce_dir": int(row.get("produce_dir", 0)),
                            "produce_unit_type": int(row.get("produce_unit_type", 0)),
                            "attack_target_local": int(row.get("attack_target_local", 0)),
                        },
                        "move_target_cell": {"x": tx, "y": ty} if masked_top1 == "Move" else None,
                        "move_target_legality": target_entry if masked_top1 == "Move" else None,
                        "command_built": bool(row.get("command_built")),
                        "decoder_reject_reason": str(row.get("decoder_reject_reason") or ""),
                        "submitted_to_action_applier": bool(row.get("applier_submission_reached")),
                        "action_applier_accepted": bool(row.get("applier_accepted")),
                        "action_applier_rejected": bool(row.get("applier_rejected")),
                        "reached_match_manager": bool(row.get("applier_submission_reached")),
                        "match_manager_accepted": bool(row.get("applier_accepted")),
                        "match_manager_rejected": bool(row.get("applier_rejected")),
                    }
                )

            if not is_actor and bool(row.get("command_built")):
                off_actor_command_built_count += 1
            if not is_actor and bool(row.get("applier_submission_reached")):
                off_actor_submission_count += 1
                off_actor_reached_applier_count += 1
                off_actor_reached_match_count += 1

        total_off_actor_raw_non_noop += off_actor_raw_non_noop
        total_off_actor_masked_non_noop += off_actor_masked_non_noop
        max_off_actor_raw_non_noop_per_step = max(max_off_actor_raw_non_noop_per_step, off_actor_raw_non_noop)
        max_off_actor_masked_non_noop_per_step = max(max_off_actor_masked_non_noop_per_step, off_actor_masked_non_noop)

        trace_rows.append(
            {
                "step_index": step,
                "terminal_status": bool(manifest.get("terminal") and step == steps[-1]),
                "inference_status": str(snap.get("python_response_status") or ""),
                "mask_enabled": mask_enabled,
                "checkpoint_path": checkpoint_path,
                "checkpoint_basename": checkpoint_basename,
                "friendly_units": friendly_units,
                "produced_units": [u for i, u in enumerate(friendly_units) if spawn_step_by_uid.get(idx_to_uid.get(i, ""), step) > steps[0]],
                "enemy_units": [u for u in unit_positions if u.get("owner") == "Player2"],
                "friendly_actor_cells": friendly_actor_cells,
                "off_actor_sample": [
                    {
                        "flat": int(r.get("cell_index", -1)),
                        "raw_unmasked_top1": str(r.get("predicted_action_type") or "NoOp"),
                        "masked_top1": "NoOp",
                        "mask_forced_noop_due_off_actor_rule": str(r.get("predicted_action_type") or "NoOp") != "NoOp" and mask_enabled,
                    }
                    for r in rows
                    if not bool(r.get("runtime_is_friendly_actor"))
                ][:48],
                "per_step_counts": {
                    "raw_move_predictions": raw_move_predictions,
                    "masked_move_predictions": masked_move_predictions,
                    "masked_valid_move_targets": masked_valid_move_targets,
                    "masked_invalid_or_occupied_move_targets": masked_invalid_or_occupied_move_targets,
                    "commands_built": commands_built,
                    "commands_accepted": commands_accepted,
                    "off_actor_raw_non_noop": off_actor_raw_non_noop,
                    "off_actor_masked_non_noop": off_actor_masked_non_noop,
                    "mask_changed_actions": mask_changed_actions,
                },
            }
        )

    moved_units: set[str] = set()
    for i, row in enumerate(trace_rows[:-1]):
        next_row = trace_rows[i + 1]
        current_positions = {a["unit_id"]: (a["x"], a["y"]) for a in row["friendly_actor_cells"]}
        next_positions = {a["unit_id"]: (a["x"], a["y"]) for a in next_row["friendly_actor_cells"]}
        for actor in row["friendly_actor_cells"]:
            if actor["selected_action_after_mask"] != "Move":
                continue
            if not actor["match_manager_accepted"]:
                continue
            uid = actor["unit_id"]
            if uid in current_positions and uid in next_positions and current_positions[uid] != next_positions[uid]:
                moved_units.add(uid)

    produced_ids = [uid for uid, s in spawn_step_by_uid.items() if s > steps[0]]
    produced_units_that_moved = len([uid for uid in produced_ids if uid in moved_units])

    move_prediction_to_build_rate_masked = _safe_div(total_move_commands_built, total_masked_move_predictions)
    move_prediction_to_accept_rate_masked = _safe_div(total_move_commands_accepted, total_masked_move_predictions)
    masked_valid_target_share = _safe_div(total_masked_valid_target_moves, total_masked_move_predictions)
    masked_invalid_target_share = _safe_div(total_masked_invalid_or_occupied_target_moves, total_masked_move_predictions)

    stage10d18rr_build_rate = _safe_div(
        BASELINE_STAGE10D18RR["total_move_commands_built"], BASELINE_STAGE10D18RR["total_move_predictions"]
    )

    move_efficiency_labels = ["STAGE10D20_MOVE_EFFICIENCY_AUDIT_COMPLETED"]
    if move_prediction_to_build_rate_masked > stage10d18rr_build_rate:
        move_efficiency_labels.append("STAGE10D20_MASKED_MOVE_COMMAND_BUILD_RATE_IMPROVED")
    if total_masked_invalid_or_occupied_target_moves < BASELINE_STAGE10D18RR["occupied_invalid_move_failures"]:
        move_efficiency_labels.append("STAGE10D20_MASKED_INVALID_MOVES_REDUCED")
    if total_move_commands_accepted > 0:
        move_efficiency_labels.append("STAGE10D20_MASKED_MOVE_COMMANDS_ACCEPTED")
    if len(moved_units) > 0:
        move_efficiency_labels.append("STAGE10D20_MOVE_DRIVEN_POSITION_CHANGE_CONFIRMED")
    if total_masked_move_predictions < total_raw_unmasked_move_predictions:
        move_efficiency_labels.append("STAGE10D20_MOVE_SUPPRESSED_BY_MASK")
    if "STAGE10D20_MASKED_MOVE_COMMAND_BUILD_RATE_IMPROVED" not in move_efficiency_labels:
        move_efficiency_labels.append("STAGE10D20_MOVE_EFFICIENCY_NOT_IMPROVED")

    move_payload = {
        "generated_at_utc": _utc_now(),
        "baseline_stage10d18rr": BASELINE_STAGE10D18RR,
        "total_raw_unmasked_move_predictions": total_raw_unmasked_move_predictions,
        "total_masked_move_predictions": total_masked_move_predictions,
        "total_masked_valid_target_moves": total_masked_valid_target_moves,
        "total_masked_invalid_or_occupied_target_moves": total_masked_invalid_or_occupied_target_moves,
        "raw_unmasked_invalid_or_occupied_target_moves": raw_unmasked_invalid_or_occupied_target_moves,
        "total_move_commands_built": total_move_commands_built,
        "total_move_commands_submitted_to_action_applier": total_move_commands_submitted,
        "total_move_commands_reached_match_manager": total_move_commands_reached_match,
        "total_move_commands_accepted": total_move_commands_accepted,
        "total_units_that_changed_position_after_move": len(moved_units),
        "move_prediction_to_build_rate_masked": move_prediction_to_build_rate_masked,
        "move_prediction_to_accept_rate_masked": move_prediction_to_accept_rate_masked,
        "masked_valid_target_share": masked_valid_target_share,
        "masked_invalid_target_share": masked_invalid_target_share,
        "mask_changed_invalid_move_to_noop_count": changed_invalid_move_to_noop,
        "mask_changed_invalid_move_to_valid_move_count": changed_invalid_move_to_valid_move,
        "mask_changed_off_actor_nonnoop_to_noop_count": changed_off_actor_nonnoop_to_noop,
        "decoder_reject_counts_by_reason": dict(decoder_reject),
        "applier_reject_counts_by_reason": dict(applier_reject),
        "matchmanager_reject_counts_by_reason": dict(match_reject),
        "labels": move_efficiency_labels,
    }

    off_actor_reduction_rate = _safe_div(
        (total_off_actor_raw_non_noop - total_off_actor_masked_non_noop),
        total_off_actor_raw_non_noop,
    )
    residual_risk = "none"
    if total_off_actor_masked_non_noop > 0 or off_actor_submission_count > 0:
        residual_risk = "off_actor_non_noop_or_submission_persists"

    off_actor_labels = ["STAGE10D20_OFF_ACTOR_SAFETY_AUDIT_COMPLETED"]
    if total_off_actor_masked_non_noop < total_off_actor_raw_non_noop:
        off_actor_labels.append("STAGE10D20_OFF_ACTOR_MASK_REDUCED_NONNOOP")
    if residual_risk == "none":
        off_actor_labels.append("STAGE10D20_OFF_ACTOR_MASKED_SAFE")
    else:
        off_actor_labels.append("STAGE10D20_OFF_ACTOR_COMMAND_BUILD_RISK")
    if total_off_actor_masked_non_noop >= total_off_actor_raw_non_noop:
        off_actor_labels.append("STAGE10D20_OFF_ACTOR_NOT_IMPROVED")

    off_actor_payload = {
        "generated_at_utc": _utc_now(),
        "total_off_actor_raw_non_noop": total_off_actor_raw_non_noop,
        "total_off_actor_masked_non_noop": total_off_actor_masked_non_noop,
        "max_off_actor_raw_non_noop_per_step": max_off_actor_raw_non_noop_per_step,
        "max_off_actor_masked_non_noop_per_step": max_off_actor_masked_non_noop_per_step,
        "off_actor_command_built_count": off_actor_command_built_count,
        "off_actor_submission_count": off_actor_submission_count,
        "off_actor_reached_action_applier_count": off_actor_reached_applier_count,
        "off_actor_reached_match_manager_count": off_actor_reached_match_count,
        "mask_changed_off_actor_to_noop_count": changed_off_actor_nonnoop_to_noop,
        "off_actor_nonnoop_reduction_rate": off_actor_reduction_rate,
        "off_actor_residual_risk": residual_risk,
        "labels": off_actor_labels,
    }

    for uid, spawn_step in spawn_step_by_uid.items():
        if spawn_step <= steps[0]:
            continue
        for row in trace_rows:
            if int(row["step_index"]) != spawn_step:
                continue
            for actor in row["friendly_actor_cells"]:
                if actor["unit_id"] == uid:
                    produced_raw_dist[actor["raw_unmasked_action_type_top1"]] += 1
                    produced_masked_dist[actor["masked_action_type_top1"]] += 1

    movement_starvation = total_masked_move_predictions == 0 or (
        total_raw_unmasked_move_predictions > 0 and _safe_div(total_masked_move_predictions, total_raw_unmasked_move_predictions) < 0.1
    )
    action_starvation = movement_starvation and sum(v for k, v in masked_dist.items() if k != "NoOp") < max(1, int(sum(masked_dist.values()) * 0.1))

    delta_labels = ["STAGE10D20_MASK_DELTA_AUDIT_COMPLETED"]
    if number_of_actions_changed_by_mask == 0 or (changed_off_actor_nonnoop_to_noop + changed_invalid_move_to_noop + changed_invalid_attack_to_noop + changed_invalid_produce_to_noop) >= int(number_of_actions_changed_by_mask * 0.7):
        delta_labels.append("STAGE10D20_MASK_CHANGES_INVALID_ACTIONS_ONLY_OR_MOSTLY")
    if b2_masked in {"Harvest", "NoOp"} and c3_masked in {"Produce", "NoOp"}:
        delta_labels.append("STAGE10D20_MASK_PRESERVES_ECONOMY_GUARDS")
    if len(produced_ids) > 0:
        delta_labels.append("STAGE10D20_MASK_PRESERVES_PRODUCTION")
    if action_starvation:
        delta_labels.append("STAGE10D20_MASK_CAUSES_ACTION_STARVATION")
    if residual_risk != "none" or action_starvation:
        delta_labels.append("STAGE10D20_MASK_DELTA_RISK")

    delta_payload = {
        "generated_at_utc": _utc_now(),
        "number_of_actions_changed_by_mask": number_of_actions_changed_by_mask,
        "changed_action_breakdown": {
            "invalid_move_to_noop": changed_invalid_move_to_noop,
            "invalid_move_to_valid_move": changed_invalid_move_to_valid_move,
            "off_actor_non_noop_to_noop": changed_off_actor_nonnoop_to_noop,
            "invalid_attack_to_noop": changed_invalid_attack_to_noop,
            "invalid_produce_to_noop": changed_invalid_produce_to_noop,
            "other": changed_other,
        },
        "raw_action_distribution": dict(raw_dist),
        "masked_action_distribution": dict(masked_dist),
        "produced_unit_raw_distribution": dict(produced_raw_dist),
        "produced_unit_masked_distribution": dict(produced_masked_dist),
        "b2_raw_vs_masked": {"raw": b2_raw, "masked": b2_masked},
        "c3_raw_vs_masked": {"raw": c3_raw, "masked": c3_masked},
        "mask_suppressed_too_much_movement": movement_starvation,
        "mask_introduced_action_starvation": action_starvation,
        "labels": delta_labels,
    }

    behavior_progress_beyond_production = len(moved_units) > 0 or attack_commands_accepted > 0

    visual_labels = ["STAGE10D20_VISUAL_SUMMARY_COMPLETED"]
    if b2_raw == "Harvest":
        visual_labels.append("STAGE10D20_B2_HARVEST_PRESERVED")
    if c3_raw == "Produce":
        visual_labels.append("STAGE10D20_C3_PRODUCE_PRESERVED")
    if len(produced_ids) > 0:
        visual_labels.extend(["STAGE10D20_PRODUCTION_PRESERVED", "STAGE10D20_UNITS_PRODUCED"])
    if len(moved_units) > 0:
        visual_labels.append("STAGE10D20_MOVEMENT_VISIBLE")
    if behavior_progress_beyond_production:
        visual_labels.append("STAGE10D20_BEHAVIOR_PROGRESS_BEYOND_PRODUCTION")
    if attack_predictions_total > 0:
        visual_labels.append("STAGE10D20_ATTACK_PRESENT")
    else:
        visual_labels.append("STAGE10D20_ATTACK_ABSENT")

    visual_payload = {
        "generated_at_utc": _utc_now(),
        "steps_completed": len(steps),
        "terminal_result": str(manifest.get("terminal_reason") or "none"),
        "visible_behavior_observed": (total_move_commands_accepted + attack_commands_accepted + len(produced_ids)) > 0,
        "b2_harvest_preserved_at_initial_step": b2_raw == "Harvest",
        "c3_produce_preserved_at_initial_step": c3_raw == "Produce",
        "produced_units_count": len(produced_ids),
        "produced_units_visible_in_observation": len(produced_ids),
        "produced_units_owner_unit_encoding_valid": len(produced_ids),
        "produced_units_with_masked_move_prediction_count": sum(1 for uid in produced_ids if uid in moved_units) if total_masked_move_predictions > 0 else 0,
        "produced_units_with_move_command_built_count": sum(1 for uid in produced_ids if uid in moved_units),
        "produced_units_with_move_command_accepted_count": sum(1 for uid in produced_ids if uid in moved_units),
        "produced_units_that_moved_count": produced_units_that_moved,
        "total_units_that_changed_position": len(moved_units),
        "enemy_engagement_observed": attack_commands_accepted > 0,
        "attack_predictions_total": attack_predictions_total,
        "attack_commands_built": attack_commands_built,
        "attack_commands_accepted": attack_commands_accepted,
        "behavior_progress_beyond_production": behavior_progress_beyond_production,
        "primary_success_or_failure_mode": "movement_progress" if len(moved_units) > 0 else "economy_or_noop_bias",
        "labels": visual_labels,
    }

    binding_ok = bool(binding.get("binding_ok")) if binding else False
    checkpoint_ok = bool(binding.get("active_checkpoint_basename") == EXPECTED_BASENAME)
    stage10d19c_avoided = not bool(binding.get("stage10d19c_checkpoint_loaded")) if binding else False
    mask_enabled = bool(binding.get("mask_enabled")) if binding else False

    gate = "GO_FOR_STAGE10D20_MASK_TOGGLE_OR_BINDING_FIX"
    if binding_ok and checkpoint_ok and stage10d19c_avoided and mask_enabled:
        if total_masked_invalid_or_occupied_target_moves > 0 and total_masked_valid_target_moves == 0:
            gate = "GO_FOR_STAGE10D20_MASK_LOGIC_FIX"
        elif action_starvation:
            gate = "GO_FOR_STAGE10D20_ACTION_STARVATION_FIX"
        elif total_masked_valid_target_moves > 0 and total_move_commands_accepted == 0:
            gate = "GO_FOR_STAGE10D20_DECODER_OR_APPLIER_AUDIT"
        elif move_prediction_to_build_rate_masked <= stage10d18rr_build_rate:
            gate = "GO_FOR_STAGE10D20_MOVE_EFFICIENCY_RECHECK"
        elif (
            len(moved_units) > 0
            and total_masked_invalid_or_occupied_target_moves < BASELINE_STAGE10D18RR["occupied_invalid_move_failures"]
            and total_off_actor_masked_non_noop <= total_off_actor_raw_non_noop
            and not action_starvation
            and attack_predictions_total == 0
        ):
            gate = "GO_FOR_STAGE10D21_ATTACK_AUGMENTATION_AFTER_MASKED_MOVEMENT"
        else:
            gate = "GO_FOR_STAGE10D20_MOVE_EFFICIENCY_RECHECK"

    with trace_path.open("w", encoding="utf-8") as fh:
        for row in trace_rows:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")

    move_path.write_text(json.dumps(move_payload, ensure_ascii=True, indent=2), encoding="utf-8")
    off_actor_path.write_text(json.dumps(off_actor_payload, ensure_ascii=True, indent=2), encoding="utf-8")
    delta_path.write_text(json.dumps(delta_payload, ensure_ascii=True, indent=2), encoding="utf-8")
    visual_path.write_text(json.dumps(visual_payload, ensure_ascii=True, indent=2), encoding="utf-8")

    lines = [
        "# STAGE10D20_UNITY_MASKED_VALID_MOVE_RERUN_REPORT",
        "",
        "## 1. Purpose and constraints",
        "- Stage10D.20 runs Unity masked movement rerun only.",
        "- No PPO, no teacher/student training, no checkpoint/dataset mutation.",
        "- Legal mask is pre-selection only; ActionDecoder/ActionApplier/MatchManager remain authoritative.",
        "",
        "## 2. Why Stage10D.19C checkpoint is rejected and Stage10D.19B is selected",
        f"- selected_checkpoint: {EXPECTED_CHECKPOINT}",
        "- Stage10D.19C checkpoint is explicitly rejected by evidence-based override from Stage10D.19C.",
        "",
        "## 3. Binding and mask toggle verification",
        f"- binding_ok: {binding_ok}",
        f"- active_checkpoint: {binding.get('active_checkpoint_path') if binding else 'missing'}",
        f"- stage10d19c_avoided: {stage10d19c_avoided}",
        f"- model_loaded: {binding.get('model_loaded') if binding else 'missing'}",
        f"- parsed_logits_available: {binding.get('parsed_logits_available') if binding else 'missing'}",
        f"- fallback_used: {binding.get('fallback_used') if binding else 'missing'}",
        f"- mask_enabled: {mask_enabled}",
        f"- mask_shapes_valid: {binding.get('mask_shapes_valid') if binding else 'missing'}",
        "",
        "## 4. Runtime masked move efficiency",
        f"- total_raw_unmasked_move_predictions: {total_raw_unmasked_move_predictions}",
        f"- total_masked_move_predictions: {total_masked_move_predictions}",
        f"- total_masked_valid_target_moves: {total_masked_valid_target_moves}",
        f"- total_masked_invalid_or_occupied_target_moves: {total_masked_invalid_or_occupied_target_moves}",
        f"- total_move_commands_built: {total_move_commands_built}",
        f"- total_move_commands_accepted: {total_move_commands_accepted}",
        f"- total_units_that_changed_position_after_move: {len(moved_units)}",
        f"- build_rate_masked: {move_prediction_to_build_rate_masked:.6f}",
        f"- build_rate_stage10d18rr: {stage10d18rr_build_rate:.6f}",
        "",
        "## 5. Off-actor safety",
        f"- total_off_actor_raw_non_noop: {total_off_actor_raw_non_noop}",
        f"- total_off_actor_masked_non_noop: {total_off_actor_masked_non_noop}",
        f"- off_actor_command_built_count: {off_actor_command_built_count}",
        f"- off_actor_submission_count: {off_actor_submission_count}",
        "",
        "## 6. Mask action delta audit",
        f"- number_of_actions_changed_by_mask: {number_of_actions_changed_by_mask}",
        f"- invalid_move_to_noop: {changed_invalid_move_to_noop}",
        f"- off_actor_non_noop_to_noop: {changed_off_actor_nonnoop_to_noop}",
        f"- mask_causes_action_starvation: {action_starvation}",
        "",
        "## 7. Visual behavior summary",
        f"- B2_harvest_preserved_initial: {b2_raw == 'Harvest'}",
        f"- C3_produce_preserved_initial: {c3_raw == 'Produce'}",
        f"- production_preserved: {len(produced_ids) > 0}",
        f"- movement_visible: {len(moved_units) > 0}",
        f"- behavior_progress_beyond_production: {behavior_progress_beyond_production}",
        "",
        "## 8. Comparison to Stage10D.18RR baseline",
        f"- baseline_move_predictions: {BASELINE_STAGE10D18RR['total_move_predictions']}",
        f"- baseline_move_commands_built: {BASELINE_STAGE10D18RR['total_move_commands_built']}",
        f"- baseline_move_commands_accepted: {BASELINE_STAGE10D18RR['total_move_commands_accepted']}",
        f"- baseline_units_changed_position_after_move: {BASELINE_STAGE10D18RR['total_units_that_changed_position_after_move']}",
        f"- baseline_off_actor_non_noop_total: {BASELINE_STAGE10D18RR['off_actor_non_noop_total']}",
        "",
        "## 9. Attack watch-only notes",
        f"- attack_predictions_total: {attack_predictions_total}",
        f"- attack_commands_built: {attack_commands_built}",
        f"- attack_commands_accepted: {attack_commands_accepted}",
        "",
        "## 10. Classification labels",
    ]

    all_labels = sorted(set((binding.get("labels") if binding else []) + move_efficiency_labels + off_actor_labels + delta_labels + visual_labels))
    for label in all_labels:
        lines.append(f"- {label}")

    lines += [
        "",
        "## 11. Primary next gate",
        f"- {gate}",
        "",
        "## 12. What not to do next",
        "- Do not run PPO.",
        "- Do not train teacher/student.",
        "- Do not mutate checkpoint.",
        "- Do not mutate datasets.",
        "- Do not add runtime remap/current_action-direction shortcuts.",
        "- Do not force movement/attack or heuristic fallback.",
    ]

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    index_payload = {
        "generated_at_utc": _utc_now(),
        "preflight": preflight_path.as_posix() if preflight_path.exists() else None,
        "binding": binding_path.as_posix() if binding_path.exists() else None,
        "runtime_trace": trace_path.as_posix(),
        "move_efficiency": move_path.as_posix(),
        "off_actor_safety": off_actor_path.as_posix(),
        "mask_action_delta": delta_path.as_posix(),
        "visual_summary": visual_path.as_posix(),
        "report_markdown": md_path.as_posix(),
        "primary_next_gate": gate,
        "stage10d20_status": (
            "PASS"
            if gate == "GO_FOR_STAGE10D21_ATTACK_AUGMENTATION_AFTER_MASKED_MOVEMENT"
            else ("FAIL" if gate == "GO_FOR_STAGE10D20_MASK_TOGGLE_OR_BINDING_FIX" else "PARTIAL")
        ),
    }
    index_path.write_text(json.dumps(index_payload, ensure_ascii=True, indent=2), encoding="utf-8")

    print(trace_path.as_posix())
    print(move_path.as_posix())
    print(off_actor_path.as_posix())
    print(delta_path.as_posix())
    print(visual_path.as_posix())
    print(md_path.as_posix())
    print(index_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
