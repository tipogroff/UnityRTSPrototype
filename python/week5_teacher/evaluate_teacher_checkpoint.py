#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

ACTION_NAMES = {
    0: "NoOp",
    1: "Move",
    2: "Harvest",
    3: "Return",
    4: "Produce",
    5: "Attack",
}


class EvalError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate/replay a fixed teacher checkpoint in Gym-microRTS, "
            "collect compact behavior summaries, and write JSON/Markdown artifacts."
        )
    )
    parser.add_argument("--checkpoint", type=Path, required=True, help="Path to teacher SB3 checkpoint .zip")
    parser.add_argument(
        "--checkpoint-env-version",
        default="0.0.0",
        help="Environment version contract passed to run_teacher_rollout.py",
    )
    parser.add_argument("--episodes", type=int, default=8)
    parser.add_argument("--rollout-step-limit", type=int, default=2000)
    parser.add_argument("--env-id", default="MicrortsSelfPlayShapedReward-v1")
    parser.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    parser.add_argument("--backend-mode", choices=("allow_fallback", "preferred_only"), default="allow_fallback")
    parser.add_argument(
        "--opponent-pool",
        default="coacAI,workerRushAI,lightRushAI,passiveAI",
        help="Comma-separated opponent pool for rollout exporter",
    )
    parser.add_argument("--opponent-sampling", choices=("static", "per_reset", "per_episode"), default="per_episode")
    parser.add_argument("--seed", type=int, default=170)
    parser.add_argument("--device", default="cpu")
    parser.add_argument(
        "--batch-label",
        default="teacher_eval_ckpt",
        help="Label forwarded to rollout exporter; timestamp is added by exporter",
    )
    parser.add_argument(
        "--run-render-probe",
        action="store_true",
        help="Try a short best-effort render probe (headless-safe; failures are recorded, not fatal).",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("WEEK6/teacher_checkpoint_80k_eval.json"),
        help="Output JSON path",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("WEEK6/TEACHER_CHECKPOINT_80K_REPLAY_SUMMARY.md"),
        help="Output Markdown path",
    )
    return parser.parse_args()


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _discover_new_summary(teacher_logs_dir: Path, before: set[Path]) -> Path:
    after = set(teacher_logs_dir.glob("teacher_rollout_*.summary.json"))
    created = [p for p in after if p not in before]
    if created:
        return max(created, key=lambda p: p.stat().st_mtime)
    if not after:
        raise EvalError(f"No rollout summaries found in {teacher_logs_dir}")
    return max(after, key=lambda p: p.stat().st_mtime)


def _to_counts_and_share(counter: Counter[int], total: int) -> Dict[str, Dict[str, float | int]]:
    out: Dict[str, Dict[str, float | int]] = {}
    for idx, name in ACTION_NAMES.items():
        count = int(counter.get(idx, 0))
        share = (count / total) if total > 0 else 0.0
        out[name] = {"count": count, "share": share}
    return out


def _extract_branch0_from_action_json(action_json: str) -> np.ndarray:
    payload = json.loads(action_json)
    if isinstance(payload, list) and len(payload) == 1 and isinstance(payload[0], list):
        flat = payload[0]
    elif isinstance(payload, list):
        flat = payload
    else:
        raise EvalError(f"Unsupported action payload type in action_t_json: {type(payload).__name__}")

    vec = np.asarray(flat, dtype=np.int64)
    if vec.ndim != 1 or vec.size % 7 != 0:
        raise EvalError(f"Unexpected action flat shape: {tuple(vec.shape)}; expected 1D with size divisible by 7")
    matrix = vec.reshape(-1, 7)
    return matrix[:, 0]


def _infer_outcome(last_info: Dict[str, Any], episode_return: float) -> Tuple[str, str]:
    # Prefer explicit winner/result signal from info payload when available.
    if "winner" in last_info:
        winner = last_info.get("winner")
        if str(winner) in {"0", "self", "player_0", "true", "True"}:
            return "win", "info.winner"
        if str(winner) in {"1", "player_1", "false", "False"}:
            return "loss", "info.winner"
        if str(winner) in {"-1", "draw", "none", "None"}:
            return "draw", "info.winner"

    result = last_info.get("result")
    if isinstance(result, str):
        lowered = result.lower()
        if lowered in {"win", "won", "victory"}:
            return "win", "info.result"
        if lowered in {"loss", "lose", "defeat"}:
            return "loss", "info.result"
        if lowered in {"draw", "tie"}:
            return "draw", "info.result"

    # Fallback: reward-sign heuristic when no explicit terminal outcome is exposed by env info.
    if episode_return > 0:
        return "win", "episode_return_sign"
    if episode_return < 0:
        return "loss", "episode_return_sign"
    return "draw", "episode_return_sign"


