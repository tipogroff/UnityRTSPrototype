#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

from legacy032_policy_action import (
    BRANCH_NAMES,
    EXPECTED_MAP_PATH,
    assert_legacy032_contract,
    build_policy_from_metadata,
    format_env_action,
    infer_logits,
    load_metadata,
    load_policy_checkpoint_strict,
    read_action_mask,
    select_action_deterministic,
    select_action_stochastic,
    step_env_training_compatible,
    summarize_action_distribution,
)

CLASS_PASS = "STAGE5N_1M_BEHAVIOR_METRICS_PASS"
CLASS_STOCH_PASS_DET_WEAK = "STAGE5N_1M_STOCHASTIC_PASS_DETERMINISTIC_WEAK"
CLASS_PARTIAL = "STAGE5N_1M_PARTIAL_PASS_CONTINUE_TRAINING"
CLASS_PATH_FIXED_POLICY_WEAK = "STAGE5N_1M_ACTION_PATH_FIXED_BUT_POLICY_WEAK"
CLASS_INCONCLUSIVE = "STAGE5N_1M_METRICS_INCONCLUSIVE"
CLASS_FAILED = "STAGE5N_1M_EVAL_FAILED"

ACTION_TYPE_NAMES = {
    0: "noop",
    1: "move",
    2: "harvest",
    3: "return",
    4: "produce",
    5: "attack",
}

SOURCE_VALID_NON_NOOP_TYPES = [1, 2, 3, 4, 5]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (_repo_root() / p).resolve()


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_ai2s(num_bot_envs: int):
    from gym_microrts import microrts_ai

    ai2s = [microrts_ai.coacAI for _ in range(max(0, num_bot_envs - 6))] + [
        microrts_ai.randomBiasedAI for _ in range(min(num_bot_envs, 2))
    ] + [microrts_ai.lightRushAI for _ in range(min(num_bot_envs, 2))] + [
        microrts_ai.workerRushAI for _ in range(min(num_bot_envs, 2))
    ]
    if len(ai2s) < num_bot_envs:
        ai2s += [microrts_ai.coacAI for _ in range(num_bot_envs - len(ai2s))]
    return ai2s[:num_bot_envs]


def _create_env(metadata: Dict[str, Any], max_steps: int):
    from gym_microrts.envs.vec_env import MicroRTSGridModeVecEnv

    md_args = metadata.get("args", {}) if isinstance(metadata.get("args"), dict) else {}
    num_selfplay = int(md_args.get("num_selfplay_envs", 0))
    num_bot = int(md_args.get("num_bot_envs", 6))

    env = MicroRTSGridModeVecEnv(
        num_selfplay_envs=num_selfplay,
        num_bot_envs=num_bot,
        max_steps=int(max_steps),
        render_theme=2,
        ai2s=_build_ai2s(num_bot),
        map_path=EXPECTED_MAP_PATH,
        reward_weight=np.array([10.0, 1.0, 1.0, 0.2, 1.0, 4.0]),
    )
    return env


def _safe_reset(env: Any, seed: int) -> np.ndarray:
    try:
        obs = env.reset(seed=seed)
    except TypeError:
        obs = env.reset()
    if isinstance(obs, tuple):
        obs = obs[0]
    return np.asarray(obs, dtype=np.float32)


def _obs_changed(prev_obs: np.ndarray, next_obs: np.ndarray, env_idx: int = 0) -> bool:
    a = np.asarray(prev_obs)
    b = np.asarray(next_obs)
    if a.shape != b.shape:
        return True
    if a.ndim == 4:
        return bool(np.any(a[env_idx] != b[env_idx]))
    return bool(np.any(a != b))


def _parse_seeds_csv(text: str) -> List[int]:
    vals: List[int] = []
    for token in str(text).split(","):
        token = token.strip()
        if not token:
            continue
        vals.append(int(token))
    return vals


