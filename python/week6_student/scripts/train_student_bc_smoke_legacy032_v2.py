#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

import numpy as np
import torch
from torch import Tensor, nn
from torch.optim import Adam

# Ensure sibling week6_student modules are importable when launching via script path.
THIS_FILE = Path(__file__).resolve()
WEEK6_STUDENT_DIR = THIS_FILE.parents[1]
if str(WEEK6_STUDENT_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK6_STUDENT_DIR))

from student_architecture_transfer import build_day3_student_model
from student_bc_contract import BCContractError, LoadedBCDataset
from student_bc_loader import load_bc_ready_dataset
from student_bc_metrics import EpochMetricAccumulator, compute_branchwise_loss
from student_branch_contract import EXPECTED_BC_BRANCH_SIZES, validate_student_branch_contract_consistency
from train_student_bc_minimal import create_dataloader


CANONICAL_STAGE5P4_BC_READY_DIR = Path(
    "python/week5_teacher_legacy032/teacher_exports_bc/"
    "legacy032_3m_unity_v2_bc_ready_stage5p4_20260506T153632Z"
)
CANONICAL_BRANCH_SIZES = [6, 4, 4, 4, 4, 7, 49]
CANONICAL_TARGET_ACTION_CONTRACT = "unity_v2_legacy032_gridnet"
CANONICAL_ATTACK_TARGET_SEMANTICS = "local_7x7_49"
CANONICAL_DATASET_TYPE = "bc_ready_legacy032_unity_v2"

EXPECTED_HEAD_SHAPES = {
    "action_type_logits": 6,
    "move_dir_logits": 4,
    "harvest_dir_logits": 4,
    "return_dir_logits": 4,
    "produce_dir_logits": 4,
    "produce_unit_type_logits": 7,
    "attack_target_local_logits": 49,
}


@dataclass(frozen=True)
class SmokeConfig:
    bc_ready_dir: str
    device: str
    epochs: int
    batch_size: int
    max_train_batches: int
    max_validation_batches: int
    seed: int
    output_dir: str
    run_label: str
    model_variant: str
    save_checkpoint: bool
    contract_check_only: bool
    dry_run_only: bool


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_bc_ready_dir() -> Path:
    return _repo_root() / CANONICAL_STAGE5P4_BC_READY_DIR


def _default_output_dir() -> Path:
    return _repo_root() / "python/week6_student/runs/legacy032_v2_bc_smoke_stage6r1"


def _parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid bool value: {value}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Stage6 canonical Week 6 BC smoke/preflight wrapper for Legacy032 Unity v2 contract. "
            "Defaults are pinned to Stage5P4 dataset and transfer architecture. "
            "Contract-check mode performs no optimizer updates and no weight writes. "
            "Training smoke mode is enabled only when both --contract-check-only and --dry-run-only are false."
        )
    )
    parser.add_argument("--bc-ready-dir", type=Path, default=_default_bc_ready_dir())
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-train-batches", type=int, default=1)
    parser.add_argument("--max-validation-batches", type=int, default=1)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--output-dir", type=Path, default=_default_output_dir())
    parser.add_argument("--run-label", type=str, default="legacy032_v2_bc_smoke_stage6r1")
    parser.add_argument("--save-checkpoint", type=_parse_bool, default=False)
    parser.add_argument(
        "--model-variant",
        type=str,
        choices=("transfer", "minimal"),
        default="transfer",
        help=(
            "Canonical smoke default is transfer. Minimal is accepted only for explicit diagnostics; "
            "the canonical Stage6 smoke path remains transfer."
        ),
    )
    parser.add_argument(
        "--contract-check-only",
        type=_parse_bool,
        default=True,
        help="When true, run preflight contract checks only and do not train.",
    )
    parser.add_argument(
        "--dry-run-only",
        type=_parse_bool,
        default=True,
        help=(
            "Alias intent for non-training smoke. Use true with contract-check-only mode; "
            "set false together with --contract-check-only false to enable controlled smoke training."
        ),
    )
    return parser.parse_args()


def _mean(values: Iterable[float]) -> float:
    vals = [float(v) for v in values]
    if not vals:
        return 0.0
    return float(sum(vals) / len(vals))


def _is_finite(value: float) -> bool:
    return bool(math.isfinite(float(value)))


