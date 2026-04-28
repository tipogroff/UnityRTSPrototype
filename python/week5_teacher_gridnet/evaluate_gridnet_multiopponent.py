#!/usr/bin/env python3
"""Multi-opponent eval runner for Gridnet checkpoints.

Spawns evaluate_gridnet_actor_level.py as a separate subprocess for each
opponent in the pool. This works around the JPype/JVM single-instance
limitation: each subprocess gets its own JVM, so true per-opponent evaluation
is possible.

Output:
  <output-dir>/multiopponent_eval_<stem>.json
  <output-dir>/multiopponent_eval_<stem>.md
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

DEFAULT_OPPONENTS = ["randomBiasedAI", "lightRushAI", "workerRushAI", "coacAI"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Multi-opponent eval runner. Invokes evaluate_gridnet_actor_level.py "
            "in a separate subprocess per opponent to bypass JPype JVM restart limitations."
        )
    )
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--model-metadata", type=Path, required=True)
    p.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    p.add_argument("--opponents", default=",".join(DEFAULT_OPPONENTS),
                   help="Comma-separated opponent names.")
    p.add_argument("--episodes", type=int, default=4)
    p.add_argument("--max-steps", type=int, default=256)
    p.add_argument("--effective-steps", type=int, default=100)
    p.add_argument("--deterministic", choices=("true", "false"), default="true",
                   help="Deterministic (argmax) or stochastic (sampled) rollout.")
    p.add_argument("--device", default="cpu")
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--python", type=Path, default=Path(sys.executable),
                   help="Python interpreter to use for subprocesses (default: current).")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--timeout", type=int, default=600,
                   help="Per-opponent subprocess timeout in seconds.")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def evaluator_script() -> Path:
    """Locate evaluate_gridnet_actor_level.py alongside this script."""
    return Path(__file__).parent / "evaluate_gridnet_actor_level.py"


def run_single_opponent(
    python: Path,
    checkpoint: Path,
    metadata: Path,
    map_path: str,
    opponent: str,
    episodes: int,
    max_steps: int,
    effective_steps: int,
    deterministic: str,
    device: str,
    seed: int,
    timeout: int,
    tmp_dir: Path,
) -> Dict[str, Any]:
    """Run the evaluator for one opponent in a subprocess."""
    safe = opponent.replace("/", "_").replace("\\", "_")
    out_json = tmp_dir / f"eval_{safe}.json"
    out_md = tmp_dir / f"eval_{safe}.md"

    script = evaluator_script()
    cmd = [
        str(python), str(script),
        "--checkpoint", str(checkpoint),
        "--model-metadata", str(metadata),
        "--map-path", map_path,
        "--opponent-pool", opponent,
        "--opponent-sampling", "static",
        "--episodes", str(episodes),
        "--max-steps", str(max_steps),
        "--effective-steps", str(effective_steps),
        "--device", device,
        "--seed", str(seed),
        "--output-json", str(out_json),
        "--output-md", str(out_md),
    ]
    # Pass deterministic flag if the evaluator supports it.
    if deterministic == "false":
        cmd += ["--deterministic", "false"]
    else:
        cmd += ["--deterministic", "true"]

    print(f"[multiopp] Starting subprocess for opponent={opponent} ...")
    result: Dict[str, Any] = {
        "opponent": opponent,
        "status": "ERROR",
        "gate_status": "ERROR",
        "verdict": "",
        "actor_level_move_share": None,
        "actor_noop_share": None,
        "effective_position_delta_count": None,
        "no_effect_action_share": None,
        "ready_movable_actor_choice_count": None,
        "subprocess_returncode": None,
        "subprocess_stderr": "",
    }

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        result["subprocess_returncode"] = proc.returncode
        result["subprocess_stderr"] = proc.stderr[-2000:] if proc.stderr else ""

        if proc.returncode != 0:
            result["verdict"] = f"Subprocess exited {proc.returncode}."
            print(f"[multiopp]   opponent={opponent} FAILED (exit {proc.returncode})")
            if proc.stderr:
                for line in proc.stderr.splitlines()[-10:]:
                    print(f"[multiopp]     stderr: {line}")
            return result

        if out_json.is_file():
            eval_data = json.loads(out_json.read_text(encoding="utf-8"))
            result.update({
                "status": eval_data.get("status", "UNKNOWN"),
                "gate_status": eval_data.get("gate_status", "UNKNOWN"),
                "verdict": eval_data.get("verdict", ""),
                "actor_level_move_share": eval_data.get("actor_level_move_share"),
                "actor_noop_share": eval_data.get("actor_noop_share"),
                "effective_position_delta_count": eval_data.get("effective_position_delta_count"),
                "no_effect_action_share": eval_data.get("no_effect_action_share"),
                "ready_movable_actor_choice_count": eval_data.get("ready_movable_actor_choice_count"),
                "full_action_counts": eval_data.get("full_action_counts"),
                "ready_actor_action_counts": eval_data.get("ready_actor_action_counts"),
            })
            print(
                f"[multiopp]   opponent={opponent} "
                f"status={result['status']} "
                f"actor_move={result.get('actor_level_move_share', 0.0):.4f} "
                f"pos_delta={result.get('effective_position_delta_count', 0)}"
            )
        else:
            result["verdict"] = "Output JSON not written despite exit 0."

    except subprocess.TimeoutExpired:
        result["verdict"] = f"Subprocess timed out after {timeout}s."
        result["subprocess_returncode"] = -1
        print(f"[multiopp]   opponent={opponent} TIMEOUT ({timeout}s)")

    return result


# ---------------------------------------------------------------------------
# Aggregation / verdict
# ---------------------------------------------------------------------------

def aggregate_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    pass_count = sum(1 for r in results if r.get("gate_status") == "PASS")
    any_pos_delta = any(
        (r.get("effective_position_delta_count") or 0) > 0 for r in results
    )
    all_no_effect_lt1 = all(
        (r.get("no_effect_action_share") or 1.0) < 1.0 for r in results
        if r.get("gate_status") == "PASS"
    )

    if pass_count >= 2 and any_pos_delta:
        aggregate_verdict = "CANDIDATE_VIABLE"
        aggregate_note = (
            f"PASS on {pass_count}/{len(results)} opponents. "
            "Consider continuation training or BC export."
        )
    elif pass_count == 1:
        only_pass = next((r for r in results if r.get("gate_status") == "PASS"), None)
        opp = only_pass["opponent"] if only_pass else "?"
        aggregate_verdict = "WEAK_SIGNAL_ONLY"
        aggregate_note = (
            f"PASS on {pass_count}/{len(results)} opponent(s) ({opp} only). "
            "Not teacher-ready. Continue training or revise reward/opponent schedule."
        )
    else:
        aggregate_verdict = "FAIL_ALL"
        aggregate_note = f"No PASS on any of {len(results)} opponents."

    return {
        "pass_count": pass_count,
        "total_opponents": len(results),
        "any_positive_position_delta": any_pos_delta,
        "all_passing_have_no_effect_lt_1": all_no_effect_lt1,
        "aggregate_verdict": aggregate_verdict,
        "aggregate_note": aggregate_note,
    }


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)


def _fmt(val: Any, fmt: str = ".4f") -> str:
    if val is None:
        return "N/A"
    try:
        return format(float(val), fmt)
    except (TypeError, ValueError):
        return str(val)


def write_markdown(path: Path, payload: Dict[str, Any]) -> None:
    agg = payload.get("aggregate", {})
    lines = [
        "# Gridnet Multi-Opponent Eval Summary",
        "",
        f"- checkpoint: {payload['checkpoint']}",
        f"- timestamp_utc: {payload['timestamp_utc']}",
        f"- deterministic_mode: {payload['deterministic_mode']}",
        f"- episodes_per_opponent: {payload['episodes_per_opponent']}",
        "",
        f"## Aggregate Verdict: {agg.get('aggregate_verdict', 'UNKNOWN')}",
        "",
        f"{agg.get('aggregate_note', '')}",
        "",
        f"- pass_count: {agg.get('pass_count', 0)} / {agg.get('total_opponents', 0)}",
        f"- any_positive_position_delta: {agg.get('any_positive_position_delta', False)}",
        "",
        "## Per-Opponent Results",
        "",
        "| opponent | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |",
        "|----------|--------|------------|------------|-----------|-----------|---------------|",
    ]
    for r in payload.get("per_opponent", []):
        lines.append(
            f"| {r['opponent']} "
            f"| {r.get('gate_status', 'ERROR')} "
            f"| {_fmt(r.get('actor_level_move_share'))} "
            f"| {_fmt(r.get('actor_noop_share'))} "
            f"| {r.get('effective_position_delta_count', 'N/A')} "
            f"| {_fmt(r.get('no_effect_action_share'))} "
            f"| {r.get('ready_movable_actor_choice_count', 'N/A')} |"
        )
    lines += [
        "",
        "## Notes",
        "- Each opponent was evaluated in an independent subprocess (separate JVM).",
        "- opponent-sampling=static within each subprocess.",
        "- PASS requires: effective_position_delta_count > 0, actor_level_move_share > 0, no_effect_action_share < 1.0.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    checkpoint = args.checkpoint.resolve()
    metadata = args.model_metadata.resolve()
    output_dir = args.output_dir.resolve()

    if not checkpoint.is_file():
        print(f"[multiopp] ERROR: checkpoint not found: {checkpoint}", file=sys.stderr)
        sys.exit(1)
    if not metadata.is_file():
        print(f"[multiopp] ERROR: model_metadata not found: {metadata}", file=sys.stderr)
        sys.exit(1)

    opponents = [o.strip() for o in args.opponents.split(",") if o.strip()]
    if not opponents:
        print("[multiopp] ERROR: No opponents specified.", file=sys.stderr)
        sys.exit(1)

    print(f"[multiopp] Checkpoint  : {checkpoint}")
    print(f"[multiopp] Opponents   : {opponents}")
    print(f"[multiopp] Episodes    : {args.episodes}")
    print(f"[multiopp] Deterministic: {args.deterministic}")
    print(f"[multiopp] Output dir  : {output_dir}")

    per_opponent_results: List[Dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="multiopp_") as tmp:
        tmp_dir = Path(tmp)
        for opp in opponents:
            r = run_single_opponent(
                python=args.python,
                checkpoint=checkpoint,
                metadata=metadata,
                map_path=args.map_path,
                opponent=opp,
                episodes=args.episodes,
                max_steps=args.max_steps,
                effective_steps=args.effective_steps,
                deterministic=args.deterministic,
                device=args.device,
                seed=args.seed,
                timeout=args.timeout,
                tmp_dir=tmp_dir,
            )
            per_opponent_results.append(r)

    aggregate = aggregate_results(per_opponent_results)

    stem = checkpoint.stem
    payload: Dict[str, Any] = {
        "schema": "gridnet_multiopponent_eval.v1",
        "timestamp_utc": utc_now(),
        "checkpoint": str(checkpoint),
        "model_metadata": str(metadata),
        "map_path": args.map_path,
        "episodes_per_opponent": args.episodes,
        "max_steps": args.max_steps,
        "effective_steps": args.effective_steps,
        "deterministic_mode": args.deterministic == "true",
        "opponents_evaluated": opponents,
        "aggregate": aggregate,
        "per_opponent": per_opponent_results,
    }

    out_json = output_dir / f"multiopponent_eval_{stem}.json"
    out_md = output_dir / f"multiopponent_eval_{stem}.md"
    write_json(out_json, payload)
    write_markdown(out_md, payload)

    print("")
    print(f"[multiopp] Aggregate verdict : {aggregate['aggregate_verdict']}")
    print(f"[multiopp] PASS count        : {aggregate['pass_count']} / {aggregate['total_opponents']}")
    print(f"[multiopp] Written           : {out_json}")
    print(f"[multiopp] Written           : {out_md}")

    # Exit 0 even if some opponents failed — summary captures all states.
    sys.exit(0)


if __name__ == "__main__":
    main()
