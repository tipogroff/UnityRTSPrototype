#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

import numpy as np
import torch
from torch import Tensor, nn
from torch.optim import AdamW
from torch.utils.data import DataLoader, Dataset

# Ensure sibling week6_student modules are importable when launching via script path.
THIS_FILE = Path(__file__).resolve()
WEEK6_STUDENT_DIR = THIS_FILE.parents[1]
if str(WEEK6_STUDENT_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK6_STUDENT_DIR))

from student_architecture_transfer import build_day3_student_model
from student_bc_contract import BCContractError, LoadedBCDataset, SplitData
from student_bc_loader import load_bc_ready_dataset
from student_bc_metrics import compute_branchwise_loss
from student_branch_contract import BRANCH_SPECS, EXPECTED_BC_BRANCH_SIZES, validate_student_branch_contract_consistency


CANONICAL_STAGE5P4_BC_READY_DIR = Path(
    "python/week5_teacher_legacy032/teacher_exports_bc/"
    "legacy032_3m_unity_v2_bc_ready_stage5p4_20260506T153632Z"
)
CANONICAL_TARGET_ACTION_CONTRACT = "unity_v2_legacy032_gridnet"
CANONICAL_ATTACK_TARGET_SEMANTICS = "local_7x7_49"
CANONICAL_DATASET_TYPE = "bc_ready_legacy032_unity_v2"
CANONICAL_BRANCH_SIZES = [6, 4, 4, 4, 4, 7, 49]

CHECKPOINT_COMPATIBILITY_FILENAME = "stage6b1_best_checkpoint_compatibility_report.json"
STAGE6B1_MAIN_REPORT_JSON = "python/week6_student/reports/stage6b1_full_student_bc_training_report.json"
STAGE6B1_MAIN_REPORT_MD = "python/week6_student/reports/STAGE6B1_FULL_STUDENT_BC_TRAINING_REPORT.md"


class BCSplitTorchDataset(Dataset[tuple[Tensor, Tensor]]):
    def __init__(self, split: SplitData) -> None:
        self._inputs = split.input_tensor
        self._targets = split.target_action_branches

    def __len__(self) -> int:
        return int(self._inputs.shape[0])

    def __getitem__(self, index: int) -> tuple[Tensor, Tensor]:
        x = torch.from_numpy(self._inputs[index]).to(dtype=torch.float32)
        y = torch.from_numpy(self._targets[index]).to(dtype=torch.long)
        return x, y


@dataclass(frozen=True)
class FullConfig:
    bc_ready_dir: str
    device: str
    epochs: int
    batch_size: int
    learning_rate: float
    weight_decay: float
    num_workers: int
    seed: int
    output_dir: str
    run_label: str
    save_every_epoch: bool
    early_stopping_patience: int
    max_train_batches: Optional[int]
    max_validation_batches: Optional[int]
    model_variant: str
    contract_check_only: bool


def _repo_root() -> Path:
    return THIS_FILE.parents[3]


def _default_bc_ready_dir() -> Path:
    return _repo_root() / CANONICAL_STAGE5P4_BC_READY_DIR


def _default_output_dir() -> Path:
    return _repo_root() / "python/week6_student/runs/legacy032_v2_full_bc_stage6b1"


def _parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid bool value: {value}")


def _parse_optional_positive_int(value: str | None) -> Optional[int]:
    if value is None:
        return None
    lowered = str(value).strip().lower()
    if lowered in {"none", "null", "unlimited", "all"}:
        return None
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("Value must be > 0 or one of: none,null,unlimited,all")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Stage6B1 full student behavior cloning training over Stage5P4 Legacy032 Unity v2 BC-ready dataset. "
            "This script trains student BC only (no teacher training, no PPO)."
        )
    )
    parser.add_argument("--bc-ready-dir", type=Path, default=_default_bc_ready_dir())
    parser.add_argument("--device", type=str, default="cpu", help="cpu | cuda | auto")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-5)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--output-dir", type=Path, default=_default_output_dir())
    parser.add_argument("--run-label", type=str, default="legacy032_v2_full_bc_stage6b1")
    parser.add_argument("--save-every-epoch", type=_parse_bool, default=True)
    parser.add_argument("--early-stopping-patience", type=int, default=5)
    parser.add_argument(
        "--max-train-batches",
        type=_parse_optional_positive_int,
        default=None,
        help="Optional cap for train batches per epoch. Default: unlimited.",
    )
    parser.add_argument(
        "--max-validation-batches",
        type=_parse_optional_positive_int,
        default=None,
        help="Optional cap for validation batches per epoch. Default: unlimited.",
    )
    parser.add_argument("--model-variant", type=str, choices=("transfer",), default="transfer")
    parser.add_argument("--contract-check-only", type=_parse_bool, default=False)
    return parser.parse_args()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BCContractError(message)


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def _resolve_device(device_arg: str) -> torch.device:
    dev = device_arg.strip().lower()
    if dev == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if dev == "cuda":
        if not torch.cuda.is_available():
            raise BCContractError("--device cuda requested but CUDA is not available")
        return torch.device("cuda")
    if dev == "cpu":
        return torch.device("cpu")
    raise BCContractError(f"Unsupported --device: {device_arg}. Expected cpu|cuda|auto")


