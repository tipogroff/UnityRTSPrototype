#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from run_teacher_rollout import build_environment, import_runtime_modules, seed_process
from train_teacher_smoke import build_seed_bundle, wrap_legacy_vec_env_for_sb3_with_options

MASK_SOURCE = 0
MASK_MOVE = 2
ACT_TYPE = 0
ACT_MOVE_DIR = 1
ACTION_NOOP = 0
ACTION_MOVE = 1


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run masked random actor baseline to validate movement is physically reachable."
    )
    p.add_argument("--env-id", default="MicrortsSelfPlayShapedReward-v1")
    p.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    p.add_argument("--opponent-pool", default="workerRushAI")
    p.add_argument("--opponent-sampling", choices=("static", "per_reset", "per_episode"), default="static")
    p.add_argument("--seed", type=int, default=170)
    p.add_argument("--num-bot-envs", type=int, default=4)
    p.add_argument("--device", default="cpu")
    p.add_argument("--steps", type=int, default=120)
    p.add_argument("--output-root", type=Path, default=Path("WEEK5R/mask_diagnostics"))
    return p.parse_args()


def _read_action_mask(env_for_training: Any) -> Optional[np.ndarray]:
    candidate = None
    if hasattr(env_for_training, "get_action_mask"):
        try:
            candidate = env_for_training.get_action_mask()
        except Exception:
            candidate = None
    if candidate is None and hasattr(env_for_training, "action_masks"):
        try:
            action_masks_attr = getattr(env_for_training, "action_masks")
            candidate = action_masks_attr() if callable(action_masks_attr) else action_masks_attr
        except Exception:
            candidate = None
    if candidate is None:
        return None
    try:
        arr = np.asarray(candidate)
    except Exception:
        return None
    if arr.ndim == 2:
        arr = np.expand_dims(arr, axis=0)
    if arr.ndim != 3:
        return None
    return arr


def _infer_move_dir_slice(mask_dim: int) -> Optional[Tuple[int, int]]:
    candidates = [(7, 11), (3, 7)]
    for start, end in candidates:
        if end <= mask_dim:
            return (start, end)
    return None


def _extract_teacher_positions(obs_batch: np.ndarray) -> List[Set[Tuple[int, int]]]:
    # Observation layout expected as [env, H, W, C], owner-self channel = 11.
    if obs_batch.ndim != 4 or obs_batch.shape[-1] < 13:
        return [set() for _ in range(int(obs_batch.shape[0]) if obs_batch.ndim > 0 else 1)]

    positions_per_env: List[Set[Tuple[int, int]]] = []
    for env_idx in range(obs_batch.shape[0]):
        obs = obs_batch[env_idx]
        owner_self = obs[:, :, 11] > 0.5
        unit_present = np.max(obs[:, :, 13:21], axis=2) > 0.1
        teacher_units = np.logical_and(owner_self, unit_present)
        ys, xs = np.where(teacher_units)
        positions_per_env.append(set((int(x), int(y)) for y, x in zip(ys.tolist(), xs.tolist())))
    return positions_per_env


