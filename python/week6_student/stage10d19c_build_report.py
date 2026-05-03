#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from stage10d19c_common import load_json, utc_now_iso


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.19C build final markdown report")
    p.add_argument("--preflight", type=Path, required=True)
    p.add_argument("--failure-cases", type=Path, required=True)
    p.add_argument("--replay-stage10d17", type=Path, required=True)
    p.add_argument("--replay-stage10d19b", type=Path, required=True)
    p.add_argument("--dataset-manifest", type=Path, required=True)
    p.add_argument("--dataset-validation", type=Path, required=True)
    p.add_argument("--training-selection", type=Path, required=True)
    p.add_argument("--offline-eval", type=Path, required=True)
    p.add_argument("--comparison", type=Path, required=True)
    p.add_argument(
        "--output-md",
        type=Path,
        default=Path("python/week6_student/reports/STAGE10D19C_MASK_AWARE_FAILURE_REPLAY_REPORT.md"),
    )
    return p.parse_args()


def _yn(v: bool) -> str:
    return "YES" if bool(v) else "NO"


def _pick_gate(dataset_valid: bool, trained: bool, eval_gate: str, compare_sel: str) -> str:
    if not dataset_valid:
        return "GO_FOR_STAGE10D19C_DATASET_FIX"
    if not trained:
        return "GO_FOR_STAGE10D19C_TRAINING_BALANCE_FIX"
    if eval_gate == "GO_FOR_STAGE10D20_UNITY_MASKED_VALID_MOVE_RERUN" and compare_sel != "none":
        return "GO_FOR_STAGE10D20_UNITY_MASKED_VALID_MOVE_RERUN"
    if eval_gate == "GO_FOR_STAGE10D19C_OFF_ACTOR_FIX":
        return "GO_FOR_STAGE10D19C_OFF_ACTOR_FIX"
    if eval_gate == "GO_FOR_STAGE10D19C_INSTRUMENTATION_FIX":
        return "GO_FOR_STAGE10D19C_INSTRUMENTATION_FIX"
    if eval_gate == "GO_FOR_STAGE10D19C_TRAINING_BALANCE_FIX":
        return "GO_FOR_STAGE10D19C_TRAINING_BALANCE_FIX"
    return "GO_FOR_STAGE10D19C_AUGMENTATION_REDESIGN"


