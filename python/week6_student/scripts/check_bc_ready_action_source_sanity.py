#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_BC_READY_DIR = Path(
    "python/week5_teacher_legacy032/teacher_exports_bc/"
    "legacy032_3m_unity_v2_bc_ready_stage5p4_20260506T153632Z"
)
SPLIT_FILES = ("bc_train.npz", "bc_validation.npz", "bc_debug.npz")
ACTION_TYPE_NAMES = ("noop", "move", "harvest", "return", "produce", "attack")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Targeted sanity check for the exact Legacy032 BC failure mode where "
            "source-invalid/off-actor cells are stored as supervised non-NoOp labels."
        )
    )
    parser.add_argument("--bc-ready-dir", type=Path, default=DEFAULT_BC_READY_DIR)
    parser.add_argument("--min-noop-share", type=float, default=0.75)
    parser.add_argument("--output-json", type=Path, default=None)
    return parser.parse_args()


def _load_actions(arrays: dict[str, np.ndarray]) -> np.ndarray:
    if "target_action_branches" in arrays:
        return np.asarray(arrays["target_action_branches"])
    if "actions" in arrays:
        return np.asarray(arrays["actions"])
    raise KeyError("split missing actions/target_action_branches")


def _histogram(action_type: np.ndarray) -> dict[str, int]:
    counts = Counter(int(v) for v in action_type.reshape(-1).tolist())
    return {ACTION_TYPE_NAMES[i]: int(counts.get(i, 0)) for i in range(len(ACTION_TYPE_NAMES))}


def check_split(path: Path, min_noop_share: float) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as npz:
        arrays = {k: np.asarray(npz[k]) for k in npz.files}

    actions = _load_actions(arrays)
    if actions.ndim != 3 or tuple(actions.shape[1:]) != (576, 7):
        raise ValueError(f"{path.name}: expected actions [N,576,7], got {list(actions.shape)}")

    action_type = actions[:, :, 0].astype(np.int32, copy=False)
    total = int(action_type.size)
    noop_count = int(np.count_nonzero(action_type == 0))
    noop_share = float(noop_count / max(1, total))

    source_invalid_non_noop = None
    source_valid_cells_mean = None
    failures: list[str] = []
    if "source_valid_action_mask" not in arrays:
        failures.append("source_valid_action_mask missing")
    else:
        mask = np.asarray(arrays["source_valid_action_mask"], dtype=np.bool_)
        if mask.shape != action_type.shape:
            raise ValueError(
                f"{path.name}: source_valid_action_mask shape mismatch: "
                f"expected {list(action_type.shape)}, got {list(mask.shape)}"
            )
        source_invalid_non_noop = int(np.count_nonzero(action_type[~mask] != 0))
        source_valid_cells_mean = float(mask.sum(axis=1).mean()) if mask.shape[0] else 0.0

    if noop_share < min_noop_share:
        failures.append(
            f"NoOp share {noop_share:.6f} < {min_noop_share:.6f}; off-actor labels likely not forced to NoOp"
        )
    if source_invalid_non_noop is not None and source_invalid_non_noop != 0:
        failures.append(f"source-invalid cells contain {source_invalid_non_noop} non-NoOp labels")

    return {
        "split": path.stem,
        "path": str(path),
        "samples": int(actions.shape[0]),
        "action_shape": list(actions.shape),
        "action_type_histogram": _histogram(action_type),
        "noop_share": noop_share,
        "source_valid_action_mask_present": bool("source_valid_action_mask" in arrays),
        "source_valid_cells_mean": source_valid_cells_mean,
        "source_invalid_non_noop": source_invalid_non_noop,
        "failures": failures,
    }


def main() -> int:
    args = parse_args()
    bc_ready_dir = args.bc_ready_dir.resolve()
    results = [check_split(bc_ready_dir / name, float(args.min_noop_share)) for name in SPLIT_FILES]
    failures = [failure for result in results for failure in result["failures"]]

    report = {
        "status": "pass" if not failures else "fail",
        "bc_ready_dir": str(bc_ready_dir),
        "min_noop_share": float(args.min_noop_share),
        "splits": results,
        "failures": failures,
    }

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
