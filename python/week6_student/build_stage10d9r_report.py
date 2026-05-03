from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_CLASSIFICATIONS = {
    "CHECKPOINT_BINDING_VERIFIED",
    "UNITY_RERUN_INFRA_FIX_APPLIED",
    "UNITY_RERUN_INFRA_STILL_BROKEN",
    "INFERENCE_ARTIFACT_CAPTURE_VERIFIED",
    "INFERENCE_ARTIFACT_CAPTURE_FAILED",
    "UNITY_STAGE10R_RERUN_COMPLETED",
    "UNITY_STAGE10R_RERUN_BEHAVIOR_IMPROVED",
    "UNITY_RUNTIME_NOOP_PERSISTS_WITH_SEMANTIC_CHECKPOINT",
    "MODEL_PREDICTS_NON_NOOP_DECODER_OR_RUNTIME_BLOCKED",
    "DECODER_APPLIER_REACHED",
    "DECODER_APPLIER_NOT_REACHED",
    "READY_FOR_STAGE10V_VISUAL_CONFIRMATION",
    "READY_FOR_RUNTIME_NOOP_PERSISTENCE_DIAGNOSTIC",
    "READY_FOR_DECODER_APPLIER_DIAGNOSTIC",
    "NOT_READY_FOR_UNITY_ANALYSIS",
}

ALLOWED_GATES = {
    "GO_FOR_STAGE10V_VISUAL_CONFIRMATION",
    "GO_FOR_RUNTIME_NOOP_PERSISTENCE_DIAGNOSTIC",
    "GO_FOR_DECODER_APPLIER_DIAGNOSTIC",
    "GO_FOR_UNITY_RERUN_INFRA_FIX_CONTINUED",
    "GO_FOR_NEXT_DIAGNOSTIC",
}

TARGET_CHECKPOINT = "python/week6_student/runs/legacy032_v2_semantic_bc_stage10d8_20260503T093718Z/student_bc_semantic_best.pt"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return {}


def _focus(snapshot: dict[str, Any], label: str) -> dict[str, Any]:
    rows = snapshot.get("focus_cell_diagnostics")
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if isinstance(row, dict) and str(row.get("logical_label")) == label:
            return row
    return {}


def _is_non_noop(value: Any) -> bool:
    return str(value or "") not in {"", "NoOp"}


def _source_is_model_logits(value: Any) -> bool:
    return str(value or "") == "model_logits"


