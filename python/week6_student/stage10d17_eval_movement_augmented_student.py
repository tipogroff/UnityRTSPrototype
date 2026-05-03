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
    read_jsonl,
    run_model_action_type_probs,
    summarize_true_raw_predictions,
    utc_now_iso,
    write_json,
)
from stage10d17_common import (
    ACTION_TYPE_MOVE,
    OWNER_SELF_INDEX,
    UNIT_TYPE_SLICE,
    get_observations_and_actions,
    load_json,
    load_split_payload,
    resolve_path,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.17 offline eval and Stage10D.16 replay diagnostics")
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--augmented-bc-ready-dir", type=Path, required=True)
    p.add_argument("--true-raw-capture", type=Path, default=Path(DEFAULT_TRUE_RAW_CAPTURE))
    p.add_argument(
        "--output-report",
        type=Path,
        default=Path("python/week6_student/reports/stage10d17_offline_eval_report.json"),
    )
    p.add_argument(
        "--output-snapshot-replay",
        type=Path,
        default=Path("python/week6_student/reports/stage10d17_stage10d16_snapshot_replay_report.json"),
    )
    p.add_argument("--emit-snapshot-replay", action="store_true")
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--device", type=str, default="cpu")
    return p.parse_args()


def _is_actor_mask(obs_rows: np.ndarray) -> np.ndarray:
    return np.asarray((obs_rows[:, :, OWNER_SELF_INDEX] > 0.5) & (np.sum(obs_rows[:, :, UNIT_TYPE_SLICE], axis=2) > 0.5), dtype=bool)


def _predict_action_and_move_dir(model: torch.nn.Module, obs: np.ndarray, device: torch.device, batch_size: int) -> tuple[np.ndarray, np.ndarray]:
    model.eval()
    a_list: List[np.ndarray] = []
    d_list: List[np.ndarray] = []
    obs4 = np.asarray(obs, dtype=np.float32)
    if obs4.ndim == 3 and obs4.shape[1:] == (576, 27):
        obs4 = obs4.reshape((-1, 24, 24, 27))
    with torch.no_grad():
        for s in range(0, obs4.shape[0], batch_size):
            e = min(s + batch_size, obs4.shape[0])
            x = torch.from_numpy(obs4[s:e]).to(device=device, dtype=torch.float32)
            out = model(x)
            a_list.append(torch.argmax(out["action_type_logits"], dim=-1).cpu().numpy())
            d_list.append(torch.argmax(out["move_dir_logits"], dim=-1).cpu().numpy())
    return np.concatenate(a_list, axis=0), np.concatenate(d_list, axis=0)


def _eval_movement_subset(
    *,
    model: torch.nn.Module,
    observations: np.ndarray,
    actions: np.ndarray,
    metadata: Sequence[Mapping[str, Any]],
    original_count: int,
    device: torch.device,
    batch_size: int,
) -> Dict[str, Any]:
    if len(metadata) == 0:
        return {
            "sample_count": 0,
            "move_target_count": 0,
            "move_recall": 0.0,
            "move_dir_accuracy": 0.0,
            "produced_unit_move_success_rate": 0.0,
            "off_actor_non_noop_count": 0,
        }

    idx = np.arange(original_count, original_count + len(metadata), dtype=np.int64)
    obs_sub = np.asarray(observations[idx], dtype=np.float32)
    act_sub = np.asarray(actions[idx], dtype=np.int64)
    pred_action, pred_dir = _predict_action_and_move_dir(model, obs_sub, device, batch_size)

    actor_mask = _is_actor_mask(obs_sub)
    off_actor_non_noop = int(np.sum(pred_action[~actor_mask] != 0))

    move_total = 0
    move_ok = 0
    move_dir_ok = 0
    produced_total = 0
    produced_ok = 0

    for i, row in enumerate(metadata):
        tgt = int(row.get("target_cell", -1))
        target_action = int(row.get("target_action_type", -1))
        if target_action != ACTION_TYPE_MOVE or tgt < 0:
            continue
        move_total += 1
        if int(pred_action[i, tgt]) == ACTION_TYPE_MOVE:
            move_ok += 1
            if int(pred_dir[i, tgt]) == int(act_sub[i, tgt, 1]):
                move_dir_ok += 1

        if str(row.get("source", "")).startswith("stage10d16"):
            produced_total += 1
            if int(pred_action[i, tgt]) == ACTION_TYPE_MOVE:
                produced_ok += 1

    return {
        "sample_count": int(len(metadata)),
        "move_target_count": int(move_total),
        "move_recall": float(move_ok / max(1, move_total)),
        "move_dir_accuracy": float(move_dir_ok / max(1, move_ok)),
        "produced_unit_move_success_rate": float(produced_ok / max(1, produced_total)),
        "off_actor_non_noop_count": int(off_actor_non_noop),
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

    aug_manifest = load_json(bc_dir / "stage10d17_movement_augmentation_manifest.json")
    original_train = int(aug_manifest["counts"]["original_train"])
    original_val = int(aug_manifest["counts"]["original_validation"])

    meta_train = read_jsonl(bc_dir / "stage10d17_augmented_sample_metadata_train.jsonl")
    meta_val = read_jsonl(bc_dir / "stage10d17_augmented_sample_metadata_validation.jsonl")

    # A) Original validation contract preservation.
    eval_a = evaluate_action_type_subset(
        model,
        val_obs.reshape((-1, 24, 24, 27)),
        val_actions,
        indices=np.arange(original_val, dtype=np.int64),
        device=device,
        batch_size=int(args.batch_size),
    )

    # B) True raw B2/C3 and off-actor behavior.
    true_raw = load_true_raw_capture_tensor(args.true_raw_capture)
    true_raw_probs = run_model_action_type_probs(model, true_raw, device)
    true_raw_summary = summarize_true_raw_predictions(true_raw_probs, true_raw)

    # C) Movement-labeled subset performance.
    eval_c_val = _eval_movement_subset(
        model=model,
        observations=val_obs,
        actions=val_actions,
        metadata=meta_val,
        original_count=original_val,
        device=device,
        batch_size=int(args.batch_size),
    )
    eval_c_train = _eval_movement_subset(
        model=model,
        observations=train_obs,
        actions=train_actions,
        metadata=meta_train,
        original_count=original_train,
        device=device,
        batch_size=int(args.batch_size),
    )

    # D) Stage10D16-style replay (runtime proxy subset).
    replay_meta_val = [r for r in meta_val if str(r.get("source", "")).startswith("stage10d16")]
    replay_meta_train = [r for r in meta_train if str(r.get("source", "")).startswith("stage10d16")]
    eval_d_val = _eval_movement_subset(
        model=model,
        observations=val_obs,
        actions=val_actions,
        metadata=replay_meta_val,
        original_count=original_val,
        device=device,
        batch_size=int(args.batch_size),
    )
    eval_d_train = _eval_movement_subset(
        model=model,
        observations=train_obs,
        actions=train_actions,
        metadata=replay_meta_train,
        original_count=original_train,
        device=device,
        batch_size=int(args.batch_size),
    )

    report: Dict[str, Any] = {
        "stage": "10D.17",
        "task": "offline_eval_movement_augmented_student",
        "generated_at_utc": utc_now_iso(),
        "checkpoint": str(checkpoint.as_posix()),
        "augmented_bc_ready_dir": str(bc_dir.as_posix()),
        "block_a_original_validation": {
            "actor_action_type_accuracy": float(eval_a["actor_cell_action_type_accuracy"]),
            "actor_non_noop_recall": float(eval_a["actor_cell_non_noop_recall"]),
            "worker_harvest_recall": float(eval_a["worker_harvest_recall"]),
            "base_produce_recall": float(eval_a["base_produce_recall"]),
        },
        "block_b_true_raw": {
            "B2": true_raw_summary["B2"],
            "C3": true_raw_summary["C3"],
            "off_actor_non_noop_count": int(true_raw_summary["off_actor_non_noop_count"]),
            "off_actor_non_noop_cells": int(true_raw_summary.get("off_actor_non_noop_cells", 0)),
        },
        "block_c_movement_augmented_subset": {
            "train": eval_c_train,
            "validation": eval_c_val,
        },
        "block_d_stage10d16_replay": {
            "train": eval_d_train,
            "validation": eval_d_val,
        },
        "classification_labels": [
            "STAGE10D17_OFFLINE_EVAL_COMPLETE",
            "MOVEMENT_REPLAY_COVERED" if (eval_d_train["sample_count"] + eval_d_val["sample_count"]) > 0 else "MOVEMENT_REPLAY_MISSING",
            "TRUE_RAW_B2_C3_EVALUATED",
        ],
    }
    write_json(args.output_report, report)

    if args.emit_snapshot_replay:
        snapshot_report = {
            "stage": "10D.17",
            "task": "stage10d16_snapshot_replay_report",
            "generated_at_utc": utc_now_iso(),
            "checkpoint": str(checkpoint.as_posix()),
            "validation": eval_d_val,
            "train": eval_d_train,
            "notes": [
                "Replay uses Stage10D17 runtime-proxy rows sourced from Stage10D16 trace/lifecycle metadata.",
            ],
        }
        write_json(args.output_snapshot_replay, snapshot_report)

    print(resolve_path(args.output_report).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
