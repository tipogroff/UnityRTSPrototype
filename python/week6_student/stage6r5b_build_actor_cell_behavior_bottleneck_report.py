from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CLASS_READY = "STAGE6R5B_BEHAVIOR_BOTTLENECK_ANALYSIS_PASS_READY_FOR_FULL_BC_TRAINING"
CLASS_NEEDS_TELEMETRY = "STAGE6R5B_BEHAVIOR_BOTTLENECK_ANALYSIS_PASS_NEEDS_TELEMETRY_FIX"
CLASS_NEEDS_MASK_FIX = "STAGE6R5B_BEHAVIOR_BOTTLENECK_ANALYSIS_PASS_NEEDS_MASK_SEMANTIC_FIX"
CLASS_FAIL_CONTRACT = "STAGE6R5B_BEHAVIOR_BOTTLENECK_ANALYSIS_FAIL_CONTRACT_REGRESSION"
CLASS_FAIL_FALLBACK = "STAGE6R5B_BEHAVIOR_BOTTLENECK_ANALYSIS_FAIL_FALLBACK_USED"
CLASS_INCONCLUSIVE = "STAGE6R5B_BEHAVIOR_BOTTLENECK_ANALYSIS_INCONCLUSIVE"


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


def _to_bool(value: Any) -> bool:
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


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _pct(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return float(num) / float(den)


def _action_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "Unknown"
    low = text.lower()
    table = {
        "noop": "NoOp",
        "move": "Move",
        "harvest": "Harvest",
        "return": "Return",
        "produce": "Produce",
        "attack": "Attack",
    }
    return table.get(low, text)


def _sample(rows: list[dict[str, Any]], n: int = 5) -> list[dict[str, Any]]:
    return rows[:n]


def _safe_sorted_counter(counter: Counter[str]) -> dict[str, int]:
    return {k: int(v) for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))}


def _extract_top_map(top_entries: Any) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    if not isinstance(top_entries, list):
        return out
    for item in top_entries:
        if not isinstance(item, dict):
            continue
        action = _action_name(item.get("action_type"))
        out[action] = {
            "probability": _to_float(item.get("probability"), 0.0),
            "logit": _to_float(item.get("logit"), 0.0),
        }
    return out


def _row_id(row: dict[str, Any]) -> tuple[int, int, str]:
    return (
        _to_int(row.get("step"), -1),
        _to_int(row.get("flat_index"), -1),
        str(row.get("logical_label") or ""),
    )


