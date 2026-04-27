"""
verify_reference_env.py
=======================
Verifies that the gym-microrts 0.3.2 reference environment is correctly set up.

Run inside the activated .venv_microrts032_reference:
    python python/week5_teacher_reference/scripts/verify_reference_env.py

Outputs:
    python/week5_teacher_reference/artifacts/reference_env_verify.json
    python/week5_teacher_reference/artifacts/reference_env_verify.md

This is a REFERENCE CHECK only — not a Unity parity check.
"""

import sys
import os
import json
import platform
import subprocess
import traceback
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR   = Path(__file__).resolve().parent
REF_ROOT     = SCRIPT_DIR.parent
ARTIFACTS    = REF_ROOT / "artifacts"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

VERIFY_JSON = ARTIFACTS / "reference_env_verify.json"
VERIFY_MD   = ARTIFACTS / "reference_env_verify.md"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def safe_version(module_name: str) -> str:
    try:
        import importlib.metadata
        return importlib.metadata.version(module_name)
    except Exception:
        pass
    try:
        mod = __import__(module_name)
        return getattr(mod, "__version__", "unknown")
    except Exception:
        return "NOT_INSTALLED"


def get_java_info() -> dict:
    java_home = os.environ.get("JAVA_HOME", "")
    java_ver  = "unknown"
    try:
        result = subprocess.run(
            ["java", "-version"],
            capture_output=True, text=True, timeout=5
        )
        output = result.stderr or result.stdout
        java_ver = output.strip().split("\n")[0] if output.strip() else "error"
    except Exception as e:
        java_ver = f"error: {e}"
    return {"JAVA_HOME": java_home or "NOT_SET", "java_version_string": java_ver}


def check_obs_surface(obs_shape) -> str:
    if obs_shape and obs_shape[-1] == 27:
        return "FULL_OBS_27_CHANNEL"
    elif obs_shape and obs_shape[-1] == 29:
        return "PARTIAL_OR_WALL_29_CHANNEL"
    else:
        return f"WARNING_UNKNOWN_SURFACE (shape={obs_shape})"


