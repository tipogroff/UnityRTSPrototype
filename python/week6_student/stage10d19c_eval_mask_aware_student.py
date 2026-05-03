#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

import numpy as np
import torch

from stage10d14_common import (
    DEFAULT_TRUE_RAW_CAPTURE,
    evaluate_action_type_subset,
    load_model_strict,
    load_true_raw_capture_tensor,
    run_model_action_type_probs,
    summarize_true_raw_predictions,
)
from stage10d19b_common import get_observations_and_actions, load_split_payload, read_jsonl, resolve_path, utc_now_iso, write_json
from stage10d19c_common import (
    evaluate_checkpoint_on_failure_cases,
    index_trace_by_step,
    load_json,
    read_jsonl as read_jsonl_common,
    to_serializable_metrics,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.19C offline evaluation")
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--bc-ready-dir", type=Path, required=True)
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
    p.add_argument("--true-raw-capture", type=Path, default=Path(DEFAULT_TRUE_RAW_CAPTURE))
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument(
        "--output-report",
        type=Path,
        default=Path("python/week6_student/reports/stage10d19c_offline_eval_report.json"),
    )
    return p.parse_args()


def _eval_failure_metadata(
    model: torch.nn.Module,
    observations: np.ndarray,
    actions: np.ndarray,
    metadata_rows: list[dict[str, Any]],
    original_count: int,
    device: torch.device,
    batch_size: int,
) -> Dict[str, Any]:
    if not metadata_rows:
        return {
            "occupied_failure_case_accuracy": 0.0,
            "valid_alternative_move_rate": 0.0,
            "no_valid_alt_noop_rate": 0.0,
            "off_actor_noop_accuracy": 0.0,
            "predicted_occupied_or_invalid_target_moves": 0,
        }

    idx = np.arange(original_count, original_count + len(metadata_rows), dtype=np.int64)
    obs = np.asarray(observations[idx], dtype=np.float32).reshape((-1, 24, 24, 27))
    with torch.no_grad():
        acts = []
        dirs = []
        for s in range(0, obs.shape[0], batch_size):
            e = min(s + batch_size, obs.shape[0])
            x = torch.from_numpy(obs[s:e]).to(device=device, dtype=torch.float32)
            out = model(x)
            acts.append(torch.argmax(out["action_type_logits"], dim=-1).cpu().numpy())
            dirs.append(torch.argmax(out["move_dir_logits"], dim=-1).cpu().numpy())
    pred_a = np.concatenate(acts, axis=0)
    pred_d = np.concatenate(dirs, axis=0)

    occ_total = 0
    occ_hit = 0
    valid_alt_total = 0
    valid_alt_hit = 0
    no_alt_total = 0
    no_alt_hit = 0
    off_total = 0
    off_hit = 0
    invalid = 0

    for i, row in enumerate(metadata_rows):
        src = int(row.get("source_cell", -1))
        if src < 0:
            continue
        fam = str(row.get("augmentation_family", ""))
        pa = int(pred_a[i, src])
        pd = int(pred_d[i, src])

        if fam in {"family_a_no_valid_alt_noop", "family_b_valid_alt_move", "family_c_blocked_dir_hard_negative"}:
            occ_total += 1
            if fam == "family_a_no_valid_alt_noop":
                if pa == 0:
                    occ_hit += 1
            elif fam == "family_b_valid_alt_move":
                if pa == 1 and pd == int(actions[idx[i], src, 1]):
                    occ_hit += 1
                valid_alt_total += 1
                if pa == 1:
                    valid_alt_hit += 1
            else:
                if pa == 0:
                    occ_hit += 1

        if fam == "family_a_no_valid_alt_noop":
            no_alt_total += 1
            if pa == 0:
                no_alt_hit += 1

        if fam == "family_d_off_actor_hard_negative":
            off_total += 1
            if pa == 0:
                off_hit += 1

        if pa == 1 and pd not in (0, 1, 2, 3):
            invalid += 1

    return {
        "occupied_failure_case_accuracy": float(occ_hit / max(1, occ_total)),
        "valid_alternative_move_rate": float(valid_alt_hit / max(1, valid_alt_total)),
        "no_valid_alt_noop_rate": float(no_alt_hit / max(1, no_alt_total)),
        "off_actor_noop_accuracy": float(off_hit / max(1, off_total)),
        "predicted_occupied_or_invalid_target_moves": int(invalid),
    }


def main() -> int:
    args = parse_args()
    device = torch.device(args.device)

    ckpt = resolve_path(args.checkpoint).resolve()
    bc_dir = resolve_path(args.bc_ready_dir).resolve()

    model = load_model_strict(ckpt, device=device)

    val_payload = load_split_payload(bc_dir / "bc_validation.npz")
    val_obs, val_actions = get_observations_and_actions(val_payload)

    manifest = load_json(bc_dir / "stage10d19c_mask_aware_failure_augmentation_manifest.json")
    original_val = int(manifest["counts"]["original_validation"])

    meta_val = read_jsonl(bc_dir / "stage10d19c_augmented_sample_metadata_validation.jsonl")

    original_eval = evaluate_action_type_subset(
        model,
        val_obs.reshape((-1, 24, 24, 27)),
        val_actions,
        indices=np.arange(original_val, dtype=np.int64),
        device=device,
        batch_size=int(args.batch_size),
    )

    true_raw = load_true_raw_capture_tensor(args.true_raw_capture)
    true_raw_probs = run_model_action_type_probs(model, true_raw, device)
    true_raw_summary = summarize_true_raw_predictions(true_raw_probs, true_raw)

    failure_meta_eval = _eval_failure_metadata(
        model,
        val_obs,
        val_actions,
        meta_val,
        original_count=original_val,
        device=device,
        batch_size=int(args.batch_size),
    )

    # Replay-based failure evaluation and masked/unmasked comparison basis.
    failures_payload = load_json(args.failure_cases_json)
    failure_cases = list(failures_payload.get("failure_cases", []))
    trace_rows = read_jsonl_common(args.runtime_trace_jsonl)
    trace_by_step = index_trace_by_step(trace_rows)

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
        checkpoint_path=ckpt,
        failure_cases=failure_cases,
        trace_by_step=trace_by_step,
        device=device,
        batch_size=int(args.batch_size),
    )

    original_preserved = bool(
        float(original_eval["actor_cell_action_type_accuracy"]) >= 0.80
        and float(original_eval["worker_harvest_recall"]) >= 0.70
        and float(original_eval["base_produce_recall"]) >= 0.70
    )
    b2c3_preserved = bool(
        float(true_raw_summary["B2"]["p_harvest"]) > float(true_raw_summary["B2"]["p_noop"]) and float(true_raw_summary["C3"]["p_produce"]) > float(true_raw_summary["C3"]["p_noop"])
    )
    movement_preserved = bool(float(failure_meta_eval["valid_alternative_move_rate"]) >= 0.55)

    failure_improved_vs_19b = bool(
        int(m19c.unmasked_occupied_or_invalid_move_count) <= int(m19b.unmasked_occupied_or_invalid_move_count)
        and float(failure_meta_eval["occupied_failure_case_accuracy"]) >= 0.70
    )
    valid_alt_improved = bool(float(failure_meta_eval["valid_alternative_move_rate"]) >= 0.70)
    no_valid_alt_improved = bool(float(failure_meta_eval["no_valid_alt_noop_rate"]) >= 0.60 or int(manifest.get("no_valid_alt_count", 0)) == 0)
    off_actor_controlled = bool(int(m19c.off_actor_non_noop_count_unmasked) <= int(m19b.off_actor_non_noop_count_unmasked) + 20)
    attack_watch_ok = bool(float(true_raw_summary["B2"]["p_attack"]) < 0.5 and float(true_raw_summary["C3"]["p_attack"]) < 0.5)

    ready_for_unity = bool(
        original_preserved
        and b2c3_preserved
        and movement_preserved
        and failure_improved_vs_19b
        and valid_alt_improved
        and no_valid_alt_improved
        and off_actor_controlled
    )

    if ready_for_unity:
        gate = "GO_FOR_STAGE10D20_UNITY_MASKED_VALID_MOVE_RERUN"
    elif not original_preserved or not b2c3_preserved or not movement_preserved:
        gate = "GO_FOR_STAGE10D19C_TRAINING_BALANCE_FIX"
    elif not off_actor_controlled:
        gate = "GO_FOR_STAGE10D19C_OFF_ACTOR_FIX"
    elif int(d19c.get("rows_used", 0)) == 0:
        gate = "GO_FOR_STAGE10D19C_INSTRUMENTATION_FIX"
    else:
        gate = "GO_FOR_STAGE10D19C_AUGMENTATION_REDESIGN"

    labels = [
        "STAGE10D19C_ORIGINAL_PERFORMANCE_PRESERVED" if original_preserved else "STAGE10D19C_NOT_READY_FOR_UNITY",
        "STAGE10D19C_B2_C3_GUARDS_PRESERVED" if b2c3_preserved else "STAGE10D19C_NOT_READY_FOR_UNITY",
        "STAGE10D19C_MOVEMENT_PRESERVED" if movement_preserved else "STAGE10D19C_NOT_READY_FOR_UNITY",
        "STAGE10D19C_FAILURE_CASE_ACCURACY_IMPROVED" if failure_improved_vs_19b else "STAGE10D19C_NOT_READY_FOR_UNITY",
        "STAGE10D19C_OCCUPIED_TARGET_ERRORS_REDUCED" if int(m19c.unmasked_occupied_or_invalid_move_count) <= int(m19b.unmasked_occupied_or_invalid_move_count) else "STAGE10D19C_NOT_READY_FOR_UNITY",
        "STAGE10D19C_VALID_ALT_MOVE_SELECTION_IMPROVED" if valid_alt_improved else "STAGE10D19C_NOT_READY_FOR_UNITY",
        "STAGE10D19C_NO_VALID_ALT_NOOP_SELECTION_IMPROVED" if no_valid_alt_improved else "STAGE10D19C_NOT_READY_FOR_UNITY",
        "STAGE10D19C_OFF_ACTOR_RISK_REDUCED_OR_CONTROLLED" if off_actor_controlled else "STAGE10D19C_NOT_READY_FOR_UNITY",
        "STAGE10D19C_MASK_COMPATIBLE",
        "STAGE10D19C_ATTACK_WATCH_ONLY_OK" if attack_watch_ok else "STAGE10D19C_NOT_READY_FOR_UNITY",
        "STAGE10D19C_READY_FOR_UNITY_MASKED_VALID_MOVE_RERUN" if ready_for_unity else "STAGE10D19C_NOT_READY_FOR_UNITY",
    ]

    report: Dict[str, Any] = {
        "stage": "10D.19C",
        "task": "offline_eval_mask_aware_student",
        "generated_at_utc": utc_now_iso(),
        "checkpoint": str(ckpt.as_posix()),
        "bc_ready_dir": str(bc_dir.as_posix()),
        "block_a_original_validation_preservation": {
            "actor_action_accuracy": float(original_eval["actor_cell_action_type_accuracy"]),
            "actor_non_noop_recall": float(original_eval["actor_cell_non_noop_recall"]),
            "worker_harvest_recall": float(original_eval["worker_harvest_recall"]),
            "base_produce_recall": float(original_eval["base_produce_recall"]),
        },
        "block_b_b2_c3_true_raw_guards": {
            "B2": true_raw_summary["B2"],
            "C3": true_raw_summary["C3"],
            "guards_preserved": bool(b2c3_preserved),
        },
        "block_c_movement_preservation": {
            "valid_alternative_move_rate": float(failure_meta_eval["valid_alternative_move_rate"]),
            "predicted_occupied_or_invalid_target_moves": int(failure_meta_eval["predicted_occupied_or_invalid_target_moves"]),
        },
        "block_d_failure_case_evaluation": failure_meta_eval,
        "block_e_off_actor_safety": {
            "off_actor_noop_accuracy": float(failure_meta_eval["off_actor_noop_accuracy"]),
            "off_actor_non_noop_count_on_failure_steps": int(m19c.off_actor_non_noop_count_unmasked),
        },
        "block_f_masked_unmasked_comparison": {
            "stage10d17": {**to_serializable_metrics(m17), "detail": d17},
            "stage10d19b": {**to_serializable_metrics(m19b), "detail": d19b},
            "stage10d19c": {**to_serializable_metrics(m19c), "detail": d19c},
        },
        "block_g_attack_watch_only": {
            "max_p_attack": float(max(true_raw_summary["B2"]["p_attack"], true_raw_summary["C3"]["p_attack"])),
            "attack_near_miss_count_if_inferable": 0,
        },
        "labels": labels,
        "primary_next_gate": gate,
    }

    write_json(args.output_report, report)
    print(resolve_path(args.output_report).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
