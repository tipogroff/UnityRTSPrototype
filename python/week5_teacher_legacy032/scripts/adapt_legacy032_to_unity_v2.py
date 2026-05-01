#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

import numpy as np


TARGET_OBS_SHAPE = (576, 27)
TARGET_ACTION_SHAPE = (576, 7)
TARGET_BRANCH_SIZES = (6, 4, 4, 4, 4, 7, 49)
SOURCE_OBS_SHAPE = (24, 24, 27)
SOURCE_ACTION_SHAPE = (576, 7)
EXPECTED_RAW_ACTION_NVEC = [576, 6, 4, 4, 4, 4, 7, 49]

ACTION_TYPE_NAMES = {
    0: "noop",
    1: "move",
    2: "harvest",
    3: "return",
    4: "produce",
    5: "attack",
}


class AdaptationError(RuntimeError):
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_path(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (_repo_root() / p).resolve()


def _now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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


def _hist_to_sorted_dict(counter: Counter) -> Dict[str, int]:
    return {str(k): int(counter[k]) for k in sorted(counter.keys())}


def _action_name(action_type: int) -> str:
    return ACTION_TYPE_NAMES.get(int(action_type), str(int(action_type)))


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
        raise AdaptationError(message)
    return False


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AdaptationError(f"Failed to parse JSON: {path} ({exc})") from exc


def _validate_source_manifest(
    source_manifest: Dict[str, Any],
    fail_on_contract_mismatch: bool,
    hard_failures: List[str],
) -> None:
    _require(
        str(source_manifest.get("teacher_lineage", "")).strip() == "legacy032",
        "source manifest teacher_lineage must be legacy032",
        fail_on_contract_mismatch,
        hard_failures,
    )
    _require(
        [int(v) for v in source_manifest.get("raw_action_nvec", [])] == EXPECTED_RAW_ACTION_NVEC,
        "source manifest raw_action_nvec mismatch; expected [576,6,4,4,4,4,7,49]",
        fail_on_contract_mismatch,
        hard_failures,
    )
    _require(
        [int(v) for v in source_manifest.get("exported_per_cell_branch_sizes", [])] == list(TARGET_BRANCH_SIZES),
        "source manifest exported_per_cell_branch_sizes mismatch; expected [6,4,4,4,4,7,49]",
        fail_on_contract_mismatch,
        hard_failures,
    )


def _validate_action_bounds(
    actions: np.ndarray,
    fail_on_contract_mismatch: bool,
    hard_failures: List[str],
) -> List[Dict[str, int]]:
    if actions.dtype.kind not in {"i", "u"}:
        _require(False, f"actions dtype must be integer; got {actions.dtype}", fail_on_contract_mismatch, hard_failures)
        return []

    branch_min_max: List[Dict[str, int]] = []
    for branch_idx, branch_size in enumerate(TARGET_BRANCH_SIZES):
        col = actions[:, :, branch_idx]
        min_v = int(col.min())
        max_v = int(col.max())
        branch_min_max.append(
            {
                "branch": int(branch_idx),
                "size": int(branch_size),
                "min": int(min_v),
                "max": int(max_v),
                "in_bounds": bool(min_v >= 0 and max_v < int(branch_size)),
            }
        )
        _require(
            min_v >= 0 and max_v < int(branch_size),
            (
                "action values out of branch bounds at "
                f"branch={branch_idx}: min={min_v}, max={max_v}, size={branch_size}"
            ),
            fail_on_contract_mismatch,
            hard_failures,
        )

    # Explicit anti-v1 remap guards.
    _require(
        int(actions[:, :, 5].max()) <= 6,
        "detected invalid produce_unit_type (>6); v1 remap path is forbidden",
        fail_on_contract_mismatch,
        hard_failures,
    )
    _require(
        int(actions[:, :, 6].max()) <= 48,
        "detected invalid attack_target_local (>48); v1 remap path is forbidden",
        fail_on_contract_mismatch,
        hard_failures,
    )

    return branch_min_max


def _build_markdown_summary(summary: Dict[str, Any]) -> str:
    lines: List[str] = [
        "# Legacy032 -> Unity v2 Adaptation Summary",
        "",
        f"- status: {summary['status']}",
        f"- run_label: {summary['run_label']}",
        f"- output_dir: {summary['output_dir']}",
        f"- source_rollout_dir: {summary['source_rollout_dir']}",
        f"- source_sample_count: {summary['source_sample_count']}",
        f"- output_sample_count: {summary['output_sample_count']}",
        "",
        "## Shapes",
        "",
        f"- source_observation_shape: {summary['source_observation_shape']}",
        f"- output_observation_shape: {summary['output_observation_shape']}",
        f"- source_action_shape: {summary['source_action_shape']}",
        f"- output_action_shape: {summary['output_action_shape']}",
        "",
        "## Branch Min/Max",
        "",
    ]

    for item in summary["branch_min_max"]:
        lines.append(
            "- branch {branch} (size={size}): min={min}, max={max}, in_bounds={in_bounds}".format(
                **item
            )
        )

    lines += [
        "",
        "## NaN/Inf Checks",
        "",
        f"- source_observation_has_nan: {summary['nan_inf_checks']['source_observation_has_nan']}",
        f"- source_observation_has_inf: {summary['nan_inf_checks']['source_observation_has_inf']}",
        f"- output_observation_has_nan: {summary['nan_inf_checks']['output_observation_has_nan']}",
        f"- output_observation_has_inf: {summary['nan_inf_checks']['output_observation_has_inf']}",
        "",
        "## Histograms",
        "",
        "### action_type_histogram",
    ]

    if summary["action_type_histogram"]:
        for k, v in summary["action_type_histogram"].items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- none")

    lines += ["", "### produce_unit_type_histogram"]
    if summary["produce_unit_type_histogram"]:
        for k, v in summary["produce_unit_type_histogram"].items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- none")

    lines += [
        "",
        "### attack_target_local",
    ]

    if summary["attack_target_local"]["histogram"]:
        for k, v in summary["attack_target_local"]["histogram"].items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- none")

    diversity = summary["attack_target_local"]["diversity"]
    lines += [
        "",
        f"- diversity.count: {diversity['count']}",
        f"- diversity.unique_targets: {diversity['unique_targets']}",
        f"- diversity.max_target_index: {diversity['max_target_index']}",
        "",
        "## Mask Availability",
        "",
        f"- action_mask_available_share: {summary['action_mask_available_share']:.6f}",
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
        for hf in summary["hard_failures"]:
            lines.append(f"- {hf}")
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Adapt Legacy032 raw rollout to Unity v2 tensor contract only. "
            "No semantic remap, no validator, no BC packaging."
        )
    )
    p.add_argument("--raw-rollout-dir", required=True)
    p.add_argument("--run-label", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--fail-on-contract-mismatch", type=_parse_bool, default=True)
    p.add_argument("--write-debug-sample", type=_parse_bool, default=False)
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if TARGET_BRANCH_SIZES != (6, 4, 4, 4, 4, 7, 49):
        raise AdaptationError("target branch sizes must stay [6,4,4,4,4,7,49]")

    raw_rollout_dir = _resolve_path(args.raw_rollout_dir)
    output_root = _resolve_path(args.output_dir)
    output_dir = output_root / f"{args.run_label}_{_now_compact()}"
    output_dir.mkdir(parents=True, exist_ok=False)

    source_rollout_file = raw_rollout_dir / "teacher_rollout_raw.npz"
    source_manifest_file = raw_rollout_dir / "teacher_rollout_manifest.json"

    adapted_dataset_path = output_dir / "adapted_dataset.npz"
    adapted_manifest_path = output_dir / "adapted_manifest.json"
    summary_json_path = output_dir / "adaptation_summary.json"
    summary_md_path = output_dir / "adaptation_summary.md"
    debug_sample_path = output_dir / "adaptation_debug_sample.json"

    warnings: List[str] = []
    hard_failures: List[str] = []

    _require(
        source_rollout_file.exists(),
        f"missing source rollout file: {source_rollout_file}",
        bool(args.fail_on_contract_mismatch),
        hard_failures,
    )
    _require(
        source_manifest_file.exists(),
        f"missing source manifest file: {source_manifest_file}",
        bool(args.fail_on_contract_mismatch),
        hard_failures,
    )

    source_manifest = _load_json(source_manifest_file)
    _validate_source_manifest(source_manifest, bool(args.fail_on_contract_mismatch), hard_failures)

    npz = np.load(str(source_rollout_file), allow_pickle=True)

    required_arrays = [
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
    for key in required_arrays:
        _require(
            key in npz,
            f"missing required array in source rollout: {key}",
            bool(args.fail_on_contract_mismatch),
            hard_failures,
        )

    source_observation = np.asarray(npz["observation_t"], dtype=np.float32)
    source_actions = np.asarray(npz["per_cell_action_t"])

    _require(
        source_observation.ndim == 4 and tuple(source_observation.shape[1:]) == SOURCE_OBS_SHAPE,
        (
            "source observation_t shape mismatch; "
            f"expected [N,{SOURCE_OBS_SHAPE[0]},{SOURCE_OBS_SHAPE[1]},{SOURCE_OBS_SHAPE[2]}], "
            f"actual {list(source_observation.shape)}"
        ),
        bool(args.fail_on_contract_mismatch),
        hard_failures,
    )
    _require(
        source_actions.ndim == 3 and tuple(source_actions.shape[1:]) == SOURCE_ACTION_SHAPE,
        (
            "source per_cell_action_t shape mismatch; "
            f"expected [N,{SOURCE_ACTION_SHAPE[0]},{SOURCE_ACTION_SHAPE[1]}], "
            f"actual {list(source_actions.shape)}"
        ),
        bool(args.fail_on_contract_mismatch),
        hard_failures,
    )

    source_n = int(source_observation.shape[0])
    _require(
        int(source_actions.shape[0]) == source_n,
        "sample count mismatch between observation_t and per_cell_action_t",
        bool(args.fail_on_contract_mismatch),
        hard_failures,
    )

    src_nan = bool(np.isnan(source_observation).any())
    src_inf = bool(np.isinf(source_observation).any())
    _require(
        not src_nan and not src_inf,
        "NaN/Inf detected in source observation_t",
        bool(args.fail_on_contract_mismatch),
        hard_failures,
    )

    # Row-major flattening preserves flat_cell_index = row * 24 + col.
    observations = source_observation.reshape(source_n, TARGET_OBS_SHAPE[0], TARGET_OBS_SHAPE[1]).astype(np.float32, copy=False)
    actions = source_actions.astype(np.int16, copy=False)

    _require(
        tuple(observations.shape[1:]) == TARGET_OBS_SHAPE,
        "output observations shape mismatch; expected [N,576,27]",
        bool(args.fail_on_contract_mismatch),
        hard_failures,
    )
    _require(
        tuple(actions.shape[1:]) == TARGET_ACTION_SHAPE,
        "output actions shape mismatch; expected [N,576,7]",
        bool(args.fail_on_contract_mismatch),
        hard_failures,
    )

    branch_min_max = _validate_action_bounds(actions, bool(args.fail_on_contract_mismatch), hard_failures)

    out_nan = bool(np.isnan(observations).any())
    out_inf = bool(np.isinf(observations).any())
    _require(
        not out_nan and not out_inf,
        "NaN/Inf detected in output observations",
        bool(args.fail_on_contract_mismatch),
        hard_failures,
    )

    episode_id = np.asarray(npz["episode_id"], dtype=np.int32)
    step_id = np.asarray(npz["step_id"], dtype=np.int32)
    reward_t = np.asarray(npz["reward_t"], dtype=np.float32)
    done_t = np.asarray(npz["done_t"], dtype=np.bool_)
    terminated_t = np.asarray(npz["terminated_t"], dtype=np.bool_)
    truncated_t = np.asarray(npz["truncated_t"], dtype=np.bool_)
    action_mask_available_t = np.asarray(npz["action_mask_available_t"], dtype=np.bool_)

    for name, arr in [
        ("episode_id", episode_id),
        ("step_id", step_id),
        ("reward_t", reward_t),
        ("done_t", done_t),
        ("terminated_t", terminated_t),
        ("truncated_t", truncated_t),
        ("action_mask_available_t", action_mask_available_t),
    ]:
        _require(
            int(arr.shape[0]) == source_n,
            f"array length mismatch for {name}; expected {source_n}, actual {arr.shape[0]}",
            bool(args.fail_on_contract_mismatch),
            hard_failures,
        )

    np.savez_compressed(
        adapted_dataset_path,
        observations=observations,
        actions=actions,
        episode_id=episode_id,
        step_id=step_id,
        reward_t=reward_t,
        done_t=done_t,
        terminated_t=terminated_t,
        truncated_t=truncated_t,
        action_mask_available_t=action_mask_available_t,
    )

    action_type_col = actions[:, :, 0].astype(np.int32, copy=False)
    total_cells = int(action_type_col.size)
    noop_cells = int(np.count_nonzero(action_type_col == 0))
    noop_share = float(noop_cells / max(1, total_cells))

    action_type_hist_raw = Counter(int(v) for v in action_type_col.reshape(-1).tolist())
    action_type_hist = {
        _action_name(k): int(v)
        for k, v in sorted(action_type_hist_raw.items())
    }

    produce_mask = action_type_col == 4
    produce_type_hist = Counter(int(v) for v in actions[:, :, 5][produce_mask].tolist()) if np.any(produce_mask) else Counter()

    attack_mask = action_type_col == 5
    attack_target_hist = Counter(int(v) for v in actions[:, :, 6][attack_mask].tolist()) if np.any(attack_mask) else Counter()

    attack_diversity = {
        "count": int(sum(attack_target_hist.values())),
        "unique_targets": int(len(attack_target_hist)),
        "max_target_index": int(max(attack_target_hist.keys())) if attack_target_hist else None,
    }

    action_mask_share = float(np.mean(action_mask_available_t.astype(np.float64)))

    if noop_share >= 0.98:
        warnings.append(f"high noop share: noop_share={noop_share:.6f}")
    if attack_diversity["count"] == 0:
        warnings.append("no attack actions observed")
    if int(sum(produce_type_hist.values())) == 0:
        warnings.append("no produce actions observed")
    if int(sum(produce_type_hist.values())) > 0 and len(produce_type_hist) <= 1:
        warnings.append("produce_unit_type diversity is low")
    if attack_diversity["count"] > 0 and attack_diversity["unique_targets"] <= 3:
        warnings.append("attack_target_local diversity is low")
    if action_mask_share < 1.0:
        warnings.append(f"action_mask_available_share is below 1.0 ({action_mask_share:.6f})")

    adapted_manifest = {
        "generated_at_utc": _now_iso(),
        "teacher_lineage": "legacy032",
        "source_pipeline": "gym_microrts==0.3.2",
        "source_export_dir": str(raw_rollout_dir),
        "source_rollout_file": "teacher_rollout_raw.npz",
        "source_manifest_file": "teacher_rollout_manifest.json",
        "target_action_contract": "unity_v2_legacy032_gridnet",
        "observation_shape_per_sample": [576, 27],
        "action_shape_per_sample": [576, 7],
        "branch_sizes": [6, 4, 4, 4, 4, 7, 49],
        "flatten_order": "row_major",
        "flat_cell_index_formula": "row * 24 + col",
        "global_vector_policy": "excluded_from_strict_bc_encoder_path",
        "attack_target_semantics": "local_7x7_49",
        "direct_weight_transfer_claim": False,
        "semantic_parity_claim": False,
        "notes": "Legacy032 raw rollout adapted to Unity v2 tensor contract only; Unity runtime semantic parity is not claimed.",
    }
    _json_dump(adapted_manifest_path, adapted_manifest)

    summary = {
        "generated_at_utc": _now_iso(),
        "status": "success",
        "run_label": args.run_label,
        "source_rollout_dir": str(raw_rollout_dir),
        "output_dir": str(output_dir),
        "source_sample_count": int(source_n),
        "output_sample_count": int(source_n),
        "source_observation_shape": list(source_observation.shape),
        "output_observation_shape": list(observations.shape),
        "source_action_shape": list(source_actions.shape),
        "output_action_shape": list(actions.shape),
        "branch_min_max": branch_min_max,
        "nan_inf_checks": {
            "source_observation_has_nan": bool(src_nan),
            "source_observation_has_inf": bool(src_inf),
            "output_observation_has_nan": bool(out_nan),
            "output_observation_has_inf": bool(out_inf),
        },
        "action_type_histogram": action_type_hist,
        "produce_unit_type_histogram": _hist_to_sorted_dict(produce_type_hist),
        "attack_target_local": {
            "histogram": _hist_to_sorted_dict(attack_target_hist),
            "diversity": attack_diversity,
        },
        "action_mask_available_share": float(action_mask_share),
        "warnings": warnings,
        "hard_failures": hard_failures,
    }
    _json_dump(summary_json_path, summary)
    summary_md_path.write_text(_build_markdown_summary(summary), encoding="utf-8")

    if bool(args.write_debug_sample):
        debug_payload: Dict[str, Any] = {
            "generated_at_utc": _now_iso(),
            "source_rollout_dir": str(raw_rollout_dir),
            "sample_index": 0,
            "sample": {
                "episode_id": int(episode_id[0]),
                "step_id": int(step_id[0]),
                "reward_t": float(reward_t[0]),
                "done_t": bool(done_t[0]),
                "terminated_t": bool(terminated_t[0]),
                "truncated_t": bool(truncated_t[0]),
                "action_mask_available_t": bool(action_mask_available_t[0]),
                "observation_first_cell_first_8_features": observations[0, 0, :8].astype(np.float32).tolist(),
                "action_first_cell": actions[0, 0, :].astype(np.int32).tolist(),
            },
        }
        _json_dump(debug_sample_path, debug_payload)

    print(
        json.dumps(
            {
                "status": "success",
                "output_dir": str(output_dir),
                "adapted_dataset": str(adapted_dataset_path),
                "adapted_manifest": str(adapted_manifest_path),
                "adaptation_summary": str(summary_json_path),
                "adaptation_summary_md": str(summary_md_path),
                "adaptation_debug_sample": str(debug_sample_path) if bool(args.write_debug_sample) else None,
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
        raise SystemExit(f"[adapt_legacy032_to_unity_v2] ERROR: {exc}")
