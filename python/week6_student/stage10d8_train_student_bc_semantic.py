#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

import numpy as np
import torch
import torch.nn.functional as F
from torch import Tensor, nn
from torch.optim import Adam
from torch.utils.data import DataLoader, Dataset

from student_architecture_transfer import build_day3_student_model
from student_bc_contract import BCContractError, SplitData
from student_bc_loader import load_bc_ready_dataset
from student_branch_contract import BRANCH_ORDER, BRANCH_SPECS, validate_student_branch_contract_consistency


NOOP_ACTION_TYPE = 0
HARVEST_ACTION_TYPE = 2
PRODUCE_ACTION_TYPE = 4
ATTACK_ACTION_TYPE = 5
UNIT_TYPE_OFFSET = 5
UNIT_TYPE_SIZE = 7
WORKER_UNIT_TYPE_INDEX = 3
BASE_UNIT_TYPE_INDEX = 1


@dataclass(frozen=True)
class TrainConfig:
    bc_ready_dir: str
    run_dir: str
    epochs: int
    batch_size: int
    learning_rate: float
    device: str
    seed: int
    gradient_clip_norm: float
    actor_cell_loss_weight: float


class BCSplitTorchDataset(Dataset[Tuple[Tensor, Tensor]]):
    def __init__(self, split: SplitData) -> None:
        self._inputs = split.input_tensor
        self._targets = split.target_action_branches

    def __len__(self) -> int:
        return int(self._inputs.shape[0])

    def __getitem__(self, index: int) -> Tuple[Tensor, Tensor]:
        x = torch.from_numpy(self._inputs[index]).to(dtype=torch.float32)
        y = torch.from_numpy(self._targets[index]).to(dtype=torch.long)
        return x, y


