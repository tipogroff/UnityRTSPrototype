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
    infer_logits,
    load_metadata,
    load_policy_checkpoint_strict,
    read_action_mask,
    select_action_deterministic,
    select_action_stochastic,
    summarize_action_distribution,
    validate_required_branch_parameters,
)


CLASS_PASS = "STAGE5I_CANONICAL_ACTION_PATH_PASS"
CLASS_PARTIAL = "STAGE5I_CANONICAL_MODULE_CREATED_BUT_NOT_FULLY_WIRED"
CLASS_VISUAL_STALE = "STAGE5I_VISUAL_SCRIPT_STILL_STALE"
CLASS_FORMAT_MISMATCH = "STAGE5I_ACTION_FORMATTING_STILL_MISMATCH"
CLASS_FAILED = "STAGE5I_VALIDATION_FAILED"


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


def _check_wiring(repo_root: Path) -> Dict[str, Any]:
    targets = [
        "python/week5_teacher_legacy032/scripts/evaluate_teacher_legacy032.py",
        "python/week5_teacher_legacy032/scripts/evaluate_teacher_large_map_diagnostics.py",
        "python/week5_teacher_legacy032/scripts/evaluate_teacher_large_map_win_diagnostics.py",
        "python/week5_teacher_legacy032/scripts/export_teacher_rollout_legacy032.py",
        "python/week5_teacher_legacy032/scripts/run_legacy032_visual_single_episode.py",
        "python/week5_teacher_legacy032/scripts/run_legacy032_3m_visual_single_episode.py",
    ]
    wired: Dict[str, Any] = {}
    for rel in targets:
        path = (repo_root / rel).resolve()
        if not path.exists():
            wired[rel] = {"exists": False, "imports_canonical": False}
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        wired[rel] = {
            "exists": True,
            "imports_canonical": ("legacy032_policy_action" in text),
            "contains_stale_stage_003000000": ("stage_003000000" in text),
        }
    return wired


def _safe_reset(env: Any, seed: int) -> np.ndarray:
    try:
        obs = env.reset(seed=seed)
    except TypeError:
        obs = env.reset()
    if isinstance(obs, tuple):
        obs = obs[0]
    return np.asarray(obs, dtype=np.float32)


def _visual_smoke_on_env(env: Any, contract: Dict[str, Any], policy, device: torch.device, seed: int, mode: str, steps: int) -> Dict[str, Any]:
    try:
        obs = _safe_reset(env, seed=seed)

        first_step = None
        total_steps = 0
        total_reward = 0.0

        for t in range(int(steps)):
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
            if mode == "deterministic":
                action_t = select_action_deterministic(logits, nvec=contract["action_space_nvec"], action_mask=mask_t)
            else:
                action_t = select_action_stochastic(logits, nvec=contract["action_space_nvec"], action_mask=mask_t, seed=seed + t)
            env_action = format_env_action(action_t)

            if first_step is None:
                first_step = {
                    "mask_source": mask_source,
                    "summary": summarize_action_distribution(env_action, mask_np),
                    "branch_validity": validate_required_branch_parameters(env_action, mask_np),
                }

            step_result = env.step(env_action)
            if len(step_result) == 4:
                next_obs, rewards, dones, _infos = step_result
                truncs = np.zeros_like(dones)
            else:
                next_obs, rewards, dones, truncs, _infos = step_result
            rewards = np.asarray(rewards)
            dones = np.asarray(dones)
            truncs = np.asarray(truncs)
            total_reward += float(rewards.reshape(-1)[0])
            total_steps += 1

            if bool(dones.reshape(-1)[0]) or bool(truncs.reshape(-1)[0]):
                break
            obs = np.asarray(next_obs, dtype=np.float32)

        return {
            "ok": True,
            "mode": mode,
            "steps": int(total_steps),
            "total_reward": float(total_reward),
            "first_step": {
                "mask_source": first_step["mask_source"] if first_step else None,
                "summary": first_step["summary"] if first_step else None,
                "effective_noop_candidate_count": (
                    int(first_step["branch_validity"].get("effective_noop_candidate_count", -1))
                    if first_step
                    else None
                ),
            },
        }
    except Exception as exc:
        return {"ok": False, "mode": mode, "error": str(exc)}
    finally:
        pass


