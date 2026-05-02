#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np

from student_bc_loader import load_bc_ready_dataset

ACTION_NAMES: Tuple[str, ...] = ("NoOp", "Move", "Harvest", "Return", "Produce", "Attack")
EXPECTED_BRANCH_SIZES_V2: Tuple[int, ...] = (6, 4, 4, 4, 4, 7, 49)
EXPECTED_OBS_SHAPE: Tuple[int, int] = (576, 27)
EXPECTED_TARGET_SHAPE: Tuple[int, int] = (576, 7)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage10D.1 dataset action distribution diagnostic")
    parser.add_argument(
        "--bc-ready-dir",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/teacher_exports_bc/"
            "day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d1_dataset_action_distribution.json"),
    )
    return parser.parse_args()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _print_npz_keys(npz_path: Path) -> None:
    with np.load(npz_path, allow_pickle=False) as npz_data:
        print(f"[stage10d1][keys] {npz_path.as_posix()} -> {list(npz_data.files)}")


def _is_actor_unit(channel_slice: np.ndarray) -> np.ndarray:
    # unit_base..unit_ranged indices [6..11]
    return np.any(channel_slice[..., 6:12] > 0.5, axis=-1)


def _is_worker(channel_slice: np.ndarray) -> np.ndarray:
    return channel_slice[..., 8] > 0.5


def _is_base(channel_slice: np.ndarray) -> np.ndarray:
    return channel_slice[..., 6] > 0.5


def _is_own(channel_slice: np.ndarray) -> np.ndarray:
    # Diagnostic-derived ownership from absolute owner channels.
    return channel_slice[..., 3] > 0.5


def _is_neutral(channel_slice: np.ndarray) -> np.ndarray:
    return channel_slice[..., 2] > 0.5


def _cells_near_any(mask_24x24: np.ndarray, target_24x24: np.ndarray) -> np.ndarray:
    h, w = mask_24x24.shape
    out = np.zeros((h, w), dtype=bool)
    target_rc = np.argwhere(target_24x24)
    if target_rc.size == 0:
        return out
    for r, c in np.argwhere(mask_24x24):
        dr = np.abs(target_rc[:, 0] - r)
        dc = np.abs(target_rc[:, 1] - c)
        out[r, c] = np.any((dr + dc) <= 1)
    return out


def _new_group_counters() -> Dict[str, Dict[str, Any]]:
    groups = (
        "all_576_cells",
        "own_actor_cells",
        "own_worker_cells",
        "own_base_cells",
        "worker_cells_near_resource",
        "worker_cells_near_own_base",
        "base_cells_with_produce_like_possibility",
        "cells_with_non_noop_labels",
        "active_eligible_actor_cells",
    )
    out: Dict[str, Dict[str, Any]] = {}
    for g in groups:
        out[g] = {
            "total_count": 0,
            "action_type_count": {name: 0 for name in ACTION_NAMES},
        }
    return out


def _accumulate(counters: Dict[str, Dict[str, Any]], group: str, action_values: np.ndarray) -> None:
    total = int(action_values.size)
    counters[group]["total_count"] += total
    if total == 0:
        return
    binc = np.bincount(action_values, minlength=len(ACTION_NAMES))
    for idx, name in enumerate(ACTION_NAMES):
        counters[group]["action_type_count"][name] += int(binc[idx])


