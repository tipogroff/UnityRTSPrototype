#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import torch

from mask_audit_utils import (
    BRANCH_LAYOUT,
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


def parse_args() -> argparse.Namespace:
    p = parse_common_args("Audit log_prob/entropy consistency between sampling and PPO-eval path.")
    p.add_argument("--trials", type=int, default=32)
    p.add_argument("--tolerance", type=float, default=1e-5)
    p.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "MASK_AUDIT_LOGPROB.json",
    )
    return p.parse_args()


def source_code_check(root: Path) -> Dict[str, Any]:
    train_path = root / "python" / "week5_teacher_gridnet" / "train_teacher_gridnet_project.py"
    result = {
        "train_file": str(train_path),
        "has_rollout_mask_read": False,
        "has_rollout_mask_store": False,
        "has_eval_mask_usage": False,
        "has_entropy_from_masked_path": False,
        "warnings": [],
    }
    if not train_path.is_file():
        result["warnings"].append("train_teacher_gridnet_project.py not found.")
        return result

    text = train_path.read_text(encoding="utf-8")
    result["has_rollout_mask_read"] = "read_invalid_action_masks(" in text
    result["has_rollout_mask_store"] = "invalid_masks_storage[step] = current_invalid_masks" in text
    result["has_eval_mask_usage"] = "invalid_action_masks=b_invalid_masks[mb_inds]" in text
    result["has_entropy_from_masked_path"] = "_, newlogprob, entropy, _ = agent.get_action(" in text

    if not result["has_eval_mask_usage"]:
        result["warnings"].append("Could not confirm invalid mask forwarding into PPO minibatch evaluate path.")
    if not result["has_entropy_from_masked_path"]:
        result["warnings"].append("Could not confirm entropy computed via masked distribution call.")
    return result


def main() -> int:
    args = parse_args()
    errors: List[str] = []
    warnings: List[str] = []

    report: Dict[str, Any] = {
        "status": "fail",
        "generated_at_utc": utc_now(),
        "trials": int(args.trials),
        "tolerance": float(args.tolerance),
        "logprob_deltas": [],
        "max_abs_logprob_delta": None,
        "entropy_sample_time": [],
        "entropy_eval_time": [],
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
            errors.append("Cannot run logprob audit: full mask unavailable.")
        else:
            obs_shape = tuple(int(v) for v in obs.shape[1:])
            mapsize = int(obs_shape[0] * obs_shape[1])
            action_nvec = [mapsize] + BRANCH_LAYOUT

            device = torch.device("cpu")
            agent = Agent(obs_shape, action_nvec).to(device)
            agent.eval()

            obs_t = torch.as_tensor(obs, dtype=torch.float32, device=device)
            mask_t = torch.as_tensor(flatten_mask(mask_nhwk), dtype=torch.float32, device=device)

            deltas = []
            entropy_s = []
            entropy_e = []
            for _ in range(max(1, int(args.trials))):
                with torch.no_grad():
                    action_t, logprob_sample, entropy_sample, _ = agent.get_action(
                        obs_t,
                        invalid_action_masks=mask_t,
                        action=None,
                        deterministic=False,
                    )
                    _same_action, logprob_eval, entropy_eval, _ = agent.get_action(
                        obs_t,
                        invalid_action_masks=mask_t,
                        action=action_t,
                        deterministic=False,
                    )

                delta = torch.abs(logprob_sample - logprob_eval).detach().cpu().numpy().reshape(-1)
                deltas.extend([float(x) for x in delta.tolist()])
                entropy_s.extend([float(x) for x in entropy_sample.detach().cpu().numpy().reshape(-1).tolist()])
                entropy_e.extend([float(x) for x in entropy_eval.detach().cpu().numpy().reshape(-1).tolist()])

            report["logprob_deltas"] = deltas
            report["max_abs_logprob_delta"] = float(max(deltas)) if deltas else None
            report["entropy_sample_time"] = entropy_s
            report["entropy_eval_time"] = entropy_e

            if report["max_abs_logprob_delta"] is None:
                errors.append("No logprob deltas collected.")
            elif report["max_abs_logprob_delta"] >= float(args.tolerance):
                errors.append(
                    f"log_prob mismatch: max_abs_delta={report['max_abs_logprob_delta']} >= tolerance={args.tolerance}"
                )

            entropy_diff = np.max(np.abs(np.asarray(entropy_s) - np.asarray(entropy_e))) if entropy_s else None
            report["max_abs_entropy_delta"] = float(entropy_diff) if entropy_diff is not None else None

            source_check = source_code_check(Path(__file__).resolve().parents[3])
            report["training_path_source_check"] = source_check
            warnings.extend(source_check.get("warnings", []))
            if not source_check["has_eval_mask_usage"]:
                errors.append("evaluate_actions path in training script does not clearly pass invalid_action_masks.")

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
