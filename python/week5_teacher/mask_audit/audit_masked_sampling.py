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
    p = parse_common_args("Audit that masked sampling never selects invalid branch values.")
    p.add_argument("--samples", type=int, default=10000)
    p.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "MASK_AUDIT_SAMPLING.json",
    )
    return p.parse_args()


def gather_state(env_for_training: Any, max_steps: int = 20):
    obs, info = reset_compat(env_for_training)
    for _ in range(max_steps):
        mask, source, warns = build_full_mask_from_candidates(env_for_training, obs, infos=[info])
        if mask is not None:
            return obs, mask, source, warns
        action = safe_action_space_sample(env_for_training)
        obs, _rew, _done, infos = step_compat(env_for_training, action)
        info = infos[0] if infos else {}
    return obs, None, "unknown", ["Unable to obtain full mask during warmup steps."]


def main() -> int:
    args = parse_args()
    errors: List[str] = []
    warnings: List[str] = []
    invalid = {name: 0 for name in BRANCH_NAMES}

    report: Dict[str, Any] = {
        "status": "fail",
        "generated_at_utc": utc_now(),
        "samples": int(args.samples),
        "invalid_sampled": invalid,
        "errors": errors,
        "warnings": warnings,
    }

    ctx = create_runtime_context(args.seed)
    env = None

    try:
        env, env_for_training, env_summary, _timing = create_wrapped_env(args, ctx)
        obs, mask_nhwk, source, warm_warnings = gather_state(env_for_training)
        warnings.extend(warm_warnings)
        report["mask_source"] = source

        if mask_nhwk is None:
            errors.append("Cannot run sampling audit: full mask unavailable.")
        else:
            obs_shape = tuple(int(v) for v in obs.shape[1:])
            mapsize = int(obs_shape[0] * obs_shape[1])
            action_nvec = [mapsize] + BRANCH_LAYOUT

            device = torch.device("cpu")
            agent = Agent(obs_shape, action_nvec).to(device)
            agent.eval()

            obs_t = torch.as_tensor(obs, dtype=torch.float32, device=device)
            flat_mask = flatten_mask(mask_nhwk)
            mask_t = torch.as_tensor(flat_mask, dtype=torch.float32, device=device)

            n_env, cells, _ = flat_mask.shape
            rng = np.random.default_rng(args.seed + 333)

            actor_indices: List[tuple[int, int]] = []
            actor_coords = np.argwhere(flat_mask[:, :, 0] > 0)
            if actor_coords.size == 0:
                errors.append("No actor/source-valid cells found in sampled state.")
            else:
                for _ in range(max(1, int(args.samples))):
                    pick = actor_coords[rng.integers(0, actor_coords.shape[0])]
                    actor_indices.append((int(pick[0]), int(pick[1])))

            if not errors:
                for _ in range(max(1, int(args.samples))):
                    with torch.no_grad():
                        action_t, _lp, _ent, _used = agent.get_action(
                            obs_t,
                            invalid_action_masks=mask_t,
                            action=None,
                            deterministic=False,
                        )
                    action_np = action_t.detach().cpu().numpy().astype(np.int64)

                    for env_i, cell_i in actor_indices[: min(len(actor_indices), n_env * 3)]:
                        chosen_type = int(action_np[env_i, cell_i, 0])
                        for b_idx, name in enumerate(BRANCH_NAMES):
                            if not is_branch_relevant(chosen_type, b_idx):
                                continue
                            chosen = int(action_np[env_i, cell_i, b_idx])
                            offset = 1 + sum(BRANCH_LAYOUT[:b_idx])
                            branch_mask = flat_mask[env_i, cell_i, offset : offset + BRANCH_LAYOUT[b_idx]]
                            if np.all(branch_mask <= 0):
                                continue
                            if chosen < 0 or chosen >= BRANCH_LAYOUT[b_idx]:
                                invalid[name] += 1
                                continue
                            if flat_mask[env_i, cell_i, offset + chosen] <= 0:
                                invalid[name] += 1

            report["obs_shape"] = list(obs.shape)
            report["mask_shape"] = list(mask_nhwk.shape)

        report["runtime_versions"] = runtime_versions_payload(ctx.versions)
        report["environment"] = environment_payload(args, env_summary)

        has_invalid = any(v > 0 for v in invalid.values())
        report["status"] = "pass" if (len(errors) == 0 and not has_invalid) else "fail"

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
