from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


CLASS_LOCAL_RESUME_VALIDATED = "LOCAL_RESUME_VALIDATED"
CLASS_LOCAL_RESUME_FAILED = "LOCAL_RESUME_FAILED"
CLASS_LOCAL_RESUME_NOT_TESTED = "LOCAL_RESUME_NOT_TESTED"


def _now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _parse_bool(value: str) -> bool:
    v = str(value).strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _run(cmd, cwd: Path, env: Dict[str, str], stdout_path: Path, stderr_path: Path) -> int:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
        proc = subprocess.run(cmd, cwd=str(cwd), env=env, stdout=out, stderr=err, text=True, check=False)
    return int(proc.returncode)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate legacy032 local full-checkpoint resume pipeline")
    p.add_argument("--run-label", default="legacy032_local_resume_validation")
    p.add_argument("--stage1-timesteps", type=int, default=25000)
    p.add_argument("--stage2-timesteps", type=int, default=50000)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    p.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    p.add_argument("--max-steps", type=int, default=6000)
    p.add_argument("--output-root", default="python/week5_teacher_legacy032/reports")
    p.add_argument("--strict-resume-config", type=_parse_bool, default=True)
    p.add_argument("--python-exe", default=sys.executable, help="Python executable used to run trainer")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = _repo_root()
    ts = _now_compact()

    report_root = (repo_root / args.output_root).resolve()
    work_root = report_root / f"legacy032_local_resume_validation_work_{ts}"
    stage1_dir = work_root / "stage_1"
    stage2_dir = work_root / "stage_2"
    logs_dir = work_root / "logs"

    trainer_script = repo_root / "python" / "week5_teacher_legacy032" / "scripts" / "ppo_gridnet_legacy032_24x24_local_save.py"

    env = os.environ.copy()

    stage1_cmd = [
        str(args.python_exe),
        str(trainer_script),
        "--exp-name",
        f"{args.run_label}_{ts}",
        "--total-timesteps",
        str(args.stage1_timesteps),
        "--schedule-total-timesteps",
        str(args.stage2_timesteps),
        "--map-path",
        args.map_path,
        "--expected-map-size",
        "24",
        "--max-steps",
        str(args.max_steps),
        "--verify-contract",
        "true",
        "--local-save-model",
        "true",
        "--local-save-dir",
        str(stage1_dir),
        "--local-save-every",
        str(args.stage1_timesteps),
        "--save-full-training-state",
        "true",
        "--num-bot-envs",
        "6",
        "--num-selfplay-envs",
        "0",
        "--seed",
        str(args.seed),
        "--cuda",
        "false" if args.device == "cpu" else "true",
    ]

    stage1_exit = _run(
        stage1_cmd,
        repo_root,
        env,
        logs_dir / "stage1_stdout.log",
        logs_dir / "stage1_stderr.log",
    )

    stage1_full_ckpt = stage1_dir / "trainer_state_final.pt"
    stage1_report = _read_json(stage1_dir / "training_machine_report.json")

    stage2_cmd = [
        str(args.python_exe),
        str(trainer_script),
        "--exp-name",
        f"{args.run_label}_{ts}",
        "--total-timesteps",
        str(args.stage2_timesteps),
        "--schedule-total-timesteps",
        str(args.stage2_timesteps),
        "--map-path",
        args.map_path,
        "--expected-map-size",
        "24",
        "--max-steps",
        str(args.max_steps),
        "--verify-contract",
        "true",
        "--local-save-model",
        "true",
        "--local-save-dir",
        str(stage2_dir),
        "--local-save-every",
        str(args.stage2_timesteps),
        "--save-full-training-state",
        "true",
        "--resume-from-local-checkpoint",
        str(stage1_full_ckpt),
        "--resume-required",
        "true",
        "--strict-resume-config",
        "true" if args.strict_resume_config else "false",
        "--num-bot-envs",
        "6",
        "--num-selfplay-envs",
        "0",
        "--seed",
        str(args.seed),
        "--cuda",
        "false" if args.device == "cpu" else "true",
    ]

    stage2_exit = _run(
        stage2_cmd,
        repo_root,
        env,
        logs_dir / "stage2_stdout.log",
        logs_dir / "stage2_stderr.log",
    )

    stage2_report = _read_json(stage2_dir / "training_machine_report.json")
    stage2_full_ckpt = stage2_dir / "trainer_state_final.pt"

    checks = {
        "stage1_exit_zero": stage1_exit == 0,
        "stage2_exit_zero": stage2_exit == 0,
        "stage1_full_checkpoint_exists": stage1_full_ckpt.exists(),
        "stage2_full_checkpoint_exists": stage2_full_ckpt.exists(),
        "stage2_resume_status_resumed": bool(stage2_report and stage2_report.get("RESUME_STATUS") == "RESUMED_FROM_FULL_CHECKPOINT"),
        "stage2_optimizer_restored": bool(stage2_report and stage2_report.get("optimizer_state_restored") is True),
        "stage2_rng_restored": bool(stage2_report and stage2_report.get("rng_state_restored") is True),
        "stage2_strict_agent_load": bool(stage2_report and stage2_report.get("strict_agent_load") is True),
        "stage2_global_step_increased": bool(
            stage2_report
            and stage1_report
            and int(stage2_report.get("global_step_end", 0)) > int(stage1_report.get("global_step_end", 0))
        ),
        "stage2_no_scratch_fallback": bool(stage2_report and stage2_report.get("RESUME_STATUS") != "STARTED_FROM_SCRATCH"),
    }

    all_pass = all(checks.values())
    classification = CLASS_LOCAL_RESUME_VALIDATED if all_pass else CLASS_LOCAL_RESUME_FAILED
    if stage1_exit != 0 and stage2_exit != 0:
        classification = CLASS_LOCAL_RESUME_NOT_TESTED

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "classification": classification,
        "run_label": args.run_label,
        "python_exe": str(args.python_exe),
        "stage1_timesteps": int(args.stage1_timesteps),
        "stage2_timesteps": int(args.stage2_timesteps),
        "stage1_exit_code": int(stage1_exit),
        "stage2_exit_code": int(stage2_exit),
        "stage1_dir": str(stage1_dir),
        "stage2_dir": str(stage2_dir),
        "stage1_trainer_report": str(stage1_dir / "training_machine_report.json"),
        "stage2_trainer_report": str(stage2_dir / "training_machine_report.json"),
        "checks": checks,
        "stage1_report": stage1_report,
        "stage2_report": stage2_report,
    }

    report_root.mkdir(parents=True, exist_ok=True)
    json_out = report_root / f"legacy032_local_resume_validation_{ts}.json"
    md_out = report_root / f"legacy032_local_resume_validation_{ts}.md"
    json_out.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

    md_lines = [
        "# Legacy032 Local Resume Validation",
        "",
        f"- classification: {classification}",
        f"- stage1_exit_code: {stage1_exit}",
        f"- stage2_exit_code: {stage2_exit}",
        f"- stage1_dir: {stage1_dir}",
        f"- stage2_dir: {stage2_dir}",
        f"- json_report: {json_out}",
        "",
        "## Checks",
        "",
    ]
    for key, value in checks.items():
        md_lines.append(f"- {key}: {value}")

    md_out.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "classification": classification,
        "json_report": str(json_out),
        "md_report": str(md_out),
    }, indent=2))
    return 0 if classification == CLASS_LOCAL_RESUME_VALIDATED else 1


if __name__ == "__main__":
    raise SystemExit(main())
