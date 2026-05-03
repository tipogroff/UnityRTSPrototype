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
    p = argparse.ArgumentParser(description="Stage10D.3 adapter observation transform trace")
    p.add_argument(
        "--raw-rollout-dir",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/teacher_rollouts/"
            "legacy032_3m_unity_v2_rollout_export_20260501T125015Z"
        ),
    )
    p.add_argument(
        "--adapted-dir",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/teacher_adapted/"
            "legacy032_3m_unity_v2_adapted_20260501T161820Z"
        ),
    )
    p.add_argument(
        "--bc-ready-dir",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/teacher_exports_bc/"
            "day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z"
        ),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d3_adapter_observation_transform_trace.json"),
    )
    p.add_argument("--sample-trace-count", type=int, default=6)
    return p.parse_args()


def _vector_delta(a: np.ndarray, b: np.ndarray) -> Dict[str, Any]:
    d = b - a
    return {
        "l2": float(np.linalg.norm(d)),
        "max_abs": float(np.max(np.abs(d))),
        "nonzero_count": int(np.count_nonzero(np.abs(d) > 1e-8)),
    }


def _suspect_permutation(src: np.ndarray, dst: np.ndarray, max_rows: int = 200000) -> Dict[str, Any]:
    if src.shape[0] != dst.shape[0]:
        raise RuntimeError(f"Permutation probe shape mismatch: {src.shape} vs {dst.shape}")
    if src.shape[0] > max_rows:
        idx = np.linspace(0, src.shape[0] - 1, num=max_rows, dtype=np.int64)
        src = src[idx]
        dst = dst[idx]

    # Greedy correlation-based estimate, diagnostic only.
    corr = np.zeros((27, 27), dtype=np.float64)
    for i in range(27):
        s = src[:, i]
        s_std = np.std(s)
        for j in range(27):
            t = dst[:, j]
            t_std = np.std(t)
            if s_std < 1e-12 or t_std < 1e-12:
                corr[i, j] = 0.0
            else:
                corr[i, j] = float(np.corrcoef(s, t)[0, 1])

    used_j = set()
    mapping: List[int] = [-1] * 27
    score_sum = 0.0
    for i in range(27):
        order = np.argsort(corr[i])[::-1]
        pick = -1
        for j in order.tolist():
            if j not in used_j:
                pick = int(j)
                break
        if pick >= 0:
            mapping[i] = pick
            used_j.add(pick)
            score_sum += corr[i, pick]

    identity = all(mapping[i] == i for i in range(27))
    return {
        "estimated_mapping_src_to_dst": mapping,
        "average_correlation": float(score_sum / 27.0),
        "identity_mapping": bool(identity),
        "rows_used": int(src.shape[0]),
    }


def _build_key_index(episode_id: np.ndarray, step_id: np.ndarray) -> Dict[Tuple[int, int], int]:
    out: Dict[Tuple[int, int], int] = {}
    for i in range(int(episode_id.shape[0])):
        out[(int(episode_id[i]), int(step_id[i]))] = int(i)
    return out


