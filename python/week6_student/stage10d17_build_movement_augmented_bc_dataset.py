#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np

from stage10d17_common import (
    ACTION_SHAPE,
    ACTION_SLICE,
    ACTION_TYPE_HARVEST,
    ACTION_TYPE_MOVE,
    ACTION_TYPE_NAMES,
    ACTION_TYPE_NOOP,
    ACTION_TYPE_PRODUCE,
    ATTACK_TARGET_INDEX,
    B2_FLAT,
    C3_FLAT,
    DIR_SLICE,
    OWNER_SELF_INDEX,
    PRODUCE_TYPE_SLICE,
    UNIT_BASE_INDEX,
    UNIT_BARRACKS_INDEX,
    UNIT_LIGHT_INDEX,
    UNIT_NAME_TO_CHANNEL,
    UNIT_RANGED_INDEX,
    UNIT_TYPE_SLICE,
    UNIT_WORKER_INDEX,
    choose_safe_move_direction,
    clear_action_context_on_cell,
    ensure_payload_defaults,
    flat_to_xy,
    get_observations_and_actions,
    load_json,
    load_split_payload,
    merge_original_and_augmented,
    normalize_empty_cells_to_no_context,
    pick_reference_action_vectors,
    resolve_path,
    save_split_npz,
    set_unit_cell,
    summarize_action_type_distribution,
    utc_dir_stamp,
    utc_now_iso,
    write_json,
    write_jsonl,
    xy_to_flat,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.17 build movement-augmented BC-ready dataset")
    p.add_argument(
        "--base-bc-ready-dir",
        type=Path,
        default=Path("python/week6_student/bc_ready/legacy032_3m_unity_v2_stage10d14_unity_like_augmented_bc_ready_20260503T145301Z"),
    )
    p.add_argument(
        "--stage10d7-bc-ready-dir",
        type=Path,
        default=Path("python/week6_student/bc_ready/legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z"),
    )
    p.add_argument(
        "--stage10d16-trace-jsonl",
        type=Path,
        default=Path("python/week6_student/reports/stage10d16_extended_runtime_trace.jsonl"),
    )
    p.add_argument(
        "--stage10d16-lifecycle-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d16_produced_unit_lifecycle.json"),
    )
    p.add_argument(
        "--output-root",
        type=Path,
        default=Path("python/week6_student/bc_ready"),
    )
    p.add_argument(
        "--run-label",
        type=str,
        default="legacy032_v2_stage10d17_movement_augmented_bc_ready",
    )
    p.add_argument("--max-runtime-move-aug-samples", type=int, default=1200)
    p.add_argument("--max-synthetic-move-aug-samples", type=int, default=1200)
    p.add_argument("--negative-control-samples", type=int, default=400)
    p.add_argument("--movement-repeat-factor", type=int, default=1)
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--seed", type=int, default=17)
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


def _build_metadata_row(**kwargs: Any) -> Dict[str, Any]:
    row = {
        "augmentation_family": kwargs.get("family"),
        "source": kwargs.get("source"),
        "split": kwargs.get("split"),
        "source_split": kwargs.get("source_split"),
        "source_sample_index": int(kwargs.get("source_sample_index", -1)),
        "source_step": int(kwargs.get("source_step", -1)),
        "unit_id": kwargs.get("unit_id"),
        "unit_type": kwargs.get("unit_type"),
        "source_position": kwargs.get("source_position"),
        "target_cell": int(kwargs.get("target_cell", -1)),
        "target_move_dir": int(kwargs.get("target_move_dir", -1)),
        "target_action_type": int(kwargs.get("target_action_type", -1)),
        "target_cell_in_bounds": bool(kwargs.get("target_cell_in_bounds", False)),
        "target_cell_free": bool(kwargs.get("target_cell_free", False)),
        "target_cell_valid": bool(kwargs.get("target_cell_valid", False)),
        "notes": kwargs.get("notes", ""),
    }
    return row


