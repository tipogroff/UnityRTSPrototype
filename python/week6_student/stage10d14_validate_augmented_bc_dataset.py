#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

import numpy as np

from stage10d14_common import (
    ACTION_SHAPE,
    ACTION_SLICE,
    ACTION_TYPE_HARVEST,
    ACTION_TYPE_PRODUCE,
    B2_FLAT,
    BRANCH_SIZES,
    C3_FLAT,
    DEFAULT_REPORTS_DIR,
    DEFAULT_TRUE_RAW_CAPTURE,
    OBS_SHAPE,
    OWNER_SLICE,
    PRODUCE_TYPE_SLICE,
    UNIT_TYPE_SLICE,
    action_index_from_observation_cell,
    compute_action_distribution,
    load_json,
    load_split_payload,
    load_true_raw_capture_tensor,
    resolve_path,
    utc_now_iso,
    validate_branch_bounds,
    write_json,
)


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _npz_obs_actions(path: Path) -> tuple[np.ndarray, np.ndarray]:
    payload = load_split_payload(path)
    observations = np.asarray(payload.get("observations", payload.get("input_tensor")), dtype=np.float32)
    actions = np.asarray(payload.get("actions", payload.get("target_action_branches")))
    return observations, actions


def _find_augmented_rows(
    metadata_rows: Sequence[Mapping[str, Any]],
    *,
    family: str | None = None,
    variant: str | None = None,
    target_cell_flat: int | None = None,
    target_action_type: int | None = None,
) -> List[int]:
    indices: List[int] = []
    for idx, row in enumerate(metadata_rows):
        if family is not None and str(row.get("augmentation_family")) != family:
            continue
        if variant is not None and str(row.get("variant")) != variant:
            continue
        if target_cell_flat is not None and int(row.get("target_cell_flat", -1)) != int(target_cell_flat):
            continue
        if target_action_type is not None and int(row.get("target_action_type", -1)) != int(target_action_type):
            continue
        indices.append(idx)
    return indices


def _check_owner_unit_unchanged(
    augmented_obs: np.ndarray,
    original_obs: np.ndarray,
    metadata_rows: Sequence[Mapping[str, Any]],
    original_count: int,
) -> Dict[str, Any]:
    checked = 0
    failures = 0
    for row_idx, row in enumerate(metadata_rows):
        source_split = str(row.get("source_split"))
        if source_split not in {"train", "validation"}:
            continue
        source_sample_index = int(row.get("source_sample_index", -1))
        target_flat = int(row.get("target_cell_flat", -1))
        if source_sample_index < 0 or target_flat < 0:
            continue
        augmented_sample_index = original_count + row_idx
        augmented_cell = augmented_obs[augmented_sample_index, target_flat]
        source_cell = original_obs[source_sample_index, target_flat]
        checked += 1
        if not np.allclose(augmented_cell[OWNER_SLICE], source_cell[OWNER_SLICE]) or not np.allclose(
            augmented_cell[UNIT_TYPE_SLICE], source_cell[UNIT_TYPE_SLICE]
        ):
            failures += 1
    return {
        "checked_rows": int(checked),
        "failure_count": int(failures),
        "passed": bool(failures == 0),
    }


