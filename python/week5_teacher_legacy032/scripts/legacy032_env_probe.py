"""
legacy032_env_probe.py
======================
Stage 1 environment probe for gym_microrts==0.3.2 legacy teacher workspace.

This script collects runtime/environment information, instantiates a gym_microrts
environment, verifies observation/action/mask contracts, runs a short smoke episode,
and writes a structured JSON report.

It does NOT train, export, or modify any existing pipeline.

Usage:
    python python/week5_teacher_legacy032/scripts/legacy032_env_probe.py \
        --env-id MicrortsSelfPlayShapedReward-v1 \
        --map-path maps/24x24/basesWorkers24x24.xml \
        --steps 128 \
        --seed 17 \
        --output-json python/week5_teacher_legacy032/reports/legacy032_env_probe.json \
        --write-markdown-report

    # Quick run with defaults:
    python python/week5_teacher_legacy032/scripts/legacy032_env_probe.py

Run inside the activated .venv_microrts032_reference virtual environment.
JAVA_HOME must be set (e.g. Eclipse Temurin JDK 17).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPECTED_UNITY_V2_BRANCH_SIZES: List[int] = [6, 4, 4, 4, 4, 7, 49]
EXPECTED_CELLS_24X24: int = 576  # 24 * 24
EXPECTED_OBS_CHANNELS: int = 27

DEFAULT_ENV_ID   = "MicrortsSelfPlayShapedReward-v1"
DEFAULT_MAP_PATH = "maps/24x24/basesWorkers24x24.xml"
DEFAULT_STEPS    = 128
DEFAULT_SEED     = 17

SCRIPT_DIR = Path(__file__).resolve().parent
LEGACY032_ROOT = SCRIPT_DIR.parent
DEFAULT_OUTPUT_JSON = str(LEGACY032_ROOT / "reports" / "legacy032_env_probe.json")


# ---------------------------------------------------------------------------
# Helper: safe package version lookup
# ---------------------------------------------------------------------------

def _safe_version(module_name: str) -> str:
    try:
        import importlib.metadata
        return importlib.metadata.version(module_name)
    except Exception:
        pass
    try:
        mod = __import__(module_name)
        return getattr(mod, "__version__", "found_no_version")
    except Exception:
        return "NOT_INSTALLED"


def _safe_import_check(module_name: str) -> Tuple[bool, str]:
    """Returns (success, error_string_or_empty)."""
    try:
        __import__(module_name)
        return True, ""
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Helper: Java version
# ---------------------------------------------------------------------------

def _get_java_info() -> Dict[str, str]:
    java_home = os.environ.get("JAVA_HOME", "NOT_SET")
    java_ver  = "unknown"
    try:
        result = subprocess.run(
            ["java", "-version"],
            capture_output=True, text=True, timeout=8,
        )
        output = (result.stderr or result.stdout or "").strip()
        java_ver = output.split("\n")[0] if output else "empty_output"
    except FileNotFoundError:
        java_ver = "java_not_on_PATH"
    except Exception as exc:
        java_ver = f"error: {exc}"
    return {"JAVA_HOME": java_home, "java_version_string": java_ver}


# ---------------------------------------------------------------------------
# Helper: to_jsonable
# ---------------------------------------------------------------------------

def to_jsonable(value: Any) -> Any:
    """Recursively convert value to a JSON-serialisable form."""
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    # numpy arrays / scalars
    try:
        import numpy as np
        if isinstance(value, np.ndarray):
            return {"__ndarray__": True, "shape": list(value.shape),
                    "dtype": str(value.dtype), "preview": value.flatten()[:8].tolist()}
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            return float(value)
    except ImportError:
        pass
    return str(value)


# ---------------------------------------------------------------------------
# Helper: summarize_space
# ---------------------------------------------------------------------------

def summarize_space(space: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {"class": type(space).__name__, "repr": repr(space)}
    try:
        result["shape"] = list(space.shape)
    except Exception:
        pass
    try:
        import numpy as np
        result["nvec"] = space.nvec.tolist() if hasattr(space, "nvec") else None
    except Exception:
        result["nvec"] = None
    try:
        result["low"]  = to_jsonable(getattr(space, "low",  None))
        result["high"] = to_jsonable(getattr(space, "high", None))
    except Exception:
        pass
    return result


# ---------------------------------------------------------------------------
# Helper: summarize_observation
# ---------------------------------------------------------------------------

def summarize_observation(obs: Any) -> Dict[str, Any]:
    summary: Dict[str, Any] = {"type": type(obs).__name__}
    try:
        import numpy as np
        if isinstance(obs, np.ndarray):
            summary["shape"]   = list(obs.shape)
            summary["dtype"]   = str(obs.dtype)
            summary["min"]     = float(obs.min())
            summary["max"]     = float(obs.max())
            summary["mean"]    = float(obs.mean())
            summary["has_nan"] = bool(np.isnan(obs).any())
            summary["has_inf"] = bool(np.isinf(obs).any())
            flat = obs.flatten()
            summary["sha256_first512"] = hashlib.sha256(
                flat[:512].tobytes()).hexdigest()
        else:
            summary["value_repr"] = repr(obs)[:200]
    except Exception as exc:
        summary["error"] = str(exc)
    return summary


# ---------------------------------------------------------------------------
# Helper: summarize_action_space
# ---------------------------------------------------------------------------

def summarize_action_space(space: Any) -> Dict[str, Any]:
    base = summarize_space(space)
    try:
        nvec = space.nvec.tolist()
        base["nvec_length"] = len(nvec)
        layout = infer_branch_layout_from_nvec(nvec)
        base.update(layout)
    except Exception as exc:
        base["branch_layout_error"] = str(exc)
    return base


# ---------------------------------------------------------------------------
# Helper: infer_branch_layout_from_nvec
# ---------------------------------------------------------------------------

def infer_branch_layout_from_nvec(nvec: List[int]) -> Dict[str, Any]:
    """
    Infers per-cell branch layout from a flat MultiDiscrete nvec.

    gym_microrts 0.3.2 uses a GLOBAL SINGLE-ACTION format:
        nvec = [src_cell, action_type, move_dir, harvest_dir, return_dir,
                produce_dir, produce_unit_type, attack_target_cell]
        where src_cell = W*H (e.g. 576 for 24x24) and attack_target = W*H (global flat).

    This is an 8-element nvec, NOT a per-cell parallel format.

    Unity v2 uses per-cell parallel actions:
        nvec = [b0, b1, b2, b3, b4, b5, b6] * n_cells  (total length n_cells * 7)
        e.g. 576 * 7 = 4032 for 24x24.

    These two representations are structurally different and require the adapter
    pipeline to convert between them.
    """
    result: Dict[str, Any] = {
        "nvec_length": len(nvec),
        "action_representation": "UNKNOWN",
        "cells_detected": None,
        "branches_per_cell_detected": None,
        "action_branch_sizes": None,
        "action_branch_layout_uniform": None,
        "action_branch_layout_matches_unity_v2": False,
        "expected_unity_v2_branch_sizes": EXPECTED_UNITY_V2_BRANCH_SIZES,
    }

    if not nvec:
        result["error"] = "empty nvec"
        return result

    n = len(nvec)

    # --- Detection: gym_microrts 0.3.2 global single-action format ---
    # Format: [src_cell, 6 action branches, attack_target]  (8 total)
    # where src_cell == attack_target == n_cells (e.g. 576 for 24x24)
    if n == 8 and nvec[0] == nvec[7] and nvec[0] > 1:
        src_cell      = nvec[0]
        branches      = nvec[1:7]   # [action_type, move, harvest, return, produce_dir, produce_unit]
        attack_target = nvec[7]
        result["action_representation"] = "GYM_MICRORTS_032_GLOBAL_SINGLE_ACTION"
        result["cells_detected"]         = src_cell
        result["branches_per_cell_detected"] = None  # not per-cell
        result["action_branch_sizes"]    = list(nvec)
        result["global_action_src_cell_size"]  = src_cell
        result["global_action_per_step_branches"] = list(branches)
        result["global_action_attack_target_size"] = attack_target
        result["action_branch_layout_uniform"] = None  # not applicable
        result["action_branch_layout_matches_unity_v2"] = False
        result["action_representation_note"] = (
            "gym_microrts 0.3.2 uses a GLOBAL single-action per step: one src cell + "
            "6 action branches + one global attack target cell. This is structurally "
            "different from Unity v2's per-cell parallel MultiDiscrete (576 cells × 7 "
            "branches = 4032). Direct mapping is NOT possible without the adapter pipeline."
        )
        result["per_step_branch_names"] = [
            "src_cell_selector",
            "action_type",
            "move_dir",
            "harvest_dir",
            "return_dir",
            "produce_dir",
            "produce_unit_type",
            "attack_target_global",
        ]
        return result

    # --- Detection: Unity v2 / gridnet per-cell parallel format ---
    # Format: n_cells * branches_per_cell (e.g. 576 * 7 = 4032)
    for branches_per_cell in (7, 6, 8, 5):
        if n % branches_per_cell == 0:
            n_cells = n // branches_per_cell
            candidates_ok = n_cells in (
                EXPECTED_CELLS_24X24,  # 576
                256,  # 16x16
                100,  # 10x10
                64,   # 8x8
                32,
            ) or (n_cells > 0)

            if candidates_ok:
                cell_layouts = [
                    nvec[i * branches_per_cell:(i + 1) * branches_per_cell]
                    for i in range(n_cells)
                ]
                first_layout = cell_layouts[0]
                uniform = all(cl == first_layout for cl in cell_layouts)

                result["action_representation"]    = "PER_CELL_PARALLEL"
                result["cells_detected"]           = n_cells
                result["branches_per_cell_detected"] = branches_per_cell
                result["action_branch_sizes"]       = list(first_layout)
                result["action_branch_layout_uniform"] = uniform

                if not uniform:
                    result["action_branch_layout_note"] = (
                        "Non-uniform layout detected; first-cell layout reported above."
                    )

                result["action_branch_layout_matches_unity_v2"] = (
                    list(first_layout) == EXPECTED_UNITY_V2_BRANCH_SIZES
                )
                return result

    # Fallback
    result["action_branch_sizes"]  = nvec[:16]
    result["decomposition_failed"] = True
    result["note"] = (
        f"Could not decompose nvec (length {n}) into a known layout. "
        f"Raw first-16 values reported above."
    )
    return result


# ---------------------------------------------------------------------------
# Helper: safe env API wrappers
# ---------------------------------------------------------------------------

def safe_reset(env: Any) -> Tuple[Any, Optional[Dict]]:
    """Call env.reset() compatible with gym <0.26 and >=0.26 APIs."""
    try:
        result = env.reset()
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
            return result[0], result[1]
        return result, {}
    except Exception as exc:
        return None, {"reset_error": str(exc)}


def safe_step(env: Any, action: Any) -> Tuple[Any, float, bool, bool, Dict]:
    """Call env.step() compatible with gym <0.26 (4-tuple) and >=0.26 (5-tuple)."""
    try:
        result = env.step(action)
        if len(result) == 5:
            obs, reward, terminated, truncated, info = result
            done = terminated or truncated
        elif len(result) == 4:
            obs, reward, done, info = result
            terminated, truncated = done, False
        else:
            return None, 0.0, True, False, {"step_error": f"unexpected result length {len(result)}"}
        return obs, float(reward), bool(terminated), bool(truncated), info or {}
    except Exception as exc:
        return None, 0.0, True, False, {"step_error": str(exc)}


def safe_close(env: Any) -> None:
    try:
        env.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helper: try_get_action_mask
# ---------------------------------------------------------------------------

def try_get_action_mask(env: Any, info: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Attempts to retrieve action mask from the environment through multiple known APIs.
    Returns a summary dict; does NOT raise exceptions.
    """
    result: Dict[str, Any] = {
        "mask_available": False,
        "mask_source": None,
        "mask_shape": None,
        "mask_dtype": None,
        "mask_min": None,
        "mask_max": None,
        "mask_sum": None,
        "mask_has_nan": None,
        "mask_has_inf": None,
        "mask_warning": None,
        "attempts": [],
    }

    def _record_mask(mask: Any, source: str) -> bool:
        """Process a retrieved mask; returns True on success."""
        try:
            import numpy as np
            arr = np.asarray(mask)
            result["mask_available"] = True
            result["mask_source"]    = source
            result["mask_shape"]     = list(arr.shape)
            result["mask_dtype"]     = str(arr.dtype)
            result["mask_min"]       = float(arr.min())
            result["mask_max"]       = float(arr.max())
            result["mask_sum"]       = float(arr.sum())
            result["mask_has_nan"]   = bool(np.isnan(arr.astype(float)).any())
            result["mask_has_inf"]   = bool(np.isinf(arr.astype(float)).any())
            return True
        except Exception as exc:
            result["attempts"].append(f"{source} → parse error: {exc}")
            return False

    # Ordered attempts
    attempts = [
        ("env.get_action_mask()",         lambda: env.get_action_mask()),
        ("env.action_masks()",            lambda: env.action_masks()),
        ("env.get_action_masks()",        lambda: env.get_action_masks()),
        ("env.unwrapped.get_action_mask()",  lambda: env.unwrapped.get_action_mask()),
        ("env.unwrapped.action_masks()",     lambda: env.unwrapped.action_masks()),
    ]

    # info-based
    if info:
        for key in ("action_mask", "action_masks", "invalid_action_mask",
                    "valid_action_mask"):
            if key in info:
                attempts.append(
                    (f"info['{key}']", lambda k=key: info[k])
                )

    # Vectorized env (env.envs)
    try:
        if hasattr(env, "envs") and env.envs:
            inner = env.envs[0]
            attempts += [
                ("env.envs[0].get_action_mask()",    lambda: inner.get_action_mask()),
                ("env.envs[0].action_masks()",       lambda: inner.action_masks()),
                ("env.envs[0].unwrapped.get_action_mask()",
                 lambda: inner.unwrapped.get_action_mask()),
            ]
    except Exception:
        pass

    for source, fn in attempts:
        try:
            mask = fn()
            if mask is not None:
                if _record_mask(mask, source):
                    return result
                # else fall through
        except AttributeError:
            result["attempts"].append(f"{source} → AttributeError")
        except Exception as exc:
            result["attempts"].append(f"{source} → {type(exc).__name__}: {exc}")

    # None found
    result["mask_warning"] = (
        "Action mask was not found through known APIs; "
        "later training scripts must confirm mask path before teacher training."
    )
    return result


