#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Mapping

from stage10d19c_common import (
    MOVABLE_UNIT_NAMES,
    build_mask_bundle_from_obs,
    find_unit_record,
    friendly_occupancy_from_step_units,
    in_bounds,
    index_trace_by_step,
    infer_alternative_free_dirs,
    load_json,
    move_target,
    read_jsonl,
    reconstruct_obs_flat_from_step_units,
    resolve_path,
    utc_now_iso,
    write_json,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.19C extract occupied-target move failure cases")
    p.add_argument(
        "--movement-audit-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d18rr_movement_command_path_audit.json"),
    )
    p.add_argument(
        "--runtime-trace-jsonl",
        type=Path,
        default=Path("python/week6_student/reports/stage10d18rr_runtime_redeploy_trace.jsonl"),
    )
    p.add_argument(
        "--move-efficiency-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d19_move_command_efficiency_audit.json"),
    )
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d19c_occupied_move_failure_cases.json"),
    )
    p.add_argument(
        "--output-jsonl",
        type=Path,
        default=Path("python/week6_student/reports/stage10d19c_occupied_move_failure_cases.jsonl"),
    )
    return p.parse_args()


def _safe_source_flat(ev: Mapping[str, Any]) -> int:
    src = ev.get("source_cell") or {}
    if isinstance(src, Mapping):
        flat = int(src.get("flat", -1))
        if flat >= 0:
            return flat
        x = int(src.get("x", -1))
        y = int(src.get("y", -1))
        if in_bounds(x, y):
            return int(y * 24 + x)
    return -1


