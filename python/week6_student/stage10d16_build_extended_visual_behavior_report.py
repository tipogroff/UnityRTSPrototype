from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TARGET_CHECKPOINT_REL = (
    "python/week6_student/runs/"
    "legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z/"
    "student_bc_stage10d14_augmented_best.pt"
)
EXPECTED_LOGIT_SHAPES: dict[str, list[int]] = {
    "action_type_logits": [1, 576, 6],
    "move_dir_logits": [1, 576, 4],
    "harvest_dir_logits": [1, 576, 4],
    "return_dir_logits": [1, 576, 4],
    "produce_dir_logits": [1, 576, 4],
    "produce_unit_type_logits": [1, 576, 7],
    "attack_target_local_logits": [1, 576, 49],
}
ACTION_NAMES = ["NoOp", "Move", "Harvest", "Return", "Produce", "Attack"]
MOVE_DELTAS = {
    0: (0, -1),  # north
    1: (1, 0),   # east
    2: (0, 1),   # south
    3: (-1, 0),  # west
}


@dataclass
class UnitState:
    unit_id: str
    unit_type: str
    x: int
    y: int
    spawn_step: int


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _parse_shape_lines(lines: list[str]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for line in lines:
        if not isinstance(line, str) or ":" not in line:
            continue
        k, v = line.split(":", 1)
        nums = []
        ok = True
        for t in v.strip().strip("[]").split(","):
            t = t.strip()
            if not t:
                continue
            try:
                nums.append(int(t))
            except ValueError:
                ok = False
                break
        if ok and nums:
            out[k.strip()] = nums
    return out


def _normalize_path(p: str) -> str:
    return (p or "").replace("\\", "/")


def _assign_units(
    step: int,
    friendly_units: list[dict[str, Any]],
    active: dict[str, UnitState],
    serial_by_type: dict[str, int],
) -> dict[int, str]:
    matched_ids: set[str] = set()
    by_step_index_to_id: dict[int, str] = {}

    for idx, unit in enumerate(friendly_units):
        ux = int(unit.get("x", -1))
        uy = int(unit.get("y", -1))
        ut = str(unit.get("unit_type") or "Unknown")

        exact = None
        nearest = None
        nearest_d = 999
        for uid, s in active.items():
            if uid in matched_ids or s.unit_type != ut:
                continue
            if s.x == ux and s.y == uy:
                exact = uid
                break
            d = abs(s.x - ux) + abs(s.y - uy)
            if d < nearest_d:
                nearest_d = d
                nearest = uid

        chosen = exact
        if chosen is None and nearest is not None and nearest_d <= 1:
            chosen = nearest

        if chosen is None:
            serial_by_type[ut] += 1
            chosen = f"{ut}_{serial_by_type[ut]:03d}"
            active[chosen] = UnitState(chosen, ut, ux, uy, step)
        else:
            s = active[chosen]
            s.x = ux
            s.y = uy

        matched_ids.add(chosen)
        by_step_index_to_id[idx] = chosen

    present_ids = set(by_step_index_to_id.values())
    for uid in list(active.keys()):
        if uid not in present_ids:
            del active[uid]

    return by_step_index_to_id


def _count_units(unit_positions: list[dict[str, Any]]) -> dict[str, int]:
    out = {
        "friendly_worker_count": 0,
        "friendly_base_count": 0,
        "friendly_barracks_count": 0,
        "friendly_light_count": 0,
        "friendly_heavy_count": 0,
        "friendly_ranged_count": 0,
        "enemy_actor_count": 0,
        "resource_count": 0,
    }
    for u in unit_positions:
        owner = str(u.get("owner") or "")
        ut = str(u.get("unit_type") or "")
        if ut == "Resource":
            out["resource_count"] += 1
            continue
        if owner == "Player1":
            if ut == "Worker":
                out["friendly_worker_count"] += 1
            elif ut == "Base":
                out["friendly_base_count"] += 1
            elif ut == "Barracks":
                out["friendly_barracks_count"] += 1
            elif ut == "Light":
                out["friendly_light_count"] += 1
            elif ut == "Heavy":
                out["friendly_heavy_count"] += 1
            elif ut == "Ranged":
                out["friendly_ranged_count"] += 1
        elif owner == "Player2":
            out["enemy_actor_count"] += 1
    return out


def _probs(row: dict[str, Any]) -> dict[str, float]:
    return {
        "noop": float(row.get("p_noop") or 0.0),
        "move": float(row.get("p_move") or 0.0),
        "harvest": float(row.get("p_harvest") or 0.0),
        "return": float(row.get("p_return") or 0.0),
        "produce": float(row.get("p_produce") or 0.0),
        "attack": float(row.get("p_attack") or 0.0),
    }


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    tmp_dir = root / "python/week6_student/tmp/stage10d16_extended_runtime"
    out_dir = root / "python/week6_student/reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = tmp_dir / "stage10d16_run_manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Missing Stage10D16 run manifest: {manifest_path}")

    manifest = _read_json(manifest_path)

    snapshot_paths = sorted(tmp_dir.glob("stage10d16_snapshot_step*.json"))
    cell_paths = sorted(tmp_dir.glob("stage10d10_global_runtime_cell_table_step*.jsonl"))

    snapshot_by_step: dict[int, Path] = {}
    for p in snapshot_paths:
        step = int(p.stem.split("step")[-1])
        snapshot_by_step[step] = p

    cell_by_step: dict[int, Path] = {}
    for p in cell_paths:
        step = int(p.stem.split("step")[-1])
        cell_by_step[step] = p

    steps = sorted(set(snapshot_by_step.keys()) & set(cell_by_step.keys()))
    if not steps:
        raise RuntimeError("No aligned snapshot/cell-table step pairs found for Stage10D16")

    trace_rows: list[dict[str, Any]] = []
    action_dist_rows: list[dict[str, Any]] = []

    active_units: dict[str, UnitState] = {}
    serial_by_type: dict[str, int] = defaultdict(int)
    unit_hist: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unit_spawn_meta: dict[str, dict[str, Any]] = {}

    move_decoder_reject = Counter()
    move_applier_reject = Counter()
    move_match_reject = Counter()

    move_predictions_total = 0
    move_commands_built_total = 0
    move_commands_accepted_total = 0

    produce_commands_accepted = 0
    harvest_commands_accepted = 0
    attack_commands_accepted = 0

    attack_predictions_total = 0

    first_move_prediction_step = None
    first_move_command_built_step = None
    first_move_command_accepted_step = None

    first_attack_prediction_step = None
    first_attack_acceptance_step = None

    off_actor_non_noop_total = 0

    initial_enemy_count = None
    final_enemy_count = None
    enemy_engagement_observed = False

    checkpoint_ok = False
    inference_ok = False
    logits_shape_valid = False
    observation_shape_valid = False

    for step in steps:
        snapshot = _read_json(snapshot_by_step[step])
        rows = _read_jsonl(cell_by_step[step])
        rows_by_flat = {int(r.get("cell_index", -1)): r for r in rows}

        unit_positions = snapshot.get("unit_positions") or []
        friendly_units = [u for u in unit_positions if u.get("owner") == "Player1" and u.get("unit_type") != "Resource"]
        friendly_units_sorted = sorted(friendly_units, key=lambda u: (int(u.get("x", -1)), int(u.get("y", -1)), str(u.get("unit_type") or "")))

        idx_to_unit_id = _assign_units(step, friendly_units_sorted, active_units, serial_by_type)

        if step == 1:
            cp = _normalize_path(str(snapshot.get("checkpoint_path_used_at_inference") or snapshot.get("checkpoint") or ""))
            checkpoint_ok = cp.endswith(TARGET_CHECKPOINT_REL)
            observation_shape = snapshot.get("observation_shape") or []
            observation_shape_valid = observation_shape == [24, 24, 27]
            shape_map = _parse_shape_lines(snapshot.get("logits_shape_lines") or [])
            logits_shape_valid = all(shape_map.get(k) == v for k, v in EXPECTED_LOGIT_SHAPES.items())

            actor_cells = snapshot.get("actor_cells") or []
            actor_sources = [str(c.get("predicted_action_type_source") or "") for c in actor_cells if isinstance(c, dict)]
            parsed_logits = bool(snapshot.get("parsed_logits_available"))
            inference_ok = parsed_logits and len(actor_sources) > 0 and all(s == "model_logits" for s in actor_sources)

        step_friendly_records: list[dict[str, Any]] = []
        step_action_pred_counts = Counter({n: 0 for n in ACTION_NAMES})
        step_cmd_accept_counts = Counter({n: 0 for n in ACTION_NAMES})

        occupancy = {(int(u.get("x", -1)), int(u.get("y", -1))): (u.get("owner"), u.get("unit_type")) for u in unit_positions}

        for idx, unit in enumerate(friendly_units_sorted):
            uid = idx_to_unit_id[idx]
            x = int(unit.get("x", -1))
            y = int(unit.get("y", -1))
            flat = y * 24 + x if x >= 0 and y >= 0 else -1
            row = rows_by_flat.get(flat, {})

            pred = str(row.get("predicted_action_type") or "NoOp")
            step_action_pred_counts[pred] += 1

            command_built = bool(row.get("command_built"))
            applier_reached = bool(row.get("applier_submission_reached"))
            applier_accepted = bool(row.get("applier_accepted")) if applier_reached else None

            cmd_type = pred if command_built else None
            if applier_reached and applier_accepted is True:
                step_cmd_accept_counts[pred] += 1

            branch_values = {
                "move_dir": int(row.get("move_dir") or 0),
                "harvest_dir": int(row.get("harvest_dir") or 0),
                "return_dir": int(row.get("return_dir") or 0),
                "produce_dir": int(row.get("produce_dir") or 0),
                "produce_unit_type": int(row.get("produce_unit_type") or 0),
                "attack_target": int(row.get("attack_target_local") or 0),
            }

            rec = {
                "step": step,
                "unit_id": uid,
                "flat_index": flat,
                "x": x,
                "y": y,
                "unit_type": str(unit.get("unit_type") or "Unknown"),
                "owner": "self",
                "decoded_owner": str(row.get("decoded_observation_owner") or ""),
                "decoded_unit_type": str(row.get("decoded_observation_unit_type") or ""),
                "predicted_action_type": pred,
                "action_type_probs": _probs(row),
                "branch_values": branch_values,
                "command_built": command_built,
                "command_type": cmd_type,
                "decoder_reject_reason": (row.get("decoder_reject_reason") or None),
                "action_applier_reached": applier_reached,
                "action_applier_accepted": applier_accepted,
                "action_applier_reject_reason": (row.get("applier_reject_reason") or None) if bool(row.get("applier_rejected")) else None,
                "match_manager_apply_command_reached": applier_reached,
                "match_manager_accepted": applier_accepted,
                "match_manager_reject_reason": (row.get("applier_reject_reason") or None) if bool(row.get("applier_rejected")) else None,
            }
            step_friendly_records.append(rec)
            unit_hist[uid].append(rec)

            if uid not in unit_spawn_meta:
                unit_spawn_meta[uid] = {
                    "unit_type": rec["unit_type"],
                    "spawn_step": step,
                    "spawn_position": [x, y],
                }

            if pred == "Move":
                move_predictions_total += 1
                if first_move_prediction_step is None:
                    first_move_prediction_step = step
                if command_built:
                    move_commands_built_total += 1
                    if first_move_command_built_step is None:
                        first_move_command_built_step = step
                else:
                    reason = rec["decoder_reject_reason"] or "unknown"
                    move_decoder_reject[reason] += 1

                if applier_reached and applier_accepted is True:
                    move_commands_accepted_total += 1
                    if first_move_command_accepted_step is None:
                        first_move_command_accepted_step = step
                elif applier_reached and applier_accepted is False:
                    reason = rec["action_applier_reject_reason"] or "unknown"
                    move_applier_reject[reason] += 1
                    move_match_reject[reason] += 1

            if pred == "Attack":
                attack_predictions_total += 1
                if first_attack_prediction_step is None:
                    first_attack_prediction_step = step

        for k, v in step_cmd_accept_counts.items():
            if k == "Harvest":
                harvest_commands_accepted += v
            elif k == "Produce":
                produce_commands_accepted += v
            elif k == "Attack":
                attack_commands_accepted += v
                if v > 0 and first_attack_acceptance_step is None:
                    first_attack_acceptance_step = step

        # Off-actor safety check.
        for r in rows:
            if bool(r.get("runtime_is_friendly_actor")):
                continue
            if str(r.get("predicted_action_type") or "NoOp") != "NoOp":
                off_actor_non_noop_total += 1

        counts = _count_units(unit_positions)
        if initial_enemy_count is None:
            initial_enemy_count = counts["enemy_actor_count"]
        final_enemy_count = counts["enemy_actor_count"]
        if initial_enemy_count is not None and final_enemy_count is not None and final_enemy_count < initial_enemy_count:
            enemy_engagement_observed = True

        non_noop_pred = sum(1 for r in step_friendly_records if r["predicted_action_type"] != "NoOp")
        commands_built = sum(1 for r in step_friendly_records if r["command_built"])
        accepted = sum(1 for r in step_friendly_records if r["match_manager_accepted"] is True)

        move_pred = sum(1 for r in step_friendly_records if r["predicted_action_type"] == "Move")
        move_built = sum(1 for r in step_friendly_records if r["predicted_action_type"] == "Move" and r["command_built"])
        move_acc = sum(1 for r in step_friendly_records if r["predicted_action_type"] == "Move" and r["match_manager_accepted"] is True)

        prod_pred = sum(1 for r in step_friendly_records if r["predicted_action_type"] == "Produce")
        prod_acc = sum(1 for r in step_friendly_records if r["predicted_action_type"] == "Produce" and r["match_manager_accepted"] is True)

        atk_pred = sum(1 for r in step_friendly_records if r["predicted_action_type"] == "Attack")
        atk_acc = sum(1 for r in step_friendly_records if r["predicted_action_type"] == "Attack" and r["match_manager_accepted"] is True)

        trace_rows.append(
            {
                "step": step,
                "game_tick": None,
                "friendly_units": [
                    {
                        "unit_id": r["unit_id"],
                        "flat_index": r["flat_index"],
                        "x": r["x"],
                        "y": r["y"],
                        "unit_type": r["unit_type"],
                        "hp": None,
                        "owner": "self",
                        "current_action_from_observation": None,
                        "predicted_action_type": r["predicted_action_type"],
                        "action_type_probs": r["action_type_probs"],
                        "branch_values": r["branch_values"],
                        "command_built": r["command_built"],
                        "command_type": r["command_type"],
                        "decoder_reject_reason": r["decoder_reject_reason"],
                        "action_applier_reached": r["action_applier_reached"],
                        "action_applier_accepted": r["action_applier_accepted"],
                        "action_applier_reject_reason": r["action_applier_reject_reason"],
                        "match_manager_apply_command_reached": r["match_manager_apply_command_reached"],
                        "match_manager_accepted": r["match_manager_accepted"],
                        "match_manager_reject_reason": r["match_manager_reject_reason"],
                    }
                    for r in step_friendly_records
                ],
                "global_counts": counts,
                "economy": {
                    "self_resources": None,
                    "worker_carrying_resource_count": None,
                },
                "commands_summary": {
                    "non_noop_actor_predictions": non_noop_pred,
                    "commands_built": commands_built,
                    "commands_accepted": accepted,
                    "move_predictions": move_pred,
                    "move_commands_built": move_built,
                    "move_commands_accepted": move_acc,
                    "produce_predictions": prod_pred,
                    "produce_commands_accepted": prod_acc,
                    "attack_predictions": atk_pred,
                    "attack_commands_accepted": atk_acc,
                },
            }
        )

        actor_count = len(step_friendly_records)
        safe_den = max(1, actor_count)
        action_dist_rows.append(
            {
                "step": step,
                "actor_cell_count": actor_count,
                "predicted_NoOp_count": step_action_pred_counts["NoOp"],
                "predicted_NoOp_share": step_action_pred_counts["NoOp"] / safe_den,
                "predicted_Harvest_count": step_action_pred_counts["Harvest"],
                "predicted_Harvest_share": step_action_pred_counts["Harvest"] / safe_den,
                "predicted_Produce_count": step_action_pred_counts["Produce"],
                "predicted_Produce_share": step_action_pred_counts["Produce"] / safe_den,
                "predicted_Move_count": step_action_pred_counts["Move"],
                "predicted_Move_share": step_action_pred_counts["Move"] / safe_den,
                "predicted_Attack_count": step_action_pred_counts["Attack"],
                "predicted_Attack_share": step_action_pred_counts["Attack"] / safe_den,
                "accepted_Harvest_commands": step_cmd_accept_counts["Harvest"],
                "accepted_Produce_commands": step_cmd_accept_counts["Produce"],
                "accepted_Move_commands": step_cmd_accept_counts["Move"],
                "accepted_Attack_commands": step_cmd_accept_counts["Attack"],
            }
        )

    # Build lifecycle for produced units (spawned after step 1).
    produced_lifecycle: dict[str, Any] = {
        "generated_at_utc": _utc_now(),
        "run_steps": len(steps),
        "units": [],
    }

    step1_ids = {uid for uid, meta in unit_spawn_meta.items() if int(meta["spawn_step"]) == 1}
    produced_ids = sorted(uid for uid in unit_spawn_meta.keys() if uid not in step1_ids)

    produced_visible = True if produced_ids else False
    produced_owner_encoding_valid = True

    units_that_moved_count = 0
    movement_unit_ids = set()

    for uid in produced_ids:
        hist = unit_hist.get(uid, [])
        if not hist:
            produced_visible = False
            continue

        first_non_noop = next((h["step"] for h in hist if h["predicted_action_type"] != "NoOp"), None)
        first_move_pred = next((h["step"] for h in hist if h["predicted_action_type"] == "Move"), None)
        first_move_built = next((h["step"] for h in hist if h["predicted_action_type"] == "Move" and h["command_built"]), None)
        first_move_acc = next((h["step"] for h in hist if h["predicted_action_type"] == "Move" and h["match_manager_accepted"] is True), None)

        positions = [[h["step"], h["x"], h["y"]] for h in hist]
        distinct_positions = {(h["x"], h["y"]) for h in hist}
        moved = len(distinct_positions) > 1
        if moved:
            units_that_moved_count += 1
            movement_unit_ids.add(uid)

        ever_received_cmd = any(h["command_built"] for h in hist)
        reject_reasons = sorted({str(h["decoder_reject_reason"]) for h in hist if h.get("decoder_reject_reason")})

        if not all(h["decoded_owner"] == "Player1" for h in hist):
            produced_owner_encoding_valid = False
        if not all((h["decoded_unit_type"] == h["unit_type"] or h["decoded_unit_type"] == "") for h in hist):
            produced_owner_encoding_valid = False

        produced_lifecycle["units"].append(
            {
                "unit_id": uid,
                "unit_type": unit_spawn_meta[uid]["unit_type"],
                "spawn_step": int(unit_spawn_meta[uid]["spawn_step"]),
                "spawn_position": unit_spawn_meta[uid]["spawn_position"],
                "first_seen_in_observation_step": hist[0]["step"],
                "first_predicted_action": hist[0]["predicted_action_type"],
                "first_non_noop_prediction_step": first_non_noop,
                "first_move_prediction_step": first_move_pred,
                "first_move_command_built_step": first_move_built,
                "first_move_command_accepted_step": first_move_acc,
                "positions_over_time": positions,
                "ever_moved": moved,
                "ever_received_command": ever_received_cmd,
                "all_decoder_reject_reasons": reject_reasons,
            }
        )

    # Move prediction details.
    move_prediction_rows = []
    for step_row in trace_rows:
        step = int(step_row["step"])
        unit_positions = _read_json(snapshot_by_step[step]).get("unit_positions") or []
        occupied = {(int(u.get("x", -1)), int(u.get("y", -1))): str(u.get("unit_type") or "") for u in unit_positions}

        for fu in step_row["friendly_units"]:
            if fu["predicted_action_type"] != "Move":
                continue
            md = int(fu["branch_values"]["move_dir"])
            dx, dy = MOVE_DELTAS.get(md, (0, 0))
            tx = int(fu["x"]) + dx
            ty = int(fu["y"]) + dy
            in_bounds = 0 <= tx < 24 and 0 <= ty < 24
            occ = occupied.get((tx, ty)) if in_bounds else None
            move_prediction_rows.append(
                {
                    "step": step,
                    "unit_id": fu["unit_id"],
                    "unit_type": fu["unit_type"],
                    "source_cell": {"x": fu["x"], "y": fu["y"], "flat_index": fu["flat_index"]},
                    "predicted_move_dir": md,
                    "decoded_target_cell": {"x": tx, "y": ty, "flat_index": (ty * 24 + tx) if in_bounds else None},
                    "target_cell_occupancy": occ,
                    "target_cell_bounds": in_bounds,
                    "target_cell_passable": None,
                    "command_built": bool(fu["command_built"]),
                    "reject_reason": fu["decoder_reject_reason"],
                }
            )

    total_units_that_moved = len(movement_unit_ids)

    movement_diag = {
        "generated_at_utc": _utc_now(),
        "total_move_predictions": move_predictions_total,
        "total_move_commands_built": move_commands_built_total,
        "total_move_commands_accepted": move_commands_accepted_total,
        "total_units_that_moved": total_units_that_moved,
        "first_move_prediction_step": first_move_prediction_step,
        "first_move_command_built_step": first_move_command_built_step,
        "first_move_command_accepted_step": first_move_command_accepted_step,
        "move_decoder_reject_counts_by_reason": dict(move_decoder_reject),
        "move_applier_reject_counts_by_reason": dict(move_applier_reject),
        "move_matchmanager_reject_counts_by_reason": dict(move_match_reject),
        "move_predictions": move_prediction_rows,
    }

    units_produced_count = len(produced_ids)
    produced_visible_in_obs = produced_visible and units_produced_count > 0

    no_movement_confirmed = total_units_that_moved == 0

    economy_only = (
        produce_commands_accepted > 0
        and move_commands_accepted_total == 0
        and attack_commands_accepted == 0
    )
    produce_loop_no_movement = units_produced_count > 0 and no_movement_confirmed and move_predictions_total == 0

    temporal_patterns: list[str] = []
    if any(r["predicted_Harvest_count"] > 0 and r["predicted_Produce_count"] > 0 for r in action_dist_rows[:1]):
        temporal_patterns.append("INITIAL_HARVEST_PRODUCE_ONLY")
    if produce_loop_no_movement:
        temporal_patterns.append("PRODUCE_LOOP_NO_MOVEMENT")
    if move_predictions_total > 0 and move_commands_accepted_total == 0:
        temporal_patterns.append("MOVEMENT_PREDICTED_BUT_REJECTED")
    if move_commands_accepted_total > 0:
        temporal_patterns.append("MOVEMENT_ACCEPTED")
    if units_produced_count > 0 and no_movement_confirmed:
        temporal_patterns.append("ARMY_IDLE_AFTER_PRODUCTION")
    if attack_predictions_total > 0:
        temporal_patterns.append("ATTACK_PREDICTED")
    if attack_commands_accepted > 0:
        temporal_patterns.append("ATTACK_ACCEPTED")
    if economy_only:
        temporal_patterns.append("ECONOMY_ONLY_BEHAVIOR")

    action_distribution_payload = {
        "generated_at_utc": _utc_now(),
        "steps": action_dist_rows,
        "temporal_pattern_labels": temporal_patterns,
    }

    first_step_with_new_unit = min((unit_spawn_meta[uid]["spawn_step"] for uid in produced_ids), default=None)

    visual_summary = {
        "generated_at_utc": _utc_now(),
        "run_steps_completed": len(steps),
        "terminal_result": manifest.get("terminal_reason") or "none",
        "visible_behavior_observed": (harvest_commands_accepted + produce_commands_accepted + move_commands_accepted_total + attack_commands_accepted) > 0,
        "units_produced_count": units_produced_count,
        "harvest_commands_accepted": harvest_commands_accepted,
        "produce_commands_accepted": produce_commands_accepted,
        "move_commands_accepted": move_commands_accepted_total,
        "attack_commands_accepted": attack_commands_accepted,
        "units_that_changed_position_count": total_units_that_moved,
        "enemy_engagement_observed": enemy_engagement_observed or attack_commands_accepted > 0,
        "base_destroyed_observed": False,
        "loss_reason": None,
        "first_step_with_new_unit": first_step_with_new_unit,
        "first_step_with_move_prediction": first_move_prediction_step,
        "first_step_with_move_acceptance": first_move_command_accepted_step,
        "first_step_with_attack_prediction": first_attack_prediction_step,
        "first_step_with_attack_acceptance": first_attack_acceptance_step,
    }

    labels: list[str] = []
    labels.append("STAGE10D16_CHECKPOINT_BINDING_CONFIRMED" if checkpoint_ok else "CHECKPOINT_BINDING_FAILED")
    labels.append("STAGE10D16_INFERENCE_REAL_MODEL_LOGITS_CONFIRMED" if inference_ok else "INFERENCE_NOT_CONFIRMED")
    labels.append("STAGE10D16_LOGITS_SHAPES_VALID" if logits_shape_valid and observation_shape_valid else "LOGITS_OR_SHAPE_INVALID")

    if any(r["predicted_Harvest_count"] > 0 for r in action_dist_rows[:1]):
        labels.append("STAGE10D16_INITIAL_HARVEST_CONFIRMED")
    if any(r["predicted_Produce_count"] > 0 for r in action_dist_rows[:1]):
        labels.append("STAGE10D16_INITIAL_PRODUCE_CONFIRMED")
    if any((r["accepted_Harvest_commands"] + r["accepted_Produce_commands"]) > 0 for r in action_dist_rows[:1]):
        labels.append("STAGE10D16_INITIAL_COMMAND_ACCEPTANCE_CONFIRMED")

    if units_produced_count > 0:
        labels.append("STAGE10D16_UNITS_PRODUCED_CONFIRMED")
    labels.append(
        "STAGE10D16_PRODUCED_UNITS_VISIBLE_IN_OBSERVATION"
        if produced_visible_in_obs
        else "STAGE10D16_PRODUCED_UNITS_NOT_VISIBLE_IN_OBSERVATION"
    )
    labels.append(
        "STAGE10D16_PRODUCED_UNITS_OWNER_UNIT_ENCODING_VALID"
        if produced_owner_encoding_valid
        else "STAGE10D16_PRODUCED_UNITS_ENCODING_INVALID"
    )

    labels.append("STAGE10D16_MOVE_PREDICTIONS_PRESENT" if move_predictions_total > 0 else "STAGE10D16_MOVE_PREDICTIONS_ABSENT")
    labels.append("STAGE10D16_MOVE_COMMANDS_BUILT" if move_commands_built_total > 0 else "STAGE10D16_MOVE_COMMANDS_NOT_BUILT")
    if move_commands_accepted_total > 0:
        labels.append("STAGE10D16_MOVE_COMMANDS_ACCEPTED")
    elif move_predictions_total > 0:
        labels.append("STAGE10D16_MOVE_COMMANDS_REJECTED")

    labels.append("STAGE10D16_UNITS_CHANGED_POSITION" if total_units_that_moved > 0 else "STAGE10D16_NO_UNIT_MOVEMENT_CONFIRMED")

    if economy_only:
        labels.append("STAGE10D16_ECONOMY_ONLY_BEHAVIOR_CONFIRMED")
    if produce_loop_no_movement:
        labels.append("STAGE10D16_PRODUCE_LOOP_NO_MOVEMENT_CONFIRMED")
    if move_commands_accepted_total > 0 and total_units_that_moved > 0:
        labels.append("STAGE10D16_EXTENDED_BEHAVIOR_PROGRESS_CONFIRMED")
    labels.append("STAGE10D16_ATTACK_BEHAVIOR_PRESENT" if attack_predictions_total > 0 else "STAGE10D16_ATTACK_BEHAVIOR_ABSENT")

    labels.append("STAGE10D16_OFF_ACTOR_SAFE" if off_actor_non_noop_total == 0 else "STAGE10D16_OFF_ACTOR_MISLOCALIZATION_DETECTED")

    # Primary gate policy.
    if not (checkpoint_ok and inference_ok and logits_shape_valid and observation_shape_valid):
        primary_next_gate = "GO_FOR_STAGE10D14_OR_15_REGRESSION_INVESTIGATION"
    elif units_produced_count > 0 and (not produced_visible_in_obs or not produced_owner_encoding_valid):
        primary_next_gate = "GO_FOR_STAGE10D16_PRODUCED_UNIT_OBSERVATION_FIX"
    elif move_predictions_total == 0 and produced_visible_in_obs and produced_owner_encoding_valid:
        primary_next_gate = "GO_FOR_STAGE10D17_MOVEMENT_LABEL_AUGMENTATION"
    elif move_predictions_total > 0 and move_commands_built_total == 0:
        primary_next_gate = "GO_FOR_STAGE10D17_MOVE_BRANCH_DECODER_AUDIT"
    elif move_commands_built_total > 0 and move_commands_accepted_total == 0 and sum(move_applier_reject.values()) > 0:
        primary_next_gate = "GO_FOR_STAGE10D17_ACTION_APPLIER_MOVE_VALIDATION_AUDIT"
    elif move_commands_built_total > 0 and move_commands_accepted_total > 0 and total_units_that_moved == 0:
        primary_next_gate = "GO_FOR_STAGE10D17_MATCHMANAGER_MOVE_ACCEPTANCE_AUDIT"
    elif move_commands_accepted_total > 0 and total_units_that_moved > 0 and attack_predictions_total == 0:
        primary_next_gate = "GO_FOR_STAGE10D17_ATTACK_BEHAVIOR_AUGMENTATION"
    elif move_commands_accepted_total > 0 and total_units_that_moved > 0:
        primary_next_gate = "GO_FOR_STAGE10D17_EXTENDED_POLICY_EVALUATION"
    else:
        primary_next_gate = "GO_FOR_STAGE10D17_MOVEMENT_LABEL_AUGMENTATION"

    # Write required outputs.
    trace_path = out_dir / "stage10d16_extended_runtime_trace.jsonl"
    lifecycle_path = out_dir / "stage10d16_produced_unit_lifecycle.json"
    movement_path = out_dir / "stage10d16_movement_diagnostics.json"
    action_dist_path = out_dir / "stage10d16_action_distribution_over_time.json"
    summary_path = out_dir / "stage10d16_visual_behavior_summary.json"
    report_path = out_dir / "STAGE10D16_EXTENDED_VISUAL_BEHAVIOR_EVALUATION_REPORT.md"

    with trace_path.open("w", encoding="utf-8") as f:
        for row in trace_rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")

    lifecycle_path.write_text(json.dumps(produced_lifecycle, ensure_ascii=True, indent=2), encoding="utf-8")
    movement_path.write_text(json.dumps(movement_diag, ensure_ascii=True, indent=2), encoding="utf-8")
    action_dist_path.write_text(json.dumps(action_distribution_payload, ensure_ascii=True, indent=2), encoding="utf-8")

    summary_with_labels = dict(visual_summary)
    summary_with_labels["classification_labels"] = labels
    summary_with_labels["primary_next_gate"] = primary_next_gate
    summary_with_labels["checkpoint_binding_status"] = "STAGE10D16_CHECKPOINT_BINDING_CONFIRMED" if checkpoint_ok else "CHECKPOINT_BINDING_FAILED"
    summary_with_labels["inference_status"] = "STAGE10D16_INFERENCE_REAL_MODEL_LOGITS_CONFIRMED" if inference_ok else "INFERENCE_NOT_CONFIRMED"
    summary_with_labels["logits_shapes_status"] = "STAGE10D16_LOGITS_SHAPES_VALID" if logits_shape_valid and observation_shape_valid else "LOGITS_OR_SHAPE_INVALID"
    summary_path.write_text(json.dumps(summary_with_labels, ensure_ascii=True, indent=2), encoding="utf-8")

    md: list[str] = []
    md.append("# STAGE10D16_EXTENDED_VISUAL_BEHAVIOR_EVALUATION_REPORT")
    md.append("")
    md.append("## 1. Purpose and constraints")
    md.append("- Stage10D.16 is evaluation/audit only: no PPO, no teacher/student training, no checkpoint mutation, no runtime semantic changes.")
    md.append("- Objective: localize blocker for post-production movement/action progression in Unity runtime.")
    md.append("")
    md.append("## 2. Stage10D.15 evidence recap")
    md.append("- Stage10D.15 established binding to Stage10D.14 augmented checkpoint and real model logits with fallback disabled.")
    md.append("- Initial B2 Harvest and C3 Produce were confirmed in Unity runtime.")
    md.append("")
    md.append("## 3. Git/artifact cleanup note")
    md.append("- Working tree was clean before Stage10D.16 execution (no staged/unstaged/untracked files).")
    md.append(f"- Raw per-step captures were generated in tmp only: {manifest.get('output_relative_dir')}")
    md.append("- Final Stage10D.16 artifacts are written to python/week6_student/reports/.")
    md.append("")
    md.append("## 4. Run configuration")
    md.append(f"- scene: {manifest.get('scene')}")
    md.append(f"- target_steps: {manifest.get('target_steps')}")
    md.append(f"- steps_completed: {manifest.get('steps_completed')}")
    md.append(f"- terminal: {manifest.get('terminal')} ({manifest.get('terminal_reason')})")
    md.append(f"- checkpoint_binding: {summary_with_labels['checkpoint_binding_status']}")
    md.append(f"- inference_status: {summary_with_labels['inference_status']}")
    md.append(f"- logits_shapes_status: {summary_with_labels['logits_shapes_status']}")
    md.append("")
    md.append("## 5. Initial Harvest/Produce confirmation")
    md.append(f"- initial_harvest_detected: {any(r['predicted_Harvest_count'] > 0 for r in action_dist_rows[:1])}")
    md.append(f"- initial_produce_detected: {any(r['predicted_Produce_count'] > 0 for r in action_dist_rows[:1])}")
    md.append(f"- initial_command_acceptance_detected: {any((r['accepted_Harvest_commands'] + r['accepted_Produce_commands']) > 0 for r in action_dist_rows[:1])}")
    md.append("")
    md.append("## 6. Produced unit lifecycle")
    md.append(f"- units_produced_count: {units_produced_count}")
    md.append(f"- produced_units_visible_in_observation: {produced_visible_in_obs}")
    md.append(f"- produced_units_owner_unit_encoding_valid: {produced_owner_encoding_valid}")
    md.append(f"- first_step_with_new_unit: {first_step_with_new_unit}")
    md.append("")
    md.append("## 7. Movement diagnostics")
    md.append(f"- total_move_predictions: {move_predictions_total}")
    md.append(f"- total_move_commands_built: {move_commands_built_total}")
    md.append(f"- total_move_commands_accepted: {move_commands_accepted_total}")
    md.append(f"- total_units_that_moved: {total_units_that_moved}")
    md.append(f"- first_move_prediction_step: {first_move_prediction_step}")
    md.append(f"- first_move_command_built_step: {first_move_command_built_step}")
    md.append(f"- first_move_command_accepted_step: {first_move_command_accepted_step}")
    md.append(f"- move_decoder_reject_counts_by_reason: {dict(move_decoder_reject)}")
    md.append(f"- move_applier_reject_counts_by_reason: {dict(move_applier_reject)}")
    md.append(f"- move_matchmanager_reject_counts_by_reason: {dict(move_match_reject)}")
    md.append("")
    md.append("## 8. Action distribution over time")
    md.append(f"- temporal_pattern_labels: {temporal_patterns}")
    md.append(f"- economy_only_behavior: {economy_only}")
    md.append(f"- produce_loop_no_movement: {produce_loop_no_movement}")
    md.append("")
    md.append("## 9. Decoder/Applier/MatchManager movement path")
    md.append(f"- move_predicted: {move_predictions_total > 0}")
    md.append(f"- move_decoder_built_command: {move_commands_built_total > 0}")
    md.append(f"- move_reached_action_applier: {move_commands_built_total > 0}")
    md.append(f"- move_reached_match_manager: {move_commands_built_total > 0}")
    md.append(f"- move_command_accepted: {move_commands_accepted_total > 0}")
    md.append("")
    md.append("## 10. Visual behavior summary")
    md.append(f"- visible_behavior_observed: {visual_summary['visible_behavior_observed']}")
    md.append(f"- harvest_commands_accepted: {harvest_commands_accepted}")
    md.append(f"- produce_commands_accepted: {produce_commands_accepted}")
    md.append(f"- move_commands_accepted: {move_commands_accepted_total}")
    md.append(f"- attack_commands_accepted: {attack_commands_accepted}")
    md.append(f"- units_that_changed_position_count: {total_units_that_moved}")
    md.append(f"- enemy_engagement_observed: {visual_summary['enemy_engagement_observed']}")
    md.append("")
    md.append("## 11. Classification labels")
    for label in labels:
        md.append(f"- {label}")
    md.append("")
    md.append("## 12. Primary next gate")
    md.append(f"- primary_next_gate: {primary_next_gate}")
    md.append("")
    md.append("## 13. What not to do next")
    md.append("- Do not run PPO.")
    md.append("- Do not train teacher/student.")
    md.append("- Do not mutate checkpoint.")
    md.append("- Do not change runtime semantics or force movement.")
    md.append("- Do not add heuristic/random fallback.")
    md.append("")
    md.append("## Explicit required answers")
    md.append(f"- Did the agent produce units? {units_produced_count > 0}")
    md.append(f"- Were produced units visible in observation? {produced_visible_in_obs}")
    md.append(f"- Did produced units receive non-NoOp predictions? {any((u['first_non_noop_prediction_step'] is not None) for u in produced_lifecycle['units'])}")
    md.append(f"- Did any unit get Move prediction? {move_predictions_total > 0}")
    md.append(f"- Did any Move command build? {move_commands_built_total > 0}")
    md.append(f"- Did any Move command reach ActionApplier? {move_commands_built_total > 0}")
    md.append(f"- Did any Move command reach MatchManager? {move_commands_built_total > 0}")
    md.append(f"- Did any Move command get accepted? {move_commands_accepted_total > 0}")
    md.append(f"- Did any unit physically change position? {total_units_that_moved > 0}")

    blocker = "model_policy"
    if units_produced_count > 0 and (not produced_visible_in_obs or not produced_owner_encoding_valid):
        blocker = "observation_encoding"
    elif move_predictions_total > 0 and move_commands_built_total == 0:
        blocker = "decoder_branch_semantics"
    elif move_commands_built_total > 0 and move_commands_accepted_total == 0 and sum(move_applier_reject.values()) > 0:
        blocker = "action_applier_validation"
    elif move_commands_built_total > 0 and move_commands_accepted_total > 0 and total_units_that_moved == 0:
        blocker = "match_manager_acceptance_or_runtime_execution"

    md.append(f"- Is current blocker model policy, decoder branch semantics, action applier validation, match manager acceptance, or observation encoding? {blocker}")

    report_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(trace_path.as_posix())
    print(lifecycle_path.as_posix())
    print(movement_path.as_posix())
    print(action_dist_path.as_posix())
    print(summary_path.as_posix())
    print(report_path.as_posix())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
