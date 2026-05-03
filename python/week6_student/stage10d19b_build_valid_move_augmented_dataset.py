#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import numpy as np

from stage10d19b_common import (
    ACTION_SHAPE,
    ACTION_TYPE_HARVEST,
    ACTION_TYPE_MOVE,
    ACTION_TYPE_NAMES,
    ACTION_TYPE_NOOP,
    ACTION_TYPE_PRODUCE,
    B2_FLAT,
    C3_FLAT,
    MAP_H,
    MAP_W,
    MOVE_DIR_TO_NAME,
    OWNER_SELF_INDEX,
    UNIT_NAME_TO_CHANNEL,
    UNIT_TYPE_SLICE,
    choose_preferred_valid_direction,
    clear_action_context_on_cell,
    ensure_payload_defaults,
    flat_to_xy,
    get_observations_and_actions,
    in_bounds_xy,
    is_cell_empty,
    is_cell_enemy,
    is_cell_resource,
    iter_jsonl,
    load_json,
    load_split_payload,
    merge_original_and_augmented,
    normalize_empty_cells_to_no_context,
    pick_reference_action_vectors,
    resolve_path,
    save_split_npz,
    set_unit_cell,
    summarize_action_type_distribution,
    target_from_source_and_dir,
    utc_dir_stamp,
    utc_now_iso,
    write_json,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.19B build valid-target move augmented BC-ready dataset")
    p.add_argument(
        "--base-bc-ready-dir",
        type=Path,
        default=Path("python/week6_student/bc_ready/legacy032_v2_stage10d17_movement_augmented_bc_ready_20260503T162905Z"),
    )
    p.add_argument(
        "--stage10d18rr-trace-jsonl",
        type=Path,
        default=Path("python/week6_student/reports/stage10d18rr_runtime_redeploy_trace.jsonl"),
    )
    p.add_argument(
        "--stage10d18rr-move-audit-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d18rr_movement_command_path_audit.json"),
    )
    p.add_argument(
        "--stage10d18rr-off-actor-audit-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d18rr_off_actor_safety_audit.json"),
    )
    p.add_argument(
        "--stage10d19-move-efficiency-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d19_move_command_efficiency_audit.json"),
    )
    p.add_argument(
        "--stage10d19-off-actor-deep-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d19_off_actor_safety_deep_audit.json"),
    )
    p.add_argument(
        "--output-root",
        type=Path,
        default=Path("python/week6_student/bc_ready"),
    )
    p.add_argument(
        "--run-label",
        type=str,
        default="legacy032_v2_stage10d19b_valid_move_augmented_bc_ready",
    )
    p.add_argument("--max-valid-move-positive-samples", type=int, default=2000)
    p.add_argument("--max-occupied-negative-samples", type=int, default=2000)
    p.add_argument("--max-direction-correction-samples", type=int, default=1500)
    p.add_argument("--max-off-actor-negative-samples", type=int, default=2000)
    p.add_argument("--max-preservation-samples", type=int, default=1800)
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--seed", type=int, default=1919)
    return p.parse_args()


def _init_collector() -> Dict[str, List[np.ndarray]]:
    return {
        "observations": [],
        "actions": [],
        "episode_id": [],
        "step_id": [],
        "reward_t": [],
        "done_t": [],
        "terminated_t": [],
        "truncated_t": [],
        "action_mask_available_t": [],
    }


def _append_row(
    collector: Dict[str, List[np.ndarray]],
    *,
    observation: np.ndarray,
    action: np.ndarray,
    source_payload: Mapping[str, np.ndarray],
    source_sample_index: int,
) -> None:
    collector["observations"].append(np.asarray(observation, dtype=np.float32))
    collector["actions"].append(np.asarray(action, dtype=np.int16))
    collector["episode_id"].append(np.asarray(source_payload["episode_id"][source_sample_index], dtype=np.int32))
    collector["step_id"].append(np.asarray(source_payload["step_id"][source_sample_index], dtype=np.int32))
    collector["reward_t"].append(np.asarray(source_payload["reward_t"][source_sample_index], dtype=np.float32))
    collector["done_t"].append(np.asarray(source_payload["done_t"][source_sample_index], dtype=np.bool_))
    collector["terminated_t"].append(np.asarray(source_payload["terminated_t"][source_sample_index], dtype=np.bool_))
    collector["truncated_t"].append(np.asarray(source_payload["truncated_t"][source_sample_index], dtype=np.bool_))
    collector["action_mask_available_t"].append(np.asarray(source_payload["action_mask_available_t"][source_sample_index], dtype=np.bool_))


