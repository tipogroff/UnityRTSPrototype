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
    DEFAULT_STAGE10D8_CHECKPOINT,
    DEFAULT_TRUE_RAW_CAPTURE,
    DEFAULT_RUNS_ROOT,
    evaluate_action_type_subset,
    evaluate_augmented_target_success,
    load_json,
    load_model_strict,
    load_true_raw_capture_tensor,
    read_jsonl,
    repo_root,
    resolve_path,
    run_model_action_type_probs,
    summarize_true_raw_predictions,
    utc_dir_stamp,
    utc_now_iso,
    write_json,
)
from stage10d8_train_student_bc_semantic import (
    _checkpoint_payload,
    create_loader,
    run_epoch,
    set_seed,
)
from student_architecture_transfer import build_day3_student_model
from student_bc_loader import load_bc_ready_dataset
from student_branch_contract import validate_student_branch_contract_consistency


@dataclass(frozen=True)
class Stage10D14TrainConfig:
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


def _default_run_dir() -> Path:
    return resolve_path(DEFAULT_RUNS_ROOT) / f"legacy032_v2_stage10d14_unity_like_augmented_bc_{utc_dir_stamp()}"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.14 supervised BC fine-tuning on Unity-like augmented dataset")
    p.add_argument("--bc-ready-dir", type=Path, required=True)
    p.add_argument("--run-dir", type=Path, default=None)
    p.add_argument("--init-checkpoint", type=Path, default=Path(DEFAULT_STAGE10D8_CHECKPOINT))
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--learning-rate", type=float, default=1e-4)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--gradient-clip-norm", type=float, default=1.0)
    p.add_argument("--actor-cell-loss-weight", type=float, default=1.0)
    p.add_argument("--patience", type=int, default=2)
    p.add_argument("--true-raw-capture", type=Path, default=Path(DEFAULT_TRUE_RAW_CAPTURE))
    return p.parse_args()


