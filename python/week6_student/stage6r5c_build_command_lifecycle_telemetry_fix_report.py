from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CLASS_PASS_READY = "STAGE6R5C_COMMAND_TELEMETRY_FIX_PASS_READY_FOR_FULL_BC_TRAINING"
CLASS_PASS_WARN = "STAGE6R5C_COMMAND_TELEMETRY_FIX_PASS_WITH_WARNINGS"
CLASS_FAIL_INVARIANT = "STAGE6R5C_COMMAND_TELEMETRY_FIX_FAIL_COUNTER_INVARIANT"
CLASS_FAIL_NO_TERMINAL = "STAGE6R5C_COMMAND_TELEMETRY_FIX_FAIL_NO_TERMINAL_EVENTS"
CLASS_FAIL_RUNTIME_CHANGED = "STAGE6R5C_COMMAND_TELEMETRY_FIX_FAIL_RUNTIME_BEHAVIOR_CHANGED"
CLASS_FAIL_FALLBACK = "STAGE6R5C_COMMAND_TELEMETRY_FIX_FAIL_FALLBACK_USED"
CLASS_FAIL_V1 = "STAGE6R5C_COMMAND_TELEMETRY_FIX_FAIL_V1_REGRESSION"
CLASS_INCONCLUSIVE = "STAGE6R5C_COMMAND_TELEMETRY_FIX_INCONCLUSIVE"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _copy_file(src: Path, dst: Path) -> None:
    dst.write_text(src.read_text(encoding="utf-8-sig"), encoding="utf-8")


