#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter

import numpy as np

from stage10d17_common import (
    ACTION_TYPE_ATTACK,
    OWNER_SELF_INDEX,
    UNIT_BASE_INDEX,
    UNIT_BARRACKS_INDEX,
    UNIT_HEAVY_INDEX,
    UNIT_LIGHT_INDEX,
    UNIT_RANGED_INDEX,
    UNIT_TYPE_SLICE,
    UNIT_WORKER_INDEX,
    get_observations_and_actions,
    load_split_payload,
)
from stage10d19_common import load_json, resolve, write_json


DATASETS = {
    "stage10d7": "python/week6_student/bc_ready/legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z",
    "stage10d14": "python/week6_student/bc_ready/legacy032_3m_unity_v2_stage10d14_unity_like_augmented_bc_ready_20260503T145301Z",
    "stage10d17": "python/week6_student/bc_ready/legacy032_v2_stage10d17_movement_augmented_bc_ready_20260503T162905Z",
}

UNIT_CHANNELS = {
    "Worker": UNIT_WORKER_INDEX,
    "Light": UNIT_LIGHT_INDEX,
    "Heavy": UNIT_HEAVY_INDEX,
    "Ranged": UNIT_RANGED_INDEX,
    "Base": UNIT_BASE_INDEX,
    "Barracks": UNIT_BARRACKS_INDEX,
}

COMBAT = {"Worker", "Light", "Heavy", "Ranged"}


def _analyze_split(obs: np.ndarray, actions: np.ndarray) -> dict:
    obs = np.asarray(obs, dtype=np.float32)
    actions = np.asarray(actions, dtype=np.int64)

    owner_self = obs[:, :, OWNER_SELF_INDEX] > 0.5
    has_unit = np.sum(obs[:, :, UNIT_TYPE_SLICE], axis=2) > 0.5
    actor = owner_self & has_unit

    action_type = actions[:, :, 0]
    attack_mask = action_type == ACTION_TYPE_ATTACK

    total_actor = int(np.sum(actor))
    attack_total = int(np.sum(attack_mask & actor))

    attack_by_unit = {}
    combat_actor = 0
    combat_attack = 0
    for name, idx in UNIT_CHANNELS.items():
        um = (obs[:, :, idx] > 0.5) & actor
        cnt = int(np.sum(attack_mask & um))
        attack_by_unit[name] = cnt
        if name in COMBAT:
            combat_actor += int(np.sum(um))
            combat_attack += cnt

    target_dist = Counter()
    if int(np.sum(attack_mask)):
        vals = actions[:, :, 6][attack_mask]
        for v in vals.reshape(-1).tolist():
            target_dist[int(v)] += 1

    # enemy-near proxy in 7x7 local (presence channel based)
    enemy_presence = (obs[:, :, 4] > 0.5).reshape(obs.shape[0], 24, 24)
    actor_map = actor.reshape(obs.shape[0], 24, 24)
    enemy_near_actor = 0
    h, w = 24, 24
    for n in range(obs.shape[0]):
        ys, xs = np.where(actor_map[n])
        for y, x in zip(ys.tolist(), xs.tolist()):
            y0 = max(0, y - 3)
            y1 = min(h, y + 4)
            x0 = max(0, x - 3)
            x1 = min(w, x + 4)
            if np.any(enemy_presence[n, y0:y1, x0:x1]):
                enemy_near_actor += 1

    return {
        "total_actor_cells": total_actor,
        "attack_labels_total": attack_total,
        "attack_labels_by_unit_type": attack_by_unit,
        "attack_target_branch_distribution": {str(k): int(v) for k, v in sorted(target_dist.items())},
        "attack_label_share_among_actor_cells": float(attack_total / max(1, total_actor)),
        "attack_label_share_among_combat_units": float(combat_attack / max(1, combat_actor)),
        "examples_with_enemy_nearby_proxy": int(enemy_near_actor),
        "valid_attack_target_range_share": float(
            sum(v for k, v in target_dist.items() if 0 <= int(k) < 49) / max(1, sum(target_dist.values()))
        ),
    }


def _analyze_dataset(path: str) -> dict:
    p = resolve(path)
    train = load_split_payload(p / "bc_train.npz")
    val = load_split_payload(p / "bc_validation.npz")
    t_obs, t_actions = get_observations_and_actions(train)
    v_obs, v_actions = get_observations_and_actions(val)

    train_stats = _analyze_split(t_obs, t_actions)
    val_stats = _analyze_split(v_obs, v_actions)
    all_actor = train_stats["total_actor_cells"] + val_stats["total_actor_cells"]
    all_attack = train_stats["attack_labels_total"] + val_stats["attack_labels_total"]

    return {
        "path": str(p.as_posix()),
        "train": train_stats,
        "validation": val_stats,
        "aggregate": {
            "total_actor_cells": all_actor,
            "attack_labels_total": all_attack,
            "attack_share": float(all_attack / max(1, all_actor)),
        },
    }


def main() -> int:
    datasets = {name: _analyze_dataset(path) for name, path in DATASETS.items()}

    s7 = datasets["stage10d7"]["aggregate"]["attack_share"]
    s14 = datasets["stage10d14"]["aggregate"]["attack_share"]
    s17 = datasets["stage10d17"]["aggregate"]["attack_share"]

    labels = ["STAGE10D19_ATTACK_LABEL_AUDIT_COMPLETED"]
    if s17 <= 0.0:
        labels.append("ATTACK_LABELS_ABSENT")
    elif s17 < 0.01:
        labels.append("ATTACK_LABELS_UNDERREPRESENTED")
    else:
        labels.append("COMBAT_ATTACK_LABELS_PRESENT")

    s17_combat_attack = sum(
        datasets["stage10d17"]["aggregate"].get("attack_labels_total", 0)
        for _ in [0]
    )
    if s17_combat_attack == 0:
        labels.append("COMBAT_ATTACK_LABELS_ABSENT")

    s17_targets = datasets["stage10d17"]["train"]["attack_target_branch_distribution"]
    if s17_targets and all(0 <= int(k) < 49 for k in s17_targets.keys()):
        labels.append("ATTACK_TARGET_DISTRIBUTION_VALID")

    if s17 <= s14:
        labels.append("ATTACK_AUGMENTATION_REQUIRED")

    payload = {
        "datasets": datasets,
        "attack_label_trend": {
            "stage10d7_attack_share": s7,
            "stage10d14_attack_share": s14,
            "stage10d17_attack_share": s17,
            "likely_washed_out_after_movement_augmentation": bool(s17 < s14),
        },
        "labels": labels,
    }

    out = write_json("python/week6_student/reports/stage10d19_attack_label_distribution_audit.json", payload)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
