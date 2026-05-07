#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np


SPLIT_FILES = ("bc_train.npz", "bc_validation.npz", "bc_debug.npz")
ACTION_NAMES = ("noop", "move", "harvest", "return", "produce", "attack")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fail-hard Unity semantic observation parity validator for Legacy032 BC-ready datasets."
    )
    p.add_argument("--bc-ready-dir", type=Path, required=True)
    p.add_argument("--output-json", type=Path, default=None)
    p.add_argument(
        "--allow-worker-produce",
        action="store_true",
        default=True,
        help="Treat Worker+Produce as runtime-compatible with the current Unity worker-build-barracks rule.",
    )
    return p.parse_args()


def _load_obs_actions(path: Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    with np.load(path, allow_pickle=False) as npz:
        obs = np.asarray(npz["observations"] if "observations" in npz else npz["input_tensor"], dtype=np.float32)
        actions = np.asarray(npz["actions"] if "actions" in npz else npz["target_action_branches"])
        source_valid = (
            np.asarray(npz["source_valid_action_mask"], dtype=np.bool_)
            if "source_valid_action_mask" in npz
            else None
        )
    if obs.ndim == 4 and tuple(obs.shape[1:]) == (24, 24, 27):
        obs = obs.reshape(obs.shape[0], 576, 27)
    if obs.ndim != 3 or tuple(obs.shape[1:]) != (576, 27):
        raise RuntimeError(f"{path.name}: expected observations [N,576,27], got {list(obs.shape)}")
    if actions.ndim != 3 or tuple(actions.shape[1:]) != (576, 7):
        raise RuntimeError(f"{path.name}: expected actions [N,576,7], got {list(actions.shape)}")
    if source_valid is not None and source_valid.shape != actions[:, :, 0].shape:
        raise RuntimeError(f"{path.name}: source_valid_action_mask shape mismatch")
    return obs, actions, source_valid


def _multi_hot_count(obs: np.ndarray, start: int, end_exclusive: int) -> int:
    return int(np.count_nonzero(np.sum(obs[..., start:end_exclusive] > 0.5, axis=-1) > 1))


def _hist(values: np.ndarray) -> Dict[str, int]:
    counts = Counter(int(v) for v in values.reshape(-1).tolist())
    return {ACTION_NAMES[i]: int(counts.get(i, 0)) for i in range(len(ACTION_NAMES))}


def _cell_decode(obs: np.ndarray, flat: int) -> Dict[str, Any]:
    v = obs[flat]
    owner_labels = ("Neutral", "Player1", "Player2")
    unit_labels = ("Resource", "Base", "Barracks", "Worker", "Light", "Heavy", "Ranged")
    action_labels = ("NoOp", "Move", "Harvest", "Return", "Produce", "Attack")
    dir_labels = ("north", "east", "south", "west")

    def onehot(start: int, labels: Tuple[str, ...]) -> str:
        block = v[start:start + len(labels)]
        hits = np.where(block > 0.5)[0]
        return labels[int(hits[0])] if len(hits) == 1 else "none"

    y, x = divmod(flat, 24)
    return {
        "x": int(x),
        "y": int(y),
        "flat_index": int(flat),
        "owner": onehot(2, owner_labels),
        "unit": onehot(5, unit_labels),
        "current_action": onehot(12, action_labels),
        "direction": onehot(18, dir_labels),
        "active_channels": [int(i) for i in np.where(v > 0.5)[0].tolist()],
    }


def _check_known_corner(obs: np.ndarray) -> List[str]:
    failures: List[str] = []
    first = obs[0]
    expected = {
        "A1": (0, "Neutral", "Resource"),
        "B1": (1, "Neutral", "Resource"),
        "B2": (25, "Player1", "Worker"),
        "C3": (50, "Player1", "Base"),
    }
    for label, (flat, owner, unit) in expected.items():
        decoded = _cell_decode(first, flat)
        if decoded["owner"] != owner or decoded["unit"] != unit:
            failures.append(
                f"{label} expected {owner} {unit}, got owner={decoded['owner']} unit={decoded['unit']} active={decoded['active_channels']}"
            )
    return failures


def check_split(path: Path, allow_worker_produce: bool) -> Dict[str, Any]:
    obs, actions, source_valid = _load_obs_actions(path)
    action_type = actions[:, :, 0].astype(np.int32, copy=False)

    owner_friendly = obs[..., 3] > 0.5
    unit_resource = obs[..., 5] > 0.5
    unit_base = obs[..., 6] > 0.5
    unit_barracks = obs[..., 7] > 0.5
    unit_worker = obs[..., 8] > 0.5
    unit_light = obs[..., 9] > 0.5
    unit_heavy = obs[..., 10] > 0.5
    unit_ranged = obs[..., 11] > 0.5

    actor = owner_friendly & (unit_worker | unit_base | unit_barracks | unit_light | unit_heavy | unit_ranged)
    worker = owner_friendly & unit_worker
    producer = owner_friendly & (unit_base | unit_barracks | (unit_worker if allow_worker_produce else False))
    attacker = owner_friendly & (unit_worker | unit_light | unit_heavy | unit_ranged)

    failures: List[str] = []
    failures.extend(_check_known_corner(obs))

    owner_multihot = _multi_hot_count(obs, 2, 5)
    unit_multihot = _multi_hot_count(obs, 5, 12)
    action_multihot = _multi_hot_count(obs, 12, 18)
    direction_multihot = _multi_hot_count(obs, 18, 22)
    impossible_resource_ranged = int(np.count_nonzero(unit_resource & unit_ranged))

    if int(np.count_nonzero(actor)) == 0:
        failures.append("actor cells count == 0")
    if int(np.count_nonzero(worker)) == 0:
        failures.append("worker cells count == 0")
    if int(np.count_nonzero(owner_friendly & unit_base)) == 0:
        failures.append("base cells count == 0")
    if owner_multihot:
        failures.append(f"owner multihot detected: {owner_multihot}")
    if unit_multihot:
        failures.append(f"unit_type multihot detected: {unit_multihot}")
    if action_multihot:
        failures.append(f"action_type multihot detected: {action_multihot}")
    if direction_multihot:
        failures.append(f"direction multihot detected: {direction_multihot}")
    if impossible_resource_ranged:
        failures.append(f"impossible unit_resource + unit_ranged cells: {impossible_resource_ranged}")

    harvest_bad = int(np.count_nonzero((action_type == 2) & ~worker))
    return_bad = int(np.count_nonzero((action_type == 3) & ~worker))
    produce_bad = int(np.count_nonzero((action_type == 4) & ~producer))
    attack_bad = int(np.count_nonzero((action_type == 5) & ~attacker))
    non_noop_bad_actor = int(np.count_nonzero((action_type != 0) & ~actor))

    if harvest_bad:
        failures.append(f"Harvest labels on non-friendly-worker cells: {harvest_bad}")
    if return_bad:
        failures.append(f"Return labels on non-friendly-worker cells: {return_bad}")
    if produce_bad:
        failures.append(f"Produce labels on incompatible producer cells: {produce_bad}")
    if attack_bad:
        failures.append(f"Attack labels on incompatible attacker cells: {attack_bad}")
    if non_noop_bad_actor:
        failures.append(f"non-NoOp labels on impossible actor cells: {non_noop_bad_actor}")

    source_invalid_non_noop = None
    if source_valid is None:
        failures.append("source_valid_action_mask missing")
    else:
        source_invalid_non_noop = int(np.count_nonzero(action_type[~source_valid] != 0))
        if source_invalid_non_noop:
            failures.append(f"source-invalid cells contain non-NoOp labels: {source_invalid_non_noop}")

    return {
        "split": path.stem,
        "path": str(path),
        "samples": int(obs.shape[0]),
        "actor_cells_count": int(np.count_nonzero(actor)),
        "worker_cells_count": int(np.count_nonzero(worker)),
        "base_cells_count": int(np.count_nonzero(owner_friendly & unit_base)),
        "action_type_histogram": _hist(action_type),
        "owner_multihot_count": owner_multihot,
        "unit_type_multihot_count": unit_multihot,
        "action_type_multihot_count": action_multihot,
        "direction_multihot_count": direction_multihot,
        "impossible_resource_ranged_count": impossible_resource_ranged,
        "target_compatibility": {
            "harvest_bad": harvest_bad,
            "return_bad": return_bad,
            "produce_bad": produce_bad,
            "attack_bad": attack_bad,
            "non_noop_bad_actor": non_noop_bad_actor,
        },
        "source_valid_action_mask_present": bool(source_valid is not None),
        "source_invalid_non_noop": source_invalid_non_noop,
        "known_corner_decodes": {
            "A1": _cell_decode(obs[0], 0),
            "B1": _cell_decode(obs[0], 1),
            "B2": _cell_decode(obs[0], 25),
            "C3": _cell_decode(obs[0], 50),
        },
        "failures": failures,
    }


def main() -> int:
    args = parse_args()
    bc_ready_dir = args.bc_ready_dir.resolve()
    results = [check_split(bc_ready_dir / name, bool(args.allow_worker_produce)) for name in SPLIT_FILES]
    failures = [failure for result in results for failure in result["failures"]]
    report = {
        "status": "pass" if not failures else "fail",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bc_ready_dir": str(bc_ready_dir),
        "unity_channel_semantics": "runtime 27-channel contract",
        "allow_worker_produce_runtime_rule": bool(args.allow_worker_produce),
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

