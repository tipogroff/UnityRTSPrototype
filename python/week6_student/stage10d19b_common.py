from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Mapping

import numpy as np


OBS_SHAPE: tuple[int, int] = (576, 27)
ACTION_SHAPE: tuple[int, int] = (576, 7)
MAP_W: int = 24
MAP_H: int = 24
BRANCH_SIZES: tuple[int, ...] = (6, 4, 4, 4, 4, 7, 49)

ACTION_TYPE_NOOP = 0
ACTION_TYPE_MOVE = 1
ACTION_TYPE_HARVEST = 2
ACTION_TYPE_RETURN = 3
ACTION_TYPE_PRODUCE = 4
ACTION_TYPE_ATTACK = 5

ACTION_TYPE_NAMES = {
    ACTION_TYPE_NOOP: "NoOp",
    ACTION_TYPE_MOVE: "Move",
    ACTION_TYPE_HARVEST: "Harvest",
    ACTION_TYPE_RETURN: "Return",
    ACTION_TYPE_PRODUCE: "Produce",
    ACTION_TYPE_ATTACK: "Attack",
}

OWNER_SLICE = slice(2, 5)
UNIT_TYPE_SLICE = slice(5, 12)
ACTION_SLICE = slice(12, 18)
DIR_SLICE = slice(18, 22)
PRODUCE_TYPE_SLICE = slice(22, 26)
ATTACK_TARGET_INDEX = 26

OWNER_NEUTRAL_INDEX = 2
OWNER_SELF_INDEX = 3
OWNER_ENEMY_INDEX = 4

UNIT_RESOURCE_INDEX = 5
UNIT_BASE_INDEX = 6
UNIT_BARRACKS_INDEX = 7
UNIT_WORKER_INDEX = 8
UNIT_LIGHT_INDEX = 9
UNIT_HEAVY_INDEX = 10
UNIT_RANGED_INDEX = 11

UNIT_NAME_TO_CHANNEL = {
    "Resource": UNIT_RESOURCE_INDEX,
    "Base": UNIT_BASE_INDEX,
    "Barracks": UNIT_BARRACKS_INDEX,
    "Worker": UNIT_WORKER_INDEX,
    "Light": UNIT_LIGHT_INDEX,
    "Heavy": UNIT_HEAVY_INDEX,
    "Ranged": UNIT_RANGED_INDEX,
}

MOVABLE_UNIT_CHANNELS = {
    UNIT_WORKER_INDEX,
    UNIT_LIGHT_INDEX,
    UNIT_HEAVY_INDEX,
    UNIT_RANGED_INDEX,
}
MOVABLE_UNIT_NAMES = {"Worker", "Light", "Heavy", "Ranged"}

B2_FLAT = 25
C3_FLAT = 50

MOVE_DIR_TO_NAME = {
    0: "north",
    1: "east",
    2: "south",
    3: "west",
}
MOVE_DELTAS = {
    0: (0, -1),
    1: (1, 0),
    2: (0, 1),
    3: (-1, 0),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (repo_root() / p)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_dir_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: str | Path) -> Dict[str, Any]:
    p = resolve_path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return json.loads(p.read_text(encoding="utf-8-sig"))


def write_json(path: str | Path, payload: Mapping[str, Any]) -> Path:
    p = resolve_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return p


def write_jsonl(path: str | Path, rows: Iterable[Mapping[str, Any]]) -> Path:
    p = resolve_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(dict(row), ensure_ascii=True) + "\n")
    return p


