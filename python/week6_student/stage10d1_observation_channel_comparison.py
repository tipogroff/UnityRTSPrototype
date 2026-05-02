#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np

from student_bc_loader import load_bc_ready_dataset

EXPECTED_BRANCH_SIZES_V2: Tuple[int, ...] = (6, 4, 4, 4, 4, 7, 49)

CHANNEL_GROUPS = {
    "owner": (2, 5),
    "unit_type": (5, 12),
    "current_action": (12, 18),
    "direction": (18, 22),
    "produce": (22, 26),
    "attack_target": (26, 27),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage10D.1 observation channel comparison diagnostic")
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
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d1_observation_channel_comparison.json"),
    )
    return parser.parse_args()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _print_npz_keys(npz_path: Path) -> None:
    with np.load(npz_path, allow_pickle=False) as npz_data:
        print(f"[stage10d1][keys] {npz_path.as_posix()} -> {list(npz_data.files)}")


def _extract_focus(snapshot_path: Path) -> Dict[str, Dict[str, Any]]:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8-sig"))
    focus_rows = payload.get("focus_cell_diagnostics", [])
    out: Dict[str, Dict[str, Any]] = {}
    for row in focus_rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("logical_label", ""))
        channels = row.get("cell_observation_channels")
        if label in ("B2", "C3") and isinstance(channels, list) and len(channels) == 27:
            out[label] = {
                "channels": np.asarray(channels, dtype=np.float64),
                "grid_position": row.get("grid_position"),
                "flat_index": row.get("flat_index"),
            }
    _require("B2" in out and "C3" in out, "Unity snapshot missing B2/C3 channel slices")
    return out


def _collect_population(inputs: np.ndarray, targets: np.ndarray, selector: str) -> Tuple[np.ndarray, str]:
    chunks = []
    mode = "channel_derived"
    for i in range(inputs.shape[0]):
        obs_flat = inputs[i].reshape(576, 27)
        y_flat = targets[i]
        own = obs_flat[:, 3] > 0.5
        worker = obs_flat[:, 8] > 0.5
        base = obs_flat[:, 6] > 0.5
        if selector == "own_worker":
            idx = np.where(own & worker)[0]
            if idx.size == 0:
                idx = np.where(y_flat[:, 0] == 2)[0]
                mode = "label_proxy_action_type_harvest"
        elif selector == "own_base":
            idx = np.where(own & base)[0]
            if idx.size == 0:
                idx = np.where(y_flat[:, 0] == 4)[0]
                mode = "label_proxy_action_type_produce"
        else:
            raise RuntimeError(f"Unknown selector: {selector}")
        if idx.size > 0:
            chunks.append(obs_flat[idx])
    if not chunks:
        return np.zeros((0, 27), dtype=np.float64), mode
    return np.concatenate(chunks, axis=0).astype(np.float64), mode


def _group_stats(v: np.ndarray, population: np.ndarray) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for group_name, (start, end) in CHANNEL_GROUPS.items():
        p = population[:, start:end]
        q = v[start:end]
        if p.shape[0] == 0:
            out[group_name] = {
                "unity": q.astype(float).tolist(),
                "bc_mean": [],
                "bc_std": [],
                "l2_from_mean": None,
                "max_abs_z": None,
            }
            continue
        mean = np.mean(p, axis=0)
        std = np.std(p, axis=0)
        z = np.abs((q - mean) / np.maximum(std, 1e-6))
        out[group_name] = {
            "unity": q.astype(float).tolist(),
            "bc_mean": mean.astype(float).tolist(),
            "bc_std": std.astype(float).tolist(),
            "l2_from_mean": float(np.linalg.norm(q - mean)),
            "max_abs_z": float(np.max(z)),
        }
    return out


def _bool_own_worker(v: np.ndarray) -> bool:
    return bool(v[3] > 0.5 and v[8] > 0.5)


def _bool_own_base(v: np.ndarray) -> bool:
    return bool(v[3] > 0.5 and v[6] > 0.5)


