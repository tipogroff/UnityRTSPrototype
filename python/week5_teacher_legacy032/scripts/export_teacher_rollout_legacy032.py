from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import torch

from legacy032_policy_action import (
    BRANCH_SIZES,
    EXPECTED_ARCHITECTURE,
    EXPECTED_MAP_PATH,
    EXPECTED_OBS_SHAPE,
    EXPECTED_RAW_ACTION_NVEC,
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
    validate_required_branch_parameters,
)


DEFAULT_CHECKPOINT_PATH = (
    "python/week5_teacher_legacy032/teacher_models/"
    "legacy032_24x24_teacher_resume_3m_from_1m_postfix/agent_final.pt"
)
DEFAULT_MODEL_METADATA_PATH = (
    "python/week5_teacher_legacy032/teacher_models/"
    "legacy032_24x24_teacher_resume_3m_from_1m_postfix/model_metadata.json"
)
DEFAULT_TRAINER_STATE_PATH = (
    "python/week5_teacher_legacy032/teacher_models/"
    "legacy032_24x24_teacher_resume_3m_from_1m_postfix/trainer_state_final.pt"
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (_repo_root() / p).resolve()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_bool(value: str) -> bool:
    v = str(value).strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


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


def _create_env(max_steps: int, map_path: str, num_bot_envs: int):
    from gym_microrts.envs.vec_env import MicroRTSGridModeVecEnv

    env = MicroRTSGridModeVecEnv(
        num_selfplay_envs=0,
        num_bot_envs=int(num_bot_envs),
        max_steps=int(max_steps),
        render_theme=2,
        ai2s=_build_ai2s(int(num_bot_envs)),
        map_path=str(map_path),
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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Export Legacy032 teacher rollout in adapter-compatible raw schema. "
            "Final evidence path uses training-compatible stepping; raw stepping is diagnostic only."
        )
    )
    p.add_argument("--checkpoint-path", default=DEFAULT_CHECKPOINT_PATH)
    p.add_argument("--model-metadata-path", default=DEFAULT_MODEL_METADATA_PATH)
    p.add_argument("--trainer-state-path", default=DEFAULT_TRAINER_STATE_PATH)
    p.add_argument("--map-path", default=EXPECTED_MAP_PATH)
    p.add_argument("--episodes", type=int, default=16)
    p.add_argument("--max-steps-per-episode", type=int, default=6000)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    p.add_argument("--output-root", default="python/week5_teacher_legacy032/teacher_rollouts")
    p.add_argument("--output-dir", default=None)
    p.add_argument("--run-label", default=None)
    p.add_argument("--export-mode", choices=["deterministic", "stochastic", "both"], default="stochastic")
    p.add_argument("--require-mask", type=_parse_bool, default=True)
    p.add_argument("--strict-load", action="store_true", default=True)
    p.add_argument("--no-strict-load", dest="strict_load", action="store_false")
    p.add_argument("--num-bot-envs", type=int, default=1)
    p.add_argument("--step-mode", choices=["raw", "training_compatible"], default="training_compatible")
    return p.parse_args()


def _choose_action(
    export_mode: str,
    logits: torch.Tensor,
    action_mask: torch.Tensor,
    nvec: List[int],
) -> torch.Tensor:
    if export_mode == "deterministic":
        return select_action_deterministic(logits=logits, nvec=nvec, action_mask=action_mask)
    return select_action_stochastic(logits=logits, nvec=nvec, action_mask=action_mask, seed=None)


