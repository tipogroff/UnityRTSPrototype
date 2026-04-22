#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import logging
import platform
import random
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from teacher_export import (
    RolloutError,
    compute_mean,
    compute_std,
    sanitize_label,
    canonical_json,
    normalize_json_payload,
    to_numpy_array,
    ensure_finite_array,
    should_write_jsonl,
    extract_action_surface_bucket,
    try_read_action_mask,
    new_episode_record,
    validate_episode_record,
    write_episode_npz,
    write_episode_jsonl,
    validate_saved_episode_npz,
    sha256_text,
)


CANONICAL_ENVIRONMENT_TARGET = (
    "MicroRTS-Py v0.6.1-compatible 27-channel observation surface "
    "(no extra terrain/walls channel)"
)


@dataclass(frozen=True)
class SeedBundle:
    random_seed: int
    env_seed: int
    rollout_seed: int


@dataclass(frozen=True)
class RuntimeVersions:
    python_version: str
    torch_version: Optional[str]
    numpy_version: Optional[str]
    stable_baselines3_version: Optional[str]
    gym_api_name: Optional[str]
    gym_api_version: Optional[str]
    microrts_module_name: Optional[str]
    microrts_version: Optional[str]


@dataclass(frozen=True)
class OutputPaths:
    root: Path
    teacher_models: Path
    teacher_rollouts: Path
    teacher_logs: Path
    teacher_exports: Path


class PolicySource:
    source_id: str
    is_canonical: bool

    def predict(self, observation: Any) -> Any:
        raise NotImplementedError

    def describe(self) -> Dict[str, Any]:
        raise NotImplementedError


class RandomPolicySource(PolicySource):
    def __init__(self, action_space: Any, rollout_seed: int) -> None:
        self.source_id = "random-policy-fallback"
        self.is_canonical = False
        self._action_space = action_space
        if hasattr(self._action_space, "seed"):
            self._action_space.seed(rollout_seed)

    def predict(self, observation: Any) -> Any:
        del observation
        return self._action_space.sample()

    def describe(self) -> Dict[str, Any]:
        return {
            "policy_source_id": self.source_id,
            "policy_kind": "random_fallback",
            "is_canonical": self.is_canonical,
            "warning": "Non-canonical smoke fallback. Not valid for teacher dataset collection.",
        }


class StableBaselinesPolicySource(PolicySource):
    def __init__(self, model: Any, algorithm_name: str, checkpoint_path: Path, checkpoint_hash: str) -> None:
        self._model = model
        self.source_id = f"sb3:{algorithm_name}:{checkpoint_path.name}"
        self.is_canonical = True
        self._algorithm_name = algorithm_name
        self._checkpoint_path = checkpoint_path
        self._checkpoint_hash = checkpoint_hash

    def predict(self, observation: Any) -> Any:
        action, _state = self._model.predict(observation, deterministic=True)
        return action

    def describe(self) -> Dict[str, Any]:
        return {
            "policy_source_id": self.source_id,
            "policy_kind": "stable_baselines3",
            "algorithm": self._algorithm_name,
            "checkpoint_path": str(self._checkpoint_path),
            "checkpoint_hash": self._checkpoint_hash,
            "is_canonical": self.is_canonical,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Week 5 Day 3: raw teacher rollout exporter with per-episode dataset artifacts.",
    )
    parser.add_argument(
        "--policy-path",
        type=Path,
        default=None,
        help="Path to a canonical teacher checkpoint. Current loader scope is Stable-Baselines3 checkpoints only.",
    )
    parser.add_argument(
        "--policy-algorithm",
        choices=("ppo", "a2c", "dqn"),
        default="ppo",
        help="Stable-Baselines3 algorithm class used to load --policy-path.",
    )
    parser.add_argument(
        "--checkpoint-env-version",
        default=None,
        help="Required when --policy-path is used. Prevents mixing legacy checkpoints with a different MicroRTS package version.",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=1,
        help="Number of episodes to roll out and export.",
    )
    parser.add_argument(
        "--batch-mode",
        choices=("debug", "training"),
        default="debug",
        help="Batch profile label used in metadata and artifact naming.",
    )
    parser.add_argument(
        "--batch-label",
        default="raw_teacher",
        help="Free-form label appended to artifact names (ASCII preferred).",
    )
    parser.add_argument(
        "--env-id",
        default="MicrortsSelfPlayShapedReward-v1",
        help="Gym/Gymnasium environment id. Override if your MicroRTS fork registers a different id.",
    )
    parser.add_argument(
        "--map-path",
        default="maps/24x24/basesWorkers24x24.xml",
        help="Candidate map path closest to Unity MVP_24x24_Symmetric. This is an approximation unless verified separately.",
    )
    parser.add_argument("--seed", type=int, default=7, help="Base random seed.")
    parser.add_argument(
        "--env-seed",
        type=int,
        default=None,
        help="Optional explicit environment seed. Defaults to seed + 1.",
    )
    parser.add_argument(
        "--rollout-seed",
        type=int,
        default=None,
        help="Optional explicit rollout/policy seed. Defaults to seed + 2.",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Torch / Stable-Baselines3 device string. The current rollout/export path keeps cpu as the safe default.",
    )
    parser.add_argument(
        "--allow-random-policy-smoke-fallback",
        action="store_true",
        help="Allow a non-canonical random policy only when --policy-path is omitted.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Root output directory. Defaults to the script directory.",
    )
    parser.add_argument(
        "--rollout-step-limit",
        type=int,
        default=5000,
        help="Hard cap per episode. Stops rollout if terminal is not reached in time.",
    )
    parser.add_argument(
        "--write-jsonl",
        choices=("debug", "always", "never"),
        default="debug",
        help="Controls per-step debug .jsonl export: debug=only in debug batch mode, always, or never.",
    )
    parser.add_argument(
        "--export-prefix",
        default="teacher_raw",
        help="Artifact filename prefix for .npz/.jsonl/.summary.json outputs.",
    )
    return parser.parse_args()


