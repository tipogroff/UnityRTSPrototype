#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Mapping

import numpy as np
import torch

from stage10d14_common import (
    B2_FLAT,
    C3_FLAT,
    DEFAULT_REPORTS_DIR,
    DEFAULT_STAGE10D8_CHECKPOINT,
    DEFAULT_TRUE_RAW_CAPTURE,
    evaluate_action_type_subset,
    evaluate_augmented_target_success,
    load_json,
    load_model_strict,
    load_true_raw_capture_tensor,
    read_jsonl,
    resolve_path,
    run_model_action_type_probs,
    summarize_true_raw_predictions,
    utc_now_iso,
    write_json,
)
from student_bc_loader import load_bc_ready_dataset


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.14 offline eval and strict replay on true raw Unity observation")
    p.add_argument("--bc-ready-dir", type=Path, required=True)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--true-raw-capture", type=Path, default=Path(DEFAULT_TRUE_RAW_CAPTURE))
    p.add_argument(
        "--stage10d8-validation-json",
        type=Path,
        default=Path("python/week6_student/runs/legacy032_v2_semantic_bc_stage10d8_20260503T093718Z/validation_metrics.json"),
    )
    p.add_argument(
        "--baseline-strict-replay-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d12r_strict_replay_probe_results.json"),
    )
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path(DEFAULT_REPORTS_DIR) / "stage10d14_offline_eval_report.json",
    )
    p.add_argument(
        "--strict-replay-output-json",
        type=Path,
        default=Path(DEFAULT_REPORTS_DIR) / "stage10d14_true_raw_strict_replay_report.json",
    )
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--batch-size", type=int, default=64)
    return p.parse_args()


def _performance_preserved(eval_metrics: Mapping[str, Any], baseline_metrics: Mapping[str, Any]) -> tuple[bool, Dict[str, Any]]:
    thresholds = {
        "actor_action_accuracy_min": float(baseline_metrics.get("val_actor_cell_action_type_accuracy", 0.0)) - 0.01,
        "actor_non_noop_recall_min": float(baseline_metrics.get("val_actor_cell_non_noop_recall", 0.0)) - 0.01,
        "worker_harvest_recall_min": float(baseline_metrics.get("val_worker_harvest_proxy_accuracy", 0.0)) - 0.02,
        "base_produce_recall_min": float(baseline_metrics.get("val_base_produce_proxy_accuracy", 0.0)) - 0.02,
    }
    checks = {
        "actor_action_accuracy": float(eval_metrics.get("actor_cell_action_type_accuracy", 0.0)) >= thresholds["actor_action_accuracy_min"],
        "actor_non_noop_recall": float(eval_metrics.get("actor_cell_non_noop_recall", 0.0)) >= thresholds["actor_non_noop_recall_min"],
        "worker_harvest_recall": float(eval_metrics.get("worker_harvest_recall", 0.0)) >= thresholds["worker_harvest_recall_min"],
        "base_produce_recall": float(eval_metrics.get("base_produce_recall", 0.0)) >= thresholds["base_produce_recall_min"],
    }
    return bool(all(checks.values())), {"thresholds": thresholds, "checks": checks}


