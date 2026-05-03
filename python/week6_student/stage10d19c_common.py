from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import numpy as np
import torch

from stage10d14_common import load_model_strict
from stage10d19m_common import (
    ACTION_TYPE_ATTACK,
    ACTION_TYPE_HARVEST,
    ACTION_TYPE_MOVE,
    ACTION_TYPE_NAMES,
    ACTION_TYPE_NOOP,
    ACTION_TYPE_PRODUCE,
    N_CELLS,
    OBS_OWNER_SELF_INDEX,
    OBS_UNIT_BASE_INDEX,
    OBS_UNIT_BARRACKS_INDEX,
    OBS_UNIT_HEAVY_INDEX,
    OBS_UNIT_LIGHT_INDEX,
    OBS_UNIT_RANGED_INDEX,
    OBS_UNIT_RESOURCE_INDEX,
    OBS_UNIT_SLICE,
    OBS_UNIT_WORKER_INDEX,
    StepMaskBundle,
    actor_mask_from_obs,
    apply_masked_selection_for_cell,
    model_forward_logits,
)

MAP_W = 24
MAP_H = 24

MOVE_DELTAS = {
    0: (0, -1),
    1: (1, 0),
    2: (0, 1),
    3: (-1, 0),
}

DIR_NAME_TO_INDEX = {
    "north": 0,
    "east": 1,
    "south": 2,
    "west": 3,
}

ACTION_NAME_TO_INDEX = {
    "NoOp": ACTION_TYPE_NOOP,
    "Move": ACTION_TYPE_MOVE,
    "Harvest": ACTION_TYPE_HARVEST,
    "Return": 3,
    "Produce": ACTION_TYPE_PRODUCE,
    "Attack": ACTION_TYPE_ATTACK,
}

UNIT_NAME_TO_CHANNEL = {
    "Resource": OBS_UNIT_RESOURCE_INDEX,
    "Base": OBS_UNIT_BASE_INDEX,
    "Barracks": OBS_UNIT_BARRACKS_INDEX,
    "Worker": OBS_UNIT_WORKER_INDEX,
    "Light": OBS_UNIT_LIGHT_INDEX,
    "Heavy": OBS_UNIT_HEAVY_INDEX,
    "Ranged": OBS_UNIT_RANGED_INDEX,
}

MOVABLE_UNIT_NAMES = {"Worker", "Light", "Heavy", "Ranged"}


@dataclass(frozen=True)
class FailureEvalMetrics:
    checkpoint: str
    cases_evaluated: int
    reconstruction_partial: bool
    unmasked_move_predictions: int
    masked_move_predictions: int
    unmasked_occupied_or_invalid_move_count: int
    masked_occupied_or_invalid_move_count: int
    invalid_move_to_noop_count: int
    invalid_move_to_valid_move_count: int
    valid_alternative_move_selected_count: int
    no_valid_alt_noop_selected_count: int
    off_actor_non_noop_count_unmasked: int
    off_actor_non_noop_count_masked: int
    movement_suppressed_count: int
    mask_changed_action_count: int
    mask_changed_action_breakdown: Dict[str, int]
    b2_guard_harvest_gt_noop_rate: float
    c3_guard_produce_gt_noop_rate: float


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (repo_root() / p)


def utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_dir_stamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: str | Path) -> Dict[str, Any]:
    p = resolve_path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return json.loads(p.read_text(encoding="utf-8-sig"))


def write_json(path: str | Path, payload: Mapping[str, Any]) -> Path:
    p = resolve_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return p


def read_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    p = resolve_path(path)
    rows: List[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: str | Path, rows: Iterable[Mapping[str, Any]]) -> Path:
    p = resolve_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(dict(row), ensure_ascii=True) + "\n")
    return p


