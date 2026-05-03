#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np


EXPECTED_OBS_SHAPE: Tuple[int, int] = (576, 27)
EXPECTED_ACTION_SHAPE: Tuple[int, int] = (576, 7)
EXPECTED_BRANCH_SIZES: Tuple[int, ...] = (6, 4, 4, 4, 4, 7, 49)
EXPECTED_OBS_SEMVER = "unity_v2_runtime_stage10d6"
EXPECTED_MAPPING_SPEC_VERSION = "stage10d6_v1"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_dump(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _require(condition: bool, message: str, hard_failures: List[str]) -> None:
    if not condition:
        hard_failures.append(message)


def _load_split(path: Path) -> Dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as npz:
        return {k: np.asarray(npz[k]) for k in npz.files}


def _get_obs_actions(split: Dict[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    if "observations" in split:
        observations = np.asarray(split["observations"])
    elif "input_tensor" in split:
        observations = np.asarray(split["input_tensor"])
    else:
        raise RuntimeError("missing observations/input_tensor")

    if "actions" in split:
        actions = np.asarray(split["actions"])
    elif "target_action_branches" in split:
        actions = np.asarray(split["target_action_branches"])
    else:
        raise RuntimeError("missing actions/target_action_branches")
    return observations, actions


def _group_metrics(obs: np.ndarray, start: int, end: int) -> Dict[str, Any]:
    g = obs[:, :, start:end]
    sums = np.sum(g, axis=2)
    return {
        "sum_min": float(np.min(sums)),
        "sum_max": float(np.max(sums)),
        "share_sum_eq_1": float(np.mean(np.isclose(sums, 1.0))),
        "share_sum_eq_0": float(np.mean(np.isclose(sums, 0.0))),
        "share_sum_le_1": float(np.mean(sums <= 1.0 + 1e-6)),
        "binary_values_only": bool(np.all((g == 0.0) | (g == 1.0))),
    }


def _md(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Stage10D.7 Semantic BC-ready Validation")
    lines.append("")
    lines.append(f"- status: {report['status']}")
    lines.append(f"- bc_ready_dir: {report['bc_ready_dir']}")
    lines.append("")
    lines.append("## File Checks")
    for k, v in report["file_checks"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Contract Checks")
    for k, v in report["contract_checks"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Semantic Compatibility")
    for k, v in report["semantic_compatibility"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Hard Failures")
    if report["hard_failures"]:
        for item in report["hard_failures"]:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate Stage10D.7 semantic BC-ready dataset")
    p.add_argument("--bc-ready-dir", type=Path, required=True)
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d7_semantic_bc_ready_validation.json"),
    )
    p.add_argument(
        "--output-md",
        type=Path,
        default=Path("python/week6_student/reports/stage10d7_semantic_bc_ready_validation.md"),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = _repo_root()
    bc_ready_dir = _resolve(root, args.bc_ready_dir).resolve()
    output_json = _resolve(root, args.output_json)
    output_md = _resolve(root, args.output_md)

    hard_failures: List[str] = []
    manifest_path = bc_ready_dir / "bc_manifest.json"
    train_path = bc_ready_dir / "bc_train.npz"
    val_path = bc_ready_dir / "bc_validation.npz"
    debug_path = bc_ready_dir / "bc_debug.npz"

    file_checks = {
        "bc_ready_dir_exists": bool(bc_ready_dir.exists() and bc_ready_dir.is_dir()),
        "bc_manifest_exists": bool(manifest_path.exists()),
        "bc_train_exists": bool(train_path.exists()),
        "bc_validation_exists": bool(val_path.exists()),
        "bc_debug_exists": bool(debug_path.exists()),
    }
    for k, v in file_checks.items():
        _require(v, f"file_check_failed: {k}", hard_failures)

    manifest: Dict[str, Any] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if hard_failures:
        report = {
            "stage": "10D.7",
            "diagnostic": "semantic_bc_ready_validation",
            "generated_at_utc": _iso_now(),
            "bc_ready_dir": bc_ready_dir.as_posix(),
            "status": "fail",
            "file_checks": file_checks,
            "contract_checks": {},
            "semantic_compatibility": {},
            "hard_failures": hard_failures,
        }
        _json_dump(output_json, report)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(_md(report), encoding="utf-8")
        print(output_json.as_posix())
        print(output_md.as_posix())
        return 1

    train_split = _load_split(train_path)
    val_split = _load_split(val_path)
    debug_split = _load_split(debug_path)

    for split_name, split in (("train", train_split), ("validation", val_split), ("debug", debug_split)):
        key_ok = (
            ("observations" in split and "actions" in split)
            or ("input_tensor" in split and "target_action_branches" in split)
        )
        _require(key_ok, f"required_keys_missing_for_loader: split={split_name}", hard_failures)

    train_obs, train_actions = _get_obs_actions(train_split)
    val_obs, val_actions = _get_obs_actions(val_split)
    debug_obs, debug_actions = _get_obs_actions(debug_split)

    def _shape_ok(obs: np.ndarray, act: np.ndarray) -> bool:
        return bool(
            obs.ndim == 3
            and act.ndim == 3
            and tuple(obs.shape[1:]) == EXPECTED_OBS_SHAPE
            and tuple(act.shape[1:]) == EXPECTED_ACTION_SHAPE
            and obs.shape[0] == act.shape[0]
        )

    contract_checks: Dict[str, Any] = {
        "schema_version_day6_bc_ready_v1": manifest.get("schema_version") == "day6.bc_ready.v1",
        "manifest_dataset_kind_semantic_bc_ready": manifest.get("dataset_kind") == "semantic_bc_ready",
        "manifest_source_stage_10D7": manifest.get("source_stage") == "10D.7",
        "manifest_source_adapted_dataset_stage_10D6": manifest.get("source_adapted_dataset_stage") == "10D.6",
        "manifest_observation_semantics_version": manifest.get("observation_semantics_version") == EXPECTED_OBS_SEMVER,
        "manifest_mapping_spec_version": manifest.get("mapping_spec_version") == EXPECTED_MAPPING_SPEC_VERSION,
        "manifest_observation_shape": list(manifest.get("observation_shape", [])) == list(EXPECTED_OBS_SHAPE),
        "manifest_action_shape": list(manifest.get("action_shape", [])) == list(EXPECTED_ACTION_SHAPE),
        "manifest_branch_sizes": list(manifest.get("branch_sizes", [])) == list(EXPECTED_BRANCH_SIZES),
        "train_shape": _shape_ok(train_obs, train_actions),
        "validation_shape": _shape_ok(val_obs, val_actions),
        "debug_shape": _shape_ok(debug_obs, debug_actions),
        "obs_dtype_float32_train": train_obs.dtype == np.float32,
        "obs_dtype_float32_validation": val_obs.dtype == np.float32,
        "obs_dtype_float32_debug": debug_obs.dtype == np.float32,
        "actions_integer_compatible_train": bool(np.issubdtype(train_actions.dtype, np.integer)),
        "actions_integer_compatible_validation": bool(np.issubdtype(val_actions.dtype, np.integer)),
        "actions_integer_compatible_debug": bool(np.issubdtype(debug_actions.dtype, np.integer)),
        "obs_no_nan": bool(not np.isnan(train_obs).any() and not np.isnan(val_obs).any() and not np.isnan(debug_obs).any()),
        "obs_no_inf": bool(not np.isinf(train_obs).any() and not np.isinf(val_obs).any() and not np.isinf(debug_obs).any()),
        "obs_range_0_1": bool(
            np.all(train_obs >= 0.0)
            and np.all(train_obs <= 1.0)
            and np.all(val_obs >= 0.0)
            and np.all(val_obs <= 1.0)
            and np.all(debug_obs >= 0.0)
            and np.all(debug_obs <= 1.0)
        ),
        "manifest_count_train_match": int(manifest.get("num_train", -1)) == int(train_obs.shape[0]),
        "manifest_count_validation_match": int(manifest.get("num_validation", -1)) == int(val_obs.shape[0]),
        "manifest_count_debug_match": int(manifest.get("num_debug", -1)) == int(debug_obs.shape[0]),
    }

    all_actions = np.concatenate([train_actions, val_actions, debug_actions], axis=0).astype(np.int64, copy=False)
    for branch_idx, branch_size in enumerate(EXPECTED_BRANCH_SIZES):
        b = all_actions[:, :, branch_idx]
        contract_checks[f"branch_{branch_idx}_range"] = bool(int(b.min()) >= 0 and int(b.max()) < int(branch_size))

    for k, v in contract_checks.items():
        _require(bool(v), f"contract_check_failed: {k}", hard_failures)

    all_obs = np.concatenate([train_obs, val_obs, debug_obs], axis=0)
    owner_metrics = _group_metrics(all_obs, 2, 5)
    unit_type_metrics = _group_metrics(all_obs, 5, 12)

    resource_and_ranged_both = np.logical_and(np.isclose(all_obs[:, :, 5], 1.0), np.isclose(all_obs[:, :, 11], 1.0))
    impossible_multi_hot_share = float(np.mean(resource_and_ranged_both))

    action_type = all_actions[:, :, 0]
    worker_mask = action_type == 2
    base_mask = action_type == 4

    unit_slice = all_obs[:, :, 5:12]
    if np.any(worker_mask):
        worker_mean = np.mean(unit_slice[worker_mask], axis=0)
    else:
        worker_mean = np.zeros((7,), dtype=np.float32)
    if np.any(base_mask):
        base_mean = np.mean(unit_slice[base_mask], axis=0)
    else:
        base_mean = np.zeros((7,), dtype=np.float32)

    worker_compatible = bool(np.argmax(worker_mean) == 3 and worker_mean[3] >= 0.5)
    base_compatible = bool(np.argmax(base_mean) == 1 and base_mean[1] >= 0.5)

    semantic_compatibility: Dict[str, Any] = {
        "owner_group_channels_2_4_one_hot_valid": bool(
            owner_metrics["share_sum_eq_1"] == 1.0
            and owner_metrics["share_sum_le_1"] == 1.0
            and owner_metrics["binary_values_only"]
        ),
        "unit_type_group_channels_5_11_one_hot_or_zero": bool(
            unit_type_metrics["share_sum_le_1"] == 1.0 and unit_type_metrics["binary_values_only"]
        ),
        "worker_harvest_proxy_compatible": worker_compatible,
        "base_produce_proxy_compatible": base_compatible,
        "resource_plus_ranged_impossible_multi_hot_share": impossible_multi_hot_share,
        "resource_plus_ranged_impossible_multi_hot_share_eq_0": bool(np.isclose(impossible_multi_hot_share, 0.0)),
        "worker_harvest_proxy_unit_type_mean": [float(x) for x in worker_mean.tolist()],
        "base_produce_proxy_unit_type_mean": [float(x) for x in base_mean.tolist()],
    }

    _require(
        bool(semantic_compatibility["owner_group_channels_2_4_one_hot_valid"]),
        "semantic_check_failed: owner_group_channels_2_4_one_hot_valid",
        hard_failures,
    )
    _require(
        bool(semantic_compatibility["unit_type_group_channels_5_11_one_hot_or_zero"]),
        "semantic_check_failed: unit_type_group_channels_5_11_one_hot_or_zero",
        hard_failures,
    )
    _require(
        bool(semantic_compatibility["worker_harvest_proxy_compatible"]),
        "semantic_check_failed: worker_harvest_proxy_compatible",
        hard_failures,
    )
    _require(
        bool(semantic_compatibility["base_produce_proxy_compatible"]),
        "semantic_check_failed: base_produce_proxy_compatible",
        hard_failures,
    )
    _require(
        bool(semantic_compatibility["resource_plus_ranged_impossible_multi_hot_share_eq_0"]),
        "semantic_check_failed: resource_plus_ranged_impossible_multi_hot_share_eq_0",
        hard_failures,
    )

    report = {
        "stage": "10D.7",
        "diagnostic": "semantic_bc_ready_validation",
        "generated_at_utc": _iso_now(),
        "bc_ready_dir": bc_ready_dir.as_posix(),
        "status": "pass" if not hard_failures else "fail",
        "file_checks": file_checks,
        "contract_checks": contract_checks,
        "semantic_compatibility": semantic_compatibility,
        "hard_failures": hard_failures,
    }

    _json_dump(output_json, report)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(_md(report), encoding="utf-8")

    print(output_json.as_posix())
    print(output_md.as_posix())
    return 0 if not hard_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
