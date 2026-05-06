#!/usr/bin/env python3
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
    format_training_compatible_java_actions,
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

    ai2s = [microrts_ai.coacAI for _ in range(max(0, num_bot_envs - 2))] + [
        microrts_ai.randomBiasedAI for _ in range(min(num_bot_envs, 1))
    ] + [microrts_ai.workerRushAI for _ in range(min(max(0, num_bot_envs - 1), 1))]
    if len(ai2s) < num_bot_envs:
        ai2s += [microrts_ai.coacAI for _ in range(num_bot_envs - len(ai2s))]
    return ai2s[:num_bot_envs]


def _create_env(metadata: Dict[str, Any], max_steps: int):
    from gym_microrts.envs.vec_env import MicroRTSGridModeVecEnv

    md_args = metadata.get("args", {}) if isinstance(metadata.get("args"), dict) else {}
    num_selfplay = int(md_args.get("num_selfplay_envs", 0))
    num_bot = int(md_args.get("num_bot_envs", 2))
    num_bot = max(1, min(2, num_bot))

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


def _reset_env_compat(env: Any, seed: int):
    try:
        return env.reset(seed=int(seed))
    except TypeError as exc:
        # gym-microrts legacy wrappers may not accept reset(seed=...).
        if "seed" not in str(exc):
            raise
        if hasattr(env, "seed"):
            try:
                env.seed(int(seed))
            except Exception:
                pass
        return env.reset()


def _obs_changed(prev_obs: np.ndarray, next_obs: np.ndarray) -> bool:
    prev_arr = np.asarray(prev_obs)
    next_arr = np.asarray(next_obs)
    if prev_arr.shape != next_arr.shape:
        return True
    return bool(np.any(prev_arr != next_arr))