def _run_single_mode(
    args: argparse.Namespace,
    export_mode: str,
    checkpoint_path: Path,
    metadata_path: Path,
    trainer_state_path: Path | None,
    output_root: Path,
) -> Tuple[int, Path, Path]:
    metadata = load_metadata(metadata_path)
    contract = assert_legacy032_contract(metadata)
    if str(args.map_path).strip() != EXPECTED_MAP_PATH:
        raise RuntimeError(f"map path mismatch: expected={EXPECTED_MAP_PATH}, actual={args.map_path}")

    if int(args.num_bot_envs) <= 0:
        raise RuntimeError("--num-bot-envs must be > 0")

    run_label = str(args.run_label).strip() if args.run_label else f"legacy032_export_{export_mode}"
    run_dir = output_root / f"{run_label}_{_now()}"
    run_dir.mkdir(parents=True, exist_ok=False)

    rollout_npz = run_dir / "teacher_rollout_raw.npz"
    manifest_json = run_dir / "teacher_rollout_manifest.json"
    summary_json = run_dir / "teacher_rollout_summary.json"

    device = torch.device("cuda" if args.device == "cuda" and torch.cuda.is_available() else "cpu")
    torch.manual_seed(int(args.seed))
    np.random.seed(int(args.seed))

    policy, build_report = build_policy_from_metadata(metadata=metadata, device=device)
    load_report = load_policy_checkpoint_strict(
        policy=policy,
        checkpoint_path=checkpoint_path,
        device=device,
        strict=bool(args.strict_load),
    )
    policy.eval()

    env = None
    observation_t: List[np.ndarray] = []
    per_cell_action_t: List[np.ndarray] = []
    episode_id: List[int] = []
    step_id: List[int] = []
    reward_t: List[float] = []
    done_t: List[bool] = []
    terminated_t: List[bool] = []
    truncated_t: List[bool] = []
    action_mask_available_t: List[bool] = []
    source_valid_action_mask_t: List[np.ndarray] = []
    source_valid_action_count_t: List[int] = []
    selected_non_noop_count_t: List[int] = []
    source_valid_non_noop_count_t: List[int] = []
    mask_source_valid_count_t: List[int] = []
    episode_returns: List[float] = []
    first_step_debug: Dict[str, Any] | None = None

    try:
        env = _create_env(
            max_steps=int(args.max_steps_per_episode),
            map_path=str(args.map_path),
            num_bot_envs=int(args.num_bot_envs),
        )

        mapsize = int(contract["mapsize"])
        mask_dim = int(contract["mask_dim"])

        for ep in range(int(args.episodes)):
            obs = _safe_reset(env, seed=int(args.seed) + ep)
            ep_return = 0.0

            for st in range(int(args.max_steps_per_episode)):
                nenv = int(obs.shape[0])
                mask_np, mask_source = read_action_mask(
                    env,
                    nenv,
                    mapsize,
                    mask_dim,
                    require_mask=bool(args.require_mask),
                )
                mask_available = str(mask_source) != "fallback_ones_mask"

                obs_t = torch.as_tensor(obs, dtype=torch.float32, device=device)
                mask_t = torch.as_tensor(mask_np, dtype=torch.float32, device=device)
                logits = infer_logits(policy, obs_t)
                action_t = _choose_action(export_mode=export_mode, logits=logits, action_mask=mask_t, nvec=contract["action_space_nvec"])
                env_action = format_env_action(action_t)

                if first_step_debug is None:
                    summary = summarize_action_distribution(env_action, mask=mask_np)
                    validity = validate_required_branch_parameters(env_action, mask_np)
                    first_step_debug = {
                        "mask_source": mask_source,
                        "action_distribution": summary,
                        "effective_noop_candidate_count": int(validity["effective_noop_candidate_count"]),
                    }

                if args.step_mode == "training_compatible":
                    step_result, step_debug = step_env_training_compatible(
                        env=env,
                        action_tensor=env_action,
                        action_mask=mask_np,
                        mapsize=mapsize,
                    )
                    sv_count = int(step_debug.get("source_valid_total", 0))
                    sv_non_noop = int(step_debug.get("source_valid_non_noop_count", 0))
                else:
                    # Raw path remains diagnostic only and must not be used as final evidence.
                    step_result = env.step(env_action)
                    source_valid = (mask_np[:, :, 0] > 0)
                    sv_count = int(np.count_nonzero(source_valid[0]))
                    action_types = env_action[0, :, 0]
                    sv_non_noop = int(np.count_nonzero(action_types[source_valid[0]] != 0)) if sv_count > 0 else 0

                if len(step_result) == 4:
                    next_obs, rewards, dones, _infos = step_result
                    truncs = np.zeros_like(dones)
                else:
                    next_obs, rewards, dones, truncs, _infos = step_result

                reward_value = float(np.asarray(rewards).reshape(-1)[0])
                terminated_flag = bool(np.asarray(dones).reshape(-1)[0])
                truncated_flag = bool(np.asarray(truncs).reshape(-1)[0])
                done_flag = bool(terminated_flag or truncated_flag)

                selected_non_noop = int(np.count_nonzero(env_action[0, :, 0] != 0))
                mask_source_valid = int(np.count_nonzero(mask_np[0, :, 0] > 0))
                source_valid_mask = np.asarray(mask_np[0, :, 0] > 0, dtype=np.bool_)
                supervised_action = env_action[0].copy()
                supervised_action[~source_valid_mask, :] = 0

                observation_t.append(np.asarray(obs, dtype=np.float32)[0])
                per_cell_action_t.append(supervised_action.astype(np.int16, copy=False))
                episode_id.append(int(ep))
                step_id.append(int(st))
                reward_t.append(reward_value)
                done_t.append(done_flag)
                terminated_t.append(terminated_flag)
                truncated_t.append(truncated_flag)
                action_mask_available_t.append(bool(mask_available))
                source_valid_action_mask_t.append(source_valid_mask)
                source_valid_action_count_t.append(int(sv_count))
                selected_non_noop_count_t.append(int(selected_non_noop))
                source_valid_non_noop_count_t.append(int(sv_non_noop))
                mask_source_valid_count_t.append(int(mask_source_valid))

                ep_return += reward_value

                if done_flag:
                    break

                obs = np.asarray(next_obs, dtype=np.float32)

            episode_returns.append(float(ep_return))

    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass

    obs_arr = np.asarray(observation_t, dtype=np.float32)
    act_arr = np.asarray(per_cell_action_t, dtype=np.int16)
    epi_arr = np.asarray(episode_id, dtype=np.int32)
    sid_arr = np.asarray(step_id, dtype=np.int32)
    rew_arr = np.asarray(reward_t, dtype=np.float32)
    done_arr = np.asarray(done_t, dtype=np.bool_)
    term_arr = np.asarray(terminated_t, dtype=np.bool_)
    trunc_arr = np.asarray(truncated_t, dtype=np.bool_)
    mask_avail_arr = np.asarray(action_mask_available_t, dtype=np.bool_)
    source_valid_mask_arr = np.asarray(source_valid_action_mask_t, dtype=np.bool_)

    sv_count_arr = np.asarray(source_valid_action_count_t, dtype=np.int32)
    sel_non_noop_arr = np.asarray(selected_non_noop_count_t, dtype=np.int32)
    sv_non_noop_arr = np.asarray(source_valid_non_noop_count_t, dtype=np.int32)
    mask_sv_count_arr = np.asarray(mask_source_valid_count_t, dtype=np.int32)

    np.savez_compressed(
        rollout_npz,
        observation_t=obs_arr,
        per_cell_action_t=act_arr,
        episode_id=epi_arr,
        step_id=sid_arr,
        reward_t=rew_arr,
        done_t=done_arr,
        terminated_t=term_arr,
        truncated_t=trunc_arr,
        action_mask_available_t=mask_avail_arr,
        source_valid_action_mask_t=source_valid_mask_arr,
        source_valid_action_count_t=sv_count_arr,
        selected_non_noop_count_t=sel_non_noop_arr,
        source_valid_non_noop_count_t=sv_non_noop_arr,
        mask_source_valid_count_t=mask_sv_count_arr,
    )

    total_steps = int(obs_arr.shape[0])
    terminal_count = int(np.count_nonzero(done_arr))
    source_valid_non_noop_share = float(
        np.sum(sv_non_noop_arr, dtype=np.float64) / max(1.0, np.sum(sv_count_arr, dtype=np.float64))
    )

    manifest: Dict[str, Any] = {
        "schema_version": "legacy032.teacher_rollout_raw.v2",
        "teacher_lineage": "legacy032",
        "checkpoint_path": str(checkpoint_path),
        "model_metadata_path": str(metadata_path),
        "trainer_state_path": str(trainer_state_path) if trainer_state_path is not None else None,
        "architecture": EXPECTED_ARCHITECTURE,
        "gym_microrts_version": "0.3.2",
        "map_path": str(args.map_path),
        "observation_shape": list(EXPECTED_OBS_SHAPE),
        "raw_action_nvec": list(EXPECTED_RAW_ACTION_NVEC),
        "stored_action_format": "supervised_per_cell_policy_branches_source_invalid_noop",
        "stored_action_dtype": str(act_arr.dtype),
        "stored_action_shape": ["T", 576, 7],
        "stored_action_branch_sizes": list(BRANCH_SIZES),
        "exported_per_cell_branch_sizes": list(BRANCH_SIZES),
        "source_invalid_cells_forced_to_noop": True,
        "source_valid_action_mask_stored": True,
        "env_step_action_format": "training_compatible_java_valid_actions" if args.step_mode == "training_compatible" else "raw_grid_action_diagnostic_only",
        "step_mode": str(args.step_mode),
        "mask_required": bool(args.require_mask),
        "mask_source": "env.vec_client.getMasks(0)",
        "export_mode": str(export_mode),
        "episodes": int(args.episodes),
        "total_steps": int(total_steps),
        "seed": int(args.seed),
        "created_utc": _now_iso(),
        "semantic_parity_claim": False,
        "direct_weight_transfer_claim": False,
        "strict_load": bool(args.strict_load),
        "strict_load_report": load_report,
        "architecture_build_report": build_report,
        "selected_source_valid_non_noop_share": float(source_valid_non_noop_share),
        "mean_reward": float(np.mean(rew_arr)) if total_steps > 0 else 0.0,
        "episode_mean_return": float(np.mean(np.asarray(episode_returns, dtype=np.float32))) if episode_returns else 0.0,
        "episode_returns": [float(v) for v in episode_returns],
        "terminal_count": int(terminal_count),
        "terminated_count": int(np.count_nonzero(term_arr)),
        "truncated_count": int(np.count_nonzero(trunc_arr)),
        "action_mask_available_share": float(np.mean(mask_avail_arr.astype(np.float64))) if total_steps > 0 else 0.0,
        "step_mode_is_final_evidence_valid": bool(args.step_mode == "training_compatible" and bool(args.require_mask)),
        "cli_args": vars(args),
        "notes": [
            "Stored supervised action is per-cell policy branch action [T,576,7] with source-invalid cells forced to NoOp.",
            "Raw sampled policy branches are still filtered through the training-compatible Java payload for env.step.",
            "Raw env.step([N,576,7]) path is diagnostic only and not valid final export evidence.",
            "Masking is pre-sampling and diagnostic; Unity runtime validation remains authoritative.",
        ],
    }
    manifest_json.write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")

    summary = {
        "status": "OK",
        "run_dir": str(run_dir),
        "rollout_npz": str(rollout_npz),
        "manifest_json": str(manifest_json),
        "summary_created_utc": _now_iso(),
        "first_step_debug": first_step_debug,
        "steps": int(total_steps),
        "episodes": int(args.episodes),
        "export_mode": str(export_mode),
        "step_mode": str(args.step_mode),
        "selected_source_valid_non_noop_share": float(source_valid_non_noop_share),
    }
    summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")

    print(str(run_dir))
    print(str(rollout_npz))
    print(str(manifest_json))
    return 0, rollout_npz, manifest_json


