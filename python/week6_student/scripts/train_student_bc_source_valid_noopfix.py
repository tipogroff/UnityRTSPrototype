#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping

import numpy as np
import torch
import torch.nn.functional as F
from torch import Tensor, nn
from torch.optim import AdamW
from torch.utils.data import DataLoader, Dataset

THIS_FILE = Path(__file__).resolve()
WEEK6_STUDENT_DIR = THIS_FILE.parents[1]
if str(WEEK6_STUDENT_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK6_STUDENT_DIR))

from student_architecture_transfer import build_day3_student_model
from student_branch_contract import BRANCH_SPECS


BRANCH_SIZES = [6, 4, 4, 4, 4, 7, 49]


@dataclass(frozen=True)
class TrainConfig:
    bc_ready_dir: str
    output_dir: str
    run_label: str
    device: str
    epochs: int
    batch_size: int
    learning_rate: float
    weight_decay: float
    seed: int
    num_workers: int
    invalid_noop_weight: float
    branch_loss_weight: float
    early_stopping_patience: int


class SourceValidDataset(Dataset[tuple[Tensor, Tensor, Tensor]]):
    def __init__(self, npz_path: Path) -> None:
        with np.load(npz_path, allow_pickle=False) as npz:
            obs = np.asarray(npz["observations"] if "observations" in npz else npz["input_tensor"], dtype=np.float32)
            actions = np.asarray(npz["actions"] if "actions" in npz else npz["target_action_branches"], dtype=np.int64)
            if "source_valid_action_mask" not in npz:
                raise RuntimeError(f"{npz_path} missing source_valid_action_mask")
            mask = np.asarray(npz["source_valid_action_mask"], dtype=np.bool_)

        if obs.ndim == 3 and tuple(obs.shape[1:]) == (576, 27):
            obs = obs.reshape(obs.shape[0], 24, 24, 27)
        if obs.ndim != 4 or tuple(obs.shape[1:]) != (24, 24, 27):
            raise RuntimeError(f"{npz_path} observation shape mismatch: {list(obs.shape)}")
        if actions.ndim != 3 or tuple(actions.shape[1:]) != (576, 7):
            raise RuntimeError(f"{npz_path} action shape mismatch: {list(actions.shape)}")
        if mask.shape != actions[:, :, 0].shape:
            raise RuntimeError(f"{npz_path} source_valid_action_mask shape mismatch: {list(mask.shape)}")

        self.observations = obs
        self.actions = actions
        self.source_valid_mask = mask

    def __len__(self) -> int:
        return int(self.observations.shape[0])

    def __getitem__(self, index: int) -> tuple[Tensor, Tensor, Tensor]:
        return (
            torch.from_numpy(self.observations[index]).to(dtype=torch.float32),
            torch.from_numpy(self.actions[index]).to(dtype=torch.long),
            torch.from_numpy(self.source_valid_mask[index]).to(dtype=torch.bool),
        )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train source-valid-aware BC student for Legacy032 NoOp-fix lineage.")
    p.add_argument("--bc-ready-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--run-label", type=str, default="legacy032_v2_bc_source_valid_noop_fix")
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--epochs", type=int, default=8)
    p.add_argument("--batch-size", type=int, default=128)
    p.add_argument("--learning-rate", type=float, default=3e-4)
    p.add_argument("--weight-decay", type=float, default=1e-5)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--num-workers", type=int, default=0)
    p.add_argument("--invalid-noop-weight", type=float, default=0.05)
    p.add_argument("--branch-loss-weight", type=float, default=0.5)
    p.add_argument("--early-stopping-patience", type=int, default=4)
    return p.parse_args()


def _repo_root() -> Path:
    return THIS_FILE.parents[3]


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else (_repo_root() / path)


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def _device(name: str) -> torch.device:
    if name == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if name == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but not available")
    return torch.device(name)


def _action_class_weights(train_ds: SourceValidDataset, device: torch.device) -> Tensor:
    action_type = train_ds.actions[:, :, 0]
    mask = train_ds.source_valid_mask
    counts = np.bincount(action_type[mask].reshape(-1), minlength=6).astype(np.float64)
    counts = np.maximum(counts, 1.0)
    weights = np.sqrt(float(np.mean(counts)) / counts)
    weights = np.clip(weights, 0.25, 10.0).astype(np.float32)
    return torch.as_tensor(weights, dtype=torch.float32, device=device)


