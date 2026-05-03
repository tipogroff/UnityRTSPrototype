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
    p = argparse.ArgumentParser(description="Stage10D.19C compare Stage10D.17/19B/19C checkpoints")
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
    p.add_argument("--stage10d19c-checkpoint", type=Path, required=True)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d19c_checkpoint_comparison.json"),
    )
    return p.parse_args()


def _score(m: Dict[str, Any]) -> tuple[float, ...]:
    return (
        float(m.get("b2_guard_harvest_gt_noop_rate", 0.0)),
        float(m.get("c3_guard_produce_gt_noop_rate", 0.0)),
        -float(m.get("unmasked_occupied_or_invalid_move_count", 1e9)),
        float(m.get("valid_alternative_move_selected_count", 0.0)),
        float(m.get("no_valid_alt_noop_selected_count", 0.0)),
        -float(m.get("off_actor_non_noop_count_unmasked", 1e9)),
    )


def main() -> int:
    args = parse_args()
    failures_payload = load_json(args.failure_cases_json)
    failure_cases = list(failures_payload.get("failure_cases", []))
    trace_by_step = index_trace_by_step(read_jsonl(args.runtime_trace_jsonl))
    device = torch.device(args.device)

    m17, d17 = evaluate_checkpoint_on_failure_cases(
        checkpoint_path=args.stage10d17_checkpoint,
        failure_cases=failure_cases,
        trace_by_step=trace_by_step,
        device=device,
        batch_size=int(args.batch_size),
    )
    m19b, d19b = evaluate_checkpoint_on_failure_cases(
        checkpoint_path=args.stage10d19b_checkpoint,
        failure_cases=failure_cases,
        trace_by_step=trace_by_step,
        device=device,
        batch_size=int(args.batch_size),
    )
    m19c, d19c = evaluate_checkpoint_on_failure_cases(
        checkpoint_path=args.stage10d19c_checkpoint,
        failure_cases=failure_cases,
        trace_by_step=trace_by_step,
        device=device,
        batch_size=int(args.batch_size),
    )

    s17 = _score(to_serializable_metrics(m17))
    s19b = _score(to_serializable_metrics(m19b))
    s19c = _score(to_serializable_metrics(m19c))

    candidate = "none"
    if s19c >= s19b and s19c >= s17:
        candidate = "stage10d19c"
    elif s19b >= s17:
        candidate = "stage10d19b"
    else:
        candidate = "stage10d17"

    # Minimal readiness guard.
    best_metrics = {
        "stage10d17": to_serializable_metrics(m17),
        "stage10d19b": to_serializable_metrics(m19b),
        "stage10d19c": to_serializable_metrics(m19c),
    }[candidate] if candidate != "none" else {}

    ready = bool(
        candidate != "none"
        and int(best_metrics.get("unmasked_occupied_or_invalid_move_count", 10**9)) <= int(
            min(m17.unmasked_occupied_or_invalid_move_count, m19b.unmasked_occupied_or_invalid_move_count, m19c.unmasked_occupied_or_invalid_move_count)
        )
        and float(best_metrics.get("b2_guard_harvest_gt_noop_rate", 0.0)) >= 0.95
        and float(best_metrics.get("c3_guard_produce_gt_noop_rate", 0.0)) >= 0.95
    )

    if not ready:
        candidate = "none"

    labels = [
        "STAGE10D19C_STAGE10D17_COMPARED",
        "STAGE10D19C_STAGE10D19B_COMPARED",
        "STAGE10D19C_STAGE10D19C_COMPARED",
    ]
    if candidate == "stage10d19c":
        labels.append("STAGE10D19C_SELECTED_STAGE10D19C_FOR_UNITY")
    elif candidate == "stage10d19b":
        labels.append("STAGE10D19C_SELECTED_STAGE10D19B_FOR_UNITY")
    elif candidate == "stage10d17":
        labels.append("STAGE10D19C_SELECTED_STAGE10D17_FOR_UNITY")
    else:
        labels.append("STAGE10D19C_NO_CANDIDATE_READY")

    report: Dict[str, Any] = {
        "stage": "10D.19C",
        "task": "checkpoint_comparison",
        "generated_at_utc": utc_now_iso(),
        "failure_case_count": int(len(failure_cases)),
        "stage10d17": {**to_serializable_metrics(m17), "detail": d17},
        "stage10d19b": {**to_serializable_metrics(m19b), "detail": d19b},
        "stage10d19c": {**to_serializable_metrics(m19c), "detail": d19c},
        "score_vectors": {
            "stage10d17": list(s17),
            "stage10d19b": list(s19b),
            "stage10d19c": list(s19c),
        },
        "selected_candidate": candidate,
        "labels": labels,
    }

    write_json(args.output_json, report)
    print(resolve_path(args.output_json).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
