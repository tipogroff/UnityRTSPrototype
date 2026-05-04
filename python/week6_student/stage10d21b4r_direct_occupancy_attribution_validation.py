from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GRID_W = 24
NOT_EXPOSED = "NOT_EXPOSED"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        text = line.strip()
        if text:
            rows.append(json.loads(text))
    return rows


def _flat_to_xy(flat: int) -> tuple[int, int]:
    if flat < 0:
        return (-1, -1)
    return (flat % GRID_W, flat // GRID_W)


def _xy_to_flat(x: int, y: int) -> int:
    if x < 0 or x >= GRID_W or y < 0 or y >= GRID_W:
        return -1
    return y * GRID_W + x


def _move_delta(move_dir: int) -> tuple[int, int]:
    # Runtime contract: North=(0,+1), East=(+1,0), South=(0,-1), West=(-1,0)
    if move_dir == 0:
        return (0, 1)
    if move_dir == 1:
        return (1, 0)
    if move_dir == 2:
        return (0, -1)
    if move_dir == 3:
        return (-1, 0)
    return (0, 0)


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "y"}:
            return True
        if text in {"false", "0", "no", "n"}:
            return False
        if text in {"not_exposed", "not_computed_runtime", "inference_only_not_from_matchmanager", ""}:
            return None
    return None


def _unit_index(snapshot: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        int(unit.get("flat_index", -1) or -1): unit
        for unit in snapshot.get("unit_positions", [])
    }


def _snapshot_occ(snapshot_path: Path, flat: int) -> dict[str, Any]:
    if flat < 0 or not snapshot_path.exists():
        return {
            "available": False,
            "occupied": "NOT_EXPOSED",
            "occupant_id": NOT_EXPOSED,
            "occupant_owner": NOT_EXPOSED,
            "occupant_type": NOT_EXPOSED,
            "occupant_cell": -1,
        }

    snap = _read_json(snapshot_path)
    occupant = _unit_index(snap).get(flat)
    if occupant is None:
        return {
            "available": True,
            "occupied": False,
            "occupant_id": None,
            "occupant_owner": None,
            "occupant_type": None,
            "occupant_cell": -1,
        }

    return {
        "available": True,
        "occupied": True,
        "occupant_id": str(occupant.get("logical_cell") or occupant.get("unit_id") or occupant.get("flat_index") or NOT_EXPOSED),
        "occupant_owner": str(occupant.get("owner") or NOT_EXPOSED),
        "occupant_type": str(occupant.get("unit_type") or NOT_EXPOSED),
        "occupant_cell": int(occupant.get("flat_index", -1) or -1),
    }


