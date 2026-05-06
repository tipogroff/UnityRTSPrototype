from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import torch

from legacy032_policy_action import (
    EXPECTED_MAP_PATH,
    assert_legacy032_contract,
    build_policy_from_metadata,
    format_env_action,
    infer_logits,
    load_metadata,
    load_policy_checkpoint_strict,
    read_action_mask,
    select_action_deterministic,
    step_env_training_compatible,
    summarize_action_distribution,
    validate_required_branch_parameters,
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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export canonical legacy032 rollout")
    p.add_argument("--checkpoint-path", required=True)
    p.add_argument("--model-metadata-path", default=None)
    p.add_argument("--output-dir", default="python/week5_teacher_legacy032/reports/rollouts")
    p.add_argument("--episode-max-steps", type=int, default=1200)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    p.add_argument("--strict-load", action="store_true", default=True)
    p.add_argument("--no-strict-load", dest="strict_load", action="store_false")
    p.add_argument("--step-mode", choices=["raw", "training_compatible"], default="training_compatible")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    checkpoint_path = _resolve(args.checkpoint_path)
    metadata_path = _resolve(args.model_metadata_path) if args.model_metadata_path else checkpoint_path.parent / "model_metadata.json"
    output_dir = _resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = _now()
    base_name = f"legacy032_rollout_{ts}"
    npz_path = output_dir / f"{base_name}.npz"
    json_path = output_dir / f"{base_name}.json"

    report: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checkpoint_path": str(checkpoint_path),
        "model_metadata_path": str(metadata_path),
        "strict_load": bool(args.strict_load),
        "step_mode": str(args.step_mode),
        "status": "RUNNING",
        "errors": [],
    }

    env = None
    try:
        metadata = load_metadata(metadata_path)
        contract = assert_legacy032_contract(metadata)
        device = torch.device("cuda" if args.device == "cuda" and torch.cuda.is_available() else "cpu")

        policy, build_report = build_policy_from_metadata(metadata=metadata, device=device)
        load_report = load_policy_checkpoint_strict(policy=policy, checkpoint_path=checkpoint_path, device=device, strict=bool(args.strict_load))
        policy.eval()

        env = _create_env(metadata=metadata, max_steps=int(args.episode_max_steps))
        obs = _safe_reset(env, seed=int(args.seed))

        obs_buf: List[np.ndarray] = []
        action_buf: List[np.ndarray] = []
        reward_buf: List[float] = []
        done_buf: List[bool] = []

        first_step_summary = None

        for step_idx in range(int(args.episode_max_steps)):
            nenv = int(obs.shape[0])
            mask_np, mask_source = read_action_mask(env, nenv, int(contract["mapsize"]), int(contract["mask_dim"]), require_mask=True)
            obs_t = torch.as_tensor(obs, dtype=torch.float32, device=device)
            mask_t = torch.as_tensor(mask_np, dtype=torch.float32, device=device)
            logits = infer_logits(policy, obs_t)
            action_t = select_action_deterministic(logits=logits, nvec=contract["action_space_nvec"], action_mask=mask_t)
            env_action = format_env_action(action_t)

            if first_step_summary is None:
                summary = summarize_action_distribution(env_action, mask=mask_np)
                validity = validate_required_branch_parameters(env_action, mask_np)
                first_step_summary = {
                    "mask_source": mask_source,
                    "summary": summary,
                    "effective_noop_candidate_count": validity["effective_noop_candidate_count"],
                }

            if args.step_mode == "training_compatible":
                step_result, _step_debug = step_env_training_compatible(
                    env=env,
                    action_tensor=env_action,
                    action_mask=mask_np,
                    mapsize=int(contract["mapsize"]),
                )
            else:
                step_result = env.step(env_action)
            if len(step_result) == 4:
                next_obs, rewards, dones, _infos = step_result
                truncs = np.zeros_like(dones)
            else:
                next_obs, rewards, dones, truncs, _infos = step_result

            rewards = np.asarray(rewards)
            dones = np.asarray(dones)
            truncs = np.asarray(truncs)

            obs_buf.append(np.asarray(obs, dtype=np.float32)[0])
            action_buf.append(env_action[0].astype(np.int32, copy=False))
            reward_buf.append(float(rewards.reshape(-1)[0]))
            done_flag = bool(dones.reshape(-1)[0]) or bool(truncs.reshape(-1)[0])
            done_buf.append(done_flag)

            if done_flag:
                break

            obs = np.asarray(next_obs, dtype=np.float32)

        np.savez_compressed(
            npz_path,
            obs=np.asarray(obs_buf, dtype=np.float32),
            action=np.asarray(action_buf, dtype=np.int32),
            reward=np.asarray(reward_buf, dtype=np.float32),
            done=np.asarray(done_buf, dtype=np.bool_),
        )

        report.update(
            {
                "status": "OK",
                "contract": contract,
                "build_report": build_report,
                "load_report": load_report,
                "first_step": first_step_summary,
                "rollout": {
                    "steps": int(len(reward_buf)),
                    "reward_sum": float(np.sum(np.asarray(reward_buf, dtype=np.float32))),
                    "npz_path": str(npz_path),
                },
            }
        )

    except Exception as exc:
        report["status"] = "ERROR"
        report["errors"].append(str(exc))

    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    print(str(npz_path))
    print(str(json_path))
    return 0 if report.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