# ---------------------------------------------------------------------------
# Helper: sample masked action
# ---------------------------------------------------------------------------

def _sample_action(env: Any, mask_info: Dict[str, Any]) -> Tuple[Any, str]:
    """Return (action, method_used). Falls back to action_space.sample()."""
    method = "action_space.sample()"
    try:
        action = env.action_space.sample()
    except Exception:
        action = None
    return action, method


# ---------------------------------------------------------------------------
# Env creation with multiple fallback strategies
# ---------------------------------------------------------------------------

def try_create_env(env_id: str, map_path: Optional[str]) -> Tuple[Any, List[Dict]]:
    """
    Attempt env creation with various strategies.
    Returns (env_or_None, list_of_attempt_records).
    """
    import gym

    attempts: List[Dict] = []

    # Strategy 1: gym.make with map_path kwarg
    if map_path:
        try:
            env = gym.make(env_id, map_path=map_path)
            attempts.append({
                "strategy": "gym.make(env_id, map_path=map_path)",
                "status": "SUCCESS",
            })
            return env, attempts
        except Exception as exc:
            attempts.append({
                "strategy": "gym.make(env_id, map_path=map_path)",
                "status": "FAILED",
                "error": str(exc),
                "traceback": traceback.format_exc(),
            })

    # Strategy 2: gym.make without map_path
    try:
        env = gym.make(env_id)
        warning = None
        if map_path:
            warning = f"map_path='{map_path}' was not applied (env created without it)"
        attempts.append({
            "strategy": "gym.make(env_id)",
            "status": "SUCCESS",
            "warning": warning,
        })
        return env, attempts
    except Exception as exc:
        attempts.append({
            "strategy": "gym.make(env_id)",
            "status": "FAILED",
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })

    return None, attempts