def _validate_manifest(payload: Mapping[str, Any]) -> None:
    _require(
        str(payload.get("dataset_type", "")) == CANONICAL_DATASET_TYPE,
        (
            "Manifest dataset_type mismatch: expected "
            f"{CANONICAL_DATASET_TYPE}, got {payload.get('dataset_type', '<missing>')}"
        ),
    )
    _require(
        str(payload.get("target_action_contract", "")) == CANONICAL_TARGET_ACTION_CONTRACT,
        (
            "Manifest target_action_contract mismatch: expected "
            f"{CANONICAL_TARGET_ACTION_CONTRACT}, got {payload.get('target_action_contract', '<missing>')}"
        ),
    )
    _require(
        list(payload.get("branch_sizes", [])) == CANONICAL_BRANCH_SIZES,
        (
            "Manifest branch_sizes mismatch: expected "
            f"{CANONICAL_BRANCH_SIZES}, got {payload.get('branch_sizes', '<missing>')}"
        ),
    )
    _require(
        list(payload.get("branch_sizes", [])) != [6, 4, 4, 4, 4, 4, 9],
        "Rejected v1 branch sizes [6,4,4,4,4,4,9]",
    )
    _require(
        str(payload.get("attack_target_semantics", "")) == CANONICAL_ATTACK_TARGET_SEMANTICS,
        (
            "Manifest attack_target_semantics mismatch: expected "
            f"{CANONICAL_ATTACK_TARGET_SEMANTICS}, got {payload.get('attack_target_semantics', '<missing>')}"
        ),
    )
    _require(
        payload.get("semantic_parity_claim", True) is False,
        "Manifest semantic_parity_claim must be false.",
    )
    _require(
        payload.get("direct_weight_transfer_claim", True) is False,
        "Manifest direct_weight_transfer_claim must be false.",
    )


def _build_dataloader(
    split: SplitData,
    *,
    batch_size: int,
    shuffle: bool,
    num_workers: int,
    seed: int,
) -> DataLoader[tuple[Tensor, Tensor]]:
    ds = BCSplitTorchDataset(split)
    generator = torch.Generator()
    generator.manual_seed(seed)
    return DataLoader(
        ds,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=False,
        drop_last=False,
        generator=generator,
    )


def _safe_div(numerator: float, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator / float(denominator))


def _action_type_shares(histogram: Mapping[str, int]) -> Dict[str, float]:
    total = int(sum(int(v) for v in histogram.values()))
    noop = int(histogram.get("0", 0))
    move = int(histogram.get("1", 0))
    produce = int(histogram.get("4", 0))
    attack = int(histogram.get("5", 0))
    return {
        "predicted_noop_share": _safe_div(float(noop), total),
        "predicted_move_share": _safe_div(float(move), total),
        "predicted_produce_share": _safe_div(float(produce), total),
        "predicted_attack_share": _safe_div(float(attack), total),
    }


def _entropy_from_histogram(histogram: Mapping[str, int]) -> Dict[str, float]:
    counts = [int(v) for v in histogram.values()]
    total = int(sum(counts))
    if total <= 0:
        return {
            "action_type_entropy": 0.0,
            "action_type_entropy_normalized": 0.0,
        }
    probs = [float(c) / float(total) for c in counts if c > 0]
    entropy = -sum(p * math.log(p) for p in probs)
    max_entropy = math.log(max(1, len(counts)))
    normalized = entropy / max_entropy if max_entropy > 0.0 else 0.0
    return {
        "action_type_entropy": float(entropy),
        "action_type_entropy_normalized": float(normalized),
    }


def _format_optional_int(value: Optional[int]) -> str:
    return "unlimited" if value is None else str(value)


def _validate_head_shapes(logits: Mapping[str, Tensor], batch_size: int) -> None:
    for spec in BRANCH_SPECS:
        if spec.logits_key not in logits:
            raise BCContractError(f"Missing logits key: {spec.logits_key}")
        shape = list(logits[spec.logits_key].shape)
        expected = [batch_size, 576, spec.branch_size]
        _require(shape == expected, f"Head shape mismatch for {spec.logits_key}: {shape} != {expected}")


