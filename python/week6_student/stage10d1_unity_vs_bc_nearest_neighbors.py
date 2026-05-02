#!/usr/bin/env python3
from __future__ import annotations

import argparse
import heapq
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from student_bc_loader import load_bc_ready_dataset

EXPECTED_BRANCH_SIZES_V2: Tuple[int, ...] = (6, 4, 4, 4, 4, 7, 49)
ACTION_NAMES = ("NoOp", "Move", "Harvest", "Return", "Produce", "Attack")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage10D.1 Unity vs BC nearest-neighbor diagnostic")
    parser.add_argument(
        "--bc-ready-dir",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/teacher_exports_bc/"
            "day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z"
        ),
    )
    parser.add_argument(
        "--unity-snapshot",
        type=Path,
        default=Path("python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json"),
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d1_unity_vs_bc_nearest_neighbors.json"),
    )
    return parser.parse_args()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _print_npz_keys(npz_path: Path) -> None:
    with np.load(npz_path, allow_pickle=False) as npz_data:
        print(f"[stage10d1][keys] {npz_path.as_posix()} -> {list(npz_data.files)}")


def _owner_label(v: np.ndarray) -> str:
    owner_idx = int(np.argmax(v[2:5]))
    return ("Neutral", "Player1", "Player2")[owner_idx]


def _unit_label(v: np.ndarray) -> str:
    unit_names = ("Resource", "Base", "Barracks", "Worker", "Light", "Heavy", "Ranged")
    return unit_names[int(np.argmax(v[5:12]))]


def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 1e-12:
        return 1.0
    return float(1.0 - (np.dot(a, b) / denom))


def _channel_summary(v: np.ndarray) -> Dict[str, Any]:
    nz = np.where(np.abs(v) > 1e-6)[0].astype(int).tolist()
    return {
        "non_zero_indices": nz,
        "owner": v[2:5].astype(float).tolist(),
        "unit_type": v[5:12].astype(float).tolist(),
        "current_action": v[12:18].astype(float).tolist(),
        "direction": v[18:22].astype(float).tolist(),
        "produce": v[22:26].astype(float).tolist(),
        "attack_target": float(v[26]),
    }


def _make_heap_record(
    dist: float,
    split: str,
    sample_idx: int,
    flat_idx: int,
    obs_vec: np.ndarray,
    label7: np.ndarray,
) -> Dict[str, Any]:
    row = flat_idx // 24
    col = flat_idx % 24
    action_type_idx = int(label7[0])
    action_type_name = ACTION_NAMES[action_type_idx] if 0 <= action_type_idx < len(ACTION_NAMES) else "Unknown"
    return {
        "split": split,
        "sample_index": int(sample_idx),
        "flat_index": int(flat_idx),
        "grid_position": [int(row), int(col)],
        "distance": float(dist),
        "detected_owner": _owner_label(obs_vec),
        "detected_unit_type": _unit_label(obs_vec),
        "action_type_label": {"id": int(action_type_idx), "name": action_type_name},
        "full_7_branch_label": [int(x) for x in label7.tolist()],
        "channel_summary": _channel_summary(obs_vec),
    }


def _filtered_indices(obs_flat: np.ndarray, y_flat: np.ndarray, focus: str) -> Tuple[np.ndarray, str]:
    own = obs_flat[:, 3] > 0.5
    unit_worker = obs_flat[:, 8] > 0.5
    unit_base = obs_flat[:, 6] > 0.5
    actor = np.any(obs_flat[:, 6:12] > 0.5, axis=1)

    if focus == "B2":
        channel_idxs = np.where(own & unit_worker & actor)[0]
        if channel_idxs.size > 0:
            return channel_idxs, "channel_derived"
        return np.where(y_flat[:, 0] == 2)[0], "label_proxy_action_type_harvest"
    if focus == "C3":
        channel_idxs = np.where(own & unit_base & actor)[0]
        if channel_idxs.size > 0:
            return channel_idxs, "channel_derived"
        return np.where(y_flat[:, 0] == 4)[0], "label_proxy_action_type_produce"
    raise RuntimeError(f"Unknown focus label: {focus}")