def _set_move_target(action_map: np.ndarray, flat_idx: int, move_dir: int, b2_vec: np.ndarray, c3_vec: np.ndarray) -> np.ndarray:
    out = np.asarray(action_map, dtype=np.int16).copy()
    out[flat_idx, :] = 0
    out[flat_idx, 0] = ACTION_TYPE_MOVE
    out[flat_idx, 1] = int(move_dir)

    out[B2_FLAT, :] = np.asarray(b2_vec, dtype=np.int16)
    out[C3_FLAT, :] = np.asarray(c3_vec, dtype=np.int16)
    return out


def _inject_unit_proxy(obs: np.ndarray, flat_idx: int, unit_type: str) -> np.ndarray:
    channel = UNIT_NAME_TO_CHANNEL.get(unit_type, UNIT_WORKER_INDEX)
    out = set_unit_cell(obs, flat_idx, owner_self=True, unit_type_channel=channel)
    out = clear_action_context_on_cell(out, flat_idx)
    out = normalize_empty_cells_to_no_context(out)
    return out


def _is_combat_or_worker(cell: np.ndarray) -> bool:
    return bool(
        (cell[UNIT_WORKER_INDEX] > 0.5)
        or (cell[UNIT_LIGHT_INDEX] > 0.5)
        or (cell[UNIT_RANGED_INDEX] > 0.5)
        or (cell[UNIT_BARRACKS_INDEX] > 0.5)
    )


