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
import torch

from gridnet_model import Agent

ACTION_NAMES = {
    0: "NoOp",
    1: "Move",
    2: "Harvest",
    3: "Return",
    4: "Produce",
    5: "Attack",
}

STATUS_PASS = "PASS"
STATUS_SUSPICIOUS = "SUSPICIOUS"
STATUS_FAIL_NOOP = "FAIL_COLLAPSED_NOOP"
STATUS_FAIL_NO_EFFECT = "FAIL_NO_EFFECT_BEHAVIOR"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Gridnet actor-level evaluator for project-compatible Branch B checkpoints. "
            "Used when SB3 teacher_behavior_gate is not checkpoint-format compatible."
        )
    )
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--model-metadata", type=Path, required=True)
    p.add_argument("--episodes", type=int, default=4)
    p.add_argument("--max-steps", type=int, default=256)
    p.add_argument("--effective-steps", type=int, default=100)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    p.add_argument("--opponent-pool", default="randomBiasedAI,lightRushAI,workerRushAI,coacAI")
    p.add_argument("--opponent-sampling", choices=("static", "per_episode"), default="per_episode")
    p.add_argument("--device", default="cpu")
    p.add_argument("--output-json", type=Path, required=True)
    p.add_argument("--output-md", type=Path, required=True)
    return p.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)


def parse_opponent_pool(raw: str) -> List[str]:
    values = [t.strip() for t in raw.split(",") if t.strip()]
    if not values:
        raise RuntimeError("Opponent pool is empty.")
    return values


def pick_opponent(pool: List[str], mode: str, seed: int, episode_idx: int) -> str:
    if mode == "static":
        return pool[0]
    return random.Random(seed + 31 + (episode_idx * 997)).choice(pool)


def build_env(map_path: str, max_steps: int, opponent_name: str):
    from gym_microrts import microrts_ai
    from gym_microrts.envs.vec_env import MicroRTSGridModeVecEnv

    opponent = getattr(microrts_ai, opponent_name, None)
    if opponent is None:
        raise RuntimeError(f"Unknown opponent '{opponent_name}'")

    return MicroRTSGridModeVecEnv(
        num_selfplay_envs=0,
        num_bot_envs=1,
        ai2s=[opponent],
        map_paths=[map_path],
        max_steps=max_steps,
        autobuild=False,
    )


def read_action_mask(env: Any) -> np.ndarray:
    raw: np.ndarray
    if hasattr(env, "get_action_mask"):
        action_mask = np.asarray(env.get_action_mask())
        if not hasattr(env, "source_unit_mask"):
            raise RuntimeError("Environment get_action_mask() did not expose source_unit_mask.")
        source_mask = np.asarray(env.source_unit_mask).reshape(action_mask.shape[0], action_mask.shape[1], 1)
        return np.concatenate([source_mask, action_mask], axis=2)
    if hasattr(env, "vec_client") and hasattr(env.vec_client, "getMasks"):
        raw = np.asarray(env.vec_client.getMasks(0))
    elif hasattr(env, "action_masks"):
        maybe = getattr(env, "action_masks")
        raw = np.asarray(maybe() if callable(maybe) else maybe)
    else:
        raise RuntimeError("No action mask provider found on environment.")

    if raw.ndim == 4:
        n, h, w, k = raw.shape
        return raw.reshape(n, h * w, k)
    if raw.ndim == 3:
        return raw
    raise RuntimeError(f"Unexpected action mask shape: {tuple(raw.shape)}")


def action_to_java(action: torch.Tensor, invalid_masks: torch.Tensor, mapsize: int):
    from jpype.types import JArray, JInt

    src = torch.arange(0, mapsize, device=action.device).unsqueeze(0).unsqueeze(2)
    real = torch.cat([src, action], dim=2)
    real_np = real.detach().cpu().numpy()

    valid_np = real_np[invalid_masks[:, :, 0].bool().detach().cpu().numpy()]
    valid_count = invalid_masks[:, :, 0].sum(1).long().detach().cpu().numpy()

    out = []
    idx = 0
    for cnt in valid_count:
        env_actions = []
        for _ in range(int(cnt)):
            env_actions.append(JArray(JInt)(valid_np[idx].tolist()))
            idx += 1
        out.append(JArray(JArray(JInt))(env_actions))
    return JArray(JArray(JArray(JInt)))(out)


