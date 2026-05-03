from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

import numpy as np
import torch

from stage10d14_common import load_model_strict

MAP_W = 24
MAP_H = 24
N_CELLS = MAP_W * MAP_H

ACTION_TYPE_NOOP = 0
ACTION_TYPE_MOVE = 1
ACTION_TYPE_HARVEST = 2
ACTION_TYPE_RETURN = 3
ACTION_TYPE_PRODUCE = 4
ACTION_TYPE_ATTACK = 5

ACTION_TYPE_NAMES = {
    ACTION_TYPE_NOOP: "NoOp",
    ACTION_TYPE_MOVE: "Move",
    ACTION_TYPE_HARVEST: "Harvest",
    ACTION_TYPE_RETURN: "Return",
    ACTION_TYPE_PRODUCE: "Produce",
    ACTION_TYPE_ATTACK: "Attack",
}

OBS_OWNER_SELF_INDEX = 3
OBS_UNIT_SLICE = slice(5, 12)
OBS_UNIT_BASE_INDEX = 6
OBS_UNIT_BARRACKS_INDEX = 7
OBS_UNIT_WORKER_INDEX = 8
OBS_UNIT_LIGHT_INDEX = 9
OBS_UNIT_HEAVY_INDEX = 10
OBS_UNIT_RANGED_INDEX = 11
OBS_UNIT_RESOURCE_INDEX = 5

MOVE_DELTAS = {
    0: (0, -1),
    1: (1, 0),
    2: (0, 1),
    3: (-1, 0),
}

PRODUCE_WORKER = 3
PRODUCE_LIGHT = 4
PRODUCE_HEAVY = 5
PRODUCE_RANGED = 6

MOVABLE_UNITS = {"Worker", "Light", "Heavy", "Ranged"}
COMBAT_UNITS = {"Worker", "Light", "Heavy", "Ranged"}


@dataclass(frozen=True)
class StepMaskBundle:
    step: int
    action_type_mask: np.ndarray
    move_dir_mask: np.ndarray
    harvest_dir_mask: np.ndarray
    return_dir_mask: np.ndarray
    produce_dir_mask: np.ndarray
    produce_unit_type_mask: np.ndarray
    attack_target_local_mask: np.ndarray
    approximation_notes: List[str]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (repo_root() / p)


def utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def flat_to_xy(flat: int) -> tuple[int, int]:
    return int(flat % MAP_W), int(flat // MAP_W)


def xy_to_flat(x: int, y: int) -> int:
    return int(y * MAP_W + x)


def in_bounds(x: int, y: int) -> bool:
    return 0 <= x < MAP_W and 0 <= y < MAP_H


def step_from_filename(path: str | Path) -> int:
    s = Path(path).stem
    m = re.search(r"step(\d+)", s, flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    digits = "".join(ch for ch in s if ch.isdigit())
    return int(digits[-4:] or "0")


def actor_mask_from_obs(obs_rows: np.ndarray) -> np.ndarray:
    obs = np.asarray(obs_rows, dtype=np.float32)
    owner_self = obs[:, :, OBS_OWNER_SELF_INDEX] > 0.5
    has_unit = np.sum(obs[:, :, OBS_UNIT_SLICE], axis=2) > 0.5
    return np.asarray(owner_self & has_unit, dtype=bool)


def move_target(source_flat: int, move_dir: int) -> tuple[int | None, bool]:
    if int(move_dir) not in MOVE_DELTAS:
        return None, False
    x, y = flat_to_xy(source_flat)
    dx, dy = MOVE_DELTAS[int(move_dir)]
    nx, ny = x + dx, y + dy
    if not in_bounds(nx, ny):
        return None, False
    return xy_to_flat(nx, ny), True


def move_dir_is_valid(obs_flat: np.ndarray, source_flat: int, move_dir: int) -> bool:
    tgt, ok = move_target(source_flat, int(move_dir))
    if (not ok) or tgt is None:
        return False
    # Target must be empty and in-bounds; resource/enemy/friendly occupancy all imply non-empty.
    occ = float(np.sum(np.asarray(obs_flat, dtype=np.float32)[tgt, OBS_UNIT_SLICE]))
    return occ <= 1e-6


def attack_index_to_offset(idx: int) -> tuple[int, int]:
    dy = int(idx // 7) - 3
    dx = int(idx % 7) - 3
    return dx, dy


def attack_offset_to_index(dx: int, dy: int) -> int:
    return int((dy + 3) * 7 + (dx + 3))


def build_step_mask_from_cell_rows(rows: Iterable[Mapping[str, Any]]) -> StepMaskBundle:
    row_list = list(rows)
    by_cell: Dict[int, Mapping[str, Any]] = {int(r.get("cell_index", -1)): r for r in row_list if int(r.get("cell_index", -1)) >= 0}

    action_type_mask = np.zeros((N_CELLS, 6), dtype=bool)
    move_dir_mask = np.zeros((N_CELLS, 4), dtype=bool)
    harvest_dir_mask = np.zeros((N_CELLS, 4), dtype=bool)
    return_dir_mask = np.zeros((N_CELLS, 4), dtype=bool)
    produce_dir_mask = np.zeros((N_CELLS, 4), dtype=bool)
    produce_unit_type_mask = np.zeros((N_CELLS, 7), dtype=bool)
    attack_target_local_mask = np.zeros((N_CELLS, 49), dtype=bool)

    notes: List[str] = [
        "Return legality is approximate when carried-resource state is unavailable; runtime ActionApplier remains authoritative.",
        "Produce resource-cost legality is approximate when resource counters are unavailable; runtime ActionApplier remains authoritative.",
        "Attack range is approximated as local 7x7 when unit-specific range metadata is unavailable.",
    ]

    step = int(next(iter(row_list), {}).get("step", 0) or 0)

    for flat in range(N_CELLS):
        action_type_mask[flat, ACTION_TYPE_NOOP] = True
        row = by_cell.get(flat)
        if row is None:
            continue

        is_actor = bool(row.get("runtime_is_friendly_actor", False))
        unit_type = str(row.get("decoded_observation_unit_type") or "Unknown")

        if not is_actor:
            # Off-actor hard rule: NoOp only.
            continue

        x, y = flat_to_xy(flat)

        # Move legality.
        if unit_type in MOVABLE_UNITS:
            for d, (dx, dy) in MOVE_DELTAS.items():
                nx, ny = x + dx, y + dy
                if not in_bounds(nx, ny):
                    continue
                nflat = xy_to_flat(nx, ny)
                nrow = by_cell.get(nflat)
                if nrow is not None and bool(nrow.get("runtime_is_empty", False)):
                    move_dir_mask[flat, d] = True
            if bool(np.any(move_dir_mask[flat])):
                action_type_mask[flat, ACTION_TYPE_MOVE] = True

        # Harvest legality.
        if unit_type == "Worker":
            for d, (dx, dy) in MOVE_DELTAS.items():
                nx, ny = x + dx, y + dy
                if not in_bounds(nx, ny):
                    continue
                nflat = xy_to_flat(nx, ny)
                nrow = by_cell.get(nflat)
                if nrow is not None and bool(nrow.get("runtime_is_resource", False)):
                    harvest_dir_mask[flat, d] = True
            if bool(np.any(harvest_dir_mask[flat])):
                action_type_mask[flat, ACTION_TYPE_HARVEST] = True

        # Return legality (approximate, carried-resource unknown).
        if unit_type == "Worker":
            for d, (dx, dy) in MOVE_DELTAS.items():
                nx, ny = x + dx, y + dy
                if not in_bounds(nx, ny):
                    continue
                nflat = xy_to_flat(nx, ny)
                nrow = by_cell.get(nflat)
                if nrow is None:
                    continue
                if bool(nrow.get("runtime_is_friendly_actor", False)) and str(nrow.get("decoded_observation_unit_type") or "") == "Base":
                    return_dir_mask[flat, d] = True
            if bool(np.any(return_dir_mask[flat])):
                action_type_mask[flat, ACTION_TYPE_RETURN] = True

        # Produce legality.
        if unit_type in {"Base", "Barracks"}:
            for d, (dx, dy) in MOVE_DELTAS.items():
                nx, ny = x + dx, y + dy
                if not in_bounds(nx, ny):
                    continue
                nflat = xy_to_flat(nx, ny)
                nrow = by_cell.get(nflat)
                if nrow is not None and bool(nrow.get("runtime_is_empty", False)):
                    produce_dir_mask[flat, d] = True
            if unit_type == "Base":
                produce_unit_type_mask[flat, PRODUCE_WORKER] = True
            else:
                produce_unit_type_mask[flat, PRODUCE_LIGHT] = True
                produce_unit_type_mask[flat, PRODUCE_HEAVY] = True
                produce_unit_type_mask[flat, PRODUCE_RANGED] = True
            if bool(np.any(produce_dir_mask[flat])) and bool(np.any(produce_unit_type_mask[flat])):
                action_type_mask[flat, ACTION_TYPE_PRODUCE] = True

        # Attack legality.
        if unit_type in COMBAT_UNITS:
            has_enemy = False
            for dy in range(-3, 4):
                for dx in range(-3, 4):
                    tx, ty = x + dx, y + dy
                    if not in_bounds(tx, ty):
                        continue
                    tflat = xy_to_flat(tx, ty)
                    trow = by_cell.get(tflat)
                    if trow is None:
                        continue
                    if bool(trow.get("runtime_is_enemy", False)):
                        attack_target_local_mask[flat, attack_offset_to_index(dx, dy)] = True
                        has_enemy = True
            if has_enemy:
                action_type_mask[flat, ACTION_TYPE_ATTACK] = True

    return StepMaskBundle(
        step=step,
        action_type_mask=action_type_mask,
        move_dir_mask=move_dir_mask,
        harvest_dir_mask=harvest_dir_mask,
        return_dir_mask=return_dir_mask,
        produce_dir_mask=produce_dir_mask,
        produce_unit_type_mask=produce_unit_type_mask,
        attack_target_local_mask=attack_target_local_mask,
        approximation_notes=notes,
    )


def validate_mask_sanity(bundle: StepMaskBundle, rows: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    row_list = list(rows)
    by_cell: Dict[int, Mapping[str, Any]] = {int(r.get("cell_index", -1)): r for r in row_list if int(r.get("cell_index", -1)) >= 0}

    violations = {
        "shape": 0,
        "noop_everywhere": 0,
        "off_actor_only_noop": 0,
        "move_rule": 0,
        "move_dir_rule": 0,
        "attack_rule": 0,
        "attack_index_range": 0,
        "branch_nonempty_only_when_action_legal": 0,
    }

    if bundle.action_type_mask.shape != (N_CELLS, 6):
        violations["shape"] += 1
    if bundle.move_dir_mask.shape != (N_CELLS, 4):
        violations["shape"] += 1
    if bundle.harvest_dir_mask.shape != (N_CELLS, 4):
        violations["shape"] += 1
    if bundle.return_dir_mask.shape != (N_CELLS, 4):
        violations["shape"] += 1
    if bundle.produce_dir_mask.shape != (N_CELLS, 4):
        violations["shape"] += 1
    if bundle.produce_unit_type_mask.shape != (N_CELLS, 7):
        violations["shape"] += 1
    if bundle.attack_target_local_mask.shape != (N_CELLS, 49):
        violations["shape"] += 1

    for flat in range(N_CELLS):
        if not bool(bundle.action_type_mask[flat, ACTION_TYPE_NOOP]):
            violations["noop_everywhere"] += 1

        row = by_cell.get(flat)
        is_actor = bool(row.get("runtime_is_friendly_actor", False)) if row is not None else False

        if not is_actor:
            if bool(np.any(bundle.action_type_mask[flat, 1:])):
                violations["off_actor_only_noop"] += 1

        if bool(bundle.action_type_mask[flat, ACTION_TYPE_MOVE]) != bool(np.any(bundle.move_dir_mask[flat])):
            violations["move_rule"] += 1

        x, y = flat_to_xy(flat)
        for d, legal in enumerate(bundle.move_dir_mask[flat]):
            if not legal:
                continue
            dx, dy = MOVE_DELTAS[d]
            nx, ny = x + dx, y + dy
            if not in_bounds(nx, ny):
                violations["move_dir_rule"] += 1
                continue
            nrow = by_cell.get(xy_to_flat(nx, ny))
            if nrow is None or not bool(nrow.get("runtime_is_empty", False)):
                violations["move_dir_rule"] += 1

        if bool(bundle.action_type_mask[flat, ACTION_TYPE_ATTACK]) != bool(np.any(bundle.attack_target_local_mask[flat])):
            violations["attack_rule"] += 1

        for idx, legal in enumerate(bundle.attack_target_local_mask[flat]):
            if not legal:
                continue
            if not (0 <= idx < 49):
                violations["attack_index_range"] += 1
                continue
            dx, dy = attack_index_to_offset(idx)
            tx, ty = x + dx, y + dy
            if not in_bounds(tx, ty):
                violations["attack_rule"] += 1
                continue
            trow = by_cell.get(xy_to_flat(tx, ty))
            if trow is None or not bool(trow.get("runtime_is_enemy", False)):
                violations["attack_rule"] += 1

        if np.any(bundle.harvest_dir_mask[flat]) and not bool(bundle.action_type_mask[flat, ACTION_TYPE_HARVEST]):
            violations["branch_nonempty_only_when_action_legal"] += 1
        if np.any(bundle.return_dir_mask[flat]) and not bool(bundle.action_type_mask[flat, ACTION_TYPE_RETURN]):
            violations["branch_nonempty_only_when_action_legal"] += 1
        if np.any(bundle.produce_dir_mask[flat]) and not bool(bundle.action_type_mask[flat, ACTION_TYPE_PRODUCE]):
            violations["branch_nonempty_only_when_action_legal"] += 1
        if np.any(bundle.produce_unit_type_mask[flat]) and not bool(bundle.action_type_mask[flat, ACTION_TYPE_PRODUCE]):
            violations["branch_nonempty_only_when_action_legal"] += 1
        if np.any(bundle.attack_target_local_mask[flat]) and not bool(bundle.action_type_mask[flat, ACTION_TYPE_ATTACK]):
            violations["branch_nonempty_only_when_action_legal"] += 1

    ok = all(v == 0 for v in violations.values())
    return {
        "ok": bool(ok),
        "violations": {k: int(v) for k, v in violations.items()},
    }


def logits_to_predictions(logits_by_key: Mapping[str, np.ndarray]) -> Dict[str, np.ndarray]:
    return {
        "action_type": np.argmax(np.asarray(logits_by_key["action_type_logits"]), axis=-1).astype(np.int64),
        "move_dir": np.argmax(np.asarray(logits_by_key["move_dir_logits"]), axis=-1).astype(np.int64),
        "harvest_dir": np.argmax(np.asarray(logits_by_key["harvest_dir_logits"]), axis=-1).astype(np.int64),
        "return_dir": np.argmax(np.asarray(logits_by_key["return_dir_logits"]), axis=-1).astype(np.int64),
        "produce_dir": np.argmax(np.asarray(logits_by_key["produce_dir_logits"]), axis=-1).astype(np.int64),
        "produce_unit_type": np.argmax(np.asarray(logits_by_key["produce_unit_type_logits"]), axis=-1).astype(np.int64),
        "attack_target_local": np.argmax(np.asarray(logits_by_key["attack_target_local_logits"]), axis=-1).astype(np.int64),
    }


def model_forward_logits(model: torch.nn.Module, obs_bhwc: np.ndarray, device: torch.device, batch_size: int) -> Dict[str, np.ndarray]:
    outs: Dict[str, List[np.ndarray]] = {
        "action_type_logits": [],
        "move_dir_logits": [],
        "harvest_dir_logits": [],
        "return_dir_logits": [],
        "produce_dir_logits": [],
        "produce_unit_type_logits": [],
        "attack_target_local_logits": [],
    }
    obs = np.asarray(obs_bhwc, dtype=np.float32)
    with torch.no_grad():
        for s in range(0, obs.shape[0], batch_size):
            e = min(s + batch_size, obs.shape[0])
            x = torch.from_numpy(obs[s:e]).to(device=device, dtype=torch.float32)
            out = model(x)
            for k in outs:
                outs[k].append(np.asarray(out[k].detach().cpu().numpy(), dtype=np.float32))
    return {k: np.concatenate(v, axis=0) for k, v in outs.items()}


def load_checkpoint_model(checkpoint: str | Path, device: torch.device) -> torch.nn.Module:
    return load_model_strict(checkpoint, device=device)


def apply_masked_selection_for_cell(
    logits_for_cell: Mapping[str, np.ndarray],
    bundle: StepMaskBundle,
    flat: int,
) -> Dict[str, int]:
    very_neg = -1.0e30

    action_logits = np.asarray(logits_for_cell["action_type_logits"], dtype=np.float32).copy()
    legal_action = np.asarray(bundle.action_type_mask[flat], dtype=bool)
    masked_action_logits = np.where(legal_action, action_logits, very_neg)
    masked_action = int(np.argmax(masked_action_logits))

    out = {
        "action_type": masked_action,
        "move_dir": 0,
        "harvest_dir": 0,
        "return_dir": 0,
        "produce_dir": 0,
        "produce_unit_type": 0,
        "attack_target_local": 0,
    }

    if masked_action == ACTION_TYPE_MOVE:
        v = np.asarray(bundle.move_dir_mask[flat], dtype=bool)
        l = np.asarray(logits_for_cell["move_dir_logits"], dtype=np.float32)
        out["move_dir"] = int(np.argmax(np.where(v, l, very_neg)))
    elif masked_action == ACTION_TYPE_HARVEST:
        v = np.asarray(bundle.harvest_dir_mask[flat], dtype=bool)
        l = np.asarray(logits_for_cell["harvest_dir_logits"], dtype=np.float32)
        out["harvest_dir"] = int(np.argmax(np.where(v, l, very_neg)))
    elif masked_action == ACTION_TYPE_RETURN:
        v = np.asarray(bundle.return_dir_mask[flat], dtype=bool)
        l = np.asarray(logits_for_cell["return_dir_logits"], dtype=np.float32)
        out["return_dir"] = int(np.argmax(np.where(v, l, very_neg)))
    elif masked_action == ACTION_TYPE_PRODUCE:
        vdir = np.asarray(bundle.produce_dir_mask[flat], dtype=bool)
        ldir = np.asarray(logits_for_cell["produce_dir_logits"], dtype=np.float32)
        out["produce_dir"] = int(np.argmax(np.where(vdir, ldir, very_neg)))
        vtyp = np.asarray(bundle.produce_unit_type_mask[flat], dtype=bool)
        ltyp = np.asarray(logits_for_cell["produce_unit_type_logits"], dtype=np.float32)
        out["produce_unit_type"] = int(np.argmax(np.where(vtyp, ltyp, very_neg)))
    elif masked_action == ACTION_TYPE_ATTACK:
        v = np.asarray(bundle.attack_target_local_mask[flat], dtype=bool)
        l = np.asarray(logits_for_cell["attack_target_local_logits"], dtype=np.float32)
        out["attack_target_local"] = int(np.argmax(np.where(v, l, very_neg)))

    return out
