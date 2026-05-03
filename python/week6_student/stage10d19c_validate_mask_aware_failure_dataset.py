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
    OBS_SHAPE,
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
    p = argparse.ArgumentParser(description="Stage10D.19C validate mask-aware failure dataset")
    p.add_argument("--augmented-bc-ready-dir", type=Path, required=True)
    p.add_argument("--base-bc-ready-dir", type=Path, default=None)
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d19c_mask_aware_failure_dataset_validation.json"),
    )
    return p.parse_args()


def _family_counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in rows:
        fam = str(r.get("augmentation_family", ""))
        out[fam] = int(out.get(fam, 0) + 1)
    return out


def _leakage_check(obs: np.ndarray, actions: np.ndarray, rows: List[Dict[str, Any]], original_count: int) -> int:
    leakage = 0
    for i, row in enumerate(rows):
        src = int(row.get("source_cell", -1))
        if src < 0:
            continue
        idx = original_count + i
        if idx >= obs.shape[0]:
            continue
        obs_action = int(np.argmax(obs[idx, src, ACTION_SLICE])) if float(np.max(obs[idx, src, ACTION_SLICE])) > 0 else -1
        tgt_action = int(actions[idx, src, 0])
        if obs_action == tgt_action and tgt_action != ACTION_TYPE_NOOP:
            leakage += 1
    return int(leakage)


def _family_legal_checks(actions: np.ndarray, rows: List[Dict[str, Any]], original_count: int) -> Dict[str, Any]:
    fam_b_total = 0
    fam_b_ok = 0
    fam_a_total = 0
    fam_a_ok = 0
    fam_d_total = 0
    fam_d_ok = 0

    for i, row in enumerate(rows):
        fam = str(row.get("augmentation_family", ""))
        src = int(row.get("source_cell", -1))
        idx = original_count + i
        if src < 0 or idx >= actions.shape[0]:
            continue
        act = int(actions[idx, src, 0])

        if fam == "family_b_valid_alt_move":
            fam_b_total += 1
            legal = bool(
                act == ACTION_TYPE_MOVE
                and bool(row.get("target_move_legal_under_mask", False))
                and bool(row.get("target_cell_in_bounds", False))
                and bool(row.get("target_cell_free", False))
                and bool(row.get("target_adjacent", False))
            )
            if legal:
                fam_b_ok += 1

        if fam == "family_a_no_valid_alt_noop":
            fam_a_total += 1
            reason = str(row.get("reason", ""))
            justified = reason in {"no_valid_alternative_dir", "policy_noop_control_for_blocked_dir"}
            if act == ACTION_TYPE_NOOP and justified:
                fam_a_ok += 1

        if fam == "family_d_off_actor_hard_negative":
            fam_d_total += 1
            if act == ACTION_TYPE_NOOP and bool(row.get("off_actor_control", False)):
                fam_d_ok += 1

    return {
        "family_b_valid_alt_total": int(fam_b_total),
        "family_b_valid_alt_ok": int(fam_b_ok),
        "family_a_no_valid_alt_total": int(fam_a_total),
        "family_a_no_valid_alt_ok": int(fam_a_ok),
        "family_d_off_actor_total": int(fam_d_total),
        "family_d_off_actor_ok": int(fam_d_ok),
    }


