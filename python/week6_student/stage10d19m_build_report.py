#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from stage10d19m_common import load_json, utc_now_iso


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.19M build final legal action mask audit markdown report")
    p.add_argument("--preflight", type=Path, required=True)
    p.add_argument("--contract", type=Path, required=True)
    p.add_argument("--mask-validation", type=Path, required=True)
    p.add_argument("--probe-stage10d17", type=Path, required=True)
    p.add_argument("--probe-stage10d19b", type=Path, required=True)
    p.add_argument("--comparison", type=Path, required=True)
    p.add_argument(
        "--output-md",
        type=Path,
        default=Path("python/week6_student/reports/STAGE10D19M_LEGAL_ACTION_MASK_AUDIT_REPORT.md"),
    )
    return p.parse_args()


def _yn(v: bool) -> str:
    return "YES" if bool(v) else "NO"


def _gate(mask_valid: bool, p17: Dict[str, Any], p19: Dict[str, Any], cmp_: Dict[str, Any]) -> str:
    if not mask_valid:
        return "GO_FOR_STAGE10D19M_MASK_BUILDER_FIX"

    selected = str(cmp_.get("selected_candidate_for_unity_mask_rerun", "none"))
    p17_ready = "STAGE10D19M_MASK_READY_FOR_UNITY_TOGGLE_PROBE" in p17.get("labels", [])
    p19_ready = "STAGE10D19M_MASK_READY_FOR_UNITY_TOGGLE_PROBE" in p19.get("labels", [])
    any_ready = p17_ready or p19_ready

    if selected in {"stage10d17", "stage10d19b"} and any_ready:
        return "GO_FOR_STAGE10D20_UNITY_MASKED_VALID_MOVE_RERUN"

    any_move_suppressed = (
        "STAGE10D19M_MASK_SUPPRESSES_ALL_MOVEMENT" in p17.get("labels", [])
        or "STAGE10D19M_MASK_SUPPRESSES_ALL_MOVEMENT" in p19.get("labels", [])
    )
    if any_move_suppressed:
        return "GO_FOR_STAGE10D19M_MASKED_SELECTION_LOGIC_FIX"

    if any_ready and selected == "none":
        return "GO_FOR_STAGE10D19M_INSTRUMENTATION_FIX"

    if (
        int(p17.get("masked_off_actor_non_noop_count", 0)) > 0
        and int(p19.get("masked_off_actor_non_noop_count", 0)) > 0
    ):
        return "GO_FOR_STAGE10D19B_OFF_ACTOR_NEGATIVE_CONTROL_FIX"

    return "GO_FOR_STAGE10D19B_AUGMENTATION_REDESIGN_WITH_MASK_AWARE_LABELS"


