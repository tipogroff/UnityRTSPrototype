from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _parse_bool(value: str) -> bool:
    if isinstance(value, bool):
        return value
    v = value.strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def _parse_training_stdout(stdout_path: Path) -> Dict[str, Any]:
    events: List[Dict[str, Any]] = []
    episode_count = 0
    total_steps = 0
    reward_values: List[float] = []

    if not stdout_path.exists():
        return {
            "events": events,
            "episode_count": 0,
            "total_steps_observed": 0,
            "final_reward_mean": None,
        }

    reward_rx = re.compile(r"global_step=(\d+),\s*episode_reward=([-+eE0-9\.]+)")
    for line in stdout_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = reward_rx.search(line)
        if not m:
            continue
        step = int(m.group(1))
        rew = float(m.group(2))
        total_steps = max(total_steps, step)
        episode_count += 1
        reward_values.append(rew)
        events.append({"type": "episode_reward", "global_step": step, "value": rew})

    mean_reward = None
    if reward_values:
        mean_reward = float(sum(reward_values) / len(reward_values))

    return {
        "events": events,
        "episode_count": episode_count,
        "total_steps_observed": total_steps,
        "final_reward_mean": mean_reward,
    }


def _write_jsonl(path: Path, events: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=True) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 4 short 24x24 smoke training wrapper for legacy032.")
    parser.add_argument("--run-label", default="legacy032_24x24_smoke")
    parser.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--total-timesteps", type=int, default=10000)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--no-wandb", action="store_true", default=False)
    parser.add_argument("--output-root", default="python/week5_teacher_legacy032")
    parser.add_argument("--require-contract-check", type=_parse_bool, default=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = _repo_root()
    ts = _ts()
    run_id = f"{args.run_label}_{ts}"

    output_root = Path(args.output_root)
    if not output_root.is_absolute():
        output_root = (repo_root / output_root).resolve()

    model_dir = output_root / "teacher_models" / run_id
    log_dir = output_root / "teacher_logs" / run_id
    report_dir = output_root / "reports"

    model_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = log_dir / "training_stdout.log"
    stderr_path = log_dir / "training_stderr.log"
    metrics_path = log_dir / "training_metrics.jsonl"

    verify_json_path = report_dir / "stage4r_24x24_contract_probe.json"
    verify_script = repo_root / "python" / "week5_teacher_legacy032" / "scripts" / "verify_legacy032_24x24_training_contract.py"
    train_script = repo_root / "python" / "week5_teacher_legacy032" / "scripts" / "ppo_gridnet_legacy032_24x24_local_save.py"

    warnings: List[str] = []
    errors: List[str] = []
    contract_probe_result: Optional[Dict[str, Any]] = None

    if args.require_contract_check:
        verify_cmd = [
            sys.executable,
            str(verify_script),
            "--map-path",
            args.map_path,
            "--num-bot-envs",
            "6",
            "--num-selfplay-envs",
            "0",
            "--seed",
            str(args.seed),
            "--output-json",
            str(verify_json_path),
        ]
        verify_proc = subprocess.run(verify_cmd, cwd=str(repo_root), check=False, text=True)
        if verify_json_path.exists():
            contract_probe_result = json.loads(verify_json_path.read_text(encoding="utf-8"))
        if verify_proc.returncode != 0:
            probe_status = None
            if isinstance(contract_probe_result, dict):
                probe_status = contract_probe_result.get("status")
            if probe_status == "BLOCKED_POLICY_ARCHITECTURE_SHAPE":
                errors.append("Contract probe blocked by policy architecture shape; training skipped.")
            else:
                errors.append("Contract probe failed; training skipped.")

    train_exit_code = None
    duration_seconds = None
    command_txt = None

    if not errors:
        train_cmd = [
            sys.executable,
            str(train_script),
            "--exp-name",
            run_id,
            "--total-timesteps",
            str(args.total_timesteps),
            "--seed",
            str(args.seed),
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
            "--map-path",
            args.map_path,
            "--max-steps",
            "2000",
            "--expected-map-size",
            "24",
            "--verify-contract",
            "true" if args.require_contract_check else "false",
        ]
        if args.device == "cpu":
            train_cmd += ["--cuda", "false"]
        else:
            train_cmd += ["--cuda", "true"]

        env = os.environ.copy()
        if args.no_wandb:
            env["WANDB_MODE"] = "disabled"

        command_txt = " ".join(train_cmd)
        (log_dir / "training_command.txt").write_text(command_txt + "\n", encoding="utf-8")

        t0 = time.time()
        with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
            proc = subprocess.run(train_cmd, cwd=str(repo_root), env=env, stdout=out, stderr=err, check=False, text=True)
            train_exit_code = int(proc.returncode)
        duration_seconds = time.time() - t0

        if train_exit_code != 0:
            errors.append(f"Training subprocess failed with exit code {train_exit_code}.")

    metrics = _parse_training_stdout(stdout_path)
    _write_jsonl(metrics_path, metrics["events"])

    checkpoint_path = model_dir / "agent_final.pt"
    metadata_path = model_dir / "model_metadata.json"
    checkpoint_saved = checkpoint_path.exists()
    metadata_saved = metadata_path.exists()

    if not checkpoint_saved:
        errors.append("agent_final.pt not found in stage4 smoke output model directory.")

    if not metadata_saved:
        errors.append("model_metadata.json not found in stage4 smoke output model directory.")

    status = "PASS" if not errors else "BLOCKED_TRAINING_FAILED"
    if errors and isinstance(contract_probe_result, dict):
        if contract_probe_result.get("status") == "BLOCKED_POLICY_ARCHITECTURE_SHAPE":
            status = "BLOCKED_POLICY_ARCHITECTURE_SHAPE"

    payload: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "run_label": args.run_label,
        "status": status,
        "map_path": args.map_path,
        "seed": args.seed,
        "device": args.device,
        "total_timesteps_requested": args.total_timesteps,
        "duration_seconds": duration_seconds,
        "training_exit_code": train_exit_code,
        "checkpoint_saved": checkpoint_saved,
        "metadata_saved": metadata_saved,
        "checkpoint_path": str(checkpoint_path) if checkpoint_saved else None,
        "metadata_path": str(metadata_path) if metadata_saved else None,
        "stdout_log_path": str(stdout_path),
        "stderr_log_path": str(stderr_path),
        "metrics_jsonl_path": str(metrics_path),
        "episode_count": metrics["episode_count"],
        "total_steps_observed": metrics["total_steps_observed"],
        "final_reward_mean": metrics["final_reward_mean"],
        "warnings": warnings,
        "errors": errors,
        "require_contract_check": args.require_contract_check,
        "contract_probe_json": str(verify_json_path),
        "contract_probe_result": contract_probe_result,
        "command_used": command_txt,
    }

    out_json = report_dir / f"stage4_24x24_smoke_training_{ts}.json"
    out_md = report_dir / f"stage4_24x24_smoke_training_{ts}.md"

    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

    lines = [
        "# Stage 4 24x24 Smoke Training",
        "",
        f"- run_id: {run_id}",
        f"- status: {status}",
        f"- map_path: {args.map_path}",
        f"- checkpoint_path: {checkpoint_path if checkpoint_saved else 'none'}",
        f"- metadata_path: {metadata_path if metadata_saved else 'none'}",
        f"- contract_probe_json: {verify_json_path}",
        "",
        "## Metrics",
        "",
        f"- episode_count: {metrics['episode_count']}",
        f"- total_steps_observed: {metrics['total_steps_observed']}",
        f"- final_reward_mean: {metrics['final_reward_mean']}",
        "",
        "## Warnings",
        "",
    ]

    if warnings:
        lines.extend([f"- {w}" for w in warnings])
    else:
        lines.append("- none")

    lines.extend(["", "## Errors", ""])
    if errors:
        lines.extend([f"- {e}" for e in errors])
    else:
        lines.append("- none")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": status,
                "json_report": str(out_json),
                "md_report": str(out_md),
                "checkpoint_path": str(checkpoint_path) if checkpoint_saved else None,
                "metadata_path": str(metadata_path) if metadata_saved else None,
            },
            indent=2,
        )
    )

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
