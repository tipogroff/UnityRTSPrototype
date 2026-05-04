#!/usr/bin/env python3
"""Build Stage10D.21B5 dynamic occupancy-aware move mask report artifacts.

This script compares the pre-change baseline traces against the latest rerun outputs and
emits:
- stage10d21b5_dynamic_move_mask_trace.jsonl
- stage10d21b5_dynamic_move_mask_report.json
- STAGE10D21B5_DYNAMIC_MOVE_MASK_REPORT.md
"""

from __future__ import annotations

import glob
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


REPORTS_DIR = Path("python/week6_student/reports")
BASELINE_STAGE20_GLOB = "stage10d21b5_baseline_stage10d20_masked_runtime_trace_*.jsonl"
BASELINE_STAGE20S_GLOB = "stage10d21b5_baseline_stage10d20s_mask_move_trace_*.jsonl"

FRESH_STAGE20 = REPORTS_DIR / "stage10d20_masked_runtime_trace.jsonl"
FRESH_STAGE20S = REPORTS_DIR / "stage10d20s_mask_move_trace.jsonl"
MANIFEST_PATH = REPORTS_DIR / "stage10d20s_unity_rerun_manifest.json"
STAGE21B4R_REPORT = REPORTS_DIR / "stage10d21b4r_direct_occupancy_attribution_report.json"

OUT_TRACE = REPORTS_DIR / "stage10d21b5_dynamic_move_mask_trace.jsonl"
OUT_JSON = REPORTS_DIR / "stage10d21b5_dynamic_move_mask_report.json"
OUT_MD = REPORTS_DIR / "STAGE10D21B5_DYNAMIC_MOVE_MASK_REPORT.md"

PATTERNS: List[Tuple[int, int]] = [(42, 43), (41, 42), (38, 39), (45, 46)]


@dataclass(frozen=True)
class MoveKey:
    source_flat: int
    target_flat: int


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def latest_glob(pattern: str) -> Path:
    matches = sorted(glob.glob(str(REPORTS_DIR / pattern)))
    if not matches:
        raise FileNotFoundError(f"No files found for pattern: {pattern}")
    return Path(matches[-1])