def _build_rerun_report(
    snapshot: dict[str, Any],
    episode: dict[str, Any],
    binding: dict[str, Any],
    verification: dict[str, Any],
) -> dict[str, Any]:
    b2 = _focus(snapshot, "B2")
    c3 = _focus(snapshot, "C3")

    binding_ok = str(binding.get("status")) == "pass"
    verification_ok = str(verification.get("status")) == "pass"

    b2_pred = b2.get("predicted_action_type")
    c3_pred = c3.get("predicted_action_type")
    b2_source = b2.get("predicted_action_type_source")
    c3_source = c3.get("predicted_action_type_source")

    b2_non_noop = _is_non_noop(b2_pred)
    c3_non_noop = _is_non_noop(c3_pred)
    b2_from_logits = _source_is_model_logits(b2_source)
    c3_from_logits = _source_is_model_logits(c3_source)

    commands_built = int(snapshot.get("commands_built") or 0)
    commands_submitted = int(snapshot.get("commands_submitted") or 0)
    action_applier_reached = bool(snapshot.get("action_applier_reached"))
    apply_command_reached = bool(snapshot.get("apply_command_reached"))

    classifications: list[str] = []
    classifications.append("CHECKPOINT_BINDING_VERIFIED" if binding_ok else "NOT_READY_FOR_UNITY_ANALYSIS")
    classifications.append("UNITY_RERUN_INFRA_FIX_APPLIED")

    if not verification_ok:
        classifications.extend(
            [
                "UNITY_RERUN_INFRA_STILL_BROKEN",
                "INFERENCE_ARTIFACT_CAPTURE_FAILED",
                "NOT_READY_FOR_UNITY_ANALYSIS",
            ]
        )
        gate = "GO_FOR_UNITY_RERUN_INFRA_FIX_CONTINUED"
    else:
        classifications.extend(["INFERENCE_ARTIFACT_CAPTURE_VERIFIED", "UNITY_STAGE10R_RERUN_COMPLETED"])

        if b2_non_noop and c3_non_noop and (commands_built > 0 or commands_submitted > 0):
            classifications.extend(["UNITY_STAGE10R_RERUN_BEHAVIOR_IMPROVED", "READY_FOR_STAGE10V_VISUAL_CONFIRMATION"])
            gate = "GO_FOR_STAGE10V_VISUAL_CONFIRMATION"
        elif (not b2_non_noop) and (not c3_non_noop) and b2_from_logits and c3_from_logits:
            classifications.extend(
                [
                    "UNITY_RUNTIME_NOOP_PERSISTS_WITH_SEMANTIC_CHECKPOINT",
                    "READY_FOR_RUNTIME_NOOP_PERSISTENCE_DIAGNOSTIC",
                ]
            )
            gate = "GO_FOR_RUNTIME_NOOP_PERSISTENCE_DIAGNOSTIC"
        elif (b2_non_noop or c3_non_noop) and b2_from_logits and c3_from_logits and commands_built <= 0:
            classifications.extend(
                [
                    "MODEL_PREDICTS_NON_NOOP_DECODER_OR_RUNTIME_BLOCKED",
                    "READY_FOR_DECODER_APPLIER_DIAGNOSTIC",
                ]
            )
            gate = "GO_FOR_DECODER_APPLIER_DIAGNOSTIC"
        else:
            classifications.append("NOT_READY_FOR_UNITY_ANALYSIS")
            gate = "GO_FOR_NEXT_DIAGNOSTIC"

    classifications.append("DECODER_APPLIER_REACHED" if action_applier_reached or apply_command_reached else "DECODER_APPLIER_NOT_REACHED")

    seen: set[str] = set()
    normalized: list[str] = []
    for item in classifications:
        if item in ALLOWED_CLASSIFICATIONS and item not in seen:
            seen.add(item)
            normalized.append(item)

    if gate not in ALLOWED_GATES:
        gate = "GO_FOR_NEXT_DIAGNOSTIC"

    return {
        "stage": "10D.9R",
        "task": "unity_rerun_infra_fix_and_verified_inference_capture",
        "generated_at_utc": _utc_now(),
        "scene": "Assets/Scenes/Week6_StudentVisualInspection.unity",
        "checkpoint": TARGET_CHECKPOINT,
        "checkpoint_binding": {
            "status": binding.get("status", "missing"),
            "report": "python/week6_student/reports/stage10d9_checkpoint_binding_verification.json",
        },
        "inference_artifact_verification": {
            "status": verification.get("status", "missing"),
            "report": "python/week6_student/reports/stage10d9r_inference_artifact_verification.json",
        },
        "runtime_snapshot": snapshot,
        "episode_diagnostics": {
            "generated_at_utc": episode.get("generated_at_utc"),
            "steps_run": episode.get("steps_run"),
            "terminal_reason": episode.get("terminal_reason"),
        },
        "focus_cells": {
            "B2": b2,
            "C3": c3,
        },
        "classifications": normalized,
        "gate_decision": gate,
    }


def _render_rerun_md(report: dict[str, Any]) -> str:
    b2 = report.get("focus_cells", {}).get("B2", {})
    c3 = report.get("focus_cells", {}).get("C3", {})
    snap = report.get("runtime_snapshot", {})
    lines: list[str] = []
    lines.append("# Stage10D.9R Unity Stage10R Rerun Report")
    lines.append("")
    lines.append(f"- generated_at_utc: {report.get('generated_at_utc')}")
    lines.append(f"- scene: {report.get('scene')}")
    lines.append(f"- checkpoint: {report.get('checkpoint')}")
    lines.append(f"- binding_status: {report.get('checkpoint_binding', {}).get('status')}")
    lines.append(f"- inference_artifact_verification: {report.get('inference_artifact_verification', {}).get('status')}")
    lines.append("")
    lines.append("## Runtime Inference")
    lines.append(f"- inference_request_count: {snap.get('inference_request_count')}")
    lines.append(f"- adapter_invoked: {snap.get('adapter_invoked')}")
    lines.append(f"- logits_shapes_captured: {snap.get('logits_shapes_captured')}")
    lines.append(f"- checkpoint_path_used_at_inference: {snap.get('checkpoint_path_used_at_inference')}")
    lines.append("")
    lines.append("## Focus Cells")
    lines.append("### B2")
    lines.append(f"- predicted_action_type: {b2.get('predicted_action_type')}")
    lines.append(f"- predicted_action_type_source: {b2.get('predicted_action_type_source')}")
    lines.append(f"- action_type_top3: {b2.get('action_type_top3')}")
    lines.append(f"- command_built: {b2.get('command_built')}")
    lines.append(f"- command_not_built_reason: {b2.get('command_not_built_reason')}")
    lines.append("### C3")
    lines.append(f"- predicted_action_type: {c3.get('predicted_action_type')}")
    lines.append(f"- predicted_action_type_source: {c3.get('predicted_action_type_source')}")
    lines.append(f"- action_type_top3: {c3.get('action_type_top3')}")
    lines.append(f"- command_built: {c3.get('command_built')}")
    lines.append(f"- command_not_built_reason: {c3.get('command_not_built_reason')}")
    lines.append("")
    lines.append("## Decoder/Applier")
    lines.append(f"- commands_built: {snap.get('commands_built')}")
    lines.append(f"- commands_submitted: {snap.get('commands_submitted')}")
    lines.append(f"- action_applier_reached: {snap.get('action_applier_reached')}")
    lines.append(f"- apply_command_reached: {snap.get('apply_command_reached')}")
    lines.append("")
    lines.append("## Decision")
    for c in report.get("classifications", []):
        lines.append(f"- {c}")
    lines.append(f"- gate: {report.get('gate_decision')}")
    lines.append("")
    return "\n".join(lines)


