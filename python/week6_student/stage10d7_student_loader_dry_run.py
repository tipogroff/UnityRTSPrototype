#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import torch

from student_bc_loader import load_bc_ready_dataset


EXPECTED_BRANCH_SIZES = [6, 4, 4, 4, 4, 7, 49]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_dump(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.7 student loader dry-run")
    p.add_argument("--bc-ready-dir", type=Path, required=True)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d7_student_loader_dry_run.json"),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = _repo_root()
    bc_ready_dir = _resolve(root, args.bc_ready_dir)
    output_json = _resolve(root, args.output_json)

    hard_failures: List[str] = []
    checks: Dict[str, Any] = {}
    details: Dict[str, Any] = {}

    try:
        dataset = load_bc_ready_dataset(bc_ready_dir)
        checks["loader_read_manifest"] = True
        checks["loader_read_train_validation"] = True
        checks["debug_npz_exists"] = bool((bc_ready_dir / "bc_debug.npz").exists())

        with np.load(bc_ready_dir / "bc_debug.npz", allow_pickle=False) as debug_npz:
            debug_keys = list(debug_npz.files)
        checks["loader_read_debug_npz"] = True

        branch_sizes = list(dataset.contract.target_branch_sizes)
        checks["branch_size_match"] = branch_sizes == EXPECTED_BRANCH_SIZES
        if not checks["branch_size_match"]:
            hard_failures.append(
                f"branch_size_mismatch: expected={EXPECTED_BRANCH_SIZES} got={branch_sizes}"
            )

        batch_size = min(int(args.batch_size), int(dataset.train.samples))
        x_np = np.asarray(dataset.train.input_tensor[:batch_size], dtype=np.float32)
        y_np = np.asarray(dataset.train.target_action_branches[:batch_size], dtype=np.int64)

        checks["one_batch_loaded"] = bool(batch_size > 0)
        checks["batch_input_shape"] = tuple(x_np.shape[1:]) == (24, 24, 27)
        checks["batch_action_shape"] = tuple(y_np.shape[1:]) == (576, 7)

        device = torch.device(args.device)
        x = torch.from_numpy(x_np).to(device=device, dtype=torch.float32)
        y = torch.from_numpy(y_np).to(device=device, dtype=torch.long)

        checks["batch_convert_model_input"] = tuple(x.shape[1:]) == (24, 24, 27)
        checks["batch_actions_align_[B,576,7]"] = tuple(y.shape[1:]) == (576, 7)
        checks["no_dtype_device_error"] = bool(x.dtype == torch.float32 and y.dtype == torch.long)
        checks["no_shape_mismatch"] = bool(tuple(x.shape[0:1]) == tuple(y.shape[0:1]))

        details = {
            "manifest_path": dataset.manifest_path.as_posix(),
            "run_dir": dataset.run_dir.as_posix(),
            "debug_npz_keys": debug_keys,
            "train_samples": int(dataset.train.samples),
            "validation_samples": int(dataset.validation.samples),
            "batch_size_used": int(batch_size),
            "batch_input_shape": list(x.shape),
            "batch_action_shape": list(y.shape),
            "branch_sizes": branch_sizes,
            "device": str(device),
        }

        for key, passed in checks.items():
            if not bool(passed):
                hard_failures.append(f"check_failed: {key}")

    except Exception as exc:
        hard_failures.append(str(exc))

    report = {
        "stage": "10D.7",
        "diagnostic": "student_loader_dry_run",
        "generated_at_utc": _iso_now(),
        "bc_ready_dir": bc_ready_dir.as_posix(),
        "status": "pass" if not hard_failures else "fail",
        "checks": checks,
        "details": details,
        "hard_failures": hard_failures,
        "explicit_non_claims": [
            "No retraining performed.",
            "No PPO performed.",
            "No checkpoint mutation.",
        ],
    }
    _json_dump(output_json, report)
    print(output_json.as_posix())
    return 0 if not hard_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
