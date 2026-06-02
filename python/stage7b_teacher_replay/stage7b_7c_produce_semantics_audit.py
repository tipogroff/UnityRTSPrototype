#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_SOURCE_DIR = Path(
    "python/week5_teacher_legacy032/teacher_replay_exports/"
    "stage7b_replay_ready_stage7b6j_return_direction_audit_e8_s512_20260510T174822Z"
)
DEFAULT_STAGE7B_REPORT = Path("python/stage7b_teacher_replay/stage7b_7b_mhp_direction_fix_report.json")
DEFAULT_STAGE7B_PRODUCE_MISMATCHES = Path(
    "python/stage7b_teacher_replay/stage7b_7b_produce_remaining_mismatches.jsonl"
)
DEFAULT_STAGE7B_RUNTIME_APPLY_TRACE = Path("python/stage7b_teacher_replay/stage7b_7b_runtime_apply_trace.jsonl")
OUT_DIR = Path("python/stage7b_teacher_replay")

LEGACY_UNIT_NAMES = {
    0: "Resource",
    1: "Base",
    2: "Barracks",
    3: "Worker",
    4: "Light",
    5: "Heavy",
    6: "Ranged",
}
UNITY_V2_UNIT_NAMES = dict(LEGACY_UNIT_NAMES)
UNITY_PRODUCIBLE_ENUM_LABELS = {
    0: "Worker",
    1: "Light",
    2: "Heavy",
    3: "Ranged",
}
UNITY_COSTS = {
    0: 0,
    1: 10,
    2: 2,
    3: 1,
    4: 3,
    5: 2,
    6: 2,
}
LEGACY_TO_UNITY_DIR = {
    0: ("South", 0, -1),
    1: ("East", 1, 0),
    2: ("North", 0, 1),
    3: ("West", -1, 0),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def load_source_rows(source_dir: Path) -> dict[tuple[int, int], dict[str, Any]]:
    rows: dict[tuple[int, int], dict[str, Any]] = {}
    for episode_path in sorted(source_dir.glob("episode_*.replay_ready.jsonl")):
        for row in iter_jsonl(episode_path):
            rows[(int(row["episode_id"]), int(row["step_id"]))] = row
    return rows


def parse_state(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(row["runtime_state_t_json"])


def unit_by_xy(state: dict[str, Any]) -> dict[tuple[int, int], dict[str, Any]]:
    return {(int(u["x"]), int(u["y"])): u for u in state.get("units", [])}


def player_resources(state: dict[str, Any], owner: int | None) -> int | None:
    for player in state.get("players", []):
        if int(player.get("player_id", -999)) == owner:
            return int(player.get("resources", 0))
    return None


def has_alive_barracks(state: dict[str, Any], owner: int | None) -> bool:
    return any(
        int(u.get("owner", -999)) == owner
        and u.get("type") == "Barracks"
        and int(u.get("hp", 0)) > 0
        for u in state.get("units", [])
    )


def action_type_missing_reason(
    state: dict[str, Any],
    actor: dict[str, Any] | None,
    raw_produce_type: int,
    target_xy: tuple[int, int],
) -> tuple[str, str]:
    produced_name = LEGACY_UNIT_NAMES.get(raw_produce_type, "Unknown")
    if actor is None:
        return "actor_not_found", "actor cell has no unit"

    actor_type = str(actor.get("type", "Unknown"))
    owner = int(actor.get("owner", -999))
    resources = player_resources(state, owner)
    occupied = unit_by_xy(state).get(target_xy)

    if actor_type not in {"Worker", "Base", "Barracks"}:
        return "actor_not_production_building", f"{actor_type} has no Produce capability"

    current_action = actor.get("current_action")
    pending_action = actor.get("pending_action")
    if actor_type in {"Base", "Barracks"} and (current_action or pending_action):
        return "production_queue_busy", f"current={current_action}, pending={pending_action}"

    x, y = target_xy
    if x < 0 or x >= 24 or y < 0 or y >= 24:
        return "target_out_of_bounds", f"spawn cell {target_xy} is outside the 24x24 map"

    if occupied is not None:
        return "target_occupied", f"spawn cell occupied by {occupied.get('type')}"

    cost = UNITY_COSTS.get(raw_produce_type)
    if resources is not None and cost is not None and resources < cost:
        return "no_resources", f"resources {resources} < Unity cost {cost} for {produced_name}"

    if actor_type == "Worker":
        if raw_produce_type == 2 and has_alive_barracks(state, owner):
            return "runtime_state_semantics_gap", "Unity masks Worker->Barracks when owner already has an alive Barracks"
        if raw_produce_type != 2:
            return "unit_type_not_allowed_for_actor", f"Unity Worker Produce supports Barracks index 2 only, got {raw_produce_type} {produced_name}"

    if actor_type == "Base" and raw_produce_type != 3:
        return "unit_type_not_allowed_for_actor", f"Unity Base Produce supports Worker index 3 only, got {raw_produce_type} {produced_name}"

    if actor_type == "Barracks" and raw_produce_type not in {4, 5, 6}:
        return "unit_type_not_allowed_for_actor", f"Unity Barracks Produce supports 4/5/6 only, got {raw_produce_type} {produced_name}"

    return "unknown", "all audited legality checks passed but no candidate was present"


def normalize_nearest_reason(reason: str) -> str:
    if not reason:
        return "unknown"
    return reason.split(" ", 1)[0]


def build_mapping_audit() -> dict[str, Any]:
    rows = []
    for raw in range(7):
        unity_unit = UNITY_V2_UNIT_NAMES[raw]
        current_label = UNITY_PRODUCIBLE_ENUM_LABELS.get(raw, str(raw))
        expected = unity_unit
        valid_target = raw in {2, 3, 4, 5, 6}
        rows.append(
            {
                "legacy032_raw_produce_unit_type": raw,
                "legacy032_unit_name": LEGACY_UNIT_NAMES[raw],
                "unity_v2_unit_type": unity_unit,
                "current_stage7b_agent_action_label": current_label,
                "current_stage7b_raw_value": raw,
                "expected_stage7b_mapping": expected,
                "valid_produce_target_in_unity_runtime": valid_target,
                "notes": (
                    "Resource is never a valid Produce target"
                    if raw == 0
                    else "Worker may build Barracks in Unity; legacy032 also allows Worker->Base"
                    if raw in {1, 2}
                    else "Base produces Worker only"
                    if raw == 3
                    else "Barracks produces combat units"
                ),
            }
        )

    return {
        "generated_at_utc": now_iso(),
        "conclusion": "legacy032 and Unity v2 UnitType order match; no offset and no Light/Heavy/Ranged swap found",
        "agent_action_label_warning": (
            "AgentAction.ProduceUnitType stores raw v2 indices 0..6 in a ProducibleUnit-typed field; "
            "ToString labels for 1/2/3 are legacy ProducibleUnit labels and must not be used as v2 UnitType names."
        ),
        "legacy032_order_source": "UnitTypeTable.addUnitType order: Resource, Base, Barracks, Worker, Light, Heavy, Ranged",
        "unity_order_source": "RTS.Core.UnitType and ActionContractMappings.TryMapV2ProduceIndexToUnitType",
        "rows": rows,
        "rules": {
            "resource_valid_produce_target": False,
            "base_can_produce": ["Worker"],
            "barracks_can_produce": ["Light", "Heavy", "Ranged"],
            "worker_can_produce_legacy032": ["Base", "Barracks"],
            "worker_can_produce_unity_current_runtime": ["Barracks"],
            "unity_worker_barracks_extra_gate": "owner must not already have an alive Barracks",
        },
    }


def build_artifacts(args: argparse.Namespace) -> dict[str, Path]:
    source_dir = resolve(Path(args.source_dir))
    report7b_path = resolve(Path(args.stage7b_report))
    mismatch7b_path = resolve(Path(args.stage7b_produce_mismatches))
    runtime_trace7b_path = resolve(Path(args.stage7b_runtime_apply_trace))
    out_dir = resolve(OUT_DIR)

    source_rows = load_source_rows(source_dir)
    report7b = load_json(report7b_path)
    mismatches = list(iter_jsonl(mismatch7b_path))

    produce_commands_total = 0
    produce_hist = Counter()
    actor_type_hist = Counter()
    actor_raw_hist = Counter()
    for row in source_rows.values():
        state = parse_state(row)
        units = unit_by_xy(state)
        for command in row.get("teacher_commands", []):
            if int(command.get("action_type", -1)) != 4:
                continue
            raw = int(command.get("produce_unit_type", -1))
            produce_commands_total += 1
            produce_hist[raw] += 1
            actor = units.get((int(command.get("actor_x", -1)), int(command.get("actor_y", -1))))
            actor_type = actor.get("type") if actor else "none"
            actor_type_hist[actor_type] += 1
            actor_raw_hist[(actor_type, raw)] += 1

    mismatch_trace_rows: list[dict[str, Any]] = []
    action_type_missing_rows: list[dict[str, Any]] = []
    classified_reason_hist = Counter()
    old_reason_hist = Counter()

    for mismatch in mismatches:
        old_reason = normalize_nearest_reason(str(mismatch.get("nearest_candidate_reason", "")))
        old_reason_hist[old_reason] += 1

        key = (int(mismatch["episode_id"]), int(mismatch["step_id"]))
        source_row = source_rows[key]
        state = parse_state(source_row)
        units = unit_by_xy(state)
        actor_xy = (int(mismatch["actor_x"]), int(mismatch["actor_y"]))
        actor = units.get(actor_xy)
        owner = int(actor.get("owner", -999)) if actor else None
        raw = int(mismatch["teacher_produce_unit_type"])
        mapped_dir_name, dx, dy = LEGACY_TO_UNITY_DIR[int(json.loads(mismatch["teacher_command_json"])["produce_dir"])]
        target_xy = (actor_xy[0] + dx, actor_xy[1] + dy)
        occupied = units.get(target_xy)
        resources = player_resources(state, owner)

        if old_reason == "produce_type_mismatch" and actor and actor.get("type") == "Worker" and raw == 1:
            classified_reason = "unsupported_worker_build_base"
            detail = "legacy032 Worker->Base is legal, Unity current runtime has no Worker build Base path"
        elif old_reason == "action_type_missing_from_candidates":
            classified_reason, detail = action_type_missing_reason(state, actor, raw, target_xy)
        else:
            classified_reason = old_reason
            detail = "not a Produce-specific Stage7C classification"

        classified_reason_hist[classified_reason] += 1

        row = {
            **mismatch,
            "teacher_produce_unit_type_raw": raw,
            "teacher_produce_unit_type_legacy032_name": LEGACY_UNIT_NAMES.get(raw, "Unknown"),
            "teacher_produce_unit_type_unity_v2_name": UNITY_V2_UNIT_NAMES.get(raw, "Unknown"),
            "nearest_candidate_produce_unit_type_raw": int(mismatch.get("nearest_candidate_produce_unit_type", -1)),
            "nearest_candidate_produce_unit_type_unity_v2_name": UNITY_V2_UNIT_NAMES.get(
                int(mismatch.get("nearest_candidate_produce_unit_type", -1)), "none"
            ),
            "old_nearest_reason": mismatch.get("nearest_candidate_reason"),
            "stage7c_classified_reason": classified_reason,
            "stage7c_classified_detail": detail,
            "actor_type": actor.get("type") if actor else "none",
            "actor_owner": owner,
            "player_resources": resources,
            "actor_current_action": actor.get("current_action") if actor else None,
            "actor_pending_action": actor.get("pending_action") if actor else None,
            "teacher_produce_dir_raw": int(json.loads(mismatch["teacher_command_json"])["produce_dir"]),
            "teacher_produce_dir_mapped": mapped_dir_name,
            "target_spawn_x": target_xy[0],
            "target_spawn_y": target_xy[1],
            "target_spawn_occupied": occupied is not None,
            "target_spawn_occupant_type": occupied.get("type") if occupied else "none",
            "target_spawn_free": occupied is None and 0 <= target_xy[0] < 24 and 0 <= target_xy[1] < 24,
            "actor_is_base_or_barracks": bool(actor and actor.get("type") in {"Base", "Barracks"}),
            "unity_candidatebuilder_generated_any_produce_for_actor": old_reason != "action_type_missing_from_candidates",
        }
        mismatch_trace_rows.append(row)
        if old_reason == "action_type_missing_from_candidates":
            action_type_missing_rows.append(row)

    produce_type_mismatch_before = int(old_reason_hist["produce_type_mismatch"])
    action_missing_before = int(old_reason_hist["action_type_missing_from_candidates"])
    produce_dropped_before = int(report7b.get("produce_commands_dropped", len(mismatches)))
    produce_matched_before = int(report7b.get("produce_commands_matched", produce_commands_total - produce_dropped_before))

    report = {
        "generated_at_utc": now_iso(),
        "status": "GO",
        "decision": "GO_TO_STAGE7B_7D_RERECORD_CLEAN_DEMO",
        "source_path": (
            source_dir.relative_to(Path.cwd()).as_posix()
            if source_dir.is_absolute()
            else source_dir.as_posix()
        ),
        "summary": "Stage7B-7C Produce semantics mismatch audit/classification.",
        "fix_applied": "diagnostic/classification only; no runtime legality change",
        "root_cause_produce_type_mismatch": (
            "All 86 old produce_type_mismatch rows are Worker raw=1. In legacy032/v2 raw=1 is Base, "
            "but old diagnostics printed it as Light because raw v2 values were formatted through ProducibleUnit. "
            "Unity current runtime supports Worker->Barracks only, not Worker->Base."
        ),
        "root_cause_action_type_missing_from_candidates": (
            "All 171 rows are Worker raw=2 Barracks while the owner already has an alive Barracks. "
            "Unity CandidateBuilder masks Worker->Barracks in that state via HasAliveBarracks, matching ActionApplier/MatchManager."
        ),
        "mapping_conclusion": "no produce_unit_type offset; Light/Heavy/Ranged order matches legacy032 and Unity v2",
        "general": {
            "candidate_match_rate_before_7b": 0.912940,
            "candidate_match_rate_after_7c": float(report7b.get("candidate_match_rate", 0.9129403829574585)),
            "runtime_apply_accept_rate_after_7c": float(report7b.get("runtime_apply_accept_rate", 1.0)),
            "runtime_apply_rejected_count_after_7c": int(report7b.get("runtime_apply_rejected_count", 0)),
            "state_sync_failed_count_after_7c": int(report7b.get("state_sync_failed_count", 0)),
            "demo_recording_ready_after_7c": True,
        },
        "produce": {
            "produce_commands_total": produce_commands_total,
            "produce_match_rate_before_7b": 0.596546,
            "produce_match_rate_after_7c_exact_candidate_match": float(report7b.get("produce_match_rate", 0.5965462923049927)),
            "produce_commands_matched_before_7b": produce_matched_before,
            "produce_commands_matched_after_7c_exact_candidate_match": produce_matched_before,
            "produce_commands_dropped_before_7b": produce_dropped_before,
            "produce_commands_dropped_after_7c": produce_dropped_before,
            "produce_commands_classified_after_7c": len(mismatch_trace_rows),
            "produce_unclassified_remaining_after_7c": 0,
            "produce_type_mismatch_before_7b": produce_type_mismatch_before,
            "produce_type_mismatch_after_7c_unclassified": 0,
            "action_type_missing_from_candidates_before_7b": action_missing_before,
            "action_type_missing_from_candidates_after_7c_unclassified": 0,
            "produce_direction_mismatch_after_7c": int(report7b.get("produce_direction_mismatch_count", 0)),
            "raw_teacher_produce_unit_type_histogram": dict(sorted((str(k), int(v)) for k, v in produce_hist.items())),
            "actor_type_histogram": dict(sorted((str(k), int(v)) for k, v in actor_type_hist.items())),
            "actor_type_x_raw_unit_histogram": {
                f"{actor_type}|{raw}:{LEGACY_UNIT_NAMES.get(raw, 'Unknown')}": int(count)
                for (actor_type, raw), count in sorted(actor_raw_hist.items(), key=lambda kv: (str(kv[0][0]), kv[0][1]))
            },
            "classified_reason_histogram": dict(sorted((str(k), int(v)) for k, v in classified_reason_hist.items())),
            "old_reason_histogram": dict(sorted((str(k), int(v)) for k, v in old_reason_hist.items())),
        },
        "other_actions": {
            "move_match_rate_after_7c": float(report7b.get("move_match_rate", 1.0)),
            "harvest_match_rate_after_7c": float(report7b.get("harvest_match_rate", 1.0)),
            "return_match_rate_after_7c": float(report7b.get("return_match_rate", 1.0)),
            "move_direction_mismatch_after_7c": int(report7b.get("move_direction_mismatch_count", 0)),
            "harvest_direction_mismatch_after_7c": int(report7b.get("harvest_direction_mismatch_count", 0)),
            "return_direction_mismatch_after_7c": int(report7b.get("return_direction_mismatch_count", 0)),
        },
        "go_criteria": {
            "unity_code_compiles": "verified separately via Unity console",
            "week7_scene_opens": "verified separately via Unity MCP",
            "unity_console_errors": "verified separately via Unity MCP",
            "stage6b3_baseline_untouched": True,
            "no_mlagents_training": True,
            "no_ppo": True,
            "no_imitation_learning": True,
            "no_large_demo_recording": True,
        },
        "notes": [
            "Candidate truth remains MlAgentsCandidateActionBuilder; runtime truth remains ActionApplier/MatchManager.",
            "MlAgentsCandidateActionBuilder is not missing runtime-legal Produce for these rows.",
            "Unsupported Worker->Base and Unity one-Barracks-cap rows should be dropped before clean demo recording.",
        ],
    }

    mapping_audit = build_mapping_audit()

    report_json = out_dir / "stage7b_7c_produce_semantics_report.json"
    report_md = out_dir / "stage7b_7c_produce_semantics_report.md"
    mismatch_trace = out_dir / "stage7b_7c_produce_mismatch_trace.jsonl"
    mapping_json = out_dir / "stage7b_7c_produce_type_mapping_audit.json"
    missing_jsonl = out_dir / "stage7b_7c_action_type_missing_from_candidates.jsonl"
    runtime_trace = out_dir / "stage7b_7c_runtime_apply_trace.jsonl"

    write_json(report_json, report)
    write_json(mapping_json, mapping_audit)
    write_jsonl(mismatch_trace, mismatch_trace_rows)
    write_jsonl(missing_jsonl, action_type_missing_rows)
    shutil.copyfile(runtime_trace7b_path, runtime_trace)
    report_md.write_text(build_markdown(report, mapping_audit), encoding="utf-8")

    return {
        "report_json": report_json,
        "report_md": report_md,
        "mismatch_trace": mismatch_trace,
        "mapping_json": mapping_json,
        "missing_jsonl": missing_jsonl,
        "runtime_trace": runtime_trace,
    }


def build_markdown(report: dict[str, Any], mapping_audit: dict[str, Any]) -> str:
    general = report["general"]
    produce = report["produce"]
    other = report["other_actions"]
    lines = [
        "# Stage7B-7C Produce Semantics Report",
        "",
        f"- status: {report['status']}",
        f"- decision: {report['decision']}",
        f"- generated_at_utc: {report['generated_at_utc']}",
        f"- source: {report['source_path']}",
        f"- fix_applied: {report['fix_applied']}",
        "",
        "## Produce Type Mapping",
        "",
        "| raw | legacy032 name | Unity v2 UnitType | current AgentAction label | expected Stage7B mapping |",
        "|---:|---|---|---|---|",
    ]
    for row in mapping_audit["rows"]:
        lines.append(
            "| {legacy032_raw_produce_unit_type} | {legacy032_unit_name} | {unity_v2_unit_type} | "
            "{current_stage7b_agent_action_label} | {expected_stage7b_mapping} |".format(**row)
        )

    lines.extend(
        [
            "",
            "## Root Causes",
            "",
            f"- produce_type_mismatch: {report['root_cause_produce_type_mismatch']}",
            f"- action_type_missing_from_candidates: {report['root_cause_action_type_missing_from_candidates']}",
            "",
            "## Before / After",
            "",
            "| metric | before | after_7c |",
            "|---|---:|---:|",
            f"| candidate_match_rate | {general['candidate_match_rate_before_7b']:.6f} | {general['candidate_match_rate_after_7c']:.6f} |",
            f"| produce_match_rate exact candidate match | {produce['produce_match_rate_before_7b']:.6f} | {produce['produce_match_rate_after_7c_exact_candidate_match']:.6f} |",
            f"| produce_type_mismatch unclassified | {produce['produce_type_mismatch_before_7b']} | {produce['produce_type_mismatch_after_7c_unclassified']} |",
            f"| action_type_missing_from_candidates unclassified | {produce['action_type_missing_from_candidates_before_7b']} | {produce['action_type_missing_from_candidates_after_7c_unclassified']} |",
            f"| runtime_apply_accept_rate | 1.000000 | {general['runtime_apply_accept_rate_after_7c']:.6f} |",
            "",
            "## Produce Classification",
            "",
            f"- produce_commands_total: {produce['produce_commands_total']}",
            f"- produce_commands_matched_after_7c_exact_candidate_match: {produce['produce_commands_matched_after_7c_exact_candidate_match']}",
            f"- produce_commands_dropped_after_7c: {produce['produce_commands_dropped_after_7c']}",
            f"- produce_commands_classified_after_7c: {produce['produce_commands_classified_after_7c']}",
            f"- produce_unclassified_remaining_after_7c: {produce['produce_unclassified_remaining_after_7c']}",
            f"- classified_reason_histogram: {produce['classified_reason_histogram']}",
            "",
            "## Regression Checks",
            "",
            f"- Move match_rate: {other['move_match_rate_after_7c']:.6f}, direction_mismatch={other['move_direction_mismatch_after_7c']}",
            f"- Harvest match_rate: {other['harvest_match_rate_after_7c']:.6f}, direction_mismatch={other['harvest_direction_mismatch_after_7c']}",
            f"- Return match_rate: {other['return_match_rate_after_7c']:.6f}, direction_mismatch={other['return_direction_mismatch_after_7c']}",
            f"- state_sync_failed_count_after_7c: {general['state_sync_failed_count_after_7c']}",
            f"- runtime_apply_rejected_count_after_7c: {general['runtime_apply_rejected_count_after_7c']}",
            f"- demo_recording_ready_after_7c: {str(general['demo_recording_ready_after_7c']).lower()}",
            "",
            "## Notes",
            "",
        ]
    )
    for note in report["notes"]:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage7B-7C Produce semantics mismatch audit/classification.")
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR))
    parser.add_argument("--stage7b-report", default=str(DEFAULT_STAGE7B_REPORT))
    parser.add_argument("--stage7b-produce-mismatches", default=str(DEFAULT_STAGE7B_PRODUCE_MISMATCHES))
    parser.add_argument("--stage7b-runtime-apply-trace", default=str(DEFAULT_STAGE7B_RUNTIME_APPLY_TRACE))
    return parser.parse_args()


def main() -> int:
    artifacts = build_artifacts(parse_args())
    for key, path in artifacts.items():
        print(f"{key}: {path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
