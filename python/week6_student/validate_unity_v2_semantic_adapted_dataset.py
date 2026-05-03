#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np


GROUPS = {
    "owner": (2, 5),
    "unit_type": (5, 12),
    "current_action": (12, 18),
    "direction": (18, 22),
    "produce": (22, 26),
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _json_dump(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _group_one_hot_metrics(obs: np.ndarray, start: int, end: int) -> Dict[str, Any]:
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
    lines.append("# Stage10D.4 Semantic Adapted Dataset Validation")
    lines.append("")
    lines.append(f"- status: {report['status']}")
    lines.append(f"- adapted_dir: {report['adapted_dir']}")
    lines.append(f"- sample_count: {report['sample_count']}")
    lines.append("")
    lines.append("## Core Checks")
    for k, v in report["core_checks"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Group Metrics")
    for k, v in report["group_metrics"].items():
        lines.append(
            f"- {k}: share_sum_eq_1={v['share_sum_eq_1']}, share_sum_eq_0={v['share_sum_eq_0']}, share_sum_le_1={v['share_sum_le_1']}, binary_values_only={v['binary_values_only']}"
        )
    lines.append("")
    lines.append("## Focus Cells")
    lines.append(f"- B2(flat=25): {report['focus_cells']['B2']}")
    lines.append(f"- C3(flat=50): {report['focus_cells']['C3']}")
    lines.append("")
    lines.append("## Proxy Compatibility")
    for k, v in report["actor_label_proxy_compatibility"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Warnings")
    for w in report["warnings"]:
        lines.append(f"- {w}")
    if not report["warnings"]:
        lines.append("- none")
    lines.append("")
    lines.append("## Hard Failures")
    for h in report["hard_failures"]:
        lines.append(f"- {h}")
    if not report["hard_failures"]:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate Stage10D.4 semantic adapted dataset")
    p.add_argument("--adapted-dir", type=Path, required=True)
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d4_semantic_adapted_dataset_validation.json"),
    )
    p.add_argument(
        "--output-md",
        type=Path,
        default=Path("python/week6_student/reports/stage10d4_semantic_adapted_dataset_validation.md"),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = _repo_root()
    adapted_dir = _resolve(root, args.adapted_dir)
    out_json = _resolve(root, args.output_json)
    out_md = _resolve(root, args.output_md)

    dataset = adapted_dir / "adapted_dataset.npz"
    manifest_file = adapted_dir / "adapted_manifest.json"

    hard_failures: List[str] = []
    warnings: List[str] = []

    if not dataset.exists():
        raise RuntimeError(f"Missing dataset: {dataset}")
    if not manifest_file.exists():
        hard_failures.append(f"missing manifest: {manifest_file}")

    manifest = {}
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

    with np.load(dataset, allow_pickle=False) as npz:
        obs = np.asarray(npz["observations"], dtype=np.float32)
        actions = np.asarray(npz["actions"], dtype=np.int16)

    core_checks = {
        "shape_expected_[N,576,27]": bool(obs.ndim == 3 and tuple(obs.shape[1:]) == (576, 27)),
        "dtype_float32": bool(obs.dtype == np.float32),
        "no_nan": bool(not np.isnan(obs).any()),
        "no_inf": bool(not np.isinf(obs).any()),
        "value_range_0_1": bool(np.all(obs >= 0.0) and np.all(obs <= 1.0)),
    }
    for k, v in core_checks.items():
        if not v:
            hard_failures.append(f"core check failed: {k}")

    group_metrics = {k: _group_one_hot_metrics(obs, v[0], v[1]) for k, v in GROUPS.items()}

    for name, m in group_metrics.items():
        if not m["share_sum_le_1"] == 1.0:
            hard_failures.append(f"group {name} has multi-hot cells")

    focus_cells = {
        "B2": {
            "mean_owner": [float(x) for x in np.mean(obs[:, 25, 2:5], axis=0).tolist()],
            "mean_unit_type": [float(x) for x in np.mean(obs[:, 25, 5:12], axis=0).tolist()],
        },
        "C3": {
            "mean_owner": [float(x) for x in np.mean(obs[:, 50, 2:5], axis=0).tolist()],
            "mean_unit_type": [float(x) for x in np.mean(obs[:, 50, 5:12], axis=0).tolist()],
        },
    }

    a0 = actions[:, :, 0]
    wmask = a0 == 2
    bmask = a0 == 4

    if np.any(wmask):
        worker_mean = np.mean(obs[:, :, 5:12][wmask], axis=0)
    else:
        worker_mean = np.zeros((7,), dtype=np.float32)
        warnings.append("worker proxy population empty")

    if np.any(bmask):
        base_mean = np.mean(obs[:, :, 5:12][bmask], axis=0)
    else:
        base_mean = np.zeros((7,), dtype=np.float32)
        warnings.append("base proxy population empty")

    legacy_wrong_pattern = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], dtype=np.float32)
    worker_l2_wrong = float(np.linalg.norm(worker_mean - legacy_wrong_pattern))
    base_l2_wrong = float(np.linalg.norm(base_mean - legacy_wrong_pattern))

    worker_compatible = bool(np.argmax(worker_mean) == 3 and worker_mean[3] >= 0.5)
    base_compatible = bool(np.argmax(base_mean) == 1 and base_mean[1] >= 0.5)

    actor_label_proxy_compatibility = {
        "worker_harvest_proxy": {
            "count": int(np.count_nonzero(wmask)),
            "unit_type_mean": [float(x) for x in worker_mean.tolist()],
            "expected_unity_peak_index": 3,
            "compatible": worker_compatible,
            "l2_from_legacy_wrong_pattern": worker_l2_wrong,
        },
        "base_produce_proxy": {
            "count": int(np.count_nonzero(bmask)),
            "unit_type_mean": [float(x) for x in base_mean.tolist()],
            "expected_unity_peak_index": 1,
            "compatible": base_compatible,
            "l2_from_legacy_wrong_pattern": base_l2_wrong,
        },
    }

    if not worker_compatible:
        hard_failures.append("worker/harvest proxy remains semantically incompatible with Unity unit_type")
    if not base_compatible:
        hard_failures.append("base/produce proxy remains semantically incompatible with Unity unit_type")

    if "critical_unavailable_channels" in manifest and manifest["critical_unavailable_channels"]:
        warnings.append(
            "manifest reports critical unavailable channels: "
            + str(manifest.get("critical_unavailable_channels"))
        )

    status = "pass" if not hard_failures else "fail"

    report = {
        "stage": "10D.4",
        "diagnostic": "semantic_adapted_dataset_validation",
        "adapted_dir": adapted_dir.as_posix(),
        "status": status,
        "sample_count": int(obs.shape[0]),
        "core_checks": core_checks,
        "group_metrics": group_metrics,
        "focus_cells": focus_cells,
        "actor_label_proxy_compatibility": actor_label_proxy_compatibility,
        "manifest_observation_semantics_version": manifest.get("observation_semantics_version"),
        "hard_failures": hard_failures,
        "warnings": warnings,
    }

    _json_dump(out_json, report)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_md(report), encoding="utf-8")

    print(out_json.as_posix())
    print(out_md.as_posix())

    return 0 if not hard_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