def _leakage_check(observations: np.ndarray, metadata_rows: Sequence[Mapping[str, Any]], original_count: int) -> Dict[str, Any]:
    checked = 0
    direct_match_count = 0
    positive_checked = 0
    positive_direct_match_count = 0
    examples: List[Dict[str, Any]] = []
    for row_idx, row in enumerate(metadata_rows):
        augmented_sample_index = original_count + row_idx
        target_flat = int(row.get("target_cell_flat", -1))
        target_action_type = int(row.get("target_action_type", -1))
        if target_flat < 0 or target_action_type < 0:
            continue
        checked += 1
        observed_idx = action_index_from_observation_cell(observations[augmented_sample_index, target_flat])
        direct_match = observed_idx == target_action_type
        if direct_match:
            direct_match_count += 1
            if len(examples) < 8:
                examples.append(
                    {
                        "metadata_index": int(row_idx),
                        "target_flat": int(target_flat),
                        "target_action_type": int(target_action_type),
                        "observed_action_index": int(observed_idx),
                        "variant": row.get("variant"),
                        "family": row.get("augmentation_family"),
                    }
                )
        if target_action_type in {ACTION_TYPE_HARVEST, ACTION_TYPE_PRODUCE}:
            positive_checked += 1
            if direct_match:
                positive_direct_match_count += 1
    return {
        "checked_rows": int(checked),
        "direct_match_count": int(direct_match_count),
        "direct_match_share": float(direct_match_count / checked) if checked > 0 else 0.0,
        "positive_checked_rows": int(positive_checked),
        "positive_direct_match_count": int(positive_direct_match_count),
        "positive_direct_match_share": float(positive_direct_match_count / positive_checked) if positive_checked > 0 else 0.0,
        "examples": examples,
        "passed": bool(positive_direct_match_count == 0),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate Stage10D.14 augmented BC dataset")
    p.add_argument("--augmented-bc-ready-dir", type=Path, required=True)
    p.add_argument("--original-bc-ready-dir", type=Path, default=None)
    p.add_argument("--true-raw-capture", type=Path, default=Path(DEFAULT_TRUE_RAW_CAPTURE))
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path(DEFAULT_REPORTS_DIR) / "stage10d14_augmented_dataset_validation.json",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    augmented_dir = resolve_path(args.augmented_bc_ready_dir).resolve()
    manifest = load_json(augmented_dir / "stage10d14_augmentation_manifest.json")
    original_dir = (
        resolve_path(args.original_bc_ready_dir).resolve()
        if args.original_bc_ready_dir is not None
        else resolve_path(manifest["original_dataset_path"]).resolve()
    )
    runtime_map = load_true_raw_capture_tensor(args.true_raw_capture)

    original_train_obs, original_train_actions = _npz_obs_actions(original_dir / "bc_train.npz")
    original_val_obs, original_val_actions = _npz_obs_actions(original_dir / "bc_validation.npz")
    augmented_train_obs, augmented_train_actions = _npz_obs_actions(augmented_dir / "bc_train.npz")
    augmented_val_obs, augmented_val_actions = _npz_obs_actions(augmented_dir / "bc_validation.npz")

    train_metadata = _read_jsonl(augmented_dir / "stage10d14_augmented_sample_metadata_train.jsonl")
    val_metadata = _read_jsonl(augmented_dir / "stage10d14_augmented_sample_metadata_validation.jsonl")

    shape_checks = {
        "train_observations_shape": bool(augmented_train_obs.ndim == 3 and tuple(augmented_train_obs.shape[1:]) == OBS_SHAPE),
        "train_actions_shape": bool(augmented_train_actions.ndim == 3 and tuple(augmented_train_actions.shape[1:]) == ACTION_SHAPE),
        "validation_observations_shape": bool(augmented_val_obs.ndim == 3 and tuple(augmented_val_obs.shape[1:]) == OBS_SHAPE),
        "validation_actions_shape": bool(augmented_val_actions.ndim == 3 and tuple(augmented_val_actions.shape[1:]) == ACTION_SHAPE),
    }
    dtype_checks = {
        "observations_float32": bool(augmented_train_obs.dtype == np.float32 and augmented_val_obs.dtype == np.float32),
        "actions_integer": bool(
            np.issubdtype(augmented_train_actions.dtype, np.integer)
            and np.issubdtype(augmented_val_actions.dtype, np.integer)
        ),
    }
    finite_checks = {
        "train_finite": bool(np.isfinite(augmented_train_obs).all()),
        "validation_finite": bool(np.isfinite(augmented_val_obs).all()),
    }
    branch_bounds = {
        "train": validate_branch_bounds(augmented_train_actions),
        "validation": validate_branch_bounds(augmented_val_actions),
    }
    branch_bounds_valid = bool(all(branch_bounds["train"].values()) and all(branch_bounds["validation"].values()))

    true_raw_train_rows = _find_augmented_rows(
        train_metadata,
        family="family1_true_raw_unity_observation_teacher_labels",
    )
    true_raw_present = bool(len(true_raw_train_rows) > 0)
    true_raw_matches = 0
    for metadata_index in true_raw_train_rows:
        sample_index = original_train_obs.shape[0] + metadata_index
        if np.allclose(augmented_train_obs[sample_index], runtime_map.reshape(OBS_SHAPE)):
            true_raw_matches += 1

    b2_rows = _find_augmented_rows(train_metadata, target_cell_flat=B2_FLAT, target_action_type=ACTION_TYPE_HARVEST)
    c3_rows = _find_augmented_rows(train_metadata, target_cell_flat=C3_FLAT, target_action_type=ACTION_TYPE_PRODUCE)

    b2_unity_like_present = False
    for row_idx in b2_rows:
        sample_index = original_train_obs.shape[0] + row_idx
        observed_action_idx = action_index_from_observation_cell(augmented_train_obs[sample_index, B2_FLAT])
        if observed_action_idx in {-1, 0}:
            b2_unity_like_present = True
            break

    c3_unity_like_present = False
    for row_idx in c3_rows:
        sample_index = original_train_obs.shape[0] + row_idx
        observed_action_idx = action_index_from_observation_cell(augmented_train_obs[sample_index, C3_FLAT])
        if observed_action_idx in {-1, 0}:
            c3_unity_like_present = True
            break

    base_local_variants_exist = bool(
        _find_augmented_rows(train_metadata, family="family3_base_local_context", variant="local_3x3_current_action_noop")
        and _find_augmented_rows(train_metadata, family="family3_base_local_context", variant="local_5x5_current_action_noop")
    )

    owner_unit_check_train = _check_owner_unit_unchanged(
        augmented_train_obs,
        original_train_obs,
        train_metadata,
        original_train_obs.shape[0],
    )
    owner_unit_check_val = _check_owner_unit_unchanged(
        augmented_val_obs,
        original_val_obs,
        val_metadata,
        original_val_obs.shape[0],
    )
    owner_unit_unchanged = bool(owner_unit_check_train["passed"] and owner_unit_check_val["passed"])

    leakage_train = _leakage_check(augmented_train_obs, train_metadata, original_train_obs.shape[0])
    leakage_val = _leakage_check(augmented_val_obs, val_metadata, original_val_obs.shape[0])
    leakage_pass = bool(leakage_train["passed"] and leakage_val["passed"])

    original_train_dist = compute_action_distribution(original_train_obs, original_train_actions)
    original_val_dist = compute_action_distribution(original_val_obs, original_val_actions)
    augmented_train_dist = compute_action_distribution(augmented_train_obs, augmented_train_actions)
    augmented_val_dist = compute_action_distribution(augmented_val_obs, augmented_val_actions)

    target_distribution_accept = bool(
        augmented_train_dist["worker_harvest"] > original_train_dist["worker_harvest"]
        and augmented_train_dist["base_produce"] > original_train_dist["base_produce"]
        and augmented_train_dist["attack"] >= original_train_dist["attack"]
        and abs(augmented_train_dist["noop_ratio_all_cells"] - original_train_dist["noop_ratio_all_cells"]) <= 0.01
        and abs(augmented_val_dist["noop_ratio_all_cells"] - original_val_dist["noop_ratio_all_cells"]) <= 0.01
    )

    semantic_checks = {
        "true_raw_unity_like_sample_exists": true_raw_present,
        "true_raw_unity_like_sample_exact_match_exists": bool(true_raw_matches > 0),
        "b2_unity_like_harvest_target_present": b2_unity_like_present,
        "c3_unity_like_produce_target_present": c3_unity_like_present,
        "owner_unit_channels_unchanged": owner_unit_unchanged,
        "c3_local_context_variants_exist": base_local_variants_exist,
    }

    overall_valid = bool(
        all(shape_checks.values())
        and all(dtype_checks.values())
        and all(finite_checks.values())
        and branch_bounds_valid
        and all(semantic_checks.values())
        and leakage_pass
        and target_distribution_accept
    )

    classification_labels: List[str] = [
        "AUGMENTED_DATASET_VALID" if overall_valid else "AUGMENTED_DATASET_INVALID",
        "TRUE_RAW_UNITY_LIKE_SAMPLE_PRESENT" if true_raw_present and true_raw_matches > 0 else "AUGMENTED_DATASET_INVALID",
        "B2_UNITY_LIKE_HARVEST_TARGET_PRESENT" if b2_unity_like_present else "AUGMENTED_DATASET_INVALID",
        "C3_UNITY_LIKE_PRODUCE_TARGET_PRESENT" if c3_unity_like_present else "AUGMENTED_DATASET_INVALID",
        "NO_OBSERVATION_LABEL_LEAKAGE_CONFIRMED" if leakage_pass else "LABEL_LEAKAGE_RISK_DETECTED",
        "BRANCH_BOUNDS_VALID" if branch_bounds_valid else "AUGMENTED_DATASET_INVALID",
        "TARGET_DISTRIBUTION_ACCEPTABLE" if target_distribution_accept else "TARGET_DISTRIBUTION_RISK",
    ]
    gate = "GO_FOR_STAGE10D14_AUGMENTED_BC_TRAINING" if overall_valid else "GO_FOR_STAGE10D14_AUGMENTATION_FIX"

    report: Dict[str, Any] = {
        "stage": "10D.14",
        "task": "augmented_bc_dataset_validation",
        "generated_at_utc": utc_now_iso(),
        "augmented_bc_ready_dir": augmented_dir.as_posix(),
        "original_bc_ready_dir": original_dir.as_posix(),
        "status": "pass" if overall_valid else "fail",
        "shape_checks": shape_checks,
        "dtype_checks": dtype_checks,
        "finite_checks": finite_checks,
        "branch_bounds": branch_bounds,
        "semantic_checks": semantic_checks,
        "owner_unit_integrity": {
            "train": owner_unit_check_train,
            "validation": owner_unit_check_val,
        },
        "label_leakage_checks": {
            "train": leakage_train,
            "validation": leakage_val,
        },
        "distribution_checks": {
            "original_train": original_train_dist,
            "original_validation": original_val_dist,
            "augmented_train": augmented_train_dist,
            "augmented_validation": augmented_val_dist,
            "target_distribution_acceptable": target_distribution_accept,
        },
        "classification_labels": classification_labels,
        "primary_next_gate": gate,
    }
    write_json(args.output_json, report)
    print(resolve_path(args.output_json).as_posix())
    return 0 if overall_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())