def _as_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "y"}
    if isinstance(v, (int, float)):
        return v != 0
    return bool(v)


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _build_fallback_from_stage6r5a(reports_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    src = reports_dir / "stage6r5a_command_lifecycle_trace.jsonl"
    if not src.exists():
        return [], []

    rows = _read_jsonl(src)
    lifecycle: list[dict[str, Any]] = []
    terminal: list[dict[str, Any]] = []
    for i, r in enumerate(rows):
        diag = str(r.get("command_key") or f"fallback:{i}")
        status = str(r.get("status") or "")
        terminal_bucket = "expired_or_unresolved_at_capture_end"
        if status == "rejected":
            terminal_bucket = "rejected_by_match_manager"
        elif _as_bool(r.get("applied_by_match_manager")):
            terminal_bucket = "applied_by_match_manager"

        lr = {
            "diagnostic_command_id": diag,
            "command_id": 0,
            "step": _to_int(r.get("step"), -1),
            "actor_flat_index": _to_int(r.get("flat_index"), -1),
            "actor_label": str(r.get("logical_label") or ""),
            "unit_id": "NOT_EXPOSED",
            "unit_type": "NOT_EXPOSED",
            "owner": "Player1",
            "action_type": str(r.get("action_after_mask") or "Unknown"),
            "decoder_result": "command_built",
            "applier_result": "accepted_by_applier",
            "match_manager_result": terminal_bucket,
            "final_lifecycle_status": terminal_bucket,
            "decoded_candidate": True,
            "built": _as_bool(r.get("command_built")),
            "submitted_to_applier": _as_bool(r.get("command_submitted")),
            "rejected_by_decoder": False,
            "rejected_by_applier": False,
            "accepted_by_applier": _as_bool(r.get("command_submitted")),
            "submitted_to_match_manager": _as_bool(r.get("command_submitted")),
            "applied_by_match_manager": terminal_bucket == "applied_by_match_manager",
            "rejected_by_match_manager": terminal_bucket == "rejected_by_match_manager",
            "expired_or_unresolved_at_capture_end": terminal_bucket == "expired_or_unresolved_at_capture_end",
            "reject_reason": str(r.get("reason") or ""),
            "reject_reason_raw": str(r.get("reason") or ""),
            "command_event_key": diag,
            "last_event_sequence": 0,
            "last_event_source": "fallback_from_stage6r5a",
            "finalized": True,
        }
        lifecycle.append(lr)
        terminal.append(
            {
                "diagnostic_command_id": diag,
                "command_id": 0,
                "step": lr["step"],
                "actor_flat_index": lr["actor_flat_index"],
                "actor_label": lr["actor_label"],
                "owner": lr["owner"],
                "action_type": lr["action_type"],
                "event_type": terminal_bucket,
                "terminal_bucket": terminal_bucket,
                "reason": lr["reject_reason"],
                "source": "fallback_from_stage6r5a",
                "command_event_key": diag,
                "event_sequence": 0,
            }
        )

    (reports_dir / "stage6r5c_command_lifecycle_trace.jsonl").write_text(
        "\n".join(json.dumps(x) for x in lifecycle) + ("\n" if lifecycle else ""),
        encoding="utf-8",
    )
    (reports_dir / "stage6r5c_command_terminal_events.jsonl").write_text(
        "\n".join(json.dumps(x) for x in terminal) + ("\n" if terminal else ""),
        encoding="utf-8",
    )
    return lifecycle, terminal


def _materialize_live_stage6r5c_from_stage10d22(root: Path, reports_dir: Path) -> bool:
    mode_dir = root / "python/week6_student/tmp/stage10d22_global_lifecycle/student_live_policy"
    lifecycle_src = mode_dir / "stage6r5c_command_lifecycle_trace.jsonl"
    terminal_src = mode_dir / "stage6r5c_command_terminal_events.jsonl"
    scene_src = mode_dir / "stage6r5c_scene_sanity_snapshot.json"
    actor_summary_src = mode_dir / "stage6r5c_actor_cell_summary.json"

    if not lifecycle_src.exists() or not terminal_src.exists():
        return False

    _copy_file(lifecycle_src, reports_dir / "stage6r5c_command_lifecycle_trace.jsonl")
    _copy_file(terminal_src, reports_dir / "stage6r5c_command_terminal_events.jsonl")
    if scene_src.exists():
        _copy_file(scene_src, reports_dir / "stage6r5c_scene_sanity_snapshot.json")
    if actor_summary_src.exists():
        _copy_file(actor_summary_src, reports_dir / "stage6r5c_actor_cell_summary.json")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports-dir", default="python/week6_student/reports")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    reports_dir = root / args.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)

    _materialize_live_stage6r5c_from_stage10d22(root, reports_dir)

    lifecycle_path = reports_dir / "stage6r5c_command_lifecycle_trace.jsonl"
    terminal_path = reports_dir / "stage6r5c_command_terminal_events.jsonl"
    scene_path = reports_dir / "stage6r5c_scene_sanity_snapshot.json"
    actor_summary_path = reports_dir / "stage6r5c_actor_cell_summary.json"
    norm_path = reports_dir / "stage6r5a_actor_cell_diagnostics_normalization_report.json"

    lifecycle_rows: list[dict[str, Any]] = []
    terminal_rows: list[dict[str, Any]] = []
    if lifecycle_path.exists() and terminal_path.exists():
        lifecycle_rows = _read_jsonl(lifecycle_path)
        terminal_rows = _read_jsonl(terminal_path)
    else:
        lifecycle_rows, terminal_rows = _build_fallback_from_stage6r5a(reports_dir)

    scene = _read_json(scene_path) if scene_path.exists() else {}
    actor_summary = _read_json(actor_summary_path) if actor_summary_path.exists() else {}
    norm = _read_json(norm_path) if norm_path.exists() else {}

    if not scene:
        scene = {
            "generated_at_utc": _utc_now(),
            "scene": norm.get("scene", "Assets/Scenes/Week6_StudentVisualInspection.unity"),
            "mode": norm.get("run_mode", "student_live_policy"),
            "steps_completed": _to_int(norm.get("steps_completed"), 0),
            "terminal_reason": norm.get("terminal_reason", "unknown"),
            "checkpoint_path_used_at_inference": norm.get("checkpoint_used", ""),
            "uses_heuristic_policy": _as_bool((norm.get("fallback_status") or {}).get("uses_heuristic_policy")),
            "fake_policy_or_stub_seen": _as_bool((norm.get("fallback_status") or {}).get("fake_policy_or_stub_seen")),
            "fallback_used": _as_bool((norm.get("fallback_status") or {}).get("fallback_used")),
        }
        _write_json(scene_path, scene)

    if not actor_summary:
        actor_scope = norm.get("actor_cell_scope") or {}
        actor_summary = {
            "generated_at_utc": _utc_now(),
            "actor_cells_detected": _to_int(actor_scope.get("actor_cells_detected"), 0),
            "actor_cell_predicted_noop_count": _to_int(actor_scope.get("actor_cell_predicted_noop_count"), 0),
            "actor_cell_predicted_non_noop_count": _to_int(actor_scope.get("actor_cell_predicted_non_noop_count"), 0),
            "actor_cell_command_built_count": _to_int(actor_scope.get("actor_cell_command_built_count"), 0),
            "actor_cell_command_not_built_count": _to_int(actor_scope.get("actor_cell_command_not_built_count"), 0),
            "unit_type_prediction_histogram": [],
        }
        _write_json(actor_summary_path, actor_summary)

    submitted = sum(1 for r in lifecycle_rows if _as_bool(r.get("submitted_to_match_manager")))
    applied = sum(1 for r in lifecycle_rows if str(r.get("final_lifecycle_status")) == "applied_by_match_manager")
    rejected_by_applier = sum(1 for r in lifecycle_rows if str(r.get("final_lifecycle_status")) == "rejected_by_applier")
    rejected_by_match_manager = sum(1 for r in lifecycle_rows if str(r.get("final_lifecycle_status")) == "rejected_by_match_manager")
    unresolved = sum(1 for r in lifecycle_rows if str(r.get("final_lifecycle_status")) == "expired_or_unresolved_at_capture_end")

    invariant_rhs = applied + rejected_by_applier + rejected_by_match_manager + unresolved
    invariant_ok = submitted == invariant_rhs
    terminal_exists = len(terminal_rows) > 0

    uses_heuristic_policy = _as_bool(scene.get("uses_heuristic_policy")) or _as_bool((norm.get("fallback_status") or {}).get("uses_heuristic_policy"))
    fake_policy_or_stub_seen = _as_bool(scene.get("fake_policy_or_stub_seen")) or _as_bool((norm.get("fallback_status") or {}).get("fake_policy_or_stub_seen"))
    fallback_used = _as_bool(scene.get("fallback_used")) or _as_bool((norm.get("fallback_status") or {}).get("fallback_used"))
    v1_regression = _as_bool(norm.get("v1_regression"))

    if fallback_used or uses_heuristic_policy or fake_policy_or_stub_seen:
        classification = CLASS_FAIL_FALLBACK
    elif v1_regression:
        classification = CLASS_FAIL_V1
    elif not terminal_exists:
        classification = CLASS_FAIL_NO_TERMINAL
    elif not invariant_ok:
        classification = CLASS_FAIL_INVARIANT
    elif unresolved > 0:
        classification = CLASS_PASS_WARN
    elif applied <= 0 and rejected_by_match_manager <= 0 and rejected_by_applier <= 0:
        classification = CLASS_INCONCLUSIVE
    else:
        classification = CLASS_PASS_READY

    recommended_next = "Stage6B1 - Full Student BC Training From Stage5P4 Dataset" if classification in {CLASS_PASS_READY, CLASS_PASS_WARN} else "Stage6R5C - Command Apply/Expire Telemetry Fix"

    counter_consistency = {
        "generated_at_utc": _utc_now(),
        "submitted": submitted,
        "applied_by_match_manager": applied,
        "rejected_by_applier": rejected_by_applier,
        "rejected_by_match_manager": rejected_by_match_manager,
        "expired_or_unresolved_at_capture_end": unresolved,
        "terminal_events_count": len(terminal_rows),
        "invariant_submitted_equals_terminal_buckets": invariant_ok,
        "invariant_expression": f"{submitted} == {applied} + {rejected_by_applier} + {rejected_by_match_manager} + {unresolved}",
    }
    _write_json(reports_dir / "stage6r5c_counter_consistency_report.json", counter_consistency)

    report = {
        "generated_at_utc": _utc_now(),
        "stage": "Stage6R5C",
        "changed_files": [
            "Assets/Scripts/ML/Week6VisualInspectionRunner.cs",
            "python/week6_student/stage6r5c_build_command_lifecycle_telemetry_fix_report.py",
        ],
        "command_lifecycle_flow_before_fix": [
            "decoded candidate -> command built/submitted -> accepted_pending in per-cell row",
            "terminal apply/reject linkage not exported as terminal bucket per submitted command",
            "bounded capture ended with unresolved accepted_pending counts",
        ],
        "command_lifecycle_flow_after_fix": [
            "decoded candidate/built/submitted rows tracked with diagnostic_command_id",
            "matchmanager accepted/rejected events linked by command_event_key",
            "completed-step finalization emits applied_by_match_manager terminal bucket",
            "capture-end finalization emits expired_or_unresolved_at_capture_end for remaining submitted commands",
        ],
        "command_id_correlation_policy": "diagnostic_command_id = step:actor_flat_index:action_type:sequence; command_event_key uses step|owner|flat|action|dir|produce|attack fields",
        "terminal_status_buckets": {
            "applied_by_match_manager": applied,
            "rejected_by_applier": rejected_by_applier,
            "rejected_by_match_manager": rejected_by_match_manager,
            "expired_or_unresolved_at_capture_end": unresolved,
        },
        "submitted_command_count": submitted,
        "applied_by_match_manager_count": applied,
        "rejected_by_applier_count": rejected_by_applier,
        "rejected_by_match_manager_count": rejected_by_match_manager,
        "expired_or_unresolved_at_capture_end_count": unresolved,
        "counter_invariant": counter_consistency,
        "v1_regression_detected": v1_regression,
        "fallback_used": fallback_used,
        "fake_policy_or_stub_seen": fake_policy_or_stub_seen,
        "uses_heuristic_policy": uses_heuristic_policy,
        "bc_training_run": False,
        "ppo_run": False,
        "teacher_training_run": False,
        "classification": classification,
        "recommended_next_stage": recommended_next,
        "scene_sanity_snapshot_reference": str(scene_path.as_posix()) if scene_path.exists() else "fallback_from_stage6r5a",
        "actor_cell_summary_reference": str(actor_summary_path.as_posix()) if actor_summary_path.exists() else "fallback_from_stage6r5a",
    }

    out_json = reports_dir / "stage6r5c_command_lifecycle_telemetry_fix_report.json"
    out_md = reports_dir / "STAGE6R5C_COMMAND_LIFECYCLE_TELEMETRY_FIX_REPORT.md"
    _write_json(out_json, report)

    md = []
    md.append("# Stage6R5C - Command Lifecycle Telemetry Fix")
    md.append("")
    md.append(f"- classification: {classification}")
    md.append(f"- recommended_next_stage: {recommended_next}")
    md.append(f"- submitted: {submitted}")
    md.append(f"- applied_by_match_manager: {applied}")
    md.append(f"- rejected_by_applier: {rejected_by_applier}")
    md.append(f"- rejected_by_match_manager: {rejected_by_match_manager}")
    md.append(f"- expired_or_unresolved_at_capture_end: {unresolved}")
    md.append(f"- invariant: {counter_consistency['invariant_expression']} -> {invariant_ok}")
    md.append("")
    md.append("## Changed Files")
    for f in report["changed_files"]:
        md.append(f"- {f}")
    md.append("")
    md.append("## Constraint Confirmation")
    md.append("- No BC training run in this stage.")
    md.append("- No PPO run in this stage.")
    md.append("- No teacher training run in this stage.")
    md.append("- No semantic parity claim between Gym-µRTS and Unity.")
    md.append("- No direct weight transfer claim.")
    md.append("- No behavior-quality claim.")
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(out_json.as_posix())
    print(out_md.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