class EpochAccumulator:
    def __init__(self) -> None:
        self.objective_loss_sum = 0.0
        self.objective_weight_sum = 0.0
        self.branch_loss_sum: Dict[str, float] = {spec.branch_name: 0.0 for spec in BRANCH_SPECS}
        self.branch_weight_sum: Dict[str, float] = {spec.branch_name: 0.0 for spec in BRANCH_SPECS}

        self.action_type_correct_all = 0
        self.all_cell_count = 0
        self.noop_pred_count_all = 0
        self.noop_target_count_all = 0

        self.actor_cell_count = 0
        self.actor_cell_action_type_correct = 0
        self.actor_cell_non_noop_pred = 0
        self.actor_cell_noop_pred = 0

        self.worker_proxy_count = 0
        self.worker_proxy_correct = 0

        self.base_proxy_count = 0
        self.base_proxy_correct = 0

        self.attack_proxy_count = 0
        self.attack_proxy_correct = 0

    def update(self, out: Dict[str, Any]) -> None:
        self.objective_loss_sum += float(out["objective_loss_sum"])
        self.objective_weight_sum += float(out["objective_weight_sum"])

        for spec in BRANCH_SPECS:
            name = spec.branch_name
            self.branch_loss_sum[name] += float(out["branch_loss_sum"][name])
            self.branch_weight_sum[name] += float(out["branch_weight_sum"][name])

        self.action_type_correct_all += int(out["action_type_correct_all"])
        self.all_cell_count += int(out["all_cell_count"])
        self.noop_pred_count_all += int(out["noop_pred_count_all"])
        self.noop_target_count_all += int(out["noop_target_count_all"])

        self.actor_cell_count += int(out["actor_cell_count"])
        self.actor_cell_action_type_correct += int(out["actor_cell_action_type_correct"])
        self.actor_cell_non_noop_pred += int(out["actor_cell_non_noop_pred"])
        self.actor_cell_noop_pred += int(out["actor_cell_noop_pred"])

        self.worker_proxy_count += int(out["worker_proxy_count"])
        self.worker_proxy_correct += int(out["worker_proxy_correct"])

        self.base_proxy_count += int(out["base_proxy_count"])
        self.base_proxy_correct += int(out["base_proxy_correct"])

        self.attack_proxy_count += int(out["attack_proxy_count"])
        self.attack_proxy_correct += int(out["attack_proxy_correct"])

    def to_metrics(self, prefix: str) -> Dict[str, float | int]:
        metrics: Dict[str, float | int] = {}

        total_loss = self.objective_loss_sum / self.objective_weight_sum if self.objective_weight_sum > 0 else 0.0
        metrics[f"{prefix}_total_loss"] = float(total_loss)

        action_type_loss = self.branch_loss_sum["action_type"] / self.branch_weight_sum["action_type"] if self.branch_weight_sum["action_type"] > 0 else 0.0
        metrics[f"{prefix}_action_type_loss"] = float(action_type_loss)

        for name in BRANCH_ORDER:
            denom = self.branch_weight_sum[name]
            value = self.branch_loss_sum[name] / denom if denom > 0 else 0.0
            metrics[f"{prefix}_{name}_loss"] = float(value)

        metrics[f"{prefix}_action_type_accuracy_all_cells"] = float(
            self.action_type_correct_all / self.all_cell_count if self.all_cell_count > 0 else 0.0
        )
        metrics[f"{prefix}_noop_share_pred_all_cells"] = float(
            self.noop_pred_count_all / self.all_cell_count if self.all_cell_count > 0 else 0.0
        )
        metrics[f"{prefix}_noop_share_target_all_cells"] = float(
            self.noop_target_count_all / self.all_cell_count if self.all_cell_count > 0 else 0.0
        )

        metrics[f"{prefix}_actor_cell_count"] = int(self.actor_cell_count)
        metrics[f"{prefix}_actor_cell_action_type_accuracy"] = float(
            self.actor_cell_action_type_correct / self.actor_cell_count if self.actor_cell_count > 0 else 0.0
        )
        metrics[f"{prefix}_actor_cell_non_noop_recall"] = float(
            self.actor_cell_non_noop_pred / self.actor_cell_count if self.actor_cell_count > 0 else 0.0
        )
        metrics[f"{prefix}_actor_cell_noop_pred_share"] = float(
            self.actor_cell_noop_pred / self.actor_cell_count if self.actor_cell_count > 0 else 1.0
        )

        metrics[f"{prefix}_worker_harvest_proxy_count"] = int(self.worker_proxy_count)
        metrics[f"{prefix}_worker_harvest_proxy_accuracy"] = float(
            self.worker_proxy_correct / self.worker_proxy_count if self.worker_proxy_count > 0 else 0.0
        )

        metrics[f"{prefix}_base_produce_proxy_count"] = int(self.base_proxy_count)
        metrics[f"{prefix}_base_produce_proxy_accuracy"] = float(
            self.base_proxy_correct / self.base_proxy_count if self.base_proxy_count > 0 else 0.0
        )

        metrics[f"{prefix}_attack_proxy_count"] = int(self.attack_proxy_count)
        metrics[f"{prefix}_attack_proxy_accuracy"] = float(
            self.attack_proxy_correct / self.attack_proxy_count if self.attack_proxy_count > 0 else 0.0
        )

        return metrics


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _iso_timestamp_for_dir() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _default_bc_ready_dir() -> Path:
    return _repo_root() / (
        "python/week6_student/bc_ready/"
        "legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z"
    )


def _default_runs_root() -> Path:
    return _repo_root() / "python/week6_student/runs"


def _default_run_dir() -> Path:
    return _default_runs_root() / f"legacy032_v2_semantic_bc_stage10d8_{_iso_timestamp_for_dir()}"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.8 semantic BC student retraining (supervised only)")
    p.add_argument("--bc-ready-dir", type=Path, default=_default_bc_ready_dir())
    p.add_argument("--run-dir", type=Path, default=None)
    p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--learning-rate", type=float, default=1e-3)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--gradient-clip-norm", type=float, default=1.0)
    p.add_argument("--actor-cell-loss-weight", type=float, default=1.0)
    return p.parse_args()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def create_loader(split: SplitData, batch_size: int, shuffle: bool, seed: int) -> DataLoader[Tuple[Tensor, Tensor]]:
    ds = BCSplitTorchDataset(split)
    generator = torch.Generator()
    generator.manual_seed(seed)
    return DataLoader(
        ds,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=0,
        pin_memory=False,
        drop_last=False,
        generator=generator,
    )


def _unit_type_peak_index_from_obs(x: Tensor) -> Tensor:
    unit_slice = x[..., UNIT_TYPE_OFFSET : UNIT_TYPE_OFFSET + UNIT_TYPE_SIZE]
    peak = torch.argmax(unit_slice, dim=-1)
    return peak.reshape(peak.shape[0], -1)


