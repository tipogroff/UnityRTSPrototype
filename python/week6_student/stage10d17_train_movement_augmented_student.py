#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

import numpy as np
import torch
from torch import nn
from torch.optim import Adam

from stage10d14_common import (
    DEFAULT_TRUE_RAW_CAPTURE,
    evaluate_action_type_subset,
    load_model_strict,
    load_true_raw_capture_tensor,
    read_jsonl,
    run_model_action_type_probs,
    summarize_true_raw_predictions,
    utc_dir_stamp,
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
from stage10d8_train_student_bc_semantic import (
    _checkpoint_payload,
    create_loader,
    run_epoch,
    set_seed,
)
from student_architecture_transfer import build_day3_student_model
from student_branch_contract import validate_student_branch_contract_consistency


@dataclass(frozen=True)
class Stage10D17TrainConfig:
    bc_ready_dir: str
    run_dir: str
    init_checkpoint: str | None
    epochs: int
    batch_size: int
    learning_rate: float
    device: str
    seed: int
    gradient_clip_norm: float
    actor_cell_loss_weight: float
    patience: int


def _default_runs_dir() -> Path:
    return resolve_path("python/week6_student/runs") / f"legacy032_v2_stage10d17_movement_augmented_bc_{utc_dir_stamp()}"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.17 supervised BC fine-tuning on movement augmented dataset")
    p.add_argument("--bc-ready-dir", type=Path, required=True)
    p.add_argument("--run-dir", type=Path, default=None)
    p.add_argument(
        "--init-checkpoint",
        type=Path,
        default=Path(
            "python/week6_student/runs/legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z/student_bc_stage10d14_augmented_best.pt"
        ),
    )
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--learning-rate", type=float, default=1e-4)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--gradient-clip-norm", type=float, default=1.0)
    p.add_argument("--actor-cell-loss-weight", type=float, default=1.0)
    p.add_argument("--patience", type=int, default=2)
    p.add_argument("--max-train-samples", type=int, default=0)
    p.add_argument("--max-val-samples", type=int, default=0)
    p.add_argument("--true-raw-capture", type=Path, default=Path(DEFAULT_TRUE_RAW_CAPTURE))
    return p.parse_args()


def _is_actor_mask(obs_rows: np.ndarray) -> np.ndarray:
    return np.asarray((obs_rows[:, :, OWNER_SELF_INDEX] > 0.5) & (np.sum(obs_rows[:, :, UNIT_TYPE_SLICE], axis=2) > 0.5), dtype=bool)


def _predict_action_and_move_dir(model: nn.Module, obs: np.ndarray, device: torch.device, batch_size: int) -> tuple[np.ndarray, np.ndarray]:
    action_preds: List[np.ndarray] = []
    move_dir_preds: List[np.ndarray] = []
    obs4 = np.asarray(obs, dtype=np.float32)
    if obs4.ndim == 3 and obs4.shape[1:] == (576, 27):
        obs4 = obs4.reshape((-1, 24, 24, 27))
    model.eval()
    with torch.no_grad():
        for start in range(0, obs4.shape[0], batch_size):
            stop = min(start + batch_size, obs4.shape[0])
            x = torch.from_numpy(obs4[start:stop]).to(device=device, dtype=torch.float32)
            out = model(x)
            action_preds.append(torch.argmax(out["action_type_logits"], dim=-1).cpu().numpy())
            move_dir_preds.append(torch.argmax(out["move_dir_logits"], dim=-1).cpu().numpy())
    return np.concatenate(action_preds, axis=0), np.concatenate(move_dir_preds, axis=0)


