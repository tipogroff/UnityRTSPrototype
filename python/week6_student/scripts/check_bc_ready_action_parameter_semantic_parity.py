#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_BC_READY_DIR = Path(
    "python/week5_teacher_legacy032/teacher_exports_bc/"
    "legacy032_3m_source_valid_semantic_obs_fix_bc_ready_20260507T085607Z"
)
SPLIT_FILES = ("bc_train.npz", "bc_validation.npz", "bc_debug.npz")
ACTION_NAMES = ("NoOp", "Move", "Harvest", "Return", "Produce", "Attack")
DIR_NAMES = ("North", "East", "South", "West")
UNIT_NAMES = ("Resource", "Base", "Barracks", "Worker", "Light", "Heavy", "Ranged")
OWNER_NAMES = ("Neutral", "Player1", "Player2")

GRID_W = 24
GRID_H = 24
CELL_COUNT = GRID_W * GRID_H
CHANNELS = 27

ACTION_NOOP = 0
ACTION_MOVE = 1
ACTION_HARVEST = 2
ACTION_RETURN = 3
ACTION_PRODUCE = 4
ACTION_ATTACK = 5

DIR_DELTAS = {
    0: (0, 1),   # Unity runtime Direction.North
    1: (1, 0),   # East
    2: (0, -1),  # South
    3: (-1, 0),  # West
}

ATTACK_OFFSETS = tuple((dx, dy) for dy in range(-3, 4) for dx in range(-3, 4))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Checks whether BC-ready action parameters point at legal targets under "
            "Unity runtime observation semantics."
        )
    )
    parser.add_argument("--bc-ready-dir", type=Path, default=DEFAULT_BC_READY_DIR)
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--max-examples", type=int, default=20)
    return parser.parse_args()


