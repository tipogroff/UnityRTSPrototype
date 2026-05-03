#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from student_bc_loader import load_bc_ready_dataset
from stage10d_owner_semantics import (
    normalize_owner_modes,
    owner_labels_for_mode,
    resolve_owner_mode_from_snapshot,
)

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
    parser.add_argument(
        "--owner-mode",
        type=str,
        default="both",
        choices=("absolute_player_channels", "perspective_friendly_enemy", "both", "auto"),
        help="Owner channel interpretation mode for diagnostics.",
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


def _collect_population(inputs: np.ndarray, targets: np.ndarray, selector: str, owner_mode: str) -> Tuple[np.ndarray, str]:
    chunks = []
    mode = "channel_derived"
    own_idx = 3
    for i in range(inputs.shape[0]):
        obs_flat = inputs[i].reshape(576, 27)
        y_flat = targets[i]
        own = obs_flat[:, own_idx] > 0.5
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


def _l2(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def _interpret_focus(v: np.ndarray, owner_mode: str) -> Dict[str, Any]:
    owner_vals = v[2:5].astype(float).tolist()
    owner_labels = owner_labels_for_mode(owner_mode)  # type: ignore[arg-type]
    owner_idx = int(np.argmax(v[2:5]))
    unit_names = ("Resource", "Base", "Barracks", "Worker", "Light", "Heavy", "Ranged")
    action_names = ("NoOp", "Move", "Harvest", "Return", "Produce", "Attack")
    dir_names = ("North", "East", "South", "West")
    produce_names = ("Worker", "Light", "Heavy", "Ranged")
    return {
        "owner": owner_labels[owner_idx],
        "owner_values": owner_vals,
        "unit_type": unit_names[int(np.argmax(v[5:12]))],
        "current_action": action_names[int(np.argmax(v[12:18]))],
        "direction": dir_names[int(np.argmax(v[18:22]))],
        "produce_type": produce_names[int(np.argmax(v[22:26]))],
        "attack_target": float(v[26]),
    }


def _exclude_indices(vec: np.ndarray, excluded: List[int]) -> np.ndarray:
    keep = [i for i in range(vec.shape[0]) if i not in excluded]
    return vec[keep]


def _compatibility_flags(unity_v: np.ndarray, bc_mean: np.ndarray) -> Dict[str, bool]:
    unit_match = int(np.argmax(unity_v[5:12])) == int(np.argmax(bc_mean[5:12]))
    action_match = int(np.argmax(unity_v[12:18])) == int(np.argmax(bc_mean[12:18]))
    dir_match = int(np.argmax(unity_v[18:22])) == int(np.argmax(bc_mean[18:22]))
    produce_match = int(np.argmax(unity_v[22:26])) == int(np.argmax(bc_mean[22:26]))
    attack_match = bool(abs(float(unity_v[26]) - float(bc_mean[26])) <= 0.1)
    return {
        "unit_type_mismatch": not unit_match,
        "current_action_mismatch": not action_match,
        "direction_mismatch": not dir_match,
        "produce_type_mismatch": not produce_match,
        "attack_target_mismatch": not attack_match,
    }


def main() -> int:
    args = parse_args()

    if args.stage10d1r_output:
        args.output = Path("python/week6_student/reports/stage10d1r_observation_channel_comparison_corrected.json")

    inferred_owner_mode = resolve_owner_mode_from_snapshot(args.unity_snapshot)
    owner_modes = normalize_owner_modes(args.owner_mode, inferred_owner_mode)

    dataset = load_bc_ready_dataset(args.bc_ready_dir)
    _print_npz_keys(dataset.train.path)
    _print_npz_keys(dataset.validation.path)

    manifest = dataset.manifest_payload
    branch_sizes = tuple(int(x) for x in manifest.get("branch_sizes", []))
    _require(branch_sizes == EXPECTED_BRANCH_SIZES_V2, f"Expected v2 branch sizes {EXPECTED_BRANCH_SIZES_V2}, got {branch_sizes}")

    focus = _extract_focus(args.unity_snapshot)

    b2 = focus["B2"]["channels"]
    c3 = focus["C3"]["channels"]

    by_mode: Dict[str, Any] = {}
    selected_owner_mode_for_population = owner_modes[0]
    for owner_mode in owner_modes:
        train_worker, train_worker_mode = _collect_population(
            dataset.train.input_tensor,
            dataset.train.target_action_branches,
            "own_worker",
            owner_mode,
        )
        val_worker, val_worker_mode = _collect_population(
            dataset.validation.input_tensor,
            dataset.validation.target_action_branches,
            "own_worker",
            owner_mode,
        )
        own_worker_population = np.concatenate([train_worker, val_worker], axis=0)

        train_base, train_base_mode = _collect_population(
            dataset.train.input_tensor,
            dataset.train.target_action_branches,
            "own_base",
            owner_mode,
        )
        val_base, val_base_mode = _collect_population(
            dataset.validation.input_tensor,
            dataset.validation.target_action_branches,
            "own_base",
            owner_mode,
        )
        own_base_population = np.concatenate([train_base, val_base], axis=0)

        b2_stats = _group_stats(b2, own_worker_population)
        c3_stats = _group_stats(c3, own_base_population)

        b2_mean = np.mean(own_worker_population, axis=0) if own_worker_population.shape[0] > 0 else np.zeros((27,), dtype=np.float64)
        c3_mean = np.mean(own_base_population, axis=0) if own_base_population.shape[0] > 0 else np.zeros((27,), dtype=np.float64)

        owner_idx = [2, 3, 4]
        sem_excluding_owner_b2 = _l2(_exclude_indices(b2, owner_idx), _exclude_indices(b2_mean, owner_idx))
        sem_excluding_owner_c3 = _l2(_exclude_indices(c3, owner_idx), _exclude_indices(c3_mean, owner_idx))
        sem_including_owner_b2 = _l2(b2, b2_mean)
        sem_including_owner_c3 = _l2(c3, c3_mean)

        b2_owner_z = b2_stats["owner"].get("max_abs_z")
        c3_owner_z = c3_stats["owner"].get("max_abs_z")
        b2_action_z = b2_stats["current_action"].get("max_abs_z")
        c3_action_z = c3_stats["current_action"].get("max_abs_z")

        b2_compat = _compatibility_flags(b2, b2_mean)
        c3_compat = _compatibility_flags(c3, c3_mean)

        b2_attack_p = own_worker_population[:, 26] if own_worker_population.shape[0] > 0 else np.asarray([])
        c3_attack_p = own_base_population[:, 26] if own_base_population.shape[0] > 0 else np.asarray([])
        b2_attack_abnormal = bool(
            b2[26] < 0.0
            or b2[26] > 1.0
            or (b2_attack_p.size > 0 and b2[26] > float(np.quantile(b2_attack_p, 0.99) + 1e-6))
        )
        c3_attack_abnormal = bool(
            c3[26] < 0.0
            or c3[26] > 1.0
            or (c3_attack_p.size > 0 and c3[26] > float(np.quantile(c3_attack_p, 0.99) + 1e-6))
        )

        by_mode[owner_mode] = {
            "diagnostic_mask_policy": {
                "own_worker_population_mode": {"train": train_worker_mode, "validation": val_worker_mode},
                "own_base_population_mode": {"train": train_base_mode, "validation": val_base_mode},
            },
            "populations": {
                "own_worker_count": int(own_worker_population.shape[0]),
                "own_base_count": int(own_base_population.shape[0]),
            },
            "comparison": {
                "B2_vs_bc_own_worker": b2_stats,
                "C3_vs_bc_own_base": c3_stats,
            },
            "semantic_distance": {
                "B2": {
                    "raw_channel_distance": sem_including_owner_b2,
                    "semantic_interpretation_distance_excluding_owner": sem_excluding_owner_b2,
                    "semantic_interpretation_distance_including_owner": sem_including_owner_b2,
                },
                "C3": {
                    "raw_channel_distance": sem_including_owner_c3,
                    "semantic_interpretation_distance_excluding_owner": sem_excluding_owner_c3,
                    "semantic_interpretation_distance_including_owner": sem_including_owner_c3,
                },
            },
            "flags": {
                "owner_labeling_conflict": bool(
                    (b2_owner_z is not None and b2_owner_z > 4.0) or (c3_owner_z is not None and c3_owner_z > 4.0)
                ),
                "unit_type_mismatch": bool(b2_compat["unit_type_mismatch"] or c3_compat["unit_type_mismatch"]),
                "current_action_mismatch": bool(
                    (b2_action_z is not None and b2_action_z > 4.0)
                    or (c3_action_z is not None and c3_action_z > 4.0)
                    or b2_compat["current_action_mismatch"]
                    or c3_compat["current_action_mismatch"]
                ),
                "direction_mismatch": bool(b2_compat["direction_mismatch"] or c3_compat["direction_mismatch"]),
                "produce_type_mismatch": bool(b2_compat["produce_type_mismatch"] or c3_compat["produce_type_mismatch"]),
                "attack_target_mismatch": bool(b2_attack_abnormal or c3_attack_abnormal),
            },
        }

    focus_interpretation = {
        "B2": {
            "raw_channels": b2.astype(float).tolist(),
            "by_owner_mode": {m: _interpret_focus(b2, m) for m in owner_modes},
        },
        "C3": {
            "raw_channels": c3.astype(float).tolist(),
            "by_owner_mode": {m: _interpret_focus(c3, m) for m in owner_modes},
        },
    }

    payload = {
        "stage": "10D.1R" if args.stage10d1r_output else "10D.1",
        "diagnostic": "observation_channel_comparison_corrected" if args.stage10d1r_output else "observation_channel_comparison",
        "dataset_dir": str(dataset.run_dir),
        "unity_snapshot": str(args.unity_snapshot),
        "contract_check": {
            "branch_sizes": list(branch_sizes),
            "unity_v2_compatible": True,
        },
        "owner_mode_argument": args.owner_mode,
        "owner_mode_inferred_from_snapshot": inferred_owner_mode,
        "owner_modes_used": owner_modes,
        "selected_owner_mode_for_population": selected_owner_mode_for_population,
        "focus_interpretation": focus_interpretation,
        "corrected_owner_semantics_applied": True,
        "stage10d1_original_owner_assumption_superseded": True,
        "mode_results": by_mode,
        "owner_labeling_conflict_is_not_full_observation_corruption_by_itself": True,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(args.output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
