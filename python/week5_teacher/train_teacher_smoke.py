#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import logging
import random
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from run_teacher_rollout import (
    RolloutError,
    SeedBundle,
    build_environment,
    compare_spaces,
    import_runtime_modules,
    seed_process,
)


PROFILE_PRESETS: Dict[str, Dict[str, Any]] = {
    "smoke": {
        "total_timesteps": 8192,
        "num_bot_envs": 4,
        "n_steps": 128,
        "batch_size": 64,
        "n_epochs": 4,
    },
    "throughput_tuned": {
        "total_timesteps": 100000,
        "num_bot_envs": 8,
        "n_steps": 1024,
        "batch_size": 2048,
        "n_epochs": 3,
    },
    "overnight": {
        "total_timesteps": 100000,
        "num_bot_envs": 8,
        "n_steps": 1024,
        "batch_size": 2048,
        "n_epochs": 3,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Week 5 minimal own-teacher training smoke. "
            "Produces first operational non-random checkpoint for rollout export."
        )
    )
    parser.add_argument("--env-id", default="MicrortsSelfPlayShapedReward-v1")
    parser.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--env-seed", type=int, default=None)
    parser.add_argument("--rollout-seed", type=int, default=None)
    parser.add_argument("--total-timesteps", type=int, default=None)
    parser.add_argument("--rollout-step-limit", type=int, default=2000)
    parser.add_argument("--num-bot-envs", type=int, default=None)
    parser.add_argument("--checkpoint-interval", type=int, default=0)
    parser.add_argument("--run-profile", choices=("smoke", "throughput_tuned", "overnight"), default="smoke")
    parser.add_argument("--device", default="cpu")

    parser.add_argument("--policy", default=None, choices=("MlpPolicy", "CnnPolicy"))
    parser.add_argument(
        "--policy-architecture",
        choices=("cnn_preferred", "mlp_fallback"),
        default="cnn_preferred",
    )
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--n-steps", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--n-epochs", type=int, default=None)
    parser.add_argument("--gamma", type=float, default=0.99)

    parser.add_argument(
        "--backend-mode",
        choices=("allow_fallback", "preferred_only"),
        default="allow_fallback",
        help="preferred backend is used first; fallback only if allowed and preferred fails.",
    )
    parser.add_argument(
        "--force-legacy-backend",
        action="store_true",
        help="Force emergency legacy backend for diagnostics only.",
    )
    parser.add_argument(
        "--opponent-pool",
        default="coacAI,workerRushAI,lightRushAI,passiveAI",
        help="Comma-separated opponent names for legacy fallback backend pool.",
    )
    parser.add_argument(
        "--opponent-sampling",
        choices=("static", "per_reset", "per_episode"),
        default="per_episode",
    )
    parser.add_argument("--opponent-seed", type=int, default=None)

    parser.add_argument(
        "--action-mask-mode",
        choices=("auto", "mask_aware", "non_mask_aware"),
        default="auto",
    )
    parser.add_argument(
        "--timing-window-steps",
        type=int,
        default=4096,
        help="Profiling aggregation window in timesteps (<=0 means full-run aggregation).",
    )

    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Default: python/week5_teacher",
    )
    parser.add_argument(
        "--run-label",
        default="day5_teacher_smoke",
        help="ASCII label used in artifact names",
    )
    return parser.parse_args()


def sanitize_label(value: str) -> str:
    allowed = []
    for ch in value.strip():
        if ch.isalnum() or ch in ("-", "_"):
            allowed.append(ch)
    return "".join(allowed) or "day5_teacher_smoke"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_seed_bundle(args: argparse.Namespace) -> SeedBundle:
    env_seed = args.env_seed if args.env_seed is not None else args.seed + 1
    rollout_seed = args.rollout_seed if args.rollout_seed is not None else args.seed + 2
    return SeedBundle(random_seed=args.seed, env_seed=env_seed, rollout_seed=rollout_seed)


def configure_logger(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("train_teacher_smoke")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)


def wrap_legacy_vec_env_for_sb3(env: Any) -> Any:
    """
    Adapt legacy MicroRTS vector env to SB3 VecEnv interface.
    This unlocks parallel rollout collection with num_envs > 1.
    """
    return wrap_legacy_vec_env_for_sb3_with_options(
        env,
        enable_mask_hot_path=False,
        timing_state=None,
        opponent_sampling="static",
        opponent_seed=None,
    )


