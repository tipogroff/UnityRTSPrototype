#!/usr/bin/env python
"""
Validator for Stage5P1 smoke export.
Checks schema, manifest, action bounds, and episode consistency.
Reports hard failures for schema/contract issues; soft warnings for behavior quality.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np


REQUIRED_NPZ_ARRAYS = [
    "observation_t",
    "per_cell_action_t",
    "episode_id",
    "step_id",
    "reward_t",
    "done_t",
    "terminated_t",
    "truncated_t",
    "action_mask_available_t",
]

OPTIONAL_DIAGNOSTIC_ARRAYS = [
    "source_valid_action_count_t",
    "selected_non_noop_count_t",
    "source_valid_non_noop_count_t",
    "mask_source_valid_count_t",
]

BRANCH_SIZES = [6, 4, 4, 4, 4, 7, 49]


def _error(msg: str) -> None:
    print(f"[ERROR] {msg}")


def _warn(msg: str) -> None:
    print(f"[WARN]  {msg}")


def _info(msg: str) -> None:
    print(f"[INFO]  {msg}")


def validate_npz_schema(npz_path: Path) -> Tuple[bool, Dict[str, Any]]:
    """Check NPZ file schema and array properties."""
    results = {
        "npz_exists": False,
        "arrays_missing": [],
        "obs_shape_valid": False,
        "obs_dtype_valid": False,
        "action_shape_valid": False,
        "action_dtype_valid": False,
        "total_steps": 0,
        "nan_inf_in_obs": False,
        "nan_inf_in_reward": False,
    }

    if not npz_path.exists():
        _error(f"NPZ file does not exist: {npz_path}")
        return False, results

    results["npz_exists"] = True

    try:
        npz = np.load(npz_path, allow_pickle=False)
    except Exception as e:
        _error(f"Failed to load NPZ: {e}")
        return False, results

    # Check required arrays
    for arr_name in REQUIRED_NPZ_ARRAYS:
        if arr_name not in npz:
            results["arrays_missing"].append(arr_name)
            _error(f"Required array missing: {arr_name}")

    if results["arrays_missing"]:
        return False, results

    # Observation validation
    obs = npz["observation_t"]
    if obs.ndim != 4:
        _error(f"observation_t.ndim={obs.ndim}, expected 4")
        return False, results
    results["obs_shape_valid"] = obs.shape[1:] == (24, 24, 27)
    if not results["obs_shape_valid"]:
        _error(f"observation_t.shape[1:]={obs.shape[1:]}, expected (24,24,27)")
        return False, results

    results["obs_dtype_valid"] = obs.dtype == np.float32
    if not results["obs_dtype_valid"]:
        _error(f"observation_t.dtype={obs.dtype}, expected float32")
        return False, results

    if np.any(np.isnan(obs)) or np.any(np.isinf(obs)):
        results["nan_inf_in_obs"] = True
        _error(f"observation_t contains NaN/Inf")
        return False, results

    # Per-cell action validation
    action = npz["per_cell_action_t"]
    if action.ndim != 3:
        _error(f"per_cell_action_t.ndim={action.ndim}, expected 3")
        return False, results
    results["action_shape_valid"] = action.shape[1:] == (576, 7)
    if not results["action_shape_valid"]:
        _error(f"per_cell_action_t.shape[1:]={action.shape[1:]}, expected (576,7)")
        return False, results

    results["action_dtype_valid"] = action.dtype in [np.int16, np.int32, np.int64]
    if not results["action_dtype_valid"]:
        _error(f"per_cell_action_t.dtype={action.dtype}, expected int16-compatible")
        return False, results

    # Metadata array length validation
    T = obs.shape[0]
    results["total_steps"] = int(T)

    for arr_name in REQUIRED_NPZ_ARRAYS[1:]:  # Skip obs (already checked)
        arr = npz[arr_name]
        if len(arr) != T:
            _error(f"{arr_name}.shape[0]={len(arr)}, expected {T}")
            return False, results

    # Reward NaN/Inf check
    reward = npz["reward_t"]
    if np.any(np.isnan(reward)) or np.any(np.isinf(reward)):
        results["nan_inf_in_reward"] = True
        _error(f"reward_t contains NaN/Inf")
        return False, results

    # Bool array dtype check
    for bool_arr_name in ["done_t", "terminated_t", "truncated_t", "action_mask_available_t"]:
        arr = npz[bool_arr_name]
        if arr.dtype != np.bool_:
            _error(f"{bool_arr_name}.dtype={arr.dtype}, expected bool")
            return False, results

    npz.close()
    return True, results


def validate_action_bounds(npz_path: Path) -> Tuple[bool, Dict[str, Any]]:
    """Check action branch bounds."""
    results = {
        "branch_bounds_valid": [False] * 7,
        "bounds_errors": [],
    }

    try:
        npz = np.load(npz_path, allow_pickle=False)
    except Exception:
        return False, results

    action = npz["per_cell_action_t"]  # [T, 576, 7]
    T = action.shape[0]

    for branch_idx, max_val in enumerate(BRANCH_SIZES):
        branch_data = action[:, :, branch_idx]  # [T, 576]
        min_val_found = int(np.min(branch_data))
        max_val_found = int(np.max(branch_data))

        if min_val_found < 0 or max_val_found >= max_val:
            msg = (
                f"Branch {branch_idx}: range [{min_val_found}, {max_val_found}], "
                f"expected [0, {max_val-1}]"
            )
            results["bounds_errors"].append(msg)
            _error(msg)
        else:
            results["branch_bounds_valid"][branch_idx] = True

    npz.close()
    return all(results["branch_bounds_valid"]), results


def validate_episode_consistency(npz_path: Path) -> Tuple[bool, Dict[str, Any]]:
    """Check episode/step consistency."""
    results = {
        "episode_count": 0,
        "episode_ids_unique": 0,
        "step_consistency_valid": False,
        "errors": [],
        "episode_lengths": [],
    }

    try:
        npz = np.load(npz_path, allow_pickle=False)
    except Exception:
        return False, results

    episode_id = npz["episode_id"]
    step_id = npz["step_id"]
    done = npz["done_t"]

    T = len(episode_id)
    results["episode_count"] = int(T)
    results["episode_ids_unique"] = int(len(np.unique(episode_id)))

    # Check that each episode's step_id starts at 0 and is contiguous
    ep_list = np.unique(episode_id)
    step_consistency_valid = True

    for ep_idx in ep_list:
        ep_mask = episode_id == ep_idx
        ep_steps = step_id[ep_mask]
        ep_done = done[ep_mask]

        if len(ep_steps) == 0:
            results["errors"].append(f"Episode {ep_idx} has no steps")
            step_consistency_valid = False
            continue

        # Check step_id starts at 0
        if ep_steps[0] != 0:
            results["errors"].append(f"Episode {ep_idx}: first step_id={ep_steps[0]}, expected 0")
            step_consistency_valid = False

        # Check contiguity
        expected_steps = np.arange(len(ep_steps))
        if not np.array_equal(ep_steps, expected_steps):
            results["errors"].append(
                f"Episode {ep_idx}: step_id is not contiguous. "
                f"got {list(ep_steps[:5])}..., expected 0,1,2,..."
            )
            step_consistency_valid = False

        results["episode_lengths"].append(int(len(ep_steps)))

    results["step_consistency_valid"] = step_consistency_valid

    npz.close()
    return step_consistency_valid and len(results["errors"]) == 0, results


def validate_manifest_schema(manifest_path: Path) -> Tuple[bool, Dict[str, Any]]:
    """Check manifest JSON schema and values."""
    results = {
        "manifest_exists": False,
        "schema_version_valid": False,
        "teacher_lineage_valid": False,
        "architecture_valid": False,
        "gym_version_valid": False,
        "map_path_valid": False,
        "obs_shape_valid": False,
        "raw_action_nvec_valid": False,
        "stored_action_format_valid": False,
        "step_mode_valid": False,
        "mask_required_valid": False,
        "export_mode_valid": False,
        "parity_claims_false": False,
        "step_mode_is_final_evidence_valid": False,
        "missing_fields": [],
        "schema_errors": [],
    }

    if not manifest_path.exists():
        _error(f"Manifest file does not exist: {manifest_path}")
        return False, results

    results["manifest_exists"] = True

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        _error(f"Failed to load manifest JSON: {e}")
        return False, results

    # Required fields check
    required_fields = [
        "schema_version",
        "teacher_lineage",
        "architecture",
        "gym_microrts_version",
        "map_path",
        "observation_shape",
        "raw_action_nvec",
        "stored_action_format",
        "stored_action_shape",
        "stored_action_branch_sizes",
        "exported_per_cell_branch_sizes",
        "env_step_action_format",
        "step_mode",
        "mask_required",
        "mask_source",
        "export_mode",
        "episodes",
        "total_steps",
        "semantic_parity_claim",
        "direct_weight_transfer_claim",
        "step_mode_is_final_evidence_valid",
    ]

    for field in required_fields:
        if field not in manifest:
            results["missing_fields"].append(field)
            _error(f"Missing manifest field: {field}")

    if results["missing_fields"]:
        return False, results

    # Schema version
    if manifest["schema_version"] != "legacy032.teacher_rollout_raw.v2":
        msg = f"schema_version={manifest['schema_version']}, expected legacy032.teacher_rollout_raw.v2"
        results["schema_errors"].append(msg)
        _error(msg)
    else:
        results["schema_version_valid"] = True

    # Teacher lineage
    if manifest["teacher_lineage"] != "legacy032":
        msg = f"teacher_lineage={manifest['teacher_lineage']}, expected legacy032"
        results["schema_errors"].append(msg)
        _error(msg)
    else:
        results["teacher_lineage_valid"] = True

    # Architecture
    if manifest["architecture"] != "legacy032_resolution_aware_gridnet_v1":
        msg = f"architecture={manifest['architecture']}, expected legacy032_resolution_aware_gridnet_v1"
        results["schema_errors"].append(msg)
        _error(msg)
    else:
        results["architecture_valid"] = True

    # Gym version
    if manifest["gym_microrts_version"] != "0.3.2":
        msg = f"gym_microrts_version={manifest['gym_microrts_version']}, expected 0.3.2"
        results["schema_errors"].append(msg)
        _error(msg)
    else:
        results["gym_version_valid"] = True

    # Map path
    if manifest["map_path"] != "maps/24x24/basesWorkers24x24.xml":
        msg = f"map_path={manifest['map_path']}, expected maps/24x24/basesWorkers24x24.xml"
        results["schema_errors"].append(msg)
        _error(msg)
    else:
        results["map_path_valid"] = True

    # Observation shape
    if manifest["observation_shape"] != [24, 24, 27]:
        msg = f"observation_shape={manifest['observation_shape']}, expected [24,24,27]"
        results["schema_errors"].append(msg)
        _error(msg)
    else:
        results["obs_shape_valid"] = True

    # Raw action nvec
    if manifest["raw_action_nvec"] != [576, 6, 4, 4, 4, 4, 7, 49]:
        msg = f"raw_action_nvec={manifest['raw_action_nvec']}, expected [576,6,4,4,4,4,7,49]"
        results["schema_errors"].append(msg)
        _error(msg)
    else:
        results["raw_action_nvec_valid"] = True

    # Stored action format
    if manifest["stored_action_format"] != "per_cell_policy_branches":
        msg = f"stored_action_format={manifest['stored_action_format']}, expected per_cell_policy_branches"
        results["schema_errors"].append(msg)
        _error(msg)
    else:
        results["stored_action_format_valid"] = True

    # Step mode
    if manifest["step_mode"] != "training_compatible":
        msg = f"step_mode={manifest['step_mode']}, expected training_compatible"
        results["schema_errors"].append(msg)
        _error(msg)
    else:
        results["step_mode_valid"] = True

    # Mask required
    if manifest["mask_required"] != True:
        msg = f"mask_required={manifest['mask_required']}, expected True"
        results["schema_errors"].append(msg)
        _error(msg)
    else:
        results["mask_required_valid"] = True

    # Export mode
    if manifest["export_mode"] not in ["deterministic", "stochastic"]:
        msg = f"export_mode={manifest['export_mode']}, expected deterministic or stochastic"
        results["schema_errors"].append(msg)
        _error(msg)
    else:
        results["export_mode_valid"] = True

    # Parity claims
    if manifest["semantic_parity_claim"] == False and manifest["direct_weight_transfer_claim"] == False:
        results["parity_claims_false"] = True
    else:
        msg = "semantic_parity_claim or direct_weight_transfer_claim is not False"
        results["schema_errors"].append(msg)
        _error(msg)

    # Step mode is final evidence valid
    if manifest.get("step_mode_is_final_evidence_valid") == True:
        results["step_mode_is_final_evidence_valid"] = True
    else:
        msg = "step_mode_is_final_evidence_valid is not True"
        results["schema_errors"].append(msg)
        _error(msg)

    return len(results["schema_errors"]) == 0, results


def validate_mask_availability(npz_path: Path) -> Tuple[bool, Dict[str, Any]]:
    """Check mask availability."""
    results = {
        "mask_available_share": 0.0,
        "mask_available_count": 0,
        "mask_unavailable_count": 0,
        "is_perfect": False,
    }

    try:
        npz = np.load(npz_path, allow_pickle=False)
    except Exception:
        return False, results

    mask_avail = npz["action_mask_available_t"]
    T = len(mask_avail)

    results["mask_available_count"] = int(np.count_nonzero(mask_avail))
    results["mask_unavailable_count"] = int(T - results["mask_available_count"])
    results["mask_available_share"] = float(
        results["mask_available_count"] / max(1, T)
    )

    results["is_perfect"] = results["mask_available_share"] == 1.0

    npz.close()
    return True, results


def compute_diagnostics(npz_path: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Compute soft diagnostic statistics."""
    diagnostics = {
        "total_steps": 0,
        "episode_count": 0,
        "episode_returns": [],
        "episode_mean_return": 0.0,
        "terminal_count": 0,
        "terminated_count": 0,
        "truncated_count": 0,
        "action_type_histogram": {},
        "selected_non_noop_total": 0,
        "source_valid_non_noop_total": 0,
        "source_valid_total": 0,
        "noop_share": 0.0,
        "is_completely_degenerate": False,
    }

    try:
        npz = np.load(npz_path, allow_pickle=False)
    except Exception:
        return diagnostics

    reward = npz["reward_t"]
    done = npz["done_t"]
    terminated = npz["terminated_t"]
    truncated = npz["truncated_t"]
    episode_id = npz["episode_id"]
    action = npz["per_cell_action_t"]

    diagnostics["total_steps"] = int(len(reward))
    diagnostics["episode_count"] = int(len(np.unique(episode_id)))
    diagnostics["terminal_count"] = int(np.count_nonzero(done))
    diagnostics["terminated_count"] = int(np.count_nonzero(terminated))
    diagnostics["truncated_count"] = int(np.count_nonzero(truncated))

    # Episode returns
    for ep_idx in np.unique(episode_id):
        ep_mask = episode_id == ep_idx
        ep_return = float(np.sum(reward[ep_mask]))
        diagnostics["episode_returns"].append(ep_return)

    if diagnostics["episode_returns"]:
        diagnostics["episode_mean_return"] = float(
            np.mean(np.array(diagnostics["episode_returns"]))
        )

    # Action type histogram (branch 0)
    action_type_0 = action[:, :, 0]  # [T, 576]
    unique, counts = np.unique(action_type_0, return_counts=True)
    diagnostics["action_type_histogram"] = {
        int(u): int(c) for u, c in zip(unique, counts)
    }

    # NoOp share (action_type_0 == 0)
    noop_count = int(np.count_nonzero(action_type_0 == 0))
    total_actions = int(action_type_0.size)
    diagnostics["noop_share"] = float(noop_count / max(1, total_actions))

    # Check for optional diagnostic arrays
    if "selected_non_noop_count_t" in npz:
        diagnostics["selected_non_noop_total"] = int(
            np.sum(npz["selected_non_noop_count_t"])
        )

    if "source_valid_non_noop_count_t" in npz:
        diagnostics["source_valid_non_noop_total"] = int(
            np.sum(npz["source_valid_non_noop_count_t"])
        )

    if "source_valid_action_count_t" in npz:
        diagnostics["source_valid_total"] = int(
            np.sum(npz["source_valid_action_count_t"])
        )

    # Degeneracy check: all actions are noop across entire rollout
    if diagnostics["noop_share"] >= 0.95:
        diagnostics["is_completely_degenerate"] = True

    npz.close()
    return diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Stage5P1 smoke export NPZ and manifest"
    )
    parser.add_argument("--rollout-dir", type=str, required=True)
    args = parser.parse_args()

    rollout_dir = Path(args.rollout_dir).resolve()
    if not rollout_dir.exists():
        _error(f"Rollout directory does not exist: {rollout_dir}")
        return 1

    npz_path = rollout_dir / "teacher_rollout_raw.npz"
    manifest_path = rollout_dir / "teacher_rollout_manifest.json"

    _info(f"Validating smoke export in: {rollout_dir}")
    print()

    # NPZ Schema
    _info("=== NPZ Schema Validation ===")
    npz_schema_pass, npz_schema_results = validate_npz_schema(npz_path)
    print(f"  Result: {'PASS' if npz_schema_pass else 'FAIL'}")
    if not npz_schema_pass:
        return 1
    print(f"  - observation_t shape: (T, 24, 24, 27) [T={npz_schema_results['total_steps']}]")
    print(f"  - per_cell_action_t shape: (T, 576, 7)")
    print()

    # Action Bounds
    _info("=== Action Branch Bounds Validation ===")
    action_bounds_pass, action_bounds_results = validate_action_bounds(npz_path)
    print(f"  Result: {'PASS' if action_bounds_pass else 'FAIL'}")
    if not action_bounds_pass:
        for err in action_bounds_results["bounds_errors"]:
            print(f"    {err}")
        return 1
    print(f"  - All 7 branches within valid ranges")
    print()

    # Episode Consistency
    _info("=== Episode/Step Consistency Validation ===")
    ep_consistency_pass, ep_consistency_results = validate_episode_consistency(npz_path)
    print(f"  Result: {'PASS' if ep_consistency_pass else 'FAIL'}")
    if not ep_consistency_pass:
        for err in ep_consistency_results["errors"]:
            print(f"    ERROR: {err}")
        return 1
    print(f"  - Episodes: {ep_consistency_results['episode_ids_unique']}")
    print(f"  - Episode lengths: {ep_consistency_results['episode_lengths']}")
    for ep_len in ep_consistency_results["episode_lengths"]:
        if ep_len == 0:
            _error(f"Episode with 0 steps detected")
            return 1
    print()

    # Manifest Schema
    _info("=== Manifest Schema Validation ===")
    manifest_pass, manifest_results = validate_manifest_schema(manifest_path)
    print(f"  Result: {'PASS' if manifest_pass else 'FAIL'}")
    if not manifest_pass:
        for err in manifest_results["schema_errors"]:
            print(f"    {err}")
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    print(f"  - schema_version: {manifest['schema_version']}")
    print(f"  - teacher_lineage: {manifest['teacher_lineage']}")
    print(f"  - step_mode: {manifest['step_mode']}")
    print(f"  - export_mode: {manifest['export_mode']}")
    print()

    # Mask Availability
    _info("=== Mask Availability Validation ===")
    mask_pass, mask_results = validate_mask_availability(npz_path)
    print(f"  Result: {'PASS' if mask_pass else 'FAIL'}")
    print(
        f"  - Mask available share: {mask_results['mask_available_share']:.2%} "
        f"({mask_results['mask_available_count']}/{npz_schema_results['total_steps']})"
    )
    if not mask_results["is_perfect"]:
        _warn(f"Mask availability is not perfect (expected 1.0 for final smoke export)")
    print()

    # Diagnostics
    _info("=== Behavior Diagnostics ===")
    diagnostics = compute_diagnostics(npz_path, manifest)
    print(f"  - Total steps: {diagnostics['total_steps']}")
    print(f"  - Episodes: {diagnostics['episode_count']}")
    print(f"  - Episode returns: {diagnostics['episode_returns']}")
    print(f"  - Episode mean return: {diagnostics['episode_mean_return']:.2f}")
    print(f"  - Terminal count: {diagnostics['terminal_count']}")
    print(f"  - Terminated count: {diagnostics['terminated_count']}")
    print(f"  - Truncated count: {diagnostics['truncated_count']}")
    print(f"  - NoOp share: {diagnostics['noop_share']:.2%}")
    print(f"  - Action type histogram: {diagnostics['action_type_histogram']}")
    if diagnostics["selected_non_noop_total"] > 0:
        print(f"  - Selected non-noop total: {diagnostics['selected_non_noop_total']}")
    if diagnostics["source_valid_non_noop_total"] > 0:
        print(f"  - Source-valid non-noop total: {diagnostics['source_valid_non_noop_total']}")
    if diagnostics["source_valid_total"] > 0:
        print(f"  - Source-valid total: {diagnostics['source_valid_total']}")
    print()

    # Overall decision
    _info("=== Final Decision ===")
    if (
        npz_schema_pass
        and action_bounds_pass
        and ep_consistency_pass
        and manifest_pass
        and mask_pass
    ):
        if diagnostics["is_completely_degenerate"]:
            print("STAGE5P1_SMOKE_EXPORT_FAIL_ACTION_PATH")
            _error("Action distribution is completely degenerate (all NoOp)")
            return 1
        elif not mask_results["is_perfect"]:
            print("STAGE5P1_SMOKE_EXPORT_PASS_WITH_WARNINGS")
            _warn("Mask availability is not perfect")
        else:
            print("STAGE5P1_SMOKE_EXPORT_PASS_READY_FOR_MAIN_EXPORT")
        return 0
    else:
        if not npz_schema_pass:
            print("STAGE5P1_SMOKE_EXPORT_FAIL_SCHEMA")
        elif not manifest_pass:
            print("STAGE5P1_SMOKE_EXPORT_FAIL_CONTRACT")
        elif not action_bounds_pass:
            print("STAGE5P1_SMOKE_EXPORT_FAIL_ACTION_PATH")
        else:
            print("STAGE5P1_SMOKE_EXPORT_FAIL_SCHEMA")
        return 1


if __name__ == "__main__":
    exit(main())
