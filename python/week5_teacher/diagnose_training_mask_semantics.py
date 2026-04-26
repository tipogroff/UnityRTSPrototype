#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from run_teacher_rollout import RolloutError, build_environment, import_runtime_modules, seed_process
from train_teacher_smoke import build_seed_bundle, wrap_legacy_vec_env_for_sb3_with_options

MASK_SOURCE = 0
MASK_MOVE = 2


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Diagnose whether MaskablePPO training env exposes valid action masks."
    )
    p.add_argument("--env-id", default="MicrortsSelfPlayShapedReward-v1")
    p.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    p.add_argument("--opponent-pool", default="coacAI,workerRushAI,lightRushAI,passiveAI")
    p.add_argument("--opponent-sampling", choices=("static", "per_reset", "per_episode"), default="per_episode")
    p.add_argument("--seed", type=int, default=170)
    p.add_argument("--num-bot-envs", type=int, default=4)
    p.add_argument("--device", default="cpu")
    p.add_argument("--sample-steps", type=int, default=20)
    p.add_argument("--output-root", type=Path, default=Path("WEEK5R/mask_diagnostics"))
    return p.parse_args()


def _read_action_mask_with_source(env_for_training: Any) -> Tuple[Optional[np.ndarray], Optional[str], Optional[str], bool, bool]:
    candidate = None
    source = None
    error = None
    has_action_masks = hasattr(env_for_training, "action_masks")
    has_get_action_mask = hasattr(env_for_training, "get_action_mask")

    if has_get_action_mask:
        try:
            candidate = env_for_training.get_action_mask()
            if candidate is not None:
                source = "env.get_action_mask"
        except Exception as exc:
            error = f"env.get_action_mask failed: {type(exc).__name__}: {exc}"

    if candidate is None and has_action_masks:
        try:
            action_masks_attr = getattr(env_for_training, "action_masks")
            candidate = action_masks_attr() if callable(action_masks_attr) else action_masks_attr
            if candidate is not None:
                source = "env.action_masks"
        except Exception as exc:
            error = f"env.action_masks failed: {type(exc).__name__}: {exc}"

    if candidate is None:
        return None, source, error, has_action_masks, has_get_action_mask

    try:
        return np.asarray(candidate), source, error, has_action_masks, has_get_action_mask
    except Exception as exc:
        return None, source, f"np.asarray(mask) failed: {type(exc).__name__}: {exc}", has_action_masks, has_get_action_mask


def _normalize_mask(mask: np.ndarray) -> Optional[np.ndarray]:
    if mask.ndim == 3:
        return mask
    if mask.ndim == 2:
        return np.expand_dims(mask, axis=0)
    return None


def _infer_move_dir_slice(mask_dim: int) -> Optional[Tuple[int, int]]:
    candidates = [(7, 11), (3, 7)]
    for start, end in candidates:
        if end <= mask_dim:
            return (start, end)
    return None


def _mask_shape_is_valid(mask: np.ndarray, n_cells: int) -> bool:
    if mask.ndim != 3:
        return False
    if mask.shape[1] != n_cells:
        return False
    if mask.shape[2] < 3:
        return False
    return True


def _safe_action_space_sample(env_for_training: Any) -> np.ndarray:
    sampled = env_for_training.action_space.sample()
    arr = np.asarray(sampled)
    num_envs = int(getattr(env_for_training, "num_envs", 1) or 1)
    if arr.ndim == 1 and num_envs > 1:
        return np.repeat(arr[np.newaxis, :], num_envs, axis=0)
    return arr


def _build_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Mask Semantics Report")
    lines.append("")
    lines.append(f"- run_id: `{report['run_id']}`")
    lines.append(f"- verdict: `{report['verdict']}`")
    lines.append(f"- mask_available: `{report['mask_available']}`")
    lines.append(f"- mask_shape: `{report['mask_shape']}`")
    lines.append(f"- mask_dtype: `{report['mask_dtype']}`")
    lines.append(f"- mask_source: `{report.get('mask_source')}`")
    lines.append(f"- steps_sampled: `{report['steps_sampled']}`")
    lines.append(f"- source_unit_mask_nonzero_steps: `{report['source_unit_mask_nonzero_steps']}`")
    lines.append(f"- ready_movable_actor_choice_count: `{report['ready_movable_actor_choice_count']}`")
    lines.append(f"- move_allowed_count: `{report['move_allowed_count']}`")
    lines.append(f"- steps_with_move_valid_teacher_actor: `{report['steps_with_move_valid_teacher_actor']}`")
    lines.append("")
    lines.append("## Warnings")
    if report["warnings"]:
        for warning in report["warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Environment")
    lines.append(f"- env_id: `{report['env_id']}`")
    lines.append(f"- map_path: `{report['map_path']}`")
    lines.append(f"- opponent_pool: `{report['opponent_pool']}`")
    lines.append(f"- opponent_sampling: `{report['opponent_sampling']}`")
    lines.append(f"- num_bot_envs: `{report['num_bot_envs']}`")
    return "\n".join(lines) + "\n"