def _render_rgb_frame(env: Any, warnings: List[str]) -> np.ndarray | None:
    attempts = [
        ("env.render(mode='rgb_array')", lambda: env.render(mode="rgb_array")),
        ("env.render('rgb_array')", lambda: env.render("rgb_array")),
        ("env.render()", lambda: env.render()),
    ]
    for name, call in attempts:
        try:
            frame = call()
        except TypeError:
            continue
        except Exception as exc:
            warnings.append(f"{name} failed: {exc}")
            continue
        if frame is not None:
            return np.asarray(frame)
    return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Legacy032 visual single-episode runner (canonical)")
    p.add_argument("--checkpoint-path", required=True)
    p.add_argument("--model-metadata-path", required=True)
    p.add_argument("--output-dir", default="python/week5_teacher_legacy032/reports/stage5i_visual_single_episode")
    p.add_argument("--run-label", default="")
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--mode", choices=["deterministic", "stochastic"], default="deterministic")
    p.add_argument("--max-steps", type=int, default=6000)
    p.add_argument("--strict-load", action="store_true", default=True)
    p.add_argument("--no-strict-load", dest="strict_load", action="store_false")
    p.add_argument("--render", action="store_true", default=False)
    p.add_argument("--frame-every", type=int, default=1)
    p.add_argument("--step-mode", choices=["raw", "training_compatible"], default="training_compatible")
    p.add_argument("--save-render-rgb-array", action="store_true", default=False)
    p.add_argument("--render-mode", choices=["human", "rgb_array", "both"], default="both")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    checkpoint_path = _resolve(args.checkpoint_path)
    metadata_path = _resolve(args.model_metadata_path)
    output_dir = _resolve(args.output_dir)
    if args.run_label:
        output_dir = output_dir / args.run_label
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_json = output_dir / f"legacy032_visual_single_episode_{_now()}.json"
    summary_md = output_dir / "LEGACY032_VISUAL_SINGLE_EPISODE.md"

    report: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checkpoint_path": str(checkpoint_path),
        "model_metadata_path": str(metadata_path),
        "mode": args.mode,
        "seed": int(args.seed),
        "strict_load": bool(args.strict_load),
        "step_mode": str(args.step_mode),
        "status": "RUNNING",
        "errors": [],
        "warnings": [],
    }

    env = None
    try:
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

        env = _create_env(metadata=metadata, max_steps=int(args.max_steps))
        obs = _reset_env_compat(env, int(args.seed))
        if isinstance(obs, tuple):
            obs = obs[0]
        obs = np.asarray(obs, dtype=np.float32)

        total_reward = 0.0
        total_steps = 0
        first_step_printed = False
        frame_paths: List[str] = []
        raw_rewards: List[float] = []
        obs_changed_first32: List[bool] = []
        total_obs_changed_steps = 0
        render_capture_status = "NOT_REQUESTED"
        java_payload_used = bool(args.step_mode == "training_compatible")

        for step in range(int(args.max_steps)):
            nenv = int(obs.shape[0])
            mask_np, mask_source = read_action_mask(
                env=env,
                num_envs=nenv,
                mapsize=int(contract["mapsize"]),
                mask_dim=int(contract["mask_dim"]),
                require_mask=True,
            )

            obs_t = torch.as_tensor(obs, dtype=torch.float32, device=device)
            mask_t = torch.as_tensor(mask_np, dtype=torch.float32, device=device)
            logits = infer_logits(policy, obs_t)
            if args.mode == "deterministic":
                action_t = select_action_deterministic(logits=logits, nvec=contract["action_space_nvec"], action_mask=mask_t)
            else:
                action_t = select_action_stochastic(
                    logits=logits,
                    nvec=contract["action_space_nvec"],
                    action_mask=mask_t,
                    seed=int(args.seed) + step,
                )

            env_action = format_env_action(action_t)
            payload_preview = format_training_compatible_java_actions(
                action_tensor=env_action,
                action_mask=mask_np,
                mapsize=int(contract["mapsize"]),
            )
            payload_debug = payload_preview["debug"]

            if not first_step_printed:
                first_summary = summarize_action_distribution(env_action, mask=mask_np)
                first_validity = validate_required_branch_parameters(env_action, mask_np)
                print(f"[visual] checkpoint={checkpoint_path}")
                print(f"[visual] metadata={metadata_path}")
                print(f"[visual] mode={args.mode} seed={args.seed}")
                print(f"[visual] mask_source={mask_source}")
                print(f"[visual] first_step_summary={json.dumps(first_summary, ensure_ascii=True)}")
                print(
                    "[visual] first_step_branch_validity="
                    + json.dumps(
                        {
                            "source_valid_total": first_validity["source_valid_total"],
                            "effective_noop_candidate_count": first_validity["effective_noop_candidate_count"],
                        },
                        ensure_ascii=True,
                    )
                )
                report["first_step"] = {
                    "mask_source": mask_source,
                    "summary": first_summary,
                    "branch_validity": {
                        "source_valid_total": first_validity["source_valid_total"],
                        "effective_noop_candidate_count": first_validity["effective_noop_candidate_count"],
                    },
                    "payload_debug": {
                        "valid_actions_counts": payload_debug.get("valid_actions_counts", []),
                        "first_valid_actions": payload_debug.get("first_valid_actions", []),
                        "source_valid_total": payload_debug.get("source_valid_total", 0),
                        "source_valid_non_noop_count": payload_debug.get("source_valid_non_noop_count", 0),
                    },
                }
                first_step_printed = True

            if bool(args.render) and (step % max(1, int(args.frame_every)) == 0):
                if args.render_mode in {"human", "both"}:
                    try:
                        env.render()
                    except Exception as exc:
                        report["warnings"].append(f"human render failed at step={step}: {exc}")
                capture_requested = bool(args.save_render_rgb_array) or (args.render_mode in {"rgb_array", "both"})
                if capture_requested:
                    frame = _render_rgb_frame(env, report["warnings"])
                    if frame is None:
                        if render_capture_status != "RENDER_WRITE_FAILED":
                            render_capture_status = "RENDER_RETURNED_NONE"
                    else:
                        frame_path = output_dir / f"frame_{step:04d}.png"
                        try:
                            import imageio.v2 as imageio

                            imageio.imwrite(frame_path, frame)
                            frame_paths.append(str(frame_path))
                            if render_capture_status != "RENDER_WRITE_FAILED":
                                render_capture_status = "CAPTURED"
                        except Exception as exc:
                            render_capture_status = "RENDER_WRITE_FAILED"
                            warn = f"frame write failed at step={step}: {exc}"
                            report["warnings"].append(warn)

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
                next_obs, rewards, dones, infos = step_result
                truncs = np.zeros_like(dones)
            else:
                next_obs, rewards, dones, truncs, infos = step_result

            rewards = np.asarray(rewards)
            dones = np.asarray(dones)
            truncs = np.asarray(truncs)
            next_obs_np = np.asarray(next_obs, dtype=np.float32)
            total_reward += float(rewards.reshape(-1)[0])
            total_steps += 1
            raw_rewards.append(float(rewards.reshape(-1)[0]))
            changed = _obs_changed(obs, next_obs_np)
            if changed:
                total_obs_changed_steps += 1
            if len(obs_changed_first32) < 32:
                obs_changed_first32.append(bool(changed))

            done = bool(dones.reshape(-1)[0]) or bool(truncs.reshape(-1)[0])
            if done:
                info0 = infos[0] if isinstance(infos, (list, tuple)) and len(infos) > 0 else infos
                report["terminal_info_keys"] = sorted(list(info0.keys())) if isinstance(info0, dict) else None
                break

            obs = next_obs_np

        report.update(
            {
                "status": "OK",
                "contract": contract,
                "build_report": build_report,
                "load_report": load_report,
                "total_steps": int(total_steps),
                "total_reward": float(total_reward),
                "step_mode": str(args.step_mode),
                "java_payload_used": bool(java_payload_used),
                "raw_rewards": raw_rewards,
                "obs_changed_first32": obs_changed_first32,
                "total_obs_changed_steps": int(total_obs_changed_steps),
                "rendered_frames_count": int(len(frame_paths)),
                "render_capture_status": render_capture_status,
                "rendered_frames": frame_paths,
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

    summary_json.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    md_lines = [
        "# Legacy032 Visual Single Episode (Canonical)",
        "",
        f"- status: {report.get('status')}",
        f"- checkpoint_path: {report.get('checkpoint_path')}",
        f"- metadata_path: {report.get('model_metadata_path')}",
        f"- mode: {report.get('mode')}",
        f"- seed: {report.get('seed')}",
        f"- strict_load: {report.get('strict_load')}",
        f"- step_mode: {report.get('step_mode')}",
        f"- java_payload_used: {report.get('java_payload_used')}",
        f"- first_step: {report.get('first_step')}",
        f"- total_steps: {report.get('total_steps')}",
        f"- total_reward: {report.get('total_reward')}",
        f"- total_obs_changed_steps: {report.get('total_obs_changed_steps')}",
        f"- rendered_frames_count: {report.get('rendered_frames_count')}",
        f"- render_capture_status: {report.get('render_capture_status')}",
    ]
    if report.get("warnings"):
        md_lines.append("")
        md_lines.append("## Warnings")
        for w in report["warnings"]:
            md_lines.append(f"- {w}")
    if report.get("errors"):
        md_lines.append("")
        md_lines.append("## Errors")
        for e in report["errors"]:
            md_lines.append(f"- {e}")
    summary_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(str(summary_json))
    print(str(summary_md))
    return 0 if report.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
