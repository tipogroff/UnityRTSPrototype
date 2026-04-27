#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


@dataclass(frozen=True)
class SweepConfig:
    name: str
    move_reward: float
    noop_penalty: float
    no_effect_penalty: float


DEFAULT_CONFIGS: List[SweepConfig] = [
    SweepConfig("baseline_mild", move_reward=0.01, noop_penalty=0.001, no_effect_penalty=0.002),
    SweepConfig("stronger_balanced", move_reward=0.05, noop_penalty=0.005, no_effect_penalty=0.01),
    SweepConfig("stronger_noeffect", move_reward=0.03, noop_penalty=0.003, no_effect_penalty=0.02),
    SweepConfig("move_heavy", move_reward=0.10, noop_penalty=0.002, no_effect_penalty=0.005),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Run short movement_warmup + activity_shaping coefficient sweep to 10k and compare gate metrics."
        )
    )
    p.add_argument("--sweep-id", default=f"movement_warmup_sweep_{utc_stamp()}")
    p.add_argument("--output-root", type=Path, default=Path("WEEK5R/movement_warmup_sweeps"))

    p.add_argument("--total-timesteps", type=int, default=10000)
    p.add_argument("--checkpoint-steps", default="2000,5000,10000")
    p.add_argument("--seed", type=int, default=170)
    p.add_argument(
        "--sweep-seeds",
        default="",
        help="Optional comma-separated seeds. If empty, uses --seed only.",
    )

    p.add_argument("--device", default="cpu")
    p.add_argument("--make-replay", action="store_true", default=False)

    p.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    p.add_argument("--episodes-gate", type=int, default=4)
    p.add_argument("--max-steps-gate", type=int, default=256)
    p.add_argument("--effective-steps-gate", type=int, default=100)

    return p.parse_args()


