from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import torch
import torch.nn.functional as F

from student_architecture_transfer import build_day3_student_model


OBS_SHAPE: tuple[int, int] = (576, 27)
ACTION_SHAPE: tuple[int, int] = (576, 7)
MAP_W: int = 24
MAP_H: int = 24
BRANCH_SIZES: tuple[int, ...] = (6, 4, 4, 4, 4, 7, 49)

ACTION_TYPE_NOOP = 0
ACTION_TYPE_MOVE = 1
ACTION_TYPE_HARVEST = 2
ACTION_TYPE_RETURN = 3
ACTION_TYPE_PRODUCE = 4
ACTION_TYPE_ATTACK = 5

OWNER_SLICE = slice(2, 5)
UNIT_TYPE_SLICE = slice(5, 12)
ACTION_SLICE = slice(12, 18)
DIR_SLICE = slice(18, 22)
PRODUCE_TYPE_SLICE = slice(22, 26)
ATTACK_TARGET_INDEX = 26

OWNER_NEUTRAL_INDEX = 2
OWNER_SELF_INDEX = 3
OWNER_ENEMY_INDEX = 4

UNIT_RESOURCE_INDEX = 5
UNIT_BASE_INDEX = 6
UNIT_BARRACKS_INDEX = 7
UNIT_WORKER_INDEX = 8

B2_FLAT = 25
C3_FLAT = 50

ACTION_NAMES = ["noop", "move", "harvest", "return", "produce", "attack"]

DEFAULT_BC_READY_DIR = (
    "python/week6_student/bc_ready/"
    "legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z"
)
DEFAULT_TRUE_RAW_CAPTURE = "python/week6_student/reports/stage10d12r_full_raw_runtime_observation_step0001.json"
DEFAULT_STAGE10D8_CHECKPOINT = (
    "python/week6_student/runs/"
    "legacy032_v2_semantic_bc_stage10d8_20260503T093718Z/student_bc_semantic_best.pt"
)
DEFAULT_REPORTS_DIR = "python/week6_student/reports"
DEFAULT_BC_OUTPUT_ROOT = "python/week6_student/bc_ready"
DEFAULT_RUNS_ROOT = "python/week6_student/runs"


@dataclass(frozen=True)
class ReferenceSample:
    split_name: str
    sample_index: int
    flat_index: int
    x: int
    y: int
    l2_distance: float
    observation_flat: np.ndarray
    action_flat: np.ndarray
    target_cell_vector: np.ndarray
    target_action_vector: np.ndarray


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (repo_root() / p)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_dir_stamp() -> str:
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


def write_jsonl(path: str | Path, rows: Iterable[Mapping[str, Any]]) -> Path:
    p = resolve_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(dict(row), ensure_ascii=True) + "\n")
    return p