def _stack_collector(collector: Mapping[str, List[np.ndarray]]) -> Dict[str, np.ndarray]:
    out: Dict[str, np.ndarray] = {}
    for key, values in collector.items():
        if len(values) == 0:
            if key == "observations":
                out[key] = np.zeros((0, 576, 27), dtype=np.float32)
            elif key == "actions":
                out[key] = np.zeros((0, 576, 7), dtype=np.int16)
            elif key == "reward_t":
                out[key] = np.zeros((0,), dtype=np.float32)
            elif key in {"done_t", "terminated_t", "truncated_t", "action_mask_available_t"}:
                out[key] = np.zeros((0,), dtype=np.bool_)
            else:
                out[key] = np.zeros((0,), dtype=np.int32)
            continue

        if key in {"observations", "actions"}:
            out[key] = np.stack(values, axis=0)
        elif key == "reward_t":
            out[key] = np.asarray(values, dtype=np.float32)
        elif key in {"done_t", "terminated_t", "truncated_t", "action_mask_available_t"}:
            out[key] = np.asarray(values, dtype=np.bool_)
        else:
            out[key] = np.asarray(values, dtype=np.int32)
    return out


def _set_target_action(
    action_map: np.ndarray,
    *,
    source_flat: int,
    action_type: int,
    move_dir: int,
    b2_vec: np.ndarray,
    c3_vec: np.ndarray,
) -> np.ndarray:
    out = np.asarray(action_map, dtype=np.int16).copy()
    out[source_flat, :] = 0
    out[source_flat, 0] = int(action_type)
    out[source_flat, 1] = int(move_dir)
    out[B2_FLAT, :] = np.asarray(b2_vec, dtype=np.int16)
    out[C3_FLAT, :] = np.asarray(c3_vec, dtype=np.int16)
    return out


def _inject_actor_on_source(obs: np.ndarray, source_flat: int, unit_type: str) -> np.ndarray:
    channel = UNIT_NAME_TO_CHANNEL.get(unit_type, UNIT_NAME_TO_CHANNEL["Worker"])
    out = set_unit_cell(obs, source_flat, owner_self=True, unit_type_channel=channel)
    out = clear_action_context_on_cell(out, source_flat)
    out = normalize_empty_cells_to_no_context(out)
    return out


def _inject_occupied_target(obs: np.ndarray, target_flat: int, as_resource: bool = False) -> np.ndarray:
    out = np.asarray(obs, dtype=np.float32).copy()
    if as_resource:
        out = set_unit_cell(out, target_flat, owner_self=False, unit_type_channel=UNIT_NAME_TO_CHANNEL["Resource"])
        out[target_flat, 2] = 1.0
        out[target_flat, 4] = 0.0
    else:
        out = set_unit_cell(out, target_flat, owner_self=True, unit_type_channel=UNIT_NAME_TO_CHANNEL["Worker"])
    out = clear_action_context_on_cell(out, target_flat)
    return out


def _sample_source_idx(obs: np.ndarray, rng: np.random.Generator) -> int:
    return int(rng.integers(0, max(1, obs.shape[0])))


def _pick_split(rng: np.random.Generator, train_ratio: float) -> str:
    return "train" if float(rng.random()) < train_ratio else "validation"


def _actor_cells(obs_row: np.ndarray) -> np.ndarray:
    owner_self = obs_row[:, OWNER_SELF_INDEX] > 0.5
    has_unit = np.sum(obs_row[:, UNIT_TYPE_SLICE], axis=1) > 0.5
    return np.asarray(owner_self & has_unit, dtype=bool)