def _finalize(counters: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for group, payload in counters.items():
        total = int(payload["total_count"])
        counts = dict(payload["action_type_count"])
        shares = {k: (float(v) / total if total > 0 else 0.0) for k, v in counts.items()}
        out[group] = {
            "total_count": total,
            "action_type_count": counts,
            "action_type_share": shares,
        }
    return out


def _select_masks(obs_flat: np.ndarray, action_type: np.ndarray) -> Dict[str, np.ndarray]:
    own = _is_own(obs_flat)
    neutral = _is_neutral(obs_flat)
    actor = _is_actor_unit(obs_flat)
    worker = _is_worker(obs_flat)
    base = _is_base(obs_flat)

    own_worker_channel = own & worker
    own_base_channel = own & base
    own_actor_channel = own & actor
    active_actor_channel = (~neutral) & actor

    channel_has_worker = bool(np.any(own_worker_channel))
    channel_has_base = bool(np.any(own_base_channel))

    if channel_has_worker and channel_has_base:
        return {
            "own_actor": own_actor_channel,
            "own_worker": own_worker_channel,
            "own_base": own_base_channel,
            "active_eligible_actor": active_actor_channel,
            "mode": np.asarray(["channel_derived"]),
        }

    # Fallback when owner/unit channels are non-informative.
    own_worker_proxy = action_type == 2
    own_base_proxy = action_type == 4
    own_actor_proxy = np.isin(action_type, np.asarray([2, 3, 4, 5], dtype=np.int64))

    return {
        "own_actor": own_actor_proxy,
        "own_worker": own_worker_proxy,
        "own_base": own_base_proxy,
        "active_eligible_actor": own_actor_proxy,
        "mode": np.asarray(["label_proxy"]),
    }


def _iter_split_stats(inputs: np.ndarray, targets: np.ndarray) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    counters = _new_group_counters()
    channel_mode_count = {"channel_derived": 0, "label_proxy": 0}

    for sample_idx in range(inputs.shape[0]):
        obs = inputs[sample_idx]
        y = targets[sample_idx]

        _require(obs.shape == (24, 24, 27), f"Unexpected sample obs shape: {obs.shape}")
        _require(y.shape == (576, 7), f"Unexpected sample target shape: {y.shape}")

        obs_flat = obs.reshape(576, 27)
        action_type = y[:, 0].astype(np.int64)

        masks = _select_masks(obs_flat, action_type)
        own_actor = masks["own_actor"]
        own_worker = masks["own_worker"]
        own_base = masks["own_base"]
        active_eligible_actor = masks["active_eligible_actor"]
        channel_mode_count[str(masks["mode"][0])] += 1

        obs_grid = obs
        worker_grid = own_worker.reshape(24, 24)
        resource_grid = (obs_grid[:, :, 5] > 0.5)
        own_base_grid = own_base.reshape(24, 24)

        near_resource = _cells_near_any(worker_grid, resource_grid).reshape(576)
        near_own_base = _cells_near_any(worker_grid, own_base_grid).reshape(576)

        # Diagnostic proxy: base cells where Produce appears in labels.
        base_produce_like = own_base & (action_type == 4)
        non_noop = action_type != 0

        _accumulate(counters, "all_576_cells", action_type)
        _accumulate(counters, "own_actor_cells", action_type[own_actor])
        _accumulate(counters, "own_worker_cells", action_type[own_worker])
        _accumulate(counters, "own_base_cells", action_type[own_base])
        _accumulate(counters, "worker_cells_near_resource", action_type[near_resource])
        _accumulate(counters, "worker_cells_near_own_base", action_type[near_own_base])
        _accumulate(counters, "base_cells_with_produce_like_possibility", action_type[base_produce_like])
        _accumulate(counters, "cells_with_non_noop_labels", action_type[non_noop])
        _accumulate(counters, "active_eligible_actor_cells", action_type[active_eligible_actor])

    return _finalize(counters), {
        "sample_count": int(inputs.shape[0]),
        "mask_mode_counts": {
            "channel_derived": int(channel_mode_count["channel_derived"]),
            "label_proxy": int(channel_mode_count["label_proxy"]),
        },
    }


def main() -> int:
    args = parse_args()
    dataset = load_bc_ready_dataset(args.bc_ready_dir)

    # Key discovery is mandatory for diagnostics.
    _print_npz_keys(dataset.train.path)
    _print_npz_keys(dataset.validation.path)

    manifest = dataset.manifest_payload
    branch_sizes = tuple(int(x) for x in manifest.get("branch_sizes", []))
    obs_shape = tuple(int(x) for x in manifest.get("observation_shape_per_sample", []))
    target_shape = tuple(int(x) for x in manifest.get("action_shape_per_sample", []))

    _require(branch_sizes == EXPECTED_BRANCH_SIZES_V2, (
        "Contract version mismatch: expected Unity v2 branch sizes "
        f"{EXPECTED_BRANCH_SIZES_V2}, got {branch_sizes}."
    ))
    _require(obs_shape == EXPECTED_OBS_SHAPE, (
        "Observation shape mismatch for Unity v2 dataset: expected "
        f"{EXPECTED_OBS_SHAPE}, got {obs_shape}."
    ))
    _require(target_shape == EXPECTED_TARGET_SHAPE, (
        "Target shape mismatch for Unity v2 dataset: expected "
        f"{EXPECTED_TARGET_SHAPE}, got {target_shape}."
    ))

    train_stats, train_mask_quality = _iter_split_stats(dataset.train.input_tensor, dataset.train.target_action_branches)
    val_stats, val_mask_quality = _iter_split_stats(dataset.validation.input_tensor, dataset.validation.target_action_branches)

    combined: Dict[str, Dict[str, Any]] = {}
    for group in train_stats.keys():
        total = train_stats[group]["total_count"] + val_stats[group]["total_count"]
        counts = {
            action: train_stats[group]["action_type_count"][action] + val_stats[group]["action_type_count"][action]
            for action in ACTION_NAMES
        }
        shares = {k: (float(v) / total if total > 0 else 0.0) for k, v in counts.items()}
        combined[group] = {
            "total_count": int(total),
            "action_type_count": counts,
            "action_type_share": shares,
        }

    payload = {
        "stage": "10D.1",
        "diagnostic": "dataset_action_distribution",
        "dataset_dir": str(dataset.run_dir),
        "contract_check": {
            "target_action_contract": manifest.get("target_action_contract"),
            "branch_sizes": list(branch_sizes),
            "observation_shape_per_sample": list(obs_shape),
            "action_shape_per_sample": list(target_shape),
            "unity_v2_compatible": True,
        },
        "group_definitions": {
            "note": (
                "Actor/eligibility masks are diagnostic-derived. If owner/unit channels are non-informative, label-proxy masks are used and reported explicitly."
            ),
            "all_576_cells": "Every grid cell in each sample.",
            "own_actor_cells": "Primary: owner_player1 AND actor unit channels(base/barracks/worker/light/heavy/ranged). Fallback: label proxy action_type in {Harvest,Return,Produce,Attack}.",
            "own_worker_cells": "Primary: owner_player1 AND unit_worker. Fallback: label proxy action_type==Harvest.",
            "own_base_cells": "Primary: owner_player1 AND unit_base. Fallback: label proxy action_type==Produce.",
            "worker_cells_near_resource": "own_worker cells with Manhattan distance <= 1 to any resource cell.",
            "worker_cells_near_own_base": "own_worker cells with Manhattan distance <= 1 to any own_base cell.",
            "base_cells_with_produce_like_possibility": (
                "Diagnostic proxy: own_base cells where label action_type==Produce."
            ),
            "cells_with_non_noop_labels": "Cells where label action_type != NoOp.",
            "active_eligible_actor_cells": "Primary: non-neutral owner AND actor unit channels. Fallback: same as label-proxy actor mask.",
        },
        "mask_quality": {
            "train": train_mask_quality,
            "validation": val_mask_quality,
        },
        "split_stats": {
            "train": train_stats,
            "validation": val_stats,
            "combined": combined,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(args.output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
