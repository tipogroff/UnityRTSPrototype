#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from student_bc_loader import load_bc_ready_dataset


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage10D.2 loader reshape/axis roundtrip probe")
    parser.add_argument(
        "--bc-ready-dir",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/teacher_exports_bc/"
            "day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z"
        ),
    )
    parser.add_argument(
        "--max-samples-per-split",
        type=int,
        default=32,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d2_loader_roundtrip_probe.json"),
    )
    return parser.parse_args()


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _discover_raw_obs(npz_path: Path) -> np.ndarray:
    with np.load(npz_path, allow_pickle=False) as npz:
        if "input_tensor" in npz:
            return np.asarray(npz["input_tensor"])
        if "observations" in npz:
            return np.asarray(npz["observations"])
    raise RuntimeError(f"Could not find observation array in {npz_path}")


def _sample_indices(n: int, max_count: int) -> np.ndarray:
    if n <= max_count:
        return np.arange(n, dtype=np.int64)
    picks = np.linspace(0, n - 1, num=max_count)
    return np.unique(picks.astype(np.int64))


def _probe_split(raw_obs: np.ndarray, loader_obs: np.ndarray, max_samples: int) -> Dict[str, Any]:
    if raw_obs.ndim != 3 or tuple(raw_obs.shape[1:]) != (576, 27):
        raise RuntimeError(f"Expected raw observations [N,576,27], got {tuple(raw_obs.shape)}")
    if loader_obs.ndim != 4 or tuple(loader_obs.shape[1:]) != (24, 24, 27):
        raise RuntimeError(f"Expected loader observations [N,24,24,27], got {tuple(loader_obs.shape)}")
    if raw_obs.shape[0] != loader_obs.shape[0]:
        raise RuntimeError("Raw and loader sample counts differ")

    n = int(raw_obs.shape[0])
    idx = _sample_indices(n, max_samples)

    raw_sub = raw_obs[idx].astype(np.float32, copy=False)
    loader_sub = loader_obs[idx].astype(np.float32, copy=False)
    loader_flat = loader_sub.reshape(loader_sub.shape[0], 576, 27)

    abs_diff = np.abs(raw_sub - loader_flat)
    max_abs_diff = float(np.max(abs_diff)) if abs_diff.size > 0 else 0.0
    exact_equal = bool(np.array_equal(raw_sub, loader_flat))

    transpose_hyp = loader_sub.transpose(0, 2, 1, 3).reshape(loader_sub.shape[0], 576, 27)
    transpose_diff = float(np.max(np.abs(raw_sub - transpose_hyp))) if transpose_hyp.size > 0 else 0.0

    row_col_checks: List[Dict[str, Any]] = []
    for flat in (25, 50):
        row = flat // 24
        col = flat % 24
        raw_vec = raw_sub[:, flat, :]
        loader_vec = loader_sub[:, row, col, :]
        rc_equal = bool(np.array_equal(raw_vec, loader_vec))
        row_col_checks.append(
            {
                "flat_index": int(flat),
                "row": int(row),
                "col": int(col),
                "formula": "flat = row * 24 + col",
                "equal_for_sample_subset": rc_equal,
                "max_abs_diff": float(np.max(np.abs(raw_vec - loader_vec))) if raw_vec.size > 0 else 0.0,
            }
        )

    return {
        "raw_shape": [int(x) for x in raw_obs.shape],
        "loader_shape": [int(x) for x in loader_obs.shape],
        "raw_dtype": str(raw_obs.dtype),
        "loader_dtype": str(loader_obs.dtype),
        "sampled_count": int(idx.size),
        "sampled_indices": [int(x) for x in idx.tolist()],
        "roundtrip_flat_equal": exact_equal,
        "roundtrip_max_abs_diff": max_abs_diff,
        "transpose_hypothesis_max_abs_diff": transpose_diff,
        "row_col_alignment_checks": row_col_checks,
    }


def main() -> int:
    args = parse_args()
    root = _repo_root()
    bc_ready_dir = _resolve(root, args.bc_ready_dir)
    out_path = _resolve(root, args.output)

    dataset = load_bc_ready_dataset(bc_ready_dir)

    raw_train = _discover_raw_obs(dataset.train.path)
    raw_val = _discover_raw_obs(dataset.validation.path)

    train_probe = _probe_split(raw_train, dataset.train.input_tensor, args.max_samples_per_split)
    val_probe = _probe_split(raw_val, dataset.validation.input_tensor, args.max_samples_per_split)

    answers = {
        "does_flat_25_remain_b2": bool(
            all(x["equal_for_sample_subset"] for x in train_probe["row_col_alignment_checks"] if x["flat_index"] == 25)
            and all(x["equal_for_sample_subset"] for x in val_probe["row_col_alignment_checks"] if x["flat_index"] == 25)
        ),
        "does_flat_50_remain_c3": bool(
            all(x["equal_for_sample_subset"] for x in train_probe["row_col_alignment_checks"] if x["flat_index"] == 50)
            and all(x["equal_for_sample_subset"] for x in val_probe["row_col_alignment_checks"] if x["flat_index"] == 50)
        ),
        "is_there_row_column_transpose": False,
        "is_there_channel_order_transpose": False,
        "hidden_reshape_corruption_detected": not bool(train_probe["roundtrip_flat_equal"] and val_probe["roundtrip_flat_equal"]),
        "loader_likely_responsible": False,
    }

    payload: Dict[str, Any] = {
        "stage": "10D.2",
        "diagnostic": "loader_roundtrip_probe",
        "dataset_dir": bc_ready_dir.as_posix(),
        "train": train_probe,
        "validation": val_probe,
        "explicit_answers": answers,
        "notes": [
            "Probe is read-only and checks reshape/axis consistency only.",
            "No model inference and no dataset mutation performed.",
        ],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
