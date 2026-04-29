#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

BRANCH_LAYOUT: List[int] = [6, 4, 4, 4, 4, 7, 49]
BRANCH_NAMES: List[str] = [
    "action_type",
    "move_dir",
    "harvest_dir",
    "return_dir",
    "produce_dir",
    "produce_unit_type",
    "attack_target",
]
EXPECTED_MASK_DEPTH = 1 + sum(BRANCH_LAYOUT)
EXPECTED_OBS_CHANNELS = 27
DEFAULT_OUTPUT_DIR = Path("python/week5_teacher/mask_audit")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def bootstrap_import_paths() -> None:
    here = Path(__file__).resolve()
    week5_dir = here.parent.parent
    root_dir = week5_dir.parent.parent
    gridnet_dir = root_dir / "python" / "week5_teacher_gridnet"
    for path in [root_dir, week5_dir, gridnet_dir]:
        p = str(path)
        if p not in sys.path:
            sys.path.insert(0, p)


bootstrap_import_paths()

from run_teacher_rollout import build_environment, import_runtime_modules, seed_process  # noqa: E402
from train_teacher_smoke import build_seed_bundle, wrap_legacy_vec_env_for_sb3_with_options  # noqa: E402


@dataclass
class RuntimeContext:
    modules: Dict[str, Optional[Any]]
    versions: Any
    seed_bundle: Any


def branch_slices() -> Dict[str, Tuple[int, int]]:
    start = 1
    out: Dict[str, Tuple[int, int]] = {}
    for name, size in zip(BRANCH_NAMES, BRANCH_LAYOUT):
        out[name] = (start, start + size)
        start += size
    return out


def index_to_attack_offset(index: int) -> Tuple[int, int]:
    if index < 0 or index >= 49:
        raise ValueError(f"attack target index out of range: {index}")
    row = index // 7
    col = index % 7
    return col - 3, row - 3


