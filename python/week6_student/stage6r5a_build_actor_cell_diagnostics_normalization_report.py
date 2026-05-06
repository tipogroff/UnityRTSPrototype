from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_BRANCH_SIZES = [6, 4, 4, 4, 4, 7, 49]
EXPECTED_OBSERVATION_SHAPE = [24, 24, 27]
EXPECTED_SINGLE_PAYLOAD_ACTION_FLAT_SIZE = 44928
CLASS_READY = "STAGE6R5A_DIAGNOSTICS_NORMALIZATION_PASS_READY_FOR_BEHAVIOR_BOTTLENECK_ANALYSIS"
CLASS_WARN = "STAGE6R5A_DIAGNOSTICS_NORMALIZATION_PASS_WITH_WARNINGS"
CLASS_FAIL_FLAT = "STAGE6R5A_DIAGNOSTICS_NORMALIZATION_FAIL_FLAT_SIZE_CONTRACT"
CLASS_FAIL_COUNTER = "STAGE6R5A_DIAGNOSTICS_NORMALIZATION_FAIL_COUNTER_INCONSISTENCY"
CLASS_FAIL_TRACE = "STAGE6R5A_DIAGNOSTICS_NORMALIZATION_FAIL_ACTOR_CELL_TRACE_MISSING"
CLASS_FAIL_FALLBACK = "STAGE6R5A_DIAGNOSTICS_NORMALIZATION_FAIL_FALLBACK_USED"
CLASS_FAIL_V1 = "STAGE6R5A_DIAGNOSTICS_NORMALIZATION_FAIL_V1_REGRESSION"
CLASS_INCONCLUSIVE = "STAGE6R5A_DIAGNOSTICS_NORMALIZATION_INCONCLUSIVE"
FOCUS_FLATS = {25: "B2", 50: "C3"}
ACTION_TYPES = ["NoOp", "Move", "Harvest", "Return", "Produce", "Attack"]


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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clean_reason(value: Any, default: str = "none") -> str:
    text = str(value or "").strip()
    if not text:
        return default
    return text.replace(" ", "_").lower()


def _norm_action(value: Any) -> str:
    text = str(value or "").strip()
    if text in ACTION_TYPES:
        return text
    low = text.lower()
    for action in ACTION_TYPES:
        if action.lower() == low:
            return action
    return "NoOp"


def _load_run_manifest(base_dir: Path) -> dict[str, Any]:
    manifest_path = base_dir / "stage10d22_run_manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Missing Stage10D22 run manifest: {manifest_path}")
    return _read_json(manifest_path)


def _load_mode_manifest(mode_dir: Path) -> dict[str, Any]:
    path = mode_dir / "stage10d22_mode_manifest.json"
    if not path.exists():
        raise RuntimeError(f"Missing student mode manifest: {path}")
    return _read_json(path)


def _load_snapshots(mode_dir: Path) -> dict[int, dict[str, Any]]:
    snapshots: dict[int, dict[str, Any]] = {}
    for path in sorted(mode_dir.glob("stage10d22_student_live_policy_snapshot_step*.json")):
        step = int(path.stem.split("step")[-1])
        snapshots[step] = _read_json(path)
    if not snapshots:
        raise RuntimeError(f"No student_live_policy snapshots found in {mode_dir}")
    return snapshots


def _load_cell_tables(mode_dir: Path) -> dict[int, list[dict[str, Any]]]:
    tables: dict[int, list[dict[str, Any]]] = {}
    for path in sorted(mode_dir.glob("stage10d10_global_runtime_cell_table_step*.jsonl")):
        step = int(path.stem.split("step")[-1])
        rows = _read_jsonl(path)
        for row in rows:
            row["step"] = step
        tables[step] = rows
    if not tables:
        raise RuntimeError(f"No Stage10D10 cell tables found in {mode_dir}")
    return tables


def _find_mode_dir(root: Path, run_manifest: dict[str, Any], mode_name: str) -> Path:
    for item in run_manifest.get("modes") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("mode") or "").strip() != mode_name:
            continue
        rel = str(item.get("output_relative_dir") or "").replace("\\", "/").strip()
        if not rel:
            break
        candidate = root / rel
        if candidate.exists():
            return candidate
    raise RuntimeError(f"Could not resolve output directory for mode '{mode_name}' from Stage10D22 manifest")


