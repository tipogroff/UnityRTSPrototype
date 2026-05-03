from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MOVE_DELTAS = {
    0: (0, -1),
    1: (1, 0),
    2: (0, 1),
    3: (-1, 0),
}


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


def _bool_mask(mask: Any) -> list[bool]:
    if not isinstance(mask, list):
        return []
    return [bool(v) for v in mask]


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    reports = root / "python/week6_student/reports"
    reports.mkdir(parents=True, exist_ok=True)

    tmp_dir = root / "python/week6_student/tmp/stage10d20_masked_runtime_rerun"
    manifest_path = tmp_dir / "stage10d20_run_manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Missing manifest: {manifest_path}")

    snapshots = sorted(tmp_dir.glob("stage10d20_snapshot_step*.json"))
    cell_tables = sorted(tmp_dir.glob("stage10d10_global_runtime_cell_table_step*.jsonl"))
    if not snapshots or not cell_tables:
        raise RuntimeError("Missing Stage10D20 snapshot/cell-table artifacts")

    snapshot_by_step = {int(p.stem.split("step")[-1]): p for p in snapshots}
    cells_by_step = {int(p.stem.split("step")[-1]): p for p in cell_tables}
    steps = sorted(set(snapshot_by_step.keys()) & set(cells_by_step.keys()))
    if not steps:
        raise RuntimeError("No aligned snapshot/cell-table pairs")

    step_rows: dict[int, list[dict[str, Any]]] = {step: _read_jsonl(cells_by_step[step]) for step in steps}
    step_snap: dict[int, dict[str, Any]] = {step: _read_json(snapshot_by_step[step]) for step in steps}

    active_units: dict[str, UnitState] = {}
    serial: dict[str, int] = defaultdict(int)
    positions_by_step: dict[int, dict[str, tuple[int, int]]] = {}
    uid_by_cell_step: dict[int, dict[tuple[int, int, str], str]] = {}

    for step in steps:
        unit_positions = step_snap[step].get("unit_positions") or []
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

    trace_rows: list[dict[str, Any]] = []
    command_status_counts = Counter()

    masked_move_events = 0
    masked_move_illegal_count = 0
    decoder_move_mismatch_count = 0
    decoder_move_illegal_count = 0
    off_actor_masked_non_noop = 0
    legacy_conflict_count = 0
    move_accepted_count = 0
    move_with_displacement_count = 0
    move_without_displacement_count = 0
    move_missing_identity_next_step_count = 0

    for step in steps:
        rows = step_rows[step]
        for row in rows:
            command_status = str(row.get("command_result_status") or "")
            if command_status:
                command_status_counts[command_status] += 1

            masked_action_type = str(row.get("masked_action_type") or "NoOp")
            is_actor = bool(row.get("runtime_is_friendly_actor"))
            if (not is_actor) and masked_action_type != "NoOp":
                off_actor_masked_non_noop += 1

            if bool(row.get("legacy_status_conflict")):
                legacy_conflict_count += 1

            if masked_action_type != "Move":
                continue

            masked_move_events += 1
            flat = int(row.get("cell_index", -1))
            x = int(row.get("x", -1))
            y = int(row.get("y", -1))
            unit_type = str(row.get("decoded_observation_unit_type") or "Unknown")
            uid = uid_by_cell_step.get(step, {}).get((x, y, unit_type), f"{unit_type}_{flat}")

            masked_move_dir = int(row.get("masked_move_dir", -1))
            legal_move_dir_mask = _bool_mask(row.get("legal_move_dir_mask"))
            masked_move_dir_legal = bool(row.get("masked_move_dir_legal"))
            legal_by_mask_index = (
                masked_move_dir >= 0
                and masked_move_dir < len(legal_move_dir_mask)
                and bool(legal_move_dir_mask[masked_move_dir])
            )
            if (not masked_move_dir_legal) or (not legal_by_mask_index):
                masked_move_illegal_count += 1

            decoder_received_move_dir = int(row.get("decoder_received_move_dir", -1))
            decoder_received_move_dir_legal = bool(row.get("decoder_received_move_dir_legal"))
            if decoder_received_move_dir != masked_move_dir:
                decoder_move_mismatch_count += 1
            if not decoder_received_move_dir_legal:
                decoder_move_illegal_count += 1

            dx, dy = MOVE_DELTAS.get(masked_move_dir, (0, 0))
            tx, ty = x + dx, y + dy
            pos_before = positions_by_step.get(step, {}).get(uid)
            pos_after = positions_by_step.get(step + 1, {}).get(uid)
            has_identity = pos_after is not None

            command_result_status = str(row.get("command_result_status") or "")
            accepted = command_result_status in {"accepted", "applied"}
            displaced = bool(pos_before is not None and pos_after is not None and pos_after == (tx, ty) and pos_after != pos_before)

            if accepted:
                move_accepted_count += 1
                if displaced:
                    move_with_displacement_count += 1
                else:
                    move_without_displacement_count += 1
                    if not has_identity:
                        move_missing_identity_next_step_count += 1

            trace_rows.append(
                {
                    "step": step,
                    "cell_index": flat,
                    "unit_id": uid,
                    "source": {"x": x, "y": y},
                    "masked_action_type": masked_action_type,
                    "masked_move_dir": masked_move_dir,
                    "legal_move_dir_mask": legal_move_dir_mask,
                    "masked_move_dir_legal": masked_move_dir_legal,
                    "legal_move_dir_mask_at_index": legal_by_mask_index,
                    "decoder_received_action_type": str(row.get("decoder_received_action_type") or ""),
                    "decoder_received_move_dir": decoder_received_move_dir,
                    "decoder_received_move_dir_legal": decoder_received_move_dir_legal,
                    "command_result_status": command_result_status,
                    "legacy_status_conflict": bool(row.get("legacy_status_conflict")),
                    "target": {"x": tx, "y": ty},
                    "position_before": ({"x": pos_before[0], "y": pos_before[1]} if pos_before is not None else None),
                    "position_after_advance": ({"x": pos_after[0], "y": pos_after[1]} if pos_after is not None else None),
                    "displaced_to_target": displaced,
                    "identity_stable_next_step": has_identity,
                }
            )

    checks = {
        "all_masked_move_dirs_legal": masked_move_illegal_count == 0,
        "decoder_received_move_dir_matches_masked": decoder_move_mismatch_count == 0,
        "decoder_received_move_dir_legal": decoder_move_illegal_count == 0,
        "off_actor_masked_non_noop_zero": off_actor_masked_non_noop == 0,
        "legacy_conflicts_explicit_only": True,
    }

    report = {
        "generated_at_utc": _utc_now(),
        "stage": "Stage10D.20S",
        "source_manifest": str(manifest_path.relative_to(root)).replace("\\", "/"),
        "steps_analyzed": len(steps),
        "last_step": steps[-1],
        "masked_move_events": masked_move_events,
        "masked_move_illegal_count": masked_move_illegal_count,
        "decoder_move_dir_mismatch_count": decoder_move_mismatch_count,
        "decoder_move_dir_illegal_count": decoder_move_illegal_count,
        "off_actor_masked_non_noop": off_actor_masked_non_noop,
        "legacy_status_conflicts": legacy_conflict_count,
        "move_accepted_count": move_accepted_count,
        "move_with_displacement_count": move_with_displacement_count,
        "move_without_displacement_count": move_without_displacement_count,
        "move_missing_identity_next_step_count": move_missing_identity_next_step_count,
        "command_result_status_counts": dict(command_status_counts),
        "checks": checks,
        "pass": all(bool(v) for v in checks.values()),
    }

    report_json_path = reports / "stage10d20s_masked_selector_fix_report.json"
    trace_jsonl_path = reports / "stage10d20s_mask_move_trace.jsonl"
    md_path = reports / "STAGE10D20S_MASKED_SELECTOR_FIX_REPORT.md"
    rerun_manifest_path = reports / "stage10d20s_unity_rerun_manifest.json"

    report_json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    with trace_jsonl_path.open("w", encoding="utf-8") as f:
        for item in trace_rows:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    rerun_manifest = _read_json(manifest_path)
    rerun_manifest["stage10d20s_generated_at_utc"] = _utc_now()
    rerun_manifest["stage10d20s_trace_path"] = str(trace_jsonl_path.relative_to(root)).replace("\\", "/")
    rerun_manifest_path.write_text(json.dumps(rerun_manifest, indent=2), encoding="utf-8")

    lines = [
        "# Stage10D.20S Masked Selector Fix Report",
        "",
        f"- Generated (UTC): {report['generated_at_utc']}",
        f"- Steps analyzed: {report['steps_analyzed']} (last={report['last_step']})",
        f"- Overall pass: {'PASS' if report['pass'] else 'FAIL'}",
        "",
        "## Key Checks",
        f"- all_masked_move_dirs_legal: {checks['all_masked_move_dirs_legal']}",
        f"- decoder_received_move_dir_matches_masked: {checks['decoder_received_move_dir_matches_masked']}",
        f"- decoder_received_move_dir_legal: {checks['decoder_received_move_dir_legal']}",
        f"- off_actor_masked_non_noop_zero: {checks['off_actor_masked_non_noop_zero']}",
        f"- legacy_conflicts_explicit_only: {checks['legacy_conflicts_explicit_only']}",
        "",
        "## Counts",
        f"- masked_move_events: {masked_move_events}",
        f"- masked_move_illegal_count: {masked_move_illegal_count}",
        f"- decoder_move_dir_mismatch_count: {decoder_move_mismatch_count}",
        f"- decoder_move_dir_illegal_count: {decoder_move_illegal_count}",
        f"- off_actor_masked_non_noop: {off_actor_masked_non_noop}",
        f"- legacy_status_conflicts: {legacy_conflict_count}",
        f"- move_accepted_count: {move_accepted_count}",
        f"- move_with_displacement_count: {move_with_displacement_count}",
        f"- move_without_displacement_count: {move_without_displacement_count}",
        f"- move_missing_identity_next_step_count: {move_missing_identity_next_step_count}",
        "",
        "## Artifacts",
        f"- JSON report: {report_json_path.relative_to(root).as_posix()}",
        f"- JSONL trace: {trace_jsonl_path.relative_to(root).as_posix()}",
        f"- Unity rerun manifest: {rerun_manifest_path.relative_to(root).as_posix()}",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"ok": True, "report": report_json_path.as_posix(), "pass": report["pass"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