def _weighted_cross_entropy_sum(logits_flat: Tensor, targets_flat: Tensor, weights_flat: Tensor) -> Tuple[Tensor, float, float]:
    ce = F.cross_entropy(logits_flat, targets_flat, reduction="none")
    weighted = ce * weights_flat
    weighted_sum = weighted.sum()
    return weighted_sum, float(weighted_sum.detach().item()), float(weights_flat.detach().sum().item())


def compute_batch_objective_and_metrics(
    logits_by_key: Mapping[str, Tensor],
    targets: Tensor,
    inputs: Tensor,
    actor_cell_loss_weight: float,
) -> Dict[str, Any]:
    action_type_targets = targets[..., 0]
    actor_mask = action_type_targets != NOOP_ACTION_TYPE
    actor_count = int(actor_mask.sum().item())

    pred_action_type = torch.argmax(logits_by_key["action_type_logits"], dim=-1)

    base_weights = torch.ones_like(action_type_targets, dtype=torch.float32)
    if actor_cell_loss_weight != 1.0:
        actor_weight_tensor = torch.full_like(base_weights, float(actor_cell_loss_weight))
        base_weights = torch.where(actor_mask, actor_weight_tensor, base_weights)

    objective_loss_sum_tensor = torch.zeros((), device=targets.device)
    objective_weight_sum = 0.0

    branch_loss_sum: Dict[str, float] = {}
    branch_weight_sum: Dict[str, float] = {}

    for spec in BRANCH_SPECS:
        logits = logits_by_key[spec.logits_key]
        branch_targets = targets[..., spec.target_index]

        if spec.action_type_gate_value is None:
            active_mask = torch.ones_like(action_type_targets, dtype=torch.bool)
        else:
            active_mask = action_type_targets == spec.action_type_gate_value

        if not torch.any(active_mask):
            branch_loss_sum[spec.branch_name] = 0.0
            branch_weight_sum[spec.branch_name] = 0.0
            continue

        logits_flat = logits[active_mask]
        targets_flat = branch_targets[active_mask]
        weights_flat = base_weights[active_mask]

        weighted_sum, weighted_sum_float, weight_sum_float = _weighted_cross_entropy_sum(
            logits_flat=logits_flat,
            targets_flat=targets_flat,
            weights_flat=weights_flat,
        )

        objective_loss_sum_tensor = objective_loss_sum_tensor + weighted_sum
        objective_weight_sum += weight_sum_float

        branch_loss_sum[spec.branch_name] = weighted_sum_float
        branch_weight_sum[spec.branch_name] = weight_sum_float

    total_loss = objective_loss_sum_tensor / max(objective_weight_sum, 1e-12)

    all_cell_count = int(action_type_targets.numel())
    noop_pred_count_all = int((pred_action_type == NOOP_ACTION_TYPE).sum().item())
    noop_target_count_all = int((action_type_targets == NOOP_ACTION_TYPE).sum().item())

    actor_correct = int((pred_action_type[actor_mask] == action_type_targets[actor_mask]).sum().item()) if actor_count > 0 else 0
    actor_non_noop_pred = int((pred_action_type[actor_mask] != NOOP_ACTION_TYPE).sum().item()) if actor_count > 0 else 0
    actor_noop_pred = int((pred_action_type[actor_mask] == NOOP_ACTION_TYPE).sum().item()) if actor_count > 0 else 0

    action_type_correct_all = int((pred_action_type == action_type_targets).sum().item())

    unit_peak = _unit_type_peak_index_from_obs(inputs)

    worker_proxy_mask = (action_type_targets == HARVEST_ACTION_TYPE) & (unit_peak == WORKER_UNIT_TYPE_INDEX)
    worker_proxy_count = int(worker_proxy_mask.sum().item())
    worker_proxy_correct = int((pred_action_type[worker_proxy_mask] == HARVEST_ACTION_TYPE).sum().item()) if worker_proxy_count > 0 else 0

    base_proxy_mask = (action_type_targets == PRODUCE_ACTION_TYPE) & (unit_peak == BASE_UNIT_TYPE_INDEX)
    base_proxy_count = int(base_proxy_mask.sum().item())
    base_proxy_correct = int((pred_action_type[base_proxy_mask] == PRODUCE_ACTION_TYPE).sum().item()) if base_proxy_count > 0 else 0

    attack_proxy_mask = action_type_targets == ATTACK_ACTION_TYPE
    attack_proxy_count = int(attack_proxy_mask.sum().item())
    attack_proxy_correct = int((pred_action_type[attack_proxy_mask] == ATTACK_ACTION_TYPE).sum().item()) if attack_proxy_count > 0 else 0

    return {
        "loss_tensor": total_loss,
        "objective_loss_sum": float(objective_loss_sum_tensor.detach().item()),
        "objective_weight_sum": float(objective_weight_sum),
        "branch_loss_sum": branch_loss_sum,
        "branch_weight_sum": branch_weight_sum,
        "all_cell_count": all_cell_count,
        "action_type_correct_all": action_type_correct_all,
        "noop_pred_count_all": noop_pred_count_all,
        "noop_target_count_all": noop_target_count_all,
        "actor_cell_count": actor_count,
        "actor_cell_action_type_correct": actor_correct,
        "actor_cell_non_noop_pred": actor_non_noop_pred,
        "actor_cell_noop_pred": actor_noop_pred,
        "worker_proxy_count": worker_proxy_count,
        "worker_proxy_correct": worker_proxy_correct,
        "base_proxy_count": base_proxy_count,
        "base_proxy_correct": base_proxy_correct,
        "attack_proxy_count": attack_proxy_count,
        "attack_proxy_correct": attack_proxy_correct,
    }


