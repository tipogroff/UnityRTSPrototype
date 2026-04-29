from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


EXPECTED_OBS = [24, 24, 27]
EXPECTED_NVEC = [576, 6, 4, 4, 4, 4, 7, 49]
EXPECTED_ARCH = "legacy032_resolution_aware_gridnet_v1"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _parse_bool(value: str) -> bool:
    if isinstance(value, bool):
        return value
    v = str(value).strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def _parse_stages(value: str) -> List[int]:
    chunks = [x.strip() for x in value.split(",") if x.strip()]
    if not chunks:
        raise argparse.ArgumentTypeError("--stages must contain at least one integer")
    out = sorted({int(x) for x in chunks})
    if any(x <= 0 for x in out):
        raise argparse.ArgumentTypeError("All stage values must be positive")
    return out


def _run_cmd(
    cmd: List[str],
    cwd: Path,
    env: Dict[str, str],
    stdout_path: Path,
    stderr_path: Path,
    dry_run: bool,
) -> int:
    if dry_run:
        stdout_path.write_text("[dry-run] command not executed\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return 0
    with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
        proc = subprocess.run(cmd, cwd=str(cwd), env=env, stdout=out, stderr=err, text=True, check=False)
    return int(proc.returncode)


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")


def _parse_training_metrics(stdout_path: Path) -> Dict[str, Any]:
    events: List[Dict[str, Any]] = []
    episode_count = 0
    last_global_step = 0
    rewards: List[float] = []

    if not stdout_path.exists():
        return {
            "events": events,
            "episode_count": episode_count,
            "last_global_step": last_global_step,
            "mean_episode_reward": None,
        }

    for line in stdout_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if "global_step=" not in line or "episode_reward=" not in line:
            continue
        try:
            left, right = line.split("global_step=", 1)
            step_part, reward_part = right.split(",", 1)
            step_val = int(step_part.strip())
            reward_val = float(reward_part.split("episode_reward=")[-1].strip())
            episode_count += 1
            last_global_step = max(last_global_step, step_val)
            rewards.append(reward_val)
            events.append({"event": "episode_reward", "global_step": step_val, "reward": reward_val})
        except Exception:
            continue

    mean_reward = None
    if rewards:
        mean_reward = float(sum(rewards) / len(rewards))

    return {
        "events": events,
        "episode_count": episode_count,
        "last_global_step": last_global_step,
        "mean_episode_reward": mean_reward,
    }


def _find_latest_gate_report(report_dir: Path, run_label: str) -> Optional[Path]:
    candidates = sorted(report_dir.glob(f"{run_label}_*.json"))
    if not candidates:
        return None
    return candidates[-1]


def _bool_status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run corrected Stage 5 24x24 staged legacy032 teacher training.")
    parser.add_argument("--run-label", default="legacy032_24x24_teacher_main")
    parser.add_argument("--stages", type=_parse_stages, default=[100000, 500000, 1000000, 3000000, 5000000])
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    parser.add_argument("--output-root", default="python/week5_teacher_legacy032")
    parser.add_argument("--evaluate-after-each", nargs="?", const="true", default="true", type=_parse_bool)
    parser.add_argument("--episodes-per-gate", type=int, default=8)
    parser.add_argument("--no-wandb", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--continue-on-gate-warning", action="store_true", default=False)
    parser.add_argument("--stop-on-gate-fail", action="store_true", default=False)
    parser.add_argument("--require-contract-check", nargs="?", const="true", default="true", type=_parse_bool)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = _repo_root()
    now_ts = _ts()
    run_id = f"{args.run_label}_{now_ts}"

    out_root = Path(args.output_root)
    if not out_root.is_absolute():
        out_root = (repo_root / out_root).resolve()

    model_root = out_root / "teacher_models" / run_id
    log_root = out_root / "teacher_logs" / run_id
    report_root = out_root / "reports"

    for d in [model_root, log_root, report_root]:
        d.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    if args.no_wandb:
        env["WANDB_MODE"] = "disabled"

    verify_script = repo_root / "python" / "week5_teacher_legacy032" / "scripts" / "verify_legacy032_24x24_training_contract.py"
    train_script = repo_root / "python" / "week5_teacher_legacy032" / "scripts" / "ppo_gridnet_legacy032_24x24_local_save.py"
    eval_script = repo_root / "python" / "week5_teacher_legacy032" / "scripts" / "evaluate_teacher_legacy032.py"

    preflight_json = report_root / "stage5a_24x24_contract_probe.json"
    preflight_status = "SKIPPED"
    preflight_result: Optional[Dict[str, Any]] = None
    preflight_errors: List[str] = []

    if args.require_contract_check:
        preflight_cmd = [
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
            str(preflight_json),
        ]
        preflight_stdout = log_root / "preflight_stdout.log"
        preflight_stderr = log_root / "preflight_stderr.log"
        preflight_exit = _run_cmd(preflight_cmd, repo_root, env, preflight_stdout, preflight_stderr, args.dry_run)
        preflight_result = _read_json(preflight_json)
        preflight_status = "PASS" if preflight_exit == 0 else "FAIL"
        if preflight_exit != 0:
            preflight_errors.append(f"Contract probe failed with exit code {preflight_exit}")
        if isinstance(preflight_result, dict):
            for field in [
                "status",
                "observation_space",
                "action_space_nvec",
                "mask_available",
                "policy_forward_ok",
                "masked_action_sample_ok",
                "env_step_ok",
            ]:
                if field not in preflight_result:
                    preflight_errors.append(f"Contract probe missing field: {field}")
        else:
            preflight_errors.append("Contract probe JSON missing or unreadable")

    stages: List[int] = list(args.stages)
    stage_rows: List[Dict[str, Any]] = []
    fatal_errors: List[str] = []

    if args.require_contract_check and preflight_status != "PASS":
        fatal_errors.extend(preflight_errors)

    for stage in stages:
        stage_name = f"stage_{stage:09d}"
        stage_model_dir = model_root / stage_name
        stage_log_dir = log_root / stage_name
        stage_model_dir.mkdir(parents=True, exist_ok=True)
        stage_log_dir.mkdir(parents=True, exist_ok=True)

        stage_row: Dict[str, Any] = {
            "stage": int(stage),
            "stage_name": stage_name,
            "training_exit_code": None,
            "training_status": "SKIPPED",
            "checkpoint_path": None,
            "metadata_path": None,
            "checkpoint_saved": False,
            "metadata_saved": False,
            "metadata_contract_ok": False,
            "metadata_contract": {},
            "gate_requested": bool(args.evaluate_after_each),
            "gate_exit_code": None,
            "gate_status": "SKIPPED",
            "gate_json_report": None,
            "gate_md_report": None,
            "gate_decision": None,
            "gate_checks": {},
            "warnings": [],
            "errors": [],
        }

        if fatal_errors:
            stage_row["errors"].append("Skipped because preflight failed")
            stage_rows.append(stage_row)
            continue

        train_cmd = [
            sys.executable,
            str(train_script),
            "--exp-name",
            run_id,
            "--total-timesteps",
            str(stage),
            "--map-path",
            args.map_path,
            "--expected-map-size",
            "24",
            "--verify-contract",
            "true",
            "--local-save-model",
            "true",
            "--local-save-dir",
            str(stage_model_dir),
            "--local-save-every",
            str(stage),
            "--num-bot-envs",
            "6",
            "--num-selfplay-envs",
            "0",
            "--seed",
            str(args.seed),
        ]
        train_cmd += ["--cuda", "false" if args.device == "cpu" else "true"]

        train_stdout = stage_log_dir / "training_stdout.log"
        train_stderr = stage_log_dir / "training_stderr.log"
        (stage_log_dir / "training_command.txt").write_text(" ".join(train_cmd) + "\n", encoding="utf-8")

        t0 = time.time()
        train_exit = _run_cmd(train_cmd, repo_root, env, train_stdout, train_stderr, args.dry_run)
        duration_sec = float(time.time() - t0)

        stage_row["training_exit_code"] = int(train_exit)
        stage_row["training_status"] = "PASS" if train_exit == 0 else "FAIL"
        stage_row["training_duration_seconds"] = duration_sec

        metrics = _parse_training_metrics(train_stdout)
        _write_jsonl(stage_log_dir / "training_metrics.jsonl", metrics["events"])
        stage_row["training_metrics_summary"] = {
            "episode_count": metrics["episode_count"],
            "last_global_step": metrics["last_global_step"],
            "mean_episode_reward": metrics["mean_episode_reward"],
        }

        step_ckpt = stage_model_dir / f"agent_step_{stage:09d}.pt"
        final_ckpt = stage_model_dir / "agent_final.pt"
        metadata_path = stage_model_dir / "model_metadata.json"

        chosen_checkpoint = step_ckpt if step_ckpt.exists() else final_ckpt
        stage_row["checkpoint_path"] = str(chosen_checkpoint) if chosen_checkpoint.exists() else None
        stage_row["metadata_path"] = str(metadata_path) if metadata_path.exists() else None
        stage_row["checkpoint_saved"] = bool(chosen_checkpoint.exists())
        stage_row["metadata_saved"] = bool(metadata_path.exists())

        if not stage_row["checkpoint_saved"]:
            stage_row["errors"].append("Checkpoint not found (agent_step or agent_final)")
        if not stage_row["metadata_saved"]:
            stage_row["errors"].append("model_metadata.json not found")

        metadata = _read_json(metadata_path) if metadata_path.exists() else None
        if isinstance(metadata, dict):
            md_arch = metadata.get("architecture_name")
            md_obs = metadata.get("observation_space")
            md_nvec = metadata.get("action_space_nvec")
            stage_row["metadata_contract"] = {
                "architecture_name": md_arch,
                "observation_space": md_obs,
                "action_space_nvec": md_nvec,
            }
            md_ok = md_arch == EXPECTED_ARCH and md_obs == EXPECTED_OBS and md_nvec == EXPECTED_NVEC
            stage_row["metadata_contract_ok"] = bool(md_ok)
            if not md_ok:
                stage_row["errors"].append("Metadata contract mismatch")
        else:
            stage_row["errors"].append("Metadata unreadable")

        if args.evaluate_after_each and stage_row["checkpoint_saved"] and stage_row["metadata_saved"]:
            gate_label = f"stage5_gate_{stage:09d}"
            eval_cmd = [
                sys.executable,
                str(eval_script),
                "--checkpoint-path",
                str(chosen_checkpoint),
                "--model-metadata-path",
                str(metadata_path),
                "--run-label",
                gate_label,
                "--episodes",
                str(args.episodes_per_gate),
                "--seed",
                str(args.seed),
                "--device",
                args.device,
                "--output-dir",
                str(report_root),
                "--eval-mode",
                "both",
                "--env-mode",
                "target_24x24_gridmode",
                "--require-mask",
                "true",
                "--max-steps-per-episode",
                "2000",
            ]
            eval_stdout = stage_log_dir / "evaluation_stdout.log"
            eval_stderr = stage_log_dir / "evaluation_stderr.log"
            (stage_log_dir / "evaluation_command.txt").write_text(" ".join(eval_cmd) + "\n", encoding="utf-8")
            eval_exit = _run_cmd(eval_cmd, repo_root, env, eval_stdout, eval_stderr, args.dry_run)
            stage_row["gate_exit_code"] = int(eval_exit)

            gate_json = _find_latest_gate_report(report_root, gate_label)
            gate_payload = _read_json(gate_json) if gate_json else None
            if gate_json is not None:
                stage_row["gate_json_report"] = str(gate_json)
                md_candidate = gate_json.with_suffix(".md")
                if md_candidate.exists():
                    stage_row["gate_md_report"] = str(md_candidate)

            if isinstance(gate_payload, dict):
                stage_row["gate_decision"] = gate_payload.get("gate_decision")
                eval_result = gate_payload.get("eval_result") or {}
                action_share = eval_result.get("action_type_share")
                stage_row["gate_checks"] = {
                    "checkpoint_load_ok": bool(gate_payload.get("checkpoint_load_ok", False)),
                    "policy_architecture_load_ok": bool(gate_payload.get("policy_architecture_load_ok", False)),
                    "inference_ok": bool(gate_payload.get("inference_ok", False)),
                    "eval_observation_shape": gate_payload.get("eval_observation_shape"),
                    "eval_action_space": gate_payload.get("eval_action_space"),
                    "env_matches_target_24x24": bool(gate_payload.get("env_matches_target_24x24", False)),
                    "mask_used_during_eval": bool(gate_payload.get("mask_used_during_eval", False)),
                    "action_type_counts": eval_result.get("action_type_counts"),
                    "action_type_share": action_share,
                    "mean_return": eval_result.get("mean_return"),
                    "effective_activity_share": eval_result.get("effective_activity_share"),
                    "noop_share": eval_result.get("noop_share"),
                    "move_share": eval_result.get("move_share"),
                    "attack_action_count": eval_result.get("attack_action_count"),
                    "produce_action_count": eval_result.get("produce_action_count"),
                    "policy_entropy_proxy": eval_result.get("policy_entropy_proxy"),
                }
                stage_row["gate_status"] = "PASS" if eval_exit == 0 else "FAIL"
            else:
                stage_row["gate_status"] = "FAIL"
                stage_row["errors"].append("Gate report JSON missing or unreadable")

        has_fatal_gate = False
        gate_checks = stage_row.get("gate_checks", {})
        if stage_row["gate_requested"]:
            required_flags = [
                bool(gate_checks.get("checkpoint_load_ok", False)),
                bool(gate_checks.get("policy_architecture_load_ok", False)),
                bool(gate_checks.get("inference_ok", False)),
                bool(gate_checks.get("env_matches_target_24x24", False)),
                bool(gate_checks.get("mask_used_during_eval", False)),
                gate_checks.get("action_type_counts") is not None,
            ]
            if not all(required_flags):
                has_fatal_gate = True
                stage_row["errors"].append("Gate technical checks did not pass")

        if has_fatal_gate and args.stop_on_gate_fail:
            fatal_errors.append(f"Stopping on gate fail at stage {stage}")

        if stage_row["gate_decision"] == "PASS_WITH_WARNINGS" and not args.continue_on_gate_warning:
            stage_row["warnings"].append("Gate is PASS_WITH_WARNINGS; continue-on-gate-warning is disabled")

        stage_rows.append(stage_row)

        if fatal_errors:
            break

    primary_stage = stage_rows[0] if stage_rows else None
    decision = "FAIL"
    decision_reasons: List[str] = []

    if primary_stage is None:
        decision = "FAIL"
        decision_reasons.append("No stage execution result produced")
    else:
        tech_checks = [
            preflight_status == "PASS" if args.require_contract_check else True,
            primary_stage.get("training_exit_code") == 0,
            bool(primary_stage.get("checkpoint_saved")),
            bool(primary_stage.get("metadata_saved")),
            bool(primary_stage.get("metadata_contract_ok")),
            primary_stage.get("gate_requested") is False or primary_stage.get("gate_json_report") is not None,
        ]
        gate_checks = primary_stage.get("gate_checks", {}) if isinstance(primary_stage, dict) else {}
        gate_tech = [
            bool(gate_checks.get("checkpoint_load_ok", False)),
            bool(gate_checks.get("policy_architecture_load_ok", False)),
            bool(gate_checks.get("inference_ok", False)),
            bool(gate_checks.get("env_matches_target_24x24", False)),
            bool(gate_checks.get("mask_used_during_eval", False)),
            gate_checks.get("action_type_counts") is not None,
        ]

        if not all(tech_checks) or (primary_stage.get("gate_requested") and not all(gate_tech)):
            decision = "FAIL"
        else:
            eff = gate_checks.get("effective_activity_share")
            if eff is None or float(eff) <= 0.0:
                decision = "PASS_WITH_WARNINGS"
                decision_reasons.append("effective_activity_share is zero or missing")
            elif primary_stage.get("gate_decision") == "PASS_WITH_WARNINGS":
                decision = "PASS_WITH_WARNINGS"
                decision_reasons.append("gate decision is PASS_WITH_WARNINGS")
            else:
                decision = "PASS"

    if preflight_status != "PASS" and args.require_contract_check:
        decision_reasons.append("Preflight contract probe did not PASS")
    if fatal_errors:
        decision_reasons.extend(fatal_errors)

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "run_label": args.run_label,
        "status": decision,
        "decision": (
            "READY_FOR_500K"
            if decision == "PASS"
            else "READY_FOR_500K_WITH_WARNINGS" if decision == "PASS_WITH_WARNINGS" else "BLOCKED"
        ),
        "decision_reasons": decision_reasons,
        "config": {
            "stages": stages,
            "seed": args.seed,
            "device": args.device,
            "map_path": args.map_path,
            "output_root": str(out_root),
            "evaluate_after_each": bool(args.evaluate_after_each),
            "episodes_per_gate": int(args.episodes_per_gate),
            "no_wandb": bool(args.no_wandb),
            "dry_run": bool(args.dry_run),
            "continue_on_gate_warning": bool(args.continue_on_gate_warning),
            "stop_on_gate_fail": bool(args.stop_on_gate_fail),
            "require_contract_check": bool(args.require_contract_check),
        },
        "preflight": {
            "status": preflight_status,
            "report_json": str(preflight_json),
            "result": preflight_result,
            "errors": preflight_errors,
        },
        "stages": stage_rows,
    }

    out_json = report_root / f"stage5_24x24_training_{now_ts}.json"
    out_md = report_root / f"stage5_24x24_training_{now_ts}.md"
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")

    md_lines: List[str] = [
        "# Stage 5 24x24 Training Run",
        "",
        f"- run_id: {run_id}",
        f"- status: {decision}",
        f"- decision: {summary['decision']}",
        f"- preflight_status: {preflight_status}",
        f"- json_report: {out_json}",
        "",
        "## Stage Results",
        "",
        "| stage | training | checkpoint | metadata | metadata_contract | gate | gate_decision | mean_return | effective_activity_share |",
        "|---|---|---|---|---|---|---|---:|---:|",
    ]

    for row in stage_rows:
        gate_checks = row.get("gate_checks", {}) if isinstance(row, dict) else {}
        md_lines.append(
            "| {stage} | {tr} | {ckpt} | {md} | {mco} | {gs} | {gd} | {mr} | {ea} |".format(
                stage=row.get("stage"),
                tr=row.get("training_status"),
                ckpt=_bool_status(bool(row.get("checkpoint_saved"))),
                md=_bool_status(bool(row.get("metadata_saved"))),
                mco=_bool_status(bool(row.get("metadata_contract_ok"))),
                gs=row.get("gate_status"),
                gd=row.get("gate_decision") or "-",
                mr="-" if gate_checks.get("mean_return") is None else f"{float(gate_checks['mean_return']):.6f}",
                ea="-"
                if gate_checks.get("effective_activity_share") is None
                else f"{float(gate_checks['effective_activity_share']):.6f}",
            )
        )

    md_lines.extend(["", "## Decision Reasons", ""])
    if decision_reasons:
        for reason in decision_reasons:
            md_lines.append(f"- {reason}")
    else:
        md_lines.append("- none")
    out_md.write_text("\n".join(md_lines), encoding="utf-8")

    stage5a_report = report_root / "STAGE5A_100K_TRAINING_REPORT.md"
    completion_report = report_root / "STAGE5A_COMPLETION_REPORT.md"

    first_gate_json = None
    first_gate_md = None
    first_ckpt = None
    first_metadata = None
    first_gate = {}
    if primary_stage:
        first_gate_json = primary_stage.get("gate_json_report")
        first_gate_md = primary_stage.get("gate_md_report")
        first_ckpt = primary_stage.get("checkpoint_path")
        first_metadata = primary_stage.get("metadata_path")
        first_gate = primary_stage.get("gate_checks", {}) if isinstance(primary_stage, dict) else {}

    stage5a_lines = [
        "# STAGE5A 100K Training Report",
        "",
        f"- Date: {datetime.now(timezone.utc).isoformat()}",
        f"- run_id: {run_id}",
        f"- Stage 5A status: {decision}",
        f"- Decision: {summary['decision']}",
        "",
        "## Summary",
        "",
        "- Scope: Stage 5A only (100k checkpoint on corrected 24x24 GridMode path).",
        "- Stages requested: 100000.",
        "- 500k/1M/3M/5M not executed in this run.",
        "",
        "## Commands Run",
        "",
        f"- preflight: {verify_script}",
        f"- train: {train_script}",
        f"- gate eval: {eval_script}",
        "",
        "## Preflight Contract Probe",
        "",
        f"- report: {preflight_json}",
        f"- status: {preflight_status}",
        f"- observation_space: {None if not preflight_result else preflight_result.get('observation_space')}",
        f"- action_space_nvec: {None if not preflight_result else preflight_result.get('action_space_nvec')}",
        f"- mask_available: {None if not preflight_result else preflight_result.get('mask_available')}",
        f"- policy_forward_ok: {None if not preflight_result else preflight_result.get('policy_forward_ok')}",
        f"- masked_action_sample_ok: {None if not preflight_result else preflight_result.get('masked_action_sample_ok')}",
        f"- env_step_ok: {None if not preflight_result else preflight_result.get('env_step_ok')}",
        "",
        "## Training Result",
        "",
        f"- checkpoint_path: {first_ckpt}",
        f"- model_metadata_path: {first_metadata}",
        f"- machine_report_json: {out_json}",
        f"- machine_report_md: {out_md}",
        "",
        "## Metadata Contract",
        "",
        f"- architecture_name_expected: {EXPECTED_ARCH}",
        f"- observation_space_expected: {EXPECTED_OBS}",
        f"- action_space_nvec_expected: {EXPECTED_NVEC}",
        f"- architecture_name_actual: {None if not primary_stage else primary_stage.get('metadata_contract', {}).get('architecture_name')}",
        f"- observation_space_actual: {None if not primary_stage else primary_stage.get('metadata_contract', {}).get('observation_space')}",
        f"- action_space_nvec_actual: {None if not primary_stage else primary_stage.get('metadata_contract', {}).get('action_space_nvec')}",
        "",
        "## Behavior Gate Result",
        "",
        f"- gate_json_report: {first_gate_json}",
        f"- gate_md_report: {first_gate_md}",
        f"- gate_decision: {None if not primary_stage else primary_stage.get('gate_decision')}",
        f"- checkpoint_load_ok: {first_gate.get('checkpoint_load_ok')}",
        f"- policy_architecture_load_ok: {first_gate.get('policy_architecture_load_ok')}",
        f"- inference_ok: {first_gate.get('inference_ok')}",
        f"- env_matches_target_24x24: {first_gate.get('env_matches_target_24x24')}",
        f"- mask_used_during_eval: {first_gate.get('mask_used_during_eval')}",
        "",
        "## Metrics Table",
        "",
        "| metric | value |",
        "|---|---|",
        f"| mean_return | {first_gate.get('mean_return')} |",
        f"| effective_activity_share | {first_gate.get('effective_activity_share')} |",
        f"| noop_share | {first_gate.get('noop_share')} |",
        f"| move_share | {first_gate.get('move_share')} |",
        f"| attack_action_count | {first_gate.get('attack_action_count')} |",
        f"| produce_action_count | {first_gate.get('produce_action_count')} |",
        f"| policy_entropy_proxy | {first_gate.get('policy_entropy_proxy')} |",
        f"| action_type_share | {first_gate.get('action_type_share')} |",
        "",
        "## Warnings / Errors",
        "",
    ]

    warnings_added = False
    if primary_stage and primary_stage.get("warnings"):
        for w in primary_stage["warnings"]:
            stage5a_lines.append(f"- warning: {w}")
            warnings_added = True
    if primary_stage and primary_stage.get("errors"):
        for e in primary_stage["errors"]:
            stage5a_lines.append(f"- error: {e}")
            warnings_added = True
    if preflight_errors:
        for e in preflight_errors:
            stage5a_lines.append(f"- preflight_error: {e}")
            warnings_added = True
    if not warnings_added:
        stage5a_lines.append("- none")

    stage5a_lines.extend(
        [
            "",
            "## Recommendation",
            "",
            (
                "- Continue to 500k stage: YES"
                if decision in {"PASS", "PASS_WITH_WARNINGS"}
                else "- Continue to 500k stage: NO (fix blockers first)"
            ),
        ]
    )
    stage5a_report.write_text("\n".join(stage5a_lines), encoding="utf-8")

    completion_lines = [
        "# STAGE5A Completion Report",
        "",
        f"- Date: {datetime.now(timezone.utc).isoformat()}",
        f"- run_id: {run_id}",
        f"- status: {decision}",
        "",
        "## Files Created / Updated",
        "",
        f"- {preflight_json}",
        f"- {out_json}",
        f"- {out_md}",
        f"- {stage5a_report}",
        f"- {completion_report}",
    ]
    if first_gate_json:
        completion_lines.append(f"- {first_gate_json}")
    if first_gate_md:
        completion_lines.append(f"- {first_gate_md}")

    completion_lines.extend(
        [
            "",
            "## Stage Checkpoint",
            "",
            f"- checkpoint_path: {first_ckpt}",
            f"- metadata_path: {first_metadata}",
            "",
            "## Current Status",
            "",
            f"- {summary['decision']}",
            "",
            "## Exact Next Action",
            "",
            (
                "- Run Stage 5B 500k only after explicit approval, using the same corrected 24x24 pipeline."
                if decision in {"PASS", "PASS_WITH_WARNINGS"}
                else "- Resolve Stage 5A blocker(s), then re-run Stage 5A 100k."
            ),
        ]
    )
    completion_report.write_text("\n".join(completion_lines), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": decision,
                "decision": summary["decision"],
                "run_id": run_id,
                "report_json": str(out_json),
                "report_md": str(out_md),
                "stage5a_report": str(stage5a_report),
                "completion_report": str(completion_report),
            },
            indent=2,
        )
    )
    return 0 if decision in {"PASS", "PASS_WITH_WARNINGS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