def _evaluate_epoch(
    *,
    model: nn.Module,
    loader: DataLoader[tuple[Tensor, Tensor]],
    device: torch.device,
    max_batches: Optional[int],
) -> Dict[str, Any]:
    model.eval()
    branch_loss_sum: Dict[str, float] = {spec.branch_name: 0.0 for spec in BRANCH_SPECS}
    branch_active: Dict[str, int] = {spec.branch_name: 0 for spec in BRANCH_SPECS}
    branch_correct: Dict[str, int] = {spec.branch_name: 0 for spec in BRANCH_SPECS}

    objective_loss_sum = 0.0
    objective_active_count = 0
    processed_batches = 0
    non_finite_detected = False

    exact_match_cells = 0
    total_cells = 0
    action_type_histogram: Dict[str, int] = {str(i): 0 for i in range(6)}
    action_type_confidence_sum = 0.0
    action_type_confidence_count = 0

    with torch.no_grad():
        for x_cpu, y_cpu in loader:
            if max_batches is not None and processed_batches >= max_batches:
                break

            x = x_cpu.to(device=device)
            y = y_cpu.to(device=device)

            logits = model(x)
            _validate_head_shapes(logits, int(x.shape[0]))

            batch = compute_branchwise_loss(logits_by_key=logits, target_action_branches=y)

            objective_loss_sum += float(batch.objective_loss_sum)
            objective_active_count += int(batch.objective_active_count)
            for spec in BRANCH_SPECS:
                name = spec.branch_name
                branch_loss_sum[name] += float(batch.loss_sum_by_branch[name])
                branch_active[name] += int(batch.active_count_by_branch[name])
                branch_correct[name] += int(batch.correct_count_by_branch[name])

            branch_all_match: Optional[Tensor] = None
            for spec in BRANCH_SPECS:
                pred = torch.argmax(logits[spec.logits_key], dim=-1)
                match = pred.eq(y[..., spec.target_index])
                branch_all_match = match if branch_all_match is None else (branch_all_match & match)

            assert branch_all_match is not None
            exact_match_cells += int(branch_all_match.sum().item())
            total_cells += int(branch_all_match.numel())

            action_type_logits = logits["action_type_logits"]
            action_type_probs = torch.softmax(action_type_logits, dim=-1)
            action_type_pred = torch.argmax(action_type_probs, dim=-1)
            action_type_max_prob = torch.max(action_type_probs, dim=-1).values

            action_type_confidence_sum += float(action_type_max_prob.sum().item())
            action_type_confidence_count += int(action_type_max_prob.numel())

            bincount = torch.bincount(action_type_pred.reshape(-1), minlength=6)
            for i in range(6):
                action_type_histogram[str(i)] += int(bincount[i].item())

            batch_total_loss = float(batch.total_loss.detach().item())
            if not math.isfinite(batch_total_loss):
                non_finite_detected = True

            processed_batches += 1

    metrics: Dict[str, Any] = {
        "validation_total_loss": _safe_div(objective_loss_sum, objective_active_count),
        "validation_exact_branch_accuracy": _safe_div(float(exact_match_cells), total_cells),
        "validation_non_finite_detected": bool(non_finite_detected),
        "validation_batches_executed": int(processed_batches),
    }

    for spec in BRANCH_SPECS:
        name = spec.branch_name
        metrics[f"validation_{name}_loss"] = _safe_div(branch_loss_sum[name], branch_active[name])
        metrics[f"validation_{name}_accuracy"] = _safe_div(float(branch_correct[name]), branch_active[name])
        metrics[f"validation_{name}_active_count"] = int(branch_active[name])

    metrics["validation_action_type_distribution"] = action_type_histogram
    metrics.update(_action_type_shares(action_type_histogram))
    metrics.update(_entropy_from_histogram(action_type_histogram))
    metrics["validation_action_type_mean_confidence"] = _safe_div(
        action_type_confidence_sum,
        action_type_confidence_count,
    )
    return metrics


