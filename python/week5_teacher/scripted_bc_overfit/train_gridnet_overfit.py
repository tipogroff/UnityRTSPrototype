#!/usr/bin/env python3
from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import torch

from scripted_bc_utils import (
    BRANCH_LAYOUT,
    DEFAULT_CHECKPOINT,
    DEFAULT_DATASET,
    DEFAULT_OUT_DIR,
    DEFAULT_TRAIN_HISTORY,
    Agent,
    branch_loss,
    calc_nonnoop_recall,
    extract_branch_masks,
    load_dataset_npz,
    mask_argmax,
    per_branch_acc,
    utc_now,
    write_json,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Supervised overfit on minimal scripted Gridnet dataset.")
    p.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    p.add_argument("--epochs", type=int, default=200)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--device", default="cpu")
    p.add_argument("--seed", type=int, default=170)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument("--output-checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    p.add_argument("--output-history", type=Path, default=DEFAULT_TRAIN_HISTORY)
    return p.parse_args()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def _to_torch(x: np.ndarray, device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    return torch.as_tensor(x, device=device, dtype=dtype)


def compute_metrics(
    agent: Agent,
    obs_t: torch.Tensor,
    masks_t: torch.Tensor,
    actions_t: torch.Tensor,
    actor_valid_t: torch.Tensor,
) -> Dict[str, Any]:
    with torch.no_grad():
        split_logits = agent._split_logits(obs_t)

    branch_masks = torch.split(masks_t[:, :, :, 1:].reshape(-1, int(sum(BRANCH_LAYOUT))), BRANCH_LAYOUT, dim=1)
    gt = actions_t.reshape(-1, 7)
    active = actor_valid_t.reshape(-1)

    preds: List[torch.Tensor] = []
    for b in range(7):
        pred_b = mask_argmax(split_logits[b], branch_masks[b])
        preds.append(pred_b)
    pred = torch.stack(preds, dim=1)

    gt_np = gt.detach().cpu().numpy()
    pred_np = pred.detach().cpu().numpy()
    active_np = active.detach().cpu().numpy().astype(bool)

    active_count = int(active_np.sum())
    action_type_acc = 0.0
    if active_count > 0:
        action_type_acc = float((pred_np[active_np, 0] == gt_np[active_np, 0]).sum() / active_count)

    non_noop_recall = calc_nonnoop_recall(pred_np[:, 0], gt_np[:, 0], active_np)

    cond_move = np.logical_and(active_np, gt_np[:, 0] == 1)
    cond_harvest = np.logical_and(active_np, gt_np[:, 0] == 2)
    cond_return = np.logical_and(active_np, gt_np[:, 0] == 3)
    cond_produce = np.logical_and(active_np, gt_np[:, 0] == 4)
    cond_attack = np.logical_and(active_np, gt_np[:, 0] == 5)

    invalid_after_argmax = 0
    # Relevant-branch validity check.
    branch_start = [1, 7, 11, 15, 19, 23, 30]
    for idx in np.where(active_np)[0]:
        at = int(pred_np[idx, 0])
        if at < 0 or at > 5:
            invalid_after_argmax += 1
            continue
        checks = [0]
        if at == 1:
            checks.append(1)
        elif at == 2:
            checks.append(2)
        elif at == 3:
            checks.append(3)
        elif at == 4:
            checks.extend([4, 5])
        elif at == 5:
            checks.append(6)

        mask_row = masks_t.reshape(-1, 79)[idx].detach().cpu().numpy()
        for b in checks:
            selected = int(pred_np[idx, b])
            pos = int(branch_start[b] + selected)
            if pos < 0 or pos >= 79 or mask_row[pos] <= 0:
                invalid_after_argmax += 1
                break

    noop_share = 1.0
    if active_count > 0:
        noop_share = float((pred_np[active_np, 0] == 0).sum() / active_count)

    return {
        "action_type_acc_active": float(action_type_acc),
        "non_noop_recall": float(non_noop_recall),
        "move_dir_acc_given_move": per_branch_acc(pred_np[:, 1], gt_np[:, 1], cond_move),
        "harvest_dir_acc_given_harvest": per_branch_acc(pred_np[:, 2], gt_np[:, 2], cond_harvest),
        "return_dir_acc_given_return": per_branch_acc(pred_np[:, 3], gt_np[:, 3], cond_return),
        "produce_dir_acc_given_produce": per_branch_acc(pred_np[:, 4], gt_np[:, 4], cond_produce),
        "produce_type_acc_given_produce": per_branch_acc(pred_np[:, 5], gt_np[:, 5], cond_produce),
        "attack_target_acc_given_attack": per_branch_acc(pred_np[:, 6], gt_np[:, 6], cond_attack),
        "invalid_after_argmax": int(invalid_after_argmax),
        "deterministic_noop_share_on_actor_cells": float(noop_share),
        "active_actor_cells": int(active_count),
    }


def main() -> int:
    args = parse_args()
    set_seed(int(args.seed))

    device = torch.device("cuda" if torch.cuda.is_available() and args.device.lower() == "cuda" else "cpu")
    data = load_dataset_npz(args.dataset)

    obs = np.asarray(data["obs"], dtype=np.float32)
    actions = np.asarray(data["actions"], dtype=np.int64)
    masks = np.asarray(data["masks"], dtype=np.float32)
    actor_valid = np.asarray(data["actor_valid"], dtype=np.bool_)

    if obs.ndim != 4 or actions.ndim != 4 or masks.ndim != 4 or actor_valid.ndim != 3:
        raise RuntimeError("Dataset shape mismatch; expected obs/actions/masks 4D and actor_valid 3D.")

    n, h, w, c = obs.shape
    action_nvec = [h * w] + BRANCH_LAYOUT

    agent = Agent((h, w, c), action_nvec).to(device)
    optimizer = torch.optim.Adam(agent.parameters(), lr=float(args.lr))

    obs_t = _to_torch(obs, device=device, dtype=torch.float32)
    actions_t = _to_torch(actions, device=device, dtype=torch.long)
    masks_t = _to_torch(masks, device=device, dtype=torch.float32)
    actor_valid_t = _to_torch(actor_valid.astype(np.float32), device=device, dtype=torch.float32) > 0.5

    class_weights = torch.as_tensor([0.2, 1.0, 2.0, 2.0, 3.0, 3.0], device=device, dtype=torch.float32)

    history: List[Dict[str, Any]] = []
    indices = np.arange(n)

    for epoch in range(1, int(args.epochs) + 1):
        np.random.shuffle(indices)
        epoch_loss = 0.0
        epoch_steps = 0
        branch_loss_sums = {
            "action_type": 0.0,
            "move_dir": 0.0,
            "harvest_dir": 0.0,
            "return_dir": 0.0,
            "produce_dir": 0.0,
            "produce_type": 0.0,
            "attack_target": 0.0,
        }

        for start in range(0, n, int(args.batch_size)):
            batch_idx = indices[start : start + int(args.batch_size)]
            b_obs = obs_t[batch_idx]
            b_actions = actions_t[batch_idx]
            b_masks = masks_t[batch_idx]
            b_active = actor_valid_t[batch_idx]

            split_logits = agent._split_logits(b_obs)
            split_masks = extract_branch_masks(b_masks.detach().cpu().numpy())
            split_masks_t = [
                torch.as_tensor(m.reshape(-1, m.shape[-1]), device=device, dtype=torch.float32)
                for m in split_masks
            ]
            gt = b_actions.reshape(-1, 7)
            active = b_active.reshape(-1)

            gt_type = gt[:, 0]
            cond_move = torch.logical_and(active, gt_type == 1)
            cond_harvest = torch.logical_and(active, gt_type == 2)
            cond_return = torch.logical_and(active, gt_type == 3)
            cond_produce = torch.logical_and(active, gt_type == 4)
            cond_attack = torch.logical_and(active, gt_type == 5)

            l_action_type = branch_loss(split_logits[0], gt[:, 0], split_masks_t[0], active, class_weights=class_weights)
            l_move = branch_loss(split_logits[1], gt[:, 1], split_masks_t[1], cond_move)
            l_harvest = branch_loss(split_logits[2], gt[:, 2], split_masks_t[2], cond_harvest)
            l_return = branch_loss(split_logits[3], gt[:, 3], split_masks_t[3], cond_return)
            l_produce_dir = branch_loss(split_logits[4], gt[:, 4], split_masks_t[4], cond_produce)
            l_produce_type = branch_loss(split_logits[5], gt[:, 5], split_masks_t[5], cond_produce)
            l_attack = branch_loss(split_logits[6], gt[:, 6], split_masks_t[6], cond_attack)

            total_loss = l_action_type + l_move + l_harvest + l_return + l_produce_dir + l_produce_type + l_attack

            optimizer.zero_grad(set_to_none=True)
            total_loss.backward()
            optimizer.step()

            epoch_loss += float(total_loss.detach().cpu().item())
            epoch_steps += 1
            branch_loss_sums["action_type"] += float(l_action_type.detach().cpu().item())
            branch_loss_sums["move_dir"] += float(l_move.detach().cpu().item())
            branch_loss_sums["harvest_dir"] += float(l_harvest.detach().cpu().item())
            branch_loss_sums["return_dir"] += float(l_return.detach().cpu().item())
            branch_loss_sums["produce_dir"] += float(l_produce_dir.detach().cpu().item())
            branch_loss_sums["produce_type"] += float(l_produce_type.detach().cpu().item())
            branch_loss_sums["attack_target"] += float(l_attack.detach().cpu().item())

        metrics = compute_metrics(agent, obs_t, masks_t, actions_t, actor_valid_t)
        record = {
            "epoch": int(epoch),
            "total_loss": float(epoch_loss / max(1, epoch_steps)),
            "branch_losses": {k: float(v / max(1, epoch_steps)) for k, v in branch_loss_sums.items()},
            **metrics,
        }
        history.append(record)

    args.output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "schema": "week5_gridnet_overfit_checkpoint.v1",
            "saved_at_utc": utc_now(),
            "model_state_dict": agent.state_dict(),
            "observation_shape": [int(h), int(w), int(c)],
            "action_nvec": [int(v) for v in action_nvec],
            "branch_layout": [int(v) for v in BRANCH_LAYOUT],
            "dataset": str(args.dataset),
            "seed": int(args.seed),
        },
        args.output_checkpoint,
    )

    history_payload = {
        "schema": "week5_gridnet_overfit_train_history.v1",
        "generated_at_utc": utc_now(),
        "dataset": str(args.dataset),
        "checkpoint": str(args.output_checkpoint),
        "epochs": int(args.epochs),
        "batch_size": int(args.batch_size),
        "lr": float(args.lr),
        "device": str(device),
        "history": history,
        "final": history[-1] if history else {},
    }
    write_json(args.output_history, history_payload)

    print(args.output_checkpoint)
    print(args.output_history)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
