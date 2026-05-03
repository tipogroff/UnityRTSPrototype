#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import torch

from student_architecture_transfer import build_day3_student_model
from student_bc_loader import load_bc_ready_dataset
from student_bc_metrics import compute_branchwise_loss


EXPECTED_LOGIT_SHAPES = {
    "action_type_logits": 6,
    "move_dir_logits": 4,
    "harvest_dir_logits": 4,
    "return_dir_logits": 4,
    "produce_dir_logits": 4,
    "produce_unit_type_logits": 7,
    "attack_target_local_logits": 49,
}


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
    p = argparse.ArgumentParser(description="Stage10D.7 student forward dry-run without training")
    p.add_argument("--bc-ready-dir", type=Path, required=True)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d7_student_forward_dry_run.json"),
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
        batch_size = min(int(args.batch_size), int(dataset.train.samples))
        x_np = np.asarray(dataset.train.input_tensor[:batch_size], dtype=np.float32)
        y_np = np.asarray(dataset.train.target_action_branches[:batch_size], dtype=np.int64)

        device = torch.device(args.device)
        model = build_day3_student_model().to(device=device)
        model.eval()

        x = torch.from_numpy(x_np).to(device=device, dtype=torch.float32)
        y = torch.from_numpy(y_np).to(device=device, dtype=torch.long)

        with torch.no_grad():
            logits = model(x)
            batch_loss = compute_branchwise_loss(logits_by_key=logits, target_action_branches=y)

        checks["batch_loaded"] = bool(batch_size > 0)
        checks["no_optimizer_step_performed"] = True
        checks["no_backward_performed"] = True
        checks["all_required_logits_present"] = all(k in logits for k in EXPECTED_LOGIT_SHAPES)

        logits_shapes: Dict[str, List[int]] = {}
        for key, branch_size in EXPECTED_LOGIT_SHAPES.items():
            if key not in logits:
                hard_failures.append(f"missing_logits_key: {key}")
                continue
            shape = list(logits[key].shape)
            logits_shapes[key] = shape
            ok = tuple(shape[1:]) == (576, branch_size)
            checks[f"shape_{key}"] = ok
            if not ok:
                hard_failures.append(
                    f"logits_shape_mismatch: key={key} expected=[B,576,{branch_size}] got={shape}"
                )

        loss_value = float(batch_loss.total_loss.detach().cpu().item())
        checks["finite_loss"] = bool(np.isfinite(loss_value))
        if not checks["finite_loss"]:
            hard_failures.append(f"loss_not_finite: {loss_value}")

        for k, passed in checks.items():
            if not bool(passed):
                hard_failures.append(f"check_failed: {k}")

        details = {
            "run_dir": dataset.run_dir.as_posix(),
            "manifest_path": dataset.manifest_path.as_posix(),
            "batch_size_used": int(batch_size),
            "input_shape": list(x.shape),
            "target_shape": list(y.shape),
            "logits_shapes": logits_shapes,
            "dry_run_supervised_loss": loss_value,
            "objective_active_count": int(batch_loss.objective_active_count),
            "device": str(device),
        }

    except Exception as exc:
        hard_failures.append(str(exc))

    report = {
        "stage": "10D.7",
        "diagnostic": "student_forward_dry_run",
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
            "No optimizer step and no weight update in this script.",
        ],
    }
    _json_dump(output_json, report)
    print(output_json.as_posix())
    return 0 if not hard_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