def extract_teacher_positions(obs_batch: np.ndarray) -> set[Tuple[int, int]]:
    obs = obs_batch[0]
    owner_self = obs[:, :, 11] > 0.5
    unit_present = np.max(obs[:, :, 13:21], axis=2) > 0.1
    teacher_units = np.logical_and(owner_self, unit_present)
    ys, xs = np.where(teacher_units)
    return set((int(x), int(y)) for y, x in zip(ys.tolist(), xs.tolist()))


def load_agent(checkpoint: Path, metadata_path: Path, device: torch.device) -> Tuple[Agent, Dict[str, Any]]:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    obs_shape = tuple(int(v) for v in metadata["observation_shape"])
    action_nvec = [int(v) for v in metadata["action_nvec"]]

    agent = Agent(obs_shape, action_nvec).to(device)
    state_dict = torch.load(checkpoint, map_location=device)
    agent.load_state_dict(state_dict)
    agent.eval()
    return agent, metadata


def evaluate(args: argparse.Namespace) -> Dict[str, Any]:
    checkpoint = args.checkpoint.resolve()
    metadata_path = args.model_metadata.resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint}")
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Model metadata not found: {metadata_path}")

    device = torch.device("cuda" if torch.cuda.is_available() and args.device.lower() == "cuda" else "cpu")
    agent, metadata = load_agent(checkpoint, metadata_path, device)

    mapsize = int(metadata["mapsize"])

    full_action_counter = Counter()
    actor_action_counter = Counter()

    ready_movable_actor_choice_count = 0
    effective_position_delta_count = 0
    no_effect_ready_nonnoop_steps = 0
    ready_nonnoop_steps = 0

    trace: List[Dict[str, Any]] = []

    pool = parse_opponent_pool(args.opponent_pool)
    actual_opponents: List[str] = []

    # JPype in this stack cannot restart JVM in-process; keep one env for all episodes.
    fixed_opponent = pick_opponent(pool, args.opponent_sampling, args.seed, 0)
    if args.opponent_sampling != "static" and args.episodes > 1:
        actual_opponents.append("NOTE: per_episode requested; using single fixed opponent due JVM restart limitation")
    env = build_env(args.map_path, args.max_steps, fixed_opponent)

    try:
        for episode in range(args.episodes):
            actual_opponents.append(fixed_opponent)
            obs = np.asarray(env.reset(), dtype=np.float32)
            prev_positions = extract_teacher_positions(obs)

            done = False
            step_id = 0

            while not done and step_id < args.max_steps:
                obs_t = torch.as_tensor(obs, device=device, dtype=torch.float32)
                mask_np = read_action_mask(env)
                mask_t = torch.as_tensor(mask_np, device=device)

                with torch.no_grad():
                    action_t, _logprob, _entropy, used_mask = agent.get_action(
                        obs_t,
                        invalid_action_masks=mask_t,
                        action=None,
                        deterministic=True,
                    )

                action_np = action_t[0].detach().cpu().numpy().astype(np.int64)
                action_types = action_np[:, 0]
                full_action_counter.update(int(v) for v in action_types.tolist())

                source_mask = used_mask[0, :, 0].bool().detach().cpu().numpy()
                move_mask = used_mask[0, :, 2].bool().detach().cpu().numpy()
                ready_indices = np.where(source_mask)[0]
                movable_indices = np.where(np.logical_and(source_mask, move_mask))[0]

                if ready_indices.size > 0:
                    actor_ready_actions = action_types[ready_indices]
                    actor_action_counter.update(int(v) for v in actor_ready_actions.tolist())

                    ready_movable_actor_choice_count += int(movable_indices.size)
                    ready_nonnoop = bool(np.any(actor_ready_actions != 0))
                    if ready_nonnoop:
                        ready_nonnoop_steps += 1

                action_env = action_t.detach().cpu().numpy().astype(np.int32)
                next_obs, _rew, dones, _infos = env.step(action_env)
                obs = np.asarray(next_obs, dtype=np.float32)
                done = bool(np.asarray(dones).reshape(-1)[0])

                next_positions = extract_teacher_positions(obs)
                pos_delta = prev_positions != next_positions
                if pos_delta:
                    effective_position_delta_count += 1
                else:
                    if ready_indices.size > 0:
                        actor_ready_actions = action_types[ready_indices]
                        if np.any(actor_ready_actions != 0):
                            no_effect_ready_nonnoop_steps += 1
                prev_positions = next_positions

                if episode == 0 and step_id < min(args.effective_steps, 20):
                    trace.append(
                        {
                            "step": int(step_id),
                            "ready_count": int(ready_indices.size),
                            "movable_ready_count": int(movable_indices.size),
                            "chosen_ready_actions": {
                                ACTION_NAMES.get(k, str(k)): int(v)
                                for k, v in sorted(Counter(int(x) for x in action_types[ready_indices].tolist()).items())
                            },
                            "position_delta": bool(pos_delta),
                        }
                    )

                step_id += 1

    finally:
        env.close()

    actor_total = int(sum(actor_action_counter.values()))
    actor_move = int(actor_action_counter.get(1, 0))
    actor_noop = int(actor_action_counter.get(0, 0))

    actor_level_move_share = (actor_move / actor_total) if actor_total > 0 else 0.0
    actor_noop_share = (actor_noop / actor_total) if actor_total > 0 else 1.0
    no_effect_action_share = (
        no_effect_ready_nonnoop_steps / max(ready_nonnoop_steps, 1)
        if ready_nonnoop_steps > 0
        else 1.0
    )

    if ready_movable_actor_choice_count == 0:
        status = STATUS_FAIL_NO_EFFECT
        verdict = "No ready movable actors detected during evaluation window."
    elif effective_position_delta_count > 0 and actor_level_move_share > 0.0 and no_effect_action_share < 1.0:
        status = STATUS_PASS
        verdict = "Actor-level effective movement detected."
    elif actor_noop_share >= 0.95 and actor_level_move_share == 0.0:
        status = STATUS_FAIL_NOOP
        verdict = "Collapsed to NoOp on ready actors."
    elif effective_position_delta_count == 0:
        status = STATUS_FAIL_NO_EFFECT
        verdict = "No effective movement detected from ready actor choices."
    else:
        status = STATUS_SUSPICIOUS
        verdict = "Non-collapsed action mix detected, but effective movement evidence is weak."

    result = {
        "schema": "gridnet_actor_level_eval.v1",
        "timestamp_utc": utc_now(),
        "checkpoint": str(checkpoint),
        "model_metadata": str(metadata_path),
        "status": status,
        "gate_status": status,
        "verdict": verdict,
        "episodes": int(args.episodes),
        "max_steps": int(args.max_steps),
        "effective_steps": int(args.effective_steps),
        "map_path": args.map_path,
        "opponents_used": actual_opponents,
        "actor_level_move_share": actor_level_move_share,
        "actor_noop_share": actor_noop_share,
        "effective_position_delta_count": int(effective_position_delta_count),
        "no_effect_action_share": no_effect_action_share,
        "ready_movable_actor_choice_count": int(ready_movable_actor_choice_count),
        "ready_nonnoop_steps": int(ready_nonnoop_steps),
        "no_effect_ready_nonnoop_steps": int(no_effect_ready_nonnoop_steps),
        "full_action_counts": {ACTION_NAMES.get(k, str(k)): int(v) for k, v in sorted(full_action_counter.items())},
        "ready_actor_action_counts": {ACTION_NAMES.get(k, str(k)): int(v) for k, v in sorted(actor_action_counter.items())},
        "trace": trace,
    }
    return result


