#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from stage10d17_common import (
    ACTION_SHAPE,
    ACTION_SLICE,
    ACTION_TYPE_HARVEST,
    ACTION_TYPE_MOVE,
    ACTION_TYPE_NOOP,
    ACTION_TYPE_PRODUCE,
    B2_FLAT,
    BRANCH_SIZES,
    C3_FLAT,
    MAP_H,
    MAP_W,
    OWNER_SELF_INDEX,
    OBS_SHAPE,
    UNIT_BASE_INDEX,
    UNIT_RESOURCE_INDEX,
    UNIT_TYPE_SLICE,
    flat_to_xy,
    get_observations_and_actions,
    load_json,
    load_split_payload,
    read_jsonl,
    resolve_path,
    summarize_action_type_distribution,
    utc_now_iso,
    validate_branch_bounds,
    write_json,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.17 validate movement-augmented dataset")
    p.add_argument("--augmented-bc-ready-dir", type=Path, required=True)
    p.add_argument("--base-bc-ready-dir", type=Path, default=None)
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d17_movement_augmented_dataset_validation.json"),
    )
    return p.parse_args()


def _check_move_semantics(
    observations: np.ndarray,
    actions: np.ndarray,
    metadata_rows: List[Dict[str, Any]],
    original_count: int,
) -> Dict[str, Any]:
    checked = 0
    valid_owner_actor = 0
    valid_not_base_resource = 0
    valid_move_dir = 0
    valid_target_in_bounds = 0
    valid_target_empty = 0
    leakage_risk = 0
    examples: List[Dict[str, Any]] = []

    for i, row in enumerate(metadata_rows):
        if int(row.get("target_action_type", -1)) != ACTION_TYPE_MOVE:
            continue
        idx = original_count + i
        if idx >= observations.shape[0]:
            continue
        target_flat = int(row.get("target_cell", -1))
        if target_flat < 0 or target_flat >= 576:
            continue

        checked += 1
        cell = observations[idx, target_flat]
        tgt = actions[idx, target_flat]

        is_actor = bool((cell[OWNER_SELF_INDEX] > 0.5) and (np.sum(cell[UNIT_TYPE_SLICE]) > 0.5))
        if is_actor:
            valid_owner_actor += 1

        not_base_resource = bool((cell[UNIT_BASE_INDEX] <= 0.5) and (cell[UNIT_RESOURCE_INDEX] <= 0.5))
        if not_base_resource:
            valid_not_base_resource += 1

        if int(tgt[1]) in (0, 1, 2, 3):
            valid_move_dir += 1

        x, y = flat_to_xy(target_flat)
        dx, dy = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}.get(int(tgt[1]), (999, 999))
        nx, ny = x + dx, y + dy
        in_bounds = 0 <= nx < MAP_W and 0 <= ny < MAP_H
        if in_bounds:
            valid_target_in_bounds += 1
            nflat = ny * MAP_W + nx
            is_empty = bool(np.sum(observations[idx, nflat, UNIT_TYPE_SLICE]) <= 1e-6)
            if is_empty:
                valid_target_empty += 1

        obs_action_idx = int(np.argmax(cell[ACTION_SLICE])) if float(np.max(cell[ACTION_SLICE])) > 0 else -1
        if obs_action_idx == ACTION_TYPE_MOVE:
            leakage_risk += 1
            if len(examples) < 10:
                examples.append(
                    {
                        "metadata_index": int(i),
                        "sample_index": int(idx),
                        "target_flat": int(target_flat),
                    }
                )

    return {
        "checked_move_samples": int(checked),
        "valid_owner_actor_count": int(valid_owner_actor),
        "valid_not_base_or_resource_count": int(valid_not_base_resource),
        "valid_move_dir_count": int(valid_move_dir),
        "valid_target_in_bounds_count": int(valid_target_in_bounds),
        "valid_target_empty_count": int(valid_target_empty),
        "leakage_risk_count": int(leakage_risk),
        "leakage_examples": examples,
    }


def _preservation_checks(actions: np.ndarray) -> Dict[str, Any]:
    b2_h = int(np.sum(actions[:, B2_FLAT, 0] == ACTION_TYPE_HARVEST))
    c3_p = int(np.sum(actions[:, C3_FLAT, 0] == ACTION_TYPE_PRODUCE))
    return {
        "b2_harvest_targets": int(b2_h),
        "c3_produce_targets": int(c3_p),
        "preserved": bool(b2_h > 0 and c3_p > 0),
    }


