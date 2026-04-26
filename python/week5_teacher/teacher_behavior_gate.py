#!/usr/bin/env python3
"""
teacher_behavior_gate.py

Behavior gate for teacher checkpoints before new training runs.

Runs two audits (actor-level + effective-behavior state-diff) inside Gym-microRTS
and combines their results into a single gate JSON + Markdown summary.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Schema / status constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "teacher_behavior_gate.v1"

STATUS_PASS = "PASS"
STATUS_SUSPICIOUS = "SUSPICIOUS"
STATUS_FAIL_NOOP = "FAIL_COLLAPSED_NOOP"
STATUS_FAIL_FALSE_TENSOR = "FAIL_FALSE_FULL_TENSOR_MOVE"
STATUS_FAIL_NO_EFFECT = "FAIL_NO_EFFECT_BEHAVIOR"

# ---------------------------------------------------------------------------
# Observation / action layout constants
# ---------------------------------------------------------------------------

CH_HP_START = 0
CH_HP_END = 5
CH_RES_START = 5
CH_RES_END = 10
CH_OWNER_NEUTRAL = 10
CH_OWNER_SELF = 11
CH_OWNER_ENEMY = 12
CH_UNIT_TYPE_START = 13
CH_UNIT_TYPE_END = 21
N_CHANNELS = 27

MASK_SOURCE = 0
MASK_NOOP = 1
MASK_MOVE = 2

ACT_TYPE = 0

DIR_OFFSETS: Dict[int, Tuple[int, int]] = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}
ACTION_NAMES: Dict[int, str] = {
    0: "NoOp", 1: "Move", 2: "Harvest", 3: "Return", 4: "Produce", 5: "Attack",
}
UNIT_TYPE_NAMES: Dict[int, str] = {
    0: "empty", 1: "Resource", 2: "Base", 3: "Barracks",
    4: "Worker", 5: "Light", 6: "Heavy", 7: "Ranged",
}

# ---------------------------------------------------------------------------
# Effective-behavior outcome constants
# ---------------------------------------------------------------------------

OUT_MOVE_DIRECT = "move_effect_observed"
OUT_MOVE_IMPLICIT_HARVEST = "implicit_move_via_harvest"
OUT_MOVE_IMPLICIT_RETURN = "implicit_move_via_return"
OUT_MOVE_IMPLICIT_ATTACK = "implicit_move_via_attack"
OUT_MOVE_IMPLICIT_OTHER = "implicit_move_via_other_action"
OUT_NO_POS_CHANGE = "no_position_change"
OUT_HARVEST_IN_PLACE = "harvest_effect_in_place"
OUT_RETURN_IN_PLACE = "return_effect_in_place"
OUT_PRODUCE_EFFECT = "produce_started_or_completed"
OUT_ATTACK_EFFECT = "attack_effect_observed"
OUT_BLOCKED = "blocked_or_no_effect"
OUT_UNKNOWN = "unknown_from_available_state"

_MOVE_OUTCOMES = frozenset({
    OUT_MOVE_DIRECT,
    OUT_MOVE_IMPLICIT_HARVEST,
    OUT_MOVE_IMPLICIT_RETURN,
    OUT_MOVE_IMPLICIT_ATTACK,
    OUT_MOVE_IMPLICIT_OTHER,
})
_NO_EFFECT_OUTCOMES = frozenset({OUT_NO_POS_CHANGE, OUT_BLOCKED})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Teacher behavior gate: actor-level + effective-behavior audit "
            "before new training runs."
        )
    )
    p.add_argument("--checkpoint", type=Path, required=True,
                   help="Path to SB3 MaskablePPO / PPO checkpoint .zip file.")
    p.add_argument("--episodes", type=int, default=8,
                   help="Number of episodes for actor-level audit (default: 8).")
    p.add_argument("--max-steps", type=int, default=2000,
                   help="Max steps per episode (default: 2000).")
    p.add_argument("--effective-steps", type=int, default=100,
                   help="Steps to run for effective-behavior state-diff audit (default: 100).")
    p.add_argument("--seed", type=int, default=170)
    p.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    p.add_argument("--opponent-pool",
                   default="coacAI,workerRushAI,lightRushAI,passiveAI")
    p.add_argument("--opponent-sampling", choices=("static", "per_episode"),
                   default="per_episode")
    p.add_argument("--device", default="cpu")
    p.add_argument(
        "--deterministic",
        choices=("true", "false"),
        default="true",
        help="Policy predict mode. true=deterministic (default), false=stochastic sampling.",
    )
    p.add_argument("--output-dir", type=Path, default=Path("WEEK5R"),
                   help="Directory to write gate JSON and Markdown (default: WEEK5R/).")
    p.add_argument("--make-replay", action="store_true",
                   help="Generate optional visual sanity replay artifacts after gate run.")
    p.add_argument("--replay-steps", type=int, default=300,
                   help="Max steps per replay episode when --make-replay is enabled (default: 300).")
    p.add_argument("--replay-output-dir", type=Path, default=None,
                   help="Directory for replay artifacts. Defaults to <output-dir>/replay_<checkpoint-stem>.")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_model(checkpoint: Path, device: str) -> Tuple[Any, str]:
    errors: List[str] = []
    try:
        from sb3_contrib import MaskablePPO
        m = MaskablePPO.load(str(checkpoint), device=device, print_system_info=False)
        return m, "sb3_contrib.MaskablePPO"
    except Exception as exc:
        errors.append(f"MaskablePPO: {type(exc).__name__}: {exc}")
    try:
        from stable_baselines3 import PPO
        m = PPO.load(str(checkpoint), device=device, print_system_info=False)
        return m, "stable_baselines3.PPO"
    except Exception as exc:
        errors.append(f"PPO: {type(exc).__name__}: {exc}")
    raise RuntimeError("Failed to load checkpoint. " + " | ".join(errors))


def build_env(map_path: str, max_steps: int, opponent_name: str) -> Any:
    from gym_microrts import microrts_ai
    from gym_microrts.envs.vec_env import MicroRTSGridModeVecEnv
    opponent = getattr(microrts_ai, opponent_name, None)
    if opponent is None:
        raise RuntimeError(f"Unknown opponent '{opponent_name}' in gym_microrts.microrts_ai")
    return MicroRTSGridModeVecEnv(
        num_selfplay_envs=0,
        num_bot_envs=1,
        ai2s=[opponent],
        map_paths=[map_path],
        max_steps=max_steps,
        autobuild=False,
    )


def read_action_mask(env: Any) -> Optional[np.ndarray]:
    if hasattr(env, "get_action_mask"):
        try:
            return np.asarray(env.get_action_mask())
        except Exception:
            pass
    if hasattr(env, "action_masks"):
        try:
            raw = env.action_masks
            result = raw() if callable(raw) else raw
            return np.asarray(result)
        except Exception:
            pass
    return None


def predict_action(
    model: Any,
    obs: Any,
    action_mask: Optional[np.ndarray],
    *,
    deterministic: bool,
) -> Any:
    if action_mask is not None:
        # sb3_contrib.MaskablePPO.predict expects action_masks to be 2-D:
        # [n_envs, sum(nvec)].  The gym_microrts env returns a 3-D array
        # [n_envs, n_cells, nvec_per_cell] (e.g. [1, 576, 78]).  Flatten to
        # [n_envs, n_cells * nvec_per_cell] so the shape contract is met.
        mask_2d = np.asarray(action_mask)
        if mask_2d.ndim == 3:
            mask_2d = mask_2d.reshape(mask_2d.shape[0], -1)
        try:
            action, _ = model.predict(obs, deterministic=deterministic, action_masks=mask_2d)
            return action
        except TypeError:
            # API does not accept action_masks keyword (plain PPO fallback).
            pass
    action, _ = model.predict(obs, deterministic=deterministic)
    return action


def action_to_matrix(action: Any) -> np.ndarray:
    arr = np.asarray(action)
    if arr.ndim == 3 and arr.shape[0] == 1 and arr.shape[2] == 7:
        return arr[0].astype(np.int64)
    if arr.ndim == 2 and arr.shape[1] == 7:
        return arr.astype(np.int64)
    flat = arr.reshape(-1)
    if flat.size % 7 != 0:
        raise RuntimeError(f"Unexpected action shape {arr.shape}; cannot reshape to (-1, 7).")
    return flat.reshape(-1, 7).astype(np.int64)


def parse_opponent_pool(raw: str) -> List[str]:
    parsed = [t.strip() for t in raw.split(",") if t.strip()]
    if not parsed:
        raise RuntimeError("Opponent pool is empty.")
    return parsed


def pick_opponent(pool: List[str], mode: str, seed: int, episode_id: int = 0) -> str:
    if mode == "static":
        return pool[0]
    return random.Random(seed + 103 + (episode_id * 9973)).choice(pool)


def pick_effective_audit_opponent(pool: List[str], mode: str, seed: int) -> Tuple[str, str]:
    if mode == "static":
        return pool[0], "static_first_pool_opponent"
    return random.Random(seed + 700001).choice(pool), "deterministic_single_from_pool"


def idx_to_xy(idx: int, width: int) -> Tuple[int, int]:
    return int(idx % width), int(idx // width)


def get_cell_owner(obs_arr: np.ndarray, y: int, x: int) -> str:
    cell = obs_arr[0, y, x, :]
    if cell[CH_OWNER_SELF] > 0.5:
        return "teacher"
    if cell[CH_OWNER_ENEMY] > 0.5:
        return "opponent"
    if cell[CH_OWNER_NEUTRAL] > 0.5:
        return "neutral"
    return "empty"


def decode_cell(obs_arr: np.ndarray, y: int, x: int) -> Dict[str, Any]:
    cell = obs_arr[0, y, x, :]
    owner = get_cell_owner(obs_arr, y, x)
    hp_band = int(np.argmax(cell[CH_HP_START:CH_HP_END]))
    res_band = int(np.argmax(cell[CH_RES_START:CH_RES_END]))
    ut_raw = cell[CH_UNIT_TYPE_START:CH_UNIT_TYPE_END]
    unit_type = UNIT_TYPE_NAMES.get(int(np.argmax(ut_raw)), "empty") if ut_raw.max() > 0.1 else "empty"
    return {"x": x, "y": y, "hp_band": hp_band, "res_band": res_band, "owner": owner, "unit_type": unit_type}


def unit_at(obs_arr: np.ndarray, y: int, x: int, height: int, width: int) -> Optional[Dict[str, Any]]:
    if x < 0 or x >= width or y < 0 or y >= height:
        return None
    cell = obs_arr[0, y, x, :]
    if cell[CH_OWNER_SELF] > 0.5 or cell[CH_OWNER_ENEMY] > 0.5:
        return decode_cell(obs_arr, y, x)
    return None


def classify_actor_outcome(
    x0: int,
    y0: int,
    unit_type_before: str,
    hp_before: int,
    res_before: int,
    chosen_action_type: int,
    obs_before: np.ndarray,
    obs_after: np.ndarray,
    height: int,
    width: int,
) -> str:
    cell_after = unit_at(obs_after, y0, x0, height, width)
    still_here = cell_after is not None and cell_after["owner"] == "teacher"

    if still_here:
        res_after = cell_after["res_band"]
        if chosen_action_type == 2:
            return OUT_HARVEST_IN_PLACE if res_after > res_before else OUT_BLOCKED
        if chosen_action_type == 3:
            return OUT_RETURN_IN_PLACE if res_after < res_before else OUT_BLOCKED
        if chosen_action_type == 4:
            for dx, dy in DIR_OFFSETS.values():
                nx, ny = x0 + dx, y0 + dy
                before_adj = unit_at(obs_before, ny, nx, height, width)
                after_adj = unit_at(obs_after, ny, nx, height, width)
                if after_adj and after_adj["owner"] == "teacher":
                    if before_adj is None or before_adj["owner"] != "teacher":
                        return OUT_PRODUCE_EFFECT
            return OUT_BLOCKED
        if chosen_action_type == 5:
            for dx, dy in DIR_OFFSETS.values():
                nx, ny = x0 + dx, y0 + dy
                opp_before = unit_at(obs_before, ny, nx, height, width)
                opp_after = unit_at(obs_after, ny, nx, height, width)
                if opp_before and opp_before["owner"] == "opponent":
                    if opp_after is None or opp_after["hp_band"] < opp_before["hp_band"]:
                        return OUT_ATTACK_EFFECT
            return OUT_BLOCKED
        if chosen_action_type == 1:
            return OUT_BLOCKED
        if chosen_action_type == 0:
            return OUT_NO_POS_CHANGE
        return OUT_UNKNOWN

    for dx, dy in DIR_OFFSETS.values():
        nx, ny = x0 + dx, y0 + dy
        adj = unit_at(obs_after, ny, nx, height, width)
        if adj and adj["owner"] == "teacher" and adj["unit_type"] == unit_type_before:
            if chosen_action_type == 1:
                return OUT_MOVE_DIRECT
            if chosen_action_type == 2:
                return OUT_MOVE_IMPLICIT_HARVEST
            if chosen_action_type == 3:
                return OUT_MOVE_IMPLICIT_RETURN
            if chosen_action_type == 5:
                return OUT_MOVE_IMPLICIT_ATTACK
            return OUT_MOVE_IMPLICIT_OTHER

    for dy2 in range(-2, 3):
        for dx2 in range(-2, 3):
            if abs(dx2) + abs(dy2) <= 1:
                continue
            nx, ny = x0 + dx2, y0 + dy2
            adj = unit_at(obs_after, ny, nx, height, width)
            if adj and adj["owner"] == "teacher" and adj["unit_type"] == unit_type_before:
                return OUT_MOVE_DIRECT if chosen_action_type == 1 else OUT_MOVE_IMPLICIT_OTHER

    return OUT_UNKNOWN


# ---------------------------------------------------------------------------
# Actor-level audit
# ---------------------------------------------------------------------------

def run_actor_level_audit(
    model: Any,
    opponent_pool: List[str],
    opponent_sampling_mode: str,
    seed: int,
    map_path: str,
    max_steps: int,
    episodes: int,
    deterministic: bool,
) -> Dict[str, Any]:
    full_counter: Counter = Counter()
    actor_counter: Counter = Counter()

    ready_actor_total = 0
    steps_with_ready_actors = 0
    steps_with_movable_ready = 0
    ready_movable_actor_choice_count = 0
    steps_movable_no_move = 0
    steps_total = 0
    opponents_by_episode: List[str] = []
    env_cache: Dict[str, Any] = {}

    for ep_id in range(episodes):
        opponent = pick_opponent(opponent_pool, opponent_sampling_mode, seed, ep_id)
        opponents_by_episode.append(opponent)

        env = env_cache.get(opponent)
        if env is None:
            env = build_env(map_path, max_steps, opponent)
            env_cache[opponent] = env

        obs = env.reset()
        done = False
        step_id = 0
        while not done and step_id < max_steps:
            action_mask = read_action_mask(env)
            action = predict_action(model, obs, action_mask, deterministic=deterministic)
            matrix = action_to_matrix(action)

            if matrix.shape[0] != 576:
                raise RuntimeError(f"Expected 576 spatial slots, got {matrix.shape[0]}.")

            action_types = matrix[:, ACT_TYPE]
            full_counter.update(Counter(int(v) for v in action_types.tolist()))
            steps_total += 1

            if action_mask is not None and action_mask.ndim == 3 and action_mask.shape[0] == 1:
                ready_mask = action_mask[0, :, MASK_SOURCE].astype(bool)
                ready_indices = np.where(ready_mask)[0]
                ready_count = int(ready_indices.size)
                if ready_count > 0:
                    steps_with_ready_actors += 1
                    ready_actor_total += ready_count

                    step_actor = Counter(int(v) for v in action_types[ready_indices].tolist())
                    actor_counter.update(step_actor)

                    if action_mask.shape[2] > MASK_MOVE:
                        move_allowed = action_mask[0, ready_indices, MASK_MOVE].astype(bool)
                        movable_count = int(move_allowed.sum())
                        ready_movable_actor_choice_count += movable_count
                        if movable_count > 0:
                            steps_with_movable_ready += 1
                            if step_actor.get(1, 0) == 0:
                                steps_movable_no_move += 1

            transition = env.step(action)
            if len(transition) == 5:
                obs, _r, terminated, truncated, _info = transition
                done = bool(terminated or truncated)
            else:
                obs, _r, done, _info = transition
            step_id += 1

    full_total = int(sum(full_counter.values()))
    actor_total = int(sum(actor_counter.values()))

    full_move_share = full_counter.get(1, 0) / full_total if full_total > 0 else 0.0
    actor_move_share = actor_counter.get(1, 0) / actor_total if actor_total > 0 else 0.0
    actor_noop_share = actor_counter.get(0, 0) / actor_total if actor_total > 0 else 0.0

    return {
        "full_tensor_move_share": round(float(full_move_share), 6),
        "actor_level_move_share": round(float(actor_move_share), 6),
        "actor_noop_share": round(float(actor_noop_share), 6),
        "ready_own_actor_count": actor_total,
        "ready_movable_actor_choice_count": int(ready_movable_actor_choice_count),
        # Backward-compatible alias. Historically this was a step-level proxy.
        "ready_movable_actor_count": int(steps_with_movable_ready),
        "steps_total": int(steps_total),
        "steps_with_ready_actors": int(steps_with_ready_actors),
        "steps_with_movable_ready_actors": int(steps_with_movable_ready),
        "steps_movable_ready_but_no_move": int(steps_movable_no_move),
        "opponents_used": sorted(set(opponents_by_episode)),
        "opponents_by_episode": opponents_by_episode,
        "full_tensor_action_distribution": {
            ACTION_NAMES.get(k, str(k)): {
                "count": int(v),
                "share": round(int(v) / full_total, 6) if full_total > 0 else 0.0,
            }
            for k, v in sorted(full_counter.items())
        },
        "actor_level_action_distribution": {
            ACTION_NAMES.get(k, str(k)): {
                "count": int(v),
                "share": round(int(v) / actor_total, 6) if actor_total > 0 else 0.0,
            }
            for k, v in sorted(actor_counter.items())
        },
    }


# ---------------------------------------------------------------------------
# Effective behavior audit
# ---------------------------------------------------------------------------

def run_effective_behavior_audit(
    model: Any,
    map_path: str,
    max_steps: int,
    opponent: str,
    deterministic: bool,
) -> Dict[str, Any]:
    outcome_counter: Counter = Counter()
    chosen_counter: Counter = Counter()

    env = build_env(map_path, max_steps, opponent)
    try:
        obs = env.reset()
        obs_arr = np.asarray(obs)
        if obs_arr.ndim != 4 or obs_arr.shape[0] != 1:
            raise RuntimeError(f"Unexpected obs shape: {obs_arr.shape}")

        height = int(obs_arr.shape[1])
        width = int(obs_arr.shape[2])
        n_cells = height * width

        done = False
        step_id = 0

        while not done and step_id < max_steps:
            obs_arr = np.asarray(obs)
            action_mask = read_action_mask(env)
            if action_mask is None:
                action, _ = model.predict(obs, deterministic=deterministic)
                transition = env.step(action)
                if len(transition) == 5:
                    obs, _, terminated, truncated, _ = transition
                    done = bool(terminated or truncated)
                else:
                    obs, _, done, _ = transition
                step_id += 1
                continue

            action = predict_action(model, obs, action_mask, deterministic=deterministic)
            action_matrix = action_to_matrix(action)
            if action_matrix.shape[0] != n_cells:
                raise RuntimeError(
                    f"Action spatial mismatch at step {step_id}: "
                    f"expected {n_cells}, got {action_matrix.shape[0]}"
                )

            action_types_all = action_matrix[:, ACT_TYPE]
            ready_mask = action_mask[0, :, MASK_SOURCE].astype(bool)
            ready_indices = np.where(ready_mask)[0]

            obs_before = obs_arr.copy()
            transition = env.step(action)
            if len(transition) == 5:
                obs, _, terminated, truncated, _ = transition
                done = bool(terminated or truncated)
            else:
                obs, _, done, _ = transition
            obs_after = np.asarray(obs)

            for idx in ready_indices:
                idx_int = int(idx)
                x0, y0 = idx_to_xy(idx_int, width)
                cell_info = decode_cell(obs_before, y0, x0)
                chosen_type = int(action_types_all[idx_int])
                chosen_counter[chosen_type] += 1

                outcome = classify_actor_outcome(
                    x0=x0,
                    y0=y0,
                    unit_type_before=cell_info["unit_type"],
                    hp_before=cell_info["hp_band"],
                    res_before=cell_info["res_band"],
                    chosen_action_type=chosen_type,
                    obs_before=obs_before,
                    obs_after=obs_after,
                    height=height,
                    width=width,
                )
                outcome_counter[outcome] += 1

            step_id += 1
    finally:
        # Do not close the env inside the gate process because gym_microrts/JPype
        # cannot safely restart the JVM in the same process after shutdown.
        pass

    chosen_total = int(sum(chosen_counter.values()))
    outcome_total = int(sum(outcome_counter.values()))

    pos_delta_count = sum(int(outcome_counter.get(k, 0)) for k in _MOVE_OUTCOMES)
    no_effect_count = sum(int(outcome_counter.get(k, 0)) for k in _NO_EFFECT_OUTCOMES)
    no_effect_share = no_effect_count / outcome_total if outcome_total > 0 else 0.0

    return {
        "effective_position_delta_count": int(pos_delta_count),
        "no_effect_action_share": round(float(no_effect_share), 6),
        "chosen_ready_own_actor_count": int(chosen_total),
        "outcome_distribution": {k: int(v) for k, v in sorted(outcome_counter.items())},
        "chosen_action_distribution": {
            ACTION_NAMES.get(k, str(k)): int(v) for k, v in sorted(chosen_counter.items())
        },
        "steps_executed": int(step_id),
    }


# ---------------------------------------------------------------------------
# Decision rules
# ---------------------------------------------------------------------------

def evaluate_gate(
    actor: Dict[str, Any],
    effective: Dict[str, Any],
) -> Tuple[str, List[str], List[str]]:
    """
    Apply decision rules and return (status, fail_reasons, warnings).

    Precedence: FAIL_COLLAPSED_NOOP > FAIL_FALSE_FULL_TENSOR_MOVE > FAIL_NO_EFFECT_BEHAVIOR
    """
    fail_reasons: List[str] = []
    warnings: List[str] = []

    full_move = actor["full_tensor_move_share"]
    actor_move = actor["actor_level_move_share"]
    actor_noop = actor["actor_noop_share"]
    movable_count = actor["ready_movable_actor_count"]
    pos_delta = effective["effective_position_delta_count"]
    no_effect_share = effective["no_effect_action_share"]
    chosen_count = effective["chosen_ready_own_actor_count"]

    if movable_count > 0 and actor_move == 0.0 and pos_delta == 0 and actor_noop > 0.90:
        fail_reasons.append(
            f"FAIL_COLLAPSED_NOOP: movable_count={movable_count}, "
            f"actor_move={actor_move:.4f}, pos_delta={pos_delta}, "
            f"actor_noop={actor_noop:.4f} > 0.90"
        )

    if full_move >= 0.10 and actor_move < 0.05:
        fail_reasons.append(
            f"FAIL_FALSE_FULL_TENSOR_MOVE: full_tensor_move={full_move:.4f} >= 0.10 "
            f"but actor_level_move={actor_move:.4f} < 0.05 "
            f"(spurious tensor signal, not real movement)"
        )

    if chosen_count > 0 and no_effect_share > 0.80 and pos_delta == 0:
        fail_reasons.append(
            f"FAIL_NO_EFFECT_BEHAVIOR: chosen_count={chosen_count}, "
            f"no_effect_share={no_effect_share:.4f} > 0.80, "
            f"pos_delta={pos_delta}"
        )

    if fail_reasons:
        if any("FAIL_COLLAPSED_NOOP" in r for r in fail_reasons):
            status = STATUS_FAIL_NOOP
        elif any("FAIL_FALSE_FULL_TENSOR_MOVE" in r for r in fail_reasons):
            status = STATUS_FAIL_FALSE_TENSOR
        else:
            status = STATUS_FAIL_NO_EFFECT
        return status, fail_reasons, warnings

    if actor_noop > 0.75:
        warnings.append(f"actor_noop_share={actor_noop:.4f} > 0.75 (suspicious passivity)")
    if no_effect_share > 0.60:
        warnings.append(f"no_effect_action_share={no_effect_share:.4f} > 0.60 (suspicious no-effect rate)")

    if warnings:
        return STATUS_SUSPICIOUS, fail_reasons, warnings

    if actor_move >= 0.05 and pos_delta > 0:
        return STATUS_PASS, fail_reasons, warnings

    warnings.append(
        f"actor_level_move_share={actor_move:.4f} < 0.05 or pos_delta={pos_delta} == 0; "
        "does not meet PASS threshold"
    )
    return STATUS_SUSPICIOUS, fail_reasons, warnings


# ---------------------------------------------------------------------------
# Markdown builder
# ---------------------------------------------------------------------------

def build_markdown(result: Dict[str, Any]) -> str:
    lines: List[str] = []
    status = result["status"]
    actor = result["actor_level"]
    eff = result["effective_behavior"]

    lines.append("# Teacher Behavior Gate Report")
    lines.append("")
    lines.append(f"Generated at (UTC): {result['meta']['generated_at_utc']}")
    lines.append(f"Schema: `{result['schema_version']}`")
    lines.append("")
    lines.append("## Checkpoint")
    lines.append(f"- Path: `{result['checkpoint']}`")
    lines.append(f"- Loader: `{result['meta']['algorithm_loader']}`")
    lines.append(f"- deterministic_mode: `{result.get('deterministic_mode', True)}`")
    lines.append(f"- Opponent sampling mode: `{result.get('opponent_sampling_mode', 'unknown')}`")
    lines.append(f"- Opponents used (actor audit): `{', '.join(result.get('opponents_used', []))}`")
    lines.append("")
    lines.append("## Gate Verdict")
    lines.append("```")
    lines.append(f"STATUS: {status}")
    lines.append("```")

    if result["fail_reasons"]:
        lines.append("")
        lines.append("### FAIL Reasons")
        for r in result["fail_reasons"]:
            lines.append(f"- {r}")

    if result["warnings"]:
        lines.append("")
        lines.append("### Warnings")
        for w in result["warnings"]:
            lines.append(f"- {w}")

    lines.append("")
    lines.append("## Actor-Level Summary")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| full_tensor_move_share | {actor['full_tensor_move_share']:.4f} ({actor['full_tensor_move_share']*100:.2f}%) |")
    lines.append(f"| actor_level_move_share | {actor['actor_level_move_share']:.4f} ({actor['actor_level_move_share']*100:.2f}%) |")
    lines.append(f"| actor_noop_share | {actor['actor_noop_share']:.4f} ({actor['actor_noop_share']*100:.2f}%) |")
    lines.append(f"| ready_own_actor_count | {actor['ready_own_actor_count']} |")
    lines.append(f"| steps_with_ready_actors | {actor.get('steps_with_ready_actors', 0)} |")
    lines.append(f"| steps_with_movable_ready_actors | {actor.get('steps_with_movable_ready_actors', 0)} |")
    lines.append(f"| ready_movable_actor_choice_count | {actor.get('ready_movable_actor_choice_count', 0)} |")
    lines.append(f"| ready_movable_actor_count (legacy alias, step-level proxy) | {actor['ready_movable_actor_count']} |")

    lines.append("")
    lines.append("## Effective Behavior Summary")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| effective_position_delta_count | {eff['effective_position_delta_count']} |")
    lines.append(f"| no_effect_action_share | {eff['no_effect_action_share']:.4f} ({eff['no_effect_action_share']*100:.2f}%) |")
    lines.append(f"| chosen_ready_own_actor_count | {eff['chosen_ready_own_actor_count']} |")
    lines.append(f"| steps_executed (effective audit) | {eff['steps_executed']} |")

    lines.append("")
    lines.append("## Visual Sanity Replay")
    replay = result.get("visual_replay", {})
    lines.append(f"- created: {bool(replay.get('created', False))}")
    lines.append(f"- trace path: `{result.get('replay_trace_path')}`")
    lines.append(f"- notes path: `{result.get('visual_notes_path')}`")
    if result.get("frames_dir"):
        lines.append(f"- frames path: `{result.get('frames_dir')}`")
    lines.append(f"- visual verdict: `{replay.get('visual_verdict', 'n/a')}`")

    lines.append("")
    lines.append("## Decision Rules Applied")
    dr = result["decision_rules"]
    for name, rule in dr.items():
        lines.append(f"### {name}")
        lines.append(f"- Triggered: {rule['triggered']}")
        for k, v in rule["values"].items():
            lines.append(f"  - {k}: {v}")

    lines.append("")
    lines.append("## Important Caveats")
    lines.append(
        "- This gate runs inside Gym-microRTS only. "
        "It does **NOT** claim Gym->Unity semantic parity."
    )
    lines.append(
        "- Full-tensor Move share is **NOT** evidence of real movement. "
        "Actor-level Move share is the authoritative signal."
    )
    lines.append(
        "- Effective-behavior state-diff is an observation proxy, "
        "not a confirmed internal execution stream."
    )

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    deterministic_mode = str(args.deterministic).strip().lower() == "true"

    checkpoint = args.checkpoint.resolve()
    if not checkpoint.is_file():
        print(f"[ERROR] Checkpoint not found: {checkpoint}")
        return 1

    print(f"[gate] checkpoint   = {checkpoint}")
    print(f"[gate] episodes     = {args.episodes}")
    print(f"[gate] max_steps    = {args.max_steps}")
    print(f"[gate] eff_steps    = {args.effective_steps}")
    print(f"[gate] map          = {args.map_path}")
    print(f"[gate] device       = {args.device}")
    print(f"[gate] deterministic= {deterministic_mode}")
    print(f"[gate] output_dir   = {args.output_dir}")
    print(f"[gate] sampling     = {args.opponent_sampling}")

    model, algorithm_loader = load_model(checkpoint, args.device)
    print(f"[gate] loaded model = {algorithm_loader}")

    opponent_pool = parse_opponent_pool(args.opponent_pool)
    print(f"[gate] opponent_pool= {opponent_pool}")

    print("[gate] running actor-level audit ...")
    actor_result = run_actor_level_audit(
        model=model,
        opponent_pool=opponent_pool,
        opponent_sampling_mode=args.opponent_sampling,
        seed=args.seed,
        map_path=args.map_path,
        max_steps=args.max_steps,
        episodes=args.episodes,
        deterministic=deterministic_mode,
    )
    print(
        f"[gate] actor: full_tensor_move={actor_result['full_tensor_move_share']:.4f} "
        f"actor_move={actor_result['actor_level_move_share']:.4f} "
        f"actor_noop={actor_result['actor_noop_share']:.4f}"
    )

    effective_opponent, effective_opponent_selection = pick_effective_audit_opponent(
        opponent_pool,
        args.opponent_sampling,
        args.seed,
    )
    print(
        f"[gate] running effective-behavior audit ({args.effective_steps} steps) "
        f"against {effective_opponent} ..."
    )
    eff_result = run_effective_behavior_audit(
        model=model,
        map_path=args.map_path,
        max_steps=args.effective_steps,
        opponent=effective_opponent,
        deterministic=deterministic_mode,
    )
    print(
        f"[gate] eff: pos_deltas={eff_result['effective_position_delta_count']} "
        f"no_effect_share={eff_result['no_effect_action_share']:.4f}"
    )

    status, fail_reasons, warnings = evaluate_gate(actor_result, eff_result)

    full_move = actor_result["full_tensor_move_share"]
    actor_move = actor_result["actor_level_move_share"]
    actor_noop = actor_result["actor_noop_share"]
    movable_count = actor_result["ready_movable_actor_count"]
    pos_delta = eff_result["effective_position_delta_count"]
    no_effect_share = eff_result["no_effect_action_share"]
    chosen_count = eff_result["chosen_ready_own_actor_count"]

    decision_rules = {
        "FAIL_COLLAPSED_NOOP": {
            "triggered": any("FAIL_COLLAPSED_NOOP" in r for r in fail_reasons),
            "values": {
                "ready_movable_actor_count": movable_count,
                "actor_level_move_share": actor_move,
                "effective_position_delta_count": pos_delta,
                "actor_noop_share": actor_noop,
                "threshold_noop": 0.90,
            },
        },
        "FAIL_FALSE_FULL_TENSOR_MOVE": {
            "triggered": any("FAIL_FALSE_FULL_TENSOR_MOVE" in r for r in fail_reasons),
            "values": {
                "full_tensor_move_share": full_move,
                "actor_level_move_share": actor_move,
                "threshold_full": 0.10,
                "threshold_actor": 0.05,
            },
        },
        "FAIL_NO_EFFECT_BEHAVIOR": {
            "triggered": any("FAIL_NO_EFFECT_BEHAVIOR" in r for r in fail_reasons),
            "values": {
                "chosen_ready_own_actor_count": chosen_count,
                "no_effect_action_share": no_effect_share,
                "effective_position_delta_count": pos_delta,
                "threshold_no_effect": 0.80,
            },
        },
        "SUSPICIOUS": {
            "triggered": status == STATUS_SUSPICIOUS,
            "values": {
                "actor_noop_share": actor_noop,
                "no_effect_action_share": no_effect_share,
                "threshold_noop": 0.75,
                "threshold_no_effect": 0.60,
            },
        },
        "PASS": {
            "triggered": status == STATUS_PASS,
            "values": {
                "actor_level_move_share": actor_move,
                "effective_position_delta_count": pos_delta,
                "threshold_move": 0.05,
            },
        },
    }

    gate_output: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "checkpoint": str(checkpoint),
        "status": status,
        "deterministic_mode": deterministic_mode,
        "opponent_sampling_mode": args.opponent_sampling,
        "opponents_used": actor_result.get("opponents_used", []),
        "fail_reasons": fail_reasons,
        "warnings": warnings,
        "actor_level": {
            "full_tensor_move_share": actor_result["full_tensor_move_share"],
            "actor_level_move_share": actor_result["actor_level_move_share"],
            "actor_noop_share": actor_result["actor_noop_share"],
            "ready_own_actor_count": actor_result["ready_own_actor_count"],
            "steps_with_ready_actors": actor_result["steps_with_ready_actors"],
            "steps_with_movable_ready_actors": actor_result["steps_with_movable_ready_actors"],
            "ready_movable_actor_choice_count": actor_result["ready_movable_actor_choice_count"],
            "ready_movable_actor_count": actor_result["ready_movable_actor_count"],
        },
        "effective_behavior": {
            "effective_position_delta_count": eff_result["effective_position_delta_count"],
            "no_effect_action_share": eff_result["no_effect_action_share"],
            "chosen_ready_own_actor_count": eff_result["chosen_ready_own_actor_count"],
            "steps_executed": eff_result["steps_executed"],
        },
        "decision_rules": decision_rules,
        "meta": {
            "generated_at_utc": utc_now(),
            "algorithm_loader": algorithm_loader,
            "opponent": actor_result.get("opponents_used", [effective_opponent])[0],
            "opponent_pool": opponent_pool,
            "opponent_sampling_mode": args.opponent_sampling,
            "actor_audit_opponents_used": actor_result.get("opponents_used", []),
            "actor_audit_opponents_by_episode": actor_result.get("opponents_by_episode", []),
            "effective_behavior_opponent": effective_opponent,
            "effective_behavior_opponent_selection": effective_opponent_selection,
            "map_path": args.map_path,
            "episodes_actor_audit": args.episodes,
            "max_steps_per_episode": args.max_steps,
            "steps_effective_audit": args.effective_steps,
            "seed": args.seed,
            "device": args.device,
            "deterministic_mode": deterministic_mode,
            "method_limits": [
                "Gate runs inside Gym-microRTS only. Does NOT claim Gym->Unity semantic parity.",
                "Full-tensor Move share is NOT evidence of real movement.",
                "Effective-behavior state-diff is an observation proxy, not a confirmed execution stream.",
                "Actor-level analysis covers source_unit_mask==1 cells (teacher-owned ready units).",
            ],
        },
        "raw_actor_level": actor_result,
        "raw_effective_behavior": eff_result,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ckpt_stem = checkpoint.stem.replace(" ", "_")

    replay_info: Dict[str, Any] = {
        "created": False,
        "replay_trace_path": None,
        "replay_summary_path": None,
        "visual_notes_path": None,
        "frames_dir": None,
        "visual_verdict": None,
        "warnings": [],
    }
    if args.make_replay:
        replay_output_dir = args.replay_output_dir or (args.output_dir / f"replay_{ckpt_stem}")
        try:
            from render_teacher_checkpoint_replay import generate_replay_artifacts

            print(f"[gate] generating replay artifacts in {replay_output_dir} ...")
            replay_info = generate_replay_artifacts(
                checkpoint=checkpoint,
                episodes=args.episodes,
                max_steps=args.replay_steps,
                seed=args.seed,
                map_path=args.map_path,
                opponent_pool=opponent_pool,
                opponent_sampling=args.opponent_sampling,
                device=args.device,
                output_dir=replay_output_dir,
                render_mode="jsonl",
                fps=4,
            )
        except Exception as exc:
            replay_info["warnings"] = [f"Replay generation failed: {type(exc).__name__}: {exc}"]

    if replay_info.get("warnings"):
        warnings.extend(replay_info["warnings"])

    gate_output["visual_replay"] = replay_info
    gate_output["replay_trace_path"] = replay_info.get("replay_trace_path")
    gate_output["replay_summary_path"] = replay_info.get("replay_summary_path")
    gate_output["visual_notes_path"] = replay_info.get("visual_notes_path")
    gate_output["frames_dir"] = replay_info.get("frames_dir")

    json_path = args.output_dir / f"gate_{ckpt_stem}.json"
    md_path = args.output_dir / f"gate_{ckpt_stem}.md"

    json_path.write_text(
        json.dumps(gate_output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path.write_text(build_markdown(gate_output), encoding="utf-8")

    print(f"[gate] STATUS       = {status}")
    if fail_reasons:
        for r in fail_reasons:
            print(f"[gate] FAIL         : {r}")
    if warnings:
        for w in warnings:
            print(f"[gate] WARN         : {w}")
    print(f"[gate] wrote json   = {json_path}")
    print(f"[gate] wrote md     = {md_path}")

    return 2 if fail_reasons else 0


if __name__ == "__main__":
    raise SystemExit(main())