def _iter_trace_rows(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield __import__("json").loads(line)


def _build_runtime_family(
    *,
    max_samples: int,
    movement_repeat_factor: int,
    trace_jsonl: Path,
    lifecycle_json: Path,
    train_obs: np.ndarray,
    train_actions: np.ndarray,
    train_payload: Mapping[str, np.ndarray],
    b2_vec: np.ndarray,
    c3_vec: np.ndarray,
    rng: np.random.Generator,
    collectors: Dict[str, Dict[str, List[np.ndarray]]],
    metadata: Dict[str, List[Dict[str, Any]]],
    family_counter: Counter[str],
    move_unit_counter: Counter[str],
    move_dir_counter: Counter[str],
    skipped: Counter[str],
    train_ratio: float,
) -> int:
    lifecycle = load_json(lifecycle_json)
    produced_ids = {str(u.get("unit_id")): str(u.get("unit_type", "Worker")) for u in lifecycle.get("units", []) or []}

    added = 0
    for row in _iter_trace_rows(trace_jsonl):
        step = int(row.get("step", -1))
        if step < 0:
            continue
        units = row.get("friendly_units", []) or []
        for u in units:
            uid = str(u.get("unit_id", ""))
            if uid not in produced_ids:
                continue
            x = int(u.get("x", -1))
            y = int(u.get("y", -1))
            if x < 0 or y < 0:
                skipped["family1_invalid_position"] += 1
                continue
            target_flat = xy_to_flat(x, y)
            source_idx = int(step % max(1, train_obs.shape[0]))
            obs = np.asarray(train_obs[source_idx], dtype=np.float32)
            act = np.asarray(train_actions[source_idx], dtype=np.int16)

            obs2 = _inject_unit_proxy(obs, target_flat, produced_ids[uid])
            move_dir, target_cell, reason = choose_safe_move_direction(obs2, target_flat, preferred_dirs=(1, 2, 0, 3))
            if move_dir is None or target_cell is None:
                skipped[f"family1_{reason or 'no_move'}"] += 1
                continue

            action2 = _set_move_target(act, target_flat, move_dir, b2_vec, c3_vec)
            split = "train" if float(rng.random()) < train_ratio else "validation"

            repeats = max(1, int(movement_repeat_factor))
            for _ in range(repeats):
                _append_row(
                    collectors[split],
                    observation=obs2,
                    action=action2,
                    source_payload=train_payload,
                    source_sample_index=source_idx,
                )
                metadata[split].append(
                    _build_metadata_row(
                        family="family1_stage10d16_runtime",
                        source="stage10d16_runtime_proxy_reconstructed",
                        split=split,
                        source_split="train",
                        source_sample_index=source_idx,
                        source_step=step,
                        unit_id=uid,
                        unit_type=produced_ids[uid],
                        source_position=[x, y],
                        target_cell=target_flat,
                        target_move_dir=move_dir,
                        target_action_type=ACTION_TYPE_MOVE,
                        target_cell_in_bounds=True,
                        target_cell_free=True,
                        target_cell_valid=True,
                        notes="runtime snapshot proxy derived from Stage10D16 trace and Stage10D14 source observation",
                    )
                )
                family_counter["family1_stage10d16_runtime"] += 1
                move_unit_counter[produced_ids[uid]] += 1
                move_dir_counter[{0: 'north', 1: 'east', 2: 'south', 3: 'west'}[int(move_dir)]] += 1
                added += 1
                if added >= max_samples:
                    return added

    return added


def _sample_indices(mask: np.ndarray, max_samples: int, rng: np.random.Generator) -> np.ndarray:
    idx = np.where(mask)[0]
    if idx.size <= max_samples:
        return idx
    rng.shuffle(idx)
    return idx[:max_samples]


def _build_family2_move_refs(
    *,
    datasets: Sequence[Tuple[str, np.ndarray, np.ndarray, Mapping[str, np.ndarray]]],
    max_samples: int,
    movement_repeat_factor: int,
    b2_vec: np.ndarray,
    c3_vec: np.ndarray,
    rng: np.random.Generator,
    collectors: Dict[str, Dict[str, List[np.ndarray]]],
    metadata: Dict[str, List[Dict[str, Any]]],
    family_counter: Counter[str],
    move_unit_counter: Counter[str],
    move_dir_counter: Counter[str],
    skipped: Counter[str],
    train_ratio: float,
) -> int:
    candidates: List[Tuple[str, int, int, int, np.ndarray, np.ndarray, Mapping[str, np.ndarray]]] = []
    for split_name, obs, act, payload in datasets:
        action_type = act[:, :, 0]
        actor = (obs[:, :, OWNER_SELF_INDEX] > 0.5) & (np.sum(obs[:, :, UNIT_TYPE_SLICE], axis=2) > 0.5)
        move = action_type == ACTION_TYPE_MOVE
        sample_idx, flat_idx = np.where(actor & move)
        for s, f in zip(sample_idx.tolist(), flat_idx.tolist()):
            d = int(act[s, f, 1])
            candidates.append((split_name, int(s), int(f), d, obs[s], act[s], payload))

    if len(candidates) == 0:
        skipped["family2_move_labels_absent"] += 1
        return 0

    if len(candidates) > max_samples:
        pick = rng.choice(len(candidates), size=max_samples, replace=False)
        candidates = [candidates[int(i)] for i in pick.tolist()]

    added = 0
    for source_split, source_idx, flat_idx, move_dir, obs, act, payload in candidates:
        obs2 = clear_action_context_on_cell(obs, flat_idx)
        obs2 = normalize_empty_cells_to_no_context(obs2)
        action2 = _set_move_target(act, flat_idx, move_dir, b2_vec, c3_vec)

        unit_type = "Worker"
        if obs[flat_idx, UNIT_LIGHT_INDEX] > 0.5:
            unit_type = "Light"
        elif obs[flat_idx, UNIT_RANGED_INDEX] > 0.5:
            unit_type = "Ranged"

        split = "train" if float(rng.random()) < train_ratio else "validation"
        for _ in range(max(1, movement_repeat_factor)):
            _append_row(
                collectors[split],
                observation=obs2,
                action=action2,
                source_payload=payload,
                source_sample_index=source_idx,
            )
            metadata[split].append(
                _build_metadata_row(
                    family="family2_bc_move_references",
                    source="bc_existing_move_labels",
                    split=split,
                    source_split=source_split,
                    source_sample_index=source_idx,
                    source_step=-1,
                    unit_id=None,
                    unit_type=unit_type,
                    source_position=list(flat_to_xy(flat_idx)),
                    target_cell=flat_idx,
                    target_move_dir=move_dir,
                    target_action_type=ACTION_TYPE_MOVE,
                    target_cell_in_bounds=True,
                    target_cell_free=True,
                    target_cell_valid=True,
                    notes="existing move label retained with unity-like no-action observation context",
                )
            )
            family_counter["family2_bc_move_references"] += 1
            move_unit_counter[unit_type] += 1
            move_dir_counter[{0: 'north', 1: 'east', 2: 'south', 3: 'west'}[int(move_dir)]] += 1
            added += 1
    return added


def _build_family3_family4_family5(
    *,
    train_obs: np.ndarray,
    train_actions: np.ndarray,
    train_payload: Mapping[str, np.ndarray],
    max_synthetic: int,
    negative_controls: int,
    movement_repeat_factor: int,
    b2_vec: np.ndarray,
    c3_vec: np.ndarray,
    rng: np.random.Generator,
    collectors: Dict[str, Dict[str, List[np.ndarray]]],
    metadata: Dict[str, List[Dict[str, Any]]],
    family_counter: Counter[str],
    move_unit_counter: Counter[str],
    move_dir_counter: Counter[str],
    skipped: Counter[str],
    train_ratio: float,
) -> tuple[int, int]:
    added_synth = 0
    added_neg = 0

    sample_indices = np.arange(train_obs.shape[0], dtype=np.int64)
    rng.shuffle(sample_indices)

    for source_idx in sample_indices.tolist():
        obs = np.asarray(train_obs[source_idx], dtype=np.float32)
        act = np.asarray(train_actions[source_idx], dtype=np.int16)
        owner = obs[:, OWNER_SELF_INDEX] > 0.5
        units = np.sum(obs[:, UNIT_TYPE_SLICE], axis=1) > 0.5
        actor_cells = np.where(owner & units)[0]

        if added_synth < max_synthetic:
            for flat_idx in actor_cells.tolist():
                cell = obs[flat_idx]
                if not _is_combat_or_worker(cell):
                    continue
                if cell[UNIT_BASE_INDEX] > 0.5 or cell[UNIT_BARRACKS_INDEX] > 0.5:
                    continue

                move_dir, _, reason = choose_safe_move_direction(obs, flat_idx, preferred_dirs=(1, 2, 0, 3))
                if move_dir is None:
                    skipped[f"family3_{reason or 'no_move'}"] += 1
                    continue

                obs2 = clear_action_context_on_cell(obs, flat_idx)
                obs2 = normalize_empty_cells_to_no_context(obs2)
                action2 = _set_move_target(act, flat_idx, move_dir, b2_vec, c3_vec)

                split = "train" if float(rng.random()) < train_ratio else "validation"
                for _ in range(max(1, movement_repeat_factor)):
                    _append_row(
                        collectors[split],
                        observation=obs2,
                        action=action2,
                        source_payload=train_payload,
                        source_sample_index=source_idx,
                    )
                    metadata[split].append(
                        _build_metadata_row(
                            family="family3_synthetic_rule_valid_move",
                            source="synthetic_rule_valid",
                            split=split,
                            source_split="train",
                            source_sample_index=source_idx,
                            source_step=-1,
                            unit_id=None,
                            unit_type="Worker" if cell[UNIT_WORKER_INDEX] > 0.5 else ("Light" if cell[UNIT_LIGHT_INDEX] > 0.5 else "Ranged"),
                            source_position=list(flat_to_xy(flat_idx)),
                            target_cell=flat_idx,
                            target_move_dir=move_dir,
                            target_action_type=ACTION_TYPE_MOVE,
                            target_cell_in_bounds=True,
                            target_cell_free=True,
                            target_cell_valid=True,
                            notes="synthetic move toward enemy-side preference with free adjacent target",
                        )
                    )
                    family_counter["family3_synthetic_rule_valid_move"] += 1
                    move_unit_counter["Worker" if cell[UNIT_WORKER_INDEX] > 0.5 else ("Light" if cell[UNIT_LIGHT_INDEX] > 0.5 else "Ranged")] += 1
                    move_dir_counter[{0: 'north', 1: 'east', 2: 'south', 3: 'west'}[int(move_dir)]] += 1
                    added_synth += 1
                if added_synth >= max_synthetic:
                    break

        # Family 4 rally near base.
        if added_synth < max_synthetic:
            base_cells = np.where((obs[:, OWNER_SELF_INDEX] > 0.5) & (obs[:, UNIT_BASE_INDEX] > 0.5))[0]
            if base_cells.size > 0:
                bx, by = flat_to_xy(int(base_cells[0]))
                for flat_idx in actor_cells.tolist():
                    if flat_idx == int(base_cells[0]):
                        continue
                    x, y = flat_to_xy(flat_idx)
                    if abs(x - bx) + abs(y - by) > 2:
                        continue
                    cell = obs[flat_idx]
                    if not (cell[UNIT_WORKER_INDEX] > 0.5 or cell[UNIT_LIGHT_INDEX] > 0.5 or cell[UNIT_RANGED_INDEX] > 0.5):
                        continue
                    preferred = [1, 2, 0, 3] if x <= bx or y <= by else [2, 1, 0, 3]
                    move_dir, _, reason = choose_safe_move_direction(obs, flat_idx, preferred_dirs=preferred)
                    if move_dir is None:
                        skipped[f"family4_{reason or 'no_move'}"] += 1
                        continue

                    obs2 = clear_action_context_on_cell(obs, flat_idx)
                    obs2 = normalize_empty_cells_to_no_context(obs2)
                    action2 = _set_move_target(act, flat_idx, move_dir, b2_vec, c3_vec)
                    split = "train" if float(rng.random()) < train_ratio else "validation"
                    _append_row(
                        collectors[split],
                        observation=obs2,
                        action=action2,
                        source_payload=train_payload,
                        source_sample_index=source_idx,
                    )
                    metadata[split].append(
                        _build_metadata_row(
                            family="family4_rally_advance_from_base",
                            source="synthetic_rally",
                            split=split,
                            source_split="train",
                            source_sample_index=source_idx,
                            source_step=-1,
                            unit_id=None,
                            unit_type="Worker" if cell[UNIT_WORKER_INDEX] > 0.5 else ("Light" if cell[UNIT_LIGHT_INDEX] > 0.5 else "Ranged"),
                            source_position=[x, y],
                            target_cell=flat_idx,
                            target_move_dir=move_dir,
                            target_action_type=ACTION_TYPE_MOVE,
                            target_cell_in_bounds=True,
                            target_cell_free=True,
                            target_cell_valid=True,
                            notes="rally/advance away from base and toward enemy quadrant",
                        )
                    )
                    family_counter["family4_rally_advance_from_base"] += 1
                    move_dir_counter[{0: 'north', 1: 'east', 2: 'south', 3: 'west'}[int(move_dir)]] += 1
                    move_unit_counter["Worker" if cell[UNIT_WORKER_INDEX] > 0.5 else ("Light" if cell[UNIT_LIGHT_INDEX] > 0.5 else "Ranged")] += 1
                    added_synth += 1
                    if added_synth >= max_synthetic:
                        break

        if added_neg < negative_controls:
            # Family 5 negative controls: keep original labels for blocked/noop/harvest/base patterns.
            action_type = act[:, 0]
            for flat_idx in actor_cells.tolist():
                if added_neg >= negative_controls:
                    break
                cell = obs[flat_idx]
                a = int(action_type[flat_idx])
                keep = False
                notes = ""
                if (cell[UNIT_BASE_INDEX] > 0.5) and (a in {ACTION_TYPE_NOOP, ACTION_TYPE_PRODUCE}):
                    keep = True
                    notes = "base_noop_or_produce_preserved"
                elif (cell[UNIT_WORKER_INDEX] > 0.5) and (a == ACTION_TYPE_HARVEST):
                    keep = True
                    notes = "worker_harvest_preserved"
                elif a == ACTION_TYPE_NOOP:
                    move_dir, _, _ = choose_safe_move_direction(obs, flat_idx, preferred_dirs=(1, 2, 0, 3))
                    if move_dir is None:
                        keep = True
                        notes = "blocked_unit_noop_preserved"

                if not keep:
                    continue

                obs2 = normalize_empty_cells_to_no_context(obs)
                action2 = np.asarray(act, dtype=np.int16).copy()
                action2[B2_FLAT, :] = np.asarray(b2_vec, dtype=np.int16)
                action2[C3_FLAT, :] = np.asarray(c3_vec, dtype=np.int16)

                split = "train" if float(rng.random()) < train_ratio else "validation"
                _append_row(
                    collectors[split],
                    observation=obs2,
                    action=action2,
                    source_payload=train_payload,
                    source_sample_index=source_idx,
                )
                metadata[split].append(
                    _build_metadata_row(
                        family="family5_negative_controls",
                        source="negative_controls",
                        split=split,
                        source_split="train",
                        source_sample_index=source_idx,
                        source_step=-1,
                        unit_id=None,
                        unit_type="Base" if cell[UNIT_BASE_INDEX] > 0.5 else "Worker",
                        source_position=list(flat_to_xy(flat_idx)),
                        target_cell=flat_idx,
                        target_move_dir=-1,
                        target_action_type=int(a),
                        target_cell_in_bounds=True,
                        target_cell_free=False,
                        target_cell_valid=True,
                        notes=notes,
                    )
                )
                family_counter["family5_negative_controls"] += 1
                added_neg += 1

        if added_synth >= max_synthetic and added_neg >= negative_controls:
            break

    return added_synth, added_neg


def main() -> int:
    args = parse_args()
    rng = np.random.default_rng(int(args.seed))

    base_dir = resolve_path(args.base_bc_ready_dir).resolve()
    stage10d7_dir = resolve_path(args.stage10d7_bc_ready_dir).resolve()
    out_dir = (resolve_path(args.output_root).resolve() / f"{args.run_label}_{utc_dir_stamp()}")
    if out_dir.exists():
        raise RuntimeError(f"Refusing overwrite: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=False)

    train_payload = ensure_payload_defaults(load_split_payload(base_dir / "bc_train.npz"), n_samples=0)
    val_payload = ensure_payload_defaults(load_split_payload(base_dir / "bc_validation.npz"), n_samples=0)
    train_obs, train_actions = get_observations_and_actions(train_payload)
    val_obs, val_actions = get_observations_and_actions(val_payload)

    train_payload = ensure_payload_defaults(train_payload, train_obs.shape[0])
    val_payload = ensure_payload_defaults(val_payload, val_obs.shape[0])

    b2_vec, c3_vec = pick_reference_action_vectors(train_actions)

    collectors = {
        "train": _init_collector(),
        "validation": _init_collector(),
    }
    metadata = {
        "train": [],
        "validation": [],
    }

    family_counter: Counter[str] = Counter()
    move_unit_counter: Counter[str] = Counter()
    move_dir_counter: Counter[str] = Counter()
    skipped: Counter[str] = Counter()

    added_family1 = _build_runtime_family(
        max_samples=int(args.max_runtime_move_aug_samples),
        movement_repeat_factor=int(args.movement_repeat_factor),
        trace_jsonl=resolve_path(args.stage10d16_trace_jsonl).resolve(),
        lifecycle_json=resolve_path(args.stage10d16_lifecycle_json).resolve(),
        train_obs=train_obs,
        train_actions=train_actions,
        train_payload=train_payload,
        b2_vec=b2_vec,
        c3_vec=c3_vec,
        rng=rng,
        collectors=collectors,
        metadata=metadata,
        family_counter=family_counter,
        move_unit_counter=move_unit_counter,
        move_dir_counter=move_dir_counter,
        skipped=skipped,
        train_ratio=float(args.train_ratio),
    )

    stage10d7_train_payload = ensure_payload_defaults(load_split_payload(stage10d7_dir / "bc_train.npz"), n_samples=0)
    stage10d7_val_payload = ensure_payload_defaults(load_split_payload(stage10d7_dir / "bc_validation.npz"), n_samples=0)
    d7_train_obs, d7_train_actions = get_observations_and_actions(stage10d7_train_payload)
    d7_val_obs, d7_val_actions = get_observations_and_actions(stage10d7_val_payload)

    stage10d7_train_payload = ensure_payload_defaults(stage10d7_train_payload, d7_train_obs.shape[0])
    stage10d7_val_payload = ensure_payload_defaults(stage10d7_val_payload, d7_val_obs.shape[0])

    added_family2 = _build_family2_move_refs(
        datasets=[
            ("stage10d14_train", train_obs, train_actions, train_payload),
            ("stage10d14_validation", val_obs, val_actions, val_payload),
            ("stage10d7_train", d7_train_obs, d7_train_actions, stage10d7_train_payload),
            ("stage10d7_validation", d7_val_obs, d7_val_actions, stage10d7_val_payload),
        ],
        max_samples=max(0, int(args.max_synthetic_move_aug_samples // 2)),
        movement_repeat_factor=int(args.movement_repeat_factor),
        b2_vec=b2_vec,
        c3_vec=c3_vec,
        rng=rng,
        collectors=collectors,
        metadata=metadata,
        family_counter=family_counter,
        move_unit_counter=move_unit_counter,
        move_dir_counter=move_dir_counter,
        skipped=skipped,
        train_ratio=float(args.train_ratio),
    )

    added_synth, added_neg = _build_family3_family4_family5(
        train_obs=train_obs,
        train_actions=train_actions,
        train_payload=train_payload,
        max_synthetic=max(0, int(args.max_synthetic_move_aug_samples - added_family2)),
        negative_controls=max(0, int(args.negative_control_samples)),
        movement_repeat_factor=int(args.movement_repeat_factor),
        b2_vec=b2_vec,
        c3_vec=c3_vec,
        rng=rng,
        collectors=collectors,
        metadata=metadata,
        family_counter=family_counter,
        move_unit_counter=move_unit_counter,
        move_dir_counter=move_dir_counter,
        skipped=skipped,
        train_ratio=float(args.train_ratio),
    )

    augmented_train = _stack_collector(collectors["train"])
    augmented_val = _stack_collector(collectors["validation"])

    merged_train = merge_original_and_augmented(train_payload, augmented_train, split_name="train")
    merged_val = merge_original_and_augmented(val_payload, augmented_val, split_name="validation")

    train_path = save_split_npz(out_dir / "bc_train.npz", merged_train)
    val_path = save_split_npz(out_dir / "bc_validation.npz", merged_val)

    # Build debug split from first augmented train+val samples.
    debug_obs = np.concatenate([augmented_train["observations"], augmented_val["observations"]], axis=0)
    debug_actions = np.concatenate([augmented_train["actions"], augmented_val["actions"]], axis=0)
    debug_n = min(256, int(debug_obs.shape[0]))
    debug_payload = {
        "observations": np.asarray(debug_obs[:debug_n], dtype=np.float32),
        "actions": np.asarray(debug_actions[:debug_n], dtype=np.int16),
        "input_tensor": np.asarray(debug_obs[:debug_n], dtype=np.float32),
        "target_action_branches": np.asarray(debug_actions[:debug_n], dtype=np.int16),
        "sample_id": np.arange(debug_n, dtype=np.int64),
        "episode_id": np.zeros((debug_n,), dtype=np.int32),
        "step_id": np.zeros((debug_n,), dtype=np.int32),
        "source_episode_file": np.full((debug_n,), "stage10d17_debug", dtype="<U32"),
        "target_action_branch_sizes": np.asarray((6, 4, 4, 4, 4, 7, 49), dtype=np.int64),
        "schema_version": np.asarray(["day6.bc_ready.v1"], dtype="<U32"),
        "split": np.asarray(["debug"], dtype="<U16"),
    }
    debug_path = save_split_npz(out_dir / "bc_debug.npz", debug_payload)

    metadata_train_path = write_jsonl(out_dir / "stage10d17_augmented_sample_metadata_train.jsonl", metadata["train"])
    metadata_val_path = write_jsonl(out_dir / "stage10d17_augmented_sample_metadata_validation.jsonl", metadata["validation"])

    original_train_dist = summarize_action_type_distribution(train_obs, train_actions)
    original_val_dist = summarize_action_type_distribution(val_obs, val_actions)
    merged_train_dist = summarize_action_type_distribution(merged_train["observations"], merged_train["actions"])
    merged_val_dist = summarize_action_type_distribution(merged_val["observations"], merged_val["actions"])

    augmentation_manifest: Dict[str, Any] = {
        "stage": "10D.17",
        "task": "movement_label_augmentation",
        "generated_at_utc": utc_now_iso(),
        "base_dataset_path": str(base_dir.as_posix()),
        "stage10d7_dataset_path": str(stage10d7_dir.as_posix()),
        "stage10d16_trace_jsonl": str(resolve_path(args.stage10d16_trace_jsonl).resolve().as_posix()),
        "stage10d16_lifecycle_json": str(resolve_path(args.stage10d16_lifecycle_json).resolve().as_posix()),
        "output_dataset_path": str(out_dir.as_posix()),
        "output_files": {
            "bc_train": str(train_path.as_posix()),
            "bc_validation": str(val_path.as_posix()),
            "bc_debug": str(debug_path.as_posix()),
            "metadata_train_jsonl": str(metadata_train_path.as_posix()),
            "metadata_validation_jsonl": str(metadata_val_path.as_posix()),
        },
        "counts": {
            "original_train": int(train_obs.shape[0]),
            "original_validation": int(val_obs.shape[0]),
            "augmented_train": int(augmented_train["observations"].shape[0]),
            "augmented_validation": int(augmented_val["observations"].shape[0]),
            "merged_train": int(merged_train["observations"].shape[0]),
            "merged_validation": int(merged_val["observations"].shape[0]),
            "family1_runtime_added": int(added_family1),
            "family2_move_reference_added": int(added_family2),
            "family3_4_synthetic_added": int(added_synth),
            "family5_negative_control_added": int(added_neg),
        },
        "family_counts": {k: int(v) for k, v in sorted(family_counter.items())},
        "move_counts": {
            "by_unit_type": {k: int(v) for k, v in sorted(move_unit_counter.items())},
            "by_direction": {k: int(v) for k, v in sorted(move_dir_counter.items())},
            "before_train_move_actor": int(original_train_dist["actor_action_type_counts"]["Move"]),
            "after_train_move_actor": int(merged_train_dist["actor_action_type_counts"]["Move"]),
            "before_val_move_actor": int(original_val_dist["actor_action_type_counts"]["Move"]),
            "after_val_move_actor": int(merged_val_dist["actor_action_type_counts"]["Move"]),
        },
        "negative_control_count": int(added_neg),
        "skipped_samples": {k: int(v) for k, v in sorted(skipped.items())},
        "explicit_non_claims": [
            "No PPO.",
            "No teacher checkpoint mutation.",
            "No runtime movement forcing.",
            "No ActionDecoder/ActionApplier/MatchManager semantic changes.",
            "No runtime action remap fallback.",
        ],
        "notes": [
            "Family1 uses Stage10D16 trace/lifecycle-derived runtime proxy because raw per-step full observation snapshots are not available under reports/tmp.",
            "Observation/action contract kept at [24,24,27] and [576,7] with branch sizes [6,4,4,4,4,7,49].",
        ],
    }

    write_json(out_dir / "stage10d17_movement_augmentation_manifest.json", augmentation_manifest)

    base_manifest = load_json(base_dir / "bc_manifest.json")
    bc_manifest = dict(base_manifest)
    bc_manifest["generated_at_utc"] = utc_now_iso()
    bc_manifest["source_stage"] = "10D.17"
    bc_manifest["num_train"] = int(merged_train["observations"].shape[0])
    bc_manifest["num_validation"] = int(merged_val["observations"].shape[0])
    bc_manifest["num_debug"] = int(debug_n)
    bc_manifest["source_bc_ready_dir"] = str(base_dir.as_posix())
    bc_manifest["stage10d17_movement_augmentation_manifest"] = str((out_dir / "stage10d17_movement_augmentation_manifest.json").as_posix())
    bc_manifest["stage10d17_metadata_sidecars"] = {
        "train": str(metadata_train_path.as_posix()),
        "validation": str(metadata_val_path.as_posix()),
    }
    bc_manifest["explicit_non_claims"] = [
        "No PPO",
        "No teacher mutation",
        "No Stage10D14 checkpoint mutation",
        "No runtime movement forcing",
        "No decoder/applier semantic mutation",
    ]

    write_json(out_dir / "bc_manifest.json", bc_manifest)

    print(out_dir.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
