"""
Stage 2 smoke training wrapper for legacy gym_microrts==0.3.2.

This script is intentionally scoped for smoke validation only:
- verifies legacy env wiring
- runs a short training loop via the reference patched script
- writes all artifacts under python/week5_teacher_legacy032/
- emits machine-readable summary JSON + markdown report

It does NOT claim final teacher quality and does NOT perform Unity v2 adaptation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _ts_compact(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_reference_script() -> str:
    return str(
        _repo_root()
        / "python"
        / "week5_teacher_reference"
        / "patched_paper_scripts"
        / "ppo_gridnet_diverse_encode_decode_local_save.py"
    )


def _bool_str(v: bool) -> str:
    return "true" if v else "false"


@dataclass
class MaskInvestigation:
    status: str
    details: str
    evidence: List[Dict[str, Any]]
    warnings: List[str]


def investigate_mask_path(reference_script_path: Path) -> MaskInvestigation:
    warnings: List[str] = []
    evidence: List[Dict[str, Any]] = []

    try:
        text = reference_script_path.read_text(encoding="utf-8")
    except Exception as exc:
        return MaskInvestigation(
            status="ERROR",
            details=f"Could not read reference script: {exc}",
            evidence=[],
            warnings=["Mask path investigation failed due to file read error."],
        )

    lines = text.splitlines()

    patterns = [
        ("CategoricalMasked", r"class\s+CategoricalMasked\s*\("),
        ("vec_client.getMasks", r"vec_client\.getMasks\("),
        ("invalid_action_masks_tensor", r"invalid_action_masks\s*=\s*torch\.tensor\("),
        ("mask_logits_where", r"torch\.where\(self\.masks"),
        ("split_invalid_masks", r"split_invalid_action_masks\s*=\s*torch\.split\("),
    ]

    for name, pattern in patterns:
        rx = re.compile(pattern)
        for idx, line in enumerate(lines, start=1):
            if rx.search(line):
                evidence.append(
                    {
                        "signal": name,
                        "line": idx,
                        "snippet": line.strip(),
                    }
                )

    has_categorical_masked = any(e["signal"] == "CategoricalMasked" for e in evidence)
    has_get_masks = any(e["signal"] == "vec_client.getMasks" for e in evidence)
    has_logits_where = any(e["signal"] == "mask_logits_where" for e in evidence)

    if has_categorical_masked and has_get_masks and has_logits_where:
        details = (
            "Mask path confirmed in reference training script: masks are retrieved via "
            "envs.vec_client.getMasks(0), split by action branches, and applied in "
            "CategoricalMasked through torch.where(...) before sampling/log-prob." 
            "This explains why probe APIs did not expose mask directly."
        )
        status = "CONFIRMED"
    else:
        details = (
            "Mask path was not fully confirmed in Stage 2 wrapper; reference script may use "
            "masking internally or through a wrapper not exposed via probe APIs. Main masked "
            "PPO training remains blocked until confirmed."
        )
        status = "NOT_FOUND"
        warnings.append("Could not conclusively confirm mask path from reference script audit.")

    return MaskInvestigation(status=status, details=details, evidence=evidence, warnings=warnings)


def _safe_json_dump(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def _parse_training_stdout(stdout_path: Path) -> Dict[str, Any]:
    metrics_events: List[Dict[str, Any]] = []
    final_reward_mean: Optional[float] = None
    episode_count = 0
    max_global_step = 0
    loss_metrics: Dict[str, float] = {}

    if not stdout_path.exists():
        return {
            "events": metrics_events,
            "final_reward_mean": None,
            "episode_count": 0,
            "total_steps_observed": 0,
            "loss_metrics": {},
        }

    reward_rx = re.compile(r"global_step=(\d+),\s*episode_reward=([-+eE0-9\.]+)")
    sps_rx = re.compile(r"SPS:\s*(\d+)")

    rewards_seen: List[float] = []
    for line in stdout_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = reward_rx.search(line)
        if m:
            g = int(m.group(1))
            r = float(m.group(2))
            episode_count += 1
            max_global_step = max(max_global_step, g)
            rewards_seen.append(r)
            metrics_events.append({"type": "episode_reward", "global_step": g, "value": r})
            continue

        s = sps_rx.search(line)
        if s:
            v = float(s.group(1))
            loss_metrics["sps_last"] = v
            metrics_events.append({"type": "sps", "value": v})

    if rewards_seen:
        final_reward_mean = sum(rewards_seen) / len(rewards_seen)

    return {
        "events": metrics_events,
        "final_reward_mean": final_reward_mean,
        "episode_count": episode_count,
        "total_steps_observed": max_global_step,
        "loss_metrics": loss_metrics,
    }


def _write_metrics_jsonl(path: Path, events: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=True) + "\n")


def _collect_checkpoint_paths(model_dir: Path) -> List[str]:
    if not model_dir.exists():
        return []
    found: List[Path] = []
    for pattern in ("*.pt", "*.pth", "*.zip"):
        found.extend(model_dir.rglob(pattern))
    found = sorted(found)
    return [str(p) for p in found]


def _read_model_metadata(model_dir: Path) -> Optional[Dict[str, Any]]:
    p = model_dir / "model_metadata.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _run_checkpoint_load_test(checkpoint_path: Path, env_id: str, map_path: str) -> Dict[str, Any]:
    out = {
        "checkpoint_load_ok": False,
        "inference_steps_ok": False,
        "random_env_steps_ok": False,
        "steps": 0,
        "error": None,
    }

    try:
        import torch  # type: ignore

        torch.load(str(checkpoint_path), map_location="cpu")
        out["checkpoint_load_ok"] = True
    except Exception as exc:
        out["error"] = f"checkpoint_load_error: {exc}"
        return out

    try:
        import gym  # type: ignore
        import gym_microrts  # noqa: F401

        env = gym.make(env_id, map_path=map_path)
        try:
            obs = env.reset()
            if isinstance(obs, tuple):
                obs = obs[0]
            for i in range(3):
                action = env.action_space.sample()
                step_result = env.step(action)
                out["steps"] = i + 1
                if len(step_result) == 4:
                    done = bool(step_result[2])
                else:
                    done = bool(step_result[2] or step_result[3])
                if done:
                    env.reset()
            out["random_env_steps_ok"] = True
            out["inference_steps_ok"] = False
            out["error"] = "model inference with loaded policy is deferred to Stage 3 (non-blocking in Stage 2)"
        finally:
            env.close()
    except Exception as exc:
        extra = f"env_steps_error: {exc}"
        out["error"] = f"{out['error']}; {extra}" if out["error"] else extra

    return out


def _preflight_env(env_id: str, map_path: str) -> Dict[str, Any]:
    result = {
        "status": "FAIL",
        "error": None,
        "observation_shape": None,
        "action_space_nvec": None,
    }
    try:
        import gym  # type: ignore
        import gym_microrts  # noqa: F401

        env = gym.make(env_id, map_path=map_path)
        try:
            obs = env.reset()
            if isinstance(obs, tuple):
                obs = obs[0]
            result["observation_shape"] = list(getattr(obs, "shape", []))
            nvec = getattr(env.action_space, "nvec", None)
            if nvec is not None:
                result["action_space_nvec"] = [int(x) for x in nvec.tolist()]
            result["status"] = "PASS"
        finally:
            env.close()
    except Exception as exc:
        result["error"] = str(exc)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 2 smoke training wrapper for legacy032")
    parser.add_argument("--run-label", default="legacy032_smoke")
    parser.add_argument("--env-id", default="MicrortsRandomEnemyShapedReward1-v1")
    parser.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--total-timesteps", type=int, default=10000)
    parser.add_argument("--output-root", default="python/week5_teacher_legacy032")
    parser.add_argument("--checkpoint-dir", default=None)
    parser.add_argument("--log-dir", default=None)
    parser.add_argument("--report-dir", default=None)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")

    parser.add_argument("--no-wandb", dest="no_wandb", action="store_true", default=True)
    parser.add_argument("--allow-wandb", dest="no_wandb", action="store_false")

    parser.add_argument("--dry-run", action="store_true", default=False)

    parser.add_argument("--allow-unmasked-smoke", dest="allow_unmasked_smoke", action="store_true", default=True)
    parser.add_argument("--disallow-unmasked-smoke", dest="allow_unmasked_smoke", action="store_false")

    parser.add_argument(
        "--require-mask-for-main-training",
        dest="require_mask_for_main_training",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--no-require-mask-for-main-training",
        dest="require_mask_for_main_training",
        action="store_false",
    )

    parser.add_argument("--reference-script-path", default=_default_reference_script())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start_dt = _now_utc()
    start_ts = _ts_compact(start_dt)
    run_id = f"{args.run_label}_{start_ts}"

    root = _repo_root()
    output_root = (root / args.output_root).resolve()
    model_root = Path(args.checkpoint_dir).resolve() if args.checkpoint_dir else (output_root / "teacher_models")
    log_root = Path(args.log_dir).resolve() if args.log_dir else (output_root / "teacher_logs")
    report_root = Path(args.report_dir).resolve() if args.report_dir else (output_root / "reports")

    model_dir = model_root / run_id
    log_dir = log_root / run_id
    report_root.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    stdout_log_path = log_dir / "training_stdout.log"
    stderr_log_path = log_dir / "training_stderr.log"
    metrics_jsonl_path = log_dir / "training_metrics.jsonl"

    ref_script = Path(args.reference_script_path).resolve()
    warnings: List[str] = []
    errors: List[str] = []

    mask_investigation = investigate_mask_path(ref_script)
    warnings.extend(mask_investigation.warnings)

    if not ref_script.exists():
        errors.append(f"Reference script not found: {ref_script}")

    preflight = _preflight_env(args.env_id, args.map_path)
    if preflight["status"] != "PASS":
        errors.append(f"Legacy env preflight failed: {preflight['error']}")

    # Reference script limitation reminder.
    warnings.append(
        "Reference script uses internal MicroRTSGridModeVecEnv configuration and may ignore --env-id/--map-path passed to wrapper."
    )

    cmd = [
        sys.executable,
        str(ref_script),
        "--total-timesteps",
        str(args.total_timesteps),
        "--seed",
        str(args.seed),
        "--exp-name",
        run_id,
        "--num-bot-envs",
        "6",
        "--num-selfplay-envs",
        "0",
        "--local-save-model",
        "true",
        "--local-save-dir",
        str(model_dir),
        "--local-save-every",
        "0",
    ]

    if args.device == "cpu":
        cmd += ["--cuda", "false"]
    else:
        cmd += ["--cuda", "true"]

    env = os.environ.copy()
    if args.no_wandb:
        env["WANDB_MODE"] = "disabled"

    command_txt = " ".join(cmd)
    (log_dir / "training_command.txt").write_text(command_txt + "\n", encoding="utf-8")

    exit_code: Optional[int] = None
    duration_seconds: Optional[float] = None
    dry_run_note = None
    total_timesteps_completed = None

    if args.dry_run:
        dry_run_note = "Dry run requested; training process was not executed."
        warnings.append(dry_run_note)
        stdout_log_path.write_text("[dry-run] no training executed\n", encoding="utf-8")
        stderr_log_path.write_text("", encoding="utf-8")
    elif errors:
        stdout_log_path.write_text("[preflight-error] training skipped due to preflight errors\n", encoding="utf-8")
        stderr_log_path.write_text("\n".join(errors) + "\n", encoding="utf-8")
    else:
        t0 = time.time()
        with stdout_log_path.open("w", encoding="utf-8") as out, stderr_log_path.open("w", encoding="utf-8") as err:
            proc = subprocess.run(
                cmd,
                cwd=str(root),
                env=env,
                stdout=out,
                stderr=err,
                check=False,
                text=True,
            )
        exit_code = int(proc.returncode)
        duration_seconds = time.time() - t0
        if exit_code != 0:
            errors.append(f"Training subprocess failed with exit code {exit_code}.")

    parse_metrics = _parse_training_stdout(stdout_log_path)
    _write_metrics_jsonl(metrics_jsonl_path, parse_metrics["events"])
    if parse_metrics["total_steps_observed"]:
        total_timesteps_completed = int(parse_metrics["total_steps_observed"])

    checkpoint_paths = _collect_checkpoint_paths(model_dir)
    checkpoint_written = len(checkpoint_paths) > 0
    metadata = _read_model_metadata(model_dir)

    load_test = {
        "checkpoint_load_ok": False,
        "inference_steps_ok": False,
        "error": None,
    }
    if checkpoint_written:
        candidate = Path(checkpoint_paths[-1])
        load_test = _run_checkpoint_load_test(
            checkpoint_path=candidate,
            env_id=args.env_id,
            map_path=args.map_path,
        )
        if not load_test.get("checkpoint_load_ok", False):
            warnings.append("Checkpoint load test failed; investigate torch serialization compatibility.")
        if not load_test.get("inference_steps_ok", False):
            warnings.append(
                "Checkpoint inference-step test was not completed in Stage 2; deferred to Stage 3 as non-blocking warning."
            )
    else:
        warnings.append("No checkpoint artifacts detected in model output directory.")

    # Resolve mask status.
    if mask_investigation.status == "ERROR":
        mask_path_status = "ERROR"
    elif mask_investigation.status == "CONFIRMED":
        mask_path_status = "CONFIRMED"
    elif checkpoint_written and not errors:
        mask_path_status = "NOT_CONFIRMED_BUT_SMOKE_OK"
    else:
        mask_path_status = "NOT_FOUND"

    training_ok = (not errors) and checkpoint_written and (exit_code in (None, 0) or args.dry_run)
    if args.dry_run:
        training_status = "FAIL"
    elif errors:
        training_status = "FAIL"
    elif not checkpoint_written:
        training_status = "FAIL"
    elif mask_path_status == "CONFIRMED":
        training_status = "PASS"
    else:
        training_status = "PASS_WITH_WARNINGS"

    if training_status == "FAIL":
        stage3_decision = "BLOCKED_TRAINING_FAILED" if errors else "BLOCKED_NO_CHECKPOINT"
    elif not checkpoint_written:
        stage3_decision = "BLOCKED_NO_CHECKPOINT"
    elif args.require_mask_for_main_training and mask_path_status != "CONFIRMED":
        stage3_decision = "BLOCKED_MASK_REQUIRED_FOR_NEXT_STAGE"
    elif checkpoint_written and mask_path_status == "CONFIRMED":
        stage3_decision = "READY_FOR_STAGE3_BEHAVIOR_GATE"
    elif checkpoint_written and training_status in ("PASS", "PASS_WITH_WARNINGS"):
        stage3_decision = "READY_FOR_STAGE3_WITH_MASK_WARNING"
    else:
        stage3_decision = "INCONCLUSIVE_NEEDS_MANUAL_CHECK"

    end_dt = _now_utc()
    summary_payload: Dict[str, Any] = {
        "run_id": run_id,
        "timestamp": end_dt.isoformat(),
        "env_id": args.env_id,
        "map_path": args.map_path,
        "seed": args.seed,
        "total_timesteps_requested": args.total_timesteps,
        "total_timesteps_completed": total_timesteps_completed,
        "duration_seconds": duration_seconds,
        "checkpoint_written": checkpoint_written,
        "checkpoint_paths": checkpoint_paths,
        "stdout_log_path": str(stdout_log_path),
        "stderr_log_path": str(stderr_log_path),
        "training_status": training_status,
        "final_reward_mean": parse_metrics["final_reward_mean"],
        "episode_count": parse_metrics["episode_count"],
        "total_steps_observed": parse_metrics["total_steps_observed"],
        "loss_metrics": parse_metrics["loss_metrics"],
        "mask_path_status": mask_path_status,
        "mask_path_details": mask_investigation.details,
        "mask_path_evidence": mask_investigation.evidence,
        "warnings": warnings,
        "errors": errors,
        "stage3_readiness_decision": stage3_decision,
        "command_used": command_txt,
        "reference_script_path": str(ref_script),
        "env_preflight": preflight,
        "dry_run": args.dry_run,
        "allow_unmasked_smoke": args.allow_unmasked_smoke,
        "require_mask_for_main_training": args.require_mask_for_main_training,
        "load_test": load_test,
        "metadata": metadata,
        "no_wandb": args.no_wandb,
        "device": args.device,
    }

    per_run_json = report_root / f"stage2_smoke_training_{start_ts}.json"
    per_run_md = report_root / f"stage2_smoke_training_{start_ts}.md"
    _safe_json_dump(per_run_json, summary_payload)

    md_lines = [
        "# Stage 2 Smoke Training Report",
        "",
        f"- run_id: {run_id}",
        f"- training_status: {training_status}",
        f"- stage3_readiness_decision: {stage3_decision}",
        "",
        "## Summary",
        "",
        "Stage 2 smoke training executed under legacy032 scope. This checkpoint is a smoke artifact only and is not a final teacher.",
        "",
        "## Command used",
        "",
        "```text",
        command_txt,
        "```",
        "",
        "## Environment",
        "",
        f"- env_id (wrapper preflight): {args.env_id}",
        f"- map_path (wrapper preflight): {args.map_path}",
        f"- env_preflight_status: {preflight['status']}",
        "",
        "## Reference script used",
        "",
        f"- {ref_script}",
        "",
        "## Output artifacts",
        "",
        f"- model_dir: {model_dir}",
        f"- log_dir: {log_dir}",
        f"- stdout: {stdout_log_path}",
        f"- stderr: {stderr_log_path}",
        f"- metrics_jsonl: {metrics_jsonl_path}",
        f"- summary_json: {per_run_json}",
        "",
        "## Checkpoint status",
        "",
        f"- checkpoint_written: {checkpoint_written}",
        f"- checkpoint_paths: {checkpoint_paths}",
        f"- load_test: {load_test}",
        "",
        "## Mask path investigation",
        "",
        f"- mask_path_status: {mask_path_status}",
        f"- details: {mask_investigation.details}",
        "",
        "## Known warnings",
        "",
    ]
    if warnings:
        md_lines.extend([f"- {w}" for w in warnings])
    else:
        md_lines.append("- none")

    md_lines += [
        "",
        "## Known errors",
        "",
    ]
    if errors:
        md_lines.extend([f"- {e}" for e in errors])
    else:
        md_lines.append("- none")

    md_lines += [
        "",
        "## Stage 3 readiness decision",
        "",
        stage3_decision,
        "",
    ]
    per_run_md.write_text("\n".join(md_lines), encoding="utf-8")

    print(json.dumps({
        "run_id": run_id,
        "training_status": training_status,
        "stage3_readiness_decision": stage3_decision,
        "summary_json": str(per_run_json),
        "summary_md": str(per_run_md),
    }, indent=2))

    return 0 if training_status in ("PASS", "PASS_WITH_WARNINGS") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
