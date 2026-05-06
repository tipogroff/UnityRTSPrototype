#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import torch

from legacy032_policy_action import (
    EXPECTED_MAP_PATH,
    assert_legacy032_contract,
    build_policy_from_metadata,
    build_source_indexed_real_action,
    format_env_action,
    format_training_compatible_java_actions,
    infer_logits,
    load_metadata,
    load_policy_checkpoint_strict,
    read_action_mask,
    select_action_deterministic,
    step_env_training_compatible,
)

CLASS_PASS = "STAGE5L_TRAINING_COMPATIBLE_STEP_PASS"
CLASS_RAW_BROKEN_COMPAT_WORKS = "STAGE5L_RAW_STEP_CONFIRMED_BROKEN_COMPAT_STEP_WORKS"
CLASS_BOTH_INERT = "STAGE5L_BOTH_STEP_MODES_INERT"
CLASS_JAVA_PAYLOAD_FAIL = "STAGE5L_JAVA_PAYLOAD_BUILD_FAILED"
CLASS_RENDER_CAPTURE_FAIL = "STAGE5L_RENDER_CAPTURE_STILL_FAILED"
CLASS_VALIDATION_FAIL = "STAGE5L_VALIDATION_FAILED"
CLASS_INCONCLUSIVE = "STAGE5L_INCONCLUSIVE"

FRESH_CKPT = "python/week5_teacher_legacy032/teacher_models/legacy032_stage5k_fresh_mini_train/agent_final.pt"
FRESH_META = "python/week5_teacher_legacy032/teacher_models/legacy032_stage5k_fresh_mini_train/model_metadata.json"
FALLBACK_CKPT = "python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/agent_final.pt"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve(path_str: str | None) -> Path | None:
    if not path_str:
        return None
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


def _safe_reset(env: Any, seed: int) -> np.ndarray:
    try:
        obs = env.reset(seed=seed)
    except TypeError:
        obs = env.reset()
    if isinstance(obs, tuple):
        obs = obs[0]
    return np.asarray(obs, dtype=np.float32)


def _obs_changed(prev_obs: np.ndarray, next_obs: np.ndarray) -> bool:
    a = np.asarray(prev_obs)
    b = np.asarray(next_obs)
    if a.shape != b.shape:
        return True
    return bool(np.any(a != b))


def _resolve_checkpoint_and_metadata(args: argparse.Namespace) -> Tuple[Path, Path, Dict[str, Any]]:
    fresh_ckpt = _resolve(args.checkpoint_path) or _resolve(FRESH_CKPT)
    fresh_meta = _resolve(args.model_metadata_path) or _resolve(FRESH_META)
    fallback_ckpt = _resolve(FALLBACK_CKPT)

    if fresh_ckpt is not None and fresh_ckpt.exists():
        checkpoint_path = fresh_ckpt
        metadata_path = fresh_meta if (fresh_meta is not None and fresh_meta.exists()) else checkpoint_path.parent / "model_metadata.json"
        return checkpoint_path, metadata_path, {"used_fallback": False}

    if fallback_ckpt is not None and fallback_ckpt.exists():
        checkpoint_path = fallback_ckpt
        metadata_path = checkpoint_path.parent / "model_metadata.json"
        if not metadata_path.exists():
            raise RuntimeError(
                "Fallback checkpoint found but metadata missing at "
                f"{metadata_path}"
            )
        return checkpoint_path, metadata_path, {"used_fallback": True, "fallback_reason": "fresh_checkpoint_missing"}

    raise RuntimeError(
        "No valid checkpoint found. Checked fresh path and fallback path."
    )


def _infer_det_action(policy, device: torch.device, obs: np.ndarray, mask_np: np.ndarray, contract: Dict[str, Any]) -> np.ndarray:
    obs_t = torch.as_tensor(obs, dtype=torch.float32, device=device)
    mask_t = torch.as_tensor(mask_np, dtype=torch.float32, device=device)
    logits = infer_logits(policy, obs_t)
    action_t = select_action_deterministic(logits=logits, nvec=contract["action_space_nvec"], action_mask=mask_t)
    return format_env_action(action_t)