def _validate_stage10d14_dataset(manifest: Mapping[str, Any], dataset: Any) -> None:
    checks = {
        "schema_version": manifest.get("schema_version") == "day6.bc_ready.v1",
        "observation_shape": list(manifest.get("observation_shape", [])) == [576, 27],
        "action_shape": list(manifest.get("action_shape", [])) == [576, 7],
        "branch_sizes": list(manifest.get("branch_sizes", [])) == [6, 4, 4, 4, 4, 7, 49],
        "train_input_shape": tuple(dataset.train.input_tensor.shape[1:]) == (24, 24, 27),
        "train_target_shape": tuple(dataset.train.target_action_branches.shape[1:]) == (576, 7),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise RuntimeError(f"Stage10D.14 contract mismatch: {failed}")


def _selection_score(epoch_metrics: Mapping[str, Any]) -> tuple[float, ...]:
    b2 = epoch_metrics.get("true_raw_B2_predicted_action") == "harvest" or float(epoch_metrics.get("true_raw_B2_p_harvest", 0.0)) > 0.5
    c3 = epoch_metrics.get("true_raw_C3_predicted_action") == "produce" or float(epoch_metrics.get("true_raw_C3_p_produce", 0.0)) > 0.5
    return (
        1.0 if b2 else 0.0,
        1.0 if c3 else 0.0,
        float(epoch_metrics.get("true_raw_B2_p_harvest", 0.0)),
        float(epoch_metrics.get("true_raw_C3_p_produce", 0.0)),
        float(epoch_metrics.get("augmented_target_B2_success_rate", 0.0)),
        float(epoch_metrics.get("augmented_target_C3_success_rate", 0.0)),
        float(epoch_metrics.get("original_val_actor_action_accuracy", 0.0)),
        float(epoch_metrics.get("original_val_actor_non_noop_recall", 0.0)),
        -float(epoch_metrics.get("val_total_loss", 1e9)),
    )


def _evaluate_epoch_targets(
    *,
    model: nn.Module,
    validation_observations: np.ndarray,
    validation_actions: np.ndarray,
    original_validation_count: int,
    augmented_validation_metadata: Sequence[Mapping[str, Any]],
    runtime_map: np.ndarray,
    device: torch.device,
    batch_size: int,
) -> Dict[str, Any]:
    original_indices = np.arange(original_validation_count, dtype=np.int64)
    augmented_indices = np.arange(original_validation_count, validation_observations.shape[0], dtype=np.int64)

    original_metrics = evaluate_action_type_subset(
        model,
        validation_observations,
        validation_actions,
        indices=original_indices,
        device=device,
        batch_size=batch_size,
    )
    augmented_metrics = evaluate_action_type_subset(
        model,
        validation_observations,
        validation_actions,
        indices=augmented_indices,
        device=device,
        batch_size=batch_size,
    )
    targeted_metrics = evaluate_augmented_target_success(
        model,
        validation_observations,
        augmented_validation_metadata,
        original_count=original_validation_count,
        device=device,
        batch_size=batch_size,
    )
    true_raw_probs = run_model_action_type_probs(model, runtime_map, device)
    true_raw_summary = summarize_true_raw_predictions(true_raw_probs, runtime_map)

    return {
        "original_val_actor_action_accuracy": float(original_metrics["actor_cell_action_type_accuracy"]),
        "original_val_actor_non_noop_recall": float(original_metrics["actor_cell_non_noop_recall"]),
        "original_val_worker_harvest_recall": float(original_metrics["worker_harvest_recall"]),
        "original_val_base_produce_recall": float(original_metrics["base_produce_recall"]),
        "original_val_predicted_noop_share_all_cells": float(original_metrics["predicted_noop_share_all_cells"]),
        "augmented_val_actor_action_accuracy": float(augmented_metrics["actor_cell_action_type_accuracy"]),
        "augmented_val_actor_non_noop_recall": float(augmented_metrics["actor_cell_non_noop_recall"]),
        "augmented_target_B2_success_rate": float(targeted_metrics["B2_success_rate"]),
        "augmented_target_C3_success_rate": float(targeted_metrics["C3_success_rate"]),
        "true_raw_B2_predicted_action": true_raw_summary["B2"]["predicted_action"],
        "true_raw_B2_p_noop": float(true_raw_summary["B2"]["p_noop"]),
        "true_raw_B2_p_harvest": float(true_raw_summary["B2"]["p_harvest"]),
        "true_raw_B2_p_produce": float(true_raw_summary["B2"]["p_produce"]),
        "true_raw_C3_predicted_action": true_raw_summary["C3"]["predicted_action"],
        "true_raw_C3_p_noop": float(true_raw_summary["C3"]["p_noop"]),
        "true_raw_C3_p_harvest": float(true_raw_summary["C3"]["p_harvest"]),
        "true_raw_C3_p_produce": float(true_raw_summary["C3"]["p_produce"]),
        "off_actor_non_noop_count": int(true_raw_summary["off_actor_non_noop_count"]),
        "global_predicted_noop_share": float(true_raw_summary["global_predicted_noop_share"]),
        "actor_predicted_noop_share": float(true_raw_summary["actor_predicted_noop_share"]),
    }


def main() -> int:
    args = parse_args()
    set_seed(int(args.seed))
    validate_student_branch_contract_consistency()

    bc_ready_dir = resolve_path(args.bc_ready_dir).resolve()
    run_dir = resolve_path(args.run_dir).resolve() if args.run_dir is not None else _default_run_dir().resolve()
    init_checkpoint = None if args.init_checkpoint is None else resolve_path(args.init_checkpoint).resolve()
    runtime_map = load_true_raw_capture_tensor(args.true_raw_capture)

    if run_dir.exists():
        raise RuntimeError(f"Refusing overwrite of existing run dir: {run_dir}")

    dataset = load_bc_ready_dataset(bc_ready_dir)
    manifest = load_json(bc_ready_dir / "bc_manifest.json")
    augmentation_manifest = load_json(bc_ready_dir / "stage10d14_augmentation_manifest.json")
    _validate_stage10d14_dataset(manifest, dataset)

    original_validation_count = int(augmentation_manifest["counts"]["original_validation_count"])
    augmented_validation_metadata = read_jsonl(bc_ready_dir / "stage10d14_augmented_sample_metadata_validation.jsonl")

    run_dir.mkdir(parents=True, exist_ok=False)
    cfg = Stage10D14TrainConfig(
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

    write_json(
        run_dir / "training_config.json",
        {
            "stage": "10D.14",
            "training_scope": "targeted_augmented_bc_supervised_finetuning_only",
            "config": asdict(cfg),
            "dataset_manifest_summary": {
                "schema_version": manifest.get("schema_version"),
                "dataset_kind": manifest.get("dataset_kind"),
                "source_stage": manifest.get("source_stage"),
                "observation_shape": manifest.get("observation_shape"),
                "action_shape": manifest.get("action_shape"),
                "branch_sizes": manifest.get("branch_sizes"),
                "num_train": manifest.get("num_train"),
                "num_validation": manifest.get("num_validation"),
            },
            "original_validation_count": original_validation_count,
            "augmented_validation_count": int(len(augmented_validation_metadata)),
            "explicit_non_claims": [
                "Supervised BC fine-tuning only.",
                "No PPO.",
                "No teacher checkpoint mutation.",
                "No Unity runtime mutation.",
            ],
        },
    )

    train_loader = create_loader(dataset.train, batch_size=cfg.batch_size, shuffle=True, seed=cfg.seed)
    val_loader = create_loader(dataset.validation, batch_size=cfg.batch_size, shuffle=False, seed=cfg.seed)

    device = torch.device(cfg.device)
    model = build_day3_student_model().to(device=device)
    if init_checkpoint is not None:
        model = load_model_strict(init_checkpoint, device=device)
    optimizer = Adam(model.parameters(), lr=cfg.learning_rate)

    history: List[Dict[str, Any]] = []
    checkpoint_paths_by_epoch: Dict[int, Path] = {}
    best_score: tuple[float, ...] | None = None
    best_epoch = -1
    epochs_without_improvement = 0

    for epoch in range(1, cfg.epochs + 1):
        start = time.perf_counter()
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
        stage10d14_metrics = _evaluate_epoch_targets(
            model=model,
            validation_observations=dataset.validation.input_tensor,
            validation_actions=dataset.validation.target_action_branches,
            original_validation_count=original_validation_count,
            augmented_validation_metadata=augmented_validation_metadata,
            runtime_map=runtime_map,
            device=device,
            batch_size=cfg.batch_size,
        )

        epoch_metrics: Dict[str, Any] = {}
        epoch_metrics.update(train_metrics)
        epoch_metrics.update(val_metrics)
        epoch_metrics.update(stage10d14_metrics)
        epoch_metrics["epoch"] = int(epoch)
        epoch_metrics["learning_rate"] = float(optimizer.param_groups[0]["lr"])
        epoch_metrics["epoch_time_sec"] = float(time.perf_counter() - start)
        history.append(epoch_metrics)

        checkpoint_path = run_dir / f"epoch_{epoch:03d}.pt"
        torch.save(
            _checkpoint_payload(
                model=model,
                optimizer=optimizer,
                epoch=epoch,
                metrics=epoch_metrics,
                config=cfg,
                dataset_manifest=manifest,
            ),
            checkpoint_path,
        )
        checkpoint_paths_by_epoch[epoch] = checkpoint_path

        score = _selection_score(epoch_metrics)
        if best_score is None or score > best_score:
            best_score = score
            best_epoch = epoch
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1

        print(
            "[epoch={}] val_total_loss={:.6f} orig_actor_acc={:.6f} b2_p_harvest={:.6f} c3_p_produce={:.6f} off_actor_non_noop_count={}".format(
                epoch,
                float(epoch_metrics["val_total_loss"]),
                float(epoch_metrics["original_val_actor_action_accuracy"]),
                float(epoch_metrics["true_raw_B2_p_harvest"]),
                float(epoch_metrics["true_raw_C3_p_produce"]),
                int(epoch_metrics["off_actor_non_noop_count"]),
            )
        )
        if epochs_without_improvement >= cfg.patience:
            print(f"[early-stop] patience reached at epoch {epoch}")
            break

    if best_epoch < 0:
        raise RuntimeError("No epoch completed during Stage10D.14 training")

    best_checkpoint = run_dir / "student_bc_stage10d14_augmented_best.pt"
    final_checkpoint = run_dir / "student_bc_stage10d14_augmented_final.pt"
    torch.save(torch.load(checkpoint_paths_by_epoch[best_epoch], map_location="cpu"), best_checkpoint)
    torch.save(torch.load(checkpoint_paths_by_epoch[max(checkpoint_paths_by_epoch.keys())], map_location="cpu"), final_checkpoint)
    for path in checkpoint_paths_by_epoch.values():
        path.unlink(missing_ok=True)

    best_metrics = next(row for row in history if int(row["epoch"]) == best_epoch)
    final_metrics = history[-1]

    write_json(
        run_dir / "stage10d14_training_history.json",
        {
            "stage": "10D.14",
            "run_dir": run_dir.as_posix(),
            "best_epoch": int(best_epoch),
            "history": history,
            "best_checkpoint": best_checkpoint.as_posix(),
            "final_checkpoint": final_checkpoint.as_posix(),
        },
    )
    write_json(
        run_dir / "stage10d14_training_selection.json",
        {
            "stage": "10D.14",
            "generated_at_utc": utc_now_iso(),
            "selected_epoch": int(best_epoch),
            "selection_score": list(best_score) if best_score is not None else None,
            "best_metrics": best_metrics,
            "final_metrics": final_metrics,
        },
    )

    print(best_checkpoint.as_posix())
    print(final_checkpoint.as_posix())
    print((run_dir / "stage10d14_training_history.json").as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())