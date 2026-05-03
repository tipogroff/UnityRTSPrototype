#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping

import numpy as np
import torch

from student_architecture_transfer import build_day3_student_model
from student_bc_loader import load_bc_ready_dataset


EXPECTED_LOGITS = {
    "action_type_logits": 6,
    "move_dir_logits": 4,
    "harvest_dir_logits": 4,
    "return_dir_logits": 4,
    "produce_dir_logits": 4,
    "produce_unit_type_logits": 7,
    "attack_target_local_logits": 49,
}

NOOP_ACTION_TYPE = 0
HARVEST_ACTION_TYPE = 2
PRODUCE_ACTION_TYPE = 4
UNIT_TYPE_OFFSET = 5
UNIT_TYPE_SIZE = 7
WORKER_UNIT_TYPE_INDEX = 3
BASE_UNIT_TYPE_INDEX = 1


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (root / path)


def _to_rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except Exception:
        return path.as_posix()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.8 checkpoint inference dry-run")
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument(
        "--bc-ready-dir",
        type=Path,
        default=Path(
            "python/week6_student/bc_ready/"
            "legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z"
        ),
    )
    p.add_argument("--batch-size", type=int, default=128)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d8_checkpoint_inference_dry_run.json"),
    )
    return p.parse_args()


def _distribution(counts: np.ndarray) -> Dict[str, Any]:
    total = int(np.sum(counts))
    if total <= 0:
        return {"count": 0, "share": 0.0}
    return {"count": total, "share": float(total / total)}


def _action_distribution(values: np.ndarray, num_classes: int) -> Dict[str, Any]:
    binc = np.bincount(values.astype(np.int64), minlength=num_classes)
    total = int(np.sum(binc))
    out: Dict[str, Any] = {"total": total, "counts": {}, "shares": {}}
    for i, c in enumerate(binc.tolist()):
        out["counts"][str(i)] = int(c)
        out["shares"][str(i)] = float(c / total) if total > 0 else 0.0
    return out


