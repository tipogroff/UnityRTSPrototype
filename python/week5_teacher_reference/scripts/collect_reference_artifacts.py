"""
collect_reference_artifacts.py
================================
Scans smoke and long run artifacts and produces a consolidated summary.

Run from repo root (inside or outside the reference venv):
    python python/week5_teacher_reference/scripts/collect_reference_artifacts.py

Outputs:
    python/week5_teacher_reference/artifacts/REFERENCE_REPRODUCTION_SUMMARY.md
    python/week5_teacher_reference/artifacts/reference_reproduction_summary.json
"""

import sys
import json
import os
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR  = Path(__file__).resolve().parent
REF_ROOT    = SCRIPT_DIR.parent
ARTIFACTS   = REF_ROOT / "artifacts"
SMOKE_BASE  = ARTIFACTS / "smoke_runs"
LONG_BASE   = ARTIFACTS / "long_runs"
OUT_JSON    = ARTIFACTS / "reference_reproduction_summary.json"
OUT_MD      = ARTIFACTS / "REFERENCE_REPRODUCTION_SUMMARY.md"

ARTIFACTS.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def collect_runs(base_dir: Path, run_type: str) -> list:
    runs = []
    if not base_dir.exists():
        return runs
    for run_dir in sorted(base_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        run_info = {
            "run_type":          run_type,
            "run_path":          str(run_dir),
            "timestamp":         run_dir.name,
            "command":           None,
            "total_timesteps":   None,
            "seed":              None,
            "observation_shape": None,
            "action_space":      None,
            "videos_found":      False,
            "checkpoints_found": False,
            "logs_found":        False,
            "exit_code":         None,
        }

        # Read summary JSON if present
        for summary_name in ("smoke_summary.json", "long_run_summary.json"):
            summary_path = run_dir / summary_name
            if summary_path.exists():
                try:
                    with open(summary_path, encoding="utf-8") as f:
                        s = json.load(f)
                    run_info["total_timesteps"] = s.get("total_timesteps")
                    run_info["seed"]            = s.get("seed")
                    run_info["exit_code"]       = s.get("exit_code")
                except Exception:
                    pass

        # Read command file
        for cmd_name in ("smoke_command.txt", "long_run_command.txt"):
            cmd_path = run_dir / cmd_name
            if cmd_path.exists():
                try:
                    run_info["command"] = cmd_path.read_text(encoding="utf-8").strip()
                except Exception:
                    pass

        # Check for logs
        for log_name in ("smoke_train.log", "long_train.log"):
            if (run_dir / log_name).exists():
                run_info["logs_found"] = True

        # Check for videos
        video_dir = run_dir / "videos"
        if video_dir.exists():
            mp4_files = list(video_dir.rglob("*.mp4")) + list(video_dir.rglob("*.avi"))
            run_info["videos_found"] = len(mp4_files) > 0

        # Check for checkpoints (pt / zip files)
        checkpoints = list(run_dir.rglob("*.pt")) + list(run_dir.rglob("*.zip"))
        run_info["checkpoints_found"] = len(checkpoints) > 0

        # Try to pull obs shape from verify report if present
        verify_json = ARTIFACTS / "reference_env_verify.json"
        if verify_json.exists():
            try:
                with open(verify_json, encoding="utf-8") as f:
                    vdata = json.load(f)
                run_info["observation_shape"] = vdata.get("observation_space")
                run_info["action_space"]      = vdata.get("action_space")
            except Exception:
                pass

        runs.append(run_info)
    return runs


def parse_verify_report() -> dict:
    verify_json = ARTIFACTS / "reference_env_verify.json"
    if not verify_json.exists():
        return {"status": "NOT_RUN", "note": "Run verify_reference_env.py first"}
    try:
        with open(verify_json, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"status": "ERROR", "note": str(e)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  Reference Artifacts Collector")
    print("=" * 60)

    smoke_runs = collect_runs(SMOKE_BASE, "smoke")
    long_runs  = collect_runs(LONG_BASE,  "long")
    all_runs   = smoke_runs + long_runs

    verify = parse_verify_report()

    summary = {
        "generated_at":    datetime.now(timezone.utc).isoformat(),
        "env_verify":      verify,
        "total_runs":      len(all_runs),
        "smoke_run_count": len(smoke_runs),
        "long_run_count":  len(long_runs),
        "runs":            all_runs,
    }

    # -- Print to console
    print(f"\nEnvironment verify status : {verify.get('overall_status', 'UNKNOWN')}")
    print(f"Smoke runs found          : {len(smoke_runs)}")
    print(f"Long runs found           : {len(long_runs)}")
    print()

    for run in all_runs:
        status = "OK" if run["exit_code"] == 0 else f"exit={run['exit_code']}"
        print(f"  [{run['run_type'].upper():5s}] {run['timestamp']}  "
              f"steps={run['total_timesteps']}  seed={run['seed']}  "
              f"logs={run['logs_found']}  video={run['videos_found']}  "
              f"ckpt={run['checkpoints_found']}  [{status}]")

    # -- Save JSON
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nJSON summary saved: {OUT_JSON}")

    # -- Save Markdown
    lines = [
        "# Reference Reproduction Summary",
        "",
        f"**Generated**: {summary['generated_at']}",
        "",
        "## Environment Verification",
        "",
        f"- Status: **{verify.get('overall_status', 'UNKNOWN')}**",
        f"- gym_microrts import: `{verify.get('gym_microrts_import', 'N/A')}`",
        f"- env create: `{verify.get('env_create', 'N/A')}`",
        f"- observation_space: `{verify.get('observation_space', 'N/A')}`",
        f"- obs surface check: `{verify.get('obs_surface_check', 'N/A')}`",
        "",
        "## Training Runs",
        "",
        f"Total runs: {len(all_runs)} (smoke: {len(smoke_runs)}, long: {len(long_runs)})",
        "",
    ]

    if all_runs:
        lines += [
            "| Type | Timestamp | Timesteps | Seed | Logs | Video | Checkpoint | Exit |",
            "|------|-----------|-----------|------|------|-------|------------|------|",
        ]
        for run in all_runs:
            lines.append(
                f"| {run['run_type']} | {run['timestamp']} "
                f"| {run['total_timesteps']} "
                f"| {run['seed']} "
                f"| {'Y' if run['logs_found'] else 'N'} "
                f"| {'Y' if run['videos_found'] else 'N'} "
                f"| {'Y' if run['checkpoints_found'] else 'N'} "
                f"| {run['exit_code']} |"
            )
        lines.append("")
    else:
        lines += ["_No training runs found. Run the smoke script first._", ""]

    lines += [
        "## Success Criteria",
        "",
        "| Criterion | Status |",
        "|-----------|--------|",
        f"| env starts up | {verify.get('env_create', 'N/A')} |",
        f"| observation space | {verify.get('observation_space', 'N/A')} |",
        f"| obs surface | {verify.get('obs_surface_check', 'N/A')} |",
        f"| training runs without crash | {'YES' if any(r['exit_code'] == 0 for r in all_runs) else 'NOT YET'} |",
        f"| video/replay created | {'YES' if any(r['videos_found'] for r in all_runs) else 'NOT YET'} |",
        f"| checkpoint saved | {'YES' if any(r['checkpoints_found'] for r in all_runs) else 'NOT YET'} |",
        "",
        "---",
        "_This is a reference reproduction summary — not a Unity parity report._",
        "_Old Gym-μRTS checkpoints are NOT directly compatible with the Unity transfer pipeline._",
    ]

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"MD  summary saved: {OUT_MD}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
