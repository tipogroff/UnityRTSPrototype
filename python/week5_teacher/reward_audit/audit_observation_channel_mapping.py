#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from reward_audit_utils import (
    ACTION_ATTACK_CH,
    ACTION_HARVEST_CH,
    ACTION_MOVE_CH,
    ACTION_NOOP_CH,
    ACTION_PRODUCE_CH,
    ACTION_RETURN_CH,
    OWNER_NEUTRAL_CH,
    OWNER_PLAYER1_CH,
    OWNER_PLAYER2_CH,
    UNIT_BARRACKS_CH,
    UNIT_BASE_CH,
    UNIT_HEAVY_CH,
    UNIT_LIGHT_CH,
    UNIT_RANGED_CH,
    UNIT_RESOURCE_CH,
    UNIT_WORKER_CH,
    DEFAULT_ENV_ID,
    DEFAULT_MAP_PATH,
    flatten_obs,
    make_env_and_reset,
    step_compat,
    utc_now,
    write_json,
    write_md,
)
from mask_audit_utils import build_full_mask_from_candidates, flatten_mask, safe_action_space_sample


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Audit observation channel mapping against actor-valid mask cells.")
    p.add_argument("--env-id", default=DEFAULT_ENV_ID)
    p.add_argument("--map-path", default=DEFAULT_MAP_PATH)
    p.add_argument("--seed", type=int, default=170)
    p.add_argument("--step-limit", type=int, default=200)
    p.add_argument("--num-bot-envs", type=int, default=1)
    p.add_argument("--opponent-pool", default="passiveAI")
    p.add_argument("--opponent-sampling", choices=("static", "per_reset", "per_episode"), default="static")
    p.add_argument("--device", default="cpu")
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path("python/week5_teacher/reward_audit/OBS_CHANNEL_MAPPING_AUDIT.json"),
    )
    p.add_argument(
        "--output-md",
        type=Path,
        default=Path("python/week5_teacher/reward_audit/OBS_CHANNEL_MAPPING_AUDIT.md"),
    )
    p.add_argument("--example-cells", type=int, default=20)
    return p.parse_args()


def _count_nonzero(flat_obs: np.ndarray, ch: int) -> int:
    if flat_obs.shape[-1] <= ch:
        return 0
    return int((flat_obs[:, :, ch] > 0.5).sum())


