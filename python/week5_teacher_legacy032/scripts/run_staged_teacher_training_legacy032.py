from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _default_reference_script() -> str:
    return str(
        _repo_root()
        / "python"
        / "week5_teacher_reference"
        / "patched_paper_scripts"
        / "ppo_gridnet_diverse_encode_decode_local_save.py"
    )


def _default_eval_script() -> str:
    return str(_repo_root() / "python" / "week5_teacher_legacy032" / "scripts" / "evaluate_teacher_legacy032.py")


def _parse_stages(value: str) -> List[int]:
    chunks = [x.strip() for x in value.split(",") if x.strip()]
    if not chunks:
        raise argparse.ArgumentTypeError("--stages must contain at least one integer.")
    out = sorted({int(x) for x in chunks})
    if any(x <= 0 for x in out):
        raise argparse.ArgumentTypeError("All stage timesteps must be > 0.")
    return out


def _find_step_checkpoint(model_dir: Path, step: int) -> Optional[Path]:
    exact = model_dir / f"agent_step_{step:09d}.pt"
    if exact.exists():
        return exact

    ckpts = sorted(model_dir.glob("agent_step_*.pt"))
    best = None
    best_step = -1
    for c in ckpts:
        m = re.search(r"agent_step_(\d+)\.pt$", c.name)
        if not m:
            continue
        s = int(m.group(1))
        if s <= step and s > best_step:
            best = c
            best_step = s
    return best


