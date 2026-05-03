#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

import numpy as np

from stage10d17_common import (
    ACTION_SHAPE,
    ACTION_TYPE_ATTACK,
    ACTION_TYPE_HARVEST,
    ACTION_TYPE_MOVE,
    ACTION_TYPE_NAMES,
    ACTION_TYPE_PRODUCE,
    MAP_W,
    OWNER_SELF_INDEX,
    UNIT_BASE_INDEX,
    UNIT_BARRACKS_INDEX,
    UNIT_HEAVY_INDEX,
    UNIT_LIGHT_INDEX,
    UNIT_RANGED_INDEX,
    UNIT_TYPE_SLICE,
    UNIT_WORKER_INDEX,
    flat_to_xy,
    get_observations_and_actions,
    iter_jsonl,
    load_json,
    load_split_payload,
    resolve_path,
    utc_now_iso,
    write_json,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.17 movement label distribution audit")
    p.add_argument(
        "--stage10d7-bc-ready-dir",
        type=Path,
        default=Path("python/week6_student/bc_ready/legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z"),
    )
    p.add_argument(
        "--stage10d14-bc-ready-dir",
        type=Path,
        default=Path("python/week6_student/bc_ready/legacy032_3m_unity_v2_stage10d14_unity_like_augmented_bc_ready_20260503T145301Z"),
    )
    p.add_argument(
        "--stage10d16-trace-jsonl",
        type=Path,
        default=Path("python/week6_student/reports/stage10d16_extended_runtime_trace.jsonl"),
    )
    p.add_argument(
        "--stage10d16-lifecycle-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d16_produced_unit_lifecycle.json"),
    )
    p.add_argument(
        "--high-move-prob-threshold",
        type=float,
        default=0.2,
    )
    p.add_argument(
        "--high-attack-prob-threshold",
        type=float,
        default=0.2,
    )
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d17_movement_label_distribution_audit.json"),
    )
    return p.parse_args()


def _unit_combo_counts(observations: np.ndarray, actions: np.ndarray) -> Dict[str, int]:
    obs = np.asarray(observations, dtype=np.float32)
    act = np.asarray(actions, dtype=np.int64)
    action_type = act[:, :, 0]

    owner_self = obs[:, :, OWNER_SELF_INDEX] > 0.5

    def count(unit_idx: int, action_idx: int) -> int:
        return int(np.sum((obs[:, :, unit_idx] > 0.5) & owner_self & (action_type == action_idx)))

    return {
        "worker_move": count(UNIT_WORKER_INDEX, ACTION_TYPE_MOVE),
        "worker_harvest": count(UNIT_WORKER_INDEX, ACTION_TYPE_HARVEST),
        "worker_return": int(np.sum((obs[:, :, UNIT_WORKER_INDEX] > 0.5) & owner_self & (action_type == 3))),
        "base_produce": count(UNIT_BASE_INDEX, ACTION_TYPE_PRODUCE),
        "barracks_produce": count(UNIT_BARRACKS_INDEX, ACTION_TYPE_PRODUCE),
        "light_move": count(UNIT_LIGHT_INDEX, ACTION_TYPE_MOVE),
        "heavy_move": count(UNIT_HEAVY_INDEX, ACTION_TYPE_MOVE),
        "ranged_move": count(UNIT_RANGED_INDEX, ACTION_TYPE_MOVE),
        "light_attack": count(UNIT_LIGHT_INDEX, ACTION_TYPE_ATTACK),
        "heavy_attack": count(UNIT_HEAVY_INDEX, ACTION_TYPE_ATTACK),
        "ranged_attack": count(UNIT_RANGED_INDEX, ACTION_TYPE_ATTACK),
    }


