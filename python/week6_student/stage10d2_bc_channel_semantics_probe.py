#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np


EXPECTED_BRANCH_SIZES = [6, 4, 4, 4, 4, 7, 49]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage10D.2 BC channel semantics probe")
    parser.add_argument(
        "--bc-ready-dir",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/teacher_exports_bc/"
            "day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z"
        ),
    )
    parser.add_argument(
        "--max-examples-per-group",
        type=int,
        default=8,
    )
    parser.add_argument(
        "--max-unique-values",
        type=int,
        default=16,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d2_bc_channel_semantics_probe.json"),
    )
    return parser.parse_args()


def _resolve(repo_root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (repo_root / p)


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _discover_npz_keys(npz_path: Path) -> Dict[str, Any]:
    with np.load(npz_path, allow_pickle=False) as npz:
        keys = list(npz.files)
        obs_key = "input_tensor" if "input_tensor" in keys else ("observations" if "observations" in keys else None)
        act_key = "target_action_branches" if "target_action_branches" in keys else ("actions" if "actions" in keys else None)
        branch_key = "target_action_branch_sizes" if "target_action_branch_sizes" in keys else None
        return {
            "keys": keys,
            "obs_key": obs_key,
            "act_key": act_key,
            "branch_key": branch_key,
        }


def _normalize_obs(obs: np.ndarray) -> Tuple[np.ndarray, np.ndarray, str]:
    if obs.ndim != 3 and obs.ndim != 4:
        raise RuntimeError(f"Unsupported observation rank: {obs.ndim}")

    if obs.ndim == 3 and tuple(obs.shape[1:]) == (576, 27):
        n = int(obs.shape[0])
        obs_flat = obs.astype(np.float32, copy=False)
        obs_hwc = obs_flat.reshape(n, 24, 24, 27)
        return obs_flat, obs_hwc, "N_576_27"

    if obs.ndim == 4 and tuple(obs.shape[1:]) == (24, 24, 27):
        n = int(obs.shape[0])
        obs_hwc = obs.astype(np.float32, copy=False)
        obs_flat = obs_hwc.reshape(n, 576, 27)
        return obs_flat, obs_hwc, "N_24_24_27"

    raise RuntimeError(f"Unsupported observation sample shape: {tuple(obs.shape[1:])}")


def _channel_stats(flat: np.ndarray, max_unique_values: int) -> List[Dict[str, Any]]:
    rows = flat.reshape(-1, 27)
    out: List[Dict[str, Any]] = []
    for ch in range(27):
        v = rows[:, ch]
        uniques = np.unique(v)
        row: Dict[str, Any] = {
            "channel": ch,
            "min": float(np.min(v)),
            "max": float(np.max(v)),
            "mean": float(np.mean(v)),
            "std": float(np.std(v)),
            "nonzero_count": int(np.count_nonzero(np.abs(v) > 1e-12)),
            "total_count": int(v.size),
            "likely_binary": bool(np.all((v == 0.0) | (v == 1.0))),
        }
        if uniques.size <= max_unique_values:
            row["unique_values"] = [float(x) for x in uniques.tolist()]
        else:
            row["unique_values"] = None
            row["unique_values_count"] = int(uniques.size)
        out.append(row)
    return out


def _one_hot_group_check(flat: np.ndarray, start: int, end_exclusive: int) -> Dict[str, Any]:
    grp = flat[:, :, start:end_exclusive]
    sums = np.sum(grp, axis=2)
    return {
        "range": [start, end_exclusive - 1],
        "sum_min": float(np.min(sums)),
        "sum_max": float(np.max(sums)),
        "share_sum_eq_1": float(np.mean(np.isclose(sums, 1.0))),
        "share_sum_eq_0": float(np.mean(np.isclose(sums, 0.0))),
        "share_sum_between_0_1": float(np.mean((sums >= 0.0) & (sums <= 1.0))),
    }


def _sample_examples(
    obs_flat: np.ndarray,
    actions: np.ndarray,
    mask: np.ndarray,
    max_examples: int,
) -> List[Dict[str, Any]]:
    idx = np.argwhere(mask)
    if idx.size == 0:
        return []
    examples: List[Dict[str, Any]] = []
    for s, f in idx[:max_examples]:
        cell_obs = obs_flat[int(s), int(f), :]
        label = actions[int(s), int(f), :]
        row = int(f) // 24
        col = int(f) % 24
        examples.append(
            {
                "sample_index": int(s),
                "flat_index": int(f),
                "row": int(row),
                "col": int(col),
                "observation_channels": [float(x) for x in cell_obs.tolist()],
                "label_branches": [int(x) for x in label.tolist()],
            }
        )
    return examples


def _group_probe(
    obs_flat: np.ndarray,
    actions: np.ndarray,
    max_examples: int,
) -> Dict[str, Any]:
    action_type = actions[:, :, 0]

    groups: Dict[str, np.ndarray] = {
        "own_worker_cells": action_type == 2,
        "own_base_cells": action_type == 4,
        "own_actor_cells": np.isin(action_type, np.asarray([2, 3, 4, 5], dtype=np.int16)),
        "resource_like_cells": (action_type == 0) & np.all(actions[:, :, 1:] == 0, axis=2),
        "non_noop_label_cells": action_type != 0,
        "empty_noop_cells": action_type == 0,
        "action_type_harvest": action_type == 2,
        "action_type_produce": action_type == 4,
    }

    out: Dict[str, Any] = {}
    for name, mask in groups.items():
        count = int(np.count_nonzero(mask))
        payload: Dict[str, Any] = {"count": count}
        if count > 0:
            selected = obs_flat[mask]
            payload["channel_mean"] = [float(x) for x in np.mean(selected, axis=0).tolist()]
            payload["channel_std"] = [float(x) for x in np.std(selected, axis=0).tolist()]
        else:
            payload["channel_mean"] = []
            payload["channel_std"] = []
        payload["examples"] = _sample_examples(obs_flat, actions, mask, max_examples)
        out[name] = payload

    for target_flat in (25, 50):
        lbl = f"flat_index_{target_flat}"
        per_cell_labels = actions[:, target_flat, :]
        action_hist = np.bincount(per_cell_labels[:, 0].astype(np.int64), minlength=6)
        out[lbl] = {
            "count": int(per_cell_labels.shape[0]),
            "action_type_histogram": {str(i): int(v) for i, v in enumerate(action_hist.tolist())},
            "examples": _sample_examples(
                obs_flat,
                actions,
                np.eye(576, dtype=bool)[target_flat][None, :].repeat(obs_flat.shape[0], axis=0),
                max_examples,
            ),
        }

    return out


def _split_probe(npz_path: Path, max_examples: int, max_unique_values: int) -> Dict[str, Any]:
    key_info = _discover_npz_keys(npz_path)
    if key_info["obs_key"] is None or key_info["act_key"] is None:
        raise RuntimeError(f"Could not discover observation/actions keys in {npz_path}")

    with np.load(npz_path, allow_pickle=False) as npz:
        obs = np.asarray(npz[key_info["obs_key"]])
        actions = np.asarray(npz[key_info["act_key"]])
        branch_sizes = None
        if key_info["branch_key"] is not None:
            branch_sizes = [int(x) for x in np.asarray(npz[key_info["branch_key"]]).reshape(-1).tolist()]

    obs_flat, obs_hwc, obs_variant = _normalize_obs(obs)
    if actions.ndim != 3 or tuple(actions.shape[1:]) != (576, 7):
        raise RuntimeError(f"Unexpected action shape in {npz_path}: {tuple(actions.shape)}")

    return {
        "file": npz_path.as_posix(),
        "npz_keys": key_info["keys"],
        "selected_obs_key": key_info["obs_key"],
        "selected_action_key": key_info["act_key"],
        "obs_shape_original": [int(x) for x in obs.shape],
        "obs_shape_variant": obs_variant,
        "obs_shape_as_flat": [int(x) for x in obs_flat.shape],
        "obs_shape_as_hwc": [int(x) for x in obs_hwc.shape],
        "action_shape": [int(x) for x in actions.shape],
        "branch_sizes_from_npz": branch_sizes,
        "channel_stats": _channel_stats(obs_flat, max_unique_values),
        "one_hot_checks": {
            "owner_2_4": _one_hot_group_check(obs_flat, 2, 5),
            "unit_type_5_11": _one_hot_group_check(obs_flat, 5, 12),
            "current_action_12_17": _one_hot_group_check(obs_flat, 12, 18),
            "direction_18_21": _one_hot_group_check(obs_flat, 18, 22),
            "produce_type_22_25": _one_hot_group_check(obs_flat, 22, 26),
        },
        "semantic_label_proxy_groups": _group_probe(obs_flat, actions, max_examples),
    }


def main() -> int:
    args = parse_args()
    root = _repo_root()
    bc_ready_dir = _resolve(root, args.bc_ready_dir)
    out_path = _resolve(root, args.output)

    manifest_path = bc_ready_dir / "bc_manifest.json"
    train_path = bc_ready_dir / "bc_train.npz"
    val_path = bc_ready_dir / "bc_validation.npz"

    if not manifest_path.exists() or not train_path.exists() or not val_path.exists():
        missing = [p.as_posix() for p in (manifest_path, train_path, val_path) if not p.exists()]
        raise RuntimeError(f"Missing required BC-ready artifacts: {missing}")

    manifest = _load_json(manifest_path)
    manifest_branch_sizes = [int(x) for x in manifest.get("branch_sizes", [])]

    train_probe = _split_probe(train_path, args.max_examples_per_group, args.max_unique_values)
    val_probe = _split_probe(val_path, args.max_examples_per_group, args.max_unique_values)

    payload: Dict[str, Any] = {
        "stage": "10D.2",
        "diagnostic": "bc_channel_semantics_probe",
        "dataset_dir": bc_ready_dir.as_posix(),
        "contract_checks": {
            "manifest_observation_shape_per_sample": manifest.get("observation_shape_per_sample"),
            "manifest_action_shape_per_sample": manifest.get("action_shape_per_sample"),
            "manifest_branch_sizes": manifest_branch_sizes,
            "expected_branch_sizes": EXPECTED_BRANCH_SIZES,
            "branch_sizes_match_expected": manifest_branch_sizes == EXPECTED_BRANCH_SIZES,
        },
        "splits": {
            "train": train_probe,
            "validation": val_probe,
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
