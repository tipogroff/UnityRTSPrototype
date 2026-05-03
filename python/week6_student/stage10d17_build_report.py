#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

from stage10d17_common import load_json, resolve_path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.17 markdown report builder")
    p.add_argument("--audit-json", type=Path, required=True)
    p.add_argument("--augmentation-manifest", type=Path, required=True)
    p.add_argument("--validation-json", type=Path, required=True)
    p.add_argument("--training-selection-json", type=Path, required=True)
    p.add_argument("--offline-eval-json", type=Path, required=True)
    p.add_argument("--snapshot-replay-json", type=Path, default=None)
    p.add_argument(
        "--output-md",
        type=Path,
        default=Path("python/week6_student/reports/STAGE10D17_MOVEMENT_LABEL_AUGMENTATION_REPORT.md"),
    )
    return p.parse_args()


def _fmt_pct(v: float) -> str:
    return f"{100.0 * float(v):.2f}%"


def _decide_gate(validation: Dict[str, Any], train_sel: Dict[str, Any], offline: Dict[str, Any]) -> tuple[str, list[str]]:
    reasons = []
    if validation.get("status") != "pass":
        reasons.append("Dataset validation failed")
        return "GO_FOR_STAGE10D17_MOVEMENT_AUGMENTATION_FIX", reasons

    best = train_sel.get("best_metrics", {})
    move_recall = float(best.get("movement_augmented_val_move_recall", 0.0))
    replay_move = float(best.get("stage10d16_replay_move_success_rate", 0.0))
    b2_h = float(best.get("true_raw_B2_p_harvest", 0.0))
    b2_n = float(best.get("true_raw_B2_p_noop", 1.0))
    c3_p = float(best.get("true_raw_C3_p_produce", 0.0))
    c3_n = float(best.get("true_raw_C3_p_noop", 1.0))

    if move_recall < 0.10:
        reasons.append("Movement recall too low")
    if replay_move < 0.10:
        reasons.append("Stage10D16 replay move success too low")
    if not (b2_h >= b2_n and c3_p >= c3_n):
        reasons.append("True-raw B2/C3 priorities regressed")

    off = offline.get("block_b_true_raw", {})
    if int(off.get("off_actor_non_noop_count", 0)) > 5:
        reasons.append("Off-actor non-noop increased")

    if reasons:
        return "GO_FOR_STAGE10D17_MOVEMENT_BC_REBALANCE", reasons
    return "GO_FOR_STAGE10D18_RUNTIME_BC_REDEPLOY_EVAL", ["All Stage10D.17 gates passed"]


