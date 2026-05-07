#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np


EXPECTED_OBS_SHAPE = (576, 27)
EXPECTED_ACTION_SHAPE = (576, 7)
EXPECTED_BRANCH_SIZES = (6, 4, 4, 4, 4, 7, 49)
EXPECTED_TARGET_ACTION_CONTRACT = "unity_v2_legacy032_gridnet"
EXPECTED_V1_BRANCH_SIZES = (6, 4, 4, 4, 4, 4, 9)

ACTION_TYPE_NAMES = {
    0: "noop",
    1: "move",
    2: "harvest",
    3: "return",
    4: "produce",
    5: "attack",
}


class PackagingError(RuntimeError):
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


def _now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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
        raise PackagingError(f"Failed to parse JSON {path}: {exc}") from exc


def _hist_to_sorted_dict(counter: Counter) -> Dict[str, int]:
    return {str(k): int(counter[k]) for k in sorted(counter.keys())}


def _action_name(idx: int) -> str:
    return ACTION_TYPE_NAMES.get(int(idx), str(int(idx)))


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
        raise PackagingError(message)
    return False


def _subset_arrays(arrays: Dict[str, np.ndarray], idx: np.ndarray) -> Dict[str, np.ndarray]:
    return {k: v[idx] for k, v in arrays.items()}


def _save_npz(path: Path, arrays: Dict[str, np.ndarray]) -> None:
    np.savez_compressed(path, **arrays)


def _compute_action_stats(actions: np.ndarray) -> Dict[str, Any]:
    if actions.size == 0:
        return {
            "action_type_histogram": {},
            "produce_unit_type_histogram": {},
            "attack_target_local_histogram": {},
            "branch_min_max": [],
            "noop_share": 0.0,
            "produce_diversity": 0,
            "attack_diversity": {"count": 0, "unique_targets": 0, "max_target_index": None},
        }

    action_type_col = actions[:, :, 0].astype(np.int32, copy=False)
    action_counter = Counter(int(v) for v in action_type_col.reshape(-1).tolist())
    action_hist = {_action_name(k): int(v) for k, v in sorted(action_counter.items())}
    noop_share = float(action_counter.get(0, 0) / max(1, action_type_col.size))

    produce_mask = action_type_col == 4
    produce_counter = Counter(
        int(v) for v in actions[:, :, 5][produce_mask].astype(np.int32).tolist()
    ) if np.any(produce_mask) else Counter()

    attack_mask = action_type_col == 5
    attack_counter = Counter(
        int(v) for v in actions[:, :, 6][attack_mask].astype(np.int32).tolist()
    ) if np.any(attack_mask) else Counter()

    branch_min_max: List[Dict[str, Any]] = []
    for i, size in enumerate(EXPECTED_BRANCH_SIZES):
        col = actions[:, :, i]
        branch_min_max.append(
            {
                "branch": int(i),
                "size": int(size),
                "min": int(col.min()),
                "max": int(col.max()),
                "in_bounds": bool(int(col.min()) >= 0 and int(col.max()) < int(size)),
            }
        )

    return {
        "action_type_histogram": action_hist,
        "produce_unit_type_histogram": _hist_to_sorted_dict(produce_counter),
        "attack_target_local_histogram": _hist_to_sorted_dict(attack_counter),
        "branch_min_max": branch_min_max,
        "noop_share": noop_share,
        "produce_diversity": int(len(produce_counter)),
        "attack_diversity": {
            "count": int(sum(attack_counter.values())),
            "unique_targets": int(len(attack_counter)),
            "max_target_index": int(max(attack_counter.keys())) if attack_counter else None,
        },
    }


