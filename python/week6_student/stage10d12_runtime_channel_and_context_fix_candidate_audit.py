#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import torch

from student_architecture_transfer import build_day3_student_model


ACTION_NAMES = ["NoOp", "Move", "Harvest", "Return", "Produce", "Attack"]

CHANNEL_NAMES = [
    "hit_points",
    "resources",
    "owner_neutral",
    "owner_self",
    "owner_enemy",
    "unit_resource",
    "unit_base",
    "unit_barracks",
    "unit_worker",
    "unit_light",
    "unit_heavy",
    "unit_ranged",
    "action_noop",
    "action_move",
    "action_harvest",
    "action_return",
    "action_produce",
    "action_attack",
    "dir_north",
    "dir_east",
    "dir_south",
    "dir_west",
    "produce_worker",
    "produce_light",
    "produce_heavy",
    "produce_ranged",
    "attack_target_index",
]

GROUPS: Dict[str, List[int]] = {
    "scalars": [0, 1, 26],
    "owner": [2, 3, 4],
    "unit_type": [5, 6, 7, 8, 9, 10, 11],
    "current_action": [12, 13, 14, 15, 16, 17],
    "direction": [18, 19, 20, 21],
    "produce_type": [22, 23, 24, 25],
}

B2_GROUP_PROBES: List[Tuple[str, List[int]]] = [
    ("scalars_only", [0, 1, 26]),
    ("owner_only", [2, 3, 4]),
    ("unit_type_only", [5, 6, 7, 8, 9, 10, 11]),
    ("current_action_only", [12, 13, 14, 15, 16, 17]),
    ("direction_only", [18, 19, 20, 21]),
    ("produce_type_only", [22, 23, 24, 25]),
    ("current_action_plus_direction", [12, 13, 14, 15, 16, 17, 18, 19, 20, 21]),
    ("scalars_plus_current_action_plus_direction", [0, 1, 26, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]),
    ("owner_plus_unit_type", [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]),
    ("owner_plus_unit_type_plus_current_action", [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]),
    (
        "owner_plus_unit_type_plus_direction",
        [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 18, 19, 20, 21],
    ),
    (
        "owner_plus_unit_type_plus_current_action_plus_direction",
        [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21],
    ),
]

B2_PER_CHANNELS = [0, 1, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 26]

FOCUS = {
    "B2": {"flat": 25, "xy": (1, 1)},
    "C3": {"flat": 50, "xy": (2, 2)},
}


@dataclass
class NpyStreamInfo:
    shape: Tuple[int, ...]
    dtype: np.dtype
    fortran_order: bool


@dataclass
class PositiveSample:
    split: str
    sample_index: int
    flat_index: int
    vector: np.ndarray
    obs_map: np.ndarray
    dist_to_runtime: float


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            rows.append(json.loads(s))
    return rows


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_npy_header(fp) -> NpyStreamInfo:
    version = np.lib.format.read_magic(fp)
    if version == (1, 0):
        shape, fortran_order, dtype = np.lib.format.read_array_header_1_0(fp)
    elif version == (2, 0):
        shape, fortran_order, dtype = np.lib.format.read_array_header_2_0(fp)
    else:
        raise RuntimeError(f"Unsupported npy version: {version}")
    return NpyStreamInfo(shape=tuple(int(x) for x in shape), dtype=np.dtype(dtype), fortran_order=bool(fortran_order))


def iter_npy_rows_from_npz(npz_path: Path, key: str, rows_per_chunk: int = 64) -> Iterator[Tuple[int, np.ndarray, Tuple[int, ...]]]:
    member = f"{key}.npy"
    with zipfile.ZipFile(npz_path, "r") as zf:
        with zf.open(member, "r") as fp:
            info = read_npy_header(fp)
            if info.fortran_order:
                raise RuntimeError(f"Fortran-order arrays are not supported: {npz_path}:{member}")
            total_rows = int(info.shape[0])
            row_shape = tuple(int(x) for x in info.shape[1:])
            row_items = int(np.prod(row_shape)) if row_shape else 1
            row_bytes = row_items * info.dtype.itemsize
            start = 0
            while start < total_rows:
                n = min(rows_per_chunk, total_rows - start)
                raw = fp.read(n * row_bytes)
                if len(raw) != n * row_bytes:
                    raise RuntimeError(f"Unexpected EOF for {npz_path}:{member}")
                arr = np.frombuffer(raw, dtype=info.dtype)
                arr = arr.reshape((n, *row_shape)) if row_shape else arr.reshape((n,))
                yield start, arr, info.shape
                start += n


def iter_paired_rows(npz_path: Path, obs_key: str, act_key: str, rows_per_chunk: int = 64) -> Iterator[Tuple[int, np.ndarray, np.ndarray]]:
    it_obs = iter_npy_rows_from_npz(npz_path, obs_key, rows_per_chunk=rows_per_chunk)
    it_act = iter_npy_rows_from_npz(npz_path, act_key, rows_per_chunk=rows_per_chunk)
    while True:
        try:
            i_obs, obs, _ = next(it_obs)
        except StopIteration:
            break
        i_act, act, _ = next(it_act)
        if i_obs != i_act or obs.shape[0] != act.shape[0]:
            raise RuntimeError(f"Stream mismatch in {npz_path}")
        yield i_obs, obs, act


def label_from_probs(prob: np.ndarray) -> str:
    i = int(np.argmax(prob))
    return ACTION_NAMES[i] if 0 <= i < len(ACTION_NAMES) else str(i)


def flat_to_xy(flat: int) -> Tuple[int, int]:
    return flat % 24, flat // 24


def xy_to_flat(x: int, y: int) -> int:
    return y * 24 + x


def patch(obs_map: np.ndarray, x: int, y: int, radius: int) -> np.ndarray:
    h, w, c = obs_map.shape
    out = np.zeros((2 * radius + 1, 2 * radius + 1, c), dtype=np.float32)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            xx = x + dx
            yy = y + dy
            if 0 <= xx < w and 0 <= yy < h:
                out[dy + radius, dx + radius, :] = obs_map[yy, xx, :]
    return out


def apply_patch_from_source(
    target_map: np.ndarray,
    target_xy: Tuple[int, int],
    source_map: np.ndarray,
    source_xy: Tuple[int, int],
    radius: int,
    channels: Optional[Sequence[int]] = None,
    include_center: bool = True,
) -> np.ndarray:
    out = target_map.copy()
    tx, ty = target_xy
    sx, sy = source_xy
    ch_idx = np.arange(target_map.shape[2], dtype=np.int64) if channels is None else np.asarray(channels, dtype=np.int64)

    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if not include_center and dx == 0 and dy == 0:
                continue
            txx = tx + dx
            tyy = ty + dy
            sxx = sx + dx
            syy = sy + dy
            if not (0 <= txx < 24 and 0 <= tyy < 24 and 0 <= sxx < 24 and 0 <= syy < 24):
                continue
            out[tyy, txx, ch_idx] = source_map[syy, sxx, ch_idx]
    return out


def run_student(model: torch.nn.Module, obs_map: np.ndarray, device: torch.device) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        x = torch.from_numpy(obs_map[None, ...]).to(device=device, dtype=torch.float32)
        logits = model(x)["action_type_logits"][0].detach().cpu().numpy()
        probs = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = probs / np.clip(np.sum(probs, axis=1, keepdims=True), 1e-12, None)
    return probs


def eval_cell_probs(probs: np.ndarray, flat: int) -> Dict[str, Any]:
    p = probs[flat]
    return {
        "flat_index": int(flat),
        "predicted_action": label_from_probs(p),
        "p_noop": float(p[0]),
        "p_move": float(p[1]),
        "p_harvest": float(p[2]),
        "p_return": float(p[3]),
        "p_produce": float(p[4]),
        "p_attack": float(p[5]),
        "probabilities": [float(x) for x in p.tolist()],
    }