@dataclass
class StageResult:
    stage: int
    stage_dir: str
    checkpoint_path: Optional[str]
    training_status: str
    eval_status: str
    gate_decision: Optional[str]
    eval_report_json: Optional[str]
    eval_report_md: Optional[str]
    mean_return: Optional[float]
    non_noop_share: Optional[float]
    move_share: Optional[float]
    attack_share: Optional[float]
    produce_share: Optional[float]
    mask_used: Optional[bool]
    env_mapping_warning: Optional[str]
    errors: List[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run staged legacy032 teacher training with behavior gates.")
    parser.add_argument("--run-label", default="legacy032_teacher_main")
    parser.add_argument("--stages", type=_parse_stages, default=[100000, 500000, 1000000, 3000000, 5000000])
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--output-root", default="python/week5_teacher_legacy032")
    parser.add_argument("--reference-script-path", default=_default_reference_script())
    parser.add_argument("--evaluate-after-each", action="store_true", default=False)
    parser.add_argument("--episodes-per-gate", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--no-wandb", action="store_true", default=False)
    parser.add_argument("--continue-on-gate-warning", action="store_true", default=False)
    parser.add_argument("--stop-on-gate-fail", action="store_true", default=False)
    return parser.parse_args()


def _run_cmd(cmd: List[str], cwd: Path, env: Dict[str, str], stdout_path: Path, stderr_path: Path, dry_run: bool) -> int:
    if dry_run:
        stdout_path.write_text("[dry-run] command not executed\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return 0

    with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
        proc = subprocess.run(cmd, cwd=str(cwd), env=env, stdout=out, stderr=err, text=True, check=False)
    return int(proc.returncode)


def _read_json_if_exists(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _render_md_summary(
    run_id: str,
    strategy: str,
    stages_planned: List[int],
    stages_run: List[StageResult],
    out_json: Path,
    out_md: Path,
) -> None:
    lines: List[str] = [
        "# Stage 3 Staged Training Run",
        "",
        f"- run_id: {run_id}",
        f"- strategy: {strategy}",
        f"- stages_planned: {stages_planned}",
        f"- stages_run: {[s.stage for s in stages_run]}",
        f"- json_report: {out_json}",
        "",
        "## Stage table",
        "",
        "| timesteps | checkpoint | training | eval | gate | mean_return | non_noop_share | move_share | attack_share | produce_share | mask_used | env warning |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|---|---|",
    ]

    for s in stages_run:
        lines.append(
            "| {t} | {ckpt} | {tr} | {ev} | {gd} | {mr} | {nn} | {mv} | {as_} | {ps} | {mu} | {ew} |".format(
                t=s.stage,
                ckpt=s.checkpoint_path or "-",
                tr=s.training_status,
                ev=s.eval_status,
                gd=s.gate_decision or "-",
                mr=("-" if s.mean_return is None else f"{s.mean_return:.6f}"),
                nn=("-" if s.non_noop_share is None else f"{s.non_noop_share:.6f}"),
                mv=("-" if s.move_share is None else f"{s.move_share:.6f}"),
                as_=("-" if s.attack_share is None else f"{s.attack_share:.6f}"),
                ps=("-" if s.produce_share is None else f"{s.produce_share:.6f}"),
                mu=("-" if s.mask_used is None else str(s.mask_used)),
                ew=s.env_mapping_warning or "-",
            )
        )

    lines.extend(["", "## Errors", ""])
    any_errors = False
    for s in stages_run:
        for e in s.errors:
            any_errors = True
            lines.append(f"- stage {s.stage}: {e}")
    if not any_errors:
        lines.append("- none")

    out_md.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = _repo_root()
    ts = _ts()
    run_id = f"{args.run_label}_{ts}"

    out_root = Path(args.output_root)
    if not out_root.is_absolute():
        out_root = (repo_root / out_root).resolve()

    model_root = out_root / "teacher_models" / run_id
    log_root = out_root / "teacher_logs" / run_id
    report_root = out_root / "reports"

    combined_model_dir = model_root / "_combined_run"
    combined_log_dir = log_root / "_combined_run"

    for d in [model_root, log_root, report_root, combined_model_dir, combined_log_dir]:
        d.mkdir(parents=True, exist_ok=True)

    stages: List[int] = list(args.stages)
    max_stage = max(stages)
    min_stage = min(stages)

    strategy = (
        "single_long_run_with_local_save_every"
        if len(stages) > 1 or min_stage != max_stage
        else "single_stage_run"
    )

    reference_script = Path(args.reference_script_path)
    if not reference_script.is_absolute():
        reference_script = (repo_root / reference_script).resolve()
    if not reference_script.exists():
        raise FileNotFoundError(f"Reference script not found: {reference_script}")

    eval_script = Path(_default_eval_script()).resolve()

    train_cmd = [
        sys.executable,
        str(reference_script),
        "--total-timesteps",
        str(max_stage),
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
        str(combined_model_dir),
        "--local-save-every",
        str(min_stage),
    ]

    if args.device == "cpu":
        train_cmd += ["--cuda", "false"]
    else:
        train_cmd += ["--cuda", "true"]

    env = os.environ.copy()
    if args.no_wandb:
        env["WANDB_MODE"] = "disabled"

    train_stdout = combined_log_dir / "training_stdout.log"
    train_stderr = combined_log_dir / "training_stderr.log"
    (combined_log_dir / "training_command.txt").write_text(" ".join(train_cmd) + "\n", encoding="utf-8")

    train_exit = _run_cmd(
        cmd=train_cmd,
        cwd=repo_root,
        env=env,
        stdout_path=train_stdout,
        stderr_path=train_stderr,
        dry_run=args.dry_run,
    )

    training_status = "PASS" if train_exit == 0 else "FAIL"

    model_metadata_path = combined_model_dir / "model_metadata.json"
    stage_results: List[StageResult] = []

    for stage in stages:
        stage_name = f"stage_{stage:09d}"
        stage_model_dir = model_root / stage_name
        stage_log_dir = log_root / stage_name
        stage_model_dir.mkdir(parents=True, exist_ok=True)
        stage_log_dir.mkdir(parents=True, exist_ok=True)

        errors: List[str] = []
        checkpoint_candidate = _find_step_checkpoint(combined_model_dir, stage)
        if checkpoint_candidate is None and stage == max_stage:
            final_pt = combined_model_dir / "agent_final.pt"
            if final_pt.exists():
                checkpoint_candidate = final_pt

        stage_checkpoint_out: Optional[Path] = None
        if checkpoint_candidate is not None:
            stage_checkpoint_out = stage_model_dir / checkpoint_candidate.name
            if not args.dry_run:
                shutil.copy2(checkpoint_candidate, stage_checkpoint_out)
        else:
            errors.append("No checkpoint found for requested stage.")

        if model_metadata_path.exists() and not args.dry_run:
            shutil.copy2(model_metadata_path, stage_model_dir / "model_metadata.json")
        else:
            errors.append("model_metadata.json not found in combined model directory.")

        # Keep per-stage logs for expected output layout.
        if train_stdout.exists() and not args.dry_run:
            shutil.copy2(train_stdout, stage_log_dir / "training_stdout.log")
        if train_stderr.exists() and not args.dry_run:
            shutil.copy2(train_stderr, stage_log_dir / "training_stderr.log")
        (stage_log_dir / "training_metrics.jsonl").write_text("", encoding="utf-8")

        eval_status = "SKIPPED"
        gate_decision = None
        eval_json_path: Optional[Path] = None
        eval_md_path: Optional[Path] = None
        mean_return = None
        non_noop_share = None
        move_share = None
        attack_share = None
        produce_share = None
        mask_used = None
        env_warning = None

        if args.evaluate_after_each and stage_checkpoint_out is not None and (stage_model_dir / "model_metadata.json").exists():
            eval_status = "FAIL"
            eval_run_label = f"stage3_gate_{stage:09d}"
            eval_cmd = [
                sys.executable,
                str(eval_script),
                "--checkpoint-path",
                str(stage_checkpoint_out),
                "--model-metadata-path",
                str(stage_model_dir / "model_metadata.json"),
                "--run-label",
                eval_run_label,
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
                "auto",
                "--require-mask",
                "true",
            ]

            eval_stdout = stage_log_dir / "evaluation_stdout.log"
            eval_stderr = stage_log_dir / "evaluation_stderr.log"
            eval_exit = _run_cmd(
                cmd=eval_cmd,
                cwd=repo_root,
                env=env,
                stdout_path=eval_stdout,
                stderr_path=eval_stderr,
                dry_run=args.dry_run,
            )
            eval_status = "PASS" if eval_exit == 0 else "FAIL"

            # Find newest matching gate report.
            candidates = sorted(report_root.glob(f"{eval_run_label}_*.json"), key=lambda p: p.stat().st_mtime)
            if candidates:
                eval_json_path = candidates[-1]
                eval_md_path = eval_json_path.with_suffix(".md")
                eval_payload = _read_json_if_exists(eval_json_path)
                if eval_payload:
                    gate_decision = eval_payload.get("gate_decision")
                    primary = eval_payload.get("eval_result") or {}
                    mean_return = primary.get("mean_return")
                    non_noop_share = primary.get("effective_activity_share")
                    move_share = primary.get("move_share")
                    action_share = primary.get("action_type_share") or {}
                    attack_share = action_share.get("attack")
                    produce_share = action_share.get("produce")
                    mask_used = eval_payload.get("mask_used_during_eval")
                    for w in eval_payload.get("warnings", []):
                        if "reference internal env/action space" in str(w):
                            env_warning = str(w)
                            break
            else:
                errors.append("Evaluation report JSON was not generated.")

            if gate_decision == "FAIL" and args.stop_on_gate_fail:
                errors.append("Gate FAIL with --stop-on-gate-fail enabled.")

            if gate_decision == "PASS_WITH_WARNINGS" and not args.continue_on_gate_warning:
                pass

        stage_results.append(
            StageResult(
                stage=stage,
                stage_dir=str(stage_model_dir),
                checkpoint_path=str(stage_checkpoint_out) if stage_checkpoint_out else None,
                training_status=training_status,
                eval_status=eval_status,
                gate_decision=gate_decision,
                eval_report_json=str(eval_json_path) if eval_json_path else None,
                eval_report_md=str(eval_md_path) if eval_md_path and eval_md_path.exists() else None,
                mean_return=mean_return,
                non_noop_share=non_noop_share,
                move_share=move_share,
                attack_share=attack_share,
                produce_share=produce_share,
                mask_used=mask_used,
                env_mapping_warning=env_warning,
                errors=errors,
            )
        )

        if errors and ("Gate FAIL with --stop-on-gate-fail enabled." in errors):
            break

    summary_json = report_root / f"stage3_training_{ts}.json"
    summary_md = report_root / f"stage3_training_{ts}.md"

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "strategy": strategy,
        "strategy_note": (
            "Reference script supports local-save-every for intermediate checkpoints, "
            "but does not expose robust CLI resume from local checkpoints in non-wandb mode."
        ),
        "stages_planned": stages,
        "stages_run": [s.stage for s in stage_results],
        "training_command": " ".join(train_cmd),
        "training_exit_code": train_exit,
        "model_root": str(model_root),
        "log_root": str(log_root),
        "report_root": str(report_root),
        "stage_results": [s.__dict__ for s in stage_results],
    }
    summary_json.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    _render_md_summary(
        run_id=run_id,
        strategy=strategy,
        stages_planned=stages,
        stages_run=stage_results,
        out_json=summary_json,
        out_md=summary_md,
    )

    print(
        json.dumps(
            {
                "run_id": run_id,
                "strategy": strategy,
                "stage3_training_json": str(summary_json),
                "stage3_training_md": str(summary_md),
                "training_exit_code": train_exit,
                "stages_run": [s.stage for s in stage_results],
            },
            indent=2,
        )
    )

    has_fail = train_exit != 0 or any((s.gate_decision == "FAIL") for s in stage_results if s.gate_decision)
    return 1 if has_fail else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
