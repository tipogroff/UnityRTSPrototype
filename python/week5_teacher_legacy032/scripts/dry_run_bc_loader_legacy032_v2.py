#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np


EXPECTED_OBS_SHAPE = (576, 27)
EXPECTED_ACTION_SHAPE = (576, 7)
EXPECTED_BRANCH_SIZES = (6, 4, 4, 4, 4, 7, 49)
EXPECTED_TARGET_ACTION_CONTRACT = "unity_v2_legacy032_gridnet"


class DryRunError(RuntimeError):
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_path(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (_repo_root() / p).resolve()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_bool(value: str) -> bool:
    v = str(value).strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def _json_dump(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise DryRunError(f"Failed to parse JSON {path}: {exc}") from exc


def _require(
    condition: bool,
    message: str,
    fail_on_contract_mismatch: bool,
    hard_failures: List[str],
) -> bool:
    if condition:
        return True
    hard_failures.append(message)
    if fail_on_contract_mismatch:
        raise DryRunError(message)
    return False


def _validate_split(name: str, arrays: Dict[str, np.ndarray], hard_failures: List[str], fail_on_contract_mismatch: bool) -> Dict[str, Any]:
    obs = arrays["observations"]
    act = arrays["actions"]
    n = int(obs.shape[0])

    _require(obs.ndim == 3 and tuple(obs.shape[1:]) == EXPECTED_OBS_SHAPE, f"{name} observations shape mismatch: {list(obs.shape)}", fail_on_contract_mismatch, hard_failures)
    _require(act.ndim == 3 and tuple(act.shape[1:]) == EXPECTED_ACTION_SHAPE, f"{name} actions shape mismatch: {list(act.shape)}", fail_on_contract_mismatch, hard_failures)
    _require(n > 0, f"{name} split has zero samples", fail_on_contract_mismatch, hard_failures)
    _require(int(act.shape[0]) == n, f"{name} obs/action sample mismatch", fail_on_contract_mismatch, hard_failures)
    _require(obs.dtype == np.float32, f"{name} observations dtype must be float32, got {obs.dtype}", fail_on_contract_mismatch, hard_failures)
    _require(act.dtype.kind in {"i", "u"}, f"{name} actions dtype must be integer, got {act.dtype}", fail_on_contract_mismatch, hard_failures)

    has_nan = bool(np.isnan(obs).any())
    has_inf = bool(np.isinf(obs).any())
    _require(not has_nan and not has_inf, f"{name} observations contain NaN/Inf", fail_on_contract_mismatch, hard_failures)

    branch_min_max: List[Dict[str, Any]] = []
    for i, size in enumerate(EXPECTED_BRANCH_SIZES):
        col = act[:, :, i]
        min_v, max_v = int(col.min()), int(col.max())
        in_bounds = bool(min_v >= 0 and max_v < int(size))
        branch_min_max.append({"branch": i, "size": int(size), "min": min_v, "max": max_v, "in_bounds": in_bounds})
        _require(in_bounds, f"{name} branch {i} out of bounds: min={min_v}, max={max_v}, size={size}", fail_on_contract_mismatch, hard_failures)

    return {
        "sample_count": n,
        "observations_shape": list(obs.shape),
        "actions_shape": list(act.shape),
        "observations_dtype": str(obs.dtype),
        "actions_dtype": str(act.dtype),
        "observation_min": float(np.min(obs)) if obs.size else None,
        "observation_max": float(np.max(obs)) if obs.size else None,
        "branch_min_max": branch_min_max,
    }


def _build_md(report: Dict[str, Any]) -> str:
    lines = [
        "# LEGACY032 BC-Ready Dry-Run Loader Report",
        "",
        "## Summary",
        "",
        f"- status: {report['status']}",
        f"- bc_ready_dir: {report['bc_ready_dir']}",
        f"- batch_size_requested: {report['batch_size_requested']}",
        f"- batch_size_train_actual: {report['batch_size_train_actual']}",
        f"- batch_size_validation_actual: {report['batch_size_validation_actual']}",
        "",
        "## Manifest Checks",
        "",
    ]
    for k, v in report["manifest_checks"].items():
        lines.append(f"- {k}: pass={v['pass']}, expected={v['expected']}, actual={v['actual']}")

    lines += [
        "",
        "## Train Split Checks",
        "",
        f"- sample_count: {report['train_checks']['sample_count']}",
        f"- observations_shape: {report['train_checks']['observations_shape']}",
        f"- actions_shape: {report['train_checks']['actions_shape']}",
        f"- observations_dtype: {report['train_checks']['observations_dtype']}",
        f"- actions_dtype: {report['train_checks']['actions_dtype']}",
        f"- observation_min: {report['train_checks']['observation_min']}",
        f"- observation_max: {report['train_checks']['observation_max']}",
        "",
        "## Validation Split Checks",
        "",
        f"- sample_count: {report['validation_checks']['sample_count']}",
        f"- observations_shape: {report['validation_checks']['observations_shape']}",
        f"- actions_shape: {report['validation_checks']['actions_shape']}",
        f"- observations_dtype: {report['validation_checks']['observations_dtype']}",
        f"- actions_dtype: {report['validation_checks']['actions_dtype']}",
        f"- observation_min: {report['validation_checks']['observation_min']}",
        f"- observation_max: {report['validation_checks']['observation_max']}",
        "",
        "## Hard Failures",
        "",
    ]

    if report["hard_failures"]:
        for h in report["hard_failures"]:
            lines.append(f"- {h}")
    else:
        lines.append("- none")

    lines += [
        "",
        "## Scope and Limitations",
        "",
        "- dry-run proves dataset/loader technical compatibility only;",
        "- dry-run does not prove behavior quality;",
        "- dry-run does not prove Unity semantic parity;",
        "- dry-run does not imply direct weight transfer.",
    ]

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Dry-run loader for BC-ready Legacy032 Unity v2 dataset.")
    p.add_argument("--bc-ready-dir", required=True)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--fail-on-contract-mismatch", type=_parse_bool, default=True)
    p.add_argument("--write-report", type=_parse_bool, default=True)
    p.add_argument("--output-dir", required=True)
    return p.parse_args()


def main() -> int:
    args = parse_args()

    bc_ready_dir = _resolve_path(args.bc_ready_dir)
    output_dir = _resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = bc_ready_dir / "bc_manifest.json"
    train_path = bc_ready_dir / "bc_train.npz"
    val_path = bc_ready_dir / "bc_validation.npz"

    json_report_path = output_dir / "LEGACY032_BC_READY_DRY_RUN_REPORT.json"
    md_report_path = output_dir / "LEGACY032_BC_READY_DRY_RUN_REPORT.md"

    hard_failures: List[str] = []

    _require(manifest_path.exists(), f"missing file: {manifest_path}", bool(args.fail_on_contract_mismatch), hard_failures)
    _require(train_path.exists(), f"missing file: {train_path}", bool(args.fail_on_contract_mismatch), hard_failures)
    _require(val_path.exists(), f"missing file: {val_path}", bool(args.fail_on_contract_mismatch), hard_failures)

    manifest = _load_json(manifest_path)

    manifest_checks: Dict[str, Dict[str, Any]] = {}

    def check_manifest(name: str, expected: Any, actual: Any, ok: bool) -> None:
        manifest_checks[name] = {"pass": bool(ok), "expected": expected, "actual": actual}
        if not ok:
            hard_failures.append(f"manifest check failed: {name}")
            if bool(args.fail_on_contract_mismatch):
                raise DryRunError(f"manifest check failed: {name}")

    check_manifest("target_action_contract", EXPECTED_TARGET_ACTION_CONTRACT, manifest.get("target_action_contract"), manifest.get("target_action_contract") == EXPECTED_TARGET_ACTION_CONTRACT)
    check_manifest("observation_shape_per_sample", list(EXPECTED_OBS_SHAPE), manifest.get("observation_shape_per_sample"), list(manifest.get("observation_shape_per_sample", [])) == list(EXPECTED_OBS_SHAPE))
    check_manifest("action_shape_per_sample", list(EXPECTED_ACTION_SHAPE), manifest.get("action_shape_per_sample"), list(manifest.get("action_shape_per_sample", [])) == list(EXPECTED_ACTION_SHAPE))
    check_manifest("branch_sizes", list(EXPECTED_BRANCH_SIZES), manifest.get("branch_sizes"), list(manifest.get("branch_sizes", [])) == list(EXPECTED_BRANCH_SIZES))
    check_manifest("direct_weight_transfer_claim", False, manifest.get("direct_weight_transfer_claim"), manifest.get("direct_weight_transfer_claim") is False)
    check_manifest("semantic_parity_claim", False, manifest.get("semantic_parity_claim"), manifest.get("semantic_parity_claim") is False)

    train_npz = np.load(str(train_path), allow_pickle=True)
    val_npz = np.load(str(val_path), allow_pickle=True)

    required_arrays = [
        "observations",
        "actions",
        "episode_id",
        "step_id",
        "reward_t",
        "done_t",
        "terminated_t",
        "truncated_t",
        "action_mask_available_t",
    ]
    for split_name, npz in [("train", train_npz), ("validation", val_npz)]:
        for k in required_arrays:
            _require(k in npz, f"{split_name} missing array: {k}", bool(args.fail_on_contract_mismatch), hard_failures)

    train_arrays = {k: np.asarray(train_npz[k]) for k in required_arrays}
    val_arrays = {k: np.asarray(val_npz[k]) for k in required_arrays}

    train_checks = _validate_split("train", train_arrays, hard_failures, bool(args.fail_on_contract_mismatch))
    val_checks = _validate_split("validation", val_arrays, hard_failures, bool(args.fail_on_contract_mismatch))

    b = int(args.batch_size)
    _require(b > 0, f"batch-size must be > 0, got {b}", bool(args.fail_on_contract_mismatch), hard_failures)

    b_train = min(b, int(train_arrays["observations"].shape[0]))
    b_val = min(b, int(val_arrays["observations"].shape[0]))

    batch_train_obs = train_arrays["observations"][:b_train]
    batch_train_act = train_arrays["actions"][:b_train]
    batch_val_obs = val_arrays["observations"][:b_val]
    batch_val_act = val_arrays["actions"][:b_val]

    _require(tuple(batch_train_obs.shape) == (b_train, 576, 27), "train batch observations shape mismatch", bool(args.fail_on_contract_mismatch), hard_failures)
    _require(tuple(batch_train_act.shape) == (b_train, 576, 7), "train batch actions shape mismatch", bool(args.fail_on_contract_mismatch), hard_failures)
    _require(tuple(batch_val_obs.shape) == (b_val, 576, 27), "validation batch observations shape mismatch", bool(args.fail_on_contract_mismatch), hard_failures)
    _require(tuple(batch_val_act.shape) == (b_val, 576, 7), "validation batch actions shape mismatch", bool(args.fail_on_contract_mismatch), hard_failures)

    status = "pass" if not hard_failures else "fail"

    report = {
        "generated_at_utc": _now_iso(),
        "status": status,
        "bc_ready_dir": str(bc_ready_dir),
        "batch_size_requested": int(b),
        "batch_size_train_actual": int(b_train),
        "batch_size_validation_actual": int(b_val),
        "manifest_checks": manifest_checks,
        "train_checks": train_checks,
        "validation_checks": val_checks,
        "batch_shapes": {
            "train_observations": list(batch_train_obs.shape),
            "train_actions": list(batch_train_act.shape),
            "validation_observations": list(batch_val_obs.shape),
            "validation_actions": list(batch_val_act.shape),
        },
        "hard_failures": hard_failures,
        "scope_notes": {
            "technical_compatibility_only": True,
            "proves_behavior_quality": False,
            "proves_unity_semantic_parity": False,
            "implies_direct_weight_transfer": False,
        },
    }

    if bool(args.write_report):
        _json_dump(json_report_path, report)
        md_report_path.write_text(_build_md(report), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": status,
                "json_report": str(json_report_path) if bool(args.write_report) else None,
                "markdown_report": str(md_report_path) if bool(args.write_report) else None,
                "hard_failures_count": len(hard_failures),
            },
            ensure_ascii=True,
            indent=2,
        )
    )

    return 0 if status == "pass" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        traceback.print_exc()
        raise SystemExit(f"[dry_run_bc_loader_legacy032_v2] ERROR: {exc}")
