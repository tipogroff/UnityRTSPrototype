#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _one_hot_metrics(flat_obs: np.ndarray, start: int, end: int) -> Dict[str, Any]:
    grp = flat_obs[:, :, start:end]
    sums = np.sum(grp, axis=2)
    return {
        "start": int(start),
        "end": int(end - 1),
        "width": int(end - start),
        "sum_min": float(np.min(sums)),
        "sum_max": float(np.max(sums)),
        "share_sum_eq_1": float(np.mean(np.isclose(sums, 1.0))),
        "share_sum_eq_0": float(np.mean(np.isclose(sums, 0.0))),
        "share_sum_le_1": float(np.mean(sums <= 1.0 + 1e-6)),
    }


def _window_scan(flat_obs: np.ndarray, width: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for start in range(0, 27 - width + 1):
        rec = _one_hot_metrics(flat_obs, start, start + width)
        rows.append(rec)
    rows.sort(key=lambda x: (x["share_sum_eq_1"], x["share_sum_le_1"]), reverse=True)
    return rows


def _action_window_alignment(flat_obs: np.ndarray, actions: np.ndarray, start: int, width: int) -> Dict[str, Any]:
    logits = flat_obs[:, :, start : start + width].reshape(-1, width)
    labels = actions[:, :, 0].reshape(-1)
    pred = np.argmax(logits, axis=1)

    counts = np.bincount(labels.astype(np.int64), minlength=width)
    baseline = float(np.max(counts) / max(1, int(labels.shape[0])))
    acc = float(np.mean(pred == labels))

    per_class: Dict[str, Any] = {}
    for k in range(width):
        m = labels == k
        if np.any(m):
            per_class[str(k)] = {
                "count": int(np.count_nonzero(m)),
                "accuracy": float(np.mean(pred[m] == labels[m])),
            }
        else:
            per_class[str(k)] = {"count": 0, "accuracy": None}

    return {
        "window": [int(start), int(start + width - 1)],
        "accuracy": acc,
        "majority_baseline": baseline,
        "lift_over_baseline": float(acc - baseline),
        "per_class": per_class,
    }


def _derive_expected_direction(actions: np.ndarray) -> np.ndarray:
    action_type = actions[:, :, 0]
    out = np.full(action_type.shape, -1, dtype=np.int16)

    move = action_type == 1
    harvest = action_type == 2
    ret = action_type == 3
    produce = action_type == 4

    out[move] = actions[:, :, 1][move]
    out[harvest] = actions[:, :, 2][harvest]
    out[ret] = actions[:, :, 3][ret]
    out[produce] = actions[:, :, 4][produce]
    return out


def _direction_window_alignment(flat_obs: np.ndarray, actions: np.ndarray, start: int, width: int) -> Dict[str, Any]:
    expected_dir = _derive_expected_direction(actions).reshape(-1)
    valid = expected_dir >= 0

    logits = flat_obs[:, :, start : start + width].reshape(-1, width)
    pred = np.argmax(logits, axis=1)

    if not np.any(valid):
        return {
            "window": [int(start), int(start + width - 1)],
            "valid_count": 0,
            "accuracy": None,
            "majority_baseline": None,
            "lift_over_baseline": None,
        }

    labels = expected_dir[valid]
    pred_v = pred[valid]
    counts = np.bincount(labels.astype(np.int64), minlength=width)
    baseline = float(np.max(counts) / max(1, int(labels.shape[0])))
    acc = float(np.mean(pred_v == labels))

    return {
        "window": [int(start), int(start + width - 1)],
        "valid_count": int(labels.shape[0]),
        "accuracy": acc,
        "majority_baseline": baseline,
        "lift_over_baseline": float(acc - baseline),
    }


def _focus_summary(flat_obs: np.ndarray, actions: np.ndarray, flat_idx: int) -> Dict[str, Any]:
    vec = flat_obs[:, flat_idx, :]
    action_type = actions[:, flat_idx, 0]

    rec: Dict[str, Any] = {
        "flat_index": int(flat_idx),
        "row": int(flat_idx // 24),
        "col": int(flat_idx % 24),
        "count": int(vec.shape[0]),
        "action_type_histogram": {
            str(i): int(v)
            for i, v in enumerate(np.bincount(action_type.astype(np.int64), minlength=6).tolist())
        },
    }

    proxy_defs = {
        "worker_proxy_harvest": action_type == 2,
        "base_proxy_produce": action_type == 4,
    }
    proxy_stats: Dict[str, Any] = {}
    for name, mask in proxy_defs.items():
        if np.any(mask):
            m = np.mean(vec[mask], axis=0)
            top = np.argsort(m)[::-1][:8]
            proxy_stats[name] = {
                "count": int(np.count_nonzero(mask)),
                "top_channels_by_mean": [
                    {"channel": int(i), "mean": float(m[i])} for i in top.tolist()
                ],
            }
        else:
            proxy_stats[name] = {"count": 0, "top_channels_by_mean": []}

    rec["proxy_stats"] = proxy_stats
    return rec


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.4 infer legacy032 raw channel semantics")
    p.add_argument(
        "--raw-rollout-dir",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/teacher_rollouts/"
            "legacy032_3m_unity_v2_rollout_export_20260501T125015Z"
        ),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d4_inferred_legacy032_raw_channel_semantics.json"),
    )
    p.add_argument("--max-samples", type=int, default=4096)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = _repo_root()
    rollout_dir = _resolve(root, args.raw_rollout_dir)
    out_path = _resolve(root, args.output)

    raw_npz = rollout_dir / "teacher_rollout_raw.npz"
    if not raw_npz.exists():
        raise RuntimeError(f"Missing rollout npz: {raw_npz}")

    with np.load(raw_npz, allow_pickle=False) as npz:
        obs = np.asarray(npz["observation_t"], dtype=np.float32)
        actions = np.asarray(npz["per_cell_action_t"], dtype=np.int16)

    if obs.ndim != 4 or tuple(obs.shape[1:]) != (24, 24, 27):
        raise RuntimeError(f"Unexpected observation shape: {obs.shape}")
    if actions.ndim != 3 or tuple(actions.shape[1:]) != (576, 7):
        raise RuntimeError(f"Unexpected per_cell_action_t shape: {actions.shape}")

    n = int(obs.shape[0])
    sample_n = min(int(args.max_samples), n)
    obs_sample = obs[:sample_n].reshape(sample_n, 576, 27)
    actions_sample = actions[:sample_n]

    rows = obs_sample.reshape(-1, 27)
    channel_stats = []
    for ch in range(27):
        v = rows[:, ch]
        uniq = np.unique(v)
        rec: Dict[str, Any] = {
            "channel": int(ch),
            "min": float(np.min(v)),
            "max": float(np.max(v)),
            "mean": float(np.mean(v)),
            "std": float(np.std(v)),
            "nonzero_share": float(np.mean(np.abs(v) > 1e-12)),
            "likely_binary": bool(np.all((v == 0.0) | (v == 1.0))),
        }
        if uniq.size <= 16:
            rec["unique_values"] = [float(x) for x in uniq.tolist()]
        else:
            rec["unique_values_count"] = int(uniq.size)
        channel_stats.append(rec)

    owner_scan = _window_scan(obs_sample, 3)
    unit_scan = _window_scan(obs_sample, 7)
    action_scan = _window_scan(obs_sample, 6)
    dir_scan = _window_scan(obs_sample, 4)

    action_alignment = []
    for start in range(0, 27 - 6 + 1):
        item = _action_window_alignment(obs_sample, actions_sample, start, 6)
        metrics = _one_hot_metrics(obs_sample, start, start + 6)
        item["one_hot_share_sum_eq_1"] = metrics["share_sum_eq_1"]
        action_alignment.append(item)
    action_alignment.sort(
        key=lambda x: (x["one_hot_share_sum_eq_1"], x["lift_over_baseline"]), reverse=True
    )

    direction_alignment = []
    for start in range(0, 27 - 4 + 1):
        item = _direction_window_alignment(obs_sample, actions_sample, start, 4)
        metrics = _one_hot_metrics(obs_sample, start, start + 4)
        item["one_hot_share_sum_eq_1"] = metrics["share_sum_eq_1"]
        direction_alignment.append(item)
    direction_alignment.sort(
        key=lambda x: (x["one_hot_share_sum_eq_1"], x.get("lift_over_baseline") or -1.0),
        reverse=True,
    )

    out: Dict[str, Any] = {
        "stage": "10D.4",
        "diagnostic": "infer_legacy032_raw_channel_semantics",
        "raw_rollout_dir": rollout_dir.as_posix(),
        "raw_rollout_npz": raw_npz.as_posix(),
        "input_shape": [int(x) for x in obs.shape],
        "sample_n": int(sample_n),
        "channel_stats": channel_stats,
        "candidate_one_hot_windows": {
            "owner_width3_top": owner_scan[:12],
            "unit_type_width7_top": unit_scan[:12],
            "current_action_width6_top": action_scan[:12],
            "direction_width4_top": dir_scan[:12],
        },
        "label_proxy_alignment": {
            "current_action_window_ranked": action_alignment[:12],
            "direction_window_ranked": direction_alignment[:12],
        },
        "focus_cells": {
            "flat_25": _focus_summary(obs_sample, actions_sample, 25),
            "flat_50": _focus_summary(obs_sample, actions_sample, 50),
        },
        "inference_notes": [
            "Inference is empirical and label-proxy assisted.",
            "This output does not claim exact source-code parity for Legacy032 raw channels.",
            "Top windows are ranking candidates only and must be reconciled via explicit mapping spec approval."
        ],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=True, indent=2), encoding="utf-8")
    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