def run_epoch(
    model: nn.Module,
    loader: DataLoader[Tuple[Tensor, Tensor]],
    device: torch.device,
    optimizer: Adam | None,
    actor_cell_loss_weight: float,
    gradient_clip_norm: float,
) -> Dict[str, float | int]:
    is_train = optimizer is not None
    if is_train:
        model.train()
    else:
        model.eval()

    acc = EpochAccumulator()

    for x_cpu, y_cpu in loader:
        x = x_cpu.to(device=device)
        y = y_cpu.to(device=device)

        with torch.set_grad_enabled(is_train):
            logits = model(x)
            out = compute_batch_objective_and_metrics(
                logits_by_key=logits,
                targets=y,
                inputs=x,
                actor_cell_loss_weight=actor_cell_loss_weight,
            )
            loss = out["loss_tensor"]

            if is_train:
                assert optimizer is not None
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                if gradient_clip_norm > 0:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=float(gradient_clip_norm))
                optimizer.step()

        acc.update(out)

    return acc.to_metrics(prefix="train" if is_train else "val")


def _validate_manifest_contract(dataset: Any) -> None:
    manifest = dataset.manifest_payload

    checks = {
        "schema_version": manifest.get("schema_version") == "day6.bc_ready.v1",
        "dataset_kind": manifest.get("dataset_kind") == "semantic_bc_ready",
        "source_stage": manifest.get("source_stage") == "10D.7",
        "source_adapted_dataset_stage": manifest.get("source_adapted_dataset_stage") == "10D.6",
        "mapping_spec_version": manifest.get("mapping_spec_version") == "stage10d6_v1",
        "observation_semantics_version": manifest.get("observation_semantics_version") == "unity_v2_runtime_stage10d6",
        "observation_shape": list(manifest.get("observation_shape", [])) == [576, 27],
        "action_shape": list(manifest.get("action_shape", [])) == [576, 7],
        "branch_sizes": list(manifest.get("branch_sizes", [])) == [6, 4, 4, 4, 4, 7, 49],
        "loader_train_input_shape": tuple(dataset.train.input_tensor.shape[1:]) == (24, 24, 27),
        "loader_train_target_shape": tuple(dataset.train.target_action_branches.shape[1:]) == (576, 7),
    }

    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise BCContractError(f"Stage10D.8 contract mismatch: {failed}")


def _checkpoint_payload(
    *,
    model: nn.Module,
    optimizer: Adam,
    epoch: int,
    metrics: Dict[str, float | int],
    config: TrainConfig,
    dataset_manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "epoch": int(epoch),
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "metrics": metrics,
        "config": asdict(config),
        "stage": "10D.8",
        "scope": "semantic_bc_supervised_retraining_only",
        "dataset_manifest_summary": {
            "schema_version": dataset_manifest.get("schema_version"),
            "dataset_kind": dataset_manifest.get("dataset_kind"),
            "source_stage": dataset_manifest.get("source_stage"),
            "mapping_spec_version": dataset_manifest.get("mapping_spec_version"),
            "observation_semantics_version": dataset_manifest.get("observation_semantics_version"),
            "branch_sizes": dataset_manifest.get("branch_sizes"),
        },
    }