def wrap_legacy_vec_env_for_sb3_with_options(
    env: Any,
    *,
    enable_mask_hot_path: bool,
    timing_state: Optional[Dict[str, Any]],
    opponent_sampling: str,
    opponent_seed: Optional[int],
) -> Any:
    try:
        from stable_baselines3.common.vec_env import VecEnv
    except Exception as exc:
        raise RolloutError("Stable-Baselines3 VecEnv interface is unavailable.") from exc

    if isinstance(env, VecEnv):
        return env

    if not hasattr(env, "num_envs") or int(getattr(env, "num_envs", 0)) < 1:
        raise RolloutError("Legacy vec-env adapter requires num_envs >= 1.")

    def _to_gymnasium_space(space: Any) -> Any:
        try:
            from gymnasium import spaces as gymnasium_spaces
        except Exception as exc:
            raise RolloutError("Gymnasium is required to build SB3-compatible spaces.") from exc

        name = type(space).__name__
        if name == "Box":
            return gymnasium_spaces.Box(low=np.asarray(space.low), high=np.asarray(space.high), shape=space.shape, dtype=space.dtype)
        if name == "Discrete":
            return gymnasium_spaces.Discrete(int(space.n))
        if name == "MultiDiscrete":
            return gymnasium_spaces.MultiDiscrete(np.asarray(space.nvec, dtype=np.int64))
        if name == "MultiBinary":
            return gymnasium_spaces.MultiBinary(space.n)
        if name == "Tuple":
            return gymnasium_spaces.Tuple(tuple(_to_gymnasium_space(child) for child in space.spaces))
        if name == "Dict":
            return gymnasium_spaces.Dict({key: _to_gymnasium_space(child) for key, child in space.spaces.items()})
        raise RolloutError(f"Unsupported legacy space type for SB3 VecEnv adaptation: {name}")

    class _LegacyMicroRTSSB3VecEnv(VecEnv):
        def __init__(self, vec_env: Any) -> None:
            self._vec_env = vec_env
            num_envs = int(getattr(vec_env, "num_envs", 1))
            self.render_mode = None
            observation_space = _to_gymnasium_space(vec_env.observation_space)
            action_space = _to_gymnasium_space(vec_env.action_space)
            super().__init__(num_envs=num_envs, observation_space=observation_space, action_space=action_space)
            self._pending_actions: np.ndarray | None = None
            self.metadata = getattr(vec_env, "metadata", {})
            self._enable_mask_hot_path = bool(enable_mask_hot_path)
            self._timing_state = timing_state if isinstance(timing_state, dict) else {}
            self._timing_state.setdefault("env_step_seconds", 0.0)
            self._timing_state.setdefault("mask_seconds", 0.0)
            self._timing_state.setdefault("env_step_calls", 0)
            self._timing_state.setdefault("mask_calls", 0)

            self._opponent_sampling = opponent_sampling
            self._opponent_rng = random.Random(int(opponent_seed if opponent_seed is not None else 0) + 811)
            raw_state = getattr(self._vec_env, "_teacher_opponent_state", None)
            self._opponent_state = raw_state if isinstance(raw_state, dict) else None
            self._opponent_switch_counter: Counter = Counter()

        def _extract_mask(self) -> Any:
            candidate = None
            if hasattr(self._vec_env, "get_action_mask"):
                candidate = self._vec_env.get_action_mask()
            elif hasattr(self._vec_env, "action_masks"):
                maybe = getattr(self._vec_env, "action_masks")
                candidate = maybe() if callable(maybe) else maybe
            if candidate is None:
                raise RolloutError("Mask-aware training was requested but the environment does not expose action masks.")
            return np.asarray(candidate)

        def _sample_opponent_pair(self) -> Optional[Tuple[str, Any]]:
            if not isinstance(self._opponent_state, dict):
                return None
            names = list(self._opponent_state.get("pool_names", []))
            funcs = list(self._opponent_state.get("pool_functions", []))
            if not names or not funcs or len(names) != len(funcs):
                return None
            index = self._opponent_rng.randrange(len(names))
            return names[index], funcs[index]

        def _resample_opponents(self, slot_indices: List[int], reason: str) -> None:
            if self._opponent_sampling == "static":
                return
            if not hasattr(self._vec_env, "ai2s"):
                return
            slot_names = list(self._opponent_state.get("current_slot_names", [])) if isinstance(self._opponent_state, dict) else []
            ai_slots = getattr(self._vec_env, "ai2s")
            if not isinstance(ai_slots, list):
                return

            for slot in slot_indices:
                sampled = self._sample_opponent_pair()
                if sampled is None:
                    return
                opponent_name, opponent_fn = sampled
                if 0 <= slot < len(ai_slots):
                    ai_slots[slot] = opponent_fn
                    if slot < len(slot_names):
                        slot_names[slot] = opponent_name
                    else:
                        while len(slot_names) <= slot:
                            slot_names.append("unknown")
                        slot_names[slot] = opponent_name
                    self._opponent_switch_counter[f"{reason}:{opponent_name}"] += 1

            if isinstance(self._opponent_state, dict):
                self._opponent_state["current_slot_names"] = slot_names

        def action_masks(self) -> Any:
            started = time.perf_counter()
            mask = self._extract_mask()
            elapsed = max(time.perf_counter() - started, 0.0)
            self._timing_state["mask_seconds"] = float(self._timing_state.get("mask_seconds", 0.0)) + elapsed
            self._timing_state["mask_calls"] = int(self._timing_state.get("mask_calls", 0)) + 1
            return mask

        def reset(self) -> np.ndarray:
            if self._opponent_sampling == "per_reset":
                self._resample_opponents(list(range(self.num_envs)), reason="reset")
            obs = self._vec_env.reset()
            self.reset_infos = [{} for _ in range(self.num_envs)]
            return np.asarray(obs)

        def step_async(self, actions: np.ndarray) -> None:
            if self._enable_mask_hot_path:
                _ = self.action_masks()
            self._pending_actions = np.asarray(actions)

        def step_wait(self):
            if self._pending_actions is None:
                raise RolloutError("step_wait called before step_async in VecEnv adapter.")
            started = time.perf_counter()
            next_obs, rewards, dones, infos = self._vec_env.step(self._pending_actions)
            elapsed = max(time.perf_counter() - started, 0.0)
            self._timing_state["env_step_seconds"] = float(self._timing_state.get("env_step_seconds", 0.0)) + elapsed
            self._timing_state["env_step_calls"] = int(self._timing_state.get("env_step_calls", 0)) + 1
            self._pending_actions = None

            obs_array = np.asarray(next_obs)
            reward_array = np.asarray(rewards, dtype=np.float32).reshape(self.num_envs)
            done_array = np.asarray(dones, dtype=bool).reshape(self.num_envs)

            if isinstance(infos, list):
                info_list = infos
            elif isinstance(infos, dict):
                info_list = [dict(infos) for _ in range(self.num_envs)]
            else:
                info_list = [{} for _ in range(self.num_envs)]

            # Keep per-env terminal observations for compatibility with SB3 wrappers.
            for index, is_done in enumerate(done_array):
                if is_done and index < len(info_list):
                    if not isinstance(info_list[index], dict):
                        info_list[index] = {}
                    info_list[index]["terminal_observation"] = obs_array[index]

            if self._opponent_sampling == "per_episode":
                done_indices = [index for index, is_done in enumerate(done_array) if bool(is_done)]
                if done_indices:
                    self._resample_opponents(done_indices, reason="episode")

            return obs_array, reward_array, done_array, info_list

        def close(self) -> None:
            if hasattr(self._vec_env, "close"):
                self._vec_env.close()

        def get_attr(self, attr_name: str, indices=None):
            del indices
            if attr_name == "action_masks":
                return [self.action_masks for _ in range(self.num_envs)]
            value = getattr(self._vec_env, attr_name)
            return [value for _ in range(self.num_envs)]

        def set_attr(self, attr_name: str, value: Any, indices=None) -> None:
            del indices
            setattr(self._vec_env, attr_name, value)

        def env_method(self, method_name: str, *method_args, indices=None, **method_kwargs):
            del indices
            if method_name == "action_masks":
                mask = self.action_masks()
                if isinstance(mask, np.ndarray) and mask.ndim > 0 and mask.shape[0] == self.num_envs:
                    return [mask[idx] for idx in range(self.num_envs)]
                return [mask for _ in range(self.num_envs)]
            method = getattr(self._vec_env, method_name)
            result = method(*method_args, **method_kwargs)
            return [result for _ in range(self.num_envs)]

        def env_is_wrapped(self, wrapper_class, indices=None):
            del wrapper_class, indices
            return [False for _ in range(self.num_envs)]

        def export_runtime_diagnostics(self) -> Dict[str, Any]:
            return {
                "opponent_switch_counts": dict(self._opponent_switch_counter),
                "opponent_sampling_mode": self._opponent_sampling,
                "opponent_current_slots": list(self._opponent_state.get("current_slot_names", [])) if isinstance(self._opponent_state, dict) else [],
            }

    return _LegacyMicroRTSSB3VecEnv(env)