def _render_final_md(final_report: dict[str, Any]) -> str:
    sections = final_report.get("sections", {})
    lines: list[str] = []
    lines.append("# LEGACY032 UNITY V2 STAGE10D9R UNITY RERUN INFRA FIX REPORT")
    lines.append("")
    for key in [
        "1_scope",
        "2_stage10d9_failure_recap",
        "3_root_cause_no_adapter_artifact",
        "4_infra_fix_applied",
        "5_checkpoint_binding_recheck",
        "6_runtime_observation",
        "7_runtime_inference_artifact_verification",
        "8_b2_c3_focus_cell_results",
        "9_decoder_applier_result",
        "10_old_vs_d9_vs_d9r",
        "11_remaining_risks",
        "12_gate_decision",
        "13_explicit_non_claims",
    ]:
        section = sections.get(key)
        if isinstance(section, list):
            title = key.split("_", 1)[1].replace("_", " ").title()
            lines.append(f"## {title}")
            for item in section:
                lines.append(f"- {item}")
            lines.append("")
    lines.append("## Classifications")
    for c in final_report.get("classifications", []):
        lines.append(f"- {c}")
    lines.append("")
    lines.append("## Gate")
    lines.append(f"- {final_report.get('gate_decision')}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    root = Path(__file__).resolve().parents[2]

    snapshot_path = root / "python/week6_student/reports/stage10d9r_unity_stage10r_rerun_snapshot_step0001.json"
    rerun_json_path = root / "python/week6_student/reports/stage10d9r_unity_stage10r_rerun_report.json"
    rerun_md_path = root / "python/week6_student/reports/stage10d9r_unity_stage10r_rerun_report.md"

    binding_path = root / "python/week6_student/reports/stage10d9_checkpoint_binding_verification.json"
    verification_path = root / "python/week6_student/reports/stage10d9r_inference_artifact_verification.json"
    episode_path = root / "python/week6_student/tmp/week6_visual/week6_visual_episode_diagnostics.json"

    old_stage10r_path = root / "python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json"
    d9_path = root / "python/week6_student/reports/stage10d9_unity_stage10r_rerun_snapshot_step0001.json"

    snapshot = _read_json(snapshot_path)
    episode = _read_json(episode_path)
    binding = _read_json(binding_path)
    verification = _read_json(verification_path)
    old_stage10r = _read_json(old_stage10r_path)
    stage10d9 = _read_json(d9_path)

    rerun_report = _build_rerun_report(snapshot, episode, binding, verification)
    rerun_json_path.write_text(json.dumps(rerun_report, ensure_ascii=True, indent=2), encoding="utf-8")
    rerun_md_path.write_text(_render_rerun_md(rerun_report), encoding="utf-8")

    b2 = rerun_report.get("focus_cells", {}).get("B2", {})
    c3 = rerun_report.get("focus_cells", {}).get("C3", {})
    snap = rerun_report.get("runtime_snapshot", {})

    final_report = {
        "stage": "10D.9R",
        "generated_at_utc": _utc_now(),
        "classifications": rerun_report.get("classifications", []),
        "gate_decision": rerun_report.get("gate_decision", "GO_FOR_NEXT_DIAGNOSTIC"),
        "sections": {
            "1_scope": [
                "Stage10D.9R focused on Unity rerun infrastructure fix and verified inference artifact capture.",
                "No retraining, PPO, teacher training, checkpoint mutation, ActionApplier patch, or MatchManager patch.",
            ],
            "2_stage10d9_failure_recap": [
                "Stage10D.9 had checkpoint binding pass but no validated policy verdict due to missing adapter artifact.",
                "Fallback NoOp in B2/C3 was infra-limited and not treated as model-level evidence.",
            ],
            "3_root_cause_no_adapter_artifact": [
                "Snapshot was captured with zero inference requests, so no adapter artifact was present at capture time.",
                "Focus-cell diagnostics fell back to no-adapter-artifact path and empty logits/top3 payload.",
            ],
            "4_infra_fix_applied": [
                "Added read-only adapter diagnostics capture in Week6StudentPolicyAdapter.",
                "Added runner snapshot fields for adapter invocation, inference count, bridge status, raw keys, and artifact-missing reason.",
                "Added fallback artifact read via last_output_json_path without changing action semantics.",
            ],
            "5_checkpoint_binding_recheck": [
                f"binding_status={binding.get('status', 'missing')}",
                f"expected_checkpoint={TARGET_CHECKPOINT}",
            ],
            "6_runtime_observation": [
                f"observation_shape={snap.get('observation_shape')}",
                f"observation_has_nan={snap.get('observation_has_nan')}",
                f"observation_has_inf={snap.get('observation_has_inf')}",
            ],
            "7_runtime_inference_artifact_verification": [
                f"verification_status={verification.get('status', 'missing')}",
                f"inference_request_count={snap.get('inference_request_count')}",
                f"adapter_invoked={snap.get('adapter_invoked')}",
                f"logits_shapes_captured={snap.get('logits_shapes_captured')}",
            ],
            "8_b2_c3_focus_cell_results": [
                f"B2_predicted_action_type={b2.get('predicted_action_type')}",
                f"B2_predicted_action_type_source={b2.get('predicted_action_type_source')}",
                f"B2_action_type_top3={b2.get('action_type_top3')}",
                f"B2_command_built={b2.get('command_built')}",
                f"C3_predicted_action_type={c3.get('predicted_action_type')}",
                f"C3_predicted_action_type_source={c3.get('predicted_action_type_source')}",
                f"C3_action_type_top3={c3.get('action_type_top3')}",
                f"C3_command_built={c3.get('command_built')}",
            ],
            "9_decoder_applier_result": [
                f"commands_built={snap.get('commands_built')}",
                f"commands_submitted={snap.get('commands_submitted')}",
                f"action_applier_reached={snap.get('action_applier_reached')}",
                f"apply_command_reached={snap.get('apply_command_reached')}",
            ],
            "10_old_vs_d9_vs_d9r": [
                f"stage10r_snapshot={old_stage10r_path.as_posix()}",
                f"stage10d9_snapshot={d9_path.as_posix()}",
                f"stage10d9r_snapshot={snapshot_path.as_posix()}",
                f"stage10r_B2_pred={_focus(old_stage10r, 'B2').get('predicted_action_type')}",
                f"stage10d9_B2_pred={_focus(stage10d9, 'B2').get('predicted_action_type')}",
                f"stage10d9r_B2_pred={b2.get('predicted_action_type')}",
            ],
            "11_remaining_risks": [
                "Do not classify policy-level NoOp persistence unless verification status is pass and sources are model_logits.",
                "If verification fails, continue infrastructure fixes before behavior conclusions.",
            ],
            "12_gate_decision": [
                f"gate_decision={rerun_report.get('gate_decision')}",
            ],
            "13_explicit_non_claims": [
                "No fallback NoOp is treated as model NoOp evidence.",
                "No policy-level success claim is made when inference artifact verification fails.",
            ],
        },
    }

    final_json_path = root / "python/week6_student/reports/LEGACY032_UNITY_V2_STAGE10D9R_UNITY_RERUN_INFRA_FIX_REPORT.json"
    final_md_path = root / "python/week6_student/reports/LEGACY032_UNITY_V2_STAGE10D9R_UNITY_RERUN_INFRA_FIX_REPORT.md"
    final_json_path.write_text(json.dumps(final_report, ensure_ascii=True, indent=2), encoding="utf-8")
    final_md_path.write_text(_render_final_md(final_report), encoding="utf-8")

    print(rerun_json_path.as_posix())
    print(rerun_md_path.as_posix())
    print(final_json_path.as_posix())
    print(final_md_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
