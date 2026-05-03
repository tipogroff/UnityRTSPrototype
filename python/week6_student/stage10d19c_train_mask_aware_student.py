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
    DEFAULT_TRUE_RAW_CAPTURE,
    evaluate_action_type_subset,
    load_model_strict,
    load_true_raw_capture_tensor,
    run_model_action_type_probs,
    summarize_true_raw_predictions,
    utc_dir_stamp,
    utc_now_iso,
    write_json,
)
from stage10d19b_common import (
    ACTION_TYPE_MOVE,
    ACTION_TYPE_NOOP,
    OWNER_SELF_INDEX,
    UNIT_TYPE_SLICE,
    get_observations_and_actions,
    load_json,
    load_split_payload,
    read_jsonl,
    resolve_path,
)
from stage10d8_train_student_bc_semantic import create_loader, run_epoch, set_seed
from student_architecture_transfer import build_day3_student_model
from student_branch_contract import validate_student_branch_contract_consistency


@dataclass(frozen=True)
class Stage10D19CTrainConfig:
    bc_ready_dir: str
    run_dir: str
    init_checkpoint: str
    epochs: int
    batch_size: int
    learning_rate: float
    device: str
    seed: int
    gradient_clip_norm: float
    actor_cell_loss_weight: float
    patience: int


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.19C supervised mask-aware BC fine-tuning")
    p.add_argument("--bc-ready-dir", type=Path, required=True)
    p.add_argument("--run-dir", type=Path, default=None)
    p.add_argument(
        "--init-checkpoint",
        type=Path,
        default=Path(
            "python/week6_student/runs/legacy032_v2_stage10d19b_valid_move_augmented_bc_20260503T192454Z/student_bc_stage10d19b_valid_move_best.pt"
        ),
    )
    p.add_argument(
        "--fallback-init-checkpoint",
        type=Path,
        default=Path(
            "python/week6_student/runs/legacy032_v2_stage10d17_movement_augmented_bc_20260503T164734Z/student_bc_stage10d17_movement_augmented_best.pt"
        ),
    )
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--learning-rate", type=float, default=5e-5)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--seed", type=int, default=1919)
    p.add_argument("--gradient-clip-norm", type=float, default=1.0)
    p.add_argument("--actor-cell-loss-weight", type=float, default=1.0)
    p.add_argument("--patience", type=int, default=2)
    p.add_argument("--max-train-samples", type=int, default=0)
    p.add_argument("--max-val-samples", type=int, default=0)
    p.add_argument("--true-raw-capture", type=Path, default=Path(DEFAULT_TRUE_RAW_CAPTURE))
    return p.parse_args()


def _default_run_dir() -> Path:
    return resolve_path("python/week6_student/runs") / f"legacy032_v2_stage10d19c_mask_aware_failure_augmented_bc_{utc_dir_stamp()}"


def _actor_mask(obs_rows: np.ndarray) -> np.ndarray:
    return np.asarray((obs_rows[:, :, OWNER_SELF_INDEX] > 0.5) & (np.sum(obs_rows[:, :, UNIT_TYPE_SLICE], axis=2) > 0.5), dtype=bool)


def _predict_action_and_move(model: nn.Module, obs: np.ndarray, device: torch.device, batch_size: int) -> tuple[np.ndarray, np.ndarray]:
    acts: List[np.ndarray] = []
    dirs: List[np.ndarray] = []
    o = np.asarray(obs, dtype=np.float32)
    if o.ndim == 3 and o.shape[1:] == (576, 27):
        o = o.reshape((-1, 24, 24, 27))
    with torch.no_grad():
        for s in range(0, o.shape[0], batch_size):
            e = min(s + batch_size, o.shape[0])
            x = torch.from_numpy(o[s:e]).to(device=device, dtype=torch.float32)
            out = model(x)
            acts.append(torch.argmax(out["action_type_logits"], dim=-1).cpu().numpy())
            dirs.append(torch.argmax(out["move_dir_logits"], dim=-1).cpu().numpy())
    return np.concatenate(acts, axis=0), np.concatenate(dirs, axis=0)


