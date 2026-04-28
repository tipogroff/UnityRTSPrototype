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
from typing import Any, Dict, List, Optional, Tuple


NUM_STEPS = 256
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
            "Reference-parity ablation sweep for Branch B Gridnet teacher training. "
            "Runs train/eval/rollout/adapter diagnostics and writes a consolidated report."
        )
    )
    p.add_argument("--python-exe", type=Path, default=Path(sys.executable))
    p.add_argument("--device", default="cpu")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--total-timesteps", type=int, default=100000)
    p.add_argument("--sweep-id", default=f"reference_parity_{utc_stamp()}")
    p.add_argument(
        "--output-root",
        type=Path,
        default=Path("WEEK5R/gridnet_reference_parity_sweeps"),
    )
    p.add_argument(
        "--configs",
        default="A_project_24env_24x24,B_reference_24env_16x16,C_selfplay_mixed_24x24,D_selfplay_reference_16x16",
        help="Comma-separated config names to run.",
    )
    p.add_argument(
        "--skip-training",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Skip training stage and only attempt post-run actions if artifacts already exist.",
    )
    p.add_argument(
        "--run-visual-top-config",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Optionally run visual eval for top ranked completed config.",
    )
    p.add_argument(
        "--stop-on-error",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Stop sweep after first failed config.",
    )
    return p.parse_args()


def build_configs(total_timesteps: int, seed: int) -> Dict[str, SweepConfig]:
    configs = [
        SweepConfig(
            name="A_project_24env_24x24",
            total_timesteps=total_timesteps,
            num_bot_envs=24,
            num_selfplay_envs=0,
            map_path="maps/24x24/basesWorkers24x24.xml",
            checkpoint_steps=CHECKPOINT_STEPS,
            seed=seed,
            diagnostic_only=False,
            project_compatible_24x24=True,
        ),
        SweepConfig(
            name="B_reference_24env_16x16",
            total_timesteps=total_timesteps,
            num_bot_envs=24,
            num_selfplay_envs=0,
            map_path="maps/16x16/basesWorkers16x16.xml",
            checkpoint_steps=CHECKPOINT_STEPS,
            seed=seed,
            diagnostic_only=True,
            project_compatible_24x24=False,
        ),
        SweepConfig(
            name="C_selfplay_mixed_24x24",
            total_timesteps=total_timesteps,
            num_bot_envs=8,
            num_selfplay_envs=16,
            map_path="maps/24x24/basesWorkers24x24.xml",
            checkpoint_steps=CHECKPOINT_STEPS,
            seed=seed,
            diagnostic_only=True,
            project_compatible_24x24=True,
        ),
        SweepConfig(
            name="D_selfplay_reference_16x16",
            total_timesteps=total_timesteps,
            num_bot_envs=8,
            num_selfplay_envs=16,
            map_path="maps/16x16/basesWorkers16x16.xml",
            checkpoint_steps=CHECKPOINT_STEPS,
            seed=seed,
            diagnostic_only=True,
            project_compatible_24x24=False,
        ),
    ]
    return {cfg.name: cfg for cfg in configs}