def apply_profile_defaults(args: argparse.Namespace) -> Dict[str, Any]:
    profile_name = str(args.run_profile)
    preset = PROFILE_PRESETS[profile_name]

    if args.total_timesteps is None:
        args.total_timesteps = int(preset["total_timesteps"])
    if args.num_bot_envs is None:
        args.num_bot_envs = int(preset["num_bot_envs"])
    if args.n_steps is None:
        args.n_steps = int(preset["n_steps"])
    if args.batch_size is None:
        args.batch_size = int(preset["batch_size"])
    if args.n_epochs is None:
        args.n_epochs = int(preset["n_epochs"])

    return {
        "run_profile": profile_name,
        "preset": preset,
        "effective": {
            "total_timesteps": int(args.total_timesteps),
            "num_bot_envs": int(args.num_bot_envs),
            "n_steps": int(args.n_steps),
            "batch_size": int(args.batch_size),
            "n_epochs": int(args.n_epochs),
        },
    }


def build_profile_diagnostic_note(phase_shares: Dict[str, float]) -> str:
    env_share = float(phase_shares.get("env_time_share", 0.0))
    update_share = float(phase_shares.get("update_backward_share", 0.0))
    policy_share = float(phase_shares.get("policy_forward_estimated_share", 0.0))

    if env_share >= 0.60:
        return "env-bound"
    if update_share >= 0.60 or (update_share + policy_share) >= 0.70:
        return "model-bound"
    return "mixed"


