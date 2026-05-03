#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

import torch

from stage10d19c_common import (
    evaluate_checkpoint_on_failure_cases,
    index_trace_by_step,
    load_json,
    read_jsonl,
    resolve_path,
    to_serializable_metrics,
    utc_now_iso,
    write_json,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.19C failure-case replay probe")
    p.add_argument(
        "--failure-cases-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d19c_occupied_move_failure_cases.json"),
    )
    p.add_argument(
        "--runtime-trace-jsonl",
        type=Path,
        default=Path("python/week6_student/reports/stage10d18rr_runtime_redeploy_trace.jsonl"),
    )
    p.add_argument(
        "--stage10d17-checkpoint",
        type=Path,
        default=Path(
            "python/week6_student/runs/legacy032_v2_stage10d17_movement_augmented_bc_20260503T164734Z/student_bc_stage10d17_movement_augmented_best.pt"
        ),
    )
    p.add_argument(
        "--stage10d19b-checkpoint",
        type=Path,
        default=Path(
            "python/week6_student/runs/legacy032_v2_stage10d19b_valid_move_augmented_bc_20260503T192454Z/student_bc_stage10d19b_valid_move_best.pt"
        ),
    )
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument(
        "--output-stage10d17",
        type=Path,
        default=Path("python/week6_student/reports/stage10d19c_failure_case_replay_probe_stage10d17.json"),
    )
    p.add_argument(
        "--output-stage10d19b",
        type=Path,
        default=Path("python/week6_student/reports/stage10d19c_failure_case_replay_probe_stage10d19b.json"),
    )
    return p.parse_args()


def _labels(payload: Dict[str, Any]) -> list[str]:
    m = payload
    labels = ["STAGE10D19C_FAILURE_REPLAY_COMPLETED"]

    if int(m.get("masked_occupied_or_invalid_move_count", 0)) < int(m.get("unmasked_occupied_or_invalid_move_count", 0)):
        labels.append("STAGE10D19C_MASK_REDUCES_FAILURE_CASE_INVALID_MOVES")
    else:
        labels.append("STAGE10D19C_MASK_DOES_NOT_HELP_FAILURE_CASES")

    if int(m.get("invalid_move_to_valid_move_count", 0)) > 0:
        labels.append("STAGE10D19C_MASK_CONVERTS_INVALID_TO_VALID_MOVE")

    if int(m.get("invalid_move_to_noop_count", 0)) > 0:
        labels.append("STAGE10D19C_MASK_CONVERTS_INVALID_TO_NOOP")

    if bool(m.get("reconstruction_partial", False)):
        labels.append("STAGE10D19C_REPLAY_OBSERVATION_RECONSTRUCTION_PARTIAL")

    return labels


def _build_report(
    *,
    checkpoint: Path,
    metrics: Dict[str, Any],
    detail: Dict[str, Any],
    failure_case_count: int,
) -> Dict[str, Any]:
    payload = {
        "stage": "10D.19C",
        "task": "failure_case_replay_probe",
        "generated_at_utc": utc_now_iso(),
        "checkpoint": str(resolve_path(checkpoint).as_posix()),
        "failure_cases_total": int(failure_case_count),
        **metrics,
        "reconstruction": detail,
        "mask_contract_note": "Legal mask used as diagnostic/pre-selection constraint only; runtime decoder/applier/matchmanager remain authoritative.",
        "labels": [],
    }
    payload["labels"] = _labels(payload)
    return payload


def main() -> int:
    args = parse_args()

    failures_payload = load_json(args.failure_cases_json)
    failure_cases = failures_payload.get("failure_cases", []) if isinstance(failures_payload, dict) else []

    trace_rows = read_jsonl(args.runtime_trace_jsonl)
    trace_by_step = index_trace_by_step(trace_rows)

    device = torch.device(args.device)

    metrics_17, detail_17 = evaluate_checkpoint_on_failure_cases(
        checkpoint_path=args.stage10d17_checkpoint,
        failure_cases=failure_cases,
        trace_by_step=trace_by_step,
        device=device,
        batch_size=int(args.batch_size),
    )

    metrics_19b, detail_19b = evaluate_checkpoint_on_failure_cases(
        checkpoint_path=args.stage10d19b_checkpoint,
        failure_cases=failure_cases,
        trace_by_step=trace_by_step,
        device=device,
        batch_size=int(args.batch_size),
    )

    report_17 = _build_report(
        checkpoint=args.stage10d17_checkpoint,
        metrics=to_serializable_metrics(metrics_17),
        detail=detail_17,
        failure_case_count=len(failure_cases),
    )
    report_19b = _build_report(
        checkpoint=args.stage10d19b_checkpoint,
        metrics=to_serializable_metrics(metrics_19b),
        detail=detail_19b,
        failure_case_count=len(failure_cases),
    )

    write_json(args.output_stage10d17, report_17)
    write_json(args.output_stage10d19b, report_19b)

    print(resolve_path(args.output_stage10d17).as_posix())
    print(resolve_path(args.output_stage10d19b).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