def _eval_failure_subset(
    model: nn.Module,
    observations: np.ndarray,
    actions: np.ndarray,
    metadata_rows: Sequence[Mapping[str, Any]],
    *,
    original_count: int,
    device: torch.device,
    batch_size: int,
) -> Dict[str, Any]:
    if not metadata_rows:
        return {
            "valid_alt_move_recall": 0.0,
            "no_valid_alt_noop_accuracy": 0.0,
            "off_actor_noop_accuracy": 0.0,
            "occupied_failure_case_accuracy": 0.0,
            "predicted_occupied_or_invalid_target_moves": 0,
            "off_actor_non_noop_count": 0,
        }

    idx = np.arange(original_count, original_count + len(metadata_rows), dtype=np.int64)
    obs = np.asarray(observations[idx], dtype=np.float32)
    act = np.asarray(actions[idx], dtype=np.int64)

    pred_a, pred_d = _predict_action_and_move(model, obs, device, batch_size)
    actor = _actor_mask(obs)

    valid_alt_total = 0
    valid_alt_hit = 0
    no_valid_total = 0
    no_valid_hit = 0
    off_total = 0
    off_hit = 0
    occupied_total = 0
    occupied_hit = 0
    invalid_target_moves = 0

    for i, row in enumerate(metadata_rows):
        src = int(row.get("source_cell", -1))
        if src < 0:
            continue
        fam = str(row.get("augmentation_family", ""))
        pa = int(pred_a[i, src])

        if fam == "family_b_valid_alt_move":
            valid_alt_total += 1
            if pa == ACTION_TYPE_MOVE and int(pred_d[i, src]) == int(act[i, src, 1]):
                valid_alt_hit += 1
            occupied_total += 1
            if pa in (ACTION_TYPE_NOOP, ACTION_TYPE_MOVE):
                occupied_hit += 1

        if fam == "family_a_no_valid_alt_noop":
            no_valid_total += 1
            if pa == ACTION_TYPE_NOOP:
                no_valid_hit += 1
            occupied_total += 1
            if pa == ACTION_TYPE_NOOP:
                occupied_hit += 1

        if fam == "family_c_blocked_dir_hard_negative":
            occupied_total += 1
            if pa == ACTION_TYPE_NOOP:
                occupied_hit += 1

        if fam == "family_d_off_actor_hard_negative":
            off_total += 1
            if pa == ACTION_TYPE_NOOP:
                off_hit += 1

        if pa == ACTION_TYPE_MOVE:
            # conservative invalid estimate: out of branch range treated as invalid.
            if int(pred_d[i, src]) not in (0, 1, 2, 3):
                invalid_target_moves += 1

    off_actor_non_noop = int(np.sum(pred_a[~actor] != ACTION_TYPE_NOOP))

    return {
        "valid_alt_move_recall": float(valid_alt_hit / max(1, valid_alt_total)),
        "no_valid_alt_noop_accuracy": float(no_valid_hit / max(1, no_valid_total)),
        "off_actor_noop_accuracy": float(off_hit / max(1, off_total)),
        "occupied_failure_case_accuracy": float(occupied_hit / max(1, occupied_total)),
        "predicted_occupied_or_invalid_target_moves": int(invalid_target_moves),
        "off_actor_non_noop_count": int(off_actor_non_noop),
    }


def _selection_score(m: Mapping[str, Any]) -> tuple[float, ...]:
    return (
        1.0 if bool(m.get("b2_guard_ok", False)) else 0.0,
        1.0 if bool(m.get("c3_guard_ok", False)) else 0.0,
        float(m.get("orig_actor_acc", 0.0)),
        float(m.get("orig_worker_harvest_recall", 0.0)),
        float(m.get("orig_base_produce_recall", 0.0)),
        float(m.get("failure_valid_alt_move_recall", 0.0)),
        float(m.get("failure_no_valid_alt_noop_accuracy", 0.0)),
        float(m.get("failure_off_actor_noop_accuracy", 0.0)),
        float(m.get("failure_occupied_accuracy", 0.0)),
        -float(m.get("failure_off_actor_non_noop", 1e9)),
        -float(m.get("val_total_loss", 1e9)),
    )