def _evaluate_move_subset(
    model: nn.Module,
    observations: np.ndarray,
    actions: np.ndarray,
    metadata_rows: Sequence[Mapping[str, Any]],
    *,
    original_count: int,
    device: torch.device,
    batch_size: int,
) -> Dict[str, Any]:
    if not metadata_rows:
        return {
            "sample_count": 0,
            "move_target_count": 0,
            "move_recall": 0.0,
            "move_dir_accuracy": 0.0,
            "produced_unit_move_success_rate": 0.0,
        }

    idx = np.arange(original_count, original_count + len(metadata_rows), dtype=np.int64)
    obs_sub = np.asarray(observations[idx], dtype=np.float32)
    act_sub = np.asarray(actions[idx], dtype=np.int64)
    pred_action, pred_move_dir = _predict_action_and_move_dir(model, obs_sub, device, batch_size)

    move_total = 0
    move_ok = 0
    move_dir_ok = 0
    produced_total = 0
    produced_ok = 0

    for i, row in enumerate(metadata_rows):
        target_action = int(row.get("target_action_type", -1))
        target_flat = int(row.get("target_cell", -1))
        if target_action != ACTION_TYPE_MOVE or target_flat < 0:
            continue
        move_total += 1
        if int(pred_action[i, target_flat]) == ACTION_TYPE_MOVE:
            move_ok += 1
            if int(pred_move_dir[i, target_flat]) == int(act_sub[i, target_flat, 1]):
                move_dir_ok += 1

        if str(row.get("source", "")).startswith("stage10d16"):
            produced_total += 1
            if int(pred_action[i, target_flat]) == ACTION_TYPE_MOVE:
                produced_ok += 1

    return {
        "sample_count": int(len(metadata_rows)),
        "move_target_count": int(move_total),
        "move_recall": float(move_ok / max(1, move_total)),
        "move_dir_accuracy": float(move_dir_ok / max(1, move_ok)),
        "produced_unit_move_success_rate": float(produced_ok / max(1, produced_total)),
    }


def _stage10d16_replay_off_actor(
    model: nn.Module,
    observations: np.ndarray,
    metadata_rows: Sequence[Mapping[str, Any]],
    *,
    original_count: int,
    device: torch.device,
    batch_size: int,
) -> Dict[str, Any]:
    selected = [i for i, r in enumerate(metadata_rows) if str(r.get("source", "")).startswith("stage10d16")]
    if not selected:
        return {
            "sample_count": 0,
            "off_actor_non_noop_count": 0,
            "produced_unit_move_predictions": 0,
        }

    idx = np.asarray([original_count + i for i in selected], dtype=np.int64)
    obs_sub = np.asarray(observations[idx], dtype=np.float32)
    pred_action, _ = _predict_action_and_move_dir(model, obs_sub, device, batch_size)

    actor = _is_actor_mask(obs_sub)
    off_actor_non_noop = int(np.sum(pred_action[~actor] != 0))

    move_preds = 0
    for local_i, meta_i in enumerate(selected):
        tgt = int(metadata_rows[meta_i].get("target_cell", -1))
        if tgt >= 0 and int(pred_action[local_i, tgt]) == ACTION_TYPE_MOVE:
            move_preds += 1

    return {
        "sample_count": int(len(selected)),
        "off_actor_non_noop_count": int(off_actor_non_noop),
        "produced_unit_move_predictions": int(move_preds),
    }


def _selection_score(epoch_metrics: Mapping[str, Any]) -> tuple[float, ...]:
    b2_ok = float(epoch_metrics.get("true_raw_B2_p_harvest", 0.0)) >= float(epoch_metrics.get("true_raw_B2_p_noop", 1.0))
    c3_ok = float(epoch_metrics.get("true_raw_C3_p_produce", 0.0)) >= float(epoch_metrics.get("true_raw_C3_p_noop", 1.0))
    return (
        1.0 if b2_ok else 0.0,
        1.0 if c3_ok else 0.0,
        float(epoch_metrics.get("movement_augmented_val_move_recall", 0.0)),
        float(epoch_metrics.get("stage10d16_replay_move_success_rate", 0.0)),
        -float(epoch_metrics.get("off_actor_non_noop_stage10d16_replay", 1e9)),
        -float(epoch_metrics.get("off_actor_non_noop_true_raw", 1e9)),
        float(epoch_metrics.get("original_val_actor_action_type_accuracy", 0.0)),
        float(epoch_metrics.get("worker_harvest_recall", 0.0)),
        float(epoch_metrics.get("base_produce_recall", 0.0)),
        -float(epoch_metrics.get("val_total_loss", 1e9)),
    )


