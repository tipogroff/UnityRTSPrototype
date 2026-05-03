#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

import numpy as np
import torch

from stage10d14_common import (
    DEFAULT_TRUE_RAW_CAPTURE,
    evaluate_action_type_subset,
    load_model_strict,
    load_true_raw_capture_tensor,
    run_model_action_type_probs,
    summarize_true_raw_predictions,
    utc_now_iso,
    write_json,
)
from stage10d19b_common import (
    ACTION_TYPE_ATTACK,
    ACTION_TYPE_MOVE,
    ACTION_TYPE_NOOP,
    OWNER_SELF_INDEX,
    UNIT_TYPE_SLICE,
    get_observations_and_actions,
    load_json,
    load_split_payload,
    read_jsonl,
    resolve_path,
    target_from_source_and_dir,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.19B offline evaluation")
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--augmented-bc-ready-dir", type=Path, required=True)
    p.add_argument("--true-raw-capture", type=Path, default=Path(DEFAULT_TRUE_RAW_CAPTURE))
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument(
        "--output-report",
        type=Path,
        default=Path("python/week6_student/reports/stage10d19b_offline_eval_report.json"),
    )
    p.add_argument(
        "--output-snapshot-replay",
        type=Path,
        default=Path("python/week6_student/reports/stage10d19b_stage10d18rr_snapshot_replay_report.json"),
    )
    p.add_argument("--emit-snapshot-replay", action="store_true")
    return p.parse_args()


def _is_actor_mask(obs_rows: np.ndarray) -> np.ndarray:
    return np.asarray((obs_rows[:, :, OWNER_SELF_INDEX] > 0.5) & (np.sum(obs_rows[:, :, UNIT_TYPE_SLICE], axis=2) > 0.5), dtype=bool)


def _predict_action_and_move_dir(model: torch.nn.Module, obs: np.ndarray, device: torch.device, batch_size: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    model.eval()
    a_list: List[np.ndarray] = []
    d_list: List[np.ndarray] = []
    attack_prob_list: List[np.ndarray] = []
    obs4 = np.asarray(obs, dtype=np.float32)
    if obs4.ndim == 3 and obs4.shape[1:] == (576, 27):
        obs4 = obs4.reshape((-1, 24, 24, 27))
    with torch.no_grad():
        for s in range(0, obs4.shape[0], batch_size):
            e = min(s + batch_size, obs4.shape[0])
            x = torch.from_numpy(obs4[s:e]).to(device=device, dtype=torch.float32)
            out = model(x)
            action_logits = out["action_type_logits"]
            probs = torch.softmax(action_logits, dim=-1)
            a_list.append(torch.argmax(action_logits, dim=-1).cpu().numpy())
            d_list.append(torch.argmax(out["move_dir_logits"], dim=-1).cpu().numpy())
            attack_prob_list.append(probs[..., ACTION_TYPE_ATTACK].cpu().numpy())
    return np.concatenate(a_list, axis=0), np.concatenate(d_list, axis=0), np.concatenate(attack_prob_list, axis=0)


def _eval_meta_subset(
    *,
    model: torch.nn.Module,
    observations: np.ndarray,
    actions: np.ndarray,
    metadata: Sequence[Mapping[str, Any]],
    original_count: int,
    device: torch.device,
    batch_size: int,
) -> Dict[str, Any]:
    if not metadata:
        return {
            "valid_move_recall": 0.0,
            "valid_move_dir_accuracy": 0.0,
            "occupied_target_negative_accuracy": 0.0,
            "off_actor_noop_accuracy": 0.0,
            "total_move_predictions": 0,
            "predicted_valid_target_moves": 0,
            "predicted_occupied_or_invalid_target_moves": 0,
            "estimated_prediction_to_build_readiness": 0.0,
            "off_actor_non_noop_count": 0,
            "off_actor_command_risk_if_inferable": "insufficient_data",
            "attack_max_probability_watch": 0.0,
        }

    idx = np.arange(original_count, original_count + len(metadata), dtype=np.int64)
    obs_sub = np.asarray(observations[idx], dtype=np.float32)
    act_sub = np.asarray(actions[idx], dtype=np.int64)
    pred_action, pred_dir, attack_prob = _predict_action_and_move_dir(model, obs_sub, device, batch_size)
    actor = _is_actor_mask(obs_sub)

    valid_total = 0
    valid_hit = 0
    dir_hit = 0
    occ_total = 0
    occ_hit = 0
    off_total = 0
    off_hit = 0

    move_preds = 0
    valid_move_preds = 0
    invalid_move_preds = 0

    for i, row in enumerate(metadata):
        src = int(row.get("source_cell", -1))
        if src < 0:
            continue
        fam = str(row.get("augmentation_family", ""))

        if fam == "family_a_valid_move_positive":
            valid_total += 1
            if int(pred_action[i, src]) == ACTION_TYPE_MOVE:
                valid_hit += 1
                if int(pred_dir[i, src]) == int(act_sub[i, src, 1]):
                    dir_hit += 1

        if fam in {"family_b_occupied_negative", "family_c_direction_correction"}:
            occ_total += 1
            if fam == "family_b_occupied_negative":
                if int(pred_action[i, src]) == ACTION_TYPE_NOOP:
                    occ_hit += 1
            else:
                if int(pred_action[i, src]) in (ACTION_TYPE_NOOP, ACTION_TYPE_MOVE):
                    occ_hit += 1

        if fam == "family_e_off_actor_negative":
            off_total += 1
            if int(pred_action[i, src]) == ACTION_TYPE_NOOP:
                off_hit += 1

        if int(pred_action[i, src]) == ACTION_TYPE_MOVE:
            move_preds += 1
            tgt, in_bounds = target_from_source_and_dir(src, int(pred_dir[i, src]))
            if (not in_bounds) or tgt is None:
                invalid_move_preds += 1
            else:
                occupied = bool(np.sum(obs_sub[i, tgt, UNIT_TYPE_SLICE]) > 0.5)
                if occupied:
                    invalid_move_preds += 1
                else:
                    valid_move_preds += 1

    off_actor_non_noop = int(np.sum(pred_action[~actor] != ACTION_TYPE_NOOP))
    attack_max = float(np.max(attack_prob)) if attack_prob.size else 0.0

    return {
        "valid_move_recall": float(valid_hit / max(1, valid_total)),
        "valid_move_dir_accuracy": float(dir_hit / max(1, valid_hit)),
        "occupied_target_negative_accuracy": float(occ_hit / max(1, occ_total)),
        "off_actor_noop_accuracy": float(off_hit / max(1, off_total)),
        "total_move_predictions": int(move_preds),
        "predicted_valid_target_moves": int(valid_move_preds),
        "predicted_occupied_or_invalid_target_moves": int(invalid_move_preds),
        "estimated_prediction_to_build_readiness": float(valid_move_preds / max(1, move_preds)),
        "off_actor_non_noop_count": int(off_actor_non_noop),
        "off_actor_command_risk_if_inferable": "low_if_decoder_filter_unchanged" if off_actor_non_noop <= 5 else "elevated",
        "attack_max_probability_watch": attack_max,
    }


def _snapshot_replay_from_metadata(
    *,
    model: torch.nn.Module,
    observations: np.ndarray,
    actions: np.ndarray,
    metadata: Sequence[Mapping[str, Any]],
    original_count: int,
    device: torch.device,
    batch_size: int,
) -> Dict[str, Any]:
    step_targets = [1, 55, 100, 200]
    out: Dict[str, Any] = {}

    for step in step_targets:
        selected = [i for i, r in enumerate(metadata) if int(r.get("source_step", -1)) == step]
        if not selected:
            out[str(step)] = {
                "present": False,
                "reason": "no_stage10d19b_augmented_rows_for_step",
            }
            continue

        idx = np.asarray([original_count + i for i in selected], dtype=np.int64)
        obs_sub = np.asarray(observations[idx], dtype=np.float32)
        pred_action, pred_dir, attack_prob = _predict_action_and_move_dir(model, obs_sub, device, batch_size)
        actor = _is_actor_mask(obs_sub)

        total_actor_cells = int(np.sum(actor))
        move_preds = int(np.sum(pred_action[actor] == ACTION_TYPE_MOVE))
        off_actor_non_noop = int(np.sum(pred_action[~actor] != ACTION_TYPE_NOOP))

        valid = 0
        invalid = 0
        b2_pred = None
        c3_pred = None
        produced_move_pred = 0

        for local_i, meta_i in enumerate(selected):
            row = metadata[meta_i]
            src = int(row.get("source_cell", -1))
            if src < 0:
                continue
            if src == 25:
                b2_pred = int(pred_action[local_i, src])
            if src == 50:
                c3_pred = int(pred_action[local_i, src])
            if str(row.get("unit_id", "")).startswith("Worker_") and int(pred_action[local_i, src]) == ACTION_TYPE_MOVE:
                produced_move_pred += 1
            if int(pred_action[local_i, src]) == ACTION_TYPE_MOVE:
                tgt, in_bounds = target_from_source_and_dir(src, int(pred_dir[local_i, src]))
                if not in_bounds or tgt is None:
                    invalid += 1
                else:
                    occupied = bool(np.sum(obs_sub[local_i, tgt, UNIT_TYPE_SLICE]) > 0.5)
                    if occupied:
                        invalid += 1
                    else:
                        valid += 1

        out[str(step)] = {
            "present": True,
            "sample_count": int(len(selected)),
            "actor_cells": total_actor_cells,
            "actor_action_distribution": {
                "NoOp": int(np.sum(pred_action[actor] == ACTION_TYPE_NOOP)),
                "Move": int(np.sum(pred_action[actor] == ACTION_TYPE_MOVE)),
                "Harvest": int(np.sum(pred_action[actor] == 2)),
                "Return": int(np.sum(pred_action[actor] == 3)),
                "Produce": int(np.sum(pred_action[actor] == 4)),
                "Attack": int(np.sum(pred_action[actor] == 5)),
            },
            "move_predictions": move_preds,
            "valid_target_moves": int(valid),
            "occupied_or_invalid_target_moves": int(invalid),
            "off_actor_non_noop": int(off_actor_non_noop),
            "b2_predicted_action": b2_pred,
            "c3_predicted_action": c3_pred,
            "produced_unit_move_predictions": int(produced_move_pred),
            "max_p_attack_watch": float(np.max(attack_prob)) if attack_prob.size else 0.0,
        }

    any_present = any(v.get("present", False) for v in out.values())
    valid_sum = sum(int(v.get("valid_target_moves", 0)) for v in out.values() if v.get("present", False))
    invalid_sum = sum(int(v.get("occupied_or_invalid_target_moves", 0)) for v in out.values() if v.get("present", False))
    off_sum = sum(int(v.get("off_actor_non_noop", 0)) for v in out.values() if v.get("present", False))

    labels = ["STAGE10D19B_SNAPSHOT_REPLAY_COMPLETED" if any_present else "STAGE10D19B_OFF_ACTOR_REPLAY_RISK"]
    labels.append("STAGE10D19B_VALID_MOVE_REPLAY_IMPROVED" if valid_sum >= invalid_sum else "STAGE10D19B_OFF_ACTOR_REPLAY_RISK")
    labels.append("STAGE10D19B_OFF_ACTOR_REPLAY_SAFE" if off_sum <= 20 else "STAGE10D19B_OFF_ACTOR_REPLAY_RISK")

    return {
        "steps": out,
        "summary": {
            "valid_sum": int(valid_sum),
            "invalid_sum": int(invalid_sum),
            "off_actor_non_noop_sum": int(off_sum),
        },
        "labels": labels,
    }


def main() -> int:
    args = parse_args()
    checkpoint = resolve_path(args.checkpoint).resolve()
    bc_dir = resolve_path(args.augmented_bc_ready_dir).resolve()
    device = torch.device(args.device)

    model = load_model_strict(checkpoint, device=device)

    train_payload = load_split_payload(bc_dir / "bc_train.npz")
    val_payload = load_split_payload(bc_dir / "bc_validation.npz")
    train_obs, train_actions = get_observations_and_actions(train_payload)
    val_obs, val_actions = get_observations_and_actions(val_payload)

    manifest = load_json(bc_dir / "stage10d19b_valid_move_augmentation_manifest.json")
    original_train = int(manifest["counts"]["original_train"])
    original_val = int(manifest["counts"]["original_validation"])

    meta_train = read_jsonl(bc_dir / "stage10d19b_augmented_sample_metadata_train.jsonl")
    meta_val = read_jsonl(bc_dir / "stage10d19b_augmented_sample_metadata_validation.jsonl")

    eval_a = evaluate_action_type_subset(
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

    eval_c_val = _eval_meta_subset(
        model=model,
        observations=val_obs,
        actions=val_actions,
        metadata=meta_val,
        original_count=original_val,
        device=device,
        batch_size=int(args.batch_size),
    )
    eval_c_train = _eval_meta_subset(
        model=model,
        observations=train_obs,
        actions=train_actions,
        metadata=meta_train,
        original_count=original_train,
        device=device,
        batch_size=int(args.batch_size),
    )

    snapshot_payload = _snapshot_replay_from_metadata(
        model=model,
        observations=val_obs,
        actions=val_actions,
        metadata=meta_val,
        original_count=original_val,
        device=device,
        batch_size=int(args.batch_size),
    )

    original_preserved = bool(
        float(eval_a["actor_cell_action_type_accuracy"]) >= 0.85
        and float(eval_a["worker_harvest_recall"]) >= 0.75
        and float(eval_a["base_produce_recall"]) >= 0.75
    )
    guards_preserved = bool(
        float(true_raw_summary["B2"]["p_harvest"]) >= float(true_raw_summary["B2"]["p_noop"])
        and float(true_raw_summary["C3"]["p_produce"]) >= float(true_raw_summary["C3"]["p_noop"])
    )
    movement_preserved = bool(float(eval_c_val["valid_move_recall"]) >= 0.55)
    valid_move_improved = bool(float(eval_c_val["estimated_prediction_to_build_readiness"]) >= 0.35)
    occupied_reduced = bool(float(eval_c_val["occupied_target_negative_accuracy"]) >= 0.70)
    off_actor_controlled = bool(int(eval_c_val["off_actor_non_noop_count"]) <= 40 and float(eval_c_val["off_actor_noop_accuracy"]) >= 0.70)

    ready_for_unity = bool(
        original_preserved
        and guards_preserved
        and movement_preserved
        and valid_move_improved
        and occupied_reduced
        and off_actor_controlled
    )

    if ready_for_unity:
        gate = "GO_FOR_STAGE10D20_UNITY_VALID_MOVE_RERUN"
    elif not original_preserved or not guards_preserved or not movement_preserved:
        gate = "GO_FOR_STAGE10D19B_TRAINING_BALANCE_FIX"
    elif not valid_move_improved or not occupied_reduced:
        gate = "GO_FOR_STAGE10D19B_AUGMENTATION_REDESIGN"
    elif not off_actor_controlled:
        gate = "GO_FOR_STAGE10D19B_OFF_ACTOR_NEGATIVE_CONTROL_FIX"
    else:
        gate = "GO_FOR_STAGE10D19B_DEEPER_OFFLINE_REPLAY_AUDIT"

    labels = [
        "STAGE10D19B_ORIGINAL_PERFORMANCE_PRESERVED" if original_preserved else "STAGE10D19B_NOT_READY_FOR_UNITY",
        "STAGE10D19B_B2_C3_GUARDS_PRESERVED" if guards_preserved else "STAGE10D19B_NOT_READY_FOR_UNITY",
        "STAGE10D19B_MOVEMENT_PRESERVED" if movement_preserved else "STAGE10D19B_NOT_READY_FOR_UNITY",
        "STAGE10D19B_VALID_MOVE_TARGET_SELECTION_IMPROVED_OFFLINE" if valid_move_improved else "STAGE10D19B_NOT_READY_FOR_UNITY",
        "STAGE10D19B_OCCUPIED_TARGET_ERRORS_REDUCED_OFFLINE" if occupied_reduced else "STAGE10D19B_NOT_READY_FOR_UNITY",
        "STAGE10D19B_OFF_ACTOR_RISK_REDUCED_OR_CONTROLLED" if off_actor_controlled else "STAGE10D19B_NOT_READY_FOR_UNITY",
        "STAGE10D19B_ATTACK_NOT_EVALUATED_AS_PRIMARY",
        "STAGE10D19B_READY_FOR_UNITY_VALID_MOVE_RERUN" if ready_for_unity else "STAGE10D19B_NOT_READY_FOR_UNITY",
    ]

    report: Dict[str, Any] = {
        "stage": "10D.19B",
        "task": "offline_eval_valid_move_student",
        "generated_at_utc": utc_now_iso(),
        "checkpoint": str(checkpoint.as_posix()),
        "augmented_bc_ready_dir": str(bc_dir.as_posix()),
        "block_a_original_validation_preservation": {
            "actor_action_accuracy": float(eval_a["actor_cell_action_type_accuracy"]),
            "actor_non_noop_recall": float(eval_a["actor_cell_non_noop_recall"]),
            "worker_harvest_recall": float(eval_a["worker_harvest_recall"]),
            "base_produce_recall": float(eval_a["base_produce_recall"]),
        },
        "block_b_stage10d17_movement_preservation": {
            "movement_recall": float(eval_c_val["valid_move_recall"]),
            "move_dir_accuracy": float(eval_c_val["valid_move_dir_accuracy"]),
            "produced_unit_move_success_proxy": float(eval_c_val["valid_move_recall"]),
        },
        "block_c_stage10d19b_validation": {
            "train": eval_c_train,
            "validation": eval_c_val,
        },
        "block_d_stage10d18rr_replay_proxy": {
            "total_move_predictions": int(eval_c_val["total_move_predictions"]),
            "predicted_valid_target_moves": int(eval_c_val["predicted_valid_target_moves"]),
            "predicted_occupied_or_invalid_target_moves": int(eval_c_val["predicted_occupied_or_invalid_target_moves"]),
            "estimated_prediction_to_build_readiness": float(eval_c_val["estimated_prediction_to_build_readiness"]),
            "off_actor_non_noop_count": int(eval_c_val["off_actor_non_noop_count"]),
            "off_actor_command_risk_if_inferable": eval_c_val["off_actor_command_risk_if_inferable"],
            "b2": true_raw_summary["B2"],
            "c3": true_raw_summary["C3"],
        },
        "block_e_attack_watch_only": {
            "max_p_attack": float(eval_c_val["attack_max_probability_watch"]),
            "true_raw_b2_p_attack": float(true_raw_summary["B2"]["p_attack"]),
            "true_raw_c3_p_attack": float(true_raw_summary["C3"]["p_attack"]),
            "notes": "Attack is watch-only in Stage10D.19B. No attack optimization performed.",
        },
        "classification_labels": labels,
        "primary_next_gate": gate,
    }

    write_json(args.output_report, report)

    if args.emit_snapshot_replay:
        snapshot_report = {
            "stage": "10D.19B",
            "task": "stage10d18rr_snapshot_replay_report",
            "generated_at_utc": utc_now_iso(),
            "checkpoint": str(checkpoint.as_posix()),
            **snapshot_payload,
        }
        write_json(args.output_snapshot_replay, snapshot_report)

    print(resolve_path(args.output_report).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