def _train_epoch(
    *,
    model: nn.Module,
    loader: DataLoader[tuple[Tensor, Tensor]],
    device: torch.device,
    optimizer: AdamW,
    max_batches: Optional[int],
) -> Dict[str, Any]:
    model.train()
    branch_loss_sum: Dict[str, float] = {spec.branch_name: 0.0 for spec in BRANCH_SPECS}
    branch_active: Dict[str, int] = {spec.branch_name: 0 for spec in BRANCH_SPECS}
    branch_correct: Dict[str, int] = {spec.branch_name: 0 for spec in BRANCH_SPECS}

    objective_loss_sum = 0.0
    objective_active_count = 0
    processed_batches = 0
    optimizer_steps = 0
    non_finite_detected = False

    for x_cpu, y_cpu in loader:
        if max_batches is not None and processed_batches >= max_batches:
            break

        x = x_cpu.to(device=device)
        y = y_cpu.to(device=device)

        logits = model(x)
        _validate_head_shapes(logits, int(x.shape[0]))
        batch = compute_branchwise_loss(logits_by_key=logits, target_action_branches=y)

        loss = batch.total_loss
        loss_value = float(loss.detach().item())
        if not math.isfinite(loss_value):
            non_finite_detected = True

        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        optimizer_steps += 1

        objective_loss_sum += float(batch.objective_loss_sum)
        objective_active_count += int(batch.objective_active_count)
        for spec in BRANCH_SPECS:
            name = spec.branch_name
            branch_loss_sum[name] += float(batch.loss_sum_by_branch[name])
            branch_active[name] += int(batch.active_count_by_branch[name])
            branch_correct[name] += int(batch.correct_count_by_branch[name])

        processed_batches += 1

    metrics: Dict[str, Any] = {
        "train_total_loss": _safe_div(objective_loss_sum, objective_active_count),
        "train_non_finite_detected": bool(non_finite_detected),
        "train_batches_executed": int(processed_batches),
        "optimizer_steps_epoch": int(optimizer_steps),
    }
    for spec in BRANCH_SPECS:
        name = spec.branch_name
        metrics[f"train_{name}_loss"] = _safe_div(branch_loss_sum[name], branch_active[name])
        metrics[f"train_{name}_accuracy"] = _safe_div(float(branch_correct[name]), branch_active[name])
        metrics[f"train_{name}_active_count"] = int(branch_active[name])
    return metrics


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _checkpoint_payload(
    *,
    model: nn.Module,
    optimizer: AdamW,
    cfg: FullConfig,
    epoch: int,
    best_validation_loss: float,
    current_metrics: Mapping[str, Any],
    optimizer_step_count_total: int,
) -> Dict[str, Any]:
    return {
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "config": asdict(cfg),
        "epoch": int(epoch),
        "best_validation_loss": float(best_validation_loss),
        "metrics": dict(current_metrics),
        "optimizer_step_count_total": int(optimizer_step_count_total),
    }


def _validate_best_checkpoint_compatibility(best_checkpoint: Path, device: torch.device) -> Dict[str, Any]:
    payload = torch.load(best_checkpoint, map_location=device)
    if not isinstance(payload, dict):
        raise BCContractError("Checkpoint payload is not a dict")
    state = payload.get("model_state_dict")
    if not isinstance(state, dict):
        raise BCContractError("Checkpoint missing model_state_dict")

    model = build_day3_student_model()
    missing, unexpected = model.load_state_dict(state, strict=True)
    model.to(device)
    model.eval()

    dummy = torch.zeros((1, 24, 24, 27), dtype=torch.float32, device=device)
    with torch.no_grad():
        logits = model(dummy)

    expected_shapes: Dict[str, list[int]] = {
        "action_type_logits": [1, 576, 6],
        "move_dir_logits": [1, 576, 4],
        "harvest_dir_logits": [1, 576, 4],
        "return_dir_logits": [1, 576, 4],
        "produce_dir_logits": [1, 576, 4],
        "produce_unit_type_logits": [1, 576, 7],
        "attack_target_local_logits": [1, 576, 49],
    }
    actual_shapes = {k: list(v.shape) for k, v in logits.items() if k in expected_shapes}

    v1_detected = False
    produce_shape = actual_shapes.get("produce_unit_type_logits", [])
    attack_shape = actual_shapes.get("attack_target_local_logits", [])
    if len(produce_shape) == 3 and produce_shape[-1] == 4:
        v1_detected = True
    if len(attack_shape) == 3 and attack_shape[-1] == 9:
        v1_detected = True

    return {
        "checkpoint_path": str(best_checkpoint),
        "load_success": True,
        "missing_state_dict_keys": list(missing),
        "unexpected_state_dict_keys": list(unexpected),
        "dummy_forward_input_shape": [1, 24, 24, 27],
        "output_head_shapes": actual_shapes,
        "expected_head_shapes": expected_shapes,
        "produce_head_size": produce_shape[-1] if len(produce_shape) == 3 else None,
        "attack_head_size": attack_shape[-1] if len(attack_shape) == 3 else None,
        "v1_regression_detected": bool(v1_detected),
        "fake_heuristic_fallback_used": False,
    }