def read_jsonl(path: str | Path) -> list[Dict[str, Any]]:
    p = resolve_path(path)
    rows: list[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def iter_jsonl(path: str | Path) -> Iterator[Dict[str, Any]]:
    p = resolve_path(path)
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def flat_to_xy(flat_index: int) -> tuple[int, int]:
    return int(flat_index % MAP_W), int(flat_index // MAP_W)


def xy_to_flat(x: int, y: int) -> int:
    return int(y * MAP_W + x)


def in_bounds_xy(x: int, y: int) -> bool:
    return 0 <= x < MAP_W and 0 <= y < MAP_H


def load_split_payload(path: str | Path) -> Dict[str, np.ndarray]:
    p = resolve_path(path)
    with np.load(p, allow_pickle=False) as npz:
        return {k: np.asarray(npz[k]) for k in npz.files}


def get_observations_and_actions(split_payload: Mapping[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    if "observations" in split_payload:
        observations = np.asarray(split_payload["observations"], dtype=np.float32)
    else:
        observations = np.asarray(split_payload["input_tensor"], dtype=np.float32)

    if "actions" in split_payload:
        actions = np.asarray(split_payload["actions"], dtype=np.int16)
    else:
        actions = np.asarray(split_payload["target_action_branches"], dtype=np.int16)
    return observations, actions


def ensure_payload_defaults(payload: Mapping[str, np.ndarray], n_samples: int) -> Dict[str, np.ndarray]:
    out = dict(payload)
    out.setdefault("episode_id", np.arange(n_samples, dtype=np.int32))
    out.setdefault("step_id", np.zeros((n_samples,), dtype=np.int32))
    out.setdefault("reward_t", np.zeros((n_samples,), dtype=np.float32))
    out.setdefault("done_t", np.zeros((n_samples,), dtype=np.bool_))
    out.setdefault("terminated_t", np.zeros((n_samples,), dtype=np.bool_))
    out.setdefault("truncated_t", np.zeros((n_samples,), dtype=np.bool_))
    out.setdefault("action_mask_available_t", np.zeros((n_samples,), dtype=np.bool_))
    return out


def actor_mask_from_observation(observations: np.ndarray) -> np.ndarray:
    obs = np.asarray(observations, dtype=np.float32)
    owner_self = obs[:, :, OWNER_SELF_INDEX] > 0.5
    has_unit = np.sum(obs[:, :, UNIT_TYPE_SLICE], axis=2) > 0.5
    return np.asarray(owner_self & has_unit, dtype=bool)


def empty_cell_mask(observation: np.ndarray) -> np.ndarray:
    unit_sum = np.sum(np.asarray(observation, dtype=np.float32)[:, UNIT_TYPE_SLICE], axis=1)
    return np.asarray(unit_sum <= 1e-6, dtype=bool)


def is_cell_movable_actor(cell_vec: np.ndarray) -> bool:
    is_self = bool(float(cell_vec[OWNER_SELF_INDEX]) > 0.5)
    if not is_self:
        return False
    return any(float(cell_vec[idx]) > 0.5 for idx in MOVABLE_UNIT_CHANNELS)


def is_cell_empty(obs_flat: np.ndarray, flat_idx: int) -> bool:
    if flat_idx < 0 or flat_idx >= OBS_SHAPE[0]:
        return False
    unit_sum = float(np.sum(np.asarray(obs_flat, dtype=np.float32)[flat_idx, UNIT_TYPE_SLICE]))
    return unit_sum <= 1e-6


def is_cell_resource(obs_flat: np.ndarray, flat_idx: int) -> bool:
    return bool(float(obs_flat[flat_idx, UNIT_RESOURCE_INDEX]) > 0.5)


def is_cell_enemy(obs_flat: np.ndarray, flat_idx: int) -> bool:
    return bool(float(obs_flat[flat_idx, OWNER_ENEMY_INDEX]) > 0.5 and float(np.sum(obs_flat[flat_idx, UNIT_TYPE_SLICE])) > 0.5)


def clear_action_context_on_cell(obs_flat: np.ndarray, flat_index: int) -> np.ndarray:
    out = np.asarray(obs_flat, dtype=np.float32).copy()
    out[flat_index, ACTION_SLICE] = 0.0
    out[flat_index, ACTION_SLICE.start + ACTION_TYPE_NOOP] = 1.0
    out[flat_index, DIR_SLICE] = 0.0
    out[flat_index, PRODUCE_TYPE_SLICE] = 0.0
    out[flat_index, ATTACK_TARGET_INDEX] = 0.0
    return out


def normalize_empty_cells_to_no_context(obs_flat: np.ndarray) -> np.ndarray:
    out = np.asarray(obs_flat, dtype=np.float32).copy()
    empties = empty_cell_mask(out)
    out[empties, ACTION_SLICE] = 0.0
    out[empties, DIR_SLICE] = 0.0
    out[empties, PRODUCE_TYPE_SLICE] = 0.0
    out[empties, ATTACK_TARGET_INDEX] = 0.0
    return out


def set_unit_cell(
    obs_flat: np.ndarray,
    flat_index: int,
    *,
    owner_self: bool,
    unit_type_channel: int,
) -> np.ndarray:
    out = np.asarray(obs_flat, dtype=np.float32).copy()
    out[flat_index, OWNER_SLICE] = 0.0
    if owner_self:
        out[flat_index, OWNER_SELF_INDEX] = 1.0
    else:
        out[flat_index, OWNER_ENEMY_INDEX] = 1.0
    out[flat_index, UNIT_TYPE_SLICE] = 0.0
    out[flat_index, unit_type_channel] = 1.0
    return out


def make_noop_action_map() -> np.ndarray:
    actions = np.zeros(ACTION_SHAPE, dtype=np.int16)
    actions[:, 0] = ACTION_TYPE_NOOP
    return actions


def target_from_source_and_dir(source_flat: int, move_dir: int) -> tuple[int | None, bool]:
    if int(move_dir) not in MOVE_DELTAS:
        return None, False
    x, y = flat_to_xy(source_flat)
    dx, dy = MOVE_DELTAS[int(move_dir)]
    nx, ny = x + dx, y + dy
    if not in_bounds_xy(nx, ny):
        return None, False
    return xy_to_flat(nx, ny), True


def choose_preferred_valid_direction(
    obs_flat: np.ndarray,
    source_flat: int,
    preferred_dirs: tuple[int, ...] = (1, 2, 0, 3),
) -> tuple[int | None, int | None, str | None]:
    x, y = flat_to_xy(source_flat)
    for d in preferred_dirs:
        dx, dy = MOVE_DELTAS[int(d)]
        nx, ny = x + dx, y + dy
        if not in_bounds_xy(nx, ny):
            continue
        nf = xy_to_flat(nx, ny)
        if is_cell_empty(obs_flat, nf):
            return int(d), int(nf), None
    return None, None, "no_valid_adjacent_free_cell"


def merge_original_and_augmented(
    original: Mapping[str, np.ndarray],
    augmented: Mapping[str, np.ndarray],
    *,
    split_name: str,
) -> Dict[str, np.ndarray]:
    keys = (
        "observations",
        "actions",
        "episode_id",
        "step_id",
        "reward_t",
        "done_t",
        "terminated_t",
        "truncated_t",
        "action_mask_available_t",
    )
    out: Dict[str, np.ndarray] = {}
    for key in keys:
        out[key] = np.concatenate([np.asarray(original[key]), np.asarray(augmented[key])], axis=0)

    n = int(out["observations"].shape[0])
    out["sample_id"] = np.arange(n, dtype=np.int64)
    out["source_episode_file"] = np.full((n,), f"stage10d19b_{split_name}", dtype="<U32")
    out["target_action_branch_sizes"] = np.asarray(BRANCH_SIZES, dtype=np.int64)
    out["schema_version"] = np.asarray(["day6.bc_ready.v1"], dtype="<U32")
    out["split"] = np.asarray([split_name], dtype="<U16")
    out["input_tensor"] = np.asarray(out["observations"], dtype=np.float32)
    out["target_action_branches"] = np.asarray(out["actions"], dtype=np.int16)
    return out


def save_split_npz(path: str | Path, split_payload: Mapping[str, np.ndarray]) -> Path:
    p = resolve_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(p, **{k: np.asarray(v) for k, v in split_payload.items()})
    return p


def summarize_action_type_distribution(
    observations: np.ndarray,
    actions: np.ndarray,
) -> Dict[str, Any]:
    obs = np.asarray(observations, dtype=np.float32)
    act = np.asarray(actions, dtype=np.int64)
    action_type = act[:, :, 0]

    actor_mask = actor_mask_from_observation(obs)
    out: Dict[str, Any] = {
        "sample_count": int(obs.shape[0]),
        "total_cells": int(obs.shape[0] * obs.shape[1]),
        "actor_cells": int(np.sum(actor_mask)),
        "noop_ratio_all_cells": float(np.mean(action_type == ACTION_TYPE_NOOP)),
        "action_type_counts": {ACTION_TYPE_NAMES[i]: int(np.sum(action_type == i)) for i in range(6)},
        "actor_action_type_counts": {
            ACTION_TYPE_NAMES[i]: int(np.sum((action_type == i) & actor_mask)) for i in range(6)
        },
    }
    return out


def validate_branch_bounds(actions: np.ndarray) -> Dict[str, bool]:
    names = [
        "action_type",
        "move_dir",
        "harvest_dir",
        "return_dir",
        "produce_dir",
        "produce_unit_type",
        "attack_target",
    ]
    a = np.asarray(actions, dtype=np.int64)
    out: Dict[str, bool] = {}
    for idx, size in enumerate(BRANCH_SIZES):
        branch = a[:, :, idx]
        out[names[idx]] = bool(int(branch.min()) >= 0 and int(branch.max()) < size)
    return out


def pick_reference_action_vectors(actions: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    a = np.asarray(actions, dtype=np.int16)
    b2_idx = np.where(a[:, B2_FLAT, 0] == ACTION_TYPE_HARVEST)[0]
    c3_idx = np.where(a[:, C3_FLAT, 0] == ACTION_TYPE_PRODUCE)[0]

    if b2_idx.size > 0:
        b2_vec = np.asarray(a[int(b2_idx[0]), B2_FLAT], dtype=np.int16)
    else:
        b2_vec = np.asarray([ACTION_TYPE_HARVEST, 0, 3, 0, 0, 0, 0], dtype=np.int16)

    if c3_idx.size > 0:
        c3_vec = np.asarray(a[int(c3_idx[0]), C3_FLAT], dtype=np.int16)
    else:
        c3_vec = np.asarray([ACTION_TYPE_PRODUCE, 0, 0, 0, 2, 3, 0], dtype=np.int16)
    return b2_vec, c3_vec
