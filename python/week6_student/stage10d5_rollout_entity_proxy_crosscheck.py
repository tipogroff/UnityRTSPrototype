#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _window_onehot_metrics(obs: np.ndarray, start: int, width: int) -> Dict[str, float]:
    grp = obs[:, :, start : start + width]
    sums = np.sum(grp, axis=2)
    return {
        "share_sum_eq_1": float(np.mean(np.isclose(sums, 1.0))),
        "share_sum_eq_0": float(np.mean(np.isclose(sums, 0.0))),
        "share_sum_le_1": float(np.mean(sums <= 1.0 + 1e-6)),
        "share_sum_gt_1": float(np.mean(sums > 1.0 + 1e-6)),
    }


def _resource_empty_proxies(flat_obs: np.ndarray, map_w: int = 24) -> Dict[str, np.ndarray]:
    # 24x24 map from known teacher config.
    resource_idx = np.array([0 * map_w + 0, 1 * map_w + 0, 22 * map_w + 23, 23 * map_w + 23], dtype=np.int32)
    empty_idx = np.array([12 * map_w + 12, 10 * map_w + 10, 13 * map_w + 13], dtype=np.int32)
    return {
        "resource_mask": np.isin(np.arange(flat_obs.shape[1]), resource_idx),
        "empty_mask": np.isin(np.arange(flat_obs.shape[1]), empty_idx),
    }


def _unit_type_window_score(flat_obs: np.ndarray, action_type: np.ndarray, start: int) -> Dict[str, Any]:
    width = 7
    grp = flat_obs[:, :, start : start + width]

    harvest = action_type == 2
    produce = action_type == 4
    attack = action_type == 5

    proxies = _resource_empty_proxies(flat_obs)
    resource_cell_mask = proxies["resource_mask"][None, :]
    empty_cell_mask = proxies["empty_mask"][None, :]

    def _mean(mask: np.ndarray) -> np.ndarray:
        if not np.any(mask):
            return np.zeros((width,), dtype=np.float32)
        return np.mean(grp[mask], axis=0)

    m_harvest = _mean(harvest)
    m_produce = _mean(produce)
    m_attack = _mean(attack)
    m_resource_cells = _mean(np.broadcast_to(resource_cell_mask, action_type.shape))
    m_empty_cells = _mean(np.broadcast_to(empty_cell_mask, action_type.shape))

    onehot = _window_onehot_metrics(flat_obs, start, width)

    worker_peak = int(np.argmax(m_harvest))
    base_peak = int(np.argmax(m_produce))
    combat_peak = int(np.argmax(m_attack))
    resource_peak = int(np.argmax(m_resource_cells))

    worker_margin = float(np.max(m_harvest) - np.partition(m_harvest, -2)[-2]) if np.any(m_harvest) else 0.0
    base_margin = float(np.max(m_produce) - np.partition(m_produce, -2)[-2]) if np.any(m_produce) else 0.0
    resource_margin = float(np.max(m_resource_cells) - np.partition(m_resource_cells, -2)[-2]) if np.any(m_resource_cells) else 0.0

    # Heuristic score: one-hot quality + proxy separability - multi-hot risk.
    score = (
        1.5 * onehot["share_sum_le_1"]
        + 0.8 * worker_margin
        + 0.8 * base_margin
        + 0.6 * resource_margin
        - 2.0 * onehot["share_sum_gt_1"]
    )

    return {
        "window": [int(start), int(start + width - 1)],
        "onehot_metrics": onehot,
        "worker_proxy_peak_local": worker_peak,
        "base_proxy_peak_local": base_peak,
        "combat_proxy_peak_local": combat_peak,
        "resource_proxy_peak_local": resource_peak,
        "worker_proxy_margin": worker_margin,
        "base_proxy_margin": base_margin,
        "resource_proxy_margin": resource_margin,
        "means": {
            "harvest_actor": [float(v) for v in m_harvest.tolist()],
            "produce_actor": [float(v) for v in m_produce.tolist()],
            "attack_actor": [float(v) for v in m_attack.tolist()],
            "resource_cells": [float(v) for v in m_resource_cells.tolist()],
            "empty_cells": [float(v) for v in m_empty_cells.tolist()],
        },
        "score": float(score),
    }


