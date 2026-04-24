#!/usr/bin/env python3
"""
render_teacher_checkpoint_replay.py

Human-readable replay artifact generator for teacher checkpoints.

Primary goal:
- replay_trace.jsonl
- replay_summary.json
- visual_notes.md

Optional best-effort frame export is supported, but failures do not break artifact generation.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

CH_HP_START = 0
CH_HP_END = 5
CH_RES_START = 5
CH_RES_END = 10
CH_OWNER_NEUTRAL = 10
CH_OWNER_SELF = 11
CH_OWNER_ENEMY = 12
CH_UNIT_TYPE_START = 13
CH_UNIT_TYPE_END = 21

MASK_SOURCE = 0
ACT_TYPE = 0

DIR_NAMES: Dict[int, str] = {0: "N", 1: "E", 2: "S", 3: "W"}
ACTION_NAMES: Dict[int, str] = {
    0: "NoOp", 1: "Move", 2: "Harvest", 3: "Return", 4: "Produce", 5: "Attack",
}
UNIT_TYPE_NAMES: Dict[int, str] = {
    0: "empty", 1: "Resource", 2: "Base", 3: "Barracks",
    4: "Worker", 5: "Light", 6: "Heavy", 7: "Ranged",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate replay artifacts for a teacher checkpoint.")
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--episodes", type=int, default=4)
    p.add_argument("--max-steps", type=int, default=300)
    p.add_argument("--seed", type=int, default=170)
    p.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    p.add_argument("--opponent-pool", default="coacAI,workerRushAI,lightRushAI,passiveAI")
    p.add_argument("--opponent-sampling", choices=("static", "per_episode"), default="per_episode")
    p.add_argument("--device", default="cpu")
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--render-mode", choices=("frames", "jsonl", "both"), default="jsonl")
    p.add_argument("--fps", type=int, default=6)
    return p.parse_args()


def parse_opponent_pool(raw: str) -> List[str]:
    parsed = [t.strip() for t in raw.split(",") if t.strip()]
    if not parsed:
        raise RuntimeError("Opponent pool is empty.")
    return parsed


def pick_opponent(pool: List[str], mode: str, seed: int, episode_id: int) -> str:
    if mode == "static":
        return pool[0]
    return random.Random(seed + 103 + (episode_id * 9973)).choice(pool)


def load_model(checkpoint: Path, device: str) -> Tuple[Any, str]:
    errors: List[str] = []
    try:
        from sb3_contrib import MaskablePPO

        return MaskablePPO.load(str(checkpoint), device=device, print_system_info=False), "sb3_contrib.MaskablePPO"
    except Exception as exc:
        errors.append(f"MaskablePPO: {type(exc).__name__}: {exc}")

    try:
        from stable_baselines3 import PPO

        return PPO.load(str(checkpoint), device=device, print_system_info=False), "stable_baselines3.PPO"
    except Exception as exc:
        errors.append(f"PPO: {type(exc).__name__}: {exc}")

    raise RuntimeError("Failed to load checkpoint. " + " | ".join(errors))


def build_env(map_path: str, max_steps: int, opponent_name: str):
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


def idx_to_xy(idx: int, width: int) -> Tuple[int, int]:
    return int(idx % width), int(idx // width)


def decode_cell(obs_arr: np.ndarray, y: int, x: int) -> Dict[str, Any]:
    cell = obs_arr[0, y, x, :]
    hp_band = int(np.argmax(cell[CH_HP_START:CH_HP_END]))
    res_band = int(np.argmax(cell[CH_RES_START:CH_RES_END]))
    ut_raw = cell[CH_UNIT_TYPE_START:CH_UNIT_TYPE_END]
    unit_type = UNIT_TYPE_NAMES.get(int(np.argmax(ut_raw)), "empty") if ut_raw.max() > 0.1 else "empty"

    if cell[CH_OWNER_SELF] > 0.5:
        owner = "teacher"
    elif cell[CH_OWNER_ENEMY] > 0.5:
        owner = "opponent"
    elif cell[CH_OWNER_NEUTRAL] > 0.5:
        owner = "neutral"
    else:
        owner = "empty"

    return {
        "x": int(x),
        "y": int(y),
        "owner": owner,
        "unit_type": unit_type,
        "hp_band": hp_band,
        "res_band": res_band,
    }


def extract_entities(obs_arr: np.ndarray) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    height = int(obs_arr.shape[1])
    width = int(obs_arr.shape[2])
    teacher_units: List[Dict[str, Any]] = []
    opponent_units: List[Dict[str, Any]] = []
    resources: List[Dict[str, Any]] = []

    for y in range(height):
        for x in range(width):
            cell = decode_cell(obs_arr, y, x)
            if cell["owner"] == "teacher":
                teacher_units.append(cell)
            elif cell["owner"] == "opponent":
                opponent_units.append(cell)
            elif cell["unit_type"] == "Resource":
                resources.append({
                    "x": cell["x"],
                    "y": cell["y"],
                    "amount_band": cell["res_band"],
                })

    return teacher_units, opponent_units, resources


def build_action_params(action_row: np.ndarray) -> Dict[str, Any]:
    move_dir = int(action_row[1]) if action_row.shape[0] > 1 else 0
    harvest_dir = int(action_row[2]) if action_row.shape[0] > 2 else 0
    return_dir = int(action_row[3]) if action_row.shape[0] > 3 else 0
    produce_dir = int(action_row[4]) if action_row.shape[0] > 4 else 0
    produce_type = int(action_row[5]) if action_row.shape[0] > 5 else 0
    attack_target = int(action_row[6]) if action_row.shape[0] > 6 else 0

    return {
        "move_dir": DIR_NAMES.get(move_dir, str(move_dir)),
        "harvest_dir": DIR_NAMES.get(harvest_dir, str(harvest_dir)),
        "return_dir": DIR_NAMES.get(return_dir, str(return_dir)),
        "produce_dir": DIR_NAMES.get(produce_dir, str(produce_dir)),
        "produce_type": produce_type,
        "attack_target": attack_target,
    }


def _position_set(units: List[Dict[str, Any]]) -> set[Tuple[int, int, str]]:
    return {(int(u["x"]), int(u["y"]), str(u.get("unit_type", ""))) for u in units}


def save_frame_png(frame: Any, path: Path) -> bool:
    if frame is None:
        return False
    arr = np.asarray(frame)
    if arr.ndim < 2:
        return False

    try:
        import imageio.v2 as imageio

        imageio.imwrite(path, arr)
        return True
    except Exception:
        pass

    try:
        from PIL import Image

        Image.fromarray(arr).save(path)
        return True
    except Exception:
        return False


def generate_replay_artifacts(
    checkpoint: Path,
    episodes: int,
    max_steps: int,
    seed: int,
    map_path: str,
    opponent_pool: List[str],
    opponent_sampling: str,
    device: str,
    output_dir: Path,
    render_mode: str,
    fps: int,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    trace_path = output_dir / "replay_trace.jsonl"
    summary_path = output_dir / "replay_summary.json"
    notes_path = output_dir / "visual_notes.md"

    save_frames = render_mode in {"frames", "both"}
    frames_dir = output_dir / "frames"
    if save_frames:
        frames_dir.mkdir(parents=True, exist_ok=True)

    model, loader = load_model(checkpoint, device)

    opponents_by_episode: List[str] = []
    action_counter: Counter = Counter()
    total_position_deltas = 0
    total_ready_choices = 0
    first_movement_step: Optional[str] = None
    noop_step_streak = 0
    noop_step_streak_max = 0
    blocked_step_streak = 0
    blocked_step_streak_max = 0
    frame_warnings: List[str] = []

    with trace_path.open("w", encoding="utf-8") as trace_file:
        for ep_id in range(episodes):
            opponent = pick_opponent(opponent_pool, opponent_sampling, seed, ep_id)
            opponents_by_episode.append(opponent)

            env = build_env(map_path, max_steps, opponent)
            try:
                obs = env.reset()
                done = False
                step_id = 0
                while not done and step_id < max_steps:
                    obs_arr = np.asarray(obs)
                    if obs_arr.ndim != 4 or obs_arr.shape[0] != 1:
                        raise RuntimeError(f"Unexpected obs shape: {obs_arr.shape}")
                    width = int(obs_arr.shape[2])

                    teacher_units_before, opponent_units_before, resources_before = extract_entities(obs_arr)

                    action_mask = read_action_mask(env)
                    action = predict_action(model, obs, action_mask)
                    action_matrix = action_to_matrix(action)

                    if action_mask is not None and action_mask.ndim == 3 and action_mask.shape[0] == 1:
                        ready_mask = action_mask[0, :, MASK_SOURCE].astype(bool)
                        ready_indices = [int(v) for v in np.where(ready_mask)[0].tolist()]
                    else:
                        ready_indices = []

                    chosen_action_for_ready_actors: List[Dict[str, Any]] = []
                    action_outcomes: List[Dict[str, Any]] = []

                    for idx in ready_indices:
                        action_row = action_matrix[idx]
                        action_type = int(action_row[ACT_TYPE])
                        action_name = ACTION_NAMES.get(action_type, str(action_type))
                        x, y = idx_to_xy(idx, width)
                        chosen_action_for_ready_actors.append({
                            "actor_index": idx,
                            "x": x,
                            "y": y,
                            "action_type": action_name,
                            "action_params": build_action_params(action_row),
                        })
                        action_counter[action_name] += 1

                    transition = env.step(action)
                    if len(transition) == 5:
                        obs_next, _reward, terminated, truncated, _info = transition
                        done = bool(terminated or truncated)
                    else:
                        obs_next, _reward, done, _info = transition

                    obs_after = np.asarray(obs_next)
                    teacher_units_after, _opponent_units_after, _resources_after = extract_entities(obs_after)

                    before_positions = _position_set(teacher_units_before)
                    after_positions = _position_set(teacher_units_after)
                    position_delta_detected = bool(before_positions != after_positions)
                    if position_delta_detected:
                        total_position_deltas += 1
                        if first_movement_step is None:
                            first_movement_step = f"ep{ep_id:03d}_step{step_id:03d}"

                    all_noop_this_step = len(chosen_action_for_ready_actors) > 0 and all(
                        entry["action_type"] == "NoOp" for entry in chosen_action_for_ready_actors
                    )
                    if all_noop_this_step:
                        noop_step_streak += 1
                    else:
                        noop_step_streak = 0
                    noop_step_streak_max = max(noop_step_streak_max, noop_step_streak)

                    blocked_like_step = False
                    if len(chosen_action_for_ready_actors) > 0 and not position_delta_detected:
                        blocked_like_step = True
                        for entry in chosen_action_for_ready_actors:
                            if entry["action_type"] not in {"NoOp", "Harvest"}:
                                blocked_like_step = False
                                break
                    if blocked_like_step:
                        blocked_step_streak += 1
                    else:
                        blocked_step_streak = 0
                    blocked_step_streak_max = max(blocked_step_streak_max, blocked_step_streak)

                    for entry in chosen_action_for_ready_actors:
                        outcome = {
                            "actor_index": entry["actor_index"],
                            "action_type": entry["action_type"],
                            "accepted": True,
                            "effective": bool(position_delta_detected),
                            "outcome_label": "position_delta_detected" if position_delta_detected else "no_position_delta_detected",
                        }
                        action_outcomes.append(outcome)

                    record = {
                        "episode_id": ep_id,
                        "step_id": step_id,
                        "opponent": opponent,
                        "teacher_units": teacher_units_before,
                        "opponent_units": opponent_units_before,
                        "resources": resources_before,
                        "ready_actor_indices": ready_indices,
                        "chosen_action_for_ready_actors": chosen_action_for_ready_actors,
                        "action_type": [entry["action_type"] for entry in chosen_action_for_ready_actors],
                        "action_params": [entry["action_params"] for entry in chosen_action_for_ready_actors],
                        "action_outcomes": action_outcomes,
                        "position_delta_detected": position_delta_detected,
                    }
                    trace_file.write(json.dumps(record, ensure_ascii=False) + "\n")

                    total_ready_choices += len(chosen_action_for_ready_actors)

                    if save_frames:
                        frame_path = frames_dir / f"ep{ep_id:03d}_step{step_id:03d}.png"
                        try:
                            frame_data = env.render(mode="rgb_array")
                        except Exception:
                            try:
                                frame_data = env.render()
                            except Exception:
                                frame_data = None
                        if not save_frame_png(frame_data, frame_path):
                            if not frame_warnings:
                                frame_warnings.append(
                                    "Frame rendering unavailable in current runtime; JSONL artifacts were still generated."
                                )

                    obs = obs_next
                    step_id += 1
            finally:
                try:
                    env.close()
                except Exception:
                    pass

    dominant_action = None
    if action_counter:
        dominant_action = action_counter.most_common(1)[0][0]

    if total_position_deltas > 0:
        visual_verdict = "visually_active"
    elif total_ready_choices == 0:
        visual_verdict = "unclear"
    elif dominant_action == "NoOp":
        visual_verdict = "visually_passive"
    else:
        visual_verdict = "unclear"

    summary: Dict[str, Any] = {
        "checkpoint": str(checkpoint),
        "loader": loader,
        "episodes": int(episodes),
        "max_steps": int(max_steps),
        "seed": int(seed),
        "map_path": map_path,
        "opponent_sampling_mode": opponent_sampling,
        "opponents_used": sorted(set(opponents_by_episode)),
        "opponents_by_episode": opponents_by_episode,
        "total_ready_actor_choices": int(total_ready_choices),
        "total_position_deltas": int(total_position_deltas),
        "first_movement_step": first_movement_step,
        "dominant_actor_level_action": dominant_action,
        "repeated_noop_streak_max": int(noop_step_streak_max),
        "repeated_blocked_or_no_effect_streak_max": int(blocked_step_streak_max),
        "visual_verdict": visual_verdict,
        "render_mode": render_mode,
        "fps": int(fps),
        "warnings": frame_warnings,
    }

    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    notes_lines: List[str] = [
        "# Visual Notes",
        "",
        f"- checkpoint path: `{checkpoint}`",
        f"- opponents used: `{', '.join(summary['opponents_used'])}`",
        f"- episodes: `{episodes}`",
        f"- max steps: `{max_steps}`",
        f"- verdict: `{visual_verdict}`",
        "",
        "## Summary",
        f"- first movement step: `{first_movement_step}`",
        f"- total position deltas: `{total_position_deltas}`",
        f"- dominant actor-level action: `{dominant_action}`",
        f"- repeated NoOp streak (max): `{noop_step_streak_max}`",
        f"- repeated blocked/no-effect streak (max): `{blocked_step_streak_max}`",
    ]
    if frame_warnings:
        notes_lines.append("")
        notes_lines.append("## Warnings")
        for warning in frame_warnings:
            notes_lines.append(f"- {warning}")
        notes_lines.append("- TODO: add robust frame renderer overlay for step id/opponent/action text.")

    notes_path.write_text("\n".join(notes_lines) + "\n", encoding="utf-8")

    frames_dir_value: Optional[str] = None
    if save_frames and any(frames_dir.glob("*.png")):
        frames_dir_value = str(frames_dir)

    return {
        "created": True,
        "replay_trace_path": str(trace_path),
        "replay_summary_path": str(summary_path),
        "visual_notes_path": str(notes_path),
        "frames_dir": frames_dir_value,
        "visual_verdict": visual_verdict,
        "opponents_used": summary["opponents_used"],
        "opponent_sampling_mode": opponent_sampling,
        "warnings": frame_warnings,
    }


def main() -> int:
    args = parse_args()
    checkpoint = args.checkpoint.resolve()
    if not checkpoint.is_file():
        print(f"[replay] checkpoint not found: {checkpoint}")
        return 1

    opponent_pool = parse_opponent_pool(args.opponent_pool)
    result = generate_replay_artifacts(
        checkpoint=checkpoint,
        episodes=args.episodes,
        max_steps=args.max_steps,
        seed=args.seed,
        map_path=args.map_path,
        opponent_pool=opponent_pool,
        opponent_sampling=args.opponent_sampling,
        device=args.device,
        output_dir=args.output_dir,
        render_mode=args.render_mode,
        fps=args.fps,
    )

    print("[replay] artifacts generated")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
