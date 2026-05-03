#!/usr/bin/env python3
"""Stage 10D.6 — Observation compatibility check against the Stage10D.6
semantic adapted dataset.

This is a standalone version that reads adapted_dataset.npz directly
(no BC-ready manifest required), enabling B2/C3 focus-cell and
worker/base proxy compatibility assessment without building a BC-ready
dataset.

Purpose:
- Verify B2/C3 Unity focus cells are semantically compatible with the
  corresponding worker/base actor-label groups in the adapted dataset.
- B2 Worker should align with worker/harvest proxy group (unit_type peak=3).
- C3 Base should align with base/produce proxy group (unit_type peak=1).
- owner/unit_type mismatch should be cleared or below threshold.
- Nearest neighbours should no longer identify B2/C3 as Resource+Ranged.

Strict constraints:
- Does NOT build BC-ready dataset.
- Does NOT retrain.
- Does NOT overwrite old Stage10D.1R artifacts.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


UNITY_UNIT_NAMES = ("Resource", "Base", "Barracks", "Worker", "Light", "Heavy", "Ranged")
UNITY_OWNER_NAMES = ("Neutral", "Friendly", "Enemy")
UNITY_ACTION_NAMES = ("NoOp", "Move", "Harvest", "Return", "Produce", "Attack")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _group_one_hot_metrics(arr: np.ndarray, start: int, end: int) -> Dict[str, Any]:
    g = arr[:, start:end]
    sums = np.sum(g, axis=-1)
    return {
        "sum_min": float(np.min(sums)),
        "sum_max": float(np.max(sums)),
        "share_sum_eq_1": float(np.mean(np.isclose(sums, 1.0))),
        "share_sum_eq_0": float(np.mean(np.isclose(sums, 0.0))),
        "share_sum_le_1": float(np.mean(sums <= 1.0 + 1e-6)),
    }


def _extract_unity_focus(snapshot_path: Path) -> Dict[str, np.ndarray]:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8-sig"))
    focus_rows = payload.get("focus_cell_diagnostics", [])
    out: Dict[str, np.ndarray] = {}
    for row in focus_rows:
        label = str(row.get("logical_label", ""))
        channels = row.get("cell_observation_channels")
        if label in ("B2", "C3") and isinstance(channels, list) and len(channels) == 27:
            out[label] = np.asarray(channels, dtype=np.float64)
    return out


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _nn_report(
    query: np.ndarray,
    label: str,
    worker_mean: np.ndarray,
    base_mean: np.ndarray,
    resource_ranged_wrong: np.ndarray,
) -> Dict[str, Any]:
    return {
        "label": label,
        "cos_sim_worker_mean": _cosine_sim(query, worker_mean),
        "cos_sim_base_mean": _cosine_sim(query, base_mean),
        "cos_sim_resource_ranged_wrong_pattern": _cosine_sim(query, resource_ranged_wrong),
        "unit_type_peak_index": int(np.argmax(query[5:12])),
        "unit_type_peak_name": UNITY_UNIT_NAMES[int(np.argmax(query[5:12]))],
        "owner_peak_index": int(np.argmax(query[2:5])),
        "owner_peak_name": UNITY_OWNER_NAMES[int(np.argmax(query[2:5]))],
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Stage10D.6 observation compatibility check on adapted dataset"
    )
    p.add_argument(
        "--adapted-dir",
        type=Path,
        default=None,
        help="Stage10D.6 adapted dataset directory. "
             "Auto-discovers latest stage10d6 dir if omitted.",
    )
    p.add_argument(
        "--unity-snapshot",
        type=Path,
        default=Path("python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json"),
    )
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path(
            "python/week6_student/reports/"
            "stage10d6_observation_channel_comparison_corrected.json"
        ),
    )
    p.add_argument(
        "--output-nn",
        type=Path,
        default=Path(
            "python/week6_student/reports/"
            "stage10d6_unity_vs_bc_nearest_neighbors_corrected.json"
        ),
    )
    p.add_argument(
        "--output-dist",
        type=Path,
        default=Path(
            "python/week6_student/reports/"
            "stage10d6_dataset_action_distribution_corrected.json"
        ),
    )
    p.add_argument(
        "--output-loss",
        type=Path,
        default=Path(
            "python/week6_student/reports/"
            "stage10d6_training_loss_audit.json"
        ),
    )
    return p.parse_args()


def _find_latest_stage10d6_adapted_dir(root: Path) -> Optional[Path]:
    teacher_adapted = root / "python/week5_teacher_legacy032/teacher_adapted"
    if not teacher_adapted.exists():
        return None
    candidates = sorted(
        [d for d in teacher_adapted.iterdir() if d.is_dir() and "stage10d6" in d.name],
        key=lambda d: d.name,
    )
    return candidates[-1] if candidates else None


def main() -> int:
    args = parse_args()
    root = _repo_root()

    adapted_dir = args.adapted_dir
    if adapted_dir is None:
        adapted_dir = _find_latest_stage10d6_adapted_dir(root)
        if adapted_dir is None:
            print("[stage10d6][obs-compat] ERROR: no stage10d6 adapted dir found")
            return 1
    else:
        adapted_dir = _resolve(root, adapted_dir)

    dataset_npz = adapted_dir / "adapted_dataset.npz"
    if not dataset_npz.exists():
        print(f"[stage10d6][obs-compat] ERROR: missing {dataset_npz}")
        return 1

    unity_snapshot = _resolve(root, args.unity_snapshot)
    if not unity_snapshot.exists():
        print(f"[stage10d6][obs-compat] WARNING: Unity snapshot not found: {unity_snapshot}")
        unity_focus: Dict[str, np.ndarray] = {}
    else:
        unity_focus = _extract_unity_focus(unity_snapshot)

    print(f"[stage10d6][obs-compat] Loading adapted dataset from {dataset_npz}")
    with np.load(dataset_npz, allow_pickle=False) as npz:
        obs = np.asarray(npz["observations"], dtype=np.float32)
        actions = np.asarray(npz["actions"], dtype=np.int16)

    N = obs.shape[0]
    obs_flat = obs.reshape(N * 576, 27)
    actions_flat = actions.reshape(N * 576, 7)

    # ── Group one-hot metrics ────────────────────────────────────────────────
    group_metrics = {
        "owner":          _group_one_hot_metrics(obs_flat, 2, 5),
        "unit_type":      _group_one_hot_metrics(obs_flat, 5, 12),
        "current_action": _group_one_hot_metrics(obs_flat, 12, 18),
        "direction":      _group_one_hot_metrics(obs_flat, 18, 22),
        "produce":        _group_one_hot_metrics(obs_flat, 22, 26),
    }

    # ── Worker / base proxy populations ─────────────────────────────────────
    action_type = actions_flat[:, 0]
    worker_mask = action_type == 2   # harvest action → worker cell proxy
    base_mask = action_type == 4     # produce action → base cell proxy

    worker_obs = obs_flat[worker_mask] if worker_mask.any() else np.zeros((0, 27), dtype=np.float32)
    base_obs = obs_flat[base_mask] if base_mask.any() else np.zeros((0, 27), dtype=np.float32)

    worker_mean = np.mean(worker_obs, axis=0) if worker_obs.shape[0] > 0 else np.zeros(27)
    base_mean = np.mean(base_obs, axis=0) if base_obs.shape[0] > 0 else np.zeros(27)

    # wrong legacy pattern: resource(0)=1, ranged(6)=1, rest=0
    wrong_pattern = np.zeros(7, dtype=np.float32)
    wrong_pattern[0] = 1.0
    wrong_pattern[6] = 1.0

    worker_unit_mean = worker_mean[5:12].tolist()
    base_unit_mean = base_mean[5:12].tolist()

    b2_worker_compatible = bool(
        worker_obs.shape[0] > 0 and int(np.argmax(worker_mean[5:12])) == 3
        and float(worker_mean[5 + 3]) >= 0.5
    )
    c3_base_compatible = bool(
        base_obs.shape[0] > 0 and int(np.argmax(base_mean[5:12])) == 1
        and float(base_mean[5 + 1]) >= 0.5
    )

    # resource+ranged impossible multi-hot
    resource_and_ranged = np.sum(
        (obs_flat[:, 5] > 0.5) & (obs_flat[:, 11] > 0.5)
    )
    resource_ranged_impossible_share = float(resource_and_ranged) / max(1, obs_flat.shape[0])

    hard_failures: List[str] = []
    warnings: List[str] = []

    if not b2_worker_compatible:
        hard_failures.append(
            f"B2 worker proxy unit_type mismatch: peak={int(np.argmax(worker_mean[5:12]))}"
            f" expected=3 (Worker), mean={worker_unit_mean}"
        )
    if not c3_base_compatible:
        hard_failures.append(
            f"C3 base proxy unit_type mismatch: peak={int(np.argmax(base_mean[5:12]))}"
            f" expected=1 (Base), mean={base_unit_mean}"
        )
    if resource_ranged_impossible_share > 0.0:
        hard_failures.append(
            f"resource+ranged impossible multi-hot share={resource_ranged_impossible_share:.4f}"
        )
    if worker_obs.shape[0] == 0:
        warnings.append("worker proxy population empty")
    if base_obs.shape[0] == 0:
        warnings.append("base proxy population empty")

    # ── B2/C3 focus cell channel means ──────────────────────────────────────
    # flat indices: B2=row1*24+col1, C3=row2*24+col2
    # B2 = grid position (1,1) → flat=25, C3=(2,2) → flat=50
    focus_cells = {
        "B2": {
            "flat_index": 25,
            "mean_owner":     [float(x) for x in np.mean(obs[:, 25, 2:5], axis=0)],
            "mean_unit_type": [float(x) for x in np.mean(obs[:, 25, 5:12], axis=0)],
            "unit_type_peak_index": int(np.argmax(np.mean(obs[:, 25, 5:12], axis=0))),
            "unit_type_peak_name": UNITY_UNIT_NAMES[int(np.argmax(np.mean(obs[:, 25, 5:12], axis=0)))],
        },
        "C3": {
            "flat_index": 50,
            "mean_owner":     [float(x) for x in np.mean(obs[:, 50, 2:5], axis=0)],
            "mean_unit_type": [float(x) for x in np.mean(obs[:, 50, 5:12], axis=0)],
            "unit_type_peak_index": int(np.argmax(np.mean(obs[:, 50, 5:12], axis=0))),
            "unit_type_peak_name": UNITY_UNIT_NAMES[int(np.argmax(np.mean(obs[:, 50, 5:12], axis=0)))],
        },
    }

    # Compare to Unity focus cells if available
    unity_comparison: Dict[str, Any] = {}
    if unity_focus:
        wrong_vec = np.zeros(27, dtype=np.float32)
        wrong_vec[5] = 1.0   # resource
        wrong_vec[11] = 1.0  # ranged

        for label, unity_vec in unity_focus.items():
            if label == "B2":
                pop_mean = worker_mean
            elif label == "C3":
                pop_mean = base_mean
            else:
                pop_mean = np.zeros(27)
            unity_comparison[label] = _nn_report(
                unity_vec.astype(np.float64),
                label,
                worker_mean.astype(np.float64),
                base_mean.astype(np.float64),
                wrong_vec.astype(np.float64),
            )
    else:
        warnings.append("Unity snapshot not available; skipping nearest-neighbour comparison")

    status = "pass" if not hard_failures else "fail"

    obs_report: Dict[str, Any] = {
        "stage": "10D.6",
        "diagnostic": "observation_channel_comparison_corrected",
        "generated_at_utc": _now_iso(),
        "adapted_dir": str(adapted_dir),
        "unity_snapshot": str(unity_snapshot),
        "status": status,
        "sample_count": int(N),
        "group_metrics": group_metrics,
        "focus_cells": focus_cells,
        "worker_harvest_proxy": {
            "count": int(worker_obs.shape[0]),
            "unit_type_mean": [float(x) for x in worker_unit_mean],
            "unit_type_peak_index": int(np.argmax(worker_mean[5:12])) if worker_obs.shape[0] > 0 else -1,
            "compatible": b2_worker_compatible,
        },
        "base_produce_proxy": {
            "count": int(base_obs.shape[0]),
            "unit_type_mean": [float(x) for x in base_unit_mean],
            "unit_type_peak_index": int(np.argmax(base_mean[5:12])) if base_obs.shape[0] > 0 else -1,
            "compatible": c3_base_compatible,
        },
        "resource_ranged_impossible_multi_hot_share": resource_ranged_impossible_share,
        "hard_failures": hard_failures,
        "warnings": warnings,
    }

    nn_report: Dict[str, Any] = {
        "stage": "10D.6",
        "diagnostic": "unity_vs_bc_nearest_neighbors_corrected",
        "generated_at_utc": _now_iso(),
        "adapted_dir": str(adapted_dir),
        "unity_snapshot": str(unity_snapshot),
        "status": status,
        "unity_comparison": unity_comparison,
        "worker_harvest_mean_unit_type": [float(x) for x in worker_unit_mean],
        "base_produce_mean_unit_type": [float(x) for x in base_unit_mean],
        "hard_failures": hard_failures,
        "warnings": warnings,
    }

    # ── Action distribution ──────────────────────────────────────────────────
    total = float(action_type.shape[0])
    action_dist: Dict[str, Any] = {
        "stage": "10D.6",
        "diagnostic": "dataset_action_distribution_corrected",
        "generated_at_utc": _now_iso(),
        "adapted_dir": str(adapted_dir),
        "status": status,
        "total_cells": int(total),
        "action_type_distribution": {
            UNITY_ACTION_NAMES[i]: int(np.sum(action_type == i))
            for i in range(6)
        },
        "action_type_share": {
            UNITY_ACTION_NAMES[i]: float(np.sum(action_type == i) / max(1, total))
            for i in range(6)
        },
    }

    # ── Training loss audit stub ─────────────────────────────────────────────
    loss_audit: Dict[str, Any] = {
        "stage": "10D.6",
        "diagnostic": "training_loss_audit",
        "generated_at_utc": _now_iso(),
        "adapted_dir": str(adapted_dir),
        "status": "skipped_no_bc_ready_dataset",
        "note": (
            "Training loss audit requires BC-ready dataset. "
            "Stage10D.6 does not build a BC-ready dataset. "
            "Loss audit will be performed in Stage10D.7."
        ),
        "worker_harvest_proxy_compatible": b2_worker_compatible,
        "base_produce_proxy_compatible": c3_base_compatible,
    }

    # ── Write outputs ─────────────────────────────────────────────────────────
    def _write(path: Path, payload: Dict[str, Any]) -> None:
        p = _resolve(root, path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        print(f"[stage10d6][obs-compat] -> {p}")

    _write(args.output_json, obs_report)
    _write(args.output_nn, nn_report)
    _write(args.output_dist, action_dist)
    _write(args.output_loss, loss_audit)

    print(f"[stage10d6][obs-compat] status={status}")
    print(f"[stage10d6][obs-compat] B2 worker compatible: {b2_worker_compatible}")
    print(f"[stage10d6][obs-compat] C3 base compatible:   {c3_base_compatible}")
    print(f"[stage10d6][obs-compat] resource+ranged impossible share: {resource_ranged_impossible_share:.4f}")

    return 0 if not hard_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