# ---------------------------------------------------------------------------
# Main verification
# ---------------------------------------------------------------------------
def main():
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "virtual_env": os.environ.get("VIRTUAL_ENV", "NOT_SET"),
        "versions": {},
        "java": {},
        "gym_microrts_import": "NOT_TESTED",
        "env_create": "NOT_TESTED",
        "observation_space": None,
        "action_space": None,
        "obs_surface_check": "NOT_TESTED",
        "exact_reference_pins": False,
        "compatibility_fallback_used": False,
        "notes": [],
        "errors": [],
        "overall_status": "UNKNOWN",
    }

    print("=" * 60)
    print("  Reference Environment Verification")
    print("  gym-microrts 0.3.2 reference recipe")
    print("=" * 60)
    print(f"Python     : {sys.version}")
    print(f"Platform   : {platform.platform()}")
    print(f"VIRTUAL_ENV: {os.environ.get('VIRTUAL_ENV', 'NOT_SET')}")
    print()

    # -- Version checks -------------------------------------------------------
    packages = ["gym", "gym_microrts", "stable_baselines3", "torch", "numpy",
                "JPype1", "wandb"]
    for pkg in packages:
        ver = safe_version(pkg)
        report["versions"][pkg] = ver
        status = "OK" if ver not in ("NOT_INSTALLED",) else "MISSING"
        print(f"  {pkg:<25} {ver:<20} [{status}]")

    print()

    # -- Java check -----------------------------------------------------------
    java_info = get_java_info()
    report["java"] = java_info
    print(f"  JAVA_HOME : {java_info['JAVA_HOME']}")
    print(f"  java      : {java_info['java_version_string']}")
    print()

    # -- gym_microrts import --------------------------------------------------
    print("[1] Testing import gym_microrts ...")
    try:
        import gym_microrts  # noqa: F401
        report["gym_microrts_import"] = "OK"
        print("    OK")
    except Exception as e:
        msg = f"FAIL: {e}"
        report["gym_microrts_import"] = msg
        report["errors"].append(f"gym_microrts import: {msg}")
        print(f"    {msg}")
        print("    Hint: JDK must be installed and JAVA_HOME must be set.")

    # -- env create -----------------------------------------------------------
    print("[2] Creating gym-microrts environment ...")
    obs_shape   = None
    act_shape   = None
    env_created = False
    try:
        import gym  # noqa: F401
        candidate_env_ids = [
            "MicrortsMining-v0",
            "MicrortsMining-v1",
            "MicrortsMining-v2",
            "MicrortsMining-v3",
            "MicrortsMining-v4",
        ]
        last_error = None
        for env_id in candidate_env_ids:
            try:
                env = gym.make(env_id)
                obs_shape = list(env.observation_space.shape)
                act_shape = str(env.action_space)
                env.close()
                env_created = True
                report["env_create"] = f"OK (env_id={env_id})"
                report["observation_space"] = obs_shape
                report["action_space"] = act_shape
                print(f"    OK  env_id={env_id}  obs_shape={obs_shape}  action_space={act_shape}")
                break
            except Exception as e:
                last_error = e
        if not env_created:
            raise RuntimeError(last_error)
    except Exception as e:
        tb = traceback.format_exc()
        msg = f"FAIL: {e}"
        report["env_create"] = msg
        report["errors"].append(f"env_create: {msg}")
        print(f"    {msg}")
        print("    Hint: Verify JDK, JPype1, and gym-microrts==0.3.2 are installed.")
        # Try fallback env id
        if not env_created:
            try:
                import gym_microrts  # noqa: F401
                # Try alternate env names from v0.3.2
                for env_id in [
                    "MicrortsMining-v0",
                    "MicroRTSMining-v0",
                    "Microrts-v0",
                ]:
                    try:
                        import gym as _gym
                        env = _gym.make(env_id)
                        obs_shape = list(env.observation_space.shape)
                        act_shape = str(env.action_space)
                        env.close()
                        report["env_create"] = f"OK (fallback env_id={env_id})"
                        report["observation_space"] = obs_shape
                        report["action_space"] = act_shape
                        print(f"    Fallback OK: env_id={env_id}  obs={obs_shape}")
                        env_created = True
                        break
                    except Exception:
                        continue
            except Exception:
                pass

    # -- obs surface check ----------------------------------------------------
    if obs_shape is not None:
        surface = check_obs_surface(obs_shape)
        report["obs_surface_check"] = surface
        print(f"[3] Observation surface: {surface}")
    else:
        report["obs_surface_check"] = "SKIPPED (env not created)"
        print("[3] Observation surface: SKIPPED")

    # -- List registered gym-microrts envs ------------------------------------
    print("[4] Listing gym-microrts registered environments ...")
    try:
        import gym as _gym
        microrts_envs = [
            spec.id for spec in _gym.envs.registry.all()
            if "icrort" in spec.id.lower() or "micrort" in spec.id.lower()
        ]
        report["registered_microrts_envs"] = microrts_envs
        print(f"    Found {len(microrts_envs)} envs: {microrts_envs[:10]}")
    except Exception as e:
        report["registered_microrts_envs"] = f"error: {e}"
        print(f"    error: {e}")

    # -- Overall status -------------------------------------------------------
    numpy_ver = report["versions"].get("numpy", "NOT_INSTALLED")
    torch_ver = report["versions"].get("torch", "NOT_INSTALLED")

    torch_exact = isinstance(torch_ver, str) and torch_ver.startswith("1.8.0")
    numpy_exact = (numpy_ver == "1.19.2")
    exact_reference = bool(numpy_exact and torch_exact)

    report["exact_reference_pins"] = exact_reference

    if numpy_ver == "NOT_INSTALLED" or torch_ver == "NOT_INSTALLED":
        report["compatibility_fallback_used"] = False
        report["notes"].append(
            "Cannot determine compatibility fallback status because numpy or torch is not installed."
        )
    else:
        report["compatibility_fallback_used"] = not exact_reference
        if report["compatibility_fallback_used"]:
            report["notes"].append(
                "Compatibility fallback detected: numpy != 1.19.2 or torch does not start with 1.8.0."
            )
        else:
            report["notes"].append("Exact reference pins detected for numpy and torch.")

    critical_ok = (
        report["gym_microrts_import"] == "OK"
        and env_created
    )
    report["overall_status"] = "PASS" if critical_ok else "FAIL"

    print()
    print(f"Exact reference pins        : {report['exact_reference_pins']}")
    print(f"Compatibility fallback used : {report['compatibility_fallback_used']}")
    if report["notes"]:
        for note in report["notes"]:
            print(f"Note: {note}")
    print()
    print(f"Overall status: {report['overall_status']}")
    print()

    # -- Save JSON ------------------------------------------------------------
    with open(VERIFY_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"JSON report saved: {VERIFY_JSON}")

    # -- Save Markdown --------------------------------------------------------
    lines = [
        "# Reference Environment Verification Report",
        "",
        f"**Date**: {report['timestamp']}",
        f"**Python**: {sys.version}",
        f"**Platform**: {platform.platform()}",
        f"**VIRTUAL_ENV**: {report['virtual_env']}",
        "",
        "## Package Versions",
        "",
        "| Package | Version |",
        "|---------|---------|",
    ]
    for pkg, ver in report["versions"].items():
        lines.append(f"| {pkg} | {ver} |")
    lines += [
        "",
        "## Java",
        "",
        f"- JAVA_HOME: `{java_info['JAVA_HOME']}`",
        f"- java version string: `{java_info['java_version_string']}`",
        "",
        "## Checks",
        "",
        f"- gym_microrts import: `{report['gym_microrts_import']}`",
        f"- env create: `{report['env_create']}`",
        f"- observation_space shape: `{report['observation_space']}`",
        f"- action_space: `{report['action_space']}`",
        f"- obs surface check: `{report['obs_surface_check']}`",
        f"- exact_reference_pins: `{report['exact_reference_pins']}`",
        f"- compatibility_fallback_used: `{report['compatibility_fallback_used']}`",
        "",
    ]
    if report["notes"]:
        lines += ["## Notes", ""]
        for note in report["notes"]:
            lines.append(f"- {note}")
        lines.append("")
    if report["errors"]:
        lines += ["## Errors", ""]
        for err in report["errors"]:
            lines.append(f"- {err}")
        lines.append("")
    lines += [
        "## Overall Status",
        "",
        f"**{report['overall_status']}**",
        "",
        "---",
        "_This is a reference environment check — not a Unity parity check._",
    ]
    with open(VERIFY_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"MD  report saved: {VERIFY_MD}")

    return 0 if report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
