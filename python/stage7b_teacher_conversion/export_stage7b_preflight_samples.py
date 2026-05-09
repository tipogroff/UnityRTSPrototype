#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np


DEFAULT_DATASET_DIR = Path(
    "python/week5_teacher_legacy032/teacher_exports_bc/"
    "day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z"
)


def _load_split(npz_path: Path) -> Tuple[np.ndarray, np.ndarray, Dict[str, np.ndarray], Dict[str, str]]:
    with np.load(npz_path, allow_pickle=True) as npz:
        keys = list(npz.keys())
        obs_key = "observations"
        act_key = "actions"
        if obs_key not in npz or act_key not in npz:
            raise KeyError(
                f"{npz_path.name}: strict format requires keys ['observations','actions'], found {keys}"
            )

        obs = np.asarray(npz[obs_key])
        act = np.asarray(npz[act_key])

        metadata: Dict[str, np.ndarray] = {}
        for k in ("sample_id", "episode_id", "step_id", "source_episode_file"):
            if k in npz:
                metadata[k] = np.asarray(npz[k])

        detected = {
            "observation_key": obs_key,
            "action_key": act_key,
        }

    return obs, act, metadata, detected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export compact Stage7B preflight sample preview from BC-ready dataset.")
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--split", choices=["train", "validation", "debug"], default="debug")
    parser.add_argument("--max-samples", type=int, default=512)
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=Path("python/stage7b_teacher_conversion/stage7b_teacher_candidate_dataset_preview.jsonl"),
    )
    return parser.parse_args()


def _shape_to_hwc_or_flat(obs_sample: np.ndarray) -> np.ndarray:
    if obs_sample.ndim == 3 and obs_sample.shape == (24, 24, 27):
        return obs_sample
    if obs_sample.ndim == 2 and obs_sample.shape == (576, 27):
        return obs_sample.reshape(24, 24, 27)
    if obs_sample.ndim == 1 and obs_sample.size == 15552:
        return obs_sample.reshape(24, 24, 27)
    raise ValueError(f"Unsupported observation sample shape: {list(obs_sample.shape)}")


def main() -> int:
    args = parse_args()
    split_path = args.dataset_dir / f"bc_{args.split}.npz"
    obs, act, meta, detected = _load_split(split_path)

    if obs.shape[0] != act.shape[0]:
        raise ValueError("Observation/action sample count mismatch")

    count = min(int(args.max_samples), int(obs.shape[0]))
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)

    with args.output_jsonl.open("w", encoding="utf-8") as f:
        for i in range(count):
            obs_hwc = _shape_to_hwc_or_flat(np.asarray(obs[i]))
            action = np.asarray(act[i])
            if action.shape != (576, 7):
                raise ValueError(f"Unsupported action sample shape: {list(action.shape)}")

            action_type = action[:, 0]
            nonnoop = int(np.count_nonzero(action_type != 0))

            row: Dict[str, Any] = {
                "split": args.split,
                "index": int(i),
                "sample_id": str(meta["sample_id"][i]) if "sample_id" in meta else None,
                "episode_id": int(meta["episode_id"][i]) if "episode_id" in meta else None,
                "step_id": int(meta["step_id"][i]) if "step_id" in meta else None,
                "observation_shape_detected": [24, 24, 27],
                "observation_nan_count": int(np.isnan(obs_hwc).sum()),
                "observation_inf_count": int(np.isinf(obs_hwc).sum()),
                "observation_min": float(np.min(obs_hwc)),
                "observation_max": float(np.max(obs_hwc)),
                "teacher_nonnoop_actor_count": nonnoop,
                "teacher_action_type_histogram": {
                    str(k): int(v)
                    for k, v in zip(*np.unique(action_type, return_counts=True))
                },
                "detected_observation_key": detected["observation_key"],
                "detected_action_key": detected["action_key"],
            }
            f.write(json.dumps(row, ensure_ascii=True) + "\n")

    print(
        json.dumps(
            {
                "status": "ok",
                "split": args.split,
                "samples_written": count,
                "output_jsonl": str(args.output_jsonl),
                "source_npz": str(split_path),
                "detected": detected,
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