def main() -> int:
    args = parse_args()
    set_seed(int(args.seed))
    validate_student_branch_contract_consistency()

    bc_ready_dir = resolve_path(args.bc_ready_dir).resolve()
    run_dir = resolve_path(args.run_dir).resolve() if args.run_dir is not None else _default_runs_dir().resolve()
    init_checkpoint = resolve_path(args.init_checkpoint).resolve() if args.init_checkpoint is not None else None
    if run_dir.exists():
        raise RuntimeError(f"Refusing overwrite: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    cfg = Stage10D17TrainConfig(
        bc_ready_dir=str(bc_ready_dir),
        run_dir=str(run_dir),
        init_checkpoint=(None if init_checkpoint is None else str(init_checkpoint)),
        epochs=int(args.epochs),
        batch_size=int(args.batch_size),
        learning_rate=float(args.learning_rate),
        device=str(args.device),
        seed=int(args.seed),
        gradient_clip_norm=float(args.gradient_clip_norm),
        actor_cell_loss_weight=float(args.actor_cell_loss_weight),
        patience=int(args.patience),
    )

    train_payload = load_split_payload(bc_ready_dir / "bc_train.npz")
    val_payload = load_split_payload(bc_ready_dir / "bc_validation.npz")
    train_obs, train_actions = get_observations_and_actions(train_payload)
    val_obs, val_actions = get_observations_and_actions(val_payload)

    if int(args.max_train_samples) > 0 and train_obs.shape[0] > int(args.max_train_samples):
        pick = np.random.default_rng(cfg.seed).choice(train_obs.shape[0], size=int(args.max_train_samples), replace=False)
        train_obs = train_obs[pick]
        train_actions = train_actions[pick]
    if int(args.max_val_samples) > 0 and val_obs.shape[0] > int(args.max_val_samples):
        pick = np.random.default_rng(cfg.seed + 1).choice(val_obs.shape[0], size=int(args.max_val_samples), replace=False)
        val_obs = val_obs[pick]
        val_actions = val_actions[pick]

    aug_manifest = load_json(bc_ready_dir / "stage10d17_movement_augmentation_manifest.json")
    original_val_count = int(aug_manifest["counts"]["original_validation"])
    val_meta = read_jsonl(bc_ready_dir / "stage10d17_augmented_sample_metadata_validation.jsonl")

    train_loader = create_loader(
        type("Split", (), {"input_tensor": train_obs.reshape((-1, 24, 24, 27)), "target_action_branches": train_actions})(),
        batch_size=cfg.batch_size,
        shuffle=True,
        seed=cfg.seed,
    )
    val_loader = create_loader(
        type("Split", (), {"input_tensor": val_obs.reshape((-1, 24, 24, 27)), "target_action_branches": val_actions})(),
        batch_size=cfg.batch_size,
        shuffle=False,
        seed=cfg.seed,
    )

    device = torch.device(cfg.device)
    model = build_day3_student_model().to(device=device)
    if init_checkpoint is not None:
        model = load_model_strict(init_checkpoint, device=device)
    optimizer = Adam(model.parameters(), lr=cfg.learning_rate)

    true_raw_map = load_true_raw_capture_tensor(args.true_raw_capture)

    write_json(
        run_dir / "training_config.json",
        {
            "stage": "10D.17",
            "config": asdict(cfg),
            "original_validation_count": int(original_val_count),
            "augmented_validation_count": int(len(val_meta)),
            "explicit_non_claims": [
                "Supervised BC fine-tuning only",
                "No PPO",
                "No teacher mutation",
                "No runtime semantics changes",
            ],
        },
    )

    history: List[Dict[str, Any]] = []
    ckpt_by_epoch: Dict[int, Path] = {}
    best_score: tuple[float, ...] | None = None
    best_epoch = -1
    no_improve = 0

    for epoch in range(1, cfg.epochs + 1):
        start_t = time.perf_counter()
        train_metrics = run_epoch(
            model=model,
            loader=train_loader,
            device=device,
            optimizer=optimizer,
            actor_cell_loss_weight=cfg.actor_cell_loss_weight,
            gradient_clip_norm=cfg.gradient_clip_norm,
        )
        val_metrics = run_epoch(
            model=model,
            loader=val_loader,
            device=device,
            optimizer=None,
            actor_cell_loss_weight=cfg.actor_cell_loss_weight,
            gradient_clip_norm=cfg.gradient_clip_norm,
        )

        original_eval = evaluate_action_type_subset(
            model,
            val_obs.reshape((-1, 24, 24, 27)),
            val_actions,
            indices=np.arange(original_val_count, dtype=np.int64),
            device=device,
            batch_size=cfg.batch_size,
        )

        move_eval = _evaluate_move_subset(
            model,
            val_obs,
            val_actions,
            val_meta,
            original_count=original_val_count,
            device=device,
            batch_size=cfg.batch_size,
        )

        replay_eval = _stage10d16_replay_off_actor(
            model,
            val_obs,
            val_meta,
            original_count=original_val_count,
            device=device,
            batch_size=cfg.batch_size,
        )

        true_raw_probs = run_model_action_type_probs(model, true_raw_map, device)
        true_raw_summary = summarize_true_raw_predictions(true_raw_probs, true_raw_map)

        row: Dict[str, Any] = {}
        row.update(train_metrics)
        row.update(val_metrics)
        row.update(
            {
                "original_val_actor_action_type_accuracy": float(original_eval["actor_cell_action_type_accuracy"]),
                "original_val_actor_non_noop_recall": float(original_eval["actor_cell_non_noop_recall"]),
                "worker_harvest_recall": float(original_eval["worker_harvest_recall"]),
                "base_produce_recall": float(original_eval["base_produce_recall"]),
                "movement_augmented_val_move_recall": float(move_eval["move_recall"]),
                "movement_augmented_val_move_dir_accuracy": float(move_eval["move_dir_accuracy"]),
                "stage10d16_replay_move_success_rate": float(move_eval["produced_unit_move_success_rate"]),
                "true_raw_B2_p_harvest": float(true_raw_summary["B2"]["p_harvest"]),
                "true_raw_B2_p_noop": float(true_raw_summary["B2"]["p_noop"]),
                "true_raw_C3_p_produce": float(true_raw_summary["C3"]["p_produce"]),
                "true_raw_C3_p_noop": float(true_raw_summary["C3"]["p_noop"]),
                "off_actor_non_noop_true_raw": int(true_raw_summary["off_actor_non_noop_count"]),
                "off_actor_non_noop_stage10d16_replay": int(replay_eval["off_actor_non_noop_count"]),
                "epoch": int(epoch),
                "epoch_time_sec": float(time.perf_counter() - start_t),
            }
        )
        history.append(row)

        ckpt_path = run_dir / f"epoch_{epoch:03d}.pt"
        torch.save(
            _checkpoint_payload(
                model=model,
                optimizer=optimizer,
                epoch=epoch,
                metrics=row,
                config=cfg,
                dataset_manifest=aug_manifest,
            ),
            ckpt_path,
        )
        ckpt_by_epoch[epoch] = ckpt_path

        score = _selection_score(row)
        if best_score is None or score > best_score:
            best_score = score
            best_epoch = epoch
            no_improve = 0
        else:
            no_improve += 1

        print(
            "[epoch={}] val_loss={:.6f} move_recall={:.4f} move_dir_acc={:.4f} b2_h={:.4f} c3_p={:.4f} off_actor_replay={}".format(
                epoch,
                float(row["val_total_loss"]),
                float(row["movement_augmented_val_move_recall"]),
                float(row["movement_augmented_val_move_dir_accuracy"]),
                float(row["true_raw_B2_p_harvest"]),
                float(row["true_raw_C3_p_produce"]),
                int(row["off_actor_non_noop_stage10d16_replay"]),
            )
        )

        if no_improve >= cfg.patience:
            print(f"[early-stop] patience reached at epoch {epoch}")
            break

    if best_epoch < 0:
        raise RuntimeError("No epoch completed")

    best_path = run_dir / "student_bc_stage10d17_movement_augmented_best.pt"
    final_path = run_dir / "student_bc_stage10d17_movement_augmented_final.pt"
    torch.save(torch.load(ckpt_by_epoch[best_epoch], map_location="cpu"), best_path)
    torch.save(torch.load(ckpt_by_epoch[max(ckpt_by_epoch.keys())], map_location="cpu"), final_path)
    for p in ckpt_by_epoch.values():
        p.unlink(missing_ok=True)

    best_metrics = next(r for r in history if int(r["epoch"]) == best_epoch)
    final_metrics = history[-1]

    write_json(
        run_dir / "stage10d17_training_history.json",
        {
            "stage": "10D.17",
            "run_dir": str(run_dir.as_posix()),
            "best_epoch": int(best_epoch),
            "history": history,
            "best_checkpoint": str(best_path.as_posix()),
            "final_checkpoint": str(final_path.as_posix()),
        },
    )
    write_json(
        run_dir / "stage10d17_training_selection.json",
        {
            "stage": "10D.17",
            "generated_at_utc": utc_now_iso(),
            "selected_epoch": int(best_epoch),
            "selection_score": list(best_score) if best_score is not None else None,
            "best_metrics": best_metrics,
            "final_metrics": final_metrics,
        },
    )

    print(best_path.as_posix())
    print(final_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
