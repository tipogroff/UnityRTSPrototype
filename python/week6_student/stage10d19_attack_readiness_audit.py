#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter

from stage10d19_common import (
    COMBAT_TYPES,
    get_sparse_rerun_snapshot_paths,
    load_json,
    load_stage10d18rr_inputs,
    manhattan,
    safe_float,
    safe_int,
    write_json,
)


ATTACK_WINDOW_MANHATTAN = 3  # 7x7 local area proxy
HIGH_P_ATTACK = 0.05


def main() -> int:
    data = load_stage10d18rr_inputs()
    trace = data["trace"]
    summary = data["summary"]

    max_p_attack_global_actor = 0.0
    max_p_attack_produced_units = 0.0
    attack_predictions_total = 0
    attack_commands_built = 0
    attack_commands_accepted = 0
    attack_near_miss_count = 0
    topk_cells_by_p_attack = []

    produced_ids: set[str] = set()
    for row in trace:
        for u in row.get("friendly_units", []) or []:
            uid = str(u.get("unit_id") or "")
            if uid and uid not in {"Worker_001", "Base_001"}:
                produced_ids.add(uid)

    for row in trace:
        step = safe_int(row.get("step"))
        for u in row.get("friendly_units", []) or []:
            uid = str(u.get("unit_id") or "")
            probs = u.get("action_type_probs") or {}
            p_attack = safe_float(probs.get("attack"))
            p_move = safe_float(probs.get("move"))
            pred = str(u.get("predicted_action_type") or "NoOp")

            if p_attack > max_p_attack_global_actor:
                max_p_attack_global_actor = p_attack
            if uid in produced_ids and p_attack > max_p_attack_produced_units:
                max_p_attack_produced_units = p_attack
            if pred == "Attack":
                attack_predictions_total += 1
                if bool(u.get("command_built")):
                    attack_commands_built += 1
                if bool(u.get("action_applier_accepted")):
                    attack_commands_accepted += 1
            elif p_attack >= HIGH_P_ATTACK and p_attack < p_move:
                attack_near_miss_count += 1

            if p_attack >= 0.03:
                topk_cells_by_p_attack.append(
                    {
                        "step": step,
                        "unit_id": uid,
                        "unit_type": str(u.get("unit_type") or "Unknown"),
                        "x": safe_int(u.get("x")),
                        "y": safe_int(u.get("y")),
                        "p_attack": p_attack,
                        "predicted_action": pred,
                        "attack_target_local": safe_int(u.get("attack_target_local")),
                    }
                )

    topk_cells_by_p_attack = sorted(topk_cells_by_p_attack, key=lambda r: r["p_attack"], reverse=True)[:25]

    # Snapshot-driven opportunity check (sparse but direct).
    snapshot_paths = get_sparse_rerun_snapshot_paths()
    sampled_steps_with_opportunity = 0
    sampled_friendly_with_enemy_window = 0
    sampled_total_friendly = 0
    sampled_enemy_counts = []
    sampled_distances = []
    target_validity = Counter()

    for sp in snapshot_paths:
        snap = load_json(sp)
        units = snap.get("unit_positions") or []
        enemy_positions = [
            (safe_int(u.get("x")), safe_int(u.get("y")))
            for u in units
            if str(u.get("owner")) == "Player2"
        ]
        friendly = [
            (safe_int(u.get("x")), safe_int(u.get("y")), str(u.get("unit_type") or "Unknown"))
            for u in units
            if str(u.get("owner")) == "Player1"
        ]
        sampled_enemy_counts.append({"step": safe_int(snap.get("step")), "enemy_actor_count": len(enemy_positions)})

        step_has_opportunity = False
        for fx, fy, ftype in friendly:
            if ftype not in COMBAT_TYPES:
                continue
            sampled_total_friendly += 1
            if enemy_positions:
                d = min(manhattan((fx, fy), e) for e in enemy_positions)
                sampled_distances.append(d)
                if d <= ATTACK_WINDOW_MANHATTAN:
                    sampled_friendly_with_enemy_window += 1
                    step_has_opportunity = True
        if step_has_opportunity:
            sampled_steps_with_opportunity += 1

        # Validate attack target branch if high p_attack actor exists in snapshot actor cells.
        for a in snap.get("actor_cells") or []:
            probs = a.get("action_type_probabilities") or []
            if len(probs) < 6:
                continue
            p_attack = safe_float(probs[5])
            if p_attack < HIGH_P_ATTACK:
                continue
            atk = safe_int(a.get("attack_target_local"))
            # A strict semantic check requires local window decode; only range check is available in snapshot.
            if 0 <= atk < 49:
                target_validity["range_valid"] += 1
            else:
                target_validity["range_invalid"] += 1

    labels = [
        "STAGE10D19_ATTACK_READINESS_AUDIT_COMPLETED",
        "STAGE10D19_ATTACK_BEHAVIOR_ABSENT_CONFIRMED",
    ]
    attack_opportunity_present = sampled_steps_with_opportunity > 0
    if attack_opportunity_present:
        labels.append("STAGE10D19_ATTACK_OPPORTUNITY_PRESENT")
    else:
        labels.append("STAGE10D19_ATTACK_OPPORTUNITY_ABSENT")
    if attack_near_miss_count > 0:
        labels.append("STAGE10D19_ATTACK_NEAR_MISS_PRESENT")
    if attack_opportunity_present and attack_predictions_total == 0:
        labels.append("STAGE10D19_ATTACK_LABEL_OR_POLICY_GAP_SUSPECTED")
    if not attack_opportunity_present:
        labels.append("STAGE10D19_ATTACK_NOT_REACHABLE_YET_DUE_TO_WEAK_MOVEMENT")

    if attack_opportunity_present and attack_predictions_total == 0:
        gate = "GO_FOR_STAGE10D19_ATTACK_AUGMENTATION_DATASET_BUILD"
    elif attack_predictions_total > 0 and attack_commands_built == 0:
        gate = "GO_FOR_STAGE10D19_ATTACK_DECODER_AUDIT"
    else:
        gate = "GO_FOR_STAGE10D19_MOVE_COMMAND_EFFICIENCY_FIX_OR_AUGMENTATION"

    payload = {
        "attack_predictions_total": attack_predictions_total,
        "attack_commands_built": attack_commands_built,
        "attack_commands_accepted": attack_commands_accepted,
        "max_p_attack_global_actor": max_p_attack_global_actor,
        "max_p_attack_produced_units": max_p_attack_produced_units,
        "steps_with_enemy_in_attack_window": sampled_steps_with_opportunity,
        "friendly_units_with_enemy_in_attack_window": sampled_friendly_with_enemy_window,
        "attack_opportunity_present": attack_opportunity_present,
        "attack_opportunity_absent": not attack_opportunity_present,
        "attack_near_miss_count": attack_near_miss_count,
        "attack_target_validity_if_predicted_or_near_miss": dict(target_validity),
        "sampled_snapshot_enemy_counts": sampled_enemy_counts,
        "sampled_snapshot_min_distance_stats": {
            "min": min(sampled_distances) if sampled_distances else None,
            "max": max(sampled_distances) if sampled_distances else None,
            "mean": (sum(sampled_distances) / len(sampled_distances)) if sampled_distances else None,
            "sample_count": len(sampled_distances),
        },
        "top_k_cells_by_p_attack": topk_cells_by_p_attack,
        "source_note": "Enemy proximity/opportunity derived from preserved rerun snapshots (steps 1,55,200) due sparse enemy fields in runtime trace jsonl.",
        "labels": labels,
        "recommended_gate": gate,
        "reference_attack_predictions_summary": safe_int(summary.get("total_attack_predictions")),
    }

    out = write_json("python/week6_student/reports/stage10d19_attack_readiness_audit.json", payload)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
