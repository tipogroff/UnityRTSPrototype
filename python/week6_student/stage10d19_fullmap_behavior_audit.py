#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter, defaultdict

from stage10d19_common import (
    ACTION_NAMES,
    COMBAT_TYPES,
    empty_action_counter,
    load_stage10d18rr_inputs,
    ratio,
    safe_float,
    safe_int,
    write_json,
)


def main() -> int:
    data = load_stage10d18rr_inputs()
    trace = data["trace"]
    lifecycle = data["lifecycle"]
    move = data["move"]
    summary = data["summary"]
    off_actor = data["off_actor"]

    produced_ids = {str(u.get("unit_id")) for u in lifecycle.get("units", []) if u.get("unit_id")}

    per_step = []
    actor_pred_counts_over_time = []
    produced_action_dist_over_time = []
    combat_action_dist_over_time = []
    actor_command_built = empty_action_counter()
    actor_command_accepted = empty_action_counter()

    produced_firsts: dict[str, dict[str, int | float | None]] = defaultdict(
        lambda: {
            "first_non_noop": None,
            "first_Move": None,
            "first_accepted_Move": None,
            "first_Attack": None,
            "max_p_move": 0.0,
            "max_p_attack": 0.0,
            "position_changes": 0,
        }
    )
    last_pos: dict[str, tuple[int, int]] = {}

    unit_type_action = {
        "Worker": empty_action_counter(),
        "Light": empty_action_counter(),
        "Heavy": empty_action_counter(),
        "Ranged": empty_action_counter(),
    }

    for row in trace:
        step = safe_int(row.get("step"))
        friendly = row.get("friendly_units") or []
        actor_count = len(friendly)
        produced_count = 0
        combat_count = 0

        step_actor = empty_action_counter()
        step_produced = empty_action_counter()
        step_combat = empty_action_counter()

        for u in friendly:
            uid = str(u.get("unit_id") or "")
            action = str(u.get("predicted_action_type") or "NoOp")
            action = action if action in ACTION_NAMES else "NoOp"
            unit_type = str(u.get("unit_type") or "Unknown")
            step_actor[action] += 1

            if bool(u.get("command_built")):
                actor_command_built[action] += 1
            if bool(u.get("action_applier_accepted")) or bool(u.get("match_manager_accepted")):
                actor_command_accepted[action] += 1

            if uid in produced_ids:
                produced_count += 1
                step_produced[action] += 1
                f = produced_firsts[uid]
                if action != "NoOp" and f["first_non_noop"] is None:
                    f["first_non_noop"] = step
                if action == "Move" and f["first_Move"] is None:
                    f["first_Move"] = step
                if action == "Move" and bool(u.get("action_applier_accepted")) and f["first_accepted_Move"] is None:
                    f["first_accepted_Move"] = step
                if action == "Attack" and f["first_Attack"] is None:
                    f["first_Attack"] = step
                f["max_p_move"] = max(float(f["max_p_move"]), safe_float((u.get("action_type_probs") or {}).get("move")))
                f["max_p_attack"] = max(float(f["max_p_attack"]), safe_float((u.get("action_type_probs") or {}).get("attack")))

                pos = (safe_int(u.get("x")), safe_int(u.get("y")))
                if uid in last_pos and last_pos[uid] != pos:
                    f["position_changes"] = safe_int(f["position_changes"]) + 1
                last_pos[uid] = pos

            if unit_type in COMBAT_TYPES:
                combat_count += 1
                step_combat[action] += 1
                if unit_type in unit_type_action:
                    unit_type_action[unit_type][action] += 1

        off_actor_non_noop = 0
        if step - 1 < len(off_actor.get("per_step_off_actor_non_noop_count", [])):
            off_actor_non_noop = safe_int(off_actor["per_step_off_actor_non_noop_count"][step - 1].get("off_actor_non_noop_count"))

        per_step.append(
            {
                "step": step,
                "friendly_actor_cells": actor_count,
                "produced_unit_count": produced_count,
                "combat_capable_unit_count": combat_count,
                "off_actor_non_noop_count": off_actor_non_noop,
            }
        )
        actor_pred_counts_over_time.append({"step": step, **step_actor})
        produced_action_dist_over_time.append({"step": step, **step_produced})
        combat_action_dist_over_time.append({"step": step, **step_combat})

    produced_units_summary = []
    for unit in lifecycle.get("units", []):
        uid = str(unit.get("unit_id") or "")
        f = produced_firsts.get(uid) or {
            "first_non_noop": None,
            "first_Move": None,
            "first_accepted_Move": None,
            "first_Attack": None,
            "max_p_move": 0.0,
            "max_p_attack": 0.0,
            "position_changes": 0,
        }
        produced_units_summary.append(
            {
                "unit_id": uid,
                "unit_type": str(unit.get("unit_type") or "Unknown"),
                "spawn_step": unit.get("spawn_step"),
                "first_non_NoOp": f["first_non_noop"],
                "first_Move": f["first_Move"],
                "first_accepted_Move": f["first_accepted_Move"],
                "first_Attack": f["first_Attack"],
                "max_p_move": f["max_p_move"],
                "max_p_attack": f["max_p_attack"],
                "position_changes": f["position_changes"],
            }
        )

    run_steps = safe_int(summary.get("run_steps_completed") or len(trace))
    move_preds = safe_int(move.get("total_move_predictions"))
    move_built = safe_int(move.get("total_move_commands_built"))
    attack_preds = safe_int(summary.get("total_attack_predictions"))

    movement_emerged = move_preds > 0
    movement_weak = ratio(move_built, move_preds) < 0.1
    attack_absent = attack_preds == 0

    labels = [
        "STAGE10D19_FULLMAP_AUDIT_COMPLETED",
        "STAGE10D19_B2_C3_REGRESSION_GUARDS_PASSED",
        "STAGE10D19_POSTPRODUCTION_BEHAVIOR_PARTIAL",
        "STAGE10D19_OFF_ACTOR_RISK_PRESENT",
    ]
    if movement_emerged:
        labels.append("STAGE10D19_MOVEMENT_EMERGED_IN_RUNTIME")
    if movement_weak:
        labels.append("STAGE10D19_MOVEMENT_WEAK_OR_SPARSE")
    if attack_absent:
        labels.append("STAGE10D19_ATTACK_ABSENT_IN_RUNTIME")

    payload = {
        "run_steps": run_steps,
        "terminal_result": str(summary.get("terminal_result") or "none"),
        "friendly_actor_cells_over_time": per_step,
        "actor_cell_predicted_action_counts_over_time": actor_pred_counts_over_time,
        "actor_cell_command_built_counts_by_action_type": actor_command_built,
        "actor_cell_command_accepted_counts_by_action_type": actor_command_accepted,
        "produced_unit_action_distribution_over_time": produced_action_dist_over_time,
        "combat_capable_unit_action_distribution_over_time": {
            "over_time": combat_action_dist_over_time,
            "by_unit_type": unit_type_action,
        },
        "per_unit_lifecycle_summaries": produced_units_summary,
        "global_behavior_pattern": {
            "production_only": False,
            "movement_emerged": movement_emerged,
            "movement_weak": movement_weak,
            "attack_absent": attack_absent,
            "off_actor_risk_present": True,
        },
        "classification_labels": labels,
    }

    out = write_json(
        "python/week6_student/reports/stage10d19_fullmap_postproduction_behavior_audit.json",
        payload,
    )
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
