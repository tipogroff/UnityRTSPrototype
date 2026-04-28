#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


CHECKPOINT_STEPS = "20000,50000,100000"


@dataclass(frozen=True)
class SweepConfig:
    name: str
    total_timesteps: int
    num_bot_envs: int
    num_selfplay_envs: int
    map_path: str
    checkpoint_steps: str
    seed: int
    diagnostic_only: bool
    project_compatible_24x24: bool
    ent_schedule: str
    ent_coef: float
    ent_coef_start: float
    ent_coef_end: float
    curriculum_mode: str
    staged_curriculum: bool
    activity_shaping: bool
    shape_move_reward: float
    shape_produce_reward: float
    shape_noop_penalty: float
    shape_no_effect_penalty: float


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Recipe redesign sweep for Branch B Gridnet teacher. "
            "Focuses on entropy/reward/curriculum interventions after reference parity did not resolve deterministic collapse."
        )
    )
    p.add_argument("--python-exe", type=Path, default=Path(sys.executable))
    p.add_argument("--device", default="cpu")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--total-timesteps", type=int, default=100000)
    p.add_argument("--sweep-id", default=f"gridnet_recipe_redesign_{utc_stamp()}")
    p.add_argument(
        "--output-root",
        type=Path,
        default=Path("WEEK5R/gridnet_recipe_sweeps"),
    )
    p.add_argument(
        "--configs",
        default="A_low_entropy,B_entropy_decay,C_passive_warmup_entropy_decay,D_activity_shaping_mild",
        help="Comma-separated config names to run. Add E_16x16_shaping_diagnostic explicitly if needed.",
    )
    p.add_argument(
        "--skip-training",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Skip training and reuse latest existing artifacts in each config directory.",
    )
    p.add_argument(
        "--run-visual-top-config",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Optionally run visual eval for best ranked completed config.",
    )
    p.add_argument(
        "--stop-on-error",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Stop sweep after first failed config.",
    )
    p.add_argument(
        "--disable-tensorboard",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Disable TensorBoard for sweep training runs to avoid Windows path-length issues.",
    )
    p.add_argument(
        "--tensorboard-root",
        type=Path,
        default=Path("WEEK5R/tb/gridnet_recipe_sweeps"),
        help="Root directory for TensorBoard logs when --no-disable-tensorboard is used.",
    )
    return p.parse_args()


def build_configs(total_timesteps: int, seed: int) -> Dict[str, SweepConfig]:
    configs = [
        SweepConfig(
            name="A_low_entropy",
            total_timesteps=total_timesteps,
            num_bot_envs=24,
            num_selfplay_envs=0,
            map_path="maps/24x24/basesWorkers24x24.xml",
            checkpoint_steps=CHECKPOINT_STEPS,
            seed=seed,
            diagnostic_only=False,
            project_compatible_24x24=True,
            ent_schedule="none",
            ent_coef=0.001,
            ent_coef_start=0.01,
            ent_coef_end=0.0005,
            curriculum_mode="none",
            staged_curriculum=False,
            activity_shaping=False,
            shape_move_reward=0.005,
            shape_produce_reward=0.003,
            shape_noop_penalty=0.0005,
            shape_no_effect_penalty=0.001,
        ),
        SweepConfig(
            name="B_entropy_decay",
            total_timesteps=total_timesteps,
            num_bot_envs=24,
            num_selfplay_envs=0,
            map_path="maps/24x24/basesWorkers24x24.xml",
            checkpoint_steps=CHECKPOINT_STEPS,
            seed=seed,
            diagnostic_only=False,
            project_compatible_24x24=True,
            ent_schedule="linear",
            ent_coef=0.01,
            ent_coef_start=0.01,
            ent_coef_end=0.0005,
            curriculum_mode="none",
            staged_curriculum=False,
            activity_shaping=False,
            shape_move_reward=0.005,
            shape_produce_reward=0.003,
            shape_noop_penalty=0.0005,
            shape_no_effect_penalty=0.001,
        ),
        SweepConfig(
            name="C_passive_warmup_entropy_decay",
            total_timesteps=total_timesteps,
            num_bot_envs=24,
            num_selfplay_envs=0,
            map_path="maps/24x24/basesWorkers24x24.xml",
            checkpoint_steps=CHECKPOINT_STEPS,
            seed=seed,
            diagnostic_only=False,
            project_compatible_24x24=True,
            ent_schedule="linear",
            ent_coef=0.01,
            ent_coef_start=0.01,
            ent_coef_end=0.0005,
            curriculum_mode="passive_warmup",
            staged_curriculum=True,
            activity_shaping=False,
            shape_move_reward=0.005,
            shape_produce_reward=0.003,
            shape_noop_penalty=0.0005,
            shape_no_effect_penalty=0.001,
        ),
        SweepConfig(
            name="D_activity_shaping_mild",
            total_timesteps=total_timesteps,
            num_bot_envs=24,
            num_selfplay_envs=0,
            map_path="maps/24x24/basesWorkers24x24.xml",
            checkpoint_steps=CHECKPOINT_STEPS,
            seed=seed,
            diagnostic_only=False,
            project_compatible_24x24=True,
            ent_schedule="linear",
            ent_coef=0.01,
            ent_coef_start=0.01,
            ent_coef_end=0.0005,
            curriculum_mode="none",
            staged_curriculum=False,
            activity_shaping=True,
            shape_move_reward=0.005,
            shape_produce_reward=0.003,
            shape_noop_penalty=0.0005,
            shape_no_effect_penalty=0.001,
        ),
        SweepConfig(
            name="E_16x16_shaping_diagnostic",
            total_timesteps=total_timesteps,
            num_bot_envs=24,
            num_selfplay_envs=0,
            map_path="maps/16x16/basesWorkers16x16.xml",
            checkpoint_steps=CHECKPOINT_STEPS,
            seed=seed,
            diagnostic_only=True,
            project_compatible_24x24=False,
            ent_schedule="linear",
            ent_coef=0.01,
            ent_coef_start=0.01,
            ent_coef_end=0.0005,
            curriculum_mode="none",
            staged_curriculum=False,
            activity_shaping=True,
            shape_move_reward=0.005,
            shape_produce_reward=0.003,
            shape_noop_penalty=0.0005,
            shape_no_effect_penalty=0.001,
        ),
    ]
    return {cfg.name: cfg for cfg in configs}


