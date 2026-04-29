#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

import numpy as np

from mask_audit_utils import (
    BRANCH_LAYOUT,
    BRANCH_NAMES,
    DEFAULT_OUTPUT_DIR,
    EXPECTED_MASK_DEPTH,
    create_runtime_context,
    create_wrapped_env,
    environment_payload,
    flatten_mask,
    get_branch,
    mask_has_expected_shape,
    parse_common_args,
    reset_compat,
    runtime_versions_payload,
    safe_action_space_sample,
    safe_json_dump,
    step_compat,
    utc_now,
    build_full_mask_from_candidates,
)


def parse_args() -> argparse.Namespace:
    p = parse_common_args("Audit mask availability/shape/layout on env reset and several steps.")
    p.add_argument("--steps", type=int, default=5)
    p.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "MASK_AUDIT_SURFACE.json",
    )
    return p.parse_args()


def init_counts() -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {}
    for name in BRANCH_NAMES:
        out[name] = {"valid_entries": 0, "total_entries": 0, "actor_cells_seen": 0}
    return out


def main() -> int:
    args = parse_args()
    errors = []
    warnings = []

    report: Dict[str, Any] = {
        "status": "fail",
        "generated_at_utc": utc_now(),
        "obs_shape": None,
        "mask_shape": None,
        "expected_mask_shape_tail": [24, 24, 79],
        "branch_layout": BRANCH_LAYOUT,
        "mask_source": "unknown",
        "actor_mask_nonzero_count": 0,
        "actor_mask_all_zero": True,
        "actor_mask_all_one": False,
        "branch_valid_counts": init_counts(),
        "errors": errors,
        "warnings": warnings,
    }

    ctx = create_runtime_context(args.seed)
    env = None
    try:
        env, env_for_training, env_summary, _timing = create_wrapped_env(args, ctx)
        obs, info = reset_compat(env_for_training)
        report["obs_shape"] = list(obs.shape)

        full_mask, mask_source, mask_warnings = build_full_mask_from_candidates(env_for_training, obs, infos=[info])
        report["mask_source"] = mask_source
        warnings.extend(mask_warnings)

        if full_mask is None:
            errors.append("Action mask unavailable or cannot be normalized to full [N,H,W,79].")
        else:
            report["mask_shape"] = list(full_mask.shape)
            if not mask_has_expected_shape(full_mask, obs):
                errors.append(
                    f"Mask shape mismatch: got {tuple(full_mask.shape)}, expected [{obs.shape[0]}, {obs.shape[1]}, {obs.shape[2]}, {EXPECTED_MASK_DEPTH}]"
                )

            flat = flatten_mask(full_mask)
            actor = flat[:, :, 0] > 0
            report["actor_mask_nonzero_count"] = int(actor.sum())
            report["actor_mask_all_zero"] = bool(np.all(~actor))
            report["actor_mask_all_one"] = bool(np.all(actor))

            if report["actor_mask_all_zero"]:
                errors.append("actor/source mask is all-zero on reset.")
            if report["actor_mask_all_one"]:
                warnings.append("actor/source mask is all-one on reset; unexpected for typical states.")

            for _ in range(max(0, int(args.steps))):
                action = safe_action_space_sample(env_for_training)
                obs, _rew, _done, infos = step_compat(env_for_training, action)
                step_mask, step_source, step_warnings = build_full_mask_from_candidates(env_for_training, obs, infos=infos)
                if step_mask is None:
                    warnings.append("step mask unavailable; skipping this step")
                    warnings.extend(step_warnings)
                    continue
                if step_source != mask_source:
                    warnings.append(f"mask source changed from {mask_source} to {step_source}")
                warnings.extend(step_warnings)

                step_flat = flatten_mask(step_mask)
                step_actor = step_flat[:, :, 0] > 0
                for branch_name in BRANCH_NAMES:
                    br = get_branch(step_flat, branch_name) > 0
                    valid_entries = int(br.sum())
                    total_entries = int(br.size)
                    actor_cells = int(step_actor.sum())
                    report["branch_valid_counts"][branch_name]["valid_entries"] += valid_entries
                    report["branch_valid_counts"][branch_name]["total_entries"] += total_entries
                    report["branch_valid_counts"][branch_name]["actor_cells_seen"] += actor_cells

            for branch_name in BRANCH_NAMES:
                if report["branch_valid_counts"][branch_name]["valid_entries"] == 0:
                    warnings.append(f"Branch '{branch_name}' had zero valid entries across sampled steps.")

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