def _actor_mask_batch(obs: np.ndarray) -> np.ndarray:
    owner_self = obs[:, :, OWNER_SELF_INDEX] > 0.5
    has_unit = np.sum(obs[:, :, UNIT_TYPE_SLICE], axis=2) > 0.5
    return np.asarray(owner_self & has_unit, dtype=bool)


def _iter_move_events(path: Path) -> Iterable[Dict[str, Any]]:
    payload = load_json(path)
    for row in payload.get("events", []) or []:
        if str(row.get("predicted_action")) == "Move":
            yield row


def _iter_trace_rows(path: Path) -> Iterable[Dict[str, Any]]:
    for row in iter_jsonl(path):
        yield row


def _metadata_row(**kwargs: Any) -> Dict[str, Any]:
    return {
        "augmentation_family": kwargs.get("augmentation_family"),
        "family_subtype": kwargs.get("family_subtype", ""),
        "source": kwargs.get("source", ""),
        "split": kwargs.get("split", ""),
        "source_split": kwargs.get("source_split", "train"),
        "source_sample_index": int(kwargs.get("source_sample_index", -1)),
        "source_step": int(kwargs.get("source_step", -1)),
        "unit_id": kwargs.get("unit_id"),
        "unit_type": kwargs.get("unit_type"),
        "source_cell": int(kwargs.get("source_cell", -1)),
        "source_xy": kwargs.get("source_xy"),
        "target_cell": int(kwargs.get("target_cell", -1)),
        "target_xy": kwargs.get("target_xy"),
        "target_occupancy": kwargs.get("target_occupancy", "unknown"),
        "chosen_move_dir": int(kwargs.get("chosen_move_dir", -1)),
        "target_action_type": int(kwargs.get("target_action_type", -1)),
        "target_cell_in_bounds": bool(kwargs.get("target_cell_in_bounds", False)),
        "target_cell_free": bool(kwargs.get("target_cell_free", False)),
        "target_cell_valid": bool(kwargs.get("target_cell_valid", False)),
        "validity_checks": kwargs.get("validity_checks", {}),
        "off_actor_control": bool(kwargs.get("off_actor_control", False)),
        "preservation_sample": bool(kwargs.get("preservation_sample", False)),
        "notes": kwargs.get("notes", ""),
    }


