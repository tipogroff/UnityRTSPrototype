#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping

import numpy as np
import torch
from torch.utils.data import DataLoader

THIS_FILE = Path(__file__).resolve()
WEEK6_STUDENT_DIR = THIS_FILE.parents[1]
if str(WEEK6_STUDENT_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK6_STUDENT_DIR))

from student_architecture_transfer import build_day3_student_model
from student_branch_contract import BRANCH_SPECS
from train_student_bc_source_valid_noopfix import SourceValidDataset


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Probe student checkpoint on BC debug/validation with source-valid metrics.")
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--bc-ready-dir", type=Path, required=True)
    p.add_argument("--split", choices=["bc_debug", "bc_validation"], default="bc_debug")
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--output-json", type=Path, required=True)
    return p.parse_args()


def _repo_root() -> Path:
    return THIS_FILE.parents[3]


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else (_repo_root() / path)


def _confusion(target: np.ndarray, pred: np.ndarray) -> np.ndarray:
    out = np.zeros((6, 6), dtype=np.int64)
    for t, p in zip(target.reshape(-1), pred.reshape(-1)):
        if 0 <= int(t) < 6 and 0 <= int(p) < 6:
            out[int(t), int(p)] += 1
    return out


def main() -> int:
    args = parse_args()
    checkpoint = _resolve(args.checkpoint).resolve()
    bc_ready_dir = _resolve(args.bc_ready_dir).resolve()
    output_json = _resolve(args.output_json).resolve()
    device = torch.device(args.device)

    ds = SourceValidDataset(bc_ready_dir / f"{args.split}.npz")
    loader = DataLoader(ds, batch_size=int(args.batch_size), shuffle=False, num_workers=0)
    model = build_day3_student_model().to(device=device)
    payload = torch.load(checkpoint, map_location=device)
    if not isinstance(payload, Mapping) or "model_state_dict" not in payload:
        raise RuntimeError(f"checkpoint missing model_state_dict: {checkpoint}")
    model.load_state_dict(payload["model_state_dict"], strict=True)
    model.eval()

    total = 0
    action_correct = 0
    branch_total = {spec.branch_name: 0 for spec in BRANCH_SPECS}
    branch_correct = {spec.branch_name: 0 for spec in BRANCH_SPECS}
    pred_hist = Counter()
    target_hist = Counter()
    cm = np.zeros((6, 6), dtype=np.int64)
    valid_actor_total = 0
    valid_actor_pred_non_noop = 0
    valid_actor_exact = 0
    invalid_total = 0
    invalid_pred_non_noop = 0
    pred_harvest_total = 0
    pred_harvest_on_worker = 0
    pred_produce_total = 0
    pred_produce_on_producer = 0
    pred_non_noop_total = 0
    pred_non_noop_on_actor = 0

    with torch.no_grad():
        for x, y, source_valid in loader:
            x = x.to(device=device)
            y = y.to(device=device)
            source_valid = source_valid.to(device=device)
            logits = model(x)
            action_target = y[..., 0]
            action_pred = torch.argmax(logits["action_type_logits"], dim=-1)
            obs_flat = x.reshape(x.shape[0], 576, 27)
            friendly = obs_flat[..., 3] > 0.5
            worker = friendly & (obs_flat[..., 8] > 0.5)
            producer = friendly & (
                (obs_flat[..., 6] > 0.5)
                | (obs_flat[..., 7] > 0.5)
                | (obs_flat[..., 8] > 0.5)
            )
            actor = friendly & (
                (obs_flat[..., 6] > 0.5)
                | (obs_flat[..., 7] > 0.5)
                | (obs_flat[..., 8] > 0.5)
                | (obs_flat[..., 9] > 0.5)
                | (obs_flat[..., 10] > 0.5)
                | (obs_flat[..., 11] > 0.5)
            )
            total += int(action_target.numel())
            action_correct += int(action_pred.eq(action_target).sum().item())

            for spec in BRANCH_SPECS:
                pred = torch.argmax(logits[spec.logits_key], dim=-1)
                target = y[..., spec.target_index]
                if spec.action_type_gate_value is None:
                    active = torch.ones_like(action_target, dtype=torch.bool)
                else:
                    active = action_target == int(spec.action_type_gate_value)
                branch_total[spec.branch_name] += int(active.sum().item())
                branch_correct[spec.branch_name] += int(pred[active].eq(target[active]).sum().item()) if bool(active.any()) else 0

            valid_actor = source_valid & action_target.ne(0)
            valid_actor_total += int(valid_actor.sum().item())
            valid_actor_pred_non_noop += int(action_pred[valid_actor].ne(0).sum().item()) if bool(valid_actor.any()) else 0
            valid_actor_exact += int(action_pred[valid_actor].eq(action_target[valid_actor]).sum().item()) if bool(valid_actor.any()) else 0
            invalid = ~source_valid
            invalid_total += int(invalid.sum().item())
            invalid_pred_non_noop += int(action_pred[invalid].ne(0).sum().item()) if bool(invalid.any()) else 0

            pred_harvest = action_pred.eq(2)
            pred_produce = action_pred.eq(4)
            pred_non_noop = action_pred.ne(0)
            pred_harvest_total += int(pred_harvest.sum().item())
            pred_harvest_on_worker += int((pred_harvest & worker).sum().item())
            pred_produce_total += int(pred_produce.sum().item())
            pred_produce_on_producer += int((pred_produce & producer).sum().item())
            pred_non_noop_total += int(pred_non_noop.sum().item())
            pred_non_noop_on_actor += int((pred_non_noop & actor).sum().item())

            pred_np = action_pred.detach().cpu().numpy()
            target_np = action_target.detach().cpu().numpy()
            cm += _confusion(target_np, pred_np)
            pred_hist.update(int(v) for v in pred_np.reshape(-1).tolist())
            target_hist.update(int(v) for v in target_np.reshape(-1).tolist())

    report: Dict[str, Any] = {
        "status": "pass",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checkpoint": str(checkpoint),
        "bc_ready_dir": str(bc_ready_dir),
        "split": args.split,
        "samples": int(len(ds)),
        "action_type_accuracy": float(action_correct / total) if total else 0.0,
        "branch_accuracies": {
            spec.branch_name: (float(branch_correct[spec.branch_name] / branch_total[spec.branch_name]) if branch_total[spec.branch_name] else 0.0)
            for spec in BRANCH_SPECS
        },
        "noop_prediction_share": float(pred_hist.get(0, 0) / total) if total else 0.0,
        "predicted_action_type_histogram": {str(i): int(pred_hist.get(i, 0)) for i in range(6)},
        "target_action_type_histogram": {str(i): int(target_hist.get(i, 0)) for i in range(6)},
        "source_valid_non_noop_recall": float(valid_actor_pred_non_noop / valid_actor_total) if valid_actor_total else 0.0,
        "source_valid_non_noop_exact_action_type_recall": float(valid_actor_exact / valid_actor_total) if valid_actor_total else 0.0,
        "source_valid_non_noop_count": int(valid_actor_total),
        "source_invalid_false_non_noop_rate": float(invalid_pred_non_noop / invalid_total) if invalid_total else 0.0,
        "source_invalid_cell_count": int(invalid_total),
        "semantic_target_compatibility_accuracy": {
            "harvest_predicted_on_worker_cells": float(pred_harvest_on_worker / pred_harvest_total) if pred_harvest_total else 1.0,
            "produce_predicted_on_base_barracks_or_worker_cells": float(pred_produce_on_producer / pred_produce_total) if pred_produce_total else 1.0,
            "non_noop_predicted_on_possible_actor_cells": float(pred_non_noop_on_actor / pred_non_noop_total) if pred_non_noop_total else 1.0,
            "pred_harvest_total": int(pred_harvest_total),
            "pred_produce_total": int(pred_produce_total),
            "pred_non_noop_total": int(pred_non_noop_total),
        },
        "action_type_confusion_matrix_rows_target_cols_pred": cm.tolist(),
        "acceptance": {
            "action_type_accuracy_far_above_random": bool((action_correct / total) > 0.35) if total else False,
            "source_invalid_false_non_noop_rate_low": bool((invalid_pred_non_noop / invalid_total) < 0.05) if invalid_total else False,
            "source_valid_non_noop_recall_meaningful": bool((valid_actor_pred_non_noop / valid_actor_total) > 0.10) if valid_actor_total else False,
            "not_all_noop": bool(pred_hist.get(0, 0) < total),
            "semantic_predicted_actions_compatible": bool(
                (pred_harvest_total == 0 or pred_harvest_on_worker / pred_harvest_total >= 0.95)
                and (pred_produce_total == 0 or pred_produce_on_producer / pred_produce_total >= 0.95)
                and (pred_non_noop_total == 0 or pred_non_noop_on_actor / pred_non_noop_total >= 0.95)
            ),
        },
    }
    report["go_for_unity_visual_inference"] = bool(all(report["acceptance"].values()))

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["go_for_unity_visual_inference"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
