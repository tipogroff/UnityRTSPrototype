#!/usr/bin/env python3
"""Visual eval rollout for Gridnet checkpoints.

Loads a trained agent, creates a gym_microrts environment with render enabled,
runs a deterministic rollout, and writes a visual_eval_summary.json/md.

If render is unavailable (headless / no display) the script does NOT crash —
it records the rollout metrics and writes visual_eval_status=unavailable.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

# Must be importable from the same package dir.
from gridnet_model import Agent


ACTION_NAMES = {
    0: "NoOp",
    1: "Move",
    2: "Harvest",
    3: "Return",
    4: "Produce",
    5: "Attack",
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Visual rollout eval for a Gridnet actor-critic checkpoint."
    )
    p.add_argument("--checkpoint", type=Path, required=True,
                   help="Path to .pt checkpoint file.")
    p.add_argument("--model-metadata", type=Path, required=True,
                   help="Path to model_metadata.json produced by the training run.")
    p.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    p.add_argument("--opponent", default="randomBiasedAI",
                   help="Single opponent name from gym_microrts.microrts_ai.")
    p.add_argument("--max-steps", type=int, default=300)
    p.add_argument("--fps", type=int, default=8,
                   help="Target rendering FPS (used to pace sleep between steps).")
    p.add_argument("--device", default="cpu")
    p.add_argument("--output-dir", type=Path, required=True,
                   help="Directory to write visual_eval_summary.json/md into.")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_agent(checkpoint: Path, metadata_path: Path,
               device: torch.device) -> Tuple[Agent, Dict[str, Any]]:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    obs_shape = tuple(int(v) for v in metadata["observation_shape"])
    action_nvec = [int(v) for v in metadata["action_nvec"]]
    agent = Agent(obs_shape, action_nvec).to(device)
    state_dict = torch.load(checkpoint, map_location=device)
    agent.load_state_dict(state_dict)
    agent.eval()
    return agent, metadata


def build_env(map_path: str, max_steps: int, opponent_name: str,
              render_theme: str = "terrain") -> Any:
    from gym_microrts import microrts_ai
    from gym_microrts.envs.vec_env import MicroRTSGridModeVecEnv

    opponent = getattr(microrts_ai, opponent_name, None)
    if opponent is None:
        raise RuntimeError(f"Unknown opponent: '{opponent_name}'")

    return MicroRTSGridModeVecEnv(
        num_selfplay_envs=0,
        num_bot_envs=1,
        ai2s=[opponent],
        map_paths=[map_path],
        max_steps=max_steps,
        autobuild=False,
        render_theme=render_theme,
    )


def read_action_mask(env: Any) -> np.ndarray:
    if hasattr(env, "get_action_mask"):
        action_mask = np.asarray(env.get_action_mask())
        source_mask = np.asarray(env.source_unit_mask).reshape(
            action_mask.shape[0], action_mask.shape[1], 1
        )
        return np.concatenate([source_mask, action_mask], axis=2)
    if hasattr(env, "vec_client") and hasattr(env.vec_client, "getMasks"):
        raw = np.asarray(env.vec_client.getMasks(0))
    elif hasattr(env, "action_masks"):
        maybe = getattr(env, "action_masks")
        raw = np.asarray(maybe() if callable(maybe) else maybe)
    else:
        raise RuntimeError("No action mask provider on environment.")

    if raw.ndim == 4:
        n, h, w, k = raw.shape
        return raw.reshape(n, h * w, k)
    if raw.ndim == 3:
        return raw
    raise RuntimeError(f"Unexpected action mask shape: {tuple(raw.shape)}")


def extract_positions(obs_batch: np.ndarray) -> set:
    obs = obs_batch[0]
    owner_self = obs[:, :, 11] > 0.5
    unit_present = np.max(obs[:, :, 13:21], axis=2) > 0.1
    mask = np.logical_and(owner_self, unit_present)
    ys, xs = np.where(mask)
    return set((int(x), int(y)) for x, y in zip(xs.tolist(), ys.tolist()))


# ---------------------------------------------------------------------------
# Rollout
# ---------------------------------------------------------------------------

def run_rollout(agent: Agent, env: Any, max_steps: int,
                device: torch.device, fps: int,
                render_active: bool) -> Dict[str, Any]:
    full_action_counter: Counter = Counter()
    actor_action_counter: Counter = Counter()
    position_delta_count = 0
    ready_movable_count = 0
    ready_nonnoop_steps = 0
    no_effect_ready_nonnoop_steps = 0
    step_trace: List[Dict[str, Any]] = []

    frame_period = 1.0 / max(fps, 1)

    obs = np.asarray(env.reset(), dtype=np.float32)
    prev_positions = extract_positions(obs)
    done = False
    step_id = 0

    while not done and step_id < max_steps:
        t0 = time.monotonic()

        obs_t = torch.as_tensor(obs, device=device, dtype=torch.float32)
        mask_np = read_action_mask(env)
        mask_t = torch.as_tensor(mask_np, device=device)

        with torch.no_grad():
            action_t, _lp, _ent, used_mask = agent.get_action(
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
            ready_actions = action_types[ready_indices]
            actor_action_counter.update(int(v) for v in ready_actions.tolist())
            ready_movable_count += int(movable_indices.size)
            ready_nonnoop = bool(np.any(ready_actions != 0))
            if ready_nonnoop:
                ready_nonnoop_steps += 1

        action_env = action_t.detach().cpu().numpy().astype(np.int32)
        next_obs, _rew, dones, _infos = env.step(action_env)
        obs = np.asarray(next_obs, dtype=np.float32)
        done = bool(np.asarray(dones).reshape(-1)[0])

        next_positions = extract_positions(obs)
        pos_delta = prev_positions != next_positions
        if pos_delta:
            position_delta_count += 1
        elif ready_indices.size > 0:
            if np.any(action_types[ready_indices] != 0):
                no_effect_ready_nonnoop_steps += 1
        prev_positions = next_positions

        if step_id < 30:
            step_trace.append({
                "step": step_id,
                "ready_count": int(ready_indices.size),
                "movable_ready_count": int(movable_indices.size),
                "chosen_ready_actions": {
                    ACTION_NAMES.get(k, str(k)): int(v)
                    for k, v in sorted(
                        Counter(int(x) for x in action_types[ready_indices].tolist()).items()
                    )
                } if ready_indices.size > 0 else {},
                "position_delta": bool(pos_delta),
            })

        if render_active:
            try:
                env.render()
            except Exception:
                render_active = False
            elapsed = time.monotonic() - t0
            pause = frame_period - elapsed
            if pause > 0:
                time.sleep(pause)

        step_id += 1

    actor_total = int(sum(actor_action_counter.values()))
    actor_move = int(actor_action_counter.get(1, 0))
    actor_noop = int(actor_action_counter.get(0, 0))
    move_share = (actor_move / actor_total) if actor_total > 0 else 0.0
    noop_share = (actor_noop / actor_total) if actor_total > 0 else 1.0
    no_effect_share = (
        no_effect_ready_nonnoop_steps / ready_nonnoop_steps
        if ready_nonnoop_steps > 0 else 1.0
    )

    return {
        "steps_run": step_id,
        "episode_done": done,
        "actor_level_move_share": move_share,
        "actor_noop_share": noop_share,
        "effective_position_delta_count": position_delta_count,
        "no_effect_action_share": no_effect_share,
        "ready_movable_actor_choice_count": ready_movable_count,
        "ready_nonnoop_steps": ready_nonnoop_steps,
        "no_effect_ready_nonnoop_steps": no_effect_ready_nonnoop_steps,
        "full_action_counts": {
            ACTION_NAMES.get(k, str(k)): int(v)
            for k, v in sorted(full_action_counter.items())
        },
        "ready_actor_action_counts": {
            ACTION_NAMES.get(k, str(k)): int(v)
            for k, v in sorted(actor_action_counter.items())
        },
        "step_trace": step_trace,
    }


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)


def write_markdown(path: Path, payload: Dict[str, Any]) -> None:
    vis = payload.get("visual_eval_status", "unknown")
    lines = [
        "# Gridnet Visual Eval Summary",
        "",
        f"- visual_eval_status: {vis}",
        f"- checkpoint: {payload['checkpoint']}",
        f"- opponent: {payload['opponent']}",
        f"- max_steps: {payload['max_steps']}",
        f"- steps_run: {payload.get('steps_run', 'N/A')}",
        f"- episode_done: {payload.get('episode_done', 'N/A')}",
        "",
        "## Actor-Level Metrics",
        f"- actor_level_move_share: {payload.get('actor_level_move_share', 0.0):.6f}",
        f"- actor_noop_share: {payload.get('actor_noop_share', 1.0):.6f}",
        f"- effective_position_delta_count: {payload.get('effective_position_delta_count', 0)}",
        f"- no_effect_action_share: {payload.get('no_effect_action_share', 1.0):.6f}",
        f"- ready_movable_actor_choice_count: {payload.get('ready_movable_actor_choice_count', 0)}",
        "",
        "## Notes",
        "- deterministic=True rollout (argmax policy).",
        "- visual_eval_status=unavailable means render failed or no display; metrics are still valid.",
    ]
    if payload.get("render_warning"):
        lines.append(f"- render_warning: {payload['render_warning']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    checkpoint = args.checkpoint.resolve()
    metadata_path = args.model_metadata.resolve()
    output_dir = args.output_dir.resolve()

    if not checkpoint.is_file():
        print(f"[render_eval] ERROR: checkpoint not found: {checkpoint}", file=sys.stderr)
        sys.exit(1)
    if not metadata_path.is_file():
        print(f"[render_eval] ERROR: model_metadata not found: {metadata_path}", file=sys.stderr)
        sys.exit(1)

    device = torch.device(
        "cuda" if torch.cuda.is_available() and args.device.lower() == "cuda" else "cpu"
    )

    print(f"[render_eval] Loading checkpoint: {checkpoint}")
    agent, metadata = load_agent(checkpoint, metadata_path, device)

    # Try to build env with render enabled; fall back to headless on failure.
    render_active = False
    render_warning: Optional[str] = None
    visual_eval_status = "unavailable"
    env = None

    try:
        env = build_env(args.map_path, args.max_steps, args.opponent, render_theme="terrain")
        # Attempt a test render to detect display issues early.
        try:
            env.reset()
            env.render()
            render_active = True
            visual_eval_status = "active"
            print(f"[render_eval] Render window opened successfully.")
        except Exception as e:
            render_warning = f"Render failed after env creation: {type(e).__name__}: {e}"
            print(f"[render_eval] WARNING: {render_warning}", file=sys.stderr)
            visual_eval_status = "unavailable"
    except Exception as e:
        render_warning = f"Env build with render failed: {type(e).__name__}: {e}"
        print(f"[render_eval] WARNING: {render_warning}. Retrying headless.", file=sys.stderr)
        try:
            env = build_env(args.map_path, args.max_steps, args.opponent)
            env.reset()
        except Exception as e2:
            print(f"[render_eval] FATAL: Could not create env at all: {e2}", file=sys.stderr)
            sys.exit(2)

    print(f"[render_eval] Running rollout: max_steps={args.max_steps}, fps={args.fps}, "
          f"render={render_active}, opponent={args.opponent}")

    rollout_data: Dict[str, Any] = {}
    try:
        rollout_data = run_rollout(agent, env, args.max_steps, device, args.fps, render_active)
    finally:
        env.close()

    payload: Dict[str, Any] = {
        "schema": "gridnet_visual_eval.v1",
        "timestamp_utc": utc_now(),
        "checkpoint": str(checkpoint),
        "model_metadata": str(metadata_path),
        "opponent": args.opponent,
        "map_path": args.map_path,
        "max_steps": args.max_steps,
        "fps": args.fps,
        "visual_eval_status": visual_eval_status,
        "deterministic_mode": True,
    }
    if render_warning:
        payload["render_warning"] = render_warning
    payload.update(rollout_data)

    stem = checkpoint.stem
    out_json = output_dir / f"visual_eval_{stem}.json"
    out_md = output_dir / f"visual_eval_{stem}.md"

    write_json(out_json, payload)
    write_markdown(out_md, payload)

    print(f"[render_eval] visual_eval_status={visual_eval_status}")
    print(f"[render_eval] actor_level_move_share={payload.get('actor_level_move_share', 0.0):.6f}")
    print(f"[render_eval] effective_position_delta_count={payload.get('effective_position_delta_count', 0)}")
    print(f"[render_eval] steps_run={payload.get('steps_run', 0)}")
    print(f"[render_eval] Written: {out_json}")
    print(f"[render_eval] Written: {out_md}")


if __name__ == "__main__":
    main()
