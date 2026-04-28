#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import random
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from gym.spaces import MultiDiscrete
from torch.utils.tensorboard import SummaryWriter

from gridnet_model import Agent


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_checkpoint_steps(raw: str, total_timesteps: int) -> List[int]:
    values: List[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        step = int(token)
        if step <= 0:
            continue
        if step > total_timesteps:
            continue
        values.append(step)
    if not values:
        values = [total_timesteps]
    out = sorted(set(values))
    if out[-1] != total_timesteps:
        out.append(total_timesteps)
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Project-compatible Gridnet teacher training (Branch B). "
            "Ports architecture/masking/opponent setup from reference, without weight reuse."
        )
    )
    p.add_argument("--env-id", default="MicrortsSelfPlayShapedReward-v1")
    p.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    p.add_argument("--run-id", default=None)
    p.add_argument("--output-root", type=Path, default=Path("WEEK5R/gridnet_teacher_runs"))

    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--device", default="cpu")

    p.add_argument("--learning-rate", type=float, default=2.5e-4)
    p.add_argument("--num-steps", type=int, default=256)
    p.add_argument("--n-minibatch", type=int, default=4)
    p.add_argument("--gamma", type=float, default=0.99)
    p.add_argument("--gae-lambda", type=float, default=0.95)
    p.add_argument("--ent-coef", type=float, default=0.01)
    p.add_argument("--ent-schedule", choices=["none", "linear"], default="none")
    p.add_argument("--ent-coef-start", type=float, default=0.01)
    p.add_argument("--ent-coef-end", type=float, default=0.01)
    p.add_argument("--vf-coef", type=float, default=0.5)
    p.add_argument("--max-grad-norm", type=float, default=0.5)
    p.add_argument("--clip-coef", type=float, default=0.1)
    p.add_argument("--update-epochs", type=int, default=4)
    p.add_argument("--anneal-lr", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--norm-adv", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--clip-vloss", action=argparse.BooleanOptionalAction, default=True)

    p.add_argument("--num-bot-envs", type=int, default=6)
    p.add_argument("--num-selfplay-envs", type=int, default=0)
    p.add_argument("--max-steps-per-episode", type=int, default=2000)

    p.add_argument("--total-timesteps", type=int, default=100000)
    p.add_argument("--checkpoint-steps", default="20000,50000,100000")
    p.add_argument("--resume-from-checkpoint", type=Path, default=None)
    p.add_argument("--resume-model-metadata", type=Path, default=None)
    p.add_argument("--initial-global-step", type=int, default=0)

    p.add_argument("--eval-after-checkpoint", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--eval-episodes", type=int, default=4)
    p.add_argument("--eval-max-steps", type=int, default=256)
    p.add_argument("--eval-effective-steps", type=int, default=100)

    p.add_argument("--capture-video", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--tensorboard-root", type=Path, default=None)
    p.add_argument("--disable-tensorboard", action=argparse.BooleanOptionalAction, default=False)

    p.add_argument("--curriculum-mode", choices=["none", "passive_warmup", "economy_warmup"], default="none")

    p.add_argument("--activity-shaping", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--shape-move-reward", type=float, default=0.005)
    p.add_argument("--shape-produce-reward", type=float, default=0.003)
    p.add_argument("--shape-noop-penalty", type=float, default=0.0005)
    p.add_argument("--shape-no-effect-penalty", type=float, default=0.001)

    p.add_argument("--render-window", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--render-during-train", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--render-during-final-eval", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--render-fps", type=int, default=8)
    p.add_argument("--render-max-steps", type=int, default=200)
    p.add_argument("--render-every-n-updates", type=int, default=0)
    p.add_argument("--save-visual-notes", action=argparse.BooleanOptionalAction, default=True)
    return p.parse_args()


class FileAndConsoleLogger:
    def __init__(self, log_path: Path) -> None:
        self.logger = logging.getLogger("gridnet_teacher")
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()

        fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(fmt)
        self.logger.addHandler(fh)

        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        self.logger.addHandler(sh)

    def info(self, msg: str, *args: Any) -> None:
        self.logger.info(msg, *args)

    def warning(self, msg: str, *args: Any) -> None:
        self.logger.warning(msg, *args)


@dataclass(frozen=True)
class ArtifactPaths:
    run_dir: Path
    checkpoints_dir: Path
    gate_reports_dir: Path
    train_log: Path
    command_txt: Path
    run_manifest: Path
    model_metadata: Path
    summary_md: Path


class NullSummaryWriter:
    def add_scalar(self, *args: Any, **kwargs: Any) -> None:
        return

    def close(self) -> None:
        return


def build_short_tb_run_name(run_name: str, max_len: int = 48) -> str:
    digest = hashlib.sha1(run_name.encode("utf-8")).hexdigest()[:8]
    max_base_len = max(1, max_len - 9)
    base = run_name[:max_base_len]
    return f"{base}_{digest}"


def prepare_artifacts(args: argparse.Namespace) -> ArtifactPaths:
    run_id = args.run_id or f"gridnet_project_{utc_stamp()}"
    run_dir = (args.output_root / run_id).resolve()
    checkpoints_dir = run_dir / "checkpoints"
    gate_reports_dir = run_dir / "gate_or_eval_reports"

    run_dir.mkdir(parents=True, exist_ok=True)
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    gate_reports_dir.mkdir(parents=True, exist_ok=True)

    paths = ArtifactPaths(
        run_dir=run_dir,
        checkpoints_dir=checkpoints_dir,
        gate_reports_dir=gate_reports_dir,
        train_log=run_dir / "train.log",
        command_txt=run_dir / "command.txt",
        run_manifest=run_dir / "run_manifest.json",
        model_metadata=run_dir / "model_metadata.json",
        summary_md=run_dir / "summary.md",
    )
    return paths


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)


def maybe_read_json(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def build_model_metadata(
    *,
    args: argparse.Namespace,
    run_dir: Path,
    obs_shape: Tuple[int, int, int],
    mapsize: int,
    nvec: List[int],
    branch_sizes: List[int],
    actor_output_channels: int,
    num_envs: int,
    final_model_path: Optional[Path] = None,
    saved_checkpoint_steps: Optional[List[int]] = None,
) -> Dict[str, Any]:
    args_payload: Dict[str, Any] = {}
    for key, value in vars(args).items():
        if isinstance(value, Path):
            args_payload[key] = str(value)
        else:
            args_payload[key] = value

    payload: Dict[str, Any] = {
        "schema": "week5_teacher_gridnet_project.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "note": "Project-compatible Gridnet teacher checkpoint. Architecture ported from reference; no reference weights reused.",
        "args": args_payload,
        "run_dir": str(run_dir),
        "observation_shape": list(obs_shape),
        "map_height": int(obs_shape[0]),
        "map_width": int(obs_shape[1]),
        "mapsize": mapsize,
        "observation_channels": int(obs_shape[2]),
        "action_nvec": nvec,
        "action_branch_sizes": branch_sizes,
        "actor_output_channels": actor_output_channels,
        "action_tensor_shape": [num_envs, mapsize, len(branch_sizes)],
        "entropy_schedule": {
            "mode": args.ent_schedule,
            "ent_coef_base": float(args.ent_coef),
            "ent_coef_start": float(args.ent_coef_start),
            "ent_coef_end": float(args.ent_coef_end),
        },
        "curriculum": {
            "mode": args.curriculum_mode,
        },
        "activity_shaping": {
            "enabled": bool(args.activity_shaping),
            "shape_move_reward": float(args.shape_move_reward),
            "shape_produce_reward": float(args.shape_produce_reward),
            "shape_noop_penalty": float(args.shape_noop_penalty),
            "shape_no_effect_penalty": float(args.shape_no_effect_penalty),
        },
        "training_surface_claim": "project-compatible-shape-only",
        "unity_checkpoint_compatible": False,
    }
    if final_model_path is not None:
        payload["final_model_path"] = str(final_model_path)
    if saved_checkpoint_steps is not None:
        payload["saved_checkpoint_steps"] = list(saved_checkpoint_steps)
    return payload


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def build_ai2s(num_bot_envs: int) -> List[Any]:
    from gym_microrts import microrts_ai

    ai2s: List[Any] = []
    template = [
        microrts_ai.randomBiasedAI,
        microrts_ai.randomBiasedAI,
        microrts_ai.lightRushAI,
        microrts_ai.lightRushAI,
        microrts_ai.workerRushAI,
        microrts_ai.workerRushAI,
    ]

    for idx in range(num_bot_envs):
        if idx < len(template):
            ai2s.append(template[idx])
        else:
            ai2s.append(microrts_ai.coacAI)
    return ai2s


def build_ai2s_from_names(num_bot_envs: int, opponent_names: Sequence[str]) -> List[Any]:
    from gym_microrts import microrts_ai

    resolved: List[Any] = []
    fallback = microrts_ai.randomBiasedAI
    for name in opponent_names:
        resolved.append(getattr(microrts_ai, name, fallback))
    if not resolved:
        return build_ai2s(num_bot_envs)

    ai2s: List[Any] = []
    for idx in range(num_bot_envs):
        ai2s.append(resolved[idx % len(resolved)])
    return ai2s


def curriculum_phase_for_step(args: argparse.Namespace, global_step: int) -> str:
    if args.curriculum_mode == "none":
        return "single"
    if global_step < 50000:
        return "warmup"
    return "diverse"


def curriculum_opponents_by_phase(args: argparse.Namespace) -> Dict[str, List[str]]:
    if args.curriculum_mode == "passive_warmup":
        return {
            "warmup": ["passiveAI", "randomBiasedAI"],
            "diverse": ["randomBiasedAI", "lightRushAI", "workerRushAI", "coacAI"],
        }
    if args.curriculum_mode == "economy_warmup":
        return {
            "warmup": ["passiveAI", "randomBiasedAI", "workerRushAI"],
            "diverse": ["randomBiasedAI", "lightRushAI", "workerRushAI", "coacAI"],
        }
    return {
        "single": ["randomBiasedAI", "randomBiasedAI", "lightRushAI", "lightRushAI", "workerRushAI", "workerRushAI", "coacAI"],
    }


def get_current_ent_coef(args: argparse.Namespace, update: int, num_updates: int) -> float:
    if args.ent_schedule == "none":
        return float(args.ent_coef)
    if num_updates <= 1:
        return float(args.ent_coef_end)
    t = (float(update) - 1.0) / float(max(1, num_updates - 1))
    return float(args.ent_coef_start + t * (args.ent_coef_end - args.ent_coef_start))


def build_env(args: argparse.Namespace, logger: FileAndConsoleLogger, curriculum_phase: str):
    from gym_microrts.envs.vec_env import MicroRTSGridModeVecEnv

    opponents_by_phase = curriculum_opponents_by_phase(args)
    opponent_names = opponents_by_phase.get(curriculum_phase, opponents_by_phase.get("single", []))
    ai2s = build_ai2s_from_names(args.num_bot_envs, opponent_names)
    common_kwargs = dict(
        num_selfplay_envs=args.num_selfplay_envs,
        num_bot_envs=args.num_bot_envs,
        max_steps=args.max_steps_per_episode,
        render_theme=2,
        ai2s=ai2s,
        reward_weight=np.array([10.0, 1.0, 1.0, 0.2, 1.0, 4.0]),
        autobuild=False,
    )

    try:
        envs = MicroRTSGridModeVecEnv(
            map_paths=[args.map_path],
            **common_kwargs,
        )
    except TypeError:
        envs = MicroRTSGridModeVecEnv(
            map_path=args.map_path,
            **common_kwargs,
        )

    logger.info("Opponent setup: curriculum_mode=%s phase=%s num_bot_envs=%s pool=%s", args.curriculum_mode, curriculum_phase, args.num_bot_envs, opponent_names)
    return envs


def build_single_eval_env(map_path: str, max_steps: int, opponent_name: str):
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


def read_invalid_action_masks(envs: Any, device: torch.device) -> torch.Tensor:
    if hasattr(envs, "get_action_mask"):
        action_mask = np.asarray(envs.get_action_mask())
        if not hasattr(envs, "source_unit_mask"):
            raise RuntimeError("Environment get_action_mask() did not expose source_unit_mask.")
        source_mask = np.asarray(envs.source_unit_mask)
        source_mask = source_mask.reshape(source_mask.shape[0], source_mask.shape[1], 1)
        raw = np.concatenate([source_mask, action_mask], axis=2)
    elif hasattr(envs, "vec_client") and hasattr(envs.vec_client, "getMasks"):
        raw = np.asarray(envs.vec_client.getMasks(0))
    elif hasattr(envs, "action_masks"):
        maybe = getattr(envs, "action_masks")
        raw = np.asarray(maybe() if callable(maybe) else maybe)
    else:
        raise RuntimeError("Environment does not expose invalid action masks.")

    raw = np.asarray(raw)
    if raw.ndim == 4:
        n, h, w, k = raw.shape
        raw = raw.reshape(n, h * w, k)
    elif raw.ndim != 3:
        raise RuntimeError(f"Expected mask shape [N, H*W, K] or [N, H, W, K], got {tuple(raw.shape)}")

    tensor = torch.as_tensor(np.array(raw, copy=True), device=device)
    return tensor


def to_java_valid_actions(
    action: torch.Tensor,
    invalid_action_mask: torch.Tensor,
    mapsize: int,
) -> Any:
    from jpype.types import JArray, JInt

    source_idx = torch.arange(0, mapsize, device=action.device).unsqueeze(0).repeat(action.shape[0], 1).unsqueeze(2)
    real_action = torch.cat([source_idx, action], dim=2)

    real_np = real_action.detach().cpu().numpy()
    valid_np = real_np[invalid_action_mask[:, :, 0].bool().detach().cpu().numpy()]
    valid_counts = invalid_action_mask[:, :, 0].sum(1).long().detach().cpu().numpy()

    java_valid_actions = []
    valid_idx = 0
    for valid_count in valid_counts:
        env_actions = []
        for _ in range(int(valid_count)):
            env_actions.append(JArray(JInt)(valid_np[valid_idx].tolist()))
            valid_idx += 1
        java_valid_actions.append(JArray(JArray(JInt))(env_actions))
    return JArray(JArray(JArray(JInt)))(java_valid_actions)


def save_checkpoint(agent: Agent, step: int, checkpoints_dir: Path) -> Path:
    path = checkpoints_dir / f"agent_step_{int(step):09d}.pt"
    torch.save(agent.state_dict(), path)
    return path


def run_checkpoint_eval(
    *,
    python_exe: str,
    evaluator_script: Path,
    checkpoint_path: Path,
    metadata_path: Path,
    output_dir: Path,
    args: argparse.Namespace,
    logger: FileAndConsoleLogger,
) -> Dict[str, Any]:
    json_path = output_dir / f"eval_{checkpoint_path.stem}.json"
    md_path = output_dir / f"eval_{checkpoint_path.stem}.md"

    cmd = [
        python_exe,
        str(evaluator_script),
        "--checkpoint", str(checkpoint_path),
        "--model-metadata", str(metadata_path),
        "--episodes", str(args.eval_episodes),
        "--max-steps", str(args.eval_max_steps),
        "--effective-steps", str(args.eval_effective_steps),
        "--seed", str(args.seed),
        "--map-path", args.map_path,
        "--output-json", str(json_path),
        "--output-md", str(md_path),
        "--device", args.device,
    ]

    logger.info("Running gridnet actor-level evaluator: %s", " ".join(cmd))
    completed = subprocess.run(cmd, capture_output=True, text=True)
    payload: Dict[str, Any] = {
        "checkpoint": str(checkpoint_path),
        "exit_code": int(completed.returncode),
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
        "report_json": str(json_path),
        "report_md": str(md_path),
    }
    if json_path.is_file():
        try:
            payload["report"] = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:
            payload["report_read_error"] = f"{type(exc).__name__}: {exc}"

    if completed.returncode != 0:
        logger.warning("Evaluator failed at checkpoint %s (exit=%s)", checkpoint_path.name, completed.returncode)
    return payload


def maybe_render_env(envs: Any, logger: FileAndConsoleLogger) -> bool:
    try:
        envs.render(mode="human")
        return True
    except Exception as exc:
        logger.warning("Render window unavailable: %s", exc)
        return False


def run_visual_final_eval(
    *,
    args: argparse.Namespace,
    logger: FileAndConsoleLogger,
    agent: Agent,
    device: torch.device,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "render_window_enabled": bool(args.render_window),
        "visual_eval_attempted": False,
        "visual_eval_status": "warning",
        "visual_eval_steps": 0,
        "visual_eval_opponent": "randomBiasedAI",
        "visual_eval_checkpoint_or_final_model": "final_model",
        "note": "visual sanity layer only; not a replacement for actor-level evaluator",
    }

    if not (args.render_window and args.render_during_final_eval):
        result["visual_eval_status"] = "unavailable"
        return result

    result["visual_eval_attempted"] = True
    env = None
    try:
        env = build_single_eval_env(args.map_path, args.max_steps_per_episode, "randomBiasedAI")
        obs = torch.as_tensor(env.reset(), device=device, dtype=torch.float32)
        done = False
        step = 0
        render_period_s = 1.0 / max(1, int(args.render_fps))

        while not done and step < int(args.render_max_steps):
            with torch.no_grad():
                invalid_masks = read_invalid_action_masks(env, device)
                action, _logprob, _entropy, _used_masks = agent.get_action(
                    obs,
                    invalid_action_masks=invalid_masks,
                    action=None,
                    deterministic=True,
                )

            render_ok = maybe_render_env(env, logger)
            if not render_ok:
                result["visual_eval_status"] = "warning"
                result["visual_eval_steps"] = int(step)
                return result

            action_np = action.detach().cpu().numpy().astype(np.int32)
            next_obs_np, _reward_np, done_np, _infos = env.step(action_np)
            obs = torch.as_tensor(next_obs_np, device=device, dtype=torch.float32)
            done = bool(np.asarray(done_np).reshape(-1)[0])
            step += 1
            time.sleep(render_period_s)

        result["visual_eval_status"] = "ok"
        result["visual_eval_steps"] = int(step)
        return result
    except Exception as exc:
        logger.warning("Visual final eval failed: %s", exc)
        result["visual_eval_status"] = "warning"
        result["visual_eval_error"] = f"{type(exc).__name__}: {exc}"
        return result
    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass


def main() -> None:
    args = parse_args()
    if args.num_bot_envs < 6:
        raise ValueError("num_bot_envs must be >= 6 to match the intended diverse-bot setup.")
    if args.initial_global_step < 0:
        raise ValueError("initial-global-step must be >= 0.")
    if args.total_timesteps <= args.initial_global_step:
        raise ValueError("total-timesteps must be greater than initial-global-step.")
    if args.ent_schedule == "linear" and args.ent_coef_start < 0.0:
        raise ValueError("ent-coef-start must be >= 0 for linear schedule.")
    if args.ent_schedule == "linear" and args.ent_coef_end < 0.0:
        raise ValueError("ent-coef-end must be >= 0 for linear schedule.")
    if args.ent_coef < 0.0:
        raise ValueError("ent-coef must be >= 0.")
    if args.resume_from_checkpoint is not None and not args.resume_from_checkpoint.is_file():
        raise FileNotFoundError(f"resume checkpoint not found: {args.resume_from_checkpoint}")
    if args.resume_model_metadata is not None and not args.resume_model_metadata.is_file():
        raise FileNotFoundError(f"resume model metadata not found: {args.resume_model_metadata}")

    checkpoint_steps = parse_checkpoint_steps(args.checkpoint_steps, args.total_timesteps)
    checkpoint_steps = [step for step in checkpoint_steps if step > args.initial_global_step]
    args.batch_size = int((args.num_bot_envs + args.num_selfplay_envs) * args.num_steps)
    args.minibatch_size = int(args.batch_size // args.n_minibatch)
    if args.minibatch_size <= 0:
        raise ValueError("Invalid minibatch size; verify n_minibatch and num_envs.")

    paths = prepare_artifacts(args)
    logger = FileAndConsoleLogger(paths.train_log)

    command_line = " ".join([sys.executable] + sys.argv)
    paths.command_txt.write_text(command_line + "\n", encoding="utf-8")

    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() and args.device.lower() == "cuda" else "cpu")

    current_curriculum_phase = curriculum_phase_for_step(args, args.initial_global_step)
    envs = build_env(args, logger, current_curriculum_phase)
    if not isinstance(envs.action_space, MultiDiscrete):
        raise RuntimeError("Only MultiDiscrete action spaces are supported.")

    obs_shape = tuple(int(v) for v in envs.observation_space.shape)
    if len(obs_shape) != 3 or obs_shape[-1] != 27:
        raise RuntimeError(
            f"Expected observation surface [H,W,27], got {obs_shape}. "
            "Branch B requires 27-channel project-compatible surface."
        )

    mapsize = int(obs_shape[0] * obs_shape[1])

    if hasattr(envs, "action_plane_space") and hasattr(envs.action_plane_space, "nvec"):
        cell_branch_sizes = [int(v) for v in envs.action_plane_space.nvec.tolist()]
    else:
        flat_nvec = [int(v) for v in envs.action_space.nvec.tolist()]
        if len(flat_nvec) % mapsize != 0:
            raise RuntimeError("Cannot derive per-cell action branches from flattened action space.")
        cell_branch_sizes = flat_nvec[: len(flat_nvec) // mapsize]

    nvec = [mapsize] + cell_branch_sizes
    branch_sizes = cell_branch_sizes
    actor_output_channels = int(sum(branch_sizes))

    logger.info("Observation shape: %s", obs_shape)
    logger.info("Action nvec: %s", nvec)
    logger.info("Actor branch sizes: %s (sum=%s)", branch_sizes, actor_output_channels)

    agent = Agent(obs_shape, nvec).to(device)
    resume_metadata = maybe_read_json(args.resume_model_metadata)
    if args.resume_from_checkpoint is not None:
        logger.info("Resuming model weights from checkpoint: %s", args.resume_from_checkpoint)
        state_dict = torch.load(args.resume_from_checkpoint, map_location=device)
        agent.load_state_dict(state_dict)
    if resume_metadata is not None:
        logger.info("Loaded resume metadata: %s", args.resume_model_metadata)
    optimizer = optim.Adam(agent.parameters(), lr=args.learning_rate, eps=1e-5)

    run_name = f"gridnet_project__{args.seed}__{utc_stamp()}"
    short_tb_run_name = build_short_tb_run_name(run_name)
    if args.tensorboard_root is not None:
        tb_root = args.tensorboard_root.resolve()
    else:
        tb_root = paths.run_dir / "tb"
    tb_log_dir = tb_root / short_tb_run_name

    writer: Any = NullSummaryWriter()
    tensorboard_status = "disabled_by_flag" if args.disable_tensorboard else "enabled"
    tensorboard_error: Optional[str] = None
    if args.disable_tensorboard:
        logger.info("TensorBoard disabled by flag; tb_log_dir=%s", tb_log_dir)
    else:
        try:
            tb_log_dir.mkdir(parents=True, exist_ok=True)
            writer = SummaryWriter(log_dir=str(tb_log_dir))
            logger.info("TensorBoard log dir: %s", tb_log_dir)
        except Exception as exc:
            tensorboard_status = "disabled_after_error"
            tensorboard_error = f"{type(exc).__name__}: {exc}"
            writer = NullSummaryWriter()
            logger.warning("TensorBoard init failed; fallback to NullSummaryWriter: %s", tensorboard_error)

    opponent_pool_by_phase = curriculum_opponents_by_phase(args)
    phase_boundaries: List[Dict[str, Any]] = []
    if args.curriculum_mode == "none":
        phase_boundaries = [
            {"phase": "single", "start_global_step": int(args.initial_global_step), "end_global_step": int(args.total_timesteps)}
        ]
    else:
        warmup_end = int(min(50000, args.total_timesteps))
        phase_boundaries = [
            {"phase": "warmup", "start_global_step": int(args.initial_global_step), "end_global_step": warmup_end},
            {"phase": "diverse", "start_global_step": warmup_end, "end_global_step": int(args.total_timesteps)},
        ]

    activity_shaping_counters: Dict[str, Any] = {
        "enabled": bool(args.activity_shaping),
        "shaping_applied": False,
        "attribution_reliable": False,
        "diagnostics_only_reason": "reliable per-step causal attribution is unavailable in current training env interface",
        "move_reward_events": 0,
        "produce_reward_events": 0,
        "repeated_noop_penalty_events": 0,
        "no_effect_penalty_events": 0,
        "shaping_total_reward_delta": 0.0,
    }

    action_shape = (mapsize, len(branch_sizes))
    invalid_mask_shape = (mapsize, actor_output_channels + 1)

    # Pre-write model metadata so checkpoint evaluator has schema/context from step 1.
    preliminary_metadata = build_model_metadata(
        args=args,
        run_dir=paths.run_dir,
        obs_shape=obs_shape,
        mapsize=mapsize,
        nvec=nvec,
        branch_sizes=branch_sizes,
        actor_output_channels=actor_output_channels,
        num_envs=envs.num_envs,
    )
    write_json(paths.model_metadata, preliminary_metadata)

    obs = torch.zeros((args.num_steps, envs.num_envs) + obs_shape, device=device)
    actions = torch.zeros((args.num_steps, envs.num_envs) + action_shape, device=device)
    logprobs = torch.zeros((args.num_steps, envs.num_envs), device=device)
    rewards = torch.zeros((args.num_steps, envs.num_envs), device=device)
    dones = torch.zeros((args.num_steps, envs.num_envs), device=device)
    values = torch.zeros((args.num_steps, envs.num_envs), device=device)
    invalid_masks_storage = torch.zeros((args.num_steps, envs.num_envs) + invalid_mask_shape, device=device)

    next_obs = torch.as_tensor(envs.reset(), device=device, dtype=torch.float32)
    next_done = torch.zeros(envs.num_envs, device=device)

    remaining_timesteps = args.total_timesteps - args.initial_global_step
    num_updates = max(1, math.ceil(remaining_timesteps / args.batch_size))
    global_step = int(args.initial_global_step)
    start_time = time.time()

    evaluator_script = Path(__file__).resolve().parent / "evaluate_gridnet_actor_level.py"
    checkpoint_reports: List[Dict[str, Any]] = []
    saved_checkpoint_steps: List[int] = []

    def maybe_save_and_eval() -> None:
        nonlocal checkpoint_reports
        while checkpoint_steps and global_step >= checkpoint_steps[0]:
            target_step = checkpoint_steps.pop(0)
            ckpt_path = save_checkpoint(agent, target_step, paths.checkpoints_dir)
            saved_checkpoint_steps.append(target_step)
            logger.info("Saved checkpoint: %s", ckpt_path)

            if args.eval_after_checkpoint:
                report = run_checkpoint_eval(
                    python_exe=sys.executable,
                    evaluator_script=evaluator_script,
                    checkpoint_path=ckpt_path,
                    metadata_path=paths.model_metadata,
                    output_dir=paths.gate_reports_dir,
                    args=args,
                    logger=logger,
                )
                checkpoint_reports.append(report)

    for update in range(1, num_updates + 1):
        desired_phase = curriculum_phase_for_step(args, global_step)
        if desired_phase != current_curriculum_phase:
            logger.info("Curriculum phase switch: %s -> %s at global_step=%s", current_curriculum_phase, desired_phase, global_step)
            envs.close()
            current_curriculum_phase = desired_phase
            envs = build_env(args, logger, current_curriculum_phase)
            next_obs = torch.as_tensor(envs.reset(), device=device, dtype=torch.float32)
            next_done = torch.zeros(envs.num_envs, device=device)

        should_render_update = (
            args.render_window
            and args.render_during_train
            and (args.render_every_n_updates <= 0 or (update % args.render_every_n_updates == 0))
        )

        if args.anneal_lr:
            frac = 1.0 - (update - 1.0) / num_updates
            optimizer.param_groups[0]["lr"] = frac * args.learning_rate

        current_ent_coef = get_current_ent_coef(args, update, num_updates)

        for step in range(args.num_steps):
            global_step += envs.num_envs
            obs[step] = next_obs
            dones[step] = next_done

            with torch.no_grad():
                values[step] = agent.get_value(obs[step]).flatten()
                current_invalid_masks = read_invalid_action_masks(envs, device)
                action, logprob, _entropy, current_invalid_masks = agent.get_action(
                    obs[step],
                    invalid_action_masks=current_invalid_masks,
                    action=None,
                    deterministic=False,
                )

            actions[step] = action
            logprobs[step] = logprob
            invalid_masks_storage[step] = current_invalid_masks

            action_np = action.detach().cpu().numpy().astype(np.int32)
            next_obs_np, reward_np, done_np, infos = envs.step(action_np)
            next_obs = torch.as_tensor(next_obs_np, device=device, dtype=torch.float32)
            reward_tensor = torch.as_tensor(reward_np, device=device, dtype=torch.float32)
            if args.activity_shaping and activity_shaping_counters["shaping_applied"]:
                reward_tensor = reward_tensor + float(activity_shaping_counters["shaping_total_reward_delta"])
            rewards[step] = reward_tensor
            next_done = torch.as_tensor(done_np, device=device, dtype=torch.float32)

            if should_render_update:
                maybe_render_env(envs, logger)
                time.sleep(1.0 / max(1, int(args.render_fps)))

            for info in infos:
                if "episode" in info:
                    writer.add_scalar("charts/episode_reward", float(info["episode"]["r"]), global_step)
                    break

            maybe_save_and_eval()

        with torch.no_grad():
            last_value = agent.get_value(next_obs).reshape(1, -1)
            advantages = torch.zeros_like(rewards, device=device)
            lastgaelam = 0.0
            for t in reversed(range(args.num_steps)):
                if t == args.num_steps - 1:
                    nextnonterminal = 1.0 - next_done
                    nextvalues = last_value
                else:
                    nextnonterminal = 1.0 - dones[t + 1]
                    nextvalues = values[t + 1]
                delta = rewards[t] + args.gamma * nextvalues * nextnonterminal - values[t]
                advantages[t] = lastgaelam = delta + args.gamma * args.gae_lambda * nextnonterminal * lastgaelam
            returns = advantages + values

        b_obs = obs.reshape((-1,) + obs_shape)
        b_logprobs = logprobs.reshape(-1)
        b_actions = actions.reshape((-1,) + action_shape)
        b_advantages = advantages.reshape(-1)
        b_returns = returns.reshape(-1)
        b_values = values.reshape(-1)
        b_invalid_masks = invalid_masks_storage.reshape((-1,) + invalid_mask_shape)

        inds = np.arange(args.batch_size)
        last_entropy = torch.tensor(0.0, device=device)
        last_pg_loss = torch.tensor(0.0, device=device)
        last_v_loss = torch.tensor(0.0, device=device)
        last_approx_kl = torch.tensor(0.0, device=device)

        for _epoch in range(args.update_epochs):
            np.random.shuffle(inds)
            for start in range(0, args.batch_size, args.minibatch_size):
                end = start + args.minibatch_size
                mb_inds = inds[start:end]

                mb_adv = b_advantages[mb_inds]
                if args.norm_adv:
                    mb_adv = (mb_adv - mb_adv.mean()) / (mb_adv.std() + 1e-8)

                _, newlogprob, entropy, _ = agent.get_action(
                    b_obs[mb_inds],
                    invalid_action_masks=b_invalid_masks[mb_inds],
                    action=b_actions.long()[mb_inds],
                    deterministic=False,
                )
                ratio = (newlogprob - b_logprobs[mb_inds]).exp()

                last_approx_kl = (b_logprobs[mb_inds] - newlogprob).mean()

                pg_loss1 = -mb_adv * ratio
                pg_loss2 = -mb_adv * torch.clamp(ratio, 1.0 - args.clip_coef, 1.0 + args.clip_coef)
                last_pg_loss = torch.max(pg_loss1, pg_loss2).mean()
                last_entropy = entropy.mean()

                new_values = agent.get_value(b_obs[mb_inds]).view(-1)
                if args.clip_vloss:
                    v_loss_unclipped = (new_values - b_returns[mb_inds]) ** 2
                    v_clipped = b_values[mb_inds] + torch.clamp(
                        new_values - b_values[mb_inds],
                        -args.clip_coef,
                        args.clip_coef,
                    )
                    v_loss_clipped = (v_clipped - b_returns[mb_inds]) ** 2
                    last_v_loss = 0.5 * torch.max(v_loss_unclipped, v_loss_clipped).mean()
                else:
                    last_v_loss = 0.5 * ((new_values - b_returns[mb_inds]) ** 2).mean()

                loss = last_pg_loss - current_ent_coef * last_entropy + args.vf_coef * last_v_loss

                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(agent.parameters(), args.max_grad_norm)
                optimizer.step()

        writer.add_scalar("charts/learning_rate", optimizer.param_groups[0]["lr"], global_step)
        writer.add_scalar("charts/update", update, global_step)
        writer.add_scalar("losses/value_loss", float(last_v_loss.item()), global_step)
        writer.add_scalar("losses/policy_loss", float(last_pg_loss.item()), global_step)
        writer.add_scalar("losses/entropy", float(last_entropy.item()), global_step)
        writer.add_scalar("losses/approx_kl", float(last_approx_kl.item()), global_step)
        writer.add_scalar("charts/current_ent_coef", float(current_ent_coef), global_step)
        writer.add_scalar("charts/curriculum_phase_id", 0.0 if current_curriculum_phase == "warmup" else (1.0 if current_curriculum_phase == "diverse" else 2.0), global_step)
        writer.add_scalar("shaping/shaping_total_reward_delta", float(activity_shaping_counters["shaping_total_reward_delta"]), global_step)
        writer.add_scalar("charts/sps", int(global_step / max(time.time() - start_time, 1e-6)), global_step)

        logger.info(
            "update=%s/%s global_step=%s lr=%.6g ent_coef=%.6g curriculum_phase=%s sps=%s",
            update,
            num_updates,
            global_step,
            optimizer.param_groups[0]["lr"],
            current_ent_coef,
            current_curriculum_phase,
            int(global_step / max(time.time() - start_time, 1e-6)),
        )

    final_model_path = paths.run_dir / "agent_final.pt"
    torch.save(agent.state_dict(), final_model_path)

    metadata = build_model_metadata(
        args=args,
        run_dir=paths.run_dir,
        obs_shape=obs_shape,
        mapsize=mapsize,
        nvec=nvec,
        branch_sizes=branch_sizes,
        actor_output_channels=actor_output_channels,
        num_envs=envs.num_envs,
        final_model_path=final_model_path,
        saved_checkpoint_steps=saved_checkpoint_steps,
    )
    write_json(paths.model_metadata, metadata)

    final_eval_report: Optional[Dict[str, Any]] = None
    if args.eval_after_checkpoint:
        final_eval_report = run_checkpoint_eval(
            python_exe=sys.executable,
            evaluator_script=evaluator_script,
            checkpoint_path=final_model_path,
            metadata_path=paths.model_metadata,
            output_dir=paths.gate_reports_dir,
            args=args,
            logger=logger,
        )

    visual_eval = run_visual_final_eval(
        args=args,
        logger=logger,
        agent=agent,
        device=device,
    )

    final_eval_status = "not_run"
    final_eval_effective_position_delta_count: Optional[int] = None
    final_eval_actor_level_move_share: Optional[float] = None
    final_eval_no_effect_action_share: Optional[float] = None
    if final_eval_report is not None:
        report_payload = final_eval_report.get("report") if isinstance(final_eval_report.get("report"), dict) else {}
        final_eval_status = str(report_payload.get("status", "eval_error"))
        if "effective_position_delta_count" in report_payload:
            final_eval_effective_position_delta_count = int(report_payload["effective_position_delta_count"])
        if "actor_level_move_share" in report_payload:
            final_eval_actor_level_move_share = float(report_payload["actor_level_move_share"])
        if "no_effect_action_share" in report_payload:
            final_eval_no_effect_action_share = float(report_payload["no_effect_action_share"])

    overshoot_steps = max(0, int(global_step - args.total_timesteps))

    manifest = {
        "schema": "week5_gridnet_manifest.v1",
        "run_id": paths.run_dir.name,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "command": command_line,
        "artifacts": {
            "command_txt": str(paths.command_txt),
            "train_log": str(paths.train_log),
            "run_manifest_json": str(paths.run_manifest),
            "checkpoints_dir": str(paths.checkpoints_dir),
            "model_metadata_json": str(paths.model_metadata),
            "gate_or_eval_reports_dir": str(paths.gate_reports_dir),
            "summary_md": str(paths.summary_md),
            "final_model": str(final_model_path),
        },
        "checkpoint_reports": checkpoint_reports,
        "final_eval_report": final_eval_report,
        "final_eval_status": final_eval_status,
        "final_eval_effective_position_delta_count": final_eval_effective_position_delta_count,
        "final_eval_actor_level_move_share": final_eval_actor_level_move_share,
        "final_eval_no_effect_action_share": final_eval_no_effect_action_share,
        "entropy_schedule": {
            "mode": args.ent_schedule,
            "ent_coef_base": float(args.ent_coef),
            "ent_coef_start": float(args.ent_coef_start),
            "ent_coef_end": float(args.ent_coef_end),
        },
        "curriculum_mode": args.curriculum_mode,
        "phase_boundaries": phase_boundaries,
        "opponent_pool_by_phase": opponent_pool_by_phase,
        "activity_shaping": {
            "enabled": bool(args.activity_shaping),
            "shape_move_reward": float(args.shape_move_reward),
            "shape_produce_reward": float(args.shape_produce_reward),
            "shape_noop_penalty": float(args.shape_noop_penalty),
            "shape_no_effect_penalty": float(args.shape_no_effect_penalty),
            "counters": activity_shaping_counters,
        },
        "tensorboard_status": tensorboard_status,
        "tensorboard_error": tensorboard_error,
        "tb_log_dir": str(tb_log_dir),
        "global_step_reached": int(global_step),
        "initial_global_step": int(args.initial_global_step),
        "remaining_timesteps_planned": int(remaining_timesteps),
        "resume_from_checkpoint": str(args.resume_from_checkpoint) if args.resume_from_checkpoint is not None else None,
        "resume_model_metadata": str(args.resume_model_metadata) if args.resume_model_metadata is not None else None,
        "resume_metadata_schema": (resume_metadata or {}).get("schema") if resume_metadata else None,
        "overshoot_steps": int(overshoot_steps),
        "render_window_enabled": bool(args.render_window),
        "visual_eval_attempted": bool(visual_eval.get("visual_eval_attempted", False)),
        "visual_eval_status": str(visual_eval.get("visual_eval_status", "unavailable")),
        "visual_eval_steps": int(visual_eval.get("visual_eval_steps", 0)),
        "visual_eval_opponent": visual_eval.get("visual_eval_opponent"),
        "visual_eval_checkpoint_or_final_model": visual_eval.get("visual_eval_checkpoint_or_final_model"),
        "visual_eval_note": visual_eval.get("note"),
        "save_visual_notes": bool(args.save_visual_notes),
    }
    write_json(paths.run_manifest, manifest)

    pass_count = 0
    for report in checkpoint_reports:
        r = report.get("report") if isinstance(report.get("report"), dict) else None
        status = (r or {}).get("status", "")
        if status == "PASS":
            pass_count += 1

    summary_lines = [
        "# Gridnet Teacher Run Summary",
        "",
        f"- run_id: {paths.run_dir.name}",
        f"- created_utc: {datetime.now(timezone.utc).isoformat()}",
        f"- total_timesteps_target: {args.total_timesteps}",
        f"- global_step_reached: {global_step}",
        f"- initial_global_step: {args.initial_global_step}",
        f"- remaining_timesteps_planned: {remaining_timesteps}",
        f"- overshoot_steps: {overshoot_steps}",
        f"- resume_from_checkpoint: {args.resume_from_checkpoint}",
        f"- resume_model_metadata: {args.resume_model_metadata}",
        f"- map_path: {args.map_path}",
        f"- observation_shape: {list(obs_shape)}",
        f"- action_nvec: {nvec}",
        f"- checkpoints_saved: {saved_checkpoint_steps}",
        f"- checkpoint_eval_reports: {len(checkpoint_reports)}",
        f"- checkpoint_eval_pass_count: {pass_count}",
        f"- final_model_saved: {final_model_path.is_file()}",
        f"- final_eval_status: {final_eval_status}",
        f"- final_eval_effective_position_delta_count: {final_eval_effective_position_delta_count}",
        f"- final_eval_actor_level_move_share: {final_eval_actor_level_move_share}",
        f"- final_eval_no_effect_action_share: {final_eval_no_effect_action_share}",
        f"- ent_schedule: {args.ent_schedule}",
        f"- ent_coef_base: {args.ent_coef}",
        f"- ent_coef_start: {args.ent_coef_start}",
        f"- ent_coef_end: {args.ent_coef_end}",
        f"- curriculum_mode: {args.curriculum_mode}",
        f"- phase_boundaries: {phase_boundaries}",
        f"- opponent_pool_by_phase: {opponent_pool_by_phase}",
        f"- activity_shaping_enabled: {bool(args.activity_shaping)}",
        f"- activity_shaping_applied: {bool(activity_shaping_counters.get('shaping_applied', False))}",
        f"- shaping_counters: {activity_shaping_counters}",
        f"- tensorboard_status: {tensorboard_status}",
        f"- tensorboard_error: {tensorboard_error}",
        f"- tb_log_dir: {tb_log_dir}",
        f"- render_window_enabled: {bool(args.render_window)}",
        f"- visual_eval_attempted: {bool(visual_eval.get('visual_eval_attempted', False))}",
        f"- visual_eval_status: {visual_eval.get('visual_eval_status', 'unavailable')}",
        f"- visual_eval_steps: {int(visual_eval.get('visual_eval_steps', 0))}",
        "",
        "## Visual Sanity",
        f"- render_window_enabled: {bool(args.render_window)}",
        f"- visual_eval_attempted: {bool(visual_eval.get('visual_eval_attempted', False))}",
        f"- visual_eval_status: {visual_eval.get('visual_eval_status', 'unavailable')}",
        "- note: visual check is human-readable sanity layer only",
        "",
        "## Compatibility Notes",
        "- This run is project-compatible by surface/discipline, not by direct Unity checkpoint loading.",
        "- No reference branch weights were imported.",
        "- No Unity-side or BC pipeline files were modified.",
    ]
    if args.save_visual_notes and visual_eval.get("note"):
        summary_lines.insert(summary_lines.index("## Compatibility Notes"), f"- visual_note: {visual_eval['note']}")
    paths.summary_md.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    logger.info("Training finished. Final model: %s", final_model_path)
    logger.info("Run summary: %s", paths.summary_md)

    envs.close()
    writer.close()


if __name__ == "__main__":
    main()