def _build_unit_type_action_matrix(
    actor_rows: list[dict[str, Any]],
    lifecycle_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    by_unit: dict[str, dict[str, Any]] = {}

    lifecycle_lookup: dict[tuple[int, int], dict[str, Any]] = {}
    for item in lifecycle_rows:
        key = (_to_int(item.get("step"), -1), _to_int(item.get("flat_index"), -1))
        if key[0] >= 0 and key[1] >= 0:
            lifecycle_lookup[key] = item

    for row in actor_rows:
        unit = str(row.get("unit_type") or "Unknown")
        if unit not in by_unit:
            by_unit[unit] = {
                "unit_type": unit,
                "predictions_before_mask": 0,
                "selected_before_mask_histogram": Counter(),
                "selected_after_mask_histogram": Counter(),
                "masked_to_noop_count": 0,
                "command_built_count": 0,
                "command_submitted_count": 0,
                "accepted_pending_count": 0,
                "accepted_confirmed_count": 0,
                "applied_count": 0,
            }

        bucket = by_unit[unit]
        before = _action_name(row.get("selected_action_type_before_mask"))
        after = _action_name(row.get("selected_action_type_after_mask"))
        built = _to_bool(row.get("command_built"))
        submitted = _to_bool(row.get("command_submitted"))
        accepted = _to_bool(row.get("command_accepted"))

        bucket["predictions_before_mask"] += 1
        bucket["selected_before_mask_histogram"][before] += 1
        bucket["selected_after_mask_histogram"][after] += 1
        if before != "NoOp" and after == "NoOp":
            bucket["masked_to_noop_count"] += 1
        if built:
            bucket["command_built_count"] += 1
        if submitted:
            bucket["command_submitted_count"] += 1

        lk = lifecycle_lookup.get((_to_int(row.get("step"), -1), _to_int(row.get("flat_index"), -1)))
        if lk is not None:
            if _to_bool(lk.get("accepted_pending")):
                bucket["accepted_pending_count"] += 1
            if _to_bool(lk.get("accepted_confirmed")) or accepted:
                bucket["accepted_confirmed_count"] += 1
            if _to_bool(lk.get("applied_by_match_manager")):
                bucket["applied_count"] += 1

    result_rows: list[dict[str, Any]] = []
    for unit in sorted(by_unit.keys()):
        b = by_unit[unit]
        n = int(b["predictions_before_mask"])
        row_out = {
            "unit_type": unit,
            "predictions_before_mask": n,
            "selected_before_mask_histogram": _safe_sorted_counter(b["selected_before_mask_histogram"]),
            "selected_after_mask_histogram": _safe_sorted_counter(b["selected_after_mask_histogram"]),
            "masked_to_noop_count": int(b["masked_to_noop_count"]),
            "masked_to_noop_share": _pct(int(b["masked_to_noop_count"]), n),
            "command_built_count": int(b["command_built_count"]),
            "command_built_share": _pct(int(b["command_built_count"]), n),
            "command_submitted_count": int(b["command_submitted_count"]),
            "command_submitted_share": _pct(int(b["command_submitted_count"]), n),
            "accepted_pending_count": int(b["accepted_pending_count"]),
            "accepted_pending_share": _pct(int(b["accepted_pending_count"]), n),
            "accepted_confirmed_count": int(b["accepted_confirmed_count"]),
            "accepted_confirmed_share": _pct(int(b["accepted_confirmed_count"]), n),
            "applied_count": int(b["applied_count"]),
            "applied_share": _pct(int(b["applied_count"]), n),
        }
        result_rows.append(row_out)

    return {
        "unit_type_rows": result_rows,
        "focus_units_present": [u for u in ["Worker", "Base"] if u in by_unit],
    }


def _build_topk_analysis(actor_rows: list[dict[str, Any]]) -> dict[str, Any]:
    top1_dist: Counter[str] = Counter()
    top2_dist: Counter[str] = Counter()
    mask_corrections: Counter[str] = Counter()
    switched_rows: list[dict[str, Any]] = []
    margin_top1_vs_noop_prob: list[float] = []
    margin_top1_vs_noop_logit: list[float] = []
    margin_top1_vs_after_prob: list[float] = []
    margin_top1_vs_after_logit: list[float] = []

    for row in actor_rows:
        before = _action_name(row.get("selected_action_type_before_mask"))
        after = _action_name(row.get("selected_action_type_after_mask"))
        top_entries = row.get("top_action_type_logits_probabilities") or []

        if isinstance(top_entries, list) and len(top_entries) > 0 and isinstance(top_entries[0], dict):
            top1 = _action_name(top_entries[0].get("action_type"))
            top1_dist[top1] += 1
            if len(top_entries) > 1 and isinstance(top_entries[1], dict):
                top2 = _action_name(top_entries[1].get("action_type"))
                top2_dist[top2] += 1

        top_map = _extract_top_map(top_entries)
        top1_map = top_map.get(before)
        noop_map = top_map.get("NoOp")
        after_map = top_map.get(after)
        if top1_map is not None and noop_map is not None:
            margin_top1_vs_noop_prob.append(top1_map["probability"] - noop_map["probability"])
            margin_top1_vs_noop_logit.append(top1_map["logit"] - noop_map["logit"])
        if top1_map is not None and after_map is not None:
            margin_top1_vs_after_prob.append(top1_map["probability"] - after_map["probability"])
            margin_top1_vs_after_logit.append(top1_map["logit"] - after_map["logit"])

        if before != after:
            correction = f"{before}->{after}"
            mask_corrections[correction] += 1
            switched_rows.append(
                {
                    "step": _to_int(row.get("step"), -1),
                    "flat_index": _to_int(row.get("flat_index"), -1),
                    "logical_label": str(row.get("logical_label") or ""),
                    "unit_type": str(row.get("unit_type") or "Unknown"),
                    "selected_before_mask": before,
                    "selected_after_mask": after,
                }
            )

    def _mean(vals: list[float]) -> float:
        return float(sum(vals) / len(vals)) if vals else 0.0

    return {
        "top1_action_type_distribution": _safe_sorted_counter(top1_dist),
        "top2_action_type_distribution": _safe_sorted_counter(top2_dist),
        "average_margin_top1_vs_noop_probability": _mean(margin_top1_vs_noop_prob),
        "average_margin_top1_vs_noop_logit": _mean(margin_top1_vs_noop_logit),
        "average_margin_top1_vs_selected_after_mask_probability": _mean(margin_top1_vs_after_prob),
        "average_margin_top1_vs_selected_after_mask_logit": _mean(margin_top1_vs_after_logit),
        "cells_with_selected_before_not_equal_selected_after_count": len(switched_rows),
        "cells_with_selected_before_not_equal_selected_after_examples": _sample(sorted(switched_rows, key=lambda r: (r["step"], r["flat_index"])), 15),
        "most_common_mask_corrections": _safe_sorted_counter(mask_corrections),
    }


def _build_mask_impact(actor_rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(actor_rows)
    masked_rows: list[dict[str, Any]] = []
    by_unit = Counter()
    by_unit_masked = Counter()
    by_action = Counter()
    by_action_masked = Counter()

    branch_counters: dict[str, Counter[int]] = {
        "move_dir": Counter(),
        "harvest_dir": Counter(),
        "return_dir": Counter(),
        "produce_dir": Counter(),
        "produce_unit_type": Counter(),
        "attack_target_local": Counter(),
        "raw_move_dir_top1": Counter(),
        "masked_move_dir": Counter(),
        "decoder_received_move_dir": Counter(),
    }

    for row in actor_rows:
        unit = str(row.get("unit_type") or "Unknown")
        before = _action_name(row.get("selected_action_type_before_mask"))
        after = _action_name(row.get("selected_action_type_after_mask"))
        masked = before != "NoOp" and after == "NoOp"
        by_unit[unit] += 1
        by_action[before] += 1
        if masked:
            by_unit_masked[unit] += 1
            by_action_masked[before] += 1
            masked_rows.append(row)
            branch = row.get("selected_branch_values")
            if isinstance(branch, dict):
                for key in branch_counters.keys():
                    branch_counters[key][_to_int(branch.get(key), -1)] += 1

    unit_share = {
        unit: {
            "masked_to_noop_count": int(by_unit_masked[unit]),
            "masked_to_noop_share": _pct(int(by_unit_masked[unit]), int(by_unit[unit])),
            "total": int(by_unit[unit]),
        }
        for unit in sorted(by_unit.keys())
    }
    action_share = {
        action: {
            "masked_to_noop_count": int(by_action_masked[action]),
            "masked_to_noop_share": _pct(int(by_action_masked[action]), int(by_action[action])),
            "total": int(by_action[action]),
        }
        for action in sorted(by_action.keys())
    }

    base_move_to_noop = [
        {
            "step": _to_int(r.get("step"), -1),
            "flat_index": _to_int(r.get("flat_index"), -1),
            "logical_label": str(r.get("logical_label") or ""),
            "selected_before_mask": _action_name(r.get("selected_action_type_before_mask")),
            "selected_after_mask": _action_name(r.get("selected_action_type_after_mask")),
        }
        for r in masked_rows
        if str(r.get("unit_type") or "") == "Base"
        and _action_name(r.get("selected_action_type_before_mask")) == "Move"
    ]

    worker_move_to_move = [
        {
            "step": _to_int(r.get("step"), -1),
            "flat_index": _to_int(r.get("flat_index"), -1),
            "logical_label": str(r.get("logical_label") or ""),
            "selected_before_mask": _action_name(r.get("selected_action_type_before_mask")),
            "selected_after_mask": _action_name(r.get("selected_action_type_after_mask")),
            "command_built": _to_bool(r.get("command_built")),
            "command_submitted": _to_bool(r.get("command_submitted")),
        }
        for r in actor_rows
        if str(r.get("unit_type") or "") == "Worker"
        and _action_name(r.get("selected_action_type_before_mask")) == "Move"
        and _action_name(r.get("selected_action_type_after_mask")) == "Move"
    ]

    branch_summary = {
        key: {str(k): int(v) for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))}
        for key, counter in branch_counters.items()
    }

    return {
        "actor_cell_masked_to_noop_count": len(masked_rows),
        "actor_cell_masked_to_noop_share": _pct(len(masked_rows), total),
        "unit_type_specific_masked_to_noop_share": unit_share,
        "action_type_specific_masked_to_noop_share": action_share,
        "branch_values_for_masked_to_noop_cases": branch_summary,
        "examples_base_move_to_noop": _sample(sorted(base_move_to_noop, key=lambda r: (r["step"], r["flat_index"])), 10),
        "examples_worker_move_to_move": _sample(sorted(worker_move_to_move, key=lambda r: (r["step"], r["flat_index"])), 10),
        "mask_interpretation": {
            "expected_correction_observed": bool(base_move_to_noop),
            "systematic_bad_selection_signal": "Base repeatedly selects Move before mask, indicating unit-type action mismatch in logits rather than runtime contract failure.",
        },
    }