def _run_one_step(env: Any, mode: str, policy, device: torch.device, contract: Dict[str, Any], seed: int) -> Dict[str, Any]:
    try:
        obs = _safe_reset(env, seed=seed)
        nenv = int(obs.shape[0])
        mask_np, mask_source = read_action_mask(
            env=env,
            num_envs=nenv,
            mapsize=int(contract["mapsize"]),
            mask_dim=int(contract["mask_dim"]),
            require_mask=True,
        )
        env_action = _infer_det_action(policy=policy, device=device, obs=obs, mask_np=mask_np, contract=contract)

        if mode == "training_compatible":
            step_result, step_debug = step_env_training_compatible(
                env=env,
                action_tensor=env_action,
                action_mask=mask_np,
                mapsize=int(contract["mapsize"]),
            )
            payload_debug = step_debug
        else:
            step_result = env.step(env_action)
            payload = format_training_compatible_java_actions(
                action_tensor=env_action,
                action_mask=mask_np,
                mapsize=int(contract["mapsize"]),
            )
            payload_debug = {
                "valid_actions_counts": [int(v) for v in np.asarray(payload["valid_actions_counts"]).tolist()],
                "first_valid_actions": payload["debug"].get("first_valid_actions", []),
                "source_valid_total": int(payload["debug"].get("source_valid_total", 0)),
                "source_valid_non_noop_count": int(payload["debug"].get("source_valid_non_noop_count", 0)),
            }

        if len(step_result) == 4:
            next_obs, rewards, dones, _infos = step_result
            truncs = np.zeros_like(dones)
        else:
            next_obs, rewards, dones, truncs, _infos = step_result

        next_obs_np = np.asarray(next_obs, dtype=np.float32)
        rewards_np = np.asarray(rewards)
        dones_np = np.asarray(dones)
        truncs_np = np.asarray(truncs)

        return {
            "ok": True,
            "mode": mode,
            "mask_source": mask_source,
            "reward": float(rewards_np.reshape(-1)[0]),
            "done": bool(dones_np.reshape(-1)[0]) or bool(truncs_np.reshape(-1)[0]),
            "obs_changed": _obs_changed(obs, next_obs_np),
            "payload_debug": payload_debug,
        }
    except Exception as exc:
        return {"ok": False, "mode": mode, "error": str(exc)}