def _build_markdown(result: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Masked Random Actor Baseline")
    lines.append("")
    lines.append(f"- run_id: `{result['run_id']}`")
    lines.append(f"- verdict: `{result['verdict']}`")
    lines.append(f"- steps: `{result['steps']}`")
    lines.append(f"- attempts_move: `{result['attempts_move']}`")
    lines.append(f"- effective_position_delta_count: `{result['effective_position_delta_count']}`")
    lines.append(f"- move_success_share: `{result['move_success_share']:.4f}`")
    lines.append(f"- ready_movable_actor_choice_count: `{result['ready_movable_actor_choice_count']}`")
    lines.append(f"- no_effect_share: `{result['no_effect_share']:.4f}`")
    lines.append("")
    lines.append("## Warnings")
    if result["warnings"]:
        for warning in result["warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def run_baseline(args: argparse.Namespace) -> Dict[str, Any]:
    run_id = utc_stamp()
    output_dir = args.output_root / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    modules, versions = import_runtime_modules()
    seed_bundle = build_seed_bundle(argparse.Namespace(seed=args.seed, env_seed=None, rollout_seed=None))
    seed_process(seed_bundle, modules)

    env_args = argparse.Namespace(
        env_id=args.env_id,
        map_path=args.map_path,
        rollout_step_limit=2000,
        num_bot_envs=args.num_bot_envs,
        backend_mode="allow_fallback",
        force_legacy_backend=False,
        opponent_pool=args.opponent_pool,
        opponent_sampling=args.opponent_sampling,
        opponent_seed=args.seed + 100,
        seed=args.seed,
    )

    import logging

    logger = logging.getLogger("run_masked_random_actor_baseline")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    env, _initial_observation, _reset_info, env_summary = build_environment(
        args=env_args,
        seed_bundle=seed_bundle,
        modules=modules,
        logger=logger,
    )

    timing_state = {
        "env_step_seconds": 0.0,
        "mask_seconds": 0.0,
        "env_step_calls": 0,
        "mask_calls": 0,
    }
    env_for_training = wrap_legacy_vec_env_for_sb3_with_options(
        env,
        enable_mask_hot_path=False,
        timing_state=timing_state,
        opponent_sampling=args.opponent_sampling,
        opponent_seed=args.seed + 100,
    )

    rng = random.Random(args.seed + 12345)
    steps = max(20, int(args.steps))
    warnings: List[str] = []

    attempts_move = 0
    effective_position_delta_count = 0
    ready_movable_actor_choice_count = 0
    no_effect_count = 0
    mask_insufficient_events = 0

    try:
        obs = np.asarray(env_for_training.reset())
        num_envs = int(obs.shape[0]) if obs.ndim >= 1 else int(getattr(env_for_training, "num_envs", 1))

        action_space = getattr(env_for_training, "action_space", None)
        n_cells = 576
        nvec = getattr(action_space, "nvec", None)
        if nvec is not None:
            nvec_size = int(np.asarray(nvec).size)
            if nvec_size % 7 == 0:
                n_cells = nvec_size // 7

        for _ in range(steps):
            mask = _read_action_mask(env_for_training)
            if mask is None:
                warnings.append("Action mask unavailable during baseline step")
                sampled_action = np.asarray(env_for_training.action_space.sample())
                obs, _rewards, _dones, _infos = env_for_training.step(sampled_action)
                obs = np.asarray(obs)
                continue

            if mask.shape[0] != num_envs or mask.shape[1] != n_cells or mask.shape[2] < 3:
                warnings.append(
                    f"Unexpected mask shape {tuple(mask.shape)}; expected [{num_envs}, {n_cells}, >=3]"
                )
                sampled_action = np.asarray(env_for_training.action_space.sample())
                obs, _rewards, _dones, _infos = env_for_training.step(sampled_action)
                obs = np.asarray(obs)
                continue

            action = np.zeros((num_envs, n_cells, 7), dtype=np.int32)
            action[:, :, ACT_TYPE] = ACTION_NOOP

            positions_before = _extract_teacher_positions(np.asarray(obs))

            for env_idx in range(num_envs):
                source_mask = mask[env_idx, :, MASK_SOURCE] > 0
                move_allowed = mask[env_idx, :, MASK_MOVE] > 0
                movable_indices = np.where(np.logical_and(source_mask, move_allowed))[0]
                ready_movable_actor_choice_count += int(movable_indices.size)

                if movable_indices.size == 0:
                    continue

                selected_idx = int(rng.choice(movable_indices.tolist()))
                action[env_idx, selected_idx, ACT_TYPE] = ACTION_MOVE
                attempts_move += 1

                move_dir_slice = _infer_move_dir_slice(mask.shape[2])
                if move_dir_slice is not None:
                    start, end = move_dir_slice
                    dir_mask = mask[env_idx, selected_idx, start:end] > 0
                    valid_dirs = np.where(dir_mask)[0]
                    if valid_dirs.size > 0:
                        action[env_idx, selected_idx, ACT_MOVE_DIR] = int(rng.choice(valid_dirs.tolist()))
                    else:
                        action[env_idx, selected_idx, ACT_MOVE_DIR] = int(rng.randrange(4))
                        mask_insufficient_events += 1
                else:
                    action[env_idx, selected_idx, ACT_MOVE_DIR] = int(rng.randrange(4))
                    mask_insufficient_events += 1

            obs_next, _rewards, _dones, _infos = env_for_training.step(action)
            obs_next_arr = np.asarray(obs_next)
            positions_after = _extract_teacher_positions(obs_next_arr)

            for env_idx in range(num_envs):
                if positions_before[env_idx] != positions_after[env_idx]:
                    effective_position_delta_count += 1

            obs = obs_next_arr

        no_effect_count = max(attempts_move - effective_position_delta_count, 0)
    finally:
        try:
            env.close()
        except Exception:
            pass

    move_success_share = float(effective_position_delta_count / attempts_move) if attempts_move > 0 else 0.0
    no_effect_share = float(no_effect_count / attempts_move) if attempts_move > 0 else 1.0

    if attempts_move == 0 and ready_movable_actor_choice_count == 0:
        verdict = "BASELINE_MASK_INSUFFICIENT"
    elif effective_position_delta_count > 0:
        verdict = "BASELINE_CAN_MOVE"
    elif attempts_move > 0 and effective_position_delta_count == 0:
        verdict = "BASELINE_CANNOT_MOVE"
    else:
        verdict = "BASELINE_MASK_INSUFFICIENT"

    result: Dict[str, Any] = {
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "env_id": args.env_id,
        "map_path": args.map_path,
        "opponent_pool": args.opponent_pool,
        "opponent_sampling": args.opponent_sampling,
        "seed": args.seed,
        "num_bot_envs": args.num_bot_envs,
        "device": args.device,
        "steps": steps,
        "attempts_move": int(attempts_move),
        "effective_position_delta_count": int(effective_position_delta_count),
        "move_success_share": float(move_success_share),
        "ready_movable_actor_choice_count": int(ready_movable_actor_choice_count),
        "no_effect_share": float(no_effect_share),
        "mask_insufficient_events": int(mask_insufficient_events),
        "warnings": warnings,
        "verdict": verdict,
        "runtime_versions": {
            "python_version": versions.python_version,
            "torch_version": versions.torch_version,
            "numpy_version": versions.numpy_version,
            "stable_baselines3_version": versions.stable_baselines3_version,
            "gym_api_name": versions.gym_api_name,
            "gym_api_version": versions.gym_api_version,
            "microrts_module_name": versions.microrts_module_name,
            "microrts_version": versions.microrts_version,
        },
        "env_summary": env_summary,
    }

    json_path = output_dir / "masked_random_baseline.json"
    md_path = output_dir / "masked_random_baseline.md"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_build_markdown(result), encoding="utf-8")

    print(f"[masked-baseline] verdict={verdict}")
    print(f"[masked-baseline] report_json={json_path}")
    print(f"[masked-baseline] report_md={md_path}")

    return result


def main() -> int:
    args = parse_args()
    result = run_baseline(args)
    if result["verdict"] == "BASELINE_CANNOT_MOVE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
