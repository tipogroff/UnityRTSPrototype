#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import random
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from stable_baselines3.common.vec_env import VecEnvWrapper

from run_teacher_rollout import RolloutError, build_environment, import_runtime_modules, seed_process
from train_teacher_smoke import (
    build_policy_configuration,
    build_seed_bundle,
    wrap_legacy_vec_env_for_sb3_with_options,
)


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
    unique_sorted = sorted(set(values))
    if not unique_sorted:
        raise ValueError("checkpoint schedule is empty after normalization")
    if unique_sorted[-1] != total_timesteps:
        unique_sorted.append(total_timesteps)
    return unique_sorted


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Behavior-first teacher retraining with mandatory gate per checkpoint."
    )
    p.add_argument("--total-timesteps", type=int, default=20000)
    p.add_argument("--checkpoint-steps", default="5000,10000,20000,50000")
    p.add_argument(
        "--curriculum-mode",
        choices=("none", "movement_warmup", "economy_warmup", "mixed"),
        default="none",
    )
    p.add_argument("--seed", type=int, default=170)
    p.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    p.add_argument("--opponent-pool", default="coacAI,workerRushAI,lightRushAI,passiveAI")
    p.add_argument("--opponent-sampling", choices=("static", "per_reset", "per_episode"), default="per_episode")
    p.add_argument("--device", default="cpu")
    p.add_argument("--output-dir", type=Path, default=Path("WEEK5R/retraining_runs"))
    p.add_argument("--gate-output-dir", type=Path, default=Path("WEEK5R/gate_runs"))

    p.add_argument("--force-mask-aware", action="store_true")
    p.add_argument("--allow-non-mask-aware", action="store_true", default=False)

    p.add_argument("--activity-shaping", action="store_true", default=False)
    p.add_argument("--shape-move-reward", type=float, default=0.01)
    p.add_argument("--shape-noop-penalty", type=float, default=0.001)
    p.add_argument("--shape-no-effect-penalty", type=float, default=0.002)
    p.add_argument(
        "--shape-reward-only-move-action",
        dest="shape_reward_only_move_action",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "If true, shape_move_reward is applied only when a ready movable actor selects Move "
            "and position delta is observed."
        ),
    )
    p.add_argument(
        "--shape-no-effect-ready-action-only",
        dest="shape_no_effect_ready_action_only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "If true, no_effect_penalty is applied only when a ready actor selects non-NoOp "
            "and no position delta is observed."
        ),
    )

    p.add_argument("--make-replay", action="store_true")
    p.add_argument("--replay-steps", type=int, default=150)

    p.add_argument("--episodes-gate", type=int, default=4)
    p.add_argument("--max-steps-gate", type=int, default=256)
    p.add_argument("--effective-steps-gate", type=int, default=100)

    p.add_argument("--env-id", default="MicrortsSelfPlayShapedReward-v1")
    p.add_argument("--num-bot-envs", type=int, default=4)
    p.add_argument("--backend-mode", choices=("allow_fallback", "preferred_only"), default="allow_fallback")
    p.add_argument("--force-legacy-backend", action="store_true")

    p.add_argument("--learning-rate", type=float, default=3e-4)
    p.add_argument("--n-steps", type=int, default=128)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--n-epochs", type=int, default=4)
    p.add_argument("--gamma", type=float, default=0.99)
    p.add_argument("--policy", choices=("MlpPolicy", "CnnPolicy"), default=None)
    p.add_argument("--policy-architecture", choices=("cnn_preferred", "mlp_fallback"), default="cnn_preferred")

    p.add_argument(
        "--min-abort-step",
        type=int,
        default=5000,
        help=(
            "Abort rules are suppressed for checkpoints whose step <= min_abort_step. "
            "Gate still runs and FAIL is still recorded; the run simply continues. "
            "Default: 5000."
        ),
    )
    p.add_argument(
        "--collect-all-checkpoints",
        action="store_true",
        default=False,
        help=(
            "If set, the run never aborts early regardless of gate results. "
            "All checkpoints are evaluated; run_status becomes completed_with_failures "
            "when any checkpoint fails. export_eligible remains False for failed checkpoints."
        ),
    )

    raw_argv = list(sys.argv[1:])
    args = p.parse_args(raw_argv)
    movement_notes = _apply_curriculum_defaults(args, raw_argv)
    setattr(args, "_movement_warmup_notes", movement_notes)
    return args


def _arg_present(raw_argv: List[str], name: str) -> bool:
    return any(token == name or token.startswith(f"{name}=") for token in raw_argv)