def _classify(report: Dict[str, Any]) -> str:
    checks = report["checks"]
    wiring = checks.get("H_wiring_old_scripts")
    stale = checks.get("I_no_stale_3m_default")

    if not isinstance(wiring, dict) or not isinstance(stale, dict):
        return CLASS_FAILED

    if not all(v.get("imports_canonical", False) for v in wiring.values() if v.get("exists")):
        return CLASS_PARTIAL
    if not stale["passed"]:
        return CLASS_VISUAL_STALE
    if not checks["E_format_env_action"]["passed"] or not checks["F_branch_bounds"]["passed"]:
        return CLASS_FORMAT_MISMATCH
    if not all(isinstance(item, dict) and item.get("passed", True) for k, item in checks.items() if k not in {"J_visual_smoke", "H_wiring_old_scripts"}):
        return CLASS_FAILED
    smoke = checks["J_visual_smoke"]
    if smoke["requested"] and (not smoke["deterministic"].get("ok") or not smoke["stochastic"].get("ok")):
        return CLASS_FAILED
    return CLASS_PASS


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate Stage5I canonical action path")
    p.add_argument("--checkpoint-path", required=True)
    p.add_argument("--model-metadata-path", required=True)
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--output-dir", default="python/week5_teacher_legacy032/reports")
    p.add_argument("--run-visual-smoke", action="store_true", default=False)
    p.add_argument("--smoke-steps", type=int, default=16)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = _repo_root()
    checkpoint_path = _resolve(args.checkpoint_path)
    metadata_path = _resolve(args.model_metadata_path)
    output_dir = _resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = _now_ts()
    json_path = output_dir / f"stage5i_canonical_action_path_validation_{ts}.json"
    md_path = output_dir / f"stage5i_canonical_action_path_validation_{ts}.md"
    canonical_md_path = output_dir / "STAGE5I_CANONICAL_ACTION_PATH_REPORT.md"

    report: Dict[str, Any] = {
        "timestamp_utc": _now_iso(),
        "status": "RUNNING",
        "checkpoint_path": str(checkpoint_path),
        "model_metadata_path": str(metadata_path),
        "checks": {},
        "errors": [],
        "classification": CLASS_FAILED,
    }

    env = None
    try:
        device = torch.device("cuda" if args.device == "cuda" and torch.cuda.is_available() else "cpu")

        # A
        report["checks"]["A_canonical_import"] = {"passed": True}

        metadata = load_metadata(metadata_path)
        contract = assert_legacy032_contract(metadata)
        policy, build_report = build_policy_from_metadata(metadata=metadata, device=device)

        # B
        load_report = load_policy_checkpoint_strict(policy, checkpoint_path=checkpoint_path, device=device, strict=True)
        report["checks"]["B_strict_load_1m"] = {
            "passed": True,
            "load_report": load_report,
        }

        env = _create_env(metadata=metadata, max_steps=64)
        obs = _safe_reset(env, seed=int(args.seed))
        mask_np, mask_source = read_action_mask(
            env=env,
            num_envs=int(obs.shape[0]),
            mapsize=int(contract["mapsize"]),
            mask_dim=int(contract["mask_dim"]),
            require_mask=True,
        )
        obs_t = torch.as_tensor(obs, dtype=torch.float32, device=device)
        mask_t = torch.as_tensor(mask_np, dtype=torch.float32, device=device)

        # C
        logits = infer_logits(policy, obs_t)
        report["checks"]["C_fixed_obs_mask_inference"] = {
            "passed": True,
            "logits_shape": list(logits.shape),
            "mask_source": mask_source,
        }

        # D
        det_action = select_action_deterministic(logits, nvec=contract["action_space_nvec"], action_mask=mask_t)
        report["checks"]["D_deterministic_shape"] = {
            "passed": bool(list(det_action.shape[1:]) == [576, 7]),
            "action_shape": list(det_action.shape),
        }

        # E + F
        env_action = format_env_action(det_action)
        report["checks"]["E_format_env_action"] = {
            "passed": bool(env_action.dtype == np.int32 and env_action.flags["C_CONTIGUOUS"]),
            "dtype": str(env_action.dtype),
            "shape": list(env_action.shape),
            "contiguous": bool(env_action.flags["C_CONTIGUOUS"]),
        }
        branch_bounds = [6, 4, 4, 4, 4, 7, 49]
        bounds_ok = True
        for i, b in enumerate(branch_bounds):
            col = env_action[:, :, i]
            if int(col.min()) < 0 or int(col.max()) >= b:
                bounds_ok = False
                break
        report["checks"]["F_branch_bounds"] = {"passed": bounds_ok}

        # G
        fresh_policy, _ = build_policy_from_metadata(metadata=metadata, device=device)
        load_policy_checkpoint_strict(fresh_policy, checkpoint_path=checkpoint_path, device=device, strict=True)
        fresh_logits = infer_logits(fresh_policy, obs_t)
        fresh_action = select_action_deterministic(fresh_logits, nvec=contract["action_space_nvec"], action_mask=mask_t)
        abs_diff = torch.abs(logits - fresh_logits)
        report["checks"]["G_fresh_reload_parity"] = {
            "passed": bool(torch.allclose(logits, fresh_logits, atol=0.0, rtol=0.0) and torch.equal(det_action, fresh_action)),
            "logits_max_abs_diff": float(abs_diff.max().item()),
            "logits_mean_abs_diff": float(abs_diff.mean().item()),
            "action_tensor_equal": bool(torch.equal(det_action, fresh_action)),
        }

        # H + I
        wiring = _check_wiring(repo_root)
        report["checks"]["H_wiring_old_scripts"] = wiring
        stale_files = [k for k, v in wiring.items() if v.get("contains_stale_stage_003000000")]
        report["checks"]["I_no_stale_3m_default"] = {
            "passed": len(stale_files) == 0,
            "stale_files": stale_files,
        }

        # J
        smoke = {
            "requested": bool(args.run_visual_smoke),
            "deterministic": {"ok": None},
            "stochastic": {"ok": None},
            "no_noop_fallback_string": True,
        }
        if args.run_visual_smoke:
            smoke_env = _create_env(metadata=metadata, max_steps=max(int(args.smoke_steps), 8))
            smoke["deterministic"] = _visual_smoke_on_env(
                env=smoke_env,
                contract=contract,
                policy=policy,
                device=device,
                seed=int(args.seed),
                mode="deterministic",
                steps=int(args.smoke_steps),
            )
            smoke["stochastic"] = _visual_smoke_on_env(
                env=smoke_env,
                contract=contract,
                policy=policy,
                device=device,
                seed=int(args.seed),
                mode="stochastic",
                steps=int(args.smoke_steps),
            )
            try:
                smoke_env.close()
            except Exception:
                pass

            visual_text = (repo_root / "python/week5_teacher_legacy032/scripts/run_legacy032_visual_single_episode.py").read_text(
                encoding="utf-8", errors="ignore"
            )
            smoke["no_noop_fallback_string"] = ("fallback" not in visual_text.lower() or "noop" not in visual_text.lower())

        report["checks"]["J_visual_smoke"] = smoke

        report["build_report"] = build_report
        report["contract"] = contract
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

    report["classification"] = _classify(report)

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")

    md_lines = [
        "# Stage5I Canonical Action Path Validation",
        "",
        f"- status: {report.get('status')}",
        f"- classification: {report.get('classification')}",
        f"- checkpoint_path: {report.get('checkpoint_path')}",
        f"- model_metadata_path: {report.get('model_metadata_path')}",
        "",
        "## Checks",
        "",
    ]

    for key, value in report.get("checks", {}).items():
        md_lines.append(f"- {key}: {value}")

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
    return 0 if report.get("classification") == CLASS_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
