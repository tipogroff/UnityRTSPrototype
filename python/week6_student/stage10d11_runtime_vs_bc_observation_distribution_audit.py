#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple

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

GROUPS = {
    "scalars": [0, 1, 26],
    "owner": [2, 3, 4],
    "unit_type": [5, 6, 7, 8, 9, 10, 11],
    "current_action": [12, 13, 14, 15, 16, 17],
    "direction": [18, 19, 20, 21],
    "produce_type": [22, 23, 24, 25],
}

OWNER_CH = {"Neutral": 2, "Player1": 3, "Player2": 4}
UNIT_CH = {
    "Resource": 5,
    "Base": 6,
    "Barracks": 7,
    "Worker": 8,
    "Light": 9,
    "Heavy": 10,
    "Ranged": 11,
}

FOCUS = {
    "B2": {"flat": 25, "xy": (1, 1), "kind": "worker_harvest"},
    "C3": {"flat": 50, "xy": (2, 2), "kind": "base_produce"},
}


@dataclass
class NpyStreamInfo:
    shape: Tuple[int, ...]
    dtype: np.dtype
    fortran_order: bool


class RunningStats:
    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.count = 0
        self.sum = np.zeros((dim,), dtype=np.float64)
        self.sumsq = np.zeros((dim,), dtype=np.float64)
        self.min = np.full((dim,), np.inf, dtype=np.float64)
        self.max = np.full((dim,), -np.inf, dtype=np.float64)

    def update(self, v: np.ndarray) -> None:
        self.count += 1
        self.sum += v
        self.sumsq += v * v
        self.min = np.minimum(self.min, v)
        self.max = np.maximum(self.max, v)

    def as_dict(self) -> Dict[str, Any]:
        if self.count == 0:
            zeros = np.zeros((self.dim,), dtype=np.float64)
            return {
                "count": 0,
                "mean": zeros.tolist(),
                "std": zeros.tolist(),
                "min": zeros.tolist(),
                "max": zeros.tolist(),
            }
        mean = self.sum / self.count
        var = np.maximum((self.sumsq / self.count) - mean * mean, 0.0)
        std = np.sqrt(var)
        return {
            "count": int(self.count),
            "mean": mean.tolist(),
            "std": std.tolist(),
            "min": self.min.tolist(),
            "max": self.max.tolist(),
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            rows.append(json.loads(s))
    return rows


def read_npy_header(fp) -> NpyStreamInfo:
    version = np.lib.format.read_magic(fp)
    if version == (1, 0):
        shape, fortran_order, dtype = np.lib.format.read_array_header_1_0(fp)
    elif version == (2, 0):
        shape, fortran_order, dtype = np.lib.format.read_array_header_2_0(fp)
    else:
        raise RuntimeError(f"Unsupported npy version: {version}")
    return NpyStreamInfo(shape=tuple(int(x) for x in shape), dtype=np.dtype(dtype), fortran_order=bool(fortran_order))


def iter_npy_rows_from_npz(npz_path: Path, key: str, rows_per_chunk: int = 128) -> Iterator[Tuple[int, np.ndarray, Tuple[int, ...]]]:
    member = f"{key}.npy"
    with zipfile.ZipFile(npz_path, "r") as zf:
        with zf.open(member, "r") as fp:
            info = read_npy_header(fp)
            if info.fortran_order:
                raise RuntimeError(f"Fortran-order arrays are not supported: {npz_path}:{member}")
            if len(info.shape) < 1:
                raise RuntimeError(f"Invalid rank: {npz_path}:{member} shape={info.shape}")

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


def safe_prob(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float64)
    x = x - np.max(x)
    e = np.exp(x)
    z = np.sum(e)
    return e / z if z > 0 else np.zeros_like(e)


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


def channel_group_dict(vec: np.ndarray) -> Dict[str, Any]:
    return {
        "scalar_channels": {
            "hit_points_ch0": float(vec[0]),
            "resources_ch1": float(vec[1]),
            "attack_target_index_ch26": float(vec[26]),
        },
        "owner_channels_2_4": {
            "neutral": float(vec[2]),
            "friendly_self": float(vec[3]),
            "enemy": float(vec[4]),
        },
        "unit_type_channels_5_11": {
            "resource": float(vec[5]),
            "base": float(vec[6]),
            "barracks": float(vec[7]),
            "worker": float(vec[8]),
            "light": float(vec[9]),
            "heavy": float(vec[10]),
            "ranged": float(vec[11]),
        },
        "current_action_channels_12_17": {
            "noop": float(vec[12]),
            "move": float(vec[13]),
            "harvest": float(vec[14]),
            "return": float(vec[15]),
            "produce": float(vec[16]),
            "attack": float(vec[17]),
        },
        "direction_channels_18_21": {
            "north": float(vec[18]),
            "east": float(vec[19]),
            "south": float(vec[20]),
            "west": float(vec[21]),
        },
        "produce_type_channels_22_25": {
            "worker": float(vec[22]),
            "light": float(vec[23]),
            "heavy": float(vec[24]),
            "ranged": float(vec[25]),
        },
    }


def most_common_pattern(counter: Counter) -> Dict[str, Any]:
    if not counter:
        return {"pattern": [], "count": 0}
    pat, cnt = counter.most_common(1)[0]
    return {"pattern": list(pat), "count": int(cnt)}


def summarize_map(obs_map: np.ndarray) -> Dict[str, Any]:
    flat = obs_map.reshape(576, 27)
    owner = np.argmax(flat[:, 2:5], axis=1)
    unit = np.argmax(flat[:, 5:12], axis=1)
    unit_present = np.max(flat[:, 5:12], axis=1) > 0.5

    owner_self = int(np.sum(owner == 1))
    owner_enemy = int(np.sum(owner == 2))
    owner_neutral = int(np.sum(owner == 0))

    resource = int(np.sum((unit == 0) & unit_present))
    base = int(np.sum((unit == 1) & unit_present))
    barracks = int(np.sum((unit == 2) & unit_present))
    worker = int(np.sum((unit == 3) & unit_present))
    combat = int(np.sum(np.isin(unit, np.asarray([4, 5, 6])) & unit_present))
    empty = int(np.sum(~unit_present))

    actor_mask = unit_present & (unit != 0)
    friendly_actor = int(np.sum(actor_mask & (owner == 1)))
    enemy_actor = int(np.sum(actor_mask & (owner == 2)))

    return {
        "count_self_friendly_cells": owner_self,
        "count_enemy_cells": owner_enemy,
        "count_neutral_cells": owner_neutral,
        "count_resources": resource,
        "count_bases": base,
        "count_workers": worker,
        "count_barracks": barracks,
        "count_combat_units": combat,
        "count_empty_cells": empty,
        "total_actor_cells": int(np.sum(actor_mask)),
        "friendly_actor_cells": friendly_actor,
        "enemy_actor_cells": enemy_actor,
    }


def reconstruct_runtime_map(cell_rows: List[Dict[str, Any]], focus_exact: Dict[str, np.ndarray]) -> np.ndarray:
    obs = np.zeros((24, 24, 27), dtype=np.float32)
    for r in cell_rows:
        x = int(r.get("x", 0))
        y = int(r.get("y", 0))
        vec = np.zeros((27,), dtype=np.float32)

        owner = str(r.get("decoded_observation_owner", "Neutral"))
        unit = str(r.get("decoded_observation_unit_type", "Resource"))
        is_empty = bool(r.get("runtime_is_empty", False))

        if owner in OWNER_CH:
            vec[OWNER_CH[owner]] = 1.0
        if unit in UNIT_CH and not is_empty:
            vec[UNIT_CH[unit]] = 1.0

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
    rows = payload.get("actor_cells", [])
    out: Dict[str, np.ndarray] = {}
    if isinstance(rows, list):
        for r in rows:
            if not isinstance(r, Mapping):
                continue
            label = str(r.get("logical_cell", ""))
            ch = r.get("cell_observation_channels")
            if label in FOCUS and isinstance(ch, list) and len(ch) == 27:
                out[label] = np.asarray(ch, dtype=np.float32)
    if len(out) < 2:
        rows2 = payload.get("focus_cell_diagnostics", [])
        if isinstance(rows2, list):
            for r in rows2:
                if not isinstance(r, Mapping):
                    continue
                label = str(r.get("logical_label", ""))
                ch = r.get("cell_observation_channels")
                if label in FOCUS and isinstance(ch, list) and len(ch) == 27:
                    out[label] = np.asarray(ch, dtype=np.float32)
    return out


def run_student(model: torch.nn.Module, obs_map: np.ndarray, device: torch.device) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        x = torch.from_numpy(obs_map[None, ...]).to(device=device, dtype=torch.float32)
        logits = model(x)["action_type_logits"][0].detach().cpu().numpy()
        probs = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = probs / np.clip(np.sum(probs, axis=1, keepdims=True), 1e-12, None)
    return probs


def top_channel_deltas(a: np.ndarray, b: np.ndarray, topk: int = 8) -> List[Dict[str, Any]]:
    d = np.abs(a.astype(np.float64) - b.astype(np.float64))
    idx = np.argsort(-d)[:topk]
    out: List[Dict[str, Any]] = []
    for i in idx.tolist():
        out.append(
            {
                "channel_index": int(i),
                "channel_name": CHANNEL_NAMES[i],
                "abs_delta": float(d[i]),
                "runtime_value": float(a[i]),
                "bc_value": float(b[i]),
            }
        )
    return out


def group_l2(a: np.ndarray, b: np.ndarray) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for g, idx in GROUPS.items():
        v = float(np.linalg.norm((a[idx] - b[idx]).astype(np.float64)))
        out[g] = v
    return out


def label_from_probs(prob: np.ndarray) -> str:
    i = int(np.argmax(prob))
    return ACTION_NAMES[i] if 0 <= i < len(ACTION_NAMES) else str(i)


def bool_owner_unit_mismatch(label: str, vec: np.ndarray) -> bool:
    owner = vec[2:5]
    unit = vec[5:12]
    owner_valid = float(np.max(owner)) >= 0.5
    unit_valid = float(np.max(unit)) >= 0.5
    if label == "B2":
        expected = int(np.argmax(unit)) == 3
    else:
        expected = int(np.argmax(unit)) == 1
    return not (owner_valid and unit_valid and expected)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.11 runtime-vs-BC observation distribution audit")
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
    runtime_summary = (root / args.runtime_summary).resolve()
    legacy_runtime_snapshot = (root / args.legacy_runtime_snapshot).resolve()
    bc_dir = (root / args.bc_ready_dir).resolve()
    checkpoint = (root / args.checkpoint).resolve()
    reports_dir = (root / args.reports_dir).resolve()

    report_paths = {
        "focus_cell_audit": reports_dir / "stage10d11_runtime_focus_cell_channel_audit.json",
        "bc_positive_stats": reports_dir / "stage10d11_bc_positive_sample_channel_stats.json",
        "runtime_vs_bc_delta": reports_dir / "stage10d11_runtime_vs_bc_channel_delta.json",
        "full_map_comparison": reports_dir / "stage10d11_full_map_context_comparison.json",
        "confidence": reports_dir / "stage10d11_student_confidence_comparison.json",
        "counterfactual": reports_dir / "stage10d11_counterfactual_probe_results.json",
        "md_report": reports_dir / "STAGE10D11_RUNTIME_VS_BC_OBSERVATION_DISTRIBUTION_AUDIT_REPORT.md",
    }

    for p in report_paths.values():
        p.parent.mkdir(parents=True, exist_ok=True)

    input_checks = {
        "runtime_cell_table_exists": runtime_cell_table.exists(),
        "runtime_logits_snapshot_exists": runtime_logits_snapshot.exists(),
        "runtime_summary_exists": runtime_summary.exists(),
        "legacy_runtime_snapshot_exists": legacy_runtime_snapshot.exists(),
        "bc_manifest_exists": (bc_dir / "bc_manifest.json").exists(),
        "bc_train_exists": (bc_dir / "bc_train.npz").exists(),
        "bc_validation_exists": (bc_dir / "bc_validation.npz").exists(),
        "checkpoint_exists": checkpoint.exists(),
    }
    missing = [k for k, v in input_checks.items() if not v]
    if missing:
        raise RuntimeError(f"Missing required inputs: {missing}")

    rows = read_jsonl(runtime_cell_table)
    runtime_summary_payload = read_json(runtime_summary)
    runtime_logits_payload = read_json(runtime_logits_snapshot)
    legacy_snapshot_payload = read_json(legacy_runtime_snapshot)

    if len(rows) != 576:
        raise RuntimeError(f"Expected 576 runtime rows, got {len(rows)}")

    focus_rows = find_focus_rows(rows)
    focus_exact_vectors = extract_focus_vectors_from_legacy_snapshot(legacy_runtime_snapshot)
    runtime_map = reconstruct_runtime_map(rows, focus_exact_vectors)

    focus_audit: Dict[str, Any] = {
        "generated_at_utc": utc_now(),
        "runtime_cell_table": str(runtime_cell_table),
        "legacy_runtime_snapshot": str(legacy_runtime_snapshot),
        "runtime_rows": int(len(rows)),
        "focus_cells": {},
        "critical_mismatch_flags": {},
    }

    for label, info in FOCUS.items():
        row = focus_rows.get(label, {})
        x, y = info["xy"]
        vec = focus_exact_vectors.get(label)
        if vec is None:
            vec = runtime_map[y, x, :].copy()

        p = np.asarray(row.get("action_type_probabilities", [0.0] * 6), dtype=np.float64)
        p = p if p.shape == (6,) else np.zeros((6,), dtype=np.float64)

        mismatch = bool_owner_unit_mismatch(label, vec)
        focus_audit["critical_mismatch_flags"][label] = mismatch

        focus_audit["focus_cells"][label] = {
            "flat_index": int(info["flat"]),
            "xy": [int(x), int(y)],
            "raw_channel_vector": [float(v) for v in vec.tolist()],
            "decoded_observation_owner": row.get("decoded_observation_owner"),
            "decoded_observation_unit_type": row.get("decoded_observation_unit_type"),
            "runtime_is_friendly_actor": bool(row.get("runtime_is_friendly_actor", False)),
            "runtime_is_friendly_worker": bool(row.get("runtime_is_friendly_worker", False)),
            "runtime_is_friendly_base": bool(row.get("runtime_is_friendly_base", False)),
            "runtime_is_resource": bool(row.get("runtime_is_resource", False)),
            "runtime_is_empty": bool(row.get("runtime_is_empty", False)),
            "predicted_action_type_name": row.get("predicted_action_type"),
            "probabilities": {
                "p_noop": float(row.get("p_noop", p[0])),
                "p_move": float(row.get("p_move", p[1])),
                "p_harvest": float(row.get("p_harvest", p[2])),
                "p_return": float(row.get("p_return", p[3])),
                "p_produce": float(row.get("p_produce", p[4])),
                "p_attack": float(row.get("p_attack", p[5])),
            },
            "channel_groups": channel_group_dict(vec),
            "critical_observation_encoding_mismatch": mismatch,
        }

    write_json(report_paths["focus_cell_audit"], focus_audit)

    bc_manifest = read_json(bc_dir / "bc_manifest.json")
    train_npz = bc_dir / "bc_train.npz"
    val_npz = bc_dir / "bc_validation.npz"

    # Some legacy files store observations/actions instead of input_tensor/target_action_branches.
    obs_key = "observations"
    act_key = "actions"

    worker_stats = RunningStats(27)
    base_stats = RunningStats(27)

    worker_owner_pat = Counter()
    worker_unit_pat = Counter()
    worker_action_pat = Counter()
    worker_dir_pat = Counter()

    base_owner_pat = Counter()
    base_unit_pat = Counter()
    base_action_pat = Counter()
    base_dir_pat = Counter()

    b2_vec = np.asarray(focus_audit["focus_cells"]["B2"]["raw_channel_vector"], dtype=np.float32)
    c3_vec = np.asarray(focus_audit["focus_cells"]["C3"]["raw_channel_vector"], dtype=np.float32)

    b2_patch5 = patch(runtime_map, 1, 1, 2)
    c3_patch5 = patch(runtime_map, 2, 2, 2)
    b2_patch7 = patch(runtime_map, 1, 1, 3)
    c3_patch7 = patch(runtime_map, 2, 2, 3)

    nearest: Dict[str, Dict[str, Any]] = {
        "B2": {
            "vector": {"dist": math.inf},
            "patch5": {"dist": math.inf},
            "patch7": {"dist": math.inf},
        },
        "C3": {
            "vector": {"dist": math.inf},
            "patch5": {"dist": math.inf},
            "patch7": {"dist": math.inf},
        },
    }

    def maybe_update_nearest(
        *,
        label: str,
        kind: str,
        split: str,
        sample_index: int,
        flat_index: int,
        vector: np.ndarray,
        sample_obs: np.ndarray,
    ) -> None:
        x, y = flat_to_xy(flat_index)
        if label == "B2":
            ref_vec = b2_vec
            ref5 = b2_patch5
            ref7 = b2_patch7
        else:
            ref_vec = c3_vec
            ref5 = c3_patch5
            ref7 = c3_patch7

        d27 = float(np.linalg.norm((vector - ref_vec).astype(np.float64)))
        p5 = patch(sample_obs.reshape(24, 24, 27), x, y, 2)
        p7 = patch(sample_obs.reshape(24, 24, 27), x, y, 3)
        d5 = float(np.linalg.norm((p5 - ref5).astype(np.float64)))
        d7 = float(np.linalg.norm((p7 - ref7).astype(np.float64)))

        if d27 < nearest[label]["vector"]["dist"]:
            nearest[label]["vector"] = {
                "dist": d27,
                "split": split,
                "sample_index": int(sample_index),
                "flat_index": int(flat_index),
                "xy": [int(x), int(y)],
                "channel_vector": [float(v) for v in vector.tolist()],
                "action_type": "Harvest" if kind == "worker_harvest" else "Produce",
            }
        if d5 < nearest[label]["patch5"]["dist"]:
            nearest[label]["patch5"] = {
                "dist": d5,
                "split": split,
                "sample_index": int(sample_index),
                "flat_index": int(flat_index),
                "xy": [int(x), int(y)],
                "patch": p5.tolist(),
            }
        if d7 < nearest[label]["patch7"]["dist"]:
            nearest[label]["patch7"] = {
                "dist": d7,
                "split": split,
                "sample_index": int(sample_index),
                "flat_index": int(flat_index),
                "xy": [int(x), int(y)],
                "patch": p7.tolist(),
            }

    split_sample_counts: Dict[str, int] = {"train": 0, "validation": 0}

    for split_name, npz_path in (("train", train_npz), ("validation", val_npz)):
        for start, obs_chunk, act_chunk in iter_paired_rows(npz_path, obs_key, act_key, rows_per_chunk=args.chunk_size):
            split_sample_counts[split_name] += int(obs_chunk.shape[0])
            for i in range(obs_chunk.shape[0]):
                sample_obs = obs_chunk[i]
                sample_act = act_chunk[i]

                action_type = sample_act[:, 0]
                is_worker = sample_obs[:, 8] > 0.5
                is_base = sample_obs[:, 6] > 0.5

                worker_idx = np.where((action_type == 2) & is_worker)[0]
                base_idx = np.where((action_type == 4) & is_base)[0]

                for flat in worker_idx.tolist():
                    v = sample_obs[int(flat)].astype(np.float64)
                    worker_stats.update(v)
                    worker_owner_pat.update([tuple((v[2:5] > 0.5).astype(np.int64).tolist())])
                    worker_unit_pat.update([tuple((v[5:12] > 0.5).astype(np.int64).tolist())])
                    worker_action_pat.update([tuple((v[12:18] > 0.5).astype(np.int64).tolist())])
                    worker_dir_pat.update([tuple((v[18:22] > 0.5).astype(np.int64).tolist())])
                    maybe_update_nearest(
                        label="B2",
                        kind="worker_harvest",
                        split=split_name,
                        sample_index=start + i,
                        flat_index=int(flat),
                        vector=v.astype(np.float32),
                        sample_obs=sample_obs.astype(np.float32),
                    )

                for flat in base_idx.tolist():
                    v = sample_obs[int(flat)].astype(np.float64)
                    base_stats.update(v)
                    base_owner_pat.update([tuple((v[2:5] > 0.5).astype(np.int64).tolist())])
                    base_unit_pat.update([tuple((v[5:12] > 0.5).astype(np.int64).tolist())])
                    base_action_pat.update([tuple((v[12:18] > 0.5).astype(np.int64).tolist())])
                    base_dir_pat.update([tuple((v[18:22] > 0.5).astype(np.int64).tolist())])
                    maybe_update_nearest(
                        label="C3",
                        kind="base_produce",
                        split=split_name,
                        sample_index=start + i,
                        flat_index=int(flat),
                        vector=v.astype(np.float32),
                        sample_obs=sample_obs.astype(np.float32),
                    )

    worker_stats_dict = worker_stats.as_dict()
    base_stats_dict = base_stats.as_dict()

    bc_stats_payload = {
        "generated_at_utc": utc_now(),
        "bc_dir": str(bc_dir),
        "split_sample_counts": split_sample_counts,
        "worker_harvest": {
            "count": int(worker_stats_dict["count"]),
            "channel_stats": worker_stats_dict,
            "group_stats": {
                g: {
                    "mean": float(np.mean(np.asarray(worker_stats_dict["mean"])[idx])),
                    "std": float(np.mean(np.asarray(worker_stats_dict["std"])[idx])),
                    "min": float(np.min(np.asarray(worker_stats_dict["min"])[idx])),
                    "max": float(np.max(np.asarray(worker_stats_dict["max"])[idx])),
                }
                for g, idx in GROUPS.items()
            },
            "most_common_owner_onehot": most_common_pattern(worker_owner_pat),
            "most_common_unit_type_onehot": most_common_pattern(worker_unit_pat),
            "most_common_current_action_onehot": most_common_pattern(worker_action_pat),
            "most_common_direction_onehot": most_common_pattern(worker_dir_pat),
        },
        "base_produce": {
            "count": int(base_stats_dict["count"]),
            "channel_stats": base_stats_dict,
            "group_stats": {
                g: {
                    "mean": float(np.mean(np.asarray(base_stats_dict["mean"])[idx])),
                    "std": float(np.mean(np.asarray(base_stats_dict["std"])[idx])),
                    "min": float(np.min(np.asarray(base_stats_dict["min"])[idx])),
                    "max": float(np.max(np.asarray(base_stats_dict["max"])[idx])),
                }
                for g, idx in GROUPS.items()
            },
            "most_common_owner_onehot": most_common_pattern(base_owner_pat),
            "most_common_unit_type_onehot": most_common_pattern(base_unit_pat),
            "most_common_current_action_onehot": most_common_pattern(base_action_pat),
            "most_common_direction_onehot": most_common_pattern(base_dir_pat),
        },
    }

    write_json(report_paths["bc_positive_stats"], bc_stats_payload)

    worker_mean = np.asarray(worker_stats_dict["mean"], dtype=np.float32)
    base_mean = np.asarray(base_stats_dict["mean"], dtype=np.float32)

    runtime_vs_bc_delta = {
        "generated_at_utc": utc_now(),
        "B2_vs_worker_harvest": {
            "runtime_vector": b2_vec.tolist(),
            "bc_mean_vector": worker_mean.tolist(),
            "nearest_27ch": nearest["B2"]["vector"],
            "nearest_5x5": {
                "distance": nearest["B2"]["patch5"].get("dist"),
                "split": nearest["B2"]["patch5"].get("split"),
                "sample_index": nearest["B2"]["patch5"].get("sample_index"),
                "flat_index": nearest["B2"]["patch5"].get("flat_index"),
                "xy": nearest["B2"]["patch5"].get("xy"),
            },
            "nearest_7x7": {
                "distance": nearest["B2"]["patch7"].get("dist"),
                "split": nearest["B2"]["patch7"].get("split"),
                "sample_index": nearest["B2"]["patch7"].get("sample_index"),
                "flat_index": nearest["B2"]["patch7"].get("flat_index"),
                "xy": nearest["B2"]["patch7"].get("xy"),
            },
            "per_channel_abs_delta_vs_mean": [float(x) for x in np.abs(b2_vec - worker_mean)],
            "group_l2_delta_vs_mean": group_l2(b2_vec, worker_mean),
            "top_differing_channels_vs_mean": top_channel_deltas(b2_vec, worker_mean),
            "group_l2_delta_vs_nearest": group_l2(b2_vec, np.asarray(nearest["B2"]["vector"]["channel_vector"], dtype=np.float32)),
            "top_differing_channels_vs_nearest": top_channel_deltas(
                b2_vec,
                np.asarray(nearest["B2"]["vector"]["channel_vector"], dtype=np.float32),
            ),
        },
        "C3_vs_base_produce": {
            "runtime_vector": c3_vec.tolist(),
            "bc_mean_vector": base_mean.tolist(),
            "nearest_27ch": nearest["C3"]["vector"],
            "nearest_5x5": {
                "distance": nearest["C3"]["patch5"].get("dist"),
                "split": nearest["C3"]["patch5"].get("split"),
                "sample_index": nearest["C3"]["patch5"].get("sample_index"),
                "flat_index": nearest["C3"]["patch5"].get("flat_index"),
                "xy": nearest["C3"]["patch5"].get("xy"),
            },
            "nearest_7x7": {
                "distance": nearest["C3"]["patch7"].get("dist"),
                "split": nearest["C3"]["patch7"].get("split"),
                "sample_index": nearest["C3"]["patch7"].get("sample_index"),
                "flat_index": nearest["C3"]["patch7"].get("flat_index"),
                "xy": nearest["C3"]["patch7"].get("xy"),
            },
            "per_channel_abs_delta_vs_mean": [float(x) for x in np.abs(c3_vec - base_mean)],
            "group_l2_delta_vs_mean": group_l2(c3_vec, base_mean),
            "top_differing_channels_vs_mean": top_channel_deltas(c3_vec, base_mean),
            "group_l2_delta_vs_nearest": group_l2(c3_vec, np.asarray(nearest["C3"]["vector"]["channel_vector"], dtype=np.float32)),
            "top_differing_channels_vs_nearest": top_channel_deltas(
                c3_vec,
                np.asarray(nearest["C3"]["vector"]["channel_vector"], dtype=np.float32),
            ),
        },
    }

    write_json(report_paths["runtime_vs_bc_delta"], runtime_vs_bc_delta)

    # Build BC representative maps for context comparison using nearest sample IDs.
    rep_indices = {
        "worker": (nearest["B2"]["vector"]["split"], int(nearest["B2"]["vector"]["sample_index"])),
        "base": (nearest["C3"]["vector"]["split"], int(nearest["C3"]["vector"]["sample_index"])),
    }

    rep_maps: Dict[str, np.ndarray] = {}
    for tag, (split_name, sample_index) in rep_indices.items():
        npz = train_npz if split_name == "train" else val_npz
        found = False
        for start, obs_chunk, _ in iter_paired_rows(npz, obs_key, act_key, rows_per_chunk=args.chunk_size):
            if start <= sample_index < start + obs_chunk.shape[0]:
                rep_maps[tag] = obs_chunk[sample_index - start].reshape(24, 24, 27).astype(np.float32)
                found = True
                break
        if not found:
            raise RuntimeError(f"Representative sample not found for {tag}: {split_name}:{sample_index}")

    full_map_payload = {
        "generated_at_utc": utc_now(),
        "runtime_reconstructed_map_summary": summarize_map(runtime_map),
        "bc_representative_worker_map_summary": summarize_map(rep_maps["worker"]),
        "bc_representative_base_map_summary": summarize_map(rep_maps["base"]),
        "local_context": {
            "B2_runtime_patch5_l2_vs_nearest_worker_patch5": float(
                np.linalg.norm(
                    (b2_patch5 - np.asarray(nearest["B2"]["patch5"]["patch"], dtype=np.float32)).astype(np.float64)
                )
            ),
            "B2_runtime_patch7_l2_vs_nearest_worker_patch7": float(
                np.linalg.norm(
                    (b2_patch7 - np.asarray(nearest["B2"]["patch7"]["patch"], dtype=np.float32)).astype(np.float64)
                )
            ),
            "C3_runtime_patch5_l2_vs_nearest_base_patch5": float(
                np.linalg.norm(
                    (c3_patch5 - np.asarray(nearest["C3"]["patch5"]["patch"], dtype=np.float32)).astype(np.float64)
                )
            ),
            "C3_runtime_patch7_l2_vs_nearest_base_patch7": float(
                np.linalg.norm(
                    (c3_patch7 - np.asarray(nearest["C3"]["patch7"]["patch"], dtype=np.float32)).astype(np.float64)
                )
            ),
        },
    }
    write_json(report_paths["full_map_comparison"], full_map_payload)

    device = torch.device(args.device)
    model = build_day3_student_model().to(device=device)
    ckpt = torch.load(checkpoint, map_location=device)
    if "model_state_dict" not in ckpt:
        raise RuntimeError("Checkpoint missing model_state_dict")
    model.load_state_dict(ckpt["model_state_dict"], strict=True)

    runtime_probs = run_student(model, runtime_map, device=device)

    b2_prob = runtime_probs[FOCUS["B2"]["flat"]]
    c3_prob = runtime_probs[FOCUS["C3"]["flat"]]

    # Representative high-confidence BC positives from validation only.
    top_worker_examples: List[Dict[str, Any]] = []
    top_base_examples: List[Dict[str, Any]] = []

    agg = {
        "worker_harvest": {"n": 0, "sum_noop": 0.0, "sum_harvest": 0.0, "sum_produce": 0.0, "pred_counter": Counter()},
        "base_produce": {"n": 0, "sum_noop": 0.0, "sum_harvest": 0.0, "sum_produce": 0.0, "pred_counter": Counter()},
    }

    for start, obs_chunk, act_chunk in iter_paired_rows(val_npz, obs_key, act_key, rows_per_chunk=args.chunk_size):
        obs_maps = obs_chunk.reshape(obs_chunk.shape[0], 24, 24, 27).astype(np.float32)
        with torch.no_grad():
            x = torch.from_numpy(obs_maps).to(device=device, dtype=torch.float32)
            logits = model(x)["action_type_logits"].detach().cpu().numpy()
        probs = np.exp(logits - np.max(logits, axis=2, keepdims=True))
        probs = probs / np.clip(np.sum(probs, axis=2, keepdims=True), 1e-12, None)

        for i in range(obs_chunk.shape[0]):
            action_type = act_chunk[i][:, 0]
            is_worker = obs_chunk[i][:, 8] > 0.5
            is_base = obs_chunk[i][:, 6] > 0.5

            worker_idx = np.where((action_type == 2) & is_worker)[0]
            base_idx = np.where((action_type == 4) & is_base)[0]

            for flat in worker_idx.tolist():
                pp = probs[i, int(flat)]
                pred = int(np.argmax(pp))
                agg["worker_harvest"]["n"] += 1
                agg["worker_harvest"]["sum_noop"] += float(pp[0])
                agg["worker_harvest"]["sum_harvest"] += float(pp[2])
                agg["worker_harvest"]["sum_produce"] += float(pp[4])
                agg["worker_harvest"]["pred_counter"].update([pred])
                item = {
                    "split": "validation",
                    "sample_index": int(start + i),
                    "flat_index": int(flat),
                    "target_action": "Harvest",
                    "target_probability": float(pp[2]),
                    "p_noop": float(pp[0]),
                    "p_harvest": float(pp[2]),
                    "p_produce": float(pp[4]),
                    "predicted_action": ACTION_NAMES[pred],
                }
                top_worker_examples.append(item)

            for flat in base_idx.tolist():
                pp = probs[i, int(flat)]
                pred = int(np.argmax(pp))
                agg["base_produce"]["n"] += 1
                agg["base_produce"]["sum_noop"] += float(pp[0])
                agg["base_produce"]["sum_harvest"] += float(pp[2])
                agg["base_produce"]["sum_produce"] += float(pp[4])
                agg["base_produce"]["pred_counter"].update([pred])
                item = {
                    "split": "validation",
                    "sample_index": int(start + i),
                    "flat_index": int(flat),
                    "target_action": "Produce",
                    "target_probability": float(pp[4]),
                    "p_noop": float(pp[0]),
                    "p_harvest": float(pp[2]),
                    "p_produce": float(pp[4]),
                    "predicted_action": ACTION_NAMES[pred],
                }
                top_base_examples.append(item)

    top_worker_examples.sort(key=lambda r: r["target_probability"], reverse=True)
    top_base_examples.sort(key=lambda r: r["target_probability"], reverse=True)

    conf_payload = {
        "generated_at_utc": utc_now(),
        "checkpoint": str(checkpoint),
        "runtime_reconstructed_from_stage10d10_cell_table": {
            "B2": {
                "flat_index": int(FOCUS["B2"]["flat"]),
                "predicted_action": label_from_probs(b2_prob),
                "p_noop": float(b2_prob[0]),
                "p_harvest": float(b2_prob[2]),
                "p_produce": float(b2_prob[4]),
                "probabilities": [float(x) for x in b2_prob.tolist()],
            },
            "C3": {
                "flat_index": int(FOCUS["C3"]["flat"]),
                "predicted_action": label_from_probs(c3_prob),
                "p_noop": float(c3_prob[0]),
                "p_harvest": float(c3_prob[2]),
                "p_produce": float(c3_prob[4]),
                "probabilities": [float(x) for x in c3_prob.tolist()],
            },
        },
        "bc_validation_positive_confidence": {
            "worker_harvest": {
                "count": int(agg["worker_harvest"]["n"]),
                "mean_p_noop": float(agg["worker_harvest"]["sum_noop"] / max(1, agg["worker_harvest"]["n"])),
                "mean_p_harvest": float(agg["worker_harvest"]["sum_harvest"] / max(1, agg["worker_harvest"]["n"])),
                "mean_p_produce": float(agg["worker_harvest"]["sum_produce"] / max(1, agg["worker_harvest"]["n"])),
                "predicted_action_distribution": {
                    ACTION_NAMES[k]: int(v) for k, v in agg["worker_harvest"]["pred_counter"].items()
                },
                "representative_high_confidence_examples": top_worker_examples[:5],
            },
            "base_produce": {
                "count": int(agg["base_produce"]["n"]),
                "mean_p_noop": float(agg["base_produce"]["sum_noop"] / max(1, agg["base_produce"]["n"])),
                "mean_p_harvest": float(agg["base_produce"]["sum_harvest"] / max(1, agg["base_produce"]["n"])),
                "mean_p_produce": float(agg["base_produce"]["sum_produce"] / max(1, agg["base_produce"]["n"])),
                "predicted_action_distribution": {
                    ACTION_NAMES[k]: int(v) for k, v in agg["base_produce"]["pred_counter"].items()
                },
                "representative_high_confidence_examples": top_base_examples[:5],
            },
        },
    }

    write_json(report_paths["confidence"], conf_payload)

    # Counterfactual probes.
    def eval_focus(obs_map: np.ndarray, label: str) -> Dict[str, Any]:
        probs = run_student(model, obs_map, device=device)
        flat = int(FOCUS[label]["flat"])
        p = probs[flat]
        return {
            "flat_index": flat,
            "predicted_action": label_from_probs(p),
            "p_noop": float(p[0]),
            "p_harvest": float(p[2]),
            "p_produce": float(p[4]),
            "probabilities": [float(x) for x in p.tolist()],
        }

    cf: Dict[str, Any] = {
        "generated_at_utc": utc_now(),
        "baseline_runtime": {
            "B2": eval_focus(runtime_map, "B2"),
            "C3": eval_focus(runtime_map, "C3"),
        },
        "probe_A_cell_replacement": {},
        "probe_B_patch5_replacement": {},
        "probe_C_patch7_replacement": {},
        "probe_D_full_map_bc_sample": {},
        "probe_E_owner_unit_action_direction_patch": {},
    }

    # Probe A
    obs_a_b2 = runtime_map.copy()
    obs_a_b2[1, 1, :] = np.asarray(nearest["B2"]["vector"]["channel_vector"], dtype=np.float32)
    cf["probe_A_cell_replacement"]["B2"] = eval_focus(obs_a_b2, "B2")

    obs_a_c3 = runtime_map.copy()
    obs_a_c3[2, 2, :] = np.asarray(nearest["C3"]["vector"]["channel_vector"], dtype=np.float32)
    cf["probe_A_cell_replacement"]["C3"] = eval_focus(obs_a_c3, "C3")

    # Probe B (5x5)
    obs_b_b2 = runtime_map.copy()
    src5_b2 = np.asarray(nearest["B2"]["patch5"]["patch"], dtype=np.float32)
    src5_c3 = np.asarray(nearest["C3"]["patch5"]["patch"], dtype=np.float32)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            xx, yy = 1 + dx, 1 + dy
            if 0 <= xx < 24 and 0 <= yy < 24:
                obs_b_b2[yy, xx, :] = src5_b2[dy + 2, dx + 2, :]
    cf["probe_B_patch5_replacement"]["B2"] = eval_focus(obs_b_b2, "B2")

    obs_b_c3 = runtime_map.copy()
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            xx, yy = 2 + dx, 2 + dy
            if 0 <= xx < 24 and 0 <= yy < 24:
                obs_b_c3[yy, xx, :] = src5_c3[dy + 2, dx + 2, :]
    cf["probe_B_patch5_replacement"]["C3"] = eval_focus(obs_b_c3, "C3")

    # Probe C (7x7)
    obs_c_b2 = runtime_map.copy()
    src7_b2 = np.asarray(nearest["B2"]["patch7"]["patch"], dtype=np.float32)
    src7_c3 = np.asarray(nearest["C3"]["patch7"]["patch"], dtype=np.float32)
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            xx, yy = 1 + dx, 1 + dy
            if 0 <= xx < 24 and 0 <= yy < 24:
                obs_c_b2[yy, xx, :] = src7_b2[dy + 3, dx + 3, :]
    cf["probe_C_patch7_replacement"]["B2"] = eval_focus(obs_c_b2, "B2")

    obs_c_c3 = runtime_map.copy()
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            xx, yy = 2 + dx, 2 + dy
            if 0 <= xx < 24 and 0 <= yy < 24:
                obs_c_c3[yy, xx, :] = src7_c3[dy + 3, dx + 3, :]
    cf["probe_C_patch7_replacement"]["C3"] = eval_focus(obs_c_c3, "C3")

    # Probe D (full BC sample)
    rep_worker_probs = run_student(model, rep_maps["worker"], device=device)
    rep_base_probs = run_student(model, rep_maps["base"], device=device)
    w_flat = int(nearest["B2"]["vector"]["flat_index"])
    b_flat = int(nearest["C3"]["vector"]["flat_index"])
    w_prob = rep_worker_probs[w_flat]
    b_prob = rep_base_probs[b_flat]
    cf["probe_D_full_map_bc_sample"] = {
        "worker_reference": {
            "split": nearest["B2"]["vector"]["split"],
            "sample_index": nearest["B2"]["vector"]["sample_index"],
            "flat_index": w_flat,
            "predicted_action": label_from_probs(w_prob),
            "p_noop": float(w_prob[0]),
            "p_harvest": float(w_prob[2]),
            "p_produce": float(w_prob[4]),
        },
        "base_reference": {
            "split": nearest["C3"]["vector"]["split"],
            "sample_index": nearest["C3"]["vector"]["sample_index"],
            "flat_index": b_flat,
            "predicted_action": label_from_probs(b_prob),
            "p_noop": float(b_prob[0]),
            "p_harvest": float(b_prob[2]),
            "p_produce": float(b_prob[4]),
        },
    }

    # Probe E (owner/unit/current_action/direction only)
    obs_e_b2 = runtime_map.copy()
    vec_b2_src = np.asarray(nearest["B2"]["vector"]["channel_vector"], dtype=np.float32)
    for lo, hi in ((2, 5), (5, 12), (12, 18), (18, 22)):
        obs_e_b2[1, 1, lo:hi] = vec_b2_src[lo:hi]
    cf["probe_E_owner_unit_action_direction_patch"]["B2"] = eval_focus(obs_e_b2, "B2")

    obs_e_c3 = runtime_map.copy()
    vec_c3_src = np.asarray(nearest["C3"]["vector"]["channel_vector"], dtype=np.float32)
    for lo, hi in ((2, 5), (5, 12), (12, 18), (18, 22)):
        obs_e_c3[2, 2, lo:hi] = vec_c3_src[lo:hi]
    cf["probe_E_owner_unit_action_direction_patch"]["C3"] = eval_focus(obs_e_c3, "C3")

    write_json(report_paths["counterfactual"], cf)

    # Classification.
    labels: List[str] = []

    b2_mismatch = bool(focus_audit["critical_mismatch_flags"]["B2"])
    c3_mismatch = bool(focus_audit["critical_mismatch_flags"]["C3"])

    b2_base_noop = float(cf["baseline_runtime"]["B2"]["p_noop"])
    c3_base_noop = float(cf["baseline_runtime"]["C3"]["p_noop"])

    b2_cell_noop = float(cf["probe_A_cell_replacement"]["B2"]["p_noop"])
    c3_cell_noop = float(cf["probe_A_cell_replacement"]["C3"]["p_noop"])

    b2_patch5_noop = float(cf["probe_B_patch5_replacement"]["B2"]["p_noop"])
    c3_patch5_noop = float(cf["probe_B_patch5_replacement"]["C3"]["p_noop"])

    b2_patch7_noop = float(cf["probe_C_patch7_replacement"]["B2"]["p_noop"])
    c3_patch7_noop = float(cf["probe_C_patch7_replacement"]["C3"]["p_noop"])

    worker_bc_pred = cf["probe_D_full_map_bc_sample"]["worker_reference"]["predicted_action"]
    base_bc_pred = cf["probe_D_full_map_bc_sample"]["base_reference"]["predicted_action"]

    if b2_mismatch or c3_mismatch:
        labels.append("RUNTIME_ACTOR_CELL_CHANNEL_ENCODING_MISMATCH")
        labels.append("OBSERVATION_EXTRACTION_BUG_SUSPECTED")
    else:
        e_b2 = cf["probe_E_owner_unit_action_direction_patch"]["B2"]
        e_c3 = cf["probe_E_owner_unit_action_direction_patch"]["C3"]
        if e_b2["predicted_action"] != "NoOp" or e_c3["predicted_action"] != "NoOp":
            labels.append("RUNTIME_CURRENT_ACTION_OR_DIRECTION_MISMATCH")

        cell_restores = (b2_cell_noop < b2_base_noop - 0.15) or (c3_cell_noop < c3_base_noop - 0.15)
        patch_restores = (
            (b2_patch5_noop < b2_base_noop - 0.15)
            or (c3_patch5_noop < c3_base_noop - 0.15)
            or (b2_patch7_noop < b2_base_noop - 0.15)
            or (c3_patch7_noop < c3_base_noop - 0.15)
        )

        if patch_restores and not cell_restores:
            labels.append("RUNTIME_LOCAL_CONTEXT_OOD")
        if worker_bc_pred in ("Harvest", "Produce") and base_bc_pred in ("Produce", "Harvest"):
            labels.append("STUDENT_REQUIRES_BC_CONTEXT_NOT_PRESENT_IN_UNITY")

        if not labels:
            labels.append("INCONCLUSIVE_NEEDS_STAGE10D11R")

    runtime_summary_counts = {
        "friendly_actor_cell_count": int(runtime_summary_payload.get("friendly_actor_cell_count", 0)),
        "friendly_worker_count": int(runtime_summary_payload.get("friendly_worker_count", 0)),
        "friendly_base_count": int(runtime_summary_payload.get("friendly_base_count", 0)),
    }

    scene_mismatch_score = 0
    runtime_map_stats = full_map_payload["runtime_reconstructed_map_summary"]
    worker_map_stats = full_map_payload["bc_representative_worker_map_summary"]
    for k in (
        "count_resources",
        "count_bases",
        "count_workers",
        "count_barracks",
        "count_combat_units",
        "friendly_actor_cells",
        "enemy_actor_cells",
    ):
        scene_mismatch_score += abs(int(runtime_map_stats[k]) - int(worker_map_stats[k]))
    if scene_mismatch_score >= 8:
        labels.append("UNITY_SCENE_DISTRIBUTION_MISMATCH")

    # Deduplicate while preserving order.
    seen = set()
    labels = [x for x in labels if not (x in seen or seen.add(x))]

    if "RUNTIME_ACTOR_CELL_CHANNEL_ENCODING_MISMATCH" in labels:
        next_gate = "GO_FOR_UNITY_OBSERVATION_BUILDER_FIX"
    elif "RUNTIME_CURRENT_ACTION_OR_DIRECTION_MISMATCH" in labels:
        next_gate = "GO_FOR_RUNTIME_CHANNEL_SEMANTIC_REMAP_FIX"
    elif "UNITY_SCENE_DISTRIBUTION_MISMATCH" in labels:
        next_gate = "GO_FOR_UNITY_SCENE_DISTRIBUTION_ALIGNMENT"
    elif "STUDENT_REQUIRES_BC_CONTEXT_NOT_PRESENT_IN_UNITY" in labels:
        next_gate = "GO_FOR_TARGETED_BC_AUGMENTATION_WITH_UNITY_LIKE_STATES"
    else:
        next_gate = "GO_FOR_STAGE10D11R_DEEPER_PROBES"

    # Markdown report.
    md = []
    md.append("# STAGE10D11 Runtime-vs-BC Observation Distribution Audit")
    md.append("")
    md.append(f"Generated at UTC: {utc_now()}")
    md.append("")
    md.append("## Section 1 - Inputs and validation")
    md.append(f"- runtime cell table: {runtime_cell_table.as_posix()}")
    md.append(f"- runtime logits snapshot: {runtime_logits_snapshot.as_posix()}")
    md.append(f"- runtime summary: {runtime_summary.as_posix()}")
    md.append(f"- legacy runtime snapshot: {legacy_runtime_snapshot.as_posix()}")
    md.append(f"- bc ready dir: {bc_dir.as_posix()}")
    md.append(f"- checkpoint: {checkpoint.as_posix()}")
    md.append(f"- runtime cell table rows: {len(rows)}")
    md.append(f"- bc dataset loaded: train={split_sample_counts['train']}, validation={split_sample_counts['validation']}")
    md.append(f"- checkpoint loaded: {checkpoint.exists()}")
    md.append("- mutation scope: read-only analysis; writes only to python/week6_student/reports")
    md.append("")

    md.append("## Section 2 - Runtime focus cell channel audit")
    for label in ("B2", "C3"):
        c = focus_audit["focus_cells"][label]
        md.append(f"- {label}: owner={c['decoded_observation_owner']}, unit={c['decoded_observation_unit_type']}, predicted={c['predicted_action_type_name']}")
        md.append(
            f"  - probs: noop={c['probabilities']['p_noop']:.6f}, harvest={c['probabilities']['p_harvest']:.6f}, produce={c['probabilities']['p_produce']:.6f}"
        )
        md.append(f"  - critical_observation_encoding_mismatch={c['critical_observation_encoding_mismatch']}")
    md.append("")

    md.append("## Section 3 - BC positive actor-cell statistics")
    md.append(
        f"- Worker+Harvest count: {bc_stats_payload['worker_harvest']['count']}"
    )
    md.append(
        f"- Base+Produce count: {bc_stats_payload['base_produce']['count']}"
    )
    md.append(
        f"- Worker owner pattern: {bc_stats_payload['worker_harvest']['most_common_owner_onehot']}"
    )
    md.append(
        f"- Base owner pattern: {bc_stats_payload['base_produce']['most_common_owner_onehot']}"
    )
    md.append("")

    md.append("## Section 4 - Runtime-vs-BC channel deltas")
    md.append(
        f"- B2 nearest L2 27ch: {runtime_vs_bc_delta['B2_vs_worker_harvest']['nearest_27ch']['dist']:.6f}"
    )
    md.append(
        f"- B2 nearest patch5 L2: {runtime_vs_bc_delta['B2_vs_worker_harvest']['nearest_5x5']['distance']:.6f}"
    )
    md.append(
        f"- B2 nearest patch7 L2: {runtime_vs_bc_delta['B2_vs_worker_harvest']['nearest_7x7']['distance']:.6f}"
    )
    md.append(
        f"- C3 nearest L2 27ch: {runtime_vs_bc_delta['C3_vs_base_produce']['nearest_27ch']['dist']:.6f}"
    )
    md.append(
        f"- C3 nearest patch5 L2: {runtime_vs_bc_delta['C3_vs_base_produce']['nearest_5x5']['distance']:.6f}"
    )
    md.append(
        f"- C3 nearest patch7 L2: {runtime_vs_bc_delta['C3_vs_base_produce']['nearest_7x7']['distance']:.6f}"
    )
    md.append("")

    md.append("## Section 5 - Full-map and local context comparison")
    md.append(f"- Runtime map summary: {full_map_payload['runtime_reconstructed_map_summary']}")
    md.append(f"- BC worker representative summary: {full_map_payload['bc_representative_worker_map_summary']}")
    md.append(f"- BC base representative summary: {full_map_payload['bc_representative_base_map_summary']}")
    md.append(f"- Local context deltas: {full_map_payload['local_context']}")
    md.append("")

    md.append("## Section 6 - Student confidence comparison")
    md.append(
        f"- Runtime B2: predicted={conf_payload['runtime_reconstructed_from_stage10d10_cell_table']['B2']['predicted_action']}, "
        f"p_noop={conf_payload['runtime_reconstructed_from_stage10d10_cell_table']['B2']['p_noop']:.6f}, "
        f"p_harvest={conf_payload['runtime_reconstructed_from_stage10d10_cell_table']['B2']['p_harvest']:.6f}"
    )
    md.append(
        f"- Runtime C3: predicted={conf_payload['runtime_reconstructed_from_stage10d10_cell_table']['C3']['predicted_action']}, "
        f"p_noop={conf_payload['runtime_reconstructed_from_stage10d10_cell_table']['C3']['p_noop']:.6f}, "
        f"p_produce={conf_payload['runtime_reconstructed_from_stage10d10_cell_table']['C3']['p_produce']:.6f}"
    )
    md.append(
        f"- BC Worker+Harvest mean p_harvest={conf_payload['bc_validation_positive_confidence']['worker_harvest']['mean_p_harvest']:.6f}, "
        f"mean p_noop={conf_payload['bc_validation_positive_confidence']['worker_harvest']['mean_p_noop']:.6f}"
    )
    md.append(
        f"- BC Base+Produce mean p_produce={conf_payload['bc_validation_positive_confidence']['base_produce']['mean_p_produce']:.6f}, "
        f"mean p_noop={conf_payload['bc_validation_positive_confidence']['base_produce']['mean_p_noop']:.6f}"
    )
    md.append("")

    md.append("## Section 7 - Counterfactual probe results")
    md.append(f"- Probe A: {cf['probe_A_cell_replacement']}")
    md.append(f"- Probe B: {cf['probe_B_patch5_replacement']}")
    md.append(f"- Probe C: {cf['probe_C_patch7_replacement']}")
    md.append(f"- Probe D: {cf['probe_D_full_map_bc_sample']}")
    md.append(f"- Probe E: {cf['probe_E_owner_unit_action_direction_patch']}")
    md.append("")

    md.append("## Section 8 - Evidence-based classification")
    for item in labels:
        md.append(f"- {item}")
    md.append("")

    md.append("## Section 9 - Recommended next gate")
    md.append(f"- Primary next gate: {next_gate}")
    md.append("")

    report_paths["md_report"].write_text("\n".join(md), encoding="utf-8")

    print(str(report_paths["focus_cell_audit"]))
    print(str(report_paths["bc_positive_stats"]))
    print(str(report_paths["runtime_vs_bc_delta"]))
    print(str(report_paths["full_map_comparison"]))
    print(str(report_paths["confidence"]))
    print(str(report_paths["counterfactual"]))
    print(str(report_paths["md_report"]))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
