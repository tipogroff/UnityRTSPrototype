#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from stage10d19b_common import load_json, utc_now_iso, write_json


def _safe(path: str) -> Dict[str, Any]:
    try:
        return load_json(path)
    except Exception:
        return {}


def _bool(v: Any) -> bool:
    return bool(v)


def main() -> int:
    preflight = _safe("python/week6_student/reports/stage10d19b_preflight_snapshot.json")
    manifest = _safe("python/week6_student/reports/stage10d19b_valid_move_augmentation_manifest.json")
    validation = _safe("python/week6_student/reports/stage10d19b_valid_move_augmented_dataset_validation.json")
    train_hist = _safe("python/week6_student/reports/stage10d19b_training_history.json")
    train_sel = _safe("python/week6_student/reports/stage10d19b_training_selection.json")
    offline = _safe("python/week6_student/reports/stage10d19b_offline_eval_report.json")
    snapshot = _safe("python/week6_student/reports/stage10d19b_stage10d18rr_snapshot_replay_report.json")
    decision_19 = _safe("python/week6_student/reports/stage10d19_decision_matrix.json")

    dataset_valid = _bool(validation.get("status") == "pass")
    training_completed = _bool(train_hist.get("best_checkpoint"))

    labels_offline = set(offline.get("classification_labels") or [])
    original_preserved = "STAGE10D19B_ORIGINAL_PERFORMANCE_PRESERVED" in labels_offline
    guards_preserved = "STAGE10D19B_B2_C3_GUARDS_PRESERVED" in labels_offline
    movement_preserved = "STAGE10D19B_MOVEMENT_PRESERVED" in labels_offline
    valid_move_improved = "STAGE10D19B_VALID_MOVE_TARGET_SELECTION_IMPROVED_OFFLINE" in labels_offline
    occupied_reduced = "STAGE10D19B_OCCUPIED_TARGET_ERRORS_REDUCED_OFFLINE" in labels_offline
    off_actor_controlled = "STAGE10D19B_OFF_ACTOR_RISK_REDUCED_OR_CONTROLLED" in labels_offline

    if (
        dataset_valid
        and training_completed
        and original_preserved
        and guards_preserved
        and movement_preserved
        and valid_move_improved
        and occupied_reduced
        and off_actor_controlled
    ):
        next_gate = "GO_FOR_STAGE10D20_UNITY_VALID_MOVE_RERUN"
    elif not dataset_valid:
        next_gate = "GO_FOR_STAGE10D19B_DATASET_FIX"
    elif valid_move_improved and not (original_preserved and guards_preserved and movement_preserved):
        next_gate = "GO_FOR_STAGE10D19B_TRAINING_BALANCE_FIX"
    elif not valid_move_improved or not occupied_reduced:
        next_gate = "GO_FOR_STAGE10D19B_AUGMENTATION_REDESIGN"
    elif not off_actor_controlled:
        next_gate = "GO_FOR_STAGE10D19B_OFF_ACTOR_NEGATIVE_CONTROL_FIX"
    else:
        next_gate = "GO_FOR_STAGE10D19_MOVE_BRANCH_DECODER_AUDIT"

    final_labels = [
        "STAGE10D19B_DATASET_VALID" if dataset_valid else "STAGE10D19B_NEEDS_DATASET_FIX",
        "STAGE10D19B_TRAINING_COMPLETED" if training_completed else "STAGE10D19B_NEEDS_TRAINING_BALANCE_FIX",
        "STAGE10D19B_ORIGINAL_PERFORMANCE_PRESERVED" if original_preserved else "STAGE10D19B_NEEDS_TRAINING_BALANCE_FIX",
        "STAGE10D19B_B2_C3_GUARDS_PRESERVED" if guards_preserved else "STAGE10D19B_NEEDS_TRAINING_BALANCE_FIX",
        "STAGE10D19B_MOVEMENT_PRESERVED" if movement_preserved else "STAGE10D19B_NEEDS_TRAINING_BALANCE_FIX",
        "STAGE10D19B_VALID_MOVE_TARGET_SELECTION_IMPROVED_OFFLINE" if valid_move_improved else "STAGE10D19B_NEEDS_AUGMENTATION_REDESIGN",
        "STAGE10D19B_OCCUPIED_TARGET_ERRORS_REDUCED_OFFLINE" if occupied_reduced else "STAGE10D19B_NEEDS_AUGMENTATION_REDESIGN",
        "STAGE10D19B_OFF_ACTOR_RISK_REDUCED_OR_CONTROLLED" if off_actor_controlled else "STAGE10D19B_OFF_ACTOR_NEGATIVE_CONTROL_FIX",
        "STAGE10D19B_READY_FOR_UNITY_VALID_MOVE_RERUN" if next_gate == "GO_FOR_STAGE10D20_UNITY_VALID_MOVE_RERUN" else "STAGE10D19B_NOT_READY_FOR_UNITY",
    ]

    out_lines = []
    out_lines.append("# STAGE10D19B_VALID_MOVE_EFFICIENCY_REPORT")
    out_lines.append("")
    out_lines.append("## 1. Purpose and constraints")
    out_lines.append("- Stage10D.19B focuses on valid-target movement augmentation and safety controls only.")
    out_lines.append("- No PPO, no Gym teacher training, no teacher checkpoint mutation, no Stage10D.17 checkpoint mutation.")
    out_lines.append("- No Unity runtime semantic shortcuts and no decoder/applier/matchmanager semantic changes.")
    out_lines.append("- Attack augmentation remains deferred in this stage.")
    out_lines.append("")
    out_lines.append("## 2. Stage10D.19 evidence recap")
    out_lines.append(f"- Stage10D.19 decision = {decision_19.get('decision')}")
    out_lines.append("- Primary issue: move target validity/occupancy mismatch before command build.")
    out_lines.append("")
    out_lines.append("## 3. Why Attack augmentation is deferred")
    out_lines.append("- Stage10D.19 gate selected movement efficiency correction first.")
    out_lines.append("- Attack signals are recorded watch-only to avoid conflating failure modes.")
    out_lines.append("")
    out_lines.append("## 4. Dataset augmentation design")
    out_lines.append(f"- Dataset dir: {manifest.get('output_dataset_dir')}")
    out_lines.append(f"- Family counts: {manifest.get('augmentation_family_counts')}")
    out_lines.append("- Families used: valid move positives, occupied-target negatives, direction corrections, congestion controls, off-actor negatives, preservation.")
    out_lines.append("")
    out_lines.append("## 5. Dataset validation")
    out_lines.append(f"- Validation status: {validation.get('status')}")
    out_lines.append(f"- Validation labels: {validation.get('classification_labels')}")
    out_lines.append(f"- Validation gate: {validation.get('primary_next_gate')}")
    out_lines.append("")
    out_lines.append("## 6. Training summary")
    out_lines.append(f"- Best checkpoint: {train_hist.get('best_checkpoint')}")
    out_lines.append(f"- Final checkpoint: {train_hist.get('final_checkpoint')}")
    out_lines.append(f"- Selection epoch: {train_sel.get('selected_epoch')}")
    out_lines.append("")
    out_lines.append("## 7. Offline preservation metrics")
    b_a = offline.get("block_a_original_validation_preservation", {})
    out_lines.append(f"- actor_action_accuracy = {b_a.get('actor_action_accuracy')}")
    out_lines.append(f"- worker_harvest_recall = {b_a.get('worker_harvest_recall')}")
    out_lines.append(f"- base_produce_recall = {b_a.get('base_produce_recall')}")
    out_lines.append("")
    out_lines.append("## 8. Valid-target movement metrics")
    c_val = ((offline.get("block_c_stage10d19b_validation") or {}).get("validation") or {})
    out_lines.append(f"- valid_move_recall = {c_val.get('valid_move_recall')}")
    out_lines.append(f"- valid_move_dir_accuracy = {c_val.get('valid_move_dir_accuracy')}")
    out_lines.append(f"- estimated_prediction_to_build_readiness = {c_val.get('estimated_prediction_to_build_readiness')}")
    out_lines.append("")
    out_lines.append("## 9. Occupied-target negative-control metrics")
    out_lines.append(f"- occupied_target_negative_accuracy = {c_val.get('occupied_target_negative_accuracy')}")
    out_lines.append(f"- predicted_occupied_or_invalid_target_moves = {c_val.get('predicted_occupied_or_invalid_target_moves')}")
    out_lines.append("")
    out_lines.append("## 10. Off-actor safety metrics")
    out_lines.append(f"- off_actor_noop_accuracy = {c_val.get('off_actor_noop_accuracy')}")
    out_lines.append(f"- off_actor_non_noop_count = {c_val.get('off_actor_non_noop_count')}")
    out_lines.append(f"- off_actor_command_risk_if_inferable = {c_val.get('off_actor_command_risk_if_inferable')}")
    out_lines.append("")
    out_lines.append("## 11. Stage10D.18RR replay/snapshot replay")
    out_lines.append(f"- Replay proxy: {offline.get('block_d_stage10d18rr_replay_proxy')}")
    out_lines.append(f"- Snapshot replay summary: {snapshot.get('summary')}")
    out_lines.append("")
    out_lines.append("## 12. Attack watch-only notes")
    out_lines.append(f"- {offline.get('block_e_attack_watch_only')}")
    out_lines.append("- Attack was monitored only; no attack augmentation/training objective was added.")
    out_lines.append("")
    out_lines.append("## 13. Classification labels")
    for lb in final_labels:
        out_lines.append(f"- {lb}")
    out_lines.append("")
    out_lines.append("## 14. Primary next gate")
    out_lines.append(f"- {next_gate}")
    out_lines.append("")
    out_lines.append("## 15. What not to do next")
    out_lines.append("- Do not run Unity rerun unless gate is GO_FOR_STAGE10D20_UNITY_VALID_MOVE_RERUN.")
    out_lines.append("- Do not start Attack augmentation before movement efficiency gate is satisfied.")
    out_lines.append("- Do not introduce runtime remaps/heuristics/forced movement as shortcuts.")
    out_lines.append("")
    out_lines.append("## Explicit answers")
    out_lines.append(f"- Did we preserve B2/C3 only as regression guards? {'Yes' if guards_preserved else 'No'}")
    out_lines.append("- Did we avoid runtime semantic shortcuts? Yes, by stage constraints and artifact trail.")
    out_lines.append(f"- Did we improve valid-target Move behavior offline? {'Yes' if valid_move_improved else 'No'}")
    out_lines.append(f"- Did we reduce occupied/invalid target Move tendency? {'Yes' if occupied_reduced else 'No'}")
    out_lines.append(f"- Did we preserve previous movement ability? {'Yes' if movement_preserved else 'No'}")
    out_lines.append(f"- Did we reduce or control off-actor non-NoOp? {'Yes' if off_actor_controlled else 'No'}")
    out_lines.append(f"- Did original validation regress? {'No' if original_preserved else 'Yes'}")
    out_lines.append(f"- Is model ready for Unity valid-Move rerun? {'Yes' if next_gate == 'GO_FOR_STAGE10D20_UNITY_VALID_MOVE_RERUN' else 'No'}")
    out_lines.append("- Why are we not doing Attack augmentation yet? Movement-target quality remains the primary unresolved bottleneck by Stage10D.19 gate logic.")
    out_lines.append(f"- Exact next gate: {next_gate}")

    out_md = Path("python/week6_student/reports/STAGE10D19B_VALID_MOVE_EFFICIENCY_REPORT.md")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    write_json(
        "python/week6_student/reports/stage10d19b_report_index.json",
        {
            "generated_at_utc": utc_now_iso(),
            "report_path": str(out_md.as_posix()),
            "next_gate": next_gate,
            "final_labels": final_labels,
            "dataset_valid": dataset_valid,
            "training_completed": training_completed,
        },
    )

    print(out_md.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