def _apply_curriculum_defaults(args: argparse.Namespace, raw_argv: List[str]) -> List[str]:
    notes: List[str] = []
    if args.curriculum_mode != "movement_warmup":
        return notes

    if not _arg_present(raw_argv, "--opponent-pool"):
        args.opponent_pool = "passiveAI"
        notes.append("movement_warmup default: opponent_pool=passiveAI")
    if not _arg_present(raw_argv, "--opponent-sampling"):
        args.opponent_sampling = "static"
        notes.append("movement_warmup default: opponent_sampling=static")
    if not _arg_present(raw_argv, "--checkpoint-steps"):
        args.checkpoint_steps = "2000,5000,10000,20000"
        notes.append("movement_warmup default: checkpoint_steps=2000,5000,10000,20000")
    if not _arg_present(raw_argv, "--total-timesteps"):
        args.total_timesteps = 20000
        notes.append("movement_warmup default: total_timesteps=20000")
    return notes


def _extract_teacher_positions(obs_batch: np.ndarray) -> List[set[Tuple[int, int]]]:
    if obs_batch.ndim != 4 or obs_batch.shape[-1] < 21:
        batch = int(obs_batch.shape[0]) if obs_batch.ndim > 0 else 1
        return [set() for _ in range(batch)]

    positions_per_env: List[set[Tuple[int, int]]] = []
    for env_idx in range(obs_batch.shape[0]):
        obs = obs_batch[env_idx]
        owner_self = obs[:, :, 11] > 0.5
        unit_present = np.max(obs[:, :, 13:21], axis=2) > 0.1
        teacher_units = np.logical_and(owner_self, unit_present)
        ys, xs = np.where(teacher_units)
        positions_per_env.append(set((int(x), int(y)) for y, x in zip(ys.tolist(), xs.tolist())))
    return positions_per_env


