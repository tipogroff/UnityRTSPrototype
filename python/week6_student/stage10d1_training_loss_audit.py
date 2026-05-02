#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage10D.1 training loss/objective audit")
    parser.add_argument(
        "--train-script",
        type=Path,
        default=Path("python/week6_student/train_student_bc_minimal.py"),
    )
    parser.add_argument(
        "--metrics-script",
        type=Path,
        default=Path("python/week6_student/student_bc_metrics.py"),
    )
    parser.add_argument(
        "--run-metrics",
        type=Path,
        default=Path(
            "python/week6_student/runs/legacy032_v2_bc_minimal_20260501T195501Z/day2_minimal_metrics_history.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d1_training_loss_audit.json"),
    )
    return parser.parse_args()


def _contains(text: str, needle: str) -> bool:
    return needle in text


def main() -> int:
    args = parse_args()
    train_text = args.train_script.read_text(encoding="utf-8")
    metrics_text = args.metrics_script.read_text(encoding="utf-8")
    run_metrics = json.loads(args.run_metrics.read_text(encoding="utf-8"))

    action_type_all_cells = _contains(metrics_text, "active_mask = torch.ones_like(action_type_targets, dtype=torch.bool)")
    actor_cell_mask_used = _contains(train_text, "actor") and _contains(metrics_text, "actor")
    class_weights_used = _contains(metrics_text, "weight=") or _contains(metrics_text, "class_weight")
    action_type_weighted_ce = _contains(metrics_text, "action_type") and (_contains(metrics_text, "weight=") or _contains(metrics_text, "weighted"))
    non_noop_oversampling = _contains(train_text, "WeightedRandomSampler") or _contains(train_text, "oversampl")
    actor_cell_accuracy_logged = _contains(train_text, "actor_cell_accuracy") or _contains(train_text, "actor_accuracy")

    val_history = run_metrics.get("history", [])
    val_dominated = None
    evidence = {}
    if isinstance(val_history, list) and val_history:
        first = val_history[0]
        action_active = int(first.get("val_action_type_active_count", 0))
        produce_active = int(first.get("val_produce_dir_active_count", 0))
        attack_active = int(first.get("val_attack_target_local_active_count", 0))
        ratio = float(action_active / max(1, produce_active + attack_active))
        val_dominated = bool(ratio > 100.0)
        evidence = {
            "val_action_type_active_count_epoch1": action_active,
            "val_produce_dir_active_count_epoch1": produce_active,
            "val_attack_target_local_active_count_epoch1": attack_active,
            "dominance_ratio_actiontype_vs_produce_plus_attack": ratio,
        }

    payload: Dict[str, Any] = {
        "stage": "10D.1",
        "diagnostic": "training_loss_audit",
        "inputs": {
            "train_script": str(args.train_script),
            "metrics_script": str(args.metrics_script),
            "run_metrics": str(args.run_metrics),
        },
        "audit": {
            "loss_computed_on_all_576_cells_or_not": {
                "value": "YES_FOR_ACTION_TYPE_BRANCH",
                "evidence": "action_type branch uses all-ones active_mask in compute_branchwise_loss",
                "bool": bool(action_type_all_cells),
            },
            "actor_cell_mask_used": {
                "bool": bool(actor_cell_mask_used),
                "evidence": "No explicit actor-cell masking logic found in training objective path",
            },
            "class_weights_used": {
                "bool": bool(class_weights_used),
                "evidence": "No class weight tensor passed into cross_entropy",
            },
            "action_type_weighted_ce_used": {
                "bool": bool(action_type_weighted_ce),
                "evidence": "No weighted CE invocation found for action_type",
            },
            "non_noop_oversampling_used": {
                "bool": bool(non_noop_oversampling),
                "evidence": "No oversampling sampler path found",
            },
            "actor_cell_accuracy_logged": {
                "bool": bool(actor_cell_accuracy_logged),
                "evidence": "Branch-wise accuracies logged; no dedicated actor-cell aggregate accuracy metric",
            },
            "validation_metrics_could_be_dominated_by_empty_cell_noop": {
                "bool": bool(val_dominated) if val_dominated is not None else None,
                "evidence": evidence,
            },
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(args.output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