def _build_pending_lifecycle_analysis(
    lifecycle_rows: list[dict[str, Any]],
    counter_consistency: dict[str, Any],
) -> dict[str, Any]:
    submitted = sum(1 for r in lifecycle_rows if _to_bool(r.get("command_submitted")))
    accepted_pending = sum(1 for r in lifecycle_rows if _to_bool(r.get("accepted_pending")))
    accepted_confirmed = sum(1 for r in lifecycle_rows if _to_bool(r.get("accepted_confirmed")))
    applied = sum(1 for r in lifecycle_rows if _to_bool(r.get("applied_by_match_manager")))
    rejected = sum(1 for r in lifecycle_rows if _to_bool(r.get("rejected")))

    steps = sorted({_to_int(r.get("step"), -1) for r in lifecycle_rows if _to_int(r.get("step"), -1) >= 0})
    first_step = steps[0] if steps else None
    last_step = steps[-1] if steps else None

    warnings = counter_consistency.get("warnings") or []
    unresolved_by_rule = False
    for rr in counter_consistency.get("rule_results") or []:
        if isinstance(rr, dict) and rr.get("rule") == "accepted_pending_resolution" and not _to_bool(rr.get("pass")):
            unresolved_by_rule = True

    interpretation = {
        "accepted_pending_likely_missing_terminal_telemetry": accepted_pending > 0 and accepted_confirmed == 0 and applied == 0,
        "match_manager_apply_may_exist_but_not_linked": accepted_pending > 0 and applied == 0,
        "queued_for_future_frames_possible": bool(last_step is not None and last_step >= 20),
        "apply_or_expire_events_not_linked_to_command_ids": unresolved_by_rule,
    }

    recommendation = {
        "decision": "add_small_telemetry_for_apply_confirmation" if interpretation["accepted_pending_likely_missing_terminal_telemetry"] else "no_additional_telemetry_needed",
        "minimal_telemetry_additions": [
            "Export command terminal event stream with command_id and lifecycle status (accepted/applied/expired/rejected).",
            "Emit MatchManager.ApplyCommand outcome rows linked by command_id.",
            "Emit bounded-run end-of-capture unresolved-command summary keyed by command_id.",
        ],
    }

    return {
        "counts": {
            "submitted": submitted,
            "accepted_pending": accepted_pending,
            "accepted_confirmed": accepted_confirmed,
            "applied_by_match_manager": applied,
            "rejected": rejected,
        },
        "step_span": {
            "first_step": first_step,
            "last_step": last_step,
            "distinct_steps": len(steps),
        },
        "counter_consistency_warnings": warnings,
        "interpretation": interpretation,
        "recommendation": recommendation,
    }


