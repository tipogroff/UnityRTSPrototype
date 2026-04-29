#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from reward_audit_utils import (
    ALL_POLICY_MODES,
    ACTION_TYPE_NAMES,
    DEFAULT_ENV_ID,
    DEFAULT_MAP_PATH,
    DEFAULT_OUTPUT_DIR,
    build_noop_action,
    build_policy_action,
    build_random_valid_action,
    collect_action_histograms,
    flatten_mask,
    flatten_obs,
    init_probe_diagnostics,
    info_invalid_action_count,
    info_terminal_flag,
    info_timeout_flag,
    make_env_and_reset,
    reset_compat,
    step_compat,
    to_env_action_shape,
    utc_now,
    validate_action_against_mask,
    write_md,
    write_json,
)
from mask_audit_utils import build_full_mask_from_candidates


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run reward sanity gate audit for Week5 teacher-side env.")
    p.add_argument("--env-id", default=DEFAULT_ENV_ID)
    p.add_argument("--map-path", default=DEFAULT_MAP_PATH)
    p.add_argument("--episodes", type=int, default=4)
    p.add_argument("--step-limit", type=int, default=500)
    p.add_argument("--seed", type=int, default=170)
    p.add_argument("--opponent-pool", default="passiveAI")
    p.add_argument("--opponent-sampling", choices=("static", "per_reset", "per_episode"), default="static")
    p.add_argument("--num-bot-envs", type=int, default=1)
    p.add_argument("--policy-mode", choices=ALL_POLICY_MODES, required=True)
    p.add_argument("--owner-mode", choices=("player1", "relative", "mask_only"), default="mask_only")
    p.add_argument("--device", default="cpu")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return p.parse_args()


def _new_episode(policy_mode: str, idx: int) -> Dict[str, Any]:
    return {
        "episode_index": idx,
        "policy_mode": policy_mode,
        "episode_return": 0.0,
        "reward_sum": 0.0,
        "reward_nonzero_steps": 0,
        "reward_min": None,
        "reward_max": None,
        "steps": 0,
        "done": False,
        "terminal": False,
        "timeout": False,
        "invalid_action_attempts": 0,
        "action_type_histogram": {},
        "produce_unit_type_histogram": {},
        "attack_target_histogram": {},
        "probe_diagnostics": init_probe_diagnostics(),
    }


def _merge_hist(dst: Dict[str, int], src: Dict[str, int]) -> None:
    for k, v in src.items():
        dst[k] = int(dst.get(k, 0)) + int(v)