def _reshape_actions_to_cells(actions: np.ndarray, num_envs: int) -> Optional[np.ndarray]:
    arr = np.asarray(actions)
    if arr.ndim == 1 and num_envs == 1:
        arr = np.expand_dims(arr, axis=0)
    if arr.ndim == 2 and arr.shape[1] % 7 == 0:
        return arr.reshape(arr.shape[0], arr.shape[1] // 7, 7)
    if arr.ndim == 3 and arr.shape[2] == 7:
        return arr
    return None


def _try_read_action_mask(env: Any) -> Optional[np.ndarray]:
    candidate = None
    if hasattr(env, "action_masks"):
        try:
            maybe = getattr(env, "action_masks")
            candidate = maybe() if callable(maybe) else maybe
        except Exception:
            candidate = None
    if candidate is None and hasattr(env, "get_action_mask"):
        try:
            candidate = env.get_action_mask()
        except Exception:
            candidate = None
    if candidate is None:
        return None
    arr = np.asarray(candidate)
    if arr.ndim == 2:
        arr = np.expand_dims(arr, axis=0)
    if arr.ndim != 3:
        return None
    return arr


class ActivityShapingVecEnv(VecEnvWrapper):
    def __init__(
        self,
        venv: Any,
        *,
        move_reward: float,
        noop_penalty: float,
        no_effect_penalty: float,
        reward_only_move_action: bool,
        no_effect_ready_action_only: bool,
    ) -> None:
        super().__init__(venv)
        self._move_reward = float(move_reward)
        self._noop_penalty = float(noop_penalty)
        self._no_effect_penalty = float(no_effect_penalty)
        self._reward_only_move_action = bool(reward_only_move_action)
        self._no_effect_ready_action_only = bool(no_effect_ready_action_only)
        self._last_obs: Optional[np.ndarray] = None
        self._last_mask: Optional[np.ndarray] = None
        self._last_actions: Optional[np.ndarray] = None
        self._noop_streak = np.zeros(self.num_envs, dtype=np.int32)
        self._event_counts: Dict[str, int] = {
            "position_delta_steps_total": 0,
            "move_reward_events_total": 0,
            "move_action_on_ready_actor_events": 0,
            "move_action_position_delta_events": 0,
            "nonmove_position_delta_events": 0,
            "noop_with_ready_movable_events": 0,
            "repeated_noop_penalty_events": 0,
            "ready_actor_nonnoop_steps": 0,
            "no_effect_ready_action_events": 0,
            "no_effect_penalty_events": 0,
            "action_decode_skipped_steps": 0,
        }

    def action_masks(self) -> Any:
        if hasattr(self.venv, "action_masks"):
            return self.venv.action_masks()
        raise RolloutError("activity shaping wrapper requires action_masks support on wrapped VecEnv")

    def get_event_counts(self) -> Dict[str, int]:
        return dict(self._event_counts)

    def reset(self) -> np.ndarray:
        obs = np.asarray(self.venv.reset())
        self._last_obs = obs
        self._last_mask = _try_read_action_mask(self.venv)
        self._last_actions = None
        self._noop_streak[:] = 0
        return obs

    def step_async(self, actions: np.ndarray) -> None:
        self._last_actions = np.asarray(actions)
        self.venv.step_async(actions)

    def step_wait(self):
        obs, rewards, dones, infos = self.venv.step_wait()
        obs_arr = np.asarray(obs)
        rew_arr = np.asarray(rewards, dtype=np.float32).reshape(self.num_envs)
        done_arr = np.asarray(dones, dtype=bool).reshape(self.num_envs)

        if self._last_obs is not None and self._last_mask is not None and self._last_actions is not None:
            actions_cells = _reshape_actions_to_cells(self._last_actions, self.num_envs)
            if actions_cells is None:
                self._event_counts["action_decode_skipped_steps"] += int(self.num_envs)
            else:
                pos_before = _extract_teacher_positions(np.asarray(self._last_obs))
                pos_after = _extract_teacher_positions(obs_arr)
                mask_prev = self._last_mask

                for env_idx in range(self.num_envs):
                    if env_idx >= mask_prev.shape[0]:
                        continue
                    source_mask = mask_prev[env_idx, :, 0] > 0
                    move_allowed = mask_prev[env_idx, :, 2] > 0
                    ready_movable = np.logical_and(source_mask, move_allowed)
                    has_ready_movable = bool(np.any(ready_movable))

                    action_env = actions_cells[env_idx]
                    n_cells = min(action_env.shape[0], ready_movable.shape[0])
                    act_type = action_env[:n_cells, 0]
                    ready_slice = ready_movable[:n_cells]
                    chose_nonnoop_ready = bool(np.any(np.logical_and(ready_slice, act_type != 0)))
                    chose_move_on_ready = bool(np.any(np.logical_and(ready_slice, act_type == 1)))
                    chose_all_noop_ready = bool(has_ready_movable and not chose_nonnoop_ready)
                    self._event_counts["ready_actor_nonnoop_steps"] += int(chose_nonnoop_ready)
                    self._event_counts["move_action_on_ready_actor_events"] += int(chose_move_on_ready)
                    self._event_counts["noop_with_ready_movable_events"] += int(chose_all_noop_ready)

                    pos_delta = pos_before[env_idx] != pos_after[env_idx]
                    self._event_counts["position_delta_steps_total"] += int(pos_delta)
                    if pos_delta and chose_move_on_ready:
                        self._event_counts["move_action_position_delta_events"] += 1
                    elif pos_delta:
                        self._event_counts["nonmove_position_delta_events"] += 1

                    reward_pos_delta = pos_delta and (
                        chose_move_on_ready if self._reward_only_move_action else True
                    )
                    if reward_pos_delta:
                        rew_arr[env_idx] += self._move_reward
                        self._event_counts["move_reward_events_total"] += 1

                    if chose_all_noop_ready:
                        self._noop_streak[env_idx] += 1
                        if self._noop_streak[env_idx] > 1:
                            rew_arr[env_idx] -= self._noop_penalty
                            self._event_counts["repeated_noop_penalty_events"] += 1
                    else:
                        self._noop_streak[env_idx] = 0

                    no_effect_ready_action = chose_nonnoop_ready and not pos_delta
                    self._event_counts["no_effect_ready_action_events"] += int(no_effect_ready_action)
                    if self._no_effect_ready_action_only:
                        penalize_no_effect = no_effect_ready_action
                    else:
                        penalize_no_effect = has_ready_movable and not pos_delta

                    if penalize_no_effect:
                        rew_arr[env_idx] -= self._no_effect_penalty
                        self._event_counts["no_effect_penalty_events"] += 1

                    if done_arr[env_idx]:
                        self._noop_streak[env_idx] = 0

        self._last_obs = obs_arr
        self._last_mask = _try_read_action_mask(self.venv)
        return obs_arr, rew_arr, done_arr, infos


def _read_action_mask_with_source(env_for_training: Any) -> Tuple[Optional[np.ndarray], Optional[str], Optional[str]]:
    candidate = None
    source = None
    error = None

    if hasattr(env_for_training, "get_action_mask"):
        try:
            candidate = env_for_training.get_action_mask()
            if candidate is not None:
                source = "env.get_action_mask"
        except Exception as exc:
            error = f"env.get_action_mask failed: {type(exc).__name__}: {exc}"

    if candidate is None and hasattr(env_for_training, "action_masks"):
        try:
            action_masks_attr = getattr(env_for_training, "action_masks")
            candidate = action_masks_attr() if callable(action_masks_attr) else action_masks_attr
            if candidate is not None:
                source = "env.action_masks"
        except Exception as exc:
            error = f"env.action_masks failed: {type(exc).__name__}: {exc}"

    if candidate is None:
        return None, source, error
    try:
        return np.asarray(candidate), source, error
    except Exception as exc:
        return None, source, f"np.asarray(mask) failed: {type(exc).__name__}: {exc}"


def _quick_mask_preflight_or_raise(env_for_training: Any, *, sample_steps: int = 12) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "mask_available": False,
        "mask_shape": None,
        "mask_dtype": None,
        "source_unit_mask_nonzero_steps": 0,
        "ready_movable_actor_choice_count": 0,
        "move_allowed_count": 0,
        "steps_with_move_valid": 0,
        "warnings": [],
        "mask_source": None,
    }

    has_method = hasattr(env_for_training, "action_masks") or hasattr(env_for_training, "get_action_mask")
    if not has_method:
        raise RolloutError(
            "Preflight mask sanity failed: env_for_training exposes neither action_masks nor get_action_mask. "
            "MaskablePPO requires valid action masks."
        )

    steps_to_run = max(10, min(int(sample_steps), 50))
    num_envs = int(getattr(env_for_training, "num_envs", 1) or 1)

    def _sample_action_batch() -> np.ndarray:
        sampled = np.asarray(env_for_training.action_space.sample())
        if sampled.ndim == 1 and num_envs > 1:
            return np.repeat(sampled[np.newaxis, :], num_envs, axis=0)
        return sampled

    try:
        env_for_training.reset()
    except Exception:
        pass

    for _ in range(steps_to_run):
        mask, source, error = _read_action_mask_with_source(env_for_training)
        if summary["mask_source"] is None and source is not None:
            summary["mask_source"] = source
        if error:
            summary["warnings"].append(error)

        if mask is None:
            raise RolloutError(
                "Preflight mask sanity failed: action mask is missing or unreadable from env_for_training."
            )

        summary["mask_available"] = True
        summary["mask_shape"] = list(mask.shape)
        summary["mask_dtype"] = str(mask.dtype)

        if mask.ndim != 3 or mask.shape[2] < 3:
            raise RolloutError(
                f"Preflight mask sanity failed: invalid mask shape {tuple(mask.shape)}; expected [num_envs, n_cells, >=3]."
            )

        source_mask = mask[:, :, 0] > 0
        move_allowed = mask[:, :, 2] > 0
        summary["source_unit_mask_nonzero_steps"] += int(np.any(source_mask))
        summary["ready_movable_actor_choice_count"] += int(np.logical_and(source_mask, move_allowed).sum())
        summary["move_allowed_count"] += int(move_allowed.sum())
        summary["steps_with_move_valid"] += int(np.any(np.logical_and(source_mask, move_allowed)))

        random_action = _sample_action_batch()
        env_for_training.step(random_action)

    try:
        env_for_training.reset()
    except Exception:
        pass

    if not summary["mask_available"]:
        raise RolloutError("Preflight mask sanity failed: mask_available=False")

    return summary