def _load_split(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    with np.load(path, allow_pickle=False) as npz:
        obs = np.asarray(npz["observations"] if "observations" in npz else npz["input_tensor"], dtype=np.float32)
        actions = np.asarray(npz["actions"] if "actions" in npz else npz["target_action_branches"])
        source_valid = (
            np.asarray(npz["source_valid_action_mask"], dtype=np.bool_)
            if "source_valid_action_mask" in npz
            else None
        )

    if obs.ndim == 4 and tuple(obs.shape[1:]) == (GRID_H, GRID_W, CHANNELS):
        obs = obs.reshape(obs.shape[0], CELL_COUNT, CHANNELS)
    if obs.ndim != 3 or tuple(obs.shape[1:]) != (CELL_COUNT, CHANNELS):
        raise ValueError(f"{path.name}: expected observations [N,576,27], got {list(obs.shape)}")
    if actions.ndim != 3 or tuple(actions.shape[1:]) != (CELL_COUNT, 7):
        raise ValueError(f"{path.name}: expected actions [N,576,7], got {list(actions.shape)}")
    if source_valid is not None and source_valid.shape != actions[:, :, 0].shape:
        raise ValueError(f"{path.name}: source_valid_action_mask shape mismatch")
    return obs, actions.astype(np.int32, copy=False), source_valid


def _xy(flat: int) -> tuple[int, int]:
    return int(flat % GRID_W), int(flat // GRID_W)


def _flat(x: int, y: int) -> int:
    return int(y * GRID_W + x)


def _dir_target(flat: int, direction: int) -> tuple[int, int, int | None]:
    x, y = _xy(flat)
    dx, dy = DIR_DELTAS.get(int(direction), (0, 0))
    tx, ty = x + dx, y + dy
    if tx < 0 or tx >= GRID_W or ty < 0 or ty >= GRID_H:
        return tx, ty, None
    return tx, ty, _flat(tx, ty)


def _attack_target(flat: int, local_index: int) -> tuple[int, int, int | None]:
    x, y = _xy(flat)
    if int(local_index) < 0 or int(local_index) >= len(ATTACK_OFFSETS):
        return x, y, None
    dx, dy = ATTACK_OFFSETS[int(local_index)]
    tx, ty = x + dx, y + dy
    if tx < 0 or tx >= GRID_W or ty < 0 or ty >= GRID_H:
        return tx, ty, None
    return tx, ty, _flat(tx, ty)


def _owner_index(obs: np.ndarray, sample: int, flat: int) -> int:
    block = obs[sample, flat, 2:5]
    hits = np.where(block > 0.5)[0]
    return int(hits[0]) if len(hits) == 1 else -1


def _unit_index(obs: np.ndarray, sample: int, flat: int) -> int:
    block = obs[sample, flat, 5:12]
    hits = np.where(block > 0.5)[0]
    return int(hits[0]) if len(hits) == 1 else -1


def _cell_decode(obs: np.ndarray, sample: int, flat: int | None) -> dict[str, Any]:
    if flat is None:
        return {"inside": False}
    owner_i = _owner_index(obs, sample, flat)
    unit_i = _unit_index(obs, sample, flat)
    x, y = _xy(flat)
    return {
        "inside": True,
        "x": x,
        "y": y,
        "flat": int(flat),
        "owner": OWNER_NAMES[owner_i] if 0 <= owner_i < len(OWNER_NAMES) else "none",
        "unit": UNIT_NAMES[unit_i] if 0 <= unit_i < len(UNIT_NAMES) else "empty",
        "unit_resource": bool(unit_i == 0),
        "occupied": bool(unit_i >= 0),
        "friendly": bool(owner_i == 1),
        "hostile": bool(owner_i == 2),
    }


def _actor_decode(obs: np.ndarray, sample: int, flat: int) -> dict[str, Any]:
    x, y = _xy(flat)
    owner_i = _owner_index(obs, sample, flat)
    unit_i = _unit_index(obs, sample, flat)
    return {
        "x": x,
        "y": y,
        "flat": int(flat),
        "owner": OWNER_NAMES[owner_i] if 0 <= owner_i < len(OWNER_NAMES) else "none",
        "unit": UNIT_NAMES[unit_i] if 0 <= unit_i < len(UNIT_NAMES) else "empty",
        "owner_index": owner_i,
        "unit_index": unit_i,
    }


def _is_friendly_worker(obs: np.ndarray, sample: int, flat: int) -> bool:
    return _owner_index(obs, sample, flat) == 1 and _unit_index(obs, sample, flat) == 3


def _is_friendly_mobile_or_building_actor(obs: np.ndarray, sample: int, flat: int) -> bool:
    return _owner_index(obs, sample, flat) == 1 and _unit_index(obs, sample, flat) in {1, 2, 3, 4, 5, 6}


def _is_friendly_attacker(obs: np.ndarray, sample: int, flat: int) -> bool:
    return _owner_index(obs, sample, flat) == 1 and _unit_index(obs, sample, flat) in {3, 4, 5, 6}


def _example(
    split: str,
    sample: int,
    flat: int,
    label: str,
    actions: np.ndarray,
    obs: np.ndarray,
    target_flat: int | None,
    reason: str,
) -> dict[str, Any]:
    tx, ty = (_xy(target_flat) if target_flat is not None else (-1, -1))
    return {
        "split": split,
        "sample": int(sample),
        "flat": int(flat),
        "label": label,
        "actor": _actor_decode(obs, sample, flat),
        "action_branches": [int(v) for v in actions[sample, flat].tolist()],
        "target": {
            "x": int(tx),
            "y": int(ty),
            "flat": None if target_flat is None else int(target_flat),
            "decoded_cell": _cell_decode(obs, sample, target_flat),
        },
        "reason": reason,
    }


def _append_example(examples: list[dict[str, Any]], max_examples: int, item: dict[str, Any]) -> None:
    if len(examples) < max_examples:
        examples.append(item)


def check_split(path: Path, max_examples: int) -> dict[str, Any]:
    obs, actions, source_valid = _load_split(path)
    split = path.stem
    action_type = actions[:, :, 0]
    if source_valid is None:
        active = np.ones_like(action_type, dtype=np.bool_)
    else:
        active = source_valid

    counters: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    hist = Counter(int(v) for v in action_type[active].reshape(-1).tolist())

    sample_idx, flat_idx = np.where(active & (action_type != ACTION_NOOP))
    for sample, flat in zip(sample_idx.tolist(), flat_idx.tolist()):
        at = int(actions[sample, flat, 0])
        if at == ACTION_HARVEST:
            counters["harvest_total"] += 1
            direction = int(actions[sample, flat, 2])
            _, _, target_flat = _dir_target(flat, direction)
            bad = False
            reason = ""
            if not _is_friendly_worker(obs, sample, flat):
                bad = True
                reason = "actor_not_friendly_worker"
            elif target_flat is None:
                bad = True
                reason = "target_out_of_bounds"
            elif _unit_index(obs, sample, target_flat) != 0:
                bad = True
                reason = "target_not_resource_under_unity_obs"
            if bad:
                counters["harvest_bad_target_count"] += 1
                _append_example(
                    examples,
                    max_examples,
                    _example(split, sample, flat, "Harvest", actions, obs, target_flat, reason),
                )
        elif at == ACTION_RETURN:
            counters["return_total"] += 1
            direction = int(actions[sample, flat, 3])
            _, _, target_flat = _dir_target(flat, direction)
            bad = False
            reason = ""
            if not _is_friendly_worker(obs, sample, flat):
                bad = True
                reason = "actor_not_friendly_worker"
            elif target_flat is None:
                bad = True
                reason = "target_out_of_bounds"
            else:
                target_owner = _owner_index(obs, sample, target_flat)
                target_unit = _unit_index(obs, sample, target_flat)
                if not (target_owner == 1 and target_unit == 1):
                    bad = True
                    reason = "target_not_friendly_base_unity_return_semantics"
            if bad:
                counters["return_bad_target_count"] += 1
                _append_example(
                    examples,
                    max_examples,
                    _example(split, sample, flat, "Return", actions, obs, target_flat, reason),
                )
        elif at == ACTION_MOVE:
            counters["move_total"] += 1
            direction = int(actions[sample, flat, 1])
            _, _, target_flat = _dir_target(flat, direction)
            bad = False
            reason = ""
            if not _is_friendly_mobile_or_building_actor(obs, sample, flat):
                bad = True
                reason = "actor_not_friendly_actor"
            elif _unit_index(obs, sample, flat) in {1, 2}:
                bad = True
                reason = "actor_is_building_unity_move_semantics"
            elif target_flat is None:
                bad = True
                reason = "target_out_of_bounds"
            elif _unit_index(obs, sample, target_flat) >= 0:
                bad = True
                reason = "target_occupied_under_unity_obs"
            if bad:
                counters["move_bad_target_count"] += 1
                _append_example(
                    examples,
                    max_examples,
                    _example(split, sample, flat, "Move", actions, obs, target_flat, reason),
                )
        elif at == ACTION_PRODUCE:
            counters["produce_total"] += 1
            direction = int(actions[sample, flat, 4])
            produce_index = int(actions[sample, flat, 5])
            _, _, target_flat = _dir_target(flat, direction)
            actor_unit = _unit_index(obs, sample, flat)
            actor_owner = _owner_index(obs, sample, flat)
            bad = False
            reason = ""
            if actor_owner != 1 or actor_unit not in {1, 2, 3}:
                bad = True
                reason = "actor_not_unity_producer"
            elif actor_unit == 3 and produce_index != 2:
                bad = True
                reason = "worker_produce_not_barracks_index_2"
            elif actor_unit == 1 and produce_index != 3:
                bad = True
                reason = "base_produce_not_worker_index_3"
            elif actor_unit == 2 and produce_index not in {4, 5, 6}:
                bad = True
                reason = "barracks_produce_not_combat_unit_index_4_5_6"
            elif target_flat is None:
                bad = True
                reason = "target_out_of_bounds"
            elif _unit_index(obs, sample, target_flat) >= 0:
                bad = True
                reason = "target_occupied_under_unity_obs"
            if bad:
                counters["produce_bad_target_count"] += 1
                _append_example(
                    examples,
                    max_examples,
                    _example(split, sample, flat, "Produce", actions, obs, target_flat, reason),
                )
        elif at == ACTION_ATTACK:
            counters["attack_total"] += 1
            local = int(actions[sample, flat, 6])
            _, _, target_flat = _attack_target(flat, local)
            bad = False
            reason = ""
            if not _is_friendly_attacker(obs, sample, flat):
                bad = True
                reason = "actor_not_friendly_attacker"
            elif target_flat is None:
                bad = True
                reason = "target_out_of_bounds_or_bad_local_index"
            elif target_flat == flat:
                bad = True
                reason = "self_target"
            elif _owner_index(obs, sample, target_flat) != 2:
                bad = True
                reason = "target_not_hostile_under_unity_obs"
            if bad:
                counters["attack_bad_target_count"] += 1
                _append_example(
                    examples,
                    max_examples,
                    _example(split, sample, flat, "Attack", actions, obs, target_flat, reason),
                )

    source_invalid_non_noop = None
    if source_valid is not None:
        source_invalid_non_noop = int(np.count_nonzero(action_type[~source_valid] != ACTION_NOOP))

    return {
        "split": split,
        "path": str(path),
        "samples": int(obs.shape[0]),
        "source_valid_action_mask_present": bool(source_valid is not None),
        "source_invalid_non_noop": source_invalid_non_noop,
        "source_valid_action_histogram": {ACTION_NAMES[k]: int(v) for k, v in sorted(hist.items())},
        "harvest_total": int(counters["harvest_total"]),
        "harvest_bad_target_count": int(counters["harvest_bad_target_count"]),
        "move_total": int(counters["move_total"]),
        "move_bad_target_count": int(counters["move_bad_target_count"]),
        "return_total": int(counters["return_total"]),
        "return_bad_target_count": int(counters["return_bad_target_count"]),
        "produce_total": int(counters["produce_total"]),
        "produce_bad_target_count": int(counters["produce_bad_target_count"]),
        "attack_total": int(counters["attack_total"]),
        "attack_bad_target_count": int(counters["attack_bad_target_count"]),
        "failing_examples": examples,
    }


def main() -> int:
    args = parse_args()
    bc_ready_dir = args.bc_ready_dir.resolve()
    splits = [check_split(bc_ready_dir / name, int(args.max_examples)) for name in SPLIT_FILES]
    totals = Counter()
    examples: list[dict[str, Any]] = []
    for split in splits:
        for key in (
            "harvest_total",
            "harvest_bad_target_count",
            "move_total",
            "move_bad_target_count",
            "return_total",
            "return_bad_target_count",
            "produce_total",
            "produce_bad_target_count",
            "attack_total",
            "attack_bad_target_count",
        ):
            totals[key] += int(split[key])
        for item in split["failing_examples"]:
            if len(examples) < int(args.max_examples):
                examples.append(item)

    bad_total = (
        totals["harvest_bad_target_count"]
        + totals["move_bad_target_count"]
        + totals["return_bad_target_count"]
        + totals["produce_bad_target_count"]
        + totals["attack_bad_target_count"]
    )
    source_invalid_non_noop_total = sum(
        int(split["source_invalid_non_noop"] or 0) for split in splits
    )
    report = {
        "status": "pass" if bad_total == 0 and source_invalid_non_noop_total == 0 else "fail",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bc_ready_dir": str(bc_ready_dir),
        "unity_coordinate_semantics": {
            "flat_formula": "flat = y * 24 + x",
            "direction_order": "0=North(+Y), 1=East(+X), 2=South(-Y), 3=West(-X)",
            "attack_target_local": "row-major 7x7 offsets dx=-3..3, dy=-3..3; center=24",
        },
        "totals": {key: int(value) for key, value in sorted(totals.items())},
        "source_invalid_non_noop_total": int(source_invalid_non_noop_total),
        "splits": splits,
        "first_20_failing_examples": examples,
    }
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