def _safe_target(ev: Mapping[str, Any], source_flat: int) -> tuple[Dict[str, int], bool]:
    tgt = ev.get("decoded_target_cell") or {}
    if isinstance(tgt, Mapping) and "x" in tgt and "y" in tgt:
        x = int(tgt.get("x", -1))
        y = int(tgt.get("y", -1))
        flat = int(tgt.get("flat", y * 24 + x if in_bounds(x, y) else -1))
        return {"x": x, "y": y, "flat": flat}, bool(in_bounds(x, y))

    move_dir = int(ev.get("move_dir", -1))
    t_flat, ok = move_target(source_flat, move_dir)
    if (not ok) or t_flat is None:
        return {"x": -1, "y": -1, "flat": -1}, False
    x = int(t_flat % 24)
    y = int(t_flat // 24)
    return {"x": x, "y": y, "flat": int(t_flat)}, True


def _p_move_bucket(p_move: float) -> str:
    p = float(p_move)
    if p < 0.2:
        return "<0.2"
    if p < 0.5:
        return "0.2-0.5"
    if p < 0.8:
        return "0.5-0.8"
    return ">=0.8"


def main() -> int:
    args = parse_args()

    move_audit = load_json(args.movement_audit_json)
    eff = load_json(args.move_efficiency_json)
    trace_rows = read_jsonl(args.runtime_trace_jsonl)
    trace_by_step = index_trace_by_step(trace_rows)

    eff_events = eff.get("events", []) if isinstance(eff, dict) else []
    eff_idx: Dict[tuple[int, str], Mapping[str, Any]] = {}
    for r in eff_events:
        if not isinstance(r, Mapping):
            continue
        step = int(r.get("step", -1))
        uid = str(r.get("unit_id", ""))
        if step >= 0 and uid:
            eff_idx[(step, uid)] = r

    out_rows: List[Dict[str, Any]] = []

    unit_counter: Counter[str] = Counter()
    dir_counter: Counter[str] = Counter()
    p_bucket_counter: Counter[str] = Counter()
    decoder_counter: Counter[str] = Counter()
    occ_type_counter: Counter[str] = Counter()

    for i, ev in enumerate(move_audit.get("events", []) or []):
        if str(ev.get("predicted_action", "")) != "Move":
            continue

        cmd_built = bool(ev.get("command_built", False))
        dec_reason = str(ev.get("decoder_reject_reason", ""))
        if not ((not cmd_built) or (dec_reason == "not_built_in_decoder_or_filter")):
            continue

        unit_type = str(ev.get("unit_type", ""))
        if unit_type not in MOVABLE_UNIT_NAMES:
            continue

        step = int(ev.get("step", -1))
        unit_id = str(ev.get("unit_id", ""))
        src_flat = _safe_source_flat(ev)
        if step < 0 or src_flat < 0 or not unit_id:
            continue

        tgt_cell, inb = _safe_target(ev, src_flat)
        target_occupied_ev = bool(ev.get("target_cell_occupied", False))
        target_invalid = bool(not inb)

        if not (target_occupied_ev or target_invalid):
            continue

        step_units = trace_by_step.get(step, [])
        unit_row = find_unit_record(step_units, unit_id)
        occ = friendly_occupancy_from_step_units(step_units)

        runtime_is_actor = bool(unit_row is not None)
        if not runtime_is_actor:
            # Keep uncertain rows but mark explicitly.
            pass

        alt_dirs = infer_alternative_free_dirs(src_flat, occ)
        bad_dir = int(ev.get("move_dir", -1))
        alt_dirs = [d for d in alt_dirs if d != bad_dir]

        preferred_alt = alt_dirs[0] if alt_dirs else None
        preferred_alt_target = None
        if preferred_alt is not None:
            t_flat, ok = move_target(src_flat, int(preferred_alt))
            if ok and t_flat is not None:
                preferred_alt_target = {"x": int(t_flat % 24), "y": int(t_flat // 24), "flat": int(t_flat)}

        occ_type = "unknown"
        tgt_flat = int(tgt_cell.get("flat", -1))
        if not inb:
            occ_type = "out_of_bounds"
        elif tgt_flat in occ:
            occ_type = "friendly"
        elif target_occupied_ev:
            # Enemy/resource occupancy cannot be fully reconstructed from friendly-only trace.
            eff_row = eff_idx.get((step, unit_id), {})
            kind = str(eff_row.get("target_cell_kind", "")).strip().lower()
            if kind == "resource":
                occ_type = "resource"
            elif kind == "enemy":
                occ_type = "enemy"
            elif kind == "occupied":
                occ_type = "unknown"
            else:
                occ_type = "unknown"

        obs = reconstruct_obs_flat_from_step_units(step_units)
        bundle = build_mask_bundle_from_obs(obs)
        mask_allow_move = bool(bundle.action_type_mask[src_flat, 1]) if 0 <= src_flat < 576 else False
        mask_allow_dir = bool(bundle.move_dir_mask[src_flat, bad_dir]) if (0 <= src_flat < 576 and bad_dir in (0, 1, 2, 3)) else False

        if mask_allow_move and preferred_alt is not None:
            mask_rec_action = "Move"
            mask_rec_dir = int(preferred_alt)
        elif mask_allow_move and preferred_alt is None:
            mask_rec_action = "Move"
            legal_dirs = [d for d in (0, 1, 2, 3) if bool(bundle.move_dir_mask[src_flat, d])]
            mask_rec_dir = int(legal_dirs[0]) if legal_dirs else None
        else:
            mask_rec_action = "NoOp"
            mask_rec_dir = None

        if not runtime_is_actor:
            family = "off_actor_or_uncertain"
        elif preferred_alt is not None:
            family = "valid_alt_available"
        elif target_occupied_ev:
            family = "occupied_target"
        else:
            family = "no_valid_alt"

        row = {
            "case_id": f"s{step:04d}_{unit_id}_d{bad_dir}_{i:05d}",
            "step": int(step),
            "unit_id": unit_id,
            "unit_type": unit_type,
            "source_cell": {
                "x": int(src_flat % 24),
                "y": int(src_flat // 24),
                "flat": int(src_flat),
            },
            "predicted_move_dir": int(bad_dir),
            "predicted_target_cell": tgt_cell,
            "target_cell_in_bounds": bool(inb),
            "target_cell_occupied": bool(target_occupied_ev),
            "target_occupancy_type": occ_type,
            "p_move": float(ev.get("p_move", 0.0)),
            "p_noop": float(ev.get("p_noop", 0.0)),
            "p_harvest": float(ev.get("p_harvest", 0.0)),
            "p_produce": float(ev.get("p_produce", 0.0)),
            "p_attack": float(ev.get("p_attack", 0.0)),
            "decoder_reject_reason": dec_reason,
            "action_applier_reached": bool(ev.get("action_applier_reached", False)),
            "match_manager_reached": bool(ev.get("match_manager_apply_command_reached", False)),
            "alternative_free_dirs": [int(d) for d in alt_dirs],
            "preferred_valid_alt_dir": int(preferred_alt) if preferred_alt is not None else None,
            "preferred_valid_alt_target": preferred_alt_target,
            "mask_would_allow_move": bool(mask_allow_move),
            "mask_would_allow_predicted_dir": bool(mask_allow_dir),
            "mask_recommended_action": mask_rec_action,
            "mask_recommended_move_dir": mask_rec_dir,
            "failure_family": family,
        }
        out_rows.append(row)

        unit_counter[unit_type] += 1
        dir_counter[str(bad_dir)] += 1
        p_bucket_counter[_p_move_bucket(float(row["p_move"]))] += 1
        decoder_counter[dec_reason or "unknown"] += 1
        occ_type_counter[occ_type] += 1

    valid_alt_count = int(sum(1 for r in out_rows if len(r.get("alternative_free_dirs", [])) > 0))
    no_valid_alt_count = int(len(out_rows) - valid_alt_count)

    labels = [
        "STAGE10D19C_FAILURE_CASE_EXTRACTION_COMPLETED",
        "STAGE10D19C_OCCUPIED_TARGET_FAILURES_CONFIRMED" if any(bool(r.get("target_cell_occupied", False)) for r in out_rows) else "STAGE10D19C_NO_FAILURE_CASES_FOUND",
        "STAGE10D19C_VALID_ALTERNATIVE_MOVES_AVAILABLE" if valid_alt_count > 0 else "STAGE10D19C_NO_VALID_ALTERNATIVE_FOR_SOME_FAILURES",
        "STAGE10D19C_NO_VALID_ALTERNATIVE_FOR_SOME_FAILURES" if no_valid_alt_count > 0 else "STAGE10D19C_ALL_FAILURES_HAVE_ALTERNATIVE",
        "STAGE10D19C_FAILURE_CASES_READY_FOR_MASK_AWARE_DATASET" if len(out_rows) > 0 else "STAGE10D19C_NO_FAILURE_CASES_FOUND",
    ]

    report = {
        "stage": "10D.19C",
        "task": "extract_occupied_move_failure_cases",
        "generated_at_utc": utc_now_iso(),
        "input_artifacts": {
            "movement_audit_json": str(resolve_path(args.movement_audit_json).as_posix()),
            "runtime_trace_jsonl": str(resolve_path(args.runtime_trace_jsonl).as_posix()),
            "move_efficiency_json": str(resolve_path(args.move_efficiency_json).as_posix()),
        },
        "total_failure_cases": int(len(out_rows)),
        "occupied_target_failure_cases": int(sum(1 for r in out_rows if bool(r.get("target_cell_occupied", False)))),
        "out_of_bounds_failure_cases": int(sum(1 for r in out_rows if not bool(r.get("target_cell_in_bounds", True)))),
        "friendly_occupied_count": int(occ_type_counter.get("friendly", 0)),
        "enemy_occupied_count": int(occ_type_counter.get("enemy", 0)),
        "resource_occupied_count": int(occ_type_counter.get("resource", 0)),
        "unknown_occupied_count": int(occ_type_counter.get("unknown", 0)),
        "cases_with_valid_alternative_dir": int(valid_alt_count),
        "cases_without_valid_alternative_dir": int(no_valid_alt_count),
        "unit_type_distribution": dict(unit_counter),
        "move_dir_distribution": dict(dir_counter),
        "p_move_bucket_distribution": dict(p_bucket_counter),
        "decoder_reject_distribution": dict(decoder_counter),
        "efficiency_reference": {
            "total_move_predictions": int(eff.get("events") and len(eff.get("events", [])) or 0),
            "invalid_target_move_prediction_count": int(eff.get("invalid_target_move_prediction_count", 0)),
            "occupied_target_count": int(eff.get("occupied_target_count", 0)),
            "move_prediction_to_build_rate": float(eff.get("move_prediction_to_build_rate", 0.0)),
        },
        "labels": labels,
        "failure_cases": out_rows,
    }

    write_json(args.output_json, report)
    write_jsonl(args.output_jsonl, out_rows)

    print(resolve_path(args.output_json).as_posix())
    print(resolve_path(args.output_jsonl).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