def load_gate_json(gate_step_dir: Path, checkpoint_path: Path) -> Dict[str, Any]:
    gate_path = gate_step_dir / f"gate_{checkpoint_path.stem}.json"
    if gate_path.is_file():
        return json.loads(gate_path.read_text(encoding="utf-8"))

    candidates = sorted(gate_step_dir.glob("gate_*.json"))
    if len(candidates) == 1:
        return json.loads(candidates[0].read_text(encoding="utf-8"))
    if len(candidates) > 1:
        raise RuntimeError(
            f"Multiple gate JSON files found in {gate_step_dir}: {[p.name for p in candidates]}"
        )
    raise RuntimeError(f"Gate JSON not found: {gate_path}")


def evaluate_checkpoint(gate_data: Dict[str, Any], checkpoint_step: int) -> Dict[str, Any]:
    status = str(gate_data.get("status", "UNKNOWN"))
    actor = gate_data.get("actor_level", {})
    eff = gate_data.get("effective_behavior", {})
    replay = gate_data.get("visual_replay", {})

    actor_move = float(actor.get("actor_level_move_share", 0.0) or 0.0)
    actor_noop = float(actor.get("actor_noop_share", 0.0) or 0.0)
    ready_movable_choices = int(actor.get("ready_movable_actor_choice_count", 0) or 0)
    pos_delta = int(eff.get("effective_position_delta_count", 0) or 0)
    no_effect = float(eff.get("no_effect_action_share", 0.0) or 0.0)
    visual_verdict = str(replay.get("visual_verdict", "n/a") or "n/a")

    abort_reasons: List[str] = []
    if actor_move == 0.0 and ready_movable_choices > 0:
        abort_reasons.append("actor_level_move_share==0 with ready_movable_actor_choice_count>0")
    if pos_delta == 0:
        abort_reasons.append("effective_position_delta_count==0")
    if no_effect > 0.80:
        abort_reasons.append("no_effect_action_share>0.80")

    continue_ok = (not status.startswith("FAIL")) and (actor_move > 0.0) and (pos_delta > 0)
    candidate_ok = (
        status == "PASS"
        and actor_move >= 0.05
        and actor_noop < 0.75
        and visual_verdict != "visually_passive"
    )
    movement_warmup_success = (actor_move > 0.0) and (pos_delta > 0) and (no_effect < 1.0)

    return {
        "checkpoint_step": checkpoint_step,
        "status": status,
        "actor_level_move_share": actor_move,
        "actor_noop_share": actor_noop,
        "ready_movable_actor_choice_count": ready_movable_choices,
        "effective_position_delta_count": pos_delta,
        "no_effect_action_share": no_effect,
        "visual_verdict": visual_verdict,
        "abort_reasons": abort_reasons,
        "continue_ok": continue_ok,
        "candidate_ok": candidate_ok,
        "movement_warmup_success": movement_warmup_success,
        "export_eligible": candidate_ok,
    }


