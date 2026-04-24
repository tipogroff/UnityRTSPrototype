#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Thin wrapper for first behavior-first retraining experiment plan."
    )
    p.add_argument("--total-timesteps", type=int, default=20000)
    p.add_argument("--checkpoint-steps", default="5000,10000,20000")
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
    return p.parse_args()


def main() -> int:
    args = parse_args()
    script_path = Path(__file__).resolve().parent / "train_teacher_behavior_first.py"

    cmd: List[str] = [
        sys.executable,
        str(script_path),
        "--total-timesteps",
        str(args.total_timesteps),
        "--checkpoint-steps",
        args.checkpoint_steps,
        "--seed",
        str(args.seed),
        "--map-path",
        args.map_path,
        "--opponent-pool",
        args.opponent_pool,
        "--opponent-sampling",
        args.opponent_sampling,
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
        "--force-mask-aware",
    ]
    if args.make_replay:
        cmd.append("--make-replay")

    proc = subprocess.run(cmd, check=False)
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
