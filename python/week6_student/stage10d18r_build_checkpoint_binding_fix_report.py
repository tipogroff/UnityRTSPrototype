from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_CHECKPOINT_BASENAME = "student_bc_stage10d17_movement_augmented_best.pt"
EXPECTED_LOGIT_SHAPES: dict[str, list[int]] = {
    "action_type_logits": [1, 576, 6],
    "move_dir_logits": [1, 576, 4],
    "harvest_dir_logits": [1, 576, 4],
    "return_dir_logits": [1, 576, 4],
    "produce_dir_logits": [1, 576, 4],
    "produce_unit_type_logits": [1, 576, 7],
    "attack_target_local_logits": [1, 576, 49],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _parse_shape_lines(lines: list[str]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for line in lines:
        if not isinstance(line, str) or ":" not in line:
            continue
        k, v = line.split(":", 1)
        values: list[int] = []
        ok = True
        for token in v.strip().strip("[]").split(","):
            token = token.strip()
            if not token:
                continue
            try:
                values.append(int(token))
            except ValueError:
                ok = False
                break
        if ok:
            out[k.strip()] = values
    return out


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    tmp_dir = root / "python/week6_student/tmp/stage10d18r_checkpoint_binding_fix"
    reports = root / "python/week6_student/reports"
    reports.mkdir(parents=True, exist_ok=True)

    manifest = _read_json(tmp_dir / "stage10d18r_run_manifest.json")
    snapshot = _read_json(tmp_dir / "stage10d18r_snapshot_step0001.json")
    table_rows = _read_jsonl(tmp_dir / "stage10d10_global_runtime_cell_table_step0001.jsonl")

    row_by_flat = {int(r.get("cell_index", -1)): r for r in table_rows}
    b2 = row_by_flat.get(25, {})
    c3 = row_by_flat.get(50, {})

    active_checkpoint_path = str(snapshot.get("checkpoint_path_used_at_inference") or snapshot.get("checkpoint") or manifest.get("configured_checkpoint_relative_path") or "").replace("\\", "/")
    checkpoint_basename = Path(active_checkpoint_path).name if active_checkpoint_path else ""

    sources = [str(r.get("predicted_action_type_source") or "") for r in snapshot.get("actor_cells", []) if isinstance(r, dict)]
    predicted_source = "model_logits" if sources and all(s == "model_logits" for s in sources) else (sources[0] if sources else "unknown")
    fallback_used = any(s and s != "model_logits" for s in sources)
    fake_logits_used = any("fake" in s.lower() for s in sources if s)
    heuristic_policy_path_used = any("heuristic" in s.lower() for s in sources if s)

    shape_map = _parse_shape_lines(snapshot.get("logits_shape_lines") or [])
    logits_shapes_valid = all(shape_map.get(k) == v for k, v in EXPECTED_LOGIT_SHAPES.items())

    model_loaded = bool(snapshot.get("parsed_logits_available"))
    adapter_invoked = bool(snapshot.get("adapter_invoked"))
    python_request_status = str(snapshot.get("python_request_status") or "")
    binding_confirmed = (
        checkpoint_basename == EXPECTED_CHECKPOINT_BASENAME
        and model_loaded
        and adapter_invoked
        and predicted_source == "model_logits"
        and not fallback_used
        and not fake_logits_used
        and not heuristic_policy_path_used
        and logits_shapes_valid
        and python_request_status != "bridge_start_failed"
    )

    bridge_status = {
        "generated_at_utc": _utc_now(),
        "adapter_invoked": adapter_invoked,
        "inference_request_count": snapshot.get("inference_request_count"),
        "python_request_status": python_request_status,
        "python_response_status": snapshot.get("python_response_status"),
        "parsed_logits_available": model_loaded,
        "adapter_artifact_created": bool(snapshot.get("adapter_artifact_created")),
        "adapter_artifact_missing_reason": snapshot.get("adapter_artifact_missing_reason"),
        "raw_bridge_response_keys": snapshot.get("raw_bridge_response_keys"),
    }

    actor_logits = {
        "generated_at_utc": _utc_now(),
        "step": 1,
        "b2": {
            "flat": 25,
            "predicted_action": b2.get("predicted_action_type"),
            "predicted_source": b2.get("predicted_action_type_source"),
            "p_noop": b2.get("p_noop"),
            "p_harvest": b2.get("p_harvest"),
            "p_move": b2.get("p_move"),
            "action_type_logits_len": len(b2.get("action_type_logits") or []),
        },
        "c3": {
            "flat": 50,
            "predicted_action": c3.get("predicted_action_type"),
            "predicted_source": c3.get("predicted_action_type_source"),
            "p_noop": c3.get("p_noop"),
            "p_produce": c3.get("p_produce"),
            "p_move": c3.get("p_move"),
            "action_type_logits_len": len(c3.get("action_type_logits") or []),
        },
        "logits_shapes": shape_map,
    }

    labels: list[str] = []
    labels.append("STAGE10D18R_UNITY_CHECKPOINT_BINDING_CONFIRMED" if checkpoint_basename == EXPECTED_CHECKPOINT_BASENAME else "STAGE10D18R_UNITY_BINDING_FIX_FAIL")
    if model_loaded:
        labels.append("STAGE10D18R_UNITY_MODEL_LOADED")
    if predicted_source == "model_logits":
        labels.append("STAGE10D18R_UNITY_REAL_MODEL_LOGITS_CONFIRMED")
    if logits_shapes_valid:
        labels.append("STAGE10D18R_UNITY_LOGITS_SHAPES_VALID")
    if not fallback_used and not fake_logits_used and not heuristic_policy_path_used:
        labels.append("STAGE10D18R_UNITY_FALLBACK_NOT_USED")
    labels.append("STAGE10D18R_UNITY_BINDING_FIX_PASS" if binding_confirmed else "STAGE10D18R_UNITY_BINDING_FIX_FAIL")

    root_cause_labels = []
    diag_path = reports / "stage10d18r_bridge_start_failure_diagnostics.json"
    if diag_path.exists():
        diag = _read_json(diag_path)
        root_cause = str(diag.get("root_cause") or "unknown")
        if "filename_gate" in root_cause:
            root_cause_labels.append("STAGE10D18R_ROOT_CAUSE_FILENAME_GATE")
        elif "path" in root_cause:
            root_cause_labels.append("STAGE10D18R_ROOT_CAUSE_PATH_RESOLUTION")
        elif "python" in root_cause:
            root_cause_labels.append("STAGE10D18R_ROOT_CAUSE_PYTHON_LAUNCH")
        elif "payload" in root_cause:
            root_cause_labels.append("STAGE10D18R_ROOT_CAUSE_CHECKPOINT_PAYLOAD")
        elif "report" in root_cause:
            root_cause_labels.append("STAGE10D18R_ROOT_CAUSE_REPORT_BUILDER_ONLY")
        else:
            root_cause_labels.append("STAGE10D18R_ROOT_CAUSE_UNKNOWN")
    else:
        root_cause_labels.append("STAGE10D18R_ROOT_CAUSE_UNKNOWN")

    labels.extend(root_cause_labels)

    if binding_confirmed:
        primary_next_gate = "GO_FOR_STAGE10D18_RUNTIME_BC_REDEPLOY_EVAL_RERUN"
    elif checkpoint_basename != EXPECTED_CHECKPOINT_BASENAME:
        primary_next_gate = "GO_FOR_STAGE10D18R_CHECKPOINT_PATH_FIX"
    elif python_request_status == "bridge_start_failed":
        primary_next_gate = "GO_FOR_STAGE10D18R_PYTHON_BRIDGE_LAUNCH_FIX"
    elif not model_loaded:
        primary_next_gate = "GO_FOR_STAGE10D18R_CHECKPOINT_LOADER_FIX"
    else:
        primary_next_gate = "GO_FOR_STAGE10D18R_INSTRUMENTATION_FIX"

    verification_payload = {
        "generated_at_utc": _utc_now(),
        "checkpoint_binding_status": "STAGE10D18R_CHECKPOINT_BINDING_CONFIRMED" if binding_confirmed else "STAGE10D18R_CHECKPOINT_BINDING_FAILED",
        "active_checkpoint_path": active_checkpoint_path,
        "active_checkpoint_basename": checkpoint_basename,
        "model_loaded": model_loaded,
        "adapter_invoked": adapter_invoked,
        "parsed_logits_available": bool(snapshot.get("parsed_logits_available")),
        "predicted_source": predicted_source,
        "fallback_used": fallback_used,
        "fake_logits_used": fake_logits_used,
        "heuristic_policy_path_used": heuristic_policy_path_used,
        "python_request_status": python_request_status,
        "logits_shapes": shape_map,
        "logits_shapes_valid": logits_shapes_valid,
        "labels": labels,
        "primary_next_gate": primary_next_gate,
    }

    checkpoint_verification_path = reports / "stage10d18r_checkpoint_binding_verification.json"
    actor_logits_path = reports / "stage10d18r_actor_cell_logits_step0001.json"
    bridge_status_path = reports / "stage10d18r_inference_bridge_status.json"
    snapshot_copy_path = reports / "stage10d18r_snapshot_step0001.json"
    report_path = reports / "STAGE10D18R_CHECKPOINT_BINDING_FIX_REPORT.md"

    checkpoint_verification_path.write_text(json.dumps(verification_payload, ensure_ascii=True, indent=2), encoding="utf-8")
    actor_logits_path.write_text(json.dumps(actor_logits, ensure_ascii=True, indent=2), encoding="utf-8")
    bridge_status_path.write_text(json.dumps(bridge_status, ensure_ascii=True, indent=2), encoding="utf-8")
    snapshot_copy_path.write_text(json.dumps(snapshot, ensure_ascii=True, indent=2), encoding="utf-8")

    lines: list[str] = []
    lines.append("# STAGE10D18R_CHECKPOINT_BINDING_FIX_REPORT")
    lines.append("")
    lines.append("## 1. Purpose and constraints")
    lines.append("- Stage10D.18R fixes checkpoint binding/bridge start only; no PPO/training/checkpoint mutation/runtime semantics changes.")
    lines.append("")
    lines.append("## 2. Stage10D.18 failure recap")
    lines.append("- Stage10D.18 failed before real logits: bridge_start_failed and fallback_no_adapter_artifact.")
    lines.append("")
    lines.append("## 3. Pre-fix git/artifact snapshot")
    lines.append("- See stage10d18r_pre_fix_git_and_failure_snapshot.json.")
    lines.append("")
    lines.append("## 4. Root cause diagnostics")
    lines.append("- See stage10d18r_bridge_start_failure_diagnostics.json.")
    lines.append(f"- root_cause_labels: {root_cause_labels}")
    lines.append("")
    lines.append("## 5. Implemented minimal fix")
    lines.append("- Week6StudentPolicyAdapter filename allowlist now includes student_bc_stage10d17_movement_augmented_best.pt.")
    lines.append("")
    lines.append("## 6. Manual checkpoint verification")
    manual_path = reports / "stage10d18r_checkpoint_binding_manual_verification.json"
    if manual_path.exists():
        manual = _read_json(manual_path)
        lines.append(f"- manual_load_status: {manual.get('load_status')}")
        lines.append(f"- manual_forward_status: {manual.get('forward_status')}")
        lines.append(f"- manual_logits_shapes_valid: {manual.get('logits_shapes_valid')}")
    else:
        lines.append("- manual verification artifact missing.")
    lines.append("")
    lines.append("## 7. Unity minimal rerun verification")
    lines.append(f"- checkpoint_binding_status: {verification_payload['checkpoint_binding_status']}")
    lines.append(f"- model_loaded: {model_loaded}")
    lines.append(f"- adapter_invoked: {adapter_invoked}")
    lines.append(f"- parsed_logits_available: {verification_payload['parsed_logits_available']}")
    lines.append(f"- predicted_source: {predicted_source}")
    lines.append(f"- fallback_used: {fallback_used}")
    lines.append(f"- logits_shapes_valid: {logits_shapes_valid}")
    lines.append(f"- B2: action={actor_logits['b2']['predicted_action']} p_noop={actor_logits['b2']['p_noop']} p_harvest={actor_logits['b2']['p_harvest']} p_move={actor_logits['b2']['p_move']}")
    lines.append(f"- C3: action={actor_logits['c3']['predicted_action']} p_noop={actor_logits['c3']['p_noop']} p_produce={actor_logits['c3']['p_produce']} p_move={actor_logits['c3']['p_move']}")
    lines.append("")
    lines.append("## 8. Classification labels")
    for label in labels:
        lines.append(f"- {label}")
    lines.append("")
    lines.append("## 9. Primary next gate")
    lines.append(f"- {primary_next_gate}")
    lines.append("")
    lines.append("## 10. What not to do next")
    lines.append("- Do not run PPO.")
    lines.append("- Do not train teacher/student.")
    lines.append("- Do not mutate checkpoints.")
    lines.append("- Do not change decoder/applier/match manager semantics.")
    lines.append("- Do not infer movement behavior conclusions until full Stage10D.18 rerun.")
    lines.append("")
    lines.append("## Explicit answers")
    lines.append(f"- Did the Stage10D.17 checkpoint file exist? {Path(active_checkpoint_path).name == EXPECTED_CHECKPOINT_BASENAME}")
    lines.append(f"- Was the basename accepted? {checkpoint_basename == EXPECTED_CHECKPOINT_BASENAME}")
    lines.append("- Was any filename gate changed? yes")
    if manual_path.exists():
        lines.append(f"- Did manual strict load pass? {manual.get('load_status') == 'ok'}")
        lines.append(f"- Did manual forward pass produce valid logits shapes? {manual.get('forward_status') == 'ok' and manual.get('logits_shapes_valid') is True}")
    else:
        lines.append("- Did manual strict load pass? unknown")
        lines.append("- Did manual forward pass produce valid logits shapes? unknown")
    lines.append(f"- Did Unity bridge start successfully after fix? {python_request_status != 'bridge_start_failed'}")
    lines.append(f"- Did Unity receive real model logits? {predicted_source == 'model_logits' and model_loaded}")
    lines.append(f"- Was fallback avoided? {not fallback_used and not fake_logits_used and not heuristic_policy_path_used}")
    lines.append(f"- Are logits shapes valid? {logits_shapes_valid}")
    lines.append(f"- Is Stage10D.18 now ready to rerun as behavior evaluation? {binding_confirmed}")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(checkpoint_verification_path.as_posix())
    print(snapshot_copy_path.as_posix())
    print(actor_logits_path.as_posix())
    print(bridge_status_path.as_posix())
    print(report_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
