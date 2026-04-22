#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict

import numpy as np
import torch
from torch import Tensor, nn
from torch.optim import Adam
from torch.utils.data import DataLoader, Dataset

from student_bc_contract import BCContractError, SplitData
from student_bc_loader import load_bc_ready_dataset
from student_bc_metrics import EpochMetricAccumulator, compute_branchwise_loss
from student_bc_model_minimal import StudentBCModelMinimal
from student_architecture_transfer import build_day3_student_model
from student_branch_contract import BRANCH_ORDER, validate_student_branch_contract_consistency


PINNED_BC_READY_RELATIVE = Path(
    "python/week5_teacher/teacher_exports_bc/"
    "day6_bc_ready_teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z"
)


@dataclass(frozen=True)
class RunConfig:
    bc_ready_dir: str
    epochs: int
    batch_size: int
    lr: float
    device: str
    seed: int
    output_dir: str
    model_variant: str


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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_bc_ready_dir() -> Path:
    return _repo_root() / PINNED_BC_READY_RELATIVE


def _default_output_dir() -> Path:
    return _repo_root() / "python/week6_student/runs/day2_minimal_bc"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Week 6 Day 2: minimal supervised branch-wise BC training loop over pinned BC-ready dataset. "
            "This script is BC-only and not RL/PPO/Unity inference integration."
        )
    )
    parser.add_argument("--bc-ready-dir", type=Path, default=_default_bc_ready_dir())
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--output-dir", type=Path, default=_default_output_dir())
    parser.add_argument(
        "--model-variant",
        type=str,
        choices=("minimal", "transfer"),
        default="minimal",
        help="Select student architecture while preserving branch-wise BC objective semantics.",
    )
    return parser.parse_args()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def create_dataloader(split: SplitData, batch_size: int, shuffle: bool) -> DataLoader[tuple[Tensor, Tensor]]:
    ds = BCSplitTorchDataset(split)
    generator = torch.Generator()
    generator.manual_seed(17)
    return DataLoader(
        ds,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=0,
        pin_memory=False,
        drop_last=False,
        generator=generator,
    )


def run_epoch(
    model: nn.Module,
    loader: DataLoader[tuple[Tensor, Tensor]],
    device: torch.device,
    optimizer: Adam | None,
) -> Dict[str, float | int]:
    is_train = optimizer is not None
    if is_train:
        model.train()
    else:
        model.eval()

    accumulator = EpochMetricAccumulator()

    for x_cpu, y_cpu in loader:
        x = x_cpu.to(device=device, non_blocking=False)
        y = y_cpu.to(device=device, non_blocking=False)

        with torch.set_grad_enabled(is_train):
            logits = model(x)
            batch_out = compute_branchwise_loss(logits_by_key=logits, target_action_branches=y)

            if is_train:
                assert optimizer is not None
                optimizer.zero_grad(set_to_none=True)
                batch_out.total_loss.backward()
                optimizer.step()

        accumulator.update(batch_out)

    prefix = "train" if is_train else "val"
    return accumulator.to_metrics(prefix=prefix)


def _validate_contract_for_day2(dataset: Any) -> None:
    if dataset.contract.schema_version != "day6.bc_ready.v1":
        raise BCContractError(f"Day2 expected schema_version day6.bc_ready.v1, got {dataset.contract.schema_version}")
    if dataset.train.mask_available or dataset.validation.mask_available:
        print("[INFO] Optional mask present in this lineage. Day2 loop remains mask-agnostic by design.")


def _save_checkpoint(
    path: Path,
    *,
    model: nn.Module,
    optimizer: Adam,
    epoch: int,
    metrics: Dict[str, float | int],
    config: RunConfig,
) -> None:
    payload: Dict[str, Any] = {
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "metrics": metrics,
        "config": asdict(config),
    }
    torch.save(payload, path)


def _fmt_metrics(metrics: Dict[str, float | int], prefix: str) -> str:
    keys: list[str] = [f"{prefix}_total_loss"]
    for branch_name in BRANCH_ORDER:
        keys.append(f"{prefix}_{branch_name}_loss")
        keys.append(f"{prefix}_{branch_name}_accuracy")
        if branch_name != "action_type":
            keys.append(f"{prefix}_{branch_name}_active_count")
    parts: list[str] = []
    for key in keys:
        value = metrics[key]
        if isinstance(value, float):
            parts.append(f"{key}={value:.6f}")
        else:
            parts.append(f"{key}={value}")
    return " | ".join(parts)