def _main_summary_markdown(summary: Mapping[str, Any]) -> str:
    branch_rows = []
    per_branch = summary.get("per_branch_validation", {})
    for spec in BRANCH_SPECS:
        name = spec.branch_name
        row = per_branch.get(name, {})
        branch_rows.append(
            "| {name} | {loss:.6f} | {acc:.6f} |".format(
                name=name,
                loss=float(row.get("loss", 0.0)),
                acc=float(row.get("accuracy", 0.0)),
            )
        )

    lines = [
        f"# {summary.get('run_label', 'stage6b1')} Training Summary",
        "",
        f"- classification: {summary.get('classification')}",
        f"- dataset_path: {summary.get('dataset_path')}",
        f"- model_variant: {summary.get('model_variant')}",
        f"- device: {summary.get('device')}",
        f"- epochs_completed: {summary.get('epochs_completed')}",
        f"- best_epoch: {summary.get('best_epoch')}",
        f"- best_validation_total_loss: {summary.get('best_validation_total_loss')}",
        f"- final_validation_total_loss: {summary.get('final_validation_total_loss')}",
        "",
        "## Validation Per-Branch",
        "",
        "| branch | val_loss | val_accuracy |",
        "|---|---:|---:|",
        *branch_rows,
        "",
        "## Offline Action-Type Diagnostics",
        "",
        f"- validation_action_type_distribution: {summary.get('validation_action_type_distribution')}",
        f"- predicted_noop_share: {summary.get('predicted_noop_share')}",
        f"- predicted_move_share: {summary.get('predicted_move_share')}",
        f"- predicted_produce_share: {summary.get('predicted_produce_share')}",
        f"- predicted_attack_share: {summary.get('predicted_attack_share')}",
        f"- action_type_entropy_normalized: {summary.get('action_type_entropy_normalized')}",
        f"- action_type_mean_confidence: {summary.get('validation_action_type_mean_confidence')}",
        "",
        "## Safety Notes",
        "",
        "- no_teacher_training: true",
        "- no_ppo_finetuning: true",
        "- semantic_parity_claim: false",
        "- direct_weight_transfer_claim: false",
        "- behavior_quality_claim_from_loss_only: false",
    ]
    return "\n".join(lines) + "\n"


def _classification_from_results(
    *,
    contract_ok: bool,
    any_non_finite: bool,
    checkpoint_ok: bool,
    v1_regression: bool,
    fallback_used: bool,
    run_limited: bool,
) -> str:
    if not contract_ok:
        return "STAGE6B1_FULL_BC_TRAINING_FAIL_CONTRACT_CHECK"
    if any_non_finite:
        return "STAGE6B1_FULL_BC_TRAINING_FAIL_LOSS_NAN_INF"
    if not checkpoint_ok:
        return "STAGE6B1_FULL_BC_TRAINING_FAIL_CHECKPOINT_LOAD"
    if v1_regression:
        return "STAGE6B1_FULL_BC_TRAINING_FAIL_V1_REGRESSION"
    if fallback_used:
        return "STAGE6B1_FULL_BC_TRAINING_FAIL_FALLBACK_USED"
    if run_limited:
        return "STAGE6B1_FULL_BC_TRAINING_PASS_WITH_WARNINGS"
    return "STAGE6B1_FULL_BC_TRAINING_PASS_READY_FOR_UNITY_SANITY"


def _run_contract_only(
    *,
    cfg: FullConfig,
    dataset: LoadedBCDataset,
    device: torch.device,
) -> Dict[str, Any]:
    model = build_day3_student_model()
    model.to(device)
    model.eval()

    val_loader = _build_dataloader(
        dataset.validation,
        batch_size=cfg.batch_size,
        shuffle=False,
        num_workers=cfg.num_workers,
        seed=cfg.seed,
    )
    x_cpu, y_cpu = next(iter(val_loader))
    x = x_cpu.to(device=device)
    y = y_cpu.to(device=device)
    with torch.no_grad():
        logits = model(x)
    _validate_head_shapes(logits, int(x.shape[0]))

    return {
        "status": "pass",
        "mode": "contract_check_only",
        "dataset_path": str(dataset.run_dir),
        "train_samples": int(dataset.train.samples),
        "validation_samples": int(dataset.validation.samples),
        "train_shape": list(dataset.train.input_tensor.shape),
        "validation_shape": list(dataset.validation.input_tensor.shape),
        "first_validation_batch_input_shape": list(x.shape),
        "first_validation_batch_target_shape": list(y.shape),
        "forward_head_shapes": {k: list(v.shape) for k, v in logits.items() if k.endswith("_logits")},
        "contract_checks": {
            "target_action_contract": dataset.manifest_payload.get("target_action_contract"),
            "branch_sizes": dataset.manifest_payload.get("branch_sizes"),
            "attack_target_semantics": dataset.manifest_payload.get("attack_target_semantics"),
            "semantic_parity_claim": dataset.manifest_payload.get("semantic_parity_claim"),
            "direct_weight_transfer_claim": dataset.manifest_payload.get("direct_weight_transfer_claim"),
        },
        "notes": [
            "No optimizer steps executed in contract-check-only mode.",
            "No checkpoint written in contract-check-only mode.",
            "No teacher training and no PPO fine-tuning.",
        ],
    }


