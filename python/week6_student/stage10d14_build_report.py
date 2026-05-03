#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Mapping

from stage10d14_common import DEFAULT_REPORTS_DIR, load_json, resolve_path, utc_now_iso


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Stage10D.14 targeted BC augmentation final report")
    p.add_argument("--augmentation-validation-json", type=Path, default=Path(DEFAULT_REPORTS_DIR) / "stage10d14_augmented_dataset_validation.json")
    p.add_argument("--training-history-json", type=Path, required=True)
    p.add_argument("--offline-eval-json", type=Path, default=Path(DEFAULT_REPORTS_DIR) / "stage10d14_offline_eval_report.json")
    p.add_argument("--strict-replay-json", type=Path, default=Path(DEFAULT_REPORTS_DIR) / "stage10d14_true_raw_strict_replay_report.json")
    p.add_argument("--output-md", type=Path, default=Path(DEFAULT_REPORTS_DIR) / "STAGE10D14_TARGETED_BC_AUGMENTATION_REPORT.md")
    return p.parse_args()


def _bool_label(condition: bool, when_true: str, when_false: str) -> str:
    return when_true if condition else when_false


def _primary_gate(*, dataset_valid: bool, training_completed: bool, preserved: bool, b2: bool, c3: bool, off_actor_safe: bool) -> str:
    if not dataset_valid:
        return "GO_FOR_STAGE10D14_AUGMENTATION_FIX"
    if dataset_valid and training_completed and preserved and b2 and c3 and off_actor_safe:
        return "GO_FOR_STAGE10D15_UNITY_VISUAL_RERUN_WITH_AUGMENTED_STUDENT"
    if dataset_valid and training_completed and not (b2 and c3):
        return "GO_FOR_STAGE10D14_TRAINING_FIX"
    if dataset_valid and training_completed and not preserved:
        return "GO_FOR_TARGETED_BC_AUGMENTATION_REDESIGN"
    return "GO_FOR_STAGE10D14_TRAINING_FIX"


