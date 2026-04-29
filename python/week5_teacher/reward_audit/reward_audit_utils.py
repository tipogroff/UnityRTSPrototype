#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

BRANCH_LAYOUT: List[int] = [6, 4, 4, 4, 4, 7, 49]
OWNER_NEUTRAL_CH = 2
OWNER_PLAYER1_CH = 3
OWNER_PLAYER2_CH = 4
UNIT_RESOURCE_CH = 5
UNIT_BASE_CH = 6
UNIT_BARRACKS_CH = 7
UNIT_WORKER_CH = 8
UNIT_LIGHT_CH = 9
UNIT_HEAVY_CH = 10
UNIT_RANGED_CH = 11
ACTION_NOOP_CH = 12
ACTION_MOVE_CH = 13
ACTION_HARVEST_CH = 14
ACTION_RETURN_CH = 15
ACTION_PRODUCE_CH = 16
ACTION_ATTACK_CH = 17
DIR_NORTH_CH = 18
DIR_EAST_CH = 19
DIR_SOUTH_CH = 20
DIR_WEST_CH = 21
PRODUCE_WORKER_CH = 22
PRODUCE_LIGHT_CH = 23
PRODUCE_HEAVY_CH = 24
PRODUCE_RANGED_CH = 25
ATTACK_TARGET_CH = 26
ACTION_TYPE_NAMES: Dict[int, str] = {
    0: "noop",
    1: "move",
    2: "harvest",
    3: "return",
    4: "produce",
    5: "attack",
}
PRODUCE_TYPE_NAMES: Dict[int, str] = {
    0: "worker",
    1: "light",
    2: "heavy",
    3: "ranged",
    4: "base",
    5: "barracks",
    6: "other",
}

DEFAULT_ENV_ID = "MicrortsSelfPlayShapedReward-v1"
DEFAULT_MAP_PATH = "maps/24x24/basesWorkers24x24.xml"
DEFAULT_OUTPUT_DIR = Path("python/week5_teacher/reward_audit")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def write_md(path: Path, lines: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def bootstrap_paths() -> None:
    here = Path(__file__).resolve()
    week5_dir = here.parent.parent
    root = week5_dir.parent.parent
    gridnet_dir = root / "python" / "week5_teacher_gridnet"
    mask_audit_dir = week5_dir / "mask_audit"
    for candidate in [root, week5_dir, gridnet_dir, mask_audit_dir]:
        raw = str(candidate)
        if raw not in sys.path:
            sys.path.insert(0, raw)


bootstrap_paths()

from mask_audit_utils import (  # noqa: E402
    build_full_mask_from_candidates,
    create_runtime_context,
    create_wrapped_env,
    flatten_mask,
    reset_compat,
    step_compat,
)


def branch_slices() -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    start = 1
    for size in BRANCH_LAYOUT:
        out.append((start, start + size))
        start += size
    return out


def safe_float(x: Any) -> float:
    try:
        if x is None:
            return 0.0
        return float(x)
    except Exception:
        return 0.0


def as_bool(x: Any) -> bool:
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x) != 0
    if isinstance(x, str):
        return x.strip().lower() in {"1", "true", "yes", "y", "done", "terminal"}
    return False


def flatten_obs(obs: np.ndarray) -> np.ndarray:
    if obs.ndim != 4:
        raise RuntimeError(f"Expected obs [N,H,W,C], got {tuple(obs.shape)}")
    n, h, w, c = obs.shape
    return obs.reshape(n, h * w, c)


def detect_mask_meta(mask_nhwk: np.ndarray, mask_source: str) -> Dict[str, Any]:
    depth = int(mask_nhwk.shape[-1]) if mask_nhwk.ndim == 4 else None
    return {
        "mask_source": mask_source,
        "mask_source_depth": depth,
        "reconstructed_source_channel": "inferred_source_from_action_type" in str(mask_source),
        "mask_shape": [int(v) for v in mask_nhwk.shape] if mask_nhwk is not None else None,
    }


def info_timeout_flag(info: Dict[str, Any]) -> bool:
    timeout_keys = [
        "timeout",
        "timed_out",
        "TimeLimit.truncated",
        "truncated",
        "episode_timeout",
    ]
    for key in timeout_keys:
        if key in info and as_bool(info[key]):
            return True
    return False


def info_terminal_flag(info: Dict[str, Any]) -> bool:
    keys = ["terminal", "terminated", "is_terminal", "episode_done", "done"]
    for key in keys:
        if key in info and as_bool(info[key]):
            return True
    return False


def info_invalid_action_count(info: Dict[str, Any]) -> int:
    keys = [
        "invalid_action_attempts",
        "invalid_actions",
        "invalid_action_count",
        "invalid_action",
    ]
    for key in keys:
        if key in info:
            try:
                return int(info[key])
            except Exception:
                continue
    return 0


def get_valid_indices(mask_vec: np.ndarray, start: int, end: int) -> np.ndarray:
    if start >= mask_vec.shape[0]:
        return np.asarray([], dtype=np.int64)
    end_c = min(end, mask_vec.shape[0])
    return np.where(mask_vec[start:end_c] > 0)[0]


