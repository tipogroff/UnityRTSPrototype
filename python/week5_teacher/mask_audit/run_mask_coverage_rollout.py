#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from mask_audit_utils import (
    DEFAULT_OUTPUT_DIR,
    build_full_mask_from_candidates,
    create_runtime_context,
    create_wrapped_env,
    environment_payload,
    flatten_mask,
    get_branch,
    parse_common_args,
    reset_compat,
    runtime_versions_payload,
    safe_action_space_sample,
    safe_json_dump,
    step_compat,
    utc_now,
)


def parse_args() -> argparse.Namespace:
    p = parse_common_args("Collect rollout mask coverage metrics across opponents.")
    p.add_argument("--steps", type=int, default=1000)
    p.add_argument("--opponents", default="passiveAI,workerRushAI,lightRushAI,coacAI")
    p.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "MASK_COVERAGE_ROLLOUT.json",
    )
    return p.parse_args()


def mean_safe(total: float, count: int) -> float:
    return float(total / count) if count > 0 else 0.0


def compute_metrics(flat_mask: np.ndarray) -> Dict[str, float]:
    source = flat_mask[:, :, 0] > 0
    ready_count = int(source.sum())

    action_type = get_branch(flat_mask, "action_type") > 0
    move = get_branch(flat_mask, "move_dir") > 0
    harvest = get_branch(flat_mask, "harvest_dir") > 0
    ret = get_branch(flat_mask, "return_dir") > 0
    produce_dir = get_branch(flat_mask, "produce_dir") > 0
    attack = get_branch(flat_mask, "attack_target") > 0

    valid_nonnoop = np.logical_and(source, np.any(action_type[:, :, 1:], axis=2))
    valid_move = np.logical_and(source, np.any(move, axis=2))
    valid_harvest = np.logical_and(source, np.any(harvest, axis=2))
    valid_return = np.logical_and(source, np.any(ret, axis=2))
    valid_produce = np.logical_and(source, np.any(produce_dir, axis=2))
    valid_attack = np.logical_and(source, np.any(attack, axis=2))

    if ready_count == 0:
        all_noop_only = 1.0
    else:
        all_noop_only = 1.0 if int(valid_nonnoop.sum()) == 0 else 0.0

    return {
        "owned_actor_cells": float(ready_count),
        "ready_actor_cells": float(ready_count),
        "valid_nonnoop_action_type_share": float(valid_nonnoop.sum() / max(1, ready_count)),
        "valid_move_share": float(valid_move.sum() / max(1, ready_count)),
        "valid_harvest_share": float(valid_harvest.sum() / max(1, ready_count)),
        "valid_return_share": float(valid_return.sum() / max(1, ready_count)),
        "valid_produce_share": float(valid_produce.sum() / max(1, ready_count)),
        "valid_attack_share": float(valid_attack.sum() / max(1, ready_count)),
        "all_noop_only_step": float(all_noop_only),
    }


def run_single_opponent(base_args: argparse.Namespace, opponent: str, ctx: Any) -> Dict[str, Any]:
    args = argparse.Namespace(**vars(base_args))
    args.opponent_pool = opponent
    args.opponent_sampling = "static"

    out: Dict[str, Any] = {
        "opponent": opponent,
        "status": "fail",
        "steps": int(args.steps),
        "steps_collected": 0,
        "warnings": [],
        "errors": [],
        "metrics": {},
    }

    env = None
    try:
        env, env_for_training, env_summary, _timing = create_wrapped_env(args, ctx)
        obs, info = reset_compat(env_for_training)

        sums = {
            "owned_actor_cells": 0.0,
            "ready_actor_cells": 0.0,
            "valid_nonnoop_action_type_share": 0.0,
            "valid_move_share": 0.0,
            "valid_harvest_share": 0.0,
            "valid_return_share": 0.0,
            "valid_produce_share": 0.0,
            "valid_attack_share": 0.0,
            "all_noop_only_step": 0.0,
        }

        for _ in range(max(1, int(args.steps))):
            mask_nhwk, _source, warns = build_full_mask_from_candidates(env_for_training, obs, infos=[info])
            out["warnings"].extend(warns)
            if mask_nhwk is not None:
                flat = flatten_mask(mask_nhwk)
                m = compute_metrics(flat)
                for key, value in m.items():
                    sums[key] += float(value)
                out["steps_collected"] += 1

            action = safe_action_space_sample(env_for_training)
            obs, _rew, _done, infos = step_compat(env_for_training, action)
            info = infos[0] if infos else {}

        n = int(out["steps_collected"])
        out["metrics"] = {
            "steps": n,
            "owned_actor_cells_mean": mean_safe(sums["owned_actor_cells"], n),
            "ready_actor_cells_mean": mean_safe(sums["ready_actor_cells"], n),
            "valid_nonnoop_action_type_share": mean_safe(sums["valid_nonnoop_action_type_share"], n),
            "valid_move_share": mean_safe(sums["valid_move_share"], n),
            "valid_harvest_share": mean_safe(sums["valid_harvest_share"], n),
            "valid_return_share": mean_safe(sums["valid_return_share"], n),
            "valid_produce_share": mean_safe(sums["valid_produce_share"], n),
            "valid_attack_share": mean_safe(sums["valid_attack_share"], n),
            "all_noop_only_steps_share": mean_safe(sums["all_noop_only_step"], n),
        }

        out["status"] = "pass" if n > 0 else "fail"
        out["environment"] = environment_payload(args, env_summary)

    except Exception as exc:
        out["errors"].append(f"Unhandled exception: {type(exc).__name__}: {exc}")
        out["status"] = "fail"
    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass

    return out


def main() -> int:
    args = parse_args()
    opponents = [t.strip() for t in str(args.opponents).split(",") if t.strip()]

    errors: List[str] = []
    warnings: List[str] = []
    ctx = create_runtime_context(args.seed)

    per_opponent: Dict[str, Any] = {}
    for opp in opponents:
        per_opponent[opp] = run_single_opponent(args, opp, ctx)

    applied = [name for name, item in per_opponent.items() if item.get("status") == "pass"]
    skipped = [name for name, item in per_opponent.items() if item.get("status") != "pass"]

    # Aggregate only from successful opponents.
    agg_keys = [
        "owned_actor_cells_mean",
        "ready_actor_cells_mean",
        "valid_nonnoop_action_type_share",
        "valid_move_share",
        "valid_harvest_share",
        "valid_return_share",
        "valid_produce_share",
        "valid_attack_share",
        "all_noop_only_steps_share",
    ]
    agg = {k: 0.0 for k in agg_keys}
    count = 0
    for item in per_opponent.values():
        if item.get("status") != "pass":
            continue
        m = item.get("metrics", {})
        count += 1
        for key in agg_keys:
            agg[key] += float(m.get(key, 0.0))
    if count > 0:
        for key in agg_keys:
            agg[key] = float(agg[key] / count)

    if skipped:
        warnings.append(f"Some opponents failed/skipped: {skipped}")

    report: Dict[str, Any] = {
        "status": "pass" if count > 0 and len(errors) == 0 else "fail",
        "generated_at_utc": utc_now(),
        "requested_opponents": opponents,
        "applied_opponents": applied,
        "skipped_opponents": skipped,
        "per_opponent": per_opponent,
        "aggregate": {
            "steps": int(args.steps),
            **agg,
        },
        "errors": errors,
        "warnings": warnings,
        "runtime_versions": runtime_versions_payload(ctx.versions),
    }

    safe_json_dump(args.output_json, report)
    print(args.output_json)
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