def _topk_search(
    *,
    split_name: str,
    inputs: np.ndarray,
    targets: np.ndarray,
    query_vec: np.ndarray,
    focus_label: str,
    top_k: int,
    metric: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    heap: List[Tuple[float, int, Dict[str, Any]]] = []
    mode_counts: Dict[str, int] = {}
    seq = 0

    for sample_idx in range(inputs.shape[0]):
        obs_flat = inputs[sample_idx].reshape(576, 27)
        y_flat = targets[sample_idx]
        idxs, mode = _filtered_indices(obs_flat, y_flat, focus_label)
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        if idxs.size == 0:
            continue

        vectors = obs_flat[idxs].astype(np.float64)
        if metric == "l2":
            dists = np.linalg.norm(vectors - query_vec[None, :], axis=1)
        elif metric == "cosine":
            dists = np.asarray([_cosine_distance(vec, query_vec) for vec in vectors], dtype=np.float64)
        else:
            raise RuntimeError(f"Unsupported metric: {metric}")

        for local_i, flat_idx in enumerate(idxs.tolist()):
            d = float(dists[local_i])
            rec = _make_heap_record(
                d,
                split_name,
                sample_idx,
                int(flat_idx),
                obs_flat[flat_idx],
                y_flat[flat_idx],
            )
            key = -d
            if len(heap) < top_k:
                heapq.heappush(heap, (key, seq, rec))
            elif key > heap[0][0]:
                heapq.heapreplace(heap, (key, seq, rec))
            seq += 1

    result = [item[2] for item in sorted(heap, key=lambda kv: kv[2]["distance"])]
    return result, mode_counts


def _extract_focus_vectors(snapshot_path: Path) -> Dict[str, np.ndarray]:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8-sig"))
    focus_rows = payload.get("focus_cell_diagnostics", [])
    out: Dict[str, np.ndarray] = {}
    for row in focus_rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("logical_label", ""))
        channels = row.get("cell_observation_channels")
        if label in ("B2", "C3") and isinstance(channels, list) and len(channels) == 27:
            out[label] = np.asarray(channels, dtype=np.float64)
    _require("B2" in out and "C3" in out, "Unity snapshot missing B2/C3 27-channel vectors")
    return out


def main() -> int:
    args = parse_args()
    dataset = load_bc_ready_dataset(args.bc_ready_dir)
    _print_npz_keys(dataset.train.path)
    _print_npz_keys(dataset.validation.path)

    manifest = dataset.manifest_payload
    branch_sizes = tuple(int(x) for x in manifest.get("branch_sizes", []))
    _require(
        branch_sizes == EXPECTED_BRANCH_SIZES_V2,
        f"Contract version mismatch: expected {EXPECTED_BRANCH_SIZES_V2}, got {branch_sizes}",
    )

    unity_vecs = _extract_focus_vectors(args.unity_snapshot)

    output: Dict[str, Any] = {
        "stage": "10D.1",
        "diagnostic": "unity_vs_bc_nearest_neighbors",
        "dataset_dir": str(dataset.run_dir),
        "unity_snapshot": str(args.unity_snapshot),
        "top_k": int(args.top_k),
        "contract_check": {
            "branch_sizes": list(branch_sizes),
            "unity_v2_compatible": True,
        },
        "focus_cells": {},
    }

    for focus_label in ("B2", "C3"):
        focus_payload: Dict[str, Any] = {
            "query_channel_vector": unity_vecs[focus_label].astype(float).tolist(),
            "prioritized_population": "own_worker_actor_cells" if focus_label == "B2" else "own_base_actor_cells",
            "neighbors": {
                "l2": {},
                "cosine": {},
            },
        }

        for metric in ("l2", "cosine"):
            train_rows, train_modes = _topk_search(
                split_name="train",
                inputs=dataset.train.input_tensor,
                targets=dataset.train.target_action_branches,
                query_vec=unity_vecs[focus_label],
                focus_label=focus_label,
                top_k=args.top_k,
                metric=metric,
            )
            val_rows, val_modes = _topk_search(
                split_name="validation",
                inputs=dataset.validation.input_tensor,
                targets=dataset.validation.target_action_branches,
                query_vec=unity_vecs[focus_label],
                focus_label=focus_label,
                top_k=args.top_k,
                metric=metric,
            )
            focus_payload["neighbors"][metric]["train"] = train_rows
            focus_payload["neighbors"][metric]["validation"] = val_rows
            focus_payload["neighbors"][metric]["candidate_mask_modes"] = {
                "train": train_modes,
                "validation": val_modes,
            }

        output["focus_cells"][focus_label] = focus_payload

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=True, indent=2), encoding="utf-8")
    print(args.output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