def flat_to_xy(flat_idx: int) -> tuple[int, int]:
    return int(flat_idx % MAP_W), int(flat_idx // MAP_W)


def xy_to_flat(x: int, y: int) -> int:
    return int(y * MAP_W + x)


def in_bounds(x: int, y: int) -> bool:
    return 0 <= x < MAP_W and 0 <= y < MAP_H


def move_target(source_flat: int, move_dir: int) -> tuple[int | None, bool]:
    if int(move_dir) not in MOVE_DELTAS:
        return None, False
    x, y = flat_to_xy(source_flat)
    dx, dy = MOVE_DELTAS[int(move_dir)]
    nx, ny = x + dx, y + dy
    if not in_bounds(nx, ny):
        return None, False
    return xy_to_flat(nx, ny), True


def _action_name_to_index(name: str) -> int:
    n = str(name or "").strip()
    return int(ACTION_NAME_TO_INDEX.get(n, ACTION_TYPE_NOOP))


def _unit_name_to_channel(unit_type: str) -> int:
    return int(UNIT_NAME_TO_CHANNEL.get(str(unit_type or ""), OBS_UNIT_WORKER_INDEX))


def index_trace_by_step(trace_rows: Sequence[Mapping[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    by_step: Dict[int, List[Dict[str, Any]]] = {}
    for row in trace_rows:
        step = int(row.get("step", -1))
        if step < 0:
            continue
        units = row.get("friendly_units", [])
        if not isinstance(units, list):
            continue
        by_step[step] = [dict(u) for u in units if isinstance(u, Mapping)]
    return by_step


def find_unit_record(step_units: Sequence[Mapping[str, Any]], unit_id: str) -> Mapping[str, Any] | None:
    uid = str(unit_id)
    for u in step_units:
        if str(u.get("unit_id", "")) == uid:
            return u
    return None


def reconstruct_obs_flat_from_step_units(step_units: Sequence[Mapping[str, Any]]) -> np.ndarray:
    obs = np.zeros((N_CELLS, 27), dtype=np.float32)
    obs[:, 2] = 1.0  # default neutral owner channel

    for unit in step_units:
        x = int(unit.get("x", -1))
        y = int(unit.get("y", -1))
        if not in_bounds(x, y):
            continue
        flat = int(unit.get("flat_index", xy_to_flat(x, y)))
        if flat < 0 or flat >= N_CELLS:
            flat = xy_to_flat(x, y)

        obs[flat, 2:5] = 0.0
        obs[flat, OBS_OWNER_SELF_INDEX] = 1.0
        obs[flat, OBS_UNIT_SLICE] = 0.0
        obs[flat, _unit_name_to_channel(str(unit.get("unit_type", "Worker")))] = 1.0

        # Preserve lightweight action context from trace predictions when available.
        obs[flat, 12:18] = 0.0
        act_idx = _action_name_to_index(str(unit.get("predicted_action_type", "NoOp")))
        obs[flat, 12 + act_idx] = 1.0

        obs[flat, 18:22] = 0.0
        move_dir = int(unit.get("move_dir", 0))
        if move_dir in (0, 1, 2, 3):
            obs[flat, 18 + move_dir] = 1.0

        obs[flat, 22:26] = 0.0
        produce_type = int(unit.get("produce_unit_type", 0))
        if 0 <= produce_type < 7:
            obs[flat, 22 + min(3, produce_type % 4)] = 1.0

        attack_local = int(unit.get("attack_target_local", 0))
        obs[flat, 26] = float(max(0, min(48, attack_local)) / 48.0)

    return obs


def friendly_occupancy_from_step_units(step_units: Sequence[Mapping[str, Any]]) -> set[int]:
    occ: set[int] = set()
    for unit in step_units:
        flat = int(unit.get("flat_index", -1))
        if 0 <= flat < N_CELLS:
            occ.add(flat)
            continue
        x = int(unit.get("x", -1))
        y = int(unit.get("y", -1))
        if in_bounds(x, y):
            occ.add(xy_to_flat(x, y))
    return occ


def infer_alternative_free_dirs(source_flat: int, occupied_flats: set[int]) -> List[int]:
    out: List[int] = []
    for d in (0, 1, 2, 3):
        tgt, ok = move_target(source_flat, d)
        if (not ok) or tgt is None:
            continue
        if tgt in occupied_flats:
            continue
        out.append(int(d))
    return out


def build_mask_bundle_from_obs(obs_flat: np.ndarray) -> StepMaskBundle:
    obs = np.asarray(obs_flat, dtype=np.float32)

    action_type_mask = np.zeros((N_CELLS, 6), dtype=bool)
    move_dir_mask = np.zeros((N_CELLS, 4), dtype=bool)
    harvest_dir_mask = np.zeros((N_CELLS, 4), dtype=bool)
    return_dir_mask = np.zeros((N_CELLS, 4), dtype=bool)
    produce_dir_mask = np.zeros((N_CELLS, 4), dtype=bool)
    produce_unit_type_mask = np.zeros((N_CELLS, 7), dtype=bool)
    attack_target_local_mask = np.zeros((N_CELLS, 49), dtype=bool)

    unit_sum = np.sum(obs[:, OBS_UNIT_SLICE], axis=1)

    for flat in range(N_CELLS):
        action_type_mask[flat, ACTION_TYPE_NOOP] = True

        is_actor = bool(float(obs[flat, OBS_OWNER_SELF_INDEX]) > 0.5 and unit_sum[flat] > 1e-6)
        if not is_actor:
            continue

        unit_type = int(np.argmax(obs[flat, OBS_UNIT_SLICE])) + OBS_UNIT_SLICE.start
        x, y = flat_to_xy(flat)

        if unit_type in (_unit_name_to_channel("Worker"), _unit_name_to_channel("Light"), _unit_name_to_channel("Heavy"), _unit_name_to_channel("Ranged")):
            for d, (dx, dy) in MOVE_DELTAS.items():
                nx, ny = x + dx, y + dy
                if not in_bounds(nx, ny):
                    continue
                nf = xy_to_flat(nx, ny)
                if float(unit_sum[nf]) <= 1e-6:
                    move_dir_mask[flat, d] = True
            if bool(np.any(move_dir_mask[flat])):
                action_type_mask[flat, ACTION_TYPE_MOVE] = True

        if unit_type == _unit_name_to_channel("Worker"):
            for d, (dx, dy) in MOVE_DELTAS.items():
                nx, ny = x + dx, y + dy
                if not in_bounds(nx, ny):
                    continue
                nf = xy_to_flat(nx, ny)
                if float(obs[nf, OBS_UNIT_RESOURCE_INDEX]) > 0.5:
                    harvest_dir_mask[flat, d] = True
            if bool(np.any(harvest_dir_mask[flat])):
                action_type_mask[flat, ACTION_TYPE_HARVEST] = True

        if unit_type in (_unit_name_to_channel("Base"), _unit_name_to_channel("Barracks")):
            for d, (dx, dy) in MOVE_DELTAS.items():
                nx, ny = x + dx, y + dy
                if not in_bounds(nx, ny):
                    continue
                nf = xy_to_flat(nx, ny)
                if float(unit_sum[nf]) <= 1e-6:
                    produce_dir_mask[flat, d] = True
            if unit_type == _unit_name_to_channel("Base"):
                produce_unit_type_mask[flat, 3] = True
            else:
                produce_unit_type_mask[flat, 4] = True
                produce_unit_type_mask[flat, 5] = True
                produce_unit_type_mask[flat, 6] = True
            if bool(np.any(produce_dir_mask[flat])) and bool(np.any(produce_unit_type_mask[flat])):
                action_type_mask[flat, ACTION_TYPE_PRODUCE] = True

    return StepMaskBundle(
        step=0,
        action_type_mask=action_type_mask,
        move_dir_mask=move_dir_mask,
        harvest_dir_mask=harvest_dir_mask,
        return_dir_mask=return_dir_mask,
        produce_dir_mask=produce_dir_mask,
        produce_unit_type_mask=produce_unit_type_mask,
        attack_target_local_mask=attack_target_local_mask,
        approximation_notes=[
            "Reconstructed from Stage10D.18RR friendly-unit trace only; enemy/resource occupancy may be partial.",
            "Mask is diagnostic/pre-selection only; runtime decoder/applier/matchmanager stay authoritative.",
        ],
    )


def _is_move_invalid_for_obs(obs_flat: np.ndarray, source_flat: int, move_dir: int) -> bool:
    tgt, ok = move_target(source_flat, int(move_dir))
    if (not ok) or tgt is None:
        return True
    occ = float(np.sum(np.asarray(obs_flat, dtype=np.float32)[tgt, OBS_UNIT_SLICE])) > 1e-6
    return bool(occ)


def evaluate_checkpoint_on_failure_cases(
    *,
    checkpoint_path: str | Path,
    failure_cases: Sequence[Mapping[str, Any]],
    trace_by_step: Mapping[int, Sequence[Mapping[str, Any]]],
    device: torch.device,
    batch_size: int = 64,
) -> tuple[FailureEvalMetrics, Dict[str, Any]]:
    model = load_model_strict(checkpoint_path, device=device)

    obs_rows: List[np.ndarray] = []
    src_cells: List[int] = []
    case_indices: List[int] = []
    bundles: List[StepMaskBundle] = []
    no_valid_alt_flags: List[bool] = []
    has_valid_alt_flags: List[bool] = []

    missing_steps = 0
    for i, case in enumerate(failure_cases):
        step = int(case.get("step", -1))
        src = int((case.get("source_cell") or {}).get("flat", -1))
        if step < 0 or src < 0:
            continue
        units = trace_by_step.get(step, [])
        if not units:
            missing_steps += 1
            continue
        obs = reconstruct_obs_flat_from_step_units(units)
        bundle = build_mask_bundle_from_obs(obs)

        obs_rows.append(obs)
        src_cells.append(src)
        case_indices.append(i)
        bundles.append(bundle)

        alts = case.get("alternative_free_dirs") or []
        has_valid_alt_flags.append(bool(len(alts) > 0))
        no_valid_alt_flags.append(bool(len(alts) == 0))

    if not obs_rows:
        empty = FailureEvalMetrics(
            checkpoint=str(resolve_path(checkpoint_path).as_posix()),
            cases_evaluated=0,
            reconstruction_partial=True,
            unmasked_move_predictions=0,
            masked_move_predictions=0,
            unmasked_occupied_or_invalid_move_count=0,
            masked_occupied_or_invalid_move_count=0,
            invalid_move_to_noop_count=0,
            invalid_move_to_valid_move_count=0,
            valid_alternative_move_selected_count=0,
            no_valid_alt_noop_selected_count=0,
            off_actor_non_noop_count_unmasked=0,
            off_actor_non_noop_count_masked=0,
            movement_suppressed_count=0,
            mask_changed_action_count=0,
            mask_changed_action_breakdown={},
            b2_guard_harvest_gt_noop_rate=0.0,
            c3_guard_produce_gt_noop_rate=0.0,
        )
        detail = {
            "reconstruction_missing_steps": int(missing_steps),
            "case_count_in": int(len(failure_cases)),
            "rows_used": 0,
        }
        return empty, detail

    obs_batch = np.asarray(obs_rows, dtype=np.float32).reshape((-1, 24, 24, 27))
    logits = model_forward_logits(model, obs_batch, device=device, batch_size=int(batch_size))

    action_unmasked = np.argmax(logits["action_type_logits"], axis=-1).astype(np.int64)
    move_unmasked = np.argmax(logits["move_dir_logits"], axis=-1).astype(np.int64)

    action_masked = np.zeros_like(action_unmasked)
    move_masked = np.zeros_like(move_unmasked)

    changed_count = 0
    changed_breakdown: Counter[str] = Counter()

    inv_to_noop = 0
    inv_to_valid_move = 0
    valid_alt_move_selected = 0
    no_valid_alt_noop_selected = 0
    unmasked_moves = 0
    masked_moves = 0
    unmasked_invalid = 0
    masked_invalid = 0
    movement_suppressed = 0

    b2_guard_ok = 0
    c3_guard_ok = 0

    for i, src in enumerate(src_cells):
        cell_logits = {
            "action_type_logits": logits["action_type_logits"][i, src],
            "move_dir_logits": logits["move_dir_logits"][i, src],
            "harvest_dir_logits": logits["harvest_dir_logits"][i, src],
            "return_dir_logits": logits["return_dir_logits"][i, src],
            "produce_dir_logits": logits["produce_dir_logits"][i, src],
            "produce_unit_type_logits": logits["produce_unit_type_logits"][i, src],
            "attack_target_local_logits": logits["attack_target_local_logits"][i, src],
        }
        masked_pred = apply_masked_selection_for_cell(cell_logits, bundles[i], src)
        action_masked[i, src] = int(masked_pred["action_type"])
        move_masked[i, src] = int(masked_pred.get("move_dir", 0))

        ua = int(action_unmasked[i, src])
        ma = int(action_masked[i, src])

        if ua == ACTION_TYPE_MOVE:
            unmasked_moves += 1
            if _is_move_invalid_for_obs(obs_rows[i], src, int(move_unmasked[i, src])):
                unmasked_invalid += 1
        if ma == ACTION_TYPE_MOVE:
            masked_moves += 1
            if _is_move_invalid_for_obs(obs_rows[i], src, int(move_masked[i, src])):
                masked_invalid += 1

        if ua == ACTION_TYPE_MOVE and _is_move_invalid_for_obs(obs_rows[i], src, int(move_unmasked[i, src])):
            if ma == ACTION_TYPE_NOOP:
                inv_to_noop += 1
                changed_breakdown["invalid Move -> NoOp"] += 1
            elif ma == ACTION_TYPE_MOVE and (not _is_move_invalid_for_obs(obs_rows[i], src, int(move_masked[i, src]))):
                inv_to_valid_move += 1
                changed_breakdown["invalid Move -> valid Move"] += 1

        if ma != ua:
            changed_count += 1
            if not (ua == ACTION_TYPE_MOVE and ma in (ACTION_TYPE_NOOP, ACTION_TYPE_MOVE)):
                changed_breakdown["other"] += 1

        if ua == ACTION_TYPE_MOVE and ma != ACTION_TYPE_MOVE:
            movement_suppressed += 1

        if has_valid_alt_flags[i] and ma == ACTION_TYPE_MOVE and (not _is_move_invalid_for_obs(obs_rows[i], src, int(move_masked[i, src]))):
            valid_alt_move_selected += 1

        if no_valid_alt_flags[i] and ma == ACTION_TYPE_NOOP:
            no_valid_alt_noop_selected += 1

        b2_logits = np.asarray(logits["action_type_logits"][i, 25], dtype=np.float32)
        c3_logits = np.asarray(logits["action_type_logits"][i, 50], dtype=np.float32)
        b2_exp = np.exp(b2_logits - np.max(b2_logits))
        c3_exp = np.exp(c3_logits - np.max(c3_logits))
        b2_p = b2_exp / np.maximum(np.sum(b2_exp), 1e-12)
        c3_p = c3_exp / np.maximum(np.sum(c3_exp), 1e-12)
        if float(b2_p[ACTION_TYPE_HARVEST]) > float(b2_p[ACTION_TYPE_NOOP]):
            b2_guard_ok += 1
        if float(c3_p[ACTION_TYPE_PRODUCE]) > float(c3_p[ACTION_TYPE_NOOP]):
            c3_guard_ok += 1

    actor_mask = actor_mask_from_obs(np.asarray(obs_rows, dtype=np.float32))

    # Fill masked arrays for non-source cells with unmasked actions to count off-actor risk across full maps.
    action_masked_full = np.asarray(action_unmasked, dtype=np.int64).copy()
    for i, src in enumerate(src_cells):
        action_masked_full[i, src] = action_masked[i, src]

    off_actor_unmasked = int(np.sum(action_unmasked[~actor_mask] != ACTION_TYPE_NOOP))
    off_actor_masked = int(np.sum(action_masked_full[~actor_mask] != ACTION_TYPE_NOOP))

    metrics = FailureEvalMetrics(
        checkpoint=str(resolve_path(checkpoint_path).as_posix()),
        cases_evaluated=int(len(obs_rows)),
        reconstruction_partial=bool(missing_steps > 0),
        unmasked_move_predictions=int(unmasked_moves),
        masked_move_predictions=int(masked_moves),
        unmasked_occupied_or_invalid_move_count=int(unmasked_invalid),
        masked_occupied_or_invalid_move_count=int(masked_invalid),
        invalid_move_to_noop_count=int(inv_to_noop),
        invalid_move_to_valid_move_count=int(inv_to_valid_move),
        valid_alternative_move_selected_count=int(valid_alt_move_selected),
        no_valid_alt_noop_selected_count=int(no_valid_alt_noop_selected),
        off_actor_non_noop_count_unmasked=int(off_actor_unmasked),
        off_actor_non_noop_count_masked=int(off_actor_masked),
        movement_suppressed_count=int(movement_suppressed),
        mask_changed_action_count=int(changed_count),
        mask_changed_action_breakdown={k: int(v) for k, v in changed_breakdown.items()},
        b2_guard_harvest_gt_noop_rate=float(b2_guard_ok / max(1, len(obs_rows))),
        c3_guard_produce_gt_noop_rate=float(c3_guard_ok / max(1, len(obs_rows))),
    )

    detail = {
        "reconstruction_missing_steps": int(missing_steps),
        "case_count_in": int(len(failure_cases)),
        "rows_used": int(len(obs_rows)),
        "action_type_unmasked_distribution": {
            ACTION_TYPE_NAMES[a]: int(np.sum(action_unmasked[np.arange(len(src_cells)), src_cells] == a))
            for a in range(6)
        },
        "action_type_masked_distribution": {
            ACTION_TYPE_NAMES[a]: int(sum(1 for i, src in enumerate(src_cells) if int(action_masked[i, src]) == a))
            for a in range(6)
        },
    }

    return metrics, detail


def to_serializable_metrics(metrics: FailureEvalMetrics) -> Dict[str, Any]:
    return {
        "checkpoint": metrics.checkpoint,
        "cases_evaluated": int(metrics.cases_evaluated),
        "reconstruction_partial": bool(metrics.reconstruction_partial),
        "unmasked_move_predictions": int(metrics.unmasked_move_predictions),
        "masked_move_predictions": int(metrics.masked_move_predictions),
        "unmasked_occupied_or_invalid_move_count": int(metrics.unmasked_occupied_or_invalid_move_count),
        "masked_occupied_or_invalid_move_count": int(metrics.masked_occupied_or_invalid_move_count),
        "invalid_move_to_noop_count": int(metrics.invalid_move_to_noop_count),
        "invalid_move_to_valid_move_count": int(metrics.invalid_move_to_valid_move_count),
        "valid_alternative_move_selected_count": int(metrics.valid_alternative_move_selected_count),
        "no_valid_alt_noop_selected_count": int(metrics.no_valid_alt_noop_selected_count),
        "off_actor_non_noop_count_unmasked": int(metrics.off_actor_non_noop_count_unmasked),
        "off_actor_non_noop_count_masked": int(metrics.off_actor_non_noop_count_masked),
        "movement_suppressed_count": int(metrics.movement_suppressed_count),
        "mask_changed_action_count": int(metrics.mask_changed_action_count),
        "mask_changed_action_breakdown": {k: int(v) for k, v in metrics.mask_changed_action_breakdown.items()},
        "b2_guard_harvest_gt_noop_rate": float(metrics.b2_guard_harvest_gt_noop_rate),
        "c3_guard_produce_gt_noop_rate": float(metrics.c3_guard_produce_gt_noop_rate),
    }