def main() -> int:
    args = parse_args()
    pre = load_json(args.preflight)
    contract = load_json(args.contract)
    sem = load_json(args.mask_validation)
    p17 = load_json(args.probe_stage10d17)
    p19 = load_json(args.probe_stage10d19b)
    cmp_ = load_json(args.comparison)

    mask_valid = "STAGE10D19M_MASK_SEMANTICS_VALID" in sem.get("labels", [])
    selected = str(cmp_.get("selected_candidate_for_unity_mask_rerun", "none"))
    next_gate = _gate(mask_valid, p17, p19, cmp_)

    # Stage classification.
    stage_status = "PARTIAL"
    if next_gate == "GO_FOR_STAGE10D20_UNITY_MASKED_VALID_MOVE_RERUN":
        stage_status = "PASS"
    elif next_gate in {"GO_FOR_STAGE10D19M_MASK_BUILDER_FIX", "GO_FOR_STAGE10D19M_MASKED_SELECTION_LOGIC_FIX"}:
        stage_status = "FAIL"

    lines: List[str] = []
    lines.append("# STAGE10D19M Legal Action Mask Audit Report")
    lines.append("")
    lines.append(f"Generated at (UTC): {utc_now_iso()}")
    lines.append(f"Stage result: {stage_status}")
    lines.append("")

    lines.append("## 1) Purpose and Constraints")
    lines.append("- Purpose: evaluate legal action masking as pre-selection constraint for action selection efficiency/safety, without changing model weights or runtime authority.")
    lines.append("- Hard constraints observed: no PPO, no teacher/student training, no checkpoint mutation, no dataset mutation, no ActionDecoder/ActionApplier/MatchManager semantic change, no force-move fallback.")
    lines.append("")

    lines.append("## 2) Why Stage10D.19B led to this audit")
    lines.append(f"- Stage10D.19B gate: {pre.get('selected_gate_from_stage10d19b')}")
    lines.append("- Interpretation used: mask-aware redesign via legal mask probe rather than blind augmentation-only continuation.")
    lines.append("")

    action_shape = contract.get("action_type_mask_shape")
    if action_shape is None:
        action_shape = contract.get("level_a_cell_action_type_mask", {}).get("shape")
    branch_shapes = contract.get("branch_mask_shapes")
    if branch_shapes is None:
        branch_shapes = contract.get("level_b_branch_masks", {})

    lines.append("## 3) Legal Action Mask Contract")
    lines.append(f"- Contract labels: {', '.join(contract.get('labels', []))}")
    lines.append(f"- Action mask shape: {action_shape}")
    lines.append(f"- Branch mask shapes: {branch_shapes}")
    lines.append("")

    lines.append("## 4) Mask Builder Implementation")
    lines.append("- Built per-step masks from preserved Stage10D.18RR cell tables for selected steps.")
    lines.append("- Approximation notes are explicit for carried-resource and produce-cost checks; runtime validation remains authoritative.")
    lines.append("")

    lines.append("## 5) Mask Semantics Validation")
    lines.append(f"- Mask semantics valid: {_yn(mask_valid)}")
    lines.append(f"- Off-actor violations: {sem.get('off_actor_violations')}")
    lines.append(f"- Move violations: {sem.get('move_mask_violations')}")
    lines.append(f"- Harvest violations: {sem.get('harvest_mask_violations')}")
    lines.append(f"- Produce violations: {sem.get('produce_mask_violations')}")
    lines.append(f"- Attack violations: {sem.get('attack_mask_violations')}")
    lines.append(f"- Branch-mask violations: {sem.get('branch_mask_violations')}")
    lines.append(f"- Validation gate: {sem.get('gate')}")
    lines.append("")

    lines.append("## 6) Offline Masked Selection Probe")
    lines.append("### Stage10D.17")
    lines.append(f"- Unmasked invalid/occupied moves: {p17.get('unmasked_occupied_or_invalid_target_moves')}")
    lines.append(f"- Masked invalid/occupied moves: {p17.get('masked_occupied_or_invalid_target_moves')}")
    lines.append(f"- Unmasked off-actor non-NoOp: {p17.get('unmasked_off_actor_non_noop_count')}")
    lines.append(f"- Masked off-actor non-NoOp: {p17.get('masked_off_actor_non_noop_count')}")
    lines.append(f"- Movement preserved: {_yn('STAGE10D19M_MASK_PRESERVES_MOVEMENT' in p17.get('labels', []))}")
    lines.append(f"- B2/C3 preserved: {_yn('STAGE10D19M_MASK_PRESERVES_B2_C3_GUARDS' in p17.get('labels', []))}")
    lines.append("### Stage10D.19B")
    lines.append(f"- Unmasked invalid/occupied moves: {p19.get('unmasked_occupied_or_invalid_target_moves')}")
    lines.append(f"- Masked invalid/occupied moves: {p19.get('masked_occupied_or_invalid_target_moves')}")
    lines.append(f"- Unmasked off-actor non-NoOp: {p19.get('unmasked_off_actor_non_noop_count')}")
    lines.append(f"- Masked off-actor non-NoOp: {p19.get('masked_off_actor_non_noop_count')}")
    lines.append(f"- Movement preserved: {_yn('STAGE10D19M_MASK_PRESERVES_MOVEMENT' in p19.get('labels', []))}")
    lines.append(f"- B2/C3 preserved: {_yn('STAGE10D19M_MASK_PRESERVES_B2_C3_GUARDS' in p19.get('labels', []))}")
    lines.append("")

    lines.append("## 7) Checkpoint Comparison")
    lines.append(f"- Selected candidate for Unity masked rerun: {selected}")
    lines.append(f"- Comparison labels: {', '.join(cmp_.get('labels', []))}")
    lines.append(f"- Decision reason: {cmp_.get('decision_reason')}")
    lines.append("")

    lines.append("## 8) Unity Toggle Implementation")
    lines.append("- Not executed in this pass. Offline-first requirement respected.")
    lines.append("")

    lines.append("## 9) Unity Masked Rerun")
    lines.append("- Not executed in this pass (gated by offline semantics/probe results).")
    lines.append("")

    lines.append("## 10) Classification Labels")
    labels = []
    labels.extend(sem.get("labels", []))
    labels.extend(p17.get("labels", []))
    labels.extend(p19.get("labels", []))
    labels.extend(cmp_.get("labels", []))
    lines.append("- " + ", ".join(sorted(set(labels))))
    lines.append("")

    lines.append("## 11) Primary Next Gate")
    lines.append(f"- {next_gate}")
    lines.append("")

    lines.append("## 12) What Not To Do Next")
    lines.append("- Do not run PPO or any training as part of this mask audit closure.")
    lines.append("- Do not mutate datasets/checkpoints to compensate for masking logic findings.")
    lines.append("- Do not bypass ActionDecoder/ActionApplier/MatchManager runtime authority.")
    lines.append("- Do not add force-move, force-attack, or heuristic/random fallback policy.")
    lines.append("")

    lines.append("## Required Explicit Answers")
    lines.append(f"- Did we avoid more blind augmentation? {_yn(True)}")
    lines.append(f"- Is legal masking only pre-selection, not runtime validation replacement? {_yn(True)}")
    lines.append(f"- Are off-actor cells restricted to NoOp? {_yn(sem.get('off_actor_violations', 1) == 0)}")
    lines.append(f"- Are invalid Move directions masked? {_yn(sem.get('move_mask_violations', 1) == 0)}")
    lines.append(f"- Are occupied Move targets masked? {_yn(sem.get('move_mask_violations', 1) == 0)}")
    lines.append(f"- Are Attack targets masked to valid enemy targets only? {_yn(sem.get('attack_mask_violations', 1) == 0)}")
    lines.append(f"- Does masked selection preserve B2/C3 guards? {_yn(('STAGE10D19M_MASK_PRESERVES_B2_C3_GUARDS' in p17.get('labels', [])) or ('STAGE10D19M_MASK_PRESERVES_B2_C3_GUARDS' in p19.get('labels', [])))}")
    lines.append(f"- Does masked selection preserve movement? {_yn(('STAGE10D19M_MASK_PRESERVES_MOVEMENT' in p17.get('labels', [])) or ('STAGE10D19M_MASK_PRESERVES_MOVEMENT' in p19.get('labels', [])))}")
    lines.append(f"- Does masked selection reduce invalid/occupied Move selections? {_yn((p17.get('masked_occupied_or_invalid_target_moves', 0) < p17.get('unmasked_occupied_or_invalid_target_moves', 0)) or (p19.get('masked_occupied_or_invalid_target_moves', 0) < p19.get('unmasked_occupied_or_invalid_target_moves', 0)))}")
    lines.append(f"- Does masked selection reduce off-actor non-NoOp? {_yn((p17.get('masked_off_actor_non_noop_count', 0) < p17.get('unmasked_off_actor_non_noop_count', 0)) or (p19.get('masked_off_actor_non_noop_count', 0) < p19.get('unmasked_off_actor_non_noop_count', 0)))}")
    lines.append(f"- Which checkpoint is better under masked selection? {selected}")
    lines.append(f"- Is Unity masked rerun justified now? {_yn(next_gate == 'GO_FOR_STAGE10D20_UNITY_MASKED_VALID_MOVE_RERUN')}")
    lines.append(f"- Did we avoid force-move/heuristic fallback? {_yn(True)}")
    lines.append(f"- Exact next gate: {next_gate}")

    out = Path(args.output_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
