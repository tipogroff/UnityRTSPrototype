#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripted_bc_utils import (
    DEFAULT_EVAL_REPORT,
    DEFAULT_OVERFIT_REPORT,
    DEFAULT_OVERFIT_SUMMARY,
    DEFAULT_TRAIN_HISTORY,
    DEFAULT_VALIDATION,
    utc_now,
    write_json,
    write_md,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build OVERFIT report from dataset validation + train + eval.")
    p.add_argument("--dataset-validation", type=Path, default=DEFAULT_VALIDATION)
    p.add_argument("--train-history", type=Path, default=DEFAULT_TRAIN_HISTORY)
    p.add_argument("--eval-report", type=Path, default=DEFAULT_EVAL_REPORT)
    p.add_argument("--output-md", type=Path, default=DEFAULT_OVERFIT_REPORT)
    p.add_argument("--output-summary", type=Path, default=DEFAULT_OVERFIT_SUMMARY)
    return p.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def metric_pass(value: Optional[float], thr: float) -> bool:
    if value is None:
        return True
    try:
        return float(value) >= float(thr)
    except Exception:
        return False


def decide(validation: Dict[str, Any], eval_report: Dict[str, Any]) -> str:
    if not validation:
        return "FAIL_DATASET_INVALID"

    val_decision = str(validation.get("decision", "INCONCLUSIVE_NEEDS_MANUAL_CHECK"))
    if val_decision.startswith("FAIL"):
        return "FAIL_DATASET_INVALID"

    m = (eval_report or {}).get("metrics", {}) if isinstance(eval_report, dict) else {}
    if not m:
        return "INCONCLUSIVE_NEEDS_MANUAL_CHECK"

    action_ok = metric_pass(m.get("action_type_acc_active"), 0.95)
    nonnoop_ok = metric_pass(m.get("non_noop_recall"), 0.90)
    invalid_ok = int(m.get("invalid_after_argmax", 1)) == 0

    move_ok = metric_pass(m.get("move_dir_acc_given_move"), 0.90)
    harvest_ok = metric_pass(m.get("harvest_dir_acc_given_harvest"), 0.90)
    return_ok = metric_pass(m.get("return_dir_acc_given_return"), 0.90)
    produce_dir_ok = metric_pass(m.get("produce_dir_acc_given_produce"), 0.90)
    produce_type_ok = metric_pass(m.get("produce_type_acc_given_produce"), 0.90)
    attack_ok = metric_pass(m.get("attack_target_acc_given_attack"), 0.90)

    class_presence = validation.get("class_presence", {}) if isinstance(validation, dict) else {}
    limited_classes = any(not bool(class_presence.get(k, False)) for k in ["harvest", "return", "produce", "attack"])

    if action_ok and nonnoop_ok and invalid_ok and move_ok and harvest_ok and return_ok and produce_dir_ok and produce_type_ok and attack_ok:
        if limited_classes:
            return "PARTIAL_PASS_OVERFIT_LIMITED_CLASSES"
        return "PASS_SUPERVISED_OVERFIT"

    if limited_classes and action_ok and nonnoop_ok and invalid_ok and move_ok:
        return "PARTIAL_PASS_OVERFIT_LIMITED_CLASSES"

    return "FAIL_OVERFIT_LAYOUT_OR_LOSS"


def main() -> int:
    args = parse_args()
    validation = load_json(args.dataset_validation)
    train_history = load_json(args.train_history)
    eval_report = load_json(args.eval_report)

    decision = decide(validation, eval_report)
    metrics = (eval_report or {}).get("metrics", {}) if isinstance(eval_report, dict) else {}
    final_train = (train_history or {}).get("final", {}) if isinstance(train_history, dict) else {}

    summary = {
        "schema": "week5_gridnet_overfit_report_summary.v1",
        "generated_at_utc": utc_now(),
        "decision": decision,
        "dataset_validation_decision": validation.get("decision"),
        "train_final": final_train,
        "eval_metrics": metrics,
        "inputs": {
            "dataset_validation": str(args.dataset_validation),
            "train_history": str(args.train_history),
            "eval_report": str(args.eval_report),
        },
        "decision_vocab": [
            "PASS_SUPERVISED_OVERFIT",
            "PARTIAL_PASS_OVERFIT_LIMITED_CLASSES",
            "FAIL_OVERFIT_LAYOUT_OR_LOSS",
            "FAIL_DATASET_INVALID",
            "INCONCLUSIVE_NEEDS_MANUAL_CHECK",
        ],
    }

    lines: List[str] = [
        "# OVERFIT_REPORT",
        "",
        f"- Decision: {decision}",
        f"- Dataset validation decision: {validation.get('decision')}",
        "",
        "## Eval Metrics",
        f"- action_type_acc_active: {metrics.get('action_type_acc_active')}",
        f"- non_noop_recall: {metrics.get('non_noop_recall')}",
        f"- invalid_after_argmax: {metrics.get('invalid_after_argmax')}",
        f"- move_dir_acc_given_move: {metrics.get('move_dir_acc_given_move')}",
        f"- harvest_dir_acc_given_harvest: {metrics.get('harvest_dir_acc_given_harvest')}",
        f"- return_dir_acc_given_return: {metrics.get('return_dir_acc_given_return')}",
        f"- produce_dir_acc_given_produce: {metrics.get('produce_dir_acc_given_produce')}",
        f"- produce_type_acc_given_produce: {metrics.get('produce_type_acc_given_produce')}",
        f"- attack_target_acc_given_attack: {metrics.get('attack_target_acc_given_attack')}",
        "",
        "## Final Train Snapshot",
        f"- total_loss: {final_train.get('total_loss')}",
        f"- action_type_acc_active: {final_train.get('action_type_acc_active')}",
        f"- non_noop_recall: {final_train.get('non_noop_recall')}",
        "",
        "## Decision Vocabulary",
        "- PASS_SUPERVISED_OVERFIT",
        "- PARTIAL_PASS_OVERFIT_LIMITED_CLASSES",
        "- FAIL_OVERFIT_LAYOUT_OR_LOSS",
        "- FAIL_DATASET_INVALID",
        "- INCONCLUSIVE_NEEDS_MANUAL_CHECK",
    ]

    write_json(args.output_summary, summary)
    write_md(args.output_md, lines)
    print(args.output_md)
    print(args.output_summary)
    return 0 if decision.startswith("PASS") or decision.startswith("PARTIAL_PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