def _analyze_batch(batch_dir: Path, rollout_summary: Dict[str, Any]) -> Dict[str, Any]:
    episode_files = sorted(batch_dir.glob("episode_*.npz"))
    if not episode_files:
        raise EvalError(f"No episode_*.npz found in {batch_dir}")

    overall = Counter()
    early20 = Counter()
    early50 = Counter()

    steps_total = 0
    steps_with_any_move = 0
    episodes_with_any_move = 0
    per_episode: List[Dict[str, Any]] = []

    wins = 0
    losses = 0
    draws = 0

    for idx, episode_path in enumerate(episode_files):
        data = np.load(episode_path, allow_pickle=True)

        action_json_steps = data["action_t_json"]
        reward_t = np.asarray(data["reward_t"], dtype=np.float32)
        info_t_json = data["info_t_json"]

        ep_counter = Counter()
        ep_has_move = False

        for step_id in range(action_json_steps.shape[0]):
            branch0 = _extract_branch0_from_action_json(str(action_json_steps[step_id]))
            step_counter = Counter(int(v) for v in branch0.tolist())
            ep_counter.update(step_counter)
            overall.update(step_counter)
            steps_total += 1

            if step_counter.get(1, 0) > 0:
                steps_with_any_move += 1
                ep_has_move = True

            if step_id < 20:
                early20.update(step_counter)
            if step_id < 50:
                early50.update(step_counter)

        if ep_has_move:
            episodes_with_any_move += 1

        last_info_raw = str(info_t_json[-1]) if info_t_json.size > 0 else "{}"
        try:
            last_info = json.loads(last_info_raw)
            if not isinstance(last_info, dict):
                last_info = {}
        except json.JSONDecodeError:
            last_info = {}

        ep_return = float(reward_t.sum()) if reward_t.size > 0 else 0.0
        outcome, outcome_source = _infer_outcome(last_info, ep_return)
        if outcome == "win":
            wins += 1
        elif outcome == "loss":
            losses += 1
        else:
            draws += 1

        per_episode.append(
            {
                "episode_index": idx,
                "episode_file": str(episode_path),
                "steps": int(action_json_steps.shape[0]),
                "episode_return": ep_return,
                "outcome": outcome,
                "outcome_source": outcome_source,
                "has_any_move": ep_has_move,
                "action_type_distribution": _to_counts_and_share(ep_counter, int(sum(ep_counter.values()))),
            }
        )

    total_action_cells = int(sum(overall.values()))
    early20_total_cells = int(sum(early20.values()))
    early50_total_cells = int(sum(early50.values()))

    episodes_count = len(episode_files)
    win_rate = (wins / episodes_count) if episodes_count > 0 else 0.0

    outcome_notes = {
        "method": "info_fields_first_then_episode_return_sign_fallback",
        "warning": (
            "If environment info does not expose explicit winner and episode returns are all ~0, "
            "draw count may be inflated by heuristic fallback."
        ),
    }

    return {
        "episodes": episodes_count,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": win_rate,
        "outcome_inference": outcome_notes,
        "action_type_distribution": _to_counts_and_share(overall, total_action_cells),
        "early_game_action_distribution": {
            "first_20_steps": _to_counts_and_share(early20, early20_total_cells),
            "first_50_steps": _to_counts_and_share(early50, early50_total_cells),
        },
        "move_presence": {
            "steps_total": steps_total,
            "steps_with_any_move": steps_with_any_move,
            "steps_with_any_move_share": (steps_with_any_move / steps_total) if steps_total > 0 else 0.0,
            "episodes_with_any_move": episodes_with_any_move,
            "episodes_with_any_move_share": (episodes_with_any_move / episodes_count) if episodes_count > 0 else 0.0,
        },
        "episode_histograms": per_episode,
        "rollout_reference": {
            "batch_name": rollout_summary["rollout"]["batch_name"],
            "batch_dir": rollout_summary["rollout"]["batch_dir"],
            "batch_summary_path": rollout_summary["rollout"]["batch_summary_path"],
        },
    }