def _distribution_for_split(observations: np.ndarray, actions: np.ndarray) -> Dict[str, Any]:
    obs = np.asarray(observations, dtype=np.float32)
    act = np.asarray(actions, dtype=np.int64)

    action_type = act[:, :, 0]
    total_samples = int(obs.shape[0])
    total_cells = int(obs.shape[0] * obs.shape[1])
    actor_mask = np.asarray((obs[:, :, OWNER_SELF_INDEX] > 0.5) & (np.sum(obs[:, :, UNIT_TYPE_SLICE], axis=2) > 0.5), dtype=bool)

    move_mask = action_type == ACTION_TYPE_MOVE
    attack_mask = action_type == ACTION_TYPE_ATTACK

    move_dir_counts = Counter()
    if np.any(move_mask):
        dirs = act[:, :, 1][move_mask].reshape(-1)
        for d in dirs.tolist():
            move_dir_counts[int(d)] += 1

    attack_target_counts = Counter()
    if np.any(attack_mask):
        targets = act[:, :, 6][attack_mask].reshape(-1)
        for t in targets.tolist():
            attack_target_counts[int(t)] += 1

    combo = _unit_combo_counts(obs, act)

    move_by_unit_type = {
        "worker": combo["worker_move"],
        "light": combo["light_move"],
        "heavy": combo["heavy_move"],
        "ranged": combo["ranged_move"],
    }
    attack_by_unit_type = {
        "light": combo["light_attack"],
        "heavy": combo["heavy_attack"],
        "ranged": combo["ranged_attack"],
    }

    return {
        "total_samples": total_samples,
        "total_cells": total_cells,
        "actor_cells": int(np.sum(actor_mask)),
        "action_type_counts": {ACTION_TYPE_NAMES[i]: int(np.sum(action_type == i)) for i in range(6)},
        "actor_cell_action_type_counts": {
            ACTION_TYPE_NAMES[i]: int(np.sum((action_type == i) & actor_mask)) for i in range(6)
        },
        "unit_type_action_counts": combo,
        "move_labels_by_unit_type": move_by_unit_type,
        "move_branch_direction_distribution": {
            "north": int(move_dir_counts.get(0, 0)),
            "east": int(move_dir_counts.get(1, 0)),
            "south": int(move_dir_counts.get(2, 0)),
            "west": int(move_dir_counts.get(3, 0)),
        },
        "attack_labels_by_unit_type": attack_by_unit_type,
        "attack_target_distribution": {str(k): int(v) for k, v in sorted(attack_target_counts.items())},
        "move_labels_exist": bool(np.any(move_mask)),
        "combat_or_produced_unit_move_examples_exist": bool(
            (combo["light_move"] + combo["heavy_move"] + combo["ranged_move"]) > 0
        ),
    }


def _dataset_distribution(bc_ready_dir: Path) -> Dict[str, Any]:
    train_payload = load_split_payload(bc_ready_dir / "bc_train.npz")
    val_payload = load_split_payload(bc_ready_dir / "bc_validation.npz")
    train_obs, train_actions = get_observations_and_actions(train_payload)
    val_obs, val_actions = get_observations_and_actions(val_payload)

    train_stats = _distribution_for_split(train_obs, train_actions)
    val_stats = _distribution_for_split(val_obs, val_actions)

    actor_cells_total = train_stats["actor_cells"] + val_stats["actor_cells"]
    move_actor_total = (
        train_stats["actor_cell_action_type_counts"]["Move"]
        + val_stats["actor_cell_action_type_counts"]["Move"]
    )
    attack_actor_total = (
        train_stats["actor_cell_action_type_counts"]["Attack"]
        + val_stats["actor_cell_action_type_counts"]["Attack"]
    )

    return {
        "path": str(bc_ready_dir.as_posix()),
        "train": train_stats,
        "validation": val_stats,
        "aggregate": {
            "actor_cells_total": int(actor_cells_total),
            "move_actor_cells_total": int(move_actor_total),
            "move_actor_share": float(move_actor_total / max(1, actor_cells_total)),
            "attack_actor_cells_total": int(attack_actor_total),
            "attack_actor_share": float(attack_actor_total / max(1, actor_cells_total)),
        },
    }


def _analyze_stage10d16(
    trace_jsonl: Path,
    lifecycle_json: Path,
    high_move_threshold: float,
    high_attack_threshold: float,
) -> Dict[str, Any]:
    lifecycle = load_json(lifecycle_json)
    units = lifecycle.get("units", []) if isinstance(lifecycle.get("units"), list) else []

    produced_unit_ids = [str(u.get("unit_id")) for u in units if str(u.get("unit_id", ""))]
    produced_unit_set = set(produced_unit_ids)

    unit_type_counts = Counter(str(u.get("unit_type", "Unknown")) for u in units)
    produced_positions = {
        str(u.get("unit_id")): [list(pos) for pos in (u.get("positions_over_time") or [])[:64]]
        for u in units
    }

    ever_non_noop = {
        str(u.get("unit_id")): bool(u.get("first_non_noop_prediction_step") is not None)
        for u in units
    }

    max_p_move: Dict[str, float] = defaultdict(float)
    max_p_attack: Dict[str, float] = defaultdict(float)
    first_high_move_not_top1_step: Dict[str, int] = {}
    first_high_attack_not_top1_step: Dict[str, int] = {}

    for row in iter_jsonl(trace_jsonl):
        step = int(row.get("step", -1))
        for u in row.get("friendly_units", []) or []:
            uid = str(u.get("unit_id", ""))
            if uid not in produced_unit_set:
                continue
            probs = u.get("action_type_probs") or {}
            p_move = float(probs.get("move", 0.0))
            p_attack = float(probs.get("attack", 0.0))
            max_p_move[uid] = max(max_p_move[uid], p_move)
            max_p_attack[uid] = max(max_p_attack[uid], p_attack)

            pred = str(u.get("predicted_action_type", ""))
            if pred != "Move" and p_move >= high_move_threshold and uid not in first_high_move_not_top1_step:
                first_high_move_not_top1_step[uid] = step
            if pred != "Attack" and p_attack >= high_attack_threshold and uid not in first_high_attack_not_top1_step:
                first_high_attack_not_top1_step[uid] = step

    return {
        "run_steps": int(lifecycle.get("run_steps", 0)),
        "produced_unit_count": int(len(units)),
        "produced_unit_ids": produced_unit_ids,
        "produced_unit_types": dict(sorted(unit_type_counts.items())),
        "produced_unit_positions_over_time_preview": produced_positions,
        "produced_units_ever_non_noop_prediction": ever_non_noop,
        "produced_units_with_high_move_prob_not_top1": sorted(first_high_move_not_top1_step.keys()),
        "produced_units_with_high_attack_prob_not_top1": sorted(first_high_attack_not_top1_step.keys()),
        "per_produced_unit_max_p_move": {k: float(v) for k, v in sorted(max_p_move.items())},
        "per_produced_unit_max_p_attack": {k: float(v) for k, v in sorted(max_p_attack.items())},
        "high_move_threshold": float(high_move_threshold),
        "high_attack_threshold": float(high_attack_threshold),
    }


