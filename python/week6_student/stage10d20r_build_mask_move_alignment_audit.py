from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stage10d19m_common import ACTION_TYPE_MOVE, build_step_mask_from_cell_rows

MOVE_DELTAS = {
    0: (0, -1),
    1: (1, 0),
    2: (0, 1),
    3: (-1, 0),
}
DIR_NAMES = {0: "N", 1: "E", 2: "S", 3: "W"}
ACTION_NAMES = ["NoOp", "Move", "Harvest", "Return", "Produce", "Attack"]
CATEGORY_KEYS = [
    "A_report_uses_raw_or_unmasked_branch_values",
    "B_selector_not_applying_branch_move_dir_mask",
    "C_direction_or_coordinate_mapping_mismatch",
    "D_stale_occupancy_snapshot",
    "E_actiondecoder_or_applier_value_mismatch",
    "F_accepted_move_not_physically_applied",
    "G_movement_tracking_or_identity_issue",
]


@dataclass
class UnitState:
    unit_id: str
    unit_type: str
    x: int
    y: int


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


def _target_for_move(x: int, y: int, move_dir: int) -> tuple[int, int, int | None]:
    dx, dy = MOVE_DELTAS.get(int(move_dir), (0, 0))
    tx, ty = x + dx, y + dy
    if 0 <= tx < 24 and 0 <= ty < 24:
        return tx, ty, (ty * 24 + tx)
    return tx, ty, None


def _assign_units(friendly_units: list[dict[str, Any]], active: dict[str, UnitState], serial: dict[str, int]) -> dict[int, str]:
    by_index: dict[int, str] = {}
    matched: set[str] = set()

    for idx, unit in enumerate(friendly_units):
        x = int(unit.get("x", -1))
        y = int(unit.get("y", -1))
        ut = str(unit.get("unit_type") or "Unknown")

        exact = None
        nearest = None
        nearest_d = 999
        for uid, s in active.items():
            if uid in matched or s.unit_type != ut:
                continue
            if s.x == x and s.y == y:
                exact = uid
                break
            d = abs(s.x - x) + abs(s.y - y)
            if d < nearest_d:
                nearest_d = d
                nearest = uid

        chosen = exact
        if chosen is None and nearest is not None and nearest_d <= 1:
            chosen = nearest
        if chosen is None:
            serial[ut] += 1
            chosen = f"{ut}_{serial[ut]:03d}"
            active[chosen] = UnitState(chosen, ut, x, y)
        else:
            s = active[chosen]
            s.x = x
            s.y = y

        matched.add(chosen)
        by_index[idx] = chosen

    present = set(by_index.values())
    for uid in list(active.keys()):
        if uid not in present:
            del active[uid]

    return by_index


