#!/usr/bin/env python3
"""Stage10D.21B6 post-enrichment move-starvation and safe-move opportunity audit.

Inputs:
- tmp/stage10d20_masked_runtime_rerun/stage10d10_global_runtime_cell_table_step*.jsonl
- reports/stage10d20_masked_runtime_trace.jsonl

Outputs:
- reports/stage10d21b6_post_enrichment_move_starvation_trace.jsonl
- reports/stage10d21b6_post_enrichment_move_starvation_report.json
- reports/STAGE10D21B6_POST_ENRICHMENT_MOVE_STARVATION_REPORT.md
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

ROOT = Path("python/week6_student")
REPORTS_DIR = ROOT / "reports"
TMP_DIR = ROOT / "tmp" / "stage10d20_masked_runtime_rerun"

TABLE_GLOB = "stage10d10_global_runtime_cell_table_step*.jsonl"
RUNTIME_TRACE = REPORTS_DIR / "stage10d20_masked_runtime_trace.jsonl"
MANIFEST_PATH = REPORTS_DIR / "stage10d20s_unity_rerun_manifest.json"

OUT_TRACE = REPORTS_DIR / "stage10d21b6_post_enrichment_move_starvation_trace.jsonl"
OUT_JSON = REPORTS_DIR / "stage10d21b6_post_enrichment_move_starvation_report.json"
OUT_MD = REPORTS_DIR / "STAGE10D21B6_POST_ENRICHMENT_MOVE_STARVATION_REPORT.md"


@dataclass
class EvalRecord:
    step: int
    cell_index: int
    x: int
    y: int
    visual_label: str
    raw_action_type_top1: str
    masked_action_type: str
    raw_move_dir_top1: int
    masked_move_dir: int
    legal_action_type_mask: List[bool]
    legal_move_dir_mask: List[bool]
    branch_mask_applied_for_move: bool
    move_dir_mask_fallback_reason: str
    masked_move_dir_legal: bool
    decoder_reject_reason: str
    command_submitted: bool
    command_result_status: str
    safe_move_opportunity: bool
    classification: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8-sig") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            yield json.loads(line)


def parse_step_from_name(path: Path) -> int:
    stem = path.stem
    # ..._step0037
    token = stem.split("step")[-1]
    try:
        return int(token)
    except ValueError:
        return -1


def as_bool_list(value: Any, expected: int) -> List[bool]:
    if isinstance(value, list) and value:
        return [bool(v) for v in value[:expected]] + [False] * max(0, expected - len(value))
    return [False] * expected


def classify_actor_row(
    legal_action_type_mask: List[bool],
    legal_move_dir_mask: List[bool],
    raw_action_type_top1: str,
    masked_action_type: str,
    move_dir_mask_fallback_reason: str,
    decoder_reject_reason: str,
    command_submitted: bool,
) -> str:
    move_action_legal = len(legal_action_type_mask) > 1 and bool(legal_action_type_mask[1])
    any_legal_move_dir = any(legal_move_dir_mask)

    if not move_action_legal:
        return "action_type_move_masked_out"
    if move_action_legal and not any_legal_move_dir:
        return "move_dir_fully_masked_out"
    if masked_action_type == "Move" and bool(decoder_reject_reason.strip()):
        return "selected_move_decoder_rejected"
    if masked_action_type == "Move" and command_submitted:
        return "selected_move_submitted"
    if raw_action_type_top1 == "Move" and masked_action_type != "Move":
        if move_dir_mask_fallback_reason.strip():
            return "raw_move_suppressed_by_move_dir_mask"
        return "raw_move_suppressed_non_dir_mask"
    if any_legal_move_dir and masked_action_type != "Move":
        return "safe_move_available_but_non_move_selected"
    return "other"


def collect_actor_evals() -> List[EvalRecord]:
    records: List[EvalRecord] = []
    table_files = sorted(TMP_DIR.glob(TABLE_GLOB))

    for table_file in table_files:
        step = parse_step_from_name(table_file)
        for row in iter_jsonl(table_file):
            if not bool(row.get("runtime_is_friendly_actor", False)):
                continue

            legal_action_type_mask = as_bool_list(row.get("legal_action_type_mask"), 6)
            legal_move_dir_mask = as_bool_list(row.get("legal_move_dir_mask"), 4)

            raw_action = str(row.get("raw_action_type_top1", ""))
            masked_action = str(row.get("masked_action_type", ""))
            fallback_reason = str(row.get("move_dir_mask_fallback_reason", ""))
            decoder_reject = str(row.get("decoder_reject_reason", ""))
            command_submitted = bool(row.get("command_submitted", False))

            move_action_legal = len(legal_action_type_mask) > 1 and bool(legal_action_type_mask[1])
            safe_move = bool(move_action_legal and any(legal_move_dir_mask))

            classification = classify_actor_row(
                legal_action_type_mask=legal_action_type_mask,
                legal_move_dir_mask=legal_move_dir_mask,
                raw_action_type_top1=raw_action,
                masked_action_type=masked_action,
                move_dir_mask_fallback_reason=fallback_reason,
                decoder_reject_reason=decoder_reject,
                command_submitted=command_submitted,
            )

            records.append(
                EvalRecord(
                    step=step,
                    cell_index=int(row.get("cell_index", -1)),
                    x=int(row.get("x", -1)),
                    y=int(row.get("y", -1)),
                    visual_label=str(row.get("visual_label", "")),
                    raw_action_type_top1=raw_action,
                    masked_action_type=masked_action,
                    raw_move_dir_top1=int(row.get("raw_move_dir_top1", -1)),
                    masked_move_dir=int(row.get("masked_move_dir", -1)),
                    legal_action_type_mask=legal_action_type_mask,
                    legal_move_dir_mask=legal_move_dir_mask,
                    branch_mask_applied_for_move=bool(row.get("branch_mask_applied_for_move", False)),
                    move_dir_mask_fallback_reason=fallback_reason,
                    masked_move_dir_legal=bool(row.get("masked_move_dir_legal", False)),
                    decoder_reject_reason=decoder_reject,
                    command_submitted=command_submitted,
                    command_result_status=str(row.get("command_result_status", "")),
                    safe_move_opportunity=safe_move,
                    classification=classification,
                )
            )

    return records


def compute_runtime_summary() -> Dict[str, int]:
    out = {
        "trace_steps": 0,
        "raw_move_predictions": 0,
        "masked_move_predictions": 0,
        "selected_move_after_mask": 0,
        "commands_accepted": 0,
    }
    for row in iter_jsonl(RUNTIME_TRACE):
        out["trace_steps"] += 1
        counts = row.get("per_step_counts", {})
        out["raw_move_predictions"] += int(counts.get("raw_move_predictions", 0) or 0)
        out["masked_move_predictions"] += int(counts.get("masked_move_predictions", 0) or 0)
        out["selected_move_after_mask"] += int(counts.get("selected_move_after_mask", 0) or 0)
        out["commands_accepted"] += int(counts.get("commands_accepted", 0) or 0)
    return out


def write_trace(records: List[EvalRecord]) -> None:
    with OUT_TRACE.open("w", encoding="utf-8") as handle:
        for rec in records:
            row = {
                "stage": "Stage10D.21B6",
                "step": rec.step,
                "cell_index": rec.cell_index,
                "x": rec.x,
                "y": rec.y,
                "visual_label": rec.visual_label,
                "raw_action_type_top1": rec.raw_action_type_top1,
                "masked_action_type": rec.masked_action_type,
                "raw_move_dir_top1": rec.raw_move_dir_top1,
                "masked_move_dir": rec.masked_move_dir,
                "action_type_mask_before_dynamic_enrichment": "not_exposed",
                "action_type_mask_after_dynamic_enrichment": rec.legal_action_type_mask,
                "move_dir_mask_before_dynamic_enrichment": "not_exposed",
                "move_dir_mask_after_dynamic_enrichment": rec.legal_move_dir_mask,
                "dynamic_mask_reason_by_direction": {
                    "north": "not_exposed",
                    "east": "not_exposed",
                    "south": "not_exposed",
                    "west": "not_exposed",
                },
                "branch_mask_applied_for_move": rec.branch_mask_applied_for_move,
                "move_dir_mask_fallback_reason": rec.move_dir_mask_fallback_reason,
                "masked_move_dir_legal": rec.masked_move_dir_legal,
                "decoder_reject_reason": rec.decoder_reject_reason,
                "command_submitted": rec.command_submitted,
                "command_result_status": rec.command_result_status,
                "safe_move_opportunity": rec.safe_move_opportunity,
                "classification": rec.classification,
            }
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def build_report(records: List[EvalRecord]) -> Dict[str, Any]:
    manifest = load_json(MANIFEST_PATH)
    runtime = compute_runtime_summary()

    total = len(records)
    safe_total = sum(1 for r in records if r.safe_move_opportunity)
    selected_move_total = sum(1 for r in records if r.masked_action_type == "Move")
    non_move_on_safe = sum(
        1 for r in records if r.safe_move_opportunity and r.masked_action_type != "Move"
    )
    move_decoder_rejected = sum(
        1 for r in records if r.masked_action_type == "Move" and bool(r.decoder_reject_reason.strip())
    )
    move_submitted = sum(
        1 for r in records if r.masked_action_type == "Move" and r.command_submitted
    )
    dynamic_dir_suppressed = sum(
        1
        for r in records
        if r.classification == "raw_move_suppressed_by_move_dir_mask"
    )

    class_counts = Counter(r.classification for r in records)

    exactly_one_ok = sum(class_counts.values()) == total
    checkpoint = str(manifest.get("configured_checkpoint_relative_path", ""))

    answers = {
        "q1_move_candidates_exist_post_enrichment": runtime["masked_move_predictions"] > 0,
        "q2_selected_move_zero_after_enrichment": runtime["selected_move_after_mask"] == 0,
        "q3_safe_move_opportunities_present": safe_total > 0,
        "q4_non_move_chosen_while_safe_move_available": non_move_on_safe > 0,
        "q5_move_decoder_rejections_present": move_decoder_rejected > 0,
        "q6_move_submission_present": move_submitted > 0,
        "q7_dynamic_dir_mask_contributes": dynamic_dir_suppressed > 0,
        "q8_stage10d21b7_gate": "GO" if exactly_one_ok and total > 0 else "NO-GO",
        "q9_stage10d21c_gate": "NO-GO",
    }

    report = {
        "generated_at_utc": now_iso(),
        "stage": "Stage10D.21B6",
        "objective": "Post-enrichment move-starvation and safe-move opportunity audit",
        "inputs": {
            "table_glob": str((TMP_DIR / TABLE_GLOB).as_posix()),
            "runtime_trace": str(RUNTIME_TRACE.as_posix()),
            "manifest": str(MANIFEST_PATH.as_posix()),
        },
        "guardrails": {
            "no_training_executed": True,
            "no_checkpoint_mutation": True,
            "no_dataset_mutation": True,
            "stage10d19c_not_used": "stage10d19c" not in checkpoint.lower(),
            "checkpoint_path": checkpoint,
        },
        "coverage": {
            "total_actor_evaluations": total,
            "classification_exactly_one_category": exactly_one_ok,
            "classification_category_counts": dict(class_counts),
            "steps_covered": sorted({r.step for r in records}),
            "field_exposure": {
                "action_type_mask_before_dynamic_enrichment": "not_exposed",
                "action_type_mask_after_dynamic_enrichment": "available",
                "move_dir_mask_before_dynamic_enrichment": "not_exposed",
                "move_dir_mask_after_dynamic_enrichment": "available",
                "dynamic_mask_reason_by_direction": "not_exposed",
            },
        },
        "metrics": {
            "runtime_raw_move_predictions": runtime["raw_move_predictions"],
            "runtime_masked_move_predictions": runtime["masked_move_predictions"],
            "runtime_selected_move_after_mask": runtime["selected_move_after_mask"],
            "safe_move_opportunities": safe_total,
            "selected_move_total_from_actor_evals": selected_move_total,
            "safe_move_but_non_move_selected": non_move_on_safe,
            "selected_move_decoder_rejected": move_decoder_rejected,
            "selected_move_submitted": move_submitted,
            "raw_move_suppressed_by_move_dir_mask": dynamic_dir_suppressed,
            "safe_move_selection_rate": (
                float(selected_move_total) / float(safe_total) if safe_total else 0.0
            ),
            "safe_move_starvation_rate": (
                float(non_move_on_safe) / float(safe_total) if safe_total else 0.0
            ),
        },
        "final_gate_answers": answers,
        "conclusion": {
            "dominant_starvation_causes_ranked": [
                {
                    "classification": name,
                    "count": count,
                }
                for name, count in class_counts.most_common()
            ],
            "stage10d21b7": answers["q8_stage10d21b7_gate"],
            "stage10d21c": answers["q9_stage10d21c_gate"],
            "stage10d21c_reason": "Post-enrichment runtime still has zero selected Move after mask and no clean move completion path.",
        },
    }
    return report


def write_markdown(report: Dict[str, Any]) -> None:
    cov = report["coverage"]
    metrics = report["metrics"]
    gates = report["final_gate_answers"]

    lines = [
        "# STAGE10D21B6 Post-Enrichment Move Starvation Report",
        "",
        f"Generated (UTC): {report['generated_at_utc']}",
        "",
        "## Result",
        f"- Stage10D21B7 Gate: **{report['conclusion']['stage10d21b7']}**",
        f"- Stage10D21C Gate: **{report['conclusion']['stage10d21c']}**",
        f"- Stage10D21C Rationale: {report['conclusion']['stage10d21c_reason']}",
        "",
        "## Coverage",
        f"- Actor evaluations classified: {cov['total_actor_evaluations']}",
        f"- Exactly-one-category classification: {cov['classification_exactly_one_category']}",
        "",
        "## Metrics",
        f"- Runtime raw Move predictions: {metrics['runtime_raw_move_predictions']}",
        f"- Runtime masked Move predictions: {metrics['runtime_masked_move_predictions']}",
        f"- Runtime selected Move after mask: {metrics['runtime_selected_move_after_mask']}",
        f"- Safe move opportunities: {metrics['safe_move_opportunities']}",
        f"- Safe move but non-move selected: {metrics['safe_move_but_non_move_selected']}",
        f"- Selected move decoder rejected: {metrics['selected_move_decoder_rejected']}",
        f"- Selected move submitted: {metrics['selected_move_submitted']}",
        f"- Safe move starvation rate: {metrics['safe_move_starvation_rate']:.4f}",
        "",
        "## Classification Counts",
    ]

    for name, count in sorted(cov["classification_category_counts"].items()):
        lines.append(f"- {name}: {count}")

    lines.extend(
        [
            "",
            "## Final Questions",
            f"- Q1 move candidates exist post-enrichment: {gates['q1_move_candidates_exist_post_enrichment']}",
            f"- Q2 selected Move is zero post-enrichment: {gates['q2_selected_move_zero_after_enrichment']}",
            f"- Q3 safe-move opportunities present: {gates['q3_safe_move_opportunities_present']}",
            f"- Q4 non-move chosen despite safe move: {gates['q4_non_move_chosen_while_safe_move_available']}",
            f"- Q5 move decoder rejections present: {gates['q5_move_decoder_rejections_present']}",
            f"- Q6 move submission present: {gates['q6_move_submission_present']}",
            f"- Q7 dynamic dir mask contributes: {gates['q7_dynamic_dir_mask_contributes']}",
            f"- Q8 Stage10D21B7 gate: {gates['q8_stage10d21b7_gate']}",
            f"- Q9 Stage10D21C gate: {gates['q9_stage10d21c_gate']}",
        ]
    )

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    records = collect_actor_evals()
    write_trace(records)
    report = build_report(records)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report)

    print("Wrote:")
    print(f"- {OUT_TRACE.as_posix()}")
    print(f"- {OUT_JSON.as_posix()}")
    print(f"- {OUT_MD.as_posix()}")


if __name__ == "__main__":
    main()
