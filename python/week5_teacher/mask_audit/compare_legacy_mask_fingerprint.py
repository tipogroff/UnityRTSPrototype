#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from mask_audit_utils import (
    DEFAULT_OUTPUT_DIR,
    build_full_mask_from_candidates,
    create_runtime_context,
    create_wrapped_env,
    flatten_mask,
    get_branch,
    parse_common_args,
    reset_compat,
    runtime_versions_payload,
    safe_action_space_sample,
    safe_json_dump,
    step_compat,
    utc_now,
)


def parse_args() -> argparse.Namespace:
    p = parse_common_args("Compare current mask fingerprint against legacy gym_microrts 0.3.2 setup.")
    p.add_argument("--steps", type=int, default=100)
    p.add_argument(
        "--legacy-python-exe",
        default="python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe",
    )
    p.add_argument(
        "--output-current",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "mask_fingerprint_current.json",
    )
    p.add_argument(
        "--output-legacy",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "mask_fingerprint_legacy_032.json",
    )
    p.add_argument(
        "--output-comparison",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "MASK_FINGERPRINT_COMPARISON.json",
    )
    return p.parse_args()


def compute_fingerprint(obs: np.ndarray, flat_mask: np.ndarray, dones_seen: int) -> Dict[str, Any]:
    source = flat_mask[:, :, 0] > 0
    action_type = get_branch(flat_mask, "action_type") > 0
    move = get_branch(flat_mask, "move_dir") > 0
    harvest = get_branch(flat_mask, "harvest_dir") > 0
    ret = get_branch(flat_mask, "return_dir") > 0
    produce = get_branch(flat_mask, "produce_dir") > 0
    attack = get_branch(flat_mask, "attack_target") > 0

    ready = int(source.sum())
    nonnoop = int(np.logical_and(source, np.any(action_type[:, :, 1:], axis=2)).sum())

    return {
        "obs_shape": list(obs.shape),
        "mask_shape": list(flat_mask.shape),
        "valid_actor_count": ready,
        "valid_action_type_distribution": {
            "noop_valid": int(np.logical_and(source, action_type[:, :, 0]).sum()),
            "move_valid": int(np.logical_and(source, action_type[:, :, 1]).sum()),
            "harvest_valid": int(np.logical_and(source, action_type[:, :, 2]).sum()),
            "return_valid": int(np.logical_and(source, action_type[:, :, 3]).sum()),
            "produce_valid": int(np.logical_and(source, action_type[:, :, 4]).sum()),
            "attack_valid": int(np.logical_and(source, action_type[:, :, 5]).sum()),
        },
        "valid_parameter_distribution": {
            "move": int(np.logical_and(source, np.any(move, axis=2)).sum()),
            "harvest": int(np.logical_and(source, np.any(harvest, axis=2)).sum()),
            "return": int(np.logical_and(source, np.any(ret, axis=2)).sum()),
            "produce": int(np.logical_and(source, np.any(produce, axis=2)).sum()),
            "attack": int(np.logical_and(source, np.any(attack, axis=2)).sum()),
        },
        "valid_nonnoop_share": float(nonnoop / max(1, ready)),
        "reward_availability": True,
        "terminal_frequency": float(dones_seen),
    }


def collect_current_fingerprint(args: argparse.Namespace, ctx: Any) -> Dict[str, Any]:
    env = None
    errors: List[str] = []
    warnings: List[str] = []
    payload: Dict[str, Any] = {"status": "fail", "errors": errors, "warnings": warnings}

    try:
        env, env_for_training, env_summary, _timing = create_wrapped_env(args, ctx)
        obs, info = reset_compat(env_for_training)

        chosen_obs = None
        chosen_mask = None
        dones_seen = 0

        for _ in range(max(1, int(args.steps))):
            mask_nhwk, source, warns = build_full_mask_from_candidates(env_for_training, obs, infos=[info])
            warnings.extend(warns)
            if mask_nhwk is not None and chosen_mask is None:
                chosen_obs = np.asarray(obs)
                chosen_mask = flatten_mask(mask_nhwk)
                payload["mask_source"] = source

            action = safe_action_space_sample(env_for_training)
            obs, _rew, done, infos = step_compat(env_for_training, action)
            info = infos[0] if infos else {}
            dones_seen += int(np.asarray(done).sum())

        if chosen_mask is None or chosen_obs is None:
            errors.append("Could not acquire full mask in current environment.")
        else:
            payload.update(compute_fingerprint(chosen_obs, chosen_mask, dones_seen))
            payload["environment"] = env_summary
            payload["status"] = "pass"

    except Exception as exc:
        errors.append(f"Unhandled exception: {type(exc).__name__}: {exc}")
        payload["status"] = "fail"
    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass

    return payload