def run_mode(args: argparse.Namespace) -> Dict[str, Any]:
    warnings: List[str] = []
    errors: List[str] = []
    episodes: List[Dict[str, Any]] = []

    env = None
    env_for_training = None
    ctx = None
    try:
        ctx, env, env_for_training, env_summary, obs, info, mask_meta, init_warnings = make_env_and_reset(args)
        warnings.extend(init_warnings)

        rng = np.random.default_rng(int(args.seed) + 919)
        reward_global_min = None
        reward_global_max = None
        mode_hist = {
            "action_type": {},
            "produce_unit_type": {},
            "attack_target": {},
        }
        mode_probe_diag = init_probe_diagnostics()

        done_count = 0
        terminal_count = 0
        timeout_count = 0

        for ep in range(int(args.episodes)):
            if ep > 0:
                obs, info = reset_compat(env_for_training)

            ep_stats = _new_episode(args.policy_mode, ep)

            for _ in range(int(args.step_limit)):
                mask_nhwk, mask_source, mask_warnings = build_full_mask_from_candidates(env_for_training, obs, infos=[info])
                warnings.extend(mask_warnings)
                if mask_nhwk is None:
                    raise RuntimeError("Mask disappeared during rollout; cannot continue reward sanity audit.")
                mask_flat = flatten_mask(mask_nhwk)
                obs_flat = flatten_obs(obs)

                if args.policy_mode == "noop":
                    action = build_noop_action(mask_flat)
                elif args.policy_mode == "random_valid":
                    action = build_random_valid_action(mask_flat, rng)
                else:
                    action = build_policy_action(
                        args.policy_mode,
                        obs_flat,
                        mask_flat,
                        warnings,
                        owner_mode=args.owner_mode,
                        diagnostics=ep_stats["probe_diagnostics"],
                    )

                invalid_local = validate_action_against_mask(action, mask_flat)
                ep_stats["invalid_action_attempts"] += int(invalid_local)

                hist = collect_action_histograms(action, mask_flat)
                _merge_hist(ep_stats["action_type_histogram"], hist.get("action_type", {}))
                _merge_hist(ep_stats["produce_unit_type_histogram"], hist.get("produce_unit_type", {}))
                _merge_hist(ep_stats["attack_target_histogram"], hist.get("attack_target", {}))

                _merge_hist(mode_hist["action_type"], hist.get("action_type", {}))
                _merge_hist(mode_hist["produce_unit_type"], hist.get("produce_unit_type", {}))
                _merge_hist(mode_hist["attack_target"], hist.get("attack_target", {}))

                env_action = to_env_action_shape(action, env_for_training)
                obs_next, rew, done, infos = step_compat(env_for_training, env_action)

                rew_val = float(np.asarray(rew).reshape(-1)[0]) if np.asarray(rew).size > 0 else 0.0
                done_flag = bool(np.asarray(done).reshape(-1)[0]) if np.asarray(done).size > 0 else False
                info0 = infos[0] if infos and isinstance(infos[0], dict) else {}

                ep_stats["steps"] += 1
                ep_stats["episode_return"] += rew_val
                ep_stats["reward_sum"] += rew_val
                if abs(rew_val) > 1e-12:
                    ep_stats["reward_nonzero_steps"] += 1
                if ep_stats["reward_min"] is None or rew_val < float(ep_stats["reward_min"]):
                    ep_stats["reward_min"] = rew_val
                if ep_stats["reward_max"] is None or rew_val > float(ep_stats["reward_max"]):
                    ep_stats["reward_max"] = rew_val

                reward_global_min = rew_val if reward_global_min is None else min(float(reward_global_min), rew_val)
                reward_global_max = rew_val if reward_global_max is None else max(float(reward_global_max), rew_val)

                ep_stats["invalid_action_attempts"] += int(info_invalid_action_count(info0))

                terminal_flag = bool(info_terminal_flag(info0))
                timeout_flag = bool(info_timeout_flag(info0))
                if done_flag:
                    ep_stats["done"] = True
                    done_count += 1
                if terminal_flag:
                    ep_stats["terminal"] = True
                    terminal_count += 1
                if timeout_flag:
                    ep_stats["timeout"] = True
                    timeout_count += 1

                obs = np.asarray(obs_next)
                info = info0

                if done_flag:
                    break

            for k, v in ep_stats["probe_diagnostics"].items():
                mode_probe_diag[k] = int(mode_probe_diag.get(k, 0)) + int(v)
            episodes.append(ep_stats)

        if args.policy_mode == "combat_probe" and int(mode_probe_diag.get("attack_chosen_count", 0)) <= 0:
            mode_probe_diag["no_attack_window_reached_count"] = int(
                mode_probe_diag.get("no_attack_window_reached_count", 0)
            ) + 1

        reward_nonzero_total = int(sum(int(x.get("reward_nonzero_steps", 0)) for x in episodes))
        reward_total = float(sum(float(x.get("reward_sum", 0.0)) for x in episodes))
        invalid_total = int(sum(int(x.get("invalid_action_attempts", 0)) for x in episodes))

        payload = {
            "schema": "week5_reward_sanity_raw.v1",
            "generated_at_utc": utc_now(),
            "status": "ok",
            "policy_mode": args.policy_mode,
            "environment": {
                "env_id": args.env_id,
                "map_path": args.map_path,
                "owner_mode": args.owner_mode,
                "opponent_pool": args.opponent_pool,
                "opponent_sampling": args.opponent_sampling,
                "num_bot_envs": int(args.num_bot_envs),
                "device": args.device,
                "seed": int(args.seed),
                "env_summary": env_summary,
                "observation_shape": list(np.asarray(obs).shape),
                "mask_shape": mask_meta.get("mask_shape"),
                "mask_source": mask_source,
                "mask_source_depth": mask_meta.get("mask_source_depth"),
                "reconstructed_source_channel": bool(mask_meta.get("reconstructed_source_channel", False)),
            },
            "episodes": episodes,
            "summary": {
                "reward_total": reward_total,
                "reward_nonzero_steps": reward_nonzero_total,
                "reward_min": reward_global_min,
                "reward_max": reward_global_max,
                "done_count": int(done_count),
                "terminal_count": int(terminal_count),
                "timeout_count": int(timeout_count),
                "invalid_action_attempts": invalid_total,
                "action_histogram": mode_hist,
                "probe_diagnostics": mode_probe_diag,
            },
            "runtime_versions": {
                "python_version": getattr(ctx.versions, "python_version", None),
                "torch_version": getattr(ctx.versions, "torch_version", None),
                "numpy_version": getattr(ctx.versions, "numpy_version", None),
                "gym_api_name": getattr(ctx.versions, "gym_api_name", None),
                "gym_api_version": getattr(ctx.versions, "gym_api_version", None),
                "microrts_module_name": getattr(ctx.versions, "microrts_module_name", None),
                "microrts_version": getattr(ctx.versions, "microrts_version", None),
            },
            "warnings": sorted(set(str(w) for w in warnings if str(w).strip())),
            "errors": errors,
        }
        return payload

    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        return {
            "schema": "week5_reward_sanity_raw.v1",
            "generated_at_utc": utc_now(),
            "status": "env_error",
            "policy_mode": args.policy_mode,
            "environment": {
                "env_id": args.env_id,
                "map_path": args.map_path,
                "owner_mode": args.owner_mode,
                "opponent_pool": args.opponent_pool,
                "opponent_sampling": args.opponent_sampling,
                "num_bot_envs": int(args.num_bot_envs),
                "device": args.device,
                "seed": int(args.seed),
            },
            "episodes": episodes,
            "summary": {
                "reward_total": 0.0,
                "reward_nonzero_steps": 0,
                "reward_min": None,
                "reward_max": None,
                "done_count": 0,
                "terminal_count": 0,
                "timeout_count": 0,
                "invalid_action_attempts": 0,
                "action_histogram": {
                    "action_type": {},
                    "produce_unit_type": {},
                    "attack_target": {},
                },
            },
            "warnings": sorted(set(str(w) for w in warnings if str(w).strip())),
            "errors": errors,
        }
    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass


