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
EXPECTED_ACTION_CONTRACT = "unity_v2_legacy032_gridnet"
EXPECTED_MAPPING_SPEC_VERSION = "stage10d6_v1"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_stamp() -> str:
    return _utc_now().strftime("%Y%m%dT%H%M%SZ")


def _iso_now() -> str:
    return _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_dump(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _require(condition: bool, message: str, failures: List[str]) -> None:
    if not condition:
        failures.append(message)


def _validate_adapted(
    observations: np.ndarray,
    actions: np.ndarray,
    manifest: Dict[str, Any],
) -> Tuple[List[str], Dict[str, Any]]:
    failures: List[str] = []
    checks: Dict[str, Any] = {
        "shape_expected_[N,576,27]": bool(observations.ndim == 3 and tuple(observations.shape[1:]) == EXPECTED_OBS_SHAPE),
        "action_shape_expected_[N,576,7]": bool(actions.ndim == 3 and tuple(actions.shape[1:]) == EXPECTED_ACTION_SHAPE),
        "observations_dtype_float32": bool(observations.dtype == np.float32),
        "actions_integer_compatible": bool(np.issubdtype(actions.dtype, np.integer)),
        "no_nan": bool(not np.isnan(observations).any()),
        "no_inf": bool(not np.isinf(observations).any()),
        "obs_range_0_1": bool(np.all(observations >= 0.0) and np.all(observations <= 1.0)),
        "observation_semantics_version_match": bool(manifest.get("observation_semantics_version") == EXPECTED_OBS_SEMVER),
    }

    for key, passed in checks.items():
        _require(bool(passed), f"adapted_contract_failed: {key}", failures)

    if actions.ndim == 3 and actions.shape[-1] == len(EXPECTED_BRANCH_SIZES):
        actions_i64 = np.asarray(actions, dtype=np.int64)
        for branch_idx, branch_size in enumerate(EXPECTED_BRANCH_SIZES):
            branch_max = int(actions_i64[:, :, branch_idx].max())
            branch_min = int(actions_i64[:, :, branch_idx].min())
            _require(
                branch_min >= 0 and branch_max < branch_size,
                f"action_bounds_failed: branch_{branch_idx} min={branch_min} max={branch_max} expected<[0,{branch_size})",
                failures,
            )

    return failures, checks


def _build_split_npz(
    path: Path,
    observations: np.ndarray,
    actions: np.ndarray,
    episode_id: np.ndarray,
    step_id: np.ndarray,
    reward_t: np.ndarray,
    done_t: np.ndarray,
    terminated_t: np.ndarray,
    truncated_t: np.ndarray,
    action_mask_available_t: np.ndarray,
) -> None:
    np.savez_compressed(
        path,
        observations=np.asarray(observations, dtype=np.float32),
        actions=np.asarray(actions, dtype=np.int16),
        episode_id=np.asarray(episode_id, dtype=np.int32),
        step_id=np.asarray(step_id, dtype=np.int32),
        reward_t=np.asarray(reward_t, dtype=np.float32),
        done_t=np.asarray(done_t, dtype=np.bool_),
        terminated_t=np.asarray(terminated_t, dtype=np.bool_),
        truncated_t=np.asarray(truncated_t, dtype=np.bool_),
        action_mask_available_t=np.asarray(action_mask_available_t, dtype=np.bool_),
    )


def _markdown_report(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Stage10D.7 Semantic BC-ready Build Report")
    lines.append("")
    lines.append(f"- status: {report['status']}")
    lines.append(f"- output_dir: {report['output_dir']}")
    lines.append(f"- source_adapted_dir: {report['source_adapted_dir']}")
    lines.append(f"- sample_count: {report['sample_count']}")
    lines.append("")
    lines.append("## Split")
    lines.append(f"- seed: {report['split']['seed']}")
    lines.append(f"- train_ratio: {report['split']['train_ratio']}")
    lines.append(f"- train_count: {report['split']['train_count']}")
    lines.append(f"- validation_count: {report['split']['validation_count']}")
    lines.append(f"- debug_count: {report['split']['debug_count']}")
    lines.append("")
    lines.append("## Contract Checks")
    for k, v in report["contract_checks"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Files")
    for k, v in report["artifacts"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Hard Failures")
    if report["hard_failures"]:
        for item in report["hard_failures"]:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Explicit Non-Claims")
    for item in report["explicit_non_claims"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage10D.7 semantic BC-ready dataset builder")
    parser.add_argument("--adapted-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--run-label", type=str, required=True)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--train-ratio", type=float, default=0.90)
    parser.add_argument("--debug-max", type=int, default=1024)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = _repo_root()
    adapted_dir = _resolve(root, args.adapted_dir).resolve()
    output_root = _resolve(root, args.output_root).resolve()
    run_dir = output_root / f"{args.run_label}_{_utc_stamp()}"

    adapted_npz = adapted_dir / "adapted_dataset.npz"
    adapted_manifest_path = adapted_dir / "adapted_manifest.json"
    semantic_report_json = adapted_dir / "observation_semantic_conversion_report.json"
    semantic_report_md = adapted_dir / "observation_semantic_conversion_report.md"

    run_dir.mkdir(parents=True, exist_ok=False)

    if not adapted_npz.exists():
        raise RuntimeError(f"missing adapted dataset: {adapted_npz}")
    if not adapted_manifest_path.exists():
        raise RuntimeError(f"missing adapted manifest: {adapted_manifest_path}")

    adapted_manifest = _read_json(adapted_manifest_path)

    with np.load(adapted_npz, allow_pickle=False) as npz:
        observations = np.asarray(npz["observations"], dtype=np.float32)
        actions = np.asarray(npz["actions"])
        episode_id = np.asarray(npz["episode_id"], dtype=np.int32)
        step_id = np.asarray(npz["step_id"], dtype=np.int32)
        reward_t = np.asarray(npz["reward_t"], dtype=np.float32)
        done_t = np.asarray(npz["done_t"], dtype=np.bool_)
        terminated_t = np.asarray(npz["terminated_t"], dtype=np.bool_)
        truncated_t = np.asarray(npz["truncated_t"], dtype=np.bool_)
        action_mask_available_t = np.asarray(npz["action_mask_available_t"], dtype=np.bool_)

    hard_failures, contract_checks = _validate_adapted(observations=observations, actions=actions, manifest=adapted_manifest)
    if hard_failures:
        report = {
            "stage": "10D.7",
            "task": "semantic_bc_ready_build",
            "status": "fail",
            "generated_at_utc": _iso_now(),
            "output_dir": run_dir.as_posix(),
            "source_adapted_dir": adapted_dir.as_posix(),
            "sample_count": int(observations.shape[0]),
            "split": {
                "seed": int(args.seed),
                "train_ratio": float(args.train_ratio),
                "train_count": 0,
                "validation_count": 0,
                "debug_count": 0,
            },
            "contract_checks": contract_checks,
            "artifacts": {},
            "hard_failures": hard_failures,
            "explicit_non_claims": [
                "No retraining performed.",
                "No PPO performed.",
                "No checkpoint mutation.",
                "No overwrite of old raw/adapted/BC-ready datasets.",
                "Semantic observation compatibility does not prove policy-level behavior.",
            ],
        }
        _json_dump(run_dir / "stage10d7_bc_ready_build_report.json", report)
        (run_dir / "stage10d7_bc_ready_build_report.md").write_text(_markdown_report(report), encoding="utf-8")
        return 1

    num_samples = int(observations.shape[0])
    rng = np.random.default_rng(int(args.seed))
    permutation = rng.permutation(num_samples)
    train_count = int(num_samples * float(args.train_ratio))
    train_indices = permutation[:train_count]
    validation_indices = permutation[train_count:]
    debug_count = int(min(int(args.debug_max), int(validation_indices.shape[0])))
    debug_indices = validation_indices[:debug_count]

    _build_split_npz(
        run_dir / "bc_train.npz",
        observations[train_indices],
        actions[train_indices],
        episode_id[train_indices],
        step_id[train_indices],
        reward_t[train_indices],
        done_t[train_indices],
        terminated_t[train_indices],
        truncated_t[train_indices],
        action_mask_available_t[train_indices],
    )
    _build_split_npz(
        run_dir / "bc_validation.npz",
        observations[validation_indices],
        actions[validation_indices],
        episode_id[validation_indices],
        step_id[validation_indices],
        reward_t[validation_indices],
        done_t[validation_indices],
        terminated_t[validation_indices],
        truncated_t[validation_indices],
        action_mask_available_t[validation_indices],
    )
    _build_split_npz(
        run_dir / "bc_debug.npz",
        observations[debug_indices],
        actions[debug_indices],
        episode_id[debug_indices],
        step_id[debug_indices],
        reward_t[debug_indices],
        done_t[debug_indices],
        terminated_t[debug_indices],
        truncated_t[debug_indices],
        action_mask_available_t[debug_indices],
    )

    manifest: Dict[str, Any] = {
        "generated_at_utc": _iso_now(),
        "schema_version": "day6.bc_ready.v1",
        "dataset_kind": "semantic_bc_ready",
        "source_stage": "10D.7",
        "source_adapted_dataset_stage": "10D.6",
        "source_teacher": "legacy032_3m",
        "source_adapted_dir": adapted_dir.as_posix(),
        "source_adapted_manifest": adapted_manifest_path.as_posix(),
        "source_observation_semantic_conversion_report_json": semantic_report_json.as_posix() if semantic_report_json.exists() else None,
        "source_observation_semantic_conversion_report_md": semantic_report_md.as_posix() if semantic_report_md.exists() else None,
        "mapping_spec_version": EXPECTED_MAPPING_SPEC_VERSION,
        "observation_semantics_version": EXPECTED_OBS_SEMVER,
        "target_action_contract": EXPECTED_ACTION_CONTRACT,
        "observation_shape": list(EXPECTED_OBS_SHAPE),
        "action_shape": list(EXPECTED_ACTION_SHAPE),
        "observation_shape_per_sample": list(EXPECTED_OBS_SHAPE),
        "action_shape_per_sample": list(EXPECTED_ACTION_SHAPE),
        "branch_sizes": list(EXPECTED_BRANCH_SIZES),
        "num_train": int(train_indices.shape[0]),
        "num_validation": int(validation_indices.shape[0]),
        "num_debug": int(debug_indices.shape[0]),
        "dtype": {
            "observations": "float32",
            "actions": "int16",
        },
        "checks": {
            "no_nan": True,
            "no_inf": True,
            "observation_value_range": [0.0, 1.0],
        },
        "split": {
            "seed": int(args.seed),
            "train_ratio": float(args.train_ratio),
            "train_count": int(train_indices.shape[0]),
            "validation_count": int(validation_indices.shape[0]),
            "debug_count": int(debug_indices.shape[0]),
        },
        "direct_weight_transfer_claim": False,
        "semantic_parity_claim": False,
        "explicit_non_claims": [
            "no retraining performed",
            "no PPO performed",
            "no checkpoint mutation",
            "semantic observation compatibility does not prove policy-level behavior",
        ],
        "notes": "Stage10D.7 semantic BC-ready packaging only. No training performed.",
    }

    _json_dump(run_dir / "bc_manifest.json", manifest)

    summary: Dict[str, Any] = {
        "generated_at_utc": _iso_now(),
        "dataset_kind": "semantic_bc_ready",
        "source_stage": "10D.7",
        "source_adapted_dataset_stage": "10D.6",
        "source_adapted_dir": adapted_dir.as_posix(),
        "sample_count": num_samples,
        "num_train": int(train_indices.shape[0]),
        "num_validation": int(validation_indices.shape[0]),
        "num_debug": int(debug_indices.shape[0]),
        "observation_shape_per_sample": list(EXPECTED_OBS_SHAPE),
        "action_shape_per_sample": list(EXPECTED_ACTION_SHAPE),
        "branch_sizes": list(EXPECTED_BRANCH_SIZES),
        "observation_semantics_version": EXPECTED_OBS_SEMVER,
        "mapping_spec_version": EXPECTED_MAPPING_SPEC_VERSION,
        "target_action_contract": EXPECTED_ACTION_CONTRACT,
        "explicit_non_claims": manifest["explicit_non_claims"],
    }
    _json_dump(run_dir / "bc_summary.json", summary)

    build_report: Dict[str, Any] = {
        "stage": "10D.7",
        "task": "semantic_bc_ready_build",
        "status": "pass",
        "generated_at_utc": _iso_now(),
        "output_dir": run_dir.as_posix(),
        "source_adapted_dir": adapted_dir.as_posix(),
        "sample_count": num_samples,
        "split": {
            "seed": int(args.seed),
            "train_ratio": float(args.train_ratio),
            "train_count": int(train_indices.shape[0]),
            "validation_count": int(validation_indices.shape[0]),
            "debug_count": int(debug_indices.shape[0]),
        },
        "contract_checks": contract_checks,
        "artifacts": {
            "bc_train": (run_dir / "bc_train.npz").as_posix(),
            "bc_validation": (run_dir / "bc_validation.npz").as_posix(),
            "bc_debug": (run_dir / "bc_debug.npz").as_posix(),
            "bc_manifest": (run_dir / "bc_manifest.json").as_posix(),
            "bc_summary": (run_dir / "bc_summary.json").as_posix(),
            "stage10d7_bc_ready_build_report_json": (run_dir / "stage10d7_bc_ready_build_report.json").as_posix(),
            "stage10d7_bc_ready_build_report_md": (run_dir / "stage10d7_bc_ready_build_report.md").as_posix(),
        },
        "hard_failures": [],
        "explicit_non_claims": manifest["explicit_non_claims"],
    }
    _json_dump(run_dir / "stage10d7_bc_ready_build_report.json", build_report)
    (run_dir / "stage10d7_bc_ready_build_report.md").write_text(_markdown_report(build_report), encoding="utf-8")

    print(run_dir.as_posix())
    print((run_dir / "stage10d7_bc_ready_build_report.json").as_posix())
    print((run_dir / "stage10d7_bc_ready_build_report.md").as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