def main() -> int:
    args = parse_args()
    set_seed(args.seed)
    validate_student_branch_contract_consistency()

    run_cfg = RunConfig(
        bc_ready_dir=str(args.bc_ready_dir),
        epochs=int(args.epochs),
        batch_size=int(args.batch_size),
        lr=float(args.lr),
        device=str(args.device),
        seed=int(args.seed),
        output_dir=str(args.output_dir),
        model_variant=str(args.model_variant),
    )

    try:
        dataset = load_bc_ready_dataset(args.bc_ready_dir)
    except (BCContractError, FileNotFoundError, ValueError, KeyError) as exc:
        print(f"[FAIL] Dataset contract load failed: {exc}")
        return 1

    _validate_contract_for_day2(dataset)

    if args.model_variant == "minimal":
        model: nn.Module = StudentBCModelMinimal()
    elif args.model_variant == "transfer":
        model = build_day3_student_model()
    else:
        raise ValueError(f"Unsupported --model-variant: {args.model_variant}")

    device = torch.device(args.device)
    model.to(device)

    train_loader = create_dataloader(dataset.train, batch_size=args.batch_size, shuffle=True)
    val_loader = create_dataloader(dataset.validation, batch_size=args.batch_size, shuffle=False)

    optimizer = Adam(model.parameters(), lr=args.lr)

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    best_val_loss = float("inf")
    history: list[Dict[str, float | int]] = []

    print("=== Week 6 BC Training (Pinned BC-ready Source) ===")
    print(f"Pinned BC-ready dir: {dataset.run_dir}")
    print(f"Model variant: {args.model_variant}")
    print(
        "Scope: supervised BC only; not RL/PPO fine-tuning; not Unity inference integration; "
        "not final architecture; does not claim transfer success"
    )

    checkpoint_prefix = f"student_bc_{args.model_variant}"

    for epoch in range(1, args.epochs + 1):
        epoch_start = time.perf_counter()

        train_metrics = run_epoch(model=model, loader=train_loader, device=device, optimizer=optimizer)
        val_metrics = run_epoch(model=model, loader=val_loader, device=device, optimizer=None)

        lr_value = float(optimizer.param_groups[0]["lr"])
        epoch_time_sec = float(time.perf_counter() - epoch_start)

        merged: Dict[str, float | int] = {}
        merged.update(train_metrics)
        merged.update(val_metrics)
        merged["learning_rate"] = lr_value
        merged["epoch_time_sec"] = epoch_time_sec
        merged["epoch"] = epoch
        history.append(merged)

        latest_path = output_dir / f"{checkpoint_prefix}_latest.pt"
        _save_checkpoint(
            latest_path,
            model=model,
            optimizer=optimizer,
            epoch=epoch,
            metrics=merged,
            config=run_cfg,
        )

        val_total_loss = float(merged["val_total_loss"])
        if val_total_loss < best_val_loss:
            best_val_loss = val_total_loss
            best_path = output_dir / f"{checkpoint_prefix}_best.pt"
            _save_checkpoint(
                best_path,
                model=model,
                optimizer=optimizer,
                epoch=epoch,
                metrics=merged,
                config=run_cfg,
            )

        print(f"\n[Epoch {epoch}/{args.epochs}] lr={lr_value:.8f} time={epoch_time_sec:.2f}s")
        print(_fmt_metrics(merged, prefix="train"))
        print(_fmt_metrics(merged, prefix="val"))

    metrics_path = output_dir / "day2_minimal_metrics_history.json"
    payload = {
        "run_config": asdict(run_cfg),
        "pinned_bc_ready_dir": str(dataset.run_dir),
        "model_variant": args.model_variant,
        "history": history,
        "scope_honesty": {
            "supervised_bc_only": True,
            "is_rl": False,
            "is_ppo_finetuning": False,
            "is_unity_inference_integration": False,
            "is_final_student_architecture": False,
            "proves_transfer_correctness": False,
        },
        "optional_mask_policy": {
            "mask_required": False,
            "mask_used_in_loss": False,
            "missing_mask_implies_all_valid": False,
        },
    }
    metrics_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"\nSaved latest checkpoint: {output_dir / f'{checkpoint_prefix}_latest.pt'}")
    print(f"Saved best checkpoint: {output_dir / f'{checkpoint_prefix}_best.pt'}")
    print(f"Saved metrics history: {metrics_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