def main() -> int:
    args = parse_args()
    root = _repo_root()
    raw_dir = _resolve(root, args.raw_rollout_dir)
    adapted_dir = _resolve(root, args.adapted_dir)
    bc_dir = _resolve(root, args.bc_ready_dir)
    out_path = _resolve(root, args.output)

    raw_npz = raw_dir / "teacher_rollout_raw.npz"
    adapted_npz = adapted_dir / "adapted_dataset.npz"
    bc_train = bc_dir / "bc_train.npz"
    bc_val = bc_dir / "bc_validation.npz"

    with np.load(raw_npz, allow_pickle=False) as r:
        raw_obs_hwc = np.asarray(r["observation_t"], dtype=np.float32)
        raw_ep = np.asarray(r["episode_id"], dtype=np.int32)
        raw_step = np.asarray(r["step_id"], dtype=np.int32)
    with np.load(adapted_npz, allow_pickle=False) as a:
        adapted_obs = np.asarray(a["observations"], dtype=np.float32)
        adapted_ep = np.asarray(a["episode_id"], dtype=np.int32)
        adapted_step = np.asarray(a["step_id"], dtype=np.int32)
    with np.load(bc_train, allow_pickle=False) as t:
        tr_obs = np.asarray(t["observations"], dtype=np.float32)
        tr_ep = np.asarray(t["episode_id"], dtype=np.int32)
        tr_step = np.asarray(t["step_id"], dtype=np.int32)
    with np.load(bc_val, allow_pickle=False) as v:
        va_obs = np.asarray(v["observations"], dtype=np.float32)
        va_ep = np.asarray(v["episode_id"], dtype=np.int32)
        va_step = np.asarray(v["step_id"], dtype=np.int32)

    raw_obs = raw_obs_hwc.reshape(raw_obs_hwc.shape[0], 576, 27)

    if raw_obs.shape != adapted_obs.shape:
        raise RuntimeError(f"raw vs adapted shape mismatch: {raw_obs.shape} vs {adapted_obs.shape}")

    raw_key_idx = _build_key_index(raw_ep, raw_step)
    adapted_key_idx = _build_key_index(adapted_ep, adapted_step)
    train_key_idx = _build_key_index(tr_ep, tr_step)
    val_key_idx = _build_key_index(va_ep, va_step)

    common_raw_adapt = set(raw_key_idx.keys()) & set(adapted_key_idx.keys())
    common_bc = (set(train_key_idx.keys()) | set(val_key_idx.keys())) & common_raw_adapt

    # Global transform diagnostics.
    raw_to_adapt = _vector_delta(raw_obs.reshape(-1, 27), adapted_obs.reshape(-1, 27))

    # Prepare matched sample traces.
    sorted_keys = sorted(common_bc)
    trace_count = min(int(args.sample_trace_count), len(sorted_keys))
    pick_keys = sorted_keys[:trace_count]

    traces: List[Dict[str, Any]] = []
    for key in pick_keys:
        epi, st = key
        ri = raw_key_idx[key]
        ai = adapted_key_idx[key]
        if key in train_key_idx:
            bi = train_key_idx[key]
            split = "train"
            bobs = tr_obs[bi]
        else:
            bi = val_key_idx[key]
            split = "validation"
            bobs = va_obs[bi]

        cells = [25, 50]
        cell_rows: List[Dict[str, Any]] = []
        for flat in cells:
            rvec = raw_obs[ri, flat, :]
            avec = adapted_obs[ai, flat, :]
            bvec = bobs[flat, :]
            cell_rows.append(
                {
                    "flat_index": int(flat),
                    "row": int(flat // 24),
                    "col": int(flat % 24),
                    "raw_vector": [float(x) for x in rvec.tolist()],
                    "adapted_vector": [float(x) for x in avec.tolist()],
                    "bc_ready_vector": [float(x) for x in bvec.tolist()],
                    "delta_raw_to_adapted": _vector_delta(rvec, avec),
                    "delta_adapted_to_bc_ready": _vector_delta(avec, bvec),
                    "delta_raw_to_bc_ready": _vector_delta(rvec, bvec),
                }
            )

        traces.append(
            {
                "episode_id": int(epi),
                "step_id": int(st),
                "raw_index": int(ri),
                "adapted_index": int(ai),
                "bc_split": split,
                "bc_index": int(bi),
                "cells": cell_rows,
            }
        )

    # BC preservation checks by keyed equality on sampled keys.
    sample_check_keys = sorted_keys[: min(512, len(sorted_keys))]
    mismatches = 0
    for key in sample_check_keys:
        ai = adapted_key_idx[key]
        if key in train_key_idx:
            bi = train_key_idx[key]
            bobs = tr_obs[bi]
        else:
            bi = val_key_idx[key]
            bobs = va_obs[bi]
        if not np.array_equal(adapted_obs[ai], bobs):
            mismatches += 1

    perm_raw_adapt = _suspect_permutation(raw_obs.reshape(-1, 27), adapted_obs.reshape(-1, 27))

    out: Dict[str, Any] = {
        "stage": "10D.3",
        "diagnostic": "adapter_observation_transform_trace",
        "paths": {
            "raw_rollout": raw_npz.as_posix(),
            "adapted_dataset": adapted_npz.as_posix(),
            "bc_train": bc_train.as_posix(),
            "bc_validation": bc_val.as_posix(),
        },
        "shape_checks": {
            "raw_obs_hwc": [int(x) for x in raw_obs_hwc.shape],
            "raw_obs_flat": [int(x) for x in raw_obs.shape],
            "adapted_obs": [int(x) for x in adapted_obs.shape],
            "bc_train_obs": [int(x) for x in tr_obs.shape],
            "bc_val_obs": [int(x) for x in va_obs.shape],
        },
        "key_alignment": {
            "raw_unique_ep_step": int(len(raw_key_idx)),
            "adapted_unique_ep_step": int(len(adapted_key_idx)),
            "bc_unique_ep_step": int(len(set(train_key_idx.keys()) | set(val_key_idx.keys()))),
            "common_raw_adapt": int(len(common_raw_adapt)),
            "common_bc": int(len(common_bc)),
        },
        "transform_diagnostics": {
            "raw_to_adapted": raw_to_adapt,
            "raw_to_adapted_equal": bool(np.array_equal(raw_obs, adapted_obs)),
            "suspected_channel_permutation_raw_to_adapted": perm_raw_adapt,
            "adapter_transform_classification": {
                "channel_copy": bool(np.array_equal(raw_obs, adapted_obs)),
                "channel_reorder": bool((not np.array_equal(raw_obs, adapted_obs)) and (not perm_raw_adapt["identity_mapping"])),
                "channel_truncation": False,
                "channel_semantic_rewrite": bool(not np.array_equal(raw_obs, adapted_obs)),
                "perspective_conversion": False,
                "notes": "Legacy032 adapter path reshapes observation_t to [N,576,27] without explicit channel remap.",
            },
        },
        "bc_packaging_preservation_check": {
            "sampled_key_count": int(len(sample_check_keys)),
            "sampled_mismatch_count": int(mismatches),
            "sampled_all_equal": bool(mismatches == 0),
            "note": "Equality sampled by (episode_id, step_id) keyed joins across adapted and BC splits.",
        },
        "sample_traces": traces,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=True, indent=2), encoding="utf-8")
    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