def _dict_to_markdown_lines(title: str, payload: Mapping[str, Any]) -> list[str]:
    lines = [f"### {title}", ""]
    for key, value in payload.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    return lines


def _run_bounded_epoch(
    *,
    model: nn.Module,
    loader: Any,
    device: torch.device,
    max_batches: int,
    optimizer: Adam | None,
) -> tuple[Dict[str, float | int], int, int]:
    is_train = optimizer is not None
    if is_train:
        model.train()
    else:
        model.eval()

    accumulator = EpochMetricAccumulator()
    batches_executed = 0
    optimizer_steps = 0

    for x_cpu, y_cpu in loader:
        if batches_executed >= max_batches:
            break
        x = x_cpu.to(device=device)
        y = y_cpu.to(device=device)

        with torch.set_grad_enabled(is_train):
            logits = model(x)
            batch_out = compute_branchwise_loss(logits_by_key=logits, target_action_branches=y)

            if is_train:
                assert optimizer is not None
                optimizer.zero_grad(set_to_none=True)
                batch_out.total_loss.backward()
                optimizer.step()
                optimizer_steps += 1

        accumulator.update(batch_out)
        batches_executed += 1

    prefix = "train" if is_train else "val"
    return accumulator.to_metrics(prefix=prefix), batches_executed, optimizer_steps


