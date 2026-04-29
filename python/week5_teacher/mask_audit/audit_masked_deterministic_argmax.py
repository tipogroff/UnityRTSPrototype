#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import torch

from mask_audit_utils import (
    BRANCH_LAYOUT,
    BRANCH_NAMES,
    DEFAULT_OUTPUT_DIR,
    branch_slices,
    build_full_mask_from_candidates,
    create_runtime_context,
    create_wrapped_env,
    environment_payload,
    flatten_mask,
    parse_common_args,
    reset_compat,
    runtime_versions_payload,
    safe_action_space_sample,
    safe_json_dump,
    step_compat,
    utc_now,
)

from gridnet_model import Agent


def is_branch_relevant(action_type: int, branch_idx: int) -> bool:
    if branch_idx == 0:
        return True
    if branch_idx == 1:
        return action_type == 1
    if branch_idx == 2:
        return action_type == 2
    if branch_idx == 3:
        return action_type == 3
    if branch_idx in (4, 5):
        return action_type == 4
    if branch_idx == 6:
        return action_type == 5
    return False


def parse_args() -> argparse.Namespace:
    p = parse_common_args("Audit deterministic argmax behavior under mask.")
    p.add_argument("--steps", type=int, default=32)
    p.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "MASK_AUDIT_ARGMAX.json",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    errors: List[str] = []
    warnings: List[str] = []

    metrics = {
        "masked_argmax_invalid": {name: 0 for name in BRANCH_NAMES},
        "masked_argmax_noop_when_nonnoop_available": 0,
        "ready_actor_cells": 0,
    }

    report: Dict[str, Any] = {
        "status": "fail",
        "generated_at_utc": utc_now(),
        "steps": int(args.steps),
        "metrics": metrics,
        "errors": errors,
        "warnings": warnings,
    }

    ctx = create_runtime_context(args.seed)
    env = None
    try:
        env, env_for_training, env_summary, _timing = create_wrapped_env(args, ctx)
        obs, info = reset_compat(env_for_training)

        mask_nhwk = None
        mask_source = "unknown"
        for _ in range(20):
            mask_nhwk, mask_source, mask_warnings = build_full_mask_from_candidates(env_for_training, obs, infos=[info])
            warnings.extend(mask_warnings)
            if mask_nhwk is not None:
                break
            action = safe_action_space_sample(env_for_training)
            obs, _rew, _done, infos = step_compat(env_for_training, action)
            info = infos[0] if infos else {}
        report["mask_source"] = mask_source

        if mask_nhwk is None:
            errors.append("Cannot run deterministic argmax audit: full mask unavailable.")
        else:
            obs_shape = tuple(int(v) for v in obs.shape[1:])
            mapsize = int(obs_shape[0] * obs_shape[1])
            action_nvec = [mapsize] + BRANCH_LAYOUT

            device = torch.device("cpu")
            agent = Agent(obs_shape, action_nvec).to(device)
            agent.eval()

            for _ in range(max(1, int(args.steps))):
                flat_mask = flatten_mask(mask_nhwk)
                obs_t = torch.as_tensor(obs, dtype=torch.float32, device=device)
                mask_t = torch.as_tensor(flat_mask, dtype=torch.float32, device=device)

                with torch.no_grad():
                    action_t, _lp, _ent, _used = agent.get_action(
                        obs_t,
                        invalid_action_masks=mask_t,
                        action=None,
                        deterministic=True,
                    )
                action_np = action_t.detach().cpu().numpy().astype(np.int64)

                actor_cells = np.argwhere(flat_mask[:, :, 0] > 0)
                metrics["ready_actor_cells"] += int(actor_cells.shape[0])

                slices = branch_slices()
                for env_i, cell_i in actor_cells:
                    env_i = int(env_i)
                    cell_i = int(cell_i)
                    chosen_type = int(action_np[env_i, cell_i, 0])
                    for b_idx, branch_name in enumerate(BRANCH_NAMES):
                        if not is_branch_relevant(chosen_type, b_idx):
                            continue
                        chosen = int(action_np[env_i, cell_i, b_idx])
                        s, _e = slices[branch_name]
                        branch_mask = flat_mask[env_i, cell_i, s : s + BRANCH_LAYOUT[b_idx]]
                        if np.all(branch_mask <= 0):
                            continue
                        if chosen < 0 or chosen >= BRANCH_LAYOUT[b_idx]:
                            metrics["masked_argmax_invalid"][branch_name] += 1
                            continue
                        if flat_mask[env_i, cell_i, s + chosen] <= 0:
                            metrics["masked_argmax_invalid"][branch_name] += 1

                    action_type_slice = flat_mask[env_i, cell_i, slices["action_type"][0]:slices["action_type"][1]]
                    nonnoop_available = bool(np.any(action_type_slice[1:] > 0))
                    if nonnoop_available and chosen_type == 0:
                        metrics["masked_argmax_noop_when_nonnoop_available"] += 1

                action = safe_action_space_sample(env_for_training)
                obs, _rew, _done, infos = step_compat(env_for_training, action)
                info = infos[0] if infos else {}
                next_mask, _next_source, next_warnings = build_full_mask_from_candidates(env_for_training, obs, infos=infos)
                warnings.extend(next_warnings)
                if next_mask is not None:
                    mask_nhwk = next_mask

            invalid_total = int(sum(metrics["masked_argmax_invalid"].values()))
            if invalid_total > 0:
                errors.append(f"masked_argmax_invalid total is {invalid_total}.")
            if metrics["ready_actor_cells"] == 0:
                warnings.append("No ready actor cells observed during deterministic audit steps.")

            report["classification"] = {
                "technical_mask_error": invalid_total > 0,
                "policy_collapse_signal": (
                    invalid_total == 0 and metrics["masked_argmax_noop_when_nonnoop_available"] > 0
                ),
            }
            report["obs_shape"] = list(obs.shape)
            report["mask_shape"] = list(mask_nhwk.shape)

        report["runtime_versions"] = runtime_versions_payload(ctx.versions)
        report["environment"] = environment_payload(args, env_summary)
        report["status"] = "pass" if len(errors) == 0 else "fail"

    except Exception as exc:
        errors.append(f"Unhandled exception: {type(exc).__name__}: {exc}")
        report["status"] = "fail"
    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass

    safe_json_dump(args.output_json, report)
    print(args.output_json)
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