def _build_summary_md(summary: Dict[str, Any]) -> str:
    lines: List[str] = [
        "# BC-Ready Legacy032 Unity v2 Packaging Summary",
        "",
        f"- status: {summary['status']}",
        f"- decision: {summary['decision']}",
        f"- output_dir: {summary['output_dir']}",
        f"- source_sample_count: {summary['source_sample_count']}",
        f"- train_count: {summary['train_count']}",
        f"- validation_count: {summary['validation_count']}",
        f"- debug_count: {summary['debug_count']}",
        "",
        "## Shapes",
        "",
        f"- observation_shape_per_sample: {summary['observation_shape_per_sample']}",
        f"- action_shape_per_sample: {summary['action_shape_per_sample']}",
        f"- branch_sizes: {summary['branch_sizes']}",
        "",
        "## Train Action Type Histogram",
        "",
    ]

    if summary["train_action_type_histogram"]:
        for k, v in summary["train_action_type_histogram"].items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- none")

    lines += ["", "## Validation Action Type Histogram", ""]
    if summary["validation_action_type_histogram"]:
        for k, v in summary["validation_action_type_histogram"].items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- none")

    lines += ["", "## Debug Action Type Histogram", ""]
    if summary["debug_action_type_histogram"]:
        for k, v in summary["debug_action_type_histogram"].items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- none")

    lines += ["", "## Branch Min/Max Train", ""]
    for item in summary["train_branch_min_max"]:
        lines.append(
            "- branch {branch} size={size} min={min} max={max} in_bounds={in_bounds}".format(**item)
        )

    lines += ["", "## Branch Min/Max Validation", ""]
    for item in summary["validation_branch_min_max"]:
        lines.append(
            "- branch {branch} size={size} min={min} max={max} in_bounds={in_bounds}".format(**item)
        )

    lines += [
        "",
        "## Mask Shares",
        "",
        f"- train: {summary['action_mask_available_share']['train']:.6f}",
        f"- validation: {summary['action_mask_available_share']['validation']:.6f}",
        f"- debug: {summary['action_mask_available_share']['debug']:.6f}",
        "",
        "## Warnings",
        "",
    ]

    if summary["warnings"]:
        for w in summary["warnings"]:
            lines.append(f"- {w}")
    else:
        lines.append("- none")

    lines += ["", "## Hard Failures", ""]
    if summary["hard_failures"]:
        for h in summary["hard_failures"]:
            lines.append(f"- {h}")
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Build BC-ready datasets from validated Legacy032 Unity v2 adapted dataset. "
            "Packaging only: no BC training."
        )
    )
    p.add_argument("--adapted-dir", required=True)
    p.add_argument("--validation-report", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--run-label", required=True)
    p.add_argument("--validation-split", type=float, default=0.15)
    p.add_argument("--debug-samples", type=int, default=512)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--fail-on-contract-mismatch", type=_parse_bool, default=True)
    return p.parse_args()


def main() -> int:
    args = parse_args()

    adapted_dir = _resolve_path(args.adapted_dir)
    validation_report_path = _resolve_path(args.validation_report)
    output_root = _resolve_path(args.output_dir)

    out_dir = output_root / f"{args.run_label}_{_now_compact()}"
    out_dir.mkdir(parents=True, exist_ok=False)

    bc_train_path = out_dir / "bc_train.npz"
    bc_val_path = out_dir / "bc_validation.npz"
    bc_debug_path = out_dir / "bc_debug.npz"
    bc_manifest_path = out_dir / "bc_manifest.json"
    bc_summary_path = out_dir / "bc_summary.json"
    bc_summary_md_path = out_dir / "bc_summary.md"

    hard_failures: List[str] = []
    warnings: List[str] = []

    adapted_dataset_path = adapted_dir / "adapted_dataset.npz"
    adapted_manifest_path = adapted_dir / "adapted_manifest.json"

    _require(validation_report_path.exists(), f"validation report missing: {validation_report_path}", bool(args.fail_on_contract_mismatch), hard_failures)
    _require(adapted_dataset_path.exists(), f"adapted_dataset missing: {adapted_dataset_path}", bool(args.fail_on_contract_mismatch), hard_failures)
    _require(adapted_manifest_path.exists(), f"adapted_manifest missing: {adapted_manifest_path}", bool(args.fail_on_contract_mismatch), hard_failures)

    validation_report = _load_json(validation_report_path)
    _require(validation_report.get("status") == "pass", "validation report status must be pass", bool(args.fail_on_contract_mismatch), hard_failures)
    _require(
        validation_report.get("decision") == "GO_FOR_BC_READY_PACKAGER",
        "validation report decision must be GO_FOR_BC_READY_PACKAGER",
        bool(args.fail_on_contract_mismatch),
        hard_failures,
    )

    manifest = _load_json(adapted_manifest_path)

    _require(
        manifest.get("target_action_contract") == EXPECTED_TARGET_ACTION_CONTRACT,
        "manifest target_action_contract mismatch",
        bool(args.fail_on_contract_mismatch),
        hard_failures,
    )

    branch_sizes = tuple(int(v) for v in manifest.get("branch_sizes", []))
    _require(branch_sizes != EXPECTED_V1_BRANCH_SIZES, "manifest contains v1 branch sizes [6,4,4,4,4,4,9]", bool(args.fail_on_contract_mismatch), hard_failures)
    _require(branch_sizes == EXPECTED_BRANCH_SIZES, "manifest branch_sizes mismatch", bool(args.fail_on_contract_mismatch), hard_failures)

    _require(
        manifest.get("direct_weight_transfer_claim") is False,
        "manifest direct_weight_transfer_claim must be false",
        bool(args.fail_on_contract_mismatch),
        hard_failures,
    )
    _require(
        manifest.get("semantic_parity_claim") is False,
        "manifest semantic_parity_claim must be false",
        bool(args.fail_on_contract_mismatch),
        hard_failures,
    )

    npz = np.load(str(adapted_dataset_path), allow_pickle=True)
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
    for key in required_arrays:
        _require(key in npz, f"missing required array: {key}", bool(args.fail_on_contract_mismatch), hard_failures)

    arrays = {
        "observations": np.asarray(npz["observations"]),
        "actions": np.asarray(npz["actions"]),
        "episode_id": np.asarray(npz["episode_id"]),
        "step_id": np.asarray(npz["step_id"]),
        "reward_t": np.asarray(npz["reward_t"]),
        "done_t": np.asarray(npz["done_t"]),
        "terminated_t": np.asarray(npz["terminated_t"]),
        "truncated_t": np.asarray(npz["truncated_t"]),
        "action_mask_available_t": np.asarray(npz["action_mask_available_t"]),
    }
    if "source_valid_action_mask" in npz:
        arrays["source_valid_action_mask"] = np.asarray(npz["source_valid_action_mask"], dtype=np.bool_)

    observations = arrays["observations"]
    actions = arrays["actions"]
    source_valid_action_mask = arrays.get("source_valid_action_mask")

    _require(
        observations.ndim == 3 and tuple(observations.shape[1:]) == EXPECTED_OBS_SHAPE,
        f"observations shape mismatch: {list(observations.shape)}",
        bool(args.fail_on_contract_mismatch),
        hard_failures,
    )
    _require(
        actions.ndim == 3 and tuple(actions.shape[1:]) == EXPECTED_ACTION_SHAPE,
        f"actions shape mismatch: {list(actions.shape)}",
        bool(args.fail_on_contract_mismatch),
        hard_failures,
    )

    n = int(observations.shape[0])
    _require(n > 0, "source sample count must be > 0", bool(args.fail_on_contract_mismatch), hard_failures)
    _require(int(actions.shape[0]) == n, "sample count mismatch observations vs actions", bool(args.fail_on_contract_mismatch), hard_failures)

    _require(observations.dtype == np.float32, f"observations dtype must be float32, got {observations.dtype}", bool(args.fail_on_contract_mismatch), hard_failures)
    _require(actions.dtype.kind in {"i", "u"}, f"actions dtype must be integer, got {actions.dtype}", bool(args.fail_on_contract_mismatch), hard_failures)
    _require(
        source_valid_action_mask is not None,
        "source_valid_action_mask missing from adapted dataset",
        bool(args.fail_on_contract_mismatch),
        hard_failures,
    )
    if source_valid_action_mask is not None:
        _require(
            source_valid_action_mask.ndim == 2 and tuple(source_valid_action_mask.shape) == (n, EXPECTED_ACTION_SHAPE[0]),
            (
                "source_valid_action_mask shape mismatch: "
                f"expected [{n},{EXPECTED_ACTION_SHAPE[0]}], got {list(source_valid_action_mask.shape)}"
            ),
            bool(args.fail_on_contract_mismatch),
            hard_failures,
        )
        invalid_action_type = actions[:, :, 0][~source_valid_action_mask]
        invalid_non_noop = int(np.count_nonzero(invalid_action_type != 0))
        _require(
            invalid_non_noop == 0,
            f"source-invalid cells must be NoOp in BC targets; found {invalid_non_noop} non-NoOp labels",
            bool(args.fail_on_contract_mismatch),
            hard_failures,
        )

    for name in ["episode_id", "step_id", "reward_t", "done_t", "terminated_t", "truncated_t", "action_mask_available_t"]:
        arr = arrays[name]
        _require(arr.ndim == 1 and int(arr.shape[0]) == n, f"{name} shape mismatch: expected [{n}], got {list(arr.shape)}", bool(args.fail_on_contract_mismatch), hard_failures)

    has_nan = bool(np.isnan(observations).any())
    has_inf = bool(np.isinf(observations).any())
    _require(not has_nan and not has_inf, "observations contain NaN/Inf", bool(args.fail_on_contract_mismatch), hard_failures)

    branch_min_max_full: List[Dict[str, Any]] = []
    for i, size in enumerate(EXPECTED_BRANCH_SIZES):
        col = actions[:, :, i]
        min_v, max_v = int(col.min()), int(col.max())
        in_bounds = bool(min_v >= 0 and max_v < int(size))
        branch_min_max_full.append({"branch": i, "size": int(size), "min": min_v, "max": max_v, "in_bounds": in_bounds})
        _require(in_bounds, f"branch bounds violation at branch {i}: min={min_v}, max={max_v}, size={size}", bool(args.fail_on_contract_mismatch), hard_failures)

    val_split = float(args.validation_split)
    _require(0.0 < val_split < 1.0, f"validation_split must be in (0,1), got {val_split}", bool(args.fail_on_contract_mismatch), hard_failures)
    if val_split < 0.05:
        warnings.append(f"validation split is very small: {val_split}")

    debug_samples = int(args.debug_samples)
    _require(debug_samples > 0, f"debug_samples must be > 0, got {debug_samples}", bool(args.fail_on_contract_mismatch), hard_failures)
    if debug_samples > n:
        warnings.append(f"debug_samples > source_sample_count ({debug_samples} > {n}); clipping to source size")
        debug_samples = n

    rng = np.random.default_rng(int(args.seed))
    perm = rng.permutation(n)
    val_count = int(round(n * val_split))
    val_count = max(1, min(n - 1, val_count))
    train_count = n - val_count

    _require(train_count > 0 and val_count > 0, f"split resulted in empty partition train={train_count}, validation={val_count}", bool(args.fail_on_contract_mismatch), hard_failures)

    val_idx = np.sort(perm[:val_count])
    train_idx = np.sort(perm[val_count:])
    debug_idx = np.sort(perm[:debug_samples])

    train_arrays = _subset_arrays(arrays, train_idx)
    val_arrays = _subset_arrays(arrays, val_idx)
    debug_arrays = _subset_arrays(arrays, debug_idx)

    _save_npz(bc_train_path, train_arrays)
    _save_npz(bc_val_path, val_arrays)
    _save_npz(bc_debug_path, debug_arrays)

    train_stats = _compute_action_stats(train_arrays["actions"])
    val_stats = _compute_action_stats(val_arrays["actions"])
    debug_stats = _compute_action_stats(debug_arrays["actions"])

    for label, stats in [("train", train_stats), ("validation", val_stats), ("debug", debug_stats)]:
        _require(
            stats["noop_share"] >= 0.75,
            (
                f"implausibly low NoOp share in {label}: {stats['noop_share']:.6f}. "
                "This usually means source-invalid/off-actor cells were stored as supervised non-NoOp labels."
            ),
            bool(args.fail_on_contract_mismatch),
            hard_failures,
        )

    for label, stats in [("train", train_stats), ("validation", val_stats), ("debug", debug_stats)]:
        if stats["noop_share"] >= 0.98:
            warnings.append(f"high noop share in {label}: noop_share={stats['noop_share']:.6f}")
        if stats["produce_diversity"] <= 1:
            warnings.append(f"low produce diversity in {label}")
        if stats["attack_diversity"]["count"] > 0 and stats["attack_diversity"]["unique_targets"] <= 3:
            warnings.append(f"low attack target diversity in {label}")

    share_train = float(np.mean(train_arrays["action_mask_available_t"].astype(np.bool_).astype(np.float64)))
    share_val = float(np.mean(val_arrays["action_mask_available_t"].astype(np.bool_).astype(np.float64)))
    share_debug = float(np.mean(debug_arrays["action_mask_available_t"].astype(np.bool_).astype(np.float64)))
    if share_train < 1.0 or share_val < 1.0 or share_debug < 1.0:
        warnings.append(
            "action_mask_available_share < 1.0 in one or more splits: "
            f"train={share_train:.6f}, validation={share_val:.6f}, debug={share_debug:.6f}"
        )

    bc_manifest = {
        "generated_at_utc": _now_iso(),
        "dataset_type": "bc_ready_legacy032_unity_v2",
        "teacher_lineage": "legacy032",
        "source_pipeline": "gym_microrts==0.3.2",
        "source_adapted_dir": str(adapted_dir),
        "source_validation_report": str(validation_report_path),
        "target_action_contract": "unity_v2_legacy032_gridnet",
        "observation_semantics_version": manifest.get("observation_semantics_version", "unknown"),
        "semantic_adapter_module": manifest.get("semantic_adapter_module"),
        "semantic_adapter_config": manifest.get("semantic_adapter_config"),
        "semantic_mapping_table": manifest.get("semantic_mapping_table", []),
        "observation_shape_per_sample": [576, 27],
        "action_shape_per_sample": [576, 7],
        "branch_sizes": [6, 4, 4, 4, 4, 7, 49],
        "flatten_order": "row_major",
        "flat_cell_index_formula": "row * 24 + col",
        "global_vector_policy": "excluded_from_strict_bc_encoder_path",
        "attack_target_semantics": "local_7x7_49",
        "source_valid_action_mask_present": bool(source_valid_action_mask is not None),
        "source_invalid_cells_forced_to_noop": bool(manifest.get("source_invalid_cells_forced_to_noop", False)),
        "split": {
            "seed": int(args.seed),
            "validation_split": float(val_split),
            "train_count": int(train_count),
            "validation_count": int(val_count),
            "debug_count": int(debug_samples),
        },
        "direct_weight_transfer_claim": False,
        "semantic_parity_claim": False,
        "notes": "BC-ready dataset packaging only. No BC training or Unity runtime semantic parity claim.",
    }
    _json_dump(bc_manifest_path, bc_manifest)

    status = "success" if not hard_failures else "failed"
    decision = "GO_FOR_DRY_RUN_LOADER" if not hard_failures else "NO_GO"

    bc_summary = {
        "generated_at_utc": _now_iso(),
        "status": status,
        "output_dir": str(out_dir),
        "source_sample_count": int(n),
        "train_count": int(train_count),
        "validation_count": int(val_count),
        "debug_count": int(debug_samples),
        "observation_shape_per_sample": [576, 27],
        "action_shape_per_sample": [576, 7],
        "branch_sizes": [6, 4, 4, 4, 4, 7, 49],
        "train_action_type_histogram": train_stats["action_type_histogram"],
        "validation_action_type_histogram": val_stats["action_type_histogram"],
        "debug_action_type_histogram": debug_stats["action_type_histogram"],
        "train_branch_min_max": train_stats["branch_min_max"],
        "validation_branch_min_max": val_stats["branch_min_max"],
        "action_mask_available_share": {
            "train": float(share_train),
            "validation": float(share_val),
            "debug": float(share_debug),
        },
        "source_valid_action_mask_present": bool(source_valid_action_mask is not None),
        "warnings": warnings,
        "hard_failures": hard_failures,
        "decision": decision,
    }

    _json_dump(bc_summary_path, bc_summary)
    bc_summary_md_path.write_text(_build_summary_md(bc_summary), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": status,
                "decision": decision,
                "output_dir": str(out_dir),
                "bc_train": str(bc_train_path),
                "bc_validation": str(bc_val_path),
                "bc_debug": str(bc_debug_path),
                "bc_manifest": str(bc_manifest_path),
                "bc_summary": str(bc_summary_path),
                "bc_summary_md": str(bc_summary_md_path),
            },
            ensure_ascii=True,
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        traceback.print_exc()
        raise SystemExit(f"[build_bc_ready_dataset_legacy032_v2] ERROR: {exc}")