def diagnose(args: argparse.Namespace) -> Dict[str, Any]:
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

    logger = logging.getLogger("diagnose_training_mask_semantics")
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

    sample_steps = max(10, min(int(args.sample_steps), 50))
    n_cells = 576
    action_space = getattr(env_for_training, "action_space", None)
    nvec = getattr(action_space, "nvec", None)
    if nvec is not None:
        nvec_size = int(np.asarray(nvec).size)
        if nvec_size % 7 == 0:
            n_cells = nvec_size // 7

    warnings: List[str] = []
    mask_available = False
    mask_shape: Optional[List[int]] = None
    mask_dtype: Optional[str] = None
    mask_source: Optional[str] = None
    source_unit_mask_nonzero_steps = 0
    ready_movable_actor_choice_count = 0
    move_allowed_count = 0
    steps_with_move_valid_teacher_actor = 0
    mask_shape_invalid = False

    try:
        env_for_training.reset()
        for _ in range(sample_steps):
            mask_raw, source, error, has_action_masks, has_get_action_mask = _read_action_mask_with_source(env_for_training)
            if source and mask_source is None:
                mask_source = source
            if error:
                warnings.append(error)

            if not has_action_masks and not has_get_action_mask:
                warnings.append("env_for_training has neither action_masks nor get_action_mask")

            if mask_raw is None:
                sampled_action = _safe_action_space_sample(env_for_training)
                env_for_training.step(sampled_action)
                continue

            mask = _normalize_mask(mask_raw)
            if mask is None:
                mask_shape_invalid = True
                mask_shape = list(mask_raw.shape)
                mask_dtype = str(mask_raw.dtype)
                warnings.append(f"Unsupported mask ndim={mask_raw.ndim}; expected 2D or 3D")
                sampled_action = _safe_action_space_sample(env_for_training)
                env_for_training.step(sampled_action)
                continue

            mask_available = True
            mask_shape = list(mask.shape)
            mask_dtype = str(mask.dtype)

            if not _mask_shape_is_valid(mask, n_cells):
                mask_shape_invalid = True
                warnings.append(
                    f"Invalid mask shape {tuple(mask.shape)}; expected [num_envs, {n_cells}, >=3]"
                )
                sampled_action = _safe_action_space_sample(env_for_training)
                env_for_training.step(sampled_action)
                continue

            source_mask = mask[:, :, MASK_SOURCE] > 0
            move_allowed_mask = mask[:, :, MASK_MOVE] > 0
            source_unit_mask_nonzero_steps += int(np.any(source_mask))
            ready_movable = np.logical_and(source_mask, move_allowed_mask)
            ready_movable_actor_choice_count += int(ready_movable.sum())
            move_allowed_count += int(move_allowed_mask.sum())
            steps_with_move_valid_teacher_actor += int(np.any(ready_movable))

            move_dir_slice = _infer_move_dir_slice(mask.shape[2])
            if move_dir_slice is None:
                warnings.append("Move-direction slice not inferable from mask width")

            sampled_action = _safe_action_space_sample(env_for_training)
            env_for_training.step(sampled_action)
    finally:
        try:
            env.close()
        except Exception:
            pass

    if not mask_available:
        verdict = "MASK_MISSING"
    elif mask_shape_invalid:
        verdict = "MASK_SHAPE_INVALID"
    elif source_unit_mask_nonzero_steps == 0:
        verdict = "MASK_NO_MOVABLE_ACTORS"
    elif ready_movable_actor_choice_count == 0:
        verdict = "MASK_NO_MOVABLE_ACTORS"
    elif move_allowed_count == 0:
        verdict = "MASK_NO_MOVE_ALLOWED"
    elif steps_with_move_valid_teacher_actor == 0:
        verdict = "MASK_NO_MOVE_ALLOWED"
    else:
        verdict = "MASK_OK"

    report: Dict[str, Any] = {
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "env_id": args.env_id,
        "map_path": args.map_path,
        "opponent_pool": args.opponent_pool,
        "opponent_sampling": args.opponent_sampling,
        "seed": args.seed,
        "num_bot_envs": args.num_bot_envs,
        "device": args.device,
        "steps_sampled": sample_steps,
        "mask_available": bool(mask_available),
        "mask_shape": mask_shape,
        "mask_dtype": mask_dtype,
        "mask_source": mask_source,
        "source_unit_mask_nonzero_steps": int(source_unit_mask_nonzero_steps),
        "ready_movable_actor_choice_count": int(ready_movable_actor_choice_count),
        "move_allowed_count": int(move_allowed_count),
        "steps_with_move_valid_teacher_actor": int(steps_with_move_valid_teacher_actor),
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

    json_path = output_dir / "mask_semantics_report.json"
    md_path = output_dir / "mask_semantics_report.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_build_markdown(report), encoding="utf-8")

    print(f"[mask-diagnose] verdict={verdict}")
    print(f"[mask-diagnose] report_json={json_path}")
    print(f"[mask-diagnose] report_md={md_path}")

    return report


def main() -> int:
    args = parse_args()
    report = diagnose(args)
    verdict = str(report.get("verdict", ""))
    if verdict in ("MASK_MISSING", "MASK_SHAPE_INVALID"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
