#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one visual Gym-microRTS episode for a teacher checkpoint (no training)."
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    parser.add_argument("--max-steps", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=171)
    parser.add_argument("--opponent", default="workerRushAI")
    parser.add_argument("--step-delay-ms", type=int, default=30)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def load_model(checkpoint: Path, device: str):
    errors: list[str] = []

    try:
        from sb3_contrib import MaskablePPO

        return MaskablePPO.load(str(checkpoint), device=device, print_system_info=False)
    except Exception as exc:
        errors.append(f"MaskablePPO: {type(exc).__name__}: {exc}")

    try:
        from stable_baselines3 import PPO

        return PPO.load(str(checkpoint), device=device, print_system_info=False)
    except Exception as exc:
        errors.append(f"PPO: {type(exc).__name__}: {exc}")

    raise RuntimeError("Failed to load checkpoint. " + " | ".join(errors))


def build_env(map_path: str, max_steps: int, opponent_name: str):
    from gym_microrts import microrts_ai
    from gym_microrts.envs.vec_env import MicroRTSGridModeVecEnv

    opponent = getattr(microrts_ai, opponent_name, None)
    if opponent is None:
        raise RuntimeError(f"Unknown opponent '{opponent_name}' in gym_microrts.microrts_ai")

    env = MicroRTSGridModeVecEnv(
        num_selfplay_envs=0,
        num_bot_envs=1,
        ai2s=[opponent],
        map_paths=[map_path],
        max_steps=max_steps,
        autobuild=False,
    )
    return env


def read_action_mask(env):
    if hasattr(env, "get_action_mask"):
        try:
            return env.get_action_mask()
        except Exception:
            return None
    if hasattr(env, "action_masks"):
        try:
            masks_attr = getattr(env, "action_masks")
            return masks_attr() if callable(masks_attr) else masks_attr
        except Exception:
            return None
    return None


def predict_action(model, obs, action_mask):
    # MaskablePPO accepts action_masks; PPO ignores it and falls back.
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


def main() -> int:
    args = parse_args()
    checkpoint = args.checkpoint.resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint}")

    model = load_model(checkpoint, args.device)
    env = build_env(args.map_path, args.max_steps, args.opponent)

    obs = env.reset()
    done = False
    steps = 0
    episode_return = 0.0

    print(f"checkpoint={checkpoint}")
    print(f"opponent={args.opponent}")
    print("Starting visual episode...")

    while not done and steps < args.max_steps:
        action_mask = read_action_mask(env)
        action = predict_action(model, obs, action_mask)
        step = env.step(action)

        if len(step) == 5:
            obs, reward, terminated, truncated, _info = step
            done = bool(terminated or truncated)
        else:
            obs, reward, done, _info = step

        try:
            reward_scalar = float(reward[0]) if hasattr(reward, "__len__") else float(reward)
        except Exception:
            reward_scalar = 0.0

        episode_return += reward_scalar
        steps += 1

        try:
            env.render()
        except Exception:
            # Rendering may fail in headless sessions.
            pass

        if args.step_delay_ms > 0:
            time.sleep(args.step_delay_ms / 1000.0)

    print(f"Episode finished: steps={steps}, return={episode_return:.6f}")

    try:
        env.close()
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
