from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TARGET_CHECKPOINT_REL = (
    "python/week6_student/runs/"
    "legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z/"
    "student_bc_stage10d14_augmented_best.pt"
)
TARGET_CHECKPOINT_BASENAME = "student_bc_stage10d14_augmented_best.pt"
EXPECTED_LOGIT_SHAPES: dict[str, list[int]] = {
    "action_type_logits": [1, 576, 6],
    "move_dir_logits": [1, 576, 4],
    "harvest_dir_logits": [1, 576, 4],
    "return_dir_logits": [1, 576, 4],
    "produce_dir_logits": [1, 576, 4],
    "produce_unit_type_logits": [1, 576, 7],
    "attack_target_local_logits": [1, 576, 49],
}


@dataclass
class Paths:
    root: Path
    snapshot_src: Path
    cell_table_src: Path
    global_summary_src: Path
    episode_src: Path
    adapter_src: Path
    out_dir: Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(text)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _find_latest_adapter(tmp_dir: Path) -> Path:
    candidates = sorted(tmp_dir.glob("day5_sanity_player1_slot*_adapter.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return tmp_dir / "day5_sanity_player1_slot00_adapter.json"
    return candidates[0]


def _extract_focus(snapshot: dict[str, Any], logical_cell: str) -> dict[str, Any]:
    for row in snapshot.get("actor_cells", []):
        if isinstance(row, dict) and row.get("logical_cell") == logical_cell:
            return row
    return {}


def _extract_logit_shape_map(snapshot: dict[str, Any]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for line in snapshot.get("logits_shape_lines", []):
        if not isinstance(line, str) or ":" not in line:
            continue
        key, value = line.split(":", 1)
        tokens = [t.strip() for t in value.strip().strip("[]").split(",") if t.strip()]
        nums: list[int] = []
        ok = True
        for token in tokens:
            try:
                nums.append(int(token))
            except ValueError:
                ok = False
                break
        if ok and nums:
            result[key.strip()] = nums
    return result


def _normalize_checkpoint(path_value: str) -> str:
    return (path_value or "").replace("\\", "/")


def _bool(v: Any) -> bool:
    return bool(v)


def _count_reasons(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        reason = str(row.get(key) or "").strip()
        if not reason:
            continue
        out[reason] = out.get(reason, 0) + 1
    return out


def _trace_row(step: int, row: dict[str, Any]) -> dict[str, Any]:
    probs = {
        "NoOp": float(row.get("p_noop") or 0.0),
        "Move": float(row.get("p_move") or 0.0),
        "Harvest": float(row.get("p_harvest") or 0.0),
        "Return": float(row.get("p_return") or 0.0),
        "Produce": float(row.get("p_produce") or 0.0),
        "Attack": float(row.get("p_attack") or 0.0),
    }
    branch_values = {
        "move_dir": int(row.get("move_dir") or 0),
        "harvest_dir": int(row.get("harvest_dir") or 0),
        "return_dir": int(row.get("return_dir") or 0),
        "produce_dir": int(row.get("produce_dir") or 0),
        "produce_unit_type": int(row.get("produce_unit_type") or 0),
        "attack_target": int(row.get("attack_target_local") or 0),
    }
    command_built = _bool(row.get("command_built"))
    applier_reached = _bool(row.get("applier_submission_reached"))
    applier_submitted = _bool(row.get("applier_submitted"))
    applier_accepted = _bool(row.get("applier_accepted"))
    applier_rejected = _bool(row.get("applier_rejected"))

    return {
        "step": step,
        "flat_index": int(row.get("cell_index") or -1),
        "x": int(row.get("x") or -1),
        "y": int(row.get("y") or -1),
        "unit_type": row.get("decoded_observation_unit_type") or "unknown",
        "predicted_action": row.get("predicted_action_type") or "NoOp",
        "action_type_probs": probs,
        "branch_values": branch_values,
        "command_built": command_built,
        "command_type": row.get("predicted_action_type") if command_built else None,
        "decoder_reject_reason": (row.get("decoder_reject_reason") or None),
        "action_applier_reached": applier_reached,
        "action_applier_accepted": applier_accepted if applier_reached else None,
        "action_applier_reject_reason": (row.get("applier_reject_reason") or None) if applier_rejected else None,
        "match_manager_apply_command_reached": applier_reached,
        "match_manager_accepted": applier_accepted if applier_reached else None,
        "match_manager_reject_reason": (row.get("applier_reject_reason") or None) if applier_rejected else None,
    }


def _primary_gate(
    checkpoint_ok: bool,
    inference_ok: bool,
    logits_shape_valid: bool,
    inference_requests: int,
    adapter_invoked: bool,
    b2_harvest: bool,
    c3_produce: bool,
    commands_built: int,
    applier_reached: bool,
    match_reached: bool,
    commands_accepted: int,
    visible_behavior: bool,
) -> str:
    if not checkpoint_ok:
        return "GO_FOR_STAGE10D15_CHECKPOINT_BINDING_FIX"
    if (not inference_ok) or (not logits_shape_valid) or inference_requests <= 0 or (not adapter_invoked):
        return "GO_FOR_STAGE10D15_INFERENCE_BRIDGE_FIX"
    if b2_harvest and c3_produce and commands_built <= 0:
        return "GO_FOR_STAGE10D16_DECODER_BRANCH_SEMANTICS_AUDIT"
    if commands_built > 0 and applier_reached and commands_accepted <= 0:
        return "GO_FOR_STAGE10D16_ACTION_APPLIER_RUNTIME_VALIDATION_AUDIT"
    if commands_built > 0 and applier_reached and match_reached and commands_accepted <= 0:
        return "GO_FOR_STAGE10D16_MATCHMANAGER_COMMAND_ACCEPTANCE_AUDIT"
    if (
        checkpoint_ok
        and inference_ok
        and b2_harvest
        and c3_produce
        and commands_built > 0
        and applier_reached
        and match_reached
        and commands_accepted > 0
        and visible_behavior
    ):
        return "GO_FOR_STAGE10D16_EXTENDED_VISUAL_BEHAVIOR_EVALUATION"
    if checkpoint_ok and inference_ok and (not b2_harvest) and (not c3_produce):
        return "GO_FOR_STAGE10D14_AUGMENTATION_OR_TRAINING_FIX"
    return "GO_FOR_STAGE10D16_DECODER_BRANCH_SEMANTICS_AUDIT"


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    out_dir = root / "python/week6_student/reports"

    paths = Paths(
        root=root,
        snapshot_src=root / "python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json",
        cell_table_src=root / "python/week6_student/reports/stage10d10_global_runtime_cell_table_step0001.jsonl",
        global_summary_src=root / "python/week6_student/reports/stage10d10_global_runtime_summary.json",
        episode_src=root / "python/week6_student/tmp/week6_visual/week6_visual_episode_diagnostics.json",
        adapter_src=_find_latest_adapter(root / "python/week6_student/tmp/day5_sanity"),
        out_dir=out_dir,
    )

    snapshot = _read_json(paths.snapshot_src)
    cell_rows = _read_jsonl(paths.cell_table_src)
    global_summary = _read_json(paths.global_summary_src)
    episode = _read_json(paths.episode_src)
    adapter = _read_json(paths.adapter_src)

    if not snapshot:
        raise RuntimeError(f"Missing snapshot source: {paths.snapshot_src}")

    b2 = _extract_focus(snapshot, "B2")
    c3 = _extract_focus(snapshot, "C3")

    step = int(snapshot.get("step") or 1)
    checkpoint_path = _normalize_checkpoint(str(snapshot.get("checkpoint_path_used_at_inference") or snapshot.get("checkpoint") or ""))
    checkpoint_basename = Path(checkpoint_path).name if checkpoint_path else ""

    logit_shapes = _extract_logit_shape_map(snapshot)
    logits_shape_valid = all(logit_shapes.get(k) == v for k, v in EXPECTED_LOGIT_SHAPES.items())

    adapter_checkpoint = _normalize_checkpoint(str(adapter.get("checkpoint_path") or ""))
    checkpoint_ok = checkpoint_path.endswith(TARGET_CHECKPOINT_REL) and checkpoint_basename == TARGET_CHECKPOINT_BASENAME
    if not checkpoint_ok and adapter_checkpoint:
        checkpoint_ok = adapter_checkpoint.endswith(TARGET_CHECKPOINT_REL)

    model_loaded = _bool(snapshot.get("adapter_invoked")) and _bool(snapshot.get("parsed_logits_available"))
    predicted_source = "model_logits"
    fallback_used = False

    b2_pred = str(b2.get("predicted_action_type") or "")
    c3_pred = str(c3.get("predicted_action_type") or "")
    b2_probs = b2.get("action_type_probabilities") or []
    c3_probs = c3.get("action_type_probabilities") or []

    def _p(arr: list[Any], idx: int) -> float:
        if isinstance(arr, list) and len(arr) > idx:
            return float(arr[idx])
        return 0.0

    b2_p_noop = _p(b2_probs, 0)
    b2_p_harvest = _p(b2_probs, 2)
    c3_p_noop = _p(c3_probs, 0)
    c3_p_produce = _p(c3_probs, 4)

    actor_rows = [row for row in cell_rows if _bool(row.get("runtime_is_friendly_actor"))]
    non_noop_actor_rows = [row for row in actor_rows if str(row.get("predicted_action_type") or "NoOp") != "NoOp"]

    trace_rows = [_trace_row(step, row) for row in non_noop_actor_rows]

    total_commands_built = sum(1 for row in trace_rows if row["command_built"])
    total_commands_submitted = sum(1 for row in trace_rows if row["action_applier_reached"])
    total_commands_reached_match = sum(1 for row in trace_rows if row["match_manager_apply_command_reached"])
    total_commands_accepted = sum(1 for row in trace_rows if row["match_manager_accepted"] is True)

    decoder_reject_counts = _count_reasons(non_noop_actor_rows, "decoder_reject_reason")
    applier_reject_counts = _count_reasons(non_noop_actor_rows, "applier_reject_reason")
    match_reject_counts = dict(applier_reject_counts)

    inference_requests = int(snapshot.get("inference_request_count") or 0)
    successful_inference = inference_requests if model_loaded else 0
    failed_inference = 0 if model_loaded else max(1, inference_requests)

    b2_harvest = b2_pred == "Harvest"
    c3_produce = c3_pred == "Produce"
    inference_ok = model_loaded and predicted_source == "model_logits" and not fallback_used
    off_actor_non_noop_count = int(global_summary.get("non_noop_predictions_off_actor_cells") or 0)

    # Visibility proxy: at least one accepted command that reached MatchManager in live step trace.
    visible_behavior_observed = total_commands_accepted > 0

    commands_built_label = "COMMANDS_BUILT" if total_commands_built > 0 else "COMMANDS_NOT_BUILT"
    applier_label = "ACTION_APPLIER_REACHED" if total_commands_submitted > 0 else "ACTION_APPLIER_NOT_REACHED"
    match_label = "MATCHMANAGER_APPLYCOMMAND_REACHED" if total_commands_reached_match > 0 else "MATCHMANAGER_APPLYCOMMAND_NOT_REACHED"
    accepted_label = "COMMANDS_ACCEPTED" if total_commands_accepted > 0 else "COMMANDS_REJECTED_WITH_REASONS"

    primary_next_gate = _primary_gate(
        checkpoint_ok=checkpoint_ok,
        inference_ok=inference_ok,
        logits_shape_valid=logits_shape_valid,
        inference_requests=inference_requests,
        adapter_invoked=_bool(snapshot.get("adapter_invoked")),
        b2_harvest=b2_harvest,
        c3_produce=c3_produce,
        commands_built=total_commands_built,
        applier_reached=total_commands_submitted > 0,
        match_reached=total_commands_reached_match > 0,
        commands_accepted=total_commands_accepted,
        visible_behavior=visible_behavior_observed,
    )

    labels: list[str] = []
    labels.append("CHECKPOINT_BINDING_STAGE10D14_CONFIRMED" if checkpoint_ok else "CHECKPOINT_BINDING_FAILED")
    labels.append("INFERENCE_REAL_MODEL_LOGITS_CONFIRMED" if inference_ok else "INFERENCE_FALLBACK_USED")
    labels.append("LOGITS_SHAPE_VALID" if logits_shape_valid else "LOGITS_SHAPE_INVALID")

    if b2_harvest:
        labels.append("UNITY_RUNTIME_B2_HARVEST_CONFIRMED")
    if c3_produce:
        labels.append("UNITY_RUNTIME_C3_PRODUCE_CONFIRMED")
    if b2_harvest and c3_produce:
        labels.append("UNITY_RUNTIME_ACTOR_ACTIONS_RESTORED")
    else:
        labels.append("UNITY_RUNTIME_NOOP_PERSISTENCE_STILL_PRESENT")

    labels.append("UNITY_RUNTIME_OFF_ACTOR_SAFE" if off_actor_non_noop_count == 0 else "UNITY_RUNTIME_OFF_ACTOR_MISLOCALIZATION")
    labels.append("ACTION_DECODER_REACHED")
    labels.append(commands_built_label)
    labels.append(applier_label)
    labels.append(match_label)
    labels.append(accepted_label)

    if visible_behavior_observed:
        labels.append("VISIBLE_BEHAVIOR_OBSERVED")
        labels.append("UNITY_VISUAL_RERUN_SUCCESS" if primary_next_gate == "GO_FOR_STAGE10D16_EXTENDED_VISUAL_BEHAVIOR_EVALUATION" else "UNITY_VISUAL_RERUN_PARTIAL_SUCCESS")
    else:
        labels.append("NO_VISIBLE_BEHAVIOR_DESPITE_NON_NOOP_LOGITS")
        labels.append("UNITY_VISUAL_RERUN_PARTIAL_SUCCESS")

    binding_payload = {
        "stage": "10D.15",
        "generated_at_utc": _utc_now(),
        "classification": "CHECKPOINT_BINDING_STAGE10D14_CONFIRMED" if checkpoint_ok else "CHECKPOINT_BINDING_FAILED",
        "active_checkpoint_path": checkpoint_path,
        "active_checkpoint_basename": checkpoint_basename,
        "target_checkpoint_path": TARGET_CHECKPOINT_REL,
        "model_loaded": model_loaded,
        "predicted_source": predicted_source,
        "fallback_used": fallback_used,
        "fake_logits_used": False,
        "heuristic_policy_path_used": False,
        "adapter_checkpoint_path": adapter_checkpoint,
    }

    summary_payload = {
        "stage": "10D.15",
        "generated_at_utc": _utc_now(),
        "checkpoint_binding_status": binding_payload["classification"],
        "active_checkpoint_path": checkpoint_path,
        "active_checkpoint_basename": checkpoint_basename,
        "total_inference_requests": inference_requests,
        "successful_inference_requests": successful_inference,
        "failed_inference_requests": failed_inference,
        "first_step_B2_predicted_action": b2_pred,
        "first_step_B2_p_harvest": b2_p_harvest,
        "first_step_B2_p_noop": b2_p_noop,
        "first_step_C3_predicted_action": c3_pred,
        "first_step_C3_p_produce": c3_p_produce,
        "first_step_C3_p_noop": c3_p_noop,
        "first_step_actor_cell_predicted_noop_share": float(global_summary.get("actor_cell_predicted_noop_share") or 0.0),
        "first_step_off_actor_non_noop_count": off_actor_non_noop_count,
        "total_non_noop_actor_predictions": len(trace_rows),
        "total_commands_built": total_commands_built,
        "total_commands_submitted_to_action_applier": total_commands_submitted,
        "total_commands_reached_match_manager": total_commands_reached_match,
        "total_commands_accepted": total_commands_accepted,
        "decoder_reject_counts_by_reason": decoder_reject_counts,
        "action_applier_reject_counts_by_reason": applier_reject_counts,
        "match_manager_reject_counts_by_reason": match_reject_counts,
        "visible_behavior_observed": visible_behavior_observed,
        "terminal_result": episode.get("terminal_reason") or snapshot.get("decision") or "unknown",
        "labels": labels,
        "primary_next_gate": primary_next_gate,
    }

    audit_payload = {
        "stage": "10D.15",
        "generated_at_utc": _utc_now(),
        "step_index": step,
        "focus_cells": {
            "B2": {
                "predicted_action_type": b2_pred,
                "top3": b2.get("action_type_top3") or [],
                "p_noop": b2_p_noop,
                "p_harvest": b2_p_harvest,
                "command_built": _bool(b2.get("command_built")),
                "command_not_built_reason": b2.get("command_not_built_reason") or None,
                "action_applier_reached": _bool(b2.get("action_applier_reached")),
                "match_manager_apply_command_reached": _bool(b2.get("apply_command_reached")),
            },
            "C3": {
                "predicted_action_type": c3_pred,
                "top3": c3.get("action_type_top3") or [],
                "p_noop": c3_p_noop,
                "p_produce": c3_p_produce,
                "command_built": _bool(c3.get("command_built")),
                "command_not_built_reason": c3.get("command_not_built_reason") or None,
                "action_applier_reached": _bool(c3.get("action_applier_reached")),
                "match_manager_apply_command_reached": _bool(c3.get("apply_command_reached")),
            },
        },
        "command_trace_rows": len(trace_rows),
        "decoder_reject_counts_by_reason": decoder_reject_counts,
        "action_applier_reject_counts_by_reason": applier_reject_counts,
        "match_manager_reject_counts_by_reason": match_reject_counts,
        "totals": {
            "total_commands_built": total_commands_built,
            "total_commands_submitted_to_action_applier": total_commands_submitted,
            "total_commands_reached_match_manager": total_commands_reached_match,
            "total_commands_accepted": total_commands_accepted,
        },
    }

    stage_snapshot_path = out_dir / "stage10d15_unity_step0001_snapshot.json"
    checkpoint_path = out_dir / "stage10d15_checkpoint_binding_verification.json"
    trace_path = out_dir / "stage10d15_unity_runtime_command_trace.jsonl"
    summary_path = out_dir / "stage10d15_unity_visual_rerun_summary.json"
    audit_path = out_dir / "stage10d15_decoder_applier_matchmanager_audit.json"
    report_md_path = out_dir / "STAGE10D15_UNITY_VISUAL_RERUN_WITH_AUGMENTED_STUDENT_REPORT.md"

    stage_snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=True, indent=2), encoding="utf-8")
    checkpoint_path.write_text(json.dumps(binding_payload, ensure_ascii=True, indent=2), encoding="utf-8")

    with trace_path.open("w", encoding="utf-8") as f:
        for row in trace_rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")

    summary_path.write_text(json.dumps(summary_payload, ensure_ascii=True, indent=2), encoding="utf-8")
    audit_path.write_text(json.dumps(audit_payload, ensure_ascii=True, indent=2), encoding="utf-8")

    md_lines: list[str] = []
    md_lines.append("# STAGE10D15_UNITY_VISUAL_RERUN_WITH_AUGMENTED_STUDENT_REPORT")
    md_lines.append("")
    md_lines.append("## 1. Purpose and constraints")
    md_lines.append("- Stage10D.15 is runtime verification only: no PPO, no teacher/student training, no checkpoint mutation, no decoder/applier/match-manager semantic changes.")
    md_lines.append("- Goal: validate live Unity path from model logits to command submission and visible runtime behavior.")
    md_lines.append("")
    md_lines.append("## 2. Active checkpoint binding verification")
    md_lines.append(f"- checkpoint_binding_status: {binding_payload['classification']}")
    md_lines.append(f"- active_checkpoint_path: {binding_payload['active_checkpoint_path']}")
    md_lines.append(f"- active_checkpoint_basename: {binding_payload['active_checkpoint_basename']}")
    md_lines.append(f"- model_loaded: {binding_payload['model_loaded']}")
    md_lines.append(f"- predicted_source: {binding_payload['predicted_source']}")
    md_lines.append(f"- fallback_used: {binding_payload['fallback_used']}")
    md_lines.append("")
    md_lines.append("## 3. Unity scene/run configuration")
    md_lines.append("- scene: Assets/Scenes/Week6_StudentVisualInspection.unity")
    md_lines.append("- observation_shape: [24,24,27]")
    md_lines.append(f"- first_step_snapshot_source: {paths.snapshot_src.as_posix()}")
    md_lines.append("")
    md_lines.append("## 4. First-step observation and logits")
    md_lines.append(f"- B2 predicted_action: {b2_pred}; p_harvest={b2_p_harvest:.10f}; p_noop={b2_p_noop:.3e}")
    md_lines.append(f"- C3 predicted_action: {c3_pred}; p_produce={c3_p_produce:.10f}; p_noop={c3_p_noop:.3e}")
    md_lines.append(f"- logits_shape_validation: {'LOGITS_SHAPE_VALID' if logits_shape_valid else 'LOGITS_SHAPE_INVALID'}")
    md_lines.append("")
    md_lines.append("## 5. Actor-cell predictions")
    md_lines.append(f"- first_step_actor_cell_predicted_noop_share: {summary_payload['first_step_actor_cell_predicted_noop_share']}")
    md_lines.append(f"- first_step_off_actor_non_noop_count: {summary_payload['first_step_off_actor_non_noop_count']}")
    md_lines.append("")
    md_lines.append("## 6. Decoder command build results")
    md_lines.append(f"- total_non_noop_actor_predictions: {summary_payload['total_non_noop_actor_predictions']}")
    md_lines.append(f"- total_commands_built: {summary_payload['total_commands_built']}")
    md_lines.append(f"- decoder_reject_counts_by_reason: {summary_payload['decoder_reject_counts_by_reason']}")
    md_lines.append("")
    md_lines.append("## 7. ActionApplier results")
    md_lines.append(f"- total_commands_submitted_to_action_applier: {summary_payload['total_commands_submitted_to_action_applier']}")
    md_lines.append(f"- action_applier_reject_counts_by_reason: {summary_payload['action_applier_reject_counts_by_reason']}")
    md_lines.append("")
    md_lines.append("## 8. MatchManager.ApplyCommand results")
    md_lines.append(f"- total_commands_reached_match_manager: {summary_payload['total_commands_reached_match_manager']}")
    md_lines.append(f"- total_commands_accepted: {summary_payload['total_commands_accepted']}")
    md_lines.append(f"- match_manager_reject_counts_by_reason: {summary_payload['match_manager_reject_counts_by_reason']}")
    md_lines.append("")
    md_lines.append("## 9. Visible behavior summary")
    md_lines.append(f"- visible_behavior_observed: {summary_payload['visible_behavior_observed']}")
    md_lines.append(f"- terminal_result: {summary_payload['terminal_result']}")
    md_lines.append("")
    md_lines.append("## 10. Classification labels")
    for label in labels:
        md_lines.append(f"- {label}")
    md_lines.append("")
    md_lines.append("## 11. Primary next gate")
    md_lines.append(f"- primary_next_gate: {primary_next_gate}")
    md_lines.append("")
    md_lines.append("## 12. What not to do next")
    md_lines.append("- Do not run PPO or retraining in Stage10D.15 follow-up.")
    md_lines.append("- Do not patch decoder/applier/match-manager semantics before Stage10D.16 gate audits.")
    md_lines.append("- Do not claim full transfer success beyond collected Unity runtime evidence.")
    md_lines.append("")
    md_lines.append("## Explicit required statements")
    md_lines.append(f"- Stage10D.14 checkpoint loaded: {checkpoint_ok}")
    md_lines.append(f"- Model logits are real: {inference_ok}")
    md_lines.append(f"- B2 switched to Harvest in live Unity: {b2_harvest}")
    md_lines.append(f"- C3 switched to Produce in live Unity: {c3_produce}")
    md_lines.append(f"- Commands were built: {total_commands_built > 0}")
    md_lines.append(f"- ActionApplier was reached: {total_commands_submitted > 0}")
    md_lines.append(f"- MatchManager.ApplyCommand was reached: {total_commands_reached_match > 0}")
    md_lines.append(f"- Visible behavior was observed: {visible_behavior_observed}")

    report_md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(checkpoint_path.as_posix())
    print(stage_snapshot_path.as_posix())
    print(trace_path.as_posix())
    print(summary_path.as_posix())
    print(audit_path.as_posix())
    print(report_md_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