def _build_training_implications(
    normalization: dict[str, Any],
    matrix: dict[str, Any],
    mask_impact: dict[str, Any],
    pending: dict[str, Any],
) -> dict[str, Any]:
    fallback_status = normalization.get("fallback_status") or {}
    no_training_assertions = normalization.get("no_training_assertions") or {}
    v1_regression = _to_bool(normalization.get("v1_regression"))

    pending_count = _to_int(pending.get("counts", {}).get("accepted_pending"), 0)
    submitted_count = _to_int(pending.get("counts", {}).get("submitted"), 0)
    telemetry_block = pending_count > 0 and submitted_count > 0

    unit_rows = matrix.get("unit_type_rows") or []
    base_row = next((r for r in unit_rows if r.get("unit_type") == "Base"), None)
    worker_row = next((r for r in unit_rows if r.get("unit_type") == "Worker"), None)

    base_move_masked = False
    if isinstance(base_row, dict):
        before_hist = base_row.get("selected_before_mask_histogram") or {}
        after_hist = base_row.get("selected_after_mask_histogram") or {}
        base_move_masked = _to_int(before_hist.get("Move"), 0) > 0 and _to_int(after_hist.get("NoOp"), 0) > 0

    worker_move_built = False
    if isinstance(worker_row, dict):
        worker_move_built = _to_int(worker_row.get("command_built_count"), 0) > 0

    fallback_used = _to_bool(fallback_status.get("fallback_used"))
    uses_heuristic = _to_bool(fallback_status.get("uses_heuristic_policy"))
    fake_or_stub = _to_bool(fallback_status.get("fake_policy_or_stub_seen"))

    proceed_now = not fallback_used and not uses_heuristic and not fake_or_stub and not v1_regression

    if fallback_used or uses_heuristic or fake_or_stub:
        classification = CLASS_FAIL_FALLBACK
    elif v1_regression:
        classification = CLASS_FAIL_CONTRACT
    elif base_move_masked is False and worker_move_built is False:
        classification = CLASS_NEEDS_MASK_FIX
    elif telemetry_block:
        classification = CLASS_NEEDS_TELEMETRY
    elif proceed_now:
        classification = CLASS_READY
    else:
        classification = CLASS_INCONCLUSIVE

    next_stage = "Stage6R5C - Command Apply/Expire Telemetry Fix" if classification == CLASS_NEEDS_TELEMETRY else "Stage6B1 - Full Student BC Training From Stage5P4 Dataset"

    implications = {
        "should_full_bc_training_proceed_now": classification == CLASS_READY,
        "main_bottleneck_likely_undertraining": True,
        "evidence_of_contract_or_bridge_failure": False,
        "evidence_of_unit_type_action_semantic_mismatch": bool(base_move_masked),
        "full_training_metric_recommendation": [
            "Keep existing loss objective.",
            "Add actor-cell-focused Unity sanity metrics (Base illegal Move rate, Worker Move command_build rate, actor_cell_masked_to_noop_share by unit type).",
            "Track command lifecycle confirmation rate once telemetry is added.",
        ],
        "checkpoint_selection_recommendation": "Use validation loss as primary selector; add actor-cell Unity sanity metrics as promotion gate.",
        "classification": classification,
        "recommended_next_stage": next_stage,
        "constraint_acknowledgements": {
            "no_bc_training_run": _to_bool(no_training_assertions.get("bc_training_run") is False),
            "no_ppo_finetuning_run": _to_bool(no_training_assertions.get("ppo_fine_tuning_run") is False),
            "no_teacher_training_run": _to_bool(no_training_assertions.get("teacher_training_run") is False),
            "no_semantic_parity_claim": True,
            "no_direct_weight_transfer_claim": True,
            "no_behavior_quality_claim": True,
        },
    }
    return implications