# ---------------------------------------------------------------------------
# Attack target semantics probe
# ---------------------------------------------------------------------------

def probe_attack_target_semantics(
    nvec: Optional[List[int]],
    branch_sizes: Optional[List[int]],
    mask_info: Dict[str, Any],
    env: Any,
) -> Dict[str, Any]:
    """
    Probe attack target branch semantics as much as possible from available APIs.
    Does NOT make unsupported claims about local vs global target.

    Handles both:
      - gym_microrts 0.3.2 GLOBAL SINGLE-ACTION format:
            nvec = [src_cell, action_type, move_dir, harvest_dir, return_dir,
                    produce_dir, produce_unit_type, attack_target_global]   (len=8)
            attack_target is at index 7, size = n_cells (global flat)
      - Per-cell parallel format (Unity v2 / gridnet):
            nvec = [b0..b6] * n_cells  (len = n_cells * 7)
            attack_target is at branch index 6, size = 49 (local 7x7)
    """
    probe: Dict[str, Any] = {
        "note": (
            "gym_microrts==0.3.2 encodes attack_target as a GLOBAL flat index across all "
            "grid cells (e.g., 576 for a 24x24 map), NOT as a local 7x7 window. "
            "The Unity v2 contract uses a local 7x7 attack target (49 values). "
            "These representations are NOT directly compatible."
        ),
        "expected_unity_v2_attack_branch": 49,
        "observed_attack_branch_size": None,
        "observed_branch_matches_unity_v2_size": None,
        "semantic_parity_proven": False,
        "semantic_parity_note": (
            "Stage 1 env probe does not attempt to prove or disprove local/global "
            "target semantics. This requires Stage 6 adapter verification using "
            "actual action trajectories and spatial decoding."
        ),
        "target_encoding_hint": "UNKNOWN_FROM_PROBE",
        "target_encoding_source": None,
        "conclusion": None,
    }

    if not branch_sizes:
        probe["conclusion"] = (
            "Branch layout could not be determined; attack target semantics are unknown. "
            "Stage 6 adapter work is blocked until branch layout is confirmed."
        )
        return probe

    # Detect gym_microrts 0.3.2 global single-action format: len==8, nvec[0]==nvec[7]
    if len(branch_sizes) == 8 and branch_sizes[0] == branch_sizes[7] and branch_sizes[0] > 1:
        attack_size = branch_sizes[7]  # attack_target_global is at index 7
        probe["action_format"]                           = "GYM_MICRORTS_032_GLOBAL_SINGLE_ACTION"
        probe["attack_branch_index"]                     = 7
        probe["observed_attack_branch_size"]             = attack_size
        probe["observed_branch_matches_unity_v2_size"]   = (attack_size == 49)
        probe["target_encoding_hint"]                    = "BRANCH_SIZE_576_GLOBAL_FLAT"
        probe["conclusion"] = (
            f"gym_microrts 0.3.2 uses a GLOBAL single-action format. The attack_target at "
            f"nvec index 7 has size {attack_size} (global flat index over all {attack_size} "
            f"grid cells). This is STRUCTURALLY INCOMPATIBLE with Unity v2 local 7x7 (49). "
            f"The Stage 6 adapter must: (1) remap global flat index → local 7x7 relative "
            f"position, and (2) convert the entire single-action-per-step representation "
            f"to per-cell parallel actions. This is a non-trivial transformation."
        )
        return probe

    # Per-cell parallel format (len >= 7)
    if len(branch_sizes) >= 7:
        attack_size = branch_sizes[6]
        probe["action_format"]                           = "PER_CELL_PARALLEL"
        probe["attack_branch_index"]                     = 6
        probe["observed_attack_branch_size"]             = attack_size
        probe["observed_branch_matches_unity_v2_size"]   = (attack_size == 49)

        if attack_size == 49:
            probe["target_encoding_hint"] = "BRANCH_SIZE_49_MATCHES_UNITY_V2"
            probe["conclusion"] = (
                "Branch size 49 confirmed, but exact local/global target semantics were not "
                "proven by env probe. Stage 6 adapter must inspect raw action_t and "
                "actor-relative target decoding before assuming direct mapping. "
                "No direct semantic parity claim is made."
            )
        elif attack_size == EXPECTED_CELLS_24X24:
            probe["target_encoding_hint"] = "BRANCH_SIZE_576_GLOBAL_FLAT"
            probe["conclusion"] = (
                f"Branch size {attack_size} matches the full 24x24 grid cell count, "
                "indicating a GLOBAL flat attack target encoding (not local 7x7). "
                "A remap from global index to Unity v2 local 7x7 (49 values) is REQUIRED "
                "in the Stage 6 adapter. No direct mapping is possible without this remap."
            )
        else:
            probe["target_encoding_hint"] = f"BRANCH_SIZE_{attack_size}_UNEXPECTED"
            probe["conclusion"] = (
                f"Observed attack branch size {attack_size} does not match either the "
                f"expected Unity v2 (49) or global 24x24 (576) encoding. "
                "Manual inspection required before Stage 6 adapter work."
            )
        return probe

    probe["conclusion"] = (
        "branch_sizes length < 7; attack target semantics undetermined. "
        "Stage 6 adapter work is blocked until branch layout is confirmed."
    )

    # Try to find any hints in env attributes
    for attr in ("attack_range", "map_size", "height", "width", "num_grid_params"):
        try:
            val = getattr(env, attr, None)
            if val is None:
                try:
                    val = getattr(env.unwrapped, attr, None)
                except Exception:
                    pass
            if val is not None:
                probe[f"env_attr_{attr}"] = to_jsonable(val)
        except Exception:
            pass

    return probe