def build_policy_configuration(
    args: argparse.Namespace,
    modules: Dict[str, Optional[Any]],
    env_for_training: Any,
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    requested = str(args.policy_architecture)
    policy_override = args.policy

    if policy_override is not None:
        policy_class = str(policy_override)
        architecture_effective = "legacy_policy_override"
        note = "Policy class was forced by --policy for compatibility."
        return policy_class, {}, {
            "requested": requested,
            "effective": architecture_effective,
            "policy_class": policy_class,
            "notes": note,
        }

    if requested == "mlp_fallback":
        return "MlpPolicy", {}, {
            "requested": requested,
            "effective": "mlp_fallback",
            "policy_class": "MlpPolicy",
            "notes": "Smoke/fallback policy path.",
        }

    sb3_module = modules.get("stable_baselines3")
    torch_module = modules.get("torch")
    if sb3_module is None or torch_module is None:
        raise RolloutError("CNN policy path requires stable_baselines3 and torch.")

    observation_space = getattr(env_for_training, "observation_space", None)
    if observation_space is None or not hasattr(observation_space, "shape"):
        raise RolloutError("CNN policy path requires an observation space with static shape.")

    observation_shape = tuple(int(x) for x in observation_space.shape)
    if len(observation_shape) != 3:
        raise RolloutError(
            f"CNN policy path expects 3D observation tensors; got shape={observation_shape}."
        )

    try:
        from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
        import torch as th
        import torch.nn as nn
    except Exception as exc:
        raise RolloutError("Failed to import SB3/PyTorch CNN components.") from exc

    class MicroRTSApproxImpalaExtractor(BaseFeaturesExtractor):
        def __init__(self, obs_space: Any, features_dim: int = 512) -> None:
            self._channel_last = False
            shape = tuple(int(v) for v in obs_space.shape)
            if len(shape) != 3:
                raise RolloutError(f"Custom CNN extractor expects 3D shape, got {shape}.")

            if shape[-1] <= 64:
                height, width, channels = shape
                self._channel_last = True
            else:
                channels, height, width = shape

            super().__init__(obs_space, features_dim)
            self.conv = nn.Sequential(
                nn.Conv2d(channels, 32, kernel_size=3, stride=1, padding=1),
                nn.ReLU(),
                nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1),
                nn.ReLU(),
                nn.Conv2d(64, 128, kernel_size=3, stride=2, padding=1),
                nn.ReLU(),
            )

            with th.no_grad():
                sample = th.zeros((1, channels, height, width), dtype=th.float32)
                n_flatten = int(self.conv(sample).reshape(1, -1).shape[1])

            self.project = nn.Sequential(
                nn.Linear(n_flatten, features_dim),
                nn.ReLU(),
            )

        def forward(self, observations: th.Tensor) -> th.Tensor:
            x = observations.float()
            if self._channel_last:
                x = x.permute(0, 3, 1, 2)
            x = self.conv(x)
            x = x.reshape(x.shape[0], -1)
            return self.project(x)

    return "CnnPolicy", {
        "features_extractor_class": MicroRTSApproxImpalaExtractor,
        "features_extractor_kwargs": {"features_dim": 512},
    }, {
        "requested": requested,
        "effective": "cnn_preferred",
        "policy_class": "CnnPolicy",
        "notes": "Custom CNN extractor is IMPALA-like approximation, not paper-identical IMPALA-CNN.",
    }