def _finalize_and_save(
    *,
    out_dir: Path,
    base_train_payload: Mapping[str, np.ndarray],
    base_val_payload: Mapping[str, np.ndarray],
    aug_collectors: Dict[str, Dict[str, List[np.ndarray]]],
    metadata: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    aug_train = _stack_collector(aug_collectors["train"])
    aug_val = _stack_collector(aug_collectors["validation"])

    merged_train = merge_original_and_augmented(base_train_payload, aug_train, split_name="train")
    merged_val = merge_original_and_augmented(base_val_payload, aug_val, split_name="validation")

    save_split_npz(out_dir / "bc_train.npz", merged_train)
    save_split_npz(out_dir / "bc_validation.npz", merged_val)

    debug_count = min(128, int(merged_val["observations"].shape[0]))
    debug_payload = {k: np.asarray(v)[:debug_count] for k, v in merged_val.items() if np.asarray(v).shape[0] == merged_val["observations"].shape[0]}
    save_split_npz(out_dir / "bc_debug.npz", debug_payload)

    write_jsonl(out_dir / "stage10d19b_augmented_sample_metadata_train.jsonl", metadata["train"])
    write_jsonl(out_dir / "stage10d19b_augmented_sample_metadata_validation.jsonl", metadata["validation"])

    return {
        "merged_train_count": int(merged_train["observations"].shape[0]),
        "merged_validation_count": int(merged_val["observations"].shape[0]),
        "augmented_train_count": int(aug_train["observations"].shape[0]),
        "augmented_validation_count": int(aug_val["observations"].shape[0]),
    }


def main() -> int:
    args = parse_args()
    rng = np.random.default_rng(int(args.seed))

    base_dir = resolve_path(args.base_bc_ready_dir).resolve()
    output_root = resolve_path(args.output_root).resolve()
    output_dir = output_root / f"{args.run_label}_{utc_dir_stamp()}"
    output_dir.mkdir(parents=True, exist_ok=False)

    base_train_payload_raw = load_split_payload(base_dir / "bc_train.npz")
    base_val_payload_raw = load_split_payload(base_dir / "bc_validation.npz")
    base_train_obs, base_train_actions = get_observations_and_actions(base_train_payload_raw)
    base_val_obs, base_val_actions = get_observations_and_actions(base_val_payload_raw)
    base_train_payload = ensure_payload_defaults(base_train_payload_raw, base_train_obs.shape[0])
    base_val_payload = ensure_payload_defaults(base_val_payload_raw, base_val_obs.shape[0])

    b2_vec, c3_vec = pick_reference_action_vectors(base_train_actions)

    collectors = {
        "train": _init_collector(),
        "validation": _init_collector(),
    }
    metadata: Dict[str, List[Dict[str, Any]]] = {
        "train": [],
        "validation": [],
    }

    family_counts: Counter[str] = Counter()
    skipped: Counter[str] = Counter()
    move_dir_counter: Counter[str] = Counter()
    unit_type_counter: Counter[str] = Counter()

    # Family A: valid free-cell move positives from Stage10D.18RR move events.
    for ev in _iter_move_events(resolve_path(args.stage10d18rr_move_audit_json)):
        if family_counts["family_a_valid_move_positive"] >= int(args.max_valid_move_positive_samples):
            break
        src = ev.get("source_cell") or {}
        src_flat = int(src.get("flat", -1))
        unit_type = str(ev.get("unit_type") or "Worker")
        if src_flat < 0 or unit_type not in {"Worker", "Light", "Heavy", "Ranged"}:
            skipped["family_a_invalid_source"] += 1
            continue

        move_dir = int(ev.get("move_dir", -1))
        target_flat, in_bounds = target_from_source_and_dir(src_flat, move_dir)
        if not in_bounds or target_flat is None:
            skipped["family_a_target_oob"] += 1
            continue

        occupied = bool(ev.get("target_cell_occupied", False))
        if occupied:
            skipped["family_a_target_occupied"] += 1
            continue

        src_idx = _sample_source_idx(base_train_obs, rng)
        obs = _inject_actor_on_source(base_train_obs[src_idx], src_flat, unit_type)
        obs = clear_action_context_on_cell(obs, src_flat)
        if not is_cell_empty(obs, target_flat):
            obs[target_flat, UNIT_TYPE_SLICE] = 0.0
            obs[target_flat, OWNER_SELF_INDEX] = 0.0
        obs = normalize_empty_cells_to_no_context(obs)

        action = _set_target_action(
            base_train_actions[src_idx],
            source_flat=src_flat,
            action_type=ACTION_TYPE_MOVE,
            move_dir=move_dir,
            b2_vec=b2_vec,
            c3_vec=c3_vec,
        )
        split = _pick_split(rng, float(args.train_ratio))
        payload = base_train_payload if split == "train" else base_val_payload
        idx = src_idx if split == "train" else int(src_idx % base_val_obs.shape[0])

        _append_row(collectors[split], observation=obs, action=action, source_payload=payload, source_sample_index=idx)
        metadata[split].append(
            _metadata_row(
                augmentation_family="family_a_valid_move_positive",
                source="stage10d18rr_movement_command_path_audit",
                split=split,
                source_sample_index=idx,
                source_step=int(ev.get("step", -1)),
                unit_id=ev.get("unit_id"),
                unit_type=unit_type,
                source_cell=src_flat,
                source_xy=list(flat_to_xy(src_flat)),
                target_cell=target_flat,
                target_xy=list(flat_to_xy(target_flat)),
                target_occupancy="empty_or_unknown",
                chosen_move_dir=move_dir,
                target_action_type=ACTION_TYPE_MOVE,
                target_cell_in_bounds=True,
                target_cell_free=True,
                target_cell_valid=True,
                validity_checks={
                    "self_owned_actor": True,
                    "movable_unit_type": True,
                    "target_not_resource": True,
                    "target_not_enemy": True,
                    "adjacent": True,
                },
                notes="Family A valid free-cell move positive from Stage10D.18RR move event",
            )
        )
        family_counts["family_a_valid_move_positive"] += 1
        move_dir_counter[MOVE_DIR_TO_NAME.get(move_dir, str(move_dir))] += 1
        unit_type_counter[unit_type] += 1

    # Families B/C from occupied target events.
    occupied_events = [
        ev for ev in _iter_move_events(resolve_path(args.stage10d18rr_move_audit_json)) if bool(ev.get("target_cell_occupied", False))
    ]
    rng.shuffle(occupied_events)
    for ev in occupied_events:
        if family_counts["family_b_occupied_negative"] >= int(args.max_occupied_negative_samples) and family_counts[
            "family_c_direction_correction"
        ] >= int(args.max_direction_correction_samples):
            break

        src = ev.get("source_cell") or {}
        src_flat = int(src.get("flat", -1))
        unit_type = str(ev.get("unit_type") or "Worker")
        src_idx = _sample_source_idx(base_train_obs, rng)
        obs = _inject_actor_on_source(base_train_obs[src_idx], src_flat, unit_type)

        bad_dir = int(ev.get("move_dir", 1))
        bad_target, in_bounds = target_from_source_and_dir(src_flat, bad_dir)
        if in_bounds and bad_target is not None:
            obs = _inject_occupied_target(obs, bad_target, as_resource=False)

        alt_dir, alt_target, reason = choose_preferred_valid_direction(obs, src_flat, preferred_dirs=(1, 2, 0, 3))
        split = _pick_split(rng, float(args.train_ratio))
        payload = base_train_payload if split == "train" else base_val_payload
        idx = src_idx if split == "train" else int(src_idx % base_val_obs.shape[0])

        # B1: blocked -> NoOp.
        if family_counts["family_b_occupied_negative"] < int(args.max_occupied_negative_samples):
            action_b1 = _set_target_action(
                base_train_actions[src_idx],
                source_flat=src_flat,
                action_type=ACTION_TYPE_NOOP,
                move_dir=0,
                b2_vec=b2_vec,
                c3_vec=c3_vec,
            )
            _append_row(collectors[split], observation=obs, action=action_b1, source_payload=payload, source_sample_index=idx)
            metadata[split].append(
                _metadata_row(
                    augmentation_family="family_b_occupied_negative",
                    family_subtype="B1_blocked_to_noop",
                    source="stage10d18rr_movement_command_path_audit",
                    split=split,
                    source_sample_index=idx,
                    source_step=int(ev.get("step", -1)),
                    unit_id=ev.get("unit_id"),
                    unit_type=unit_type,
                    source_cell=src_flat,
                    source_xy=list(flat_to_xy(src_flat)),
                    target_cell=(-1 if bad_target is None else bad_target),
                    target_xy=(None if bad_target is None else list(flat_to_xy(bad_target))),
                    target_occupancy="occupied",
                    chosen_move_dir=bad_dir,
                    target_action_type=ACTION_TYPE_NOOP,
                    target_cell_in_bounds=bool(in_bounds),
                    target_cell_free=False,
                    target_cell_valid=False,
                    validity_checks={"blocked_predicted_direction": True, "noop_justified": True},
                    notes="Family B1 occupied-target negative control",
                )
            )
            family_counts["family_b_occupied_negative"] += 1

        # B2/C: blocked direction but alternative free cell exists.
        if alt_dir is not None and alt_target is not None and family_counts["family_c_direction_correction"] < int(
            args.max_direction_correction_samples
        ):
            action_c = _set_target_action(
                base_train_actions[src_idx],
                source_flat=src_flat,
                action_type=ACTION_TYPE_MOVE,
                move_dir=alt_dir,
                b2_vec=b2_vec,
                c3_vec=c3_vec,
            )
            _append_row(collectors[split], observation=obs, action=action_c, source_payload=payload, source_sample_index=idx)
            metadata[split].append(
                _metadata_row(
                    augmentation_family="family_c_direction_correction",
                    family_subtype="C_alt_free_dir",
                    source="stage10d18rr_movement_command_path_audit",
                    split=split,
                    source_sample_index=idx,
                    source_step=int(ev.get("step", -1)),
                    unit_id=ev.get("unit_id"),
                    unit_type=unit_type,
                    source_cell=src_flat,
                    source_xy=list(flat_to_xy(src_flat)),
                    target_cell=alt_target,
                    target_xy=list(flat_to_xy(alt_target)),
                    target_occupancy="empty_or_unknown",
                    chosen_move_dir=alt_dir,
                    target_action_type=ACTION_TYPE_MOVE,
                    target_cell_in_bounds=True,
                    target_cell_free=True,
                    target_cell_valid=True,
                    validity_checks={"alternative_adjacent_free": True, "preferred_direction_policy": True},
                    notes=f"Family C direction correction ({reason or 'preferred'})",
                )
            )
            family_counts["family_c_direction_correction"] += 1
            move_dir_counter[MOVE_DIR_TO_NAME.get(alt_dir, str(alt_dir))] += 1
            unit_type_counter[unit_type] += 1

    # Family D: congestion/rally controls around base.
    for row in _iter_trace_rows(resolve_path(args.stage10d18rr_trace_jsonl)):
        if family_counts["family_d_congestion_rally"] >= 1000:
            break
        for u in row.get("friendly_units", []) or []:
            if str(u.get("unit_type")) != "Worker":
                continue
            x = int(u.get("x", -1))
            y = int(u.get("y", -1))
            if not (0 <= x <= 6 and 0 <= y <= 6):
                continue
            src_flat = int(u.get("flat_index", -1))
            if src_flat < 0:
                continue
            src_idx = _sample_source_idx(base_train_obs, rng)
            obs = _inject_actor_on_source(base_train_obs[src_idx], src_flat, "Worker")
            alt_dir, alt_target, reason = choose_preferred_valid_direction(obs, src_flat, preferred_dirs=(1, 2, 0, 3))
            if alt_dir is None or alt_target is None:
                continue

            action = _set_target_action(
                base_train_actions[src_idx],
                source_flat=src_flat,
                action_type=ACTION_TYPE_MOVE,
                move_dir=alt_dir,
                b2_vec=b2_vec,
                c3_vec=c3_vec,
            )
            split = _pick_split(rng, float(args.train_ratio))
            payload = base_train_payload if split == "train" else base_val_payload
            idx = src_idx if split == "train" else int(src_idx % base_val_obs.shape[0])
            _append_row(collectors[split], observation=obs, action=action, source_payload=payload, source_sample_index=idx)
            metadata[split].append(
                _metadata_row(
                    augmentation_family="family_d_congestion_rally",
                    source="stage10d18rr_runtime_trace",
                    split=split,
                    source_sample_index=idx,
                    source_step=int(row.get("step", -1)),
                    unit_id=u.get("unit_id"),
                    unit_type="Worker",
                    source_cell=src_flat,
                    source_xy=[x, y],
                    target_cell=alt_target,
                    target_xy=list(flat_to_xy(alt_target)),
                    target_occupancy="empty_or_unknown",
                    chosen_move_dir=alt_dir,
                    target_action_type=ACTION_TYPE_MOVE,
                    target_cell_in_bounds=True,
                    target_cell_free=True,
                    target_cell_valid=True,
                    validity_checks={"base_congestion_zone": True, "adjacent_free_move": True},
                    notes=f"Family D base congestion control ({reason or 'preferred'})",
                )
            )
            family_counts["family_d_congestion_rally"] += 1
            move_dir_counter[MOVE_DIR_TO_NAME.get(alt_dir, str(alt_dir))] += 1
            unit_type_counter["Worker"] += 1

    # Family E: off-actor negative controls from runtime-like states.
    off_actor_limit = int(args.max_off_actor_negative_samples)
    sampled_rows = 0
    for row in _iter_trace_rows(resolve_path(args.stage10d18rr_trace_jsonl)):
        if sampled_rows >= off_actor_limit:
            break

        src_idx = _sample_source_idx(base_train_obs, rng)
        obs = np.asarray(base_train_obs[src_idx], dtype=np.float32).copy()
        actor_mask = _actor_cells(obs)
        candidate = np.where(~actor_mask)[0]
        if candidate.size == 0:
            continue
        rng.shuffle(candidate)
        for target_flat in candidate[:6].tolist():
            if sampled_rows >= off_actor_limit:
                break
            action = _set_target_action(
                base_train_actions[src_idx],
                source_flat=int(target_flat),
                action_type=ACTION_TYPE_NOOP,
                move_dir=0,
                b2_vec=b2_vec,
                c3_vec=c3_vec,
            )
            split = _pick_split(rng, float(args.train_ratio))
            payload = base_train_payload if split == "train" else base_val_payload
            idx = src_idx if split == "train" else int(src_idx % base_val_obs.shape[0])
            _append_row(collectors[split], observation=obs, action=action, source_payload=payload, source_sample_index=idx)

            cell_kind = "empty"
            if is_cell_resource(obs, int(target_flat)):
                cell_kind = "resource"
            elif is_cell_enemy(obs, int(target_flat)):
                cell_kind = "enemy"

            metadata[split].append(
                _metadata_row(
                    augmentation_family="family_e_off_actor_negative",
                    source="stage10d18rr_runtime_trace",
                    split=split,
                    source_sample_index=idx,
                    source_step=int(row.get("step", -1)),
                    unit_id=f"off_actor_{target_flat}",
                    unit_type="off_actor_cell",
                    source_cell=int(target_flat),
                    source_xy=list(flat_to_xy(int(target_flat))),
                    target_cell=int(target_flat),
                    target_xy=list(flat_to_xy(int(target_flat))),
                    target_occupancy=cell_kind,
                    chosen_move_dir=-1,
                    target_action_type=ACTION_TYPE_NOOP,
                    target_cell_in_bounds=True,
                    target_cell_free=(cell_kind == "empty"),
                    target_cell_valid=True,
                    validity_checks={"off_actor_noop_required": True},
                    off_actor_control=True,
                    notes="Family E off-actor negative control",
                )
            )
            family_counts["family_e_off_actor_negative"] += 1
            sampled_rows += 1

    # Family F: preservation (copy base examples with explicit markers).
    preserve_limit = int(args.max_preservation_samples)
    base_actor = np.where((base_train_actions[:, :, 0] == ACTION_TYPE_MOVE) & _actor_mask_batch(base_train_obs))
    move_sample_indices = np.unique(base_actor[0])
    if move_sample_indices.size == 0:
        move_sample_indices = np.arange(base_train_obs.shape[0], dtype=np.int64)
    rng.shuffle(move_sample_indices)

    added_preserve = 0
    for src_idx in move_sample_indices.tolist():
        if added_preserve >= preserve_limit:
            break
        obs = np.asarray(base_train_obs[src_idx], dtype=np.float32)
        action = np.asarray(base_train_actions[src_idx], dtype=np.int16)
        split = _pick_split(rng, float(args.train_ratio))
        payload = base_train_payload if split == "train" else base_val_payload
        idx = src_idx if split == "train" else int(src_idx % base_val_obs.shape[0])

        _append_row(collectors[split], observation=obs, action=action, source_payload=payload, source_sample_index=idx)
        metadata[split].append(
            _metadata_row(
                augmentation_family="family_f_preservation",
                source="stage10d17_base_dataset",
                split=split,
                source_sample_index=idx,
                source_step=int(base_train_payload["step_id"][src_idx]),
                unit_id="preservation_row",
                unit_type="mixed",
                source_cell=-1,
                source_xy=None,
                target_cell=-1,
                target_xy=None,
                target_occupancy="n/a",
                chosen_move_dir=-1,
                target_action_type=-1,
                target_cell_in_bounds=False,
                target_cell_free=False,
                target_cell_valid=False,
                validity_checks={"b2_guard_present": True, "c3_guard_present": True},
                preservation_sample=True,
                notes="Family F preservation sample from Stage10D.17 dataset",
            )
        )
        family_counts["family_f_preservation"] += 1
        added_preserve += 1

    save_stats = _finalize_and_save(
        out_dir=output_dir,
        base_train_payload=base_train_payload,
        base_val_payload=base_val_payload,
        aug_collectors=collectors,
        metadata=metadata,
    )

    merged_train = load_split_payload(output_dir / "bc_train.npz")
    merged_val = load_split_payload(output_dir / "bc_validation.npz")
    train_obs, train_actions = get_observations_and_actions(merged_train)
    val_obs, val_actions = get_observations_and_actions(merged_val)

    manifest: Dict[str, Any] = {
        "stage": "10D.19B",
        "task": "build_valid_move_augmented_dataset",
        "generated_at_utc": utc_now_iso(),
        "output_dataset_dir": str(output_dir.as_posix()),
        "base_dataset_path": str(base_dir.as_posix()),
        "stage10d18rr_artifact_paths": {
            "trace_jsonl": str(resolve_path(args.stage10d18rr_trace_jsonl).as_posix()),
            "movement_audit_json": str(resolve_path(args.stage10d18rr_move_audit_json).as_posix()),
            "off_actor_audit_json": str(resolve_path(args.stage10d18rr_off_actor_audit_json).as_posix()),
        },
        "stage10d19_audit_artifact_paths": {
            "move_efficiency_audit": str(resolve_path(args.stage10d19_move_efficiency_json).as_posix()),
            "off_actor_deep_audit": str(resolve_path(args.stage10d19_off_actor_deep_json).as_posix()),
        },
        "counts": {
            "original_train": int(base_train_obs.shape[0]),
            "original_validation": int(base_val_obs.shape[0]),
            **save_stats,
        },
        "augmentation_family_counts": dict(family_counts),
        "valid_move_positive_count": int(family_counts["family_a_valid_move_positive"]),
        "invalid_or_occupied_negative_count": int(family_counts["family_b_occupied_negative"]),
        "direction_correction_count": int(family_counts["family_c_direction_correction"]),
        "off_actor_negative_control_count": int(family_counts["family_e_off_actor_negative"]),
        "preservation_count": int(family_counts["family_f_preservation"]),
        "skipped_sample_counts_by_reason": dict(skipped),
        "move_dir_distribution": dict(move_dir_counter),
        "unit_type_distribution": dict(unit_type_counter),
        "distribution_summary": {
            "train": summarize_action_type_distribution(train_obs, train_actions),
            "validation": summarize_action_type_distribution(val_obs, val_actions),
        },
        "config": {
            "max_valid_move_positive_samples": int(args.max_valid_move_positive_samples),
            "max_occupied_negative_samples": int(args.max_occupied_negative_samples),
            "max_direction_correction_samples": int(args.max_direction_correction_samples),
            "max_off_actor_negative_samples": int(args.max_off_actor_negative_samples),
            "max_preservation_samples": int(args.max_preservation_samples),
            "train_ratio": float(args.train_ratio),
            "seed": int(args.seed),
        },
        "explicit_non_claims": [
            "no PPO",
            "no teacher mutation",
            "no runtime force movement",
            "no decoder/applier/matchmanager change",
            "no attack augmentation in this stage",
        ],
    }

    write_json(output_dir / "bc_manifest.json", manifest)
    write_json(output_dir / "stage10d19b_valid_move_augmentation_manifest.json", manifest)
    write_json("python/week6_student/reports/stage10d19b_valid_move_augmentation_manifest.json", manifest)

    print(output_dir.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