def main() -> int:
    args = parse_args()
    aug_dir = resolve_path(args.augmented_bc_ready_dir).resolve()

    aug_manifest = load_json(aug_dir / "stage10d17_movement_augmentation_manifest.json")
    base_dir = (
        resolve_path(args.base_bc_ready_dir).resolve()
        if args.base_bc_ready_dir is not None
        else resolve_path(aug_manifest["base_dataset_path"]).resolve()
    )

    aug_train_payload = load_split_payload(aug_dir / "bc_train.npz")
    aug_val_payload = load_split_payload(aug_dir / "bc_validation.npz")
    base_train_payload = load_split_payload(base_dir / "bc_train.npz")
    base_val_payload = load_split_payload(base_dir / "bc_validation.npz")

    aug_train_obs, aug_train_actions = get_observations_and_actions(aug_train_payload)
    aug_val_obs, aug_val_actions = get_observations_and_actions(aug_val_payload)
    base_train_obs, base_train_actions = get_observations_and_actions(base_train_payload)
    base_val_obs, base_val_actions = get_observations_and_actions(base_val_payload)

    meta_train = read_jsonl(aug_dir / "stage10d17_augmented_sample_metadata_train.jsonl")
    meta_val = read_jsonl(aug_dir / "stage10d17_augmented_sample_metadata_validation.jsonl")

    shape_checks = {
        "train_observations_shape": bool(aug_train_obs.ndim == 3 and tuple(aug_train_obs.shape[1:]) == OBS_SHAPE),
        "train_actions_shape": bool(aug_train_actions.ndim == 3 and tuple(aug_train_actions.shape[1:]) == ACTION_SHAPE),
        "validation_observations_shape": bool(aug_val_obs.ndim == 3 and tuple(aug_val_obs.shape[1:]) == OBS_SHAPE),
        "validation_actions_shape": bool(aug_val_actions.ndim == 3 and tuple(aug_val_actions.shape[1:]) == ACTION_SHAPE),
    }
    dtype_checks = {
        "observations_float32": bool(aug_train_obs.dtype == np.float32 and aug_val_obs.dtype == np.float32),
        "actions_integer": bool(np.issubdtype(aug_train_actions.dtype, np.integer) and np.issubdtype(aug_val_actions.dtype, np.integer)),
    }
    finite_checks = {
        "train_finite": bool(np.isfinite(aug_train_obs).all()),
        "validation_finite": bool(np.isfinite(aug_val_obs).all()),
    }

    branch_train = validate_branch_bounds(aug_train_actions)
    branch_val = validate_branch_bounds(aug_val_actions)
    branch_valid = bool(all(branch_train.values()) and all(branch_val.values()))

    move_sem_train = _check_move_semantics(aug_train_obs, aug_train_actions, meta_train, base_train_obs.shape[0])
    move_sem_val = _check_move_semantics(aug_val_obs, aug_val_actions, meta_val, base_val_obs.shape[0])

    leakage_ok = bool((move_sem_train["leakage_risk_count"] + move_sem_val["leakage_risk_count"]) == 0)

    move_targets_present = bool(
        move_sem_train["checked_move_samples"] + move_sem_val["checked_move_samples"] > 0
    )

    move_targets_valid = bool(
        move_sem_train["checked_move_samples"] > 0
        and move_sem_train["valid_owner_actor_count"] == move_sem_train["checked_move_samples"]
        and move_sem_train["valid_not_base_or_resource_count"] == move_sem_train["checked_move_samples"]
        and move_sem_train["valid_move_dir_count"] == move_sem_train["checked_move_samples"]
        and move_sem_train["valid_target_in_bounds_count"] == move_sem_train["checked_move_samples"]
    ) and bool(
        move_sem_val["checked_move_samples"] >= 0
        and move_sem_val["valid_owner_actor_count"] == move_sem_val["checked_move_samples"]
        and move_sem_val["valid_not_base_or_resource_count"] == move_sem_val["checked_move_samples"]
        and move_sem_val["valid_move_dir_count"] == move_sem_val["checked_move_samples"]
        and move_sem_val["valid_target_in_bounds_count"] == move_sem_val["checked_move_samples"]
    )

    preserve_train = _preservation_checks(aug_train_actions)
    preserve_val = _preservation_checks(aug_val_actions)
    preserve_ok = bool(preserve_train["preserved"] and preserve_val["preserved"])

    dist_base_train = summarize_action_type_distribution(base_train_obs, base_train_actions)
    dist_base_val = summarize_action_type_distribution(base_val_obs, base_val_actions)
    dist_aug_train = summarize_action_type_distribution(aug_train_obs, aug_train_actions)
    dist_aug_val = summarize_action_type_distribution(aug_val_obs, aug_val_actions)

    move_increase = bool(
        dist_aug_train["actor_action_type_counts"]["Move"] > dist_base_train["actor_action_type_counts"]["Move"]
    )
    no_catastrophic_noop_shift = bool(
        abs(dist_aug_train["noop_ratio_all_cells"] - dist_base_train["noop_ratio_all_cells"]) <= 0.10
        and abs(dist_aug_val["noop_ratio_all_cells"] - dist_base_val["noop_ratio_all_cells"]) <= 0.10
    )

    negative_controls_present = bool(int(aug_manifest.get("negative_control_count", 0)) > 0)

    target_distribution_ok = bool(move_increase and no_catastrophic_noop_shift and negative_controls_present)

    overall_valid = bool(
        all(shape_checks.values())
        and all(dtype_checks.values())
        and all(finite_checks.values())
        and branch_valid
        and move_targets_present
        and move_targets_valid
        and leakage_ok
        and preserve_ok
        and target_distribution_ok
    )

    labels = [
        "MOVEMENT_AUGMENTED_DATASET_VALID" if overall_valid else "MOVEMENT_AUGMENTED_DATASET_INVALID",
        "MOVE_TARGETS_PRESENT" if move_targets_present else "MOVEMENT_AUGMENTED_DATASET_INVALID",
        "MOVE_TARGETS_VALID" if move_targets_valid else "MOVEMENT_AUGMENTED_DATASET_INVALID",
        "MOVE_BRANCH_BOUNDS_VALID" if branch_valid else "MOVEMENT_AUGMENTED_DATASET_INVALID",
        "MOVE_TARGET_CELLS_VALID" if move_targets_valid else "MOVEMENT_AUGMENTED_DATASET_INVALID",
        "NO_MOVEMENT_LABEL_LEAKAGE_CONFIRMED" if leakage_ok else "MOVEMENT_LABEL_LEAKAGE_RISK",
        "HARVEST_PRODUCE_TARGETS_PRESERVED" if preserve_ok else "MOVEMENT_AUGMENTED_DATASET_INVALID",
        "NEGATIVE_CONTROLS_PRESENT" if negative_controls_present else "TARGET_DISTRIBUTION_RISK",
        "TARGET_DISTRIBUTION_ACCEPTABLE" if target_distribution_ok else "TARGET_DISTRIBUTION_RISK",
    ]
    gate = "GO_FOR_STAGE10D17_MOVEMENT_BC_TRAINING" if overall_valid else "GO_FOR_STAGE10D17_MOVEMENT_AUGMENTATION_FIX"

    report: Dict[str, Any] = {
        "stage": "10D.17",
        "task": "validate_movement_augmented_dataset",
        "generated_at_utc": utc_now_iso(),
        "augmented_bc_ready_dir": str(aug_dir.as_posix()),
        "base_bc_ready_dir": str(base_dir.as_posix()),
        "status": "pass" if overall_valid else "fail",
        "shape_checks": shape_checks,
        "dtype_checks": dtype_checks,
        "finite_checks": finite_checks,
        "branch_bounds": {
            "train": branch_train,
            "validation": branch_val,
        },
        "movement_semantics": {
            "train": move_sem_train,
            "validation": move_sem_val,
        },
        "label_leakage": {
            "no_leakage_confirmed": leakage_ok,
        },
        "distribution": {
            "base_train": dist_base_train,
            "base_validation": dist_base_val,
            "augmented_train": dist_aug_train,
            "augmented_validation": dist_aug_val,
            "move_increase": move_increase,
            "no_catastrophic_noop_shift": no_catastrophic_noop_shift,
            "negative_controls_present": negative_controls_present,
        },
        "regression_preservation": {
            "train": preserve_train,
            "validation": preserve_val,
        },
        "classification_labels": labels,
        "primary_next_gate": gate,
    }
    write_json(args.output_json, report)
    print(resolve_path(args.output_json).as_posix())
    return 0 if overall_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