def safe_json_dump(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json_or_none(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def parse_common_args(description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--env-id", default="MicrortsSelfPlayShapedReward-v1")
    p.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    p.add_argument("--opponent-pool", default="passiveAI")
    p.add_argument("--opponent-sampling", choices=("static", "per_reset", "per_episode"), default="static")
    p.add_argument("--seed", type=int, default=170)
    p.add_argument("--num-bot-envs", type=int, default=4)
    p.add_argument("--rollout-step-limit", type=int, default=2000)
    p.add_argument("--device", default="cpu")
    return p


def create_runtime_context(seed: int) -> RuntimeContext:
    modules, versions = import_runtime_modules()
    seed_bundle = build_seed_bundle(argparse.Namespace(seed=seed, env_seed=None, rollout_seed=None))
    seed_process(seed_bundle, modules)
    return RuntimeContext(modules=modules, versions=versions, seed_bundle=seed_bundle)


def create_wrapped_env(args: argparse.Namespace, ctx: RuntimeContext) -> Tuple[Any, Any, Dict[str, Any], Dict[str, Any]]:
    env_args = argparse.Namespace(
        env_id=args.env_id,
        map_path=args.map_path,
        rollout_step_limit=args.rollout_step_limit,
        num_bot_envs=args.num_bot_envs,
        backend_mode="allow_fallback",
        force_legacy_backend=False,
        opponent_pool=args.opponent_pool,
        opponent_sampling=args.opponent_sampling,
        opponent_seed=args.seed + 100,
        seed=args.seed,
    )

    import logging

    logger = logging.getLogger("mask_audit")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    env, initial_observation, reset_info, env_summary = build_environment(
        args=env_args,
        seed_bundle=ctx.seed_bundle,
        modules=ctx.modules,
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
    return env, env_for_training, env_summary, timing_state


def reset_compat(env: Any) -> Tuple[np.ndarray, Dict[str, Any]]:
    out = env.reset()
    if isinstance(out, tuple) and len(out) == 2:
        obs, info = out
        return np.asarray(obs), info if isinstance(info, dict) else {}
    return np.asarray(out), {}


def step_compat(env: Any, action: Any) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[Dict[str, Any]]]:
    out = env.step(action)
    if isinstance(out, tuple) and len(out) == 4:
        obs, rew, done, info = out
        infos = info if isinstance(info, list) else [info] if isinstance(info, dict) else [{}]
        return np.asarray(obs), np.asarray(rew), np.asarray(done), infos
    if isinstance(out, tuple) and len(out) == 5:
        obs, rew, terminated, truncated, info = out
        done = np.logical_or(np.asarray(terminated), np.asarray(truncated))
        infos = info if isinstance(info, list) else [info] if isinstance(info, dict) else [{}]
        return np.asarray(obs), np.asarray(rew), np.asarray(done), infos
    raise RuntimeError(f"Unsupported step output format: {type(out)}")


def obs_hw(obs: np.ndarray) -> Tuple[Optional[int], Optional[int]]:
    if obs.ndim == 4:
        return int(obs.shape[1]), int(obs.shape[2])
    return None, None


def normalize_mask(mask: np.ndarray, height: Optional[int], width: Optional[int]) -> Optional[np.ndarray]:
    m = np.asarray(mask)
    if m.ndim == 2:
        m = np.expand_dims(m, axis=0)
    if m.ndim == 4:
        return m
    if m.ndim != 3:
        return None

    n, cells, k = m.shape
    if height is not None and width is not None and cells == height * width:
        return m.reshape(n, height, width, k)

    side = int(round(np.sqrt(cells)))
    if side * side == cells:
        return m.reshape(n, side, side, k)
    return None


def mask_source_candidates(env: Any, infos: Optional[List[Dict[str, Any]]] = None) -> List[Tuple[str, np.ndarray]]:
    candidates: List[Tuple[str, np.ndarray]] = []

    if hasattr(env, "get_action_mask"):
        try:
            candidates.append(("env.get_action_mask", np.asarray(env.get_action_mask())))
        except Exception:
            pass

    if hasattr(env, "action_masks"):
        try:
            raw = getattr(env, "action_masks")
            value = raw() if callable(raw) else raw
            candidates.append(("env.action_masks", np.asarray(value)))
        except Exception:
            pass

    vec_client = getattr(env, "vec_client", None)
    if vec_client is not None and hasattr(vec_client, "getMasks"):
        try:
            candidates.append(("env.vec_client.getMasks", np.asarray(vec_client.getMasks(0))))
        except Exception:
            pass

    if infos:
        for info in infos:
            if isinstance(info, dict) and "action_mask" in info:
                try:
                    candidates.append(("info['action_mask']", np.asarray(info["action_mask"])))
                    break
                except Exception:
                    pass

    return candidates


def build_full_mask_from_candidates(
    env: Any,
    obs: np.ndarray,
    infos: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Optional[np.ndarray], str, List[str]]:
    warnings: List[str] = []
    h, w = obs_hw(obs)
    candidates = mask_source_candidates(env, infos=infos)

    for source_name, candidate in candidates:
        if source_name == "env.get_action_mask":
            source_unit = getattr(env, "source_unit_mask", None)
            if source_unit is None:
                warnings.append("env.get_action_mask available but source_unit_mask missing")
                continue

            try:
                source_arr = np.asarray(source_unit)
                norm_candidate = normalize_mask(candidate, h, w)
                if norm_candidate is None:
                    warnings.append(f"{source_name} returned unsupported shape {tuple(candidate.shape)}")
                    continue

                if source_arr.ndim == 2:
                    source_arr = source_arr[:, :, np.newaxis]
                elif source_arr.ndim == 3 and source_arr.shape[-1] != 1:
                    source_arr = source_arr[:, :, np.newaxis]
                elif source_arr.ndim == 4 and source_arr.shape[-1] == 1:
                    pass
                else:
                    source_arr = np.asarray(source_arr)

                if norm_candidate.ndim == 4:
                    n, hh, ww, kk = norm_candidate.shape
                    if source_arr.ndim == 3 and source_arr.shape[1] == hh * ww:
                        source_arr = source_arr.reshape(n, hh, ww, 1)
                    elif source_arr.ndim == 2 and source_arr.shape[1] == hh * ww:
                        source_arr = source_arr.reshape(n, hh, ww, 1)
                    elif source_arr.ndim == 3 and source_arr.shape == (n, hh, ww):
                        source_arr = source_arr[..., np.newaxis]

                    if source_arr.ndim != 4:
                        warnings.append(f"source_unit_mask unsupported shape {tuple(np.asarray(source_unit).shape)}")
                        continue

                    if kk == EXPECTED_MASK_DEPTH:
                        return norm_candidate, source_name + "(full)", warnings
                    if kk == EXPECTED_MASK_DEPTH - 1:
                        full = np.concatenate([source_arr, norm_candidate], axis=3)
                        return full, source_name + "+source_unit_mask", warnings

                    warnings.append(
                        f"Unexpected mask depth from {source_name}: {kk} (expected 78 or 79 tail)")
            except Exception as exc:
                warnings.append(f"Failed to compose full mask from {source_name}: {type(exc).__name__}: {exc}")
            continue

        norm = normalize_mask(candidate, h, w)
        if norm is None:
            warnings.append(f"{source_name} returned unsupported shape {tuple(candidate.shape)}")
            continue
        if norm.shape[-1] == EXPECTED_MASK_DEPTH:
            return norm, source_name, warnings
        if norm.shape[-1] == EXPECTED_MASK_DEPTH - 1:
            source_unit = getattr(env, "source_unit_mask", None)
            if source_unit is None:
                # Fallback: infer actor/source from action_type validity.
                # In this MicroRTS variant the 78-tail may omit source_unit_mask.
                action_type_start = 0
                action_type_end = BRANCH_LAYOUT[0]
                inferred_source = (np.any(norm[:, :, :, action_type_start:action_type_end] > 0, axis=3)).astype(norm.dtype)
                inferred_source = inferred_source[:, :, :, np.newaxis]
                full = np.concatenate([inferred_source, norm], axis=3)
                warnings.append(
                    f"{source_name} returned 78 channels; source_unit_mask missing, actor/source reconstructed from action_type validity"
                )
                return full, source_name + "+inferred_source_from_action_type", warnings
            source_arr = np.asarray(source_unit)
            if source_arr.ndim == 2 and h is not None and w is not None:
                source_arr = source_arr.reshape(source_arr.shape[0], h, w, 1)
            elif source_arr.ndim == 3 and source_arr.shape[-1] != 1 and h is not None and w is not None:
                source_arr = source_arr.reshape(source_arr.shape[0], h, w, 1)
            elif source_arr.ndim == 3 and source_arr.shape[-1] == 1:
                source_arr = source_arr
            elif source_arr.ndim == 3 and h is not None and w is not None and source_arr.shape[1:] == (h, w):
                source_arr = source_arr[..., np.newaxis]
            else:
                warnings.append(f"Cannot normalize source_unit_mask shape {tuple(np.asarray(source_unit).shape)}")
                continue
            full = np.concatenate([source_arr, norm], axis=3)
            return full, source_name + "+source_unit_mask", warnings

    return None, "unknown", warnings


def mask_has_expected_shape(mask: np.ndarray, obs: np.ndarray) -> bool:
    if mask.ndim != 4:
        return False
    if obs.ndim != 4:
        return False
    return (
        mask.shape[0] == obs.shape[0]
        and mask.shape[1] == obs.shape[1]
        and mask.shape[2] == obs.shape[2]
        and mask.shape[3] == EXPECTED_MASK_DEPTH
    )


def flatten_mask(mask_nhwk: np.ndarray) -> np.ndarray:
    n, h, w, k = mask_nhwk.shape
    return mask_nhwk.reshape(n, h * w, k)


def flatten_obs(obs_nhwc: np.ndarray) -> np.ndarray:
    n, h, w, c = obs_nhwc.shape
    return obs_nhwc.reshape(n, h * w, c)


def get_branch(mask_flat: np.ndarray, branch_name: str) -> np.ndarray:
    s, e = branch_slices()[branch_name]
    return mask_flat[:, :, s:e]


def make_random_valid_actions(mask_flat: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    n, cells, _k = mask_flat.shape
    actions = np.zeros((n, cells, 7), dtype=np.int32)
    slices = branch_slices()

    for env_i in range(n):
        for cell in range(cells):
            if mask_flat[env_i, cell, 0] <= 0:
                continue
            for b_idx, branch_name in enumerate(BRANCH_NAMES):
                s, e = slices[branch_name]
                valid = np.where(mask_flat[env_i, cell, s:e] > 0)[0]
                if valid.size == 0:
                    actions[env_i, cell, b_idx] = 0
                else:
                    actions[env_i, cell, b_idx] = int(rng.choice(valid))
    return actions


def safe_action_space_sample(env: Any) -> np.ndarray:
    sampled = np.asarray(env.action_space.sample())
    num_envs = int(getattr(env, "num_envs", 1) or 1)
    if sampled.ndim == 1 and num_envs > 1:
        return np.repeat(sampled[np.newaxis, :], num_envs, axis=0)
    return sampled


def runtime_versions_payload(versions: Any) -> Dict[str, Any]:
    return {
        "python_version": getattr(versions, "python_version", None),
        "torch_version": getattr(versions, "torch_version", None),
        "numpy_version": getattr(versions, "numpy_version", None),
        "stable_baselines3_version": getattr(versions, "stable_baselines3_version", None),
        "gym_api_name": getattr(versions, "gym_api_name", None),
        "gym_api_version": getattr(versions, "gym_api_version", None),
        "microrts_module_name": getattr(versions, "microrts_module_name", None),
        "microrts_version": getattr(versions, "microrts_version", None),
    }


def environment_payload(args: argparse.Namespace, env_summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "env_id": args.env_id,
        "map_path": args.map_path,
        "opponent_pool": args.opponent_pool,
        "opponent_sampling": args.opponent_sampling,
        "num_bot_envs": args.num_bot_envs,
        "device": args.device,
        "seed": args.seed,
        "env_summary": env_summary,
    }