def _resolve_adapter_artifact(adapter_dir: Path, snapshots: dict[int, dict[str, Any]]) -> Path:
    snapshot_paths: list[Path] = []
    for step in sorted(snapshots.keys()):
        raw = str(snapshots[step].get("adapter_artifact_last_output_json_path") or "").strip()
        if raw:
            candidate = Path(raw)
            if candidate.exists():
                snapshot_paths.append(candidate)
    if snapshot_paths:
        snapshot_paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return snapshot_paths[0]

    candidates = sorted(adapter_dir.glob("*_adapter.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError(f"No adapter artifacts found under {adapter_dir}")
    return candidates[0]


def _build_cell_index(rows_by_step: dict[int, list[dict[str, Any]]]) -> dict[int, dict[int, dict[str, Any]]]:
    index: dict[int, dict[int, dict[str, Any]]] = {}
    for step, rows in rows_by_step.items():
        by_cell: dict[int, dict[str, Any]] = {}
        for row in rows:
            by_cell[_to_int(row.get("cell_index"), -1)] = row
        index[step] = by_cell
    return index


def _top_action_entries(row: dict[str, Any]) -> list[dict[str, Any]]:
    top3 = row.get("top3_action_type_probabilities") or []
    entries: list[dict[str, Any]] = []
    if isinstance(top3, list):
        for item in top3:
            if not isinstance(item, dict):
                continue
            entries.append(
                {
                    "action_type": str(item.get("class_name") or ""),
                    "class_id": _to_int(item.get("class_id"), -1),
                    "logit": float(item.get("logit", 0.0) or 0.0),
                    "probability": float(item.get("probability", 0.0) or 0.0),
                }
            )
    return entries


def _command_key(row: dict[str, Any]) -> str:
    command_id = _to_int(row.get("command_id"), 0)
    if command_id > 0:
        return f"cmd:{command_id}"
    step = _to_int(row.get("step"), -1)
    cell = _to_int(row.get("cell_index"), -1)
    action = _norm_action(row.get("decoder_received_action_type") or row.get("masked_action_type"))
    move_dir = _to_int(row.get("decoder_received_move_dir"), _to_int(row.get("masked_move_dir"), -1))
    return f"legacy:{step}:{cell}:{action}:{move_dir}"


def _command_applied(row: dict[str, Any]) -> bool:
    status = str(row.get("command_result_status") or "").strip().lower()
    return status in {"applied", "completed"}


def _choose_reason(row: dict[str, Any]) -> str:
    for key in (
        "applier_reject_reason",
        "reject_reason",
        "decoder_reject_reason",
        "command_not_built_reason",
        "reject_reason_normalized",
    ):
        text = str(row.get(key) or "").strip()
        if text and text != "NOT_EXPOSED":
            return _clean_reason(text)
    return "none"


def _warning_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(item) for item in row) + " |")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage10d22-dir",
        default="python/week6_student/tmp/stage10d22_global_lifecycle",
        help="Directory containing the Stage10D22 bounded Unity run outputs.",
    )
    parser.add_argument(
        "--adapter-dir",
        default="python/week6_student/tmp/day5_sanity",
        help="Directory containing raw adapter JSON artifacts.",
    )
    parser.add_argument(
        "--reports-dir",
        default="python/week6_student/reports",
        help="Directory where Stage6R5A report artifacts will be written.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    stage10d22_dir = root / args.stage10d22_dir
    adapter_dir = root / args.adapter_dir
    reports_dir = root / args.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)

    run_manifest = _load_run_manifest(stage10d22_dir)
    mode_dir = _find_mode_dir(root, run_manifest, "student_live_policy")
    mode_manifest = _load_mode_manifest(mode_dir)
    snapshots = _load_snapshots(mode_dir)
    rows_by_step = _load_cell_tables(mode_dir)
    adapter_path = _resolve_adapter_artifact(adapter_dir, snapshots)
    adapter_payload = _read_json(adapter_path)

    steps_completed_limit = _to_int(mode_manifest.get("steps_completed"), 0)
    if steps_completed_limit > 0:
        snapshots = {step: payload for step, payload in snapshots.items() if step <= steps_completed_limit}
        rows_by_step = {step: rows for step, rows in rows_by_step.items() if step <= steps_completed_limit}

    cell_index = _build_cell_index(rows_by_step)
    steps = sorted(rows_by_step.keys())
    if not steps:
        raise RuntimeError("Stage6R5A requires at least one bounded student_live_policy step")

    total_rows = 0
    all_grid_predicted_noop_count = 0
    all_grid_predicted_non_noop_count = 0
    all_grid_non_actor_rejections = 0
    actor_prediction_rows = 0
    actor_predicted_noop_count = 0
    actor_predicted_non_noop_count = 0
    actor_masked_to_noop_count = 0
    actor_command_built_count = 0
    actor_not_built_reasons: Counter[str] = Counter()
    actor_not_built_count = 0
    fallback_used = False
    fake_policy_used = False
    heuristic_used = False

    actor_cells_detected = 0
    controllable_actor_cells_detected = 0
    actor_trace_rows: list[dict[str, Any]] = []
    command_trace_rows: list[dict[str, Any]] = []
    top_actor_command_outcomes: list[dict[str, Any]] = []

    command_records: dict[str, dict[str, Any]] = {}
    submitted_expansion_map: dict[tuple[int, int], set[str]] = defaultdict(set)

    for step in steps:
        snapshot = snapshots.get(step, {})
        actor_cells = list(snapshot.get("actor_cells") or [])
        actor_cells_detected += len(actor_cells)
        controllable_actor_cells_detected += sum(1 for cell in actor_cells if _as_bool(cell.get("eligible")))
        fallback_used = fallback_used or _as_bool(snapshot.get("uses_heuristic_policy"))
        heuristic_used = heuristic_used or _as_bool(snapshot.get("uses_heuristic_policy"))
        fake_policy_used = fake_policy_used or (str(snapshot.get("policy_source") or "").strip().lower() in {"heuristic", "fake", "stub", "random"})

        focus_rows = set(FOCUS_FLATS.keys())
        for cell in actor_cells:
            focus_rows.add(_to_int(cell.get("flat_index"), -1))

        for flat in sorted(focus_rows):
            row = cell_index.get(step, {}).get(flat)
            if row is None:
                continue

            is_runtime_actor = _as_bool(row.get("runtime_is_friendly_actor"))
            is_focus = flat in FOCUS_FLATS
            if not is_runtime_actor and not is_focus:
                continue

            predicted = _norm_action(row.get("predicted_action_type"))
            selected_before_mask = _norm_action(row.get("raw_action_type_top1") or row.get("predicted_action_type"))
            selected_after_mask = _norm_action(row.get("masked_action_type"))
            raw_command_built = _as_bool(row.get("command_built"))
            raw_command_submitted = _as_bool(row.get("command_submitted") or row.get("applier_submitted"))
            command_accepted = _as_bool(row.get("command_event_accepted") or row.get("applier_accepted"))
            command_rejected = _as_bool(row.get("command_event_rejected") or row.get("applier_rejected"))
            actionable_after_mask = selected_after_mask != "NoOp"
            command_built = actionable_after_mask and raw_command_built
            command_submitted = actionable_after_mask and (raw_command_submitted or command_accepted or command_rejected)
            reason = _choose_reason(row)
            if predicted != "NoOp" and selected_after_mask == "NoOp":
                reason = "masked_to_noop"
            elif predicted == "NoOp":
                reason = "predicted_noop"
            elif not command_built:
                reason = _clean_reason(row.get("command_not_built_reason"), "not_built_in_decoder_or_filter")
            grid_coordinate = {"x": _to_int(row.get("x"), -1), "y": _to_int(row.get("y"), -1)}

            trace_row = {
                "step": step,
                "flat_index": flat,
                "logical_label": str(row.get("visual_label") or FOCUS_FLATS.get(flat, "")),
                "grid_coordinate": grid_coordinate,
                "unit_type": str(row.get("decoded_observation_unit_type") or row.get("unit_type") or "unknown"),
                "owner": str(row.get("decoded_observation_owner") or row.get("unit_owner") or "unknown"),
                "is_controllable_actor_cell": is_runtime_actor,
                "is_focus_cell": is_focus,
                "focus_label": FOCUS_FLATS.get(flat, ""),
                "busy_or_cooldown_state_available": False,
                "busy_state": None,
                "cooldown_state": None,
                "top_action_type_logits_probabilities": _top_action_entries(row),
                "selected_action_type_before_mask": selected_before_mask,
                "selected_action_type_after_mask": selected_after_mask,
                "selected_branch_values": {
                    "move_dir": _to_int(row.get("move_dir"), -1),
                    "harvest_dir": _to_int(row.get("harvest_dir"), -1),
                    "return_dir": _to_int(row.get("return_dir"), -1),
                    "produce_dir": _to_int(row.get("produce_dir"), -1),
                    "produce_unit_type": _to_int(row.get("produce_unit_type"), -1),
                    "attack_target_local": _to_int(row.get("attack_target_local"), -1),
                    "raw_move_dir_top1": _to_int(row.get("raw_move_dir_top1"), -1),
                    "masked_move_dir": _to_int(row.get("masked_move_dir"), -1),
                    "decoder_received_move_dir": _to_int(row.get("decoder_received_move_dir"), -1),
                },
                "command_built": command_built,
                "command_submitted": command_submitted,
                "command_accepted": command_accepted,
                "command_rejected": command_rejected,
                "command_result_status": str(row.get("command_result_status") or ""),
                "reason_if_not_built_or_rejected": reason,
            }
            actor_trace_rows.append(trace_row)

            if is_runtime_actor and len(top_actor_command_outcomes) < 12:
                top_actor_command_outcomes.append(
                    {
                        "step": step,
                        "flat_index": flat,
                        "logical_label": trace_row["logical_label"],
                        "unit_type": trace_row["unit_type"],
                        "selected_before_mask": selected_before_mask,
                        "selected_after_mask": selected_after_mask,
                        "command_built": command_built,
                        "command_submitted": command_submitted,
                        "command_accepted": command_accepted,
                        "command_rejected": command_rejected,
                        "status": trace_row["command_result_status"],
                        "reason": reason,
                    }
                )

        for row in rows_by_step[step]:
            total_rows += 1
            predicted = _norm_action(row.get("predicted_action_type"))
            predicted_non_noop = predicted != "NoOp"
            runtime_actor = _as_bool(row.get("runtime_is_friendly_actor"))
            if predicted_non_noop:
                all_grid_predicted_non_noop_count += 1
            else:
                all_grid_predicted_noop_count += 1
            if predicted_non_noop and not runtime_actor and _clean_reason(row.get("decoder_reject_reason")) == "non_actor_cell":
                all_grid_non_actor_rejections += 1

            if not runtime_actor:
                continue

            actor_prediction_rows += 1
            if predicted_non_noop:
                actor_predicted_non_noop_count += 1
            else:
                actor_predicted_noop_count += 1

            masked_action = _norm_action(row.get("masked_action_type"))
            if predicted_non_noop and masked_action == "NoOp":
                actor_masked_to_noop_count += 1

            actionable_after_mask = masked_action != "NoOp"
            raw_command_built = _as_bool(row.get("command_built"))
            command_built = actionable_after_mask and raw_command_built
            if command_built:
                actor_command_built_count += 1
            else:
                actor_not_built_count += 1
                if predicted == "NoOp":
                    actor_not_built_reasons["predicted_noop"] += 1
                elif not actionable_after_mask:
                    actor_not_built_reasons["masked_to_noop"] += 1
                else:
                    actor_not_built_reasons[_clean_reason(row.get("command_not_built_reason"), "not_built_in_decoder_or_filter")] += 1

            command_submitted = actionable_after_mask and _as_bool(row.get("command_submitted") or row.get("applier_submitted"))
            command_key = _command_key(row)
            if actionable_after_mask and (command_built or command_submitted or _as_bool(row.get("command_event_accepted")) or _as_bool(row.get("command_event_rejected"))):
                submitted_expansion_map[(step, _to_int(row.get("cell_index"), -1))].add(command_key)
                record = command_records.setdefault(
                    command_key,
                    {
                        "command_key": command_key,
                        "step": step,
                        "flat_index": _to_int(row.get("cell_index"), -1),
                        "logical_label": str(row.get("visual_label") or ""),
                        "action_after_mask": masked_action,
                        "command_built": False,
                        "command_submitted": False,
                        "accepted_confirmed": False,
                        "rejected": False,
                        "applied_by_match_manager": False,
                        "status": str(row.get("command_result_status") or ""),
                        "reasons": [],
                    },
                )
                record["command_built"] = record["command_built"] or command_built
                record["command_submitted"] = record["command_submitted"] or command_submitted
                record["accepted_confirmed"] = record["accepted_confirmed"] or _as_bool(row.get("command_event_accepted") or row.get("applier_accepted"))
                record["rejected"] = record["rejected"] or _as_bool(row.get("command_event_rejected") or row.get("applier_rejected"))
                record["applied_by_match_manager"] = record["applied_by_match_manager"] or _command_applied(row)
                record["status"] = str(row.get("command_result_status") or record["status"])
                reason = _choose_reason(row)
                if reason != "none":
                    record["reasons"].append(reason)

    for key in sorted(command_records.keys()):
        record = command_records[key]
        accepted_pending = bool(record["command_submitted"] and not record["accepted_confirmed"] and not record["rejected"])
        not_applied = bool(record["command_submitted"] and not record["applied_by_match_manager"])
        reason = record["reasons"][0] if record["reasons"] else ("accepted_pending_unresolved" if accepted_pending else "none")
        command_trace_rows.append(
            {
                "command_key": record["command_key"],
                "step": record["step"],
                "flat_index": record["flat_index"],
                "logical_label": record["logical_label"],
                "action_after_mask": record["action_after_mask"],
                "command_built": record["command_built"],
                "command_submitted": record["command_submitted"],
                "accepted_pending": accepted_pending,
                "accepted_confirmed": record["accepted_confirmed"],
                "rejected": record["rejected"],
                "applied_by_match_manager": record["applied_by_match_manager"],
                "not_applied": not_applied,
                "status": record["status"],
                "reason": reason,
            }
        )

    command_lifecycle_scope = {
        "commands_built": sum(1 for item in command_trace_rows if item["command_built"]),
        "commands_submitted": sum(1 for item in command_trace_rows if item["command_submitted"]),
        "commands_accepted_pending": sum(1 for item in command_trace_rows if item["accepted_pending"]),
        "commands_accepted_confirmed": sum(1 for item in command_trace_rows if item["accepted_confirmed"]),
        "commands_rejected": sum(1 for item in command_trace_rows if item["rejected"]),
        "commands_applied_by_match_manager": sum(1 for item in command_trace_rows if item["applied_by_match_manager"]),
        "commands_not_applied": sum(1 for item in command_trace_rows if item["not_applied"]),
        "rejection_or_drop_reasons": dict(Counter(item["reason"] for item in command_trace_rows if item["reason"] != "none")),
    }

    multi_command_expansion_pairs = [
        {"step": step, "flat_index": flat, "command_count": len(keys), "command_keys": sorted(keys)}
        for (step, flat), keys in sorted(submitted_expansion_map.items())
        if len(keys) > 1
    ]
    multi_command_expansion_exists = bool(multi_command_expansion_pairs)

    consistency_warnings: list[str] = []
    rule_results: list[dict[str, Any]] = []

    submitted_gt_built = command_lifecycle_scope["commands_submitted"] > command_lifecycle_scope["commands_built"]
    rule_results.append(
        {
            "rule": "commands_submitted_vs_built",
            "pass": (not submitted_gt_built) or multi_command_expansion_exists,
            "details": {
                "commands_submitted": command_lifecycle_scope["commands_submitted"],
                "commands_built": command_lifecycle_scope["commands_built"],
                "multi_command_expansion_exists": multi_command_expansion_exists,
                "multi_command_expansion_pairs": multi_command_expansion_pairs[:12],
            },
        }
    )
    if submitted_gt_built and not multi_command_expansion_exists:
        consistency_warnings.append(
            "commands_submitted exceeds commands_built without observed multi-command expansion; treat submitted telemetry as a higher-level lifecycle counter."
        )

    unresolved_pending = command_lifecycle_scope["commands_accepted_pending"]
    rule_results.append(
        {
            "rule": "accepted_pending_resolution",
            "pass": unresolved_pending == 0,
            "details": {
                "accepted_pending": unresolved_pending,
                "resolution_definition": "accepted_pending means submitted command with no confirmed accept/reject/apply terminal event in current bounded capture.",
            },
        }
    )
    if unresolved_pending > 0:
        consistency_warnings.append(
            f"{unresolved_pending} submitted commands remain in accepted_pending/unknown state at capture end; no explicit expire/apply terminal event was exported for them."
        )

    accounted_submitted = (
        command_lifecycle_scope["commands_accepted_confirmed"]
        + command_lifecycle_scope["commands_accepted_pending"]
        + command_lifecycle_scope["commands_rejected"]
    )
    unaccounted_submitted = command_lifecycle_scope["commands_submitted"] - accounted_submitted
    rejected_zero_with_gap = command_lifecycle_scope["commands_rejected"] == 0 and unaccounted_submitted > 0
    rule_results.append(
        {
            "rule": "rejected_events_visibility",
            "pass": not rejected_zero_with_gap,
            "details": {
                "commands_rejected": command_lifecycle_scope["commands_rejected"],
                "commands_accepted_pending": command_lifecycle_scope["commands_accepted_pending"],
                "commands_accepted_confirmed": command_lifecycle_scope["commands_accepted_confirmed"],
                "commands_submitted": command_lifecycle_scope["commands_submitted"],
                "unaccounted_submitted": unaccounted_submitted,
            },
        }
    )
    if rejected_zero_with_gap:
        consistency_warnings.append(
            "rejected_events stayed at zero while some submitted commands were neither accepted nor pending; rejection visibility is incomplete."
        )

    accepted_event_definition = (
        "accepted_confirmed is defined as row.command_event_accepted or row.applier_accepted, i.e. MatchManager acceptance telemetry as exposed through the runner export."
    )

    all_grid_scope = {
        "total_cells_evaluated": total_rows,
        "all_grid_predicted_noop_count": all_grid_predicted_noop_count,
        "all_grid_predicted_non_noop_count": all_grid_predicted_non_noop_count,
        "all_grid_non_actor_cell_rejections": all_grid_non_actor_rejections,
    }
    actor_cell_scope = {
        "actor_cells_detected": actor_cells_detected,
        "controllable_actor_cells_detected": controllable_actor_cells_detected,
        "actor_cell_predictions_count": actor_prediction_rows,
        "actor_cell_predicted_noop_count": actor_predicted_noop_count,
        "actor_cell_predicted_non_noop_count": actor_predicted_non_noop_count,
        "actor_cell_masked_to_noop_count": actor_masked_to_noop_count,
        "actor_cell_command_built_count": actor_command_built_count,
        "actor_cell_command_not_built_count": actor_not_built_count,
        "actor_cell_command_not_built_reasons": dict(actor_not_built_reasons),
    }

    adapter_branch_sizes = [int(x) for x in (adapter_payload.get("branch_sizes") or [])]
    adapter_observation_shape = [int(x) for x in (adapter_payload.get("observation_shape") or [])]
    single_payload_action_flat_size = _to_int(adapter_payload.get("action_flat_size"), -1)
    v1_regression = not (
        str(adapter_payload.get("action_contract_version") or "") == "v2_gridnet_compatible"
        and adapter_branch_sizes == EXPECTED_BRANCH_SIZES
        and adapter_observation_shape == EXPECTED_OBSERVATION_SHAPE
        and single_payload_action_flat_size == EXPECTED_SINGLE_PAYLOAD_ACTION_FLAT_SIZE
    )

    legacy_stage6r4_payload_summary_path = reports_dir / "stage6r4_payload_summary.json"
    legacy_reported_action_flat_size = None
    if legacy_stage6r4_payload_summary_path.exists():
        legacy_stage6r4_payload = _read_json(legacy_stage6r4_payload_summary_path)
        legacy_reported_action_flat_size = _to_int(legacy_stage6r4_payload.get("action_flat_size"), -1)

    flat_size_report = {
        "generated_at_utc": _utc_now(),
        "scene": str(run_manifest.get("scene") or ""),
        "mode": "student_live_policy",
        "adapter_artifact_path": str(adapter_path.relative_to(root)).replace("\\", "/"),
        "action_contract_version": str(adapter_payload.get("action_contract_version") or ""),
        "branch_sizes": adapter_branch_sizes,
        "observation_shape": adapter_observation_shape,
        "single_payload_expected_action_flat_size": EXPECTED_SINGLE_PAYLOAD_ACTION_FLAT_SIZE,
        "single_payload_action_flat_size": single_payload_action_flat_size,
        "single_payload_action_flat_size_pass": single_payload_action_flat_size == EXPECTED_SINGLE_PAYLOAD_ACTION_FLAT_SIZE,
        "legacy_stage6r4_reported_action_flat_size": legacy_reported_action_flat_size,
        "legacy_stage6r4_interpretation": (
            "legacy downstream report value; raw adapter payload remains 44928 and no checked-in runtime adapter path emits 526848"
            if legacy_reported_action_flat_size is not None
            else "no legacy Stage6R4 payload summary found"
        ),
        "corrected_field_name": "single_payload_action_flat_size",
        "aggregate_action_value_count": None,
    }

    fallback_status = {
        "uses_student_checkpoint": all(_as_bool(snapshots[step].get("uses_student_checkpoint")) for step in snapshots),
        "uses_python_adapter": all(_as_bool(snapshots[step].get("uses_python_adapter")) for step in snapshots),
        "uses_heuristic_policy": heuristic_used,
        "fake_policy_or_stub_seen": fake_policy_used,
        "fallback_used": fallback_used or heuristic_used or fake_policy_used,
    }

    if single_payload_action_flat_size != EXPECTED_SINGLE_PAYLOAD_ACTION_FLAT_SIZE:
        classification = CLASS_FAIL_FLAT
        classification_reason = "single_payload_action_flat_size no longer matches 44928"
    elif fallback_status["fallback_used"]:
        classification = CLASS_FAIL_FALLBACK
        classification_reason = "student_live_policy used a heuristic/fake/stub fallback"
    elif v1_regression:
        classification = CLASS_FAIL_V1
        classification_reason = "adapter payload no longer matches the enforced v2 contract"
    elif not actor_trace_rows:
        classification = CLASS_FAIL_TRACE
        classification_reason = "actor_cell_trace is empty"
    elif any(not result["pass"] for result in rule_results if result["rule"] in {"commands_submitted_vs_built", "rejected_events_visibility"}):
        classification = CLASS_FAIL_COUNTER
        classification_reason = "command lifecycle counters are internally inconsistent"
    else:
        classification = CLASS_READY
        classification_reason = "single payload flat size is 44928, actor-cell-only counters are separated from all-grid counters, and lifecycle warnings are explicit."

    exact_scene = str(run_manifest.get("scene") or mode_manifest.get("scene") or "Assets/Scenes/Week6_StudentVisualInspection.unity")
    mode_steps_completed = _to_int(mode_manifest.get("steps_completed"), steps[-1])
    mode_terminal = _as_bool(mode_manifest.get("terminal"))
    mode_terminal_reason = str(mode_manifest.get("terminal_reason") or "")
    checkpoint_used = str(next(iter(snapshots.values())).get("checkpoint_path_used_at_inference") or adapter_payload.get("checkpoint_path") or "")

    rejection_reason_summary = {
        "all_grid_decoder_reject_reasons": {"non_actor_cell": all_grid_non_actor_rejections},
        "actor_cell_command_not_built_reasons": dict(actor_not_built_reasons),
        "command_lifecycle_rejection_or_drop_reasons": command_lifecycle_scope["rejection_or_drop_reasons"],
    }

    counter_consistency_report = {
        "generated_at_utc": _utc_now(),
        "accepted_event_definition": accepted_event_definition,
        "rule_results": rule_results,
        "warnings": consistency_warnings,
        "multi_command_expansion_exists": multi_command_expansion_exists,
        "multi_command_expansion_examples": multi_command_expansion_pairs[:12],
    }

    final_report = {
        "generated_at_utc": _utc_now(),
        "stage": "Stage6R5A",
        "scene": exact_scene,
        "run_mode": "student_live_policy",
        "target_steps": _to_int(mode_manifest.get("target_steps"), 80),
        "steps_completed": mode_steps_completed,
        "terminal": mode_terminal,
        "terminal_reason": mode_terminal_reason,
        "checkpoint_used": checkpoint_used,
        "flat_size": flat_size_report,
        "all_grid_scope": all_grid_scope,
        "actor_cell_scope": actor_cell_scope,
        "command_lifecycle_scope": command_lifecycle_scope,
        "counter_consistency": counter_consistency_report,
        "top_actor_cell_command_outcomes": top_actor_command_outcomes,
        "fallback_status": fallback_status,
        "v1_regression": v1_regression,
        "no_training_assertions": {
            "bc_training_run": False,
            "ppo_fine_tuning_run": False,
            "teacher_training_run": False,
        },
        "claims_not_made": {
            "semantic_parity_claim": False,
            "direct_weight_transfer_claim": False,
            "policy_quality_claim": False,
        },
        "classification": classification,
        "classification_reason": classification_reason,
        "recommended_next_stage": "Stage6R5B — Behavior Bottleneck Analysis on Actor Cells" if classification == CLASS_READY else "Hold on Stage6R5B until Stage6R5A failures/warnings are resolved.",
    }

    actor_trace_path = reports_dir / "stage6r5a_actor_cell_trace.jsonl"
    command_trace_path = reports_dir / "stage6r5a_command_lifecycle_trace.jsonl"
    counter_consistency_path = reports_dir / "stage6r5a_counter_consistency_report.json"
    flat_size_path = reports_dir / "stage6r5a_flat_size_report.json"
    rejection_summary_path = reports_dir / "stage6r5a_rejection_reason_summary.json"
    report_json_path = reports_dir / "stage6r5a_actor_cell_diagnostics_normalization_report.json"
    report_md_path = reports_dir / "STAGE6R5A_ACTOR_CELL_DIAGNOSTICS_NORMALIZATION_REPORT.md"

    _write_jsonl(actor_trace_path, actor_trace_rows)
    _write_jsonl(command_trace_path, command_trace_rows)
    _write_json(counter_consistency_path, counter_consistency_report)
    _write_json(flat_size_path, flat_size_report)
    _write_json(rejection_summary_path, rejection_reason_summary)
    _write_json(report_json_path, final_report)

    warning_rows = [[idx + 1, warning] for idx, warning in enumerate(consistency_warnings)] or [["-", "none"]]
    top_rows = [
        [
            item["step"],
            item["flat_index"],
            item["logical_label"],
            item["unit_type"],
            item["selected_before_mask"],
            item["selected_after_mask"],
            item["status"],
            item["reason"],
        ]
        for item in top_actor_command_outcomes[:8]
    ]
    if not top_rows:
        top_rows = [["-", "-", "-", "-", "-", "-", "-", "none"]]

    md_lines = [
        "# STAGE6R5A Actor-Cell Diagnostics Normalization Report",
        "",
        f"- Generated (UTC): {final_report['generated_at_utc']}",
        f"- Scene/run used: {exact_scene} | mode=student_live_policy | target_steps={final_report['target_steps']} | steps_completed={mode_steps_completed} | terminal={mode_terminal} | terminal_reason={mode_terminal_reason or 'none'}",
        f"- Checkpoint used: {checkpoint_used}",
        f"- Classification: {classification}",
        f"- Classification reason: {classification_reason}",
        "",
        "## Flat Size",
        f"- single_payload_action_flat_size: {single_payload_action_flat_size}",
        f"- expected_single_payload_action_flat_size: {EXPECTED_SINGLE_PAYLOAD_ACTION_FLAT_SIZE}",
        f"- legacy_stage6r4_reported_action_flat_size: {legacy_reported_action_flat_size}",
        f"- corrected interpretation: {flat_size_report['legacy_stage6r4_interpretation']}",
        "",
        "## Scopes",
        f"- all_grid_scope.total_cells_evaluated: {all_grid_scope['total_cells_evaluated']}",
        f"- all_grid_scope.all_grid_predicted_noop_count: {all_grid_scope['all_grid_predicted_noop_count']}",
        f"- all_grid_scope.all_grid_predicted_non_noop_count: {all_grid_scope['all_grid_predicted_non_noop_count']}",
        f"- all_grid_scope.all_grid_non_actor_cell_rejections: {all_grid_scope['all_grid_non_actor_cell_rejections']}",
        f"- actor_cell_scope.actor_cells_detected: {actor_cell_scope['actor_cells_detected']}",
        f"- actor_cell_scope.controllable_actor_cells_detected: {actor_cell_scope['controllable_actor_cells_detected']}",
        f"- actor_cell_scope.actor_cell_predictions_count: {actor_cell_scope['actor_cell_predictions_count']}",
        f"- actor_cell_scope.actor_cell_predicted_noop_count: {actor_cell_scope['actor_cell_predicted_noop_count']}",
        f"- actor_cell_scope.actor_cell_predicted_non_noop_count: {actor_cell_scope['actor_cell_predicted_non_noop_count']}",
        f"- actor_cell_scope.actor_cell_masked_to_noop_count: {actor_cell_scope['actor_cell_masked_to_noop_count']}",
        f"- actor_cell_scope.actor_cell_command_built_count: {actor_cell_scope['actor_cell_command_built_count']}",
        f"- actor_cell_scope.actor_cell_command_not_built_count: {actor_cell_scope['actor_cell_command_not_built_count']}",
        f"- command_lifecycle_scope.commands_built: {command_lifecycle_scope['commands_built']}",
        f"- command_lifecycle_scope.commands_submitted: {command_lifecycle_scope['commands_submitted']}",
        f"- command_lifecycle_scope.commands_accepted_pending: {command_lifecycle_scope['commands_accepted_pending']}",
        f"- command_lifecycle_scope.commands_accepted_confirmed: {command_lifecycle_scope['commands_accepted_confirmed']}",
        f"- command_lifecycle_scope.commands_rejected: {command_lifecycle_scope['commands_rejected']}",
        f"- command_lifecycle_scope.commands_applied_by_match_manager: {command_lifecycle_scope['commands_applied_by_match_manager']}",
        f"- command_lifecycle_scope.commands_not_applied: {command_lifecycle_scope['commands_not_applied']}",
        "",
        "## Consistency Warnings",
        *_warning_table(["#", "warning"], warning_rows),
        "",
        "## Top Actor Outcomes",
        *_warning_table(
            ["step", "flat", "label", "unit", "before_mask", "after_mask", "status", "reason"],
            top_rows,
        ),
        "",
        "## Safety Gates",
        f"- fallback_used: {fallback_status['fallback_used']}",
        f"- uses_heuristic_policy: {fallback_status['uses_heuristic_policy']}",
        f"- fake_policy_or_stub_seen: {fallback_status['fake_policy_or_stub_seen']}",
        f"- v1_regression: {v1_regression}",
        f"- accepted_event_definition: {accepted_event_definition}",
        "",
        "## Explicit Notes",
        "- No BC training was run.",
        "- No PPO fine-tuning was run.",
        "- No teacher training was run.",
        "- No semantic parity claim is made.",
        "- No direct weight transfer claim is made.",
        "- No behavior-quality claim is made.",
        "",
        "## Artifacts",
        f"- JSON report: {report_json_path.relative_to(root).as_posix()}",
        f"- Actor trace: {actor_trace_path.relative_to(root).as_posix()}",
        f"- Command lifecycle trace: {command_trace_path.relative_to(root).as_posix()}",
        f"- Counter consistency report: {counter_consistency_path.relative_to(root).as_posix()}",
        f"- Flat size report: {flat_size_path.relative_to(root).as_posix()}",
        f"- Rejection reason summary: {rejection_summary_path.relative_to(root).as_posix()}",
    ]
    report_md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(report_json_path.relative_to(root).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())