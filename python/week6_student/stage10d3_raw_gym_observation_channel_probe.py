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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.3 raw Gym observation channel probe")
    p.add_argument(
        "--rollout-dir",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/teacher_rollouts/"
            "legacy032_3m_unity_v2_rollout_export_20260501T125015Z"
        ),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d3_raw_gym_observation_channel_probe.json"),
    )
    p.add_argument("--max-samples", type=int, default=2048)
    return p.parse_args()


def _stats_per_channel(rows: np.ndarray) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for ch in range(rows.shape[1]):
        v = rows[:, ch]
        uniq = np.unique(v)
        rec: Dict[str, Any] = {
            "channel": ch,
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
        out.append(rec)
    return out


def _one_hot_check(flat_obs: np.ndarray, start: int, end: int) -> Dict[str, Any]:
    grp = flat_obs[:, :, start:end]
    sums = np.sum(grp, axis=2)
    return {
        "range": [start, end - 1],
        "width": int(end - start),
        "sum_min": float(np.min(sums)),
        "sum_max": float(np.max(sums)),
        "share_sum_eq_1": float(np.mean(np.isclose(sums, 1.0))),
        "share_sum_eq_0": float(np.mean(np.isclose(sums, 0.0))),
        "share_sum_le_1": float(np.mean(sums <= 1.0 + 1e-6)),
    }


def _scan_candidate_windows(flat_obs: np.ndarray, width: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for start in range(0, 27 - width + 1):
        end = start + width
        rec = _one_hot_check(flat_obs, start, end)
        rec["start"] = int(start)
        rec["end"] = int(end - 1)
        out.append(rec)
    out.sort(key=lambda x: (x["share_sum_eq_1"], x["share_sum_le_1"]), reverse=True)
    return out


def _flat_to_row_col(flat_idx: int) -> Tuple[int, int]:
    return (flat_idx // 24, flat_idx % 24)


def _focus_dump(flat_obs: np.ndarray, actions: np.ndarray, flat_idx: int, sample_cap: int = 16) -> Dict[str, Any]:
    n = flat_obs.shape[0]
    row, col = _flat_to_row_col(flat_idx)
    vectors = flat_obs[:, flat_idx, :]
    action_type = actions[:, flat_idx, 0]
    hist = np.bincount(action_type.astype(np.int64), minlength=6)

    examples: List[Dict[str, Any]] = []
    k = min(sample_cap, n)
    for i in range(k):
        examples.append(
            {
                "sample_index": int(i),
                "flat_index": int(flat_idx),
                "row": int(row),
                "col": int(col),
                "obs_vector": [float(x) for x in vectors[i].tolist()],
                "label_branches": [int(x) for x in actions[i, flat_idx, :].tolist()],
            }
        )

    return {
        "flat_index": int(flat_idx),
        "row": int(row),
        "col": int(col),
        "count": int(n),
        "mean_vector": [float(x) for x in np.mean(vectors, axis=0).tolist()],
        "std_vector": [float(x) for x in np.std(vectors, axis=0).tolist()],
        "action_type_histogram": {str(i): int(v) for i, v in enumerate(hist.tolist())},
        "examples": examples,
    }


def main() -> int:
    args = parse_args()
    root = _repo_root()
    rollout_dir = _resolve(root, args.rollout_dir)
    out_path = _resolve(root, args.output)

    raw_npz_path = rollout_dir / "teacher_rollout_raw.npz"
    manifest_path = rollout_dir / "teacher_rollout_manifest.json"
    if not raw_npz_path.exists():
        raise RuntimeError(f"Missing raw rollout npz: {raw_npz_path}")
    if not manifest_path.exists():
        raise RuntimeError(f"Missing rollout manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    with np.load(raw_npz_path, allow_pickle=False) as npz:
        required = ["observation_t", "per_cell_action_t", "episode_id", "step_id"]
        for k in required:
            if k not in npz:
                raise RuntimeError(f"Missing key '{k}' in {raw_npz_path}")

        obs = np.asarray(npz["observation_t"], dtype=np.float32)
        actions = np.asarray(npz["per_cell_action_t"], dtype=np.int16)
        episode_id = np.asarray(npz["episode_id"], dtype=np.int32)
        step_id = np.asarray(npz["step_id"], dtype=np.int32)

    if obs.ndim != 4 or tuple(obs.shape[1:]) != (24, 24, 27):
        raise RuntimeError(f"Unexpected observation_t shape: {tuple(obs.shape)}")
    if actions.ndim != 3 or tuple(actions.shape[1:]) != (576, 7):
        raise RuntimeError(f"Unexpected per_cell_action_t shape: {tuple(actions.shape)}")

    n = int(obs.shape[0])
    flat_obs = obs.reshape(n, 576, 27)

    sample_n = min(int(args.max_samples), n)
    sampled_rows = flat_obs[:sample_n].reshape(-1, 27)

    candidate_groups = {
        "owner_width3": _scan_candidate_windows(flat_obs[:sample_n], 3)[:8],
        "unit_type_width7": _scan_candidate_windows(flat_obs[:sample_n], 7)[:8],
        "current_action_width6": _scan_candidate_windows(flat_obs[:sample_n], 6)[:8],
        "direction_width4": _scan_candidate_windows(flat_obs[:sample_n], 4)[:8],
    }

    declared_checks = {
        "owner_2_4": _one_hot_check(flat_obs[:sample_n], 2, 5),
        "unit_type_5_11": _one_hot_check(flat_obs[:sample_n], 5, 12),
        "current_action_12_17": _one_hot_check(flat_obs[:sample_n], 12, 18),
        "direction_18_21": _one_hot_check(flat_obs[:sample_n], 18, 22),
        "produce_type_22_25": _one_hot_check(flat_obs[:sample_n], 22, 26),
    }

    out: Dict[str, Any] = {
        "stage": "10D.3",
        "diagnostic": "raw_gym_observation_channel_probe",
        "rollout_dir": rollout_dir.as_posix(),
        "source_rollout_npz": raw_npz_path.as_posix(),
        "source_rollout_manifest": manifest_path.as_posix(),
        "manifest_contract": {
            "observation_shape": manifest.get("observation_shape"),
            "raw_action_nvec": manifest.get("raw_action_nvec"),
            "exported_per_cell_action_shape": manifest.get("exported_per_cell_action_shape"),
            "exported_per_cell_branch_sizes": manifest.get("exported_per_cell_branch_sizes"),
            "notes": manifest.get("notes"),
        },
        "observations": {
            "shape": [int(x) for x in obs.shape],
            "dtype": str(obs.dtype),
            "flattened_shape": [int(x) for x in flat_obs.shape],
            "channel_stats": _stats_per_channel(sampled_rows),
        },
        "actions": {
            "shape": [int(x) for x in actions.shape],
            "dtype": str(actions.dtype),
        },
        "sample_metadata": {
            "num_samples": int(n),
            "sampled_for_stats": int(sample_n),
            "first_episode_step_pairs": [
                {"sample_index": int(i), "episode_id": int(episode_id[i]), "step_id": int(step_id[i])}
                for i in range(min(12, n))
            ],
        },
        "empirical_channel_map_inference": {
            "candidate_one_hot_windows": candidate_groups,
            "declared_group_checks": declared_checks,
            "interpretation_note": (
                "Inference is empirical only. Candidate windows are ranked by one-hot behavior; "
                "this script does not enforce semantic parity with Unity contract."
            ),
        },
        "focus_cells": {
            "flat_25": _focus_dump(flat_obs, actions, 25),
            "flat_50": _focus_dump(flat_obs, actions, 50),
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=True, indent=2), encoding="utf-8")
    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
