#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from stage10d_owner_semantics import (
    normalize_owner_modes,
    owner_labels_for_mode,
    resolve_owner_mode_from_snapshot,
)
from student_bc_loader import load_bc_ready_dataset

EXPECTED_BRANCH_SIZES_V2: Tuple[int, ...] = (6, 4, 4, 4, 4, 7, 49)
ACTION_NAMES = ("NoOp", "Move", "Harvest", "Return", "Produce", "Attack")
UNIT_NAMES = ("Resource", "Base", "Barracks", "Worker", "Light", "Heavy", "Ranged")
CUR_ACTION_NAMES = ("NoOp", "Move", "Harvest", "Return", "Produce", "Attack")


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
        "--owner-mode",
        type=str,
        default="both",
        choices=("absolute_player_channels", "perspective_friendly_enemy", "both", "auto"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d1_unity_vs_bc_nearest_neighbors.json"),
    )
    parser.add_argument(
        "--stage10d1r-output",
        action="store_true",
        help="Write Stage10D.1R corrected artifact filename.",
    )
    return parser.parse_args()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _print_npz_keys(npz_path: Path) -> None:
    with np.load(npz_path, allow_pickle=False) as npz_data:
        print(f"[stage10d1][keys] {npz_path.as_posix()} -> {list(npz_data.files)}")


def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 1e-12:
        return 1.0
    return float(1.0 - (np.dot(a, b) / denom))


def _interpret_owner(obs_vec: np.ndarray, owner_mode: str) -> str:
    labels = owner_labels_for_mode(owner_mode)  # type: ignore[arg-type]
    idx = int(np.argmax(obs_vec[2:5]))
    return labels[idx]


def _interpret_unit(obs_vec: np.ndarray) -> str:
    return UNIT_NAMES[int(np.argmax(obs_vec[5:12]))]


def _interpret_current_action(obs_vec: np.ndarray) -> str:
    return CUR_ACTION_NAMES[int(np.argmax(obs_vec[12:18]))]


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


def _feature_indices(mode: str) -> np.ndarray:
    all_idx = np.arange(27, dtype=np.int64)
    if mode == "all_27":
        return all_idx
    if mode == "exclude_owner_2_4":
        return np.asarray([i for i in all_idx if i not in {2, 3, 4}], dtype=np.int64)
    if mode == "exclude_current_action_12_17":
        return np.asarray([i for i in all_idx if i not in {12, 13, 14, 15, 16, 17}], dtype=np.int64)
    if mode == "exclude_owner_and_current_action":
        return np.asarray([i for i in all_idx if i not in {2, 3, 4, 12, 13, 14, 15, 16, 17}], dtype=np.int64)
    raise RuntimeError(f"Unknown feature mode: {mode}")


def _population_mask(obs_flat: np.ndarray, y_flat: np.ndarray, focus: str, group: str) -> np.ndarray:
    if group == "worker_harvest_labels":
        return y_flat[:, 0] == 2
    if group == "base_produce_labels":
        return y_flat[:, 0] == 4
    if group == "non_noop_actor_cells":
        return np.isin(y_flat[:, 0], np.asarray([2, 3, 4, 5], dtype=np.int16))

    # fallback legacy group per focus
    if focus == "B2":
        return y_flat[:, 0] == 2
    return y_flat[:, 0] == 4


def _sem_compat(focus: str, unity_vec: np.ndarray, neigh_vec: np.ndarray) -> bool:
    expected_unit = "Worker" if focus == "B2" else "Base"
    unit_ok = _interpret_unit(neigh_vec) == expected_unit
    action_ok = _interpret_current_action(neigh_vec) in ("Harvest", "Produce")
    return bool(unit_ok and action_ok)


