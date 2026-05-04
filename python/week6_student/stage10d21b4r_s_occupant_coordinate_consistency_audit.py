from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GRID_W = 24
NOT_EXPOSED = "not_exposed"
REQUIRED_BUCKETS = [
    "consistent_direct_occupant",
    "instrumentation_wrote_target_as_occupant_cell",
    "stale_occupancy_map_reference",
    "occupant_logical_position_mismatch",
    "coordinate_mapping_mismatch",
    "visual_name_coordinate_mismatch",
    "not_exposed",
    "unknown_inconsistent",
]


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


def _xy_to_flat(x: int, y: int) -> int:
    if x < 0 or x >= GRID_W or y < 0 or y >= GRID_W:
        return -1
    return y * GRID_W + x


def _flat_to_xy(flat: int) -> tuple[int, int]:
    if flat < 0:
        return (-1, -1)
    return (flat % GRID_W, flat // GRID_W)


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        t = value.strip().lower()
        if t in {"true", "1", "yes", "y"}:
            return True
        if t in {"false", "0", "no", "n"}:
            return False
        if t in {"", "not_exposed", "not_computed_runtime", "inference_only_not_from_matchmanager", "nan"}:
            return None
    return None


def _parse_name_coords(text: str) -> tuple[int, int] | None:
    if not text:
        return None
    m = re.search(r"\((\d+)\s*,\s*(\d+)\)", text)
    if m is None:
        return None
    return (int(m.group(1)), int(m.group(2)))


def _parse_instance_id(text: str) -> int:
    if not text:
        return 0
    m = re.search(r"#(-?\d+)$", text.strip())
    if m is None:
        return 0
    return int(m.group(1))


def _tri(value: bool | None) -> Any:
    return NOT_EXPOSED if value is None else value


def _classify(row: dict[str, Any]) -> str:
    target_cell = int(row["target_cell_from_command"])
    target_x = int(row["target_x"])
    target_y = int(row["target_y"])
    target_roundtrip_ok = bool(row["target_flat_roundtrip_ok"])
    lookup_key_cell = int(row["occupancy_lookup_key_cell"])
    logical_cell = int(row["occupant_logical_cell"])
    logical_matches_target = bool(row["occupant_logical_cell_matches_target_cell"])
    grid_lookup_target_ok = _to_bool(row["grid_lookup_by_target_returns_occupant"])
    occ_map_key_ok = _to_bool(row["occupancy_map_key_matches_occupant_logical_position"])
    name_cell = int(row.get("occupant_name_cell", -1))
    previous_cell = int(row.get("occupant_cell_reported_previous", -1))

    if not target_roundtrip_ok or _xy_to_flat(target_x, target_y) != target_cell:
        return "coordinate_mapping_mismatch"

    if logical_cell < 0:
        return "not_exposed"

    if logical_cell != lookup_key_cell:
        if previous_cell == target_cell:
            return "instrumentation_wrote_target_as_occupant_cell"
        if grid_lookup_target_ok is False or occ_map_key_ok is False:
            return "stale_occupancy_map_reference"
        return "occupant_logical_position_mismatch"

    if logical_matches_target:
        if name_cell >= 0 and name_cell != logical_cell:
            return "visual_name_coordinate_mismatch"
        return "consistent_direct_occupant"

    if previous_cell == target_cell and logical_cell != target_cell:
        return "instrumentation_wrote_target_as_occupant_cell"

    if grid_lookup_target_ok is False or occ_map_key_ok is False:
        return "stale_occupancy_map_reference"

    if logical_cell != target_cell:
        return "occupant_logical_position_mismatch"

    return "unknown_inconsistent"


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    reports = root / "python/week6_student/reports"
    reports.mkdir(parents=True, exist_ok=True)

    source_trace_path = reports / "stage10d21b4r_direct_occupancy_attribution_trace.jsonl"
    source_report_path = reports / "stage10d21b4r_direct_occupancy_attribution_report.json"
    if not source_trace_path.exists() or not source_report_path.exists():
        raise RuntimeError("Missing Stage10D.21B4R artifacts. Expected direct occupancy trace and report.")

    source_trace = _read_jsonl(source_trace_path)
    source_report = _read_json(source_report_path)

    expected_command_ids = [
        str(item["command_id"])
        for item in source_report.get("required_answers", {}).get("q1_for_each_command_source_and_target", [])
    ]
    if len(expected_command_ids) != 4:
        raise RuntimeError("Expected exactly 4 commands from Stage10D.21B4R report.")

    source_by_cmd = {str(row.get("command_id")): row for row in source_trace}

    out_rows: list[dict[str, Any]] = []
    bucket_counts: Counter[str] = Counter()

    for cmd in expected_command_ids:
        src = source_by_cmd.get(cmd)
        if src is None:
            raise RuntimeError(f"Missing source trace row for command {cmd}")

        target_cell = int(src.get("target_cell_from_command", -1) or -1)
        target_x = int(src.get("target_x_from_command", -1) or -1)
        target_y = int(src.get("target_y_from_command", -1) or -1)

        source_cell = int(src.get("source_cell_from_command", -1) or -1)
        source_x = int(src.get("source_x_from_command", -1) or -1)
        source_y = int(src.get("source_y_from_command", -1) or -1)
        move_dir = int(src.get("move_dir", -1) or -1)

        target_flat_roundtrip_ok = _xy_to_flat(target_x, target_y) == target_cell
        source_flat_roundtrip_ok = _xy_to_flat(source_x, source_y) == source_cell

        dir_map = {0: (0, 1), 1: (1, 0), 2: (0, -1), 3: (-1, 0)}
        dx, dy = dir_map.get(move_dir, (0, 0))
        reconstructed_target = _xy_to_flat(source_x + dx, source_y + dy)
        reconstructed_target_matches = reconstructed_target == target_cell

        occupancy_lookup_key_cell = int(src.get("occupancy_lookup_key_cell", target_cell) or target_cell)
        occupancy_lookup_key_x = int(src.get("occupancy_lookup_key_x", target_x) or target_x)
        occupancy_lookup_key_y = int(src.get("occupancy_lookup_key_y", target_y) or target_y)

        try_get_occupant_result = _to_bool(src.get("try_get_occupant_result"))
        occupant_ref_exists = _to_bool(src.get("occupant_ref_exists"))

        occupant_name = str(src.get("occupant_name") or src.get("occupant_id_at_target") or "")
        occupant_instance_id = int(src.get("occupant_instance_id", 0) or 0)
        if occupant_instance_id == 0:
            occupant_instance_id = _parse_instance_id(occupant_name)

        occupant_owner = str(src.get("occupant_owner_at_target") or NOT_EXPOSED)
        occupant_type = str(src.get("occupant_type_at_target") or NOT_EXPOSED)

        occupant_logical_x = int(src.get("occupant_logical_x", src.get("occupant_x_at_target", -1)) or -1)
        occupant_logical_y = int(src.get("occupant_logical_y", src.get("occupant_y_at_target", -1)) or -1)
        occupant_logical_cell = int(src.get("occupant_logical_cell", src.get("occupant_cell_at_target", -1)) or -1)

        occupant_logical_cell_roundtrip_ok = (
            occupant_logical_cell >= 0
            and _xy_to_flat(occupant_logical_x, occupant_logical_y) == occupant_logical_cell
        )
        occupant_logical_cell_matches_lookup_key = occupant_logical_cell == occupancy_lookup_key_cell
        occupant_logical_cell_matches_target_cell = occupant_logical_cell == target_cell

        occupant_transform_x_raw = src.get("occupant_transform_x", math.nan)
        occupant_transform_y_raw = src.get("occupant_transform_y", math.nan)
        occupant_transform_x = float(occupant_transform_x_raw) if occupant_transform_x_raw is not None else math.nan
        occupant_transform_y = float(occupant_transform_y_raw) if occupant_transform_y_raw is not None else math.nan

        occupant_visual_grid_x = int(src.get("occupant_visual_grid_x", -1) or -1)
        occupant_visual_grid_y = int(src.get("occupant_visual_grid_y", -1) or -1)
        occupant_visual_cell = int(src.get("occupant_visual_cell", -1) or -1)
        if occupant_visual_cell < 0 and occupant_visual_grid_x >= 0 and occupant_visual_grid_y >= 0:
            occupant_visual_cell = _xy_to_flat(occupant_visual_grid_x, occupant_visual_grid_y)

        if occupant_visual_cell >= 0:
            occupant_visual_cell_matches_logical_cell = occupant_visual_cell == occupant_logical_cell
        else:
            occupant_visual_cell_matches_logical_cell = _to_bool(src.get("occupant_visual_cell_matches_logical_cell"))

        grid_lookup_by_target_returns_occupant = _to_bool(src.get("grid_lookup_by_target_returns_occupant"))
        if grid_lookup_by_target_returns_occupant is None:
            grid_lookup_by_target_returns_occupant = _to_bool(src.get("target_occupied_by_runtime_lookup"))

        grid_lookup_by_occupant_logical_cell_returns_same_occupant = _to_bool(
            src.get("grid_lookup_by_occupant_logical_cell_returns_same_occupant")
        )
        grid_lookup_by_occupant_visual_cell_returns_same_occupant = _to_bool(
            src.get("grid_lookup_by_occupant_visual_cell_returns_same_occupant")
        )
        occupancy_map_key_matches_occupant_logical_position = _to_bool(
            src.get("occupancy_map_key_matches_occupant_logical_position")
        )

        target_occupied_by_runtime_lookup = _to_bool(src.get("target_occupied_by_runtime_lookup"))
        target_occupied_at_reject = _to_bool(src.get("target_occupied_at_reject"))

        occupant_cell_reported_previous = int(
            src.get("occupant_cell_reported_previous", src.get("occupant_cell_at_target", -1)) or -1
        )

        parsed_name_xy = _parse_name_coords(occupant_name)
        occupant_name_cell = -1
        if parsed_name_xy is not None:
            occupant_name_cell = _xy_to_flat(parsed_name_xy[0], parsed_name_xy[1])

        row = {
            "command_id": cmd,
            "source_cell": source_cell,
            "source_x": source_x,
            "source_y": source_y,
            "target_cell_from_command": target_cell,
            "target_x": target_x,
            "target_y": target_y,
            "move_dir": move_dir,
            "target_flat_roundtrip_ok": target_flat_roundtrip_ok,
            "reconstructed_target_from_source_and_move_dir": reconstructed_target,
            "reconstructed_target_matches_command_target": reconstructed_target_matches,
            "occupancy_lookup_method": str(src.get("occupancy_lookup_method") or NOT_EXPOSED),
            "occupancy_lookup_key_cell": occupancy_lookup_key_cell,
            "occupancy_lookup_key_x": occupancy_lookup_key_x,
            "occupancy_lookup_key_y": occupancy_lookup_key_y,
            "try_get_occupant_result": _tri(try_get_occupant_result),
            "occupant_ref_exists": _tri(occupant_ref_exists),
            "occupant_instance_id": occupant_instance_id,
            "occupant_name": occupant_name or NOT_EXPOSED,
            "occupant_owner": occupant_owner,
            "occupant_type": occupant_type,
            "occupant_logical_x": occupant_logical_x,
            "occupant_logical_y": occupant_logical_y,
            "occupant_logical_cell": occupant_logical_cell,
            "occupant_logical_cell_roundtrip_ok": occupant_logical_cell_roundtrip_ok,
            "occupant_logical_cell_matches_lookup_key": occupant_logical_cell_matches_lookup_key,
            "occupant_logical_cell_matches_target_cell": occupant_logical_cell_matches_target_cell,
            "occupant_transform_x": occupant_transform_x,
            "occupant_transform_y": occupant_transform_y,
            "occupant_visual_grid_x": occupant_visual_grid_x,
            "occupant_visual_grid_y": occupant_visual_grid_y,
            "occupant_visual_cell": occupant_visual_cell,
            "occupant_visual_cell_matches_logical_cell": _tri(occupant_visual_cell_matches_logical_cell),
            "grid_lookup_by_target_returns_occupant": _tri(grid_lookup_by_target_returns_occupant),
            "grid_lookup_by_occupant_logical_cell_returns_same_occupant": _tri(grid_lookup_by_occupant_logical_cell_returns_same_occupant),
            "grid_lookup_by_occupant_visual_cell_returns_same_occupant": _tri(grid_lookup_by_occupant_visual_cell_returns_same_occupant),
            "occupancy_map_key_matches_occupant_logical_position": _tri(occupancy_map_key_matches_occupant_logical_position),
            "target_occupied_at_reject": _tri(target_occupied_at_reject),
            "target_occupied_by_runtime_lookup": _tri(target_occupied_by_runtime_lookup),
            "target_cell_from_command_duplicate": target_cell,
            "occupancy_lookup_key_cell_duplicate": occupancy_lookup_key_cell,
            "occupant_visual_name_xy": list(parsed_name_xy) if parsed_name_xy is not None else None,
            "occupant_name_cell": occupant_name_cell,
            "occupant_cell_reported_previous": occupant_cell_reported_previous,
            "source_flat_roundtrip_ok": source_flat_roundtrip_ok,
            "occupant_cell_reported_previous_matches_target": occupant_cell_reported_previous == target_cell,
        }

        bucket = _classify(row)
        row["consistency_bucket"] = bucket
        bucket_counts[bucket] += 1
        out_rows.append(row)

    if len(out_rows) != 4:
        raise RuntimeError("Expected exactly 4 command rows in Stage10D.21B4R-S trace")

    command_ids = [row["command_id"] for row in out_rows]
    unique_ids = len(set(command_ids)) == 4

    for row in out_rows:
        if row["consistency_bucket"] not in REQUIRED_BUCKETS:
            raise RuntimeError(f"Unexpected consistency bucket: {row['consistency_bucket']}")

    all_logical_match_target = all(bool(row["occupant_logical_cell_matches_target_cell"]) for row in out_rows)
    any_logical_mismatch = any(not bool(row["occupant_logical_cell_matches_target_cell"]) for row in out_rows)
    any_instrumentation_bucket = any(
        row["consistency_bucket"] == "instrumentation_wrote_target_as_occupant_cell"
        for row in out_rows
    )

    if any_instrumentation_bucket:
        stage10d21b5_gate = "FIX_B4R_INSTRUMENTATION_AND_RERUN_DIRECT_OCCUPANCY_PROOF"
    elif all_logical_match_target:
        stage10d21b5_gate = "GO_FOR_STAGE10D21B5_DYNAMIC_OCCUPANCY_MASK_ENRICHMENT"
    elif any_logical_mismatch:
        stage10d21b5_gate = "HOLD_STAGE10D21B5_AND_FIX_GRIDMANAGER_OCCUPANCY_OR_INSTRUMENTATION"
    else:
        stage10d21b5_gate = "HOLD_STAGE10D21B5_AND_FIX_GRIDMANAGER_OCCUPANCY_OR_INSTRUMENTATION"

    is_player2_occupied_targets = all(
        row["target_occupied_by_runtime_lookup"] is True
        and row["occupant_owner"] == "Player2"
        and row["occupant_logical_cell"] == row["target_cell_from_command"]
        for row in out_rows
    )

    target_occupied_real_and_consistent_raw = all_logical_match_target and all(
        row["target_occupied_by_runtime_lookup"] is True for row in out_rows
    )

    target_occupied_real_but_exported_incorrectly = any(
        row["consistency_bucket"] in {
            "instrumentation_wrote_target_as_occupant_cell",
            "visual_name_coordinate_mismatch",
        }
        for row in out_rows
    )

    gridmanager_stale_or_wrong = any(
        row["consistency_bucket"] in {
            "stale_occupancy_map_reference",
            "occupant_logical_position_mismatch",
        }
        for row in out_rows
    )

    evidence_inconclusive = any(
        row["consistency_bucket"] in {"not_exposed", "unknown_inconsistent"}
        for row in out_rows
    )

    answers = {
        "q1_for_each_command_target_cell_queried": {
            row["command_id"]: row["target_cell_from_command"] for row in out_rows
        },
        "q2_what_occupant_trygetoccupant_returned": {
            row["command_id"]: {
                "occupant_name": row["occupant_name"],
                "occupant_instance_id": row["occupant_instance_id"],
                "occupant_owner": row["occupant_owner"],
                "occupant_type": row["occupant_type"],
            }
            for row in out_rows
        },
        "q3_occupant_actual_logical_coordinates_and_cell": {
            row["command_id"]: {
                "logical_x": row["occupant_logical_x"],
                "logical_y": row["occupant_logical_y"],
                "logical_cell": row["occupant_logical_cell"],
            }
            for row in out_rows
        },
        "q4_does_occupant_logical_flat_equal_target_cell": {
            row["command_id"]: row["occupant_logical_cell_matches_target_cell"]
            for row in out_rows
        },
        "q5_does_occupant_logical_flat_equal_previous_occupant_cell_at_target": {
            row["command_id"]: row["occupant_logical_cell"] == row["occupant_cell_reported_previous"]
            for row in out_rows
        },
        "q6_did_instrumentation_accidentally_write_target_as_occupant_cell": any_instrumentation_bucket,
        "q7_is_gridmanager_occupancy_map_internally_consistent": not gridmanager_stale_or_wrong,
        "q8_are_player2_units_actually_occupying_39_42_43_46": is_player2_occupied_targets,
        "q9_stage10d21b5_status": stage10d21b5_gate,
        "q10_stage10d21c_status": "NO-GO",
    }

    bucket_map = {name: 0 for name in REQUIRED_BUCKETS}
    for name, value in bucket_counts.items():
        bucket_map[name] = int(value)

    acceptance_pass = unique_ids and sum(bucket_map.values()) == 4 and all(v in {0, 1, 2, 3, 4} for v in bucket_map.values())

    if gridmanager_stale_or_wrong:
        primary_conclusion = "gridmanager_occupancy_stale_or_wrong"
    elif evidence_inconclusive:
        primary_conclusion = "evidence_inconclusive"
    elif target_occupied_real_but_exported_incorrectly:
        primary_conclusion = "target_occupied_real_but_occupant_attribution_exported_incorrectly"
    elif target_occupied_real_and_consistent_raw:
        primary_conclusion = "target_occupied_is_real_and_consistent"
    else:
        primary_conclusion = "evidence_inconclusive"

    report = {
        "generated_at_utc": _utc_now(),
        "stage": "Stage10D.21B4R-S",
        "source_stage": "Stage10D.21B4R fresh rerun",
        "counts": {
            "commands_analyzed": len(out_rows),
            "consistency_bucket_counts": bucket_map,
        },
        "consistency_buckets": REQUIRED_BUCKETS,
        "commands": out_rows,
        "required_answers": answers,
        "adjudication": {
            "primary_conclusion": primary_conclusion,
            "target_occupied_is_real_and_consistent": primary_conclusion == "target_occupied_is_real_and_consistent",
            "target_occupied_real_but_occupant_attribution_exported_incorrectly": primary_conclusion == "target_occupied_real_but_occupant_attribution_exported_incorrectly",
            "gridmanager_occupancy_is_stale_or_wrong": primary_conclusion == "gridmanager_occupancy_stale_or_wrong",
            "evidence_inconclusive": primary_conclusion == "evidence_inconclusive",
        },
        "go_no_go": {
            "stage10d21b4r_s_occupant_coordinate_consistency_audit": "PASS" if acceptance_pass else "FAIL",
            "stage10d21b5_dynamic_occupancy_mask_enrichment": stage10d21b5_gate,
            "stage10d21c": "NO-GO",
        },
    }

    trace_out = reports / "stage10d21b4r_s_occupant_coordinate_consistency_trace.jsonl"
    report_out = reports / "stage10d21b4r_s_occupant_coordinate_consistency_report.json"
    md_out = reports / "STAGE10D21B4R_S_OCCUPANT_COORDINATE_CONSISTENCY_REPORT.md"

    with trace_out.open("w", encoding="utf-8") as fh:
        for row in out_rows:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")

    report_out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# STAGE10D21B4R-S Occupant Coordinate Consistency Audit",
        "",
        f"- Generated (UTC): {report['generated_at_utc']}",
        f"- Commands analyzed: {report['counts']['commands_analyzed']}",
        f"- Audit gate: {report['go_no_go']['stage10d21b4r_s_occupant_coordinate_consistency_audit']}",
        f"- Stage10D.21B5 gate: {report['go_no_go']['stage10d21b5_dynamic_occupancy_mask_enrichment']}",
        f"- Stage10D.21C gate: {report['go_no_go']['stage10d21c']}",
        "",
        "## Consistency Buckets",
    ]

    for bucket in REQUIRED_BUCKETS:
        lines.append(f"- {bucket}: {bucket_map[bucket]}")

    lines.extend(
        [
            "",
            "## Final Answers",
            f"- Q1 target cell queried by command: {json.dumps(answers['q1_for_each_command_target_cell_queried'], ensure_ascii=True)}",
            f"- Q2 TryGetOccupant result object: {json.dumps(answers['q2_what_occupant_trygetoccupant_returned'], ensure_ascii=True)}",
            f"- Q3 occupant logical coordinates/flat: {json.dumps(answers['q3_occupant_actual_logical_coordinates_and_cell'], ensure_ascii=True)}",
            f"- Q4 logical flat equals target: {json.dumps(answers['q4_does_occupant_logical_flat_equal_target_cell'], ensure_ascii=True)}",
            f"- Q5 logical flat equals previous occupant_cell_at_target: {json.dumps(answers['q5_does_occupant_logical_flat_equal_previous_occupant_cell_at_target'], ensure_ascii=True)}",
            f"- Q6 instrumentation wrote target as occupant cell: {answers['q6_did_instrumentation_accidentally_write_target_as_occupant_cell']}",
            f"- Q7 GridManager occupancy consistency: {answers['q7_is_gridmanager_occupancy_map_internally_consistent']}",
            f"- Q8 Player2 actually occupies 39/42/43/46: {answers['q8_are_player2_units_actually_occupying_39_42_43_46']}",
            f"- Q9 Stage10D.21B5 status: {answers['q9_stage10d21b5_status']}",
            f"- Q10 Stage10D.21C status: {answers['q10_stage10d21c_status']}",
            "",
            "## Adjudication",
            f"- target_occupied is real and consistent: {report['adjudication']['target_occupied_is_real_and_consistent']}",
            f"- target_occupied is real but attribution exported incorrectly: {report['adjudication']['target_occupied_real_but_occupant_attribution_exported_incorrectly']}",
            f"- GridManager occupancy is stale/wrong: {report['adjudication']['gridmanager_occupancy_is_stale_or_wrong']}",
            f"- evidence remains inconclusive: {report['adjudication']['evidence_inconclusive']}",
            "",
            "## Artifacts",
            f"- Trace: {trace_out.relative_to(root).as_posix()}",
            f"- JSON report: {report_out.relative_to(root).as_posix()}",
            f"- Markdown report: {md_out.relative_to(root).as_posix()}",
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
                "gate": report["go_no_go"]["stage10d21b4r_s_occupant_coordinate_consistency_audit"],
                "gate21b5": report["go_no_go"]["stage10d21b5_dynamic_occupancy_mask_enrichment"],
                "gate21c": report["go_no_go"]["stage10d21c"],
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
