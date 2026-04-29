#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

import numpy as np
import torch

from scripted_bc_utils import (
    BRANCH_LAYOUT,
    DEFAULT_CHECKPOINT,
    DEFAULT_DATASET,
    DEFAULT_EVAL_REPORT,
    Agent,
    calc_nonnoop_recall,
    load_dataset_npz,
    mask_argmax,
    per_branch_acc,
    utc_now,
    write_json,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate overfit checkpoint on the same minimal dataset.")
    p.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    p.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    p.add_argument("--device", default="cpu")
    p.add_argument("--output", type=Path, default=DEFAULT_EVAL_REPORT)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    data = load_dataset_npz(args.dataset)
    obs = np.asarray(data["obs"], dtype=np.float32)
    actions = np.asarray(data["actions"], dtype=np.int64)
    masks = np.asarray(data["masks"], dtype=np.float32)
    actor_valid = np.asarray(data["actor_valid"], dtype=np.bool_)

    payload = torch.load(args.checkpoint, map_location="cpu")
    obs_shape = tuple(int(v) for v in payload.get("observation_shape", obs.shape[1:4]))
    action_nvec = [int(v) for v in payload.get("action_nvec", [obs_shape[0] * obs_shape[1]] + BRANCH_LAYOUT)]

    device = torch.device("cuda" if torch.cuda.is_available() and args.device.lower() == "cuda" else "cpu")
    agent = Agent(obs_shape, action_nvec).to(device)
    state = payload["model_state_dict"] if isinstance(payload, dict) and "model_state_dict" in payload else payload
    agent.load_state_dict(state)
    agent.eval()

    obs_t = torch.as_tensor(obs, device=device, dtype=torch.float32)
    masks_t = torch.as_tensor(masks, device=device, dtype=torch.float32)
    actions_t = torch.as_tensor(actions, device=device, dtype=torch.long)
    actor_t = torch.as_tensor(actor_valid, device=device, dtype=torch.bool)

    with torch.no_grad():
        split_logits = agent._split_logits(obs_t)

    flat_masks = masks_t[:, :, :, 1:].reshape(-1, int(sum(BRANCH_LAYOUT)))
    mask_splits = torch.split(flat_masks, BRANCH_LAYOUT, dim=1)
    gt = actions_t.reshape(-1, 7)
    active = actor_t.reshape(-1).detach().cpu().numpy().astype(bool)

    preds = []
    for b in range(7):
        preds.append(mask_argmax(split_logits[b], mask_splits[b]))
    pred = torch.stack(preds, dim=1)

    pred_np = pred.detach().cpu().numpy()
    gt_np = gt.detach().cpu().numpy()

    active_count = int(active.sum())
    action_type_acc_active = float((pred_np[active, 0] == gt_np[active, 0]).sum() / max(1, active_count))
    non_noop_recall = float(calc_nonnoop_recall(pred_np[:, 0], gt_np[:, 0], active))

    cond_move = np.logical_and(active, gt_np[:, 0] == 1)
    cond_harvest = np.logical_and(active, gt_np[:, 0] == 2)
    cond_return = np.logical_and(active, gt_np[:, 0] == 3)
    cond_produce = np.logical_and(active, gt_np[:, 0] == 4)
    cond_attack = np.logical_and(active, gt_np[:, 0] == 5)

    branch_start = [1, 7, 11, 15, 19, 23, 30]
    invalid_after_argmax = 0
    flat_mask79 = masks_t.reshape(-1, 79).detach().cpu().numpy()

    for idx in np.where(active)[0]:
        at = int(pred_np[idx, 0])
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
        for b in checks:
            pos = int(branch_start[b] + int(pred_np[idx, b]))
            if pos < 0 or pos >= 79 or flat_mask79[idx, pos] <= 0:
                invalid_after_argmax += 1
                break

    result: Dict[str, Any] = {
        "schema": "week5_gridnet_overfit_eval.v1",
        "generated_at_utc": utc_now(),
        "dataset": str(args.dataset),
        "checkpoint": str(args.checkpoint),
        "metrics": {
            "action_type_acc_active": float(action_type_acc_active),
            "non_noop_recall": float(non_noop_recall),
            "move_dir_acc_given_move": per_branch_acc(pred_np[:, 1], gt_np[:, 1], cond_move),
            "harvest_dir_acc_given_harvest": per_branch_acc(pred_np[:, 2], gt_np[:, 2], cond_harvest),
            "return_dir_acc_given_return": per_branch_acc(pred_np[:, 3], gt_np[:, 3], cond_return),
            "produce_dir_acc_given_produce": per_branch_acc(pred_np[:, 4], gt_np[:, 4], cond_produce),
            "produce_type_acc_given_produce": per_branch_acc(pred_np[:, 5], gt_np[:, 5], cond_produce),
            "attack_target_acc_given_attack": per_branch_acc(pred_np[:, 6], gt_np[:, 6], cond_attack),
            "invalid_after_argmax": int(invalid_after_argmax),
            "deterministic_noop_share_on_actor_cells": float((pred_np[active, 0] == 0).sum() / max(1, active_count)),
            "active_actor_cells": int(active_count),
        },
    }

    write_json(args.output, result)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
