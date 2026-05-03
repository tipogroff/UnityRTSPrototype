#!/usr/bin/env python3
"""Stage 10D.6 — Full semantic adapter rebuild runner.

Thin orchestration wrapper that calls the existing
adapt_legacy032_to_unity_v2_observation_semantics.py with the Stage10D.6
patched mapping spec and a new timestamped output directory.

Strict constraints:
- Does NOT retrain, run PPO, or mutate any checkpoint.
- Does NOT overwrite old adapted datasets.
- Output always goes to a new timestamped directory.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Stage10D.6 full semantic adapter rebuild"
    )
    p.add_argument(
        "--raw-rollout-dir",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/teacher_rollouts/"
            "legacy032_3m_unity_v2_rollout_export_20260501T125015Z"
        ),
    )
    p.add_argument(
        "--mapping-json",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/observation_semantics/"
            "legacy032_to_unity_v2_observation_mapping.json"
        ),
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("python/week5_teacher_legacy032/teacher_adapted"),
    )
    p.add_argument(
        "--run-label",
        type=str,
        default="legacy032_3m_unity_v2_semantic_adapted_stage10d6",
    )
    p.add_argument(
        "--adapter-script",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/scripts/"
            "adapt_legacy032_to_unity_v2_observation_semantics.py"
        ),
    )
    p.add_argument(
        "--run-result-json",
        type=Path,
        default=Path(
            "python/week6_student/reports/stage10d6_adapter_rebuild_run_result.json"
        ),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = _repo_root()

    adapter_script = _resolve(root, args.adapter_script)
    mapping_json = _resolve(root, args.mapping_json)
    raw_rollout_dir = _resolve(root, args.raw_rollout_dir)
    output_dir = _resolve(root, args.output_dir)
    run_result_json = _resolve(root, args.run_result_json)

    if not adapter_script.exists():
        raise RuntimeError(f"Missing adapter script: {adapter_script}")
    if not mapping_json.exists():
        raise RuntimeError(f"Missing mapping json: {mapping_json}")
    if not raw_rollout_dir.exists():
        raise RuntimeError(f"Missing raw rollout dir: {raw_rollout_dir}")

    # Confirm spec has been patched to stage10d6_v1
    spec = json.loads(mapping_json.read_text(encoding="utf-8"))
    spec_version = spec.get("mapping_spec_version", "")
    if spec_version != "stage10d6_v1":
        print(
            f"[stage10d6][ADAPTER] WARNING: mapping spec version is '{spec_version}', "
            "expected 'stage10d6_v1'. Aborting rebuild until spec is patched.",
            file=sys.stderr,
        )
        return 1

    cmd = [
        sys.executable,
        str(adapter_script),
        "--raw-rollout-dir", str(raw_rollout_dir),
        "--mapping-json", str(mapping_json),
        "--output-dir", str(output_dir),
        "--run-label", args.run_label,
        "--allow-critical-unavailable", "true",
    ]

    print(f"[stage10d6][ADAPTER] Running: {' '.join(cmd)}")
    started_at = _now_iso()
    result = subprocess.run(cmd, capture_output=False)
    finished_at = _now_iso()

    run_result: Dict[str, Any] = {
        "stage": "10D.6",
        "diagnostic": "adapter_rebuild_run",
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "returncode": result.returncode,
        "run_label": args.run_label,
        "mapping_spec_version": spec_version,
        "adapter_script": str(adapter_script),
        "mapping_json": str(mapping_json),
        "raw_rollout_dir": str(raw_rollout_dir),
        "output_dir": str(output_dir),
        "status": "success" if result.returncode == 0 else "failed",
        "explicit_non_claims": [
            "No retraining, PPO, or checkpoint mutation performed.",
            "No raw rollout overwrite.",
            "No old adapted dataset overwrite.",
        ],
    }

    run_result_json.parent.mkdir(parents=True, exist_ok=True)
    run_result_json.write_text(
        json.dumps(run_result, ensure_ascii=True, indent=2), encoding="utf-8"
    )
    print(f"[stage10d6][ADAPTER] run result -> {run_result_json}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
