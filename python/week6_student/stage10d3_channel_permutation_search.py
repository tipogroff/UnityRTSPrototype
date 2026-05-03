#!/usr/bin/env python3
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np

from student_bc_loader import load_bc_ready_dataset


UNIT_NAMES = ("Resource", "Base", "Barracks", "Worker", "Light", "Heavy", "Ranged")
ACTION_NAMES = ("NoOp", "Move", "Harvest", "Return", "Produce", "Attack")
DIR_NAMES = ("North", "East", "South", "West")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.3 channel permutation search")
    p.add_argument(
        "--bc-ready-dir",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/teacher_exports_bc/"
            "day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z"
        ),
    )
    p.add_argument(
        "--unity-snapshot",
        type=Path,
        default=Path("python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json"),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d3_channel_permutation_search.json"),
    )
    return p.parse_args()


def _extract_focus(snapshot_path: Path) -> Dict[str, np.ndarray]:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8-sig"))
    out: Dict[str, np.ndarray] = {}
    for row in payload.get("focus_cell_diagnostics", []):
        label = str(row.get("logical_label", ""))
        ch = row.get("cell_observation_channels")
        if label in ("B2", "C3") and isinstance(ch, list) and len(ch) == 27:
            out[label] = np.asarray(ch, dtype=np.float64)
    if "B2" not in out or "C3" not in out:
        raise RuntimeError("Unity snapshot missing B2/C3 vectors")
    return out


def _population_mean(dataset: Any, action_type_id: int) -> np.ndarray:
    chunks: List[np.ndarray] = []
    for split in (dataset.train, dataset.validation):
        x = split.input_tensor.reshape(split.input_tensor.shape[0], 576, 27)
        y = split.target_action_branches
        mask = y[:, :, 0] == action_type_id
        if np.any(mask):
            chunks.append(x[mask])
    if not chunks:
        return np.zeros((27,), dtype=np.float64)
    pop = np.concatenate(chunks, axis=0)
    return np.mean(pop, axis=0)


def _argmax_name(v: np.ndarray, names: Tuple[str, ...]) -> str:
    return names[int(np.argmax(v))]


def _best_perm(onehot_vec: np.ndarray, target_mean: np.ndarray) -> Dict[str, Any]:
    n = int(onehot_vec.shape[0])
    base_l2 = float(np.linalg.norm(onehot_vec - target_mean))
    best_l2 = base_l2
    best_perm = tuple(range(n))

    idxs = tuple(range(n))
    for perm in itertools.permutations(idxs):
        v = onehot_vec[list(perm)]
        l2 = float(np.linalg.norm(v - target_mean))
        if l2 < best_l2:
            best_l2 = l2
            best_perm = perm

    return {
        "baseline_l2": base_l2,
        "best_l2": best_l2,
        "best_perm": [int(x) for x in best_perm],
        "improvement": float(base_l2 - best_l2),
    }


def _window_search(unity_group: np.ndarray, bc_mean: np.ndarray, width: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for s in range(0, 27 - width + 1):
        e = s + width
        l2 = float(np.linalg.norm(unity_group - bc_mean[s:e]))
        out.append({"start": int(s), "end": int(e - 1), "l2": l2})
    out.sort(key=lambda x: x["l2"])
    return out[:6]


def main() -> int:
    args = parse_args()
    root = _repo_root()
    out_path = _resolve(root, args.output)

    dataset = load_bc_ready_dataset(args.bc_ready_dir)
    focus = _extract_focus(_resolve(root, args.unity_snapshot))

    b2 = focus["B2"]
    c3 = focus["C3"]

    # Label-proxy populations from Stage10D.1 logic: harvest for worker cells, produce for base cells.
    mean_worker = _population_mean(dataset, action_type_id=2)
    mean_base = _population_mean(dataset, action_type_id=4)

    groups = {
        "unit_type": (5, 12),
        "current_action": (12, 18),
        "direction": (18, 22),
    }

    result: Dict[str, Any] = {
        "stage": "10D.3",
        "diagnostic": "channel_permutation_search",
        "unity_focus": {
            "B2": [float(x) for x in b2.tolist()],
            "C3": [float(x) for x in c3.tolist()],
        },
        "bc_population_means": {
            "worker_label_proxy_action_type_harvest": [float(x) for x in mean_worker.tolist()],
            "base_label_proxy_action_type_produce": [float(x) for x in mean_base.tolist()],
        },
        "analysis": {},
    }

    per_focus: Dict[str, Any] = {}
    for focus_name, unity_vec, bc_mean in (
        ("B2_vs_worker_population", b2, mean_worker),
        ("C3_vs_base_population", c3, mean_base),
    ):
        group_rows: Dict[str, Any] = {}
        for group_name, (s, e) in groups.items():
            unity_group = unity_vec[s:e]
            bc_group = bc_mean[s:e]
            perm = _best_perm(unity_group, bc_group)
            win = _window_search(unity_group, bc_mean, e - s)

            if group_name == "unit_type":
                unity_name = _argmax_name(unity_group, UNIT_NAMES)
                bc_name = _argmax_name(bc_group, UNIT_NAMES)
            elif group_name == "current_action":
                unity_name = _argmax_name(unity_group, ACTION_NAMES)
                bc_name = _argmax_name(bc_group, ACTION_NAMES)
            else:
                unity_name = _argmax_name(unity_group, DIR_NAMES)
                bc_name = _argmax_name(bc_group, DIR_NAMES)

            group_rows[group_name] = {
                "unity_slice": [float(x) for x in unity_group.tolist()],
                "bc_mean_slice": [float(x) for x in bc_group.tolist()],
                "unity_argmax": unity_name,
                "bc_argmax": bc_name,
                "best_within_group_permutation": perm,
                "best_window_anywhere_in_27": win,
                "pure_permutation_explains_gap": bool(perm["best_l2"] < 1e-6),
                "argmax_mismatch": bool(unity_name != bc_name),
            }

        per_focus[focus_name] = group_rows

    # High-level summary.
    b2_u = per_focus["B2_vs_worker_population"]["unit_type"]
    c3_u = per_focus["C3_vs_base_population"]["unit_type"]
    b2_a = per_focus["B2_vs_worker_population"]["current_action"]
    c3_a = per_focus["C3_vs_base_population"]["current_action"]
    b2_d = per_focus["B2_vs_worker_population"]["direction"]
    c3_d = per_focus["C3_vs_base_population"]["direction"]

    result["analysis"] = per_focus
    result["findings"] = {
        "worker_appears_as_resource_ranged_explained_by_permutation": bool(
            b2_u["pure_permutation_explains_gap"]
        ),
        "base_appears_as_resource_ranged_explained_by_permutation": bool(
            c3_u["pure_permutation_explains_gap"]
        ),
        "noop_vs_attack_return_produce_explained_by_permutation": bool(
            b2_a["pure_permutation_explains_gap"] and c3_a["pure_permutation_explains_gap"]
        ),
        "south_vs_west_explained_by_permutation": bool(
            b2_d["pure_permutation_explains_gap"] and c3_d["pure_permutation_explains_gap"]
        ),
        "diagnostic_only": True,
        "note": "Search checks if simple channel permutations/group shifts can explain observed mismatch; no remap is applied.",
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")
    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
