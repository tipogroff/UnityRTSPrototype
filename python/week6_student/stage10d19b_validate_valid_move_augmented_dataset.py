#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from stage10d19b_common import (
    ACTION_SHAPE,
    ACTION_SLICE,
    ACTION_TYPE_ATTACK,
    ACTION_TYPE_HARVEST,
    ACTION_TYPE_MOVE,
    ACTION_TYPE_NAMES,
    ACTION_TYPE_NOOP,
    ACTION_TYPE_PRODUCE,
    B2_FLAT,
    BRANCH_SIZES,
    C3_FLAT,
    MAP_H,
    MAP_W,
    MOVABLE_UNIT_NAMES,
    OWNER_SELF_INDEX,
    OBS_SHAPE,
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
    p = argparse.ArgumentParser(description="Stage10D.19B validate valid-move augmented dataset")
    p.add_argument("--augmented-bc-ready-dir", type=Path, required=True)
    p.add_argument("--base-bc-ready-dir", type=Path, default=None)
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d19b_valid_move_augmented_dataset_validation.json"),
    )
    return p.parse_args()


def _cell_has_unit(obs: np.ndarray, flat: int) -> bool:
    return bool(float(np.sum(obs[flat, UNIT_TYPE_SLICE])) > 0.5)


def _move_checks(
    observations: np.ndarray,
    actions: np.ndarray,
    metadata_rows: List[Dict[str, Any]],
    *,
    original_count: int,
) -> Dict[str, Any]:
    checked = 0
    unit_ok = 0
    dir_ok = 0
    in_bounds_ok = 0
    free_ok = 0
    adjacent_ok = 0
    leakage_risk = 0

    for i, row in enumerate(metadata_rows):
        if str(row.get("augmentation_family")) != "family_a_valid_move_positive":
            continue
        idx = original_count + i
        if idx >= observations.shape[0]:
            continue

        src = int(row.get("source_cell", -1))
        tgt = int(row.get("target_cell", -1))
        move_dir = int(row.get("chosen_move_dir", -1))
        unit_type = str(row.get("unit_type", ""))
        if src < 0 or tgt < 0:
            continue

        checked += 1
        obs = observations[idx]
        act = actions[idx]

        if unit_type in MOVABLE_UNIT_NAMES and bool(obs[src, OWNER_SELF_INDEX] > 0.5) and _cell_has_unit(obs, src):
            unit_ok += 1
        if move_dir in (0, 1, 2, 3) and int(act[src, 1]) in (0, 1, 2, 3):
            dir_ok += 1

        tx, ty = flat_to_xy(tgt)
        if 0 <= tx < MAP_W and 0 <= ty < MAP_H:
            in_bounds_ok += 1

        if not _cell_has_unit(obs, tgt) and float(obs[tgt, UNIT_RESOURCE_INDEX]) <= 0.5:
            free_ok += 1

        sx, sy = flat_to_xy(src)
        if abs(tx - sx) + abs(ty - sy) == 1:
            adjacent_ok += 1

        source_obs_action = int(np.argmax(obs[src, ACTION_SLICE])) if float(np.max(obs[src, ACTION_SLICE])) > 0 else -1
        if source_obs_action == ACTION_TYPE_MOVE:
            leakage_risk += 1

    return {
        "checked": int(checked),
        "unit_ok": int(unit_ok),
        "dir_ok": int(dir_ok),
        "in_bounds_ok": int(in_bounds_ok),
        "free_ok": int(free_ok),
        "adjacent_ok": int(adjacent_ok),
        "leakage_risk": int(leakage_risk),
    }


def _negative_checks(
    observations: np.ndarray,
    actions: np.ndarray,
    metadata_rows: List[Dict[str, Any]],
    *,
    original_count: int,
) -> Dict[str, Any]:
    occupied_exists = 0
    occupied_good = 0
    off_actor_exists = 0
    off_actor_good = 0

    for i, row in enumerate(metadata_rows):
        idx = original_count + i
        if idx >= observations.shape[0]:
            continue
        src = int(row.get("source_cell", -1))
        if src < 0:
            continue
        act_type = int(actions[idx, src, 0])

        fam = str(row.get("augmentation_family", ""))
        if fam == "family_b_occupied_negative":
            occupied_exists += 1
            if act_type != ACTION_TYPE_MOVE:
                occupied_good += 1
        if fam == "family_c_direction_correction":
            occupied_exists += 1
            tgt = int(row.get("target_cell", -1))
            if act_type == ACTION_TYPE_MOVE and tgt >= 0 and not _cell_has_unit(observations[idx], tgt):
                occupied_good += 1
        if fam == "family_e_off_actor_negative":
            off_actor_exists += 1
            if act_type == ACTION_TYPE_NOOP:
                off_actor_good += 1

    return {
        "occupied_controls_exist": int(occupied_exists),
        "occupied_controls_valid": int(occupied_good),
        "off_actor_controls_exist": int(off_actor_exists),
        "off_actor_controls_valid": int(off_actor_good),
    }