def _nearest(
    *,
    split_name: str,
    inputs: np.ndarray,
    targets: np.ndarray,
    query_vec: np.ndarray,
    focus_label: str,
    top_k: int,
    metric: str,
    feature_mode: str,
    semantic_group: str,
    owner_modes: List[str],
) -> List[Dict[str, Any]]:
    idx_keep = _feature_indices(feature_mode)
    query = query_vec[idx_keep]
    rows: List[Dict[str, Any]] = []

    for sample_idx in range(inputs.shape[0]):
        obs_flat = inputs[sample_idx].reshape(576, 27).astype(np.float64)
        y_flat = targets[sample_idx]
        mask = _population_mask(obs_flat, y_flat, focus_label, semantic_group)
        if not np.any(mask):
            continue
        flat_indices = np.where(mask)[0]
        vectors = obs_flat[flat_indices][:, idx_keep]
        if metric == "l2":
            dists = np.linalg.norm(vectors - query[None, :], axis=1)
        else:
            dists = np.asarray([_cosine_distance(v, query) for v in vectors], dtype=np.float64)

        for i, flat_idx in enumerate(flat_indices.tolist()):
            obs_vec = obs_flat[int(flat_idx)]
            action_type = int(y_flat[int(flat_idx), 0])
            row = int(flat_idx) // 24
            col = int(flat_idx) % 24
            rows.append(
                {
                    "split": split_name,
                    "sample_index": int(sample_idx),
                    "flat_index": int(flat_idx),
                    "grid_position": [row, col],
                    "distance": float(dists[i]),
                    "label_action_type": {
                        "id": action_type,
                        "name": ACTION_NAMES[action_type] if 0 <= action_type < len(ACTION_NAMES) else "Unknown",
                    },
                    "raw_channel_vector": obs_vec.astype(float).tolist(),
                    "interpreted_owner_by_mode": {m: _interpret_owner(obs_vec, m) for m in owner_modes},
                    "interpreted_unit_type": _interpret_unit(obs_vec),
                    "interpreted_current_action": _interpret_current_action(obs_vec),
                    "semantically_compatible": _sem_compat(focus_label, query_vec, obs_vec),
                }
            )

    rows.sort(key=lambda r: r["distance"])
    return rows[:top_k]


def _best_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {"status": "no_candidates"}
    top = rows[0]
    return {
        "best_distance": top["distance"],
        "neighbor_sample_index": top["sample_index"],
        "neighbor_flat_index": top["flat_index"],
        "label_action_type": top["label_action_type"],
        "interpreted_owner_by_mode": top["interpreted_owner_by_mode"],
        "interpreted_unit_type": top["interpreted_unit_type"],
        "interpreted_current_action": top["interpreted_current_action"],
        "semantically_compatible": top["semantically_compatible"],
    }


def main() -> int:
    args = parse_args()
    if args.stage10d1r_output:
        args.output = Path("python/week6_student/reports/stage10d1r_unity_vs_bc_nearest_neighbors_corrected.json")

    inferred_mode = resolve_owner_mode_from_snapshot(args.unity_snapshot)
    owner_modes = normalize_owner_modes(args.owner_mode, inferred_mode)

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

    feature_modes = [
        "all_27",
        "exclude_owner_2_4",
        "exclude_current_action_12_17",
        "exclude_owner_and_current_action",
    ]
    groups = ["worker_harvest_labels", "base_produce_labels", "non_noop_actor_cells"]

    output: Dict[str, Any] = {
        "stage": "10D.1R" if args.stage10d1r_output else "10D.1",
        "diagnostic": "unity_vs_bc_nearest_neighbors_corrected" if args.stage10d1r_output else "unity_vs_bc_nearest_neighbors",
        "dataset_dir": str(dataset.run_dir),
        "unity_snapshot": str(args.unity_snapshot),
        "top_k": int(args.top_k),
        "owner_mode_argument": args.owner_mode,
        "owner_mode_inferred_from_snapshot": inferred_mode,
        "owner_modes_used": owner_modes,
        "contract_check": {
            "branch_sizes": list(branch_sizes),
            "unity_v2_compatible": True,
        },
        "focus_cells": {},
    }

    for focus_label in ("B2", "C3"):
        query = unity_vecs[focus_label].astype(np.float64)
        focus_payload: Dict[str, Any] = {
            "query_channel_vector": query.astype(float).tolist(),
            "query_interpreted_owner_by_mode": {m: _interpret_owner(query, m) for m in owner_modes},
            "query_interpreted_unit_type": _interpret_unit(query),
            "query_interpreted_current_action": _interpret_current_action(query),
            "analysis": {},
        }

        for feature_mode in feature_modes:
            feature_block: Dict[str, Any] = {}
            for group in groups:
                train_rows = _nearest(
                    split_name="train",
                    inputs=dataset.train.input_tensor,
                    targets=dataset.train.target_action_branches,
                    query_vec=query,
                    focus_label=focus_label,
                    top_k=args.top_k,
                    metric="l2",
                    feature_mode=feature_mode,
                    semantic_group=group,
                    owner_modes=owner_modes,
                )
                val_rows = _nearest(
                    split_name="validation",
                    inputs=dataset.validation.input_tensor,
                    targets=dataset.validation.target_action_branches,
                    query_vec=query,
                    focus_label=focus_label,
                    top_k=args.top_k,
                    metric="l2",
                    feature_mode=feature_mode,
                    semantic_group=group,
                    owner_modes=owner_modes,
                )
                all_rows = sorted(train_rows + val_rows, key=lambda r: r["distance"])[: args.top_k]
                feature_block[group] = {
                    "best": _best_summary(all_rows),
                    "neighbors": all_rows,
                }
            focus_payload["analysis"][feature_mode] = feature_block

        output["focus_cells"][focus_label] = focus_payload

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