def read_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    p = resolve_path(path)
    rows: List[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def flat_to_xy(flat_index: int) -> tuple[int, int]:
    return int(flat_index % MAP_W), int(flat_index // MAP_W)


def xy_to_flat(x: int, y: int) -> int:
    return int(y * MAP_W + x)


def reshape_obs(obs_flat: np.ndarray) -> np.ndarray:
    return np.asarray(obs_flat, dtype=np.float32).reshape(MAP_H, MAP_W, OBS_SHAPE[1])


def flatten_obs(obs_map: np.ndarray) -> np.ndarray:
    return np.asarray(obs_map, dtype=np.float32).reshape(OBS_SHAPE)


def load_split_payload(path: str | Path) -> Dict[str, np.ndarray]:
    p = resolve_path(path)
    with np.load(p, allow_pickle=False) as npz:
        return {k: np.asarray(npz[k]) for k in npz.files}


def get_observations_and_actions(split_payload: Mapping[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    if "observations" in split_payload:
        observations = np.asarray(split_payload["observations"], dtype=np.float32)
    else:
        observations = np.asarray(split_payload["input_tensor"], dtype=np.float32)

    if "actions" in split_payload:
        actions = np.asarray(split_payload["actions"])
    else:
        actions = np.asarray(split_payload["target_action_branches"])
    return observations, actions


def load_true_raw_capture_tensor(path: str | Path) -> np.ndarray:
    payload = load_json(path)
    cells = payload.get("cells", [])
    if not isinstance(cells, list) or len(cells) != 576:
        raise RuntimeError(f"Expected 576 cells in true raw capture, got {len(cells)}")
    tensor = np.zeros((576, 27), dtype=np.float32)
    for idx, cell in enumerate(cells):
        vec = cell.get("raw_channel_vector", []) if isinstance(cell, Mapping) else []
        if not isinstance(vec, list) or len(vec) != 27:
            raise RuntimeError(f"Cell {idx} raw_channel_vector must have length 27")
        tensor[idx, :] = np.asarray(vec, dtype=np.float32)
    if not np.isfinite(tensor).all():
        raise RuntimeError("True raw runtime tensor contains NaN/Inf")
    return tensor.reshape(MAP_H, MAP_W, 27)


def action_index_from_observation_cell(cell_vec: np.ndarray) -> int:
    action_slice = np.asarray(cell_vec[ACTION_SLICE], dtype=np.float32)
    if float(action_slice.max(initial=0.0)) <= 0.0:
        return -1
    return int(np.argmax(action_slice))


def set_action_noop_on_cell(
    obs_map: np.ndarray,
    flat_index: int,
    *,
    clear_direction: bool,
    clear_auxiliary: bool,
) -> np.ndarray:
    out = np.asarray(obs_map, dtype=np.float32).copy()
    x, y = flat_to_xy(flat_index)
    out[y, x, ACTION_SLICE] = 0.0
    out[y, x, ACTION_SLICE.start + ACTION_TYPE_NOOP] = 1.0
    if clear_direction:
        out[y, x, DIR_SLICE] = 0.0
    if clear_auxiliary:
        out[y, x, PRODUCE_TYPE_SLICE] = 0.0
        out[y, x, ATTACK_TARGET_INDEX] = 0.0
    return out


def normalize_empty_cells_unity_like(obs_map: np.ndarray) -> np.ndarray:
    out = np.asarray(obs_map, dtype=np.float32).copy()
    unit_sum = np.sum(out[:, :, UNIT_TYPE_SLICE], axis=2)
    empty_mask = np.isclose(unit_sum, 0.0)
    out[empty_mask, ACTION_SLICE] = 0.0
    out[empty_mask, DIR_SLICE] = 0.0
    out[empty_mask, PRODUCE_TYPE_SLICE] = 0.0
    out[empty_mask, ATTACK_TARGET_INDEX] = 0.0
    return out


def patch_local_action_context_from_runtime(
    obs_map: np.ndarray,
    *,
    target_flat: int,
    runtime_map: np.ndarray,
    runtime_center_flat: int,
    radius: int,
) -> np.ndarray:
    out = np.asarray(obs_map, dtype=np.float32).copy()
    tx, ty = flat_to_xy(target_flat)
    rx, ry = flat_to_xy(runtime_center_flat)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            target_x = tx + dx
            target_y = ty + dy
            source_x = rx + dx
            source_y = ry + dy
            if not (0 <= target_x < MAP_W and 0 <= target_y < MAP_H):
                continue
            if not (0 <= source_x < MAP_W and 0 <= source_y < MAP_H):
                continue
            out[target_y, target_x, ACTION_SLICE] = runtime_map[source_y, source_x, ACTION_SLICE]
            out[target_y, target_x, DIR_SLICE] = runtime_map[source_y, source_x, DIR_SLICE]
            out[target_y, target_x, PRODUCE_TYPE_SLICE] = runtime_map[source_y, source_x, PRODUCE_TYPE_SLICE]
            out[target_y, target_x, ATTACK_TARGET_INDEX] = runtime_map[source_y, source_x, ATTACK_TARGET_INDEX]
    return out


def load_model_strict(checkpoint_path: str | Path, device: torch.device) -> torch.nn.Module:
    checkpoint = torch.load(resolve_path(checkpoint_path), map_location=device)
    model = build_day3_student_model().to(device=device)
    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        state_dict = checkpoint["model_state_dict"]
    elif isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        state_dict = checkpoint["state_dict"]
    else:
        state_dict = checkpoint
    model.load_state_dict(state_dict, strict=True)
    model.eval()
    return model


def run_model_action_type_probs(model: torch.nn.Module, obs_map: np.ndarray, device: torch.device) -> np.ndarray:
    with torch.no_grad():
        x = torch.from_numpy(np.asarray(obs_map, dtype=np.float32)[None, ...]).to(device=device, dtype=torch.float32)
        logits = model(x)["action_type_logits"]
        probs = F.softmax(logits, dim=-1)[0].detach().cpu().numpy()
    return probs


def eval_cell_probs(action_probs: np.ndarray, flat_index: int) -> Dict[str, Any]:
    p = np.asarray(action_probs[flat_index], dtype=np.float32)
    pred_idx = int(np.argmax(p))
    return {
        "flat_index": int(flat_index),
        "predicted_action": ACTION_NAMES[pred_idx],
        "p_noop": float(p[0]),
        "p_move": float(p[1]),
        "p_harvest": float(p[2]),
        "p_return": float(p[3]),
        "p_produce": float(p[4]),
        "p_attack": float(p[5]),
        "full_probabilities": [float(x) for x in p.tolist()],
    }


def summarize_true_raw_predictions(action_probs: np.ndarray, obs_map: np.ndarray) -> Dict[str, Any]:
    action_pred = np.argmax(action_probs, axis=1).astype(np.int64)
    friendly_actor_mask = np.logical_and(
        np.asarray(obs_map.reshape(OBS_SHAPE)[:, OWNER_SELF_INDEX] > 0.5, dtype=bool),
        np.asarray(np.sum(obs_map.reshape(OBS_SHAPE)[:, UNIT_TYPE_SLICE], axis=1) > 0.5, dtype=bool),
    )
    actor_predictions: List[Dict[str, Any]] = []
    for flat_index in np.where(friendly_actor_mask)[0].tolist():
        cell = eval_cell_probs(action_probs, int(flat_index))
        x, y = flat_to_xy(int(flat_index))
        cell.update({"x": x, "y": y})
        actor_predictions.append(cell)

    off_actor_non_noop_count = int(np.sum(action_pred[~friendly_actor_mask] != ACTION_TYPE_NOOP))
    global_noop_share = float(np.mean(action_pred == ACTION_TYPE_NOOP))
    actor_noop_share = float(np.mean(action_pred[friendly_actor_mask] == ACTION_TYPE_NOOP)) if np.any(friendly_actor_mask) else 1.0
    return {
        "B2": eval_cell_probs(action_probs, B2_FLAT),
        "C3": eval_cell_probs(action_probs, C3_FLAT),
        "friendly_actor_predictions": actor_predictions,
        "off_actor_non_noop_count": off_actor_non_noop_count,
        "global_predicted_noop_share": global_noop_share,
        "actor_predicted_noop_share": actor_noop_share,
    }


def evaluate_action_type_subset(
    model: torch.nn.Module,
    observations: np.ndarray,
    actions: np.ndarray,
    *,
    indices: Sequence[int],
    device: torch.device,
    batch_size: int = 64,
) -> Dict[str, Any]:
    if len(indices) == 0:
        return {
            "sample_count": 0,
            "actor_cell_count": 0,
            "actor_cell_action_type_accuracy": 0.0,
            "actor_cell_non_noop_recall": 0.0,
            "worker_harvest_recall": 0.0,
            "base_produce_recall": 0.0,
            "action_type_accuracy_all_cells": 0.0,
            "predicted_noop_share_all_cells": 1.0,
        }

    sample_indices = np.asarray(indices, dtype=np.int64)
    obs_subset = np.asarray(observations[sample_indices], dtype=np.float32)
    action_subset = np.asarray(actions[sample_indices], dtype=np.int64)

    pred_rows: List[np.ndarray] = []
    model.eval()
    with torch.no_grad():
        for start in range(0, obs_subset.shape[0], batch_size):
            stop = min(start + batch_size, obs_subset.shape[0])
            batch = torch.from_numpy(obs_subset[start:stop]).to(device=device, dtype=torch.float32)
            logits = model(batch)["action_type_logits"]
            preds = torch.argmax(logits, dim=-1).detach().cpu().numpy()
            pred_rows.append(np.asarray(preds, dtype=np.int64))
    pred_action_type = np.concatenate(pred_rows, axis=0)

    target_action_type = np.asarray(action_subset[:, :, 0], dtype=np.int64)
    obs_flat = obs_subset.reshape(obs_subset.shape[0], 576, 27)
    actor_mask = np.asarray(target_action_type != ACTION_TYPE_NOOP, dtype=bool)
    worker_mask = np.asarray(obs_flat[:, :, UNIT_WORKER_INDEX] > 0.5, dtype=bool)
    base_mask = np.asarray(obs_flat[:, :, UNIT_BASE_INDEX] > 0.5, dtype=bool)

    actor_count = int(np.sum(actor_mask))
    worker_harvest_mask = np.asarray((target_action_type == ACTION_TYPE_HARVEST) & worker_mask & actor_mask, dtype=bool)
    base_produce_mask = np.asarray((target_action_type == ACTION_TYPE_PRODUCE) & base_mask & actor_mask, dtype=bool)

    return {
        "sample_count": int(obs_subset.shape[0]),
        "actor_cell_count": actor_count,
        "actor_cell_action_type_accuracy": float(np.mean(pred_action_type[actor_mask] == target_action_type[actor_mask])) if actor_count > 0 else 0.0,
        "actor_cell_non_noop_recall": float(np.mean(pred_action_type[actor_mask] != ACTION_TYPE_NOOP)) if actor_count > 0 else 0.0,
        "worker_harvest_recall": float(np.mean(pred_action_type[worker_harvest_mask] == ACTION_TYPE_HARVEST)) if np.any(worker_harvest_mask) else 0.0,
        "base_produce_recall": float(np.mean(pred_action_type[base_produce_mask] == ACTION_TYPE_PRODUCE)) if np.any(base_produce_mask) else 0.0,
        "action_type_accuracy_all_cells": float(np.mean(pred_action_type == target_action_type)),
        "predicted_noop_share_all_cells": float(np.mean(pred_action_type == ACTION_TYPE_NOOP)),
    }


def evaluate_augmented_target_success(
    model: torch.nn.Module,
    observations: np.ndarray,
    metadata_rows: Sequence[Mapping[str, Any]],
    *,
    original_count: int,
    device: torch.device,
    batch_size: int = 64,
) -> Dict[str, Any]:
    if not metadata_rows:
        return {
            "sample_count": 0,
            "B2_success_count": 0,
            "B2_success_rate": 0.0,
            "C3_success_count": 0,
            "C3_success_rate": 0.0,
        }

    sample_indices = np.arange(original_count, original_count + len(metadata_rows), dtype=np.int64)
    obs_subset = np.asarray(observations[sample_indices], dtype=np.float32)
    pred_rows: List[np.ndarray] = []
    model.eval()
    with torch.no_grad():
        for start in range(0, obs_subset.shape[0], batch_size):
            stop = min(start + batch_size, obs_subset.shape[0])
            batch = torch.from_numpy(obs_subset[start:stop]).to(device=device, dtype=torch.float32)
            logits = model(batch)["action_type_logits"]
            pred_rows.append(torch.argmax(logits, dim=-1).detach().cpu().numpy())
    pred_action_type = np.concatenate(pred_rows, axis=0)

    b2_total = 0
    b2_success = 0
    c3_total = 0
    c3_success = 0
    for metadata_index, row in enumerate(metadata_rows):
        target_flat = int(row.get("target_cell_flat", -1))
        target_action_type = int(row.get("target_action_type", -1))
        pred = int(pred_action_type[metadata_index, target_flat]) if target_flat >= 0 else -1
        if target_flat == B2_FLAT and target_action_type == ACTION_TYPE_HARVEST:
            b2_total += 1
            if pred == ACTION_TYPE_HARVEST:
                b2_success += 1
        if target_flat == C3_FLAT and target_action_type == ACTION_TYPE_PRODUCE:
            c3_total += 1
            if pred == ACTION_TYPE_PRODUCE:
                c3_success += 1
    return {
        "sample_count": int(len(metadata_rows)),
        "B2_success_count": int(b2_success),
        "B2_success_rate": float(b2_success / b2_total) if b2_total > 0 else 0.0,
        "C3_success_count": int(c3_success),
        "C3_success_rate": float(c3_success / c3_total) if c3_total > 0 else 0.0,
    }


def select_reference_sample(
    observations: np.ndarray,
    actions: np.ndarray,
    *,
    split_name: str,
    runtime_vec: np.ndarray,
    target_action_type: int,
    target_unit_channel: int,
) -> Optional[ReferenceSample]:
    action_mask = np.asarray(actions[:, :, 0] == target_action_type, dtype=bool)
    unit_mask = np.asarray(observations[:, :, target_unit_channel] > 0.5, dtype=bool)
    friendly_mask = np.asarray(observations[:, :, OWNER_SELF_INDEX] > 0.5, dtype=bool)
    valid_mask = action_mask & unit_mask & friendly_mask
    if not np.any(valid_mask):
        return None
    sample_indices, flat_indices = np.where(valid_mask)
    candidate_vectors = observations[sample_indices, flat_indices, :]
    dists = np.linalg.norm(candidate_vectors - np.asarray(runtime_vec, dtype=np.float32)[None, :], axis=1)
    best_idx = int(np.argmin(dists))
    sample_index = int(sample_indices[best_idx])
    flat_index = int(flat_indices[best_idx])
    x, y = flat_to_xy(flat_index)
    return ReferenceSample(
        split_name=split_name,
        sample_index=sample_index,
        flat_index=flat_index,
        x=x,
        y=y,
        l2_distance=float(dists[best_idx]),
        observation_flat=np.asarray(observations[sample_index], dtype=np.float32).copy(),
        action_flat=np.asarray(actions[sample_index], dtype=np.int64).copy(),
        target_cell_vector=np.asarray(observations[sample_index, flat_index], dtype=np.float32).copy(),
        target_action_vector=np.asarray(actions[sample_index, flat_index], dtype=np.int64).copy(),
    )


def choose_nearest_reference(candidates: Sequence[Optional[ReferenceSample]]) -> ReferenceSample:
    valid = [candidate for candidate in candidates if candidate is not None]
    if not valid:
        raise RuntimeError("No valid BC-positive reference sample found")
    return min(valid, key=lambda item: item.l2_distance)


def compute_action_distribution(observations: np.ndarray, actions: np.ndarray) -> Dict[str, Any]:
    action_type = np.asarray(actions[:, :, 0], dtype=np.int64)
    obs = np.asarray(observations, dtype=np.float32)
    actor_mask = np.logical_and(obs[:, :, OWNER_SELF_INDEX] > 0.5, np.sum(obs[:, :, UNIT_TYPE_SLICE], axis=2) > 0.5)
    worker_mask = np.asarray(obs[:, :, UNIT_WORKER_INDEX] > 0.5, dtype=bool)
    base_mask = np.asarray(obs[:, :, UNIT_BASE_INDEX] > 0.5, dtype=bool)

    counts = {
        "sample_count": int(obs.shape[0]),
        "actor_cell_count": int(np.sum(actor_mask)),
        "worker_harvest": int(np.sum((action_type == ACTION_TYPE_HARVEST) & worker_mask & actor_mask)),
        "base_produce": int(np.sum((action_type == ACTION_TYPE_PRODUCE) & base_mask & actor_mask)),
        "attack": int(np.sum(action_type == ACTION_TYPE_ATTACK)),
        "noop_actor_cells": int(np.sum((action_type == ACTION_TYPE_NOOP) & actor_mask)),
        "noop_all_cells": int(np.sum(action_type == ACTION_TYPE_NOOP)),
        "noop_ratio_all_cells": float(np.mean(action_type == ACTION_TYPE_NOOP)),
    }
    return counts


def validate_branch_bounds(actions: np.ndarray) -> Dict[str, bool]:
    actions_i64 = np.asarray(actions, dtype=np.int64)
    result: Dict[str, bool] = {}
    branch_names = [
        "action_type",
        "move_dir",
        "harvest_dir",
        "return_dir",
        "produce_dir",
        "produce_unit_type",
        "attack_target",
    ]
    for idx, size in enumerate(BRANCH_SIZES):
        branch = actions_i64[:, :, idx]
        result[branch_names[idx]] = bool(int(branch.min()) >= 0 and int(branch.max()) < size)
    return result
