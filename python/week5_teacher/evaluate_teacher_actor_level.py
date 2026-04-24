#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

ACTION_NAMES = {
    0: "NoOp",
    1: "Move",
    2: "Harvest",
    3: "Return",
    4: "Produce",
    5: "Attack",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Actor-level teacher behavior audit for Gym-microRTS checkpoints. "
            "Separates full action tensor statistics from ready-actor teacher-side choices."
        )
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--episodes", type=int, default=8)
    parser.add_argument("--max-steps", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=170)
    parser.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    parser.add_argument("--opponent-pool", default="coacAI,workerRushAI,lightRushAI,passiveAI")
    parser.add_argument("--opponent-sampling", choices=("static", "per_episode"), default="per_episode")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--trace-steps", type=int, default=20)
    parser.add_argument("--output-json", type=Path, default=Path("WEEK6/teacher_actor_level_eval.json"))
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("WEEK6/TEACHER_ACTOR_LEVEL_EVAL_SUMMARY.md"),
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_model(checkpoint: Path, device: str):
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


def parse_opponent_pool(raw: str) -> List[str]:
    parsed = [token.strip() for token in raw.split(",") if token.strip()]
    if not parsed:
        raise RuntimeError("Opponent pool is empty.")
    return parsed


def pick_opponents(pool: List[str], episodes: int, mode: str, seed: int) -> List[str]:
    if mode == "static":
        return [pool[0]] * episodes
    rng = random.Random(seed + 103)
    return [rng.choice(pool) for _ in range(episodes)]


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


def read_action_mask(env) -> np.ndarray | None:
    if hasattr(env, "get_action_mask"):
        try:
            return np.asarray(env.get_action_mask())
        except Exception:
            return None
    if hasattr(env, "action_masks"):
        try:
            masks_attr = getattr(env, "action_masks")
            raw = masks_attr() if callable(masks_attr) else masks_attr
            return np.asarray(raw)
        except Exception:
            return None
    return None


def predict_action(model, obs, action_mask):
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
        return arr[0].astype(np.int64, copy=False)

    if arr.ndim == 2 and arr.shape[1] == 7:
        return arr.astype(np.int64, copy=False)

    flat = arr.reshape(-1)
    if flat.size % 7 != 0:
        raise RuntimeError(f"Unexpected action shape {arr.shape}; cannot reshape into (-1, 7).")
    return flat.reshape(-1, 7).astype(np.int64, copy=False)


def to_named_counts(counter: Counter[int], total: int) -> Dict[str, Dict[str, float | int]]:
    out: Dict[str, Dict[str, float | int]] = {}
    for idx, name in ACTION_NAMES.items():
        count = int(counter.get(idx, 0))
        share = (count / total) if total > 0 else 0.0
        out[name] = {"count": count, "share": share}
    return out


def summarize_trace_step(step_id: int, ready_count: int, movable_ready_count: int, actor_counter: Counter[int]) -> Dict[str, Any]:
    return {
        "step": step_id,
        "ready_teacher_actors": int(ready_count),
        "movable_ready_teacher_actors": int(movable_ready_count),
        "chosen_actions_teacher_ready_actors": {ACTION_NAMES[k]: int(v) for k, v in sorted(actor_counter.items())},
        "notable": (
            "movable-ready actors existed but no Move selected"
            if movable_ready_count > 0 and actor_counter.get(1, 0) == 0
            else ""
        ),
    }


