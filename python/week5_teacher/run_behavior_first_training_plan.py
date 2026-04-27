#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List


def parse_args() -> argparse.Namespace:
    raw_argv = list(sys.argv[1:])

    p = argparse.ArgumentParser(
        description="Thin wrapper for first behavior-first retraining experiment plan."
    )
    p.add_argument("--total-timesteps", type=int, default=20000)
    p.add_argument("--checkpoint-steps", default="5000,10000,20000")
    p.add_argument(
        "--curriculum-mode",
        choices=("none", "movement_warmup", "economy_warmup", "mixed"),
        default="none",
    )
    p.add_argument("--seed", type=int, default=170)
    p.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    p.add_argument("--opponent-pool", default="coacAI,workerRushAI,lightRushAI,passiveAI")
    p.add_argument("--opponent-sampling", choices=("static", "per_episode"), default="per_episode")
    p.add_argument("--device", default="cpu")
    p.add_argument("--output-dir", type=Path, default=Path("WEEK5R/retraining_runs"))
    p.add_argument("--gate-output-dir", type=Path, default=Path("WEEK5R/gate_runs"))

    p.add_argument("--episodes-gate", type=int, default=4)
    p.add_argument("--max-steps-gate", type=int, default=256)
    p.add_argument("--effective-steps-gate", type=int, default=100)
    p.add_argument("--replay-steps", type=int, default=150)
    p.add_argument("--make-replay", action="store_true")
    p.add_argument("--activity-shaping", action="store_true", default=False)
    p.add_argument("--shape-move-reward", type=float, default=0.01)
    p.add_argument("--shape-noop-penalty", type=float, default=0.001)
    p.add_argument("--shape-no-effect-penalty", type=float, default=0.002)
    p.add_argument(
        "--shape-reward-only-move-action",
        dest="shape_reward_only_move_action",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    p.add_argument(
        "--shape-no-effect-ready-action-only",
        dest="shape_no_effect_ready_action_only",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    p.add_argument(
        "--min-abort-step",
        type=int,
        default=5000,
        help="Abort suppressed for checkpoints whose step < this value. Default: 5000.",
    )
    p.add_argument(
        "--collect-all-checkpoints",
        action="store_true",
        default=False,
        help="Never abort early; evaluate all checkpoints regardless of gate results.",
    )
    args = p.parse_args(raw_argv)
    setattr(args, "_raw_argv", raw_argv)
    return args


def _arg_present(raw_argv: List[str], name: str) -> bool:
    return any(token == name or token.startswith(f"{name}=") for token in raw_argv)


def main() -> int:
    args = parse_args()
    raw_argv: List[str] = list(getattr(args, "_raw_argv", []))
    script_path = Path(__file__).resolve().parent / "train_teacher_behavior_first.py"

    use_warmup_defaults = args.curriculum_mode == "movement_warmup"

    cmd: List[str] = [
        sys.executable,
        str(script_path),
        "--curriculum-mode",
        args.curriculum_mode,
        "--seed",
        str(args.seed),
        "--map-path",
        args.map_path,
        "--device",
        args.device,
        "--output-dir",
        str(args.output_dir),
        "--gate-output-dir",
        str(args.gate_output_dir),
        "--episodes-gate",
        str(args.episodes_gate),
        "--max-steps-gate",
        str(args.max_steps_gate),
        "--effective-steps-gate",
        str(args.effective_steps_gate),
        "--replay-steps",
        str(args.replay_steps),
        "--shape-move-reward",
        str(args.shape_move_reward),
        "--shape-noop-penalty",
        str(args.shape_noop_penalty),
        "--shape-no-effect-penalty",
        str(args.shape_no_effect_penalty),
        "--force-mask-aware",
        "--min-abort-step",
        str(args.min_abort_step),
    ]

    if not use_warmup_defaults or _arg_present(raw_argv, "--total-timesteps"):
        cmd.extend(["--total-timesteps", str(args.total_timesteps)])
    if not use_warmup_defaults or _arg_present(raw_argv, "--checkpoint-steps"):
        cmd.extend(["--checkpoint-steps", args.checkpoint_steps])
    if not use_warmup_defaults or _arg_present(raw_argv, "--opponent-pool"):
        cmd.extend(["--opponent-pool", args.opponent_pool])
    if not use_warmup_defaults or _arg_present(raw_argv, "--opponent-sampling"):
        cmd.extend(["--opponent-sampling", args.opponent_sampling])

    if args.make_replay:
        cmd.append("--make-replay")
    if args.activity_shaping:
        cmd.append("--activity-shaping")
    if args.shape_reward_only_move_action:
        cmd.append("--shape-reward-only-move-action")
    else:
        cmd.append("--no-shape-reward-only-move-action")
    if args.shape_no_effect_ready_action_only:
        cmd.append("--shape-no-effect-ready-action-only")
    else:
        cmd.append("--no-shape-no-effect-ready-action-only")
    if args.collect_all_checkpoints:
        cmd.append("--collect-all-checkpoints")

    proc = subprocess.run(cmd, check=False)
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