def parse_seed_list(raw: str, fallback_seed: int) -> List[int]:
    if not raw.strip():
        return [int(fallback_seed)]
    seeds: List[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        seeds.append(int(token))
    unique = sorted(set(seeds))
    if not unique:
        return [int(fallback_seed)]
    return unique


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_latest_manifest(run_output_dir: Path) -> Optional[Path]:
    candidates = sorted(
        run_output_dir.glob("behavior_first_*/behavior_first_run_manifest.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _checkpoint_row(record: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not record:
        return {
            "status": "MISSING",
            "actor_move": 0.0,
            "actor_noop": 0.0,
            "pos_delta": 0,
            "no_effect": 1.0,
            "movement_warmup_success": False,
            "gate_json": None,
        }

    return {
        "status": str(record.get("status", "UNKNOWN")),
        "actor_move": _safe_float(record.get("actor_level_move_share")),
        "actor_noop": _safe_float(record.get("actor_noop_share")),
        "pos_delta": _safe_int(record.get("effective_position_delta_count")),
        "no_effect": _safe_float(record.get("no_effect_action_share"), default=1.0),
        "movement_warmup_success": bool(record.get("movement_warmup_success", False)),
        "gate_json": record.get("gate_json_path"),
    }


def _rank_key(run: Dict[str, Any]) -> tuple:
    k10 = run["checkpoints"].get("10000", {})
    pos_delta_10k = _safe_int(k10.get("pos_delta", 0))
    no_effect_10k = _safe_float(k10.get("no_effect", 1.0), default=1.0)
    actor_move_10k = _safe_float(k10.get("actor_move", 0.0))
    actor_noop_10k = _safe_float(k10.get("actor_noop", 1.0), default=1.0)
    move_action_pos_delta = _safe_int(run.get("move_action_position_delta_events", 0))

    return (
        int(pos_delta_10k > 0),
        -no_effect_10k,
        actor_move_10k,
        -actor_noop_10k,
        int(move_action_pos_delta > 0),
    )


def run_single(
    *,
    cfg: SweepConfig,
    seed: int,
    args: argparse.Namespace,
    sweep_root: Path,
) -> Dict[str, Any]:
    run_key = f"{cfg.name}_seed{seed}"
    run_root = sweep_root / "runs" / run_key
    retraining_out = run_root / "retraining_runs"
    gate_out = run_root / "gate_runs"
    retraining_out.mkdir(parents=True, exist_ok=True)
    gate_out.mkdir(parents=True, exist_ok=True)

    script_path = Path(__file__).resolve().parent / "run_behavior_first_training_plan.py"
    cmd: List[str] = [
        sys.executable,
        str(script_path),
        "--curriculum-mode",
        "movement_warmup",
        "--activity-shaping",
        "--total-timesteps",
        str(args.total_timesteps),
        "--checkpoint-steps",
        args.checkpoint_steps,
        "--collect-all-checkpoints",
        "--seed",
        str(seed),
        "--device",
        args.device,
        "--map-path",
        args.map_path,
        "--episodes-gate",
        str(args.episodes_gate),
        "--max-steps-gate",
        str(args.max_steps_gate),
        "--effective-steps-gate",
        str(args.effective_steps_gate),
        "--shape-move-reward",
        str(cfg.move_reward),
        "--shape-noop-penalty",
        str(cfg.noop_penalty),
        "--shape-no-effect-penalty",
        str(cfg.no_effect_penalty),
        "--shape-reward-only-move-action",
        "--shape-no-effect-ready-action-only",
        "--output-dir",
        str(retraining_out),
        "--gate-output-dir",
        str(gate_out),
    ]
    if args.make_replay:
        cmd.append("--make-replay")

    print(f"[sweep] start {run_key} with config={cfg}")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    manifest_path = _find_latest_manifest(retraining_out)

    result: Dict[str, Any] = {
        "run_key": run_key,
        "config_name": cfg.name,
        "seed": int(seed),
        "shape_move_reward": float(cfg.move_reward),
        "shape_noop_penalty": float(cfg.noop_penalty),
        "shape_no_effect_penalty": float(cfg.no_effect_penalty),
        "train_exit_code": int(proc.returncode),
        "manifest_path": str(manifest_path) if manifest_path else None,
        "stdout_tail": (proc.stdout or "").splitlines()[-20:],
        "stderr_tail": (proc.stderr or "").splitlines()[-20:],
        "checkpoints": {},
        "shaping_event_counts": {},
        "move_action_position_delta_events": 0,
        "nonmove_position_delta_events": 0,
        "status": "manifest_missing",
    }

    if not manifest_path or not manifest_path.is_file():
        return result

    manifest = _load_json(manifest_path)
    result["status"] = str(manifest.get("status", "unknown"))
    result["run_id"] = manifest.get("run_id")
    result["shaping_alignment_mode"] = manifest.get("shaping_alignment_mode", {})

    records = manifest.get("records", []) or []
    by_step: Dict[int, Dict[str, Any]] = {}
    for rec in records:
        step = _safe_int(rec.get("checkpoint_step"), default=-1)
        if step > 0:
            by_step[step] = rec

    for step in (2000, 5000, 10000):
        result["checkpoints"][str(step)] = _checkpoint_row(by_step.get(step))

    shaping_counts = manifest.get("shaping_event_counts", {}) or {}
    result["shaping_event_counts"] = shaping_counts
    result["move_action_position_delta_events"] = _safe_int(
        shaping_counts.get("move_action_position_delta_events", 0)
    )
    result["nonmove_position_delta_events"] = _safe_int(
        shaping_counts.get("nonmove_position_delta_events", 0)
    )

    return result


def write_outputs(sweep_root: Path, sweep_id: str, all_runs: List[Dict[str, Any]]) -> None:
    ranked = sorted(all_runs, key=_rank_key, reverse=True)

    json_path = sweep_root / "sweep_results.json"
    payload = {
        "sweep_id": sweep_id,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ranking_rule": [
            "1) pos_delta > 0 at 10k",
            "2) no_effect lower at 10k",
            "3) actor_move > 0.05 at 10k",
            "4) actor_noop lower while avoiding no-effect collapse",
            "5) move_action_position_delta_events > 0",
        ],
        "runs": all_runs,
        "ranked_run_keys": [r["run_key"] for r in ranked],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    md_path = sweep_root / "SWEEP_RESULTS.md"
    lines: List[str] = []
    lines.append(f"# Movement Warmup Sweep Results: {sweep_id}")
    lines.append("")
    lines.append("## Ranking Rule")
    lines.append("1. pos_delta > 0 at 10k")
    lines.append("2. lower no_effect at 10k")
    lines.append("3. higher actor_move at 10k (target > 0.05)")
    lines.append("4. lower actor_noop at 10k without no-effect collapse")
    lines.append("5. move_action_position_delta_events > 0")
    lines.append("")
    lines.append("## Ranked Runs")
    for idx, run in enumerate(ranked, start=1):
        c10 = run["checkpoints"].get("10000", {})
        lines.append(
            (
                f"{idx}. {run['run_key']} | status={run.get('status')} | "
                f"pos_delta10k={c10.get('pos_delta')} | no_effect10k={c10.get('no_effect')} | "
                f"actor_move10k={c10.get('actor_move')} | actor_noop10k={c10.get('actor_noop')} | "
                f"move_action_position_delta_events={run.get('move_action_position_delta_events')}"
            )
        )
    lines.append("")
    lines.append("## Summary Table")
    lines.append(
        "| run_key | status | actor_move_2k | actor_move_5k | actor_move_10k | actor_noop_10k | pos_delta_10k | no_effect_10k | movement_warmup_success_10k | move_action_position_delta_events | nonmove_position_delta_events |"
    )
    lines.append(
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    )

    for run in ranked:
        c2 = run["checkpoints"].get("2000", {})
        c5 = run["checkpoints"].get("5000", {})
        c10 = run["checkpoints"].get("10000", {})
        lines.append(
            "| {run_key} | {status} | {a2:.4f} | {a5:.4f} | {a10:.4f} | {noop10:.4f} | {pd10} | {ne10:.4f} | {mw10} | {mad} | {nmad} |".format(
                run_key=run.get("run_key"),
                status=run.get("status"),
                a2=_safe_float(c2.get("actor_move", 0.0)),
                a5=_safe_float(c5.get("actor_move", 0.0)),
                a10=_safe_float(c10.get("actor_move", 0.0)),
                noop10=_safe_float(c10.get("actor_noop", 1.0), default=1.0),
                pd10=_safe_int(c10.get("pos_delta", 0)),
                ne10=_safe_float(c10.get("no_effect", 1.0), default=1.0),
                mw10=bool(c10.get("movement_warmup_success", False)),
                mad=_safe_int(run.get("move_action_position_delta_events", 0)),
                nmad=_safe_int(run.get("nonmove_position_delta_events", 0)),
            )
        )

    lines.append("")
    lines.append("## Artifacts")
    lines.append(f"- JSON: {json_path.as_posix()}")
    lines.append(f"- Sweep root: {sweep_root.as_posix()}")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    seeds = parse_seed_list(args.sweep_seeds, args.seed)

    sweep_root = args.output_root / args.sweep_id
    sweep_root.mkdir(parents=True, exist_ok=True)

    all_runs: List[Dict[str, Any]] = []
    for seed in seeds:
        for cfg in DEFAULT_CONFIGS:
            run_result = run_single(cfg=cfg, seed=seed, args=args, sweep_root=sweep_root)
            all_runs.append(run_result)

    write_outputs(sweep_root=sweep_root, sweep_id=args.sweep_id, all_runs=all_runs)
    print(f"[sweep] done sweep_id={args.sweep_id} root={sweep_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