def _run_render_probe(checkpoint: Path, map_path: str, env_id: str) -> Dict[str, Any]:
    # Best effort only: this environment often runs headless in automation.
    try:
        import gymnasium as gym
        model = None
        load_errors: List[str] = []

        try:
            from sb3_contrib import MaskablePPO

            model = MaskablePPO.load(str(checkpoint), device="cpu", print_system_info=False)
        except Exception as exc:
            load_errors.append(f"MaskablePPO: {type(exc).__name__}: {exc}")

        if model is None:
            try:
                from stable_baselines3 import PPO

                model = PPO.load(str(checkpoint), device="cpu", print_system_info=False)
            except Exception as exc:
                load_errors.append(f"PPO: {type(exc).__name__}: {exc}")

        if model is None:
            raise EvalError("; ".join(load_errors) if load_errors else "unknown model load failure")

        env = gym.make(env_id, map_path=map_path)
        obs, _ = env.reset(seed=321)

        probe_steps = 0
        for _ in range(120):
            action, _ = model.predict(obs, deterministic=True)
            step = env.step(action)
            if len(step) == 5:
                obs, _reward, terminated, truncated, _info = step
                done = bool(terminated or truncated)
            else:
                obs, _reward, done, _info = step
            probe_steps += 1
            try:
                env.render()
            except Exception:
                # Render can fail in headless mode even if env stepping is fine.
                pass
            if done:
                break

        try:
            env.close()
        except Exception:
            pass

        return {
            "attempted": True,
            "success": True,
            "note": "Render probe stepped successfully; visual confirmation still depends on local display availability.",
            "probe_steps": probe_steps,
        }
    except Exception as exc:
        return {
            "attempted": True,
            "success": False,
            "note": "Render probe failed; evaluation remained non-visual.",
            "error": f"{type(exc).__name__}: {exc}",
        }


def _format_pct(value: float) -> str:
    return f"{value * 100:.3f}%"