def run_command(
    cmd: List[str],
    *,
    cwd: Path,
    timeout: Optional[int] = None,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    started = now_iso()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    ended = now_iso()
    return {
        "command": cmd,
        "cwd": str(cwd),
        "started_utc": started,
        "ended_utc": ended,
        "exit_code": int(proc.returncode),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
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

    cmd = [str(python_exe), "-c", probe_code]
    result = run_command(cmd, cwd=workspace_root)
    ok, payload, parse_error = parse_probe_output(result["stdout"])

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


def run_training(
    *,
    python_exe: Path,
    workspace_root: Path,
    cfg: SweepConfig,
    config_dir: Path,
    device: str,
) -> Dict[str, Any]:
    train_script = workspace_root / "python" / "week5_teacher_gridnet" / "train_teacher_gridnet_project.py"
    run_id = f"{cfg.name}_{utc_stamp()}"

    cmd = [
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
    ]

    result = run_command(cmd, cwd=workspace_root)
    run_dir = config_dir / run_id
    artifacts = {
        "run_dir": str(run_dir),
        "final_model": str(run_dir / "agent_final.pt"),
        "model_metadata": str(run_dir / "model_metadata.json"),
        "gate_or_eval_reports_dir": str(run_dir / "gate_or_eval_reports"),
    }
    return {
        "result": result,
        "artifacts": artifacts,
        "ok": result["exit_code"] == 0,
    }


def find_training_artifacts(config_dir: Path) -> Optional[Dict[str, str]]:
    candidates = sorted([p for p in config_dir.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True)
    for run_dir in candidates:
        final_model = run_dir / "agent_final.pt"
        metadata = run_dir / "model_metadata.json"
        reports = run_dir / "gate_or_eval_reports"
        if final_model.is_file() and metadata.is_file() and reports.is_dir():
            return {
                "run_dir": str(run_dir),
                "final_model": str(final_model),
                "model_metadata": str(metadata),
                "gate_or_eval_reports_dir": str(reports),
            }
    return None


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


def find_baseline_paths(workspace_root: Path) -> Dict[str, Dict[str, Optional[Path]]]:
    return {
        "fresh100k_v2": {
            "effectiveness": workspace_root
            / "WEEK5R"
            / "gridnet_teacher_runs"
            / "gridnet_fresh_100k_v2_20260428T191104Z"
            / "gate_or_eval_reports"
            / "effectiveness_metrics_fresh_100k_v2.json",
            "visual": workspace_root
            / "WEEK5R"
            / "gridnet_teacher_runs"
            / "gridnet_fresh_100k_v2_20260428T191104Z"
            / "gate_or_eval_reports"
            / "visual_eval_agent_final.json",
        },
        "old100k": {
            "multi_det": workspace_root
            / "WEEK5R"
            / "gridnet_teacher_runs"
            / "gridnet_100k_20260427T221123Z"
            / "gate_or_eval_reports"
            / "multiopponent_eval_agent_final.json",
            "roll_det": workspace_root
            / "WEEK5R"
            / "gridnet_teacher_rollouts"
            / "gridnet_100k_det_ab"
            / "rollout_summary.json",
            "roll_stoch": workspace_root
            / "WEEK5R"
            / "gridnet_teacher_rollouts"
            / "gridnet_100k_stoch_ab"
            / "rollout_summary.json",
            "visual": workspace_root
            / "WEEK5R"
            / "gridnet_teacher_runs"
            / "gridnet_100k_20260427T221123Z"
            / "gate_or_eval_reports"
            / "visual_eval_agent_final.json",
        },
        "continue200k": {
            "effectiveness": workspace_root
            / "WEEK5R"
            / "gridnet_teacher_runs"
            / "gridnet_200k_continue_20260428T183153Z"
            / "gate_or_eval_reports"
            / "effectiveness_metrics_200k.json",
            "visual": workspace_root
            / "WEEK5R"
            / "gridnet_teacher_runs"
            / "gridnet_200k_continue_20260428T183153Z"
            / "gate_or_eval_reports"
            / "visual_eval_200k"
            / "visual_eval_agent_final.json",
        },
        "reference_legacy": {
            "result_md": workspace_root
            / "python"
            / "week5_teacher_reference"
            / "REFERENCE_REPRODUCTION_RESULT.md"
        },
    }


def load_baselines(workspace_root: Path) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    paths = find_baseline_paths(workspace_root)

    fresh = paths["fresh100k_v2"]["effectiveness"]
    if fresh is not None and fresh.is_file():
        payload = read_json(fresh)
        out["fresh100k_v2"] = {
            "det_roll": payload.get("det_roll"),
            "stoch_roll": payload.get("stoch_roll"),
            "det_multi": {
                "pass_count": payload.get("det_multi", {}).get("aggregate", {}).get("pass_count", 0),
                "actor_move_mean": statistics.mean(
                    [
                        float(x.get("actor_level_move_share", 0.0) or 0.0)
                        for x in payload.get("det_multi", {}).get("per_opponent", [])
                    ]
                )
                if payload.get("det_multi", {}).get("per_opponent")
                else 0.0,
            },
        }

    c200 = paths["continue200k"]["effectiveness"]
    if c200 is not None and c200.is_file():
        payload = read_json(c200)
        out["continue200k"] = {
            "det_roll": payload.get("det_roll"),
            "stoch_roll": payload.get("stoch_roll"),
            "det_multi": {
                "pass_count": payload.get("det_multi", {}).get("aggregate", {}).get("pass_count", 0),
                "actor_move_mean": statistics.mean(
                    [
                        float(x.get("actor_level_move_share", 0.0) or 0.0)
                        for x in payload.get("det_multi", {}).get("per_opponent", [])
                    ]
                )
                if payload.get("det_multi", {}).get("per_opponent")
                else 0.0,
            },
        }

    old = paths["old100k"]
    old_det_roll = summarize_rollout(old["roll_det"]) if old.get("roll_det") and old["roll_det"].is_file() else None
    old_stoch_roll = summarize_rollout(old["roll_stoch"]) if old.get("roll_stoch") and old["roll_stoch"].is_file() else None
    old_det_multi = summarize_multiopponent(old["multi_det"]) if old.get("multi_det") and old["multi_det"].is_file() else None
    if old_det_roll or old_stoch_roll or old_det_multi:
        out["old100k"] = {
            "det_roll": old_det_roll,
            "stoch_roll": old_stoch_roll,
            "det_multi": old_det_multi,
        }

    ref_md = paths["reference_legacy"]["result_md"]
    if ref_md is not None and ref_md.is_file():
        lines = ref_md.read_text(encoding="utf-8").splitlines()
        bullets: List[str] = []
        capture = False
        for line in lines:
            if line.strip().startswith("## Visual Observation"):
                capture = True
                continue
            if capture and line.strip().startswith("## "):
                break
            if capture and line.strip().startswith("-"):
                bullets.append(line.strip().lstrip("-").strip())
        out["reference_legacy"] = {
            "visual_behavior_notes": bullets,
            "source": str(ref_md),
        }

    return out


def classify_adapter_clean(adapter_summary: Dict[str, Any]) -> bool:
    if adapter_summary.get("status") != "ok":
        return False
    return (
        float(adapter_summary.get("remap_to_noop_share", 1.0)) == 0.0
        and float(adapter_summary.get("semantic_weakening_share", 1.0)) == 0.0
        and int(adapter_summary.get("dropped_samples", 1)) == 0
    )


def rank_completed_configs(results: Dict[str, Dict[str, Any]]) -> List[Tuple[str, Dict[str, Any]]]:
    scored: List[Tuple[Tuple[Any, ...], str, Dict[str, Any]]] = []
    for name, item in results.items():
        if item.get("status") != "completed":
            continue
        det_roll = item.get("metrics", {}).get("det_roll", {})
        stoch_roll = item.get("metrics", {}).get("stoch_roll", {})
        adapter = item.get("metrics", {}).get("adapter", {})
        visual = item.get("metrics", {}).get("visual", {})

        det_noop = float(det_roll.get("noop_share", 1.0) or 1.0)
        det_ret = float(det_roll.get("mean_return", -1e9) or -1e9)
        stoch_entropy = float(stoch_roll.get("entropy_norm", 1.0) or 1.0)
        visual_active = 1 if visual.get("status") == "ok" and visual.get("visual_eval_status") == "active" else 0
        adapter_clean = 1 if (
            classify_adapter_clean(adapter.get("det", {})) and classify_adapter_clean(adapter.get("stoch", {}))
        ) else 0

        score = (
            det_noop,
            -det_ret,
            stoch_entropy,
            -visual_active,
            -adapter_clean,
        )
        scored.append((score, name, item))

    scored.sort(key=lambda x: x[0])
    return [(name, item) for _, name, item in scored]


def decide_next_step(results: Dict[str, Dict[str, Any]], baselines: Dict[str, Any]) -> str:
    def extract(config_name: str) -> Optional[Dict[str, Any]]:
        cfg = results.get(config_name)
        if not cfg or cfg.get("status") != "completed":
            return None
        return cfg.get("metrics", {})

    A = extract("A_project_24env_24x24")
    B = extract("B_reference_24env_16x16")
    C = extract("C_selfplay_mixed_24x24")
    D = extract("D_selfplay_reference_16x16")

    baseline_noops: List[float] = []
    for key in ("fresh100k_v2", "old100k", "continue200k"):
        det_roll = baselines.get(key, {}).get("det_roll", {})
        if isinstance(det_roll, dict) and "noop_share" in det_roll:
            baseline_noops.append(float(det_roll.get("noop_share", 1.0) or 1.0))

    baseline_best_noop = min(baseline_noops) if baseline_noops else 1.0

    if A:
        a_det_noop = float(A.get("det_roll", {}).get("noop_share", 1.0) or 1.0)
        a_det_ret = float(A.get("det_roll", {}).get("mean_return", 0.0) or 0.0)
        a_stoch_entropy = float(A.get("stoch_roll", {}).get("entropy_norm", 1.0) or 1.0)
        if a_det_noop <= baseline_best_noop * 0.8 and a_det_ret > 2.0 and a_stoch_entropy < 0.98:
            return "PROMOTE_NUM_BOT_ENVS_24_BASELINE"

    if B and (not A or float(A.get("det_roll", {}).get("mean_return", 0.0) or 0.0) <= 2.0):
        b_det_ret = float(B.get("det_roll", {}).get("mean_return", 0.0) or 0.0)
        b_det_noop = float(B.get("det_roll", {}).get("noop_share", 1.0) or 1.0)
        if b_det_ret > 2.0 and b_det_noop < 0.95:
            return "LIKELY_MAP_DIFFICULTY_24X24_NOT_TRAINER"

    if C or D:
        c_entropy = float(C.get("stoch_roll", {}).get("entropy_norm", 1.0) or 1.0) if C else 1.0
        d_entropy = float(D.get("stoch_roll", {}).get("entropy_norm", 1.0) or 1.0) if D else 1.0
        b_entropy = float(B.get("stoch_roll", {}).get("entropy_norm", 1.0) or 1.0) if B else 1.0
        c_det_noop = float(C.get("det_roll", {}).get("noop_share", 1.0) or 1.0) if C else 1.0
        a_det_noop = float(A.get("det_roll", {}).get("noop_share", 1.0) or 1.0) if A else 1.0
        if c_det_noop < a_det_noop or d_entropy < min(0.98, c_entropy, b_entropy):
            return "SELFPLAY_RECIPE_WORTH_FOLLOW_UP"

    return "NONE_HELPED_MOVE_TO_ENTROPY_REWARD_CURRICULUM_REDESIGN"


def render_report_markdown(
    *,
    sweep_id: str,
    output_dir: Path,
    config_results: Dict[str, Dict[str, Any]],
    baselines: Dict[str, Any],
    ranking: List[Tuple[str, Dict[str, Any]]],
    decision: str,
) -> str:
    lines: List[str] = []
    lines.append("# Gridnet Reference-Parity Sweep Results")
    lines.append("")
    lines.append(f"- sweep_id: {sweep_id}")
    lines.append(f"- generated_utc: {now_iso()}")
    lines.append(f"- output_dir: {output_dir}")
    lines.append("")
    lines.append("## Scope")
    lines.append("- Branch B Gridnet teacher reference-parity ablation only.")
    lines.append("- No Unity runtime modification.")
    lines.append("- No BC-ready packaging.")
    lines.append("- No student retraining.")
    lines.append("- No teacher-ready claim.")
    lines.append("")

    lines.append("## Config Status")
    lines.append("| config | status | map | num_bot_envs | num_selfplay_envs | diagnostic_only | project_compatible_24x24 |")
    lines.append("|---|---|---|---:|---:|---|---|")
    for name, item in config_results.items():
        cfg = item.get("config", {})
        lines.append(
            "| "
            f"{name} | {item.get('status', 'unknown')} | {cfg.get('map_path')} "
            f"| {cfg.get('num_bot_envs')} | {cfg.get('num_selfplay_envs')} "
            f"| {cfg.get('diagnostic_only')} | {cfg.get('project_compatible_24x24')} |"
        )

    lines.append("")
    lines.append("## Metrics Summary")
    lines.append(
        "| config | det_noop_share | det_return_mean | det_return_std | det_actor_move_mean | det_multi_pass_count | "
        "stoch_return_mean | stoch_return_std | stoch_entropy_norm | stoch_top_action_share | adapter_24x24 |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")

    for name, item in config_results.items():
        metrics = item.get("metrics", {})
        det_roll = metrics.get("det_roll", {})
        stoch_roll = metrics.get("stoch_roll", {})
        det_multi = metrics.get("det_multi", {})
        adapter = metrics.get("adapter", {})

        adapter_state = "n/a"
        if adapter:
            det_clean = classify_adapter_clean(adapter.get("det", {}))
            stoch_clean = classify_adapter_clean(adapter.get("stoch", {}))
            adapter_state = f"det_clean={det_clean}, stoch_clean={stoch_clean}"

        lines.append(
            "| "
            f"{name} "
            f"| {det_roll.get('noop_share', 'n/a')} "
            f"| {det_roll.get('mean_return', 'n/a')} "
            f"| {det_roll.get('std_return', 'n/a')} "
            f"| {det_multi.get('actor_move_mean', 'n/a')} "
            f"| {det_multi.get('pass_count', 'n/a')} "
            f"| {stoch_roll.get('mean_return', 'n/a')} "
            f"| {stoch_roll.get('std_return', 'n/a')} "
            f"| {stoch_roll.get('entropy_norm', 'n/a')} "
            f"| {stoch_roll.get('top_share', 'n/a')} "
            f"| {adapter_state} |"
        )

    lines.append("")
    lines.append("## Baseline Comparison")
    lines.append("- Compared against fresh100k v2, old100k, 200k continuation, and reference legacy staged visual behavior.")
    lines.append("- Baseline payload is embedded in the JSON results artifact.")

    if baselines.get("reference_legacy", {}).get("visual_behavior_notes"):
        lines.append("- Reference legacy staged visual behavior notes:")
        for note in baselines["reference_legacy"]["visual_behavior_notes"]:
            lines.append(f"  - {note}")

    lines.append("")
    lines.append("## Ranking")
    lines.append("Priority order used:")
    lines.append("1. deterministic NoOp share lower")
    lines.append("2. deterministic return > 2.0")
    lines.append("3. stochastic entropy lower than 0.98")
    lines.append("4. visual behavior more active")
    lines.append("5. adapter clean for 24x24 configs")
    if not ranking:
        lines.append("- No completed configs to rank.")
    else:
        for idx, (name, _) in enumerate(ranking, start=1):
            lines.append(f"- {idx}. {name}")

    lines.append("")
    lines.append("## Decision")
    lines.append(f"- {decision}")
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
        "schema": "gridnet_reference_parity_sweep.v1",
        "sweep_id": args.sweep_id,
        "created_utc": now_iso(),
        "workspace_root": str(workspace_root),
        "python_exe": str(python_exe),
        "device": args.device,
        "configs": [asdict(cfg) for cfg in selected],
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

        num_envs = cfg.num_bot_envs + cfg.num_selfplay_envs
        batch_size = num_envs * NUM_STEPS
        pre_run_safety = {
            "created_utc": now_iso(),
            "num_envs": int(num_envs),
            "batch_size": int(batch_size),
            "map_path": cfg.map_path,
            "observation_shape": probe.get("probe_payload", {}).get("observation_shape"),
            "action_nvec": probe.get("probe_payload", {}).get("action_nvec"),
            "branch_sizes": probe.get("probe_payload", {}).get("branch_sizes"),
            "project_compatible_24x24": bool(cfg.project_compatible_24x24),
            "diagnostic_only": bool(cfg.diagnostic_only),
        }
        run_notes["pre_run_safety"] = pre_run_safety
        write_json(config_dir / "pre_run_safety.json", pre_run_safety)

        if probe.get("status") != "ok":
            run_notes["status"] = "skipped"
            if cfg.num_selfplay_envs > 0:
                run_notes["skip_reason"] = "selfplay_not_supported_or_api_limited"
            else:
                run_notes["skip_reason"] = "env_probe_failed"
            write_json(config_dir / "config_result.json", run_notes)
            config_results[cfg.name] = run_notes
            if args.stop_on_error:
                break
            continue

        artifacts: Optional[Dict[str, str]] = None
        if args.skip_training:
            artifacts = find_training_artifacts(config_dir)
            if artifacts is None:
                run_notes["status"] = "skipped"
                run_notes["skip_reason"] = "skip_training_enabled_and_no_existing_artifacts"
                write_json(config_dir / "config_result.json", run_notes)
                config_results[cfg.name] = run_notes
                continue
        else:
            train = run_training(
                python_exe=python_exe,
                workspace_root=workspace_root,
                cfg=cfg,
                config_dir=config_dir,
                device=args.device,
            )
            run_notes["train"] = train
            if not train["ok"]:
                run_notes["status"] = "failed"
                write_json(config_dir / "config_result.json", run_notes)
                config_results[cfg.name] = run_notes
                if args.stop_on_error:
                    break
                continue
            artifacts = train["artifacts"]

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

        adapter_notes: Dict[str, Any] = {}
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

        adapter_summary = {}
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
        }
        run_notes["status"] = "completed"

        write_json(config_dir / "config_result.json", run_notes)
        config_results[cfg.name] = run_notes

    baselines = load_baselines(workspace_root)

    ranking = rank_completed_configs(config_results)

    if args.run_visual_top_config and ranking:
        top_name, top_payload = ranking[0]
        top_cfg = all_configs[top_name]
        top_artifacts = None
        train_payload = top_payload.get("train", {})
        if train_payload and train_payload.get("artifacts"):
            top_artifacts = train_payload["artifacts"]
        else:
            top_artifacts = find_training_artifacts(sweep_root / top_name)
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
            top_payload.setdefault("metrics", {})["visual"] = {
                "status": "ok" if visual.get("ok") else "failed",
                "visual_eval_json": visual.get("output_json"),
            }
            write_json(sweep_root / top_name / "config_result.json", top_payload)

    decision = decide_next_step(config_results, baselines)

    report_json = {
        "schema": "gridnet_reference_parity_sweep_report.v1",
        "sweep_id": args.sweep_id,
        "generated_utc": now_iso(),
        "sweep_root": str(sweep_root),
        "config_results": config_results,
        "baselines": baselines,
        "ranking": [name for name, _ in ranking],
        "decision": decision,
        "non_goals": {
            "bc_ready_dataset": False,
            "student_retrain": False,
            "unity_modification": False,
            "teacher_ready_claim": False,
        },
    }

    write_json(sweep_root / "GRIDNET_REFERENCE_PARITY_SWEEP_RESULTS.json", report_json)

    md = render_report_markdown(
        sweep_id=args.sweep_id,
        output_dir=sweep_root,
        config_results=config_results,
        baselines=baselines,
        ranking=ranking,
        decision=decision,
    )
    (sweep_root / "GRIDNET_REFERENCE_PARITY_SWEEP_RESULTS.md").write_text(md, encoding="utf-8")

    summary["results_json"] = str(sweep_root / "GRIDNET_REFERENCE_PARITY_SWEEP_RESULTS.json")
    summary["results_md"] = str(sweep_root / "GRIDNET_REFERENCE_PARITY_SWEEP_RESULTS.md")
    summary["config_status"] = {k: v.get("status") for k, v in config_results.items()}
    write_json(sweep_root / "sweep_manifest.json", summary)

    print(f"[sweep] done: {sweep_root}")
    print(f"[sweep] report json: {sweep_root / 'GRIDNET_REFERENCE_PARITY_SWEEP_RESULTS.json'}")
    print(f"[sweep] report md: {sweep_root / 'GRIDNET_REFERENCE_PARITY_SWEEP_RESULTS.md'}")


if __name__ == "__main__":
    main()