def run_actor_level_audit(args: argparse.Namespace) -> Dict[str, Any]:
    checkpoint = args.checkpoint.resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint}")

    model, algorithm_name = load_model(checkpoint, args.device)

    opponent_pool = parse_opponent_pool(args.opponent_pool)
    requested_opponents = pick_opponents(opponent_pool, args.episodes, args.opponent_sampling, args.seed)
    actual_opponent = requested_opponents[0]

    full_counter = Counter()
    full_early20 = Counter()
    full_early50 = Counter()

    actor_counter = Counter()
    actor_early20 = Counter()
    actor_early50 = Counter()

    steps_total = 0
    actor_steps_total = 0

    steps_with_any_actor_move = 0
    episodes_with_any_actor_move = 0

    ready_actor_total = 0
    steps_with_ready_actors = 0

    steps_with_movable_ready_actors = 0
    steps_movable_ready_but_no_move = 0

    episode_summaries: List[Dict[str, Any]] = []
    trace_steps: List[Dict[str, Any]] = []

    env = build_env(args.map_path, args.max_steps, actual_opponent)

    for episode_index in range(args.episodes):
        obs = env.reset()

        done = False
        step_id = 0
        ep_return = 0.0
        ep_has_actor_move = False

        while not done and step_id < args.max_steps:
            action_mask = read_action_mask(env)
            action = predict_action(model, obs, action_mask)
            matrix = action_to_matrix(action)

            if matrix.shape[0] != 576:
                raise RuntimeError(f"Expected 576 spatial slots, got {matrix.shape[0]}.")

            action_types = matrix[:, 0]
            step_full_counter = Counter(int(v) for v in action_types.tolist())
            full_counter.update(step_full_counter)
            if step_id < 20:
                full_early20.update(step_full_counter)
            if step_id < 50:
                full_early50.update(step_full_counter)

            steps_total += 1

            step_actor_counter = Counter()
            ready_count = 0
            movable_ready_count = 0

            # Proxy for teacher-owned ready controllable actors:
            # mask[..., 0] is source_unit_mask consumed by legacy env.step filtering.
            if action_mask is not None and action_mask.ndim == 3 and action_mask.shape[0] == 1 and action_mask.shape[1] == 576:
                ready_mask = action_mask[0, :, 0].astype(bool)
                ready_indices = np.where(ready_mask)[0]
                ready_count = int(ready_indices.size)
                if ready_count > 0:
                    steps_with_ready_actors += 1
                    ready_actor_total += ready_count
                    actor_steps_total += ready_count

                    actor_action_types = action_types[ready_indices]
                    step_actor_counter = Counter(int(v) for v in actor_action_types.tolist())

                    actor_counter.update(step_actor_counter)
                    if step_id < 20:
                        actor_early20.update(step_actor_counter)
                    if step_id < 50:
                        actor_early50.update(step_actor_counter)

                    if step_actor_counter.get(1, 0) > 0:
                        ep_has_actor_move = True
                        steps_with_any_actor_move += 1

                    # Action-type masks are assumed in slots [1:7] as NoOp, Move, Harvest, Return, Produce, Attack.
                    # If the layout differs in another backend, this metric becomes unavailable/noisy.
                    action_type_mask = action_mask[0, ready_indices, 1:7]
                    if action_type_mask.shape[1] == 6:
                        move_allowed = action_type_mask[:, 1].astype(bool)
                        movable_ready_count = int(move_allowed.sum())
                        if movable_ready_count > 0:
                            steps_with_movable_ready_actors += 1
                            if step_actor_counter.get(1, 0) == 0:
                                steps_movable_ready_but_no_move += 1

            if episode_index == 0 and step_id < args.trace_steps:
                trace_steps.append(summarize_trace_step(step_id, ready_count, movable_ready_count, step_actor_counter))

            transition = env.step(action)
            if len(transition) == 5:
                obs, reward, terminated, truncated, _info = transition
                done = bool(terminated or truncated)
            else:
                obs, reward, done, _info = transition

            reward_scalar = float(reward[0]) if hasattr(reward, "__len__") else float(reward)
            ep_return += reward_scalar
            step_id += 1

        if ep_has_actor_move:
            episodes_with_any_actor_move += 1

        episode_summaries.append(
            {
                "episode_index": episode_index,
                "opponent": actual_opponent,
                "steps": step_id,
                "episode_return": ep_return,
                "teacher_selected_move_on_ready_actors": ep_has_actor_move,
            }
        )

    try:
        env.close()
    except Exception:
        pass

    full_total_cells = int(sum(full_counter.values()))
    actor_total_ready_choices = int(sum(actor_counter.values()))

    full_move_share = (full_counter.get(1, 0) / full_total_cells) if full_total_cells > 0 else 0.0
    actor_move_share = (actor_counter.get(1, 0) / actor_total_ready_choices) if actor_total_ready_choices > 0 else 0.0

    avg_ready_actors_per_step = (ready_actor_total / steps_with_ready_actors) if steps_with_ready_actors > 0 else 0.0

    return {
        "report_generated_at_utc": utc_now(),
        "checkpoint": {
            "path": str(checkpoint),
            "algorithm_loader": algorithm_name,
        },
        "protocol": {
            "episodes": args.episodes,
            "max_steps": args.max_steps,
            "map_path": args.map_path,
            "opponent_pool": opponent_pool,
            "opponent_sampling_requested": args.opponent_sampling,
            "episode_opponents_requested": requested_opponents,
            "opponent_sampling_effective": "static",
            "episode_opponents_effective": [actual_opponent] * args.episodes,
            "opponent_sampling_note": (
                "Legacy gym_microrts backend runs under a single JVM per process. "
                "To avoid JVM restart failures, this evaluator reuses one env/opponent for all episodes."
            ),
            "seed": args.seed,
        },
        "teacher_side": {
            "full_tensor_action_distribution": to_named_counts(full_counter, full_total_cells),
            "full_tensor_early_game_distribution": {
                "first_20_steps": to_named_counts(full_early20, int(sum(full_early20.values()))),
                "first_50_steps": to_named_counts(full_early50, int(sum(full_early50.values()))),
            },
            "actor_level_chosen_action_distribution": to_named_counts(actor_counter, actor_total_ready_choices),
            "actor_level_early_game_distribution": {
                "first_20_steps": to_named_counts(actor_early20, int(sum(actor_early20.values()))),
                "first_50_steps": to_named_counts(actor_early50, int(sum(actor_early50.values()))),
            },
            "move_presence_actor_level": {
                "steps_total": steps_total,
                "steps_with_any_teacher_actor_move": steps_with_any_actor_move,
                "steps_with_any_teacher_actor_move_share": (steps_with_any_actor_move / steps_total) if steps_total > 0 else 0.0,
                "episodes_total": args.episodes,
                "episodes_with_any_teacher_actor_move": episodes_with_any_actor_move,
                "episodes_with_any_teacher_actor_move_share": (
                    episodes_with_any_actor_move / args.episodes if args.episodes > 0 else 0.0
                ),
            },
            "ready_actor_summary": {
                "steps_with_ready_teacher_actors": steps_with_ready_actors,
                "avg_ready_teacher_actors_per_ready_step": avg_ready_actors_per_step,
                "steps_with_movable_ready_teacher_actors": steps_with_movable_ready_actors,
                "steps_movable_ready_but_no_move_selected": steps_movable_ready_but_no_move,
                "steps_movable_ready_but_no_move_selected_share": (
                    steps_movable_ready_but_no_move / steps_with_movable_ready_actors
                    if steps_with_movable_ready_actors > 0
                    else 0.0
                ),
            },
            "full_tensor_vs_actor_level_move_share": {
                "full_tensor_move_share": full_move_share,
                "actor_level_move_share": actor_move_share,
                "delta_actor_minus_full": actor_move_share - full_move_share,
            },
            "episode_summaries": episode_summaries,
            "step_trace_first_episode": trace_steps,
        },
        "opponent_side": {
            "telemetry_available": False,
            "note": (
                "This evaluator does not read opponent-side chosen/executed action stream from env API. "
                "Teacher-side telemetry is isolated and never mixed with opponent actions."
            ),
        },
        "method_limits": [
            "Actor-level behavior is computed as chosen actions over teacher ready controllable actors (source_unit_mask proxy).",
            "Executed/effective action facts are not directly exposed in this path and are not claimed.",
            "Move-availability summary assumes action-type mask layout [NoOp, Move, Harvest, Return, Produce, Attack] in slots [1:7].",
        ],
    }