def choose_from_valid(mask_vec: np.ndarray, start: int, end: int, fallback: int = 0) -> int:
    valid = get_valid_indices(mask_vec, start, end)
    if valid.size <= 0:
        return int(fallback)
    return int(valid[0])


def choose_random_from_valid(rng: np.random.Generator, mask_vec: np.ndarray, start: int, end: int, fallback: int = 0) -> int:
    valid = get_valid_indices(mask_vec, start, end)
    if valid.size <= 0:
        return int(fallback)
    return int(rng.choice(valid))


def build_noop_action(mask_flat: np.ndarray) -> np.ndarray:
    n, cells, _ = mask_flat.shape
    return np.zeros((n, cells, 7), dtype=np.int32)


def build_random_valid_action(mask_flat: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    n, cells, _ = mask_flat.shape
    slices = branch_slices()
    action = np.zeros((n, cells, 7), dtype=np.int32)

    for env_i in range(n):
        for cell in range(cells):
            row = mask_flat[env_i, cell]
            if row[0] <= 0:
                continue
            for b in range(7):
                s, e = slices[b]
                action[env_i, cell, b] = choose_random_from_valid(rng, row, s, e, fallback=0)
    return action


def actor_owner_flags(obs_flat: np.ndarray, owner_mode: str = "mask_only") -> np.ndarray:
    if obs_flat.shape[-1] <= UNIT_RANGED_CH:
        return np.zeros(obs_flat.shape[:2], dtype=bool)

    has_unit = np.max(obs_flat[:, :, UNIT_RESOURCE_CH : UNIT_RANGED_CH + 1], axis=2) > 0.1
    owner_player1 = obs_flat[:, :, OWNER_PLAYER1_CH] > 0.5
    owner_player2 = obs_flat[:, :, OWNER_PLAYER2_CH] > 0.5
    owner_neutral = obs_flat[:, :, OWNER_NEUTRAL_CH] > 0.5

    if owner_mode == "player1":
        return np.logical_and(owner_player1, has_unit)
    if owner_mode == "relative":
        # In relative mode treat player1 as self; this is equivalent to player1 until a wrapper exposes explicit self-channel.
        return np.logical_and(owner_player1, has_unit)
    if owner_mode == "mask_only":
        # Ownership is resolved by source/actor mask upstream.
        return np.logical_and(~owner_neutral, has_unit)

    return np.logical_and(owner_player1, np.logical_and(~owner_player2, has_unit))


def infer_unit_kind(obs_cell: np.ndarray) -> str:
    if obs_cell.shape[0] <= UNIT_RANGED_CH:
        return "unknown"
    unit_slice = obs_cell[UNIT_RESOURCE_CH : UNIT_RANGED_CH + 1]
    if unit_slice.size <= 0:
        return "unknown"
    idx = int(np.argmax(unit_slice))
    names = {
        0: "resource",
        1: "base",
        2: "barracks",
        3: "worker",
        4: "light",
        5: "heavy",
        6: "ranged",
    }
    return names.get(idx, "unknown")


def scripted_action_for_cell(obs_cell: np.ndarray, mask_vec: np.ndarray, warnings: List[str]) -> np.ndarray:
    out = np.zeros((7,), dtype=np.int32)
    slices = branch_slices()

    action_type_s, action_type_e = slices[0]
    move_s, move_e = slices[1]
    harvest_s, harvest_e = slices[2]
    return_s, return_e = slices[3]
    produce_dir_s, produce_dir_e = slices[4]
    produce_type_s, produce_type_e = slices[5]
    attack_s, attack_e = slices[6]

    valid_action_types = get_valid_indices(mask_vec, action_type_s, action_type_e)

    def can(t: int) -> bool:
        return np.any(valid_action_types == t)

    unit_kind = infer_unit_kind(obs_cell)

    if unit_kind == "worker":
        if can(2):
            out[0] = 2
            out[2] = choose_from_valid(mask_vec, harvest_s, harvest_e, fallback=0)
            return out
        if can(3):
            out[0] = 3
            out[3] = choose_from_valid(mask_vec, return_s, return_e, fallback=0)
            return out
        if can(1):
            out[0] = 1
            out[1] = choose_from_valid(mask_vec, move_s, move_e, fallback=0)
            return out
        out[0] = 0
        return out

    if unit_kind == "base":
        if can(4):
            out[0] = 4
            out[4] = choose_from_valid(mask_vec, produce_dir_s, produce_dir_e, fallback=0)
            # Worker first, else any valid produce type.
            produce_valid = get_valid_indices(mask_vec, produce_type_s, produce_type_e)
            if np.any(produce_valid == 0):
                out[5] = 0
            elif produce_valid.size > 0:
                out[5] = int(produce_valid[0])
            return out
        out[0] = 0
        return out

    if unit_kind == "barracks":
        if can(4):
            out[0] = 4
            out[4] = choose_from_valid(mask_vec, produce_dir_s, produce_dir_e, fallback=0)
            produce_valid = get_valid_indices(mask_vec, produce_type_s, produce_type_e)
            preferred = [1, 2, 3]
            chosen = None
            for p in preferred:
                if np.any(produce_valid == p):
                    chosen = p
                    break
            if chosen is None:
                if produce_valid.size > 0:
                    chosen = int(produce_valid[0])
                else:
                    chosen = 0
            out[5] = int(chosen)
            return out
        out[0] = 0
        return out

    if unit_kind in {"light", "heavy", "ranged"}:
        if can(5):
            out[0] = 5
            out[6] = choose_from_valid(mask_vec, attack_s, attack_e, fallback=24)
            return out
        if can(1):
            out[0] = 1
            out[1] = choose_from_valid(mask_vec, move_s, move_e, fallback=0)
            return out
        out[0] = 0
        return out

    if unit_kind in {"resource", "unknown"}:
        warnings.append("scripted_probe encountered unknown/non-agent unit kind; falling back to noop")
    out[0] = 0
    return out


def build_scripted_probe_action(
    obs_flat: np.ndarray,
    mask_flat: np.ndarray,
    warnings: List[str],
    owner_mode: str = "mask_only",
) -> np.ndarray:
    n, cells, _ = mask_flat.shape
    action = np.zeros((n, cells, 7), dtype=np.int32)
    owned = actor_owner_flags(obs_flat, owner_mode=owner_mode)

    for env_i in range(n):
        for cell in range(cells):
            if mask_flat[env_i, cell, 0] <= 0:
                continue
            if owner_mode != "mask_only" and not owned[env_i, cell]:
                continue
            action[env_i, cell] = scripted_action_for_cell(obs_flat[env_i, cell], mask_flat[env_i, cell], warnings)
    return action


def to_env_action_shape(action_ncw7: np.ndarray, env_for_training: Any) -> np.ndarray:
    sample = np.asarray(env_for_training.action_space.sample())
    target_shape = tuple(sample.shape)
    num_envs = int(getattr(env_for_training, "num_envs", action_ncw7.shape[0]))

    if len(target_shape) == 1:
        flat = action_ncw7.reshape(action_ncw7.shape[0], -1)
        if num_envs == 1:
            return flat.reshape(-1)
        return flat

    if len(target_shape) == 2 and target_shape[0] == num_envs:
        return action_ncw7.reshape(num_envs, -1)

    if len(target_shape) == 2 and target_shape[0] != num_envs:
        return action_ncw7.reshape(target_shape)

    if len(target_shape) == 3:
        return action_ncw7.reshape(target_shape)

    return action_ncw7


def validate_action_against_mask(action_ncw7: np.ndarray, mask_flat: np.ndarray) -> int:
    slices = branch_slices()
    invalid = 0
    n, cells, _ = action_ncw7.shape
    for env_i in range(n):
        for cell in range(cells):
            if mask_flat[env_i, cell, 0] <= 0:
                continue
            for b in range(7):
                s, _e = slices[b]
                idx = int(action_ncw7[env_i, cell, b])
                pos = s + idx
                if pos < 0 or pos >= mask_flat.shape[-1]:
                    invalid += 1
                    continue
                if mask_flat[env_i, cell, pos] <= 0:
                    invalid += 1
    return int(invalid)


def collect_action_histograms(action_ncw7: np.ndarray, mask_flat: np.ndarray) -> Dict[str, Dict[str, int]]:
    action_hist = Counter()
    produce_hist = Counter()
    attack_hist = Counter()

    n, cells, _ = action_ncw7.shape
    for env_i in range(n):
        for cell in range(cells):
            if mask_flat[env_i, cell, 0] <= 0:
                continue
            at = int(action_ncw7[env_i, cell, 0])
            action_hist[ACTION_TYPE_NAMES.get(at, f"unknown_{at}")] += 1
            if at == 4:
                pt = int(action_ncw7[env_i, cell, 5])
                produce_hist[PRODUCE_TYPE_NAMES.get(pt, f"type_{pt}")] += 1
            if at == 5:
                attack_hist[str(int(action_ncw7[env_i, cell, 6]))] += 1

    return {
        "action_type": {k: int(v) for k, v in sorted(action_hist.items())},
        "produce_unit_type": {k: int(v) for k, v in sorted(produce_hist.items())},
        "attack_target": {k: int(v) for k, v in sorted(attack_hist.items())},
    }


def make_env_and_reset(args: Any) -> Tuple[Any, Any, Any, Dict[str, Any], np.ndarray, Dict[str, Any], Dict[str, Any], List[str]]:
    warnings: List[str] = []
    ctx = create_runtime_context(int(args.seed))
    env, env_for_training, env_summary, _timing = create_wrapped_env(args, ctx)
    obs, info = reset_compat(env_for_training)

    mask_nhwk, mask_source, mask_warn = build_full_mask_from_candidates(env_for_training, obs, infos=[info])
    warnings.extend(mask_warn)
    if mask_nhwk is None:
        raise RuntimeError("Action mask unavailable in current env; cannot run reward sanity.")

    meta = detect_mask_meta(mask_nhwk, mask_source)
    return ctx, env, env_for_training, env_summary, obs, info, meta, warnings