def decision_from_raw(payload: Dict[str, Any]) -> str:
    if payload.get("status") != "ok":
        return "FAIL_REWARD_ENV_ERROR"

    summary = payload.get("summary", {})
    reward_nonzero = int(summary.get("reward_nonzero_steps", 0))
    reward_total = float(summary.get("reward_total", 0.0))
    invalid_actions = int(summary.get("invalid_action_attempts", 0))
    done_count = int(summary.get("done_count", 0))
    terminal_count = int(summary.get("terminal_count", 0))

    if reward_nonzero <= 0 and abs(reward_total) <= 1e-12:
        return "FAIL_REWARD_ALL_ZERO"

    if invalid_actions > 0:
        return "PARTIAL_PASS_REWARD_SANITY"

    if done_count <= 0 and terminal_count <= 0:
        return "PARTIAL_PASS_REWARD_SANITY"

    return "PASS_REWARD_SANITY"


def main() -> int:
    args = parse_args()
    args.rollout_step_limit = int(args.step_limit)

    raw = run_mode(args)
    mode_decision = decision_from_raw(raw)

    out_raw = args.output_dir / "REWARD_SANITY_RAW.json"
    out_report = args.output_dir / "REWARD_SANITY_REPORT.json"

    existing_raw = None
    if out_raw.is_file():
        try:
            existing_raw = __import__("json").loads(out_raw.read_text(encoding="utf-8"))
        except Exception:
            existing_raw = None

    runs_by_mode: Dict[str, Any] = {}
    if isinstance(existing_raw, dict) and isinstance(existing_raw.get("runs_by_mode"), dict):
        runs_by_mode = dict(existing_raw.get("runs_by_mode", {}))
    runs_by_mode[str(args.policy_mode)] = raw

    aggregated_raw = {
        "schema": "week5_reward_sanity_raw_collection.v1",
        "generated_at_utc": utc_now(),
        "runs_by_mode": runs_by_mode,
        "latest_mode": args.policy_mode,
        "latest_mode_decision": mode_decision,
    }

    noop_run = runs_by_mode.get("noop", {}) if isinstance(runs_by_mode.get("noop", {}), dict) else {}
    random_run = runs_by_mode.get("random_valid", {}) if isinstance(runs_by_mode.get("random_valid", {}), dict) else {}

    probe_mode_names = [
        "scripted_probe",
        "economy_probe",
        "production_probe",
        "combat_probe",
        "mixed_probe",
    ]
    probe_runs = {
        m: runs_by_mode.get(m, {}) for m in probe_mode_names if isinstance(runs_by_mode.get(m, {}), dict)
    }

    def _sum_reward(run: Dict[str, Any]) -> float:
        return float((run.get("summary") or {}).get("reward_total", 0.0))

    def _nonzero_steps(run: Dict[str, Any]) -> int:
        return int((run.get("summary") or {}).get("reward_nonzero_steps", 0))

    def _status(run: Dict[str, Any]) -> str:
        return str(run.get("status", "missing"))

    scripted_run = probe_runs.get("scripted_probe", {})
    scripted_better_than_noop = _sum_reward(scripted_run) != _sum_reward(noop_run)
    random_better_than_noop = _sum_reward(random_run) != _sum_reward(noop_run)
    probe_nonzero = sum(_nonzero_steps(r) for r in probe_runs.values())
    probe_differ_from_noop = any(_sum_reward(r) != _sum_reward(noop_run) for r in probe_runs.values())
    nonnoop_any_nonzero = probe_nonzero > 0 or (_nonzero_steps(random_run) > 0)
    env_error_any = any(_status(r) == "env_error" for r in [noop_run, random_run, *probe_runs.values()] if r)
    missing_modes = [m for m in ["noop", "random_valid"] if m not in runs_by_mode]

    if env_error_any:
        final_decision = "FAIL_REWARD_ENV_ERROR"
    elif nonnoop_any_nonzero or scripted_better_than_noop or random_better_than_noop or probe_differ_from_noop:
        invalid_total = 0
        for run in [noop_run, random_run, *probe_runs.values()]:
            if not run:
                continue
            invalid_total += int((run.get("summary") or {}).get("invalid_action_attempts", 0))
        if invalid_total > 0:
            final_decision = "PARTIAL_PASS_REWARD_SANITY"
        else:
            final_decision = "PASS_REWARD_SANITY"
    elif missing_modes:
        final_decision = "INCONCLUSIVE_NEEDS_MANUAL_CHECK"
    else:
        final_decision = "FAIL_REWARD_ALL_ZERO"

    report = {
        "schema": "week5_reward_sanity_report.v1",
        "generated_at_utc": utc_now(),
        "decision": final_decision,
        "latest_mode": args.policy_mode,
        "latest_mode_decision": mode_decision,
        "modes_present": sorted(list(runs_by_mode.keys())),
        "missing_modes_for_strict_compare": missing_modes,
        "comparisons": {
            "scripted_reward_total": _sum_reward(scripted_run),
            "random_reward_total": _sum_reward(random_run),
            "noop_reward_total": _sum_reward(noop_run),
            "scripted_vs_noop_differs": bool(scripted_better_than_noop),
            "random_vs_noop_differs": bool(random_better_than_noop),
            "probe_vs_noop_differs": bool(probe_differ_from_noop),
            "nonnoop_reward_nonzero_steps": int(probe_nonzero + _nonzero_steps(random_run)),
        },
        "runs_by_mode_summary": {
            mode: {
                "status": (payload.get("status") if isinstance(payload, dict) else "missing"),
                "reward_total": float(((payload.get("summary") or {}).get("reward_total", 0.0)) if isinstance(payload, dict) else 0.0),
                "reward_nonzero_steps": int(((payload.get("summary") or {}).get("reward_nonzero_steps", 0)) if isinstance(payload, dict) else 0),
                "done_count": int(((payload.get("summary") or {}).get("done_count", 0)) if isinstance(payload, dict) else 0),
                "terminal_count": int(((payload.get("summary") or {}).get("terminal_count", 0)) if isinstance(payload, dict) else 0),
                "timeout_count": int(((payload.get("summary") or {}).get("timeout_count", 0)) if isinstance(payload, dict) else 0),
                "invalid_action_attempts": int(((payload.get("summary") or {}).get("invalid_action_attempts", 0)) if isinstance(payload, dict) else 0),
            }
            for mode, payload in sorted(runs_by_mode.items())
        },
        "probe_diagnostics_by_mode": {
            mode: dict((payload.get("summary") or {}).get("probe_diagnostics", {}))
            for mode, payload in sorted(runs_by_mode.items())
        },
        "warnings": sorted(
            {
                str(w)
                for payload in runs_by_mode.values()
                if isinstance(payload, dict)
                for w in (payload.get("warnings") or [])
                if str(w).strip()
            }
        ),
        "errors": [
            {
                "mode": mode,
                "errors": list(payload.get("errors", [])) if isinstance(payload, dict) else ["missing payload"],
            }
            for mode, payload in sorted(runs_by_mode.items())
            if (isinstance(payload, dict) and payload.get("errors")) or (not isinstance(payload, dict))
        ],
        "pass_criteria": {
            "reward_nonzero_or_non_noop_diff_required": True,
            "not_all_zero_required": True,
            "terminal_or_done_or_explained": True,
            "no_systematic_invalid_actions": True,
        },
    }

    md_lines = [
        "# REWARD_SANITY_REPORT",
        "",
        f"- Decision: {report['decision']}",
        f"- Latest mode: {report['latest_mode']} ({report['latest_mode_decision']})",
        f"- Modes present: {', '.join(report['modes_present']) if report['modes_present'] else 'none'}",
        f"- Missing modes for strict compare: {', '.join(missing_modes) if missing_modes else 'none'}",
        "",
        "## Mode Summary",
    ]
    for mode, summary in sorted(report["runs_by_mode_summary"].items()):
        md_lines.append(
            f"- {mode}: status={summary['status']}, reward_total={summary['reward_total']:.6f}, "
            f"reward_nonzero_steps={summary['reward_nonzero_steps']}, done={summary['done_count']}, "
            f"terminal={summary['terminal_count']}, timeout={summary['timeout_count']}, "
            f"invalid_action_attempts={summary['invalid_action_attempts']}"
        )

    md_lines.extend(
        [
            "",
            "## Key Comparisons",
            f"- scripted_vs_noop_differs: {report['comparisons']['scripted_vs_noop_differs']}",
            f"- random_vs_noop_differs: {report['comparisons']['random_vs_noop_differs']}",
            f"- probe_vs_noop_differs: {report['comparisons']['probe_vs_noop_differs']}",
            f"- nonnoop_reward_nonzero_steps: {report['comparisons']['nonnoop_reward_nonzero_steps']}",
            "",
            "## Caveats",
            "- Current env may expose 78-channel mask tail; source channel can be reconstructed from action_type validity to build full 79-channel view.",
            "- PASS here means reward sanity gate only, not teacher-ready and not Unity-ready.",
        ]
    )
    if report["warnings"]:
        md_lines.append("")
        md_lines.append("## Warnings")
        for w in report["warnings"]:
            md_lines.append(f"- {w}")

    write_json(out_raw, aggregated_raw)
    write_json(out_report, report)
    write_md(args.output_dir / "REWARD_SANITY_REPORT.md", md_lines)

    print(out_raw)
    print(out_report)
    return 0 if final_decision.startswith("PASS") or final_decision.startswith("PARTIAL_PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