def build_summary(report: Dict[str, Any]) -> str:
    ckpt = report["checkpoint"]["path"]
    protocol = report["protocol"]
    teacher = report["teacher_side"]
    move_cmp = teacher["full_tensor_vs_actor_level_move_share"]
    ready = teacher["ready_actor_summary"]
    move_presence = teacher["move_presence_actor_level"]

    def fmt_pct(value: float) -> str:
        return f"{value * 100.0:.2f}%"

    decision = (
        "teacher actor-level move-capable"
        if move_presence["episodes_with_any_teacher_actor_move"] > 0 and move_cmp["actor_level_move_share"] > 0.0
        else "move signal mostly lives in raw tensor and is weak on actor level"
    )

    lines: List[str] = []
    lines.append("# Teacher Actor-Level Evaluation Summary")
    lines.append("")
    lines.append(f"Generated at (UTC): {report['report_generated_at_utc']}")
    lines.append("")
    lines.append("## 1) Checkpoint")
    lines.append(f"- Path: {ckpt}")
    lines.append(f"- Loader: {report['checkpoint']['algorithm_loader']}")
    lines.append("")
    lines.append("## 2) Environment and Opponent Protocol")
    lines.append(f"- Episodes: {protocol['episodes']}")
    lines.append(f"- Max steps per episode: {protocol['max_steps']}")
    lines.append(f"- Map: {protocol['map_path']}")
    lines.append(f"- Opponent pool: {', '.join(protocol['opponent_pool'])}")
    lines.append(f"- Opponent sampling requested: {protocol['opponent_sampling_requested']}")
    lines.append(f"- Opponent sampling effective: {protocol['opponent_sampling_effective']}")
    lines.append(f"- Effective opponent for all episodes: {protocol['episode_opponents_effective'][0]}")
    lines.append(f"- Note: {protocol['opponent_sampling_note']}")
    lines.append("")
    lines.append("## 3) Full-Tensor Action Distribution (Teacher Output Tensor)")
    for name in ACTION_NAMES.values():
        stat = teacher["full_tensor_action_distribution"][name]
        lines.append(f"- {name}: count={stat['count']} share={fmt_pct(float(stat['share']))}")
    lines.append("")
    lines.append("## 4) Actor-Level Teacher Action Distribution (Ready Own Actors)")
    for name in ACTION_NAMES.values():
        stat = teacher["actor_level_chosen_action_distribution"][name]
        lines.append(f"- {name}: count={stat['count']} share={fmt_pct(float(stat['share']))}")
    lines.append("")
    lines.append("## 5) Early-Game Actor-Level Distribution")
    lines.append("- First 20 steps:")
    for name in ACTION_NAMES.values():
        stat = teacher["actor_level_early_game_distribution"]["first_20_steps"][name]
        lines.append(f"  - {name}: count={stat['count']} share={fmt_pct(float(stat['share']))}")
    lines.append("- First 50 steps:")
    for name in ACTION_NAMES.values():
        stat = teacher["actor_level_early_game_distribution"]["first_50_steps"][name]
        lines.append(f"  - {name}: count={stat['count']} share={fmt_pct(float(stat['share']))}")
    lines.append("")
    lines.append("## 6) Teacher Actor-Level Move Presence")
    lines.append(
        f"- Steps with any teacher actor selecting Move: {move_presence['steps_with_any_teacher_actor_move']} / {move_presence['steps_total']} "
        f"({fmt_pct(float(move_presence['steps_with_any_teacher_actor_move_share']))})"
    )
    lines.append(
        f"- Episodes with any teacher actor selecting Move: {move_presence['episodes_with_any_teacher_actor_move']} / "
        f"{move_presence['episodes_total']} ({fmt_pct(float(move_presence['episodes_with_any_teacher_actor_move_share']))})"
    )
    lines.append("")
    lines.append("## 7) Ready-Actor Summary")
    lines.append(f"- Avg ready own actors per ready step: {ready['avg_ready_teacher_actors_per_ready_step']:.3f}")
    lines.append(
        f"- Steps with movable-ready actors but no Move selected: {ready['steps_movable_ready_but_no_move_selected']} / "
        f"{ready['steps_with_movable_ready_teacher_actors']} "
        f"({fmt_pct(float(ready['steps_movable_ready_but_no_move_selected_share']))})"
    )
    lines.append("")
    lines.append("## 8) Full-Tensor vs Actor-Level Move Share")
    lines.append(f"- Full-tensor Move share: {fmt_pct(float(move_cmp['full_tensor_move_share']))}")
    lines.append(f"- Actor-level Move share: {fmt_pct(float(move_cmp['actor_level_move_share']))}")
    lines.append(f"- Delta (actor - full): {fmt_pct(float(move_cmp['delta_actor_minus_full']))}")
    lines.append("")
    lines.append("## 9) Diagnostic Conclusion")
    lines.append(f"- {decision}")
    lines.append("- Executed/effective action facts are not claimed where env API does not expose them directly.")

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    report = run_actor_level_audit(args)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)

    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(build_summary(report), encoding="utf-8")

    print(f"checkpoint={report['checkpoint']['path']}")
    print(f"episodes={report['protocol']['episodes']}")
    print(f"wrote_json={args.output_json}")
    print(f"wrote_md={args.output_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