def main() -> int:
    args = parse_args()
    bc_ready_dir = resolve_path(args.bc_ready_dir).resolve()
    checkpoint_path = resolve_path(args.checkpoint).resolve()
    output_json = resolve_path(args.output_json).resolve()
    strict_output_json = resolve_path(args.strict_replay_output_json).resolve()
    device = torch.device(args.device)

    dataset = load_bc_ready_dataset(bc_ready_dir)
    augmentation_manifest = load_json(bc_ready_dir / "stage10d14_augmentation_manifest.json")
    original_validation_count = int(augmentation_manifest["counts"]["original_validation_count"])
    augmented_validation_metadata = read_jsonl(bc_ready_dir / "stage10d14_augmented_sample_metadata_validation.jsonl")

    model = load_model_strict(checkpoint_path, device=device)

    original_eval = evaluate_action_type_subset(
        model,
        dataset.validation.input_tensor,
        dataset.validation.target_action_branches,
        indices=np.arange(original_validation_count, dtype=np.int64),
        device=device,
        batch_size=args.batch_size,
    )
    augmented_eval = evaluate_action_type_subset(
        model,
        dataset.validation.input_tensor,
        dataset.validation.target_action_branches,
        indices=np.arange(original_validation_count, dataset.validation.input_tensor.shape[0], dtype=np.int64),
        device=device,
        batch_size=args.batch_size,
    )
    targeted_eval = evaluate_augmented_target_success(
        model,
        dataset.validation.input_tensor,
        augmented_validation_metadata,
        original_count=original_validation_count,
        device=device,
        batch_size=args.batch_size,
    )

    runtime_map = load_true_raw_capture_tensor(args.true_raw_capture)
    true_raw_probs = run_model_action_type_probs(model, runtime_map, device)
    true_raw_summary = summarize_true_raw_predictions(true_raw_probs, runtime_map)

    baseline_validation_payload = load_json(args.stage10d8_validation_json)
    baseline_validation_metrics = baseline_validation_payload.get("best_validation_metrics", baseline_validation_payload)
    preserved, preservation_details = _performance_preserved(original_eval, baseline_validation_metrics)

    baseline_strict = load_json(args.baseline_strict_replay_json)
    baseline_b2 = baseline_strict.get("baseline_inference", {}).get("B2", {})
    baseline_c3 = baseline_strict.get("baseline_inference", {}).get("C3", {})
    baseline_off_actor_non_noop = int(baseline_strict.get("off_actor_non_noop_count", 0))

    b2_restored = bool(
        true_raw_summary["B2"]["predicted_action"] == "harvest"
        or float(true_raw_summary["B2"]["p_harvest"]) > 0.5
    )
    c3_restored = bool(
        true_raw_summary["C3"]["predicted_action"] == "produce"
        or float(true_raw_summary["C3"]["p_produce"]) > 0.5
    )
    off_actor_safe = bool(int(true_raw_summary["off_actor_non_noop_count"]) <= baseline_off_actor_non_noop + 2)

    offline_labels = [
        "ORIGINAL_BC_PERFORMANCE_PRESERVED" if preserved else "ORIGINAL_BC_PERFORMANCE_REGRESSED",
        "TRUE_RAW_B2_HARVEST_RESTORED" if b2_restored else "AUGMENTED_STUDENT_NOT_READY",
        "TRUE_RAW_C3_PRODUCE_RESTORED" if c3_restored else "AUGMENTED_STUDENT_NOT_READY",
        "TRUE_RAW_ACTOR_ACTIONS_RESTORED" if b2_restored and c3_restored else "AUGMENTED_STUDENT_NOT_READY",
        "OFF_ACTOR_MISLOCALIZATION_NOT_DETECTED" if off_actor_safe else "OFF_ACTOR_MISLOCALIZATION_DETECTED",
        "AUGMENTED_STUDENT_READY_FOR_STRICT_REPLAY" if preserved and b2_restored and c3_restored and off_actor_safe else "AUGMENTED_STUDENT_NOT_READY",
    ]
    offline_gate = (
        "GO_FOR_STAGE10D14_STRICT_REPLAY_WITH_AUGMENTED_STUDENT"
        if preserved and b2_restored and c3_restored and off_actor_safe
        else "GO_FOR_STAGE10D14_AUGMENTATION_OR_TRAINING_FIX"
    )

    offline_report: Dict[str, Any] = {
        "stage": "10D.14",
        "task": "offline_eval_augmented_student_on_true_raw",
        "generated_at_utc": utc_now_iso(),
        "bc_ready_dir": bc_ready_dir.as_posix(),
        "checkpoint_path": checkpoint_path.as_posix(),
        "original_validation_eval": original_eval,
        "augmented_validation_eval": augmented_eval,
        "augmented_target_success": targeted_eval,
        "true_raw_eval": true_raw_summary,
        "baseline_validation_metrics": baseline_validation_metrics,
        "original_performance_preservation": preservation_details,
        "classification_labels": offline_labels,
        "primary_next_gate": offline_gate,
    }
    write_json(output_json, offline_report)

    strict_labels = [
        "STRICT_REPLAY_AUGMENTED_MODEL_LOADED",
        "STRICT_REPLAY_TRUE_RAW_B2_HARVEST" if b2_restored else "STRICT_REPLAY_NOT_READY_FOR_UNITY",
        "STRICT_REPLAY_TRUE_RAW_C3_PRODUCE" if c3_restored else "STRICT_REPLAY_NOT_READY_FOR_UNITY",
        "STRICT_REPLAY_TRUE_RAW_ACTOR_ACTIONS_RESTORED" if b2_restored and c3_restored else "STRICT_REPLAY_NOT_READY_FOR_UNITY",
        "STRICT_REPLAY_OFF_ACTOR_SAFE" if off_actor_safe else "STRICT_REPLAY_OFF_ACTOR_RISK",
        "STRICT_REPLAY_READY_FOR_UNITY_VISUAL_RERUN" if b2_restored and c3_restored and off_actor_safe else "STRICT_REPLAY_NOT_READY_FOR_UNITY",
    ]
    strict_gate = (
        "GO_FOR_STAGE10D15_UNITY_VISUAL_RERUN_WITH_AUGMENTED_STUDENT"
        if b2_restored and c3_restored and off_actor_safe
        else "GO_FOR_STAGE10D14_AUGMENTATION_OR_TRAINING_FIX"
    )
    strict_report: Dict[str, Any] = {
        "stage": "10D.14",
        "task": "true_raw_strict_replay",
        "generated_at_utc": utc_now_iso(),
        "checkpoint_path": checkpoint_path.as_posix(),
        "model_loaded_strict": True,
        "B2": true_raw_summary["B2"],
        "C3": true_raw_summary["C3"],
        "friendly_actor_predictions": true_raw_summary["friendly_actor_predictions"],
        "off_actor_non_noop_count": int(true_raw_summary["off_actor_non_noop_count"]),
        "global_predicted_noop_share": float(true_raw_summary["global_predicted_noop_share"]),
        "actor_predicted_noop_share": float(true_raw_summary["actor_predicted_noop_share"]),
        "comparison_with_stage10d12r_baseline": {
            "B2_delta_p_harvest": float(true_raw_summary["B2"]["p_harvest"] - float(baseline_b2.get("p_harvest", 0.0))),
            "B2_delta_p_noop": float(true_raw_summary["B2"]["p_noop"] - float(baseline_b2.get("p_noop", 0.0))),
            "C3_delta_p_produce": float(true_raw_summary["C3"]["p_produce"] - float(baseline_c3.get("p_produce", 0.0))),
            "C3_delta_p_noop": float(true_raw_summary["C3"]["p_noop"] - float(baseline_c3.get("p_noop", 0.0))),
        },
        "classification_labels": strict_labels,
        "primary_next_gate": strict_gate,
    }
    write_json(strict_output_json, strict_report)

    print(output_json.as_posix())
    print(strict_output_json.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())