def _write_smoke_reports(
    *,
    output_dir: Path,
    run_label: str,
    json_payload: Mapping[str, Any],
) -> tuple[Path, Path]:
    json_path = output_dir / f"{run_label}_smoke_training_report.json"
    md_path = output_dir / f"{run_label}_smoke_training_report.md"

    json_path.write_text(json.dumps(json_payload, ensure_ascii=True, indent=2), encoding="utf-8")

    lines: list[str] = [
        f"# {run_label} Smoke Training Report",
        "",
        f"- status: {json_payload.get('status')}",
        f"- mode: {json_payload.get('mode')}",
        f"- model_variant: {json_payload.get('model_variant')}",
        f"- optimizer_step_count: {json_payload.get('optimizer_step_count')}",
        f"- train_batches_executed: {json_payload.get('train_batches_executed')}",
        f"- validation_batches_executed: {json_payload.get('validation_batches_executed')}",
        f"- checkpoint_path: {json_payload.get('checkpoint_path')}",
        "",
    ]
    lines.extend(_dict_to_markdown_lines("Train Metrics", json_payload.get("train_metrics", {})))
    lines.extend(_dict_to_markdown_lines("Validation Metrics", json_payload.get("validation_metrics", {})))
    lines.extend(_dict_to_markdown_lines("Dataset Contract", json_payload.get("manifest_checks", {})))

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def _run_controlled_smoke_training(config: SmokeConfig) -> Dict[str, Any]:
    validate_student_branch_contract_consistency(expected_bc_branch_sizes=EXPECTED_BC_BRANCH_SIZES)
    dataset: LoadedBCDataset = load_bc_ready_dataset(Path(config.bc_ready_dir))
    _validate_manifest(dataset.manifest_payload)

    if config.model_variant != "transfer":
        raise BCContractError(
            "Stage6A1 canonical smoke requires --model-variant transfer; "
            f"got {config.model_variant}"
        )

    device = torch.device(config.device)
    model: nn.Module = build_day3_student_model()
    model.to(device)

    train_loader = create_dataloader(dataset.train, batch_size=config.batch_size, shuffle=True)
    val_loader = create_dataloader(dataset.validation, batch_size=config.batch_size, shuffle=False)

    first_train_x, first_train_y = next(iter(train_loader))
    first_train_x = first_train_x.to(device=device)
    first_train_y = first_train_y.to(device=device)
    _validate_tensor_finite("first_train_x", first_train_x)

    with torch.no_grad():
        first_train_logits = model(first_train_x)

    expected_first_shapes = _expected_head_shapes(int(first_train_x.shape[0]))
    for key, expected_shape in expected_first_shapes.items():
        if key not in first_train_logits:
            raise BCContractError(f"Missing train logits key: {key}")
        actual_shape = list(first_train_logits[key].shape)
        _require(actual_shape == expected_shape, f"Train logits {key} shape mismatch: {actual_shape} != {expected_shape}")
        _validate_tensor_finite(f"first_train_logits[{key}]", first_train_logits[key])

    _require(
        list(first_train_y.shape) == [int(first_train_x.shape[0]), 576, 7],
        f"Train targets shape mismatch: {list(first_train_y.shape)}",
    )

    optimizer = Adam(model.parameters(), lr=1e-3)

    train_total_losses: list[float] = []
    val_total_losses: list[float] = []
    final_train_metrics: Dict[str, float | int] = {}
    final_val_metrics: Dict[str, float | int] = {}
    total_optimizer_steps = 0
    total_train_batches = 0
    total_val_batches = 0

    for _ in range(config.epochs):
        train_metrics, train_batches, optimizer_steps = _run_bounded_epoch(
            model=model,
            loader=train_loader,
            device=device,
            max_batches=config.max_train_batches,
            optimizer=optimizer,
        )
        val_metrics, val_batches, _ = _run_bounded_epoch(
            model=model,
            loader=val_loader,
            device=device,
            max_batches=config.max_validation_batches,
            optimizer=None,
        )

        total_optimizer_steps += optimizer_steps
        total_train_batches += train_batches
        total_val_batches += val_batches

        train_total_losses.append(float(train_metrics["train_total_loss"]))
        val_total_losses.append(float(val_metrics["val_total_loss"]))
        final_train_metrics = train_metrics
        final_val_metrics = val_metrics

    no_nan_inf_loss = all(_is_finite(v) for v in train_total_losses + val_total_losses)
    if not no_nan_inf_loss:
        raise BCContractError("NaN/Inf detected in smoke training loss values")

    checkpoint_path: str | None = None
    if config.save_checkpoint:
        output_dir = Path(config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        ckpt = {
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "config": asdict(config),
            "train_metrics": final_train_metrics,
            "validation_metrics": final_val_metrics,
            "optimizer_step_count": total_optimizer_steps,
        }
        save_path = output_dir / f"{config.run_label}_smoke_checkpoint.pt"
        torch.save(ckpt, save_path)
        checkpoint_path = str(save_path)

    manifest = dataset.manifest_payload
    train_branch_losses = {
        k: float(v)
        for k, v in final_train_metrics.items()
        if isinstance(v, float) and k.startswith("train_") and k.endswith("_loss") and k != "train_total_loss"
    }
    train_branch_acc = {
        k: float(v)
        for k, v in final_train_metrics.items()
        if isinstance(v, float) and k.startswith("train_") and k.endswith("_accuracy")
    }
    val_branch_losses = {
        k: float(v)
        for k, v in final_val_metrics.items()
        if isinstance(v, float) and k.startswith("val_") and k.endswith("_loss") and k != "val_total_loss"
    }
    val_branch_acc = {
        k: float(v)
        for k, v in final_val_metrics.items()
        if isinstance(v, float) and k.startswith("val_") and k.endswith("_accuracy")
    }

    return {
        "status": "pass",
        "mode": "controlled_smoke_training",
        "config": asdict(config),
        "manifest_checks": {
            "dataset_type": manifest.get("dataset_type"),
            "target_action_contract": manifest.get("target_action_contract"),
            "branch_sizes": manifest.get("branch_sizes"),
            "attack_target_semantics": manifest.get("attack_target_semantics"),
            "semantic_parity_claim": manifest.get("semantic_parity_claim"),
            "direct_weight_transfer_claim": manifest.get("direct_weight_transfer_claim"),
        },
        "model_variant": config.model_variant,
        "branch_sizes": CANONICAL_BRANCH_SIZES,
        "first_batch_head_shapes": {k: list(v.shape) for k, v in first_train_logits.items() if k in EXPECTED_HEAD_SHAPES},
        "first_batch_target_shape": list(first_train_y.shape),
        "train_total_loss_first": float(train_total_losses[0]) if train_total_losses else 0.0,
        "train_total_loss_last": float(train_total_losses[-1]) if train_total_losses else 0.0,
        "train_total_loss_mean": _mean(train_total_losses),
        "validation_total_loss_mean": _mean(val_total_losses),
        "train_branch_losses": train_branch_losses,
        "validation_branch_losses": val_branch_losses,
        "train_branch_accuracies": train_branch_acc,
        "validation_branch_accuracies": val_branch_acc,
        "train_metrics": final_train_metrics,
        "validation_metrics": final_val_metrics,
        "train_batches_executed": int(total_train_batches),
        "validation_batches_executed": int(total_val_batches),
        "optimizer_step_count": int(total_optimizer_steps),
        "checkpoint_path": checkpoint_path,
        "no_nan_inf_loss": bool(no_nan_inf_loss),
        "v1_regression_detected": False,
    }


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BCContractError(message)


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


def _validate_tensor_finite(name: str, tensor: Tensor) -> None:
    if not torch.isfinite(tensor).all().item():
        raise BCContractError(f"{name} contains non-finite values (NaN/Inf)")


def _expected_head_shapes(batch_size: int) -> Dict[str, list[int]]:
    return {k: [batch_size, 576, v] for k, v in EXPECTED_HEAD_SHAPES.items()}


def _run_contract_preflight(config: SmokeConfig) -> Dict[str, Any]:
    validate_student_branch_contract_consistency(expected_bc_branch_sizes=EXPECTED_BC_BRANCH_SIZES)

    dataset: LoadedBCDataset = load_bc_ready_dataset(Path(config.bc_ready_dir))
    _validate_manifest(dataset.manifest_payload)

    device = torch.device(config.device)
    if config.model_variant != "transfer":
        raise BCContractError(
            "Stage6R1 canonical smoke requires --model-variant transfer by default; "
            f"got {config.model_variant}"
        )

    model: nn.Module = build_day3_student_model()
    model.to(device)
    model.eval()

    train_loader = create_dataloader(dataset.train, batch_size=config.batch_size, shuffle=False)
    val_loader = create_dataloader(dataset.validation, batch_size=config.batch_size, shuffle=False)

    try:
        x_train, y_train = next(iter(train_loader))
    except StopIteration as exc:
        raise BCContractError("Train split is empty; cannot construct first batch") from exc

    try:
        x_val, y_val = next(iter(val_loader))
    except StopIteration as exc:
        raise BCContractError("Validation split is empty; cannot construct first batch") from exc

    _require(list(y_train.shape) == [x_train.shape[0], 576, 7], f"Train targets shape mismatch: {list(y_train.shape)}")
    _require(list(y_val.shape) == [x_val.shape[0], 576, 7], f"Validation targets shape mismatch: {list(y_val.shape)}")

    x_train = x_train.to(device=device)
    x_val = x_val.to(device=device)
    _validate_tensor_finite("x_train", x_train)
    _validate_tensor_finite("x_val", x_val)

    with torch.no_grad():
        train_logits = model(x_train)
        val_logits = model(x_val)

    expected_train_shapes = _expected_head_shapes(int(x_train.shape[0]))
    expected_val_shapes = _expected_head_shapes(int(x_val.shape[0]))

    for key, expected_shape in expected_train_shapes.items():
        if key not in train_logits:
            raise BCContractError(f"Missing train logits key: {key}")
        actual_shape = list(train_logits[key].shape)
        _require(actual_shape == expected_shape, f"Train logits {key} shape mismatch: {actual_shape} != {expected_shape}")
        _validate_tensor_finite(f"train_logits[{key}]", train_logits[key])

    for key, expected_shape in expected_val_shapes.items():
        if key not in val_logits:
            raise BCContractError(f"Missing validation logits key: {key}")
        actual_shape = list(val_logits[key].shape)
        _require(actual_shape == expected_shape, f"Validation logits {key} shape mismatch: {actual_shape} != {expected_shape}")
        _validate_tensor_finite(f"val_logits[{key}]", val_logits[key])

    manifest = dataset.manifest_payload
    report: Dict[str, Any] = {
        "status": "pass",
        "mode": "contract_check_only",
        "config": asdict(config),
        "canonical_constants": {
            "CANONICAL_STAGE5P4_BC_READY_DIR": str(CANONICAL_STAGE5P4_BC_READY_DIR),
            "CANONICAL_BRANCH_SIZES": CANONICAL_BRANCH_SIZES,
            "CANONICAL_TARGET_ACTION_CONTRACT": CANONICAL_TARGET_ACTION_CONTRACT,
            "CANONICAL_ATTACK_TARGET_SEMANTICS": CANONICAL_ATTACK_TARGET_SEMANTICS,
        },
        "manifest_checks": {
            "dataset_type": manifest.get("dataset_type"),
            "target_action_contract": manifest.get("target_action_contract"),
            "branch_sizes": manifest.get("branch_sizes"),
            "attack_target_semantics": manifest.get("attack_target_semantics"),
            "semantic_parity_claim": manifest.get("semantic_parity_claim"),
            "direct_weight_transfer_claim": manifest.get("direct_weight_transfer_claim"),
        },
        "split_shapes": {
            "train_input": list(dataset.train.input_tensor.shape),
            "train_target": list(dataset.train.target_action_branches.shape),
            "validation_input": list(dataset.validation.input_tensor.shape),
            "validation_target": list(dataset.validation.target_action_branches.shape),
            "train_batch_input": list(x_train.shape),
            "train_batch_target": list(y_train.shape),
            "validation_batch_input": list(x_val.shape),
            "validation_batch_target": list(y_val.shape),
        },
        "forward_shapes": {
            "train": {k: list(v.shape) for k, v in train_logits.items() if k in EXPECTED_HEAD_SHAPES},
            "validation": {k: list(v.shape) for k, v in val_logits.items() if k in EXPECTED_HEAD_SHAPES},
        },
        "optimizer_step_executed": False,
        "weights_updated": False,
        "notes": [
            "Contract preflight executed with torch.no_grad().",
            "No optimizer was instantiated; no checkpoint write was attempted.",
            "No v1 branch regression permitted in canonical smoke path.",
        ],
    }
    return report


def main() -> int:
    args = parse_args()
    _set_seed(int(args.seed))

    config = SmokeConfig(
        bc_ready_dir=str(args.bc_ready_dir),
        device=str(args.device),
        epochs=int(args.epochs),
        batch_size=int(args.batch_size),
        max_train_batches=int(args.max_train_batches),
        max_validation_batches=int(args.max_validation_batches),
        seed=int(args.seed),
        output_dir=str(args.output_dir),
        run_label=str(args.run_label),
        model_variant=str(args.model_variant),
        save_checkpoint=bool(args.save_checkpoint),
        contract_check_only=bool(args.contract_check_only),
        dry_run_only=bool(args.dry_run_only),
    )

    if config.max_train_batches <= 0 or config.max_validation_batches <= 0:
        print("[FAIL] max-train-batches and max-validation-batches must be > 0")
        return 1

    mode_contract_only = config.contract_check_only is True and config.dry_run_only is True
    mode_training = config.contract_check_only is False and config.dry_run_only is False
    if not mode_contract_only and not mode_training:
        print(
            "[FAIL] Invalid mode combination. Use either "
            "(--contract-check-only true and --dry-run-only true) for preflight, or "
            "(--contract-check-only false and --dry-run-only false) for controlled smoke training."
        )
        return 1

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if mode_contract_only and config.save_checkpoint:
        print("[WARN] --save-checkpoint is ignored in contract-check-only mode.")

    try:
        if mode_contract_only:
            report = _run_contract_preflight(config)
            report_path = output_dir / f"{config.run_label}_contract_check_report.json"
            report_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
            print("[OK] Stage6 contract-check-only preflight passed.")
            print(f"[OK] Canonical BC-ready dir: {config.bc_ready_dir}")
            print(f"[OK] Model variant: {config.model_variant}")
            print(f"[OK] Report: {report_path}")
            return 0

        smoke_report = _run_controlled_smoke_training(config)
        json_report_path, md_report_path = _write_smoke_reports(
            output_dir=output_dir,
            run_label=config.run_label,
            json_payload=smoke_report,
        )
        print("[OK] Stage6 controlled BC smoke training completed.")
        print(f"[OK] Canonical BC-ready dir: {config.bc_ready_dir}")
        print(f"[OK] Model variant: {config.model_variant}")
        print(f"[OK] Optimizer steps: {smoke_report['optimizer_step_count']}")
        print(f"[OK] JSON report: {json_report_path}")
        print(f"[OK] Markdown report: {md_report_path}")
        return 0

    except (BCContractError, FileNotFoundError, ValueError, KeyError, RuntimeError) as exc:
        fail_report_path = output_dir / f"{config.run_label}_stage6_wrapper_failure_report.json"
        fail_payload = {
            "status": "fail",
            "error": str(exc),
            "config": asdict(config),
            "optimizer_step_executed": False,
            "weights_updated": False,
        }
        fail_report_path.write_text(json.dumps(fail_payload, ensure_ascii=True, indent=2), encoding="utf-8")
        print(f"[FAIL] Stage6 wrapper run failed: {exc}")
        print(f"[INFO] Wrote failure report: {fail_report_path}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