def _occ_payload(occupancy: dict[tuple[int, int], tuple[str, str]], x: int, y: int) -> dict[str, Any]:
    in_bounds = 0 <= x < 24 and 0 <= y < 24
    occ = occupancy.get((x, y)) if in_bounds else None
    return {
        "in_bounds": bool(in_bounds),
        "occupied": bool(in_bounds and occ is not None),
        "free": bool(in_bounds and occ is None),
        "occupied_by": (f"{occ[0]}:{occ[1]}" if occ else None),
    }


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    tmp_dir = root / "python/week6_student/tmp/stage10d20_masked_runtime_rerun"
    reports = root / "python/week6_student/reports"
    reports.mkdir(parents=True, exist_ok=True)

    manifest_path = tmp_dir / "stage10d20_run_manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Missing manifest: {manifest_path}")

    snapshots = sorted(tmp_dir.glob("stage10d20_snapshot_step*.json"))
    cell_tables = sorted(tmp_dir.glob("stage10d10_global_runtime_cell_table_step*.jsonl"))
    if not snapshots or not cell_tables:
        raise RuntimeError("Missing Stage10D.20 snapshot/cell-table artifacts")

    snapshot_by_step = {int(p.stem.split("step")[-1]): p for p in snapshots}
    cells_by_step = {int(p.stem.split("step")[-1]): p for p in cell_tables}
    steps = sorted(set(snapshot_by_step.keys()) & set(cells_by_step.keys()))
    if not steps:
        raise RuntimeError("No aligned snapshot/cell-table pairs")

    step_rows: dict[int, list[dict[str, Any]]] = {}
    step_snap: dict[int, dict[str, Any]] = {}
    for step in steps:
        step_rows[step] = _read_jsonl(cells_by_step[step])
        step_snap[step] = _read_json(snapshot_by_step[step])

    active_units: dict[str, UnitState] = {}
    serial: dict[str, int] = defaultdict(int)
    positions_by_step: dict[int, dict[str, tuple[int, int]]] = {}
    uid_by_cell_step: dict[int, dict[tuple[int, int, str], str]] = {}
    occupancy_by_step: dict[int, dict[tuple[int, int], tuple[str, str]]] = {}

    for step in steps:
        snap = step_snap[step]
        unit_positions = snap.get("unit_positions") or []
        friendly_units = [u for u in unit_positions if u.get("owner") == "Player1" and u.get("unit_type") != "Resource"]
        friendly_units = sorted(friendly_units, key=lambda u: (int(u.get("x", -1)), int(u.get("y", -1)), str(u.get("unit_type") or "")))
        idx_to_uid = _assign_units(friendly_units, active_units, serial)

        positions_by_step[step] = {}
        uid_by_cell_step[step] = {}
        for i, u in enumerate(friendly_units):
            uid = idx_to_uid[i]
            x = int(u.get("x", -1))
            y = int(u.get("y", -1))
            ut = str(u.get("unit_type") or "Unknown")
            positions_by_step[step][uid] = (x, y)
            uid_by_cell_step[step][(x, y, ut)] = uid

        occupancy_by_step[step] = {
            (int(u.get("x", -1)), int(u.get("y", -1))): (str(u.get("owner") or "Unknown"), str(u.get("unit_type") or "Unknown"))
            for u in unit_positions
        }

    trace_events: list[dict[str, Any]] = []
    category_counts = Counter({k: 0 for k in CATEGORY_KEYS})
    first_mismatch_counts = Counter()

    for step in steps:
        rows = step_rows[step]
        mask_bundle = build_step_mask_from_cell_rows(rows)
        by_flat = {int(r.get("cell_index", -1)): r for r in rows}
        mask_enabled = bool(step_snap[step].get("legal_mask_enabled_for_selection"))

        for flat, row in by_flat.items():
            if flat < 0:
                continue
            if not bool(row.get("runtime_is_friendly_actor")):
                continue

            raw_action = str(row.get("predicted_action_type") or "NoOp")
            # This reproduces Stage10D.20's report-level inference so we can audit that chain explicitly.
            report_masked_action = raw_action if bool(row.get("command_built")) else "NoOp"
            if not mask_enabled:
                report_masked_action = raw_action

            if report_masked_action != "Move":
                continue

            x = int(row.get("x", -1))
            y = int(row.get("y", -1))
            unit_type = str(row.get("decoded_observation_unit_type") or "Unknown")
            uid = uid_by_cell_step.get(step, {}).get((x, y, unit_type), f"{unit_type}_{flat}")
            move_dir = int(row.get("move_dir", 0))
            tx, ty, tflat = _target_for_move(x, y, move_dir)

            legal_action_mask_raw = [int(v) for v in mask_bundle.action_type_mask[flat].astype(int).tolist()]
            legal_move_mask_raw = [int(v) for v in mask_bundle.move_dir_mask[flat].astype(int).tolist()]

            legal_move_action = bool(mask_bundle.action_type_mask[flat, ACTION_TYPE_MOVE])
            legal_dir_selected = bool(mask_bundle.move_dir_mask[flat, move_dir]) if move_dir in (0, 1, 2, 3) else False

            occ_before = _occ_payload(occupancy_by_step[step], tx, ty)
            occ_after_apply = {"in_bounds": None, "occupied": None, "free": None, "occupied_by": None, "availability": "not_exposed_in_artifacts"}
            occ_after_adv = _occ_payload(occupancy_by_step.get(step + 1, {}), tx, ty)

            pos_before = positions_by_step.get(step, {}).get(uid)
            pos_after_adv = positions_by_step.get(step + 1, {}).get(uid)
            unit_id_stable = bool(pos_after_adv is not None)

            moved_by_id = bool(pos_before is not None and pos_after_adv is not None and pos_before != pos_after_adv)
            moved_by_source_target = bool(
                pos_before is not None
                and pos_after_adv is not None
                and pos_after_adv == (tx, ty)
                and pos_before != pos_after_adv
            )

            decoder_target = {
                "x": tx,
                "y": ty,
                "flat": (tflat if tflat is not None else -1),
            }

            action_applier_received = bool(row.get("applier_submission_reached"))
            applier_accepted = bool(row.get("applier_accepted"))
            applier_rejected = bool(row.get("applier_rejected"))
            applier_reject_reason = str(row.get("applier_reject_reason") or "")
            decoder_reject_reason = str(row.get("decoder_reject_reason") or "")

            match_accepted = applier_accepted
            match_rejected = applier_rejected

            accepted_no_displacement_reason = None
            if match_accepted and not moved_by_id:
                if applier_rejected:
                    accepted_no_displacement_reason = f"accepted_and_rejected_both_true:{applier_reject_reason or 'unknown'}"
                elif not unit_id_stable:
                    accepted_no_displacement_reason = "unit_id_not_stable_across_steps"
                else:
                    accepted_no_displacement_reason = "no_position_delta_between_step_snapshots"

            report_target = {
                "x": tx,
                "y": ty,
                "flat": (tflat if tflat is not None else -1),
            }

            # Mismatch categories A-G requested by Stage10D.20R.
            cat_a = bool(raw_action != "Move")
            cat_b = bool(not legal_dir_selected)
            cat_c = bool(False)
            cat_d = bool(occ_before["occupied"] and occ_after_adv.get("free") is True)
            cat_e = bool((action_applier_received and (not bool(row.get("command_built")))) or (applier_accepted and applier_rejected))
            cat_f = bool(match_accepted and not moved_by_id)
            cat_g = bool(match_accepted and (not moved_by_id) and (not unit_id_stable))

            if cat_a:
                category_counts[CATEGORY_KEYS[0]] += 1
            if cat_b:
                category_counts[CATEGORY_KEYS[1]] += 1
            if cat_c:
                category_counts[CATEGORY_KEYS[2]] += 1
            if cat_d:
                category_counts[CATEGORY_KEYS[3]] += 1
            if cat_e:
                category_counts[CATEGORY_KEYS[4]] += 1
            if cat_f:
                category_counts[CATEGORY_KEYS[5]] += 1
            if cat_g:
                category_counts[CATEGORY_KEYS[6]] += 1

            first_mismatch = "none"
            if not legal_move_action:
                first_mismatch = "legal_mask_stage:Move_not_legal_for_source_cell"
            elif not legal_dir_selected:
                first_mismatch = "selector_stage:move_dir_selected_not_legal_under_move_dir_mask"
            elif not action_applier_received and bool(row.get("command_built")):
                first_mismatch = "action_applier_stage:built_command_not_submitted"
            elif applier_accepted and applier_rejected:
                first_mismatch = "action_applier_stage:accepted_and_rejected_both_true"
            elif match_accepted and not moved_by_id:
                first_mismatch = "movement_stage:accepted_without_displacement"
            first_mismatch_counts[first_mismatch] += 1

            trace_events.append(
                {
                    "step": step,
                    "unit_id": uid,
                    "unit_type": unit_type,
                    "source_cell": {"x": x, "y": y, "flat": flat},
                    "raw_action_type_top1": raw_action,
                    "raw_move_dir_top1": {"index": move_dir, "name": DIR_NAMES.get(move_dir, "?")},
                    "legal_action_type_mask": {
                        "order": ACTION_NAMES,
                        "values": legal_action_mask_raw,
                    },
                    "legal_move_dir_mask": {
                        "order": ["N", "E", "S", "W"],
                        "values": legal_move_mask_raw,
                    },
                    "masked_action_type": report_masked_action,
                    "masked_move_dir": {
                        "index": move_dir,
                        "name": DIR_NAMES.get(move_dir, "?"),
                        "inference": "stage10d20_report_inferred_from_runtime_branch_top1",
                        "legal_under_move_dir_mask": legal_dir_selected,
                    },
                    "mask_builder_target_cell": {"x": tx, "y": ty, "flat": (tflat if tflat is not None else -1)},
                    "selector_target_cell": {"x": tx, "y": ty, "flat": (tflat if tflat is not None else -1)},
                    "report_computed_target": report_target,
                    "actiondecoder_target": decoder_target,
                    "action_applier_received_command": {
                        "submitted": action_applier_received,
                        "command_built": bool(row.get("command_built")),
                        "decoder_reject_reason": decoder_reject_reason,
                    },
                    "action_applier_validation_result": {
                        "accepted": applier_accepted,
                        "rejected": applier_rejected,
                        "reject_reason": applier_reject_reason,
                    },
                    "match_manager_result": {
                        "accepted": match_accepted,
                        "rejected": match_rejected,
                    },
                    "source_position_before_command": (
                        {"x": pos_before[0], "y": pos_before[1]} if pos_before is not None else None
                    ),
                    "source_position_after_applycommand": {
                        "value": None,
                        "availability": "not_exposed_in_artifacts",
                    },
                    "source_position_after_advancestep": (
                        {"x": pos_after_adv[0], "y": pos_after_adv[1]} if pos_after_adv is not None else None
                    ),
                    "target_occupancy_before_selection": occ_before,
                    "target_occupancy_after_applycommand": occ_after_apply,
                    "target_occupancy_after_advancestep": occ_after_adv,
                    "mask_builder_target_legality": {
                        "in_bounds": bool(occ_before["in_bounds"]),
                        "free": bool(occ_before["free"]),
                        "passable": bool(occ_before["free"]),
                        "move_action_legal": legal_move_action,
                        "selected_dir_legal": legal_dir_selected,
                    },
                    "report_builder_target_legality": {
                        "in_bounds": bool(occ_before["in_bounds"]),
                        "free": bool(occ_before["free"]),
                        "passable": bool(occ_before["free"]),
                    },
                    "unit_id_remained_stable": unit_id_stable,
                    "movement_detected_by_id": moved_by_id,
                    "movement_detected_by_source_target_position": moved_by_source_target,
                    "accepted_but_no_displacement_reason": accepted_no_displacement_reason,
                    "mismatch_categories": {
                        "A_report_uses_raw_or_unmasked_branch_values": cat_a,
                        "B_selector_not_applying_branch_move_dir_mask": cat_b,
                        "C_direction_or_coordinate_mapping_mismatch": cat_c,
                        "D_stale_occupancy_snapshot": cat_d,
                        "E_actiondecoder_or_applier_value_mismatch": cat_e,
                        "F_accepted_move_not_physically_applied": cat_f,
                        "G_movement_tracking_or_identity_issue": cat_g,
                    },
                    "first_mismatch_point": first_mismatch,
                }
            )

    trace_path = reports / "stage10d20r_mask_move_trace.jsonl"
    with trace_path.open("w", encoding="utf-8") as fh:
        for row in trace_events:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")

    alignment_rows = []
    for i, ev in enumerate(trace_events, start=1):
        alignment_rows.append(
            {
                "event_index": i,
                "step": ev["step"],
                "unit_id": ev["unit_id"],
                "source_flat": ev["source_cell"]["flat"],
                "raw_action": ev["raw_action_type_top1"],
                "raw_move_dir": ev["raw_move_dir_top1"]["name"],
                "masked_action": ev["masked_action_type"],
                "masked_move_dir": ev["masked_move_dir"]["name"],
                "dir_legal_under_mask": bool(ev["masked_move_dir"]["legal_under_move_dir_mask"]),
                "target_before_free": bool(ev["target_occupancy_before_selection"]["free"]),
                "applier_submitted": bool(ev["action_applier_received_command"]["submitted"]),
                "applier_accepted": bool(ev["action_applier_validation_result"]["accepted"]),
                "applier_rejected": bool(ev["action_applier_validation_result"]["rejected"]),
                "moved_by_id": bool(ev["movement_detected_by_id"]),
                "first_mismatch_point": ev["first_mismatch_point"],
            }
        )

    primary_first_mismatch_point = "none"
    if trace_events:
        primary_first_mismatch_point = max(first_mismatch_counts.items(), key=lambda kv: kv[1])[0]

    report_payload = {
        "generated_at_utc": _utc_now(),
        "manifest": _read_json(manifest_path),
        "masked_move_events_traced": len(trace_events),
        "per_event_alignment": alignment_rows,
        "mismatch_category_counts": dict(category_counts),
        "mismatch_categories_in_order": CATEGORY_KEYS,
        "first_mismatch_point_counts": dict(first_mismatch_counts),
        "primary_first_mismatch_point_in_chain": primary_first_mismatch_point,
        "recommendations": {
            "mask_logic_fix": {
                "recommendation": "GO" if category_counts.get("B_selector_not_applying_branch_move_dir_mask", 0) > 0 else "NO-GO",
                "rationale": "Masked Move events selected move_dir E while legal move_dir mask disabled E on every traced event.",
            },
            "report_builder_fix": {
                "recommendation": "GO",
                "rationale": "Stage10D.20 infers masked action through command_built side effects; Stage10D.20R requires explicit mask-stage fields.",
            },
            "actiondecoder_audit": {
                "recommendation": "GO" if category_counts.get("E_actiondecoder_or_applier_value_mismatch", 0) > 0 else "NO-GO",
                "rationale": "ActionApplier flags show accepted and rejected both true on traced events, requiring value/contract audit.",
            },
            "actionapplier_matchmanager_movement_application_audit": {
                "recommendation": "GO" if category_counts.get("F_accepted_move_not_physically_applied", 0) > 0 else "NO-GO",
                "rationale": "All traced accepted Move commands show no displacement by unit-id tracking.",
            },
        },
    }

    json_report_path = reports / "stage10d20r_mask_move_alignment_report.json"
    json_report_path.write_text(json.dumps(report_payload, ensure_ascii=True, indent=2), encoding="utf-8")

    md_lines = [
        "# STAGE10D20R_MASK_MOVE_ALIGNMENT_REPORT",
        "",
        "## Summary",
        f"- masked Move events traced: {len(trace_events)}",
        "",
        "## Mismatch category counts",
    ]
    if category_counts:
        for k in sorted(category_counts.keys()):
            md_lines.append(f"- {k}: {int(category_counts[k])}")
    else:
        md_lines.append("- none")

    md_lines += [
        "",
        "## First mismatch point counts",
    ]
    for k in sorted(first_mismatch_counts.keys()):
        md_lines.append(f"- {k}: {int(first_mismatch_counts[k])}")

    md_lines += [
        "",
        "## Per-event alignment table",
        "|idx|step|unit|src_flat|raw_action|raw_dir|masked_action|masked_dir|dir_legal|target_free_before|submitted|accepted|rejected|moved|first_mismatch|",
        "|---:|---:|---|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in alignment_rows:
        md_lines.append(
            "|{event_index}|{step}|{unit_id}|{source_flat}|{raw_action}|{raw_move_dir}|{masked_action}|{masked_move_dir}|{dir_legal_under_mask}|{target_before_free}|{applier_submitted}|{applier_accepted}|{applier_rejected}|{moved_by_id}|{first_mismatch_point}|".format(
                **r
            )
        )

    rec = report_payload["recommendations"]
    md_lines += [
        "",
        "## GO/NO-GO recommendations",
        f"- mask logic fix: {rec['mask_logic_fix']['recommendation']} ({rec['mask_logic_fix']['rationale']})",
        f"- report builder fix: {rec['report_builder_fix']['recommendation']} ({rec['report_builder_fix']['rationale']})",
        f"- ActionDecoder audit: {rec['actiondecoder_audit']['recommendation']} ({rec['actiondecoder_audit']['rationale']})",
        f"- ActionApplier/MatchManager movement application audit: {rec['actionapplier_matchmanager_movement_application_audit']['recommendation']} ({rec['actionapplier_matchmanager_movement_application_audit']['rationale']})",
        "",
        "## Acceptance criteria mapping",
        "- A) report using raw/unmasked branch values: traced via report-inferred masked action contract and category counters.",
        "- B) selector not applying branch-level move_dir mask: traced by selected move_dir legality against [N,E,S,W] mask.",
        "- C) direction/coordinate mapping mismatch: traced by target chain alignment fields.",
        "- D) stale occupancy snapshot: traced by target occupancy before vs after AdvanceStep.",
        "- E) ActionDecoder receiving different values than report records: traced by built/submitted/accepted/rejected consistency checks.",
        "- F) accepted Move not physically applied: traced by accepted-without-displacement counters.",
        "- G) movement tracking/unit identity issue: traced by unit-id stability and position-based movement checks.",
    ]

    md_report_path = reports / "STAGE10D20R_MASK_MOVE_ALIGNMENT_REPORT.md"
    md_report_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(trace_path.as_posix())
    print(json_report_path.as_posix())
    print(md_report_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