def main() -> int:
    args = parse_args()
    cfg = FullConfig(
        bc_ready_dir=str(args.bc_ready_dir),
        device=str(args.device),
        epochs=int(args.epochs),
        batch_size=int(args.batch_size),
        learning_rate=float(args.learning_rate),
        weight_decay=float(args.weight_decay),
        num_workers=int(args.num_workers),
        seed=int(args.seed),
        output_dir=str(args.output_dir),
        run_label=str(args.run_label),
        save_every_epoch=bool(args.save_every_epoch),
        early_stopping_patience=int(args.early_stopping_patience),
        max_train_batches=args.max_train_batches,
        max_validation_batches=args.max_validation_batches,
        model_variant=str(args.model_variant),
        contract_check_only=bool(args.contract_check_only),
    )

    _set_seed(cfg.seed)
    validate_student_branch_contract_consistency(expected_bc_branch_sizes=EXPECTED_BC_BRANCH_SIZES)

    output_dir = Path(cfg.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        dataset = load_bc_ready_dataset(Path(cfg.bc_ready_dir))
        _validate_manifest(dataset.manifest_payload)
        _require(
            list(dataset.manifest_payload.get("branch_sizes", [])) == CANONICAL_BRANCH_SIZES,
            "Dataset branch sizes are not canonical unity v2 [6,4,4,4,4,7,49]",
        )

        device = _resolve_device(cfg.device)

        if cfg.contract_check_only:
            preflight = _run_contract_only(cfg=cfg, dataset=dataset, device=device)
            preflight_path = output_dir / f"{cfg.run_label}_contract_check_report.json"
            _write_json(preflight_path, preflight)
            print(f"[OK] Contract check passed: {preflight_path}")
            return 0

        model = build_day3_student_model()
        model.to(device)
        train_loader = _build_dataloader(
            dataset.train,
            batch_size=cfg.batch_size,
            shuffle=True,
            num_workers=cfg.num_workers,
            seed=cfg.seed,
        )
        val_loader = _build_dataloader(
            dataset.validation,
            batch_size=cfg.batch_size,
            shuffle=False,
            num_workers=cfg.num_workers,
            seed=cfg.seed,
        )
        optimizer = AdamW(
            model.parameters(),
            lr=cfg.learning_rate,
            weight_decay=cfg.weight_decay,
        )

        history: list[Dict[str, Any]] = []
        best_val_loss = float("inf")
        best_epoch = 0
        best_checkpoint_path = output_dir / f"{cfg.run_label}_best.pt"
        final_checkpoint_path = output_dir / f"{cfg.run_label}_final.pt"
        patience_bad_epochs = 0
        optimizer_step_count_total = 0
        any_non_finite = False
        stopped_early = False
        stop_reason = "completed_all_epochs"

        for epoch in range(1, cfg.epochs + 1):
            epoch_start = time.perf_counter()
            train_metrics = _train_epoch(
                model=model,
                loader=train_loader,
                device=device,
                optimizer=optimizer,
                max_batches=cfg.max_train_batches,
            )
            val_metrics = _evaluate_epoch(
                model=model,
                loader=val_loader,
                device=device,
                max_batches=cfg.max_validation_batches,
            )
            epoch_duration_sec = float(time.perf_counter() - epoch_start)

            optimizer_step_count_total += int(train_metrics["optimizer_steps_epoch"])
            epoch_record: Dict[str, Any] = {
                "epoch": int(epoch),
                "learning_rate": float(optimizer.param_groups[0]["lr"]),
                "optimizer_step_count_total": int(optimizer_step_count_total),
                "epoch_duration_sec": epoch_duration_sec,
                "no_nan_inf_loss": bool(
                    (not bool(train_metrics.get("train_non_finite_detected", False)))
                    and (not bool(val_metrics.get("validation_non_finite_detected", False)))
                ),
            }
            epoch_record.update(train_metrics)
            epoch_record.update(val_metrics)
            history.append(epoch_record)

            train_total = float(epoch_record["train_total_loss"])
            val_total = float(epoch_record["validation_total_loss"])
            any_non_finite = any_non_finite or (not math.isfinite(train_total)) or (not math.isfinite(val_total))
            any_non_finite = any_non_finite or (not bool(epoch_record["no_nan_inf_loss"]))

            if cfg.save_every_epoch:
                epoch_ckpt = output_dir / f"{cfg.run_label}_epoch_{epoch:03d}.pt"
                torch.save(
                    _checkpoint_payload(
                        model=model,
                        optimizer=optimizer,
                        cfg=cfg,
                        epoch=epoch,
                        best_validation_loss=best_val_loss,
                        current_metrics=epoch_record,
                        optimizer_step_count_total=optimizer_step_count_total,
                    ),
                    epoch_ckpt,
                )

            improved = val_total < best_val_loss
            if improved:
                best_val_loss = val_total
                best_epoch = epoch
                patience_bad_epochs = 0
                torch.save(
                    _checkpoint_payload(
                        model=model,
                        optimizer=optimizer,
                        cfg=cfg,
                        epoch=epoch,
                        best_validation_loss=best_val_loss,
                        current_metrics=epoch_record,
                        optimizer_step_count_total=optimizer_step_count_total,
                    ),
                    best_checkpoint_path,
                )
            else:
                patience_bad_epochs += 1

            if cfg.early_stopping_patience > 0 and patience_bad_epochs >= cfg.early_stopping_patience:
                stopped_early = True
                stop_reason = f"early_stopping_patience_{cfg.early_stopping_patience}"
                break

        _require(len(history) > 0, "No training epochs executed")

        final_epoch_record = history[-1]
        torch.save(
            _checkpoint_payload(
                model=model,
                optimizer=optimizer,
                cfg=cfg,
                epoch=int(final_epoch_record["epoch"]),
                best_validation_loss=best_val_loss,
                current_metrics=final_epoch_record,
                optimizer_step_count_total=optimizer_step_count_total,
            ),
            final_checkpoint_path,
        )

        _require(best_checkpoint_path.exists(), "Best checkpoint was not saved")

        compatibility = _validate_best_checkpoint_compatibility(best_checkpoint_path, device=device)
        compatibility_report_path = output_dir / CHECKPOINT_COMPATIBILITY_FILENAME
        _write_json(compatibility_report_path, compatibility)

        checkpoint_ok = bool(compatibility.get("load_success", False)) and not bool(
            compatibility.get("missing_state_dict_keys")
        ) and not bool(compatibility.get("unexpected_state_dict_keys"))
        v1_regression = bool(compatibility.get("v1_regression_detected", True))
        fallback_used = bool(compatibility.get("fake_heuristic_fallback_used", False))

        run_limited = (cfg.max_train_batches is not None) or (cfg.max_validation_batches is not None)
        classification = _classification_from_results(
            contract_ok=True,
            any_non_finite=any_non_finite,
            checkpoint_ok=checkpoint_ok,
            v1_regression=v1_regression,
            fallback_used=fallback_used,
            run_limited=run_limited,
        )

        per_branch_validation: Dict[str, Dict[str, float]] = {}
        for spec in BRANCH_SPECS:
            per_branch_validation[spec.branch_name] = {
                "loss": float(final_epoch_record[f"validation_{spec.branch_name}_loss"]),
                "accuracy": float(final_epoch_record[f"validation_{spec.branch_name}_accuracy"]),
            }

        summary_payload: Dict[str, Any] = {
            "stage": "Stage6B1",
            "classification": classification,
            "dataset_path": str(dataset.run_dir),
            "model_variant": cfg.model_variant,
            "device": str(device),
            "train_samples": int(dataset.train.samples),
            "validation_samples": int(dataset.validation.samples),
            "epochs_configured": int(cfg.epochs),
            "epochs_completed": int(len(history)),
            "best_epoch": int(best_epoch),
            "best_validation_total_loss": float(best_val_loss),
            "final_validation_total_loss": float(final_epoch_record["validation_total_loss"]),
            "final_train_total_loss": float(final_epoch_record["train_total_loss"]),
            "validation_exact_branch_accuracy": float(final_epoch_record["validation_exact_branch_accuracy"]),
            "validation_action_type_distribution": final_epoch_record["validation_action_type_distribution"],
            "predicted_noop_share": float(final_epoch_record["predicted_noop_share"]),
            "predicted_move_share": float(final_epoch_record["predicted_move_share"]),
            "predicted_produce_share": float(final_epoch_record["predicted_produce_share"]),
            "predicted_attack_share": float(final_epoch_record["predicted_attack_share"]),
            "action_type_entropy": float(final_epoch_record["action_type_entropy"]),
            "action_type_entropy_normalized": float(final_epoch_record["action_type_entropy_normalized"]),
            "validation_action_type_mean_confidence": float(final_epoch_record["validation_action_type_mean_confidence"]),
            "per_branch_validation": per_branch_validation,
            "learning_rate": float(cfg.learning_rate),
            "weight_decay": float(cfg.weight_decay),
            "batch_size": int(cfg.batch_size),
            "num_workers": int(cfg.num_workers),
            "seed": int(cfg.seed),
            "max_train_batches": cfg.max_train_batches,
            "max_validation_batches": cfg.max_validation_batches,
            "save_every_epoch": bool(cfg.save_every_epoch),
            "early_stopping_patience": int(cfg.early_stopping_patience),
            "stopped_early": bool(stopped_early),
            "stop_reason": stop_reason,
            "optimizer_step_count_total": int(optimizer_step_count_total),
            "no_nan_inf_loss": bool(not any_non_finite),
            "contract_checks": {
                "dataset_type": dataset.manifest_payload.get("dataset_type"),
                "target_action_contract": dataset.manifest_payload.get("target_action_contract"),
                "attack_target_semantics": dataset.manifest_payload.get("attack_target_semantics"),
                "branch_sizes": dataset.manifest_payload.get("branch_sizes"),
                "observation_shape_per_sample": dataset.manifest_payload.get("observation_shape_per_sample"),
                "action_shape_per_sample": dataset.manifest_payload.get("action_shape_per_sample"),
            },
            "checkpoint_paths": {
                "best": str(best_checkpoint_path),
                "final": str(final_checkpoint_path),
                "compatibility_report": str(compatibility_report_path),
            },
            "compatibility": compatibility,
            "base_worker_metrics": {
                "available": False,
                "reason": "Unit type channels are not inferred in this script; reporting unavailable by design.",
            },
            "constraints": {
                "no_teacher_training": True,
                "no_ppo_finetuning": True,
                "no_week5_artifact_modification": True,
                "semantic_parity_claim": False,
                "direct_weight_transfer_claim": False,
                "behavior_quality_claim_from_loss_only": False,
                "fake_heuristic_random_fallback_used": False,
                "v1_rejection_weakened": False,
            },
            "recommended_next_stage": "Stage6B2 — Bind Full BC Checkpoint To Unity Bridge And Run Controlled Sanity With Stage6R5C Telemetry",
            "run_label": cfg.run_label,
        }

        history_payload: Dict[str, Any] = {
            "stage": "Stage6B1",
            "run_label": cfg.run_label,
            "dataset_path": str(dataset.run_dir),
            "history": history,
        }

        history_path = output_dir / "training_history.json"
        summary_json_path = output_dir / "training_summary.json"
        summary_md_path = output_dir / "training_summary.md"
        _write_json(history_path, history_payload)
        _write_json(summary_json_path, summary_payload)
        _write_text(summary_md_path, _main_summary_markdown(summary_payload))

        main_report_json_path = _repo_root() / STAGE6B1_MAIN_REPORT_JSON
        main_report_md_path = _repo_root() / STAGE6B1_MAIN_REPORT_MD
        _write_json(main_report_json_path, summary_payload)
        _write_text(main_report_md_path, _main_summary_markdown(summary_payload))

        print(f"[OK] Stage6B1 training completed. classification={classification}")
        print(f"[OK] best_checkpoint={best_checkpoint_path}")
        print(f"[OK] final_checkpoint={final_checkpoint_path}")
        print(f"[OK] training_history={history_path}")
        print(f"[OK] training_summary_json={summary_json_path}")
        print(f"[OK] training_summary_md={summary_md_path}")
        print(f"[OK] compatibility_report={compatibility_report_path}")
        print(f"[OK] main_report_json={main_report_json_path}")
        print(f"[OK] main_report_md={main_report_md_path}")
        return 0

    except (BCContractError, FileNotFoundError, ValueError, KeyError, RuntimeError) as exc:
        failure_payload = {
            "stage": "Stage6B1",
            "classification": "STAGE6B1_FULL_BC_TRAINING_INCONCLUSIVE",
            "error": str(exc),
            "config": asdict(cfg),
            "constraints": {
                "no_teacher_training": True,
                "no_ppo_finetuning": True,
            },
        }
        fail_path = output_dir / "stage6b1_failure_report.json"
        _write_json(fail_path, failure_payload)
        print(f"[FAIL] Stage6B1 failed: {exc}")
        print(f"[INFO] Failure report: {fail_path}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