def _preservation_checks(base_actions: np.ndarray, aug_actions: np.ndarray, metadata_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    b2_h_base = int(np.sum(base_actions[:, B2_FLAT, 0] == ACTION_TYPE_HARVEST))
    c3_p_base = int(np.sum(base_actions[:, C3_FLAT, 0] == ACTION_TYPE_PRODUCE))
    b2_h_aug = int(np.sum(aug_actions[:, B2_FLAT, 0] == ACTION_TYPE_HARVEST))
    c3_p_aug = int(np.sum(aug_actions[:, C3_FLAT, 0] == ACTION_TYPE_PRODUCE))

    base_move = int(np.sum(base_actions[:, :, 0] == ACTION_TYPE_MOVE))
    aug_move = int(np.sum(aug_actions[:, :, 0] == ACTION_TYPE_MOVE))

    attack_base = int(np.sum(base_actions[:, :, 0] == ACTION_TYPE_ATTACK))
    attack_aug = int(np.sum(aug_actions[:, :, 0] == ACTION_TYPE_ATTACK))

    preserve_rows = int(sum(1 for r in metadata_rows if bool(r.get("preservation_sample", False))))

    return {
        "b2_harvest_base": b2_h_base,
        "b2_harvest_augmented": b2_h_aug,
        "c3_produce_base": c3_p_base,
        "c3_produce_augmented": c3_p_aug,
        "move_labels_base": base_move,
        "move_labels_augmented": aug_move,
        "attack_labels_base": attack_base,
        "attack_labels_augmented": attack_aug,
        "preservation_metadata_rows": preserve_rows,
        "guards_preserved": bool(b2_h_aug >= b2_h_base and c3_p_aug >= c3_p_base and preserve_rows > 0),
        "movement_preserved": bool(aug_move >= base_move),
        "attack_not_removed": bool(attack_aug >= attack_base),
    }


def main() -> int:
    args = parse_args()
    aug_dir = resolve_path(args.augmented_bc_ready_dir).resolve()

    aug_manifest = load_json(aug_dir / "stage10d19b_valid_move_augmentation_manifest.json")
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

    meta_train = read_jsonl(aug_dir / "stage10d19b_augmented_sample_metadata_train.jsonl")
    meta_val = read_jsonl(aug_dir / "stage10d19b_augmented_sample_metadata_validation.jsonl")

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

    move_train = _move_checks(aug_train_obs, aug_train_actions, meta_train, original_count=base_train_obs.shape[0])
    move_val = _move_checks(aug_val_obs, aug_val_actions, meta_val, original_count=base_val_obs.shape[0])

    neg_train = _negative_checks(aug_train_obs, aug_train_actions, meta_train, original_count=base_train_obs.shape[0])
    neg_val = _negative_checks(aug_val_obs, aug_val_actions, meta_val, original_count=base_val_obs.shape[0])

    preserve_train = _preservation_checks(base_train_actions, aug_train_actions, meta_train)
    preserve_val = _preservation_checks(base_val_actions, aug_val_actions, meta_val)

    dist_base_train = summarize_action_type_distribution(base_train_obs, base_train_actions)
    dist_base_val = summarize_action_type_distribution(base_val_obs, base_val_actions)
    dist_aug_train = summarize_action_type_distribution(aug_train_obs, aug_train_actions)
    dist_aug_val = summarize_action_type_distribution(aug_val_obs, aug_val_actions)

    move_rebalanced = bool(
        dist_aug_train["actor_action_type_counts"]["Move"] >= dist_base_train["actor_action_type_counts"]["Move"]
    )
    noop_shift_ok = bool(
        abs(dist_aug_train["noop_ratio_all_cells"] - dist_base_train["noop_ratio_all_cells"]) <= 0.15
        and abs(dist_aug_val["noop_ratio_all_cells"] - dist_base_val["noop_ratio_all_cells"]) <= 0.15
    )

    valid_positive_present = bool(move_train["checked"] + move_val["checked"] > 0)
    valid_targets_confirmed = bool(
        move_train["checked"] > 0
        and move_train["unit_ok"] == move_train["checked"]
        and move_train["dir_ok"] == move_train["checked"]
        and move_train["in_bounds_ok"] == move_train["checked"]
        and move_train["adjacent_ok"] == move_train["checked"]
        and move_val["unit_ok"] == move_val["checked"]
        and move_val["dir_ok"] == move_val["checked"]
        and move_val["in_bounds_ok"] == move_val["checked"]
        and move_val["adjacent_ok"] == move_val["checked"]
    )
    no_leakage = bool((move_train["leakage_risk"] + move_val["leakage_risk"]) == 0)

    occupied_controls_present = bool((neg_train["occupied_controls_exist"] + neg_val["occupied_controls_exist"]) > 0)
    off_actor_controls_present = bool((neg_train["off_actor_controls_exist"] + neg_val["off_actor_controls_exist"]) > 0)

    occupied_controls_ok = bool(
        neg_train["occupied_controls_valid"] == neg_train["occupied_controls_exist"]
        and neg_val["occupied_controls_valid"] == neg_val["occupied_controls_exist"]
    )
    off_actor_controls_ok = bool(
        neg_train["off_actor_controls_valid"] == neg_train["off_actor_controls_exist"]
        and neg_val["off_actor_controls_valid"] == neg_val["off_actor_controls_exist"]
    )

    guards_preserved = bool(preserve_train["guards_preserved"] and preserve_val["guards_preserved"])
    movement_preserved = bool(preserve_train["movement_preserved"] and preserve_val["movement_preserved"])
    attack_not_removed = bool(preserve_train["attack_not_removed"] and preserve_val["attack_not_removed"])

    target_distribution_ok = bool(move_rebalanced and noop_shift_ok and occupied_controls_present and off_actor_controls_present)

    overall_valid = bool(
        all(shape_checks.values())
        and all(dtype_checks.values())
        and all(finite_checks.values())
        and branch_valid
        and valid_positive_present
        and valid_targets_confirmed
        and no_leakage
        and occupied_controls_ok
        and off_actor_controls_ok
        and guards_preserved
        and movement_preserved
        and attack_not_removed
        and target_distribution_ok
    )

    labels = [
        "STAGE10D19B_DATASET_VALID" if overall_valid else "STAGE10D19B_DATASET_INVALID",
        "STAGE10D19B_VALID_MOVE_POSITIVES_PRESENT" if valid_positive_present else "STAGE10D19B_DATASET_INVALID",
        "STAGE10D19B_VALID_MOVE_TARGETS_CONFIRMED" if valid_targets_confirmed else "STAGE10D19B_DATASET_INVALID",
        "STAGE10D19B_OCCUPIED_NEGATIVE_CONTROLS_PRESENT" if occupied_controls_present else "STAGE10D19B_DATASET_INVALID",
        "STAGE10D19B_OFF_ACTOR_NEGATIVE_CONTROLS_PRESENT" if off_actor_controls_present else "STAGE10D19B_DATASET_INVALID",
        "STAGE10D19B_NO_LABEL_LEAKAGE_CONFIRMED" if no_leakage else "STAGE10D19B_DATASET_INVALID",
        "STAGE10D19B_B2_C3_GUARDS_PRESERVED" if guards_preserved else "STAGE10D19B_DATASET_INVALID",
        "STAGE10D19B_MOVEMENT_PRESERVATION_CONFIRMED" if movement_preserved else "STAGE10D19B_DATASET_INVALID",
        "STAGE10D19B_TARGET_DISTRIBUTION_ACCEPTABLE" if target_distribution_ok else "STAGE10D19B_TARGET_DISTRIBUTION_RISK",
    ]
    gate = "GO_FOR_STAGE10D19B_VALID_MOVE_BC_TRAINING" if overall_valid else "GO_FOR_STAGE10D19B_DATASET_FIX"

    report: Dict[str, Any] = {
        "stage": "10D.19B",
        "task": "validate_valid_move_augmented_dataset",
        "generated_at_utc": utc_now_iso(),
        "augmented_bc_ready_dir": str(aug_dir.as_posix()),
        "base_bc_ready_dir": str(base_dir.as_posix()),
        "status": "pass" if overall_valid else "fail",
        "shape_checks": shape_checks,
        "dtype_checks": dtype_checks,
        "finite_checks": finite_checks,
        "branch_bounds": {
            "expected": list(BRANCH_SIZES),
            "train": branch_train,
            "validation": branch_val,
        },
        "valid_move_positive_checks": {
            "train": move_train,
            "validation": move_val,
        },
        "negative_control_checks": {
            "train": neg_train,
            "validation": neg_val,
        },
        "preservation_checks": {
            "train": preserve_train,
            "validation": preserve_val,
        },
        "distribution": {
            "base_train": dist_base_train,
            "base_validation": dist_base_val,
            "augmented_train": dist_aug_train,
            "augmented_validation": dist_aug_val,
            "move_rebalanced": move_rebalanced,
            "noop_shift_ok": noop_shift_ok,
        },
        "classification_labels": labels,
        "primary_next_gate": gate,
    }
    write_json(args.output_json, report)
    print(resolve_path(args.output_json).as_posix())
    return 0 if overall_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