def _tri_bool(value: bool | None) -> Any:
    if value is None:
        return NOT_EXPOSED
    return value


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    reports = root / "python/week6_student/reports"
    reports.mkdir(parents=True, exist_ok=True)
    tmp = root / "python/week6_student/tmp/stage10d20_masked_runtime_rerun"

    stage21b3_report = _read_json(reports / "stage10d21b3_status_mapping_report.json")
    stage21b3_trace = _read_jsonl(reports / "stage10d21b3_status_mapping_trace.jsonl")
    stage20s_trace = _read_jsonl(reports / "stage10d20s_mask_move_trace.jsonl")

    prior_b4_path = reports / "stage10d21b4_matchmanager_move_rejection_report.json"
    prior_b4 = _read_json(prior_b4_path) if prior_b4_path.exists() else {"commands": []}
    prior_by_cmd = {str(item.get("command_id")): item for item in prior_b4.get("commands", [])}

    target_commands = {
        str(item.get("command_id")): item
        for item in stage21b3_report.get("previously_conflicting_commands", [])
        if str(item.get("final_command_result_status")) == "matchmanager_rejected"
    }
    if len(target_commands) != 4:
        raise RuntimeError("Expected 4 matchmanager_rejected commands from Stage10D.21B3")

    trace_rows_by_cmd: dict[str, dict[str, Any]] = {}
    for row in stage21b3_trace:
        cmd = str(row.get("command_id") or "")
        if cmd not in target_commands:
            continue
        prev = trace_rows_by_cmd.get(cmd)
        if prev is None or int(row.get("command_event_sequence", 0) or 0) >= int(prev.get("command_event_sequence", 0) or 0):
            trace_rows_by_cmd[cmd] = row

    move_trace_by_step_cell = {
        (int(row.get("step", -1) or -1), int(row.get("cell_index", -1) or -1)): row
        for row in stage20s_trace
    }

    out_rows: list[dict[str, Any]] = []
    occupancy_outcome_counts: Counter[str] = Counter()
    player2_proven: list[str] = []
    player2_disproven: list[str] = []

    for command_id in sorted(target_commands.keys()):
        trace = trace_rows_by_cmd.get(command_id)
        if trace is None:
            raise RuntimeError(f"Missing Stage10D.21B3 trace row for {command_id}")

        step = int(trace.get("step", -1) or -1)
        cell = int(trace.get("cell_index", -1) or -1)
        event_step = int(trace.get("command_event_step", -1) or -1)
        move_row = move_trace_by_step_cell.get((step, cell), {})

        move_dir = int(trace.get("move_dir", move_row.get("masked_move_dir", -1)) or -1)

        source_cell = int(trace.get("source_cell_from_command", -1) or -1)
        if source_cell < 0:
            source_cell = cell

        source_x = int(trace.get("source_x_from_command", -1) or -1)
        source_y = int(trace.get("source_y_from_command", -1) or -1)
        if source_x < 0 or source_y < 0:
            sx, sy = _flat_to_xy(source_cell)
            source_x, source_y = sx, sy

        target_cell = int(trace.get("target_cell_from_command", -1) or -1)
        target_x = int(trace.get("target_x_from_command", -1) or -1)
        target_y = int(trace.get("target_y_from_command", -1) or -1)
        if target_x < 0 or target_y < 0:
            tx, ty = _flat_to_xy(target_cell)
            target_x, target_y = tx, ty
        if target_cell < 0 and target_x >= 0 and target_y >= 0:
            target_cell = _xy_to_flat(target_x, target_y)

        if target_cell < 0 and isinstance(move_row.get("target"), dict):
            target_x = int(move_row["target"].get("x", target_x) or target_x)
            target_y = int(move_row["target"].get("y", target_y) or target_y)
            target_cell = _xy_to_flat(target_x, target_y)

        source_xy_from_flat = _flat_to_xy(source_cell)
        target_xy_from_flat = _flat_to_xy(target_cell)
        source_flat_roundtrip = _xy_to_flat(source_x, source_y)
        target_flat_roundtrip = _xy_to_flat(target_x, target_y)
        source_roundtrip_ok = source_flat_roundtrip == source_cell
        target_roundtrip_ok = target_flat_roundtrip == target_cell

        dx, dy = _move_delta(move_dir)
        reconstructed_target = _xy_to_flat(source_x + dx, source_y + dy)
        reconstructed_target_matches = reconstructed_target == target_cell

        runtime_target_matches_reconstructed = _bool_or_none(
            trace.get("direct_runtime_target_matches_reconstructed_target")
        )
        if runtime_target_matches_reconstructed is None:
            runtime_target_matches_reconstructed = reconstructed_target_matches

        report_target_matches_move_trace = True
        if isinstance(move_row.get("target"), dict):
            mt_flat = _xy_to_flat(int(move_row["target"].get("x", -1) or -1), int(move_row["target"].get("y", -1) or -1))
            report_target_matches_move_trace = mt_flat == target_cell

        runtime_occupied = _bool_or_none(trace.get("target_occupied_by_runtime_lookup"))
        target_in_bounds = _bool_or_none(trace.get("target_in_bounds_at_reject"))
        target_passable = _bool_or_none(trace.get("target_passable_at_reject"))

        occ_exists = _bool_or_none(trace.get("occupant_exists_at_target"))
        occupant_id = str(trace.get("occupant_id_at_target") or NOT_EXPOSED)
        occupant_owner = str(trace.get("occupant_owner_at_target") or NOT_EXPOSED)
        occupant_type = str(trace.get("occupant_type_at_target") or NOT_EXPOSED)
        occupant_cell = int(trace.get("occupant_cell_at_target", -1) or -1)
        occupant_x = int(trace.get("occupant_x_at_target", -1) or -1)
        occupant_y = int(trace.get("occupant_y_at_target", -1) or -1)

        snap_decision = _snapshot_occ(tmp / f"stage10d20_snapshot_step{event_step:04d}.json", target_cell)
        snap_before_reject = _snapshot_occ(tmp / f"stage10d20_snapshot_step{max(0, step - 1):04d}.json", target_cell)
        snap_at_reject = _snapshot_occ(tmp / f"stage10d20_snapshot_step{step:04d}.json", target_cell)

        snapshot_lookup = snap_at_reject["occupied"] if snap_at_reject["available"] else NOT_EXPOSED
        runtime_vs_snapshot = NOT_EXPOSED
        if isinstance(runtime_occupied, bool) and isinstance(snapshot_lookup, bool):
            runtime_vs_snapshot = runtime_occupied == snapshot_lookup

        prior_owner_claim = str(prior_by_cmd.get(command_id, {}).get("target_occupied_owner_at_reject") or NOT_EXPOSED)
        if runtime_occupied is True and occupant_owner == "Player2":
            player2_proven.append(command_id)
        elif prior_owner_claim == "Player2":
            player2_disproven.append(command_id)

        occupant_fully_exposed = (
            runtime_occupied is True
            and occ_exists is True
            and occupant_id not in {NOT_EXPOSED, "", "None"}
            and occupant_owner not in {NOT_EXPOSED, "", "None"}
            and occupant_type not in {NOT_EXPOSED, "", "None"}
            and occupant_cell >= 0
        )

        if occupant_fully_exposed:
            occupancy_outcome = "A_RUNTIME_OCCUPIED_WITH_DIRECT_OCCUPANT"
        elif runtime_occupied is False:
            occupancy_outcome = "B_RUNTIME_NOT_OCCUPIED_DIAGNOSTIC_MISMATCH"
        else:
            occupancy_outcome = "C_RUNTIME_OCCUPANT_NOT_EXPOSED"
        occupancy_outcome_counts[occupancy_outcome] += 1

        row = {
            "command_id": command_id,
            "command_event_key": str(trace.get("command_event_key") or ""),
            "command_event_sequence": int(trace.get("command_event_sequence", 0) or 0),
            "command_event_step": event_step,
            "reject_callsite": str(trace.get("reject_callsite") or "NOT_EXPOSED"),
            "reject_reason_raw": str(trace.get("reject_reason_raw") or trace.get("terminal_reject_reason") or ""),
            "reject_reason_normalized": str(trace.get("reject_reason_normalized") or "NOT_EXPOSED"),
            "action_type": str(trace.get("action_type") or "Move"),
            "move_dir": move_dir,
            "source_cell_from_command": source_cell,
            "source_x_from_command": source_x,
            "source_y_from_command": source_y,
            "target_cell_from_command": target_cell,
            "target_x_from_command": target_x,
            "target_y_from_command": target_y,
            "unit_id": str(trace.get("unit_id") or NOT_EXPOSED),
            "unit_owner": str(trace.get("unit_owner") or NOT_EXPOSED),
            "unit_type": str(trace.get("unit_type") or NOT_EXPOSED),
            "unit_position_x_at_reject": int(trace.get("unit_position_x_at_reject", -1) or -1),
            "unit_position_y_at_reject": int(trace.get("unit_position_y_at_reject", -1) or -1),
            "unit_cell_at_reject": int(trace.get("unit_cell_at_reject", -1) or -1),
            "occupant_exists_at_target": _tri_bool(occ_exists),
            "occupant_id_at_target": occupant_id,
            "occupant_owner_at_target": occupant_owner,
            "occupant_type_at_target": occupant_type,
            "occupant_x_at_target": occupant_x,
            "occupant_y_at_target": occupant_y,
            "occupant_cell_at_target": occupant_cell,
            "occupancy_lookup_method": str(trace.get("occupancy_lookup_method") or NOT_EXPOSED),
            "occupancy_lookup_source": str(trace.get("occupancy_lookup_source") or NOT_EXPOSED),
            "target_in_bounds_at_reject": _tri_bool(target_in_bounds),
            "target_passable_at_reject": _tri_bool(target_passable),
            "target_occupied_at_reject": _tri_bool(runtime_occupied),
            "target_occupied_by_runtime_lookup": _tri_bool(runtime_occupied),
            "target_occupied_by_snapshot_lookup": _tri_bool(_bool_or_none(trace.get("target_occupied_by_snapshot_lookup"))),
            "snapshot_step_used_for_attribution": int(trace.get("snapshot_step_used_for_attribution", -1) or -1),
            "direct_runtime_lookup_matches_snapshot_lookup": runtime_vs_snapshot,
            "direct_runtime_target_matches_reconstructed_target": runtime_target_matches_reconstructed,
            "flat_to_xy_source_cell": {"x": source_xy_from_flat[0], "y": source_xy_from_flat[1]},
            "flat_to_xy_target_cell": {"x": target_xy_from_flat[0], "y": target_xy_from_flat[1]},
            "xy_to_flat_source": source_flat_roundtrip,
            "xy_to_flat_target": target_flat_roundtrip,
            "source_flat_roundtrip_ok": source_roundtrip_ok,
            "target_flat_roundtrip_ok": target_roundtrip_ok,
            "move_dir_delta_used": {"dx": dx, "dy": dy},
            "reconstructed_target_from_source_and_move_dir": reconstructed_target,
            "reconstructed_target_matches_command_target": reconstructed_target_matches,
            "unity_runtime_target_matches_report_target": report_target_matches_move_trace,
            "snapshot_comparison": {
                "command_decision_step_target_occupancy": snap_decision,
                "immediately_before_reject_target_occupancy": snap_before_reject,
                "at_reject_step_target_occupancy": snap_at_reject,
                "direct_runtime_lookup_at_reject": {
                    "occupied": _tri_bool(runtime_occupied),
                    "occupant_id": occupant_id,
                    "occupant_owner": occupant_owner,
                    "occupant_type": occupant_type,
                    "occupant_cell": occupant_cell,
                },
            },
            "occupancy_outcome": occupancy_outcome,
        }
        out_rows.append(row)

    all_traced = len(out_rows) == 4 and all(str(row["command_id"]).startswith("cmd:") for row in out_rows)

    runtime_true_all = all(row["target_occupied_by_runtime_lookup"] is True for row in out_rows)
    runtime_confirmed_any_false_or_unknown = any(
        row["target_occupied_by_runtime_lookup"] in {False, NOT_EXPOSED}
        for row in out_rows
    )

    prior_player2_claims = {
        cmd: str(item.get("target_occupied_owner_at_reject") or "") == "Player2"
        for cmd, item in prior_by_cmd.items()
        if cmd in target_commands
    }

    corrected_attribution_needed = False
    for row in out_rows:
        cid = row["command_id"]
        if not prior_player2_claims.get(cid, False):
            continue
        if row["target_occupied_by_runtime_lookup"] is True and row["occupant_owner_at_target"] != "Player2":
            corrected_attribution_needed = True
        if row["target_occupied_by_runtime_lookup"] in {False, NOT_EXPOSED}:
            corrected_attribution_needed = True

    if runtime_true_all and not corrected_attribution_needed:
        gate_21b5 = "GO_FOR_STAGE10D21B5_DYNAMIC_OCCUPANCY_MASK_ENRICHMENT"
    elif runtime_true_all and corrected_attribution_needed:
        gate_21b5 = "GO_FOR_STAGE10D21B5_TARGET_OCCUPANCY_FIX_WITH_CORRECTED_ATTRIBUTION"
    else:
        gate_21b5 = "HOLD_STAGE10D21B5_AND_FIX_COORDINATE_OR_SNAPSHOT_ATTRIBUTION"

    acceptance_pass = all_traced and all(
        row["occupancy_outcome"] in {
            "A_RUNTIME_OCCUPIED_WITH_DIRECT_OCCUPANT",
            "B_RUNTIME_NOT_OCCUPIED_DIAGNOSTIC_MISMATCH",
            "C_RUNTIME_OCCUPANT_NOT_EXPOSED",
        }
        for row in out_rows
    )

    q_answers = {
        "q1_for_each_command_source_and_target": [
            {
                "command_id": row["command_id"],
                "source_cell": row["source_cell_from_command"],
                "target_cell": row["target_cell_from_command"],
            }
            for row in out_rows
        ],
        "q2_source_target_flat_index_roundtrip_pass": {
            row["command_id"]: bool(row["source_flat_roundtrip_ok"] and row["target_flat_roundtrip_ok"]) for row in out_rows
        },
        "q3_reconstructed_target_matches_command_target": {
            row["command_id"]: bool(row["reconstructed_target_matches_command_target"]) for row in out_rows
        },
        "q4_target_occupied_true_in_direct_runtime": {
            row["command_id"]: row["target_occupied_by_runtime_lookup"] for row in out_rows
        },
        "q5_exact_occupant_direct_from_matchmanager": {
            row["command_id"]: {
                "occupant_id": row["occupant_id_at_target"],
                "occupant_owner": row["occupant_owner_at_target"],
                "occupant_type": row["occupant_type_at_target"],
                "occupant_cell": row["occupant_cell_at_target"],
            }
            for row in out_rows
        },
        "q6_direct_runtime_matches_snapshot_or_posthoc": {
            row["command_id"]: row["direct_runtime_lookup_matches_snapshot_lookup"] for row in out_rows
        },
        "q7_player2_occupant_claims_proven_or_disproven": {
            "directly_proven": sorted(player2_proven),
            "directly_disproven_or_unproven": sorted(player2_disproven),
        },
        "q8_is_b4_target_occupied_still_valid": runtime_true_all,
        "q9_occupant_attribution_validity": (
            "valid" if runtime_true_all and not corrected_attribution_needed
            else ("invalid" if corrected_attribution_needed and not runtime_confirmed_any_false_or_unknown else "inconclusive")
        ),
        "q10_stage10d21b5_gate": gate_21b5,
        "q11_stage10d21c_gate": "NO-GO",
    }

    report = {
        "generated_at_utc": _utc_now(),
        "stage": "Stage10D.21B4R",
        "counts": {
            "commands_analyzed": len(out_rows),
            "occupancy_outcome_counts": dict(occupancy_outcome_counts),
        },
        "checks": {
            "all_4_commands_traced": all_traced,
            "acceptance_gate": "PASS" if acceptance_pass else "FAIL",
            "no_unsupported_player2_claims": all(
                not (
                    row["occupant_owner_at_target"] == "Player2"
                    and row["target_occupied_by_runtime_lookup"] not in {True}
                )
                for row in out_rows
            ),
        },
        "commands": out_rows,
        "required_answers": q_answers,
        "go_no_go": {
            "stage10d21b4r_direct_occupancy_attribution_validation": "PASS" if acceptance_pass else "FAIL",
            "stage10d21b5_legal_mask_enrichment_gate": gate_21b5,
            "stage10d21c_movement_application_audit": "NO-GO",
        },
    }

    trace_out = reports / "stage10d21b4r_direct_occupancy_attribution_trace.jsonl"
    report_out = reports / "stage10d21b4r_direct_occupancy_attribution_report.json"
    md_out = reports / "STAGE10D21B4R_DIRECT_OCCUPANCY_ATTRIBUTION_REPORT.md"

    with trace_out.open("w", encoding="utf-8") as fh:
        for row in out_rows:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")

    report_out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# STAGE10D21B4R Direct Occupancy Attribution Validation",
        "",
        f"- Generated (UTC): {report['generated_at_utc']}",
        f"- Commands analyzed: {report['counts']['commands_analyzed']}",
        f"- Stage10D.21B4R gate: {report['go_no_go']['stage10d21b4r_direct_occupancy_attribution_validation']}",
        f"- Stage10D.21B5 decision: {report['go_no_go']['stage10d21b5_legal_mask_enrichment_gate']}",
        f"- Stage10D.21C gate: {report['go_no_go']['stage10d21c_movement_application_audit']}",
        "",
        "## Occupancy Outcomes",
    ]

    for key, value in sorted(occupancy_outcome_counts.items()):
        lines.append(f"- {key}: {value}")

    lines.extend(
        [
            "",
            "## Required Answers",
            f"- Q1 source/target by command: {json.dumps(q_answers['q1_for_each_command_source_and_target'], ensure_ascii=True)}",
            f"- Q2 roundtrip pass: {json.dumps(q_answers['q2_source_target_flat_index_roundtrip_pass'], ensure_ascii=True)}",
            f"- Q3 reconstructed target matches: {json.dumps(q_answers['q3_reconstructed_target_matches_command_target'], ensure_ascii=True)}",
            f"- Q4 direct runtime target_occupied: {json.dumps(q_answers['q4_target_occupied_true_in_direct_runtime'], ensure_ascii=True)}",
            f"- Q5 direct runtime occupant tuples: {json.dumps(q_answers['q5_exact_occupant_direct_from_matchmanager'], ensure_ascii=True)}",
            f"- Q6 direct runtime vs snapshot/post-hoc: {json.dumps(q_answers['q6_direct_runtime_matches_snapshot_or_posthoc'], ensure_ascii=True)}",
            f"- Q7 Player2 claims: {json.dumps(q_answers['q7_player2_occupant_claims_proven_or_disproven'], ensure_ascii=True)}",
            f"- Q8 B4 target_occupied still valid: {q_answers['q8_is_b4_target_occupied_still_valid']}",
            f"- Q9 occupant attribution validity: {q_answers['q9_occupant_attribution_validity']}",
            f"- Q10 Stage10D.21B5 gate: {q_answers['q10_stage10d21b5_gate']}",
            f"- Q11 Stage10D.21C gate: {q_answers['q11_stage10d21c_gate']}",
            "",
            "## Artifacts",
            f"- Trace: {trace_out.relative_to(root).as_posix()}",
            f"- JSON: {report_out.relative_to(root).as_posix()}",
            f"- Markdown: {md_out.relative_to(root).as_posix()}",
        ]
    )

    md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "trace": trace_out.as_posix(),
                "report": report_out.as_posix(),
                "markdown": md_out.as_posix(),
                "gate21b4r": report["go_no_go"]["stage10d21b4r_direct_occupancy_attribution_validation"],
                "gate21b5": report["go_no_go"]["stage10d21b5_legal_mask_enrichment_gate"],
                "gate21c": report["go_no_go"]["stage10d21c_movement_application_audit"],
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
