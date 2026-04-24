#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

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
    p.add_argument("--seed", type=int, default=170)
    p.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    p.add_argument("--opponent-pool", default="coacAI,workerRushAI,lightRushAI,passiveAI")
    p.add_argument("--opponent-sampling", choices=("static", "per_reset", "per_episode"), default="per_episode")
    p.add_argument("--device", default="cpu")
    p.add_argument("--output-dir", type=Path, default=Path("WEEK5R/retraining_runs"))
    p.add_argument("--gate-output-dir", type=Path, default=Path("WEEK5R/gate_runs"))

    p.add_argument("--force-mask-aware", action="store_true")
    p.add_argument("--allow-non-mask-aware", action="store_true", default=False)

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

    return p.parse_args()


def load_gate_json(gate_step_dir: Path, checkpoint_path: Path) -> Dict[str, Any]:
    gate_path = gate_step_dir / f"gate_{checkpoint_path.stem}.json"
    if not gate_path.is_file():
        raise RuntimeError(f"Gate JSON not found: {gate_path}")
    return json.loads(gate_path.read_text(encoding="utf-8"))


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
    if args.make_replay:
        cmd.extend([
            "--make-replay",
            "--replay-steps",
            str(args.replay_steps),
            "--replay-output-dir",
            str(gate_step_dir / "replay"),
        ])

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    data = load_gate_json(gate_step_dir, checkpoint_path)
    output_lines = [line for line in (proc.stdout + "\n" + proc.stderr).splitlines() if line.strip()]
    return proc.returncode, data, output_lines


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
) -> None:
    lines: List[str] = []
    lines.append("# Teacher Retraining Results")
    lines.append("")
    lines.append(f"- run_id: `{run_id}`")
    lines.append(f"- run_status: `{run_status}`")
    lines.append(f"- retraining_dir: `{retraining_dir}`")
    lines.append(f"- gate_dir: `{gate_dir}`")
    lines.append(f"- gate_comparison_md: `{compare_md_path}`")
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
    lines.append("## Abort Criteria Checks")
    lines.append("- FAIL_COLLAPSED_NOOP at 5k and 10k consecutively")
    lines.append("- actor_level_move_share == 0 while ready_movable_actor_choice_count > 0")
    lines.append("- effective_position_delta_count == 0")
    lines.append("- no_effect_action_share > 0.80")

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

    print(f"[behavior-first] run_id={run_id}")
    print(f"[behavior-first] checkpoints={checkpoint_steps}")
    print(f"[behavior-first] policy={policy_summary.get('policy_class')}")
    print(f"[behavior-first] mask backend=sb3_contrib.MaskablePPO")

    records: List[Dict[str, Any]] = []
    run_notes: List[str] = []
    gate_json_paths: List[Path] = []

    current_step = 0
    consecutive_fail_5k_10k = False

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

            abort_reasons = list(rec["abort_reasons"])
            if rec["status"] == "FAIL_COLLAPSED_NOOP" and target in (5000, 10000):
                if target == 10000:
                    prior_5k = next((r for r in records if r["checkpoint_step"] == 5000), None)
                    if prior_5k and prior_5k.get("status") == "FAIL_COLLAPSED_NOOP":
                        consecutive_fail_5k_10k = True
                        abort_reasons.append("FAIL_COLLAPSED_NOOP at 5k and 10k consecutively")

            if abort_reasons:
                run_notes.append(f"Abort at step {target}: {'; '.join(abort_reasons)}")
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

    run_manifest = {
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "aborted" if run_notes and any(note.startswith("Abort") for note in run_notes) else "completed",
        "total_timesteps": args.total_timesteps,
        "checkpoint_steps": checkpoint_steps,
        "records": records,
        "retraining_run_dir": str(retraining_run_dir),
        "gate_run_dir": str(gate_run_dir),
        "compare_markdown": str(compare_md_path),
        "runtime_versions": asdict(versions),
        "seed_bundle": asdict(seed_bundle),
        "env_summary": env_summary,
        "notes": run_notes,
        "consecutive_fail_5k_10k": consecutive_fail_5k_10k,
    }
    manifest_path = retraining_run_dir / "behavior_first_run_manifest.json"
    manifest_path.write_text(json.dumps(run_manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    global_results_path = Path("WEEK5R/TEACHER_RETRAINING_RESULTS.md")
    write_results_md(
        output_path=global_results_path,
        run_id=run_id,
        run_status=run_manifest["status"],
        run_notes=run_notes,
        records=records,
        compare_md_path=compare_md_path,
        retraining_dir=retraining_run_dir,
        gate_dir=gate_run_dir,
    )

    per_run_results = retraining_run_dir / "TEACHER_RETRAINING_RESULTS.md"
    write_results_md(
        output_path=per_run_results,
        run_id=run_id,
        run_status=run_manifest["status"],
        run_notes=run_notes,
        records=records,
        compare_md_path=compare_md_path,
        retraining_dir=retraining_run_dir,
        gate_dir=gate_run_dir,
    )

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
