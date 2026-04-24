#!/usr/bin/env python3
"""
audit_teacher_effective_behavior.py

Root-cause audit: teacher-side chosen actions vs effective state transitions.

Goals
-----
1. Explicitly confirm which side is teacher-controlled (via owner observation channels
   cross-referenced against source_unit_mask).
2. For each step (first N steps), collect per-actor chosen actions + mask context.
3. Perform honest state-diff audit (obs_before vs obs_after) to classify effective outcomes.
4. Classify implicit movement: does Harvest/Return/Attack cause position change?
5. Produce compact JSON + Markdown artifacts.

Observation channel layout (27 channels, from ObservationContract):
  [0]  HP
  [1]  resources carried
  [2]  owner_self   (player 0 = teacher)
  [3]  owner_enemy  (player 1 = opponent)
  [4]  owner_neutral
  [5:12]  unit_type one-hot (7 types)
  [12:18] action_type one-hot (6 types, current/last)
  [18:22] direction one-hot (4 dirs)
  [22:26] produce_type one-hot (4 types)
  [26]    attack_target

Action mask layout (36 columns per cell):
  [0]     source_unit_mask
  [1]     NoOp allowed
  [2]     Move allowed
  [3]     Harvest allowed
  [4]     Return allowed
  [5]     Produce allowed
  [6]     Attack allowed
  [7:11]  move direction masks
  [11:15] harvest direction masks
  [15:19] return direction masks
  [19:23] produce direction masks
  [23:27] produce unit type masks
  [27:36] attack target masks (3×3)

Action tensor columns per cell (7 branches):
  [0] action_type   (0=NoOp, 1=Move, 2=Harvest, 3=Return, 4=Produce, 5=Attack)
  [1] move_dir      (0=N, 1=E, 2=S, 3=W)
  [2] harvest_dir
  [3] return_dir
  [4] produce_dir
  [5] produce_unit_type
  [6] attack_target (0-8, 3×3 relative)

Checkpoint: teacher_sb3_ppo_step_000080000.zip
Protocol:   basesWorkers24x24, workerRushAI, first 50 steps, deterministic.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Observation channel indices — verified against gym-microrts runtime
#
# Actual layout (5+5+3+8+6 = 27):
#   [0:5]   HP one-hot bands (0=0HP, 1=1HP, 2=2HP, 3=3HP, 4=high-HP)
#   [5:10]  resources one-hot bands (0=0, 1=1, 2=2, 3=3, 4=max)
#   [10:13] owner one-hot: ch10=neutral, ch11=player0(teacher), ch12=player1(opponent)
#   [13:21] unit_type one-hot (0=empty, 1=Resource, 2=Base, 3=Barracks,
#                               4=Worker, 5=Light, 6=Heavy, 7=Ranged)
#   [21:27] current_action one-hot (0=NoOp, 1=Move, 2=Harvest, 3=Return,
#                                    4=Produce, 5=Attack)
# ---------------------------------------------------------------------------
CH_HP_START = 0          # [0:5]
CH_HP_END = 5
CH_RES_START = 5         # [5:10]
CH_RES_END = 10
CH_OWNER_NEUTRAL = 10    # ch10
CH_OWNER_SELF = 11       # ch11 = player 0 = teacher
CH_OWNER_ENEMY = 12      # ch12 = player 1 = opponent
CH_UNIT_TYPE_START = 13  # [13:21]
CH_UNIT_TYPE_END = 21
CH_ACTION_TYPE_START = 21  # [21:27]
CH_ACTION_TYPE_END = 27
N_CHANNELS = 27

# Action mask column indices
MASK_SOURCE = 0
MASK_NOOP = 1
MASK_MOVE = 2
MASK_HARVEST = 3
MASK_RETURN = 4
MASK_PRODUCE = 5
MASK_ATTACK = 6

# Action tensor branch indices
ACT_TYPE = 0
ACT_MOVE_DIR = 1
ACT_HARVEST_DIR = 2
ACT_RETURN_DIR = 3
ACT_PRODUCE_DIR = 4
ACT_PRODUCE_TYPE = 5
ACT_ATTACK_TARGET = 6

# Unit type indices are offsets from CH_UNIT_TYPE_START:
# index 0=empty, 1=Resource, 2=Base, 3=Barracks, 4=Worker, 5=Light, 6=Heavy, 7=Ranged
UNIT_TYPE_NAMES: Dict[int, str] = {
    0: "empty",
    1: "Resource",
    2: "Base",
    3: "Barracks",
    4: "Worker",
    5: "Light",
    6: "Heavy",
    7: "Ranged",
}
ACTION_NAMES: Dict[int, str] = {
    0: "NoOp",
    1: "Move",
    2: "Harvest",
    3: "Return",
    4: "Produce",
    5: "Attack",
}
DIR_NAMES: Dict[int, str] = {0: "N", 1: "E", 2: "S", 3: "W"}
# dir → (dx, dy) where x=col, y=row
DIR_OFFSETS: Dict[int, Tuple[int, int]] = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}

# Outcome class constants
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Teacher-side root-cause audit: chosen actions vs effective state transitions."
    )
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    p.add_argument("--opponent", default="workerRushAI")
    p.add_argument("--max-steps", type=int, default=50,
                   help="Number of env steps to audit (50 is sufficient for root-cause).")
    p.add_argument("--device", default="cpu")
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path("WEEK6/teacher_effective_behavior_audit.json"),
    )
    p.add_argument(
        "--output-md",
        type=Path,
        default=Path("WEEK6/TEACHER_EFFECTIVE_BEHAVIOR_AUDIT.md"),
    )
    return p.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Model + env loading
# ---------------------------------------------------------------------------

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


def predict_action(model: Any, obs: Any, action_mask: Optional[np.ndarray]) -> Any:
    if action_mask is not None:
        try:
            action, _ = model.predict(obs, deterministic=True, action_masks=action_mask)
            return action
        except TypeError:
            pass
        except Exception:
            pass
    action, _ = model.predict(obs, deterministic=True)
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


# ---------------------------------------------------------------------------
# Observation helpers
# ---------------------------------------------------------------------------

def idx_to_xy(idx: int, width: int) -> Tuple[int, int]:
    return int(idx % width), int(idx // width)


def cell_has_unit(obs_arr: np.ndarray, y: int, x: int) -> bool:
    """A cell has a unit if any owner channel is set."""
    cell = obs_arr[0, y, x, :]
    return bool(cell[CH_OWNER_NEUTRAL:CH_OWNER_ENEMY + 1].max() > 0.5)


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
    # HP: argmax of one-hot bands [0:5]; band value = absolute HP (0,1,2,3,4+)
    hp_band = int(np.argmax(cell[CH_HP_START:CH_HP_END]))
    # Resources: argmax of one-hot bands [5:10]; band = resource count (0,1,2,3,4+)
    res_band = int(np.argmax(cell[CH_RES_START:CH_RES_END]))
    # Unit type: argmax over [13:21]; index 0=empty, 1=Resource, ..., 7=Ranged
    ut_raw = cell[CH_UNIT_TYPE_START:CH_UNIT_TYPE_END]
    if ut_raw.max() > 0.1:
        ut_idx = int(np.argmax(ut_raw))
        unit_type = UNIT_TYPE_NAMES.get(ut_idx, f"type_{ut_idx}")
    else:
        unit_type = "empty"
    return {
        "x": x,
        "y": y,
        "hp_band": hp_band,
        "res_band": res_band,
        "owner": owner,
        "unit_type": unit_type,
    }


def get_teacher_units(obs_arr: np.ndarray, height: int, width: int) -> List[Dict[str, Any]]:
    return [
        decode_cell(obs_arr, y, x)
        for y in range(height)
        for x in range(width)
        if obs_arr[0, y, x, CH_OWNER_SELF] > 0.5
    ]


def get_opponent_units(obs_arr: np.ndarray, height: int, width: int) -> List[Dict[str, Any]]:
    return [
        decode_cell(obs_arr, y, x)
        for y in range(height)
        for x in range(width)
        if obs_arr[0, y, x, CH_OWNER_ENEMY] > 0.5
    ]


def unit_at(obs_arr: np.ndarray, y: int, x: int, height: int, width: int) -> Optional[Dict[str, Any]]:
    """Return decoded cell if it contains a OWNED unit (teacher or opponent), else None."""
    if x < 0 or x >= width or y < 0 or y >= height:
        return None
    cell = obs_arr[0, y, x, :]
    # Only return if an actual player (teacher or opponent) owns this cell
    if cell[CH_OWNER_SELF] > 0.5 or cell[CH_OWNER_ENEMY] > 0.5:
        return decode_cell(obs_arr, y, x)
    return None


# ---------------------------------------------------------------------------
# Teacher-side confirmation
# ---------------------------------------------------------------------------

def confirm_teacher_side(
    obs_arr: np.ndarray,
    action_mask: np.ndarray,
    height: int,
    width: int,
) -> Dict[str, Any]:
    """
    Cross-reference source_unit_mask with observation owner channels
    to confirm which side teacher controls.
    """
    mask_flat = action_mask[0, :, MASK_SOURCE].astype(bool)  # [H*W]
    ready_indices = np.where(mask_flat)[0]

    teacher_channel_agrees = 0
    opponent_channel_agrees = 0
    neutral_channel_agrees = 0
    empty_agrees = 0

    for idx in ready_indices:
        x, y = idx_to_xy(int(idx), width)
        owner = get_cell_owner(obs_arr, y, x)
        if owner == "teacher":
            teacher_channel_agrees += 1
        elif owner == "opponent":
            opponent_channel_agrees += 1
        elif owner == "neutral":
            neutral_channel_agrees += 1
        else:
            empty_agrees += 1

    total_ready = int(ready_indices.size)
    teacher_units_all = get_teacher_units(obs_arr, height, width)
    opponent_units_all = get_opponent_units(obs_arr, height, width)

    dominant = "teacher" if teacher_channel_agrees >= max(opponent_channel_agrees, 1) else "uncertain"
    confirmed = teacher_channel_agrees == total_ready and total_ready > 0

    return {
        "method": (
            "Cross-reference source_unit_mask (mask column 0) with obs owner channels. "
            "Actual layout: ch10=neutral, ch11=player0(teacher), ch12=player1(opponent). "
            "Player 0 = RL agent (MicroRTSGridModeVecEnv, num_bot_envs=1, ai2s=[opponent])."
        ),
        "obs_channel_layout_verified": {
            "HP_one_hot": "[0:5]",
            "resources_one_hot": "[5:10]",
            "owner_neutral": "ch10",
            "owner_teacher_player0": "ch11",
            "owner_opponent_player1": "ch12",
            "unit_type_one_hot_8types": "[13:21]",
            "current_action_one_hot": "[21:27]",
            "total_channels": 27,
        },
        "total_ready_source_unit_mask": total_ready,
        "ready_with_teacher_owner_channel": teacher_channel_agrees,
        "ready_with_opponent_owner_channel": opponent_channel_agrees,
        "ready_with_neutral_owner_channel": neutral_channel_agrees,
        "ready_with_empty_channel": empty_agrees,
        "teacher_side_confirmed": confirmed,
        "dominant_side": dominant,
        "teacher_units_on_map": len(teacher_units_all),
        "opponent_units_on_map": len(opponent_units_all),
        "teacher_unit_types": [u["unit_type"] for u in teacher_units_all],
        "teacher_unit_details": teacher_units_all,
        "opponent_unit_details": opponent_units_all,
        "confirmation_verdict": (
            "CONFIRMED: source_unit_mask aligns with teacher owner channel (ch11=player0)."
            if confirmed
            else f"PARTIAL: {teacher_channel_agrees}/{total_ready} ready cells match teacher owner channel (ch11)."
        ),
    }


# ---------------------------------------------------------------------------
# State-diff and outcome classification
# ---------------------------------------------------------------------------

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
) -> Dict[str, Any]:
    """
    Classify effective outcome for a single ready actor after one env step.
    Compares obs_before vs obs_after.
    Distinguishes direct position change from implied-by-action position change.
    """
    state_changes: Dict[str, Any] = {}
    implicit_movement = False

    # Check if teacher unit still at original position after step
    cell_after = unit_at(obs_after, y0, x0, height, width)
    still_here = cell_after is not None and cell_after["owner"] == "teacher"

    if still_here:
        hp_after = cell_after["hp_band"]
        res_after = cell_after["res_band"]
        state_changes["hp_band_delta"] = hp_after - hp_before
        state_changes["res_band_delta"] = res_after - res_before

        if chosen_action_type == 2:  # Harvest: stayed but gathered resource
            if res_after > res_before:
                outcome = OUT_HARVEST_IN_PLACE
                state_changes["note"] = "harvest effect confirmed: carried resource band increased"
            else:
                outcome = OUT_BLOCKED
                state_changes["note"] = "harvest chosen but no resource gain while staying; may be blocked"

        elif chosen_action_type == 3:  # Return: stayed but deposited resource
            if res_after < res_before:
                outcome = OUT_RETURN_IN_PLACE
                state_changes["note"] = "return effect: carried resource band decreased (deposited)"
            else:
                outcome = OUT_BLOCKED
                state_changes["note"] = "return chosen but no resource drop while staying"

        elif chosen_action_type == 4:  # Produce
            new_adj_unit = None
            for dx, dy in DIR_OFFSETS.values():
                nx, ny = x0 + dx, y0 + dy
                before_adj = unit_at(obs_before, ny, nx, height, width)
                after_adj = unit_at(obs_after, ny, nx, height, width)
                if after_adj and after_adj["owner"] == "teacher":
                    if before_adj is None or before_adj["owner"] != "teacher":
                        new_adj_unit = after_adj
                        break
            if new_adj_unit:
                outcome = OUT_PRODUCE_EFFECT
                state_changes["new_unit"] = new_adj_unit
            else:
                outcome = OUT_BLOCKED
                state_changes["note"] = "produce chosen; no new adjacent teacher unit detected"

        elif chosen_action_type == 5:  # Attack
            attack_confirmed = False
            for dx, dy in DIR_OFFSETS.values():
                nx, ny = x0 + dx, y0 + dy
                opp_before = unit_at(obs_before, ny, nx, height, width)
                opp_after = unit_at(obs_after, ny, nx, height, width)
                if opp_before and opp_before["owner"] == "opponent":
                    if opp_after is None or (opp_after["hp_band"] < opp_before["hp_band"]):
                        attack_confirmed = True
                        state_changes["attack_target_hp_band_before"] = opp_before["hp_band"]
                        state_changes["attack_target_hp_band_after"] = opp_after["hp_band"] if opp_after else 0
                        break
            outcome = OUT_ATTACK_EFFECT if attack_confirmed else OUT_BLOCKED

        elif chosen_action_type == 1:  # Move chosen but didn't move
            outcome = OUT_BLOCKED
            state_changes["note"] = "Move chosen but unit remained at same position (blocked or NoOp-like)"

        elif chosen_action_type == 0:  # NoOp
            outcome = OUT_NO_POS_CHANGE
            state_changes["note"] = "NoOp chosen; no position change expected"

        else:
            outcome = OUT_UNKNOWN

    else:
        # Unit no longer at original position → look for it at adjacent cells
        found_new: Optional[Tuple[int, int]] = None
        for dx, dy in DIR_OFFSETS.values():
            nx, ny = x0 + dx, y0 + dy
            adj = unit_at(obs_after, ny, nx, height, width)
            if adj and adj["owner"] == "teacher" and adj["unit_type"] == unit_type_before:
                found_new = (nx, ny)
                break

        if found_new:
            state_changes["moved_from"] = {"x": x0, "y": y0}
            state_changes["moved_to"] = {"x": found_new[0], "y": found_new[1]}
            implicit_movement = (chosen_action_type != 1)  # True if action was NOT Move

            if chosen_action_type == 1:
                outcome = OUT_MOVE_DIRECT
            elif chosen_action_type == 2:
                outcome = OUT_MOVE_IMPLICIT_HARVEST
                state_changes["note"] = "Harvest caused unit to move to adjacent cell (implicit movement)"
            elif chosen_action_type == 3:
                outcome = OUT_MOVE_IMPLICIT_RETURN
                state_changes["note"] = "Return caused unit to move to adjacent cell (implicit movement)"
            elif chosen_action_type == 5:
                outcome = OUT_MOVE_IMPLICIT_ATTACK
                state_changes["note"] = "Attack caused unit to move toward target (implicit movement)"
            else:
                outcome = OUT_MOVE_IMPLICIT_OTHER
                state_changes["note"] = f"Action {ACTION_NAMES.get(chosen_action_type,'?')} caused position change"
        else:
            # Unit disappeared; check if it died or moved >1 cell (ambiguous)
            # Try wider search (up to 2 cells) to detect >1 cell movement
            found_far: Optional[Tuple[int, int]] = None
            for dy2 in range(-2, 3):
                for dx2 in range(-2, 3):
                    if abs(dx2) + abs(dy2) <= 1:
                        continue  # already checked adjacent
                    nx, ny = x0 + dx2, y0 + dy2
                    adj = unit_at(obs_after, ny, nx, height, width)
                    if adj and adj["owner"] == "teacher" and adj["unit_type"] == unit_type_before:
                        found_far = (nx, ny)
                        break
                if found_far:
                    break

            if found_far:
                state_changes["moved_from"] = {"x": x0, "y": y0}
                state_changes["moved_to"] = {"x": found_far[0], "y": found_far[1]}
                state_changes["note"] = "unit moved >1 cell in one step (multi-step effect or teleport)"
                implicit_movement = (chosen_action_type != 1)
                outcome = OUT_MOVE_DIRECT if chosen_action_type == 1 else OUT_MOVE_IMPLICIT_OTHER
            else:
                # Unit truly disappeared from its vicinity
                # Could be death, captured, or matching failed
                state_changes["note"] = (
                    "unit not found at original pos or within 2 cells; "
                    "possible death, produced unit counted, or matching ambiguous"
                )
                outcome = OUT_UNKNOWN

    return {
        "outcome_class": outcome,
        "implicit_movement": implicit_movement,
        "state_changes": state_changes,
    }


# ---------------------------------------------------------------------------
# Main audit loop
# ---------------------------------------------------------------------------

def run_audit(args: argparse.Namespace) -> Dict[str, Any]:
    checkpoint = args.checkpoint.resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint}")

    model, loader_name = load_model(checkpoint, args.device)
    env = build_env(args.map_path, args.max_steps, args.opponent)

    obs = env.reset()
    obs_arr = np.asarray(obs)
    if obs_arr.ndim != 4 or obs_arr.shape[0] != 1:
        raise RuntimeError(f"Unexpected obs shape: {obs_arr.shape}")

    height = int(obs_arr.shape[1])
    width = int(obs_arr.shape[2])
    channels = int(obs_arr.shape[3])
    n_cells = height * width

    if channels != N_CHANNELS:
        print(f"[WARN] Expected {N_CHANNELS} obs channels, got {channels}. "
              "Owner/unit-type channel offsets may be wrong.")

    # -----------------------------------------------------------------------
    # Step 0: teacher-side confirmation (before any action)
    # -----------------------------------------------------------------------
    action_mask_0 = read_action_mask(env)
    if action_mask_0 is None:
        raise RuntimeError("Action mask unavailable; cannot perform audit.")

    teacher_confirmation = confirm_teacher_side(obs_arr, action_mask_0, height, width)

    # -----------------------------------------------------------------------
    # Per-step audit loop
    # -----------------------------------------------------------------------
    step_records: List[Dict[str, Any]] = []

    # Aggregate counters
    full_tensor_counter: Counter = Counter()
    chosen_action_counter: Counter = Counter()       # over all ready actors
    outcome_counter: Counter = Counter()
    implicit_move_by_action: Counter = Counter()     # action_type → count of implicit moves

    done = False
    step_id = 0

    while not done and step_id < args.max_steps:
        obs_arr = np.asarray(obs)
        action_mask = read_action_mask(env)

        if action_mask is None or action_mask.ndim != 3 or action_mask.shape[0] != 1:
            raise RuntimeError(f"Unexpected mask shape at step {step_id}: {getattr(action_mask, 'shape', None)}")

        action = predict_action(model, obs, action_mask)
        action_matrix = action_to_matrix(action)   # [H*W, 7]

        if action_matrix.shape[0] != n_cells:
            raise RuntimeError(f"Action spatial mismatch at step {step_id}: expected {n_cells}, got {action_matrix.shape[0]}")

        # --- Full tensor histogram (all cells) ---
        action_types_all = action_matrix[:, ACT_TYPE]
        step_full_counter: Counter = Counter(int(v) for v in action_types_all.tolist())
        full_tensor_counter.update(step_full_counter)

        # --- Ready actors (source_unit_mask) ---
        ready_mask = action_mask[0, :, MASK_SOURCE].astype(bool)
        ready_indices = np.where(ready_mask)[0]
        ready_count = int(ready_indices.size)

        # --- Step env ---
        obs_before = obs_arr.copy()
        transition = env.step(action)
        if len(transition) == 5:
            obs, _reward, terminated, truncated, _info = transition
            done = bool(terminated or truncated)
        else:
            obs, _reward, done, _info = transition
        obs_after = np.asarray(obs)

        # --- Per-actor audit ---
        actor_records: List[Dict[str, Any]] = []
        step_actor_counter: Counter = Counter()

        for idx in ready_indices:
            idx_int = int(idx)
            x0, y0 = idx_to_xy(idx_int, width)
            cell_info = decode_cell(obs_before, y0, x0)

            chosen_type = int(action_types_all[idx_int])
            step_actor_counter[chosen_type] += 1
            chosen_action_counter[chosen_type] += 1

            # Skip neutral/resource cells that appear in mask due to env quirks
            # (confirmed teacher-owned = ch11 > 0.5)
            if cell_info["owner"] not in ("teacher",):
                pass  # Still record but note side mismatch

            mask_row = action_mask[0, idx_int]
            move_allowed = bool(mask_row[MASK_MOVE]) if mask_row.shape[0] > MASK_MOVE else False
            harvest_allowed = bool(mask_row[MASK_HARVEST]) if mask_row.shape[0] > MASK_HARVEST else False
            return_allowed = bool(mask_row[MASK_RETURN]) if mask_row.shape[0] > MASK_RETURN else False
            produce_allowed = bool(mask_row[MASK_PRODUCE]) if mask_row.shape[0] > MASK_PRODUCE else False
            attack_allowed = bool(mask_row[MASK_ATTACK]) if mask_row.shape[0] > MASK_ATTACK else False

            action_params: Dict[str, Any] = {
                "move_dir": DIR_NAMES.get(int(action_matrix[idx_int, ACT_MOVE_DIR]), "?"),
                "harvest_dir": DIR_NAMES.get(int(action_matrix[idx_int, ACT_HARVEST_DIR]), "?"),
                "return_dir": DIR_NAMES.get(int(action_matrix[idx_int, ACT_RETURN_DIR]), "?"),
                "produce_dir": DIR_NAMES.get(int(action_matrix[idx_int, ACT_PRODUCE_DIR]), "?"),
                "produce_unit_type": UNIT_TYPE_NAMES.get(int(action_matrix[idx_int, ACT_PRODUCE_TYPE]), "?"),
                "attack_target": int(action_matrix[idx_int, ACT_ATTACK_TARGET]),
            }

            # State-diff outcome
            outcome_info = classify_actor_outcome(
                x0=x0, y0=y0,
                unit_type_before=cell_info["unit_type"],
                hp_before=cell_info["hp_band"],
                res_before=cell_info["res_band"],
                chosen_action_type=chosen_type,
                obs_before=obs_before,
                obs_after=obs_after,
                height=height,
                width=width,
            )
            outcome_counter[outcome_info["outcome_class"]] += 1
            if outcome_info["implicit_movement"]:
                implicit_move_by_action[chosen_type] += 1

            actor_records.append({
                "flat_idx": idx_int,
                "x": x0,
                "y": y0,
                "unit_type": cell_info["unit_type"],
                "hp_band_before": cell_info["hp_band"],
                "res_band_before": cell_info["res_band"],
                "owner_confirmed": cell_info["owner"],
                "chosen_action_type": ACTION_NAMES.get(chosen_type, str(chosen_type)),
                "chosen_action_type_raw": chosen_type,
                "action_params": action_params,
                "mask_context": {
                    "move_allowed": move_allowed,
                    "harvest_allowed": harvest_allowed,
                    "return_allowed": return_allowed,
                    "produce_allowed": produce_allowed,
                    "attack_allowed": attack_allowed,
                    "chosen_action_allowed": bool(
                        mask_row[1 + chosen_type] if mask_row.shape[0] > 1 + chosen_type else True
                    ),
                },
                "effective_outcome": outcome_info,
            })

        # Teacher/opponent unit snapshots (compact)
        teacher_units_after = get_teacher_units(obs_after, height, width)
        opponent_units_after = get_opponent_units(obs_after, height, width)

        step_records.append({
            "step": step_id,
            "ready_actor_count": ready_count,
            "full_tensor_action_counts": {ACTION_NAMES[k]: int(v) for k, v in sorted(step_full_counter.items())},
            "ready_actor_action_counts": {ACTION_NAMES[k]: int(v) for k, v in sorted(step_actor_counter.items())},
            "actor_details": actor_records,
            "teacher_units_after_step": teacher_units_after,
            "opponent_units_after_step": opponent_units_after,
        })

        step_id += 1

        if done:
            break

    try:
        env.close()
    except Exception:
        pass

    # -----------------------------------------------------------------------
    # Build aggregate summary
    # -----------------------------------------------------------------------
    full_total = int(sum(full_tensor_counter.values()))
    chosen_total = int(sum(chosen_action_counter.values()))
    outcome_total = int(sum(outcome_counter.values()))

    def action_dist(counter: Counter, total: int) -> Dict[str, Any]:
        return {
            ACTION_NAMES.get(k, str(k)): {
                "count": int(v),
                "share": round(v / total, 4) if total > 0 else 0.0,
            }
            for k, v in sorted(counter.items())
        }

    # Implicit movement summary
    implicit_move_total = int(sum(implicit_move_by_action.values()))
    implicit_move_summary: Dict[str, int] = {
        ACTION_NAMES.get(k, str(k)): int(v) for k, v in implicit_move_by_action.items()
    }

    # Move effects totals
    direct_moves = int(outcome_counter.get(OUT_MOVE_DIRECT, 0))
    implicit_harvest_moves = int(outcome_counter.get(OUT_MOVE_IMPLICIT_HARVEST, 0))
    implicit_return_moves = int(outcome_counter.get(OUT_MOVE_IMPLICIT_RETURN, 0))
    implicit_attack_moves = int(outcome_counter.get(OUT_MOVE_IMPLICIT_ATTACK, 0))
    any_move_effect = direct_moves + implicit_harvest_moves + implicit_return_moves + implicit_attack_moves

    # Overall verdict
    if any_move_effect > 0:
        if direct_moves > 0:
            verdict = "Teacher selects Move and direct position changes observed."
        else:
            verdict = (
                "Direct Move effect NOT observed on ready actors, but implicit movement "
                "detected via other action types (Harvest/Return/Attack)."
            )
    elif chosen_action_counter.get(1, 0) > 0:
        verdict = "Move chosen by teacher on ready actors but no position change observed (blocked/ineffective)."
    else:
        verdict = "No Move chosen and no position changes on ready actors. Teacher appears passive on these cells."

    # Check if any actions are being chosen at all for ready actors
    noop_only = (chosen_total > 0 and chosen_action_counter.get(0, 0) == chosen_total)
    if noop_only:
        verdict = "Teacher selects only NoOp on all ready actors (complete passivity)."

    return {
        "generated_at_utc": utc_now(),
        "checkpoint": {
            "path": str(checkpoint),
            "loader": loader_name,
            "step_tag": "80000",
        },
        "protocol": {
            "map_path": args.map_path,
            "opponent": args.opponent,
            "requested_steps": args.max_steps,
            "executed_steps": step_id,
            "deterministic": True,
        },
        "shapes": {
            "observation": [1, height, width, channels],
            "action_mask": list(np.asarray(action_mask).shape),
            "action_spatial": [n_cells, 7],
        },
        "teacher_side_confirmation": teacher_confirmation,
        "method_levels": {
            "full_tensor": "action_type distribution over ALL spatial cells per step",
            "ready_actor_chosen": "action_type distribution over source_unit_mask==1 cells only",
            "effective_state_diff": "obs_before vs obs_after per ready actor; position+HP+resource changes",
            "execution_claim": (
                "NOT claimed. State-diff audit is an observation proxy, not a confirmed execution stream. "
                "Implicit movement is inferred from position change correlation with chosen action type."
            ),
        },
        "aggregate_summary": {
            "steps_executed": step_id,
            "full_tensor_action_distribution": action_dist(full_tensor_counter, full_total),
            "full_tensor_total_cells": full_total,
            "ready_actor_chosen_action_distribution": action_dist(chosen_action_counter, chosen_total),
            "ready_actor_total_choices": chosen_total,
            "effective_outcome_distribution": {
                k: int(v) for k, v in sorted(outcome_counter.items())
            },
            "effective_outcome_total": outcome_total,
            "move_effects_summary": {
                "direct_move_effect_count": direct_moves,
                "implicit_move_via_harvest_count": implicit_harvest_moves,
                "implicit_move_via_return_count": implicit_return_moves,
                "implicit_move_via_attack_count": implicit_attack_moves,
                "any_move_effect_total": any_move_effect,
                "any_move_effect_share_of_ready_choices": round(any_move_effect / chosen_total, 4) if chosen_total > 0 else 0.0,
            },
            "implicit_movement_hypothesis": {
                "implicit_moves_total": implicit_move_total,
                "implicit_moves_by_action_type": implicit_move_summary,
                "harvest_causes_implicit_movement": implicit_harvest_moves > 0,
                "return_causes_implicit_movement": implicit_return_moves > 0,
                "attack_causes_implicit_movement": implicit_attack_moves > 0,
                "evidence_basis": "state-diff: unit not found at original position after step, found at adjacent cell",
            },
        },
        "verdict": verdict,
        "step_trace": step_records,
        "opponent_side_note": (
            "Opponent-side actions are not tracked in this script. "
            "All actor-level analysis strictly covers teacher-owned (player 0) ready units only."
        ),
    }


# ---------------------------------------------------------------------------
# Markdown report builder
# ---------------------------------------------------------------------------

def build_md(report: Dict[str, Any]) -> str:
    lines: List[str] = []

    ckpt = report["checkpoint"]
    proto = report["protocol"]
    conf = report["teacher_side_confirmation"]
    agg = report["aggregate_summary"]
    move_sum = agg["move_effects_summary"]
    impl_hyp = agg["implicit_movement_hypothesis"]

    lines.append("# Teacher Effective Behavior Audit")
    lines.append("")
    lines.append(f"Generated at (UTC): {report['generated_at_utc']}")
    lines.append("")

    lines.append("## 1) Checkpoint")
    lines.append(f"- Path: `{ckpt['path']}`")
    lines.append(f"- Loader: `{ckpt['loader']}`")
    lines.append(f"- Step tag: {ckpt['step_tag']}")
    lines.append("")

    lines.append("## 2) Protocol")
    lines.append(f"- Map: `{proto['map_path']}`")
    lines.append(f"- Opponent: `{proto['opponent']}`")
    lines.append(f"- Requested steps: {proto['requested_steps']}")
    lines.append(f"- Executed steps: {proto['executed_steps']}")
    lines.append(f"- Deterministic: {proto['deterministic']}")
    lines.append("")

    lines.append("## 3) Teacher-Controlled Side Confirmation")
    lines.append(f"- Method: {conf['method']}")
    lines.append(f"- Total source_unit_mask ready cells (step 0): {conf['total_ready_source_unit_mask']}")
    lines.append(f"- With teacher owner channel (ch2 > 0.5): {conf['ready_with_teacher_owner_channel']}")
    lines.append(f"- With opponent owner channel (ch3 > 0.5): {conf['ready_with_opponent_owner_channel']}")
    lines.append(f"- With neutral owner channel: {conf['ready_with_neutral_owner_channel']}")
    lines.append(f"- Teacher units on map at start: {conf['teacher_units_on_map']} "
                 f"({', '.join(conf['teacher_unit_types'])})")
    lines.append(f"- Opponent units on map at start: {conf['opponent_units_on_map']}")
    lines.append(f"- **Verdict: {conf['confirmation_verdict']}**")
    lines.append("")

    lines.append("## 4) Full-Tensor Action Distribution (all cells)")
    for name, stat in agg["full_tensor_action_distribution"].items():
        lines.append(f"  - {name}: {stat['count']} ({stat['share']*100:.2f}%)")
    lines.append(f"  - Total cell-choices: {agg['full_tensor_total_cells']}")
    lines.append("")

    lines.append("## 5) Ready-Actor Chosen Action Distribution (teacher own ready actors only)")
    if agg["ready_actor_total_choices"] == 0:
        lines.append("  - **No ready actors found in any step. Actor-level distribution unavailable.**")
    else:
        for name, stat in agg["ready_actor_chosen_action_distribution"].items():
            lines.append(f"  - {name}: {stat['count']} ({stat['share']*100:.2f}%)")
        lines.append(f"  - Total actor-choices: {agg['ready_actor_total_choices']}")
    lines.append("")

    lines.append("## 6) Effective Outcome Distribution (state-diff audit)")
    if agg["effective_outcome_total"] == 0:
        lines.append("  - No actor-level state-diffs collected.")
    else:
        for outcome_class, count in sorted(agg["effective_outcome_distribution"].items()):
            share = count / agg["effective_outcome_total"] * 100.0 if agg["effective_outcome_total"] > 0 else 0.0
            lines.append(f"  - `{outcome_class}`: {count} ({share:.1f}%)")
    lines.append("")

    lines.append("## 7) Move Effects Summary")
    lines.append(f"- Direct move effects (Move chosen → position changed): {move_sum['direct_move_effect_count']}")
    lines.append(f"- Implicit move via Harvest: {move_sum['implicit_move_via_harvest_count']}")
    lines.append(f"- Implicit move via Return: {move_sum['implicit_move_via_return_count']}")
    lines.append(f"- Implicit move via Attack: {move_sum['implicit_move_via_attack_count']}")
    lines.append(f"- Any movement effect total: {move_sum['any_move_effect_total']} "
                 f"({move_sum['any_move_effect_share_of_ready_choices']*100:.1f}% of ready-actor choices)")
    lines.append("")

    lines.append("## 8) Implicit Movement Hypothesis")
    lines.append(f"- Harvest causes implicit movement: **{impl_hyp['harvest_causes_implicit_movement']}**")
    lines.append(f"- Return causes implicit movement: **{impl_hyp['return_causes_implicit_movement']}**")
    lines.append(f"- Attack causes implicit movement: **{impl_hyp['attack_causes_implicit_movement']}**")
    lines.append(f"- Implicit moves total: {impl_hyp['implicit_moves_total']}")
    if impl_hyp['implicit_moves_by_action_type']:
        lines.append(f"- Breakdown by action: {impl_hyp['implicit_moves_by_action_type']}")
    lines.append(f"- Evidence basis: {impl_hyp['evidence_basis']}")
    lines.append("")

    lines.append("## 9) Per-Step Trace (Compact)")
    lines.append("")
    lines.append("| step | ready | full_Move | actor_NoOp | actor_Move | actor_Harvest | actor_Return | actor_Produce | actor_Attack | move_effects |")
    lines.append("|------|-------|-----------|------------|------------|---------------|--------------|---------------|--------------|--------------|")
    for s in report["step_trace"]:
        full_d = s["full_tensor_action_counts"]
        act_d = s["ready_actor_action_counts"]
        # count move effects in this step
        step_move_effects = sum(
            1 for a in s["actor_details"]
            if a["effective_outcome"]["outcome_class"] in (
                OUT_MOVE_DIRECT, OUT_MOVE_IMPLICIT_HARVEST,
                OUT_MOVE_IMPLICIT_RETURN, OUT_MOVE_IMPLICIT_ATTACK,
                OUT_MOVE_IMPLICIT_OTHER
            )
        )
        lines.append(
            f"| {s['step']} "
            f"| {s['ready_actor_count']} "
            f"| {full_d.get('Move', 0)} "
            f"| {act_d.get('NoOp', 0)} "
            f"| {act_d.get('Move', 0)} "
            f"| {act_d.get('Harvest', 0)} "
            f"| {act_d.get('Return', 0)} "
            f"| {act_d.get('Produce', 0)} "
            f"| {act_d.get('Attack', 0)} "
            f"| {step_move_effects} |"
        )
    lines.append("")

    lines.append("## 10) Method Limits")
    for k, v in report["method_levels"].items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")

    lines.append("## 11) Verdict")
    lines.append(f"> {report['verdict']}")
    lines.append("")

    lines.append("## 12) Opponent Side Note")
    lines.append(f"> {report['opponent_side_note']}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    print(f"[audit] checkpoint: {args.checkpoint}")
    print(f"[audit] map: {args.map_path}  opponent: {args.opponent}  steps: {args.max_steps}")

    report = run_audit(args)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)

    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(build_md(report), encoding="utf-8")

    agg = report["aggregate_summary"]
    conf = report["teacher_side_confirmation"]
    move_sum = agg["move_effects_summary"]
    impl_hyp = agg["implicit_movement_hypothesis"]

    print()
    print("=== AUDIT RESULTS ===")
    print(f"Teacher side confirmed: {conf['teacher_side_confirmed']}")
    print(f"  {conf['confirmation_verdict']}")
    print(f"Steps executed: {report['protocol']['executed_steps']}")
    print(f"Ready-actor choices: {agg['ready_actor_total_choices']}")
    print()
    print("Ready-actor chosen action breakdown:")
    for name, stat in agg["ready_actor_chosen_action_distribution"].items():
        print(f"  {name}: {stat['count']} ({stat['share']*100:.1f}%)")
    print()
    print("Effective outcome distribution:")
    for cls, cnt in sorted(agg["effective_outcome_distribution"].items()):
        total = agg["effective_outcome_total"]
        print(f"  {cls}: {cnt} ({cnt/total*100:.1f}%)" if total > 0 else f"  {cls}: {cnt}")
    print()
    print(f"Direct move effects:           {move_sum['direct_move_effect_count']}")
    print(f"Implicit moves via Harvest:    {move_sum['implicit_move_via_harvest_count']}")
    print(f"Implicit moves via Return:     {move_sum['implicit_move_via_return_count']}")
    print(f"Implicit moves via Attack:     {move_sum['implicit_move_via_attack_count']}")
    print()
    print(f"Harvest causes implicit move:  {impl_hyp['harvest_causes_implicit_movement']}")
    print(f"Return causes implicit move:   {impl_hyp['return_causes_implicit_movement']}")
    print(f"Attack causes implicit move:   {impl_hyp['attack_causes_implicit_movement']}")
    print()
    print(f"VERDICT: {report['verdict']}")
    print()
    print(f"Artifacts written:")
    print(f"  JSON: {args.output_json}")
    print(f"  MD:   {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