def _run_microtrace_training_compatible(
    env: Any,
    policy,
    device: torch.device,
    contract: Dict[str, Any],
    seed: int,
    trace_steps: int,
) -> Dict[str, Any]:
    try:
        obs = _safe_reset(env, seed=seed)

        steps: List[Dict[str, Any]] = []
        done = False
        for t in range(int(trace_steps)):
            nenv = int(obs.shape[0])
            mask_np, _mask_source = read_action_mask(
                env=env,
                num_envs=nenv,
                mapsize=int(contract["mapsize"]),
                mask_dim=int(contract["mask_dim"]),
                require_mask=True,
            )
            env_action = _infer_det_action(policy=policy, device=device, obs=obs, mask_np=mask_np, contract=contract)
            step_result, step_debug = step_env_training_compatible(
                env=env,
                action_tensor=env_action,
                action_mask=mask_np,
                mapsize=int(contract["mapsize"]),
            )

            if len(step_result) == 4:
                next_obs, rewards, dones, _infos = step_result
                truncs = np.zeros_like(dones)
            else:
                next_obs, rewards, dones, truncs, _infos = step_result

            next_obs_np = np.asarray(next_obs, dtype=np.float32)
            reward = float(np.asarray(rewards).reshape(-1)[0])
            done = bool(np.asarray(dones).reshape(-1)[0]) or bool(np.asarray(truncs).reshape(-1)[0])
            changed = _obs_changed(obs, next_obs_np)
            steps.append(
                {
                    "step": int(t),
                    "selected_source_valid_actions": step_debug.get("first_valid_actions", []),
                    "valid_actions_counts": step_debug.get("valid_actions_counts", []),
                    "source_valid_total": int(step_debug.get("source_valid_total", 0)),
                    "source_valid_non_noop_count": int(step_debug.get("source_valid_non_noop_count", 0)),
                    "obs_changed": bool(changed),
                    "raw_reward": float(reward),
                    "done": bool(done),
                }
            )
            obs = next_obs_np
            if done:
                break

        return {
            "ok": True,
            "trace_steps_requested": int(trace_steps),
            "trace_steps_ran": int(len(steps)),
            "obs_changed_steps": int(sum(1 for s in steps if s["obs_changed"])),
            "steps": steps,
            "done": bool(done),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _run_visual_runner_smoke(
    checkpoint_path: Path,
    metadata_path: Path,
    device: str,
    seed: int,
    max_steps: int,
    output_dir: Path,
) -> Dict[str, Any]:
    script_path = _repo_root() / "python/week5_teacher_legacy032/scripts/run_legacy032_visual_single_episode.py"
    run_label = f"stage5l_smoke_{_now_ts()}"
    cmd = [
        sys.executable,
        str(script_path),
        "--checkpoint-path",
        str(checkpoint_path),
        "--model-metadata-path",
        str(metadata_path),
        "--device",
        str(device),
        "--seed",
        str(int(seed)),
        "--mode",
        "deterministic",
        "--max-steps",
        str(int(min(max_steps, 128))),
        "--strict-load",
        "--render",
        "--step-mode",
        "training_compatible",
        "--save-render-rgb-array",
        "--render-mode",
        "both",
        "--output-dir",
        str(output_dir),
        "--run-label",
        run_label,
    ]

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    except Exception as exc:
        return {"ok": False, "error": f"visual_smoke_subprocess_failed: {exc}"}

    json_candidates: List[Path] = []
    for line in (proc.stdout or "").splitlines():
        text = line.strip()
        if text.endswith(".json"):
            candidate = Path(text)
            if candidate.exists():
                json_candidates.append(candidate)

    if not json_candidates:
        run_dir = output_dir / run_label
        if run_dir.exists():
            json_candidates.extend(sorted(run_dir.glob("legacy032_visual_single_episode_*.json")))

    if not json_candidates:
        return {
            "ok": False,
            "exit_code": int(proc.returncode),
            "stdout_tail": (proc.stdout or "")[-4000:],
            "stderr_tail": (proc.stderr or "")[-4000:],
            "error": "visual_smoke_report_not_found",
        }

    report_path = json_candidates[-1]
    try:
        visual = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "ok": False,
            "exit_code": int(proc.returncode),
            "report_path": str(report_path),
            "error": f"visual_smoke_report_parse_failed: {exc}",
        }

    return {
        "ok": bool(proc.returncode == 0 and visual.get("status") == "OK"),
        "exit_code": int(proc.returncode),
        "report_path": str(report_path),
        "visual": visual,
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
    }