def write_markdown(path: Path, payload: Dict[str, Any]) -> None:
    lines = [
        "# Gridnet Actor-Level Evaluation",
        "",
        f"- status: {payload['status']}",
        f"- verdict: {payload['verdict']}",
        f"- checkpoint: {payload['checkpoint']}",
        f"- episodes: {payload['episodes']}",
        f"- map_path: {payload['map_path']}",
        "",
        "## Key Metrics",
        f"- actor_level_move_share: {payload['actor_level_move_share']:.6f}",
        f"- actor_noop_share: {payload['actor_noop_share']:.6f}",
        f"- effective_position_delta_count: {payload['effective_position_delta_count']}",
        f"- no_effect_action_share: {payload['no_effect_action_share']:.6f}",
        f"- ready_movable_actor_choice_count: {payload['ready_movable_actor_choice_count']}",
        "",
        "## Notes",
        "- Vocabulary is aligned with teacher_behavior_gate statuses (PASS/SUSPICIOUS/FAIL_*).",
        "- PASS requires actor-level effective movement evidence, not full-tensor move share only.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    result = evaluate(args)
    write_json(args.output_json, result)
    write_markdown(args.output_md, result)

    print(f"[gate] status={result['status']}")
    print(f"[gate] verdict={result['verdict']}")
    print(f"[gate] actor_level_move_share={result['actor_level_move_share']:.6f}")
    print(f"[gate] actor_noop_share={result['actor_noop_share']:.6f}")
    print(f"[gate] effective_position_delta_count={result['effective_position_delta_count']}")
    print(f"[gate] no_effect_action_share={result['no_effect_action_share']:.6f}")


if __name__ == "__main__":
    main()
