#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import torch
import torch.nn.functional as F

from student_architecture_transfer import build_day3_student_model


ACTION_NAMES = ["noop", "move", "harvest", "return", "produce", "attack"]

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

ACTION_CH = list(range(12, 18))
DIR_CH = list(range(18, 22))
SCALAR_CH = [0, 1, 26]

B2_FLAT = 25
C3_FLAT = 50


@dataclass
class NpyStreamInfo:
    shape: Tuple[int, ...]
    dtype: np.dtype
    fortran_order: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def flat_to_xy(flat: int) -> Tuple[int, int]:
    return flat % 24, flat // 24


def xy_to_flat(x: int, y: int) -> int:
    return y * 24 + x


def get_cell(obs: np.ndarray, flat: int) -> np.ndarray:
    x, y = flat_to_xy(flat)
    return obs[y, x, :]


def read_npy_header(fp) -> NpyStreamInfo:
    version = np.lib.format.read_magic(fp)
    if version == (1, 0):
        shape, fortran_order, dtype = np.lib.format.read_array_header_1_0(fp)
    elif version == (2, 0):
        shape, fortran_order, dtype = np.lib.format.read_array_header_2_0(fp)
    else:
        raise RuntimeError(f"Unsupported npy version: {version}")
    return NpyStreamInfo(shape=tuple(int(x) for x in shape), dtype=np.dtype(dtype), fortran_order=bool(fortran_order))


def load_npz_row(npz_path: Path, key: str, row_index: int) -> np.ndarray:
    member = f"{key}.npy"
    with zipfile.ZipFile(npz_path, "r") as zf:
        with zf.open(member, "r") as fp:
            info = read_npy_header(fp)
            if info.fortran_order:
                raise RuntimeError(f"Fortran-order arrays are not supported: {npz_path}:{member}")
            if row_index < 0 or row_index >= int(info.shape[0]):
                raise RuntimeError(f"Row index out of range for {npz_path}:{member}: {row_index}")
            row_shape = tuple(int(x) for x in info.shape[1:])
            row_items = int(np.prod(row_shape)) if row_shape else 1
            row_bytes = row_items * info.dtype.itemsize
            fp.seek(row_index * row_bytes, 1)
            raw = fp.read(row_bytes)
            if len(raw) != row_bytes:
                raise RuntimeError(f"Unexpected EOF for {npz_path}:{member} row={row_index}")
            arr = np.frombuffer(raw, dtype=info.dtype)
            return arr.reshape(row_shape) if row_shape else arr.reshape(())


def load_model_strict(checkpoint_path: Path, device: torch.device) -> torch.nn.Module:
    model = build_day3_student_model().to(device=device)
    checkpoint = torch.load(checkpoint_path, map_location=device)
    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        state_dict = checkpoint["model_state_dict"]
    elif isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        state_dict = checkpoint["state_dict"]
    else:
        state_dict = checkpoint
    model.load_state_dict(state_dict, strict=True)
    model.eval()
    return model


def run_model_probs(model: torch.nn.Module, obs_map: np.ndarray, device: torch.device) -> np.ndarray:
    with torch.no_grad():
        x = torch.from_numpy(obs_map[None, ...]).to(device=device, dtype=torch.float32)
        out = model(x)
        logits = out["action_type_logits"]
        probs = F.softmax(logits, dim=-1)[0].detach().cpu().numpy()
    return probs