# ---------------------------------------------------------------------------
# Main probe
# ---------------------------------------------------------------------------

def run_probe(args: argparse.Namespace) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "schema_version": "1.0",
        "probe_script":   "legacy032_env_probe.py",
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "args": {
            "env_id":                  args.env_id,
            "map_path":                args.map_path,
            "steps":                   args.steps,
            "seed":                    args.seed,
            "allow_random_actions":    args.allow_random_actions,
            "allow_mask_random_actions": args.allow_mask_random_actions,
        },
        "system": {},
        "package_versions": {},
        "import_errors": {},
        "java": {},
        "gym_microrts_version": None,
        "env_creation": {
            "status": "NOT_ATTEMPTED",
            "env_id_used": args.env_id,
            "map_path_used": args.map_path,
            "attempts": [],
        },
        "observation_space": None,
        "observation_probe": None,
        "action_space": None,
        "action_contract": None,
        "mask_probe": None,
        "smoke_run": None,
        "attack_target_semantics_probe": None,
        "warnings": [],
        "errors": [],
        "overall_status": "UNKNOWN",
    }

    # ------------------------------------------------------------------
    # 1. System info
    # ------------------------------------------------------------------
    report["system"] = {
        "os":           platform.system(),
        "platform":     platform.platform(),
        "python_version": sys.version,
        "executable":   sys.executable,
        "virtual_env":  os.environ.get("VIRTUAL_ENV", "NOT_SET"),
        "cwd":          os.getcwd(),
    }

    # ------------------------------------------------------------------
    # 2. Package versions
    # ------------------------------------------------------------------
    packages = [
        ("gym",                "gym"),
        ("gym_microrts",       "gym-microrts"),
        ("gym_microrts_alt",   "gym_microrts"),
        ("torch",              "torch"),
        ("numpy",              "numpy"),
        ("stable_baselines3",  "stable-baselines3"),
        ("stable_baselines",   "stable-baselines"),
        ("sb3_contrib",        "sb3-contrib"),
        ("JPype1",             "JPype1"),
        ("wandb",              "wandb"),
    ]
    for attr_name, pkg_name in packages:
        ver = _safe_version(pkg_name)
        report["package_versions"][attr_name] = ver

    # Confirm gym_microrts version
    gm_ver = report["package_versions"]["gym_microrts"]
    if gm_ver == "NOT_INSTALLED":
        gm_ver = report["package_versions"]["gym_microrts_alt"]
    report["gym_microrts_version"] = gm_ver if gm_ver != "NOT_INSTALLED" else None

    if report["gym_microrts_version"] != "0.3.2":
        report["warnings"].append(
            f"gym_microrts version is '{report['gym_microrts_version']}', "
            f"expected '0.3.2'. Results may not reflect legacy032 environment."
        )

    # Import checks
    for mod in ("gym_microrts", "torch", "numpy", "stable_baselines3"):
        ok, err = _safe_import_check(mod)
        if not ok:
            report["import_errors"][mod] = err

    # ------------------------------------------------------------------
    # 3. Java
    # ------------------------------------------------------------------
    report["java"] = _get_java_info()
    if "NOT_SET" in report["java"]["JAVA_HOME"] or "not_on_PATH" in report["java"]["java_version_string"]:
        report["warnings"].append(
            "JAVA_HOME is not set or java is not on PATH. "
            "gym_microrts requires a JDK installation with JAVA_HOME configured."
        )

    # ------------------------------------------------------------------
    # 4. Import gym_microrts
    # ------------------------------------------------------------------
    print("[1] Importing gym_microrts ...")
    gm_import_ok, gm_import_err = _safe_import_check("gym_microrts")
    if not gm_import_ok:
        report["errors"].append(f"gym_microrts import failed: {gm_import_err}")
        report["overall_status"] = "FAIL_IMPORT"
        report["env_creation"]["status"] = "SKIPPED_IMPORT_FAILED"
        print(f"    FAILED: {gm_import_err}")
        return report
    print("    OK")

    # ------------------------------------------------------------------
    # 5. Register gym_microrts envs
    # ------------------------------------------------------------------
    print("[2] Importing gym (triggers gym_microrts registration) ...")
    try:
        import gym
        import gym_microrts  # noqa: F401
        # Trigger registration if needed
        try:
            from gym_microrts import envs as _gm_envs  # noqa: F401
        except Exception:
            pass
        registered = [
            spec.id for spec in gym.envs.registry.all()
            if "microrts" in spec.id.lower() or "Microrts" in spec.id
        ]
        report["registered_microrts_envs"] = registered[:30]  # cap for json size
        print(f"    OK — {len(registered)} microrts env(s) registered")
    except Exception as exc:
        report["errors"].append(f"gym registration: {exc}")
        print(f"    WARNING: {exc}")

    # ------------------------------------------------------------------
    # 6. Create env
    # ------------------------------------------------------------------
    print(f"[3] Creating env '{args.env_id}' ...")
    env, creation_attempts = try_create_env(args.env_id, args.map_path)
    report["env_creation"]["attempts"] = creation_attempts

    if env is None:
        report["env_creation"]["status"] = "FAILED"
        report["errors"].append(f"Could not create env '{args.env_id}'")
        report["overall_status"] = "FAIL_ENV_CREATION"
        print(f"    FAILED — see env_creation.attempts in report")
        return report

    report["env_creation"]["status"] = "SUCCESS"
    print("    OK")

    # ------------------------------------------------------------------
    # 7. Seed
    # ------------------------------------------------------------------
    if args.seed is not None:
        try:
            env.seed(args.seed)
        except AttributeError:
            try:
                env.reset(seed=args.seed)
            except Exception:
                pass
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 8. Observation space
    # ------------------------------------------------------------------
    print("[4] Probing observation space ...")
    try:
        obs_space = env.observation_space
        report["observation_space"] = summarize_space(obs_space)
        obs_shape = list(obs_space.shape) if hasattr(obs_space, "shape") else None
        print(f"    shape={obs_shape}")
        if obs_shape and obs_shape[-1] != EXPECTED_OBS_CHANNELS:
            report["warnings"].append(
                f"Observation last-dim={obs_shape[-1]} != expected {EXPECTED_OBS_CHANNELS}. "
                f"Channel layout may differ from Unity observation contract."
            )
    except Exception as exc:
        report["errors"].append(f"observation_space probe: {exc}")
        print(f"    ERROR: {exc}")

    # ------------------------------------------------------------------
    # 9. Action space
    # ------------------------------------------------------------------
    print("[5] Probing action space ...")
    try:
        act_space = env.action_space
        report["action_space"]   = summarize_space(act_space)
        report["action_contract"] = summarize_action_space(act_space)
        branch_sizes = report["action_contract"].get("action_branch_sizes")
        print(f"    nvec_length={report['action_contract'].get('nvec_length')}")
        print(f"    cells={report['action_contract'].get('cells_detected')}")
        print(f"    branch_sizes={branch_sizes}")
        matches = report["action_contract"].get("action_branch_layout_matches_unity_v2")
        print(f"    matches Unity v2 {EXPECTED_UNITY_V2_BRANCH_SIZES}: {matches}")
        if not matches:
            report["warnings"].append(
                f"Action branch layout {branch_sizes} does not match "
                f"Unity v2 contract {EXPECTED_UNITY_V2_BRANCH_SIZES}. "
                f"Adapter will be required."
            )
    except Exception as exc:
        report["errors"].append(f"action_space probe: {exc}")
        print(f"    ERROR: {exc}")
        branch_sizes = None
    else:
        action_repr = report["action_contract"].get("action_representation", "UNKNOWN")
        print(f"    action_representation={action_repr}")
        if action_repr == "GYM_MICRORTS_032_GLOBAL_SINGLE_ACTION":
            print(f"    NOTE: single-action-per-step format; per-cell parallel adapter required for Unity v2")

    # ------------------------------------------------------------------
    # 10. Reset and initial mask
    # ------------------------------------------------------------------
    print("[6] Resetting env ...")
    obs, info = safe_reset(env)
    if obs is None:
        report["errors"].append("env.reset() returned None observation")
        safe_close(env)
        report["overall_status"] = "FAIL_RESET"
        return report

    report["observation_probe"] = summarize_observation(obs)
    print(f"    obs shape: {report['observation_probe'].get('shape')}")

    # Mask probe after reset
    print("[7] Probing action mask ...")
    mask_info = try_get_action_mask(env, info)
    report["mask_probe"] = mask_info
    if mask_info["mask_available"]:
        print(f"    mask_available=True  source={mask_info['mask_source']}  shape={mask_info['mask_shape']}")
    else:
        print(f"    mask_available=False  warning={mask_info.get('mask_warning')}")
        report["warnings"].append(mask_info.get("mask_warning", "mask not found"))

    # ------------------------------------------------------------------
    # 11. Attack target semantics
    # ------------------------------------------------------------------
    print("[8] Probing attack target semantics ...")
    nvec = None
    try:
        nvec = env.action_space.nvec.tolist()
    except Exception:
        pass
    report["attack_target_semantics_probe"] = probe_attack_target_semantics(
        nvec, branch_sizes, mask_info, env
    )
    print(f"    hint: {report['attack_target_semantics_probe'].get('target_encoding_hint')}")

    # ------------------------------------------------------------------
    # 12. Smoke run
    # ------------------------------------------------------------------
    print(f"[9] Running smoke episode ({args.steps} steps) ...")
    smoke: Dict[str, Any] = {
        "smoke_steps_requested":  args.steps,
        "smoke_steps_executed":   0,
        "smoke_done_reached":     False,
        "terminal_type":          None,
        "total_reward":           0.0,
        "reward_mean":            None,
        "action_method_used":     None,
        "step_summaries":         [],
        "error":                  None,
    }
    try:
        rewards = []
        for step_i in range(args.steps):
            action, method = _sample_action(env, mask_info)
            smoke["action_method_used"] = method

            obs2, reward, terminated, truncated, step_info = safe_step(env, action)

            # Update mask on each step if possible
            step_mask = try_get_action_mask(env, step_info)

            step_summary = {
                "step_id":                step_i,
                "reward":                 reward,
                "terminated":             terminated,
                "truncated":              truncated,
                "obs_shape":              list(obs2.shape) if hasattr(obs2, "shape") else None,
                "info_keys":              list(step_info.keys()) if step_info else [],
                "mask_available_on_step": step_mask["mask_available"],
            }
            smoke["step_summaries"].append(step_summary)
            rewards.append(reward)
            smoke["smoke_steps_executed"] += 1

            if terminated or truncated:
                smoke["smoke_done_reached"] = True
                smoke["terminal_type"] = "terminated" if terminated else "truncated"
                break

        smoke["total_reward"] = float(sum(rewards))
        smoke["reward_mean"]  = float(sum(rewards) / len(rewards)) if rewards else None
        print(f"    steps_executed={smoke['smoke_steps_executed']}  "
              f"done={smoke['smoke_done_reached']}  "
              f"total_reward={smoke['total_reward']:.3f}")
    except Exception as exc:
        smoke["error"] = str(exc)
        smoke["traceback"] = traceback.format_exc()
        report["errors"].append(f"smoke run error: {exc}")
        print(f"    ERROR: {exc}")

    # Keep step_summaries reasonable in JSON (cap at 20)
    smoke["step_summaries_truncated"] = len(smoke["step_summaries"]) > 20
    smoke["step_summaries"] = smoke["step_summaries"][:20]
    report["smoke_run"] = smoke

    safe_close(env)
    print("[10] Env closed.")

    # ------------------------------------------------------------------
    # 13. Overall status
    # ------------------------------------------------------------------
    errors = report["errors"]
    if errors:
        report["overall_status"] = "FAIL"
    elif not report["mask_probe"]["mask_available"]:
        report["overall_status"] = "PASS_WITH_WARNINGS"
    elif smoke["error"]:
        report["overall_status"] = "PASS_WITH_WARNINGS"
    else:
        report["overall_status"] = "PASS"

    return report


# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------

def write_json(report: Dict[str, Any], path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=to_jsonable), encoding="utf-8")
    print(f"\nJSON report written: {out}")


def write_markdown_report(report: Dict[str, Any], json_path: str) -> None:
    """Write a companion Markdown summary next to the JSON file."""
    md_path = Path(json_path).with_suffix(".md")

    ts          = report.get("timestamp", "?")
    status      = report.get("overall_status", "?")
    sys_info    = report.get("system", {})
    versions    = report.get("package_versions", {})
    java_info   = report.get("java", {})
    env_cr      = report.get("env_creation", {})
    obs_probe   = report.get("observation_probe") or {}
    act_c       = report.get("action_contract") or {}
    mask_p      = report.get("mask_probe") or {}
    smoke       = report.get("smoke_run") or {}
    atk         = report.get("attack_target_semantics_probe") or {}
    warnings    = report.get("warnings", [])
    errors      = report.get("errors", [])

    branch_sizes = act_c.get("action_branch_sizes")
    matches_v2   = act_c.get("action_branch_layout_matches_unity_v2")

    # Stage 2 readiness decision
    if env_cr.get("status") != "SUCCESS":
        readiness = "BLOCKED_ENV_CREATION_FAILED"
    elif branch_sizes and list(branch_sizes) != EXPECTED_UNITY_V2_BRANCH_SIZES:
        # Different branch sizes don't necessarily block; may need adapter
        readiness = "INCONCLUSIVE_NEEDS_MANUAL_CHECK"
    elif not mask_p.get("mask_available"):
        readiness = "INCONCLUSIVE_NEEDS_MANUAL_CHECK"
    elif smoke.get("error"):
        readiness = "INCONCLUSIVE_NEEDS_MANUAL_CHECK"
    elif errors:
        readiness = "INCONCLUSIVE_NEEDS_MANUAL_CHECK"
    else:
        readiness = "READY_FOR_STAGE2_SMOKE_TRAINING"

    lines = [
        "# Legacy032 Stage 1 — Environment Probe Report",
        "",
        f"**Date**: {ts}  ",
        f"**Overall status**: `{status}`  ",
        f"**Stage 2 readiness**: `{readiness}`",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"| Item | Value |",
        f"|------|-------|",
        f"| gym_microrts | {report.get('gym_microrts_version')} |",
        f"| Python | {sys_info.get('python_version', '?').split()[0]} |",
        f"| Platform | {sys_info.get('platform', '?')} |",
        f"| Java | {java_info.get('java_version_string', '?')} |",
        f"| Env created | {env_cr.get('status')} |",
        f"| Obs shape | {obs_probe.get('shape')} |",
        f"| Branch sizes | {branch_sizes} |",
        f"| Matches Unity v2 | {matches_v2} |",
        f"| Mask available | {mask_p.get('mask_available')} |",
        f"| Smoke steps | {smoke.get('smoke_steps_executed')}/{smoke.get('smoke_steps_requested')} |",
        f"| Smoke error | {smoke.get('error')} |",
        "",
        "---",
        "",
        "## Package versions",
        "",
        "| Package | Version |",
        "|---------|---------|",
    ]
    for k, v in versions.items():
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "## Environment creation",
        "",
        f"- env_id: `{env_cr.get('env_id_used')}`",
        f"- map_path: `{env_cr.get('map_path_used')}`",
        f"- status: **{env_cr.get('status')}**",
        "",
    ]
    for attempt in env_cr.get("attempts", []):
        s = attempt.get("status")
        strat = attempt.get("strategy")
        err = attempt.get("error", "")
        warn = attempt.get("warning", "")
        lines.append(f"  - `{strat}` → **{s}**" + (f" — {err}" if err else "") + (f" ⚠️ {warn}" if warn else ""))

    lines += [
        "",
        "## Observation contract",
        "",
        f"| Item | Value |",
        f"|------|-------|",
        f"| shape | {obs_probe.get('shape')} |",
        f"| dtype | {obs_probe.get('dtype')} |",
        f"| min/max | {obs_probe.get('min'):.4f} / {obs_probe.get('max'):.4f}" if obs_probe.get("min") is not None else "| min/max | N/A |",
        f"| has_nan | {obs_probe.get('has_nan')} |",
        f"| has_inf | {obs_probe.get('has_inf')} |",
        "",
        "## Action contract",
        "",
        f"| Item | Value |",
        f"|------|-------|",
        f"| nvec_length | {act_c.get('nvec_length')} |",
        f"| cells_detected | {act_c.get('cells_detected')} |",
        f"| branches_per_cell | {act_c.get('branches_per_cell_detected')} |",
        f"| branch_sizes | `{branch_sizes}` |",
        f"| uniform | {act_c.get('action_branch_layout_uniform')} |",
        f"| matches Unity v2 `[6,4,4,4,4,7,49]` | **{matches_v2}** |",
        "",
        "## Action mask",
        "",
        f"| Item | Value |",
        f"|------|-------|",
        f"| mask_available | **{mask_p.get('mask_available')}** |",
        f"| mask_source | {mask_p.get('mask_source')} |",
        f"| mask_shape | {mask_p.get('mask_shape')} |",
        f"| mask_dtype | {mask_p.get('mask_dtype')} |",
        f"| mask_sum | {mask_p.get('mask_sum')} |",
    ]
    if mask_p.get("mask_warning"):
        lines += ["", f"> ⚠️ {mask_p['mask_warning']}", ""]

    lines += [
        "",
        "## Runtime smoke",
        "",
        f"| Item | Value |",
        f"|------|-------|",
        f"| steps requested | {smoke.get('smoke_steps_requested')} |",
        f"| steps executed | {smoke.get('smoke_steps_executed')} |",
        f"| done reached | {smoke.get('smoke_done_reached')} |",
        f"| total reward | {smoke.get('total_reward')} |",
        f"| action method | {smoke.get('action_method_used')} |",
        f"| error | {smoke.get('error')} |",
        "",
        "## Attack target semantics",
        "",
        f"> **{atk.get('conclusion', 'No conclusion available.')}**",
        "",
        f"| Item | Value |",
        f"|------|-------|",
        f"| observed attack branch size | {atk.get('observed_attack_branch_size')} |",
        f"| matches Unity v2 size (49) | {atk.get('observed_branch_matches_unity_v2_size')} |",
        f"| encoding hint | `{atk.get('target_encoding_hint')}` |",
        f"| semantic_parity_proven | **{atk.get('semantic_parity_proven')}** |",
        "",
        "> Note: Unity v2 uses local 7×7 attack target (49 values).",
        "> gym_microrts 0.3.2 may use global flat target.",
        "> Stage 6 adapter must verify this before assuming direct mapping.",
        "",
        "## Compatibility with Unity v2",
        "",
    ]

    if matches_v2:
        lines.append(
            "Branch sizes match Unity v2 contract `[6,4,4,4,4,7,49]`. "
            "However, **semantic parity is not proven** — attack target encoding "
            "must be confirmed in Stage 6 adapter work."
        )
    else:
        lines += [
            f"Branch sizes `{branch_sizes}` differ from Unity v2 `[6,4,4,4,4,7,49]`.",
            "The adapter pipeline is required to convert teacher trajectories.",
            "If the attack branch is 576 (global flat), remap to local 7x7 is needed.",
        ]

    if warnings:
        lines += ["", "## Warnings", ""]
        for w in warnings:
            lines.append(f"- ⚠️ {w}")

    if errors:
        lines += ["", "## Errors", ""]
        for e in errors:
            lines.append(f"- ❌ {e}")

    lines += [
        "",
        "## Known gaps",
        "",
        "- Attack target semantics (local vs global) not proven at Stage 1",
        "- `validate_adapted_dataset.py` still has hardcoded v1 contract — must be migrated at Stage 7",
        "- `build_bc_ready_dataset_day6.py` still has hardcoded v1 contract — must be migrated at Stage 7",
        "- Adapter `adapt_teacher_dataset.py` default is `v1_mvp`; must use `--target-action-contract v2_gridnet_compatible`",
        "",
        "## Stage 2 readiness decision",
        "",
        f"**`{readiness}`**",
        "",
    ]

    if readiness == "READY_FOR_STAGE2_SMOKE_TRAINING":
        lines += [
            "Env creates successfully, observation confirmed, action branch layout determined, ",
            "smoke run passed. Proceed to Stage 2 smoke training.",
        ]
    elif readiness == "BLOCKED_ENV_CREATION_FAILED":
        lines += [
            "Env creation failed. Cannot proceed to Stage 2 until env is confirmed working.",
            "Check Java installation, JAVA_HOME, and gym_microrts registration.",
        ]
    else:
        lines += [
            "Manual verification required before Stage 2. Check warnings and errors above.",
        ]

    lines += [
        "",
        f"---",
        "",
        f"Full JSON report: `{json_path}`",
    ]

    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Markdown report written: {md_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage 1 environment probe for gym_microrts==0.3.2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--env-id",
        default=DEFAULT_ENV_ID,
        help=f"gym env id to probe (default: {DEFAULT_ENV_ID})",
    )
    parser.add_argument(
        "--map-path",
        default=DEFAULT_MAP_PATH,
        help=f"map path passed to env (default: {DEFAULT_MAP_PATH})",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=DEFAULT_STEPS,
        help=f"number of steps for smoke run (default: {DEFAULT_STEPS})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"random seed (default: {DEFAULT_SEED})",
    )
    parser.add_argument(
        "--output-json",
        default=DEFAULT_OUTPUT_JSON,
        help="path to write JSON report",
    )
    parser.add_argument(
        "--write-markdown-report",
        action="store_true",
        default=True,
        help="also write a companion .md report (default: True)",
    )
    parser.add_argument(
        "--no-markdown-report",
        dest="write_markdown_report",
        action="store_false",
    )
    parser.add_argument(
        "--allow-random-actions",
        action="store_true",
        default=True,
        help="use action_space.sample() for smoke run (default: True)",
    )
    parser.add_argument(
        "--allow-mask-random-actions",
        action="store_true",
        default=False,
        help="attempt mask-aware sampling for smoke run (default: False)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = parse_args()

    print("=" * 65)
    print("  legacy032_env_probe.py — Stage 1 Environment Probe")
    print(f"  gym_microrts==0.3.2 legacy teacher workspace")
    print("=" * 65)

    report = run_probe(args)

    write_json(report, args.output_json)
    if args.write_markdown_report:
        write_markdown_report(report, args.output_json)

    print()
    print(f"Overall status: {report['overall_status']}")
    if report["warnings"]:
        print(f"Warnings ({len(report['warnings'])}):")
        for w in report["warnings"]:
            print(f"  ⚠  {w}")
    if report["errors"]:
        print(f"Errors ({len(report['errors'])}):")
        for e in report["errors"]:
            print(f"  ✗  {e}")