def main() -> int:
    args = parse_args()

    checkpoint_path = _resolve(args.checkpoint_path)
    metadata_path = _resolve(args.model_metadata_path)
    trainer_state_path = _resolve(args.trainer_state_path) if args.trainer_state_path else None

    if not checkpoint_path.exists():
        raise SystemExit(f"checkpoint path does not exist: {checkpoint_path}")
    if not metadata_path.exists():
        raise SystemExit(f"model metadata path does not exist: {metadata_path}")
    if trainer_state_path is not None and not trainer_state_path.exists():
        raise SystemExit(f"trainer state path does not exist: {trainer_state_path}")

    output_root = _resolve(args.output_dir) if args.output_dir else _resolve(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    modes = ["deterministic", "stochastic"] if args.export_mode == "both" else [str(args.export_mode)]

    status_codes: List[int] = []
    for mode in modes:
        run_args = argparse.Namespace(**vars(args))
        if args.export_mode == "both":
            base_label = str(args.run_label).strip() if args.run_label else "legacy032_export"
            run_args.run_label = f"{base_label}_{mode}"
        code, _npz, _manifest = _run_single_mode(
            args=run_args,
            export_mode=mode,
            checkpoint_path=checkpoint_path,
            metadata_path=metadata_path,
            trainer_state_path=trainer_state_path,
            output_root=output_root,
        )
        status_codes.append(int(code))

    return 0 if all(c == 0 for c in status_codes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