def setup_output_paths(root: Path) -> OutputPaths:
    root.mkdir(parents=True, exist_ok=True)
    teacher_models = root / "teacher_models"
    teacher_rollouts = root / "teacher_rollouts"
    teacher_logs = root / "teacher_logs"
    teacher_exports = root / "teacher_exports"
    for path in (teacher_models, teacher_rollouts, teacher_logs, teacher_exports):
        path.mkdir(parents=True, exist_ok=True)
    return OutputPaths(
        root=root,
        teacher_models=teacher_models,
        teacher_rollouts=teacher_rollouts,
        teacher_logs=teacher_logs,
        teacher_exports=teacher_exports,
    )


def configure_logging(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("week5_teacher")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def resolve_seed_bundle(args: argparse.Namespace) -> SeedBundle:
    env_seed = args.env_seed if args.env_seed is not None else args.seed + 1
    rollout_seed = args.rollout_seed if args.rollout_seed is not None else args.seed + 2
    return SeedBundle(random_seed=args.seed, env_seed=env_seed, rollout_seed=rollout_seed)


def get_module_version(module_name: str) -> Optional[str]:
    try:
        return importlib.metadata.version(module_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def get_first_available_version(candidate_names: Sequence[str]) -> Optional[str]:
    for candidate in candidate_names:
        version = get_module_version(candidate)
        if version is not None:
            return version
    return None


def try_import(module_name: str) -> Optional[Any]:
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


def import_runtime_modules() -> Tuple[Dict[str, Optional[Any]], RuntimeVersions]:
    modules: Dict[str, Optional[Any]] = {
        "numpy": try_import("numpy"),
        "torch": try_import("torch"),
        "stable_baselines3": try_import("stable_baselines3"),
        "sb3_contrib": try_import("sb3_contrib"),
    }

    gym_api_name = None
    gym_module = try_import("gymnasium")
    if gym_module is not None:
        gym_api_name = "gymnasium"
    else:
        gym_module = try_import("gym")
        if gym_module is not None:
            gym_api_name = "gym"
    modules["gym_api"] = gym_module

    microrts_module_name = None
    microrts_module = try_import("microrts")
    if microrts_module is not None:
        microrts_module_name = "microrts"
    else:
        microrts_module = try_import("gym_microrts")
        if microrts_module is not None:
            microrts_module_name = "gym_microrts"
    modules["microrts"] = microrts_module

    versions = RuntimeVersions(
        python_version=platform.python_version(),
        torch_version=get_module_version("torch"),
        numpy_version=get_module_version("numpy"),
        stable_baselines3_version=get_module_version("stable-baselines3"),
        gym_api_name=gym_api_name,
        gym_api_version=get_module_version(gym_api_name) if gym_api_name else None,
        microrts_module_name=microrts_module_name,
        microrts_version=(
            get_first_available_version(("gym-microrts", "gym_microrts", "microrts"))
            if microrts_module_name
            else None
        ),
    )
    return modules, versions


def log_runtime_versions(logger: logging.Logger, versions: RuntimeVersions) -> None:
    logger.info("Python version: %s", versions.python_version)
    logger.info("Torch version: %s", versions.torch_version or "not installed")
    logger.info("NumPy version: %s", versions.numpy_version or "not installed")
    logger.info("Stable-Baselines3 version: %s", versions.stable_baselines3_version or "not installed")
    logger.info(
        "Gym API: %s (%s)",
        versions.gym_api_name or "not installed",
        versions.gym_api_version or "unknown",
    )
    logger.info(
        "MicroRTS package: %s (%s)",
        versions.microrts_module_name or "not installed",
        versions.microrts_version or "unknown",
    )


def seed_process(seed_bundle: SeedBundle, modules: Dict[str, Optional[Any]]) -> None:
    random.seed(seed_bundle.random_seed)

    numpy_module = modules.get("numpy")
    if numpy_module is not None:
        numpy_module.random.seed(seed_bundle.random_seed)

    torch_module = modules.get("torch")
    if torch_module is not None:
        torch_module.manual_seed(seed_bundle.random_seed)
        if hasattr(torch_module.cuda, "manual_seed_all"):
            torch_module.cuda.manual_seed_all(seed_bundle.random_seed)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summarize_space(space: Any) -> Dict[str, Any]:
    if space is None:
        return {"type": "unknown"}

    summary: Dict[str, Any] = {"type": type(space).__name__}

    if hasattr(space, "shape") and getattr(space, "shape") is not None:
        try:
            summary["shape"] = list(space.shape)
        except TypeError:
            summary["shape"] = str(space.shape)

    if hasattr(space, "dtype"):
        summary["dtype"] = str(space.dtype)

    if hasattr(space, "n"):
        summary["n"] = int(space.n)

    if hasattr(space, "nvec"):
        nvec = getattr(space, "nvec")
        try:
            summary["nvec"] = [int(value) for value in nvec.tolist()]
        except AttributeError:
            summary["nvec"] = [int(value) for value in nvec]

    if hasattr(space, "spaces"):
        nested = getattr(space, "spaces")
        if isinstance(nested, dict):
            summary["spaces"] = {key: summarize_space(value) for key, value in nested.items()}
        else:
            summary["spaces"] = [summarize_space(value) for value in nested]

    if hasattr(space, "low") and hasattr(space, "high"):
        summary["bounded"] = True

    return summary


def compare_spaces(reference_space: Any, candidate_space: Any, path: str) -> List[str]:
    issues: List[str] = []

    if type(reference_space) is not type(candidate_space):
        issues.append(f"{path}: type mismatch {type(reference_space).__name__} != {type(candidate_space).__name__}")
        return issues

    if hasattr(reference_space, "shape") and hasattr(candidate_space, "shape"):
        if tuple(reference_space.shape or ()) != tuple(candidate_space.shape or ()):
            issues.append(f"{path}: shape mismatch {reference_space.shape} != {candidate_space.shape}")

    if hasattr(reference_space, "n") and hasattr(candidate_space, "n"):
        if int(reference_space.n) != int(candidate_space.n):
            issues.append(f"{path}: discrete size mismatch {reference_space.n} != {candidate_space.n}")

    if hasattr(reference_space, "nvec") and hasattr(candidate_space, "nvec"):
        ref_nvec = [int(value) for value in reference_space.nvec]
        cand_nvec = [int(value) for value in candidate_space.nvec]
        if ref_nvec != cand_nvec:
            issues.append(f"{path}: nvec mismatch {ref_nvec} != {cand_nvec}")

    if hasattr(reference_space, "spaces") and hasattr(candidate_space, "spaces"):
        ref_nested = reference_space.spaces
        cand_nested = candidate_space.spaces
        if isinstance(ref_nested, dict) and isinstance(cand_nested, dict):
            if set(ref_nested.keys()) != set(cand_nested.keys()):
                issues.append(f"{path}: dict keys mismatch {sorted(ref_nested.keys())} != {sorted(cand_nested.keys())}")
            else:
                for key in sorted(ref_nested.keys()):
                    issues.extend(compare_spaces(ref_nested[key], cand_nested[key], f"{path}.{key}"))
        elif isinstance(ref_nested, Sequence) and isinstance(cand_nested, Sequence):
            if len(ref_nested) != len(cand_nested):
                issues.append(f"{path}: tuple length mismatch {len(ref_nested)} != {len(cand_nested)}")
            else:
                for index, (ref_child, cand_child) in enumerate(zip(ref_nested, cand_nested)):
                    issues.extend(compare_spaces(ref_child, cand_child, f"{path}[{index}]"))

    return issues


def infer_observation_shape(observation: Any, numpy_module: Optional[Any]) -> List[int]:
    if numpy_module is not None:
        return list(numpy_module.asarray(observation).shape)

    if isinstance(observation, (list, tuple)):
        shape: List[int] = []
        current = observation
        while isinstance(current, (list, tuple)):
            shape.append(len(current))
            if not current:
                break
            current = current[0]
        return shape

    return []


def coerce_scalar_reward(reward: Any, numpy_module: Optional[Any]) -> float:
    if isinstance(reward, (int, float)):
        return float(reward)

    if numpy_module is not None:
        array = numpy_module.asarray(reward)
        if array.size == 1:
            return float(array.reshape(-1)[0])

    raise RolloutError(
        f"Current rollout/export path expects a scalar reward, but env.step() returned unsupported reward payload: {type(reward).__name__}."
    )


def normalize_reset_output(reset_result: Any) -> Tuple[Any, Dict[str, Any]]:
    if isinstance(reset_result, tuple) and len(reset_result) == 2 and isinstance(reset_result[1], dict):
        return reset_result[0], reset_result[1]
    return reset_result, {}


def normalize_step_output(step_result: Any) -> Tuple[Any, float, bool, bool, Dict[str, Any]]:
    if not isinstance(step_result, tuple):
        raise RolloutError("env.step() returned a non-tuple result, which is incompatible with current rollout/export checks.")

    if len(step_result) == 5:
        observation, reward, terminated, truncated, info = step_result
        return (
            observation,
            reward,
            normalize_terminal_flag(terminated, "terminated"),
            normalize_terminal_flag(truncated, "truncated"),
            info if isinstance(info, dict) else {},
        )

    if len(step_result) == 4:
        observation, reward, done, info = step_result
        return (
            observation,
            reward,
            normalize_terminal_flag(done, "done"),
            False,
            info if isinstance(info, dict) else {},
        )

    raise RolloutError(f"env.step() returned {len(step_result)} items; expected 4 or 5.")


def reset_environment(env: Any, seed: int) -> Tuple[Any, Dict[str, Any]]:
    try:
        return normalize_reset_output(env.reset(seed=seed))
    except TypeError:
        if hasattr(env, "seed"):
            env.seed(seed)
        return normalize_reset_output(env.reset())


def normalize_terminal_flag(value: Any, field_name: str) -> bool:
    if isinstance(value, (bool, int)):
        return bool(value)

    try:
        import numpy as np  # local import keeps startup tolerant when numpy is unavailable

        array = np.asarray(value)
        if array.size == 1:
            return bool(array.reshape(-1)[0])
    except Exception:
        pass

    raise RolloutError(
        f"Unsupported terminal flag payload for '{field_name}': {type(value).__name__}. "
        "Expected bool/int or a scalar-like array."
    )


def build_scenario_comparison_note(map_path: Optional[str]) -> Dict[str, Any]:
    normalized = (map_path or "").replace("\\", "/").lower()
    known_matches: List[str] = []
    if "24x24" in normalized:
        known_matches.append("24x24 grid size")
    if "basesworkers" in normalized:
        known_matches.append("bases/workers map family")
    if known_matches:
        known_matches.append("symmetric intent")

    return {
        "scenario_match_scope": "approximation-only",
        "known_matches": known_matches,
        "known_unknowns": [
            "exact starting resources",
            "exact unit subset",
            "reward shaping behavior",
            "action semantics",
            "step timing",
        ],
        "parity_claim": False,
    }


def detect_observation_channels(observation_shape: Sequence[int]) -> Optional[int]:
    if not observation_shape:
        return None
    if len(observation_shape) >= 3:
        return int(observation_shape[-1])
    return None


def build_legacy_microrts_vec_env(args: argparse.Namespace, logger: logging.Logger) -> Any:
    try:
        from gym_microrts import microrts_ai
        from gym_microrts.envs.vec_env import MicroRTSGridModeVecEnv
    except Exception as exc:
        raise RolloutError(
            "Legacy gym_microrts vector env fallback is unavailable even though gym_microrts is installed."
        ) from exc

    if not args.map_path:
        raise RolloutError(
            "Legacy gym_microrts vector env fallback requires --map-path for explicit scenario control."
        )

    logger.warning(
        "Using legacy gym_microrts MicroRTSGridModeVecEnv fallback (no gym registry env-id available)."
    )
    return MicroRTSGridModeVecEnv(
        num_selfplay_envs=0,
        num_bot_envs=1,
        ai2s=[microrts_ai.passiveAI],
        map_paths=[args.map_path],
        max_steps=min(args.rollout_step_limit, 2000),
        autobuild=False,
    )


def derive_scenario_note(env_id: str, map_path: Optional[str]) -> str:
    if not map_path:
        return (
            f"Environment '{env_id}' is running with its default map/settings. "
            "This is not equivalent to Unity MVP_24x24_Symmetric unless verified separately."
        )

    normalized = map_path.replace("\\", "/").lower()
    if "24x24" in normalized and "basesworkers" in normalized:
        return (
            "Using a 24x24 bases/workers MicroRTS map as the closest available approximation to "
            "Unity MVP_24x24_Symmetric. This is still an approximation, not an exact parity claim."
        )

    return (
        f"Map '{map_path}' does not self-identify as a 24x24 bases/workers layout. "
        "Treat any Unity comparison as unresolved approximation until validated explicitly."
    )


def build_environment(
    args: argparse.Namespace,
    seed_bundle: SeedBundle,
    modules: Dict[str, Optional[Any]],
    logger: logging.Logger,
) -> Tuple[Any, Any, Dict[str, Any], Dict[str, Any]]:
    gym_module = modules.get("gym_api")
    if gym_module is None:
        raise RolloutError("Neither gymnasium nor gym is installed. The current rollout/export path cannot create an environment.")

    make_kwargs: Dict[str, Any] = {}
    if args.map_path:
        make_kwargs["map_path"] = args.map_path

    logger.info("Creating environment '%s' with kwargs=%s", args.env_id, make_kwargs or "{}")
    env_backend = "gym.make"
    try:
        env = gym_module.make(args.env_id, **make_kwargs)
    except TypeError as exc:
        if args.map_path:
            raise RolloutError(
                "Environment construction rejected 'map_path'. The current rollout/export path does not silently retry with a different signature, "
                "because that would hide scenario drift. Override --env-id / --map-path with a valid combination."
            ) from exc
        raise RolloutError(f"Failed to construct environment '{args.env_id}': {exc}") from exc
    except Exception as exc:
        if modules.get("microrts") is not None:
            env = build_legacy_microrts_vec_env(args, logger)
            env_backend = "gym_microrts.envs.vec_env.MicroRTSGridModeVecEnv"
        else:
            raise RolloutError(f"Failed to construct environment '{args.env_id}': {exc}") from exc

    if hasattr(env, "action_space") and hasattr(env.action_space, "seed"):
        env.action_space.seed(seed_bundle.rollout_seed)
    if hasattr(env, "observation_space") and hasattr(env.observation_space, "seed"):
        env.observation_space.seed(seed_bundle.env_seed)

    initial_observation, reset_info = reset_environment(env, seed_bundle.env_seed)
    observation_shape = infer_observation_shape(initial_observation, modules.get("numpy"))
    observation_channels = detect_observation_channels(observation_shape)
    observation_surface_verified = "27-channel compatible" if observation_channels == 27 else "channel-mismatch"
    env_summary = {
        "env_id": args.env_id,
        "env_backend": env_backend,
        "map_path": args.map_path,
        "scenario_note": derive_scenario_note(args.env_id, args.map_path),
        "scenario_comparison_note": build_scenario_comparison_note(args.map_path),
        "canonical_environment_target": CANONICAL_ENVIRONMENT_TARGET,
        "observation_surface_expected_channels": 27,
        "observation_surface_detected_channels": observation_channels,
        "observation_surface_verified": observation_surface_verified,
        "compatibility_scope": "shape-only",
        "semantic_parity_verified": False,
        "observation_space": summarize_space(getattr(env, "observation_space", None)),
        "action_space": summarize_space(getattr(env, "action_space", None)),
        "initial_observation_shape": observation_shape,
        "env_spec_id": getattr(getattr(env, "spec", None), "id", None),
    }

    logger.info("Scenario note: %s", env_summary["scenario_note"])
    logger.info("Initial observation shape: %s", observation_shape)
    logger.info("Observation surface verification: %s", observation_surface_verified)
    logger.info("Observation space summary: %s", json.dumps(env_summary["observation_space"], ensure_ascii=True))
    logger.info("Action space summary: %s", json.dumps(env_summary["action_space"], ensure_ascii=True))

    return env, initial_observation, reset_info, env_summary


def load_policy_source(
    args: argparse.Namespace,
    env: Any,
    seed_bundle: SeedBundle,
    versions: RuntimeVersions,
    modules: Dict[str, Optional[Any]],
    logger: logging.Logger,
) -> PolicySource:
    if args.policy_path is None:
        if args.allow_random_policy_smoke_fallback:
            logger.warning(
                "No --policy-path provided. Using explicit random fallback for smoke-check only; this is non-canonical."
            )
            return RandomPolicySource(env.action_space, seed_bundle.rollout_seed)
        raise RolloutError(
            "No policy source configured. Provide --policy-path or opt in with --allow-random-policy-smoke-fallback."
        )

    checkpoint_path = args.policy_path.resolve()
    if not checkpoint_path.is_file():
        raise RolloutError(f"Checkpoint not found: {checkpoint_path}")

    if args.checkpoint_env_version is None:
        raise RolloutError(
            "--checkpoint-env-version is required when --policy-path is used. The Day 3 raw export path refuses to load a checkpoint without an explicit environment-version contract."
        )

    if versions.microrts_version is None:
        raise RolloutError(
            "Cannot verify checkpoint compatibility because the active MicroRTS package version is unknown in this environment."
        )

    if args.checkpoint_env_version != versions.microrts_version:
        raise RolloutError(
            "Checkpoint env version mismatch: "
            f"checkpoint expects '{args.checkpoint_env_version}', runtime provides '{versions.microrts_version}'."
        )

    stable_baselines3_module = modules.get("stable_baselines3")
    sb3_contrib_module = modules.get("sb3_contrib")
    if stable_baselines3_module is None:
        raise RolloutError(
            "Stable-Baselines3 is not installed, but --policy-path was provided. Current loader scope is SB3-only checkpoint loading."
        )

    algorithm_candidates: List[Tuple[str, Any]]
    if args.policy_algorithm == "ppo":
        algorithm_candidates = [("stable_baselines3.PPO", stable_baselines3_module.PPO)]
        maskable_ppo = getattr(sb3_contrib_module, "MaskablePPO", None) if sb3_contrib_module is not None else None
        if maskable_ppo is not None:
            algorithm_candidates.append(("sb3_contrib.MaskablePPO", maskable_ppo))
    else:
        algorithm_lookup = {
            "a2c": ("stable_baselines3.A2C", stable_baselines3_module.A2C),
            "dqn": ("stable_baselines3.DQN", stable_baselines3_module.DQN),
        }
        algorithm_candidates = [algorithm_lookup[args.policy_algorithm]]
    checkpoint_hash = sha256_file(checkpoint_path)

    logger.info(
        "Loading teacher checkpoint '%s' with %s (sha256=%s)",
        checkpoint_path,
        args.policy_algorithm.upper(),
        checkpoint_hash,
    )
    model = None
    load_errors: List[str] = []
    loaded_via = None
    for loader_name, algorithm_class in algorithm_candidates:
        try:
            model = algorithm_class.load(str(checkpoint_path), device=args.device, print_system_info=False)
            loaded_via = loader_name
            break
        except Exception as exc:
            load_errors.append(f"{loader_name}: {exc}")

    if model is None:
        joined = " | ".join(load_errors)
        raise RolloutError(f"Failed to load checkpoint '{checkpoint_path}': {joined}")

    logger.info("Checkpoint loader selected: %s", loaded_via)

    if not hasattr(model, "observation_space") or not hasattr(model, "action_space"):
        raise RolloutError(
            "Loaded checkpoint does not expose observation_space/action_space. Current rollout/export path will not guess policy semantics."
        )

    observation_issues = compare_spaces(model.observation_space, env.observation_space, "observation_space")
    action_issues = compare_spaces(model.action_space, env.action_space, "action_space")
    issues = observation_issues + action_issues
    if issues:
        joined = " | ".join(issues)
        raise RolloutError(f"Checkpoint shape compatibility check failed: {joined}")

    logger.info("Checkpoint shape compatibility check passed against current env spaces.")
    return StableBaselinesPolicySource(
        model=model,
        algorithm_name=args.policy_algorithm,
        checkpoint_path=checkpoint_path,
        checkpoint_hash=checkpoint_hash,
    )



def run_rollouts(
    env: Any,
    policy: PolicySource,
    args: argparse.Namespace,
    seed_bundle: SeedBundle,
    modules: Dict[str, Optional[Any]],
    logger: logging.Logger,
    output_paths: OutputPaths,
    timestamp: str,
    runtime_versions: RuntimeVersions,
) -> Dict[str, Any]:
    numpy_module = modules.get("numpy")
    if numpy_module is None:
        raise RolloutError("NumPy is required for Day 3 exporter path, but it is not installed.")

    batch_label = sanitize_label(args.batch_label)
    batch_name = f"{args.export_prefix}_{args.batch_mode}_{batch_label}_{timestamp}"
    batch_dir = output_paths.teacher_rollouts / batch_name
    batch_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Export batch directory: %s", batch_dir)

    episode_lengths: List[int] = []
    episode_returns: List[float] = []
    terminal_counts = {"terminated": 0, "truncated": 0}
    step_rewards: List[float] = []
    action_surface_histogram: Counter = Counter()
    validation_errors: List[str] = []
    exported_episode_files: List[str] = []
    exported_jsonl_files: List[str] = []
    total_steps = 0
    mask_available_steps = 0
    mask_sources: Counter = Counter()
    mask_capture_errors: List[str] = []
    jsonl_enabled = should_write_jsonl(args.write_jsonl, args.batch_mode)

    batch_metadata = {
        "batch_name": batch_name,
        "batch_mode": args.batch_mode,
        "batch_label": batch_label,
        "export_prefix": args.export_prefix,
        "policy_source_id": policy.source_id,
        "env_id": args.env_id,
        "env_version": runtime_versions.microrts_version,
        "map_path": args.map_path,
        "seed_metadata": {
            "random_seed": seed_bundle.random_seed,
            "env_seed": seed_bundle.env_seed,
            "rollout_seed": seed_bundle.rollout_seed,
        },
    }

    for episode_index in range(args.episodes):
        record = new_episode_record(episode_id=episode_index)
        episode_seed = seed_bundle.env_seed + episode_index
        observation, reset_info = reset_environment(env, episode_seed)
        logger.info(
            "Episode %d/%d reset with env_seed=%d info_keys=%s",
            episode_index + 1,
            args.episodes,
            episode_seed,
            sorted(reset_info.keys()),
        )

        done = False
        step_count = 0
        episode_return = 0.0

        while not done:
            step_id = step_count
            obs_array = to_numpy_array(observation, numpy_module, "observation_t")
            ensure_finite_array(obs_array, numpy_module, "observation_t", record.episode_id, step_id)
            obs_shape = list(obs_array.shape)
            if record.observation_shape is None:
                record.observation_shape = obs_shape
            elif record.observation_shape != obs_shape:
                raise RolloutError(
                    "Observation shape drift detected inside a single episode: "
                    f"episode_id={record.episode_id}, step_id={step_id}, "
                    f"expected={record.observation_shape}, got={obs_shape}."
                )

            action_mask_json, mask_available, mask_source, mask_error = try_read_action_mask(
                env=env,
                step_info=reset_info if step_id == 0 else {},
                numpy_module=numpy_module,
            )
            if mask_error:
                mask_capture_errors.append(
                    f"episode_id={record.episode_id}, step_id={step_id}: {mask_error}"
                )
            if mask_available:
                mask_available_steps += 1
                if mask_source:
                    mask_sources[mask_source] += 1

            action = policy.predict(observation)
            action_payload = normalize_json_payload(action, numpy_module)
            action_json = canonical_json(action_payload)
            action_hash = sha256_text(action_json)
            step_output = normalize_step_output(env.step(action))
            observation, reward_value, terminated, truncated, step_info = step_output
            reward_scalar = coerce_scalar_reward(reward_value, modules.get("numpy"))
            episode_return += reward_scalar
            step_rewards.append(reward_scalar)
            step_count += 1
            done = terminated or truncated

            info_payload = normalize_json_payload(step_info if isinstance(step_info, dict) else {}, numpy_module)
            info_json = canonical_json(info_payload)
            if isinstance(step_info, dict):
                record.env_info_keys_union.extend(step_info.keys())

            record.step_id.append(step_id)
            record.observation_t.append(obs_array)
            record.action_t.append(action_payload)
            record.action_t_json.append(action_json)
            record.action_t_hash.append(action_hash)
            record.reward_t.append(float(reward_scalar))
            record.done_t.append(bool(done))
            record.terminated_t.append(bool(terminated))
            record.truncated_t.append(bool(truncated))
            if bool(terminated):
                record.terminal_type_t.append("terminated")
            elif bool(truncated):
                record.terminal_type_t.append("truncated")
            else:
                record.terminal_type_t.append("ongoing")
            record.info_t_json.append(info_json)
            record.action_mask_t_json.append(action_mask_json)
            record.action_mask_available_t.append(mask_available)

            action_surface_histogram[extract_action_surface_bucket(action_payload)] += 1

            if done:
                terminal_key = "terminated" if terminated else "truncated"
                terminal_counts[terminal_key] += 1
                logger.info(
                    "Episode %d finished after %d steps with return=%.6f (%s, info_keys=%s)",
                    episode_index + 1,
                    step_count,
                    episode_return,
                    terminal_key,
                    sorted(step_info.keys()),
                )

            if step_count >= args.rollout_step_limit and not done:
                raise RolloutError(
                    f"Episode {episode_index + 1} exceeded rollout step limit {args.rollout_step_limit} without reaching terminal."
                )

        episode_lengths.append(step_count)
        episode_returns.append(episode_return)
        total_steps += step_count
        record.env_info_keys_union = sorted(set(record.env_info_keys_union))

        episode_validation = validate_episode_record(record, numpy_module)
        if not episode_validation.ok:
            validation_errors.extend(episode_validation.errors)
            continue

        episode_stem = f"episode_{episode_index:05d}"
        episode_npz_path = batch_dir / f"{episode_stem}.npz"
        write_episode_npz(episode_npz_path, record, numpy_module, batch_metadata)
        serialized_validation = validate_saved_episode_npz(episode_npz_path, numpy_module)
        if not serialized_validation.ok:
            validation_errors.extend(serialized_validation.errors)
            continue
        exported_episode_files.append(str(episode_npz_path))

        if jsonl_enabled:
            episode_jsonl_path = batch_dir / f"{episode_stem}.jsonl"
            write_episode_jsonl(episode_jsonl_path, record)
            exported_jsonl_files.append(str(episode_jsonl_path))

    if sum(terminal_counts.values()) == 0:
        raise RolloutError("Smoke-check failed: no episode reached terminal.")

    if total_steps == 0:
        raise RolloutError("Exporter produced zero steps. Cannot create a valid Day 3 raw batch.")

    if validation_errors:
        raise RolloutError(
            "Day 3 primary validation failed. Export is not self-consistent. "
            f"First error: {validation_errors[0]}"
        )

    if mask_available_steps == 0:
        mask_recording_mode = "unavailable"
    elif mask_available_steps == total_steps:
        mask_recording_mode = "explicit"
    else:
        mask_recording_mode = "partial"

    summary_payload = {
        "timestamp_utc": timestamp,
        "status": "success",
        "batch_name": batch_name,
        "batch_mode": args.batch_mode,
        "batch_label": batch_label,
        "format": {
            "primary": "npz",
            "debug": "jsonl" if jsonl_enabled else "disabled",
        },
        "mask_recording_mode": mask_recording_mode,
        "mask_capture": {
            "available_steps": mask_available_steps,
            "total_steps": total_steps,
            "sources": dict(mask_sources),
            "capture_errors": mask_capture_errors,
        },
        "policy_source_id": policy.source_id,
        "env_id": args.env_id,
        "env_version": runtime_versions.microrts_version,
        "map_path": args.map_path,
        "seed_metadata": {
            "random_seed": seed_bundle.random_seed,
            "env_seed": seed_bundle.env_seed,
            "rollout_seed": seed_bundle.rollout_seed,
        },
        "validation": {
            "status": "passed",
            "checks": [
                "array lengths per step are consistent",
                "episode_id / step_id are contiguous and aligned",
                "no NaN/Inf in reward_t and observation_t",
                "done_t finalization is terminal-consistent",
                "no same-episode continuation after done_t=True",
                "action payload serialization hash is stable",
            ],
        },
        "batch_statistics": {
            "episodes": args.episodes,
            "steps": total_steps,
            "mean_episode_length": compute_mean(episode_lengths),
            "mean_episode_return": compute_mean(episode_returns),
            "std_episode_return": compute_std(episode_returns),
            "reward_mean": compute_mean(step_rewards),
            "reward_std": compute_std(step_rewards),
            "terminal_counts": terminal_counts,
            "action_surface_histogram": dict(action_surface_histogram),
        },
        "artifacts": {
            "batch_dir": str(batch_dir),
            "npz_files": exported_episode_files,
            "jsonl_files": exported_jsonl_files,
        },
        "notes": [
            "Raw teacher-side representations are preserved; no Gym->Unity remap is applied.",
            "Day 3 export is intentionally pre-adapter and pre-BC conversion.",
            "Action histogram is a payload-surface view, not a semantic action taxonomy claim.",
        ],
    }

    batch_summary_path = batch_dir / "batch.summary.json"
    write_summary(batch_summary_path, summary_payload)

    return {
        "batch_name": batch_name,
        "batch_dir": str(batch_dir),
        "batch_summary_path": str(batch_summary_path),
        "episodes": args.episodes,
        "steps": total_steps,
        "episode_lengths": episode_lengths,
        "episode_returns": episode_returns,
        "mean_episode_length": compute_mean(episode_lengths),
        "mean_episode_return": compute_mean(episode_returns),
        "std_episode_return": compute_std(episode_returns),
        "reward_mean": compute_mean(step_rewards),
        "reward_std": compute_std(step_rewards),
        "terminal_counts": terminal_counts,
        "mask_recording_mode": mask_recording_mode,
        "mask_available_steps": mask_available_steps,
        "npz_file_count": len(exported_episode_files),
        "jsonl_file_count": len(exported_jsonl_files),
        "action_surface_histogram": dict(action_surface_histogram),
    }


def write_summary(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def main() -> int:
    args = parse_args()
    if args.episodes < 1:
        print("--episodes must be >= 1", file=sys.stderr)
        return 2
    if args.rollout_step_limit < 1:
        print("--rollout-step-limit must be >= 1", file=sys.stderr)
        return 2

    run_root = args.output_dir.resolve() if args.output_dir else Path(__file__).resolve().parent
    output_paths = setup_output_paths(run_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = output_paths.teacher_logs / f"teacher_rollout_{timestamp}.log"
    summary_path = output_paths.teacher_logs / f"teacher_rollout_{timestamp}.summary.json"
    logger = configure_logging(log_path)
    env: Optional[Any] = None

    try:
        seed_bundle = resolve_seed_bundle(args)
        modules, versions = import_runtime_modules()
        seed_process(seed_bundle, modules)

        logger.info("Week 5 Day 3 raw exporter started.")
        logger.info("Output root: %s", output_paths.root)
        logger.info(
            "Seeds: random_seed=%d env_seed=%d rollout_seed=%d",
            seed_bundle.random_seed,
            seed_bundle.env_seed,
            seed_bundle.rollout_seed,
        )
        log_runtime_versions(logger, versions)

        env, initial_observation, reset_info, env_summary = build_environment(args, seed_bundle, modules, logger)
        del initial_observation
        del reset_info

        policy = load_policy_source(args, env, seed_bundle, versions, modules, logger)
        logger.info("Policy source: %s", json.dumps(policy.describe(), ensure_ascii=True))

        rollout_stats = run_rollouts(
            env=env,
            policy=policy,
            args=args,
            seed_bundle=seed_bundle,
            modules=modules,
            logger=logger,
            output_paths=output_paths,
            timestamp=timestamp,
            runtime_versions=versions,
        )

        smoke_check = {
            "policy_loaded": True,
            "environment_created": True,
            "observation_shape_readable": bool(env_summary.get("initial_observation_shape") is not None),
            "action_space_readable": bool(env_summary.get("action_space")),
            "terminal_episode_observed": sum(rollout_stats["terminal_counts"].values()) >= 1,
            "first_rollout_completed_without_crash": True,
        }

        summary_payload = {
            "timestamp_utc": timestamp,
            "status": "success",
            "smoke_check": smoke_check,
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
            "seeds": {
                "random_seed": seed_bundle.random_seed,
                "env_seed": seed_bundle.env_seed,
                "rollout_seed": seed_bundle.rollout_seed,
            },
            "paths": {
                "root": str(output_paths.root),
                "teacher_models": str(output_paths.teacher_models),
                "teacher_rollouts": str(output_paths.teacher_rollouts),
                "teacher_logs": str(output_paths.teacher_logs),
                "teacher_exports": str(output_paths.teacher_exports),
            },
            "environment": env_summary,
            "policy": policy.describe(),
            "rollout": rollout_stats,
            "compatibility_scope": "shape-only",
            "semantic_parity_verified": False,
            "notes": [
                "Day 3 keeps the validated runtime contract and adds raw teacher per-episode export.",
                "No Gym->Unity adapter conversion is applied in this script.",
                "No BC-ready shaping is applied in this script.",
                "Reward handling remains strict: scalar reward payload is required.",
                env_summary["scenario_note"],
            ],
        }
        write_summary(summary_path, summary_payload)

        logger.info("Rollout summary written to %s", summary_path)
        logger.info(
            "Completed %d episode(s) and exported raw batch '%s': steps=%d mean_len=%.2f mean_return=%.6f std_return=%.6f mask_mode=%s terminals=%s",
            rollout_stats["episodes"],
            rollout_stats["batch_name"],
            rollout_stats["steps"],
            rollout_stats["mean_episode_length"],
            rollout_stats["mean_episode_return"],
            rollout_stats["std_episode_return"],
            rollout_stats["mask_recording_mode"],
            rollout_stats["terminal_counts"],
        )
        return 0
    except RolloutError as exc:
        logger.error("Day 3 exporter failed: %s", exc)
        summary_payload = {
            "timestamp_utc": timestamp,
            "status": "error",
            "error": str(exc),
        }
        write_summary(summary_path, summary_payload)
        logger.error("Failure summary written to %s", summary_path)
        return 1
    except Exception as exc:
        logger.exception("Unexpected failure: %s", exc)
        summary_payload = {
            "timestamp_utc": timestamp,
            "status": "error",
            "error": f"Unexpected failure: {exc}",
        }
        write_summary(summary_path, summary_payload)
        logger.error("Failure summary written to %s", summary_path)
        return 1
    finally:
        if env is not None and hasattr(env, "close"):
            env.close()


if __name__ == "__main__":
    raise SystemExit(main())