def main() -> int:
    args = parse_args()

    audit = load_json(args.audit_json)
    aug = load_json(args.augmentation_manifest)
    val = load_json(args.validation_json)
    train_sel = load_json(args.training_selection_json)
    offline = load_json(args.offline_eval_json)
    snap = load_json(args.snapshot_replay_json) if args.snapshot_replay_json is not None else None

    next_gate, gate_reasons = _decide_gate(val, train_sel, offline)

    best = train_sel.get("best_metrics", {})
    move_counts = aug.get("move_counts", {})
    counts = aug.get("counts", {})
    dist = val.get("distribution", {})
    b_true = offline.get("block_b_true_raw", {})
    c_val = offline.get("block_c_movement_augmented_subset", {}).get("validation", {})
    d_val = offline.get("block_d_stage10d16_replay", {}).get("validation", {})

    lines = [
        "# STAGE10D.17 Movement Label Augmentation and Post-Production Policy Expansion",
        "",
        "## Summary",
        f"- Audit primary gate: {audit.get('primary_next_gate', 'unknown')}",
        f"- Dataset validation status: {val.get('status', 'unknown')}",
        f"- Training selected epoch: {train_sel.get('selected_epoch', 'unknown')}",
        f"- Final Stage10D.17 gate: {next_gate}",
        "",
        "## 1. Movement Label Audit",
        f"- Classification labels: {', '.join(audit.get('classification_labels', []))}",
        f"- Train actor Move before/after: {audit.get('train_distribution', {}).get('actor_action_type_counts', {}).get('Move', 0)} -> {audit.get('augmentation_projection', {}).get('projected_train', {}).get('actor_action_type_counts', {}).get('Move', 0)}",
        f"- Validation actor Move before/after: {audit.get('validation_distribution', {}).get('actor_action_type_counts', {}).get('Move', 0)} -> {audit.get('augmentation_projection', {}).get('projected_validation', {}).get('actor_action_type_counts', {}).get('Move', 0)}",
        "",
        "## 2. Movement Augmented Dataset Build",
        f"- Original train/val: {counts.get('original_train', 0)} / {counts.get('original_validation', 0)}",
        f"- Augmented train/val: {counts.get('augmented_train', 0)} / {counts.get('augmented_validation', 0)}",
        f"- Merged train/val: {counts.get('merged_train', 0)} / {counts.get('merged_validation', 0)}",
        f"- Family counts: {aug.get('family_counts', {})}",
        f"- Move by unit: {move_counts.get('by_unit_type', {})}",
        f"- Move by direction: {move_counts.get('by_direction', {})}",
        "",
        "## 3. Dataset Validation",
        f"- Labels: {', '.join(val.get('classification_labels', []))}",
        f"- Branch bounds valid: {all(val.get('branch_bounds', {}).get('train', {}).values()) and all(val.get('branch_bounds', {}).get('validation', {}).values())}",
        f"- Leakage confirmed absent: {val.get('label_leakage', {}).get('no_leakage_confirmed', False)}",
        f"- Target distribution acceptable: {dist.get('move_increase', False) and dist.get('no_catastrophic_noop_shift', False) and dist.get('negative_controls_present', False)}",
        "",
        "## 4. Supervised Fine-Tune",
        f"- Movement augmented val move recall: {_fmt_pct(best.get('movement_augmented_val_move_recall', 0.0))}",
        f"- Movement augmented val move-dir accuracy: {_fmt_pct(best.get('movement_augmented_val_move_dir_accuracy', 0.0))}",
        f"- Stage10D16 replay move success: {_fmt_pct(best.get('stage10d16_replay_move_success_rate', 0.0))}",
        f"- Original val actor action-type accuracy: {_fmt_pct(best.get('original_val_actor_action_type_accuracy', 0.0))}",
        f"- Worker harvest recall: {_fmt_pct(best.get('worker_harvest_recall', 0.0))}",
        f"- Base produce recall: {_fmt_pct(best.get('base_produce_recall', 0.0))}",
        f"- True raw B2 p_harvest vs p_noop: {_fmt_pct(best.get('true_raw_B2_p_harvest', 0.0))} vs {_fmt_pct(best.get('true_raw_B2_p_noop', 0.0))}",
        f"- True raw C3 p_produce vs p_noop: {_fmt_pct(best.get('true_raw_C3_p_produce', 0.0))} vs {_fmt_pct(best.get('true_raw_C3_p_noop', 0.0))}",
        "",
        "## 5. Offline Eval",
        f"- Block A original validation actor acc: {_fmt_pct(offline.get('block_a_original_validation', {}).get('actor_action_type_accuracy', 0.0))}",
        f"- Block B true raw off-actor non-noop: {b_true.get('off_actor_non_noop_count', 0)}",
        f"- Block C validation move recall: {_fmt_pct(c_val.get('move_recall', 0.0))}",
        f"- Block C validation move-dir accuracy: {_fmt_pct(c_val.get('move_dir_accuracy', 0.0))}",
        f"- Block D validation replay move success: {_fmt_pct(d_val.get('produced_unit_move_success_rate', 0.0))}",
    ]

    if snap is not None:
        lines.extend(
            [
                "",
                "## 6. Snapshot Replay (Optional)",
                f"- Validation replay samples: {snap.get('validation', {}).get('sample_count', 0)}",
                f"- Validation replay move success: {_fmt_pct(snap.get('validation', {}).get('produced_unit_move_success_rate', 0.0))}",
                f"- Validation replay off-actor non-noop: {snap.get('validation', {}).get('off_actor_non_noop_count', 0)}",
            ]
        )

    lines.extend(
        [
            "",
            "## 7. Constraints and Non-Claims",
            "- No PPO used",
            "- No teacher checkpoint mutation",
            "- No runtime ActionDecoder/ActionApplier semantics mutation",
            "- No runtime movement forcing",
            "",
            "## 8. Final Decision",
            f"- Selected next gate: {next_gate}",
            f"- Gate reasons: {', '.join(gate_reasons)}",
        ]
    )

    out_path = resolve_path(args.output_md)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
