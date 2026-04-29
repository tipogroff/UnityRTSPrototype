#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from scripted_bc_utils import (
    TARGETED_POLICY_MODES,
    ACTION_TYPE_NAMES,
    build_policy_action,
    DEFAULT_DATASET,
    DEFAULT_MANIFEST,
    DEFAULT_OUT_DIR,
    build_full_mask_from_candidates,
    branch_slices,
    class_presence_from_hist,
        init_probe_diagnostics,
        merge_probe_diagnostics,
    ensure_full_mask,
    fallback_fill_invalid_actions,
    flatten_mask,
    flatten_obs,
    make_env_once,
    reset_compat,
    step_compat,
    to_env_action_shape,
    to_spatial_action,
    utc_now,
    validate_action_against_mask,
    write_json,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export minimal scripted dataset in Gridnet-native branch layout.")
    p.add_argument("--samples", type=int, default=1024)
    p.add_argument("--env-id", default="MicrortsSelfPlayShapedReward-v1")
    p.add_argument("--map-path", default="maps/24x24/basesWorkers24x24.xml")
    p.add_argument("--seed", type=int, default=170)
    p.add_argument("--owner-mode", choices=("player1", "relative", "mask_only"), default="mask_only")
    p.add_argument(
        "--generation-mode",
        choices=(
            "scripted_probe",
            "economy_probe",
            "production_probe",
            "combat_probe",
            "mixed_probe",
            "balanced_probes",
        ),
        default="scripted_probe",
    )
    p.add_argument("--step-limit", type=int, default=2000)
    p.add_argument("--episodes", type=int, default=16)
    p.add_argument("--opponent-pool", default="passiveAI")
    p.add_argument("--opponent-sampling", choices=("static", "per_reset", "per_episode"), default="static")
    p.add_argument("--num-bot-envs", type=int, default=1)
    p.add_argument("--device", default="cpu")
    p.add_argument("--output-dataset", type=Path, default=DEFAULT_DATASET)
    p.add_argument("--output-manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    args.rollout_step_limit = int(args.step_limit)

    obs_rows: List[np.ndarray] = []
    mask_rows: List[np.ndarray] = []
    action_rows: List[np.ndarray] = []
    actor_rows: List[np.ndarray] = []

    warnings: List[str] = []
    errors: List[str] = []
    class_hist: Dict[str, int] = {name: 0 for name in ACTION_TYPE_NAMES.values()}
    per_mode_sample_count: Dict[str, int] = {}
    per_mode_action_histogram: Dict[str, Dict[str, int]] = {}
    per_mode_probe_diagnostics: Dict[str, Dict[str, int]] = {}

    fallback_to_valid_count = 0
    fallback_to_noop_count = 0
    invalid_after_generation_count = 0

    env = None
    env_for_training = None

    try:
        ctx, env, env_for_training, env_summary, obs, info, mask_meta, init_warnings = make_env_once(args)
        warnings.extend(init_warnings)

        samples_collected = 0
        episode_idx = 0

        balanced_modes = ["economy_probe", "production_probe", "combat_probe", "mixed_probe"]

        while samples_collected < int(args.samples) and episode_idx < int(args.episodes):
            if episode_idx > 0:
                obs, info = reset_compat(env_for_training)

            done = False
            steps = 0
            while (not done) and steps < int(args.step_limit) and samples_collected < int(args.samples):
                mask_nhwk, mask_source, mask_warn = build_full_mask_from_candidates(env_for_training, obs, infos=[info])
                warnings.extend(mask_warn)
                if mask_nhwk is None:
                    raise RuntimeError("Mask unavailable during scripted dataset export.")
                mask_nhwk = ensure_full_mask(np.asarray(mask_nhwk))

                obs_flat = flatten_obs(np.asarray(obs))
                mask_flat = flatten_mask(mask_nhwk)

                if args.generation_mode == "balanced_probes":
                    active_mode = balanced_modes[samples_collected % len(balanced_modes)]
                else:
                    active_mode = str(args.generation_mode)

                step_diag = init_probe_diagnostics()
                actions = build_policy_action(
                    active_mode,
                    obs_flat,
                    mask_flat,
                    warnings,
                    owner_mode=args.owner_mode,
                    diagnostics=step_diag,
                )
                actions, fb = fallback_fill_invalid_actions(actions, mask_flat)

                fallback_to_valid_count += int(fb["fallback_to_valid_count"])
                fallback_to_noop_count += int(fb["fallback_to_noop_count"])
                invalid_after_generation_count += int(fb["invalid_after_generation_count"])

                actor_valid = mask_nhwk[:, :, :, 0] > 0
                n, h, w, _ = mask_nhwk.shape
                actions_spatial = to_spatial_action(actions, h, w)

                per_mode_sample_count[active_mode] = int(per_mode_sample_count.get(active_mode, 0))
                per_mode_action_hist = per_mode_action_histogram.setdefault(
                    active_mode, {name: 0 for name in ACTION_TYPE_NAMES.values()}
                )
                per_mode_probe_diagnostics[active_mode] = merge_probe_diagnostics(
                    per_mode_probe_diagnostics.get(active_mode, init_probe_diagnostics()), step_diag
                )

                for n_i in range(n):
                    obs_rows.append(np.asarray(obs[n_i], dtype=np.float32))
                    mask_rows.append(np.asarray(mask_nhwk[n_i], dtype=np.float32))
                    action_rows.append(np.asarray(actions_spatial[n_i], dtype=np.int64))
                    actor_rows.append(np.asarray(actor_valid[n_i], dtype=np.bool_))

                    for y in range(h):
                        for x in range(w):
                            if not bool(actor_valid[n_i, y, x]):
                                continue
                            at = int(actions_spatial[n_i, y, x, 0])
                            key = ACTION_TYPE_NAMES.get(at, f"unknown_{at}")
                            class_hist[key] = int(class_hist.get(key, 0)) + 1
                            per_mode_action_hist[key] = int(per_mode_action_hist.get(key, 0)) + 1

                    samples_collected += 1
                    per_mode_sample_count[active_mode] = int(per_mode_sample_count.get(active_mode, 0)) + 1
                    if samples_collected >= int(args.samples):
                        break

                env_action = to_env_action_shape(actions, env_for_training)
                obs_next, _rew, done_arr, infos = step_compat(env_for_training, env_action)
                done = bool(np.asarray(done_arr).reshape(-1)[0]) if np.asarray(done_arr).size > 0 else False
                obs = np.asarray(obs_next)
                info = infos[0] if infos and isinstance(infos[0], dict) else {}
                steps += 1

            episode_idx += 1

        if not obs_rows:
            raise RuntimeError("No actor-valid samples collected; dataset is empty.")

        total = len(obs_rows)

        obs_np = np.asarray(obs_rows, dtype=np.float32)
        actions_np = np.asarray(action_rows, dtype=np.int64)
        masks_np = np.asarray(mask_rows, dtype=np.float32)
        actor_np = np.asarray(actor_rows, dtype=np.bool_)

        n, h, w, _ = actions_np.shape
        invalid_final = int(validate_action_against_mask(actions_np.reshape(n, h * w, 7), masks_np.reshape(n, h * w, 79)))
        invalid_after_generation_count += invalid_final

        class_presence = class_presence_from_hist(class_hist)
        per_mode_missing_classes: Dict[str, List[str]] = {}
        for name, present in class_presence.items():
            if (not present) and name != "noop":
                warnings.append(f"class_missing:{name}")

        for mode_name, hist in per_mode_action_histogram.items():
            mode_presence = class_presence_from_hist(hist)
            missing = [k for k in ["move", "harvest", "return", "produce", "attack"] if not mode_presence.get(k, False)]
            per_mode_missing_classes[mode_name] = missing
            if len(missing) >= 5:
                warnings.append(f"mode_{mode_name}_no_nonnoop_classes")

        args.output_dataset.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            args.output_dataset,
            obs=obs_np,
            actions=actions_np,
            masks=masks_np,
            actor_valid=actor_np,
        )

        manifest = {
            "schema": "week5_minimal_scripted_dataset_manifest.v1",
            "generated_at_utc": utc_now(),
            "dataset_path": str(args.output_dataset),
            "samples_requested": int(args.samples),
            "samples_collected": int(total),
            "shapes": {
                "obs": [int(v) for v in obs_np.shape],
                "actions": [int(v) for v in actions_np.shape],
                "masks": [int(v) for v in masks_np.shape],
                "actor_valid": [int(v) for v in actor_np.shape],
            },
            "branch_layout": [6, 4, 4, 4, 4, 7, 49],
            "generation_mode": args.generation_mode,
            "action_type_histogram": {k: int(v) for k, v in sorted(class_hist.items())},
            "class_presence": class_presence,
            "per_mode_sample_count": {k: int(v) for k, v in sorted(per_mode_sample_count.items())},
            "per_mode_action_histogram": {
                mode_name: {k: int(v) for k, v in sorted(hist.items())}
                for mode_name, hist in sorted(per_mode_action_histogram.items())
            },
            "per_mode_missing_classes": per_mode_missing_classes,
            "probe_diagnostics_summary": {
                mode_name: {k: int(v) for k, v in sorted(diag.items())}
                for mode_name, diag in sorted(per_mode_probe_diagnostics.items())
            },
            "fallback_counters": {
                "fallback_to_valid_count": int(fallback_to_valid_count),
                "fallback_to_noop_count": int(fallback_to_noop_count),
                "invalid_after_generation_count": int(invalid_after_generation_count),
            },
            "environment": {
                "env_id": args.env_id,
                "map_path": args.map_path,
                "owner_mode": args.owner_mode,
                "opponent_pool": args.opponent_pool,
                "opponent_sampling": args.opponent_sampling,
                "num_bot_envs": int(args.num_bot_envs),
                "seed": int(args.seed),
                "env_summary": env_summary,
                "mask_source": mask_meta.get("mask_source"),
                "mask_source_depth": mask_meta.get("mask_source_depth"),
                "reconstructed_source_channel": bool(mask_meta.get("reconstructed_source_channel", False)),
            },
            "warnings": sorted(set(str(w) for w in warnings if str(w).strip())),
            "errors": errors,
        }
        write_json(args.output_manifest, manifest)

        print(args.output_dataset)
        print(args.output_manifest)
        return 0

    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        fail_manifest = {
            "schema": "week5_minimal_scripted_dataset_manifest.v1",
            "generated_at_utc": utc_now(),
            "dataset_path": str(args.output_dataset),
            "samples_requested": int(args.samples),
            "samples_collected": int(len(obs_rows)),
            "status": "env_error",
            "warnings": sorted(set(str(w) for w in warnings if str(w).strip())),
            "errors": errors,
        }
        write_json(args.output_manifest, fail_manifest)
        print(args.output_manifest)
        return 2

    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