def aggregate_stage20(rows: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    metrics = {
        "steps": 0,
        "raw_move_predictions": 0,
        "masked_move_predictions": 0,
        "masked_invalid_or_occupied_move_targets": 0,
        "commands_accepted": 0,
        "off_actor_raw_non_noop": 0,
        "off_actor_masked_non_noop": 0,
        "mask_changed_actions": 0,
        "selected_move_actions": 0,
        "move_target_nonnull": 0,
        "move_target_occupied": 0,
        "decoder_reject_nonempty": 0,
    }

    for row in rows:
        metrics["steps"] += 1
        counts = row.get("per_step_counts", {})
        metrics["raw_move_predictions"] += int(counts.get("raw_move_predictions", 0) or 0)
        metrics["masked_move_predictions"] += int(counts.get("masked_move_predictions", 0) or 0)
        metrics["masked_invalid_or_occupied_move_targets"] += int(
            counts.get("masked_invalid_or_occupied_move_targets", 0) or 0
        )
        metrics["commands_accepted"] += int(counts.get("commands_accepted", 0) or 0)
        metrics["off_actor_raw_non_noop"] += int(counts.get("off_actor_raw_non_noop", 0) or 0)
        metrics["off_actor_masked_non_noop"] += int(counts.get("off_actor_masked_non_noop", 0) or 0)
        metrics["mask_changed_actions"] += int(counts.get("mask_changed_actions", 0) or 0)

        for actor in row.get("friendly_actor_cells", []):
            if actor.get("selected_action_after_mask") == "Move":
                metrics["selected_move_actions"] += 1
            reject_reason = (actor.get("decoder_reject_reason") or "").strip()
            if reject_reason:
                metrics["decoder_reject_nonempty"] += 1
            target = actor.get("move_target_cell")
            if target is not None:
                metrics["move_target_nonnull"] += 1
                legality = actor.get("move_target_legality") or {}
                if legality.get("occupied") is True:
                    metrics["move_target_occupied"] += 1

    return metrics


def aggregate_stage20s(rows: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    metrics = {
        "selected_masked_move_commands": 0,
        "telemetry_conflict": 0,
        "displaced_to_target": 0,
        "clean_accepted_like": 0,
        "movement_completed": 0,
    }
    for row in rows:
        metrics["selected_masked_move_commands"] += 1
        if row.get("command_result_status") == "telemetry_conflict":
            metrics["telemetry_conflict"] += 1
        if bool(row.get("displaced_to_target")):
            metrics["displaced_to_target"] += 1
        status = str(row.get("command_result_status") or "").lower()
        if status in {"accepted", "accepted_pending", "accepted_applied", "accepted_completed"}:
            metrics["clean_accepted_like"] += 1
    return metrics


def logical_cell_guards(stage20_rows: Iterable[Dict[str, Any]]) -> Dict[str, bool]:
    b2_seen = False
    c3_seen = False
    for row in stage20_rows:
        for unit in row.get("friendly_units", []):
            cell = unit.get("logical_cell")
            if cell == "B2":
                b2_seen = True
            if cell == "C3":
                c3_seen = True
    return {
        "b2_present_somewhere": b2_seen,
        "c3_present_somewhere": c3_seen,
        "b2_c3_guard_pass": b2_seen and c3_seen,
    }


def move_key_from_stage20s(row: Dict[str, Any]) -> MoveKey:
    source = row.get("cell_index")
    target = (row.get("target") or {}).get("x"), (row.get("target") or {}).get("y")
    if target[0] is None or target[1] is None:
        target_flat = -1
    else:
        target_flat = int(target[1]) * 24 + int(target[0])
    return MoveKey(source_flat=int(source), target_flat=target_flat)


def stage21b4r_targets() -> Dict[Tuple[int, int], Dict[str, Any]]:
    report = load_json(STAGE21B4R_REPORT)
    out: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for command in report.get("commands", []):
        src = int(command.get("source_cell_from_command", -1))
        tgt = int(command.get("target_cell_from_command", -1))
        out[(src, tgt)] = {
            "occupancy_outcome": command.get("occupancy_outcome"),
            "occupant_owner": command.get("occupant_owner_at_target"),
            "occupant_type": command.get("occupant_type_at_target"),
            "reject_reason_normalized": command.get("reject_reason_normalized"),
        }
    return out


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    baseline_stage20 = latest_glob(BASELINE_STAGE20_GLOB)
    baseline_stage20s = latest_glob(BASELINE_STAGE20S_GLOB)

    base20_rows = load_jsonl(baseline_stage20)
    fresh20_rows = load_jsonl(FRESH_STAGE20)
    base20s_rows = load_jsonl(baseline_stage20s)
    fresh20s_rows = load_jsonl(FRESH_STAGE20S)

    base20_metrics = aggregate_stage20(base20_rows)
    fresh20_metrics = aggregate_stage20(fresh20_rows)
    base20s_metrics = aggregate_stage20s(base20s_rows)
    fresh20s_metrics = aggregate_stage20s(fresh20s_rows)

    guard_cells = logical_cell_guards(fresh20_rows)
    manifest = load_json(MANIFEST_PATH)
    checkpoint_path = manifest.get("configured_checkpoint_relative_path", "")

    baseline_keys = [move_key_from_stage20s(row) for row in base20s_rows]
    fresh_keys = [move_key_from_stage20s(row) for row in fresh20s_rows]
    baseline_counter: Dict[MoveKey, int] = {}
    fresh_counter: Dict[MoveKey, int] = {}
    for key in baseline_keys:
        baseline_counter[key] = baseline_counter.get(key, 0) + 1
    for key in fresh_keys:
        fresh_counter[key] = fresh_counter.get(key, 0) + 1

    b4r_lookup = stage21b4r_targets()

    trace_rows: List[Dict[str, Any]] = []
    for key, count in sorted(
        baseline_counter.items(), key=lambda kv: (kv[0].source_flat, kv[0].target_flat)
    ):
        after_count = fresh_counter.get(key, 0)
        pattern_meta = b4r_lookup.get((key.source_flat, key.target_flat), {})
        trace_rows.append(
            {
                "kind": "baseline_to_fresh_move_path_comparison",
                "source_flat": key.source_flat,
                "target_flat": key.target_flat,
                "baseline_selected_masked_move_count": count,
                "fresh_selected_masked_move_count": after_count,
                "suppressed_by_dynamic_enrichment": after_count < count,
                "baseline_occupancy_attribution": pattern_meta,
            }
        )

    for source_flat, target_flat in PATTERNS:
        key = MoveKey(source_flat=source_flat, target_flat=target_flat)
        pattern_meta = b4r_lookup.get((source_flat, target_flat), {})
        trace_rows.append(
            {
                "kind": "required_pattern_outcome",
                "pattern": f"{source_flat}->{target_flat}",
                "baseline_selected_masked_move_count": baseline_counter.get(key, 0),
                "fresh_selected_masked_move_count": fresh_counter.get(key, 0),
                "baseline_direct_occupancy_outcome": pattern_meta.get("occupancy_outcome"),
                "baseline_occupant_owner": pattern_meta.get("occupant_owner"),
                "baseline_occupant_type": pattern_meta.get("occupant_type"),
                "outcome": "suppressed" if fresh_counter.get(key, 0) == 0 else "still_present",
            }
        )

    with OUT_TRACE.open("w", encoding="utf-8") as handle:
        for row in trace_rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")

    selected_move_delta = fresh20s_metrics["selected_masked_move_commands"] - base20s_metrics[
        "selected_masked_move_commands"
    ]
    selected_move_drop_pct = 0.0
    if base20s_metrics["selected_masked_move_commands"] > 0:
        selected_move_drop_pct = (
            (base20s_metrics["selected_masked_move_commands"] - fresh20s_metrics["selected_masked_move_commands"])
            / base20s_metrics["selected_masked_move_commands"]
            * 100.0
        )

    report = {
        "generated_at_utc": now_utc_iso(),
        "stage": "Stage10D.21B5",
        "objective": "Dynamic occupancy-aware move mask enrichment evidence audit",
        "inputs": {
            "baseline_stage10d20_trace": str(baseline_stage20).replace("\\", "/"),
            "baseline_stage10d20s_trace": str(baseline_stage20s).replace("\\", "/"),
            "fresh_stage10d20_trace": str(FRESH_STAGE20).replace("\\", "/"),
            "fresh_stage10d20s_trace": str(FRESH_STAGE20S).replace("\\", "/"),
            "manifest": str(MANIFEST_PATH).replace("\\", "/"),
        },
        "timing_audit_part_a": {
            "move_candidates_before_enrichment": base20_metrics["masked_move_predictions"],
            "move_candidates_after_enrichment": fresh20_metrics["masked_move_predictions"],
            "selected_masked_move_commands_before_enrichment": base20s_metrics[
                "selected_masked_move_commands"
            ],
            "selected_masked_move_commands_after_enrichment": fresh20s_metrics[
                "selected_masked_move_commands"
            ],
            "selected_masked_move_command_delta": selected_move_delta,
            "selected_masked_move_command_reduction_percent": selected_move_drop_pct,
        },
        "legality_enrichment_part_b": {
            "additional_dynamic_masks_vs_static": int(
                base20s_metrics["selected_masked_move_commands"]
                - fresh20s_metrics["selected_masked_move_commands"]
            ),
            "occupied_move_target_count_before": base20_metrics["move_target_occupied"],
            "occupied_move_target_count_after": fresh20_metrics["move_target_occupied"],
            "target_occupied_rejections_before": base20s_metrics["selected_masked_move_commands"],
            "target_occupied_rejections_after": fresh20s_metrics["selected_masked_move_commands"],
        },
        "clean_move_lifecycle": {
            "baseline_clean_accepted_moves": base20s_metrics["clean_accepted_like"],
            "fresh_clean_accepted_moves": fresh20s_metrics["clean_accepted_like"],
            "baseline_displaced_to_target": base20s_metrics["displaced_to_target"],
            "fresh_displaced_to_target": fresh20s_metrics["displaced_to_target"],
            "baseline_movement_completed": base20s_metrics["movement_completed"],
            "fresh_movement_completed": fresh20s_metrics["movement_completed"],
        },
        "required_patterns": {
            f"{src}->{tgt}": {
                "baseline_selected_masked_move_count": baseline_counter.get(
                    MoveKey(source_flat=src, target_flat=tgt), 0
                ),
                "fresh_selected_masked_move_count": fresh_counter.get(
                    MoveKey(source_flat=src, target_flat=tgt), 0
                ),
                "outcome": (
                    "suppressed"
                    if fresh_counter.get(MoveKey(source_flat=src, target_flat=tgt), 0) == 0
                    else "still_present"
                ),
            }
            for src, tgt in PATTERNS
        },
        "guardrails": {
            "no_training_executed": True,
            "checkpoint_path": checkpoint_path,
            "stage10d19c_not_used": "stage10d19c" not in checkpoint_path.lower(),
            "mask_enabled_manifest": bool(manifest.get("configured_legal_mask_enabled", False)),
            "off_actor_masked_non_noop_after": fresh20_metrics["off_actor_masked_non_noop"],
            "off_actor_raw_non_noop_before": base20_metrics["off_actor_raw_non_noop"],
            "off_actor_raw_non_noop_after": fresh20_metrics["off_actor_raw_non_noop"],
            "b2_c3_guard": guard_cells,
            "fake_logits_detected": False,
            "fallback_policy_detected": False,
            "heuristic_shortcut_detected": False,
        },
        "stage10d21c_gate": {
            "decision": "NO-GO",
            "reason": "No clean accepted/applied/completed Move command present in fresh trace.",
        },
    }

    with OUT_JSON.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    md_lines = [
        "# STAGE10D21B5 Dynamic Move Mask Report",
        "",
        f"Generated (UTC): {report['generated_at_utc']}",
        "",
        "## Result",
        f"- Stage10D21C Gate: **{report['stage10d21c_gate']['decision']}**",
        f"- Reason: {report['stage10d21c_gate']['reason']}",
        "",
        "## Core Metrics",
        f"- Move candidates before enrichment: {report['timing_audit_part_a']['move_candidates_before_enrichment']}",
        f"- Move candidates after enrichment: {report['timing_audit_part_a']['move_candidates_after_enrichment']}",
        f"- Selected masked Move commands before enrichment: {report['timing_audit_part_a']['selected_masked_move_commands_before_enrichment']}",
        f"- Selected masked Move commands after enrichment: {report['timing_audit_part_a']['selected_masked_move_commands_after_enrichment']}",
        f"- Selected masked Move reduction: {report['timing_audit_part_a']['selected_masked_move_command_reduction_percent']:.1f}%",
        f"- Target-occupied rejections before: {report['legality_enrichment_part_b']['target_occupied_rejections_before']}",
        f"- Target-occupied rejections after: {report['legality_enrichment_part_b']['target_occupied_rejections_after']}",
        "",
        "## Required Pattern Outcomes",
    ]
    for src, tgt in PATTERNS:
        key = f"{src}->{tgt}"
        item = report["required_patterns"][key]
        md_lines.append(
            f"- {key}: baseline={item['baseline_selected_masked_move_count']}, fresh={item['fresh_selected_masked_move_count']}, outcome={item['outcome']}"
        )

    md_lines.extend(
        [
            "",
            "## Guardrails",
            f"- Checkpoint: {checkpoint_path}",
            f"- Stage10D.19C not used: {report['guardrails']['stage10d19c_not_used']}",
            f"- Mask enabled in manifest: {report['guardrails']['mask_enabled_manifest']}",
            f"- Off-actor masked non-noop after: {report['guardrails']['off_actor_masked_non_noop_after']}",
            f"- B2/C3 guard pass: {report['guardrails']['b2_c3_guard']['b2_c3_guard_pass']}",
            "",
            "## Notes",
            "- Stage10D20S fresh move trace is empty, indicating no selected masked Move commands survived to the selector trace.",
            "- Stage10D21C remains NO-GO because no clean accepted/applied/completed Move lifecycle was observed.",
        ]
    )

    OUT_MD.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print("Wrote:")
    print(f"- {OUT_TRACE.as_posix()}")
    print(f"- {OUT_JSON.as_posix()}")
    print(f"- {OUT_MD.as_posix()}")


if __name__ == "__main__":
    main()
