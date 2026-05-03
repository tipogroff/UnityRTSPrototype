#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Mapping

import numpy as np
import torch

from stage10d19b_common import get_observations_and_actions, load_split_payload, read_jsonl
from stage10d19m_common import (
    ACTION_TYPE_ATTACK,
    ACTION_TYPE_MOVE,
    ACTION_TYPE_NAMES,
    ACTION_TYPE_NOOP,
    N_CELLS,
    OBS_OWNER_SELF_INDEX,
    OBS_UNIT_SLICE,
    StepMaskBundle,
    actor_mask_from_obs,
    apply_masked_selection_for_cell,
    attack_index_to_offset,
    flat_to_xy,
    in_bounds,
    load_checkpoint_model,
    model_forward_logits,
    move_target,
    utc_now_iso,
    write_json,
    xy_to_flat,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.19M masked-vs-unmasked selection probe")
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--augmented-bc-ready-dir", type=Path, required=True)
    p.add_argument("--mask-build-json", action="append", required=True)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--checkpoint-tag", type=str, default="checkpoint")
    p.add_argument(
        "--output-report",
        type=Path,
        default=Path("python/week6_student/reports/stage10d19m_masked_selection_probe_checkpoint.json"),
    )
    return p.parse_args()


def _softmax(x: np.ndarray) -> np.ndarray:
    z = x - np.max(x)
    e = np.exp(z)
    return e / np.maximum(np.sum(e), 1e-12)


def _is_enemy(obs_flat: np.ndarray, flat: int) -> bool:
    owner_enemy = bool(float(obs_flat[flat, 4]) > 0.5)
    has_unit = bool(float(np.sum(obs_flat[flat, OBS_UNIT_SLICE])) > 1e-6)
    return owner_enemy and has_unit


def _is_move_valid(obs_flat: np.ndarray, src: int, move_dir: int) -> bool:
    tgt, ok = move_target(src, int(move_dir))
    if (not ok) or tgt is None:
        return False
    return bool(float(np.sum(obs_flat[tgt, OBS_UNIT_SLICE])) <= 1e-6)


def _is_attack_valid(obs_flat: np.ndarray, src: int, local_idx: int) -> bool:
    x, y = flat_to_xy(src)
    dx, dy = attack_index_to_offset(int(local_idx))
    tx, ty = x + dx, y + dy
    if not in_bounds(tx, ty):
        return False
    return _is_enemy(obs_flat, xy_to_flat(tx, ty))


def _load_masks(paths: List[str]) -> Dict[int, StepMaskBundle]:
    out: Dict[int, StepMaskBundle] = {}
    for p in paths:
        payload = __import__("json").loads(Path(p).read_text(encoding="utf-8"))
        step = int(payload.get("step", 0))
        out[step] = StepMaskBundle(
            step=step,
            action_type_mask=np.asarray(payload["action_type_mask"], dtype=bool),
            move_dir_mask=np.asarray(payload["move_dir_mask"], dtype=bool),
            harvest_dir_mask=np.asarray(payload["harvest_dir_mask"], dtype=bool),
            return_dir_mask=np.asarray(payload["return_dir_mask"], dtype=bool),
            produce_dir_mask=np.asarray(payload["produce_dir_mask"], dtype=bool),
            produce_unit_type_mask=np.asarray(payload["produce_unit_type_mask"], dtype=bool),
            attack_target_local_mask=np.asarray(payload["attack_target_local_mask"], dtype=bool),
            approximation_notes=list(payload.get("approximation_notes", [])),
        )
    return out


def main() -> int:
    args = parse_args()
    device = torch.device(args.device)

    masks_by_step = _load_masks(list(args.mask_build_json))
    selected_steps = sorted(masks_by_step.keys())

    bc_dir = Path(args.augmented_bc_ready_dir)
    val_payload = load_split_payload(bc_dir / "bc_validation.npz")
    val_obs, _ = get_observations_and_actions(val_payload)
    meta_val = read_jsonl(bc_dir / "stage10d19b_augmented_sample_metadata_validation.jsonl")
    manifest = __import__("json").loads((bc_dir / "stage10d19b_valid_move_augmentation_manifest.json").read_text(encoding="utf-8"))
    original_val = int(manifest["counts"]["original_validation"])

    selected_meta_idx = [
        i for i, r in enumerate(meta_val) if int(r.get("source_step", -1)) in set(selected_steps)
    ]
    if not selected_meta_idx:
        raise RuntimeError("No validation metadata rows matched selected mask steps")

    sample_indices = np.asarray([original_val + i for i in selected_meta_idx], dtype=np.int64)
    obs_flat = np.asarray(val_obs[sample_indices], dtype=np.float32)
    obs_map = obs_flat.reshape((-1, 24, 24, 27))

    model = load_checkpoint_model(args.checkpoint, device=device)
    logits = model_forward_logits(model, obs_map, device=device, batch_size=int(args.batch_size))

    unmasked = {
        "action_type": np.argmax(logits["action_type_logits"], axis=-1).astype(np.int64),
        "move_dir": np.argmax(logits["move_dir_logits"], axis=-1).astype(np.int64),
        "harvest_dir": np.argmax(logits["harvest_dir_logits"], axis=-1).astype(np.int64),
        "return_dir": np.argmax(logits["return_dir_logits"], axis=-1).astype(np.int64),
        "produce_dir": np.argmax(logits["produce_dir_logits"], axis=-1).astype(np.int64),
        "produce_unit_type": np.argmax(logits["produce_unit_type_logits"], axis=-1).astype(np.int64),
        "attack_target_local": np.argmax(logits["attack_target_local_logits"], axis=-1).astype(np.int64),
    }

    n = obs_flat.shape[0]
    masked = {
        "action_type": np.zeros((n, N_CELLS), dtype=np.int64),
        "move_dir": np.zeros((n, N_CELLS), dtype=np.int64),
        "harvest_dir": np.zeros((n, N_CELLS), dtype=np.int64),
        "return_dir": np.zeros((n, N_CELLS), dtype=np.int64),
        "produce_dir": np.zeros((n, N_CELLS), dtype=np.int64),
        "produce_unit_type": np.zeros((n, N_CELLS), dtype=np.int64),
        "attack_target_local": np.zeros((n, N_CELLS), dtype=np.int64),
    }

    changed_total = 0
    changed_breakdown = Counter()

    for i, meta_i in enumerate(selected_meta_idx):
        row = meta_val[meta_i]
        step = int(row.get("source_step", -1))
        bundle = masks_by_step[step]
        obs_i = obs_flat[i]
        actor_i = actor_mask_from_obs(obs_flat[i : i + 1])[0]

        for flat in range(N_CELLS):
            pred = apply_masked_selection_for_cell(
                {
                    "action_type_logits": logits["action_type_logits"][i, flat],
                    "move_dir_logits": logits["move_dir_logits"][i, flat],
                    "harvest_dir_logits": logits["harvest_dir_logits"][i, flat],
                    "return_dir_logits": logits["return_dir_logits"][i, flat],
                    "produce_dir_logits": logits["produce_dir_logits"][i, flat],
                    "produce_unit_type_logits": logits["produce_unit_type_logits"][i, flat],
                    "attack_target_local_logits": logits["attack_target_local_logits"][i, flat],
                },
                bundle,
                flat,
            )
            for k in masked:
                masked[k][i, flat] = int(pred[k])

            u_act = int(unmasked["action_type"][i, flat])
            m_act = int(masked["action_type"][i, flat])
            if u_act != m_act:
                changed_total += 1
                if (not actor_i[flat]) and (u_act != ACTION_TYPE_NOOP) and (m_act == ACTION_TYPE_NOOP):
                    changed_breakdown["off-actor non-NoOp -> NoOp"] += 1
                elif u_act == ACTION_TYPE_MOVE:
                    u_valid = _is_move_valid(obs_i, flat, int(unmasked["move_dir"][i, flat]))
                    m_valid = _is_move_valid(obs_i, flat, int(masked["move_dir"][i, flat])) if m_act == ACTION_TYPE_MOVE else False
                    if (not u_valid) and (m_act == ACTION_TYPE_NOOP):
                        changed_breakdown["invalid Move -> NoOp"] += 1
                    elif (not u_valid) and (m_act == ACTION_TYPE_MOVE) and m_valid:
                        changed_breakdown["invalid Move -> valid Move"] += 1
                    else:
                        changed_breakdown["other"] += 1
                elif u_act == ACTION_TYPE_ATTACK:
                    u_valid = _is_attack_valid(obs_i, flat, int(unmasked["attack_target_local"][i, flat]))
                    if (not u_valid) and (m_act == ACTION_TYPE_NOOP):
                        changed_breakdown["invalid Attack -> NoOp"] += 1
                    else:
                        changed_breakdown["other"] += 1
                else:
                    changed_breakdown["other"] += 1

    actor_mask = actor_mask_from_obs(obs_flat)

    def _dist(action_pred: np.ndarray) -> Dict[str, int]:
        c = Counter(int(v) for v in action_pred[actor_mask].reshape(-1))
        return {ACTION_TYPE_NAMES[i]: int(c.get(i, 0)) for i in range(6)}

    unmasked_action_distribution = _dist(unmasked["action_type"])
    masked_action_distribution = _dist(masked["action_type"])

    unmasked_off_actor_non_noop = int(np.sum(unmasked["action_type"][~actor_mask] != ACTION_TYPE_NOOP))
    masked_off_actor_non_noop = int(np.sum(masked["action_type"][~actor_mask] != ACTION_TYPE_NOOP))

    unmasked_move_predictions = 0
    masked_move_predictions = 0
    unmasked_valid_moves = 0
    masked_valid_moves = 0
    unmasked_invalid_moves = 0
    masked_invalid_moves = 0
    unmasked_attack_predictions = 0
    masked_attack_predictions = 0
    masked_attack_valid_targets = 0

    produced_masked_action_dist = Counter()

    for i, meta_i in enumerate(selected_meta_idx):
        row = meta_val[meta_i]
        src = int(row.get("source_cell", -1))
        if src < 0:
            continue

        u_act = int(unmasked["action_type"][i, src])
        m_act = int(masked["action_type"][i, src])

        if str(row.get("unit_id", "")).startswith("Worker_"):
            produced_masked_action_dist[ACTION_TYPE_NAMES[m_act]] += 1

        if u_act == ACTION_TYPE_MOVE:
            unmasked_move_predictions += 1
            if _is_move_valid(obs_flat[i], src, int(unmasked["move_dir"][i, src])):
                unmasked_valid_moves += 1
            else:
                unmasked_invalid_moves += 1
        if m_act == ACTION_TYPE_MOVE:
            masked_move_predictions += 1
            if _is_move_valid(obs_flat[i], src, int(masked["move_dir"][i, src])):
                masked_valid_moves += 1
            else:
                masked_invalid_moves += 1

        if u_act == ACTION_TYPE_ATTACK:
            unmasked_attack_predictions += 1
        if m_act == ACTION_TYPE_ATTACK:
            masked_attack_predictions += 1
            if _is_attack_valid(obs_flat[i], src, int(masked["attack_target_local"][i, src])):
                masked_attack_valid_targets += 1

    # B2/C3 reference from first selected sample.
    ref_i = 0
    b2_probs = _softmax(np.asarray(logits["action_type_logits"][ref_i, 25], dtype=np.float32))
    c3_probs = _softmax(np.asarray(logits["action_type_logits"][ref_i, 50], dtype=np.float32))

    b2_u = int(unmasked["action_type"][ref_i, 25])
    b2_m = int(masked["action_type"][ref_i, 25])
    c3_u = int(unmasked["action_type"][ref_i, 50])
    c3_m = int(masked["action_type"][ref_i, 50])

    b2_c3_preserved = bool((b2_m == b2_u) and (c3_m == c3_u) and (b2_m != ACTION_TYPE_NOOP) and (c3_m != ACTION_TYPE_NOOP))

    movement_suppressed = bool(masked_move_predictions == 0 and unmasked_move_predictions > 0)
    movement_preserved = bool((not movement_suppressed) and (masked_move_predictions >= max(1, int(0.25 * max(1, unmasked_move_predictions)))))

    reduced_invalid_moves = bool(masked_invalid_moves < unmasked_invalid_moves)
    reduced_off_actor = bool(masked_off_actor_non_noop < unmasked_off_actor_non_noop)

    ready_for_toggle_probe = bool(
        reduced_invalid_moves and reduced_off_actor and b2_c3_preserved and movement_preserved
    )

    labels = [
        "STAGE10D19M_MASKED_SELECTION_PROBE_COMPLETED",
        "STAGE10D19M_MASK_REDUCES_INVALID_MOVES" if reduced_invalid_moves else "STAGE10D19M_MASK_NOT_READY",
        "STAGE10D19M_MASK_REDUCES_OFF_ACTOR_NONNOOP" if reduced_off_actor else "STAGE10D19M_MASK_NOT_READY",
        "STAGE10D19M_MASK_PRESERVES_B2_C3_GUARDS" if b2_c3_preserved else "STAGE10D19M_MASK_NOT_READY",
        "STAGE10D19M_MASK_PRESERVES_MOVEMENT" if movement_preserved else "STAGE10D19M_MASK_SUPPRESSES_ALL_MOVEMENT",
        "STAGE10D19M_MASK_ATTACK_STILL_ABSENT" if masked_attack_predictions == 0 else "STAGE10D19M_MASK_ATTACK_ENABLED_WHEN_VALID",
        "STAGE10D19M_MASK_READY_FOR_UNITY_TOGGLE_PROBE" if ready_for_toggle_probe else "STAGE10D19M_MASK_NOT_READY",
    ]

    report = {
        "stage": "10D.19M",
        "task": "masked_selection_probe",
        "generated_at_utc": utc_now_iso(),
        "checkpoint": str(Path(args.checkpoint).as_posix()),
        "checkpoint_tag": args.checkpoint_tag,
        "augmented_bc_ready_dir": str(bc_dir.as_posix()),
        "selected_source_steps": selected_steps,
        "sample_count": int(len(selected_meta_idx)),
        "evidence_note": "Probe uses Stage10D19B validation rows derived from Stage10D18RR replay sources. Steps with missing full raw runtime state are evaluated via this preserved proxy subset.",
        "unmasked_action_distribution": unmasked_action_distribution,
        "masked_action_distribution": masked_action_distribution,
        "unmasked_off_actor_non_noop_count": int(unmasked_off_actor_non_noop),
        "masked_off_actor_non_noop_count": int(masked_off_actor_non_noop),
        "unmasked_move_predictions": int(unmasked_move_predictions),
        "masked_move_predictions": int(masked_move_predictions),
        "unmasked_valid_target_moves": int(unmasked_valid_moves),
        "masked_valid_target_moves": int(masked_valid_moves),
        "unmasked_occupied_or_invalid_target_moves": int(unmasked_invalid_moves),
        "masked_occupied_or_invalid_target_moves": int(masked_invalid_moves),
        "unmasked_estimated_command_build_readiness": float(unmasked_valid_moves / max(1, unmasked_move_predictions)),
        "masked_estimated_command_build_readiness": float(masked_valid_moves / max(1, masked_move_predictions)),
        "unmasked_attack_predictions": int(unmasked_attack_predictions),
        "masked_attack_predictions": int(masked_attack_predictions),
        "masked_attack_valid_target_count": int(masked_attack_valid_targets),
        "B2": {
            "unmasked_action": ACTION_TYPE_NAMES[b2_u],
            "masked_action": ACTION_TYPE_NAMES[b2_m],
            "probabilities": [float(x) for x in b2_probs.tolist()],
        },
        "C3": {
            "unmasked_action": ACTION_TYPE_NAMES[c3_u],
            "masked_action": ACTION_TYPE_NAMES[c3_m],
            "probabilities": [float(x) for x in c3_probs.tolist()],
        },
        "produced_unit_masked_action_distribution": dict(produced_masked_action_dist),
        "number_of_actions_changed_by_mask": int(changed_total),
        "changed_action_breakdown": {
            "invalid Move -> NoOp": int(changed_breakdown.get("invalid Move -> NoOp", 0)),
            "invalid Move -> valid Move": int(changed_breakdown.get("invalid Move -> valid Move", 0)),
            "off-actor non-NoOp -> NoOp": int(changed_breakdown.get("off-actor non-NoOp -> NoOp", 0)),
            "invalid Attack -> NoOp": int(changed_breakdown.get("invalid Attack -> NoOp", 0)),
            "other": int(changed_breakdown.get("other", 0)),
        },
        "labels": labels,
    }

    write_json(args.output_report, report)
    print(Path(args.output_report).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