def run_command(
    cmd: Sequence[str],
    *,
    cwd: Path,
    timeout: Optional[int] = None,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    started = now_iso()
    proc = subprocess.run(
        list(cmd),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    ended = now_iso()
    return {
        "command": list(cmd),
        "cwd": str(cwd),
        "started_utc": started,
        "ended_utc": ended,
        "exit_code": int(proc.returncode),
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def parse_probe_output(raw: str) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
            return True, payload, None
        except Exception:
            continue
    return False, {}, "probe did not emit parseable JSON payload"


def probe_env_surface(
    python_exe: Path,
    workspace_root: Path,
    cfg: SweepConfig,
) -> Dict[str, Any]:
    probe_code = r'''
import json
import numpy as np

from gym_microrts import microrts_ai
from gym_microrts.envs.vec_env import MicroRTSGridModeVecEnv

map_path = MAP_PATH
num_bot_envs = NUM_BOT_ENVS
num_selfplay_envs = NUM_SELFPLAY_ENVS

ai2s = [microrts_ai.randomBiasedAI for _ in range(num_bot_envs)]
kwargs = dict(
    num_selfplay_envs=num_selfplay_envs,
    num_bot_envs=num_bot_envs,
    ai2s=ai2s,
    max_steps=64,
    autobuild=False,
)

env = None
try:
    try:
        env = MicroRTSGridModeVecEnv(map_paths=[map_path], **kwargs)
    except TypeError:
        env = MicroRTSGridModeVecEnv(map_path=map_path, **kwargs)

    obs_shape = tuple(int(v) for v in env.observation_space.shape)
    mapsize = int(obs_shape[0] * obs_shape[1])

    if hasattr(env, "action_plane_space") and hasattr(env.action_plane_space, "nvec"):
        branch_sizes = [int(v) for v in env.action_plane_space.nvec.tolist()]
    else:
        flat_nvec = [int(v) for v in env.action_space.nvec.tolist()]
        if mapsize <= 0 or len(flat_nvec) % mapsize != 0:
            raise RuntimeError("Cannot derive branch sizes from action space")
        branch_sizes = flat_nvec[: len(flat_nvec) // mapsize]

    action_nvec = [mapsize] + branch_sizes
    payload = {
        "status": "ok",
        "observation_shape": list(obs_shape),
        "action_nvec": action_nvec,
        "branch_sizes": branch_sizes,
        "num_envs": int(getattr(env, "num_envs", num_bot_envs + num_selfplay_envs)),
    }
    print(json.dumps(payload, ensure_ascii=True))
except Exception as exc:
    print(json.dumps({"status": "error", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=True))
finally:
    if env is not None:
        try:
            env.close()
        except Exception:
            pass
'''
    probe_code = (
        probe_code.replace("MAP_PATH", repr(cfg.map_path))
        .replace("NUM_BOT_ENVS", str(cfg.num_bot_envs))
        .replace("NUM_SELFPLAY_ENVS", str(cfg.num_selfplay_envs))
    )

    result = run_command([str(python_exe), "-c", probe_code], cwd=workspace_root)
    ok, payload, parse_error = parse_probe_output(result.get("stdout_tail", "") + "\n" + result.get("stderr_tail", ""))
    if not ok:
        return {
            "status": "error",
            "parse_error": parse_error,
            "result": result,
        }
    if payload.get("status") != "ok":
        return {
            "status": "error",
            "probe_error": payload.get("error", "unknown probe error"),
            "result": result,
            "probe_payload": payload,
        }
    return {
        "status": "ok",
        "probe_payload": payload,
        "result": result,
    }


def entropy_metrics(action_distribution: Dict[str, Any]) -> Dict[str, Any]:
    dist: Dict[str, int] = {}
    for key, value in action_distribution.items():
        try:
            dist[str(key)] = int(value)
        except Exception:
            continue
    total = sum(dist.values())
    if total <= 0:
        return {
            "entropy": 0.0,
            "entropy_norm": 0.0,
            "top_action": None,
            "top_share": 0.0,
            "distribution": dist,
        }

    probs = [v / total for v in dist.values() if v > 0]
    entropy = -sum(p * math.log(p) for p in probs)
    entropy_norm = entropy / math.log(len(dist)) if len(dist) > 1 else 0.0
    top_action, top_count = max(dist.items(), key=lambda kv: kv[1])
    return {
        "entropy": float(entropy),
        "entropy_norm": float(entropy_norm),
        "top_action": top_action,
        "top_share": float(top_count / total),
        "distribution": dist,
    }


def summarize_rollout(rollout_summary_path: Path) -> Dict[str, Any]:
    if not rollout_summary_path.is_file():
        return {"status": "missing", "path": str(rollout_summary_path)}

    payload = read_json(rollout_summary_path)
    returns = [float(ep.get("episode_return", 0.0)) for ep in payload.get("per_episode", [])]
    mean_return = statistics.mean(returns) if returns else 0.0
    std_return = statistics.pstdev(returns) if returns else 0.0
    entropy = entropy_metrics(payload.get("action_type_distribution", {}))

    return {
        "status": "ok",
        "path": str(rollout_summary_path),
        "mean_return": float(mean_return),
        "std_return": float(std_return),
        "move_share": float(payload.get("move_share", 0.0) or 0.0),
        "noop_share": float(payload.get("noop_share_full_grid", 0.0) or 0.0),
        "episodes": int(payload.get("episodes", 0) or 0),
        "total_steps": int(payload.get("total_steps", 0) or 0),
        **entropy,
    }


def summarize_multiopponent(multi_path: Path) -> Dict[str, Any]:
    if not multi_path.is_file():
        return {"status": "missing", "path": str(multi_path)}

    payload = read_json(multi_path)
    per_opponent = payload.get("per_opponent", [])
    actor_move_values: List[float] = []
    actor_noop_values: List[float] = []
    for item in per_opponent:
        try:
            actor_move_values.append(float(item.get("actor_level_move_share", 0.0) or 0.0))
            actor_noop_values.append(float(item.get("actor_noop_share", 1.0) or 1.0))
        except Exception:
            continue

    return {
        "status": "ok",
        "path": str(multi_path),
        "aggregate_verdict": payload.get("aggregate", {}).get("aggregate_verdict"),
        "pass_count": int(payload.get("aggregate", {}).get("pass_count", 0) or 0),
        "total_opponents": int(payload.get("aggregate", {}).get("total_opponents", 0) or 0),
        "actor_move_mean": float(statistics.mean(actor_move_values)) if actor_move_values else 0.0,
        "actor_noop_mean": float(statistics.mean(actor_noop_values)) if actor_noop_values else 1.0,
    }


def summarize_adapter(conversion_report_path: Path) -> Dict[str, Any]:
    if not conversion_report_path.is_file():
        return {"status": "missing", "path": str(conversion_report_path)}

    payload = read_json(conversion_report_path)
    counters = payload.get("counters", {})
    sample = counters.get("samples", {})
    weakening = counters.get("semantic_weakening", {})
    action_cells = counters.get("action_cells", {})
    cells_processed = max(1, int(action_cells.get("cells_processed", 0) or 0))

    return {
        "status": "ok",
        "path": str(conversion_report_path),
        "usable_samples": int(sample.get("exact", 0) or 0) + int(sample.get("adapted", 0) or 0),
        "dropped_samples": int(sample.get("dropped", 0) or 0),
        "remap_to_noop_count": int(weakening.get("remapped_to_noop_count", 0) or 0),
        "remap_to_noop_share": float((weakening.get("remapped_to_noop_count", 0) or 0) / cells_processed),
        "semantic_weakening_share": float(weakening.get("semantic_weakening_share", 0.0) or 0.0),
        "requires_unity_v2_validation_count": int(weakening.get("requires_unity_v2_validation_count", 0) or 0),
    }


def run_training_single(
    *,
    python_exe: Path,
    workspace_root: Path,
    cfg: SweepConfig,
    config_dir: Path,
    device: str,
    disable_tensorboard: bool,
    tensorboard_root: Path,
) -> Dict[str, Any]:
    train_script = workspace_root / "python" / "week5_teacher_gridnet" / "train_teacher_gridnet_project.py"
    run_id = f"{cfg.name}_{utc_stamp()}"

    cmd: List[str] = [
        str(python_exe),
        str(train_script),
        "--run-id",
        run_id,
        "--total-timesteps",
        str(cfg.total_timesteps),
        "--checkpoint-steps",
        cfg.checkpoint_steps,
        "--initial-global-step",
        "0",
        "--num-bot-envs",
        str(cfg.num_bot_envs),
        "--num-selfplay-envs",
        str(cfg.num_selfplay_envs),
        "--seed",
        str(cfg.seed),
        "--device",
        device,
        "--eval-after-checkpoint",
        "--map-path",
        cfg.map_path,
        "--output-root",
        str(config_dir),
        "--ent-schedule",
        cfg.ent_schedule,
        "--ent-coef",
        str(cfg.ent_coef),
        "--ent-coef-start",
        str(cfg.ent_coef_start),
        "--ent-coef-end",
        str(cfg.ent_coef_end),
        "--curriculum-mode",
        cfg.curriculum_mode,
        "--activity-shaping" if cfg.activity_shaping else "--no-activity-shaping",
        "--shape-move-reward",
        str(cfg.shape_move_reward),
        "--shape-produce-reward",
        str(cfg.shape_produce_reward),
        "--shape-noop-penalty",
        str(cfg.shape_noop_penalty),
        "--shape-no-effect-penalty",
        str(cfg.shape_no_effect_penalty),
    ]
    if disable_tensorboard:
        cmd.append("--disable-tensorboard")
    else:
        cmd.extend(["--tensorboard-root", str(tensorboard_root / cfg.name)])

    result = run_command(cmd, cwd=workspace_root)
    run_dir = config_dir / run_id
    artifacts = {
        "mode": "single",
        "run_dir": str(run_dir),
        "final_model": str(run_dir / "agent_final.pt"),
        "model_metadata": str(run_dir / "model_metadata.json"),
        "run_manifest": str(run_dir / "run_manifest.json"),
        "gate_or_eval_reports_dir": str(run_dir / "gate_or_eval_reports"),
    }
    return {
        "result": result,
        "artifacts": artifacts,
        "ok": result["exit_code"] == 0,
    }


def run_training_staged(
    *,
    python_exe: Path,
    workspace_root: Path,
    cfg: SweepConfig,
    config_dir: Path,
    device: str,
    disable_tensorboard: bool,
    tensorboard_root: Path,
) -> Dict[str, Any]:
    train_script = workspace_root / "python" / "week5_teacher_gridnet" / "train_teacher_gridnet_project.py"
    stage1_total = 50000
    stage2_total = cfg.total_timesteps

    stage1_id = f"{cfg.name}_stage1_{utc_stamp()}"
    stage1_cmd: List[str] = [
        str(python_exe),
        str(train_script),
        "--run-id",
        stage1_id,
        "--total-timesteps",
        str(stage1_total),
        "--checkpoint-steps",
        "20000,50000",
        "--initial-global-step",
        "0",
        "--num-bot-envs",
        str(cfg.num_bot_envs),
        "--num-selfplay-envs",
        str(cfg.num_selfplay_envs),
        "--seed",
        str(cfg.seed),
        "--device",
        device,
        "--eval-after-checkpoint",
        "--map-path",
        cfg.map_path,
        "--output-root",
        str(config_dir),
        "--ent-schedule",
        cfg.ent_schedule,
        "--ent-coef",
        str(cfg.ent_coef),
        "--ent-coef-start",
        str(cfg.ent_coef_start),
        "--ent-coef-end",
        str(cfg.ent_coef_end),
        "--curriculum-mode",
        "passive_warmup",
        "--no-activity-shaping",
        "--shape-move-reward",
        str(cfg.shape_move_reward),
        "--shape-produce-reward",
        str(cfg.shape_produce_reward),
        "--shape-noop-penalty",
        str(cfg.shape_noop_penalty),
        "--shape-no-effect-penalty",
        str(cfg.shape_no_effect_penalty),
    ]
    if disable_tensorboard:
        stage1_cmd.append("--disable-tensorboard")
    else:
        stage1_cmd.extend(["--tensorboard-root", str(tensorboard_root / cfg.name / "stage1")])
    stage1_result = run_command(stage1_cmd, cwd=workspace_root)
    if stage1_result["exit_code"] != 0:
        return {
            "ok": False,
            "stage1": {
                "command": stage1_cmd,
                "result": stage1_result,
            },
        }

    stage1_dir = config_dir / stage1_id
    resume_ckpt = stage1_dir / "agent_final.pt"
    resume_meta = stage1_dir / "model_metadata.json"
    if not resume_ckpt.is_file() or not resume_meta.is_file():
        return {
            "ok": False,
            "stage1": {
                "command": stage1_cmd,
                "result": stage1_result,
                "error": "stage1_artifacts_missing",
            },
        }

    stage2_id = f"{cfg.name}_stage2_{utc_stamp()}"
    stage2_cmd: List[str] = [
        str(python_exe),
        str(train_script),
        "--run-id",
        stage2_id,
        "--total-timesteps",
        str(stage2_total),
        "--checkpoint-steps",
        "50000,100000",
        "--initial-global-step",
        str(stage1_total),
        "--resume-from-checkpoint",
        str(resume_ckpt),
        "--resume-model-metadata",
        str(resume_meta),
        "--num-bot-envs",
        str(cfg.num_bot_envs),
        "--num-selfplay-envs",
        str(cfg.num_selfplay_envs),
        "--seed",
        str(cfg.seed),
        "--device",
        device,
        "--eval-after-checkpoint",
        "--map-path",
        cfg.map_path,
        "--output-root",
        str(config_dir),
        "--ent-schedule",
        cfg.ent_schedule,
        "--ent-coef",
        str(cfg.ent_coef),
        "--ent-coef-start",
        str(cfg.ent_coef_start),
        "--ent-coef-end",
        str(cfg.ent_coef_end),
        "--curriculum-mode",
        "passive_warmup",
        "--no-activity-shaping",
        "--shape-move-reward",
        str(cfg.shape_move_reward),
        "--shape-produce-reward",
        str(cfg.shape_produce_reward),
        "--shape-noop-penalty",
        str(cfg.shape_noop_penalty),
        "--shape-no-effect-penalty",
        str(cfg.shape_no_effect_penalty),
    ]
    if disable_tensorboard:
        stage2_cmd.append("--disable-tensorboard")
    else:
        stage2_cmd.extend(["--tensorboard-root", str(tensorboard_root / cfg.name / "stage2")])
    stage2_result = run_command(stage2_cmd, cwd=workspace_root)
    stage2_dir = config_dir / stage2_id

    artifacts = {
        "mode": "staged",
        "stage1_run_dir": str(stage1_dir),
        "stage1_final_model": str(resume_ckpt),
        "stage1_model_metadata": str(resume_meta),
        "stage1_run_manifest": str(stage1_dir / "run_manifest.json"),
        "stage2_run_dir": str(stage2_dir),
        "final_model": str(stage2_dir / "agent_final.pt"),
        "model_metadata": str(stage2_dir / "model_metadata.json"),
        "run_manifest": str(stage2_dir / "run_manifest.json"),
        "gate_or_eval_reports_dir": str(stage2_dir / "gate_or_eval_reports"),
        "resume_from_checkpoint": str(resume_ckpt),
        "resume_model_metadata": str(resume_meta),
    }

    return {
        "ok": stage2_result["exit_code"] == 0,
        "stage1": {
            "command": stage1_cmd,
            "result": stage1_result,
        },
        "stage2": {
            "command": stage2_cmd,
            "result": stage2_result,
        },
        "artifacts": artifacts,
    }


def find_training_artifacts(config_dir: Path, staged: bool) -> Optional[Dict[str, str]]:
    candidates = sorted([p for p in config_dir.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True)
    if not staged:
        for run_dir in candidates:
            final_model = run_dir / "agent_final.pt"
            metadata = run_dir / "model_metadata.json"
            reports = run_dir / "gate_or_eval_reports"
            manifest = run_dir / "run_manifest.json"
            if final_model.is_file() and metadata.is_file() and reports.is_dir() and manifest.is_file():
                return {
                    "mode": "single",
                    "run_dir": str(run_dir),
                    "final_model": str(final_model),
                    "model_metadata": str(metadata),
                    "run_manifest": str(manifest),
                    "gate_or_eval_reports_dir": str(reports),
                }
        return None

    stage1_dirs = [p for p in candidates if "_stage1_" in p.name]
    stage2_dirs = [p for p in candidates if "_stage2_" in p.name]
    if not stage1_dirs or not stage2_dirs:
        return None

    stage1 = stage1_dirs[0]
    stage2 = stage2_dirs[0]
    final_model = stage2 / "agent_final.pt"
    metadata = stage2 / "model_metadata.json"
    reports = stage2 / "gate_or_eval_reports"
    manifest = stage2 / "run_manifest.json"
    if not (final_model.is_file() and metadata.is_file() and reports.is_dir() and manifest.is_file()):
        return None

    stage1_final = stage1 / "agent_final.pt"
    stage1_meta = stage1 / "model_metadata.json"
    return {
        "mode": "staged",
        "stage1_run_dir": str(stage1),
        "stage1_final_model": str(stage1_final),
        "stage1_model_metadata": str(stage1_meta),
        "stage1_run_manifest": str(stage1 / "run_manifest.json"),
        "stage2_run_dir": str(stage2),
        "final_model": str(final_model),
        "model_metadata": str(metadata),
        "run_manifest": str(manifest),
        "gate_or_eval_reports_dir": str(reports),
        "resume_from_checkpoint": str(stage1_final),
        "resume_model_metadata": str(stage1_meta),
    }


def run_multiopponent_eval(
    *,
    python_exe: Path,
    workspace_root: Path,
    checkpoint: Path,
    metadata: Path,
    map_path: str,
    deterministic: bool,
    output_dir: Path,
    seed: int,
    device: str,
) -> Dict[str, Any]:
    script = workspace_root / "python" / "week5_teacher_gridnet" / "evaluate_gridnet_multiopponent.py"
    cmd = [
        str(python_exe),
        str(script),
        "--checkpoint",
        str(checkpoint),
        "--model-metadata",
        str(metadata),
        "--map-path",
        map_path,
        "--episodes",
        "4",
        "--max-steps",
        "256",
        "--effective-steps",
        "100",
        "--deterministic",
        "true" if deterministic else "false",
        "--device",
        device,
        "--output-dir",
        str(output_dir),
        "--python",
        str(python_exe),
        "--seed",
        str(seed),
    ]
    result = run_command(cmd, cwd=workspace_root)
    out_json = output_dir / f"multiopponent_eval_{checkpoint.stem}.json"
    return {
        "result": result,
        "output_json": str(out_json),
        "ok": result["exit_code"] == 0 and out_json.is_file(),
    }


def run_rollout_export(
    *,
    python_exe: Path,
    workspace_root: Path,
    checkpoint: Path,
    metadata: Path,
    map_path: str,
    deterministic: bool,
    output_dir: Path,
    batch_label: str,
    seed: int,
    device: str,
) -> Dict[str, Any]:
    script = workspace_root / "python" / "week5_teacher_gridnet" / "export_gridnet_teacher_rollout.py"
    cmd = [
        str(python_exe),
        str(script),
        "--checkpoint",
        str(checkpoint),
        "--model-metadata",
        str(metadata),
        "--episodes",
        "4",
        "--max-steps",
        "512",
        "--seed",
        str(seed),
        "--map-path",
        map_path,
        "--deterministic",
        "true" if deterministic else "false",
        "--device",
        device,
        "--output-dir",
        str(output_dir),
        "--batch-label",
        batch_label,
    ]
    result = run_command(cmd, cwd=workspace_root)
    batch_dir = output_dir / batch_label
    rollout_summary = batch_dir / "rollout_summary.json"
    return {
        "result": result,
        "batch_dir": str(batch_dir),
        "rollout_summary": str(rollout_summary),
        "ok": result["exit_code"] == 0 and rollout_summary.is_file(),
    }


def run_adapter_v2(
    *,
    python_exe: Path,
    workspace_root: Path,
    input_batch_dir: Path,
    output_root: Path,
    output_batch_name: str,
) -> Dict[str, Any]:
    script = workspace_root / "python" / "week5_teacher" / "adapt_teacher_dataset.py"
    cmd = [
        str(python_exe),
        str(script),
        "--input-batch-dir",
        str(input_batch_dir),
        "--output-root",
        str(output_root),
        "--output-batch-name",
        output_batch_name,
        "--target-action-contract",
        "v2_gridnet_compatible",
    ]
    result = run_command(cmd, cwd=workspace_root)
    output_batch_dir = output_root / output_batch_name
    report_path = output_batch_dir / "conversion_report.json"
    return {
        "result": result,
        "output_batch_dir": str(output_batch_dir),
        "conversion_report": str(report_path),
        "ok": result["exit_code"] == 0 and report_path.is_file(),
    }


def run_visual_eval(
    *,
    python_exe: Path,
    workspace_root: Path,
    checkpoint: Path,
    metadata: Path,
    map_path: str,
    output_dir: Path,
    device: str,
) -> Dict[str, Any]:
    script = workspace_root / "python" / "week5_teacher_gridnet" / "render_gridnet_checkpoint.py"
    cmd = [
        str(python_exe),
        str(script),
        "--checkpoint",
        str(checkpoint),
        "--model-metadata",
        str(metadata),
        "--map-path",
        map_path,
        "--max-steps",
        "300",
        "--fps",
        "8",
        "--device",
        device,
        "--output-dir",
        str(output_dir),
    ]
    result = run_command(cmd, cwd=workspace_root)
    out_json = output_dir / f"visual_eval_{checkpoint.stem}.json"
    return {
        "result": result,
        "output_json": str(out_json),
        "ok": result["exit_code"] == 0 and out_json.is_file(),
    }


def classify_adapter_clean(adapter_summary: Dict[str, Any]) -> bool:
    if adapter_summary.get("status") != "ok":
        return False
    return (
        float(adapter_summary.get("remap_to_noop_share", 1.0)) == 0.0
        and float(adapter_summary.get("semantic_weakening_share", 1.0)) == 0.0
        and int(adapter_summary.get("dropped_samples", 1)) == 0
    )


def load_shaping_counters(run_manifest_path: Path) -> Dict[str, Any]:
    if not run_manifest_path.is_file():
        return {
            "status": "missing",
            "path": str(run_manifest_path),
        }
    manifest = read_json(run_manifest_path)
    activity = manifest.get("activity_shaping", {})
    counters = activity.get("counters", {})
    out: Dict[str, Any] = {
        "status": "ok",
        "enabled": bool(activity.get("enabled", False)),
        "shape_move_reward": float(activity.get("shape_move_reward", 0.0) or 0.0),
        "shape_produce_reward": float(activity.get("shape_produce_reward", 0.0) or 0.0),
        "shape_noop_penalty": float(activity.get("shape_noop_penalty", 0.0) or 0.0),
        "shape_no_effect_penalty": float(activity.get("shape_no_effect_penalty", 0.0) or 0.0),
    }
    for key in [
        "shaping_applied",
        "attribution_reliable",
        "diagnostics_only_reason",
        "move_reward_events",
        "produce_reward_events",
        "repeated_noop_penalty_events",
        "no_effect_penalty_events",
        "shaping_total_reward_delta",
    ]:
        if key in counters:
            out[key] = counters[key]
    return out


def extract_compact_metrics(item: Dict[str, Any]) -> Dict[str, Any]:
    metrics = item.get("metrics", {})
    det_roll = metrics.get("det_roll", {})
    stoch_roll = metrics.get("stoch_roll", {})
    det_multi = metrics.get("det_multi", {})
    stoch_multi = metrics.get("stoch_multi", {})
    adapter = metrics.get("adapter", {})

    det_adapter_clean = False
    stoch_adapter_clean = False
    if adapter and isinstance(adapter, dict) and adapter.get("det") and adapter.get("stoch"):
        det_adapter_clean = classify_adapter_clean(adapter.get("det", {}))
        stoch_adapter_clean = classify_adapter_clean(adapter.get("stoch", {}))

    return {
        "det_noop_share": float(det_roll.get("noop_share", 1.0) or 1.0),
        "det_return_mean": float(det_roll.get("mean_return", 0.0) or 0.0),
        "det_return_std": float(det_roll.get("std_return", 0.0) or 0.0),
        "det_actor_move_mean": float(det_multi.get("actor_move_mean", 0.0) or 0.0),
        "det_pass_count": int(det_multi.get("pass_count", 0) or 0),
        "stoch_return_mean": float(stoch_roll.get("mean_return", 0.0) or 0.0),
        "stoch_return_std": float(stoch_roll.get("std_return", 0.0) or 0.0),
        "stoch_entropy_norm": float(stoch_roll.get("entropy_norm", 1.0) or 1.0),
        "stoch_top_action_share": float(stoch_roll.get("top_share", 0.0) or 0.0),
        "stoch_actor_move_mean": float(stoch_multi.get("actor_move_mean", 0.0) or 0.0),
        "adapter_det_clean": bool(det_adapter_clean),
        "adapter_stoch_clean": bool(stoch_adapter_clean),
    }


def evaluate_success_criteria(item: Dict[str, Any]) -> Dict[str, Any]:
    compact = extract_compact_metrics(item)
    visual = item.get("metrics", {}).get("visual", {})
    visual_consistent = False
    if isinstance(visual, dict) and visual.get("status") == "ok":
        summary = visual.get("summary", {}) if isinstance(visual.get("summary"), dict) else {}
        visual_consistent = (
            float(summary.get("actor_level_move_share", 0.0) or 0.0) > 0.01
            and int(summary.get("effective_position_delta_count", 0) or 0) > 0
        )

    det_condition = compact["det_noop_share"] < 0.95 or compact["det_actor_move_mean"] > 0.02
    det_return_condition = compact["det_return_mean"] > 2.0
    stoch_entropy_condition = compact["stoch_entropy_norm"] < 0.95
    adapter_condition = compact["adapter_det_clean"] and compact["adapter_stoch_clean"]

    promising = det_condition and det_return_condition and stoch_entropy_condition and visual_consistent and adapter_condition
    return {
        "det_behavior_condition": det_condition,
        "det_return_condition": det_return_condition,
        "stoch_entropy_condition": stoch_entropy_condition,
        "visual_consistent_condition": visual_consistent,
        "adapter_clean_condition": adapter_condition,
        "promising": promising,
    }


def decide_next_step(results: Dict[str, Dict[str, Any]]) -> str:
    completed = {k: v for k, v in results.items() if v.get("status") == "completed"}
    if not completed:
        return "CONTINUE_SWEEP"

    checks = {name: evaluate_success_criteria(payload) for name, payload in completed.items()}
    if any(v.get("promising", False) for v in checks.values()):
        return "PROMOTE_TO_200K"

    compact = {name: extract_compact_metrics(payload) for name, payload in completed.items()}

    any_det_signal = any(
        (m.get("det_noop_share", 1.0) < 0.98) or (m.get("det_actor_move_mean", 0.0) > 0.01)
        for m in compact.values()
    )
    any_entropy_drop = any(m.get("stoch_entropy_norm", 1.0) < 0.98 for m in compact.values())

    shaping = compact.get("D_activity_shaping_mild")
    shaping_payload = completed.get("D_activity_shaping_mild", {}).get("metrics", {}).get("activity_shaping", {})
    shaping_applied = bool(shaping_payload.get("shaping_applied", False))
    if shaping_applied and shaping and (
        (shaping.get("det_actor_move_mean", 0.0) > 0.01) or (shaping.get("det_noop_share", 1.0) < 0.98)
    ):
        return "ADD_STRONGER_SHAPING"

    if not any_det_signal and not any_entropy_drop:
        return "REJECT_CURRENT_GRIDNET_RECIPE"

    if any_det_signal and not any(v.get("promising", False) for v in checks.values()):
        return "CONTINUE_SWEEP"

    return "TRY_SCRIPTED_BC_WARMSTART"


def rank_completed_configs(results: Dict[str, Dict[str, Any]]) -> List[Tuple[str, Dict[str, Any]]]:
    scored: List[Tuple[Tuple[Any, ...], str, Dict[str, Any]]] = []
    for name, item in results.items():
        if item.get("status") != "completed":
            continue
        compact = extract_compact_metrics(item)
        checks = evaluate_success_criteria(item)
        score = (
            -int(checks.get("promising", False)),
            compact.get("det_noop_share", 1.0),
            -compact.get("det_actor_move_mean", 0.0),
            -compact.get("det_return_mean", 0.0),
            compact.get("stoch_entropy_norm", 1.0),
        )
        scored.append((score, name, item))
    scored.sort(key=lambda x: x[0])
    return [(name, item) for _, name, item in scored]


def render_report_markdown(
    *,
    sweep_id: str,
    output_dir: Path,
    config_results: Dict[str, Dict[str, Any]],
    ranking: List[Tuple[str, Dict[str, Any]]],
    decision: str,
) -> str:
    lines: List[str] = []
    lines.append("# Gridnet Recipe Redesign Sweep Results")
    lines.append("")
    lines.append(f"- sweep_id: {sweep_id}")
    lines.append(f"- generated_utc: {now_iso()}")
    lines.append(f"- output_dir: {output_dir}")
    lines.append("")
    lines.append("## Scope")
    lines.append("- Entropy/reward/curriculum redesign only for Branch B Gridnet teacher.")
    lines.append("- No Unity runtime modifications.")
    lines.append("- No BC-ready dataset generation.")
    lines.append("- No student retraining.")
    lines.append("- No teacher-ready claim.")
    lines.append("- D_activity_shaping_mild is diagnostics-only unless shaping_applied=true in run_manifest.")
    lines.append("")

    lines.append("## Config Status")
    lines.append("| config | status | map | num_bot_envs | curriculum_mode | staged_curriculum | ent_schedule | activity_shaping |")
    lines.append("|---|---|---|---:|---|---|---|---|")
    for name, item in config_results.items():
        cfg = item.get("config", {})
        lines.append(
            "| "
            f"{name} | {item.get('status', 'unknown')} | {cfg.get('map_path')} | {cfg.get('num_bot_envs')} "
            f"| {cfg.get('curriculum_mode')} | {cfg.get('staged_curriculum')} | {cfg.get('ent_schedule')} | {cfg.get('activity_shaping')} |"
        )

    lines.append("")
    lines.append("## Metrics Summary")
    lines.append(
        "| config | det_noop_share | det_return_mean | det_return_std | det_actor_move_mean | det_pass_count | "
        "stoch_return_mean | stoch_return_std | stoch_entropy_norm | stoch_top_action_share | stoch_actor_move_mean | adapter_clean |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")

    for name, item in config_results.items():
        compact = extract_compact_metrics(item)
        adapter_state = "n/a"
        if item.get("config", {}).get("project_compatible_24x24"):
            adapter_state = f"det={compact['adapter_det_clean']}, stoch={compact['adapter_stoch_clean']}"
        lines.append(
            "| "
            f"{name} | {compact['det_noop_share']} | {compact['det_return_mean']} | {compact['det_return_std']} "
            f"| {compact['det_actor_move_mean']} | {compact['det_pass_count']} | {compact['stoch_return_mean']} "
            f"| {compact['stoch_return_std']} | {compact['stoch_entropy_norm']} | {compact['stoch_top_action_share']} "
            f"| {compact['stoch_actor_move_mean']} | {adapter_state} |"
        )

    lines.append("")
    lines.append("## Success Criteria Check")
    lines.append("| config | det_behavior | det_return_gt_2 | stoch_entropy_lt_0_95 | visual_consistent | adapter_clean | promising |")
    lines.append("|---|---|---|---|---|---|---|")
    for name, item in config_results.items():
        checks = evaluate_success_criteria(item)
        lines.append(
            "| "
            f"{name} | {checks['det_behavior_condition']} | {checks['det_return_condition']} "
            f"| {checks['stoch_entropy_condition']} | {checks['visual_consistent_condition']} "
            f"| {checks['adapter_clean_condition']} | {checks['promising']} |"
        )

    lines.append("")
    lines.append("## Activity Shaping Diagnostics")
    lines.append("- D_activity_shaping_mild is diagnostics-only unless shaping_applied=true in run_manifest.")
    for name, item in config_results.items():
        shaping = item.get("metrics", {}).get("activity_shaping", {})
        if not shaping:
            continue
        lines.append(f"- {name}: {json.dumps(shaping, ensure_ascii=True)}")

    lines.append("")
    lines.append("## Ranking")
    if not ranking:
        lines.append("- No completed configs to rank.")
    else:
        for idx, (name, _) in enumerate(ranking, start=1):
            lines.append(f"- {idx}. {name}")

    lines.append("")
    lines.append("## Decision")
    lines.append(f"- {decision}")
    lines.append("- Do not promote based only on stochastic return when entropy remains near 1.0.")
    lines.append("")
    lines.append("## Non-Goals Reinforced")
    lines.append("- No BC-ready package created in this sweep.")
    lines.append("- No student retraining performed.")
    lines.append("- No Unity modifications.")
    lines.append("- No teacher-ready claim made.")
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    workspace_root = Path(__file__).resolve().parents[2]
    python_exe = args.python_exe.resolve()

    all_configs = build_configs(args.total_timesteps, args.seed)
    selected_names = [x.strip() for x in str(args.configs).split(",") if x.strip()]
    selected: List[SweepConfig] = []
    for name in selected_names:
        if name not in all_configs:
            raise ValueError(f"Unknown config: {name}")
        selected.append(all_configs[name])

    sweep_root = (workspace_root / args.output_root / args.sweep_id).resolve()
    sweep_root.mkdir(parents=True, exist_ok=True)

    summary: Dict[str, Any] = {
        "schema": "gridnet_recipe_redesign_sweep.v1",
        "sweep_id": args.sweep_id,
        "created_utc": now_iso(),
        "workspace_root": str(workspace_root),
        "python_exe": str(python_exe),
        "device": args.device,
        "disable_tensorboard": bool(args.disable_tensorboard),
        "tensorboard_root": str(args.tensorboard_root),
        "configs": [asdict(cfg) for cfg in selected],
        "reference_parity_context": str(
            workspace_root
            / "WEEK5R"
            / "gridnet_reference_parity_sweeps"
            / "rp_ab_01"
        ),
    }

    config_results: Dict[str, Dict[str, Any]] = {}

    for cfg in selected:
        config_dir = sweep_root / cfg.name
        config_dir.mkdir(parents=True, exist_ok=True)

        run_notes: Dict[str, Any] = {
            "config": asdict(cfg),
            "status": "pending",
            "events": [],
        }

        probe = probe_env_surface(python_exe, workspace_root, cfg)
        run_notes["probe"] = probe

        pre_run_safety = {
            "created_utc": now_iso(),
            "map_path": cfg.map_path,
            "num_envs": int(cfg.num_bot_envs + cfg.num_selfplay_envs),
            "observation_shape": probe.get("probe_payload", {}).get("observation_shape"),
            "action_nvec": probe.get("probe_payload", {}).get("action_nvec"),
            "branch_sizes": probe.get("probe_payload", {}).get("branch_sizes"),
            "project_compatible_24x24": bool(cfg.project_compatible_24x24),
            "diagnostic_only": bool(cfg.diagnostic_only),
            "curriculum_mode": cfg.curriculum_mode,
            "staged_curriculum": bool(cfg.staged_curriculum),
            "ent_schedule": cfg.ent_schedule,
            "ent_coef": cfg.ent_coef,
            "ent_coef_start": cfg.ent_coef_start,
            "ent_coef_end": cfg.ent_coef_end,
            "activity_shaping": bool(cfg.activity_shaping),
        }
        run_notes["pre_run_safety"] = pre_run_safety
        write_json(config_dir / "pre_run_safety.json", pre_run_safety)

        if probe.get("status") != "ok":
            run_notes["status"] = "skipped"
            run_notes["skip_reason"] = "env_probe_failed"
            write_json(config_dir / "config_result.json", run_notes)
            config_results[cfg.name] = run_notes
            if args.stop_on_error:
                break
            continue

        artifacts: Optional[Dict[str, str]] = None
        if args.skip_training:
            artifacts = find_training_artifacts(config_dir, cfg.staged_curriculum)
            if artifacts is None:
                run_notes["status"] = "skipped"
                run_notes["skip_reason"] = "skip_training_enabled_and_no_existing_artifacts"
                write_json(config_dir / "config_result.json", run_notes)
                config_results[cfg.name] = run_notes
                continue
        else:
            if cfg.staged_curriculum:
                train = run_training_staged(
                    python_exe=python_exe,
                    workspace_root=workspace_root,
                    cfg=cfg,
                    config_dir=config_dir,
                    device=args.device,
                    disable_tensorboard=bool(args.disable_tensorboard),
                    tensorboard_root=(workspace_root / args.tensorboard_root / args.sweep_id).resolve(),
                )
            else:
                train = run_training_single(
                    python_exe=python_exe,
                    workspace_root=workspace_root,
                    cfg=cfg,
                    config_dir=config_dir,
                    device=args.device,
                    disable_tensorboard=bool(args.disable_tensorboard),
                    tensorboard_root=(workspace_root / args.tensorboard_root / args.sweep_id).resolve(),
                )
            run_notes["train"] = train
            if not train.get("ok", False):
                run_notes["status"] = "failed"
                write_json(config_dir / "config_result.json", run_notes)
                config_results[cfg.name] = run_notes
                if args.stop_on_error:
                    break
                continue
            artifacts = train.get("artifacts")

        if artifacts is None:
            run_notes["status"] = "failed"
            run_notes["failure"] = "missing_artifacts"
            write_json(config_dir / "config_result.json", run_notes)
            config_results[cfg.name] = run_notes
            if args.stop_on_error:
                break
            continue

        checkpoint = Path(artifacts["final_model"])
        metadata = Path(artifacts["model_metadata"])
        run_manifest_path = Path(artifacts["run_manifest"])

        eval_root = config_dir / "evals"
        eval_root.mkdir(parents=True, exist_ok=True)

        multi_det = run_multiopponent_eval(
            python_exe=python_exe,
            workspace_root=workspace_root,
            checkpoint=checkpoint,
            metadata=metadata,
            map_path=cfg.map_path,
            deterministic=True,
            output_dir=eval_root / "multiopponent_det",
            seed=cfg.seed,
            device=args.device,
        )
        multi_stoch = run_multiopponent_eval(
            python_exe=python_exe,
            workspace_root=workspace_root,
            checkpoint=checkpoint,
            metadata=metadata,
            map_path=cfg.map_path,
            deterministic=False,
            output_dir=eval_root / "multiopponent_stoch",
            seed=cfg.seed,
            device=args.device,
        )
        run_notes["multiopponent"] = {"det": multi_det, "stoch": multi_stoch}

        rollout_root = config_dir / "rollouts"
        rollout_root.mkdir(parents=True, exist_ok=True)

        det_batch = f"{cfg.name}_det_ab"
        stoch_batch = f"{cfg.name}_stoch_ab"

        rollout_det = run_rollout_export(
            python_exe=python_exe,
            workspace_root=workspace_root,
            checkpoint=checkpoint,
            metadata=metadata,
            map_path=cfg.map_path,
            deterministic=True,
            output_dir=rollout_root,
            batch_label=det_batch,
            seed=cfg.seed,
            device=args.device,
        )
        rollout_stoch = run_rollout_export(
            python_exe=python_exe,
            workspace_root=workspace_root,
            checkpoint=checkpoint,
            metadata=metadata,
            map_path=cfg.map_path,
            deterministic=False,
            output_dir=rollout_root,
            batch_label=stoch_batch,
            seed=cfg.seed,
            device=args.device,
        )
        run_notes["rollout"] = {"det": rollout_det, "stoch": rollout_stoch}

        adapter_notes: Dict[str, Any]
        if cfg.project_compatible_24x24:
            adapter_root = config_dir / "adapter_v2"
            adapter_root.mkdir(parents=True, exist_ok=True)

            det_adapter = run_adapter_v2(
                python_exe=python_exe,
                workspace_root=workspace_root,
                input_batch_dir=Path(rollout_det["batch_dir"]),
                output_root=adapter_root,
                output_batch_name=f"teacher_adapted_{det_batch}_v2_{utc_stamp()}",
            )
            stoch_adapter = run_adapter_v2(
                python_exe=python_exe,
                workspace_root=workspace_root,
                input_batch_dir=Path(rollout_stoch["batch_dir"]),
                output_root=adapter_root,
                output_batch_name=f"teacher_adapted_{stoch_batch}_v2_{utc_stamp()}",
            )
            adapter_notes = {"det": det_adapter, "stoch": stoch_adapter}
        else:
            adapter_notes = {
                "status": "skipped",
                "reason": "diagnostic_16x16_not_unity_target_shape_24x24x27",
            }
        run_notes["adapter"] = adapter_notes

        det_roll_summary = summarize_rollout(Path(rollout_det["rollout_summary"]))
        stoch_roll_summary = summarize_rollout(Path(rollout_stoch["rollout_summary"]))
        det_multi_summary = summarize_multiopponent(Path(multi_det["output_json"]))
        stoch_multi_summary = summarize_multiopponent(Path(multi_stoch["output_json"]))

        adapter_summary: Dict[str, Any] = {}
        if cfg.project_compatible_24x24:
            adapter_summary = {
                "det": summarize_adapter(Path(adapter_notes.get("det", {}).get("conversion_report", ""))),
                "stoch": summarize_adapter(Path(adapter_notes.get("stoch", {}).get("conversion_report", ""))),
            }

        run_notes["metrics"] = {
            "det_roll": det_roll_summary,
            "stoch_roll": stoch_roll_summary,
            "det_multi": det_multi_summary,
            "stoch_multi": stoch_multi_summary,
            "adapter": adapter_summary,
            "activity_shaping": load_shaping_counters(run_manifest_path),
        }
        run_notes["status"] = "completed"

        write_json(config_dir / "config_result.json", run_notes)
        config_results[cfg.name] = run_notes

    ranking = rank_completed_configs(config_results)

    if args.run_visual_top_config and ranking:
        top_name, top_payload = ranking[0]
        top_cfg = all_configs[top_name]

        top_artifacts: Optional[Dict[str, str]] = None
        train_payload = top_payload.get("train", {})
        if train_payload and train_payload.get("artifacts"):
            top_artifacts = train_payload["artifacts"]
        else:
            top_artifacts = find_training_artifacts(sweep_root / top_name, bool(top_cfg.staged_curriculum))

        if top_artifacts:
            visual = run_visual_eval(
                python_exe=python_exe,
                workspace_root=workspace_root,
                checkpoint=Path(top_artifacts["final_model"]),
                metadata=Path(top_artifacts["model_metadata"]),
                map_path=top_cfg.map_path,
                output_dir=(sweep_root / top_name / "evals" / "visual_top"),
                device=args.device,
            )
            if visual.get("ok"):
                visual_json = Path(str(visual.get("output_json")))
                if visual_json.is_file():
                    top_payload.setdefault("metrics", {})["visual"] = {
                        "status": "ok",
                        "path": str(visual_json),
                        "summary": read_json(visual_json),
                    }
                else:
                    top_payload.setdefault("metrics", {})["visual"] = {
                        "status": "missing",
                        "path": str(visual_json),
                    }
            else:
                top_payload.setdefault("metrics", {})["visual"] = {
                    "status": "failed",
                    "result": visual,
                }
            write_json(sweep_root / top_name / "config_result.json", top_payload)
            config_results[top_name] = top_payload

    decision = decide_next_step(config_results)

    results_json = {
        "schema": "gridnet_recipe_redesign_sweep_report.v1",
        "sweep_id": args.sweep_id,
        "generated_utc": now_iso(),
        "sweep_root": str(sweep_root),
        "reference_parity_context": str(
            workspace_root
            / "WEEK5R"
            / "gridnet_reference_parity_sweeps"
            / "rp_ab_01"
        ),
        "config_results": config_results,
        "ranking": [name for name, _ in rank_completed_configs(config_results)],
        "success_checks": {
            name: evaluate_success_criteria(payload)
            for name, payload in config_results.items()
            if payload.get("status") == "completed"
        },
        "decision": decision,
        "non_goals": {
            "bc_ready_dataset": False,
            "student_retrain": False,
            "unity_modification": False,
            "teacher_ready_claim": False,
        },
    }
    write_json(sweep_root / "GRIDNET_RECIPE_REDESIGN_SWEEP_RESULTS.json", results_json)

    md = render_report_markdown(
        sweep_id=args.sweep_id,
        output_dir=sweep_root,
        config_results=config_results,
        ranking=rank_completed_configs(config_results),
        decision=decision,
    )
    (sweep_root / "GRIDNET_RECIPE_REDESIGN_SWEEP_RESULTS.md").write_text(md, encoding="utf-8")

    summary["results_json"] = str(sweep_root / "GRIDNET_RECIPE_REDESIGN_SWEEP_RESULTS.json")
    summary["results_md"] = str(sweep_root / "GRIDNET_RECIPE_REDESIGN_SWEEP_RESULTS.md")
    summary["config_status"] = {k: v.get("status") for k, v in config_results.items()}
    write_json(sweep_root / "sweep_manifest.json", summary)

    print(f"[recipe-sweep] done: {sweep_root}")
    print(f"[recipe-sweep] report json: {sweep_root / 'GRIDNET_RECIPE_REDESIGN_SWEEP_RESULTS.json'}")
    print(f"[recipe-sweep] report md: {sweep_root / 'GRIDNET_RECIPE_REDESIGN_SWEEP_RESULTS.md'}")


if __name__ == "__main__":
    main()