def main() -> int:
    args = parse_args()
    set_seed(int(args.seed))
    validate_student_branch_contract_consistency()

    bc_dir = resolve_path(args.bc_ready_dir).resolve()
    run_dir = resolve_path(args.run_dir).resolve() if args.run_dir is not None else _default_run_dir().resolve()
    init_ckpt = resolve_path(args.init_checkpoint).resolve()
    if not init_ckpt.exists():
        init_ckpt = resolve_path(args.fallback_init_checkpoint).resolve()

    if run_dir.exists():
        raise RuntimeError(f"Refusing overwrite: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    cfg = Stage10D19CTrainConfig(
        bc_ready_dir=str(bc_dir),
        run_dir=str(run_dir),
        init_checkpoint=str(init_ckpt),
        epochs=int(args.epochs),
        batch_size=int(args.batch_size),
        learning_rate=float(args.learning_rate),
        device=str(args.device),
        seed=int(args.seed),
        gradient_clip_norm=float(args.gradient_clip_norm),
        actor_cell_loss_weight=float(args.actor_cell_loss_weight),
        patience=int(args.patience),
    )

    train_payload = load_split_payload(bc_dir / "bc_train.npz")
    val_payload = load_split_payload(bc_dir / "bc_validation.npz")
    train_obs, train_actions = get_observations_and_actions(train_payload)
    val_obs, val_actions = get_observations_and_actions(val_payload)

    if int(args.max_train_samples) > 0 and train_obs.shape[0] > int(args.max_train_samples):
        pick = np.random.default_rng(cfg.seed).choice(train_obs.shape[0], size=int(args.max_train_samples), replace=False)
        train_obs = train_obs[pick]
        train_actions = train_actions[pick]
    if int(args.max_val_samples) > 0 and val_obs.shape[0] > int(args.max_val_samples):
        pick = np.random.default_rng(cfg.seed + 1).choice(val_obs.shape[0], size=int(args.max_val_samples), replace=False)
        val_obs = val_obs[pick]
        val_actions = val_actions[pick]

    manifest = load_json(bc_dir / "stage10d19c_mask_aware_failure_augmentation_manifest.json")
    orig_val_n = int(manifest["counts"]["original_validation"])
    meta_val = read_jsonl(bc_dir / "stage10d19c_augmented_sample_metadata_validation.jsonl")

    train_loader = create_loader(
        type("Split", (), {"input_tensor": train_obs.reshape((-1, 24, 24, 27)), "target_action_branches": train_actions})(),
        batch_size=cfg.batch_size,
        shuffle=True,
        seed=cfg.seed,
    )
    val_loader = create_loader(
        type("Split", (), {"input_tensor": val_obs.reshape((-1, 24, 24, 27)), "target_action_branches": val_actions})(),
        batch_size=cfg.batch_size,
        shuffle=False,
        seed=cfg.seed,
    )

    device = torch.device(cfg.device)
    model = build_day3_student_model().to(device=device)
    model = load_model_strict(init_ckpt, device=device)
    optimizer = Adam(model.parameters(), lr=cfg.learning_rate)

    true_raw = load_true_raw_capture_tensor(args.true_raw_capture)

    write_json(
        run_dir / "training_config.json",
        {
            "stage": "10D.19C",
            "config": asdict(cfg),
            "explicit_non_claims": [
                "supervised BC only",
                "no PPO",
                "no teacher mutation",
                "no runtime semantics changes",
                "no Unity rerun in this stage",
            ],
        },
    )

    history: List[Dict[str, Any]] = []
    ckpts: Dict[int, Path] = {}
    best_score: tuple[float, ...] | None = None
    best_epoch = -1
    no_improve = 0

    for epoch in range(1, cfg.epochs + 1):
        t0 = time.perf_counter()
        tr = run_epoch(
            model=model,
            loader=train_loader,
            device=device,
            optimizer=optimizer,
            actor_cell_loss_weight=cfg.actor_cell_loss_weight,
            gradient_clip_norm=cfg.gradient_clip_norm,
        )
        va = run_epoch(
            model=model,
            loader=val_loader,
            device=device,
            optimizer=None,
            actor_cell_loss_weight=cfg.actor_cell_loss_weight,
            gradient_clip_norm=cfg.gradient_clip_norm,
        )

        orig_eval = evaluate_action_type_subset(
            model,
            val_obs.reshape((-1, 24, 24, 27)),
            val_actions,
            indices=np.arange(orig_val_n, dtype=np.int64),
            device=device,
            batch_size=cfg.batch_size,
        )
        fail_eval = _eval_failure_subset(
            model,
            val_obs,
            val_actions,
            meta_val,
            original_count=orig_val_n,
            device=device,
            batch_size=cfg.batch_size,
        )

        probs = run_model_action_type_probs(model, true_raw, device)
        true_raw_summary = summarize_true_raw_predictions(probs, true_raw)

        b2_guard_ok = bool(float(true_raw_summary["B2"]["p_harvest"]) > float(true_raw_summary["B2"]["p_noop"]))
        c3_guard_ok = bool(float(true_raw_summary["C3"]["p_produce"]) > float(true_raw_summary["C3"]["p_noop"]))

        row = {
            "epoch": int(epoch),
            "train_total_loss": float(tr["train_total_loss"]),
            "val_total_loss": float(va["val_total_loss"]),
            "orig_actor_acc": float(orig_eval["actor_cell_action_type_accuracy"]),
            "orig_worker_harvest_recall": float(orig_eval["worker_harvest_recall"]),
            "orig_base_produce_recall": float(orig_eval["base_produce_recall"]),
            "failure_valid_alt_move_recall": float(fail_eval["valid_alt_move_recall"]),
            "failure_no_valid_alt_noop_accuracy": float(fail_eval["no_valid_alt_noop_accuracy"]),
            "failure_off_actor_noop_accuracy": float(fail_eval["off_actor_noop_accuracy"]),
            "failure_occupied_accuracy": float(fail_eval["occupied_failure_case_accuracy"]),
            "failure_off_actor_non_noop": int(fail_eval["off_actor_non_noop_count"]),
            "b2_guard_ok": bool(b2_guard_ok),
            "c3_guard_ok": bool(c3_guard_ok),
            "elapsed_sec": float(time.perf_counter() - t0),
        }
        row["selection_score"] = list(_selection_score(row))

        ckpt_path = run_dir / f"student_bc_stage10d19c_mask_aware_epoch_{epoch:03d}.pt"
        torch.save(
            {
                "stage": "10D.19C",
                "epoch": int(epoch),
                "model_state_dict": model.state_dict(),
                "metrics": row,
            },
            ckpt_path,
        )
        ckpts[epoch] = ckpt_path

        score = _selection_score(row)
        if (best_score is None) or (score > best_score):
            best_score = score
            best_epoch = epoch
            no_improve = 0
        else:
            no_improve += 1

        history.append(row)
        if no_improve >= cfg.patience:
            break

    if best_epoch < 0:
        raise RuntimeError("No training epoch produced a checkpoint")

    best_src = ckpts[best_epoch]
    best_dst = run_dir / "student_bc_stage10d19c_mask_aware_best.pt"
    final_dst = run_dir / "student_bc_stage10d19c_mask_aware_final.pt"

    best_dst.write_bytes(best_src.read_bytes())
    final_dst.write_bytes(ckpts[max(ckpts.keys())].read_bytes())

    write_json(run_dir / "stage10d19c_training_history.json", {"stage": "10D.19C", "history": history})
    write_json(
        run_dir / "stage10d19c_training_selection.json",
        {
            "stage": "10D.19C",
            "generated_at_utc": utc_now_iso(),
            "best_epoch": int(best_epoch),
            "best_checkpoint": str(best_dst.as_posix()),
            "final_checkpoint": str(final_dst.as_posix()),
            "selection_priority": [
                "B2 Harvest preserved",
                "C3 Produce preserved",
                "original validation preserved",
                "worker harvest recall preserved",
                "base produce recall preserved",
                "movement recall preserved",
                "valid Move recall improved",
                "occupied failure-case accuracy improved",
                "off-actor NoOp accuracy improved",
            ],
            "history_rows": len(history),
        },
    )

    print(best_dst.as_posix())
    print(final_dst.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