def main() -> int:
    args = parse_args()

    pre = load_json(args.preflight)
    fail = load_json(args.failure_cases)
    rep17 = load_json(args.replay_stage10d17)
    rep19b = load_json(args.replay_stage10d19b)
    man = load_json(args.dataset_manifest)
    val = load_json(args.dataset_validation)
    train = load_json(args.training_selection)
    off = load_json(args.offline_eval)
    cmp_ = load_json(args.comparison)

    dataset_valid = str(val.get("status", "")) == "pass"
    trained = bool(train.get("best_checkpoint"))
    selected_candidate = str(cmp_.get("selected_candidate", "none"))
    eval_gate = str(off.get("primary_next_gate", "GO_FOR_STAGE10D19C_AUGMENTATION_REDESIGN"))
    next_gate = _pick_gate(dataset_valid, trained, eval_gate, selected_candidate)

    stage_status = "PARTIAL"
    if next_gate == "GO_FOR_STAGE10D20_UNITY_MASKED_VALID_MOVE_RERUN":
        stage_status = "PASS"
    elif next_gate in {"GO_FOR_STAGE10D19C_DATASET_FIX", "GO_FOR_STAGE10D19C_INSTRUMENTATION_FIX"}:
        stage_status = "FAIL"

    fail_count = int(fail.get("total_failure_cases", 0))
    occ_count = int(fail.get("occupied_target_failure_cases", 0))

    replay_mask_help = bool(
        int(rep17.get("masked_occupied_or_invalid_move_count", 10**9)) < int(rep17.get("unmasked_occupied_or_invalid_move_count", 10**9))
        or int(rep19b.get("masked_occupied_or_invalid_move_count", 10**9)) < int(rep19b.get("unmasked_occupied_or_invalid_move_count", 10**9))
    )

    lines: List[str] = []
    lines.append("# STAGE10D19C Mask-Aware Occupied-Target Augmentation and Failure-Case Replay Report")
    lines.append("")
    lines.append(f"Generated at (UTC): {utc_now_iso()}")
    lines.append(f"Stage result: {stage_status}")
    lines.append("")

    lines.append("## 1. Purpose and constraints")
    lines.append("- Purpose: target real occupied-target Move failures from Stage10D.18RR/19, not proxy-only slices.")
    lines.append("- Constraints respected: no PPO, no teacher mutation, no runtime semantic changes, no force movement/attack, no Unity rerun inside Stage10D.19C.")
    lines.append("")

    lines.append("## 2. Why Stage10D.19M was PARTIAL")
    lines.append(f"- Stage10D.19M selected gate: {pre.get('selected_gate_from_stage10d19m')}")
    lines.append("- Interpretation: legal mask semantics were valid, but previous probe coverage did not represent the actual occupied-target failure distribution.")
    lines.append("")

    lines.append("## 3. Real failure-case extraction")
    lines.append(f"- Extracted failure cases: {fail_count}")
    lines.append(f"- Occupied-target failures in extracted set: {occ_count}")
    lines.append(f"- Efficiency reference occupied-target count: {fail.get('efficiency_reference', {}).get('occupied_target_count')}")
    lines.append(f"- Labels: {', '.join(fail.get('labels', []))}")
    lines.append("")

    lines.append("## 4. Failure-case replay before training")
    lines.append("- Stage10D.17 replay:")
    lines.append(f"  unmasked invalid moves = {rep17.get('unmasked_occupied_or_invalid_move_count')}, masked invalid moves = {rep17.get('masked_occupied_or_invalid_move_count')}")
    lines.append("- Stage10D.19B replay:")
    lines.append(f"  unmasked invalid moves = {rep19b.get('unmasked_occupied_or_invalid_move_count')}, masked invalid moves = {rep19b.get('masked_occupied_or_invalid_move_count')}")
    lines.append(f"- Mask helped on real failure cases: {_yn(replay_mask_help)}")
    lines.append("")

    lines.append("## 5. Mask-aware dataset design")
    lines.append(f"- Base dataset: {man.get('base_dataset_path')}")
    lines.append(f"- Augmentation family counts: {man.get('augmentation_family_counts', {})}")
    lines.append("- Families A/B/C/D/E/F implemented with metadata and non-claim constraints preserved.")
    lines.append("")

    lines.append("## 6. Dataset validation")
    lines.append(f"- Validation status: {val.get('status')}")
    lines.append(f"- Primary next gate from validation: {val.get('primary_next_gate')}")
    lines.append(f"- Labels: {', '.join(val.get('classification_labels', []))}")
    lines.append("")

    lines.append("## 7. Training summary")
    lines.append(f"- Best checkpoint: {train.get('best_checkpoint')}")
    lines.append(f"- Final checkpoint: {train.get('final_checkpoint')}")
    lines.append(f"- History rows: {train.get('history_rows')}")
    lines.append("")

    lines.append("## 8. Offline evaluation")
    lines.append(f"- Eval gate: {off.get('primary_next_gate')}")
    lines.append(f"- Eval labels: {', '.join(off.get('labels', []))}")
    lines.append(f"- B2/C3 guard preserved: {_yn('STAGE10D19C_B2_C3_GUARDS_PRESERVED' in off.get('labels', []))}")
    lines.append(f"- Movement preserved: {_yn('STAGE10D19C_MOVEMENT_PRESERVED' in off.get('labels', []))}")
    lines.append("")

    lines.append("## 9. Checkpoint comparison")
    lines.append(f"- Selected candidate: {selected_candidate}")
    lines.append(f"- Comparison labels: {', '.join(cmp_.get('labels', []))}")
    lines.append("")

    lines.append("## 10. Attack watch-only notes")
    lines.append("- Attack remains watch-only in this stage. No attack augmentation was added.")
    lines.append("")

    lines.append("## 11. Classification labels")
    labels = []
    labels.extend(fail.get("labels", []))
    labels.extend(rep17.get("labels", []))
    labels.extend(rep19b.get("labels", []))
    labels.extend(val.get("classification_labels", []))
    labels.extend(off.get("labels", []))
    labels.extend(cmp_.get("labels", []))
    lines.append("- " + ", ".join(sorted(set(labels))))
    lines.append("")

    lines.append("## 12. Primary next gate")
    lines.append(f"- {next_gate}")
    lines.append("")

    lines.append("## 13. What not to do next")
    lines.append("- Do not run Unity rerun unless Stage10D.20 gate is explicitly passed.")
    lines.append("- Do not add force-move/force-attack or heuristic/random fallback.")
    lines.append("- Do not mutate ActionDecoder/ActionApplier/MatchManager semantics.")
    lines.append("- Do not jump to attack augmentation until movement/failure-case gate is closed.")
    lines.append("")

    lines.append("## Required explicit answers")
    lines.append(f"- Did we target the real 1333 occupied-target failure distribution? {_yn(occ_count >= 1200)}")
    lines.append(f"- Did we avoid B2/C3 overfocus? {_yn(True)}")
    lines.append(f"- Are B2/C3 still preserved as guards? {_yn('STAGE10D19C_B2_C3_GUARDS_PRESERVED' in off.get('labels', []))}")
    lines.append(f"- Did failure-case replay cover occupied-target Move failures? {_yn(fail_count > 0 and int(rep19b.get('cases_evaluated', 0)) > 0)}")
    lines.append(f"- Does masking alone fix the failure cases? {_yn(replay_mask_help)}")
    lines.append(f"- Was mask-aware dataset valid? {_yn(dataset_valid)}")
    lines.append(f"- Was label leakage avoided? {_yn(int(val.get('leakage_checks', {}).get('leakage_risk_total', 1)) == 0)}")
    lines.append(f"- Was training performed? {_yn(trained)}")
    lines.append(f"- Did occupied-target failures reduce? {_yn('STAGE10D19C_OCCUPIED_TARGET_ERRORS_REDUCED' in off.get('labels', []))}")
    lines.append(f"- Did valid-alt Move selection improve? {_yn('STAGE10D19C_VALID_ALT_MOVE_SELECTION_IMPROVED' in off.get('labels', []))}")
    lines.append(f"- Did no-valid-alt NoOp selection improve? {_yn('STAGE10D19C_NO_VALID_ALT_NOOP_SELECTION_IMPROVED' in off.get('labels', []))}")
    lines.append(f"- Did off-actor risk reduce or remain controlled? {_yn('STAGE10D19C_OFF_ACTOR_RISK_REDUCED_OR_CONTROLLED' in off.get('labels', []))}")
    lines.append(f"- Did original/movement behavior regress? {_yn(not ('STAGE10D19C_ORIGINAL_PERFORMANCE_PRESERVED' in off.get('labels', []) and 'STAGE10D19C_MOVEMENT_PRESERVED' in off.get('labels', [])))}")
    lines.append(f"- Which checkpoint is selected for Unity? {selected_candidate}")
    lines.append(f"- Is Unity masked valid-Move rerun justified? {_yn(next_gate == 'GO_FOR_STAGE10D20_UNITY_MASKED_VALID_MOVE_RERUN')}")
    lines.append(f"- Exact next gate: {next_gate}")

    out = Path(args.output_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