def select_algorithm_backend(
    args: argparse.Namespace,
    modules: Dict[str, Optional[Any]],
) -> Tuple[Any, Dict[str, Any]]:
    sb3_module = modules.get("stable_baselines3")
    if sb3_module is None:
        raise RolloutError("Stable-Baselines3 is not installed in the active environment.")

    requested_mode = str(args.action_mask_mode)
    if requested_mode == "non_mask_aware":
        return sb3_module.PPO, {
            "requested": requested_mode,
            "effective": "non_mask_aware",
            "algorithm_backend": "stable_baselines3.PPO",
            "fallback_reason": None,
        }

    try:
        sb3_contrib = importlib.import_module("sb3_contrib")
        maskable_class = getattr(sb3_contrib, "MaskablePPO", None)
        if maskable_class is None:
            raise ImportError("MaskablePPO is unavailable in sb3_contrib")
        return maskable_class, {
            "requested": requested_mode,
            "effective": "mask_aware",
            "algorithm_backend": "sb3_contrib.MaskablePPO",
            "fallback_reason": None,
        }
    except Exception as exc:
        if requested_mode == "mask_aware":
            raise RolloutError("Mask-aware mode requested but sb3_contrib MaskablePPO is unavailable.") from exc
        return sb3_module.PPO, {
            "requested": requested_mode,
            "effective": "non_mask_aware",
            "algorithm_backend": "stable_baselines3.PPO",
            "fallback_reason": f"auto_fallback:{type(exc).__name__}",
        }


class PhaseTimingCallback:
    def __init__(self, base_callback_cls: Any) -> None:
        class _TimingCallback(base_callback_cls):
            def __init__(self) -> None:
                super().__init__(verbose=0)
                self._rollout_started_at: Optional[float] = None
                self._rollout_finished_at: Optional[float] = None
                self.rollout_events: List[Tuple[int, float]] = []
                self.update_events: List[Tuple[int, float]] = []

            def _on_training_start(self) -> None:
                self._rollout_started_at = None
                self._rollout_finished_at = None

            def _on_rollout_start(self) -> None:
                now = time.perf_counter()
                if self._rollout_finished_at is not None:
                    self.update_events.append((int(self.num_timesteps), max(now - self._rollout_finished_at, 0.0)))
                self._rollout_started_at = now

            def _on_rollout_end(self) -> None:
                now = time.perf_counter()
                if self._rollout_started_at is not None:
                    self.rollout_events.append((int(self.num_timesteps), max(now - self._rollout_started_at, 0.0)))
                self._rollout_finished_at = now

            def _on_step(self) -> bool:
                return True

        self.callback = _TimingCallback()


def _sum_windowed_events(events: List[Tuple[int, float]], current_steps: int, window_steps: int) -> float:
    if window_steps <= 0:
        return float(sum(duration for _steps, duration in events))
    threshold = max(current_steps - window_steps, 0)
    return float(sum(duration for step, duration in events if step >= threshold))