def _loss(
    logits: Mapping[str, Tensor],
    y: Tensor,
    source_valid: Tensor,
    class_weights: Tensor,
    invalid_noop_weight: float,
    branch_loss_weight: float,
) -> Tensor:
    action_targets = y[..., 0]
    action_logits = logits["action_type_logits"]
    ce = F.cross_entropy(
        action_logits.reshape(-1, action_logits.shape[-1]),
        action_targets.reshape(-1),
        reduction="none",
        weight=class_weights,
    ).reshape_as(action_targets)
    weights = torch.where(
        source_valid,
        torch.ones_like(ce),
        torch.full_like(ce, float(invalid_noop_weight)),
    )
    total = (ce * weights).sum() / torch.clamp(weights.sum(), min=1.0)

    branch_losses: list[Tensor] = []
    for spec in BRANCH_SPECS:
        if spec.action_type_gate_value is None:
            continue
        active = action_targets == int(spec.action_type_gate_value)
        if not bool(active.any()):
            continue
        branch_logits = logits[spec.logits_key][active]
        branch_targets = y[..., spec.target_index][active]
        branch_losses.append(F.cross_entropy(branch_logits, branch_targets))
    if branch_losses:
        total = total + float(branch_loss_weight) * torch.stack(branch_losses).mean()
    return total


def _confusion_matrix(target: np.ndarray, pred: np.ndarray) -> list[list[int]]:
    out = np.zeros((6, 6), dtype=np.int64)
    for t, p in zip(target.reshape(-1), pred.reshape(-1)):
        if 0 <= int(t) < 6 and 0 <= int(p) < 6:
            out[int(t), int(p)] += 1
    return out.tolist()


def _evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> Dict[str, Any]:
    model.eval()
    total_loss = 0.0
    batches = 0
    total_cells = 0
    action_correct = 0
    branch_correct = {spec.branch_name: 0 for spec in BRANCH_SPECS}
    branch_total = {spec.branch_name: 0 for spec in BRANCH_SPECS}
    confusion = np.zeros((6, 6), dtype=np.int64)
    pred_hist = Counter()
    target_hist = Counter()
    source_valid_actor_total = 0
    source_valid_actor_pred_non_noop = 0
    source_valid_actor_exact = 0
    source_invalid_total = 0
    source_invalid_pred_non_noop = 0

    with torch.no_grad():
        for x, y, source_valid in loader:
            x = x.to(device=device)
            y = y.to(device=device)
            source_valid = source_valid.to(device=device)
            logits = model(x)
            action_pred = torch.argmax(logits["action_type_logits"], dim=-1)
            action_target = y[..., 0]

            total_cells += int(action_target.numel())
            action_correct += int(action_pred.eq(action_target).sum().item())
            for spec in BRANCH_SPECS:
                pred = torch.argmax(logits[spec.logits_key], dim=-1)
                target = y[..., spec.target_index]
                if spec.action_type_gate_value is None:
                    active = torch.ones_like(action_target, dtype=torch.bool)
                else:
                    active = action_target == int(spec.action_type_gate_value)
                branch_total[spec.branch_name] += int(active.sum().item())
                branch_correct[spec.branch_name] += int(pred[active].eq(target[active]).sum().item()) if bool(active.any()) else 0

            valid_actor = source_valid & action_target.ne(0)
            source_valid_actor_total += int(valid_actor.sum().item())
            source_valid_actor_pred_non_noop += int(action_pred[valid_actor].ne(0).sum().item()) if bool(valid_actor.any()) else 0
            source_valid_actor_exact += int(action_pred[valid_actor].eq(action_target[valid_actor]).sum().item()) if bool(valid_actor.any()) else 0

            invalid = ~source_valid
            source_invalid_total += int(invalid.sum().item())
            source_invalid_pred_non_noop += int(action_pred[invalid].ne(0).sum().item()) if bool(invalid.any()) else 0

            pred_np = action_pred.detach().cpu().numpy()
            target_np = action_target.detach().cpu().numpy()
            confusion += np.asarray(_confusion_matrix(target_np, pred_np), dtype=np.int64)
            pred_hist.update(int(v) for v in pred_np.reshape(-1).tolist())
            target_hist.update(int(v) for v in target_np.reshape(-1).tolist())
            batches += 1

    branch_acc = {
        spec.branch_name: (float(branch_correct[spec.branch_name] / branch_total[spec.branch_name]) if branch_total[spec.branch_name] else 0.0)
        for spec in BRANCH_SPECS
    }
    return {
        "validation_batches": int(batches),
        "action_type_accuracy": float(action_correct / total_cells) if total_cells else 0.0,
        "branch_accuracies": branch_acc,
        "noop_prediction_share": float(pred_hist.get(0, 0) / total_cells) if total_cells else 0.0,
        "source_valid_non_noop_recall": float(source_valid_actor_pred_non_noop / source_valid_actor_total) if source_valid_actor_total else 0.0,
        "source_valid_non_noop_exact_action_type_recall": float(source_valid_actor_exact / source_valid_actor_total) if source_valid_actor_total else 0.0,
        "source_valid_non_noop_count": int(source_valid_actor_total),
        "source_invalid_false_non_noop_rate": float(source_invalid_pred_non_noop / source_invalid_total) if source_invalid_total else 0.0,
        "source_invalid_cell_count": int(source_invalid_total),
        "action_type_confusion_matrix": confusion.tolist(),
        "predicted_action_type_histogram": {str(i): int(pred_hist.get(i, 0)) for i in range(6)},
        "target_action_type_histogram": {str(i): int(target_hist.get(i, 0)) for i in range(6)},
    }