def main() -> int:
    args = parse_args()
    dataset = load_bc_ready_dataset(args.bc_ready_dir)
    _print_npz_keys(dataset.train.path)
    _print_npz_keys(dataset.validation.path)

    manifest = dataset.manifest_payload
    branch_sizes = tuple(int(x) for x in manifest.get("branch_sizes", []))
    _require(branch_sizes == EXPECTED_BRANCH_SIZES_V2, f"Expected v2 branch sizes {EXPECTED_BRANCH_SIZES_V2}, got {branch_sizes}")

    focus = _extract_focus(args.unity_snapshot)

    train_worker, train_worker_mode = _collect_population(
        dataset.train.input_tensor,
        dataset.train.target_action_branches,
        "own_worker",
    )
    val_worker, val_worker_mode = _collect_population(
        dataset.validation.input_tensor,
        dataset.validation.target_action_branches,
        "own_worker",
    )
    own_worker_population = np.concatenate(
        [
            train_worker,
            val_worker,
        ],
        axis=0,
    )
    train_base, train_base_mode = _collect_population(
        dataset.train.input_tensor,
        dataset.train.target_action_branches,
        "own_base",
    )
    val_base, val_base_mode = _collect_population(
        dataset.validation.input_tensor,
        dataset.validation.target_action_branches,
        "own_base",
    )
    own_base_population = np.concatenate(
        [
            train_base,
            val_base,
        ],
        axis=0,
    )

    b2 = focus["B2"]["channels"]
    c3 = focus["C3"]["channels"]

    b2_stats = _group_stats(b2, own_worker_population)
    c3_stats = _group_stats(c3, own_base_population)

    b2_attack_p = own_worker_population[:, 26] if own_worker_population.shape[0] > 0 else np.asarray([])
    c3_attack_p = own_base_population[:, 26] if own_base_population.shape[0] > 0 else np.asarray([])

    b2_attack_abnormal = bool(
        b2[26] < 0.0 or b2[26] > 1.0 or (b2_attack_p.size > 0 and b2[26] > float(np.quantile(b2_attack_p, 0.99) + 1e-6))
    )
    c3_attack_abnormal = bool(
        c3[26] < 0.0 or c3[26] > 1.0 or (c3_attack_p.size > 0 and c3[26] > float(np.quantile(c3_attack_p, 0.99) + 1e-6))
    )

    b2_owner_z = b2_stats["owner"].get("max_abs_z")
    c3_owner_z = c3_stats["owner"].get("max_abs_z")
    b2_action_z = b2_stats["current_action"].get("max_abs_z")
    c3_action_z = c3_stats["current_action"].get("max_abs_z")

    payload = {
        "stage": "10D.1",
        "diagnostic": "observation_channel_comparison",
        "dataset_dir": str(dataset.run_dir),
        "unity_snapshot": str(args.unity_snapshot),
        "contract_check": {
            "branch_sizes": list(branch_sizes),
            "unity_v2_compatible": True,
        },
        "diagnostic_mask_policy": {
            "note": "Population masks are diagnostic-derived from observation channels; runtime-authoritative logic remains Unity ActionApplier/MatchManager.",
            "own_worker_population_mode": {
                "train": train_worker_mode,
                "validation": val_worker_mode,
            },
            "own_base_population_mode": {
                "train": train_base_mode,
                "validation": val_base_mode,
            },
        },
        "focus_detection": {
            "B2_detected_as_own_worker": _bool_own_worker(b2),
            "C3_detected_as_own_base": _bool_own_base(c3),
        },
        "populations": {
            "own_worker_count": int(own_worker_population.shape[0]),
            "own_base_count": int(own_base_population.shape[0]),
        },
        "comparison": {
            "B2_vs_bc_own_worker": b2_stats,
            "C3_vs_bc_own_base": c3_stats,
        },
        "flags": {
            "owner_relative_vs_absolute_encoding_mismatch_suspected": bool(
                (b2_owner_z is not None and b2_owner_z > 4.0) or (c3_owner_z is not None and c3_owner_z > 4.0)
            ),
            "row_column_mismatch_suspicion": False,
            "current_action_mismatch_suspected": bool(
                (b2_action_z is not None and b2_action_z > 4.0) or (c3_action_z is not None and c3_action_z > 4.0)
            ),
            "abnormal_attack_target_value": {
                "B2": b2_attack_abnormal,
                "C3": c3_attack_abnormal,
            },
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(args.output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
