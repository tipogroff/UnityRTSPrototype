from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping

import torch
import torch.nn.functional as F
from torch import Tensor


ACTION_TYPE_BRANCH_INDEX: int = 0


@dataclass(frozen=True)
class BranchSpec:
    name: str
    logits_key: str
    target_branch_index: int
    action_type_gate_value: int | None


BRANCH_SPECS: tuple[BranchSpec, ...] = (
    BranchSpec("action_type", "action_type_logits", 0, None),
    BranchSpec("move_dir", "move_dir_logits", 1, 1),
    BranchSpec("harvest_dir", "harvest_dir_logits", 2, 2),
    BranchSpec("return_dir", "return_dir_logits", 3, 3),
    BranchSpec("produce_dir", "produce_dir_logits", 4, 4),
    BranchSpec("produce_unit_type", "produce_unit_type_logits", 5, 4),
    BranchSpec("attack_target_local", "attack_target_local_logits", 6, 5),
)


@dataclass
class BatchLossOutput:
    total_loss: Tensor
    objective_loss_sum: float
    objective_active_count: int
    loss_sum_by_branch: Dict[str, float]
    active_count_by_branch: Dict[str, int]
    correct_count_by_branch: Dict[str, int]


class EpochMetricAccumulator:
    def __init__(self) -> None:
        self.objective_loss_sum: float = 0.0
        self.objective_active_count: int = 0
        self.loss_sum_by_branch: Dict[str, float] = {spec.name: 0.0 for spec in BRANCH_SPECS}
        self.active_count_by_branch: Dict[str, int] = {spec.name: 0 for spec in BRANCH_SPECS}
        self.correct_count_by_branch: Dict[str, int] = {spec.name: 0 for spec in BRANCH_SPECS}

    def update(self, batch: BatchLossOutput) -> None:
        self.objective_loss_sum += batch.objective_loss_sum
        self.objective_active_count += batch.objective_active_count
        for spec in BRANCH_SPECS:
            name = spec.name
            self.loss_sum_by_branch[name] += batch.loss_sum_by_branch[name]
            self.active_count_by_branch[name] += batch.active_count_by_branch[name]
            self.correct_count_by_branch[name] += batch.correct_count_by_branch[name]

    def to_metrics(self, prefix: str) -> Dict[str, float | int]:
        metrics: Dict[str, float | int] = {}

        total_loss = (
            self.objective_loss_sum / self.objective_active_count
            if self.objective_active_count > 0
            else 0.0
        )
        for spec in BRANCH_SPECS:
            name = spec.name
            active_count = self.active_count_by_branch[name]
            loss_value = self.loss_sum_by_branch[name] / active_count if active_count > 0 else 0.0
            acc_value = self.correct_count_by_branch[name] / active_count if active_count > 0 else 0.0

            metrics[f"{prefix}_{name}_loss"] = float(loss_value)
            metrics[f"{prefix}_{name}_accuracy"] = float(acc_value)
            metrics[f"{prefix}_{name}_active_count"] = int(active_count)

        metrics[f"{prefix}_total_loss"] = float(total_loss)
        return metrics


def compute_branchwise_loss(
    logits_by_key: Mapping[str, Tensor],
    target_action_branches: Tensor,
) -> BatchLossOutput:
    """Compute Day 2 branch-wise objective with explicit active/inactive gating.

    - action_type is always active.
    - other branches are active only by action_type target.
    - inactive branches are not penalized.
    - branch with zero actives contributes zero loss and zero active count.
    """
    if target_action_branches.ndim != 3:
        raise ValueError(
            "target_action_branches must be [B, 576, 7], "
            f"got shape={tuple(target_action_branches.shape)}"
        )

    device = target_action_branches.device
    action_type_targets = target_action_branches[..., ACTION_TYPE_BRANCH_INDEX].reshape(-1)

    objective_loss_sum_tensor: Tensor = torch.zeros((), device=device)
    objective_active_count = 0
    loss_sum_by_branch: Dict[str, float] = {}
    active_count_by_branch: Dict[str, int] = {}
    correct_count_by_branch: Dict[str, int] = {}

    for spec in BRANCH_SPECS:
        logits = logits_by_key[spec.logits_key]
        targets = target_action_branches[..., spec.target_branch_index].reshape(-1)
        logits_flat = logits.reshape(-1, logits.shape[-1])

        if spec.action_type_gate_value is None:
            active_mask = torch.ones_like(action_type_targets, dtype=torch.bool)
        else:
            active_mask = action_type_targets == spec.action_type_gate_value

        active_count = int(active_mask.sum().item())
        active_count_by_branch[spec.name] = active_count

        if active_count == 0:
            loss_sum_by_branch[spec.name] = 0.0
            correct_count_by_branch[spec.name] = 0
            continue

        active_logits = logits_flat[active_mask]
        active_targets = targets[active_mask]

        loss_per_item = F.cross_entropy(active_logits, active_targets, reduction="none")
        loss_sum = loss_per_item.sum()

        preds = torch.argmax(active_logits, dim=-1)
        correct = int((preds == active_targets).sum().item())

        objective_loss_sum_tensor = objective_loss_sum_tensor + loss_sum
        objective_active_count += active_count
        loss_sum_by_branch[spec.name] = float(loss_sum.detach().item())
        correct_count_by_branch[spec.name] = correct

    if objective_active_count > 0:
        total_loss = objective_loss_sum_tensor / objective_active_count
    else:
        total_loss = torch.zeros((), device=device)

    return BatchLossOutput(
        total_loss=total_loss,
        objective_loss_sum=float(objective_loss_sum_tensor.detach().item()),
        objective_active_count=int(objective_active_count),
        loss_sum_by_branch=loss_sum_by_branch,
        active_count_by_branch=active_count_by_branch,
        correct_count_by_branch=correct_count_by_branch,
    )