def run_gate_for_checkpoint(
    checkpoint_path: Path,
    args: argparse.Namespace,
    gate_step_dir: Path,
) -> Tuple[int, Dict[str, Any], List[str]]:
    gate_script = Path(__file__).resolve().parent / "teacher_behavior_gate.py"
    gate_sampling_mode = "static" if args.opponent_sampling == "static" else "per_episode"
    cmd: List[str] = [
        sys.executable,
        str(gate_script),
        "--checkpoint",
        str(checkpoint_path),
        "--episodes",
        str(args.episodes_gate),
        "--max-steps",
        str(args.max_steps_gate),
        "--effective-steps",
        str(args.effective_steps_gate),
        "--seed",
        str(args.seed),
        "--map-path",
        args.map_path,
        "--opponent-pool",
        args.opponent_pool,
        "--opponent-sampling",
        gate_sampling_mode,
        "--device",
        args.device,
        "--output-dir",
        str(gate_step_dir),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    output_lines = [line for line in (proc.stdout + "\n" + proc.stderr).splitlines() if line.strip()]
    try:
        data = load_gate_json(gate_step_dir, checkpoint_path)
    except Exception as exc:
        tail = "\n".join(output_lines[-40:])
        raise RuntimeError(
            f"Gate artifacts unavailable for {checkpoint_path.name} (return code {proc.returncode}).\n"
            f"Root error: {type(exc).__name__}: {exc}\n"
            f"Gate logs tail:\n{tail}"
        ) from exc

    return proc.returncode, data, output_lines


def run_replay_for_checkpoint(
    checkpoint_path: Path,
    args: argparse.Namespace,
    replay_step_dir: Path,
    checkpoint_env_version: str,
) -> Tuple[int, List[str]]:
    rollout_script = Path(__file__).resolve().parent / "run_teacher_rollout.py"
    replay_step_dir.mkdir(parents=True, exist_ok=True)

    cmd: List[str] = [
        sys.executable,
        str(rollout_script),
        "--policy-path",
        str(checkpoint_path),
        "--policy-algorithm",
        "ppo",
        "--checkpoint-env-version",
        checkpoint_env_version,
        "--episodes",
        "1",
        "--batch-mode",
        "debug",
        "--batch-label",
        f"behavior_first_step_{checkpoint_path.stem.split('_')[-1]}",
        "--env-id",
        args.env_id,
        "--map-path",
        args.map_path,
        "--opponent-pool",
        args.opponent_pool,
        "--opponent-sampling",
        "static",
        "--seed",
        str(args.seed),
        "--device",
        args.device,
        "--output-dir",
        str(replay_step_dir),
        "--rollout-step-limit",
        str(args.replay_steps),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    output_lines = [line for line in (proc.stdout + "\n" + proc.stderr).splitlines() if line.strip()]
    return int(proc.returncode), output_lines


def run_compare(gate_jsons: List[Path], output_md: Path) -> Tuple[int, str]:
    compare_script = Path(__file__).resolve().parent / "compare_teacher_behavior_gates.py"
    cmd: List[str] = [sys.executable, str(compare_script)] + [str(p) for p in gate_jsons] + [
        "--output-md",
        str(output_md),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    merged_output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return proc.returncode, merged_output


def write_results_md(
    output_path: Path,
    run_id: str,
    run_status: str,
    run_notes: List[str],
    records: List[Dict[str, Any]],
    compare_md_path: Path,
    retraining_dir: Path,
    gate_dir: Path,
    min_abort_step: int = 5000,
    collect_all_checkpoints: bool = False,
    abort_suppressed_count: int = 0,
    checkpoints_failed_count: int = 0,
    checkpoints_passed_count: int = 0,
) -> None:
    lines: List[str] = []
    lines.append("# Teacher Retraining Results")
    lines.append("")
    lines.append(f"- run_id: `{run_id}`")
    lines.append(f"- run_status: `{run_status}`")
    lines.append(f"- retraining_dir: `{retraining_dir}`")
    lines.append(f"- gate_dir: `{gate_dir}`")
    lines.append(f"- gate_comparison_md: `{compare_md_path}`")
    lines.append(f"- min_abort_step: `{min_abort_step}`")
    lines.append(f"- collect_all_checkpoints: `{collect_all_checkpoints}`")
    lines.append(f"- abort_suppressed_count: `{abort_suppressed_count}`")
    lines.append(f"- checkpoints_failed: `{checkpoints_failed_count}`  checkpoints_passed: `{checkpoints_passed_count}`")
    lines.append("")

    if run_notes:
        lines.append("## Run Notes")
        for note in run_notes:
            lines.append(f"- {note}")
        lines.append("")

    lines.append("## Checkpoint Gate Summary")
    lines.append("| step | status | actor_move | actor_noop | pos_delta | no_effect | continue_ok | candidate_ok | visual_verdict |")
    lines.append("|---|---|---:|---:|---:|---:|---|---|---|")
    for rec in records:
        lines.append(
            f"| {rec['checkpoint_step']} | {rec['status']} | {rec['actor_level_move_share']:.4f} | "
            f"{rec['actor_noop_share']:.4f} | {rec['effective_position_delta_count']} | "
            f"{rec['no_effect_action_share']:.4f} | {rec['continue_ok']} | {rec['candidate_ok']} | {rec['visual_verdict']} |"
        )

    lines.append("")
    lines.append("## Abort Policy")
    lines.append(f"- Abort suppressed for checkpoint_step <= min_abort_step ({min_abort_step})")
    if collect_all_checkpoints:
        lines.append("- `--collect-all-checkpoints` active: abort never triggered regardless of gate results")
    lines.append("- Hard abort triggers (when not suppressed):")
    lines.append("  - FAIL_COLLAPSED_NOOP at 5k and 10k consecutively")
    lines.append("  - actor_level_move_share == 0 while ready_movable_actor_choice_count > 0")
    lines.append("  - effective_position_delta_count == 0")
    lines.append("  - no_effect_action_share > 0.80")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def train_behavior_first(args: argparse.Namespace) -> int:
    if args.allow_non_mask_aware:
        raise RolloutError(
            "--allow-non-mask-aware is not supported in behavior-first mode. "
            "MaskablePPO is mandatory for this script."
        )

    if not args.force_mask_aware:
        # Behavior-first always enforces mask-aware path.
        args.force_mask_aware = True

    movement_warmup_notes: List[str] = list(getattr(args, "_movement_warmup_notes", []))

    checkpoint_steps = parse_checkpoint_steps(args.checkpoint_steps, args.total_timesteps)
    run_id = f"behavior_first_{utc_stamp()}"

    retraining_run_dir = args.output_dir / run_id
    gate_run_dir = args.gate_output_dir / run_id
    checkpoints_dir = retraining_run_dir / "checkpoints"
    retraining_run_dir.mkdir(parents=True, exist_ok=True)
    gate_run_dir.mkdir(parents=True, exist_ok=True)
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    modules, versions = import_runtime_modules()
    if modules.get("stable_baselines3") is None:
        raise RolloutError("Stable-Baselines3 is not available.")

    try:
        from sb3_contrib import MaskablePPO
    except Exception as exc:
        raise RolloutError("MaskablePPO is required but unavailable (no PPO fallback allowed).") from exc

    seed_bundle = build_seed_bundle(argparse.Namespace(seed=args.seed, env_seed=None, rollout_seed=None))
    seed_process(seed_bundle, modules)

    env_args = argparse.Namespace(
        env_id=args.env_id,
        map_path=args.map_path,
        rollout_step_limit=2000,
        num_bot_envs=args.num_bot_envs,
        backend_mode=args.backend_mode,
        force_legacy_backend=args.force_legacy_backend,
        opponent_pool=args.opponent_pool,
        opponent_sampling=args.opponent_sampling,
        opponent_seed=args.seed + 100,
        seed=args.seed,
    )

    logger = logging.getLogger("train_teacher_behavior_first")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(logging.StreamHandler(sys.stdout))

    env, initial_observation, reset_info, env_summary = build_environment(
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

    shaping_env: Optional[ActivityShapingVecEnv] = None
    if args.activity_shaping:
        shaping_env = ActivityShapingVecEnv(
            env_for_training,
            move_reward=args.shape_move_reward,
            noop_penalty=args.shape_noop_penalty,
            no_effect_penalty=args.shape_no_effect_penalty,
            reward_only_move_action=args.shape_reward_only_move_action,
            no_effect_ready_action_only=args.shape_no_effect_ready_action_only,
        )
        env_for_training = shaping_env

    policy_class, policy_kwargs, policy_summary = build_policy_configuration(args, modules, env_for_training)
    model = MaskablePPO(
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

    preflight = _quick_mask_preflight_or_raise(env_for_training, sample_steps=12)
    if preflight["ready_movable_actor_choice_count"] == 0:
        print(
            "[behavior-first] WARNING preflight: ready_movable_actor_choice_count==0 across sampled steps; "
            "training may remain passive."
        )
    if preflight["move_allowed_count"] == 0:
        print(
            "[behavior-first] WARNING preflight: move_allowed_count==0 across sampled steps; "
            "check action-mask semantics."
        )
    print(
        "[behavior-first] preflight mask: source={} shape={} dtype={} source_nonzero_steps={} ready_movable={} move_allowed={}".format(
            preflight.get("mask_source"),
            preflight.get("mask_shape"),
            preflight.get("mask_dtype"),
            preflight.get("source_unit_mask_nonzero_steps"),
            preflight.get("ready_movable_actor_choice_count"),
            preflight.get("move_allowed_count"),
        )
    )

    print(f"[behavior-first] run_id={run_id}")
    print(f"[behavior-first] checkpoints={checkpoint_steps}")
    print(f"[behavior-first] policy={policy_summary.get('policy_class')}")
    print(f"[behavior-first] mask backend=sb3_contrib.MaskablePPO")
    print(f"[behavior-first] curriculum_mode={args.curriculum_mode}")
    print(f"[behavior-first] activity_shaping={args.activity_shaping}")
    if args.activity_shaping:
        print(
            "[behavior-first] shaping config: move_reward={:.4f} noop_penalty={:.4f} no_effect_penalty={:.4f} reward_only_move_action={} no_effect_ready_action_only={}".format(
                args.shape_move_reward,
                args.shape_noop_penalty,
                args.shape_no_effect_penalty,
                args.shape_reward_only_move_action,
                args.shape_no_effect_ready_action_only,
            )
        )
    print(f"[behavior-first] min_abort_step={args.min_abort_step}  (abort suppressed for steps below this)")
    print(f"[behavior-first] collect_all_checkpoints={args.collect_all_checkpoints}")
    for note in movement_warmup_notes:
        print(f"[behavior-first] {note}")

    records: List[Dict[str, Any]] = []
    run_notes: List[str] = []
    gate_json_paths: List[Path] = []

    current_step = 0
    consecutive_fail_5k_10k = False
    abort_suppressed_count = 0
    did_abort = False

    try:
        for target in checkpoint_steps:
            delta = target - current_step
            if delta <= 0:
                continue

            print(f"[behavior-first] train segment: {current_step} -> {target} (+{delta})")
            model.learn(total_timesteps=delta, reset_num_timesteps=False, progress_bar=False)
            current_step = target

            checkpoint_path = checkpoints_dir / f"teacher_sb3_ppo_step_{target:09d}.zip"
            model.save(str(checkpoint_path.with_suffix("")))

            gate_step_dir = gate_run_dir / f"step_{target:09d}"
            gate_step_dir.mkdir(parents=True, exist_ok=True)

            gate_return, gate_data, gate_logs = run_gate_for_checkpoint(checkpoint_path, args, gate_step_dir)
            gate_json_path = gate_step_dir / f"gate_{checkpoint_path.stem}.json"
            gate_json_paths.append(gate_json_path)

            rec = evaluate_checkpoint(gate_data, target)
            rec["checkpoint_path"] = str(checkpoint_path)
            rec["gate_json_path"] = str(gate_json_path)
            rec["gate_return_code"] = int(gate_return)
            rec["gate_logs_tail"] = gate_logs[-10:]

            if args.make_replay:
                replay_dir = gate_step_dir / "replay"
                checkpoint_env_version = versions.microrts_version or "0.0.0"
                replay_return, replay_logs = run_replay_for_checkpoint(
                    checkpoint_path=checkpoint_path,
                    args=args,
                    replay_step_dir=replay_dir,
                    checkpoint_env_version=checkpoint_env_version,
                )
                rec["replay_return_code"] = int(replay_return)
                rec["replay_logs_tail"] = replay_logs[-10:]
                if replay_return != 0:
                    run_notes.append(
                        f"Replay subprocess failed at step {target} with exit_code={replay_return}"
                    )

            records.append(rec)

            print(
                "[behavior-first] gate step={} status={} actor_move={:.4f} pos_delta={} no_effect={:.4f}".format(
                    target,
                    rec["status"],
                    rec["actor_level_move_share"],
                    rec["effective_position_delta_count"],
                    rec["no_effect_action_share"],
                )
            )
            if args.curriculum_mode == "movement_warmup":
                print(
                    f"[behavior-first] movement_warmup_success step={target}: {rec['movement_warmup_success']}"
                )

            abort_reasons = list(rec["abort_reasons"])
            if rec["status"] == "FAIL_COLLAPSED_NOOP" and target in (5000, 10000):
                if target == 10000:
                    prior_5k = next((r for r in records if r["checkpoint_step"] == 5000), None)
                    if prior_5k and prior_5k.get("status") == "FAIL_COLLAPSED_NOOP":
                        consecutive_fail_5k_10k = True
                        abort_reasons.append("FAIL_COLLAPSED_NOOP at 5k and 10k consecutively")

            if abort_reasons:
                step_below_min = target <= args.min_abort_step
                suppress = step_below_min or args.collect_all_checkpoints
                if suppress:
                    suppress_reason = (
                        f"checkpoint_step {target} <= min_abort_step {args.min_abort_step}"
                        if step_below_min
                        else "collect_all_checkpoints=True"
                    )
                    note = (
                        f"Abort suppressed at step {target} ({suppress_reason}): "
                        f"{'; '.join(abort_reasons)} — continuing to next checkpoint."
                    )
                    run_notes.append(note)
                    print(f"[behavior-first] {note}")
                    abort_suppressed_count += 1
                else:
                    run_notes.append(f"Abort at step {target}: {'; '.join(abort_reasons)}")
                    did_abort = True
                    break

        final_model_path = retraining_run_dir / "teacher_sb3_ppo_behavior_first_last.zip"
        model.save(str(final_model_path.with_suffix("")))

    finally:
        try:
            env.close()
        except Exception:
            pass

    compare_md_path = gate_run_dir / "TEACHER_BEHAVIOR_GATE_COMPARISON.md"
    compare_code = -1
    compare_output = ""
    if gate_json_paths:
        compare_code, compare_output = run_compare(gate_json_paths, compare_md_path)
        run_notes.append(f"compare_teacher_behavior_gates.py exit_code={compare_code}")
        if compare_output.strip():
            run_notes.append("comparison tool output captured")

    checkpoints_failed_count = sum(1 for r in records if str(r.get("status", "")).startswith("FAIL"))
    checkpoints_passed_count = sum(1 for r in records if r.get("status") == "PASS")

    if did_abort:
        run_status = "aborted"
    elif checkpoints_failed_count > 0:
        run_status = "completed_with_failures"
    else:
        run_status = "completed"

    run_manifest = {
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": run_status,
        "total_timesteps": args.total_timesteps,
        "checkpoint_steps": checkpoint_steps,
        "min_abort_step": args.min_abort_step,
        "collect_all_checkpoints": args.collect_all_checkpoints,
        "abort_suppressed_count": abort_suppressed_count,
        "checkpoints_failed_count": checkpoints_failed_count,
        "checkpoints_passed_count": checkpoints_passed_count,
        "records": records,
        "retraining_run_dir": str(retraining_run_dir),
        "gate_run_dir": str(gate_run_dir),
        "compare_markdown": str(compare_md_path),
        "runtime_versions": asdict(versions),
        "seed_bundle": asdict(seed_bundle),
        "env_summary": env_summary,
        "preflight_mask_sanity": preflight,
        "curriculum_mode": args.curriculum_mode,
        "activity_shaping_enabled": bool(args.activity_shaping),
        "shaping_config": {
            "shape_move_reward": float(args.shape_move_reward),
            "shape_noop_penalty": float(args.shape_noop_penalty),
            "shape_no_effect_penalty": float(args.shape_no_effect_penalty),
            "shape_reward_only_move_action": bool(args.shape_reward_only_move_action),
            "shape_no_effect_ready_action_only": bool(args.shape_no_effect_ready_action_only),
        },
        "shaping_alignment_mode": {
            "reward_only_move_action": bool(args.shape_reward_only_move_action),
            "no_effect_ready_action_only": bool(args.shape_no_effect_ready_action_only),
        },
        "shaping_event_counts": shaping_env.get_event_counts() if shaping_env is not None else {
            "position_delta_steps_total": 0,
            "move_reward_events_total": 0,
            "move_action_on_ready_actor_events": 0,
            "move_action_position_delta_events": 0,
            "nonmove_position_delta_events": 0,
            "noop_with_ready_movable_events": 0,
            "repeated_noop_penalty_events": 0,
            "ready_actor_nonnoop_steps": 0,
            "no_effect_ready_action_events": 0,
            "no_effect_penalty_events": 0,
            "action_decode_skipped_steps": 0,
        },
        "movement_warmup_notes": movement_warmup_notes,
        "notes": run_notes,
        "consecutive_fail_5k_10k": consecutive_fail_5k_10k,
    }
    manifest_path = retraining_run_dir / "behavior_first_run_manifest.json"
    manifest_path.write_text(json.dumps(run_manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    global_results_path = Path("WEEK5R/TEACHER_RETRAINING_RESULTS.md")
    _write_kwargs = dict(
        run_id=run_id,
        run_status=run_manifest["status"],
        run_notes=run_notes,
        records=records,
        compare_md_path=compare_md_path,
        retraining_dir=retraining_run_dir,
        gate_dir=gate_run_dir,
        min_abort_step=args.min_abort_step,
        collect_all_checkpoints=args.collect_all_checkpoints,
        abort_suppressed_count=abort_suppressed_count,
        checkpoints_failed_count=checkpoints_failed_count,
        checkpoints_passed_count=checkpoints_passed_count,
    )
    write_results_md(output_path=global_results_path, **_write_kwargs)

    per_run_results = retraining_run_dir / "TEACHER_RETRAINING_RESULTS.md"
    write_results_md(output_path=per_run_results, **_write_kwargs)

    print(f"[behavior-first] manifest={manifest_path}")
    print(f"[behavior-first] results={global_results_path}")
    print(f"[behavior-first] run_results={per_run_results}")

    if run_manifest["status"] == "aborted":
        return 2
    return 0


def main() -> int:
    args = parse_args()
    return train_behavior_first(args)


if __name__ == "__main__":
    raise SystemExit(main())
