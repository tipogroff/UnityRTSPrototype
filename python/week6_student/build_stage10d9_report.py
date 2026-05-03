from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_CLASSIFICATIONS = {
    "CHECKPOINT_BINDING_VERIFIED",
    "CHECKPOINT_BINDING_FAILED",
    "UNITY_STAGE10R_RERUN_COMPLETED",
    "UNITY_STAGE10R_RERUN_INFRA_FAILURE",
    "UNITY_STAGE10R_RERUN_BEHAVIOR_IMPROVED",
    "UNITY_RUNTIME_NOOP_PERSISTS_WITH_SEMANTIC_CHECKPOINT",
    "DECODER_APPLIER_REACHED",
    "DECODER_APPLIER_NOT_REACHED",
    "READY_FOR_STAGE10V_VISUAL_CONFIRMATION",
    "READY_FOR_RUNTIME_NOOP_PERSISTENCE_DIAGNOSTIC",
    "NOT_READY_FOR_UNITY_ANALYSIS",
}

ALLOWED_GATES = {
    "GO_FOR_STAGE10V_VISUAL_CONFIRMATION",
    "GO_FOR_RUNTIME_NOOP_PERSISTENCE_DIAGNOSTIC",
    "GO_FOR_CHECKPOINT_BINDING_FIX",
    "GO_FOR_UNITY_RERUN_INFRA_FIX",
    "GO_FOR_NEXT_DIAGNOSTIC",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = None
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except Exception:
        try:
            text = path.read_text(encoding="utf-8-sig")
            data = json.loads(text)
        except Exception:
            return {}
    return data if isinstance(data, dict) else {}


def _to_rel(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _focus_cell(snapshot: dict[str, Any], label: str) -> dict[str, Any]:
    items = snapshot.get("focus_cell_diagnostics")
    if not isinstance(items, list):
        return {}
    for item in items:
        if isinstance(item, dict) and str(item.get("logical_label")) == label:
            return item
    return {}


def _format_top3(fc: dict[str, Any]) -> list[dict[str, Any]]:
    top3 = fc.get("action_type_top3")
    if isinstance(top3, list):
        out: list[dict[str, Any]] = []
        for row in top3:
            if isinstance(row, dict):
                out.append(
                    {
                        "class_id": row.get("class_id"),
                        "class_name": row.get("class_name"),
                        "probability": row.get("probability"),
                    }
                )
        return out
    return []


def _bool(v: Any) -> bool:
    return bool(v)


def _build_stage10d9_unity_rerun_report(
    repo_root: Path,
    binding_verification: dict[str, Any],
    snapshot: dict[str, Any],
    episode_diag: dict[str, Any],
    old_snapshot: dict[str, Any],
) -> dict[str, Any]:
    binding_ok = binding_verification.get("status") == "pass"

    b2 = _focus_cell(snapshot, "B2")
    c3 = _focus_cell(snapshot, "C3")

    logits_shapes_captured = _bool(snapshot.get("logits_shapes_captured"))
    observation_shape = snapshot.get("observation_shape")
    observation_shape_ok = observation_shape == [24, 24, 27]

    b2_top3 = _format_top3(b2)
    c3_top3 = _format_top3(c3)
    b2_pred = b2.get("predicted_action_type")
    c3_pred = c3.get("predicted_action_type")

    action_applier_reached = _bool(snapshot.get("action_applier_reached"))
    apply_command_reached = _bool(snapshot.get("apply_command_reached"))
    command_built_any = _bool(snapshot.get("commands_built", 0) > 0)

    student_side = episode_diag.get("student_side") if isinstance(episode_diag.get("student_side"), dict) else {}
    terminal_reason = episode_diag.get("terminal_reason")

    # Infrastructure readiness for runtime verdict.
    infra_fail = (
        (not binding_ok)
        or (not observation_shape_ok)
        or (not logits_shapes_captured)
        or (not b2_top3)
        or (not c3_top3)
    )

    behavior_improved = (
        (b2_pred is not None and str(b2_pred) != "NoOp")
        and (c3_pred is not None and str(c3_pred) != "NoOp")
        and command_built_any
        and action_applier_reached
    )

    noop_persists = (
        binding_ok
        and not infra_fail
        and str(b2_pred) == "NoOp"
        and str(c3_pred) == "NoOp"
        and not command_built_any
    )

    classifications: list[str] = []
    classifications.append("CHECKPOINT_BINDING_VERIFIED" if binding_ok else "CHECKPOINT_BINDING_FAILED")

    if infra_fail:
        classifications.append("UNITY_STAGE10R_RERUN_INFRA_FAILURE")
    else:
        classifications.append("UNITY_STAGE10R_RERUN_COMPLETED")
        if behavior_improved:
            classifications.append("UNITY_STAGE10R_RERUN_BEHAVIOR_IMPROVED")
            classifications.append("READY_FOR_STAGE10V_VISUAL_CONFIRMATION")
        elif noop_persists:
            classifications.append("UNITY_RUNTIME_NOOP_PERSISTS_WITH_SEMANTIC_CHECKPOINT")
            classifications.append("READY_FOR_RUNTIME_NOOP_PERSISTENCE_DIAGNOSTIC")

    classifications.append("DECODER_APPLIER_REACHED" if action_applier_reached else "DECODER_APPLIER_NOT_REACHED")

    if infra_fail:
        classifications.append("NOT_READY_FOR_UNITY_ANALYSIS")

    # Preserve order and deduplicate.
    dedup: list[str] = []
    for c in classifications:
        if c not in dedup:
            dedup.append(c)
    classifications = [c for c in dedup if c in ALLOWED_CLASSIFICATIONS]

    if not binding_ok:
        gate = "GO_FOR_CHECKPOINT_BINDING_FIX"
    elif infra_fail:
        gate = "GO_FOR_UNITY_RERUN_INFRA_FIX"
    elif behavior_improved:
        gate = "GO_FOR_STAGE10V_VISUAL_CONFIRMATION"
    else:
        gate = "GO_FOR_RUNTIME_NOOP_PERSISTENCE_DIAGNOSTIC"

    if gate not in ALLOWED_GATES:
        gate = "GO_FOR_NEXT_DIAGNOSTIC"

    old_b2 = _focus_cell(old_snapshot, "B2")
    old_c3 = _focus_cell(old_snapshot, "C3")

    return {
        "stage": "10D.9",
        "task": "unity_stage10r_rerun_with_semantic_checkpoint",
        "generated_at_utc": _utc_now(),
        "scene": "Assets/Scenes/Week6_StudentVisualInspection.unity",
        "checkpoint_binding": {
            "new_checkpoint": "python/week6_student/runs/legacy032_v2_semantic_bc_stage10d8_20260503T093718Z/student_bc_semantic_best.pt",
            "binding_verification_status": binding_verification.get("status", "missing"),
            "binding_verification_report": "python/week6_student/reports/stage10d9_checkpoint_binding_verification.json",
        },
        "runtime_observation": {
            "shape": observation_shape,
            "shape_ok": observation_shape_ok,
            "snapshot_generated_at_utc": snapshot.get("generated_at_utc"),
            "input_mode": "full_unity_runtime_observation",
        },
        "runtime_inference": {
            "inference_request_count": student_side.get("candidate_cells_total"),
            "python_bridge_checkpoint_path_used": snapshot.get("checkpoint"),
            "logits_shapes_captured": logits_shapes_captured,
            "logits_shape_lines": snapshot.get("logits_shape_lines", []),
            "expected_branch_sizes": [6, 4, 4, 4, 4, 7, 49],
            "expected_logits_shapes": {
                "action_type_logits": [1, 576, 6],
                "move_dir_logits": [1, 576, 4],
                "harvest_dir_logits": [1, 576, 4],
                "return_dir_logits": [1, 576, 4],
                "produce_dir_logits": [1, 576, 4],
                "produce_unit_type_logits": [1, 576, 7],
                "attack_target_local_logits": [1, 576, 49],
            },
        },
        "focus_cells": {
            "B2": {
                "flat_index": 25,
                "cell_observation_slice": b2.get("cell_observation_channels", []),
                "action_type_probabilities": b2.get("action_type_probabilities", []),
                "action_type_top3": b2_top3,
                "predicted_action_type": b2_pred,
                "command_built": b2.get("command_built"),
                "decoder_or_applier_reason": b2.get("command_not_built_reason"),
            },
            "C3": {
                "flat_index": 50,
                "cell_observation_slice": c3.get("cell_observation_channels", []),
                "action_type_probabilities": c3.get("action_type_probabilities", []),
                "action_type_top3": c3_top3,
                "predicted_action_type": c3_pred,
                "command_built": c3.get("command_built"),
                "decoder_or_applier_reason": c3.get("command_not_built_reason"),
            },
        },
        "decoder_applier": {
            "aggregate_student_action_type_distribution": student_side.get("raw_chosen_action_type_histogram", []),
            "commands_built": snapshot.get("commands_built"),
            "commands_submitted": snapshot.get("commands_submitted"),
            "accepted_meaningful_commands": student_side.get("accepted_total"),
            "rejected_commands": student_side.get("rejected_total"),
            "action_applier_reached": action_applier_reached,
            "apply_command_reached": apply_command_reached,
        },
        "terminal_outcome": {
            "steps_run": episode_diag.get("steps_run"),
            "terminal_reason": terminal_reason,
            "episode_generated_at_utc": episode_diag.get("generated_at_utc"),
        },
        "old_vs_new_stage10r": {
            "old": {
                "snapshot": "python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json",
                "B2_predicted_action_type": old_b2.get("predicted_action_type"),
                "C3_predicted_action_type": old_c3.get("predicted_action_type"),
                "B2_command_built": old_b2.get("command_built"),
                "C3_command_built": old_c3.get("command_built"),
            },
            "new": {
                "snapshot": "python/week6_student/reports/stage10d9_unity_stage10r_rerun_snapshot_step0001.json",
                "B2_predicted_action_type": b2_pred,
                "C3_predicted_action_type": c3_pred,
                "B2_command_built": b2.get("command_built"),
                "C3_command_built": c3.get("command_built"),
            },
            "note": "Old Stage10R remained NoOp-only. New rerun missing bridge logits payload at step0001, so policy-level comparison is infra-limited.",
        },
        "known_risks": [
            "Stage10D.8 offline sparse snapshot probe failed (B2/C3 near NoOp-only); carried forward as known risk.",
            "Stage10D.9 rerun step0001 has bridge payload missing, so B2/C3 top-3 probabilities are unavailable in this run.",
            "Do not claim policy-level success until Unity runtime rerun with full bridge logits capture passes.",
        ],
        "classifications": classifications,
        "gate_decision": gate,
        "explicit_non_claims": [
            "No retraining performed in Stage10D.9.",
            "No PPO or teacher training performed in Stage10D.9.",
            "No checkpoint mutation performed.",
            "No ActionApplier or MatchManager behavioral patch applied.",
            "No forced non-NoOp fallback added.",
            "No policy-level success claim is made in this stage.",
        ],
    }


def _render_stage10d9_md(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Stage10D.9 Unity Stage10R Rerun Report")
    lines.append("")
    lines.append(f"- generated_at_utc: {report.get('generated_at_utc')}")
    lines.append(f"- scene: {report.get('scene')}")
    cb = report.get("checkpoint_binding", {})
    lines.append(f"- checkpoint: {cb.get('new_checkpoint')}")
    lines.append(f"- binding_verification_status: {cb.get('binding_verification_status')}")
    lines.append("")
    lines.append("## Runtime Observation")
    ro = report.get("runtime_observation", {})
    lines.append(f"- shape: {ro.get('shape')}")
    lines.append(f"- shape_ok: {ro.get('shape_ok')}")
    lines.append("")
    lines.append("## Runtime Inference")
    ri = report.get("runtime_inference", {})
    lines.append(f"- inference_request_count: {ri.get('inference_request_count')}")
    lines.append(f"- checkpoint_path_used_by_bridge: {ri.get('python_bridge_checkpoint_path_used')}")
    lines.append(f"- logits_shapes_captured: {ri.get('logits_shapes_captured')}")
    lines.append("")
    lines.append("## Focus Cells")
    fc = report.get("focus_cells", {})
    for label in ("B2", "C3"):
        item = fc.get(label, {})
        lines.append(f"### {label}")
        lines.append(f"- predicted_action_type: {item.get('predicted_action_type')}")
        lines.append(f"- action_type_top3: {item.get('action_type_top3')}")
        lines.append(f"- command_built: {item.get('command_built')}")
        lines.append(f"- reason: {item.get('decoder_or_applier_reason')}")
    lines.append("")
    lines.append("## Decoder/Applier")
    da = report.get("decoder_applier", {})
    lines.append(f"- action_applier_reached: {da.get('action_applier_reached')}")
    lines.append(f"- apply_command_reached: {da.get('apply_command_reached')}")
    lines.append(f"- accepted_meaningful_commands: {da.get('accepted_meaningful_commands')}")
    lines.append(f"- rejected_commands: {da.get('rejected_commands')}")
    lines.append("")
    lines.append("## Terminal")
    te = report.get("terminal_outcome", {})
    lines.append(f"- steps_run: {te.get('steps_run')}")
    lines.append(f"- terminal_reason: {te.get('terminal_reason')}")
    lines.append("")
    lines.append("## Old vs New")
    ovn = report.get("old_vs_new_stage10r", {})
    lines.append(f"- old: {ovn.get('old')}")
    lines.append(f"- new: {ovn.get('new')}")
    lines.append(f"- note: {ovn.get('note')}")
    lines.append("")
    lines.append("## Classifications")
    for c in report.get("classifications", []):
        lines.append(f"- {c}")
    lines.append("")
    lines.append(f"## Gate\n- {report.get('gate_decision')}")
    lines.append("")
    lines.append("## Explicit Non-Claims")
    for n in report.get("explicit_non_claims", []):
        lines.append(f"- {n}")
    return "\n".join(lines) + "\n"


def _render_legacy_stage10d9_md(report: dict[str, Any], stage10d8_recap: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# LEGACY032 UNITY V2 STAGE10D9 UNITY STAGE10R RERUN REPORT")
    lines.append("")
    lines.append("## 1. Scope")
    lines.append("- Stage10D.9 rerun only; no retraining/PPO/teacher continuation.")
    lines.append("- No checkpoint mutation and no ActionApplier/MatchManager behavioral patch.")
    lines.append("")
    lines.append("## 2. Stage10D.8 Recap")
    lines.append(f"- stage10d8_gate: {stage10d8_recap.get('gate_decision')}")
    lines.append(f"- stage10d8_authorized_unity_rerun: {stage10d8_recap.get('unity_stage10r_rerun_authorized')}")
    lines.append("- known_risk_carried: Stage10D.8 sparse snapshot probe had B2/C3 near NoOp-only.")
    lines.append("")
    lines.append("## 3. Checkpoint Binding")
    cb = report.get("checkpoint_binding", {})
    lines.append(f"- new_checkpoint: {cb.get('new_checkpoint')}")
    lines.append(f"- verification_status: {cb.get('binding_verification_status')}")
    lines.append(f"- verification_report: {cb.get('binding_verification_report')}")
    lines.append("")
    lines.append("## 4. Unity Scene / Runner")
    lines.append(f"- scene: {report.get('scene')}")
    lines.append("- runner: RTS.ML.Week6VisualInspectionRunner")
    lines.append("- execution_mode: full Unity runtime observation (not sparse offline tensor)")
    lines.append("")
    lines.append("## 5. Runtime Observation Check")
    ro = report.get("runtime_observation", {})
    lines.append(f"- observation_shape: {ro.get('shape')}")
    lines.append(f"- shape_ok_[24,24,27]: {ro.get('shape_ok')}")
    lines.append("")
    lines.append("## 6. Runtime Inference Check")
    ri = report.get("runtime_inference", {})
    lines.append(f"- inference_request_count: {ri.get('inference_request_count')}")
    lines.append(f"- checkpoint_path_used_by_bridge: {ri.get('python_bridge_checkpoint_path_used')}")
    lines.append(f"- logits_shapes_captured: {ri.get('logits_shapes_captured')}")
    lines.append(f"- logits_shape_lines: {ri.get('logits_shape_lines')}")
    lines.append("")
    lines.append("## 7. B2/C3 Focus Cell Result")
    fc = report.get("focus_cells", {})
    for label in ("B2", "C3"):
        item = fc.get(label, {})
        lines.append(f"- {label}_predicted_action_type: {item.get('predicted_action_type')}")
        lines.append(f"- {label}_top3: {item.get('action_type_top3')}")
        lines.append(f"- {label}_command_built: {item.get('command_built')}")
        lines.append(f"- {label}_reason_if_no_command: {item.get('decoder_or_applier_reason')}")
    lines.append("")
    lines.append("## 8. Decoder/Applier Result")
    da = report.get("decoder_applier", {})
    lines.append(f"- commands_built: {da.get('commands_built')}")
    lines.append(f"- commands_submitted: {da.get('commands_submitted')}")
    lines.append(f"- action_applier_reached: {da.get('action_applier_reached')}")
    lines.append(f"- apply_command_reached: {da.get('apply_command_reached')}")
    lines.append("")
    lines.append("## 9. Old vs New Stage10R Comparison")
    ovn = report.get("old_vs_new_stage10r", {})
    lines.append(f"- old: {ovn.get('old')}")
    lines.append(f"- new: {ovn.get('new')}")
    lines.append(f"- comparison_note: {ovn.get('note')}")
    lines.append("")
    lines.append("## 10. Remaining Risks")
    for r in report.get("known_risks", []):
        lines.append(f"- {r}")
    lines.append("")
    lines.append("## 11. Gate Decision")
    lines.append(f"- gate_decision: {report.get('gate_decision')}")
    lines.append("")
    lines.append("## 12. Explicit Non-Claims")
    for n in report.get("explicit_non_claims", []):
        lines.append(f"- {n}")
    lines.append("")
    lines.append("## Classifications")
    for c in report.get("classifications", []):
        lines.append(f"- {c}")
    return "\n".join(lines) + "\n"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]

    binding_path = repo_root / "python/week6_student/reports/stage10d9_checkpoint_binding_verification.json"
    snapshot_path = repo_root / "python/week6_student/reports/stage10d9_unity_stage10r_rerun_snapshot_step0001.json"
    episode_path = repo_root / "python/week6_student/tmp/week6_visual/week6_visual_episode_diagnostics.json"
    old_snapshot_path = repo_root / "python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json"
    stage10d8_path = repo_root / "python/week6_student/reports/LEGACY032_UNITY_V2_STAGE10D8_SEMANTIC_BC_RETRAINING_REPORT.json"

    binding = _read_json(binding_path)
    snapshot = _read_json(snapshot_path)
    episode = _read_json(episode_path)
    old_snapshot = _read_json(old_snapshot_path)
    stage10d8 = _read_json(stage10d8_path)

    rerun_report = _build_stage10d9_unity_rerun_report(repo_root, binding, snapshot, episode, old_snapshot)

    out_rerun_json = repo_root / "python/week6_student/reports/stage10d9_unity_stage10r_rerun_report.json"
    out_rerun_md = repo_root / "python/week6_student/reports/stage10d9_unity_stage10r_rerun_report.md"

    out_legacy_json = repo_root / "python/week6_student/reports/LEGACY032_UNITY_V2_STAGE10D9_UNITY_STAGE10R_RERUN_REPORT.json"
    out_legacy_md = repo_root / "python/week6_student/reports/LEGACY032_UNITY_V2_STAGE10D9_UNITY_STAGE10R_RERUN_REPORT.md"

    out_rerun_json.parent.mkdir(parents=True, exist_ok=True)

    out_rerun_json.write_text(json.dumps(rerun_report, ensure_ascii=True, indent=2), encoding="utf-8")
    out_rerun_md.write_text(_render_stage10d9_md(rerun_report), encoding="utf-8")

    legacy_report = dict(rerun_report)
    legacy_report["report_name"] = "LEGACY032_UNITY_V2_STAGE10D9_UNITY_STAGE10R_RERUN_REPORT"
    out_legacy_json.write_text(json.dumps(legacy_report, ensure_ascii=True, indent=2), encoding="utf-8")
    out_legacy_md.write_text(_render_legacy_stage10d9_md(legacy_report, stage10d8), encoding="utf-8")

    print(_to_rel(repo_root, out_rerun_json))
    print(_to_rel(repo_root, out_rerun_md))
    print(_to_rel(repo_root, out_legacy_json))
    print(_to_rel(repo_root, out_legacy_md))
    print(f"gate={rerun_report.get('gate_decision')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