def main() -> int:
    args = parse_args()
    args.rollout_step_limit = int(args.step_limit)

    env = None
    warnings: List[str] = []
    errors: List[str] = []

    owner_counts = {
        "owner_neutral": 0,
        "owner_player1": 0,
        "owner_player2": 0,
    }
    unit_counts = {
        "unit_resource": 0,
        "unit_base": 0,
        "unit_barracks": 0,
        "unit_worker": 0,
        "unit_light": 0,
        "unit_heavy": 0,
        "unit_ranged": 0,
    }
    action_channel_counts = {
        "action_noop": 0,
        "action_move": 0,
        "action_harvest": 0,
        "action_return": 0,
        "action_produce": 0,
        "action_attack": 0,
    }

    actor_valid_count = 0
    actor_valid_with_any_unit = 0
    actor_valid_examples: List[Dict[str, Any]] = []

    try:
        _ctx, env, env_for_training, env_summary, obs, info, _meta, init_warnings = make_env_and_reset(args)
        warnings.extend(init_warnings)

        for _ in range(int(args.step_limit)):
            obs_arr = np.asarray(obs)
            obs_flat = flatten_obs(obs_arr)

            owner_counts["owner_neutral"] += _count_nonzero(obs_flat, OWNER_NEUTRAL_CH)
            owner_counts["owner_player1"] += _count_nonzero(obs_flat, OWNER_PLAYER1_CH)
            owner_counts["owner_player2"] += _count_nonzero(obs_flat, OWNER_PLAYER2_CH)

            unit_counts["unit_resource"] += _count_nonzero(obs_flat, UNIT_RESOURCE_CH)
            unit_counts["unit_base"] += _count_nonzero(obs_flat, UNIT_BASE_CH)
            unit_counts["unit_barracks"] += _count_nonzero(obs_flat, UNIT_BARRACKS_CH)
            unit_counts["unit_worker"] += _count_nonzero(obs_flat, UNIT_WORKER_CH)
            unit_counts["unit_light"] += _count_nonzero(obs_flat, UNIT_LIGHT_CH)
            unit_counts["unit_heavy"] += _count_nonzero(obs_flat, UNIT_HEAVY_CH)
            unit_counts["unit_ranged"] += _count_nonzero(obs_flat, UNIT_RANGED_CH)

            action_channel_counts["action_noop"] += _count_nonzero(obs_flat, ACTION_NOOP_CH)
            action_channel_counts["action_move"] += _count_nonzero(obs_flat, ACTION_MOVE_CH)
            action_channel_counts["action_harvest"] += _count_nonzero(obs_flat, ACTION_HARVEST_CH)
            action_channel_counts["action_return"] += _count_nonzero(obs_flat, ACTION_RETURN_CH)
            action_channel_counts["action_produce"] += _count_nonzero(obs_flat, ACTION_PRODUCE_CH)
            action_channel_counts["action_attack"] += _count_nonzero(obs_flat, ACTION_ATTACK_CH)

            mask_nhwk, _source, mask_warn = build_full_mask_from_candidates(env_for_training, obs_arr, infos=[info])
            warnings.extend(mask_warn)
            if mask_nhwk is not None:
                flat_mask = flatten_mask(mask_nhwk)
                n = int(mask_nhwk.shape[0])
                h = int(mask_nhwk.shape[1])
                w = int(mask_nhwk.shape[2])
                for env_i in range(n):
                    for cell in range(h * w):
                        if flat_mask[env_i, cell, 0] <= 0:
                            continue
                        actor_valid_count += 1
                        y = int(cell // w)
                        x = int(cell % w)
                        obs_cell = obs_arr[env_i, y, x]
                        unit_vec = obs_cell[UNIT_RESOURCE_CH : UNIT_RANGED_CH + 1]
                        owner_vec = obs_cell[OWNER_NEUTRAL_CH : OWNER_PLAYER2_CH + 1]
                        if np.any(unit_vec > 0.5):
                            actor_valid_with_any_unit += 1
                        if len(actor_valid_examples) < int(args.example_cells):
                            action_mask = flat_mask[env_i, cell, 1 : 1 + 6]
                            actor_valid_examples.append(
                                {
                                    "env": env_i,
                                    "y": y,
                                    "x": x,
                                    "owner_vector": [float(v) for v in owner_vec.tolist()],
                                    "unit_type_vector": [float(v) for v in unit_vec.tolist()],
                                    "valid_action_type_mask": [int(v > 0) for v in action_mask.tolist()],
                                }
                            )

            action = safe_action_space_sample(env_for_training)
            obs, _rew, _done, infos = step_compat(env_for_training, action)
            info = infos[0] if infos else {}

        report = {
            "schema": "week5_obs_channel_mapping_audit.v1",
            "generated_at_utc": utc_now(),
            "environment": {
                "env_id": args.env_id,
                "map_path": args.map_path,
                "opponent_pool": args.opponent_pool,
                "opponent_sampling": args.opponent_sampling,
                "num_bot_envs": int(args.num_bot_envs),
                "seed": int(args.seed),
                "env_summary": env_summary,
            },
            "counts": {
                "owner": owner_counts,
                "unit": unit_counts,
                "action_channels": action_channel_counts,
            },
            "mask_alignment": {
                "actor_valid_cells": int(actor_valid_count),
                "actor_valid_cells_with_any_unit": int(actor_valid_with_any_unit),
                "actor_valid_with_unit_share": float(actor_valid_with_any_unit / max(1, actor_valid_count)),
            },
            "actor_valid_examples": actor_valid_examples,
            "warnings": sorted(set(str(w) for w in warnings if str(w).strip())),
            "errors": errors,
        }

        write_json(args.output_json, report)

        md_lines = [
            "# OBS_CHANNEL_MAPPING_AUDIT",
            "",
            "## Environment",
            f"- env_id: {args.env_id}",
            f"- map_path: {args.map_path}",
            f"- opponent_pool: {args.opponent_pool}",
            f"- steps: {args.step_limit}",
            "",
            "## Owner Channel Counts",
            f"- owner_neutral: {owner_counts['owner_neutral']}",
            f"- owner_player1: {owner_counts['owner_player1']}",
            f"- owner_player2: {owner_counts['owner_player2']}",
            "",
            "## Unit Channel Counts",
            f"- unit_resource: {unit_counts['unit_resource']}",
            f"- unit_base: {unit_counts['unit_base']}",
            f"- unit_barracks: {unit_counts['unit_barracks']}",
            f"- unit_worker: {unit_counts['unit_worker']}",
            f"- unit_light: {unit_counts['unit_light']}",
            f"- unit_heavy: {unit_counts['unit_heavy']}",
            f"- unit_ranged: {unit_counts['unit_ranged']}",
            "",
            "## Action Channel Counts",
            f"- action_noop: {action_channel_counts['action_noop']}",
            f"- action_move: {action_channel_counts['action_move']}",
            f"- action_harvest: {action_channel_counts['action_harvest']}",
            f"- action_return: {action_channel_counts['action_return']}",
            f"- action_produce: {action_channel_counts['action_produce']}",
            f"- action_attack: {action_channel_counts['action_attack']}",
            "",
            "## Mask Alignment",
            f"- actor_valid_cells: {actor_valid_count}",
            f"- actor_valid_cells_with_any_unit: {actor_valid_with_any_unit}",
            f"- actor_valid_with_unit_share: {report['mask_alignment']['actor_valid_with_unit_share']:.6f}",
            "",
            "## Example actor_valid cells",
        ]
        for ex in actor_valid_examples:
            md_lines.append(
                f"- (env={ex['env']}, y={ex['y']}, x={ex['x']}): owner={ex['owner_vector']}, unit={ex['unit_type_vector']}, valid_action_type={ex['valid_action_type_mask']}"
            )

        if report["warnings"]:
            md_lines.append("")
            md_lines.append("## Warnings")
            for w in report["warnings"]:
                md_lines.append(f"- {w}")

        write_md(args.output_md, md_lines)
        print(args.output_json)
        print(args.output_md)
        return 0
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        fail = {
            "schema": "week5_obs_channel_mapping_audit.v1",
            "generated_at_utc": utc_now(),
            "errors": errors,
            "warnings": warnings,
        }
        write_json(args.output_json, fail)
        write_md(args.output_md, ["# OBS_CHANNEL_MAPPING_AUDIT", "", "- status: fail", f"- error: {errors[-1]}"])
        print(args.output_json)
        print(args.output_md)
        return 2
    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
