#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
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


class ValidationError(RuntimeError):
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
        raise ValidationError(f"Failed to parse JSON {path}: {exc}") from exc


def _require(condition: bool, hard_failures: List[str], message: str) -> bool:
    if condition:
        return True
    hard_failures.append(message)
    return False


def _warn_if(condition: bool, warnings: List[str], message: str) -> None:
    if condition:
        warnings.append(message)


def _hist_to_sorted_dict(counter: Counter) -> Dict[str, int]:
    return {str(k): int(counter[k]) for k in sorted(counter.keys())}


def _action_name(idx: int) -> str:
    return ACTION_TYPE_NAMES.get(int(idx), str(int(idx)))


def _build_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = []

    lines.append("# LEGACY032 Unity v2 Dataset Validation Report")
    lines.append("")
    lines.append("## 1. Summary")
    lines.append("")
    lines.append(f"- status: {report['status']}")
    lines.append(f"- decision: {report['decision']}")
    lines.append(f"- sample_count: {report['sample_count']}")
    lines.append(f"- adapted_dir: {report['adapted_dir']}")
    lines.append("")

    lines.append("## 2. Input Artifacts")
    lines.append("")
    lines.append(f"- adapted_dataset: {report['input_artifacts']['adapted_dataset']}")
    lines.append(f"- adapted_manifest: {report['input_artifacts']['adapted_manifest']}")
    lines.append("")

    lines.append("## 3. Manifest Checks")
    lines.append("")
    for check_name, item in report["manifest_checks"].items():
        lines.append(f"- {check_name}: pass={item['pass']}, expected={item['expected']}, actual={item['actual']}")
    lines.append("")

    lines.append("## 4. Dataset Shape and Dtype Checks")
    lines.append("")
    for check_name, item in report["dataset_checks"].items():
        lines.append(f"- {check_name}: pass={item['pass']}, detail={item['detail']}")
    lines.append("")
    lines.append(f"- observation_shape: {report['observation_shape']}")
    lines.append(f"- action_shape: {report['action_shape']}")
    lines.append(f"- observation_dtype: {report['observation_dtype']}")
    lines.append(f"- action_dtype: {report['action_dtype']}")
    lines.append("")

    lines.append("## 5. Observation Value Checks")
    lines.append("")
    lines.append(f"- observation_min: {report['observation_min']}")
    lines.append(f"- observation_max: {report['observation_max']}")
    lines.append(f"- observation_out_of_range_share: {report['observation_out_of_range_share']}")
    lines.append(f"- has_nan: {report['nan_inf_checks']['observation_has_nan']}")
    lines.append(f"- has_inf: {report['nan_inf_checks']['observation_has_inf']}")
    lines.append("")

    lines.append("## 6. Action Branch Bounds")
    lines.append("")
    for item in report["branch_min_max"]:
        lines.append(
            "- branch {branch} size={size} min={min} max={max} in_bounds={in_bounds}".format(**item)
        )
    lines.append("")

    lines.append("## 7. Action Statistics")
    lines.append("")
    lines.append("### action_type_histogram")
    for k, v in report["action_type_histogram"].items():
        lines.append(f"- {k}: {v}")
    if not report["action_type_histogram"]:
        lines.append("- none")
    lines.append("")

    lines.append("### produce_unit_type_histogram")
    for k, v in report["produce_unit_type_histogram"].items():
        lines.append(f"- {k}: {v}")
    if not report["produce_unit_type_histogram"]:
        lines.append("- none")
    lines.append("")

    lines.append("### attack_target_local_histogram")
    for k, v in report["attack_target_local_histogram"].items():
        lines.append(f"- {k}: {v}")
    if not report["attack_target_local_histogram"]:
        lines.append("- none")
    lines.append("")

    div = report["attack_target_local_diversity"]
    lines.append(f"- attack_target_local_diversity.count: {div['count']}")
    lines.append(f"- attack_target_local_diversity.unique_targets: {div['unique_targets']}")
    lines.append(f"- attack_target_local_diversity.max_target_index: {div['max_target_index']}")
    lines.append(f"- action_mask_available_share: {report['action_mask_available_share']}")
    if "source_valid_action_mask" in report:
        svm = report["source_valid_action_mask"]
        lines.append(f"- source_valid_action_mask_present: {svm['present']}")
        lines.append(f"- source_valid_action_mask_shape: {svm['shape']}")
        lines.append(f"- source_valid_cells_mean: {svm['source_valid_cells_mean']}")
        lines.append(f"- source_invalid_non_noop_count: {svm['source_invalid_non_noop_count']}")
    lines.append("")

    lines.append("## 8. Warnings")
    lines.append("")
    for w in report["warnings"]:
        lines.append(f"- {w}")
    if not report["warnings"]:
        lines.append("- none")
    lines.append("")

    lines.append("## 9. Hard Failures")
    lines.append("")
    for h in report["hard_failures"]:
        lines.append(f"- {h}")
    if not report["hard_failures"]:
        lines.append("- none")
    lines.append("")

    lines.append("## 10. Decision")
    lines.append("")
    lines.append(f"- {report['decision']}")

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Independent strict validator for Legacy032 Unity v2 adapted dataset. "
            "Reads adapted_dataset.npz and adapted_manifest.json directly."
        )
    )
    p.add_argument("--adapted-dir", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--fail-on-hard-errors", type=_parse_bool, default=True)
    p.add_argument("--write-debug-json", type=_parse_bool, default=False)
    return p.parse_args()


def main() -> int:
    args = parse_args()

    adapted_dir = _resolve_path(args.adapted_dir)
    output_dir = _resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_report_path = output_dir / "LEGACY032_UNITY_V2_DATASET_VALIDATION_REPORT.json"
    md_report_path = output_dir / "LEGACY032_UNITY_V2_DATASET_VALIDATION_REPORT.md"
    debug_report_path = output_dir / "LEGACY032_UNITY_V2_DATASET_VALIDATION_DEBUG.json"

    adapted_dataset_path = adapted_dir / "adapted_dataset.npz"
    adapted_manifest_path = adapted_dir / "adapted_manifest.json"

    hard_failures: List[str] = []
    warnings: List[str] = []

    manifest_checks: Dict[str, Dict[str, Any]] = {}
    dataset_checks: Dict[str, Dict[str, Any]] = {}

    def add_manifest_check(name: str, expected: Any, actual: Any, ok: bool) -> None:
        manifest_checks[name] = {
            "pass": bool(ok),
            "expected": expected,
            "actual": actual,
        }
        if not ok:
            hard_failures.append(f"manifest check failed: {name}")

    def add_dataset_check(name: str, ok: bool, detail: str) -> None:
        dataset_checks[name] = {
            "pass": bool(ok),
            "detail": detail,
        }
        if not ok:
            hard_failures.append(f"dataset check failed: {name} ({detail})")

    if not adapted_dataset_path.exists():
        hard_failures.append(f"missing adapted_dataset.npz: {adapted_dataset_path}")
    if not adapted_manifest_path.exists():
        hard_failures.append(f"missing adapted_manifest.json: {adapted_manifest_path}")

    manifest: Dict[str, Any] = {}
    if adapted_manifest_path.exists():
        manifest = _load_json(adapted_manifest_path)

        add_manifest_check(
            "teacher_lineage",
            "legacy032",
            manifest.get("teacher_lineage"),
            manifest.get("teacher_lineage") == "legacy032",
        )
        add_manifest_check(
            "source_pipeline",
            "gym_microrts==0.3.2",
            manifest.get("source_pipeline"),
            manifest.get("source_pipeline") == "gym_microrts==0.3.2",
        )

        actual_contract = manifest.get("target_action_contract")
        add_manifest_check(
            "target_action_contract",
            EXPECTED_TARGET_ACTION_CONTRACT,
            actual_contract,
            actual_contract == EXPECTED_TARGET_ACTION_CONTRACT,
        )

        obs_per_sample = manifest.get("observation_shape_per_sample")
        action_per_sample = manifest.get("action_shape_per_sample")
        branch_sizes = manifest.get("branch_sizes")

        add_manifest_check(
            "observation_shape_per_sample",
            list(EXPECTED_OBS_SHAPE),
            obs_per_sample,
            list(obs_per_sample or []) == list(EXPECTED_OBS_SHAPE),
        )
        add_manifest_check(
            "action_shape_per_sample",
            list(EXPECTED_ACTION_SHAPE),
            action_per_sample,
            list(action_per_sample or []) == list(EXPECTED_ACTION_SHAPE),
        )
        add_manifest_check(
            "branch_sizes",
            list(EXPECTED_BRANCH_SIZES),
            branch_sizes,
            list(branch_sizes or []) == list(EXPECTED_BRANCH_SIZES),
        )

        if tuple(branch_sizes or ()) == EXPECTED_V1_BRANCH_SIZES:
            hard_failures.append("manifest contains v1 branch sizes [6,4,4,4,4,4,9]")

        add_manifest_check(
            "flatten_order",
            "row_major",
            manifest.get("flatten_order"),
            manifest.get("flatten_order") == "row_major",
        )
        add_manifest_check(
            "flat_cell_index_formula",
            "row * 24 + col",
            manifest.get("flat_cell_index_formula"),
            manifest.get("flat_cell_index_formula") == "row * 24 + col",
        )
        add_manifest_check(
            "global_vector_policy",
            "excluded_from_strict_bc_encoder_path",
            manifest.get("global_vector_policy"),
            manifest.get("global_vector_policy") == "excluded_from_strict_bc_encoder_path",
        )
        add_manifest_check(
            "attack_target_semantics",
            "local_7x7_49",
            manifest.get("attack_target_semantics"),
            manifest.get("attack_target_semantics") == "local_7x7_49",
        )
        add_manifest_check(
            "direct_weight_transfer_claim",
            False,
            manifest.get("direct_weight_transfer_claim"),
            manifest.get("direct_weight_transfer_claim") is False,
        )
        add_manifest_check(
            "semantic_parity_claim",
            False,
            manifest.get("semantic_parity_claim"),
            manifest.get("semantic_parity_claim") is False,
        )

    observations = np.empty((0, 576, 27), dtype=np.float32)
    actions = np.empty((0, 576, 7), dtype=np.int16)
    episode_id = np.empty((0,), dtype=np.int32)
    step_id = np.empty((0,), dtype=np.int32)
    reward_t = np.empty((0,), dtype=np.float32)
    done_t = np.empty((0,), dtype=np.bool_)
    terminated_t = np.empty((0,), dtype=np.bool_)
    truncated_t = np.empty((0,), dtype=np.bool_)
    action_mask_available_t = np.empty((0,), dtype=np.bool_)
    source_valid_action_mask = None
    source_valid_action_mask_report: Dict[str, Any] = {
        "present": False,
        "shape": [],
        "shape_ok": False,
        "source_valid_cells_mean": None,
        "source_invalid_non_noop_count": None,
    }

    if adapted_dataset_path.exists():
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
            present = key in npz
            add_dataset_check(
                f"required_array_{key}",
                present,
                "present" if present else "missing",
            )

        if all((k in npz) for k in required_arrays):
            observations = np.asarray(npz["observations"])
            actions = np.asarray(npz["actions"])
            episode_id = np.asarray(npz["episode_id"])
            step_id = np.asarray(npz["step_id"])
            reward_t = np.asarray(npz["reward_t"])
            done_t = np.asarray(npz["done_t"])
            terminated_t = np.asarray(npz["terminated_t"])
            truncated_t = np.asarray(npz["truncated_t"])
            action_mask_available_t = np.asarray(npz["action_mask_available_t"])
            if "source_valid_action_mask" in npz:
                source_valid_action_mask = np.asarray(npz["source_valid_action_mask"], dtype=np.bool_)

            obs_shape_ok = observations.ndim == 3 and tuple(observations.shape[1:]) == EXPECTED_OBS_SHAPE
            act_shape_ok = actions.ndim == 3 and tuple(actions.shape[1:]) == EXPECTED_ACTION_SHAPE

            add_dataset_check(
                "observations_shape",
                obs_shape_ok,
                f"expected [N,{EXPECTED_OBS_SHAPE[0]},{EXPECTED_OBS_SHAPE[1]}], actual {list(observations.shape)}",
            )
            add_dataset_check(
                "actions_shape",
                act_shape_ok,
                f"expected [N,{EXPECTED_ACTION_SHAPE[0]},{EXPECTED_ACTION_SHAPE[1]}], actual {list(actions.shape)}",
            )

            n_obs = int(observations.shape[0]) if observations.ndim >= 1 else 0
            n_act = int(actions.shape[0]) if actions.ndim >= 1 else 0
            add_dataset_check("sample_count_gt_zero", n_obs > 0, f"N={n_obs}")
            add_dataset_check("sample_count_match_obs_actions", n_obs == n_act, f"obs_N={n_obs}, action_N={n_act}")

            obs_dtype_ok = observations.dtype == np.float32
            add_dataset_check(
                "observations_dtype_float32",
                obs_dtype_ok,
                f"dtype={observations.dtype}",
            )

            act_int_ok = actions.dtype.kind in {"i", "u"}
            add_dataset_check(
                "actions_integer_dtype",
                act_int_ok,
                f"dtype={actions.dtype}",
            )

            for name, arr in [
                ("episode_id", episode_id),
                ("step_id", step_id),
                ("reward_t", reward_t),
                ("done_t", done_t),
                ("terminated_t", terminated_t),
                ("truncated_t", truncated_t),
                ("action_mask_available_t", action_mask_available_t),
            ]:
                ok = arr.ndim == 1 and int(arr.shape[0]) == n_obs
                add_dataset_check(
                    f"{name}_shape",
                    ok,
                    f"expected [{n_obs}], actual {list(arr.shape)}",
                )

            has_nan = bool(np.isnan(observations).any())
            has_inf = bool(np.isinf(observations).any())
            add_dataset_check("observations_no_nan", not has_nan, f"has_nan={has_nan}")
            add_dataset_check("observations_no_inf", not has_inf, f"has_inf={has_inf}")

            if actions.ndim == 3 and actions.shape[2] == 7 and actions.shape[0] > 0:
                branch_min_max: List[Dict[str, Any]] = []
                for i, size in enumerate(EXPECTED_BRANCH_SIZES):
                    col = actions[:, :, i]
                    min_v = int(col.min())
                    max_v = int(col.max())
                    in_bounds = bool(min_v >= 0 and max_v < int(size))
                    branch_min_max.append(
                        {
                            "branch": int(i),
                            "size": int(size),
                            "min": int(min_v),
                            "max": int(max_v),
                            "in_bounds": in_bounds,
                        }
                    )
                    add_dataset_check(
                        f"branch_{i}_bounds",
                        in_bounds,
                        f"size={size}, min={min_v}, max={max_v}",
                    )
            else:
                branch_min_max = []
                hard_failures.append("cannot compute branch bounds due to invalid actions shape")

            action_mask_bool = action_mask_available_t.astype(np.bool_, copy=False)
            action_mask_share = float(np.mean(action_mask_bool.astype(np.float64))) if n_obs > 0 else 0.0

            source_valid_action_mask_report = {
                "present": bool(source_valid_action_mask is not None),
                "shape": list(source_valid_action_mask.shape) if source_valid_action_mask is not None else [],
                "shape_ok": False,
                "source_valid_cells_mean": None,
                "source_invalid_non_noop_count": None,
            }
            add_dataset_check(
                "source_valid_action_mask_present",
                source_valid_action_mask is not None,
                "present" if source_valid_action_mask is not None else "missing",
            )
            if source_valid_action_mask is not None:
                source_mask_shape_ok = (
                    source_valid_action_mask.ndim == 2
                    and tuple(source_valid_action_mask.shape) == (n_obs, EXPECTED_ACTION_SHAPE[0])
                )
                source_valid_action_mask_report["shape_ok"] = bool(source_mask_shape_ok)
                add_dataset_check(
                    "source_valid_action_mask_shape",
                    source_mask_shape_ok,
                    (
                        f"expected [{n_obs},{EXPECTED_ACTION_SHAPE[0]}], "
                        f"actual {list(source_valid_action_mask.shape)}"
                    ),
                )
                if source_mask_shape_ok and actions.ndim == 3 and actions.shape[2] == 7:
                    invalid_action_type = actions[:, :, 0][~source_valid_action_mask]
                    invalid_non_noop = int(np.count_nonzero(invalid_action_type != 0))
                    source_valid_action_mask_report["source_valid_cells_mean"] = float(
                        source_valid_action_mask.sum(axis=1).mean()
                    ) if n_obs > 0 else 0.0
                    source_valid_action_mask_report["source_invalid_non_noop_count"] = invalid_non_noop
                    add_dataset_check(
                        "source_invalid_cells_action_type_noop",
                        invalid_non_noop == 0,
                        f"source_invalid_non_noop_count={invalid_non_noop}",
                    )

            if observations.size > 0:
                obs_min = float(np.min(observations))
                obs_max = float(np.max(observations))
                out_of_range = np.logical_or(observations < 0.0, observations > 1.0)
                out_of_range_share = float(np.mean(out_of_range.astype(np.float64)))
            else:
                obs_min = None
                obs_max = None
                out_of_range_share = 0.0

            if actions.size > 0:
                action_type_col = actions[:, :, 0].astype(np.int32, copy=False)
                action_type_counter = Counter(int(v) for v in action_type_col.reshape(-1).tolist())
                action_type_hist = {
                    _action_name(k): int(v)
                    for k, v in sorted(action_type_counter.items())
                }
                noop_share = float(action_type_counter.get(0, 0) / max(1, action_type_col.size))

                produce_mask = action_type_col == 4
                if np.any(produce_mask):
                    produce_counter = Counter(
                        int(v) for v in actions[:, :, 5][produce_mask].astype(np.int32).tolist()
                    )
                else:
                    produce_counter = Counter()

                attack_mask = action_type_col == 5
                if np.any(attack_mask):
                    attack_counter = Counter(
                        int(v) for v in actions[:, :, 6][attack_mask].astype(np.int32).tolist()
                    )
                else:
                    attack_counter = Counter()

                attack_diversity = {
                    "count": int(sum(attack_counter.values())),
                    "unique_targets": int(len(attack_counter)),
                    "max_target_index": int(max(attack_counter.keys())) if attack_counter else None,
                }

                produce_count = int(sum(produce_counter.values()))
                produce_unique = int(len(produce_counter))
                branch5_max = int(actions[:, :, 5].max())
                branch6_max = int(actions[:, :, 6].max())
            else:
                action_type_hist = {}
                noop_share = 0.0
                produce_counter = Counter()
                attack_counter = Counter()
                attack_diversity = {"count": 0, "unique_targets": 0, "max_target_index": None}
                produce_count = 0
                produce_unique = 0
                branch5_max = None
                branch6_max = None

            _warn_if(noop_share >= 0.98, warnings, f"high noop share: noop_share={noop_share:.6f}")
            _warn_if(produce_count == 0, warnings, "no produce actions")
            _warn_if(attack_diversity["count"] == 0, warnings, "no attack actions")
            _warn_if(produce_count > 0 and produce_unique <= 1, warnings, "low produce_unit_type diversity")
            _warn_if(
                attack_diversity["count"] > 0 and attack_diversity["unique_targets"] <= 3,
                warnings,
                "low attack_target_local diversity",
            )
            _warn_if(
                out_of_range_share > 0.0,
                warnings,
                f"observation values outside [0,1]: share={out_of_range_share:.10f}",
            )
            _warn_if(
                action_mask_share < 1.0,
                warnings,
                f"action_mask_available_share < 1.0 ({action_mask_share:.6f})",
            )
            _warn_if(
                branch5_max is not None and branch5_max <= 3,
                warnings,
                (
                    "branch 5 max <= 3 observed; this can reflect current policy behavior and is not, by itself, "
                    "evidence of remap"
                ),
            )
            _warn_if(
                branch6_max is not None and branch6_max <= 8,
                warnings,
                (
                    "branch 6 max <= 8 observed; this may indicate no far local targets selected and is not, by itself, "
                    "proof of remap without manifest or branch-size mismatch"
                ),
            )

    else:
        branch_min_max = []
        has_nan = False
        has_inf = False
        obs_min = None
        obs_max = None
        out_of_range_share = 0.0
        action_type_hist = {}
        produce_counter = Counter()
        attack_counter = Counter()
        attack_diversity = {"count": 0, "unique_targets": 0, "max_target_index": None}
        action_mask_share = 0.0

    status = "pass" if not hard_failures else "fail"
    decision = "GO_FOR_BC_READY_PACKAGER" if status == "pass" else "NO_GO"

    report: Dict[str, Any] = {
        "generated_at_utc": _now_iso(),
        "status": status,
        "adapted_dir": str(adapted_dir),
        "input_artifacts": {
            "adapted_dataset": str(adapted_dataset_path),
            "adapted_manifest": str(adapted_manifest_path),
        },
        "sample_count": int(observations.shape[0]) if observations.ndim > 0 else 0,
        "manifest_checks": manifest_checks,
        "dataset_checks": dataset_checks,
        "observation_shape": list(observations.shape),
        "action_shape": list(actions.shape),
        "observation_dtype": str(observations.dtype),
        "action_dtype": str(actions.dtype),
        "observation_min": obs_min,
        "observation_max": obs_max,
        "observation_out_of_range_share": float(out_of_range_share),
        "nan_inf_checks": {
            "observation_has_nan": bool(has_nan),
            "observation_has_inf": bool(has_inf),
        },
        "branch_min_max": branch_min_max,
        "action_type_histogram": action_type_hist,
        "produce_unit_type_histogram": _hist_to_sorted_dict(produce_counter),
        "attack_target_local_histogram": _hist_to_sorted_dict(attack_counter),
        "attack_target_local_diversity": attack_diversity,
        "action_mask_available_share": float(action_mask_share),
        "source_valid_action_mask": source_valid_action_mask_report,
        "hard_failures": hard_failures,
        "warnings": warnings,
        "decision": decision,
    }

    _json_dump(json_report_path, report)
    md_report_path.write_text(_build_markdown(report), encoding="utf-8")

    if bool(args.write_debug_json):
        debug_payload = {
            "generated_at_utc": _now_iso(),
            "notes": "Independent validation debug payload generated from adapted_dataset.npz and adapted_manifest.json.",
            "manifest_keys": sorted(list(manifest.keys())) if manifest else [],
            "dataset_keys_seen": sorted(list(np.load(str(adapted_dataset_path), allow_pickle=True).keys())) if adapted_dataset_path.exists() else [],
            "report_paths": {
                "json": str(json_report_path),
                "markdown": str(md_report_path),
            },
        }
        _json_dump(debug_report_path, debug_payload)

    print(
        json.dumps(
            {
                "status": status,
                "decision": decision,
                "json_report": str(json_report_path),
                "markdown_report": str(md_report_path),
                "debug_report": str(debug_report_path) if bool(args.write_debug_json) else None,
                "hard_failures_count": len(hard_failures),
                "warnings_count": len(warnings),
            },
            ensure_ascii=True,
            indent=2,
        )
    )

    if bool(args.fail_on_hard_errors) and hard_failures:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        traceback.print_exc()
        raise SystemExit(f"[validate_legacy032_unity_v2_dataset] ERROR: {exc}")
