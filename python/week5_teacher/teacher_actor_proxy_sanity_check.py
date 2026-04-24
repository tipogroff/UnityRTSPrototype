#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

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
        description="Short source_unit_mask sanity check for teacher actor proxy (first N steps)."
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    parser.add_argument("--opponent", default="workerRushAI")
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument("--device", default="cpu")
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("WEEK6/teacher_source_unit_mask_sanity.json"),
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("WEEK6/TEACHER_SOURCE_UNIT_MASK_SANITY.md"),
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


def idx_to_xy(index: int, width: int) -> Dict[str, int]:
    return {"x": int(index % width), "y": int(index // width)}


def run_sanity(args: argparse.Namespace) -> Dict[str, Any]:
    checkpoint = args.checkpoint.resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint}")

    model, loader_name = load_model(checkpoint, args.device)
    env = build_env(args.map_path, args.max_steps, args.opponent)

    obs = env.reset()
    obs_arr = np.asarray(obs)
    if obs_arr.ndim != 4 or obs_arr.shape[0] != 1:
        raise RuntimeError(f"Unexpected observation shape: {obs_arr.shape}")

    height, width, channels = int(obs_arr.shape[1]), int(obs_arr.shape[2]), int(obs_arr.shape[3])

    step_trace: List[Dict[str, Any]] = []
    total_actor_choices = 0
    total_actor_move_choices = 0
    steps_with_any_actor_move = 0

    for step_id in range(args.max_steps):
        obs_arr = np.asarray(obs)
        action_mask = read_action_mask(env)
        if action_mask is None:
            raise RuntimeError("Action mask is unavailable; cannot validate source_unit_mask proxy.")
        if action_mask.ndim != 3 or action_mask.shape[0] != 1 or action_mask.shape[1] != height * width:
            raise RuntimeError(f"Unexpected action mask shape: {action_mask.shape}")

        action = predict_action(model, obs, action_mask)
        action_matrix = action_to_matrix(action)
        if action_matrix.shape[0] != height * width:
            raise RuntimeError(
                f"Action spatial size mismatch. expected={height*width}, got={action_matrix.shape[0]}"
            )

        action_type_full = action_matrix[:, 0]
        full_tensor_counter = Counter(int(v) for v in action_type_full.tolist())

        ready_mask = action_mask[0, :, 0].astype(bool)
        ready_indices = np.where(ready_mask)[0].tolist()
        actor_counter = Counter()
        move_allowed_count = 0

        per_actor: List[Dict[str, Any]] = []
        for idx in ready_indices:
            idx_int = int(idx)
            chosen = int(action_type_full[idx_int])
            actor_counter[chosen] += 1

            mask_row = action_mask[0, idx_int]
            move_allowed = bool(mask_row[2]) if mask_row.shape[0] >= 3 else False
            if move_allowed:
                move_allowed_count += 1

            xy = idx_to_xy(idx_int, width)
            cell_obs = obs_arr[0, xy["y"], xy["x"], :]

            # Optional observation-channel proxy using Week contract indexing.
            owner_proxy = cell_obs[2:5].astype(float).tolist() if channels >= 5 else []
            unit_type_proxy = cell_obs[5:12].astype(float).tolist() if channels >= 12 else []

            per_actor.append(
                {
                    "flat_index": idx_int,
                    "x": xy["x"],
                    "y": xy["y"],
                    "chosen_action_type": ACTION_NAMES.get(chosen, str(chosen)),
                    "move_allowed_by_action_mask": move_allowed,
                    "observation_owner_proxy_channels_2_4": owner_proxy,
                    "observation_unit_type_proxy_channels_5_11": unit_type_proxy,
                }
            )

        actor_move_count = int(actor_counter.get(1, 0))
        if actor_move_count > 0:
            steps_with_any_actor_move += 1

        total_actor_choices += int(sum(actor_counter.values()))
        total_actor_move_choices += actor_move_count

        step_trace.append(
            {
                "step": int(step_id),
                "source_unit_mask_ready_count": int(len(ready_indices)),
                "source_unit_mask_ready_indices": [int(x) for x in ready_indices],
                "source_unit_mask_ready_coords": [idx_to_xy(int(x), width) for x in ready_indices],
                "selected_action_types_on_ready_actors": {
                    ACTION_NAMES[k]: int(v) for k, v in sorted(actor_counter.items())
                },
                "move_allowed_ready_actor_count": int(move_allowed_count),
                "move_selected_ready_actor_count": int(actor_move_count),
                "full_tensor_action_types_count": {
                    ACTION_NAMES[k]: int(v) for k, v in sorted(full_tensor_counter.items())
                },
                "ready_actor_details": per_actor,
            }
        )

        transition = env.step(action)
        if len(transition) == 5:
            obs, _reward, terminated, truncated, _info = transition
            done = bool(terminated or truncated)
        else:
            obs, _reward, done, _info = transition

        if done:
            break

    try:
        env.close()
    except Exception:
        pass

    actor_move_share = (total_actor_move_choices / total_actor_choices) if total_actor_choices > 0 else 0.0

    proxy_valid = all(s["source_unit_mask_ready_count"] > 0 for s in step_trace[: min(5, len(step_trace))])

    return {
        "generated_at_utc": utc_now(),
        "checkpoint": {
            "path": str(checkpoint),
            "loader": loader_name,
        },
        "protocol": {
            "map_path": args.map_path,
            "opponent": args.opponent,
            "requested_steps": args.max_steps,
            "executed_steps": len(step_trace),
        },
        "shapes": {
            "observation": [1, height, width, channels],
            "action_mask": list(np.asarray(action_mask).shape),
            "action_spatial": [height * width, 7],
        },
        "method": {
            "raw_full_tensor_level": "action_type over all spatial slots",
            "actor_proxy_level": "action_type over source_unit_mask==1 indices only",
            "executed_fact_claim": "not claimed; this is chosen-action proxy-level check",
            "owner_proxy_note": "owner/unit_type channel slices are optional observation-channel proxies assuming Week contract indexing",
        },
        "step_trace": step_trace,
        "summary": {
            "total_actor_choices": int(total_actor_choices),
            "total_actor_move_choices": int(total_actor_move_choices),
            "steps_with_any_actor_move": int(steps_with_any_actor_move),
            "actor_move_share": float(actor_move_share),
            "proxy_validity_hint": "source_unit_mask proxy looks valid" if proxy_valid else "source_unit_mask proxy looks suspicious",
        },
    }


def build_md(report: Dict[str, Any]) -> str:
    lines: List[str] = []

    lines.append("# Teacher Source Unit Mask Sanity Check")
    lines.append("")
    lines.append(f"Generated at (UTC): {report['generated_at_utc']}")
    lines.append("")
    lines.append("## Checkpoint")
    lines.append(f"- Path: {report['checkpoint']['path']}")
    lines.append(f"- Loader: {report['checkpoint']['loader']}")
    lines.append("")
    lines.append("## Protocol")
    lines.append(f"- Map: {report['protocol']['map_path']}")
    lines.append(f"- Opponent: {report['protocol']['opponent']}")
    lines.append(f"- Requested steps: {report['protocol']['requested_steps']}")
    lines.append(f"- Executed steps: {report['protocol']['executed_steps']}")
    lines.append("")
    lines.append("## Step Trace (Compact)")
    for step in report["step_trace"]:
        lines.append(
            "- "
            + f"step={step['step']} ready={step['source_unit_mask_ready_count']} "
            + f"move_allowed={step['move_allowed_ready_actor_count']} "
            + f"move_selected={step['move_selected_ready_actor_count']} "
            + f"ready_actions={step['selected_action_types_on_ready_actors']} "
            + f"coords={step['source_unit_mask_ready_coords']}"
        )
    lines.append("")
    lines.append("## Levels Separation")
    lines.append(f"- Raw full tensor: {report['method']['raw_full_tensor_level']}")
    lines.append(f"- Source-unit-mask actor proxy: {report['method']['actor_proxy_level']}")
    lines.append(f"- Execution claim: {report['method']['executed_fact_claim']}")
    lines.append("")
    lines.append("## Conclusion")
    lines.append(f"- {report['summary']['proxy_validity_hint']}")
    lines.append(
        "- "
        + f"Actor-level Move choices: {report['summary']['total_actor_move_choices']} / {report['summary']['total_actor_choices']} "
        + f"({report['summary']['actor_move_share'] * 100.0:.2f}%)"
    )

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    report = run_sanity(args)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)

    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(build_md(report), encoding="utf-8")

    print(f"checkpoint={report['checkpoint']['path']}")
    print(f"executed_steps={report['protocol']['executed_steps']}")
    print(f"wrote_json={args.output_json}")
    print(f"wrote_md={args.output_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