def _composite_score(metrics: Mapping[str, float | int]) -> Tuple[float, float, float]:
    actor_acc = float(metrics.get("val_actor_cell_action_type_accuracy", 0.0))
    actor_noop_share = float(metrics.get("val_actor_cell_noop_pred_share", 1.0))
    val_total_loss = float(metrics.get("val_total_loss", 1e9))
    return (actor_acc, -actor_noop_share, -val_total_loss)


def _select_best_epoch(history: List[Dict[str, float | int]]) -> Dict[str, Any]:
    best_idx = -1
    best_score = (-1e9, -1e9, -1e9)

    for i, row in enumerate(history):
        score = _composite_score(row)
        if score > best_score:
            best_score = score
            best_idx = i

    if best_idx < 0:
        raise RuntimeError("No epochs available for checkpoint selection")

    best_row = history[best_idx]

    actor_count = int(best_row.get("val_actor_cell_count", 0))
    actor_acc = float(best_row.get("val_actor_cell_action_type_accuracy", 0.0))
    actor_noop_share = float(best_row.get("val_actor_cell_noop_pred_share", 1.0))
    worker_proxy_acc = float(best_row.get("val_worker_harvest_proxy_accuracy", 0.0))
    base_proxy_acc = float(best_row.get("val_base_produce_proxy_accuracy", 0.0))

    thresholds = {
        "actor_cell_count_gt_0": actor_count > 0,
        "actor_cell_action_type_accuracy_gt_0_25": actor_acc > 0.25,
        "actor_cell_noop_pred_share_lt_0_5": actor_noop_share < 0.5,
        "worker_harvest_proxy_accuracy_gt_0_5": worker_proxy_acc > 0.5,
        "base_produce_proxy_accuracy_gt_0_5": base_proxy_acc > 0.5,
    }

    metrics_pass = all(bool(v) for v in thresholds.values())

    return {
        "selected_epoch": int(best_row["epoch"]),
        "selected_epoch_index": int(best_idx),
        "composite_score": {
            "actor_cell_action_type_accuracy": float(best_score[0]),
            "negative_actor_cell_noop_pred_share": float(best_score[1]),
            "negative_val_total_loss": float(best_score[2]),
        },
        "selection_rule": {
            "primary": "maximize val_actor_cell_action_type_accuracy",
            "secondary": "minimize val_actor_cell_noop_pred_share",
            "tertiary": "minimize val_total_loss",
        },
        "thresholds": thresholds,
        "actor_metrics_pass": bool(metrics_pass),
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _build_training_md(report: Mapping[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Stage10D.8 Semantic BC Student Retraining Report")
    lines.append("")
    lines.append(f"- generated_at_utc: {report['generated_at_utc']}")
    lines.append(f"- run_dir: {report['run_dir']}")
    lines.append(f"- gate_candidate: {report['gate_candidate']}")
    lines.append("")

    lines.append("## Scope")
    lines.append("- Supervised BC retraining only.")
    lines.append("- No PPO.")
    lines.append("- No teacher training.")
    lines.append("- No checkpoint mutation of prior runs.")
    lines.append("- No Unity runtime behavior changes.")
    lines.append("")

    cfg = report["training_config"]
    lines.append("## Training Configuration")
    for key in (
        "bc_ready_dir",
        "epochs",
        "batch_size",
        "learning_rate",
        "device",
        "seed",
        "gradient_clip_norm",
        "actor_cell_loss_weight",
    ):
        lines.append(f"- {key}: {cfg[key]}")
    lines.append("")

    best = report["best_validation_metrics"]
    lines.append("## Best Checkpoint Metrics (Validation)")
    for key in (
        "val_total_loss",
        "val_action_type_accuracy_all_cells",
        "val_noop_share_pred_all_cells",
        "val_noop_share_target_all_cells",
        "val_actor_cell_count",
        "val_actor_cell_action_type_accuracy",
        "val_actor_cell_non_noop_recall",
        "val_actor_cell_noop_pred_share",
        "val_worker_harvest_proxy_accuracy",
        "val_base_produce_proxy_accuracy",
        "val_attack_proxy_accuracy",
    ):
        lines.append(f"- {key}: {best.get(key)}")
    lines.append("")

    sel = report["checkpoint_selection_report"]
    lines.append("## Checkpoint Selection")
    lines.append(f"- selected_epoch: {sel['selected_epoch']}")
    lines.append(f"- actor_metrics_pass: {sel['actor_metrics_pass']}")
    for key, value in sel["thresholds"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")

    lines.append("## Notes")
    lines.append(f"- actor weighting used: {float(cfg['actor_cell_loss_weight']) != 1.0}")
    lines.append(f"- actor_cell_loss_weight: {cfg['actor_cell_loss_weight']}")
    lines.append(
        "- comparability_with_stage7: true when actor_cell_loss_weight==1.0; otherwise objective weighting differs."
    )
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    set_seed(int(args.seed))
    validate_student_branch_contract_consistency()

    repo_root = _repo_root()
    bc_ready_dir = (args.bc_ready_dir if args.bc_ready_dir.is_absolute() else (repo_root / args.bc_ready_dir)).resolve()

    if args.run_dir is None:
        run_dir = _default_run_dir().resolve()
    else:
        run_dir = (args.run_dir if args.run_dir.is_absolute() else (repo_root / args.run_dir)).resolve()

    if run_dir.exists():
        print(f"[FAIL] run_dir already exists, refusing overwrite: {run_dir}")
        return 1

    try:
        dataset = load_bc_ready_dataset(bc_ready_dir)
        _validate_manifest_contract(dataset)
    except Exception as exc:
        print(f"[FAIL] Dataset load/contract validation failed: {exc}")
        return 1

    run_dir.mkdir(parents=True, exist_ok=False)

    cfg = TrainConfig(
        bc_ready_dir=str(bc_ready_dir),
        run_dir=str(run_dir),
        epochs=int(args.epochs),
        batch_size=int(args.batch_size),
        learning_rate=float(args.learning_rate),
        device=str(args.device),
        seed=int(args.seed),
        gradient_clip_norm=float(args.gradient_clip_norm),
        actor_cell_loss_weight=float(args.actor_cell_loss_weight),
    )

    _write_json(
        run_dir / "training_config.json",
        {
            "stage": "10D.8",
            "training_scope": "semantic_bc_supervised_only",
            "config": asdict(cfg),
            "dataset_manifest_summary": {
                "schema_version": dataset.manifest_payload.get("schema_version"),
                "dataset_kind": dataset.manifest_payload.get("dataset_kind"),
                "source_stage": dataset.manifest_payload.get("source_stage"),
                "source_adapted_dataset_stage": dataset.manifest_payload.get("source_adapted_dataset_stage"),
                "mapping_spec_version": dataset.manifest_payload.get("mapping_spec_version"),
                "observation_semantics_version": dataset.manifest_payload.get("observation_semantics_version"),
                "observation_shape": dataset.manifest_payload.get("observation_shape"),
                "action_shape": dataset.manifest_payload.get("action_shape"),
                "branch_sizes": dataset.manifest_payload.get("branch_sizes"),
                "num_train": dataset.manifest_payload.get("num_train"),
                "num_validation": dataset.manifest_payload.get("num_validation"),
                "num_debug": dataset.manifest_payload.get("num_debug"),
            },
            "explicit_non_claims": [
                "No PPO run.",
                "No teacher training run.",
                "No Unity runtime mutation.",
                "No checkpoint overwrite of previous runs.",
            ],
        },
    )

    train_loader = create_loader(dataset.train, batch_size=cfg.batch_size, shuffle=True, seed=cfg.seed)
    val_loader = create_loader(dataset.validation, batch_size=cfg.batch_size, shuffle=False, seed=cfg.seed)

    model = build_day3_student_model().to(torch.device(cfg.device))
    optimizer = Adam(model.parameters(), lr=cfg.learning_rate)

    history: List[Dict[str, float | int]] = []
    checkpoint_paths_by_epoch: Dict[int, Path] = {}

    print("=== Stage10D.8 Semantic BC Student Retraining ===")
    print(f"bc_ready_dir={bc_ready_dir.as_posix()}")
    print(f"run_dir={run_dir.as_posix()}")

    for epoch in range(1, cfg.epochs + 1):
        start = time.perf_counter()

        train_metrics = run_epoch(
            model=model,
            loader=train_loader,
            device=torch.device(cfg.device),
            optimizer=optimizer,
            actor_cell_loss_weight=cfg.actor_cell_loss_weight,
            gradient_clip_norm=cfg.gradient_clip_norm,
        )
        val_metrics = run_epoch(
            model=model,
            loader=val_loader,
            device=torch.device(cfg.device),
            optimizer=None,
            actor_cell_loss_weight=cfg.actor_cell_loss_weight,
            gradient_clip_norm=cfg.gradient_clip_norm,
        )

        epoch_metrics: Dict[str, float | int] = {}
        epoch_metrics.update(train_metrics)
        epoch_metrics.update(val_metrics)
        epoch_metrics["epoch"] = int(epoch)
        epoch_metrics["learning_rate"] = float(optimizer.param_groups[0]["lr"])
        epoch_metrics["epoch_time_sec"] = float(time.perf_counter() - start)

        history.append(epoch_metrics)

        epoch_ckpt = run_dir / f"epoch_{epoch:03d}.pt"
        torch.save(
            _checkpoint_payload(
                model=model,
                optimizer=optimizer,
                epoch=epoch,
                metrics=epoch_metrics,
                config=cfg,
                dataset_manifest=dataset.manifest_payload,
            ),
            epoch_ckpt,
        )
        checkpoint_paths_by_epoch[epoch] = epoch_ckpt

        print(
            "[epoch={}] val_total_loss={:.6f} val_actor_acc={:.6f} val_actor_noop_share={:.6f} val_worker_proxy_acc={:.6f} val_base_proxy_acc={:.6f}".format(
                epoch,
                float(epoch_metrics["val_total_loss"]),
                float(epoch_metrics["val_actor_cell_action_type_accuracy"]),
                float(epoch_metrics["val_actor_cell_noop_pred_share"]),
                float(epoch_metrics["val_worker_harvest_proxy_accuracy"]),
                float(epoch_metrics["val_base_produce_proxy_accuracy"]),
            )
        )

    selection = _select_best_epoch(history)
    best_epoch = int(selection["selected_epoch"])

    best_src = checkpoint_paths_by_epoch[best_epoch]
    best_dst = run_dir / "student_bc_semantic_best.pt"
    last_dst = run_dir / "student_bc_semantic_last.pt"

    torch.save(torch.load(best_src, map_location="cpu"), best_dst)
    torch.save(torch.load(checkpoint_paths_by_epoch[cfg.epochs], map_location="cpu"), last_dst)

    for path in checkpoint_paths_by_epoch.values():
        path.unlink(missing_ok=True)

    history_payload = {
        "stage": "10D.8",
        "history": history,
    }
    _write_json(run_dir / "training_history.json", history_payload)

    best_metrics = history[selection["selected_epoch_index"]]
    last_metrics = history[-1]

    _write_json(
        run_dir / "validation_metrics.json",
        {
            "stage": "10D.8",
            "best_epoch": best_epoch,
            "best_validation_metrics": best_metrics,
            "last_validation_metrics": last_metrics,
        },
    )

    _write_json(run_dir / "checkpoint_selection_report.json", selection)

    gate_candidate = (
        "GO_FOR_UNITY_STAGE10R_RERUN"
        if bool(selection["actor_metrics_pass"])
        else "GO_FOR_BC_OBJECTIVE_REWEIGHTING_OR_SAMPLING_FIX"
    )

    training_report = {
        "stage": "10D.8",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_dir": run_dir.as_posix(),
        "bc_ready_dir": bc_ready_dir.as_posix(),
        "training_config": asdict(cfg),
        "best_checkpoint": best_dst.as_posix(),
        "last_checkpoint": last_dst.as_posix(),
        "best_validation_metrics": best_metrics,
        "last_validation_metrics": last_metrics,
        "checkpoint_selection_report": selection,
        "gate_candidate": gate_candidate,
        "actor_weighting": {
            "used": bool(float(cfg.actor_cell_loss_weight) != 1.0),
            "actor_cell_loss_weight": float(cfg.actor_cell_loss_weight),
            "comparable_with_stage7": bool(float(cfg.actor_cell_loss_weight) == 1.0),
        },
        "explicit_non_claims": [
            "No PPO performed.",
            "No teacher training continued.",
            "No old checkpoint overwritten.",
            "No Unity runtime behavior modified.",
            "No ActionApplier changes.",
            "No MatchManager changes.",
            "No forced non-NoOp fallback introduced.",
            "No semantic parity claim made.",
        ],
    }

    _write_json(run_dir / "stage10d8_training_report.json", training_report)
    (run_dir / "stage10d8_training_report.md").write_text(_build_training_md(training_report), encoding="utf-8")

    print(best_dst.as_posix())
    print(last_dst.as_posix())
    print((run_dir / "stage10d8_training_report.json").as_posix())
    print((run_dir / "stage10d8_training_report.md").as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