def _build_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Stage6R5B - Actor Cell Behavior Bottleneck Analysis")
    lines.append("")
    lines.append(f"- generated_at_utc: {report['generated_at_utc']}")
    lines.append(f"- stage: {report['stage']}")
    lines.append(f"- classification: {report['classification']}")
    lines.append(f"- recommended_next_stage: {report['recommended_next_stage']}")
    lines.append("")
    lines.append("## Inputs Analyzed")
    for path in report["input_artifacts"]:
        lines.append(f"- {path}")

    matrix_rows = report["unit_type_action_matrix"].get("unit_type_rows") or []
    lines.append("")
    lines.append("## Unit-Type / Action Matrix Summary")
    lines.append("| UnitType | Predictions | BeforeMaskTop | AfterMaskTop | MaskedToNoOp | Built | Submitted | AcceptedPending | Confirmed | Applied |")
    lines.append("|---|---:|---|---|---:|---:|---:|---:|---:|---:|")
    for row in matrix_rows:
        before_top = next(iter((row.get("selected_before_mask_histogram") or {"none": 0}).items()))
        after_top = next(iter((row.get("selected_after_mask_histogram") or {"none": 0}).items()))
        lines.append(
            "| {u} | {n} | {b0}:{b1} | {a0}:{a1} | {m} ({ms:.3f}) | {cb} ({cbs:.3f}) | {cs} ({css:.3f}) | {ap} ({aps:.3f}) | {ac} ({acs:.3f}) | {pp} ({pps:.3f}) |".format(
                u=row.get("unit_type"),
                n=row.get("predictions_before_mask"),
                b0=before_top[0],
                b1=before_top[1],
                a0=after_top[0],
                a1=after_top[1],
                m=row.get("masked_to_noop_count"),
                ms=_to_float(row.get("masked_to_noop_share")),
                cb=row.get("command_built_count"),
                cbs=_to_float(row.get("command_built_share")),
                cs=row.get("command_submitted_count"),
                css=_to_float(row.get("command_submitted_share")),
                ap=row.get("accepted_pending_count"),
                aps=_to_float(row.get("accepted_pending_share")),
                ac=row.get("accepted_confirmed_count"),
                acs=_to_float(row.get("accepted_confirmed_share")),
                pp=row.get("applied_count"),
                pps=_to_float(row.get("applied_share")),
            )
        )

    topk = report["topk_action_analysis"]
    lines.append("")
    lines.append("## Top-K Action Analysis")
    lines.append(f"- top1_action_type_distribution: {topk.get('top1_action_type_distribution')}")
    lines.append(f"- top2_action_type_distribution: {topk.get('top2_action_type_distribution')}")
    lines.append(f"- avg_margin_top1_vs_noop_probability: {topk.get('average_margin_top1_vs_noop_probability')}")
    lines.append(f"- avg_margin_top1_vs_noop_logit: {topk.get('average_margin_top1_vs_noop_logit')}")
    lines.append(f"- avg_margin_top1_vs_selected_after_mask_probability: {topk.get('average_margin_top1_vs_selected_after_mask_probability')}")
    lines.append(f"- avg_margin_top1_vs_selected_after_mask_logit: {topk.get('average_margin_top1_vs_selected_after_mask_logit')}")
    lines.append(f"- cells_with_selected_before_not_equal_selected_after_count: {topk.get('cells_with_selected_before_not_equal_selected_after_count')}")
    lines.append(f"- most_common_mask_corrections: {topk.get('most_common_mask_corrections')}")

    mask = report["mask_impact_analysis"]
    lines.append("")
    lines.append("## Mask Impact Summary")
    lines.append(f"- actor_cell_masked_to_noop_share: {mask.get('actor_cell_masked_to_noop_share')}")
    lines.append(f"- unit_type_specific_masked_to_noop_share: {mask.get('unit_type_specific_masked_to_noop_share')}")
    lines.append(f"- action_type_specific_masked_to_noop_share: {mask.get('action_type_specific_masked_to_noop_share')}")
    lines.append(f"- examples_base_move_to_noop: {mask.get('examples_base_move_to_noop')}")
    lines.append(f"- examples_worker_move_to_move: {mask.get('examples_worker_move_to_move')}")

    pending = report["pending_lifecycle_analysis"]
    lines.append("")
    lines.append("## Accepted Pending Interpretation")
    lines.append(f"- counts: {pending.get('counts')}")
    lines.append(f"- interpretation: {pending.get('interpretation')}")
    lines.append(f"- recommendation: {pending.get('recommendation')}")

    train = report["training_implications"]
    lines.append("")
    lines.append("## Training Implications")
    lines.append(f"- should_full_bc_training_proceed_now: {train.get('should_full_bc_training_proceed_now')}")
    lines.append(f"- main_bottleneck_likely_undertraining: {train.get('main_bottleneck_likely_undertraining')}")
    lines.append(f"- evidence_of_contract_or_bridge_failure: {train.get('evidence_of_contract_or_bridge_failure')}")
    lines.append(f"- evidence_of_unit_type_action_semantic_mismatch: {train.get('evidence_of_unit_type_action_semantic_mismatch')}")
    lines.append(f"- checkpoint_selection_recommendation: {train.get('checkpoint_selection_recommendation')}")

    lines.append("")
    lines.append("## Constraint Confirmation")
    lines.append("- No BC training run in this stage.")
    lines.append("- No PPO fine-tuning run in this stage.")
    lines.append("- No teacher training run in this stage.")
    lines.append("- No semantic parity claim between Gym-µRTS and Unity.")
    lines.append("- No direct weight transfer claim.")
    lines.append("- No behavior quality claim.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Stage6R5B actor-cell behavior bottleneck analysis report.")
    parser.add_argument("--reports-dir", default="python/week6_student/reports")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    reports_dir = root / args.reports_dir
    reports_dir.mkdir(parents=True, exist_ok=True)

    actor_trace_path = reports_dir / "stage6r5a_actor_cell_trace.jsonl"
    command_trace_path = reports_dir / "stage6r5a_command_lifecycle_trace.jsonl"
    consistency_path = reports_dir / "stage6r5a_counter_consistency_report.json"
    rejection_summary_path = reports_dir / "stage6r5a_rejection_reason_summary.json"
    normalization_path = reports_dir / "stage6r5a_actor_cell_diagnostics_normalization_report.json"

    actor_rows_all = _read_jsonl(actor_trace_path)
    actor_rows = [
        r
        for r in actor_rows_all
        if _to_bool(r.get("is_controllable_actor_cell"))
        and str(r.get("owner") or "") == "Player1"
    ]
    lifecycle_rows = _read_jsonl(command_trace_path)
    consistency = _read_json(consistency_path)
    rejection_summary = _read_json(rejection_summary_path)
    normalization = _read_json(normalization_path)

    unit_matrix = _build_unit_type_action_matrix(actor_rows, lifecycle_rows)
    topk = _build_topk_analysis(actor_rows)
    mask = _build_mask_impact(actor_rows)
    pending = _build_pending_lifecycle_analysis(lifecycle_rows, consistency)
    training = _build_training_implications(normalization, unit_matrix, mask, pending)

    classification = str(training.get("classification") or CLASS_INCONCLUSIVE)
    report = {
        "generated_at_utc": _utc_now(),
        "stage": "Stage6R5B",
        "input_artifacts": [
            str(actor_trace_path.as_posix()),
            str(command_trace_path.as_posix()),
            str(consistency_path.as_posix()),
            str(rejection_summary_path.as_posix()),
            str(normalization_path.as_posix()),
        ],
        "analysis_scope": {
            "actor_rows_total_in_trace": len(actor_rows_all),
            "actor_rows_used_player1_controllable_only": len(actor_rows),
            "lifecycle_rows_total": len(lifecycle_rows),
        },
        "unit_type_action_matrix": unit_matrix,
        "topk_action_analysis": topk,
        "mask_impact_analysis": mask,
        "pending_lifecycle_analysis": pending,
        "training_implications": training,
        "rejection_reason_summary_reference": rejection_summary,
        "classification": classification,
        "recommended_next_stage": str(training.get("recommended_next_stage") or "Stage6B1 - Full Student BC Training From Stage5P4 Dataset"),
    }

    report_json_path = reports_dir / "stage6r5b_actor_cell_behavior_bottleneck_report.json"
    report_md_path = reports_dir / "STAGE6R5B_ACTOR_CELL_BEHAVIOR_BOTTLENECK_REPORT.md"

    unit_matrix_path = reports_dir / "stage6r5b_unit_type_action_matrix.json"
    mask_path = reports_dir / "stage6r5b_mask_impact_summary.json"
    pending_path = reports_dir / "stage6r5b_pending_lifecycle_analysis.json"
    training_path = reports_dir / "stage6r5b_training_implications.json"

    _write_json(report_json_path, report)
    _write_json(unit_matrix_path, unit_matrix)
    _write_json(mask_path, mask)
    _write_json(pending_path, pending)
    _write_json(training_path, training)
    report_md_path.write_text(_build_markdown(report), encoding="utf-8")

    print(report_json_path.as_posix())
    print(report_md_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
