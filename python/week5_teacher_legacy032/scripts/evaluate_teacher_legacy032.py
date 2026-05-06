from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

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
    select_action_stochastic,
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
    p = argparse.ArgumentParser(description="Legacy032 canonical evaluator")
    p.add_argument("--checkpoint-path", required=True)
    p.add_argument("--model-metadata-path", default=None)
    p.add_argument("--episodes", type=int, default=8)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    p.add_argument("--eval-mode", choices=["deterministic", "stochastic", "both"], default="both")
    p.add_argument("--max-steps-per-episode", type=int, default=6000)
    p.add_argument("--output-dir", default="python/week5_teacher_legacy032/reports")
    p.add_argument("--run-label", default="stage3_behavior_gate")
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
    json_path = output_dir / f"{args.run_label}_{ts}.json"
    md_path = output_dir / f"{args.run_label}_{ts}.md"

    report: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_label": args.run_label,
        "checkpoint_path": str(checkpoint_path),
        "model_metadata_path": str(metadata_path),
        "strict_load": bool(args.strict_load),
        "step_mode": str(args.step_mode),
        "status": "RUNNING",
        "errors": [],
        "warnings": [],
        "eval_results": {},
    }

    env = None
    try:
        metadata = load_metadata(metadata_path)
        contract = assert_legacy032_contract(metadata)
        device = torch.device("cuda" if args.device == "cuda" and torch.cuda.is_available() else "cpu")

        policy, build_report = build_policy_from_metadata(metadata=metadata, device=device)
        load_report = load_policy_checkpoint_strict(policy=policy, checkpoint_path=checkpoint_path, device=device, strict=bool(args.strict_load))
        policy.eval()

        env = _create_env(metadata=metadata, max_steps=int(args.max_steps_per_episode))
        eval_modes = [args.eval_mode] if args.eval_mode != "both" else ["deterministic", "stochastic"]

        first_step = None
        for mode in eval_modes:
            mode_seed = int(args.seed) if mode == "deterministic" else int(args.seed) + 123
            torch.manual_seed(mode_seed)
            np.random.seed(mode_seed)

            steps = 0
            reward_sum = 0.0
            done_count = 0

            for ep in range(int(args.episodes)):
                obs = _safe_reset(env, seed=mode_seed + ep)
                for _ in range(int(args.max_steps_per_episode)):
                    nenv = int(obs.shape[0])
                    mask_np, mask_source = read_action_mask(env, nenv, int(contract["mapsize"]), int(contract["mask_dim"]), require_mask=True)
                    obs_t = torch.as_tensor(obs, dtype=torch.float32, device=device)
                    mask_t = torch.as_tensor(mask_np, dtype=torch.float32, device=device)
                    logits = infer_logits(policy, obs_t)
                    if mode == "deterministic":
                        action_t = select_action_deterministic(logits=logits, nvec=contract["action_space_nvec"], action_mask=mask_t)
                    else:
                        action_t = select_action_stochastic(logits=logits, nvec=contract["action_space_nvec"], action_mask=mask_t, seed=mode_seed + steps)
                    env_action = format_env_action(action_t)

                    if first_step is None:
                        summary = summarize_action_distribution(env_action, mask=mask_np)
                        validity = validate_required_branch_parameters(env_action, mask_np)
                        first_step = {
                            "mask_source": mask_source,
                            "mode": mode,
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
                    reward_sum += float(rewards.reshape(-1)[0])
                    steps += 1
                    done = bool(dones.reshape(-1)[0]) or bool(truncs.reshape(-1)[0])
                    if done:
                        done_count += 1
                        break
                    obs = np.asarray(next_obs, dtype=np.float32)

            report["eval_results"][mode] = {"steps": int(steps), "reward_sum": float(reward_sum), "done_count": int(done_count)}

        report["first_step"] = first_step
        report["contract"] = contract
        report["build_report"] = build_report
        report["load_report"] = load_report
        report["status"] = "OK"

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
    md_lines = [
        "# Legacy032 Canonical Evaluation",
        "",
        f"- status: {report.get('status')}",
        f"- checkpoint_path: {report.get('checkpoint_path')}",
        f"- metadata_path: {report.get('model_metadata_path')}",
        f"- strict_load: {report.get('strict_load')}",
        f"- load_report: {report.get('load_report')}",
        f"- eval_results: {report.get('eval_results')}",
        f"- first_step: {report.get('first_step')}",
    ]
    if report.get("errors"):
        md_lines.append("")
        md_lines.append("## Errors")
        for e in report["errors"]:
            md_lines.append(f"- {e}")
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(str(json_path))
    print(str(md_path))
    return 0 if report.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