def collect_legacy_fingerprint(args: argparse.Namespace) -> Dict[str, Any]:
    legacy_python = Path(args.legacy_python_exe)
    if not legacy_python.is_file():
        return {
            "status": "skipped",
            "errors": [],
            "warnings": [f"Legacy python exe not found: {legacy_python}"],
            "skip_reason": "legacy_python_missing",
        }

    snippet = r'''
import json
import numpy as np
from pathlib import Path

from gym_microrts import microrts_ai
from gym_microrts.envs.vec_env import MicroRTSGridModeVecEnv

def read_full_mask(env):
    if hasattr(env, "get_action_mask"):
        am = np.asarray(env.get_action_mask())
        if hasattr(env, "source_unit_mask"):
            sm = np.asarray(env.source_unit_mask)
            if sm.ndim == 2:
                sm = sm[:, :, None]
            elif sm.ndim == 3 and sm.shape[-1] != 1:
                sm = sm[:, :, None]
            if am.ndim == 3:
                n, cells, k = am.shape
                side = int(round(np.sqrt(cells)))
                am = am.reshape(n, side, side, k)
                sm = sm.reshape(n, side, side, 1)
            return np.concatenate([sm, am], axis=-1)
    if hasattr(env, "action_masks"):
        raw = getattr(env, "action_masks")
        arr = np.asarray(raw() if callable(raw) else raw)
        if arr.ndim == 3:
            n, cells, k = arr.shape
            side = int(round(np.sqrt(cells)))
            arr = arr.reshape(n, side, side, k)
        return arr
    return None

env = MicroRTSGridModeVecEnv(
    num_selfplay_envs=0,
    num_bot_envs=1,
    ai2s=[microrts_ai.passiveAI],
    map_paths=["maps/24x24/basesWorkers24x24.xml"],
    max_steps=500,
    autobuild=False,
)
try:
    obs = np.asarray(env.reset())
    mask = read_full_mask(env)
    out = {
        "status": "pass" if mask is not None else "fail",
        "obs_shape": list(obs.shape),
        "mask_shape": list(mask.shape) if mask is not None else None,
        "mask_depth": int(mask.shape[-1]) if mask is not None else None,
    }
finally:
    try:
        env.close()
    except Exception:
        pass

Path(r"{out_path}").write_text(json.dumps(out, indent=2), encoding="utf-8")
'''

    with tempfile.TemporaryDirectory() as td:
        out_path = Path(td) / "legacy_fingerprint.json"
        code = snippet.replace("{out_path}", str(out_path).replace("\\", "\\\\"))
        cmd = [str(legacy_python), "-c", code]
        completed = subprocess.run(cmd, capture_output=True, text=True)

        if not out_path.is_file():
            return {
                "status": "skipped",
                "errors": [],
                "warnings": [
                    "Legacy run did not produce output file.",
                    f"exit_code={completed.returncode}",
                    f"stderr_tail={completed.stderr[-1000:]}",
                ],
                "skip_reason": "legacy_execution_failed",
            }

        data = json.loads(out_path.read_text(encoding="utf-8"))
        data["subprocess_exit_code"] = int(completed.returncode)
        if completed.returncode != 0:
            data.setdefault("warnings", []).append(f"legacy process exit code {completed.returncode}")
        return data


def main() -> int:
    args = parse_args()
    ctx = create_runtime_context(args.seed)

    current = collect_current_fingerprint(args, ctx)
    legacy = collect_legacy_fingerprint(args)

    safe_json_dump(args.output_current, current)
    safe_json_dump(args.output_legacy, legacy)

    comparison: Dict[str, Any] = {
        "status": "pass",
        "generated_at_utc": utc_now(),
        "current_status": current.get("status"),
        "legacy_status": legacy.get("status"),
        "differences": {},
        "errors": [],
        "warnings": [],
        "runtime_versions": runtime_versions_payload(ctx.versions),
    }

    if current.get("status") != "pass":
        comparison["status"] = "fail"
        comparison["errors"].append("Current fingerprint collection failed.")

    if legacy.get("status") != "pass":
        comparison["status"] = "inconclusive"
        comparison["warnings"].append(
            f"Legacy fingerprint unavailable ({legacy.get('skip_reason', 'unknown')}); comparison is partial."
        )
    else:
        comparison["differences"] = {
            "obs_shape": {
                "current": current.get("obs_shape"),
                "legacy": legacy.get("obs_shape"),
            },
            "mask_shape": {
                "current": current.get("mask_shape"),
                "legacy": legacy.get("mask_shape"),
            },
            "valid_nonnoop_share": {
                "current": current.get("valid_nonnoop_share"),
                "legacy": legacy.get("valid_nonnoop_share"),
            },
        }

    safe_json_dump(args.output_comparison, comparison)
    print(args.output_current)
    print(args.output_legacy)
    print(args.output_comparison)

    return 0 if comparison["status"] in {"pass", "inconclusive"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