def _render_md(report: Dict[str, Any]) -> str:
    metrics = report["metrics"]
    overall = metrics["action_type_distribution"]
    early20 = metrics["early_game_action_distribution"]["first_20_steps"]
    early50 = metrics["early_game_action_distribution"]["first_50_steps"]
    move_presence = metrics["move_presence"]
    visual = report["visualization"]

    lines: List[str] = []
    lines.append("# Teacher checkpoint evaluation summary")
    lines.append("")
    lines.append(f"- generated_at_utc: {report['generated_at_utc']}")
    lines.append(f"- checkpoint_requested: {report['checkpoint_requested']}")
    lines.append(f"- checkpoint_used: {report['checkpoint_used']}")
    lines.append(f"- checkpoint_sha256: {report['checkpoint_sha256']}")
    lines.append(f"- episodes: {metrics['episodes']}")
    lines.append(f"- opponents: {','.join(report['evaluation_protocol']['opponent_pool'])}")
    lines.append(f"- render_probe: attempted={visual['attempted']} success={visual.get('success', False)}")
    lines.append("")

    lines.append("## Win/Loss summary")
    lines.append(f"- wins: {metrics['wins']}")
    lines.append(f"- losses: {metrics['losses']}")
    lines.append(f"- draws: {metrics['draws']}")
    lines.append(f"- win_rate: {_format_pct(metrics['win_rate'])}")
    lines.append("")

    lines.append("## Action type distribution (overall)")
    for name in ACTION_NAMES.values():
        item = overall[name]
        lines.append(f"- {name}: {item['count']} ({_format_pct(float(item['share']))})")
    lines.append("")

    lines.append("## Early-game action distribution (first 20 steps)")
    for name in ACTION_NAMES.values():
        item = early20[name]
        lines.append(f"- {name}: {item['count']} ({_format_pct(float(item['share']))})")
    lines.append("")

    lines.append("## Early-game action distribution (first 50 steps)")
    for name in ACTION_NAMES.values():
        item = early50[name]
        lines.append(f"- {name}: {item['count']} ({_format_pct(float(item['share']))})")
    lines.append("")

    lines.append("## Move presence diagnostics")
    lines.append(
        f"- steps_with_any_move: {move_presence['steps_with_any_move']} / {move_presence['steps_total']} "
        f"({_format_pct(float(move_presence['steps_with_any_move_share']))})"
    )
    lines.append(
        f"- episodes_with_any_move: {move_presence['episodes_with_any_move']} / {metrics['episodes']} "
        f"({_format_pct(float(move_presence['episodes_with_any_move_share']))})"
    )
    lines.append("")

    lines.append("## Visual behavior note")
    lines.append(f"- {visual['note']}")
    if visual.get("error"):
        lines.append(f"- render_error: {visual['error']}")
    lines.append("")

    lines.append("## Diagnostic conclusion")
    move_share = float(overall["Move"]["share"])
    if move_share > 0.05 and move_presence["episodes_with_any_move"] > 0:
        lines.append(
            "- Teacher is move-capable in Gym-microRTS under this checkpoint/protocol; "
            "investigation should continue on transfer/adaptation/student path."
        )
    else:
        lines.append(
            "- Teacher itself appears move-suppressed in this protocol/checkpoint; "
            "teacher-side behavior is a likely upstream contributor."
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()

    checkpoint = args.checkpoint.resolve()
    if not checkpoint.is_file():
        raise EvalError(f"Checkpoint not found: {checkpoint}")

    project_root = Path(__file__).resolve().parents[2]
    rollout_script = project_root / "python" / "week5_teacher" / "run_teacher_rollout.py"
    if not rollout_script.is_file():
        raise EvalError(f"Rollout script not found: {rollout_script}")

    teacher_logs_dir = project_root / "python" / "week5_teacher" / "teacher_logs"
    before_summaries = set(teacher_logs_dir.glob("teacher_rollout_*.summary.json"))

    rollout_cmd = [
        sys.executable,
        str(rollout_script),
        "--policy-path",
        str(checkpoint),
        "--policy-algorithm",
        "ppo",
        "--checkpoint-env-version",
        str(args.checkpoint_env_version),
        "--episodes",
        str(args.episodes),
        "--batch-mode",
        "training",
        "--batch-label",
        str(args.batch_label),
        "--env-id",
        str(args.env_id),
        "--map-path",
        str(args.map_path),
        "--backend-mode",
        str(args.backend_mode),
        "--opponent-pool",
        str(args.opponent_pool),
        "--opponent-sampling",
        str(args.opponent_sampling),
        "--seed",
        str(args.seed),
        "--device",
        str(args.device),
        "--rollout-step-limit",
        str(args.rollout_step_limit),
        "--write-jsonl",
        "never",
    ]

    subprocess.run(rollout_cmd, check=True, cwd=str(project_root))

    summary_path = _discover_new_summary(teacher_logs_dir, before_summaries)
    rollout_summary = _json_load(summary_path)
    batch_dir = Path(rollout_summary["rollout"]["batch_dir"])

    metrics = _analyze_batch(batch_dir=batch_dir, rollout_summary=rollout_summary)

    visualization = {
        "attempted": False,
        "success": False,
        "note": "Render probe not requested; evaluation was non-visual and based on rollout/action diagnostics.",
    }
    if args.run_render_probe:
        visualization = _run_render_probe(checkpoint=checkpoint, map_path=args.map_path, env_id=args.env_id)

    sha256 = rollout_summary.get("policy", {}).get("checkpoint_hash", "unknown")

    report: Dict[str, Any] = {
        "generated_at_utc": _utc_now(),
        "checkpoint_requested": str(args.checkpoint),
        "checkpoint_used": str(checkpoint),
        "checkpoint_sha256": sha256,
        "rollout_summary_path": str(summary_path),
        "evaluation_protocol": {
            "entrypoint": str(Path(__file__).resolve()),
            "episodes": args.episodes,
            "rollout_step_limit": args.rollout_step_limit,
            "env_id": args.env_id,
            "map_path": args.map_path,
            "backend_mode": args.backend_mode,
            "opponent_pool": [x.strip() for x in str(args.opponent_pool).split(",") if x.strip()],
            "opponent_sampling": args.opponent_sampling,
            "seed": args.seed,
            "device": args.device,
        },
        "policy_from_rollout_summary": rollout_summary.get("policy", {}),
        "metrics": metrics,
        "visualization": visualization,
    }

    output_json = (project_root / args.output_json).resolve() if not args.output_json.is_absolute() else args.output_json
    output_md = (project_root / args.output_md).resolve() if not args.output_md.is_absolute() else args.output_md
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)

    output_json.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    output_md.write_text(_render_md(report), encoding="utf-8")

    print(f"Evaluation JSON: {output_json}")
    print(f"Evaluation summary: {output_md}")
    print(f"Rollout summary used: {summary_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvalError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(2)
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] Rollout command failed with exit code {exc.returncode}", file=sys.stderr)
        raise SystemExit(exc.returncode)
