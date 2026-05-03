#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter

from stage10d19_common import (
    classify_cell_type,
    get_sparse_rerun_cell_tables,
    load_jsonl,
    load_stage10d18rr_inputs,
    manhattan,
    safe_int,
    write_json,
)


def _collect_friendly_and_base(rows: list[dict]) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    friendly = []
    base = []
    for r in rows:
        if bool(r.get("runtime_is_friendly_actor")):
            p = (safe_int(r.get("x")), safe_int(r.get("y")))
            friendly.append(p)
            if bool(r.get("runtime_is_friendly_base")):
                base.append(p)
    return friendly, base


def main() -> int:
    data = load_stage10d18rr_inputs()
    off_actor = data["off_actor"]
    total_off_actor_non_noop_count = safe_int(off_actor.get("total_off_actor_non_noop_count"))
    max_off_actor_non_noop_count = safe_int(off_actor.get("max_off_actor_non_noop_count"))

    action_type_dist = Counter()
    cell_type_dist = Counter()
    off_actor_command_built_count = 0
    off_actor_submission_count = 0
    near_friendly = 0
    near_base = 0
    near_produced_like = 0
    sampled_count = 0

    for table in get_sparse_rerun_cell_tables():
        rows = load_jsonl(table)
        friendly_cells, base_cells = _collect_friendly_and_base(rows)
        for r in rows:
            if bool(r.get("runtime_is_friendly_actor")):
                continue
            pred = str(r.get("predicted_action_type") or "NoOp")
            if pred == "NoOp":
                continue

            sampled_count += 1
            action_type_dist[pred] += 1
            ctype = classify_cell_type(r)
            cell_type_dist[ctype] += 1

            if bool(r.get("command_built")):
                off_actor_command_built_count += 1
            if bool(r.get("applier_submission_reached")) or bool(r.get("applier_submitted")):
                off_actor_submission_count += 1

            p = (safe_int(r.get("x")), safe_int(r.get("y")))
            if friendly_cells and min(manhattan(p, f) for f in friendly_cells) <= 2:
                near_friendly += 1
            if base_cells and min(manhattan(p, b) for b in base_cells) <= 3:
                near_base += 1
            if friendly_cells and min(manhattan(p, f) for f in friendly_cells) <= 1:
                near_produced_like += 1

    share_near_friendly = float(near_friendly) / float(sampled_count) if sampled_count else 0.0
    share_near_base = float(near_base) / float(sampled_count) if sampled_count else 0.0
    share_near_produced = float(near_produced_like) / float(sampled_count) if sampled_count else 0.0

    labels = [
        "STAGE10D19_OFF_ACTOR_SAFETY_AUDIT_COMPLETED",
        "STAGE10D19_OFF_ACTOR_NONNOOP_PRESENT",
        "STAGE10D19_OFF_ACTOR_NEGATIVE_CONTROLS_REQUIRED",
    ]
    if off_actor_command_built_count == 0 and off_actor_submission_count == 0:
        labels.append("STAGE10D19_OFF_ACTOR_FILTERED_BEFORE_COMMAND_BUILD")
    else:
        labels.append("STAGE10D19_OFF_ACTOR_COMMAND_BUILD_RISK")
    if share_near_friendly >= 0.5 or share_near_base >= 0.5:
        labels.append("STAGE10D19_OFF_ACTOR_CONV_SPILLOVER_SUSPECTED")

    if off_actor_command_built_count > 0 or off_actor_submission_count > 0:
        gate = "GO_FOR_STAGE10D19_RUNTIME_SAFETY_FIX"
    else:
        gate = "GO_FOR_STAGE10D19_OFF_ACTOR_NEGATIVE_CONTROL_AUGMENTATION"

    payload = {
        "total_off_actor_non_noop_count": total_off_actor_non_noop_count,
        "max_off_actor_non_noop_count": max_off_actor_non_noop_count,
        "off_actor_action_type_distribution": dict(action_type_dist),
        "off_actor_cell_type_distribution": dict(cell_type_dist),
        "off_actor_command_built_count": off_actor_command_built_count,
        "off_actor_submission_count": off_actor_submission_count,
        "off_actor_near_friendly_actor_share": share_near_friendly,
        "off_actor_near_base_share": share_near_base,
        "off_actor_near_produced_unit_share": share_near_produced,
        "sampled_cell_table_non_noop_count": sampled_count,
        "sampled_cell_tables": [p.name for p in get_sparse_rerun_cell_tables()],
        "labels": labels,
        "recommended_gate": gate,
    }

    out = write_json("python/week6_student/reports/stage10d19_off_actor_safety_deep_audit.json", payload)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