def _parse_raw_rewards(value: Any) -> Optional[List[float]]:
    if value is None:
        return None
    try:
        arr = np.asarray(value, dtype=np.float64).reshape(-1)
    except Exception:
        return None
    if arr.size == 0:
        return None
    return [float(v) for v in arr.tolist()]


def _empty_action_hist() -> Dict[str, int]:
    return {name: 0 for name in ACTION_TYPE_NAMES.values()}


def _update_hist_by_type_index(hist: Dict[str, int], action_types: np.ndarray) -> None:
    for idx, name in ACTION_TYPE_NAMES.items():
        hist[name] += int(np.count_nonzero(action_types == idx))


def _safe_mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return float(np.asarray(values, dtype=np.float64).mean())


def _safe_median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return float(statistics.median(values))


def _safe_min(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return float(min(values))


def _safe_max(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return float(max(values))


def _share(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def _classify_outcome_from_reward(reward: float) -> str:
    if reward > 0.0:
        return "win"
    if reward < 0.0:
        return "loss"
    return "draw"


def _terminal_reason(done_flag: bool, trunc_flag: bool, steps: int, max_steps: int, terminal_info: Dict[str, Any]) -> str:
    for key in ["terminal_reason", "termination_reason", "result", "outcome", "winner"]:
        if key in terminal_info:
            return f"info:{key}={terminal_info[key]}"
    if trunc_flag:
        return "env_truncated"
    if done_flag:
        return "env_done"
    if steps >= max_steps:
        return "max_steps_limit"
    return "unknown"


def _normalize_terminal_info(info_item: Any) -> Dict[str, Any]:
    if isinstance(info_item, dict):
        return dict(info_item)
    return {}


def _sum_raw_reward_vectors(vectors: List[List[float]]) -> Optional[List[float]]:
    if not vectors:
        return None
    max_len = max(len(v) for v in vectors)
    if max_len <= 0:
        return None
    acc = np.zeros((max_len,), dtype=np.float64)
    for vec in vectors:
        arr = np.asarray(vec, dtype=np.float64).reshape(-1)
        acc[: arr.size] += arr
    return [float(v) for v in acc.tolist()]


def _format_hist_shares(hist: Dict[str, int]) -> Dict[str, Optional[float]]:
    total = int(sum(int(v) for v in hist.values()))
    if total <= 0:
        return {k: None for k in hist.keys()}
    return {k: float(v) / float(total) for k, v in hist.items()}


def _evaluate_mode_seed(
    env: Any,
    policy: torch.nn.Module,
    device: torch.device,
    contract: Dict[str, Any],
    mode: str,
    seed: int,
    episodes: int,
    max_steps_per_episode: int,
    step_mode: str,
) -> Dict[str, Any]:
    if step_mode != "training_compatible":
        raise RuntimeError("Stage5N final metrics require training_compatible step mode")

    torch.manual_seed(int(seed))
    np.random.seed(int(seed))
    obs = _safe_reset(env, seed=seed)

    mode_result: Dict[str, Any] = {
        "mode": mode,
        "seed": int(seed),
        "episodes_requested": int(episodes),
        "max_steps_per_episode": int(max_steps_per_episode),
        "episodes": [],
        "env_step_errors": [],
        "mask_source": None,
        "java_payload_used": True,
    }

    episode_idx = 0
    step_global = 0
    while episode_idx < int(episodes):
        ep_reward = 0.0
        ep_steps = 0
        ep_done = False
        ep_obs_changed_steps = 0
        ep_java_payload_count = 0
        ep_raw_rewards: List[List[float]] = []

        ep_all_hist = _empty_action_hist()
        ep_source_hist = _empty_action_hist()
        ep_source_valid_total = 0
        ep_source_valid_non_noop = 0

        first_step_snapshot: Optional[Dict[str, Any]] = None
        terminal_info: Dict[str, Any] = {}
        terminal_done = False
        terminal_trunc = False

        while ep_steps < int(max_steps_per_episode):
            nenv = int(obs.shape[0])
            mask_np, mask_source = read_action_mask(
                env=env,
                num_envs=nenv,
                mapsize=int(contract["mapsize"]),
                mask_dim=int(contract["mask_dim"]),
                require_mask=True,
            )
            if mode_result["mask_source"] is None:
                mode_result["mask_source"] = mask_source

            obs_t = torch.as_tensor(obs, dtype=torch.float32, device=device)
            mask_t = torch.as_tensor(mask_np, dtype=torch.float32, device=device)
            logits = infer_logits(policy, obs_t)

            if mode == "deterministic":
                action_t = select_action_deterministic(
                    logits=logits,
                    nvec=contract["action_space_nvec"],
                    action_mask=mask_t,
                )
            else:
                action_t = select_action_stochastic(
                    logits=logits,
                    nvec=contract["action_space_nvec"],
                    action_mask=mask_t,
                    seed=seed + step_global,
                )

            env_action = format_env_action(action_t)
            step_summary = summarize_action_distribution(env_action, mask_np)

            all_types = env_action[:, :, 0].astype(np.int32, copy=False)
            source_valid_mask = mask_np[:, :, 0] > 0
            source_types = all_types[source_valid_mask]

            _update_hist_by_type_index(ep_all_hist, all_types.reshape(-1))
            _update_hist_by_type_index(ep_source_hist, source_types.reshape(-1))

            ep_source_valid_total += int(source_types.size)
            ep_source_valid_non_noop += int(np.count_nonzero(source_types != 0))

            try:
                step_result, step_debug = step_env_training_compatible(
                    env=env,
                    action_tensor=env_action,
                    action_mask=mask_np,
                    mapsize=int(contract["mapsize"]),
                )
                ep_java_payload_count += 1
            except Exception as exc:
                mode_result["env_step_errors"].append(
                    {
                        "episode_index": int(episode_idx),
                        "step_index": int(ep_steps),
                        "error": str(exc),
                    }
                )
                break

            if first_step_snapshot is None:
                first_step_snapshot = {
                    "mask_source": mask_source,
                    "source_valid_total": int(step_debug.get("source_valid_total", 0)),
                    "source_valid_non_noop_count": int(step_debug.get("source_valid_non_noop_count", 0)),
                    "action_type_histogram_source_valid": step_debug.get("action_type_histogram_source_valid", {}),
                    "valid_actions_counts": [int(v) for v in step_debug.get("valid_actions_counts", [])],
                    "all_cell_action_type_counts": step_summary.get("all_cell_action_type_counts", {}),
                    "source_valid_action_type_counts": step_summary.get("source_valid_action_type_counts", {}),
                }

            if len(step_result) == 4:
                next_obs, rewards, dones, infos = step_result
                truncs = np.zeros_like(dones)
            else:
                next_obs, rewards, dones, truncs, infos = step_result

            rewards_np = np.asarray(rewards)
            dones_np = np.asarray(dones)
            truncs_np = np.asarray(truncs)
            next_obs_np = np.asarray(next_obs, dtype=np.float32)
            infos_list = list(infos) if isinstance(infos, (list, tuple)) else []

            ep_reward += float(rewards_np.reshape(-1)[0])
            ep_steps += 1
            step_global += 1

            if _obs_changed(obs, next_obs_np, env_idx=0):
                ep_obs_changed_steps += 1

            if infos_list:
                info0 = _normalize_terminal_info(infos_list[0])
                rr = _parse_raw_rewards(info0.get("raw_rewards"))
                if rr is not None:
                    ep_raw_rewards.append(rr)

            done0 = bool(dones_np.reshape(-1)[0])
            trunc0 = bool(truncs_np.reshape(-1)[0])
            if done0 or trunc0:
                ep_done = True
                terminal_done = done0
                terminal_trunc = trunc0
                if infos_list:
                    terminal_info = _normalize_terminal_info(infos_list[0])
                break

            obs = next_obs_np

        if ep_steps == 0:
            mode_result["env_step_errors"].append(
                {
                    "episode_index": int(episode_idx),
                    "step_index": 0,
                    "error": "episode_collected_zero_steps",
                }
            )

        raw_sum = _sum_raw_reward_vectors(ep_raw_rewards)
        outcome = _classify_outcome_from_reward(ep_reward)
        terminal_reason = _terminal_reason(
            done_flag=terminal_done,
            trunc_flag=terminal_trunc,
            steps=ep_steps,
            max_steps=int(max_steps_per_episode),
            terminal_info=terminal_info,
        )

        source_non_noop_share = _share(ep_source_valid_non_noop, ep_source_valid_total)
        ep_record: Dict[str, Any] = {
            "mode": mode,
            "seed": int(seed),
            "episode_index": int(episode_idx),
            "steps": int(ep_steps),
            "total_reward": float(ep_reward),
            "done": bool(ep_done),
            "terminal_info_keys": sorted([str(k) for k in terminal_info.keys()]),
            "raw_rewards_sum": raw_sum,
            "outcome": outcome,
            "terminal_reason": terminal_reason,
            "total_obs_changed_steps": int(ep_obs_changed_steps),
            "obs_changed_share": _share(ep_obs_changed_steps, ep_steps),
            "first_step": first_step_snapshot,
            "action_type_counts_all_cells": ep_all_hist,
            "action_type_counts_source_valid": ep_source_hist,
            "source_valid_non_noop_count": int(ep_source_valid_non_noop),
            "source_valid_non_noop_share": source_non_noop_share,
            "source_valid_action_type_shares": _format_hist_shares(ep_source_hist),
            "java_payload_used_count": int(ep_java_payload_count),
            "java_payload_used_share": _share(ep_java_payload_count, ep_steps),
            "env_step_error_count": 0,
            "branch_names": list(BRANCH_NAMES),
        }

        mode_result["episodes"].append(ep_record)
        episode_idx += 1

        obs = _safe_reset(env, seed=seed + episode_idx)

    return mode_result


def _aggregate_mode_seed(result: Dict[str, Any]) -> Dict[str, Any]:
    episodes = list(result.get("episodes", []))

    rewards = [float(ep.get("total_reward", 0.0)) for ep in episodes]
    lengths = [int(ep.get("steps", 0)) for ep in episodes]
    obs_changed_steps = [int(ep.get("total_obs_changed_steps", 0)) for ep in episodes]
    obs_changed_shares = [float(ep.get("obs_changed_share", 0.0) or 0.0) for ep in episodes]
    source_non_noop_shares = [float(ep.get("source_valid_non_noop_share", 0.0) or 0.0) for ep in episodes]

    win_count = int(sum(1 for ep in episodes if ep.get("outcome") == "win"))
    loss_count = int(sum(1 for ep in episodes if ep.get("outcome") == "loss"))
    draw_count = int(sum(1 for ep in episodes if ep.get("outcome") == "draw"))

    terminal_counts: Dict[str, int] = {}
    all_hist = _empty_action_hist()
    source_hist = _empty_action_hist()
    raw_sums: List[List[float]] = []

    for ep in episodes:
        reason = str(ep.get("terminal_reason", "unknown"))
        terminal_counts[reason] = terminal_counts.get(reason, 0) + 1

        all_ep = ep.get("action_type_counts_all_cells", {})
        source_ep = ep.get("action_type_counts_source_valid", {})
        for k in all_hist.keys():
            all_hist[k] += int(all_ep.get(k, 0))
            source_hist[k] += int(source_ep.get(k, 0))

        rr = ep.get("raw_rewards_sum")
        if isinstance(rr, list) and rr:
            raw_sums.append([float(v) for v in rr])

    mean_raw_rewards_components = _sum_raw_reward_vectors(raw_sums)
    if mean_raw_rewards_components is not None and episodes:
        mean_raw_rewards_components = [float(v / max(1, len(raw_sums))) for v in mean_raw_rewards_components]

    source_shares = _format_hist_shares(source_hist)

    aggregate = {
        "mode": result.get("mode"),
        "seed": result.get("seed"),
        "episodes_completed": int(len(episodes)),
        "mean_reward": _safe_mean(rewards),
        "median_reward": _safe_median(rewards),
        "min_reward": _safe_min(rewards),
        "max_reward": _safe_max(rewards),
        "mean_episode_length": _safe_mean([float(v) for v in lengths]),
        "max_episode_length": (max(lengths) if lengths else None),
        "mean_obs_changed_steps": _safe_mean([float(v) for v in obs_changed_steps]),
        "mean_obs_changed_share": _safe_mean(obs_changed_shares),
        "win_count": int(win_count),
        "loss_count": int(loss_count),
        "draw_count": int(draw_count),
        "win_rate": _share(win_count, len(episodes)),
        "mean_source_valid_non_noop_share": _safe_mean(source_non_noop_shares),
        "mean_source_valid_action_type_shares": source_shares,
        "terminal_counts": terminal_counts,
        "mean_raw_rewards_components": mean_raw_rewards_components,
        "action_type_counts_all_cells": all_hist,
        "action_type_counts_source_valid": source_hist,
        "env_step_error_count": int(len(result.get("env_step_errors", []))),
        "mask_source": result.get("mask_source"),
    }
    return aggregate


def _is_strong_outcome(agg: Dict[str, Any]) -> bool:
    mean_reward = float(agg.get("mean_reward") or 0.0)
    win_rate = agg.get("win_rate")
    obs_share = float(agg.get("mean_obs_changed_share") or 0.0)
    non_noop = float(agg.get("mean_source_valid_non_noop_share") or 0.0)
    win_ok = True if win_rate is None else float(win_rate) >= 0.5
    return bool(mean_reward >= 150.0 and win_ok and obs_share >= 0.5 and non_noop >= 0.05)


def _decision_block(aggregates: Dict[str, Dict[str, Any]], eval_status_ok: bool) -> Dict[str, Any]:
    if not eval_status_ok:
        return {
            "classification": CLASS_FAILED,
            "recommendation": "Fix evaluator/runtime before any training or export decision.",
            "comparison": {
                "is_stochastic_better_than_deterministic": None,
                "deterministic_still_weaker_or_stranger": None,
            },
            "answers": {
                "rollout_export_policy": "inconclusive",
                "is_1m_valid_teacher_candidate": False,
                "continue_to_2m_3m_before_bc": True,
                "is_1m_good_enough_to_export_rollouts": False,
                "is_1m_good_enough_to_continue_training": False,
            },
        }

    det = aggregates.get("deterministic_seed17", {})
    st17 = aggregates.get("stochastic_seed17", {})
    st123 = aggregates.get("stochastic_seed123", {})

    det_reward = float(det.get("mean_reward") or 0.0)
    st_rewards = [float(st17.get("mean_reward") or 0.0), float(st123.get("mean_reward") or 0.0)]
    st_reward_mean = float(np.asarray(st_rewards, dtype=np.float64).mean())

    st_strong = _is_strong_outcome(st17) and _is_strong_outcome(st123)
    det_strong = _is_strong_outcome(det)
    det_weaker = bool(det_reward + 20.0 < st_reward_mean)

    st_better = bool(st_reward_mean > det_reward)

    behavior_exists = bool(
        det_reward > 0.0
        or st_reward_mean > 0.0
        or float(det.get("mean_obs_changed_share") or 0.0) > 0.1
        or float(st17.get("mean_obs_changed_share") or 0.0) > 0.1
    )

    if st_strong and det_weaker:
        classification = CLASS_STOCH_PASS_DET_WEAK
        recommendation = (
            "Use stochastic sampling for behavior evidence and rollout export. "
            "Continue to 2M/3M to improve deterministic stability before BC decisions."
        )
        rollout_policy = "stochastic"
        valid_teacher = True
        continue_2m3m = True
        export_ok = True
    elif st_strong and det_strong:
        classification = CLASS_PASS
        recommendation = (
            "1M checkpoint is a valid post-fix teacher candidate. "
            "You may export rollouts now; 2M/3M remains optional for stronger teacher quality."
        )
        rollout_policy = "stochastic_or_deterministic"
        valid_teacher = True
        continue_2m3m = False
        export_ok = True
    elif behavior_exists and (st_better or det_reward > 0.0):
        classification = CLASS_PARTIAL
        recommendation = (
            "Behavior exists but remains inconsistent. Continue training to 2M using fixed training-compatible path, then revalidate."
        )
        rollout_policy = "stochastic"
        valid_teacher = False
        continue_2m3m = True
        export_ok = False
    elif behavior_exists:
        classification = CLASS_PATH_FIXED_POLICY_WEAK
        recommendation = (
            "Action path is fixed, but policy quality is weak. Investigate reward/training recipe or continue training only if trends improve."
        )
        rollout_policy = "do_not_export"
        valid_teacher = False
        continue_2m3m = True
        export_ok = False
    else:
        classification = CLASS_INCONCLUSIVE
        recommendation = "Metrics are inconclusive. Re-run evaluation with diagnostic logging before any export/training decision."
        rollout_policy = "inconclusive"
        valid_teacher = False
        continue_2m3m = True
        export_ok = False

    return {
        "classification": classification,
        "recommendation": recommendation,
        "comparison": {
            "is_stochastic_better_than_deterministic": st_better,
            "deterministic_still_weaker_or_stranger": det_weaker,
            "deterministic_mean_reward": det_reward,
            "stochastic_mean_reward_across_seeds": st_reward_mean,
        },
        "answers": {
            "rollout_export_policy": rollout_policy,
            "is_1m_valid_teacher_candidate": valid_teacher,
            "continue_to_2m_3m_before_bc": continue_2m3m,
            "is_1m_good_enough_to_export_rollouts": export_ok,
            "is_1m_good_enough_to_continue_training": True,
        },
    }


def _build_markdown(report: Dict[str, Any]) -> str:
    strict_load = report.get("strict_load", {})
    contract = report.get("contract", {})
    matrix = report.get("evaluation_matrix", {})
    aggs = report.get("aggregates", {})
    decision = report.get("decision", {})

    lines: List[str] = [
        "# Stage5N Post-Fix Behavior Metrics Revalidation",
        "",
        f"- status: {report.get('status')}",
        f"- timestamp_utc: {report.get('timestamp_utc')}",
        f"- checkpoint_path: {report.get('checkpoint_path')}",
        f"- model_metadata_path: {report.get('model_metadata_path')}",
        f"- step_mode: {report.get('step_mode')}",
        "",
        "## Strict Load",
        "",
        f"- strict_load: {strict_load.get('strict_load')}",
        f"- checkpoint_format: {strict_load.get('checkpoint_format')}",
        f"- strict_load_status: {strict_load.get('strict_load_status')}",
        f"- missing_keys: {strict_load.get('missing_keys')}",
        f"- unexpected_keys: {strict_load.get('unexpected_keys')}",
        "",
        "## Contract",
        "",
        f"- observation_space: {contract.get('observation_space')}",
        f"- action_space_nvec: {contract.get('action_space_nvec')}",
        f"- architecture_name: {contract.get('architecture_name')}",
        f"- map_path: {contract.get('map_path')}",
        f"- mask_source_expected: env.vec_client.getMasks(0)",
        f"- step_mode: {report.get('step_mode')}",
        f"- java_payload_used: {contract.get('java_payload_used')}",
        "",
        "## Evaluation Matrix",
        "",
    ]

    for key, item in matrix.items():
        lines.append(
            f"- {key}: mode={item.get('mode')} seed={item.get('seed')} "
            f"episodes={item.get('episodes_requested')} max_steps={item.get('max_steps_per_episode')}"
        )

    lines.extend([
        "",
        "## Aggregate Metrics",
        "",
    ])

    for key, agg in aggs.items():
        lines.extend(
            [
                f"### {key}",
                "",
                f"- episodes_completed: {agg.get('episodes_completed')}",
                f"- mean_reward: {agg.get('mean_reward')}",
                f"- median_reward: {agg.get('median_reward')}",
                f"- min_reward: {agg.get('min_reward')}",
                f"- max_reward: {agg.get('max_reward')}",
                f"- mean_episode_length: {agg.get('mean_episode_length')}",
                f"- max_episode_length: {agg.get('max_episode_length')}",
                f"- mean_obs_changed_steps: {agg.get('mean_obs_changed_steps')}",
                f"- mean_obs_changed_share: {agg.get('mean_obs_changed_share')}",
                f"- win/loss/draw: {agg.get('win_count')}/{agg.get('loss_count')}/{agg.get('draw_count')}",
                f"- win_rate: {agg.get('win_rate')}",
                f"- mean_source_valid_non_noop_share: {agg.get('mean_source_valid_non_noop_share')}",
                f"- mean_source_valid_action_type_shares: {agg.get('mean_source_valid_action_type_shares')}",
                f"- terminal_counts: {agg.get('terminal_counts')}",
                f"- mean_raw_rewards_components: {agg.get('mean_raw_rewards_components')}",
                f"- env_step_error_count: {agg.get('env_step_error_count')}",
                "",
            ]
        )

    lines.extend(
        [
            "## Deterministic vs Stochastic",
            "",
            f"- is_stochastic_better_than_deterministic: {((decision.get('comparison') or {}).get('is_stochastic_better_than_deterministic'))}",
            f"- deterministic_still_weaker_or_stranger: {((decision.get('comparison') or {}).get('deterministic_still_weaker_or_stranger'))}",
            f"- rollout_export_policy: {((decision.get('answers') or {}).get('rollout_export_policy'))}",
            f"- is_1m_valid_teacher_candidate: {((decision.get('answers') or {}).get('is_1m_valid_teacher_candidate'))}",
            f"- continue_to_2m_3m_before_bc: {((decision.get('answers') or {}).get('continue_to_2m_3m_before_bc'))}",
            "",
            "## Final",
            "",
            f"- classification: {decision.get('classification')}",
            f"- recommendation: {decision.get('recommendation')}",
            "",
        ]
    )

    if report.get("errors"):
        lines.append("## Errors")
        lines.append("")
        for err in report.get("errors", []):
            lines.append(f"- {err}")

    return "\n".join(lines).strip() + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage5N post-fix behavior revalidation for Legacy032 1M teacher")
    p.add_argument(
        "--checkpoint-path",
        default=(
            "python/week5_teacher_legacy032/teacher_models/"
            "legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/agent_final.pt"
        ),
    )
    p.add_argument(
        "--model-metadata-path",
        default=(
            "python/week5_teacher_legacy032/teacher_models/"
            "legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/model_metadata.json"
        ),
    )
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    p.add_argument("--episodes", type=int, default=8)
    p.add_argument("--max-steps-per-episode", type=int, default=6000)
    p.add_argument("--seeds", default="17,123")
    p.add_argument("--include-deterministic", action="store_true", default=False)
    p.add_argument("--include-stochastic", action="store_true", default=False)
    p.add_argument("--step-mode", choices=["raw", "training_compatible"], default="training_compatible")
    p.add_argument("--strict-load", action="store_true", default=False)
    p.add_argument("--output-dir", default="python/week5_teacher_legacy032/reports")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    checkpoint_path = _resolve(args.checkpoint_path)
    metadata_path = _resolve(args.model_metadata_path)
    output_dir = _resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = _now_ts()
    json_path = output_dir / f"stage5n_postfix_behavior_revalidation_{ts}.json"
    md_path = output_dir / f"stage5n_postfix_behavior_revalidation_{ts}.md"
    canonical_md_path = output_dir / "STAGE5N_POSTFIX_BEHAVIOR_REVALIDATION_REPORT.md"

    report: Dict[str, Any] = {
        "timestamp_utc": _now_iso(),
        "status": "RUNNING",
        "checkpoint_path": str(checkpoint_path),
        "model_metadata_path": str(metadata_path),
        "step_mode": str(args.step_mode),
        "strict_load": {},
        "contract": {},
        "evaluation_matrix": {},
        "aggregates": {},
        "decision": {},
        "warnings": [],
        "errors": [],
    }

    env = None
    try:
        if args.step_mode != "training_compatible":
            raise RuntimeError("Stage5N final evidence must use --step-mode training_compatible")

        if not args.include_deterministic and not args.include_stochastic:
            report["warnings"].append("Neither deterministic nor stochastic explicitly selected; defaulting to both.")
            args.include_deterministic = True
            args.include_stochastic = True

        metadata = load_metadata(metadata_path)
        contract = assert_legacy032_contract(metadata)

        device = torch.device("cuda" if args.device == "cuda" and torch.cuda.is_available() else "cpu")
        policy, build_report = build_policy_from_metadata(metadata=metadata, device=device)
        load_report = load_policy_checkpoint_strict(
            policy=policy,
            checkpoint_path=checkpoint_path,
            device=device,
            strict=bool(args.strict_load),
        )
        policy.eval()

        report["strict_load"] = {
            "strict_load": bool(args.strict_load),
            "checkpoint_format": load_report.get("checkpoint_format"),
            "strict_load_status": load_report.get("strict_load_status"),
            "missing_keys": load_report.get("missing_keys", []),
            "unexpected_keys": load_report.get("unexpected_keys", []),
            "allowed_unexpected_keys_policy": "critic.* may be ignored by loader before reporting",
        }
        report["contract"] = {
            "observation_space": contract.get("observation_space"),
            "action_space_nvec": contract.get("action_space_nvec"),
            "architecture_name": contract.get("architecture_name"),
            "map_path": contract.get("map_path"),
            "mask_source": "env.vec_client.getMasks(0)",
            "step_mode": args.step_mode,
            "java_payload_used": True,
            "build_report": build_report,
        }

        eval_specs: List[Tuple[str, str, int]] = []
        seed_list = _parse_seeds_csv(args.seeds)
        if args.include_deterministic:
            eval_specs.append(("deterministic_seed17", "deterministic", 17))
        if args.include_stochastic:
            for seed in seed_list:
                eval_specs.append((f"stochastic_seed{seed}", "stochastic", int(seed)))

        env = _create_env(metadata=metadata, max_steps=int(args.max_steps_per_episode))

        for eval_id, mode, seed in eval_specs:
            mode_seed_result = _evaluate_mode_seed(
                env=env,
                policy=policy,
                device=device,
                contract=contract,
                mode=mode,
                seed=seed,
                episodes=int(args.episodes),
                max_steps_per_episode=int(args.max_steps_per_episode),
                step_mode=str(args.step_mode),
            )
            report["evaluation_matrix"][eval_id] = mode_seed_result
            report["aggregates"][eval_id] = _aggregate_mode_seed(mode_seed_result)

        eval_ok = True
        for agg in report["aggregates"].values():
            if int(agg.get("episodes_completed", 0)) < int(args.episodes):
                eval_ok = False
            if int(agg.get("env_step_error_count", 0)) > 0:
                eval_ok = False

        report["decision"] = _decision_block(report["aggregates"], eval_status_ok=eval_ok)
        report["status"] = "OK" if eval_ok else "PARTIAL"

    except Exception as exc:
        report["status"] = "ERROR"
        report["errors"].append(str(exc))
        report["decision"] = _decision_block({}, eval_status_ok=False)

    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    md_text = _build_markdown(report)
    md_path.write_text(md_text, encoding="utf-8")
    canonical_md_path.write_text(md_text, encoding="utf-8")

    print(str(json_path))
    print(str(md_path))
    print(str(canonical_md_path))

    return 0 if report.get("status") in {"OK", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