def _classify(report: Dict[str, Any]) -> Tuple[str, str]:
    if report.get("status") != "OK":
        return CLASS_VALIDATION_FAIL, "Fix validator/runtime errors and rerun Stage5L checks."

    checks = report.get("checks", {})
    if not checks:
        return CLASS_INCONCLUSIVE, "No checks were recorded; rerun validator."

    if not checks.get("java_payload_build", {}).get("passed", False):
        return CLASS_JAVA_PAYLOAD_FAIL, "Match Java payload construction to trainer path exactly."

    raw_step = checks.get("one_step_raw", {})
    compat_step = checks.get("one_step_training_compatible", {})
    microtrace = checks.get("training_compatible_microtrace", {})
    visual_smoke = checks.get("visual_runner_smoke", {})

    raw_ok = bool(raw_step.get("ok"))
    compat_ok = bool(compat_step.get("ok"))
    if not raw_ok or not compat_ok:
        return CLASS_VALIDATION_FAIL, "One-step execution failed; inspect one_step_raw/one_step_training_compatible errors."

    raw_changed = bool(raw_step.get("obs_changed", False))
    compat_changed = bool(compat_step.get("obs_changed", False)) or bool(microtrace.get("obs_changed_steps", 0) > 0)

    compat_payload = compat_step.get("payload_debug", {}) if isinstance(compat_step.get("payload_debug"), dict) else {}
    non_noop_selected = int(compat_payload.get("source_valid_non_noop_count", 0)) > 0

    visual_ok = bool(visual_smoke.get("ok"))
    visual_payload = visual_smoke.get("visual", {}) if isinstance(visual_smoke.get("visual"), dict) else {}
    rendered_frames_count = int(visual_payload.get("rendered_frames_count", 0) or 0)
    render_capture_status = str(visual_payload.get("render_capture_status", "UNKNOWN"))
    visual_obs_changed_steps = int(visual_payload.get("total_obs_changed_steps", 0) or 0)

    if (not raw_changed) and compat_changed:
        return CLASS_RAW_BROKEN_COMPAT_WORKS, "Use training-compatible step everywhere and rerun visual by-eye check."

    if compat_changed and visual_ok and visual_obs_changed_steps > 0:
        if rendered_frames_count <= 0 and render_capture_status == "RENDER_RETURNED_NONE":
            return CLASS_RENDER_CAPTURE_FAIL, "Separate render capture issue from action application and keep training-compatible stepping."
        return CLASS_PASS, "Rerun Stage5J/Stage5K visual checks, then resume teacher decision track."

    if non_noop_selected and (not raw_changed) and (not compat_changed):
        return CLASS_BOTH_INERT, "Inspect action semantics and initial map layout, especially Harvest/Produce validity."

    if compat_changed and rendered_frames_count <= 0 and render_capture_status in {"RENDER_RETURNED_NONE", "RENDER_WRITE_FAILED"}:
        return CLASS_RENDER_CAPTURE_FAIL, "Behavior works but frame capture still fails; isolate renderer path from action path."

    return CLASS_INCONCLUSIVE, "Rerun validator with extended trace and inspect payload/debug fields."


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate Stage5L training-compatible Java action payload stepping")
    p.add_argument("--checkpoint-path", default=FRESH_CKPT)
    p.add_argument("--model-metadata-path", default=FRESH_META)
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--max-steps", type=int, default=128)
    p.add_argument("--output-dir", default="python/week5_teacher_legacy032/reports")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = _resolve(args.output_dir)
    if output_dir is None:
        raise SystemExit(2)
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = _now_ts()
    json_path = output_dir / f"stage5l_training_compatible_step_{ts}.json"
    md_path = output_dir / f"stage5l_training_compatible_step_{ts}.md"
    canonical_md_path = output_dir / "STAGE5L_TRAINING_COMPATIBLE_STEP_REPORT.md"

    report: Dict[str, Any] = {
        "timestamp_utc": _now_iso(),
        "status": "RUNNING",
        "checks": {},
        "errors": [],
        "classification": CLASS_VALIDATION_FAIL,
        "recommendation": "",
    }
    env = None

    try:
        checkpoint_path, metadata_path, fallback_info = _resolve_checkpoint_and_metadata(args)
        report["checkpoint_path"] = str(checkpoint_path)
        report["model_metadata_path"] = str(metadata_path)
        report["fallback"] = fallback_info

        device = torch.device("cuda" if args.device == "cuda" and torch.cuda.is_available() else "cpu")

        report["checks"]["canonical_import"] = {"passed": True}

        metadata = load_metadata(metadata_path)
        contract = assert_legacy032_contract(metadata)
        policy, build_report = build_policy_from_metadata(metadata=metadata, device=device)
        load_report = load_policy_checkpoint_strict(
            policy=policy,
            checkpoint_path=checkpoint_path,
            device=device,
            strict=True,
        )
        policy.eval()

        report["build_report"] = build_report
        report["load_report"] = load_report
        report["contract"] = contract
        report["checks"]["strict_load"] = {"passed": True, "strict_load_status": load_report.get("strict_load_status")}

        env = _create_env(metadata=metadata, max_steps=max(64, int(args.max_steps)))
        obs = _safe_reset(env, seed=int(args.seed))
        nenv = int(obs.shape[0])
        mask_np, mask_source = read_action_mask(
            env=env,
            num_envs=nenv,
            mapsize=int(contract["mapsize"]),
            mask_dim=int(contract["mask_dim"]),
            require_mask=True,
        )
        env_action = _infer_det_action(policy=policy, device=device, obs=obs, mask_np=mask_np, contract=contract)
        real_action = build_source_indexed_real_action(env_action, mapsize=int(contract["mapsize"]))

        source_indices = real_action[:, :, 0]
        expected_source = np.broadcast_to(
            np.arange(int(contract["mapsize"]), dtype=np.int32).reshape(1, int(contract["mapsize"])),
            source_indices.shape,
        )
        source_indices_ok = bool(np.array_equal(source_indices, expected_source))
        branches_preserved_ok = bool(np.array_equal(real_action[:, :, 1:], env_action))

        payload = format_training_compatible_java_actions(
            action_tensor=env_action,
            action_mask=mask_np,
            mapsize=int(contract["mapsize"]),
        )
        counts_expected = (mask_np[:, :, 0] > 0).sum(axis=1).astype(np.int32)
        counts_actual = np.asarray(payload["valid_actions_counts"], dtype=np.int32)
        counts_match = bool(np.array_equal(counts_actual, counts_expected))

        report["checks"]["source_indexed_real_action"] = {
            "passed": bool(real_action.shape == (nenv, int(contract["mapsize"]), 8) and source_indices_ok and branches_preserved_ok),
            "real_action_shape": list(real_action.shape),
            "mask_source": mask_source,
            "source_indices_ok": source_indices_ok,
            "branches_preserved_ok": branches_preserved_ok,
        }
        report["checks"]["java_payload_build"] = {
            "passed": bool(counts_match),
            "valid_actions_counts": [int(v) for v in counts_actual.tolist()],
            "counts_expected": [int(v) for v in counts_expected.tolist()],
            "counts_match": counts_match,
            "source_valid_total": int(payload["debug"].get("source_valid_total", 0)),
            "source_valid_non_noop_count": int(payload["debug"].get("source_valid_non_noop_count", 0)),
            "first_valid_actions": payload["debug"].get("first_valid_actions", []),
        }

        report["checks"]["one_step_raw"] = _run_one_step(
            env=env,
            mode="raw",
            policy=policy,
            device=device,
            contract=contract,
            seed=int(args.seed),
        )
        report["checks"]["one_step_training_compatible"] = _run_one_step(
            env=env,
            mode="training_compatible",
            policy=policy,
            device=device,
            contract=contract,
            seed=int(args.seed),
        )

        report["checks"]["raw_vs_training_compatible_comparison"] = {
            "both_ok": bool(report["checks"]["one_step_raw"].get("ok") and report["checks"]["one_step_training_compatible"].get("ok")),
            "obs_changed_raw": report["checks"]["one_step_raw"].get("obs_changed"),
            "obs_changed_training_compatible": report["checks"]["one_step_training_compatible"].get("obs_changed"),
            "reward_raw": report["checks"]["one_step_raw"].get("reward"),
            "reward_training_compatible": report["checks"]["one_step_training_compatible"].get("reward"),
            "done_raw": report["checks"]["one_step_raw"].get("done"),
            "done_training_compatible": report["checks"]["one_step_training_compatible"].get("done"),
        }

        report["checks"]["training_compatible_microtrace"] = _run_microtrace_training_compatible(
            env=env,
            policy=policy,
            device=device,
            contract=contract,
            seed=int(args.seed),
            trace_steps=min(32, int(args.max_steps)),
        )

        visual_output_dir = output_dir / "stage5l_visual_smoke"
        visual_output_dir.mkdir(parents=True, exist_ok=True)
        report["checks"]["visual_runner_smoke"] = _run_visual_runner_smoke(
            checkpoint_path=checkpoint_path,
            metadata_path=metadata_path,
            device=str(args.device),
            seed=int(args.seed),
            max_steps=int(args.max_steps),
            output_dir=visual_output_dir,
        )

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

    classification, recommendation = _classify(report)
    report["classification"] = classification
    report["recommendation"] = recommendation

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")

    md_lines = [
        "# Stage5L Training-Compatible Step Validation",
        "",
        f"- status: {report.get('status')}",
        f"- classification: {report.get('classification')}",
        f"- recommendation: {report.get('recommendation')}",
        f"- checkpoint_path: {report.get('checkpoint_path')}",
        f"- model_metadata_path: {report.get('model_metadata_path')}",
        "",
        "## Checks",
        "",
    ]
    for k, v in report.get("checks", {}).items():
        md_lines.append(f"- {k}: {v}")
    if report.get("errors"):
        md_lines.extend(["", "## Errors", ""])
        for e in report["errors"]:
            md_lines.append(f"- {e}")

    md_text = "\n".join(md_lines) + "\n"
    md_path.write_text(md_text, encoding="utf-8")
    canonical_md_path.write_text(md_text, encoding="utf-8")

    print(str(json_path))
    print(str(md_path))
    print(str(canonical_md_path))

    return 0 if classification in {CLASS_PASS, CLASS_RAW_BROKEN_COMPAT_WORKS, CLASS_RENDER_CAPTURE_FAIL, CLASS_BOTH_INERT, CLASS_INCONCLUSIVE} and report.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