def _classify_and_gate(stage10d14: Mapping[str, Any], stage10d16: Mapping[str, Any]) -> tuple[list[str], str]:
    move_share = float(stage10d14["aggregate"]["move_actor_share"])
    attack_share = float(stage10d14["aggregate"]["attack_actor_share"])
    combat_move_total = (
        int(stage10d14["train"]["unit_type_action_counts"]["light_move"])
        + int(stage10d14["train"]["unit_type_action_counts"]["heavy_move"])
        + int(stage10d14["train"]["unit_type_action_counts"]["ranged_move"])
        + int(stage10d14["validation"]["unit_type_action_counts"]["light_move"])
        + int(stage10d14["validation"]["unit_type_action_counts"]["heavy_move"])
        + int(stage10d14["validation"]["unit_type_action_counts"]["ranged_move"])
    )

    produced_move_max = max([float(v) for v in stage10d16["per_produced_unit_max_p_move"].values()] + [0.0])

    move_absent = move_share <= 1e-6
    move_under = (move_share > 1e-6) and (move_share < 0.01)
    attack_under = attack_share < 0.005

    labels: list[str] = []
    labels.append("MOVE_LABELS_ABSENT" if move_absent else ("MOVE_LABELS_UNDERREPRESENTED" if move_under else "MOVE_LABELS_PRESENT"))
    labels.append("COMBAT_MOVE_LABELS_ABSENT" if combat_move_total == 0 else "COMBAT_MOVE_LABELS_PRESENT")
    labels.append("ATTACK_LABELS_UNDERREPRESENTED" if attack_under else "ATTACK_LABELS_PRESENT")

    produced_gap = (produced_move_max < 0.2) and (len(stage10d16["produced_units_with_high_move_prob_not_top1"]) == 0)
    if produced_gap:
        labels.append("PRODUCED_UNIT_MOVE_GAP_CONFIRMED")

    if move_absent or move_under or produced_gap:
        labels.append("STAGE10D17_MOVEMENT_AUGMENTATION_REQUIRED")

    if move_absent or move_under:
        gate = "GO_FOR_STAGE10D17_BUILD_MOVEMENT_AUGMENTATION"
    elif produced_move_max < 0.2:
        gate = "GO_FOR_STAGE10D17_TRAINING_REWEIGHTING_OR_HARD_NEGATIVE_AUDIT"
    else:
        gate = "GO_FOR_STAGE10D17_RUNTIME_OBSERVATION_DISTRIBUTION_AUDIT"
    return labels, gate


def main() -> int:
    args = parse_args()
    stage10d7_dir = resolve_path(args.stage10d7_bc_ready_dir).resolve()
    stage10d14_dir = resolve_path(args.stage10d14_bc_ready_dir).resolve()

    d7 = _dataset_distribution(stage10d7_dir)
    d14 = _dataset_distribution(stage10d14_dir)
    d16 = _analyze_stage10d16(
        resolve_path(args.stage10d16_trace_jsonl).resolve(),
        resolve_path(args.stage10d16_lifecycle_json).resolve(),
        high_move_threshold=float(args.high_move_prob_threshold),
        high_attack_threshold=float(args.high_attack_prob_threshold),
    )

    labels, gate = _classify_and_gate(d14, d16)

    report: Dict[str, Any] = {
        "stage": "10D.17",
        "task": "movement_label_distribution_audit",
        "generated_at_utc": utc_now_iso(),
        "datasets": {
            "stage10d7_semantic_bc_ready": d7,
            "stage10d14_augmented_bc_ready": d14,
        },
        "stage10d16_lifecycle_and_trace_audit": d16,
        "classification_labels": labels,
        "primary_next_gate": gate,
    }
    write_json(args.output_json, report)
    print(resolve_path(args.output_json).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