def _preservation_checks(base_actions: np.ndarray, aug_actions: np.ndarray, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    b2_base = int(np.sum(base_actions[:, B2_FLAT, 0] == ACTION_TYPE_HARVEST))
    c3_base = int(np.sum(base_actions[:, C3_FLAT, 0] == ACTION_TYPE_PRODUCE))
    b2_aug = int(np.sum(aug_actions[:, B2_FLAT, 0] == ACTION_TYPE_HARVEST))
    c3_aug = int(np.sum(aug_actions[:, C3_FLAT, 0] == ACTION_TYPE_PRODUCE))

    move_base = int(np.sum(base_actions[:, :, 0] == ACTION_TYPE_MOVE))
    move_aug = int(np.sum(aug_actions[:, :, 0] == ACTION_TYPE_MOVE))

    attack_base = int(np.sum(base_actions[:, :, 0] == ACTION_TYPE_ATTACK))
    attack_aug = int(np.sum(aug_actions[:, :, 0] == ACTION_TYPE_ATTACK))

    preserve_rows = int(sum(1 for r in rows if bool(r.get("preservation_sample", False))))

    return {
        "b2_harvest_base": b2_base,
        "b2_harvest_augmented": b2_aug,
        "c3_produce_base": c3_base,
        "c3_produce_augmented": c3_aug,
        "move_labels_base": move_base,
        "move_labels_augmented": move_aug,
        "attack_labels_base": attack_base,
        "attack_labels_augmented": attack_aug,
        "preservation_rows": preserve_rows,
        "b2_c3_preserved": bool(b2_aug >= b2_base and c3_aug >= c3_base),
        "movement_preserved": bool(move_aug >= int(0.85 * move_base)),
        "attack_preserved": bool(attack_aug >= int(0.5 * attack_base)),
    }


def main() -> int:
    args = parse_args()
    aug_dir = resolve_path(args.augmented_bc_ready_dir)

    manifest = load_json(aug_dir / "stage10d19c_mask_aware_failure_augmentation_manifest.json")
    base_dir = resolve_path(args.base_bc_ready_dir) if args.base_bc_ready_dir else Path(manifest["base_dataset_path"])

    aug_train_payload = load_split_payload(aug_dir / "bc_train.npz")
    aug_val_payload = load_split_payload(aug_dir / "bc_validation.npz")
    base_train_payload = load_split_payload(base_dir / "bc_train.npz")
    base_val_payload = load_split_payload(base_dir / "bc_validation.npz")

    aug_train_obs, aug_train_actions = get_observations_and_actions(aug_train_payload)
    aug_val_obs, aug_val_actions = get_observations_and_actions(aug_val_payload)
    base_train_obs, base_train_actions = get_observations_and_actions(base_train_payload)
    base_val_obs, base_val_actions = get_observations_and_actions(base_val_payload)

    meta_train = read_jsonl(aug_dir / "stage10d19c_augmented_sample_metadata_train.jsonl")
    meta_val = read_jsonl(aug_dir / "stage10d19c_augmented_sample_metadata_validation.jsonl")

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

    family_train = _family_counts(meta_train)
    family_val = _family_counts(meta_val)

    coverage = {
        "occupied_target_failure_cases_included": bool((family_train.get("family_b_valid_alt_move", 0) + family_val.get("family_b_valid_alt_move", 0)) > 0),
        "valid_alt_cases_included": bool((family_train.get("family_b_valid_alt_move", 0) + family_val.get("family_b_valid_alt_move", 0)) > 0),
        "no_valid_alt_cases_included": bool((family_train.get("family_a_no_valid_alt_noop", 0) + family_val.get("family_a_no_valid_alt_noop", 0)) > 0),
        "off_actor_hard_negatives_included": bool((family_train.get("family_d_off_actor_hard_negative", 0) + family_val.get("family_d_off_actor_hard_negative", 0)) > 0),
        "preservation_rows_included": bool((family_train.get("family_f_preservation", 0) + family_val.get("family_f_preservation", 0)) > 0),
    }

    legal_train = _family_legal_checks(aug_train_actions, meta_train, original_count=base_train_obs.shape[0])
    legal_val = _family_legal_checks(aug_val_actions, meta_val, original_count=base_val_obs.shape[0])

    leakage_train = _leakage_check(aug_train_obs, aug_train_actions, meta_train, original_count=base_train_obs.shape[0])
    leakage_val = _leakage_check(aug_val_obs, aug_val_actions, meta_val, original_count=base_val_obs.shape[0])

    preserve_train = _preservation_checks(base_train_actions, aug_train_actions, meta_train)
    preserve_val = _preservation_checks(base_val_actions, aug_val_actions, meta_val)

    dist_base_train = summarize_action_type_distribution(base_train_obs, base_train_actions)
    dist_base_val = summarize_action_type_distribution(base_val_obs, base_val_actions)
    dist_aug_train = summarize_action_type_distribution(aug_train_obs, aug_train_actions)
    dist_aug_val = summarize_action_type_distribution(aug_val_obs, aug_val_actions)

    noop_ratio_ok = bool(
        abs(dist_aug_train["noop_ratio_all_cells"] - dist_base_train["noop_ratio_all_cells"]) <= 0.2
        and abs(dist_aug_val["noop_ratio_all_cells"] - dist_base_val["noop_ratio_all_cells"]) <= 0.2
    )
    move_not_catastrophic = bool(
        dist_aug_train["actor_action_type_counts"]["Move"] >= int(0.75 * dist_base_train["actor_action_type_counts"]["Move"])
    )
    off_actor_present = coverage["off_actor_hard_negatives_included"]

    target_distribution_ok = bool(noop_ratio_ok and move_not_catastrophic and off_actor_present)

    legal_ok = bool(
        legal_train["family_b_valid_alt_ok"] == legal_train["family_b_valid_alt_total"]
        and legal_val["family_b_valid_alt_ok"] == legal_val["family_b_valid_alt_total"]
        and legal_train["family_a_no_valid_alt_ok"] == legal_train["family_a_no_valid_alt_total"]
        and legal_val["family_a_no_valid_alt_ok"] == legal_val["family_a_no_valid_alt_total"]
        and legal_train["family_d_off_actor_ok"] >= max(0, legal_train["family_d_off_actor_total"] - 1)
        and legal_val["family_d_off_actor_ok"] >= max(0, legal_val["family_d_off_actor_total"] - 1)
    )

    no_leakage = bool((leakage_train + leakage_val) == 0)
    b2c3_ok = bool(preserve_train["b2_c3_preserved"] and preserve_val["b2_c3_preserved"])
    movement_ok = bool(preserve_train["movement_preserved"] and preserve_val["movement_preserved"])
    attack_ok = bool(preserve_train["attack_preserved"] and preserve_val["attack_preserved"])

    overall_valid = bool(
        all(shape_checks.values())
        and all(dtype_checks.values())
        and all(finite_checks.values())
        and all(branch_train.values())
        and all(branch_val.values())
        and coverage["occupied_target_failure_cases_included"]
        and coverage["valid_alt_cases_included"]
        and coverage["off_actor_hard_negatives_included"]
        and coverage["preservation_rows_included"]
        and legal_ok
        and no_leakage
        and b2c3_ok
        and movement_ok
        and attack_ok
        and target_distribution_ok
    )

    labels = [
        "STAGE10D19C_DATASET_VALID" if overall_valid else "STAGE10D19C_DATASET_INVALID",
        "STAGE10D19C_FAILURE_CASE_COVERAGE_CONFIRMED" if coverage["occupied_target_failure_cases_included"] else "STAGE10D19C_DATASET_INVALID",
        "STAGE10D19C_VALID_ALT_MOVE_LABELS_CONFIRMED" if coverage["valid_alt_cases_included"] else "STAGE10D19C_DATASET_INVALID",
        "STAGE10D19C_NO_VALID_ALT_NOOP_LABELS_CONFIRMED" if coverage["no_valid_alt_cases_included"] else "STAGE10D19C_TARGET_DISTRIBUTION_RISK",
        "STAGE10D19C_OFF_ACTOR_HARD_NEGATIVES_CONFIRMED" if coverage["off_actor_hard_negatives_included"] else "STAGE10D19C_DATASET_INVALID",
        "STAGE10D19C_MASK_LEGAL_LABELS_CONFIRMED" if legal_ok else "STAGE10D19C_DATASET_INVALID",
        "STAGE10D19C_NO_LABEL_LEAKAGE_CONFIRMED" if no_leakage else "STAGE10D19C_DATASET_INVALID",
        "STAGE10D19C_B2_C3_GUARDS_PRESERVED" if b2c3_ok else "STAGE10D19C_DATASET_INVALID",
        "STAGE10D19C_MOVEMENT_PRESERVATION_CONFIRMED" if movement_ok else "STAGE10D19C_DATASET_INVALID",
        "STAGE10D19C_ATTACK_LABELS_PRESERVED" if attack_ok else "STAGE10D19C_DATASET_INVALID",
        "STAGE10D19C_TARGET_DISTRIBUTION_ACCEPTABLE" if target_distribution_ok else "STAGE10D19C_TARGET_DISTRIBUTION_RISK",
    ]

    gate = "GO_FOR_STAGE10D19C_MASK_AWARE_BC_TRAINING" if overall_valid else "GO_FOR_STAGE10D19C_DATASET_FIX"

    report: Dict[str, Any] = {
        "stage": "10D.19C",
        "task": "validate_mask_aware_failure_dataset",
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
        "family_coverage": coverage,
        "family_counts": {"train": family_train, "validation": family_val},
        "legal_label_checks": {"train": legal_train, "validation": legal_val},
        "leakage_checks": {
            "leakage_risk_train": int(leakage_train),
            "leakage_risk_validation": int(leakage_val),
            "leakage_risk_total": int(leakage_train + leakage_val),
        },
        "preservation": {"train": preserve_train, "validation": preserve_val},
        "distribution": {
            "base_train": dist_base_train,
            "base_validation": dist_base_val,
            "augmented_train": dist_aug_train,
            "augmented_validation": dist_aug_val,
            "noop_ratio_ok": noop_ratio_ok,
            "move_not_catastrophic": move_not_catastrophic,
        },
        "classification_labels": labels,
        "primary_next_gate": gate,
    }

    write_json(args.output_json, report)
    print(resolve_path(args.output_json).as_posix())
    return 0 if overall_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