def find_focus_rows(cell_rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    by_flat = {int(r.get("cell_index", -1)): r for r in cell_rows}
    for label, info in FOCUS.items():
        flat = int(info["flat"])
        if flat in by_flat:
            out[label] = by_flat[flat]
    return out


def extract_focus_vectors_from_legacy_snapshot(path: Path) -> Dict[str, np.ndarray]:
    payload = read_json(path)
    out: Dict[str, np.ndarray] = {}

    for key, label_key in (("actor_cells", "logical_cell"), ("focus_cell_diagnostics", "logical_label")):
        rows = payload.get(key, [])
        if not isinstance(rows, list):
            continue
        for r in rows:
            if not isinstance(r, Mapping):
                continue
            label = str(r.get(label_key, ""))
            ch = r.get("cell_observation_channels")
            if label in FOCUS and isinstance(ch, list) and len(ch) == 27:
                out[label] = np.asarray(ch, dtype=np.float32)
    return out


def reconstruct_runtime_map(cell_rows: List[Dict[str, Any]], focus_exact: Dict[str, np.ndarray]) -> np.ndarray:
    owner_ch = {"Neutral": 2, "Player1": 3, "Player2": 4}
    unit_ch = {
        "Resource": 5,
        "Base": 6,
        "Barracks": 7,
        "Worker": 8,
        "Light": 9,
        "Heavy": 10,
        "Ranged": 11,
    }

    obs = np.zeros((24, 24, 27), dtype=np.float32)
    for r in cell_rows:
        x = int(r.get("x", 0))
        y = int(r.get("y", 0))
        owner = str(r.get("decoded_observation_owner", "Neutral"))
        unit = str(r.get("decoded_observation_unit_type", "Resource"))
        is_empty = bool(r.get("runtime_is_empty", False))

        vec = np.zeros((27,), dtype=np.float32)
        if owner in owner_ch:
            vec[owner_ch[owner]] = 1.0
        if unit in unit_ch and not is_empty:
            vec[unit_ch[unit]] = 1.0

        vec[0] = 0.0 if is_empty else 1.0
        vec[1] = 1.0 if unit == "Resource" else 0.0
        if not is_empty:
            vec[12] = 1.0
        obs[y, x, :] = vec

    for label, info in FOCUS.items():
        if label in focus_exact:
            x, y = info["xy"]
            obs[y, x, :] = focus_exact[label].astype(np.float32)
    return obs


def find_positive_reference(
    *,
    runtime_vec: np.ndarray,
    bc_dir: Path,
    target_action: int,
    target_unit_ch: int,
    chunk_size: int,
) -> PositiveSample:
    obs_key = "observations"
    act_key = "actions"

    best: Optional[PositiveSample] = None

    for split_name, npz_path in (("train", bc_dir / "bc_train.npz"), ("validation", bc_dir / "bc_validation.npz")):
        for start, obs_chunk, act_chunk in iter_paired_rows(npz_path, obs_key, act_key, rows_per_chunk=chunk_size):
            for i in range(obs_chunk.shape[0]):
                obs = obs_chunk[i]
                act = act_chunk[i]
                action_type = act[:, 0]
                unit_mask = obs[:, target_unit_ch] > 0.5
                idx = np.where((action_type == target_action) & unit_mask)[0]
                if idx.size == 0:
                    continue

                for flat in idx.tolist():
                    vec = obs[int(flat)].astype(np.float32)
                    dist = float(np.linalg.norm((vec - runtime_vec).astype(np.float64)))
                    if best is None or dist < best.dist_to_runtime:
                        best = PositiveSample(
                            split=split_name,
                            sample_index=int(start + i),
                            flat_index=int(flat),
                            vector=vec.copy(),
                            obs_map=obs.reshape(24, 24, 27).astype(np.float32).copy(),
                            dist_to_runtime=dist,
                        )
    if best is None:
        raise RuntimeError("No positive reference found in BC dataset")
    return best


def find_raw_fullmap_candidates(obj: Any, path: str = "root", max_hits: int = 20) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []

    def rec(v: Any, p: str) -> None:
        if len(hits) >= max_hits:
            return
        if isinstance(v, list):
            if len(v) == 576 and v and all(isinstance(x, list) and len(x) == 27 for x in v[: min(8, len(v))]):
                hits.append({"path": p, "shape_hint": [576, 27], "kind": "list_of_576x27"})
            if len(v) == 24 and v and all(isinstance(x, list) and len(x) == 24 for x in v[: min(8, len(v))]):
                # Possible [24][24][27] structure.
                ok = True
                for row in v[: min(6, len(v))]:
                    if not all(isinstance(cell, list) and len(cell) == 27 for cell in row[: min(6, len(row))]):
                        ok = False
                        break
                if ok:
                    hits.append({"path": p, "shape_hint": [24, 24, 27], "kind": "list_of_24x24x27"})
            if len(v) > 0:
                rec(v[0], p + "[0]")
        elif isinstance(v, dict):
            for k, vv in v.items():
                rec(vv, p + f".{k}")

    rec(obj, path)
    return hits


def availability_classification(
    *,
    runtime_cell_rows: List[Dict[str, Any]],
    stage10r_snapshot: Dict[str, Any],
    stage10d10_logits_snapshot: Dict[str, Any],
    stage10d11_fullmap: Dict[str, Any],
) -> Dict[str, Any]:
    raw_hits_stage10r = find_raw_fullmap_candidates(stage10r_snapshot)
    raw_hits_logits = find_raw_fullmap_candidates(stage10d10_logits_snapshot)
    raw_hits_stage10d11 = find_raw_fullmap_candidates(stage10d11_fullmap)

    has_focus_raw = False
    actor_cells = stage10r_snapshot.get("actor_cells", [])
    if isinstance(actor_cells, list):
        for r in actor_cells:
            if isinstance(r, Mapping) and isinstance(r.get("cell_observation_channels"), list) and len(r.get("cell_observation_channels", [])) == 27:
                has_focus_raw = True
                break

    has_full_raw = bool(raw_hits_stage10r or raw_hits_logits or raw_hits_stage10d11)
    has_reconstructed = "runtime_reconstructed_map_summary" in stage10d11_fullmap

    if has_full_raw:
        status = "FULL_RAW_576_AVAILABLE"
    elif has_focus_raw:
        status = "FOCUS_ONLY_RAW_AVAILABLE"
    elif has_reconstructed:
        status = "RECONSTRUCTED_FULLMAP_ONLY"
    else:
        status = "RAW_OBSERVATION_UNAVAILABLE"

    return {
        "generated_at_utc": utc_now(),
        "classification": status,
        "full_raw_576_available": has_full_raw,
        "focus_only_raw_available": has_focus_raw,
        "reconstructed_fullmap_available": has_reconstructed,
        "strict_probes": bool(has_full_raw),
        "preliminary_probes_based_on_reconstructed_fullmap": not bool(has_full_raw),
        "go_for_stage10d12r_full_raw_observation_capture": not bool(has_full_raw),
        "evidence": {
            "stage10r_full_raw_candidates": raw_hits_stage10r,
            "stage10d10_logits_full_raw_candidates": raw_hits_logits,
            "stage10d11_fullmap_candidates": raw_hits_stage10d11,
            "stage10d10_cell_table_row_count": int(len(runtime_cell_rows)),
            "stage10r_actor_cells_with_27ch": int(
                sum(
                    1
                    for r in actor_cells
                    if isinstance(r, Mapping)
                    and isinstance(r.get("cell_observation_channels"), list)
                    and len(r.get("cell_observation_channels", [])) == 27
                )
            ),
        },
    }


def summarize_scene(obs_map: np.ndarray, focus_b2_xy: Tuple[int, int], focus_c3_xy: Tuple[int, int]) -> Dict[str, Any]:
    flat = obs_map.reshape(576, 27)
    owner = np.argmax(flat[:, 2:5], axis=1)
    unit = np.argmax(flat[:, 5:12], axis=1)
    unit_present = np.max(flat[:, 5:12], axis=1) > 0.5

    counts = {
        "friendly_actor_count": int(np.sum(unit_present & (unit != 0) & (owner == 1))),
        "enemy_actor_count": int(np.sum(unit_present & (unit != 0) & (owner == 2))),
        "workers_count": int(np.sum(unit_present & (unit == 3))),
        "bases_count": int(np.sum(unit_present & (unit == 1))),
        "barracks_count": int(np.sum(unit_present & (unit == 2))),
        "resources_count": int(np.sum(unit_present & (unit == 0))),
        "empty_cells_count": int(np.sum(~unit_present)),
    }

    worker_cells = np.where(unit_present & (unit == 3) & (owner == 1))[0]
    base_cells = np.where(unit_present & (unit == 1) & (owner == 1))[0]
    resource_cells = np.where(unit_present & (unit == 0))[0]

    def min_dist_set(src: np.ndarray, dst: np.ndarray) -> Optional[float]:
        if src.size == 0 or dst.size == 0:
            return None
        src_xy = np.asarray([flat_to_xy(int(i)) for i in src], dtype=np.float32)
        dst_xy = np.asarray([flat_to_xy(int(i)) for i in dst], dtype=np.float32)
        d = np.sqrt(((src_xy[:, None, :] - dst_xy[None, :, :]) ** 2).sum(axis=2))
        return float(np.min(d))

    def surrounding_free_cells_for_base(flat_idx: int) -> int:
        x, y = flat_to_xy(int(flat_idx))
        free = 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                xx = x + dx
                yy = y + dy
                if not (0 <= xx < 24 and 0 <= yy < 24):
                    continue
                f = xy_to_flat(xx, yy)
                if not bool(unit_present[f]):
                    free += 1
        return int(free)

    base_free_counts = [surrounding_free_cells_for_base(int(f)) for f in base_cells.tolist()]

    def adjacent_counts_for_base(flat_idx: int, unit_kind: int) -> int:
        x, y = flat_to_xy(int(flat_idx))
        c = 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                xx = x + dx
                yy = y + dy
                if not (0 <= xx < 24 and 0 <= yy < 24):
                    continue
                f = xy_to_flat(xx, yy)
                if bool(unit_present[f]) and int(unit[f]) == unit_kind:
                    c += 1
        return int(c)

    base_adj_workers = [adjacent_counts_for_base(int(f), 3) for f in base_cells.tolist()]
    base_adj_resources = [adjacent_counts_for_base(int(f), 0) for f in base_cells.tolist()]

    def enemy_in_patch(center_xy: Tuple[int, int], radius: int = 2) -> int:
        x, y = center_xy
        c = 0
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                xx = x + dx
                yy = y + dy
                if not (0 <= xx < 24 and 0 <= yy < 24):
                    continue
                f = xy_to_flat(xx, yy)
                if bool(unit_present[f]) and int(unit[f]) != 0 and int(owner[f]) == 2:
                    c += 1
        return int(c)

    return {
        **counts,
        "distance_worker_to_resource_min": min_dist_set(worker_cells, resource_cells),
        "distance_worker_to_base_min": min_dist_set(worker_cells, base_cells),
        "base_surrounding_free_cells_mean": float(np.mean(base_free_counts)) if base_free_counts else None,
        "base_adjacent_resources_mean": float(np.mean(base_adj_resources)) if base_adj_resources else None,
        "base_adjacent_workers_mean": float(np.mean(base_adj_workers)) if base_adj_workers else None,
        "enemy_presence_around_b2_patch5": enemy_in_patch(focus_b2_xy, radius=2),
        "enemy_presence_around_c3_patch5": enemy_in_patch(focus_c3_xy, radius=2),
    }


def choose_b2_classification(group_results: List[Dict[str, Any]], reverse_results: List[Dict[str, Any]]) -> str:
    by_name = {r["probe_name"]: r for r in group_results}

    def helps(name: str) -> bool:
        r = by_name.get(name)
        return bool(r and r.get("harvest_top1") and r.get("p_harvest_gt_0_5") and r.get("p_noop_lt_0_5"))

    if helps("current_action_only"):
        return "B2_CURRENT_ACTION_MISMATCH"
    if helps("direction_only"):
        return "B2_DIRECTION_MISMATCH"
    if helps("scalars_only"):
        return "B2_SCALAR_MISMATCH"
    if helps("owner_plus_unit_type") and (helps("current_action_only") or helps("direction_only")):
        return "B2_OWNER_UNIT_OK_BUT_ACTION_CONTEXT_BAD"

    reverse_harmful = [r for r in reverse_results if r.get("harvest_destroyed")]
    if reverse_harmful:
        names = {r["probe_name"] for r in reverse_harmful}
        if "current_action_only" in names or "direction_only" in names:
            return "B2_OWNER_UNIT_OK_BUT_ACTION_CONTEXT_BAD"
        return "B2_CELL_CONTEXT_MIXED"

    return "B2_INCONCLUSIVE"


def choose_c3_classification(
    radius_results: List[Dict[str, Any]],
    decomposition_results: List[Dict[str, Any]],
    neighbor_summary: Dict[str, Any],
) -> str:
    by_radius = {r["probe_name"]: r for r in radius_results}

    cell_only = by_radius.get("cell_only")
    patch5 = by_radius.get("patch_5x5")
    patch7 = by_radius.get("patch_7x7")

    if cell_only and not cell_only.get("produce_top1"):
        if patch5 and patch5.get("produce_top1"):
            if neighbor_summary.get("small_subset_sufficient"):
                return "C3_NEIGHBOR_CONTEXT_REQUIRED"
            return "C3_CENTER_CELL_NOT_SUFFICIENT"

    by_name = {r["probe_name"]: r for r in decomposition_results}
    if by_name.get("owner_plus_unit_type", {}).get("produce_top1"):
        return "C3_OWNER_UNIT_CONTEXT_REQUIRED"
    if by_name.get("owner_plus_unit_type_plus_current_action_plus_direction", {}).get("produce_top1"):
        return "C3_CURRENT_ACTION_DIRECTION_CONTEXT_REQUIRED"
    if by_name.get("only_neighbor_cells_excluding_center", {}).get("produce_top1"):
        return "C3_NEIGHBOR_CONTEXT_REQUIRED"
    if patch7 and patch7.get("produce_top1") and not (patch5 and patch5.get("produce_top1")):
        return "C3_LOCAL_CONTEXT_OOD"

    return "C3_INCONCLUSIVE"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.12 runtime channel/context fix candidate audit")
    p.add_argument(
        "--runtime-cell-table",
        type=Path,
        default=Path("python/week6_student/reports/stage10d10_global_runtime_cell_table_step0001.jsonl"),
    )
    p.add_argument(
        "--runtime-logits-snapshot",
        type=Path,
        default=Path("python/week6_student/reports/stage10d10_global_runtime_logits_snapshot_step0001.json"),
    )
    p.add_argument(
        "--runtime-summary",
        type=Path,
        default=Path("python/week6_student/reports/stage10d10_global_runtime_summary.json"),
    )
    p.add_argument(
        "--legacy-runtime-snapshot",
        type=Path,
        default=Path("python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json"),
    )
    p.add_argument(
        "--stage10d11-focus-audit",
        type=Path,
        default=Path("python/week6_student/reports/stage10d11_runtime_focus_cell_channel_audit.json"),
    )
    p.add_argument(
        "--stage10d11-fullmap-comparison",
        type=Path,
        default=Path("python/week6_student/reports/stage10d11_full_map_context_comparison.json"),
    )
    p.add_argument(
        "--stage10d11-counterfactual",
        type=Path,
        default=Path("python/week6_student/reports/stage10d11_counterfactual_probe_results.json"),
    )
    p.add_argument(
        "--bc-ready-dir",
        type=Path,
        default=Path(
            "python/week6_student/bc_ready/"
            "legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z"
        ),
    )
    p.add_argument(
        "--checkpoint",
        type=Path,
        default=Path(
            "python/week6_student/runs/legacy032_v2_semantic_bc_stage10d8_20260503T093718Z/"
            "student_bc_semantic_best.pt"
        ),
    )
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--chunk-size", type=int, default=32)
    p.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("python/week6_student/reports"),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = repo_root()

    runtime_cell_table = (root / args.runtime_cell_table).resolve()
    runtime_logits_snapshot = (root / args.runtime_logits_snapshot).resolve()
    runtime_summary_path = (root / args.runtime_summary).resolve()
    legacy_runtime_snapshot = (root / args.legacy_runtime_snapshot).resolve()
    stage10d11_focus = (root / args.stage10d11_focus_audit).resolve()
    stage10d11_fullmap = (root / args.stage10d11_fullmap_comparison).resolve()
    stage10d11_counterfactual = (root / args.stage10d11_counterfactual).resolve()
    bc_dir = (root / args.bc_ready_dir).resolve()
    checkpoint = (root / args.checkpoint).resolve()
    reports_dir = (root / args.reports_dir).resolve()

    for p in (
        runtime_cell_table,
        runtime_logits_snapshot,
        runtime_summary_path,
        legacy_runtime_snapshot,
        stage10d11_focus,
        stage10d11_fullmap,
        stage10d11_counterfactual,
        bc_dir / "bc_train.npz",
        bc_dir / "bc_validation.npz",
        checkpoint,
    ):
        if not p.exists():
            raise RuntimeError(f"Missing required input: {p}")

    out_paths = {
        "availability": reports_dir / "stage10d12_raw_fullmap_observation_availability_audit.json",
        "b2_group": reports_dir / "stage10d12_b2_channel_group_isolation_probe.json",
        "b2_channel": reports_dir / "stage10d12_b2_per_channel_isolation_probe.json",
        "c3_decomp": reports_dir / "stage10d12_c3_local_context_decomposition_probe.json",
        "c3_neighbor": reports_dir / "stage10d12_c3_neighbor_cell_importance_probe.json",
        "decision": reports_dir / "stage10d12_candidate_fix_decision_matrix.json",
        "report": reports_dir / "STAGE10D12_RUNTIME_CHANNEL_AND_CONTEXT_FIX_CANDIDATE_AUDIT_REPORT.md",
    }

    runtime_rows = read_jsonl(runtime_cell_table)
    runtime_logits_payload = read_json(runtime_logits_snapshot)
    runtime_summary_payload = read_json(runtime_summary_path)
    stage10r_payload = read_json(legacy_runtime_snapshot)
    stage10d11_focus_payload = read_json(stage10d11_focus)
    stage10d11_fullmap_payload = read_json(stage10d11_fullmap)
    stage10d11_counter_payload = read_json(stage10d11_counterfactual)

    if len(runtime_rows) != 576:
        raise RuntimeError(f"Expected 576 runtime rows, got {len(runtime_rows)}")

    availability_payload = availability_classification(
        runtime_cell_rows=runtime_rows,
        stage10r_snapshot=stage10r_payload,
        stage10d10_logits_snapshot=runtime_logits_payload,
        stage10d11_fullmap=stage10d11_fullmap_payload,
    )
    write_json(out_paths["availability"], availability_payload)

    focus_exact = extract_focus_vectors_from_legacy_snapshot(legacy_runtime_snapshot)
    runtime_map = reconstruct_runtime_map(runtime_rows, focus_exact)

    b2_flat = int(FOCUS["B2"]["flat"])
    c3_flat = int(FOCUS["C3"]["flat"])
    b2_xy = tuple(int(x) for x in FOCUS["B2"]["xy"])
    c3_xy = tuple(int(x) for x in FOCUS["C3"]["xy"])

    b2_runtime_vec = runtime_map[b2_xy[1], b2_xy[0], :].copy()
    c3_runtime_vec = runtime_map[c3_xy[1], c3_xy[0], :].copy()

    worker_ref = find_positive_reference(
        runtime_vec=b2_runtime_vec,
        bc_dir=bc_dir,
        target_action=2,
        target_unit_ch=8,
        chunk_size=args.chunk_size,
    )
    base_ref = find_positive_reference(
        runtime_vec=c3_runtime_vec,
        bc_dir=bc_dir,
        target_action=4,
        target_unit_ch=6,
        chunk_size=args.chunk_size,
    )

    device = torch.device(args.device)
    model = build_day3_student_model().to(device=device)
    ckpt = torch.load(checkpoint, map_location=device)
    if "model_state_dict" not in ckpt:
        raise RuntimeError("Checkpoint missing model_state_dict")
    model.load_state_dict(ckpt["model_state_dict"], strict=True)

    baseline_probs = run_student(model, runtime_map, device=device)
    b2_baseline = eval_cell_probs(baseline_probs, b2_flat)
    c3_baseline = eval_cell_probs(baseline_probs, c3_flat)

    # 2) B2 group isolation + reverse ablation.
    b2_group_forward: List[Dict[str, Any]] = []
    b2_group_reverse: List[Dict[str, Any]] = []

    src_wx, src_wy = flat_to_xy(worker_ref.flat_index)

    worker_base_probs = run_student(model, worker_ref.obs_map, device=device)
    worker_ref_before = eval_cell_probs(worker_base_probs, worker_ref.flat_index)

    for probe_name, channels in B2_GROUP_PROBES:
        obs = runtime_map.copy()
        obs[b2_xy[1], b2_xy[0], channels] = worker_ref.vector[channels]
        p = run_student(model, obs, device=device)
        r = eval_cell_probs(p, b2_flat)
        r.update(
            {
                "probe_name": probe_name,
                "channels": [int(c) for c in channels],
                "channel_names": [CHANNEL_NAMES[int(c)] for c in channels],
                "delta_from_runtime": {
                    "delta_p_noop": float(r["p_noop"] - b2_baseline["p_noop"]),
                    "delta_p_harvest": float(r["p_harvest"] - b2_baseline["p_harvest"]),
                    "delta_p_produce": float(r["p_produce"] - b2_baseline["p_produce"]),
                },
                "harvest_top1": bool(r["predicted_action"] == "Harvest"),
                "p_noop_lt_0_5": bool(r["p_noop"] < 0.5),
                "p_harvest_gt_0_5": bool(r["p_harvest"] > 0.5),
            }
        )
        b2_group_forward.append(r)

        rev = worker_ref.obs_map.copy()
        rev[src_wy, src_wx, channels] = b2_runtime_vec[channels]
        p_rev = run_student(model, rev, device=device)
        rr = eval_cell_probs(p_rev, worker_ref.flat_index)
        rr.update(
            {
                "probe_name": probe_name,
                "channels": [int(c) for c in channels],
                "channel_names": [CHANNEL_NAMES[int(c)] for c in channels],
                "delta_from_worker_reference": {
                    "delta_p_noop": float(rr["p_noop"] - worker_ref_before["p_noop"]),
                    "delta_p_harvest": float(rr["p_harvest"] - worker_ref_before["p_harvest"]),
                },
                "harvest_destroyed": bool(rr["predicted_action"] != "Harvest"),
                "p_noop_gt_0_5": bool(rr["p_noop"] > 0.5),
            }
        )
        b2_group_reverse.append(rr)

    b2_classification = choose_b2_classification(b2_group_forward, b2_group_reverse)

    b2_group_payload = {
        "generated_at_utc": utc_now(),
        "based_on_reconstructed_fullmap": bool(
            availability_payload["preliminary_probes_based_on_reconstructed_fullmap"]
        ),
        "runtime_b2_baseline": b2_baseline,
        "reference_worker_harvest": {
            "split": worker_ref.split,
            "sample_index": int(worker_ref.sample_index),
            "flat_index": int(worker_ref.flat_index),
            "xy": [int(src_wx), int(src_wy)],
            "dist_to_runtime_b2_l2": float(worker_ref.dist_to_runtime),
            "reference_cell_probs": worker_ref_before,
        },
        "forward_group_patch_results": b2_group_forward,
        "reverse_group_ablation_results": b2_group_reverse,
        "classification": b2_classification,
    }
    write_json(out_paths["b2_group"], b2_group_payload)

    # 3) B2 per-channel isolation.
    b2_channel_results: List[Dict[str, Any]] = []

    for ch in B2_PER_CHANNELS:
        obs = runtime_map.copy()
        obs[b2_xy[1], b2_xy[0], ch] = worker_ref.vector[ch]
        p_fwd = run_student(model, obs, device=device)
        f = eval_cell_probs(p_fwd, b2_flat)

        rev = worker_ref.obs_map.copy()
        rev[src_wy, src_wx, ch] = b2_runtime_vec[ch]
        p_rev = run_student(model, rev, device=device)
        r = eval_cell_probs(p_rev, worker_ref.flat_index)

        row = {
            "channel_index": int(ch),
            "channel_name": CHANNEL_NAMES[ch],
            "forward_patch_runtime_to_bc_channel": {
                **f,
                "delta_p_harvest": float(f["p_harvest"] - b2_baseline["p_harvest"]),
                "delta_p_noop": float(f["p_noop"] - b2_baseline["p_noop"]),
            },
            "reverse_patch_bc_to_runtime_channel": {
                **r,
                "delta_p_harvest": float(r["p_harvest"] - worker_ref_before["p_harvest"]),
                "delta_p_noop": float(r["p_noop"] - worker_ref_before["p_noop"]),
            },
            "impact_score": {
                "forward_harvest_gain": float(f["p_harvest"] - b2_baseline["p_harvest"]),
                "forward_noop_drop": float(b2_baseline["p_noop"] - f["p_noop"]),
                "reverse_harvest_drop": float(worker_ref_before["p_harvest"] - r["p_harvest"]),
                "reverse_noop_gain": float(r["p_noop"] - worker_ref_before["p_noop"]),
            },
        }
        b2_channel_results.append(row)

    ranked = sorted(
        b2_channel_results,
        key=lambda x: (
            x["impact_score"]["forward_harvest_gain"]
            + x["impact_score"]["forward_noop_drop"]
            + x["impact_score"]["reverse_harvest_drop"]
            + x["impact_score"]["reverse_noop_gain"]
        ),
        reverse=True,
    )

    b2_channel_payload = {
        "generated_at_utc": utc_now(),
        "triggered_by_groups": {
            "current_action_or_direction_or_scalars_flag": bool(
                b2_classification
                in {
                    "B2_CURRENT_ACTION_MISMATCH",
                    "B2_DIRECTION_MISMATCH",
                    "B2_SCALAR_MISMATCH",
                    "B2_OWNER_UNIT_OK_BUT_ACTION_CONTEXT_BAD",
                }
            )
        },
        "runtime_b2_baseline": b2_baseline,
        "reference_worker_harvest": {
            "split": worker_ref.split,
            "sample_index": int(worker_ref.sample_index),
            "flat_index": int(worker_ref.flat_index),
            "reference_cell_probs": worker_ref_before,
        },
        "per_channel_results": b2_channel_results,
        "ranked_channels_by_combined_impact": [
            {
                "channel_index": int(r["channel_index"]),
                "channel_name": r["channel_name"],
                "combined_score": float(
                    r["impact_score"]["forward_harvest_gain"]
                    + r["impact_score"]["forward_noop_drop"]
                    + r["impact_score"]["reverse_harvest_drop"]
                    + r["impact_score"]["reverse_noop_gain"]
                ),
            }
            for r in ranked
        ],
        "minimal_channel_set_candidate": [int(r["channel_index"]) for r in ranked[:3]],
    }
    write_json(out_paths["b2_channel"], b2_channel_payload)

    # 4) C3 local context decomposition.
    src_bx, src_by = flat_to_xy(base_ref.flat_index)
    base_ref_probs = run_student(model, base_ref.obs_map, device=device)
    c3_ref_before = eval_cell_probs(base_ref_probs, base_ref.flat_index)

    c3_radius_results: List[Dict[str, Any]] = []
    for radius, name in ((0, "cell_only"), (1, "patch_3x3"), (2, "patch_5x5"), (3, "patch_7x7")):
        obs = apply_patch_from_source(
            runtime_map,
            target_xy=c3_xy,
            source_map=base_ref.obs_map,
            source_xy=(src_bx, src_by),
            radius=radius,
            channels=None,
            include_center=True,
        )
        p = run_student(model, obs, device=device)
        r = eval_cell_probs(p, c3_flat)
        r.update(
            {
                "probe_name": name,
                "radius": int(radius),
                "delta_from_runtime": {
                    "delta_p_noop": float(r["p_noop"] - c3_baseline["p_noop"]),
                    "delta_p_produce": float(r["p_produce"] - c3_baseline["p_produce"]),
                },
                "produce_top1": bool(r["predicted_action"] == "Produce"),
            }
        )
        c3_radius_results.append(r)

    min_radius_restore = None
    for r in c3_radius_results:
        if r["produce_top1"]:
            min_radius_restore = int(r["radius"])
            break

    decomp_specs: List[Tuple[str, Optional[List[int]], bool, bool]] = [
        ("owner_only_all_cells_5x5", GROUPS["owner"], True, True),
        ("unit_type_only_all_cells_5x5", GROUPS["unit_type"], True, True),
        ("current_action_only_all_cells_5x5", GROUPS["current_action"], True, True),
        ("direction_only_all_cells_5x5", GROUPS["direction"], True, True),
        ("scalar_only_all_cells_5x5", GROUPS["scalars"], True, True),
        ("owner_plus_unit_type", GROUPS["owner"] + GROUPS["unit_type"], True, True),
        (
            "owner_plus_unit_type_plus_current_action",
            GROUPS["owner"] + GROUPS["unit_type"] + GROUPS["current_action"],
            True,
            True,
        ),
        (
            "owner_plus_unit_type_plus_current_action_plus_direction",
            GROUPS["owner"] + GROUPS["unit_type"] + GROUPS["current_action"] + GROUPS["direction"],
            True,
            True,
        ),
        ("all_non_scalar_onehot_groups", list(range(2, 26)), True, True),
        ("all_groups_except_center_c3", None, False, True),
        ("only_neighbor_cells_excluding_center", None, False, True),
        ("only_center_c3", None, True, False),
    ]

    c3_decomp_results: List[Dict[str, Any]] = []
    for probe_name, channels, include_center, include_neighbors in decomp_specs:
        if probe_name == "only_center_c3":
            obs = runtime_map.copy()
            ch = np.arange(27, dtype=np.int64) if channels is None else np.asarray(channels, dtype=np.int64)
            obs[c3_xy[1], c3_xy[0], ch] = base_ref.obs_map[src_by, src_bx, ch]
        elif probe_name in {"all_groups_except_center_c3", "only_neighbor_cells_excluding_center"}:
            obs = apply_patch_from_source(
                runtime_map,
                target_xy=c3_xy,
                source_map=base_ref.obs_map,
                source_xy=(src_bx, src_by),
                radius=2,
                channels=channels,
                include_center=False,
            )
        else:
            obs = runtime_map.copy()
            if include_neighbors:
                obs = apply_patch_from_source(
                    obs,
                    target_xy=c3_xy,
                    source_map=base_ref.obs_map,
                    source_xy=(src_bx, src_by),
                    radius=2,
                    channels=channels,
                    include_center=include_center,
                )
            elif include_center:
                ch = np.arange(27, dtype=np.int64) if channels is None else np.asarray(channels, dtype=np.int64)
                obs[c3_xy[1], c3_xy[0], ch] = base_ref.obs_map[src_by, src_bx, ch]

        p = run_student(model, obs, device=device)
        r = eval_cell_probs(p, c3_flat)
        r.update(
            {
                "probe_name": probe_name,
                "channels": ([int(c) for c in channels] if channels is not None else "all_channels"),
                "delta_from_runtime": {
                    "delta_p_noop": float(r["p_noop"] - c3_baseline["p_noop"]),
                    "delta_p_produce": float(r["p_produce"] - c3_baseline["p_produce"]),
                },
                "produce_top1": bool(r["predicted_action"] == "Produce"),
            }
        )
        c3_decomp_results.append(r)

    # 5) C3 neighbor cell importance.
    neighbor_cells: List[Tuple[int, int]] = []
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if dx == 0 and dy == 0:
                continue
            xx = c3_xy[0] + dx
            yy = c3_xy[1] + dy
            if 0 <= xx < 24 and 0 <= yy < 24:
                neighbor_cells.append((xx, yy))

    src_neighbor_cells = [(src_bx + (x - c3_xy[0]), src_by + (y - c3_xy[1])) for x, y in neighbor_cells]

    one_cell_results: List[Dict[str, Any]] = []

    def cell_kind(vec: np.ndarray) -> Dict[str, Any]:
        owner = int(np.argmax(vec[2:5]))
        unit = int(np.argmax(vec[5:12]))
        present = bool(np.max(vec[5:12]) > 0.5)
        return {
            "owner_idx": owner,
            "unit_idx": unit,
            "is_empty": not present,
            "is_worker": bool(present and unit == 3),
            "is_resource": bool(present and unit == 0),
            "is_friendly": bool(present and owner == 1),
            "is_enemy": bool(present and owner == 2),
            "is_neutral": bool(owner == 0),
        }

    for (tx, ty), (sx, sy) in zip(neighbor_cells, src_neighbor_cells):
        if not (0 <= sx < 24 and 0 <= sy < 24):
            continue
        obs = runtime_map.copy()
        obs[ty, tx, :] = base_ref.obs_map[sy, sx, :]
        p = run_student(model, obs, device=device)
        r = eval_cell_probs(p, c3_flat)
        kind = cell_kind(base_ref.obs_map[sy, sx, :])
        row = {
            "target_xy": [int(tx), int(ty)],
            "source_xy": [int(sx), int(sy)],
            "target_flat": int(xy_to_flat(tx, ty)),
            "source_flat": int(xy_to_flat(sx, sy)),
            "semantic_flags": kind,
            "p_noop": float(r["p_noop"]),
            "p_produce": float(r["p_produce"]),
            "predicted_action": r["predicted_action"],
            "delta_p_produce": float(r["p_produce"] - c3_baseline["p_produce"]),
            "delta_p_noop": float(r["p_noop"] - c3_baseline["p_noop"]),
        }
        one_cell_results.append(row)

    one_cell_results.sort(key=lambda x: x["delta_p_produce"], reverse=True)

    def apply_neighbor_set(target_cells: List[Tuple[int, int]]) -> Dict[str, Any]:
        obs = runtime_map.copy()
        for tx, ty in target_cells:
            sx = src_bx + (tx - c3_xy[0])
            sy = src_by + (ty - c3_xy[1])
            if 0 <= sx < 24 and 0 <= sy < 24:
                obs[ty, tx, :] = base_ref.obs_map[sy, sx, :]
        p = run_student(model, obs, device=device)
        r = eval_cell_probs(p, c3_flat)
        return {
            "patched_cell_count": int(len(target_cells)),
            "target_cells": [[int(x), int(y)] for x, y in target_cells],
            "predicted_action": r["predicted_action"],
            "p_noop": float(r["p_noop"]),
            "p_produce": float(r["p_produce"]),
            "delta_p_produce": float(r["p_produce"] - c3_baseline["p_produce"]),
            "delta_p_noop": float(r["p_noop"] - c3_baseline["p_noop"]),
            "produce_top1": bool(r["predicted_action"] == "Produce"),
        }

    top1 = [(one_cell_results[0]["target_xy"][0], one_cell_results[0]["target_xy"][1])] if one_cell_results else []
    top2 = [tuple(r["target_xy"]) for r in one_cell_results[:2]]
    top3 = [tuple(r["target_xy"]) for r in one_cell_results[:3]]

    same_row = [(x, y) for x, y in neighbor_cells if y == c3_xy[1]]
    same_col = [(x, y) for x, y in neighbor_cells if x == c3_xy[0]]

    resource_cells = [tuple(r["target_xy"]) for r in one_cell_results if r["semantic_flags"]["is_resource"]]
    worker_cells = [tuple(r["target_xy"]) for r in one_cell_results if r["semantic_flags"]["is_worker"]]
    empty_cells = [tuple(r["target_xy"]) for r in one_cell_results if r["semantic_flags"]["is_empty"]]
    friendly_cells = [tuple(r["target_xy"]) for r in one_cell_results if r["semantic_flags"]["is_friendly"]]
    enemy_cells = [tuple(r["target_xy"]) for r in one_cell_results if r["semantic_flags"]["is_enemy"]]
    neutral_or_resource = [
        tuple(r["target_xy"]) for r in one_cell_results if r["semantic_flags"]["is_neutral"] or r["semantic_flags"]["is_resource"]
    ]

    combination_results = {
        "top_1_neighbor": apply_neighbor_set(top1),
        "top_2_neighbors": apply_neighbor_set(top2),
        "top_3_neighbors": apply_neighbor_set(top3),
        "same_row_as_c3": apply_neighbor_set(same_row),
        "same_column_as_c3": apply_neighbor_set(same_col),
        "resource_cells_only": apply_neighbor_set(resource_cells),
        "worker_cells_only": apply_neighbor_set(worker_cells),
        "empty_free_cells_only": apply_neighbor_set(empty_cells),
        "friendly_cells_only": apply_neighbor_set(friendly_cells),
        "enemy_cells_only": apply_neighbor_set(enemy_cells),
        "neutral_or_resource_cells_only": apply_neighbor_set(neutral_or_resource),
    }

    small_subset_sufficient = any(
        bool(combination_results[k]["produce_top1"]) for k in ("top_1_neighbor", "top_2_neighbors", "top_3_neighbors")
    )

    c3_neighbor_payload = {
        "generated_at_utc": utc_now(),
        "runtime_c3_baseline": c3_baseline,
        "reference_base_produce": {
            "split": base_ref.split,
            "sample_index": int(base_ref.sample_index),
            "flat_index": int(base_ref.flat_index),
            "xy": [int(src_bx), int(src_by)],
            "dist_to_runtime_c3_l2": float(base_ref.dist_to_runtime),
            "reference_cell_probs": c3_ref_before,
        },
        "single_neighbor_results": one_cell_results,
        "combination_results": combination_results,
        "summary": {
            "most_important_neighbors": one_cell_results[:5],
            "small_subset_sufficient": bool(small_subset_sufficient),
            "produce_requires_full_5x5_context": bool(
                not small_subset_sufficient and not bool(combination_results["same_row_as_c3"]["produce_top1"])
            ),
        },
    }
    write_json(out_paths["c3_neighbor"], c3_neighbor_payload)

    c3_classification = choose_c3_classification(c3_radius_results, c3_decomp_results, c3_neighbor_payload["summary"])

    c3_decomp_payload = {
        "generated_at_utc": utc_now(),
        "based_on_reconstructed_fullmap": bool(
            availability_payload["preliminary_probes_based_on_reconstructed_fullmap"]
        ),
        "runtime_c3_baseline": c3_baseline,
        "reference_base_produce": {
            "split": base_ref.split,
            "sample_index": int(base_ref.sample_index),
            "flat_index": int(base_ref.flat_index),
            "xy": [int(src_bx), int(src_by)],
            "dist_to_runtime_c3_l2": float(base_ref.dist_to_runtime),
            "reference_cell_probs": c3_ref_before,
        },
        "radius_patch_results": c3_radius_results,
        "minimal_radius_restoring_produce": min_radius_restore,
        "decomposition_5x5_results": c3_decomp_results,
        "classification": c3_classification,
    }
    write_json(out_paths["c3_decomp"], c3_decomp_payload)

    # 6) Scene distribution check.
    runtime_scene = summarize_scene(runtime_map, focus_b2_xy=b2_xy, focus_c3_xy=c3_xy)
    worker_scene = summarize_scene(worker_ref.obs_map, focus_b2_xy=flat_to_xy(worker_ref.flat_index), focus_c3_xy=flat_to_xy(base_ref.flat_index))
    base_scene = summarize_scene(base_ref.obs_map, focus_b2_xy=flat_to_xy(worker_ref.flat_index), focus_c3_xy=flat_to_xy(base_ref.flat_index))

    scene_numeric_keys = [
        "friendly_actor_count",
        "enemy_actor_count",
        "workers_count",
        "bases_count",
        "barracks_count",
        "resources_count",
        "empty_cells_count",
        "enemy_presence_around_c3_patch5",
        "enemy_presence_around_b2_patch5",
    ]

    def scene_delta(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k in scene_numeric_keys:
            out[k] = float(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))))
        for k in (
            "distance_worker_to_resource_min",
            "distance_worker_to_base_min",
            "base_surrounding_free_cells_mean",
            "base_adjacent_resources_mean",
            "base_adjacent_workers_mean",
        ):
            av = a.get(k)
            bv = b.get(k)
            if av is None or bv is None:
                out[k] = None
            else:
                out[k] = float(abs(float(av) - float(bv)))
        return out

    delta_runtime_vs_worker = scene_delta(runtime_scene, worker_scene)
    delta_runtime_vs_base = scene_delta(runtime_scene, base_scene)

    scene_delta_score = 0.0
    for d in (delta_runtime_vs_worker, delta_runtime_vs_base):
        for v in d.values():
            if v is None:
                continue
            scene_delta_score += float(v)

    scene_ood_likely = bool(scene_delta_score >= 12.0)

    # 7) Candidate decision matrix + 8/9 classification and next gate.
    b2_current_dir_like = b2_classification in {
        "B2_CURRENT_ACTION_MISMATCH",
        "B2_DIRECTION_MISMATCH",
        "B2_OWNER_UNIT_OK_BUT_ACTION_CONTEXT_BAD",
    }
    b2_channel_semantic_like = b2_classification in {
        "B2_CURRENT_ACTION_MISMATCH",
        "B2_DIRECTION_MISMATCH",
        "B2_SCALAR_MISMATCH",
        "B2_OWNER_UNIT_OK_BUT_ACTION_CONTEXT_BAD",
    }
    c3_neighbor_required = c3_classification in {
        "C3_NEIGHBOR_CONTEXT_REQUIRED",
        "C3_CENTER_CELL_NOT_SUFFICIENT",
    }

    full_raw_missing = not bool(availability_payload["full_raw_576_available"])

    labels: List[str] = []
    if full_raw_missing:
        labels.append("FULL_RAW_OBSERVATION_CAPTURE_REQUIRED")

    if b2_channel_semantic_like:
        labels.append("B2_RUNTIME_CHANNEL_SEMANTIC_MISMATCH")
    if b2_current_dir_like:
        labels.append("B2_CURRENT_ACTION_DIRECTION_MISMATCH")

    if c3_classification == "C3_LOCAL_CONTEXT_OOD":
        labels.append("C3_LOCAL_CONTEXT_REQUIRED")
    if c3_neighbor_required:
        labels.append("C3_NEIGHBOR_CONTEXT_REQUIRED")

    if scene_ood_likely:
        labels.append("UNITY_SCENE_DISTRIBUTION_MISMATCH_CONFIRMED")

    if b2_channel_semantic_like and not full_raw_missing:
        labels.append("UNITY_OBSERVATION_BUILDER_FIX_REQUIRED")
        labels.append("RUNTIME_CHANNEL_REMAP_FIX_REQUIRED")

    if scene_ood_likely and not b2_channel_semantic_like:
        labels.append("TARGETED_BC_AUGMENTATION_LIKELY_REQUIRED")

    if not labels:
        labels.append("INCONCLUSIVE_NEEDS_STAGE10D12R")

    candidates = {
        "Candidate_A_Unity_observation_channel_semantic_remap_fix": {
            "evidence_for": [
                f"B2 classification={b2_classification}",
                "Group/per-channel probes show B2 sensitivity to channel semantics" if b2_channel_semantic_like else "No strong B2 semantic evidence",
            ],
            "evidence_against": [
                "Full raw 576 observation not available" if full_raw_missing else "Full raw available",
                "C3 issue appears context-driven" if c3_neighbor_required else "C3 may not require neighbor context",
            ],
            "risk": "medium",
            "expected_effort": "medium",
            "recommended": bool(b2_channel_semantic_like and not full_raw_missing),
        },
        "Candidate_B_Unity_full_raw_observation_extraction_fix_first": {
            "evidence_for": [
                f"raw availability classification={availability_payload['classification']}",
                "Current probes rely on reconstructed full-map for non-focus cells" if full_raw_missing else "Not required",
            ],
            "evidence_against": [
                "Would delay runtime fix implementation",
            ],
            "risk": "low",
            "expected_effort": "low",
            "recommended": bool(full_raw_missing),
        },
        "Candidate_C_Unity_scene_distribution_alignment": {
            "evidence_for": [
                f"scene_delta_score={scene_delta_score:.3f}",
                f"C3 classification={c3_classification}",
            ],
            "evidence_against": [
                "B2 channel mismatch may be primary for worker behavior" if b2_channel_semantic_like else "No strong contradictory signal",
            ],
            "risk": "medium",
            "expected_effort": "medium",
            "recommended": bool(scene_ood_likely and not b2_channel_semantic_like and not full_raw_missing),
        },
        "Candidate_D_Targeted_BC_augmentation_with_Unity_like_states": {
            "evidence_for": [
                "Relevant when observations are valid but state distribution differs",
                f"scene_ood_likely={scene_ood_likely}",
            ],
            "evidence_against": [
                "Not first action when channel semantics are unresolved",
                "Not first action while full raw is unavailable" if full_raw_missing else "",
            ],
            "risk": "medium",
            "expected_effort": "high",
            "recommended": bool(scene_ood_likely and not b2_channel_semantic_like and not full_raw_missing),
        },
        "Candidate_E_Student_objective_reweighting": {
            "evidence_for": [
                "Use only after data+observation validity confirmed",
            ],
            "evidence_against": [
                "Current stage still indicates observation/context mismatch candidates",
                "Offline BC confidence already high on positive samples",
            ],
            "risk": "high",
            "expected_effort": "high",
            "recommended": False,
        },
        "Candidate_F_Inconclusive_deeper_probes": {
            "evidence_for": [
                "Use when signals conflict",
                "Selected if no decisive candidate is recommended",
            ],
            "evidence_against": [
                "Can extend timeline",
            ],
            "risk": "low",
            "expected_effort": "medium",
            "recommended": False,
        },
    }

    if full_raw_missing:
        primary_next_gate = "GO_FOR_STAGE10D12R_FULL_RAW_OBSERVATION_CAPTURE"
    elif b2_channel_semantic_like:
        primary_next_gate = "GO_FOR_UNITY_OBSERVATION_CHANNEL_REMAP_FIX"
    elif scene_ood_likely and c3_neighbor_required:
        primary_next_gate = "GO_FOR_UNITY_SCENE_DISTRIBUTION_ALIGNMENT"
    elif scene_ood_likely:
        primary_next_gate = "GO_FOR_TARGETED_BC_AUGMENTATION_WITH_UNITY_LIKE_STATES"
    else:
        primary_next_gate = "GO_FOR_STAGE10D12R_DEEPER_PROBES"

    decision_payload = {
        "generated_at_utc": utc_now(),
        "runtime_scene_summary": runtime_scene,
        "bc_worker_reference_scene_summary": worker_scene,
        "bc_base_reference_scene_summary": base_scene,
        "scene_delta_runtime_vs_worker": delta_runtime_vs_worker,
        "scene_delta_runtime_vs_base": delta_runtime_vs_base,
        "scene_delta_score": float(scene_delta_score),
        "scene_ood_likely": bool(scene_ood_likely),
        "b2_classification": b2_classification,
        "c3_classification": c3_classification,
        "candidate_matrix": candidates,
        "final_classification_labels": labels,
        "primary_next_gate": primary_next_gate,
    }
    write_json(out_paths["decision"], decision_payload)

    # 10) Final markdown report.
    loaded_inputs = [
        runtime_cell_table,
        runtime_logits_snapshot,
        runtime_summary_path,
        legacy_runtime_snapshot,
        stage10d11_focus,
        (root / "python/week6_student/reports/stage10d11_bc_positive_sample_channel_stats.json").resolve(),
        (root / "python/week6_student/reports/stage10d11_runtime_vs_bc_channel_delta.json").resolve(),
        stage10d11_fullmap,
        (root / "python/week6_student/reports/stage10d11_student_confidence_comparison.json").resolve(),
        stage10d11_counterfactual,
        bc_dir,
        checkpoint,
    ]

    md: List[str] = []
    md.append("# STAGE10D12 Runtime Channel and Context Fix Candidate Audit Report")
    md.append("")
    md.append(f"Generated at UTC: {utc_now()}")
    md.append("")

    md.append("## Section 1 - Inputs and raw observation availability")
    md.append("- Loaded inputs:")
    for p in loaded_inputs:
        md.append(f"  - {p.as_posix()}")
    md.append(f"- Raw availability classification: {availability_payload['classification']}")
    md.append(f"- strict_probes={availability_payload['strict_probes']}")
    md.append(
        "- probes_mode="
        + ("strict (full raw full-map available)" if availability_payload["strict_probes"] else "preliminary (based_on_reconstructed_fullmap)")
    )
    if availability_payload["go_for_stage10d12r_full_raw_observation_capture"]:
        md.append("- Recommendation: GO_FOR_STAGE10D12R_FULL_RAW_OBSERVATION_CAPTURE")
    md.append("")

    md.append("## Section 2 - B2 worker channel group isolation")
    md.append(
        f"- Baseline B2: predicted={b2_baseline['predicted_action']}, p_noop={b2_baseline['p_noop']:.6f}, p_harvest={b2_baseline['p_harvest']:.6f}, p_produce={b2_baseline['p_produce']:.6f}"
    )
    md.append(
        f"- Worker reference: split={worker_ref.split}, sample_index={worker_ref.sample_index}, flat={worker_ref.flat_index}, dist_l2={worker_ref.dist_to_runtime:.6f}"
    )
    md.append("- Group patch results:")
    for r in b2_group_forward:
        md.append(
            f"  - {r['probe_name']}: pred={r['predicted_action']}, p_noop={r['p_noop']:.6f}, p_harvest={r['p_harvest']:.6f}, harvest_top1={r['harvest_top1']}"
        )
    md.append("- Reverse ablation results:")
    for r in b2_group_reverse:
        md.append(
            f"  - {r['probe_name']}: pred={r['predicted_action']}, p_noop={r['p_noop']:.6f}, p_harvest={r['p_harvest']:.6f}, harvest_destroyed={r['harvest_destroyed']}"
        )
    md.append(f"- Minimal group classification: {b2_classification}")
    md.append("")

    md.append("## Section 3 - B2 per-channel isolation")
    md.append("- Top channels by combined impact:")
    for r in b2_channel_payload["ranked_channels_by_combined_impact"][:8]:
        md.append(f"  - ch{r['channel_index']} {r['channel_name']}: score={r['combined_score']:.6f}")
    md.append(f"- Minimal channel set candidate: {b2_channel_payload['minimal_channel_set_candidate']}")
    md.append("")

    md.append("## Section 4 - C3 base local context decomposition")
    md.append(
        f"- Baseline C3: predicted={c3_baseline['predicted_action']}, p_noop={c3_baseline['p_noop']:.6f}, p_produce={c3_baseline['p_produce']:.6f}"
    )
    md.append("- Radius probes:")
    for r in c3_radius_results:
        md.append(
            f"  - {r['probe_name']}: pred={r['predicted_action']}, p_noop={r['p_noop']:.6f}, p_produce={r['p_produce']:.6f}, produce_top1={r['produce_top1']}"
        )
    md.append(f"- Minimal radius restoring Produce: {min_radius_restore}")
    md.append("- 5x5 semantic group decomposition:")
    for r in c3_decomp_results:
        md.append(
            f"  - {r['probe_name']}: pred={r['predicted_action']}, p_noop={r['p_noop']:.6f}, p_produce={r['p_produce']:.6f}, produce_top1={r['produce_top1']}"
        )
    md.append(f"- C3 classification: {c3_classification}")
    md.append("")

    md.append("## Section 5 - C3 neighbor importance")
    md.append("- Most important neighbor cells by delta p_produce:")
    for r in one_cell_results[:8]:
        md.append(
            f"  - xy={r['target_xy']}: delta_p_produce={r['delta_p_produce']:.6f}, delta_p_noop={r['delta_p_noop']:.6f}, pred={r['predicted_action']}"
        )
    md.append("- Combination probes:")
    for k, v in combination_results.items():
        md.append(
            f"  - {k}: patched={v['patched_cell_count']}, pred={v['predicted_action']}, p_produce={v['p_produce']:.6f}, produce_top1={v['produce_top1']}"
        )
    md.append(
        f"- small_subset_sufficient={c3_neighbor_payload['summary']['small_subset_sufficient']}, produce_requires_full_5x5_context={c3_neighbor_payload['summary']['produce_requires_full_5x5_context']}"
    )
    md.append("")

    md.append("## Section 6 - Scene distribution check")
    md.append(f"- Runtime scene summary: {runtime_scene}")
    md.append(f"- BC worker reference scene summary: {worker_scene}")
    md.append(f"- BC base reference scene summary: {base_scene}")
    md.append(f"- runtime_vs_worker_delta: {delta_runtime_vs_worker}")
    md.append(f"- runtime_vs_base_delta: {delta_runtime_vs_base}")
    md.append(f"- scene_delta_score={scene_delta_score:.6f}, scene_ood_likely={scene_ood_likely}")
    md.append("")

    md.append("## Section 7 - Candidate fix decision matrix")
    for name, data in candidates.items():
        md.append(f"- {name}")
        md.append(f"  - evidence_for: {data['evidence_for']}")
        md.append(f"  - evidence_against: {data['evidence_against']}")
        md.append(f"  - risk: {data['risk']}")
        md.append(f"  - expected_effort: {data['expected_effort']}")
        md.append(f"  - recommendation: {'recommended' if data['recommended'] else 'not recommended'}")
    md.append("")

    md.append("## Section 8 - Evidence-based classification")
    for label in labels:
        md.append(f"- {label}")
    md.append("")

    md.append("## Section 9 - Primary next gate")
    md.append(f"- {primary_next_gate}")
    if primary_next_gate == "GO_FOR_STAGE10D12R_FULL_RAW_OBSERVATION_CAPTURE":
        md.append("- Why: full raw 576 observation tensor is unavailable; non-focus context probes are preliminary and based on reconstructed full-map.")
    elif primary_next_gate == "GO_FOR_UNITY_OBSERVATION_CHANNEL_REMAP_FIX":
        md.append("- Why: channel/group probes isolate actionable semantic mismatch with sufficient confidence.")
    elif primary_next_gate == "GO_FOR_UNITY_SCENE_DISTRIBUTION_ALIGNMENT":
        md.append("- Why: channel semantics appear valid while local/global context is OOD versus BC references.")
    elif primary_next_gate == "GO_FOR_TARGETED_BC_AUGMENTATION_WITH_UNITY_LIKE_STATES":
        md.append("- Why: runtime observation semantics are acceptable and scene intent differs from BC support.")
    elif primary_next_gate == "GO_FOR_STAGE10D13_MINIMAL_RUNTIME_OBSERVATION_FIX":
        md.append("- Why: minimal safe runtime observation fix candidate is already proven.")
    else:
        md.append("- Why: current evidence is mixed; deeper probes required.")

    write_md(out_paths["report"], "\n".join(md) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
