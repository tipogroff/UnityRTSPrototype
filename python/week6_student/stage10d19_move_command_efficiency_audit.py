#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter, defaultdict

from stage10d19_common import (
    flat_to_xy,
    in_bounds,
    load_stage10d18rr_inputs,
    p_bucket,
    ratio,
    safe_float,
    safe_int,
    top_competing_action,
    write_json,
)


MOVE_DELTAS = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}


def main() -> int:
    data = load_stage10d18rr_inputs()
    trace = data["trace"]
    move = data["move"]

    produced_ids: set[str] = set()
    for row in trace:
        for u in row.get("friendly_units", []) or []:
            uid = str(u.get("unit_id") or "")
            if uid and uid not in {"Worker_001", "Base_001"}:
                produced_ids.add(uid)

    later_accepted_move = set()
    for row in trace:
        for u in row.get("friendly_units", []) or []:
            if str(u.get("predicted_action_type")) == "Move" and bool(u.get("action_applier_accepted")):
                later_accepted_move.add(str(u.get("unit_id") or ""))

    by_unit_type = Counter()
    by_produced = Counter()
    by_move_dir = Counter()
    by_reject_reason = Counter()
    by_top_competing = Counter()
    by_p_bucket = Counter()
    by_target_kind = Counter()
    by_actor_validity = Counter()

    occupied_target_count = 0
    out_of_bounds_target_count = 0
    valid_target_move_prediction_count = 0
    invalid_target_move_prediction_count = 0
    busy_unit_or_current_action_block_count = 0
    off_actor_move_prediction_count = 0
    friendly_actor_move_prediction_count = 0

    detailed = []

    for ev in move.get("events", []):
        uid = str(ev.get("unit_id") or "")
        unit_type = str(ev.get("unit_type") or "Unknown")
        source = ev.get("source_cell") or {}
        target = ev.get("decoded_target_cell") or {}
        sxy = (safe_int(source.get("x")), safe_int(source.get("y")))
        txy = (safe_int(target.get("x")), safe_int(target.get("y")))

        inb = bool(ev.get("target_cell_in_bounds")) if ev.get("target_cell_in_bounds") is not None else in_bounds(*txy)
        occ = bool(ev.get("target_cell_occupied")) if ev.get("target_cell_occupied") is not None else False
        built = bool(ev.get("command_built"))
        rej = str(ev.get("decoder_reject_reason") or "")
        p_move = safe_float(ev.get("p_move"))
        top_comp = top_competing_action(
            {
                "noop": ev.get("p_noop"),
                "harvest": ev.get("p_harvest"),
                "produce": ev.get("p_produce"),
                "attack": ev.get("p_attack"),
            }
        )

        if inb and not occ:
            valid_target_move_prediction_count += 1
        else:
            invalid_target_move_prediction_count += 1
        if occ:
            occupied_target_count += 1
        if not inb:
            out_of_bounds_target_count += 1

        is_actor = uid != ""
        if is_actor:
            friendly_actor_move_prediction_count += 1
        else:
            off_actor_move_prediction_count += 1

        if "current_action" in rej.lower() or "busy" in rej.lower() or "locked" in rej.lower():
            busy_unit_or_current_action_block_count += 1

        by_unit_type[unit_type] += 1
        by_produced["produced" if uid in produced_ids else "original"] += 1
        by_move_dir[str(ev.get("move_dir_name") or ev.get("move_dir"))] += 1
        by_reject_reason[rej or "none"] += 1
        by_top_competing[top_comp] += 1
        by_p_bucket[p_bucket(p_move)] += 1
        by_target_kind[("occupied" if occ else "empty_or_unknown") + ("_in_bounds" if inb else "_out_of_bounds")] += 1
        by_actor_validity["runtime_is_friendly_actor_true" if is_actor else "runtime_is_friendly_actor_false"] += 1

        detailed.append(
            {
                "step": ev.get("step"),
                "unit_id": uid,
                "unit_type": unit_type,
                "produced_vs_original": "produced" if uid in produced_ids else "original",
                "source_cell": {"x": sxy[0], "y": sxy[1]},
                "move_dir": ev.get("move_dir"),
                "target_cell": {"x": txy[0], "y": txy[1]},
                "target_cell_in_bounds": inb,
                "target_cell_occupied": occ,
                "target_cell_kind": "occupied" if occ else "empty_or_unknown",
                "command_built": built,
                "decoder_filter_reject_reason": rej or "none",
                "same_unit_later_got_accepted_move": uid in later_accepted_move,
                "p_move_bucket": p_bucket(p_move),
                "top_competing_action": top_comp,
                "runtime_is_friendly_actor": is_actor,
                "owner_unit_encoding": "present" if uid else "missing",
            }
        )

    total_move_predictions = safe_int(move.get("total_move_predictions"))
    total_move_commands_built = safe_int(move.get("total_move_commands_built"))
    total_move_commands_accepted = safe_int(move.get("total_move_commands_accepted"))

    prediction_to_build = ratio(total_move_commands_built, total_move_predictions)
    build_to_accept = ratio(total_move_commands_accepted, total_move_commands_built)
    prediction_to_accept = ratio(total_move_commands_accepted, total_move_predictions)

    labels = [
        "STAGE10D19_MOVE_EFFICIENCY_AUDIT_COMPLETED",
        "STAGE10D19_MOVE_RUNTIME_COMMAND_PATH_OK_FOR_BUILT_COMMANDS",
    ]
    if prediction_to_build < 0.2:
        labels.append("STAGE10D19_MOVE_PREDICTION_TO_BUILD_LOW")
    if occupied_target_count >= max(1, invalid_target_move_prediction_count * 0.5):
        labels.append("STAGE10D19_MOVE_TARGET_OCCUPIED_DOMINANT")
    if invalid_target_move_prediction_count > valid_target_move_prediction_count:
        labels.append("STAGE10D19_MOVE_TARGET_INVALID_DOMINANT")
        labels.append("STAGE10D19_MOVE_POLICY_TARGET_SELECTION_SUSPECTED")
    if busy_unit_or_current_action_block_count > 0:
        labels.append("STAGE10D19_MOVE_BUSY_UNIT_GATING_SUSPECTED")
    if by_reject_reason.get("not_built_in_decoder_or_filter", 0) > 0:
        labels.append("STAGE10D19_MOVE_DECODER_FILTER_ALIGNMENT_SUSPECTED")

    if valid_target_move_prediction_count > total_move_commands_built * 3 and by_reject_reason.get("not_built_in_decoder_or_filter", 0) > 0:
        gate = "GO_FOR_STAGE10D19_MOVE_BRANCH_DECODER_AUDIT"
    elif invalid_target_move_prediction_count >= valid_target_move_prediction_count:
        gate = "GO_FOR_STAGE10D19_MOVEMENT_POLICY_REBALANCE_WITH_VALID_TARGETS"
    else:
        gate = "GO_FOR_STAGE10D19_MOVE_BRANCH_DECODER_AUDIT"

    payload = {
        "move_prediction_to_build_rate": prediction_to_build,
        "move_build_to_accept_rate": build_to_accept,
        "move_prediction_to_accept_rate": prediction_to_accept,
        "valid_target_move_prediction_count": valid_target_move_prediction_count,
        "invalid_target_move_prediction_count": invalid_target_move_prediction_count,
        "occupied_target_count": occupied_target_count,
        "out_of_bounds_target_count": out_of_bounds_target_count,
        "busy_unit_or_current_action_block_count": busy_unit_or_current_action_block_count,
        "off_actor_move_prediction_count": off_actor_move_prediction_count,
        "friendly_actor_move_prediction_count": friendly_actor_move_prediction_count,
        "grouping": {
            "by_unit_type": dict(by_unit_type),
            "by_produced_vs_original": dict(by_produced),
            "by_move_dir": dict(by_move_dir),
            "by_target_kind": dict(by_target_kind),
            "by_top_competing_action": dict(by_top_competing),
            "by_p_move_bucket": dict(by_p_bucket),
            "by_decoder_filter_reject_reason": dict(by_reject_reason),
            "by_actor_validity": dict(by_actor_validity),
        },
        "labels": labels,
        "recommended_gate": gate,
        "events": detailed,
    }

    out = write_json("python/week6_student/reports/stage10d19_move_command_efficiency_audit.json", payload)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