def _owner_window_score(flat_obs: np.ndarray, action_type: np.ndarray, start: int) -> Dict[str, Any]:
    width = 3
    grp = flat_obs[:, :, start : start + width]
    actor = action_type > 0

    onehot = _window_onehot_metrics(flat_obs, start, width)

    if np.any(actor):
        m_actor = np.mean(grp[actor], axis=0)
        dominant = int(np.argmax(m_actor))
        margin = float(np.max(m_actor) - np.partition(m_actor, -2)[-2])
    else:
        m_actor = np.zeros((width,), dtype=np.float32)
        dominant = -1
        margin = 0.0

    # map-based player cells for perspective consistency hints
    p0_cells = np.array([1 * 24 + 1, 2 * 24 + 2], dtype=np.int32)
    p1_cells = np.array([22 * 24 + 22, 21 * 24 + 21], dtype=np.int32)
    p0_mask = np.isin(np.arange(flat_obs.shape[1]), p0_cells)[None, :]
    p1_mask = np.isin(np.arange(flat_obs.shape[1]), p1_cells)[None, :]

    m_p0 = np.mean(grp[np.broadcast_to(p0_mask, action_type.shape)], axis=0)
    m_p1 = np.mean(grp[np.broadcast_to(p1_mask, action_type.shape)], axis=0)
    p0_idx = int(np.argmax(m_p0))
    p1_idx = int(np.argmax(m_p1))
    distinct = p0_idx != p1_idx

    score = 1.2 * onehot["share_sum_le_1"] + 0.8 * margin + (0.8 if distinct else 0.0) - 2.0 * onehot["share_sum_gt_1"]

    return {
        "window": [int(start), int(start + width - 1)],
        "onehot_metrics": onehot,
        "actor_dominant_local": dominant,
        "actor_margin": margin,
        "player0_peak_local": p0_idx,
        "player1_peak_local": p1_idx,
        "player_peaks_distinct": bool(distinct),
        "means": {
            "actor_cells": [float(v) for v in m_actor.tolist()],
            "player0_cells": [float(v) for v in m_p0.tolist()],
            "player1_cells": [float(v) for v in m_p1.tolist()],
        },
        "score": float(score),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.5 rollout entity proxy crosscheck")
    p.add_argument(
        "--raw-rollout-dir",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/teacher_rollouts/"
            "legacy032_3m_unity_v2_rollout_export_20260501T125015Z"
        ),
    )
    p.add_argument("--max-samples", type=int, default=4096)
    p.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d5_rollout_entity_proxy_crosscheck.json"),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = _repo_root()
    rollout_dir = _resolve(root, args.raw_rollout_dir)
    out_path = _resolve(root, args.output)

    npz_path = rollout_dir / "teacher_rollout_raw.npz"
    if not npz_path.exists():
        raise RuntimeError(f"missing rollout npz: {npz_path}")

    with np.load(npz_path, allow_pickle=False) as npz:
        obs = np.asarray(npz["observation_t"], dtype=np.float32)
        actions = np.asarray(npz["per_cell_action_t"], dtype=np.int16)

    n = min(int(args.max_samples), int(obs.shape[0]))
    obs_sample = obs[:n].reshape(n, 576, 27)
    actions_sample = actions[:n]
    action_type = actions_sample[:, :, 0]

    unit_rows: List[Dict[str, Any]] = []
    for start in range(0, 27 - 7 + 1):
        unit_rows.append(_unit_type_window_score(obs_sample, action_type, start))
    unit_rows.sort(key=lambda x: x["score"], reverse=True)

    owner_rows: List[Dict[str, Any]] = []
    for start in range(0, 27 - 3 + 1):
        owner_rows.append(_owner_window_score(obs_sample, action_type, start))
    owner_rows.sort(key=lambda x: x["score"], reverse=True)

    out: Dict[str, Any] = {
        "stage": "10D.5",
        "diagnostic": "rollout_entity_proxy_crosscheck",
        "status": "pass",
        "raw_rollout_npz": npz_path.as_posix(),
        "sample_n": int(n),
        "proxy_definitions": {
            "worker_proxy": "action_type == harvest (2)",
            "base_proxy": "action_type == produce (4)",
            "combat_proxy": "action_type == attack (5)",
            "resource_proxy": "known map resource cells from 24x24 basesWorkers map",
            "empty_proxy": "known empty map cells",
        },
        "owner_candidate_windows": owner_rows[:10],
        "unit_type_candidate_windows": unit_rows[:10],
        "supporting_evidence_only": True,
        "note": "Proxy-only crosscheck is not sufficient for final authorization without source/controlled evidence agreement.",
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=True, indent=2), encoding="utf-8")
    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
