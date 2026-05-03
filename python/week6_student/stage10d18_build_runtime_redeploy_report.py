from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TARGET_CHECKPOINT_BASENAME = "student_bc_stage10d17_movement_augmented_best.pt"
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
MOVE_DIR_NAMES = {0: "north", 1: "east", 2: "south", 3: "west"}


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


def _normalize_path(p: str) -> str:
    return (p or "").replace("\\", "/")


def _basename(p: str) -> str:
    return Path(_normalize_path(p)).name if p else ""


def _parse_shape_lines(lines: list[str]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for line in lines:
        if not isinstance(line, str) or ":" not in line:
            continue
        k, v = line.split(":", 1)
        nums: list[int] = []
        ok = True
        for token in v.strip().strip("[]").split(","):
            token = token.strip()
            if not token:
                continue
            try:
                nums.append(int(token))
            except ValueError:
                ok = False
                break
        if ok and nums:
            out[k.strip()] = nums
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


def _fallback_from_snapshot(snapshot: dict[str, Any], actor_rows: list[dict[str, Any]]) -> tuple[bool, bool, bool]:
    fallback_used = bool(snapshot.get("fallback_used") or snapshot.get("used_fallback") or False)
    fake_logits_used = bool(snapshot.get("fake_logits_used") or snapshot.get("stage10r_fake_logits_used") or False)
    heuristic_policy_path_used = bool(snapshot.get("heuristic_policy_path_used") or False)

    for row in actor_rows:
        source = str(row.get("predicted_action_type_source") or "")
        if source and source != "model_logits":
            fallback_used = True
        if source and "fake" in source.lower():
            fake_logits_used = True
        if source and "heuristic" in source.lower():
            heuristic_policy_path_used = True

    return fallback_used, fake_logits_used, heuristic_policy_path_used


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    tmp_dir = root / "python/week6_student/tmp/stage10d18_runtime_redeploy"
    out_dir = root / "python/week6_student/reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = tmp_dir / "stage10d18_run_manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Missing Stage10D18 run manifest: {manifest_path}")
    manifest = _read_json(manifest_path)

    snapshot_paths = sorted(tmp_dir.glob("stage10d18_snapshot_step*.json"))
    cell_paths = sorted(tmp_dir.glob("stage10d10_global_runtime_cell_table_step*.jsonl"))

    snapshot_by_step: dict[int, Path] = {}
    for p in snapshot_paths:
        snapshot_by_step[int(p.stem.split("step")[-1])] = p

    cell_by_step: dict[int, Path] = {}
    for p in cell_paths:
        cell_by_step[int(p.stem.split("step")[-1])] = p

    steps = sorted(set(snapshot_by_step.keys()) & set(cell_by_step.keys()))
    if not steps:
        raise RuntimeError("No aligned snapshot/cell-table pairs found for Stage10D18")

    # Binding verification from step 1.
    snapshot_step1 = _read_json(snapshot_by_step[steps[0]])
    rows_step1 = _read_jsonl(cell_by_step[steps[0]])
    actor_rows_step1 = [r for r in rows_step1 if bool(r.get("runtime_is_friendly_actor"))]

    active_checkpoint_path = _normalize_path(
        str(snapshot_step1.get("checkpoint_path_used_at_inference") or snapshot_step1.get("checkpoint") or manifest.get("configured_checkpoint_relative_path") or "")
    )
    active_checkpoint_basename = _basename(active_checkpoint_path)
    shape_map = _parse_shape_lines(snapshot_step1.get("logits_shape_lines") or [])
    logits_shapes_valid = all(shape_map.get(k) == v for k, v in EXPECTED_LOGIT_SHAPES.items())
    observation_shape = snapshot_step1.get("observation_shape") or []
    observation_shape_valid = observation_shape == [24, 24, 27]

    model_loaded = bool(snapshot_step1.get("parsed_logits_available"))
    predicted_source = "model_logits"
    if actor_rows_step1:
        sources = [str(r.get("predicted_action_type_source") or "") for r in actor_rows_step1]
        if any(s and s != "model_logits" for s in sources):
            predicted_source = "mixed"

    fallback_used, fake_logits_used, heuristic_policy_path_used = _fallback_from_snapshot(snapshot_step1, actor_rows_step1)
    checkpoint_path_ok = active_checkpoint_basename == TARGET_CHECKPOINT_BASENAME
    binding_ok = (
        checkpoint_path_ok
        and model_loaded
        and predicted_source == "model_logits"
        and not fallback_used
        and not fake_logits_used
        and not heuristic_policy_path_used
        and logits_shapes_valid
        and observation_shape_valid
    )

    binding_labels: list[str] = []
    binding_labels.append("STAGE10D18_CHECKPOINT_BINDING_CONFIRMED" if checkpoint_path_ok else "STAGE10D18_CHECKPOINT_BINDING_FAILED")
    binding_labels.append("STAGE10D18_INFERENCE_REAL_MODEL_LOGITS_CONFIRMED" if (model_loaded and predicted_source == "model_logits" and not fallback_used and not fake_logits_used and not heuristic_policy_path_used) else "STAGE10D18_INFERENCE_FALLBACK_USED")
    binding_labels.append("STAGE10D18_LOGITS_SHAPES_VALID" if (logits_shapes_valid and observation_shape_valid) else "STAGE10D18_LOGITS_SHAPES_INVALID")

    binding_payload = {
        "generated_at_utc": _utc_now(),
        "active_checkpoint_path": active_checkpoint_path,
        "active_checkpoint_basename": active_checkpoint_basename,
        "expected_checkpoint_basename": TARGET_CHECKPOINT_BASENAME,
        "checkpoint_path_matches_expected": checkpoint_path_ok,
        "model_loaded": model_loaded,
        "predicted_source": predicted_source,
        "fallback_used": fallback_used,
        "fake_logits_used": fake_logits_used,
        "heuristic_policy_path_used": heuristic_policy_path_used,
        "observation_shape": observation_shape,
        "observation_shape_valid": observation_shape_valid,
        "logits_shapes": shape_map,
        "expected_logits_shapes": EXPECTED_LOGIT_SHAPES,
        "logits_shapes_valid": logits_shapes_valid,
        "labels": binding_labels,
        "binding_ok": binding_ok,
    }

    binding_path = out_dir / "stage10d18_checkpoint_binding_verification.json"
    binding_path.write_text(json.dumps(binding_payload, ensure_ascii=True, indent=2), encoding="utf-8")

    # If binding fails, emit minimal artifacts and stop behavioral conclusions.
    if not binding_ok:
        minimal_gate = "GO_FOR_STAGE10D18_CHECKPOINT_BINDING_FIX"
        trace_path = out_dir / "stage10d18_runtime_redeploy_trace.jsonl"
        lifecycle_path = out_dir / "stage10d18_produced_unit_lifecycle.json"
        move_path = out_dir / "stage10d18_movement_command_path_audit.json"
        action_dist_path = out_dir / "stage10d18_action_distribution_over_time.json"
        off_actor_path = out_dir / "stage10d18_off_actor_safety_audit.json"
        summary_path = out_dir / "stage10d18_visual_behavior_summary.json"
        report_path = out_dir / "STAGE10D18_RUNTIME_BC_REDEPLOY_EVAL_REPORT.md"

        trace_path.write_text("", encoding="utf-8")
        lifecycle_path.write_text(
            json.dumps(
                {
                    "generated_at_utc": _utc_now(),
                    "status": "SKIPPED_BINDING_FAILED",
                    "reason": "Checkpoint binding/inference verification failed before runtime behavior analysis.",
                    "produced_units_count": 0,
                    "produced_units_visible_in_observation": 0,
                    "produced_units_owner_unit_encoding_valid": 0,
                    "produced_units_with_move_prediction_count": 0,
                    "produced_units_with_move_command_built_count": 0,
                    "produced_units_with_move_command_accepted_count": 0,
                    "produced_units_that_moved_count": 0,
                    "units": [],
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )
        move_path.write_text(
            json.dumps(
                {
                    "generated_at_utc": _utc_now(),
                    "status": "SKIPPED_BINDING_FAILED",
                    "reason": "Binding failed: movement command path audit not executed.",
                    "total_move_predictions": 0,
                    "total_move_commands_built": 0,
                    "total_move_commands_submitted_to_action_applier": 0,
                    "total_move_commands_reached_match_manager": 0,
                    "total_move_commands_accepted": 0,
                    "total_units_that_changed_position_after_move": 0,
                    "move_decoder_reject_counts_by_reason": {},
                    "move_applier_reject_counts_by_reason": {},
                    "move_matchmanager_reject_counts_by_reason": {},
                    "events": [],
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )
        action_dist_path.write_text(
            json.dumps(
                {
                    "generated_at_utc": _utc_now(),
                    "status": "SKIPPED_BINDING_FAILED",
                    "reason": "Binding failed: action distribution over time not analyzed.",
                    "steps": [],
                    "temporal_pattern_labels": [],
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )
        off_actor_path.write_text(
            json.dumps(
                {
                    "generated_at_utc": _utc_now(),
                    "status": "SKIPPED_BINDING_FAILED",
                    "reason": "Binding failed: off-actor safety audit not analyzed.",
                    "per_step_off_actor_non_noop_count": [],
                    "max_off_actor_non_noop_count": None,
                    "total_off_actor_non_noop_count": None,
                    "off_actor_predicted_action_types": {},
                    "off_actor_predictions_reached_command_build": None,
                    "off_actor_predictions_reached_submission": None,
                    "off_actor_status": "STAGE10D18_OFF_ACTOR_MISLOCALIZATION_DETECTED",
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )
        summary_path.write_text(
            json.dumps(
                {
                    "generated_at_utc": _utc_now(),
                    "run_steps_completed": len(steps),
                    "terminal_result": manifest.get("terminal_reason") or "none",
                    "active_checkpoint_path": active_checkpoint_path,
                    "active_checkpoint_basename": active_checkpoint_basename,
                    "visible_behavior_observed": False,
                    "initial_b2_harvest_preserved": False,
                    "initial_c3_produce_preserved": False,
                    "units_produced_count": 0,
                    "produced_units_visible_in_observation": 0,
                    "produced_units_owner_unit_encoding_valid": 0,
                    "total_move_predictions": 0,
                    "total_move_commands_built": 0,
                    "total_move_commands_accepted": 0,
                    "units_that_changed_position_count": 0,
                    "move_driven_position_change_count": 0,
                    "total_attack_predictions": 0,
                    "total_attack_commands_accepted": 0,
                    "enemy_engagement_observed": False,
                    "base_destroyed_observed": False,
                    "off_actor_safety_status": "SKIPPED_BINDING_FAILED",
                    "primary_failure_or_success_mode": "binding_failure",
                    "classification_labels": [
                        "STAGE10D18_CHECKPOINT_BINDING_FAILED",
                        "STAGE10D18_INFERENCE_FALLBACK_USED",
                        "STAGE10D18_LOGITS_SHAPES_INVALID",
                        "STAGE10D18_RUNTIME_REDEPLOY_FAIL",
                    ],
                    "primary_next_gate": minimal_gate,
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )

        report_lines = [
            "# STAGE10D18_RUNTIME_BC_REDEPLOY_EVAL_REPORT",
            "",
            "## 1. Purpose and constraints",
            "- Stage10D.18 is runtime redeploy evaluation only (no PPO/training/checkpoint mutation/runtime semantic changes).",
            "",
            "## 2. Checkpoint binding verification",
            f"- active_checkpoint_path: {active_checkpoint_path}",
            f"- active_checkpoint_basename: {active_checkpoint_basename}",
            f"- expected_checkpoint_basename: {TARGET_CHECKPOINT_BASENAME}",
            f"- model_loaded: {model_loaded}",
            f"- predicted_source: {predicted_source}",
            f"- fallback_used: {fallback_used}",
            f"- fake_logits_used: {fake_logits_used}",
            f"- heuristic_policy_path_used: {heuristic_policy_path_used}",
            f"- logits_shapes_valid: {logits_shapes_valid and observation_shape_valid}",
            "",
            "## 3. Classification labels",
        ]
        for label in binding_labels:
            report_lines.append(f"- {label}")
        report_lines += [
            "",
            "## 4. Primary next gate",
            f"- {minimal_gate}",
            "",
            "## 5. What not to do next",
            "- Do not run PPO.",
            "- Do not train teacher/student.",
            "- Do not mutate checkpoint.",
            "- Do not add runtime fallback/remap heuristics.",
        ]
        report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
        print(binding_path.as_posix())
        print(trace_path.as_posix())
        print(lifecycle_path.as_posix())
        print(move_path.as_posix())
        print(action_dist_path.as_posix())
        print(off_actor_path.as_posix())
        print(summary_path.as_posix())
        print(report_path.as_posix())
        return 0

    trace_rows: list[dict[str, Any]] = []
    action_dist_rows: list[dict[str, Any]] = []
    move_path_rows: list[dict[str, Any]] = []

    active_units: dict[str, UnitState] = {}
    serial_by_type: dict[str, int] = defaultdict(int)
    unit_hist: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unit_spawn_meta: dict[str, dict[str, Any]] = {}
    step_positions_by_unit: dict[int, dict[str, tuple[int, int]]] = {}

    move_decoder_reject = Counter()
    move_applier_reject = Counter()
    move_match_reject = Counter()

    off_actor_total = 0
    off_actor_max = 0
    off_actor_types = Counter()
    off_actor_built_any = False
    off_actor_submitted_any = False

    move_predictions_total = 0
    move_commands_built_total = 0
    move_to_applier_total = 0
    move_to_match_total = 0
    move_commands_accepted_total = 0
    attack_predictions_total = 0
    attack_commands_accepted = 0
    harvest_commands_accepted = 0
    produce_commands_accepted = 0

    b2_step1 = None
    c3_step1 = None
    step1_off_actor_non_noop = 0

    for step in steps:
        snapshot = _read_json(snapshot_by_step[step])
        rows = _read_jsonl(cell_by_step[step])
        rows_by_flat = {int(r.get("cell_index", -1)): r for r in rows}

        unit_positions = snapshot.get("unit_positions") or []
        friendly_units = [u for u in unit_positions if u.get("owner") == "Player1" and u.get("unit_type") != "Resource"]
        friendly_units_sorted = sorted(friendly_units, key=lambda u: (int(u.get("x", -1)), int(u.get("y", -1)), str(u.get("unit_type") or "")))

        idx_to_unit_id = _assign_units(step, friendly_units_sorted, active_units, serial_by_type)
        step_positions_by_unit[step] = {}

        step_action_pred_counts = Counter({n: 0 for n in ACTION_NAMES})
        step_cmd_accept_counts = Counter({n: 0 for n in ACTION_NAMES})
        step_friendly_records: list[dict[str, Any]] = []
        occupancy = {(int(u.get("x", -1)), int(u.get("y", -1))): (u.get("owner"), u.get("unit_type")) for u in unit_positions}

        for idx, unit in enumerate(friendly_units_sorted):
            uid = idx_to_unit_id[idx]
            x = int(unit.get("x", -1))
            y = int(unit.get("y", -1))
            flat = y * 24 + x if x >= 0 and y >= 0 else -1
            row = rows_by_flat.get(flat, {})

            pred = str(row.get("predicted_action_type") or "NoOp")
            probs = _probs(row)
            step_action_pred_counts[pred] += 1

            command_built = bool(row.get("command_built"))
            applier_reached = bool(row.get("applier_submission_reached"))
            applier_accepted = bool(row.get("applier_accepted")) if applier_reached else None

            action_applier_reject_reason = None
            if bool(row.get("applier_rejected")):
                action_applier_reject_reason = row.get("applier_reject_reason") or None

            rec = {
                "step": step,
                "unit_id": uid,
                "unit_type": str(unit.get("unit_type") or "Unknown"),
                "x": x,
                "y": y,
                "flat_index": flat,
                "decoded_owner": str(row.get("decoded_observation_owner") or ""),
                "decoded_unit_type": str(row.get("decoded_observation_unit_type") or ""),
                "predicted_action_type": pred,
                "action_type_probs": probs,
                "move_dir": int(row.get("move_dir") or 0),
                "harvest_dir": int(row.get("harvest_dir") or 0),
                "return_dir": int(row.get("return_dir") or 0),
                "produce_dir": int(row.get("produce_dir") or 0),
                "produce_unit_type": int(row.get("produce_unit_type") or 0),
                "attack_target_local": int(row.get("attack_target_local") or 0),
                "command_built": command_built,
                "decoder_reject_reason": row.get("decoder_reject_reason") or None,
                "action_applier_reached": applier_reached,
                "action_applier_accepted": applier_accepted,
                "action_applier_reject_reason": action_applier_reject_reason,
                "match_manager_apply_command_reached": applier_reached,
                "match_manager_accepted": applier_accepted,
                "match_manager_reject_reason": action_applier_reject_reason,
            }
            step_friendly_records.append(rec)
            unit_hist[uid].append(rec)
            step_positions_by_unit[step][uid] = (x, y)

            if uid not in unit_spawn_meta:
                unit_spawn_meta[uid] = {
                    "unit_type": rec["unit_type"],
                    "spawn_step": step,
                    "spawn_position": [x, y],
                }

            if applier_reached and applier_accepted is True:
                step_cmd_accept_counts[pred] += 1

            if pred == "Move":
                move_predictions_total += 1
                md = rec["move_dir"]
                dx, dy = MOVE_DELTAS.get(md, (0, 0))
                tx = x + dx
                ty = y + dy
                in_bounds = 0 <= tx < 24 and 0 <= ty < 24
                occ = occupancy.get((tx, ty)) if in_bounds else None
                target_occupied = occ is not None

                if command_built:
                    move_commands_built_total += 1
                else:
                    move_decoder_reject[rec["decoder_reject_reason"] or "unknown"] += 1

                if applier_reached:
                    move_to_applier_total += 1
                    move_to_match_total += 1
                    if applier_accepted is True:
                        move_commands_accepted_total += 1
                    else:
                        reason = rec["action_applier_reject_reason"] or "unknown"
                        move_applier_reject[reason] += 1
                        move_match_reject[reason] += 1

                move_path_rows.append(
                    {
                        "step": step,
                        "unit_id": uid,
                        "unit_type": rec["unit_type"],
                        "source_cell": {"x": x, "y": y, "flat": flat},
                        "predicted_action": "Move",
                        "p_move": probs["move"],
                        "p_noop": probs["noop"],
                        "move_dir": md,
                        "move_dir_name": MOVE_DIR_NAMES.get(md, "unknown"),
                        "decoded_target_cell": {"x": tx, "y": ty, "flat": (ty * 24 + tx) if in_bounds else -1},
                        "target_cell_in_bounds": in_bounds,
                        "target_cell_occupied": target_occupied,
                        "target_cell_passable_or_empty": None,
                        "command_built": command_built,
                        "decoder_reject_reason": rec["decoder_reject_reason"],
                        "action_applier_reached": applier_reached,
                        "action_applier_accepted": applier_accepted,
                        "action_applier_reject_reason": rec["action_applier_reject_reason"],
                        "match_manager_apply_command_reached": applier_reached,
                        "match_manager_accepted": applier_accepted,
                        "match_manager_reject_reason": rec["match_manager_reject_reason"],
                        "position_changed_after_command": None,
                    }
                )

            if pred == "Attack":
                attack_predictions_total += 1

        harvest_commands_accepted += step_cmd_accept_counts["Harvest"]
        produce_commands_accepted += step_cmd_accept_counts["Produce"]
        attack_commands_accepted += step_cmd_accept_counts["Attack"]

        step_off_actor_non_noop = 0
        for row in rows:
            if bool(row.get("runtime_is_friendly_actor")):
                continue
            pred = str(row.get("predicted_action_type") or "NoOp")
            if pred != "NoOp":
                step_off_actor_non_noop += 1
                off_actor_types[pred] += 1
                if bool(row.get("command_built")):
                    off_actor_built_any = True
                if bool(row.get("applier_submission_reached")):
                    off_actor_submitted_any = True

        off_actor_total += step_off_actor_non_noop
        off_actor_max = max(off_actor_max, step_off_actor_non_noop)
        if step == 1:
            step1_off_actor_non_noop = step_off_actor_non_noop
            b2 = rows_by_flat.get(25, {})
            c3 = rows_by_flat.get(50, {})
            b2_step1 = {
                "predicted_action": str(b2.get("predicted_action_type") or "NoOp"),
                "probabilities": _probs(b2),
                "command_built": bool(b2.get("command_built")),
                "accepted": bool(b2.get("applier_accepted")) if bool(b2.get("applier_submission_reached")) else None,
            }
            c3_step1 = {
                "predicted_action": str(c3.get("predicted_action_type") or "NoOp"),
                "probabilities": _probs(c3),
                "command_built": bool(c3.get("command_built")),
                "accepted": bool(c3.get("applier_accepted")) if bool(c3.get("applier_submission_reached")) else None,
            }

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
                "off_actor_non_noop_count": step_off_actor_non_noop,
            }
        )

        trace_rows.append(
            {
                "step": step,
                "friendly_units": step_friendly_records,
            }
        )

    # Resolve move-driven position changes.
    moved_after_move_units: set[str] = set()
    for row in move_path_rows:
        uid = str(row["unit_id"])
        step = int(row["step"])
        here = step_positions_by_unit.get(step, {}).get(uid)
        nxt = step_positions_by_unit.get(step + 1, {}).get(uid)
        changed = None
        if row["match_manager_accepted"] is True and here is not None and nxt is not None:
            changed = here != nxt
            if changed:
                moved_after_move_units.add(uid)
        row["position_changed_after_command"] = changed

    # Produced unit lifecycle.
    step1_ids = {uid for uid, meta in unit_spawn_meta.items() if int(meta["spawn_step"]) == 1}
    produced_ids = sorted(uid for uid in unit_spawn_meta if uid not in step1_ids)

    produced_units_visible = 0
    produced_owner_valid = 0
    produced_with_move_pred = 0
    produced_with_move_built = 0
    produced_with_move_accepted = 0
    produced_that_moved = 0

    lifecycle_units: list[dict[str, Any]] = []
    for uid in produced_ids:
        hist = unit_hist.get(uid, [])
        if not hist:
            continue

        produced_units_visible += 1
        owner_valid = all(h.get("decoded_owner") in ("", "Player1") for h in hist) and all(
            h.get("decoded_unit_type") in ("", h.get("unit_type")) for h in hist
        )
        if owner_valid:
            produced_owner_valid += 1

        first_non_noop = next((h["step"] for h in hist if h["predicted_action_type"] != "NoOp"), None)
        first_move_pred = next((h["step"] for h in hist if h["predicted_action_type"] == "Move"), None)
        first_move_built = next((h["step"] for h in hist if h["predicted_action_type"] == "Move" and h["command_built"]), None)
        first_move_acc = next((h["step"] for h in hist if h["predicted_action_type"] == "Move" and h["match_manager_accepted"] is True), None)

        positions = [[h["step"], h["x"], h["y"]] for h in hist]
        first_pos = (hist[0]["x"], hist[0]["y"])
        first_pos_change = next((h["step"] for h in hist if (h["x"], h["y"]) != first_pos), None)
        moved = first_pos_change is not None

        max_p_move = max(float(h["action_type_probs"].get("move", 0.0)) for h in hist)
        max_p_attack = max(float(h["action_type_probs"].get("attack", 0.0)) for h in hist)

        ever_pred_move = first_move_pred is not None
        ever_built_move = first_move_built is not None
        ever_acc_move = first_move_acc is not None

        if ever_pred_move:
            produced_with_move_pred += 1
        if ever_built_move:
            produced_with_move_built += 1
        if ever_acc_move:
            produced_with_move_accepted += 1
        if moved:
            produced_that_moved += 1

        decoder_reasons = sorted({str(h.get("decoder_reject_reason")) for h in hist if h.get("decoder_reject_reason")})
        applier_reasons = sorted({str(h.get("action_applier_reject_reason")) for h in hist if h.get("action_applier_reject_reason")})
        match_reasons = sorted({str(h.get("match_manager_reject_reason")) for h in hist if h.get("match_manager_reject_reason")})

        lifecycle_units.append(
            {
                "unit_id": uid,
                "unit_type": unit_spawn_meta[uid]["unit_type"],
                "spawn_step": int(unit_spawn_meta[uid]["spawn_step"]),
                "spawn_position": unit_spawn_meta[uid]["spawn_position"],
                "first_seen_in_observation_step": hist[0]["step"],
                "owner_unit_encoding_valid": owner_valid,
                "first_predicted_action": hist[0]["predicted_action_type"],
                "first_non_noop_prediction_step": first_non_noop,
                "first_move_prediction_step": first_move_pred,
                "first_move_command_built_step": first_move_built,
                "first_move_command_accepted_step": first_move_acc,
                "first_position_change_step": first_pos_change,
                "positions_over_time": positions,
                "max_p_move": max_p_move,
                "max_p_attack": max_p_attack,
                "ever_predicted_move": ever_pred_move,
                "ever_built_move_command": ever_built_move,
                "ever_accepted_move_command": ever_acc_move,
                "ever_moved": moved,
                "all_decoder_reject_reasons": decoder_reasons,
                "all_applier_reject_reasons": applier_reasons,
                "all_matchmanager_reject_reasons": match_reasons,
            }
        )

    lifecycle_payload = {
        "generated_at_utc": _utc_now(),
        "run_steps": len(steps),
        "produced_units_count": len(produced_ids),
        "produced_units_visible_in_observation": produced_units_visible,
        "produced_units_owner_unit_encoding_valid": produced_owner_valid,
        "produced_units_with_move_prediction_count": produced_with_move_pred,
        "produced_units_with_move_command_built_count": produced_with_move_built,
        "produced_units_with_move_command_accepted_count": produced_with_move_accepted,
        "produced_units_that_moved_count": produced_that_moved,
        "units": lifecycle_units,
    }

    units_changed_after_move = len(moved_after_move_units)
    move_audit_payload = {
        "generated_at_utc": _utc_now(),
        "total_move_predictions": move_predictions_total,
        "total_move_commands_built": move_commands_built_total,
        "total_move_commands_submitted_to_action_applier": move_to_applier_total,
        "total_move_commands_reached_match_manager": move_to_match_total,
        "total_move_commands_accepted": move_commands_accepted_total,
        "total_units_that_changed_position_after_move": units_changed_after_move,
        "move_decoder_reject_counts_by_reason": dict(move_decoder_reject),
        "move_applier_reject_counts_by_reason": dict(move_applier_reject),
        "move_matchmanager_reject_counts_by_reason": dict(move_match_reject),
        "events": move_path_rows,
    }

    b2_harvest_preserved = bool(
        b2_step1
        and b2_step1["predicted_action"] == "Harvest"
        and b2_step1["probabilities"]["harvest"] > b2_step1["probabilities"]["noop"]
    )
    c3_produce_preserved = bool(
        c3_step1
        and c3_step1["predicted_action"] == "Produce"
        and c3_step1["probabilities"]["produce"] > c3_step1["probabilities"]["noop"]
    )
    initial_acceptance = bool(
        action_dist_rows
        and (
            action_dist_rows[0]["accepted_Harvest_commands"] > 0
            or action_dist_rows[0]["accepted_Produce_commands"] > 0
        )
    )

    produced_visible_and_valid = (produced_units_visible == len(produced_ids)) and (produced_owner_valid == len(produced_ids))

    move_predictions_present = move_predictions_total > 0
    move_commands_built = move_commands_built_total > 0
    move_commands_accepted = move_commands_accepted_total > 0
    move_driven_position_change = units_changed_after_move > 0

    behavior_progress_beyond_production = bool(move_driven_position_change or attack_commands_accepted > 0)
    economy_only_behavior = produce_commands_accepted > 0 and not behavior_progress_beyond_production
    produce_loop_no_movement = len(produced_ids) > 0 and not move_predictions_present
    attack_behavior_present = attack_predictions_total > 0 or attack_commands_accepted > 0

    temporal_labels: list[str] = []
    if b2_harvest_preserved and c3_produce_preserved:
        temporal_labels.append("INITIAL_HARVEST_PRODUCE_PRESERVED")
    if move_predictions_present:
        temporal_labels.append("MOVEMENT_PREDICTIONS_PRESENT")
    if move_commands_accepted:
        temporal_labels.append("MOVEMENT_COMMANDS_ACCEPTED")
    if move_predictions_present and not move_commands_accepted:
        temporal_labels.append("MOVEMENT_PREDICTED_BUT_REJECTED")
    if economy_only_behavior:
        temporal_labels.append("ECONOMY_ONLY_BEHAVIOR_PERSISTED")
    if produce_loop_no_movement:
        temporal_labels.append("PRODUCE_LOOP_NO_MOVEMENT_PERSISTED")
    if attack_predictions_total > 0:
        temporal_labels.append("ATTACK_PREDICTIONS_PRESENT")
    if not attack_behavior_present:
        temporal_labels.append("ATTACK_BEHAVIOR_ABSENT")
    if behavior_progress_beyond_production:
        temporal_labels.append("BEHAVIOR_PROGRESS_BEYOND_PRODUCTION")

    action_distribution_payload = {
        "generated_at_utc": _utc_now(),
        "steps": action_dist_rows,
        "temporal_pattern_labels": temporal_labels,
    }

    off_actor_safe = (off_actor_total == 0 and not off_actor_built_any and not off_actor_submitted_any)
    off_actor_status = "STAGE10D18_OFF_ACTOR_SAFE"
    if off_actor_built_any or off_actor_submitted_any:
        off_actor_status = "STAGE10D18_OFF_ACTOR_COMMAND_BUILD_RISK"
    elif off_actor_total > 0:
        off_actor_status = "STAGE10D18_OFF_ACTOR_MISLOCALIZATION_DETECTED"

    off_actor_payload = {
        "generated_at_utc": _utc_now(),
        "per_step_off_actor_non_noop_count": [
            {"step": r["step"], "off_actor_non_noop_count": r["off_actor_non_noop_count"]}
            for r in action_dist_rows
        ],
        "max_off_actor_non_noop_count": off_actor_max,
        "total_off_actor_non_noop_count": off_actor_total,
        "off_actor_predicted_action_types": dict(off_actor_types),
        "off_actor_predictions_reached_command_build": off_actor_built_any,
        "off_actor_predictions_reached_submission": off_actor_submitted_any,
        "status": off_actor_status,
    }

    # Primary gate policy from Stage10D.18 rules.
    if not binding_ok:
        primary_next_gate = "GO_FOR_STAGE10D18_CHECKPOINT_BINDING_FIX"
    elif not (b2_harvest_preserved and c3_produce_preserved):
        primary_next_gate = "GO_FOR_STAGE10D17_TRAINING_BALANCE_FIX"
    elif move_predictions_present and not move_commands_built:
        primary_next_gate = "GO_FOR_STAGE10D19_MOVE_BRANCH_DECODER_AUDIT"
    elif move_commands_built and move_to_applier_total > 0 and move_commands_accepted_total == 0 and sum(move_applier_reject.values()) > 0:
        primary_next_gate = "GO_FOR_STAGE10D19_ACTION_APPLIER_MOVE_VALIDATION_AUDIT"
    elif move_to_match_total > 0 and (move_commands_accepted_total == 0 or (move_commands_accepted_total > 0 and not move_driven_position_change)):
        primary_next_gate = "GO_FOR_STAGE10D19_MATCHMANAGER_MOVE_ACCEPTANCE_AUDIT"
    elif (not move_predictions_present) and produced_visible_and_valid and b2_harvest_preserved and c3_produce_preserved:
        primary_next_gate = "GO_FOR_STAGE10D19_MOVEMENT_POLICY_REBALANCE"
    elif move_predictions_present and move_commands_accepted and move_driven_position_change and behavior_progress_beyond_production and not attack_behavior_present:
        primary_next_gate = "GO_FOR_STAGE10D19_ATTACK_BEHAVIOR_AUGMENTATION"
    elif move_predictions_present and move_commands_built and move_commands_accepted and move_driven_position_change and off_actor_safe:
        primary_next_gate = "GO_FOR_STAGE10D19_EXTENDED_TACTICAL_EVALUATION"
    else:
        primary_next_gate = "GO_FOR_STAGE10D18_RUNTIME_REDEPLOY_RERUN"

    labels: list[str] = []
    labels.extend(binding_labels)

    if b2_harvest_preserved:
        labels.append("STAGE10D18_INITIAL_B2_HARVEST_PRESERVED")
    if c3_produce_preserved:
        labels.append("STAGE10D18_INITIAL_C3_PRODUCE_PRESERVED")
    if initial_acceptance:
        labels.append("STAGE10D18_INITIAL_COMMAND_ACCEPTANCE_CONFIRMED")
    if not (b2_harvest_preserved and c3_produce_preserved):
        labels.append("STAGE10D18_INITIAL_BEHAVIOR_REGRESSED")

    if len(produced_ids) > 0:
        labels.append("STAGE10D18_UNITS_PRODUCED_CONFIRMED")
    if produced_units_visible == len(produced_ids) and len(produced_ids) > 0:
        labels.append("STAGE10D18_PRODUCED_UNITS_VISIBLE_IN_OBSERVATION")
    if produced_owner_valid == len(produced_ids) and len(produced_ids) > 0:
        labels.append("STAGE10D18_PRODUCED_UNITS_OWNER_UNIT_ENCODING_VALID")

    labels.append("STAGE10D18_MOVE_PREDICTIONS_PRESENT" if move_predictions_present else "STAGE10D18_MOVE_PREDICTIONS_ABSENT")
    labels.append("STAGE10D18_MOVE_COMMANDS_BUILT" if move_commands_built else "STAGE10D18_MOVE_COMMANDS_NOT_BUILT")
    if move_commands_accepted:
        labels.append("STAGE10D18_MOVE_COMMANDS_ACCEPTED")
    elif move_predictions_present:
        labels.append("STAGE10D18_MOVE_COMMANDS_REJECTED")
    if move_driven_position_change:
        labels.append("STAGE10D18_UNITS_CHANGED_POSITION")
        labels.append("STAGE10D18_MOVE_DRIVEN_POSITION_CHANGE_CONFIRMED")
    else:
        labels.append("STAGE10D18_NO_MOVE_DRIVEN_POSITION_CHANGE")

    if behavior_progress_beyond_production:
        labels.append("STAGE10D18_BEHAVIOR_PROGRESS_BEYOND_PRODUCTION")
    if economy_only_behavior:
        labels.append("STAGE10D18_ECONOMY_ONLY_BEHAVIOR_PERSISTED")
    if produce_loop_no_movement:
        labels.append("STAGE10D18_PRODUCE_LOOP_NO_MOVEMENT_PERSISTED")
    labels.append("STAGE10D18_ATTACK_BEHAVIOR_PRESENT" if attack_behavior_present else "STAGE10D18_ATTACK_BEHAVIOR_ABSENT")

    labels.append(off_actor_status)

    if primary_next_gate in ("GO_FOR_STAGE10D19_EXTENDED_TACTICAL_EVALUATION", "GO_FOR_STAGE10D19_ATTACK_BEHAVIOR_AUGMENTATION"):
        labels.append("STAGE10D18_RUNTIME_REDEPLOY_SUCCESS")
        runtime_mode = "success"
    elif primary_next_gate == "GO_FOR_STAGE10D18_CHECKPOINT_BINDING_FIX":
        labels.append("STAGE10D18_RUNTIME_REDEPLOY_FAIL")
        runtime_mode = "binding_failure"
    elif primary_next_gate in (
        "GO_FOR_STAGE10D19_MOVE_BRANCH_DECODER_AUDIT",
        "GO_FOR_STAGE10D19_ACTION_APPLIER_MOVE_VALIDATION_AUDIT",
        "GO_FOR_STAGE10D19_MATCHMANAGER_MOVE_ACCEPTANCE_AUDIT",
        "GO_FOR_STAGE10D19_MOVEMENT_POLICY_REBALANCE",
    ):
        labels.append("STAGE10D18_RUNTIME_REDEPLOY_PARTIAL_SUCCESS")
        runtime_mode = "partial_runtime_progress"
    else:
        labels.append("STAGE10D18_RUNTIME_REDEPLOY_FAIL")
        runtime_mode = "insufficient_evidence"

    visual_summary = {
        "generated_at_utc": _utc_now(),
        "run_steps_completed": len(steps),
        "terminal_result": manifest.get("terminal_reason") or "none",
        "active_checkpoint_path": active_checkpoint_path,
        "active_checkpoint_basename": active_checkpoint_basename,
        "visible_behavior_observed": (harvest_commands_accepted + produce_commands_accepted + move_commands_accepted_total + attack_commands_accepted) > 0,
        "initial_b2_harvest_preserved": b2_harvest_preserved,
        "initial_c3_produce_preserved": c3_produce_preserved,
        "units_produced_count": len(produced_ids),
        "produced_units_visible_in_observation": produced_units_visible,
        "produced_units_owner_unit_encoding_valid": produced_owner_valid,
        "total_move_predictions": move_predictions_total,
        "total_move_commands_built": move_commands_built_total,
        "total_move_commands_accepted": move_commands_accepted_total,
        "units_that_changed_position_count": produced_that_moved,
        "move_driven_position_change_count": units_changed_after_move,
        "total_attack_predictions": attack_predictions_total,
        "total_attack_commands_accepted": attack_commands_accepted,
        "enemy_engagement_observed": attack_commands_accepted > 0,
        "base_destroyed_observed": False,
        "off_actor_safety_status": off_actor_status,
        "primary_failure_or_success_mode": runtime_mode,
        "classification_labels": labels,
        "primary_next_gate": primary_next_gate,
    }

    # Write final artifacts.
    trace_path = out_dir / "stage10d18_runtime_redeploy_trace.jsonl"
    lifecycle_path = out_dir / "stage10d18_produced_unit_lifecycle.json"
    move_path = out_dir / "stage10d18_movement_command_path_audit.json"
    action_dist_path = out_dir / "stage10d18_action_distribution_over_time.json"
    off_actor_path = out_dir / "stage10d18_off_actor_safety_audit.json"
    summary_path = out_dir / "stage10d18_visual_behavior_summary.json"
    report_path = out_dir / "STAGE10D18_RUNTIME_BC_REDEPLOY_EVAL_REPORT.md"

    with trace_path.open("w", encoding="utf-8") as f:
        for row in trace_rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")

    lifecycle_path.write_text(json.dumps(lifecycle_payload, ensure_ascii=True, indent=2), encoding="utf-8")
    move_path.write_text(json.dumps(move_audit_payload, ensure_ascii=True, indent=2), encoding="utf-8")
    action_dist_path.write_text(json.dumps(action_distribution_payload, ensure_ascii=True, indent=2), encoding="utf-8")
    off_actor_path.write_text(json.dumps(off_actor_payload, ensure_ascii=True, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(visual_summary, ensure_ascii=True, indent=2), encoding="utf-8")

    report_lines: list[str] = []
    report_lines.append("# STAGE10D18_RUNTIME_BC_REDEPLOY_EVAL_REPORT")
    report_lines.append("")
    report_lines.append("## 1. Purpose and constraints")
    report_lines.append("- Runtime redeploy evaluation only: no PPO, no teacher/student training, no checkpoint mutation, no decoder/applier/match manager semantic changes.")
    report_lines.append("")
    report_lines.append("## 2. Stage10D.17 evidence recap")
    report_lines.append("- Stage10D.17 closed with movement-augmented dataset/training and gate GO_FOR_STAGE10D18_RUNTIME_BC_REDEPLOY_EVAL.")
    report_lines.append("")
    report_lines.append("## 3. Checkpoint binding verification")
    report_lines.append(f"- active_checkpoint_path: {active_checkpoint_path}")
    report_lines.append(f"- active_checkpoint_basename: {active_checkpoint_basename}")
    report_lines.append(f"- expected_basename: {TARGET_CHECKPOINT_BASENAME}")
    report_lines.append(f"- model_loaded: {model_loaded}")
    report_lines.append(f"- predicted_source: {predicted_source}")
    report_lines.append(f"- fallback_used: {fallback_used}")
    report_lines.append(f"- fake_logits_used: {fake_logits_used}")
    report_lines.append(f"- heuristic_policy_path_used: {heuristic_policy_path_used}")
    report_lines.append(f"- logits_shapes_valid: {logits_shapes_valid and observation_shape_valid}")
    report_lines.append("")
    report_lines.append("## 4. Run configuration")
    report_lines.append(f"- scene: {manifest.get('scene')}")
    report_lines.append(f"- target_steps: {manifest.get('target_steps')}")
    report_lines.append(f"- steps_completed: {manifest.get('steps_completed')}")
    report_lines.append(f"- terminal: {manifest.get('terminal_reason')}")
    report_lines.append("")
    report_lines.append("## 5. Initial Harvest/Produce regression check")
    report_lines.append(f"- B2: {b2_step1}")
    report_lines.append(f"- C3: {c3_step1}")
    report_lines.append(f"- actor_cell_predicted_noop_share_step1: {action_dist_rows[0]['predicted_NoOp_share'] if action_dist_rows else None}")
    report_lines.append(f"- off_actor_non_noop_count_step1: {step1_off_actor_non_noop}")
    report_lines.append(f"- commands_built_step1: {(action_dist_rows[0]['accepted_Harvest_commands'] + action_dist_rows[0]['accepted_Produce_commands'] + action_dist_rows[0]['accepted_Move_commands'] + action_dist_rows[0]['accepted_Attack_commands']) if action_dist_rows else 0}")
    report_lines.append("")
    report_lines.append("## 6. Produced unit lifecycle")
    report_lines.append(f"- produced_units_count: {len(produced_ids)}")
    report_lines.append(f"- produced_units_visible_in_observation: {produced_units_visible}")
    report_lines.append(f"- produced_units_owner_unit_encoding_valid: {produced_owner_valid}")
    report_lines.append(f"- produced_units_with_move_prediction_count: {produced_with_move_pred}")
    report_lines.append(f"- produced_units_with_move_command_built_count: {produced_with_move_built}")
    report_lines.append(f"- produced_units_with_move_command_accepted_count: {produced_with_move_accepted}")
    report_lines.append(f"- produced_units_that_moved_count: {produced_that_moved}")
    report_lines.append("")
    report_lines.append("## 7. Movement command path audit")
    report_lines.append(f"- total_move_predictions: {move_predictions_total}")
    report_lines.append(f"- total_move_commands_built: {move_commands_built_total}")
    report_lines.append(f"- total_move_commands_submitted_to_action_applier: {move_to_applier_total}")
    report_lines.append(f"- total_move_commands_reached_match_manager: {move_to_match_total}")
    report_lines.append(f"- total_move_commands_accepted: {move_commands_accepted_total}")
    report_lines.append(f"- total_units_that_changed_position_after_move: {units_changed_after_move}")
    report_lines.append(f"- move_decoder_reject_counts_by_reason: {dict(move_decoder_reject)}")
    report_lines.append(f"- move_applier_reject_counts_by_reason: {dict(move_applier_reject)}")
    report_lines.append(f"- move_matchmanager_reject_counts_by_reason: {dict(move_match_reject)}")
    report_lines.append("")
    report_lines.append("## 8. Action distribution over time")
    report_lines.append(f"- temporal_pattern_labels: {temporal_labels}")
    report_lines.append("")
    report_lines.append("## 9. Off-actor safety audit")
    report_lines.append(f"- off_actor_safety_status: {off_actor_status}")
    report_lines.append(f"- max_off_actor_non_noop_count: {off_actor_max}")
    report_lines.append(f"- total_off_actor_non_noop_count: {off_actor_total}")
    report_lines.append("")
    report_lines.append("## 10. Visual behavior summary")
    report_lines.append(f"- run_steps_completed: {len(steps)}")
    report_lines.append(f"- terminal_result: {manifest.get('terminal_reason')}")
    report_lines.append(f"- primary_failure_or_success_mode: {runtime_mode}")
    report_lines.append("")
    report_lines.append("## 11. Classification labels")
    for label in labels:
        report_lines.append(f"- {label}")
    report_lines.append("")
    report_lines.append("## 12. Primary next gate")
    report_lines.append(f"- {primary_next_gate}")
    report_lines.append("")
    report_lines.append("## 13. What not to do next")
    report_lines.append("- Do not run PPO.")
    report_lines.append("- Do not train teacher.")
    report_lines.append("- Do not train student.")
    report_lines.append("- Do not mutate checkpoint.")
    report_lines.append("- Do not add force-move/heuristic/random/current_action remap fallbacks.")
    report_lines.append("")
    report_lines.append("## Explicit required answers")
    report_lines.append(f"- Was Stage10D.17 checkpoint loaded? {checkpoint_path_ok}")
    report_lines.append(f"- Were logits real model logits? {predicted_source == 'model_logits' and not fallback_used and not fake_logits_used and not heuristic_policy_path_used}")
    report_lines.append(f"- Did B2 Harvest remain? {b2_harvest_preserved}")
    report_lines.append(f"- Did C3 Produce remain? {c3_produce_preserved}")
    report_lines.append(f"- Were units produced? {len(produced_ids) > 0}")
    report_lines.append(f"- Were produced units visible and correctly encoded? {produced_visible_and_valid}")
    report_lines.append(f"- Did Move predictions appear? {move_predictions_present}")
    report_lines.append(f"- Did Move commands build? {move_commands_built}")
    report_lines.append(f"- Did Move commands reach ActionApplier? {move_to_applier_total > 0}")
    report_lines.append(f"- Did Move commands reach MatchManager? {move_to_match_total > 0}")
    report_lines.append(f"- Did Move commands get accepted? {move_commands_accepted}")
    report_lines.append(f"- Did units physically move because of Move commands? {move_driven_position_change}")
    report_lines.append(f"- Was off-actor safety preserved? {off_actor_safe}")
    report_lines.append(f"- Did behavior progress beyond production? {behavior_progress_beyond_production}")
    if move_predictions_present and not move_commands_built:
        blocker = "decoder"
    elif move_commands_built and move_commands_accepted_total == 0 and sum(move_applier_reject.values()) > 0:
        blocker = "action_applier"
    elif move_to_match_total > 0 and (move_commands_accepted_total == 0 or not move_driven_position_change):
        blocker = "match_manager"
    elif not move_predictions_present:
        blocker = "policy"
    elif move_predictions_present and move_commands_accepted and move_driven_position_change and not attack_behavior_present:
        blocker = "attack_behavior"
    else:
        blocker = "none_major"
    report_lines.append(f"- Is next blocker policy, decoder, applier, match manager, or attack behavior? {blocker}")

    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(binding_path.as_posix())
    print(trace_path.as_posix())
    print(lifecycle_path.as_posix())
    print(move_path.as_posix())
    print(action_dist_path.as_posix())
    print(off_actor_path.as_posix())
    print(summary_path.as_posix())
    print(report_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