def _load_debug_split_npz(bc_ready_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    debug_path = bc_ready_dir / "bc_debug.npz"
    if not debug_path.exists():
        raise FileNotFoundError(f"bc_debug.npz not found: {debug_path}")

    with np.load(debug_path, allow_pickle=False) as npz:
        arrays = {k: np.asarray(npz[k]) for k in npz.files}

    observations = arrays.get("input_tensor")
    if observations is None:
        observations = arrays.get("observations")
    actions = arrays.get("target_action_branches")
    if actions is None:
        actions = arrays.get("actions")

    if observations is None or actions is None:
        raise RuntimeError("bc_debug.npz missing observations/input_tensor or actions/target_action_branches")

    observations = np.asarray(observations, dtype=np.float32)
    actions = np.asarray(actions, dtype=np.int64)

    if observations.ndim == 3 and tuple(observations.shape[1:]) == (576, 27):
        observations = observations.reshape(observations.shape[0], 24, 24, 27)

    return observations, actions


def main() -> int:
    args = parse_args()
    root = _repo_root()

    checkpoint = _resolve(root, args.checkpoint).resolve()
    bc_ready_dir = _resolve(root, args.bc_ready_dir).resolve()
    output_json = _resolve(root, args.output_json).resolve()

    failures: List[str] = []

    if not checkpoint.exists():
        failures.append(f"checkpoint_not_found: {checkpoint.as_posix()}")

    try:
        dataset = load_bc_ready_dataset(bc_ready_dir)
    except Exception as exc:
        failures.append(f"dataset_load_failed: {exc}")
        dataset = None

    details: Dict[str, Any] = {
        "checkpoint": _to_rel(root, checkpoint),
        "bc_ready_dir": _to_rel(root, bc_ready_dir),
    }

    if failures:
        payload = {
            "stage": "10D.8",
            "diagnostic": "checkpoint_inference_dry_run",
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "fail",
            "checks": {},
            "details": details,
            "hard_failures": failures,
            "explicit_non_claims": [
                "No checkpoint mutation.",
                "No Unity runtime execution.",
            ],
        }
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        print(output_json.as_posix())
        return 1

    assert dataset is not None

    x_np, y_np = _load_debug_split_npz(bc_ready_dir)

    if x_np.ndim != 4 or tuple(x_np.shape[1:]) != (24, 24, 27):
        failures.append(f"debug_input_shape_mismatch: got={list(x_np.shape)}")
    if y_np.ndim != 3 or tuple(y_np.shape[1:]) != (576, 7):
        failures.append(f"debug_target_shape_mismatch: got={list(y_np.shape)}")

    batch_size = min(int(args.batch_size), int(x_np.shape[0]))
    x_np = x_np[:batch_size]
    y_np = y_np[:batch_size]

    device = torch.device(args.device)
    model = build_day3_student_model().to(device=device)

    ckpt = torch.load(checkpoint, map_location=device)
    if not isinstance(ckpt, Mapping) or "model_state_dict" not in ckpt:
        failures.append("checkpoint_payload_invalid_or_missing_model_state_dict")
    else:
        missing, unexpected = model.load_state_dict(ckpt["model_state_dict"], strict=True)
        if missing or unexpected:
            failures.append(f"state_dict_mismatch: missing={missing}, unexpected={unexpected}")

    if failures:
        payload = {
            "stage": "10D.8",
            "diagnostic": "checkpoint_inference_dry_run",
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "fail",
            "checks": {},
            "details": details,
            "hard_failures": failures,
            "explicit_non_claims": [
                "No checkpoint mutation.",
                "No Unity runtime execution.",
            ],
        }
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        print(output_json.as_posix())
        return 1

    model.eval()
    with torch.no_grad():
        x = torch.from_numpy(x_np).to(device=device, dtype=torch.float32)
        logits = model(x)

    checks: Dict[str, Any] = {}
    logits_shapes: Dict[str, Any] = {}

    for key, branch_size in EXPECTED_LOGITS.items():
        checks[f"has_{key}"] = key in logits
        if key not in logits:
            failures.append(f"missing_logits_key: {key}")
            continue
        shape = list(logits[key].shape)
        logits_shapes[key] = shape
        ok = tuple(shape[1:]) == (576, branch_size)
        checks[f"shape_{key}"] = ok
        if not ok:
            failures.append(f"logits_shape_mismatch: {key} got={shape} expected=[B,576,{branch_size}]")

    pred_action_type = torch.argmax(logits["action_type_logits"], dim=-1).detach().cpu().numpy()
    target_action_type = y_np[..., 0]

    actor_mask = target_action_type != NOOP_ACTION_TYPE
    actor_count = int(np.sum(actor_mask))

    unit_peak = np.argmax(x_np[..., UNIT_TYPE_OFFSET : UNIT_TYPE_OFFSET + UNIT_TYPE_SIZE], axis=-1)
    unit_peak = unit_peak.reshape(unit_peak.shape[0], -1)
    worker_proxy_mask = (target_action_type == HARVEST_ACTION_TYPE) & (unit_peak == WORKER_UNIT_TYPE_INDEX)
    base_proxy_mask = (target_action_type == PRODUCE_ACTION_TYPE) & (unit_peak == BASE_UNIT_TYPE_INDEX)

    worker_proxy_count = int(np.sum(worker_proxy_mask))
    base_proxy_count = int(np.sum(base_proxy_mask))

    actor_pred = pred_action_type[actor_mask]
    actor_non_noop_count = int(np.sum(actor_pred != NOOP_ACTION_TYPE)) if actor_count > 0 else 0
    actor_noop_share = float(np.mean(actor_pred == NOOP_ACTION_TYPE)) if actor_count > 0 else 1.0

    worker_harvest_pred_count = int(np.sum(pred_action_type[worker_proxy_mask] == HARVEST_ACTION_TYPE)) if worker_proxy_count > 0 else 0
    base_produce_pred_count = int(np.sum(pred_action_type[base_proxy_mask] == PRODUCE_ACTION_TYPE)) if base_proxy_count > 0 else 0

    checks["actor_cell_count_gt_0"] = actor_count > 0
    checks["actor_cells_not_noop_only"] = actor_non_noop_count > 0
    checks["some_harvest_pred_on_worker_proxy"] = worker_proxy_count > 0 and worker_harvest_pred_count > 0
    checks["some_produce_pred_on_base_proxy"] = base_proxy_count > 0 and base_produce_pred_count > 0

    for key, passed in checks.items():
        if not bool(passed):
            failures.append(f"check_failed: {key}")

    details.update(
        {
            "batch_size_used": int(batch_size),
            "input_shape": list(x_np.shape),
            "target_shape": list(y_np.shape),
            "logits_shapes": logits_shapes,
            "action_type_distribution_all_cells": _action_distribution(pred_action_type.reshape(-1), num_classes=6),
            "action_type_distribution_actor_cells": _action_distribution(actor_pred.reshape(-1), num_classes=6)
            if actor_count > 0
            else {"total": 0, "counts": {str(i): 0 for i in range(6)}, "shares": {str(i): 0.0 for i in range(6)}},
            "worker_harvest_proxy": {
                "count": worker_proxy_count,
                "predicted_harvest_count": worker_harvest_pred_count,
                "predicted_harvest_share": float(worker_harvest_pred_count / worker_proxy_count) if worker_proxy_count > 0 else 0.0,
                "action_type_distribution": _action_distribution(pred_action_type[worker_proxy_mask], num_classes=6)
                if worker_proxy_count > 0
                else {"total": 0, "counts": {str(i): 0 for i in range(6)}, "shares": {str(i): 0.0 for i in range(6)}},
            },
            "base_produce_proxy": {
                "count": base_proxy_count,
                "predicted_produce_count": base_produce_pred_count,
                "predicted_produce_share": float(base_produce_pred_count / base_proxy_count) if base_proxy_count > 0 else 0.0,
                "action_type_distribution": _action_distribution(pred_action_type[base_proxy_mask], num_classes=6)
                if base_proxy_count > 0
                else {"total": 0, "counts": {str(i): 0 for i in range(6)}, "shares": {str(i): 0.0 for i in range(6)}},
            },
            "actor_cell_metrics": {
                "actor_cell_count": actor_count,
                "actor_cell_non_noop_pred_count": actor_non_noop_count,
                "actor_cell_noop_pred_share": actor_noop_share,
            },
        }
    )

    payload = {
        "stage": "10D.8",
        "diagnostic": "checkpoint_inference_dry_run",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "pass" if not failures else "fail",
        "checks": checks,
        "details": details,
        "hard_failures": failures,
        "explicit_non_claims": [
            "Dry-run only; no Unity runtime behavior claim.",
            "No checkpoint mutation.",
            "No PPO or retraining in this script.",
        ],
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(output_json.as_posix())
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