def build_profiling_summary(
    timing_state: Dict[str, Any],
    timing_callback: Any,
    current_steps: int,
    window_steps: int,
) -> Dict[str, Any]:
    rollout_seconds = _sum_windowed_events(timing_callback.rollout_events, current_steps, window_steps)
    update_seconds = _sum_windowed_events(timing_callback.update_events, current_steps, window_steps)
    env_seconds = float(timing_state.get("env_step_seconds", 0.0))
    mask_seconds = float(timing_state.get("mask_seconds", 0.0))
    policy_forward_estimated = max(rollout_seconds - env_seconds - mask_seconds, 0.0)

    accounted = env_seconds + mask_seconds + policy_forward_estimated + update_seconds
    if accounted <= 0:
        shares = {
            "env_time_share": 0.0,
            "mask_overhead_share": 0.0,
            "policy_forward_estimated_share": 0.0,
            "update_backward_share": 0.0,
        }
    else:
        shares = {
            "env_time_share": env_seconds / accounted,
            "mask_overhead_share": mask_seconds / accounted,
            "policy_forward_estimated_share": policy_forward_estimated / accounted,
            "update_backward_share": update_seconds / accounted,
        }

    return {
        "timing_window_steps": int(window_steps),
        "rollout_seconds": rollout_seconds,
        "update_backward_seconds": update_seconds,
        "env_step_seconds": env_seconds,
        "mask_seconds": mask_seconds,
        "policy_forward_estimated_seconds": policy_forward_estimated,
        "env_step_calls": int(timing_state.get("env_step_calls", 0)),
        "mask_calls": int(timing_state.get("mask_calls", 0)),
        "shares": shares,
        "diagnostic_note": build_profile_diagnostic_note(shares),
        "estimation_notes": [
            "policy_forward_estimated_seconds is rollout minus env_step minus mask capture time.",
            "This is lightweight instrumentation, not a full profiler trace.",
        ],
    }