def _md(report: Mapping[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# STAGE10D14 TARGETED BC AUGMENTATION REPORT")
    lines.append("")
    lines.append(f"- generated_at_utc: {report['generated_at_utc']}")
    lines.append(f"- primary_next_gate: {report['primary_next_gate']}")
    lines.append("")

    lines.append("## 1. Purpose and Constraints")
    for item in report["purpose_and_constraints"]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## 2. Evidence from Stage10D.12R and Stage10D.13A")
    for item in report["evidence"]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## 3. Augmentation Design")
    for item in report["augmentation_design"]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## 4. Dataset Validation")
    for key, value in report["dataset_validation"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")

    lines.append("## 5. Training Summary")
    for key, value in report["training_summary"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")

    lines.append("## 6. Offline Eval on Original Validation")
    for key, value in report["offline_original_validation"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")

    lines.append("## 7. Offline Eval on Augmented Validation")
    for key, value in report["offline_augmented_validation"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")

    lines.append("## 8. Strict Replay on True Raw Unity Observation")
    for key, value in report["strict_replay_summary"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")

    lines.append("## 9. Regression / Safety Analysis")
    for item in report["regression_and_safety"]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## 10. Primary Next Gate")
    lines.append(f"- {report['primary_next_gate']}")
    lines.append("")

    lines.append("## Final Decision Labels")
    for label in report["final_decision_labels"]:
        lines.append(f"- {label}")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    validation = load_json(args.augmentation_validation_json)
    training = load_json(args.training_history_json)
    offline = load_json(args.offline_eval_json)
    strict = load_json(args.strict_replay_json)

    best_epoch = int(training.get("best_epoch", 0))
    history = training.get("history", [])
    best_row = next((row for row in history if int(row.get("epoch", -1)) == best_epoch), history[-1] if history else {})

    dataset_valid = validation.get("status") == "pass"
    training_completed = bool(training.get("best_checkpoint") or training.get("final_checkpoint") or history)
    preserved = "ORIGINAL_BC_PERFORMANCE_PRESERVED" in offline.get("classification_labels", [])
    b2_restored = "TRUE_RAW_B2_HARVEST_RESTORED" in offline.get("classification_labels", [])
    c3_restored = "TRUE_RAW_C3_PRODUCE_RESTORED" in offline.get("classification_labels", [])
    off_actor_safe = "STRICT_REPLAY_OFF_ACTOR_SAFE" in strict.get("classification_labels", [])

    primary_gate = _primary_gate(
        dataset_valid=dataset_valid,
        training_completed=training_completed,
        preserved=preserved,
        b2=b2_restored,
        c3=c3_restored,
        off_actor_safe=off_actor_safe,
    )

    final_labels = [
        _bool_label(dataset_valid, "STAGE10D14_AUGMENTATION_DATASET_VALID", "STAGE10D14_NEEDS_AUGMENTATION_FIX"),
        _bool_label(training_completed, "STAGE10D14_TRAINING_COMPLETED", "STAGE10D14_NEEDS_TRAINING_FIX"),
        _bool_label(preserved, "STAGE10D14_ORIGINAL_PERFORMANCE_PRESERVED", "STAGE10D14_NEEDS_AUGMENTATION_FIX"),
        _bool_label(b2_restored and c3_restored, "STAGE10D14_TRUE_RAW_ACTOR_ACTIONS_RESTORED", "STAGE10D14_NEEDS_TRAINING_FIX"),
        _bool_label(off_actor_safe and b2_restored and c3_restored and preserved, "STAGE10D14_SAFE_FOR_UNITY_VISUAL_RERUN", "STAGE10D14_NEEDS_TRAINING_FIX"),
    ]

    report: Dict[str, Any] = {
        "stage": "10D.14",
        "generated_at_utc": utc_now_iso(),
        "purpose_and_constraints": [
            "Targeted supervised adaptation to Unity-like observation distribution only.",
            "No PPO.",
            "No teacher checkpoint change.",
            "No Unity runtime observation remap deployed as a runtime fix.",
            "No ActionDecoder, ActionApplier, or MatchManager change.",
        ],
        "evidence": [
            "Stage10D.12R baseline on true raw Unity observation predicted NoOp at B2 and C3.",
            "Stage10D.13A confirmed current_action/direction patches can restore Harvest/Produce offline but runtime remap is high risk.",
            "Stage10D.13A selected targeted BC augmentation as the preferred next gate.",
        ],
        "augmentation_design": [
            "Family 1: exact true raw Unity observation with teacher labels for B2/C3 targets.",
            "Family 2: positive BC samples converted to Unity-like NoOp-state observations while preserving action labels.",
            "Family 3: base-centric local context variants for Produce restoration.",
            "Family 4: negative controls to limit shortcut overgeneralization.",
        ],
        "dataset_validation": {
            "status": validation.get("status"),
            "classification_labels": validation.get("classification_labels"),
            "primary_next_gate": validation.get("primary_next_gate"),
            "label_leakage_pass": "NO_OBSERVATION_LABEL_LEAKAGE_CONFIRMED" in validation.get("classification_labels", []),
            "target_distribution_acceptable": "TARGET_DISTRIBUTION_ACCEPTABLE" in validation.get("classification_labels", []),
        },
        "training_summary": {
            "best_epoch": best_epoch,
            "history_length": len(history),
            "best_checkpoint": training.get("best_checkpoint"),
            "final_checkpoint": training.get("final_checkpoint"),
            "true_raw_B2_p_harvest": best_row.get("true_raw_B2_p_harvest"),
            "true_raw_C3_p_produce": best_row.get("true_raw_C3_p_produce"),
        },
        "offline_original_validation": offline.get("original_validation_eval", {}),
        "offline_augmented_validation": {
            "augmented_validation_eval": offline.get("augmented_validation_eval", {}),
            "augmented_target_success": offline.get("augmented_target_success", {}),
        },
        "strict_replay_summary": {
            "B2": strict.get("B2", {}),
            "C3": strict.get("C3", {}),
            "off_actor_non_noop_count": strict.get("off_actor_non_noop_count"),
            "global_predicted_noop_share": strict.get("global_predicted_noop_share"),
            "actor_predicted_noop_share": strict.get("actor_predicted_noop_share"),
            "baseline_deltas": strict.get("comparison_with_stage10d12r_baseline", {}),
        },
        "regression_and_safety": [
            f"Original BC performance preserved: {preserved}",
            f"True raw B2 restored: {b2_restored}",
            f"True raw C3 restored: {c3_restored}",
            f"Off-actor safety acceptable: {off_actor_safe}",
        ],
        "final_decision_labels": final_labels,
        "primary_next_gate": primary_gate,
    }

    output_path = resolve_path(args.output_md).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_md(report), encoding="utf-8")
    print(output_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())