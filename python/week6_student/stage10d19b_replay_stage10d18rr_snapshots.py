#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

import numpy as np
import torch

from stage10d14_common import load_model_strict, utc_now_iso, write_json
from stage10d19b_common import (
    ACTION_TYPE_ATTACK,
    ACTION_TYPE_MOVE,
    ACTION_TYPE_NOOP,
    OWNER_SELF_INDEX,
    UNIT_TYPE_SLICE,
    get_observations_and_actions,
    load_json,
    load_split_payload,
    read_jsonl,
    resolve_path,
    target_from_source_and_dir,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.19B replay selected Stage10D.18RR snapshot steps using dataset proxies")
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--augmented-bc-ready-dir", type=Path, required=True)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument(
        "--output-report",
        type=Path,
        default=Path("python/week6_student/reports/stage10d19b_stage10d18rr_snapshot_replay_report.json"),
    )
    return p.parse_args()


def _is_actor_mask(obs_rows: np.ndarray) -> np.ndarray:
    return np.asarray((obs_rows[:, :, OWNER_SELF_INDEX] > 0.5) & (np.sum(obs_rows[:, :, UNIT_TYPE_SLICE], axis=2) > 0.5), dtype=bool)


def _predict_action_and_move_dir(model: torch.nn.Module, obs: np.ndarray, device: torch.device, batch_size: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    model.eval()
    a_list: List[np.ndarray] = []
    d_list: List[np.ndarray] = []
    attack_prob_list: List[np.ndarray] = []
    obs4 = np.asarray(obs, dtype=np.float32)
    if obs4.ndim == 3 and obs4.shape[1:] == (576, 27):
        obs4 = obs4.reshape((-1, 24, 24, 27))
    with torch.no_grad():
        for s in range(0, obs4.shape[0], batch_size):
            e = min(s + batch_size, obs4.shape[0])
            x = torch.from_numpy(obs4[s:e]).to(device=device, dtype=torch.float32)
            out = model(x)
            action_logits = out["action_type_logits"]
            probs = torch.softmax(action_logits, dim=-1)
            a_list.append(torch.argmax(action_logits, dim=-1).cpu().numpy())
            d_list.append(torch.argmax(out["move_dir_logits"], dim=-1).cpu().numpy())
            attack_prob_list.append(probs[..., ACTION_TYPE_ATTACK].cpu().numpy())
    return np.concatenate(a_list, axis=0), np.concatenate(d_list, axis=0), np.concatenate(attack_prob_list, axis=0)


def main() -> int:
    args = parse_args()
    checkpoint = resolve_path(args.checkpoint).resolve()
    bc_dir = resolve_path(args.augmented_bc_ready_dir).resolve()
    device = torch.device(args.device)

    model = load_model_strict(checkpoint, device=device)
    val_payload = load_split_payload(bc_dir / "bc_validation.npz")
    val_obs, val_actions = get_observations_and_actions(val_payload)
    manifest = load_json(bc_dir / "stage10d19b_valid_move_augmentation_manifest.json")
    original_val = int(manifest["counts"]["original_validation"])
    meta_val = read_jsonl(bc_dir / "stage10d19b_augmented_sample_metadata_validation.jsonl")

    out: Dict[str, Any] = {}
    for step in (1, 55, 100, 200):
        selected = [i for i, r in enumerate(meta_val) if int(r.get("source_step", -1)) == step]
        if not selected:
            out[str(step)] = {"present": False, "reason": "no_augmented_rows_for_step"}
            continue

        idx = np.asarray([original_val + i for i in selected], dtype=np.int64)
        obs_sub = np.asarray(val_obs[idx], dtype=np.float32)
        pred_action, pred_dir, attack_prob = _predict_action_and_move_dir(model, obs_sub, device, int(args.batch_size))
        actor = _is_actor_mask(obs_sub)

        valid = 0
        invalid = 0
        b2 = None
        c3 = None
        produced = 0
        for local_i, meta_i in enumerate(selected):
            row = meta_val[meta_i]
            src = int(row.get("source_cell", -1))
            if src < 0:
                continue
            if src == 25:
                b2 = int(pred_action[local_i, src])
            if src == 50:
                c3 = int(pred_action[local_i, src])
            if str(row.get("unit_id", "")).startswith("Worker_") and int(pred_action[local_i, src]) == ACTION_TYPE_MOVE:
                produced += 1
            if int(pred_action[local_i, src]) == ACTION_TYPE_MOVE:
                tgt, in_bounds = target_from_source_and_dir(src, int(pred_dir[local_i, src]))
                if not in_bounds or tgt is None:
                    invalid += 1
                else:
                    if bool(np.sum(obs_sub[local_i, tgt, UNIT_TYPE_SLICE]) > 0.5):
                        invalid += 1
                    else:
                        valid += 1

        out[str(step)] = {
            "present": True,
            "sample_count": int(len(selected)),
            "actor_action_distribution": {
                "NoOp": int(np.sum(pred_action[actor] == ACTION_TYPE_NOOP)),
                "Move": int(np.sum(pred_action[actor] == ACTION_TYPE_MOVE)),
                "Harvest": int(np.sum(pred_action[actor] == 2)),
                "Return": int(np.sum(pred_action[actor] == 3)),
                "Produce": int(np.sum(pred_action[actor] == 4)),
                "Attack": int(np.sum(pred_action[actor] == 5)),
            },
            "move_predictions": int(np.sum(pred_action[actor] == ACTION_TYPE_MOVE)),
            "valid_target_moves": int(valid),
            "occupied_or_invalid_target_moves": int(invalid),
            "off_actor_non_noop": int(np.sum(pred_action[~actor] != ACTION_TYPE_NOOP)),
            "b2_predicted_action": b2,
            "c3_predicted_action": c3,
            "produced_unit_move_predictions": int(produced),
            "max_p_attack_watch": float(np.max(attack_prob)) if attack_prob.size else 0.0,
        }

    valid_sum = sum(int(v.get("valid_target_moves", 0)) for v in out.values() if v.get("present", False))
    invalid_sum = sum(int(v.get("occupied_or_invalid_target_moves", 0)) for v in out.values() if v.get("present", False))
    off_actor_sum = sum(int(v.get("off_actor_non_noop", 0)) for v in out.values() if v.get("present", False))

    labels = ["STAGE10D19B_SNAPSHOT_REPLAY_COMPLETED"]
    labels.append("STAGE10D19B_VALID_MOVE_REPLAY_IMPROVED" if valid_sum >= invalid_sum else "STAGE10D19B_OFF_ACTOR_REPLAY_RISK")
    labels.append("STAGE10D19B_OFF_ACTOR_REPLAY_SAFE" if off_actor_sum <= 20 else "STAGE10D19B_OFF_ACTOR_REPLAY_RISK")

    report = {
        "stage": "10D.19B",
        "task": "stage10d18rr_snapshot_replay",
        "generated_at_utc": utc_now_iso(),
        "checkpoint": str(checkpoint.as_posix()),
        "augmented_bc_ready_dir": str(bc_dir.as_posix()),
        "steps": out,
        "summary": {
            "valid_sum": int(valid_sum),
            "invalid_sum": int(invalid_sum),
            "off_actor_non_noop_sum": int(off_actor_sum),
        },
        "labels": labels,
    }
    write_json(args.output_report, report)
    print(resolve_path(args.output_report).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