def train_smoke(args: argparse.Namespace) -> Tuple[Path, Path]:
    profile_summary = apply_profile_defaults(args)

    output_root = args.output_root.resolve()
    models_dir = output_root / "teacher_models"
    logs_dir = output_root / "teacher_logs"
    models_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    run_id = f"{sanitize_label(args.run_label)}_{utc_timestamp()}"
    run_model_dir = models_dir / run_id
    checkpoint_dir = run_model_dir / "checkpoints"
    run_model_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    log_path = logs_dir / f"{run_id}.log"
    logger = configure_logger(log_path)

    modules, versions = import_runtime_modules()

    seed_bundle = build_seed_bundle(args)
    seed_process(seed_bundle, modules)

    algorithm_class, mask_mode_summary = select_algorithm_backend(args, modules)

    timing_state: Dict[str, Any] = {
        "env_step_seconds": 0.0,
        "mask_seconds": 0.0,
        "env_step_calls": 0,
        "mask_calls": 0,
    }

    env_args = argparse.Namespace(
        env_id=args.env_id,
        map_path=args.map_path,
        rollout_step_limit=args.rollout_step_limit,
        num_bot_envs=args.num_bot_envs,
        backend_mode=args.backend_mode,
        force_legacy_backend=args.force_legacy_backend,
        opponent_pool=args.opponent_pool,
        opponent_sampling=args.opponent_sampling,
        opponent_seed=args.opponent_seed,
        seed=args.seed,
    )

    env, initial_observation, reset_info, env_summary = build_environment(
        args=env_args,
        seed_bundle=seed_bundle,
        modules=modules,
        logger=logger,
    )

    env_for_training = wrap_legacy_vec_env_for_sb3_with_options(
        env,
        enable_mask_hot_path=False,
        timing_state=timing_state,
        opponent_sampling=args.opponent_sampling,
        opponent_seed=args.opponent_seed,
    )

    policy_class, policy_kwargs, policy_summary = build_policy_configuration(args, modules, env_for_training)

    sb3_module = modules.get("stable_baselines3")
    if sb3_module is None:
        raise RolloutError("Stable-Baselines3 is not installed in the active environment.")

    logger.info("Initial observation shape: %s", getattr(initial_observation, "shape", type(initial_observation).__name__))
    logger.info("Reset info keys: %s", sorted(reset_info.keys()))
    logger.info("Training env count: %d", int(getattr(env_for_training, "num_envs", 1)))
    logger.info(
        "Backend routing: role=%s backend=%s mode=%s forced_legacy=%s",
        env_summary.get("backend_role"),
        env_summary.get("env_backend"),
        args.backend_mode,
        args.force_legacy_backend,
    )
    logger.info("Mask regime: requested=%s effective=%s", mask_mode_summary["requested"], mask_mode_summary["effective"])
    logger.info("Policy architecture: requested=%s effective=%s", policy_summary["requested"], policy_summary["effective"])
    logger.info("Opponent regime: %s", json.dumps(env_summary.get("opponent_regime", {}), ensure_ascii=True))

    model = algorithm_class(
        policy=policy_class,
        env=env_for_training,
        learning_rate=args.learning_rate,
        n_steps=args.n_steps,
        batch_size=args.batch_size,
        n_epochs=args.n_epochs,
        gamma=args.gamma,
        seed=seed_bundle.rollout_seed,
        device=args.device,
        policy_kwargs=policy_kwargs,
        verbose=1,
    )

    logger.info(
        "Starting teacher training: total_timesteps=%d, policy=%s, seed=%d, profile=%s",
        args.total_timesteps,
        policy_class,
        seed_bundle.rollout_seed,
        args.run_profile,
    )

    class PeriodicCheckpointCallback(sb3_module.common.callbacks.BaseCallback):
        def __init__(self, interval_timesteps: int, target_dir: Path, base_name: str, run_logger: logging.Logger):
            super().__init__(verbose=0)
            self.interval_timesteps = max(int(interval_timesteps), 0)
            self.target_dir = target_dir
            self.base_name = base_name
            self.run_logger = run_logger
            self._last_saved_timestep = 0

        def _on_step(self) -> bool:
            if self.interval_timesteps <= 0:
                return True
            if (self.num_timesteps - self._last_saved_timestep) < self.interval_timesteps:
                return True

            save_base = self.target_dir / f"{self.base_name}_step_{self.num_timesteps:09d}"
            self.model.save(str(save_base))
            checkpoint_path = save_base.with_suffix(".zip")
            self._last_saved_timestep = self.num_timesteps

            latest_interval_pointer = self.target_dir / "LATEST_INTERVAL_CHECKPOINT.txt"
            latest_interval_pointer.write_text(str(checkpoint_path), encoding="utf-8")
            self.run_logger.info("Periodic checkpoint saved at timestep=%d: %s", self.num_timesteps, checkpoint_path)
            return True

    callback_list: List[Any] = []
    if args.checkpoint_interval > 0:
        callback_list.append(
            PeriodicCheckpointCallback(
            interval_timesteps=args.checkpoint_interval,
            target_dir=checkpoint_dir,
            base_name="teacher_sb3_ppo",
            run_logger=logger,
            )
        )

    timing_wrapper = PhaseTimingCallback(sb3_module.common.callbacks.BaseCallback)
    callback_list.append(timing_wrapper.callback)

    callback: Optional[Any]
    if callback_list:
        if len(callback_list) == 1:
            callback = callback_list[0]
        else:
            callback = sb3_module.common.callbacks.CallbackList(callback_list)
    else:
        callback = None

    final_status = "success"
    failure_reason: Optional[str] = None

    try:
        model.learn(total_timesteps=args.total_timesteps, progress_bar=False, callback=callback)
    except KeyboardInterrupt:
        final_status = "interrupted"
        failure_reason = "keyboard_interrupt"
        logger.warning("Training interrupted by user signal; saving latest model snapshot.")
    except Exception as exc:
        final_status = "failed"
        failure_reason = f"{type(exc).__name__}: {exc}"
        logger.exception("Training failed before completion.")

    completed_total_timesteps = int(getattr(model, "num_timesteps", 0))

    if final_status == "success":
        checkpoint_base = run_model_dir / "teacher_sb3_ppo"
    else:
        checkpoint_base = run_model_dir / f"teacher_sb3_ppo_{final_status}"

    model.save(str(checkpoint_base))
    checkpoint_path = checkpoint_base.with_suffix(".zip")
    logger.info("Checkpoint saved: %s", checkpoint_path)

    if final_status == "success":
        loaded_model = algorithm_class.load(str(checkpoint_path), device=args.device, print_system_info=False)
        obs_issues = compare_spaces(loaded_model.observation_space, env.observation_space, "observation_space")
        act_issues = compare_spaces(loaded_model.action_space, env.action_space, "action_space")
        issues = obs_issues + act_issues
        if issues:
            raise RolloutError("Checkpoint load mismatch after training: " + " | ".join(issues))
        logger.info("Checkpoint load validation passed (no shape/action-space mismatches).")
    else:
        logger.warning("Skipping strict checkpoint load validation due to final_status=%s", final_status)

    checkpoint_hash = sha256_file(checkpoint_path)
    profiling_summary = build_profiling_summary(
        timing_state=timing_state,
        timing_callback=timing_wrapper.callback,
        current_steps=completed_total_timesteps,
        window_steps=int(args.timing_window_steps),
    )

    adapter_diagnostics = {}
    if hasattr(env_for_training, "export_runtime_diagnostics"):
        try:
            adapter_diagnostics = env_for_training.export_runtime_diagnostics()
        except Exception:
            adapter_diagnostics = {}

    metadata = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": final_status,
        "final_status": final_status,
        "run_profile": args.run_profile,
        "run_profile_effective": profile_summary,
        "purpose": "Week 5 minimal own-teacher smoke checkpoint",
        "training_backend": mask_mode_summary["algorithm_backend"],
        "backend_routing": {
            "preferred_backend": "gym.make",
            "fallback_backend": "gym_microrts.envs.vec_env.MicroRTSGridModeVecEnv",
            "backend_mode": args.backend_mode,
            "force_legacy_backend": bool(args.force_legacy_backend),
            "actual_backend": env_summary.get("env_backend"),
            "backend_role": env_summary.get("backend_role"),
            "fallback_trigger_reason": env_summary.get("backend_selection", {}).get("fallback_trigger_reason"),
        },
        "algorithm": "PPO",
        "policy_architecture": policy_summary,
        "mask_regime": mask_mode_summary,
        "planned_total_timesteps": args.total_timesteps,
        "completed_total_timesteps": completed_total_timesteps,
        "checkpoint_interval": args.checkpoint_interval,
        "hyperparameters": {
            "learning_rate": args.learning_rate,
            "n_steps": args.n_steps,
            "batch_size": args.batch_size,
            "n_epochs": args.n_epochs,
            "gamma": args.gamma,
            "device": args.device,
            "num_bot_envs": args.num_bot_envs,
        },
        "opponent_regime": {
            "configured_pool": [token.strip() for token in str(args.opponent_pool).split(",") if token.strip()],
            "configured_sampling": args.opponent_sampling,
            "runtime": env_summary.get("opponent_regime", {}),
            "adapter_diagnostics": adapter_diagnostics,
        },
        "profiling": profiling_summary,
        "seed_bundle": asdict(seed_bundle),
        "runtime_versions": asdict(versions),
        "canonical_training_assumptions": {
            "python_version": versions.python_version,
            "microrts_version": versions.microrts_version,
            "env_id": args.env_id,
            "map_path": args.map_path,
            "compatibility_scope": "hardened-week5, still not final paper reproduction",
        },
        "env_summary": env_summary,
        "checkpoint": {
            "path": str(checkpoint_path),
            "sha256": checkpoint_hash,
            "format": "stable-baselines3 zip",
        },
        "artifacts": {
            "train_log": str(log_path),
            "checkpoint_dir": str(checkpoint_dir),
            "latest_interval_pointer": str(checkpoint_dir / "LATEST_INTERVAL_CHECKPOINT.txt"),
        },
        "limitations": [
            "Custom CNN extractor is IMPALA-like approximation, not paper-identical IMPALA-CNN.",
            "Opponent pool control is explicit on legacy fallback backend; preferred backend may remain backend-managed.",
            "Phase timings are lightweight estimates for diagnosis, not instruction-level profiling.",
        ],
    }
    if failure_reason is not None:
        metadata["failure_reason"] = failure_reason

    metadata_path = logs_dir / f"{run_id}.training.json"
    write_json(metadata_path, metadata)

    # Convenience pointer for downstream scripts.
    latest_pointer = output_root / "teacher_models" / "LATEST_DAY5_TEACHER_CHECKPOINT.txt"
    latest_pointer.write_text(str(checkpoint_path), encoding="utf-8")

    logger.info("Training metadata written: %s", metadata_path)
    logger.info("Latest checkpoint pointer updated: %s", latest_pointer)

    if final_status == "failed":
        raise RolloutError(f"Training failed; see metadata/log for details. reason={failure_reason}")

    try:
        if hasattr(env, "close"):
            env.close()
    except Exception:
        pass

    return checkpoint_path, metadata_path


def main() -> None:
    args = parse_args()
    checkpoint_path, metadata_path = train_smoke(args)
    print("Teacher training completed successfully.")
    print(f"Checkpoint: {checkpoint_path}")
    print(f"Metadata:   {metadata_path}")


if __name__ == "__main__":
    main()