def _save_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    cfg = TrainConfig(
        bc_ready_dir=str(args.bc_ready_dir),
        output_dir=str(args.output_dir),
        run_label=args.run_label,
        device=args.device,
        epochs=int(args.epochs),
        batch_size=int(args.batch_size),
        learning_rate=float(args.learning_rate),
        weight_decay=float(args.weight_decay),
        seed=int(args.seed),
        num_workers=int(args.num_workers),
        invalid_noop_weight=float(args.invalid_noop_weight),
        branch_loss_weight=float(args.branch_loss_weight),
        early_stopping_patience=int(args.early_stopping_patience),
    )
    _set_seed(cfg.seed)
    device = _device(cfg.device)
    bc_ready_dir = _resolve(Path(cfg.bc_ready_dir)).resolve()
    output_dir = _resolve(Path(cfg.output_dir)).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    train_ds = SourceValidDataset(bc_ready_dir / "bc_train.npz")
    val_ds = SourceValidDataset(bc_ready_dir / "bc_validation.npz")
    train_loader = DataLoader(train_ds, batch_size=cfg.batch_size, shuffle=True, num_workers=cfg.num_workers)
    val_loader = DataLoader(val_ds, batch_size=cfg.batch_size, shuffle=False, num_workers=cfg.num_workers)

    model = build_day3_student_model().to(device=device)
    optimizer = AdamW(model.parameters(), lr=cfg.learning_rate, weight_decay=cfg.weight_decay)
    class_weights = _action_class_weights(train_ds, device)

    best_metric = -1.0
    best_epoch = 0
    bad_epochs = 0
    history: list[Dict[str, Any]] = []
    best_path = output_dir / f"{cfg.run_label}_best.pt"
    final_path = output_dir / f"{cfg.run_label}_final.pt"

    for epoch in range(1, cfg.epochs + 1):
        started = time.perf_counter()
        model.train()
        train_loss_sum = 0.0
        train_batches = 0
        for x, y, source_valid in train_loader:
            x = x.to(device=device)
            y = y.to(device=device)
            source_valid = source_valid.to(device=device)
            logits = model(x)
            loss = _loss(
                logits,
                y,
                source_valid,
                class_weights,
                cfg.invalid_noop_weight,
                cfg.branch_loss_weight,
            )
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            train_loss_sum += float(loss.detach().item())
            train_batches += 1

        metrics = _evaluate(model, val_loader, device)
        metric = (
            metrics["action_type_accuracy"]
            + metrics["source_valid_non_noop_exact_action_type_recall"]
            - metrics["source_invalid_false_non_noop_rate"]
        )
        record = {
            "epoch": int(epoch),
            "duration_sec": float(time.perf_counter() - started),
            "train_loss": float(train_loss_sum / max(1, train_batches)),
            "train_batches": int(train_batches),
            "selection_metric": float(metric),
            **metrics,
        }
        history.append(record)

        if metric > best_metric:
            best_metric = float(metric)
            best_epoch = int(epoch)
            bad_epochs = 0
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "config": asdict(cfg),
                    "epoch": int(epoch),
                    "metrics": record,
                    "source_valid_class_weights": [float(v) for v in class_weights.detach().cpu().tolist()],
                },
                best_path,
            )
        else:
            bad_epochs += 1
            if cfg.early_stopping_patience > 0 and bad_epochs >= cfg.early_stopping_patience:
                break

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "config": asdict(cfg),
            "epoch": int(history[-1]["epoch"]),
            "metrics": history[-1],
            "source_valid_class_weights": [float(v) for v in class_weights.detach().cpu().tolist()],
        },
        final_path,
    )

    summary = {
        "status": "pass",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bc_ready_dir": str(bc_ready_dir),
        "output_dir": str(output_dir),
        "best_checkpoint": str(best_path),
        "final_checkpoint": str(final_path),
        "best_epoch": int(best_epoch),
        "epochs_completed": int(len(history)),
        "best_metric": float(best_metric),
        "best_metrics": history[best_epoch - 1] if best_epoch > 0 else {},
        "final_metrics": history[-1],
        "config": asdict(cfg),
        "constraints": {
            "no_teacher_training": True,
            "no_ppo": True,
            "no_unity_runtime_changes": True,
        },
    }
    _save_json(output_dir / "training_summary.json", summary)
    _save_json(output_dir / "training_history.json", {"history": history})
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