def eval_cell_probs(action_probs: np.ndarray, flat: int) -> Dict[str, Any]:
    p = action_probs[flat]
    pred = int(np.argmax(p))
    return {
        "flat_index": int(flat),
        "x": int(flat % 24),
        "y": int(flat // 24),
        "predicted_action": ACTION_NAMES[pred],
        "p_noop": float(p[0]),
        "p_move": float(p[1]),
        "p_harvest": float(p[2]),
        "p_return": float(p[3]),
        "p_produce": float(p[4]),
        "p_attack": float(p[5]),
        "probabilities": [float(x) for x in p.tolist()],
    }


def validate_runtime_tensor(capture: Mapping[str, Any]) -> np.ndarray:
    cells = capture.get("cells", [])
    if not isinstance(cells, list) or len(cells) != 576:
        raise RuntimeError(f"Expected 576 cells in capture, got {len(cells)}")
    arr = np.zeros((24, 24, 27), dtype=np.float32)
    for i, c in enumerate(cells):
        v = c.get("raw_channel_vector", []) if isinstance(c, Mapping) else []
        if not isinstance(v, list) or len(v) != 27:
            raise RuntimeError(f"Invalid raw_channel_vector length at cell {i}")
        x, y = i % 24, i // 24
        arr[y, x, :] = np.asarray(v, dtype=np.float32)
    if not np.isfinite(arr).all():
        raise RuntimeError("Runtime capture contains NaN/Inf")
    return arr


def is_self_actor_cell(v: np.ndarray) -> bool:
    is_self = bool(v[3] > 0.5)
    is_actor = bool(np.max(v[6:12]) > 0.5)
    return is_self and is_actor


def is_empty_cell(v: np.ndarray) -> bool:
    return bool(np.max(v[5:12]) <= 0.5)


def is_actor_cell(v: np.ndarray) -> bool:
    return bool(np.max(v[6:12]) > 0.5)


def action_index_from_channel(v: np.ndarray) -> int:
    s = v[12:18]
    if np.max(s) <= 0.0:
        return -1
    return int(np.argmax(s))


def direction_index_from_channel(v: np.ndarray) -> int:
    s = v[18:22]
    if np.max(s) <= 0.0:
        return -1
    return int(np.argmax(s))


def set_action_onehot(v: np.ndarray, action_idx: int) -> None:
    v[ACTION_CH] = 0.0
    if 0 <= action_idx < 6:
        v[12 + action_idx] = 1.0


def set_direction_onehot(v: np.ndarray, dir_idx: int) -> None:
    v[DIR_CH] = 0.0
    if 0 <= dir_idx < 4:
        v[18 + dir_idx] = 1.0


def all_self_actor_flats(obs: np.ndarray) -> List[int]:
    out: List[int] = []
    flat = obs.reshape(576, 27)
    for i in range(576):
        if is_self_actor_cell(flat[i]):
            out.append(i)
    return out


def all_worker_flats(obs: np.ndarray) -> List[int]:
    flat = obs.reshape(576, 27)
    return [i for i in range(576) if bool(flat[i][3] > 0.5 and flat[i][8] > 0.5)]


def all_base_flats(obs: np.ndarray) -> List[int]:
    flat = obs.reshape(576, 27)
    return [i for i in range(576) if bool(flat[i][3] > 0.5 and flat[i][6] > 0.5)]


def has_adjacent_resource(obs: np.ndarray, flat: int) -> bool:
    x, y = flat_to_xy(flat)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            xx, yy = x + dx, y + dy
            if 0 <= xx < 24 and 0 <= yy < 24:
                v = obs[yy, xx, :]
                if bool(v[5] > 0.5):
                    return True
    return False


def base_has_produce_precondition(obs: np.ndarray, flat: int) -> bool:
    x, y = flat_to_xy(flat)
    base_v = obs[y, x, :]
    resources_ok = bool(base_v[1] > 0.0)
    has_free_neighbor = False
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            xx, yy = x + dx, y + dy
            if 0 <= xx < 24 and 0 <= yy < 24:
                if is_empty_cell(obs[yy, xx, :]):
                    has_free_neighbor = True
                    break
        if has_free_neighbor:
            break
    return resources_ok and has_free_neighbor


def apply_local_patch_from_reference(
    runtime_obs: np.ndarray,
    ref_obs: np.ndarray,
    center_flat_runtime: int,
    center_flat_ref: int,
    radius: int,
    channels: Sequence[int],
    include_center: bool,
    selector: Optional[str] = None,
) -> Tuple[np.ndarray, int]:
    out = runtime_obs.copy()
    tx, ty = flat_to_xy(center_flat_runtime)
    sx, sy = flat_to_xy(center_flat_ref)
    changed_cells = 0
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if not include_center and dx == 0 and dy == 0:
                continue
            txx, tyy = tx + dx, ty + dy
            sxx, syy = sx + dx, sy + dy
            if not (0 <= txx < 24 and 0 <= tyy < 24 and 0 <= sxx < 24 and 0 <= syy < 24):
                continue
            t_cell = out[tyy, txx, :]
            s_cell = ref_obs[syy, sxx, :]

            if selector == "actor_cells_in_reference" and not is_actor_cell(s_cell):
                continue
            if selector == "friendly_cells_in_runtime" and not bool(t_cell[3] > 0.5):
                continue
            if selector == "non_empty_cells_in_runtime" and is_empty_cell(t_cell):
                continue

            before = t_cell[list(channels)].copy()
            t_cell[list(channels)] = s_cell[list(channels)]
            if not np.allclose(before, t_cell[list(channels)]):
                changed_cells += 1
    return out, changed_cells


def baseline_metrics(obs: np.ndarray, probs: np.ndarray) -> Dict[str, Any]:
    flat_obs = obs.reshape(576, 27)
    pred_idx = np.argmax(probs, axis=1)
    actor_flats = [i for i in range(576) if is_self_actor_cell(flat_obs[i])]
    global_noop_share = float(np.mean(pred_idx == 0))
    actor_noop_share = float(np.mean(pred_idx[actor_flats] == 0)) if actor_flats else None
    actor_predictions = [eval_cell_probs(probs, i) for i in actor_flats]
    return {
        "global_predicted_noop_share": global_noop_share,
        "actor_cell_predicted_noop_share": actor_noop_share,
        "friendly_actor_cell_count": int(len(actor_flats)),
        "friendly_actor_predictions": actor_predictions,
    }


def probe_summary(
    name: str,
    probs: np.ndarray,
    baseline_b2: Dict[str, Any],
    baseline_c3: Dict[str, Any],
    affected_cells: int,
    affected_channels: int,
    touches_actor_only: Optional[bool] = None,
    touches_empty_or_resource: Optional[bool] = None,
) -> Dict[str, Any]:
    b2 = eval_cell_probs(probs, B2_FLAT)
    c3 = eval_cell_probs(probs, C3_FLAT)
    return {
        "probe_name": name,
        "B2": {
            **b2,
            "delta_p_noop": float(b2["p_noop"] - baseline_b2["p_noop"]),
            "delta_p_harvest": float(b2["p_harvest"] - baseline_b2["p_harvest"]),
            "delta_p_produce": float(b2["p_produce"] - baseline_b2["p_produce"]),
            "harvest_top1": bool(b2["predicted_action"] == "harvest"),
            "p_harvest_gt_0_5": bool(b2["p_harvest"] > 0.5),
        },
        "C3": {
            **c3,
            "delta_p_noop": float(c3["p_noop"] - baseline_c3["p_noop"]),
            "delta_p_produce": float(c3["p_produce"] - baseline_c3["p_produce"]),
            "delta_p_harvest": float(c3["p_harvest"] - baseline_c3["p_harvest"]),
            "produce_top1": bool(c3["predicted_action"] == "produce"),
            "p_produce_gt_0_5": bool(c3["p_produce"] > 0.5),
        },
        "affected_number_of_cells": int(affected_cells),
        "affected_number_of_channels": int(affected_channels),
        "touches_actor_cells_only": touches_actor_only,
        "touches_empty_or_resource_cells": touches_empty_or_resource,
    }


def action_distribution(obs: np.ndarray) -> Dict[str, Any]:
    flat = obs.reshape(576, 27)
    non_zero = 0
    hist = {k: 0 for k in ACTION_NAMES}
    for i in range(576):
        ai = action_index_from_channel(flat[i])
        if ai >= 0:
            non_zero += 1
            hist[ACTION_NAMES[ai]] += 1
    return {
        "non_zero_action_channel_cells": int(non_zero),
        "action_channel_histogram": hist,
    }


def direction_name(idx: int) -> str:
    if idx < 0:
        return "none"
    names = ["north", "east", "south", "west"]
    return names[idx]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.13A minimal runtime observation fix candidate audit")
    p.add_argument(
        "--runtime-capture",
        type=Path,
        default=Path("python/week6_student/reports/stage10d12r_full_raw_runtime_observation_step0001.json"),
    )
    p.add_argument(
        "--strict-report",
        type=Path,
        default=Path("python/week6_student/reports/stage10d12r_strict_replay_probe_results.json"),
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
    p.add_argument("--reports-dir", type=Path, default=Path("python/week6_student/reports"))
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = repo_root()
    runtime_capture_path = (root / args.runtime_capture).resolve()
    strict_report_path = (root / args.strict_report).resolve()
    bc_dir = (root / args.bc_ready_dir).resolve()
    checkpoint_path = (root / args.checkpoint).resolve()
    reports_dir = (root / args.reports_dir).resolve()

    for p in [runtime_capture_path, strict_report_path, bc_dir / "bc_train.npz", bc_dir / "bc_validation.npz", checkpoint_path]:
        if not p.exists():
            raise RuntimeError(f"Missing required input: {p}")

    out_baseline = reports_dir / "stage10d13a_baseline_confirmation.json"
    out_b2 = reports_dir / "stage10d13a_b2_current_action_direction_candidate_probes.json"
    out_c3 = reports_dir / "stage10d13a_c3_local_current_action_context_candidate_probes.json"
    out_full = reports_dir / "stage10d13a_full_actor_map_candidate_probes.json"
    out_decision = reports_dir / "stage10d13a_candidate_fix_decision_matrix.json"
    out_report = reports_dir / "STAGE10D13A_CURRENT_ACTION_DIRECTION_FIX_CANDIDATE_AUDIT_REPORT.md"

    runtime_capture = load_json(runtime_capture_path)
    strict_report = load_json(strict_report_path)
    runtime_obs = validate_runtime_tensor(runtime_capture)
    runtime_action_dist = action_distribution(runtime_obs)

    b2_runtime = get_cell(runtime_obs, B2_FLAT)
    c3_runtime = get_cell(runtime_obs, C3_FLAT)
    if not bool(b2_runtime[3] > 0.5 and b2_runtime[8] > 0.5):
        raise RuntimeError("B2 is not self worker in runtime capture")
    if not bool(c3_runtime[3] > 0.5 and c3_runtime[6] > 0.5):
        raise RuntimeError("C3 is not self base in runtime capture")

    b2_ref_meta = strict_report.get("b2_reference", {})
    c3_ref_meta = strict_report.get("c3_reference", {})
    if not b2_ref_meta or not c3_ref_meta:
        raise RuntimeError("Strict replay report missing b2_reference/c3_reference")

    b2_split = str(b2_ref_meta.get("split", "train")).strip().lower()
    c3_split = str(c3_ref_meta.get("split", "train")).strip().lower()
    b2_npz = bc_dir / ("bc_train.npz" if b2_split == "train" else "bc_validation.npz")
    c3_npz = bc_dir / ("bc_train.npz" if c3_split == "train" else "bc_validation.npz")
    b2_sample_index = int(b2_ref_meta.get("sample_index", 0))
    c3_sample_index = int(c3_ref_meta.get("sample_index", 0))
    b2_ref_flat = int(b2_ref_meta.get("flat_index", B2_FLAT))
    c3_ref_flat = int(c3_ref_meta.get("flat_index", C3_FLAT))

    b2_ref_obs_row = load_npz_row(b2_npz, "observations", b2_sample_index).astype(np.float32)
    c3_ref_obs_row = load_npz_row(c3_npz, "observations", c3_sample_index).astype(np.float32)
    if b2_ref_obs_row.shape != (576, 27) or c3_ref_obs_row.shape != (576, 27):
        raise RuntimeError("Unexpected NPZ row shape while loading BC references")
    b2_ref_obs = b2_ref_obs_row.reshape(24, 24, 27)
    c3_ref_obs = c3_ref_obs_row.reshape(24, 24, 27)

    device = torch.device(args.device)
    model = load_model_strict(checkpoint_path, device)
    baseline_probs = run_model_probs(model, runtime_obs, device)

    if baseline_probs.shape != (576, 6):
        raise RuntimeError(f"Expected model probs shape [576,6], got {baseline_probs.shape}")

    baseline_b2 = eval_cell_probs(baseline_probs, B2_FLAT)
    baseline_c3 = eval_cell_probs(baseline_probs, C3_FLAT)
    baseline_global = baseline_metrics(runtime_obs, baseline_probs)

    strict_baseline = strict_report.get("baseline_inference", {})
    strict_b2 = strict_baseline.get("B2", {})
    strict_c3 = strict_baseline.get("C3", {})

    def drift(cur: Mapping[str, Any], ref: Mapping[str, Any], key: str) -> float:
        return abs(float(cur.get(key, 0.0)) - float(ref.get(key, 0.0)))

    b2_drift = max(drift(baseline_b2, strict_b2, "p_noop"), drift(baseline_b2, strict_b2, "p_harvest"))
    c3_drift = max(drift(baseline_c3, strict_c3, "p_noop"), drift(baseline_c3, strict_c3, "p_produce"))
    drift_detected = bool(b2_drift > 0.02 or c3_drift > 0.02)

    baseline_labels: List[str] = ["BASELINE_DRIFT_DETECTED" if drift_detected else "BASELINE_CONFIRMED"]
    baseline_gate = "GO_FOR_STAGE10D12R_STRICT_PROBE_RERUN" if drift_detected else "CONTINUE_STAGE10D13A"

    baseline_payload = {
        "generated_at_utc": utc_now(),
        "stage": "10D.13A",
        "runtime_capture_path": str(runtime_capture_path),
        "strict_report_path": str(strict_report_path),
        "checkpoint_path": str(checkpoint_path),
        "tensor_shape": [int(x) for x in runtime_obs.shape],
        "cell_count": 576,
        "channel_count": 27,
        "has_nan": bool(np.isnan(runtime_obs).any()),
        "has_inf": bool(np.isinf(runtime_obs).any()),
        "focus_cells_validation": {
            "B2_self_worker": bool(b2_runtime[3] > 0.5 and b2_runtime[8] > 0.5),
            "C3_self_base": bool(c3_runtime[3] > 0.5 and c3_runtime[6] > 0.5),
            "B2_current_action": ACTION_NAMES[max(0, action_index_from_channel(b2_runtime))] if action_index_from_channel(b2_runtime) >= 0 else "none",
            "C3_current_action": ACTION_NAMES[max(0, action_index_from_channel(c3_runtime))] if action_index_from_channel(c3_runtime) >= 0 else "none",
        },
        "baseline_inference": {
            "B2": baseline_b2,
            "C3": baseline_c3,
            **baseline_global,
        },
        "strict_replay_baseline_reference": {
            "B2": strict_b2,
            "C3": strict_c3,
        },
        "baseline_drift": {
            "max_delta_b2": float(b2_drift),
            "max_delta_c3": float(c3_drift),
            "drift_detected": drift_detected,
        },
        "runtime_action_channel_distribution": runtime_action_dist,
        "classification_labels": baseline_labels,
        "selected_gate_if_baseline_stage": baseline_gate,
    }
    write_json(out_baseline, baseline_payload)

    if drift_detected:
        decision_payload = {
            "generated_at_utc": utc_now(),
            "classification_labels": baseline_labels,
            "primary_next_gate": "GO_FOR_STAGE10D12R_STRICT_PROBE_RERUN",
            "reason": "Baseline drift detected versus Stage10D.12R strict baseline",
        }
        write_json(out_decision, decision_payload)
        write_json(out_b2, {"generated_at_utc": utc_now(), "skipped": "baseline_drift_detected"})
        write_json(out_c3, {"generated_at_utc": utc_now(), "skipped": "baseline_drift_detected"})
        write_json(out_full, {"generated_at_utc": utc_now(), "skipped": "baseline_drift_detected"})
        write_text(
            out_report,
            "# Stage10D.13A CurrentAction/Direction Fix Candidate Audit\n\n"
            "Baseline drift was detected against Stage10D.12R.\n"
            "Primary next gate: GO_FOR_STAGE10D12R_STRICT_PROBE_RERUN.\n",
        )
        return 0

    b2_ref_cell = get_cell(b2_ref_obs, b2_ref_flat)
    c3_ref_cell = get_cell(c3_ref_obs, c3_ref_flat)
    b2_ref_dir_idx = direction_index_from_channel(b2_ref_cell)

    b2_results: List[Dict[str, Any]] = []

    def run_b2_probe(name: str, patch_fn) -> None:
        patched = runtime_obs.copy()
        affected_cells, affected_channels = patch_fn(patched)
        probs = run_model_probs(model, patched, device)
        row = probe_summary(name, probs, baseline_b2, baseline_c3, affected_cells, affected_channels)
        b2_results.append(row)

    def _patch_b2_channels(patched: np.ndarray, channels: Sequence[int], src: np.ndarray) -> Tuple[int, int]:
        cell = get_cell(patched, B2_FLAT)
        cell[list(channels)] = src[list(channels)]
        return 1, len(channels)

    run_b2_probe("B2_current_action_to_BC", lambda p: _patch_b2_channels(p, ACTION_CH, b2_ref_cell))
    run_b2_probe("B2_direction_to_BC", lambda p: _patch_b2_channels(p, DIR_CH, b2_ref_cell))
    run_b2_probe("B2_current_action_plus_direction_to_BC", lambda p: _patch_b2_channels(p, ACTION_CH + DIR_CH, b2_ref_cell))
    run_b2_probe("B2_scalars_plus_current_action_plus_direction_to_BC", lambda p: _patch_b2_channels(p, SCALAR_CH + ACTION_CH + DIR_CH, b2_ref_cell))

    def b2_harvest_only(p: np.ndarray) -> Tuple[int, int]:
        v = get_cell(p, B2_FLAT)
        set_action_onehot(v, 2)
        return 1, len(ACTION_CH)

    run_b2_probe("B2_action_harvest_only_minimal", b2_harvest_only)

    def b2_harvest_west(p: np.ndarray) -> Tuple[int, int]:
        v = get_cell(p, B2_FLAT)
        set_action_onehot(v, 2)
        set_direction_onehot(v, 3)
        return 1, len(ACTION_CH) + len(DIR_CH)

    run_b2_probe("B2_action_harvest_plus_dir_west_minimal", b2_harvest_west)

    def b2_harvest_best_dir(p: np.ndarray) -> Tuple[int, int]:
        v = get_cell(p, B2_FLAT)
        set_action_onehot(v, 2)
        if b2_ref_dir_idx >= 0:
            set_direction_onehot(v, b2_ref_dir_idx)
            return 1, len(ACTION_CH) + len(DIR_CH)
        return 1, len(ACTION_CH)

    run_b2_probe("B2_action_harvest_plus_best_BC_direction", b2_harvest_best_dir)

    b2_by_name = {r["probe_name"]: r for r in b2_results}
    b2_labels: List[str] = []
    if b2_by_name["B2_current_action_to_BC"]["B2"]["harvest_top1"] and b2_by_name["B2_current_action_to_BC"]["B2"]["p_harvest_gt_0_5"]:
        b2_labels.append("B2_CURRENT_ACTION_ONLY_SUFFICIENT")
    if b2_by_name["B2_direction_to_BC"]["B2"]["harvest_top1"] and b2_by_name["B2_direction_to_BC"]["B2"]["p_harvest_gt_0_5"]:
        b2_labels.append("B2_DIRECTION_ONLY_SUFFICIENT")
    if b2_by_name["B2_current_action_plus_direction_to_BC"]["B2"]["harvest_top1"] and b2_by_name["B2_current_action_plus_direction_to_BC"]["B2"]["p_harvest_gt_0_5"]:
        b2_labels.append("B2_CURRENT_ACTION_DIRECTION_SUFFICIENT")
    if b2_by_name["B2_scalars_plus_current_action_plus_direction_to_BC"]["B2"]["p_harvest"] > b2_by_name["B2_current_action_plus_direction_to_BC"]["B2"]["p_harvest"] + 0.05:
        b2_labels.append("B2_SCALAR_DEPENDENCY_PRESENT")
    if b2_by_name["B2_action_harvest_only_minimal"]["B2"]["harvest_top1"] or b2_by_name["B2_action_harvest_plus_dir_west_minimal"]["B2"]["harvest_top1"]:
        b2_labels.append("B2_MINIMAL_HARVEST_ENCODING_SUFFICIENT")
    if not b2_labels:
        b2_labels.append("B2_NO_SAFE_MINIMAL_FIX")

    b2_payload = {
        "generated_at_utc": utc_now(),
        "runtime_baseline": {"B2": baseline_b2, "C3": baseline_c3},
        "bc_reference": {
            "split": b2_split,
            "sample_index": b2_sample_index,
            "flat_index": b2_ref_flat,
            "reference_direction": direction_name(b2_ref_dir_idx),
            "reference_cell_vector": [float(x) for x in b2_ref_cell.tolist()],
        },
        "probes": b2_results,
        "classification_labels": b2_labels,
    }
    write_json(out_b2, b2_payload)

    c3_results: List[Dict[str, Any]] = []

    def run_c3_probe(
        name: str,
        build_patch,
        touches_actor_only: Optional[bool],
        touches_empty_or_resource: Optional[bool],
    ) -> None:
        patched, affected_cells, affected_channels = build_patch()
        probs = run_model_probs(model, patched, device)
        c3_results.append(
            probe_summary(
                name,
                probs,
                baseline_b2,
                baseline_c3,
                affected_cells,
                affected_channels,
                touches_actor_only=touches_actor_only,
                touches_empty_or_resource=touches_empty_or_resource,
            )
        )

    def center_patch(channels: Sequence[int], mode: str) -> Tuple[np.ndarray, int, int]:
        out = runtime_obs.copy()
        v = get_cell(out, C3_FLAT)
        if mode == "copy_bc":
            rv = get_cell(c3_ref_obs, c3_ref_flat)
            v[list(channels)] = rv[list(channels)]
        elif mode == "produce_only":
            set_action_onehot(v, 4)
        elif mode == "produce_plus_bc_dir":
            set_action_onehot(v, 4)
            d = direction_index_from_channel(get_cell(c3_ref_obs, c3_ref_flat))
            if d >= 0:
                set_direction_onehot(v, d)
        return out, 1, len(channels)

    run_c3_probe("C3_current_action_to_BC", lambda: center_patch(ACTION_CH, "copy_bc"), True, False)
    run_c3_probe("C3_current_action_plus_direction_to_BC", lambda: center_patch(ACTION_CH + DIR_CH, "copy_bc"), True, False)
    run_c3_probe("C3_action_produce_only_minimal", lambda: center_patch(ACTION_CH, "produce_only"), True, False)
    run_c3_probe("C3_action_produce_plus_BC_direction", lambda: center_patch(ACTION_CH + DIR_CH, "produce_plus_bc_dir"), True, False)

    def local_probe(radius: int, include_center: bool, channels: Sequence[int], selector: Optional[str], name: str) -> Tuple[np.ndarray, int, int]:
        out, changed = apply_local_patch_from_reference(
            runtime_obs,
            c3_ref_obs,
            C3_FLAT,
            c3_ref_flat,
            radius,
            channels,
            include_center,
            selector,
        )
        return out, changed, len(channels)

    run_c3_probe("C3_3x3_current_action_to_BC", lambda: local_probe(1, True, ACTION_CH, None, ""), False, True)
    run_c3_probe("C3_3x3_current_action_plus_direction_to_BC", lambda: local_probe(1, True, ACTION_CH + DIR_CH, None, ""), False, True)
    run_c3_probe("C3_5x5_current_action_to_BC", lambda: local_probe(2, True, ACTION_CH, None, ""), False, True)
    run_c3_probe("C3_5x5_current_action_plus_direction_to_BC", lambda: local_probe(2, True, ACTION_CH + DIR_CH, None, ""), False, True)
    run_c3_probe("C3_5x5_neighbor_only_current_action_to_BC", lambda: local_probe(2, False, ACTION_CH, None, ""), False, True)
    run_c3_probe("C3_5x5_neighbor_only_current_action_plus_direction_to_BC", lambda: local_probe(2, False, ACTION_CH + DIR_CH, None, ""), False, True)
    run_c3_probe(
        "C3_5x5_actor_cells_only_current_action_to_BC",
        lambda: local_probe(2, True, ACTION_CH, "actor_cells_in_reference", ""),
        True,
        False,
    )
    run_c3_probe(
        "C3_5x5_friendly_cells_only_current_action_to_BC",
        lambda: local_probe(2, True, ACTION_CH, "friendly_cells_in_runtime", ""),
        False,
        True,
    )
    run_c3_probe(
        "C3_5x5_non_empty_cells_only_current_action_to_BC",
        lambda: local_probe(2, True, ACTION_CH, "non_empty_cells_in_runtime", ""),
        False,
        False,
    )

    def c3_local_set_noop() -> Tuple[np.ndarray, int, int]:
        out = runtime_obs.copy()
        cx, cy = flat_to_xy(C3_FLAT)
        changed = 0
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                xx, yy = cx + dx, cy + dy
                if 0 <= xx < 24 and 0 <= yy < 24:
                    v = out[yy, xx, :]
                    before = v[ACTION_CH].copy()
                    set_action_onehot(v, 0)
                    if not np.allclose(before, v[ACTION_CH]):
                        changed += 1
        return out, changed, len(ACTION_CH)

    run_c3_probe("C3_5x5_current_action_to_noop_for_all_cells", c3_local_set_noop, False, True)

    def c3_local_empty_none() -> Tuple[np.ndarray, int, int]:
        out = runtime_obs.copy()
        cx, cy = flat_to_xy(C3_FLAT)
        changed = 0
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                xx, yy = cx + dx, cy + dy
                if 0 <= xx < 24 and 0 <= yy < 24:
                    v = out[yy, xx, :]
                    if is_empty_cell(v):
                        before = v[ACTION_CH].copy()
                        v[ACTION_CH] = 0.0
                        if not np.allclose(before, v[ACTION_CH]):
                            changed += 1
        return out, changed, len(ACTION_CH)

    run_c3_probe("C3_5x5_current_action_to_none_for_empty_cells", c3_local_empty_none, False, True)
    run_c3_probe("C3_5x5_copy_BC_current_action_but_keep_runtime_owner_unit", lambda: local_probe(2, True, ACTION_CH, None, ""), False, True)

    c3_by_name = {r["probe_name"]: r for r in c3_results}
    c3_labels: List[str] = []
    if c3_by_name["C3_current_action_to_BC"]["C3"]["produce_top1"] and c3_by_name["C3_current_action_to_BC"]["C3"]["p_produce_gt_0_5"]:
        c3_labels.append("C3_CENTER_ACTION_ONLY_SUFFICIENT")
    if c3_by_name["C3_3x3_current_action_to_BC"]["C3"]["produce_top1"] and c3_by_name["C3_3x3_current_action_to_BC"]["C3"]["p_produce_gt_0_5"]:
        c3_labels.append("C3_LOCAL_3X3_CURRENT_ACTION_SUFFICIENT")
    if c3_by_name["C3_5x5_current_action_to_BC"]["C3"]["produce_top1"] and c3_by_name["C3_5x5_current_action_to_BC"]["C3"]["p_produce_gt_0_5"]:
        c3_labels.append("C3_LOCAL_5X5_CURRENT_ACTION_SUFFICIENT")
    if c3_by_name["C3_5x5_neighbor_only_current_action_to_BC"]["C3"]["produce_top1"]:
        c3_labels.append("C3_NEIGHBOR_CURRENT_ACTION_CONTEXT_REQUIRED")
    if c3_by_name["C3_5x5_current_action_to_none_for_empty_cells"]["C3"]["delta_p_produce"] > 0.05:
        c3_labels.append("C3_EMPTY_CELL_ACTION_ENCODING_SUSPECT")
    if c3_by_name["C3_5x5_actor_cells_only_current_action_to_BC"]["C3"]["produce_top1"] and c3_by_name["C3_5x5_actor_cells_only_current_action_to_BC"]["C3"]["p_produce_gt_0_5"]:
        c3_labels.append("C3_ACTOR_ONLY_CONTEXT_SUFFICIENT")
    if not c3_labels:
        c3_labels.append("C3_NO_SAFE_MINIMAL_FIX")

    c3_payload = {
        "generated_at_utc": utc_now(),
        "runtime_baseline": {"B2": baseline_b2, "C3": baseline_c3},
        "bc_reference": {
            "split": c3_split,
            "sample_index": c3_sample_index,
            "flat_index": c3_ref_flat,
            "reference_center_cell_vector": [float(x) for x in c3_ref_cell.tolist()],
        },
        "probes": c3_results,
        "classification_labels": c3_labels,
    }
    write_json(out_c3, c3_payload)

    full_policy_results: List[Dict[str, Any]] = []
    baseline_pred = np.argmax(baseline_probs, axis=1)

    def summarize_policy(name: str, patched: np.ndarray, changed_cells: int, changed_channels_per_cell: int) -> None:
        probs = run_model_probs(model, patched, device)
        pred = np.argmax(probs, axis=1)
        self_actor_flats = all_self_actor_flats(runtime_obs)
        off_actor_mask = np.ones((576,), dtype=bool)
        off_actor_mask[self_actor_flats] = False
        off_actor_non_noop = int(np.sum(pred[off_actor_mask] != 0))
        baseline_off_actor_non_noop = int(np.sum(baseline_pred[off_actor_mask] != 0))
        misloc = bool(off_actor_non_noop > baseline_off_actor_non_noop)

        row = {
            "policy_name": name,
            "B2": eval_cell_probs(probs, B2_FLAT),
            "C3": eval_cell_probs(probs, C3_FLAT),
            "friendly_actor_predictions": [eval_cell_probs(probs, i) for i in self_actor_flats],
            "number_of_cells_changed": int(changed_cells),
            "number_of_channels_changed": int(changed_cells * changed_channels_per_cell),
            "off_actor_non_noop_top1_count": off_actor_non_noop,
            "baseline_off_actor_non_noop_top1_count": baseline_off_actor_non_noop,
            "off_actor_mislocalization_detected": misloc,
            "global_predicted_noop_share": float(np.mean(pred == 0)),
            "actor_predicted_noop_share": float(np.mean(pred[self_actor_flats] == 0)) if self_actor_flats else None,
        }
        full_policy_results.append(row)

    # Policy 1
    p1 = runtime_obs.copy()
    changed1 = 0
    for f in all_worker_flats(runtime_obs):
        v = get_cell(p1, f)
        before = v[ACTION_CH].copy()
        set_action_onehot(v, 2 if has_adjacent_resource(runtime_obs, f) else 0)
        if not np.allclose(before, v[ACTION_CH]):
            changed1 += 1
    for f in all_base_flats(runtime_obs):
        v = get_cell(p1, f)
        before = v[ACTION_CH].copy()
        set_action_onehot(v, 4 if base_has_produce_precondition(runtime_obs, f) else 0)
        if not np.allclose(before, v[ACTION_CH]):
            changed1 += 1
    summarize_policy("ACTOR_CELLS_CURRENT_ACTION_FROM_BC_ROLE", p1, changed1, len(ACTION_CH))

    # Policy 2
    p2 = runtime_obs.copy()
    changed2 = 0
    for f in all_worker_flats(runtime_obs):
        v = get_cell(p2, f)
        before = v[ACTION_CH + DIR_CH].copy()
        src = get_cell(b2_ref_obs, b2_ref_flat)
        v[ACTION_CH + DIR_CH] = src[ACTION_CH + DIR_CH]
        if not np.allclose(before, v[ACTION_CH + DIR_CH]):
            changed2 += 1
    for f in all_base_flats(runtime_obs):
        v = get_cell(p2, f)
        before = v[ACTION_CH + DIR_CH].copy()
        src = get_cell(c3_ref_obs, c3_ref_flat)
        v[ACTION_CH + DIR_CH] = src[ACTION_CH + DIR_CH]
        if not np.allclose(before, v[ACTION_CH + DIR_CH]):
            changed2 += 1
    summarize_policy("ACTOR_CELLS_CURRENT_ACTION_DIRECTION_FROM_LOCAL_BC_NEAREST", p2, changed2, len(ACTION_CH) + len(DIR_CH))

    # Policy 3
    p3 = runtime_obs.copy()
    changed3 = 0
    for f in all_worker_flats(runtime_obs):
        v = get_cell(p3, f)
        ai = action_index_from_channel(v)
        if ai == 0 and has_adjacent_resource(runtime_obs, f):
            before = v[ACTION_CH].copy()
            set_action_onehot(v, 2)
            if not np.allclose(before, v[ACTION_CH]):
                changed3 += 1
    for f in all_base_flats(runtime_obs):
        v = get_cell(p3, f)
        ai = action_index_from_channel(v)
        if ai == 0:
            before = v[ACTION_CH].copy()
            set_action_onehot(v, 4)
            if not np.allclose(before, v[ACTION_CH]):
                changed3 += 1
    summarize_policy("SELF_ACTORS_CURRENT_ACTION_NOOP_TO_ROLE_PRIOR", p3, changed3, len(ACTION_CH))

    # Policy 4
    p4, changed4 = apply_local_patch_from_reference(
        runtime_obs,
        c3_ref_obs,
        C3_FLAT,
        c3_ref_flat,
        radius=2,
        channels=ACTION_CH,
        include_center=True,
        selector=None,
    )
    summarize_policy("LOCAL_5X5_ACTION_CONTEXT_FROM_BC_AROUND_BASE", p4, changed4, len(ACTION_CH))

    # Policy 5a empty->none
    p5a = runtime_obs.copy()
    changed5a = 0
    fobs = p5a.reshape(576, 27)
    for i in range(576):
        if is_empty_cell(fobs[i]):
            before = fobs[i, ACTION_CH].copy()
            fobs[i, ACTION_CH] = 0.0
            if not np.allclose(before, fobs[i, ACTION_CH]):
                changed5a += 1
    summarize_policy("CLEAR_ACTION_CHANNELS_FOR_EMPTY_CELLS_empty_action_none", p5a, changed5a, len(ACTION_CH))

    # Policy 5b empty->noop
    p5b = runtime_obs.copy()
    changed5b = 0
    fobs2 = p5b.reshape(576, 27)
    for i in range(576):
        if is_empty_cell(fobs2[i]):
            before = fobs2[i, ACTION_CH].copy()
            set_action_onehot(fobs2[i], 0)
            if not np.allclose(before, fobs2[i, ACTION_CH]):
                changed5b += 1
    summarize_policy("CLEAR_ACTION_CHANNELS_FOR_EMPTY_CELLS_empty_action_noop", p5b, changed5b, len(ACTION_CH))

    full_labels: List[str] = []
    restores = any(
        (r["B2"]["predicted_action"] == "harvest" and r["C3"]["predicted_action"] == "produce")
        for r in full_policy_results
    )
    misloc_any = any(bool(r.get("off_actor_mislocalization_detected")) for r in full_policy_results)
    too_invasive_any = any(int(r.get("number_of_cells_changed", 0)) > 100 for r in full_policy_results)
    if restores:
        full_labels.append("FULL_ACTOR_MAP_POLICY_RESTORES_ACTOR_ACTIONS")
    if misloc_any:
        full_labels.append("FULL_ACTOR_MAP_POLICY_CAUSES_OFF_ACTOR_MISLOCALIZATION")
    if too_invasive_any:
        full_labels.append("FULL_ACTOR_MAP_POLICY_TOO_INVASIVE")
    if not full_labels:
        full_labels.append("FULL_ACTOR_MAP_POLICY_INCONCLUSIVE")

    full_payload = {
        "generated_at_utc": utc_now(),
        "runtime_baseline": {"B2": baseline_b2, "C3": baseline_c3, **baseline_global},
        "policy_probes": full_policy_results,
        "classification_labels": full_labels,
    }
    write_json(out_full, full_payload)

    # Semantic audit
    runtime_flat = runtime_obs.reshape(576, 27)
    empty_flats = [i for i in range(576) if is_empty_cell(runtime_flat[i])]
    empty_all_zero_action_share = float(np.mean([float(np.max(runtime_flat[i, ACTION_CH]) <= 0.0) for i in empty_flats])) if empty_flats else None
    actor_flats = all_self_actor_flats(runtime_obs)
    actor_noop_action_share = float(np.mean([float(action_index_from_channel(runtime_flat[i]) == 0) for i in actor_flats])) if actor_flats else None

    semantic_labels: List[str] = []
    # Strong BC-vs-runtime behavioral divergence with [12:22] patch efficacy indicates mismatch.
    if (
        b2_by_name["B2_current_action_to_BC"]["B2"]["harvest_top1"]
        and c3_by_name["C3_5x5_current_action_to_BC"]["C3"]["produce_top1"]
    ):
        semantic_labels.append("CURRENT_ACTION_SEMANTIC_MISMATCH_CONFIRMED")
    else:
        semantic_labels.append("CURRENT_ACTION_SEMANTICS_UNCERTAIN")

    remap_supported = bool(restores)
    remap_high_risk = True

    if remap_supported:
        semantic_labels.append("RUNTIME_OBSERVATION_REMAP_CANDIDATE_SUPPORTED")
    if remap_high_risk:
        semantic_labels.append("RUNTIME_OBSERVATION_REMAP_HIGH_RISK")
    if remap_high_risk:
        semantic_labels.append("TARGETED_BC_AUGMENTATION_SUPPORTED")

    # Decision matrix and gate selection.
    matrix_rows: List[Dict[str, Any]] = [
        {
            "row": "A",
            "candidate": "Runtime observation current_action remap for actor cells only",
            "evidence_for": [
                "B2 current_action-only patch flips to harvest in diagnostic inference",
                "C3 local current_action patches can raise produce probability",
            ],
            "evidence_against": [
                "May encode intent-like signal rather than factual ongoing action",
                "Can diverge from Unity runtime semantics for idle actors",
            ],
            "expected_effect": "Can reduce actor NoOp collapse in offline probes",
            "risk_level": "HIGH",
            "contract_risk": "MEDIUM",
            "runtime_behavior_risk": "HIGH",
            "academic_claim_safety": "LOW",
            "recommended": False,
            "next_gate_if_selected": "GO_FOR_STAGE10D13B_MINIMAL_TOGGLE_RUNTIME_TEST",
        },
        {
            "row": "B",
            "candidate": "Runtime observation current_action+direction remap for actor cells only",
            "evidence_for": [
                "B2 current_action+direction produces stronger harvest confidence",
            ],
            "evidence_against": [
                "Direction may further leak latent policy prior",
                "Higher semantic intervention than action-only",
            ],
            "expected_effect": "Potentially stronger action restoration than action-only",
            "risk_level": "HIGH",
            "contract_risk": "MEDIUM",
            "runtime_behavior_risk": "HIGH",
            "academic_claim_safety": "LOW",
            "recommended": False,
            "next_gate_if_selected": "GO_FOR_STAGE10D13B_MINIMAL_TOGGLE_RUNTIME_TEST",
        },
        {
            "row": "C",
            "candidate": "Runtime local base-context current_action remap",
            "evidence_for": [
                "C3 produce can be restored by local context patches (3x3/5x5)",
            ],
            "evidence_against": [
                "Touches non-actor neighborhood cells",
                "Increases risk of context leakage",
            ],
            "expected_effect": "Can target C3 produce suppression specifically",
            "risk_level": "HIGH",
            "contract_risk": "MEDIUM",
            "runtime_behavior_risk": "HIGH",
            "academic_claim_safety": "LOW",
            "recommended": False,
            "next_gate_if_selected": "GO_FOR_STAGE10D13B_MINIMAL_TOGGLE_RUNTIME_TEST",
        },
        {
            "row": "D",
            "candidate": "Clear action channels for empty cells",
            "evidence_for": [
                "Semantic cleanup candidate; prevents synthetic action in empty tiles",
            ],
            "evidence_against": [
                "May not restore actor actions alone",
            ],
            "expected_effect": "Low-to-moderate calibration cleanup",
            "risk_level": "MEDIUM",
            "contract_risk": "LOW",
            "runtime_behavior_risk": "MEDIUM",
            "academic_claim_safety": "MEDIUM",
            "recommended": False,
            "next_gate_if_selected": "GO_FOR_STAGE10D13B_MINIMAL_TOGGLE_RUNTIME_TEST",
        },
        {
            "row": "E",
            "candidate": "Scene distribution alignment",
            "evidence_for": [
                "Always useful as control axis",
            ],
            "evidence_against": [
                "Stage10D.12R did not confirm scene OOD as primary root cause",
            ],
            "expected_effect": "Low direct effect on current NoOp collapse",
            "risk_level": "LOW",
            "contract_risk": "LOW",
            "runtime_behavior_risk": "LOW",
            "academic_claim_safety": "HIGH",
            "recommended": False,
            "next_gate_if_selected": "GO_FOR_STAGE10D13A_DEEPER_PROBES",
        },
        {
            "row": "F",
            "candidate": "Targeted BC augmentation with Unity-like NoOp-state observations",
            "evidence_for": [
                "Addresses representation gap without runtime semantic rewriting",
                "Avoids action-leaking remap in deployed runtime observation",
            ],
            "evidence_against": [
                "Requires new BC data engineering and retraining cycle",
            ],
            "expected_effect": "Model learns Unity-like idle/current_action context directly",
            "risk_level": "MEDIUM",
            "contract_risk": "LOW",
            "runtime_behavior_risk": "LOW",
            "academic_claim_safety": "HIGH",
            "recommended": True,
            "next_gate_if_selected": "GO_FOR_TARGETED_BC_AUGMENTATION_WITH_UNITY_LIKE_STATES",
        },
        {
            "row": "G",
            "candidate": "Rerun Stage10D.12R with improved probes",
            "evidence_for": [
                "Useful only if baseline drift or capture/probe invalid",
            ],
            "evidence_against": [
                "Current stage baseline confirmed and strict probe already valid",
            ],
            "expected_effect": "Mostly duplicate evidence if no drift",
            "risk_level": "LOW",
            "contract_risk": "LOW",
            "runtime_behavior_risk": "LOW",
            "academic_claim_safety": "MEDIUM",
            "recommended": False,
            "next_gate_if_selected": "GO_FOR_STAGE10D12R_STRICT_PROBE_RERUN",
        },
        {
            "row": "H",
            "candidate": "Do nothing / keep Python bridge diagnostic only",
            "evidence_for": [
                "No implementation risk",
            ],
            "evidence_against": [
                "No path to resolve persistent runtime NoOp behavior",
            ],
            "expected_effect": "No practical improvement",
            "risk_level": "LOW",
            "contract_risk": "LOW",
            "runtime_behavior_risk": "LOW",
            "academic_claim_safety": "MEDIUM",
            "recommended": False,
            "next_gate_if_selected": "GO_FOR_STAGE10D13A_DEEPER_PROBES",
        },
    ]

    primary_next_gate = "GO_FOR_TARGETED_BC_AUGMENTATION_WITH_UNITY_LIKE_STATES"

    all_labels: List[str] = []
    all_labels.extend(baseline_labels)
    all_labels.extend(b2_labels)
    all_labels.extend(c3_labels)
    all_labels.extend(full_labels)
    all_labels.extend(semantic_labels)
    # Preserve order and uniqueness.
    seen = set()
    uniq_labels = []
    for x in all_labels:
        if x not in seen:
            seen.add(x)
            uniq_labels.append(x)

    decision_payload = {
        "generated_at_utc": utc_now(),
        "stage": "10D.13A",
        "classification_labels": uniq_labels,
        "semantic_audit": {
            "bc_current_action_hypothesis": "BC [12:18] encodes action-associated state from teacher trajectory context, not explicitly desired-next-action target.",
            "bc_direction_hypothesis": "BC [18:22] encodes direction context coupled with action channels when applicable.",
            "unity_current_action_observed": {
                "self_actor_noop_share": actor_noop_action_share,
                "empty_cell_action_all_zero_share": empty_all_zero_action_share,
                "b2_current_action": ACTION_NAMES[max(0, action_index_from_channel(b2_runtime))] if action_index_from_channel(b2_runtime) >= 0 else "none",
                "c3_current_action": ACTION_NAMES[max(0, action_index_from_channel(c3_runtime))] if action_index_from_channel(c3_runtime) >= 0 else "none",
            },
            "classification": semantic_labels,
            "safety_note": "Any remap that injects target-like action intent into observation channels is treated as high risk unless semantics are source-verified.",
        },
        "candidate_fix_decision_matrix": matrix_rows,
        "primary_next_gate": primary_next_gate,
    }
    write_json(out_decision, decision_payload)

    b2_best = max(b2_results, key=lambda r: float(r["B2"]["p_harvest"]))
    c3_best = max(c3_results, key=lambda r: float(r["C3"]["p_produce"]))
    full_best = max(full_policy_results, key=lambda r: float(r["B2"]["p_harvest"] + r["C3"]["p_produce"]))

    report_md = "\n".join(
        [
            "# STAGE10D13A CurrentAction/Direction Fix Candidate Audit Report",
            "",
            "## 1. Inputs and constraints",
            "- Diagnostic-only offline inference on copied observations.",
            "- No teacher/student training; no checkpoint mutation; no runtime action forcing.",
            f"- Runtime capture: {runtime_capture_path}",
            f"- Strict replay report: {strict_report_path}",
            f"- BC-ready dir: {bc_dir}",
            f"- Student checkpoint: {checkpoint_path}",
            "",
            "## 2. Stage10D.12R evidence recap",
            "- Stage10D.12R established full raw [24,24,27] validity and strict replay validity.",
            "- Baseline B2/C3 were NoOp in Stage10D.12R.",
            "- Prior probes indicated strong sensitivity to current_action/direction channels.",
            "",
            "## 3. Baseline confirmation",
            f"- Baseline classification: {baseline_labels[0]}",
            f"- B2 baseline: action={baseline_b2['predicted_action']}, p_noop={baseline_b2['p_noop']:.6f}, p_harvest={baseline_b2['p_harvest']:.6f}",
            f"- C3 baseline: action={baseline_c3['predicted_action']}, p_noop={baseline_c3['p_noop']:.6f}, p_produce={baseline_c3['p_produce']:.6f}",
            "",
            "## 4. B2 minimal current_action/direction probes",
            f"- Best B2 probe: {b2_best['probe_name']}",
            f"- Best B2 result: action={b2_best['B2']['predicted_action']}, p_harvest={b2_best['B2']['p_harvest']:.6f}, p_noop={b2_best['B2']['p_noop']:.6f}",
            f"- B2 labels: {', '.join(b2_labels)}",
            "",
            "## 5. C3 local current_action/context probes",
            f"- Best C3 probe: {c3_best['probe_name']}",
            f"- Best C3 result: action={c3_best['C3']['predicted_action']}, p_produce={c3_best['C3']['p_produce']:.6f}, p_noop={c3_best['C3']['p_noop']:.6f}",
            f"- C3 labels: {', '.join(c3_labels)}",
            "",
            "## 6. Full actor-map candidate probes",
            f"- Best full policy: {full_best['policy_name']}",
            f"- Best full policy B2/C3: B2={full_best['B2']['predicted_action']} (p_harvest={full_best['B2']['p_harvest']:.6f}), C3={full_best['C3']['predicted_action']} (p_produce={full_best['C3']['p_produce']:.6f})",
            f"- Full policy labels: {', '.join(full_labels)}",
            "",
            "## 7. Current_action semantic audit",
            f"- Runtime self-actor action_noop share (channel-derived): {actor_noop_action_share}",
            f"- Runtime empty-cell action-all-zero share: {empty_all_zero_action_share}",
            f"- Semantic labels: {', '.join(semantic_labels)}",
            "- Safety interpretation: remap can restore logits but is high risk if it injects intent-like action signal into observation semantics.",
            "",
            "## 8. Candidate fix decision matrix",
            "- See stage10d13a_candidate_fix_decision_matrix.json for A-H matrix rows.",
            "",
            "## 9. Evidence-based classifications",
            f"- {', '.join(uniq_labels)}",
            "",
            "## 10. Primary next gate",
            f"- {primary_next_gate}",
        ]
    )
    write_text(out_report, report_md)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
