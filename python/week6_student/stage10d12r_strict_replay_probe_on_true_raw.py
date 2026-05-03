#!/usr/bin/env python3
"""
Stage10D.12R-Fix2: BC-reference strict probes on true raw runtime observation.

This script performs diagnostic-only probes:
- Loads true raw runtime tensor [24,24,27] from capture JSON.
- Loads Stage10D.8 student checkpoint strictly and runs real inference.
- Loads BC-ready dataset (train/validation NPZ) and finds nearest BC-positive
  references for B2 Worker+Harvest and C3 Base+Produce.
- Runs BC-reference forward and reverse probes (no training, no weight changes).
- Emits strict replay probe report consumed by orchestration.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

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

B2_FLAT = 25
B2_XY = (1, 1)
C3_FLAT = 50
C3_XY = (2, 2)

B2_GROUP_PROBES: List[Tuple[str, List[int]]] = [
    ("current_action_only", [12, 13, 14, 15, 16, 17]),
    ("direction_only", [18, 19, 20, 21]),
    ("scalars_only", [0, 1, 26]),
    ("current_action_plus_direction", [12, 13, 14, 15, 16, 17, 18, 19, 20, 21]),
    (
        "scalars_plus_current_action_plus_direction",
        [0, 1, 26, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21],
    ),
    ("owner_plus_unit_type", [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]),
    (
        "owner_plus_unit_type_plus_current_action_plus_direction",
        [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21],
    ),
    ("full_b2_cell", list(range(27))),
]

C3_RADIUS_PROBES: List[Tuple[str, int, bool]] = [
    ("cell_only", 0, True),
    ("patch_3x3", 1, True),
    ("patch_5x5", 2, True),
    ("patch_7x7", 3, True),
    ("neighbor_only_5x5", 2, False),
    ("center_only", 0, True),
]

C3_SEMANTIC_GROUP_PROBES: List[Tuple[str, Optional[List[int]], int, bool, str]] = [
    ("owner_only_all_cells_5x5", [2, 3, 4], 2, True, "patch"),
    ("unit_type_only_all_cells_5x5", [5, 6, 7, 8, 9, 10, 11], 2, True, "patch"),
    ("current_action_only_all_cells_5x5", [12, 13, 14, 15, 16, 17], 2, True, "patch"),
    ("direction_only_all_cells_5x5", [18, 19, 20, 21], 2, True, "patch"),
    ("scalar_only_all_cells_5x5", [0, 1, 26], 2, True, "patch"),
    ("owner_plus_unit_type", [2, 3, 4, 5, 6, 7, 8, 9, 10, 11], 2, True, "patch"),
    (
        "owner_plus_unit_type_plus_current_action_plus_direction",
        [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21],
        2,
        True,
        "patch",
    ),
    ("all_non_scalar_onehot_groups", list(range(2, 26)), 2, True, "patch"),
    ("all_groups_except_center_c3", None, 2, False, "patch"),
    ("only_neighbor_cells_excluding_center", None, 2, False, "patch"),
    ("only_center_c3", None, 0, True, "center"),
]

B2_PER_CHANNELS = [0, 1, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 26]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def flat_to_xy(flat_index: int) -> Tuple[int, int]:
    return flat_index % 24, flat_index // 24


def validate_captured_cells(captured: Mapping[str, Any]) -> np.ndarray:
    cells = captured.get("cells", [])
    if not isinstance(cells, list) or len(cells) != 576:
        raise RuntimeError(f"Captured JSON must contain 576 cells, got {len(cells)}")

    tensor = np.zeros((576, 27), dtype=np.float32)
    for i, cell in enumerate(cells):
        v = cell.get("raw_channel_vector", []) if isinstance(cell, Mapping) else []
        if not isinstance(v, list) or len(v) != 27:
            raise RuntimeError(f"Cell {i} raw_channel_vector must be length 27")
        tensor[i, :] = np.asarray(v, dtype=np.float32)
    if not np.isfinite(tensor).all():
        raise RuntimeError("Captured runtime tensor contains NaN/Inf")
    return tensor.reshape(24, 24, 27)


def load_model_strict(checkpoint_path: Path, device: torch.device) -> torch.nn.Module:
    model = build_day3_student_model().to(device=device)
    checkpoint = torch.load(checkpoint_path, map_location=device)
    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        state_dict = checkpoint["model_state_dict"]
    elif isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        state_dict = checkpoint["state_dict"]
    elif isinstance(checkpoint, dict):
        state_dict = checkpoint
    else:
        state_dict = checkpoint
    model.load_state_dict(state_dict, strict=True)
    model.eval()
    return model


def run_model_probs(model: torch.nn.Module, obs_map: np.ndarray, device: torch.device) -> np.ndarray:
    with torch.no_grad():
        x = torch.from_numpy(obs_map[None, ...]).to(device=device, dtype=torch.float32)
        logits = model(x)["action_type_logits"]
        probs = F.softmax(logits, dim=-1)[0].detach().cpu().numpy()
    return probs


def eval_cell_probs(action_probs: np.ndarray, flat_index: int) -> Dict[str, Any]:
    p = action_probs[flat_index]
    predicted_idx = int(np.argmax(p))
    return {
        "flat_index": int(flat_index),
        "predicted_action": ACTION_NAMES[predicted_idx],
        "p_noop": float(p[0]),
        "p_move": float(p[1]),
        "p_harvest": float(p[2]),
        "p_return": float(p[3]),
        "p_produce": float(p[4]),
        "p_attack": float(p[5]),
        "full_probabilities": [float(x) for x in p.tolist()],
    }


def validate_bc_npz_shapes(npz_path: Path) -> Tuple[np.ndarray, np.ndarray]:
    payload = np.load(npz_path, allow_pickle=False)
    if "observations" not in payload or "actions" not in payload:
        raise RuntimeError(f"{npz_path} missing observations/actions keys")
    observations = payload["observations"]
    actions = payload["actions"]
    if observations.ndim != 3 or observations.shape[1:] != (576, 27):
        raise RuntimeError(f"{npz_path}: observations shape expected [N,576,27], got {observations.shape}")
    if actions.ndim != 3 or actions.shape[1:] != (576, 7):
        raise RuntimeError(f"{npz_path}: actions shape expected [N,576,7], got {actions.shape}")
    return observations, actions


def find_nearest_reference(
    split_name: str,
    observations: np.ndarray,
    actions: np.ndarray,
    runtime_vec: np.ndarray,
    target_action: int,
    target_unit_channel: int,
) -> Optional[Dict[str, Any]]:
    action_type_branch = actions[:, :, 0]
    mask_action = action_type_branch == target_action
    mask_unit = observations[:, :, target_unit_channel] > 0.5
    mask_base = mask_action & mask_unit
    if not np.any(mask_base):
        return None

    mask_friendly = observations[:, :, 3] > 0.5
    friendly_mask = mask_base & mask_friendly

    candidates = np.argwhere(friendly_mask if np.any(friendly_mask) else mask_base)
    sample_indices = candidates[:, 0]
    flat_indices = candidates[:, 1]
    candidate_vectors = observations[sample_indices, flat_indices, :]
    dists = np.linalg.norm(candidate_vectors - runtime_vec[None, :], axis=1)
    best_idx = int(np.argmin(dists))

    sample_index = int(sample_indices[best_idx])
    flat_index = int(flat_indices[best_idx])
    selected_obs_row = observations[sample_index]
    selected_action_row = actions[sample_index]
    if not np.isfinite(selected_obs_row).all() or not np.isfinite(selected_action_row).all():
        raise RuntimeError(
            f"Selected {split_name} reference row contains NaN/Inf: sample_index={sample_index}"
        )

    x, y = flat_to_xy(flat_index)
    return {
        "split": split_name,
        "sample_index": sample_index,
        "flat_index": flat_index,
        "x": int(x),
        "y": int(y),
        "l2": float(dists[best_idx]),
        "obs_map": selected_obs_row.reshape(24, 24, 27).astype(np.float32, copy=True),
        "cell_vector": selected_obs_row[flat_index].astype(np.float32, copy=True),
    }


def choose_nearest_reference(
    references: List[Optional[Dict[str, Any]]],
    l2_field_name: str,
) -> Dict[str, Any]:
    valid = [r for r in references if r is not None]
    if not valid:
        raise RuntimeError("No candidate BC-positive reference found for strict probe")
    best = min(valid, key=lambda r: float(r["l2"]))
    best[l2_field_name] = best.pop("l2")
    return best


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


def probe_payload(
    probe_name: str,
    patched_channels: Sequence[int],
    current: Dict[str, Any],
    baseline: Dict[str, Any],
    action_name: str,
) -> Dict[str, Any]:
    return {
        "probe_name": probe_name,
        "patched_channels": [int(c) for c in patched_channels],
        "channel_names": [CHANNEL_NAMES[int(c)] for c in patched_channels],
        "predicted_action": current["predicted_action"],
        "p_noop": current["p_noop"],
        "p_move": current["p_move"],
        "p_harvest": current["p_harvest"],
        "p_return": current["p_return"],
        "p_produce": current["p_produce"],
        "p_attack": current["p_attack"],
        "full_probabilities": current["full_probabilities"],
        "delta_p_noop": float(current["p_noop"] - baseline["p_noop"]),
        f"delta_p_{action_name}": float(current[f"p_{action_name}"] - baseline[f"p_{action_name}"]),
        f"{action_name}_top1": bool(current["predicted_action"] == action_name),
        "p_noop_lt_0_5": bool(current["p_noop"] < 0.5),
        f"p_{action_name}_gt_0_5": bool(current[f"p_{action_name}"] > 0.5),
    }


def decode_owner(vec: np.ndarray) -> str:
    slice_ = vec[2:5]
    idx = int(np.argmax(slice_))
    if float(slice_[idx]) <= 0.5:
        return "none"
    return ["neutral", "self", "enemy"][idx]


def decode_unit(vec: np.ndarray) -> str:
    slice_ = vec[5:12]
    idx = int(np.argmax(slice_))
    if float(slice_[idx]) <= 0.5:
        return "none"
    return ["resource", "base", "barracks", "worker", "light", "heavy", "ranged"][idx]


def decode_action(vec: np.ndarray) -> str:
    slice_ = vec[12:18]
    idx = int(np.argmax(slice_))
    if float(slice_[idx]) <= 0.5:
        return "none"
    return ACTION_NAMES[idx]


def summarize_scene(obs_map: np.ndarray, b2_xy: Tuple[int, int], c3_xy: Tuple[int, int]) -> Dict[str, Any]:
    owner_distribution: Dict[str, int] = {"neutral": 0, "self": 0, "enemy": 0, "none": 0}
    unit_distribution: Dict[str, int] = {
        "resource": 0,
        "base": 0,
        "barracks": 0,
        "worker": 0,
        "light": 0,
        "heavy": 0,
        "ranged": 0,
        "none": 0,
    }
    action_distribution: Dict[str, int] = {
        "noop": 0,
        "move": 0,
        "harvest": 0,
        "return": 0,
        "produce": 0,
        "attack": 0,
        "none": 0,
    }

    friendly_actor_count = 0
    enemy_actor_count = 0
    workers_count = 0
    bases_count = 0
    barracks_count = 0
    resources_count = 0
    empty_cells_count = 0

    actor_units = {"base", "barracks", "worker", "light", "heavy", "ranged"}
    b2_decoded: Dict[str, str] = {}
    c3_decoded: Dict[str, str] = {}

    flat = obs_map.reshape(576, 27)
    for i in range(576):
        vec = flat[i]
        owner = decode_owner(vec)
        unit = decode_unit(vec)
        action = decode_action(vec)

        owner_distribution[owner] += 1
        unit_distribution[unit] += 1
        action_distribution[action] += 1

        if owner == "self" and unit in actor_units:
            friendly_actor_count += 1
        if owner == "enemy" and unit in actor_units:
            enemy_actor_count += 1
        if unit == "worker":
            workers_count += 1
        if unit == "base":
            bases_count += 1
        if unit == "barracks":
            barracks_count += 1
        if unit == "resource":
            resources_count += 1
        if unit == "none":
            empty_cells_count += 1

        x, y = flat_to_xy(i)
        decoded = {"owner": owner, "unit": unit, "action": action}
        if (x, y) == b2_xy:
            b2_decoded = decoded
        if (x, y) == c3_xy:
            c3_decoded = decoded

    return {
        "owner_distribution": owner_distribution,
        "unit_distribution": unit_distribution,
        "action_distribution": action_distribution,
        "friendly_actor_count": int(friendly_actor_count),
        "enemy_actor_count": int(enemy_actor_count),
        "workers_count": int(workers_count),
        "bases_count": int(bases_count),
        "barracks_count": int(barracks_count),
        "resources_count": int(resources_count),
        "empty_cells_count": int(empty_cells_count),
        "B2_decoded": b2_decoded,
        "C3_decoded": c3_decoded,
    }


def choose_recommended_gate(
    probes_completed: bool,
    inconclusive: bool,
    b2_confirmed: bool,
    c3_confirmed: bool,
    scene_ood_confirmed: bool,
    scene_ood_not_confirmed: bool,
    top_channels: List[Dict[str, Any]],
) -> str:
    if not probes_completed or inconclusive:
        return "GO_FOR_STAGE10D12R_STRICT_PROBE_RERUN"

    minimal_patch_clear = False
    if top_channels:
        lead = top_channels[0]
        name = str(lead.get("channel_name", ""))
        score = float(lead.get("combined_score", 0.0))
        minimal_patch_clear = score > 0.80 and name in {
            "action_harvest",
            "action_noop",
            "dir_north",
            "dir_east",
            "dir_south",
            "dir_west",
        }

    if b2_confirmed and minimal_patch_clear and not c3_confirmed:
        return "GO_FOR_STAGE10D13_MINIMAL_RUNTIME_OBSERVATION_FIX"
    if b2_confirmed:
        return "GO_FOR_UNITY_OBSERVATION_CHANNEL_REMAP_FIX"
    if c3_confirmed and scene_ood_confirmed:
        return "GO_FOR_UNITY_SCENE_DISTRIBUTION_ALIGNMENT"
    if c3_confirmed and scene_ood_not_confirmed:
        return "GO_FOR_TARGETED_BC_AUGMENTATION_WITH_UNITY_LIKE_STATES"
    return "GO_FOR_STAGE10D12R_STRICT_PROBE_RERUN"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage10D.12R strict BC-reference replay probe")
    parser.add_argument(
        "--capture-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d12r_full_raw_runtime_observation_step0001.json"),
    )
    parser.add_argument(
        "--bc-ready-dir",
        type=Path,
        default=Path(
            "python/week6_student/bc_ready/"
            "legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z"
        ),
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path(
            "python/week6_student/runs/legacy032_v2_semantic_bc_stage10d8_20260503T093718Z/"
            "student_bc_semantic_best.pt"
        ),
    )
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d12r_strict_replay_probe_results.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = repo_root()

    capture_json = (root / args.capture_json).resolve()
    bc_ready_dir = (root / args.bc_ready_dir).resolve()
    checkpoint_path = (root / args.checkpoint).resolve()
    output_path = (root / args.output).resolve()

    train_npz = bc_ready_dir / "bc_train.npz"
    val_npz = bc_ready_dir / "bc_validation.npz"

    for req in (capture_json, checkpoint_path, train_npz, val_npz):
        if not req.exists():
            print(f"FATAL: Required input missing: {req}")
            return 1

    print("=" * 72)
    print("Stage10D.12R-Fix2 strict BC-reference replay probes")
    print("=" * 72)

    captured = load_json(capture_json)
    runtime_map = validate_captured_cells(captured)
    runtime_vec_b2 = runtime_map[B2_XY[1], B2_XY[0], :].copy()
    runtime_vec_c3 = runtime_map[C3_XY[1], C3_XY[0], :].copy()

    train_obs, train_actions = validate_bc_npz_shapes(train_npz)
    val_obs, val_actions = validate_bc_npz_shapes(val_npz)

    b2_candidates = [
        find_nearest_reference("train", train_obs, train_actions, runtime_vec_b2, target_action=2, target_unit_channel=8),
        find_nearest_reference("validation", val_obs, val_actions, runtime_vec_b2, target_action=2, target_unit_channel=8),
    ]
    c3_candidates = [
        find_nearest_reference("train", train_obs, train_actions, runtime_vec_c3, target_action=4, target_unit_channel=6),
        find_nearest_reference("validation", val_obs, val_actions, runtime_vec_c3, target_action=4, target_unit_channel=6),
    ]

    b2_ref = choose_nearest_reference(b2_candidates, "l2_to_runtime_b2")
    c3_ref = choose_nearest_reference(c3_candidates, "l2_to_runtime_c3")

    device = torch.device(args.device)
    model = load_model_strict(checkpoint_path, device=device)

    runtime_probs = run_model_probs(model, runtime_map, device)
    baseline_b2 = eval_cell_probs(runtime_probs, B2_FLAT)
    baseline_c3 = eval_cell_probs(runtime_probs, C3_FLAT)
    baseline_results = {"B2": baseline_b2, "C3": baseline_c3}

    b2_ref_probs = run_model_probs(model, b2_ref["obs_map"], device)
    b2_ref_cell = eval_cell_probs(b2_ref_probs, int(b2_ref["flat_index"]))
    b2_ref["reference_prediction"] = {
        "predicted_action": b2_ref_cell["predicted_action"],
        "p_harvest": b2_ref_cell["p_harvest"],
        "p_noop": b2_ref_cell["p_noop"],
    }

    c3_ref_probs = run_model_probs(model, c3_ref["obs_map"], device)
    c3_ref_cell = eval_cell_probs(c3_ref_probs, int(c3_ref["flat_index"]))
    c3_ref["reference_prediction"] = {
        "predicted_action": c3_ref_cell["predicted_action"],
        "p_produce": c3_ref_cell["p_produce"],
        "p_noop": c3_ref_cell["p_noop"],
    }

    # B2 forward group probes (runtime <- BC reference vector at B2).
    b2_group_probe_results: List[Dict[str, Any]] = []
    for probe_name, channels in B2_GROUP_PROBES:
        obs = runtime_map.copy()
        obs[B2_XY[1], B2_XY[0], channels] = b2_ref["cell_vector"][channels]
        probs = run_model_probs(model, obs, device)
        current = eval_cell_probs(probs, B2_FLAT)
        b2_group_probe_results.append(
            probe_payload(
                probe_name=probe_name,
                patched_channels=channels,
                current=current,
                baseline=baseline_b2,
                action_name="harvest",
            )
        )

    # B2 reverse ablation (BC reference <- runtime B2 groups at reference flat).
    b2_reverse_group_probe_results: List[Dict[str, Any]] = []
    ref_b2_xy = (int(b2_ref["x"]), int(b2_ref["y"]))
    ref_b2_baseline = b2_ref_cell
    for probe_name, channels in B2_GROUP_PROBES:
        obs = b2_ref["obs_map"].copy()
        obs[ref_b2_xy[1], ref_b2_xy[0], channels] = runtime_vec_b2[channels]
        probs = run_model_probs(model, obs, device)
        current = eval_cell_probs(probs, int(b2_ref["flat_index"]))
        b2_reverse_group_probe_results.append(
            {
                "probe_name": probe_name,
                "patched_channels": [int(c) for c in channels],
                "channel_names": [CHANNEL_NAMES[int(c)] for c in channels],
                "reference_flat_index": int(b2_ref["flat_index"]),
                "predicted_action": current["predicted_action"],
                "p_noop": current["p_noop"],
                "p_harvest": current["p_harvest"],
                "harvest_destroyed": bool(current["predicted_action"] != "harvest"),
                "delta_from_bc_reference_baseline": {
                    "delta_p_noop": float(current["p_noop"] - ref_b2_baseline["p_noop"]),
                    "delta_p_harvest": float(current["p_harvest"] - ref_b2_baseline["p_harvest"]),
                },
            }
        )

    # C3 radius probes (runtime <- BC reference map around source base location into runtime C3).
    c3_radius_probe_results: List[Dict[str, Any]] = []
    src_c3_xy = (int(c3_ref["x"]), int(c3_ref["y"]))
    for probe_name, radius, include_center in C3_RADIUS_PROBES:
        patched = apply_patch_from_source(
            target_map=runtime_map,
            target_xy=C3_XY,
            source_map=c3_ref["obs_map"],
            source_xy=src_c3_xy,
            radius=radius,
            channels=None,
            include_center=include_center,
        )
        probs = run_model_probs(model, patched, device)
        current = eval_cell_probs(probs, C3_FLAT)
        patched_channels = list(range(27))
        item = probe_payload(
            probe_name=probe_name,
            patched_channels=patched_channels,
            current=current,
            baseline=baseline_c3,
            action_name="produce",
        )
        item["radius"] = int(radius)
        item["include_center"] = bool(include_center)
        c3_radius_probe_results.append(item)

    # C3 semantic group probes within 5x5.
    c3_semantic_group_probe_results: List[Dict[str, Any]] = []
    for probe_name, channels, radius, include_center, mode in C3_SEMANTIC_GROUP_PROBES:
        if mode == "center":
            patched = runtime_map.copy()
            src_vec = c3_ref["obs_map"][src_c3_xy[1], src_c3_xy[0], :]
            if channels is None:
                patched[C3_XY[1], C3_XY[0], :] = src_vec
                patched_channels = list(range(27))
            else:
                patched[C3_XY[1], C3_XY[0], channels] = src_vec[channels]
                patched_channels = [int(c) for c in channels]
        else:
            patched = apply_patch_from_source(
                target_map=runtime_map,
                target_xy=C3_XY,
                source_map=c3_ref["obs_map"],
                source_xy=src_c3_xy,
                radius=radius,
                channels=channels,
                include_center=include_center,
            )
            patched_channels = list(range(27)) if channels is None else [int(c) for c in channels]

        probs = run_model_probs(model, patched, device)
        current = eval_cell_probs(probs, C3_FLAT)
        item = probe_payload(
            probe_name=probe_name,
            patched_channels=patched_channels,
            current=current,
            baseline=baseline_c3,
            action_name="produce",
        )
        item["radius"] = int(radius)
        item["include_center"] = bool(include_center)
        c3_semantic_group_probe_results.append(item)

    # B2 per-channel probes.
    b2_per_channel_probe_results: List[Dict[str, Any]] = []
    for ch in B2_PER_CHANNELS:
        obs_fwd = runtime_map.copy()
        obs_fwd[B2_XY[1], B2_XY[0], ch] = b2_ref["cell_vector"][ch]
        probs_fwd = run_model_probs(model, obs_fwd, device)
        fwd = eval_cell_probs(probs_fwd, B2_FLAT)

        obs_rev = b2_ref["obs_map"].copy()
        obs_rev[ref_b2_xy[1], ref_b2_xy[0], ch] = runtime_vec_b2[ch]
        probs_rev = run_model_probs(model, obs_rev, device)
        rev = eval_cell_probs(probs_rev, int(b2_ref["flat_index"]))

        forward_harvest_gain = float(fwd["p_harvest"] - baseline_b2["p_harvest"])
        forward_noop_drop = float(baseline_b2["p_noop"] - fwd["p_noop"])
        reverse_harvest_drop = float(ref_b2_baseline["p_harvest"] - rev["p_harvest"])
        reverse_noop_gain = float(rev["p_noop"] - ref_b2_baseline["p_noop"])
        combined_score = (
            forward_harvest_gain + forward_noop_drop + reverse_harvest_drop + reverse_noop_gain
        )

        b2_per_channel_probe_results.append(
            {
                "channel_index": int(ch),
                "channel_name": CHANNEL_NAMES[ch],
                "forward": {
                    "predicted_action": fwd["predicted_action"],
                    "p_noop": fwd["p_noop"],
                    "p_harvest": fwd["p_harvest"],
                    "delta_p_noop": float(fwd["p_noop"] - baseline_b2["p_noop"]),
                    "delta_p_harvest": float(fwd["p_harvest"] - baseline_b2["p_harvest"]),
                    "full_probabilities": fwd["full_probabilities"],
                },
                "reverse": {
                    "predicted_action": rev["predicted_action"],
                    "p_noop": rev["p_noop"],
                    "p_harvest": rev["p_harvest"],
                    "delta_p_noop": float(rev["p_noop"] - ref_b2_baseline["p_noop"]),
                    "delta_p_harvest": float(rev["p_harvest"] - ref_b2_baseline["p_harvest"]),
                    "full_probabilities": rev["full_probabilities"],
                },
                "combined_score": float(combined_score),
                "combined_terms": {
                    "forward_harvest_gain": float(forward_harvest_gain),
                    "forward_noop_drop": float(forward_noop_drop),
                    "reverse_harvest_drop": float(reverse_harvest_drop),
                    "reverse_noop_gain": float(reverse_noop_gain),
                },
            }
        )

    b2_per_channel_probe_results = sorted(
        b2_per_channel_probe_results,
        key=lambda item: float(item["combined_score"]),
        reverse=True,
    )

    top_channel_ranking = [
        {
            "channel_index": int(item["channel_index"]),
            "channel_name": item["channel_name"],
            "combined_score": float(item["combined_score"]),
        }
        for item in b2_per_channel_probe_results
    ]

    # Scene summary and OOD check.
    runtime_scene_summary = summarize_scene(runtime_map, B2_XY, C3_XY)
    bc_reference_scene_summary = summarize_scene(c3_ref["obs_map"], (int(b2_ref["x"]), int(b2_ref["y"])), src_c3_xy)

    scene_deltas = {
        "enemy_actor_count_delta": int(
            abs(runtime_scene_summary["enemy_actor_count"] - bc_reference_scene_summary["enemy_actor_count"])
        ),
        "workers_count_delta": int(
            abs(runtime_scene_summary["workers_count"] - bc_reference_scene_summary["workers_count"])
        ),
        "empty_cells_count_delta": int(
            abs(runtime_scene_summary["empty_cells_count"] - bc_reference_scene_summary["empty_cells_count"])
        ),
    }
    scene_ood_confirmed = bool(
        scene_deltas["enemy_actor_count_delta"] > 2
        or scene_deltas["workers_count_delta"] > 2
        or scene_deltas["empty_cells_count_delta"] > 5
    )

    # Strict classifications.
    b2_baseline_noop = baseline_b2["predicted_action"] == "noop"
    c3_baseline_noop = baseline_c3["predicted_action"] == "noop"

    b2_by_name = {r["probe_name"]: r for r in b2_group_probe_results}
    b2_confirmed = bool(
        (
            b2_by_name.get("current_action_plus_direction", {}).get("harvest_top1")
            and b2_by_name.get("current_action_plus_direction", {}).get("p_harvest_gt_0_5")
        )
        or (
            b2_by_name.get("scalars_plus_current_action_plus_direction", {}).get("harvest_top1")
            and b2_by_name.get("scalars_plus_current_action_plus_direction", {}).get("p_harvest_gt_0_5")
        )
        or b2_by_name.get("full_b2_cell", {}).get("harvest_top1")
    )

    c3_by_name = {r["probe_name"]: r for r in c3_radius_probe_results}
    cell_only_no_produce = not bool(c3_by_name.get("cell_only", {}).get("produce_top1"))
    any_neighbor_context_restore = bool(
        c3_by_name.get("patch_3x3", {}).get("produce_top1")
        or c3_by_name.get("patch_5x5", {}).get("produce_top1")
        or c3_by_name.get("neighbor_only_5x5", {}).get("produce_top1")
    )
    c3_confirmed = bool(cell_only_no_produce and any_neighbor_context_restore)

    conflicting_evidence = False
    reverse_full_b2 = next((r for r in b2_reverse_group_probe_results if r["probe_name"] == "full_b2_cell"), None)
    if b2_confirmed and reverse_full_b2 and not reverse_full_b2.get("harvest_destroyed", False):
        conflicting_evidence = True

    classifications: List[str] = [
        "REAL_STRICT_REPLAY_COMPLETED",
        "REAL_MODEL_CHECKPOINT_LOADED",
        "BC_REFERENCE_PATCH_PROBES_COMPLETED",
    ]
    classifications.append(
        "STRICT_B2_BASELINE_NOOP_CONFIRMED" if b2_baseline_noop else "STRICT_B2_BASELINE_NOOP_NOT_CONFIRMED"
    )
    classifications.append(
        "STRICT_C3_BASELINE_NOOP_CONFIRMED" if c3_baseline_noop else "STRICT_C3_BASELINE_NOOP_NOT_CONFIRMED"
    )
    classifications.append(
        "STRICT_B2_CHANNEL_MISMATCH_CONFIRMED"
        if b2_confirmed
        else "STRICT_B2_CHANNEL_MISMATCH_NOT_CONFIRMED"
    )
    classifications.append(
        "STRICT_C3_LOCAL_CONTEXT_REQUIRED_CONFIRMED"
        if c3_confirmed
        else "STRICT_C3_LOCAL_CONTEXT_NOT_CONFIRMED"
    )
    classifications.append(
        "STRICT_SCENE_OOD_CONFIRMED" if scene_ood_confirmed else "STRICT_SCENE_OOD_NOT_CONFIRMED"
    )
    if conflicting_evidence:
        classifications.append("STRICT_PROBES_INCONCLUSIVE")

    recommended_next_gate = choose_recommended_gate(
        probes_completed=True,
        inconclusive=conflicting_evidence,
        b2_confirmed=b2_confirmed,
        c3_confirmed=c3_confirmed,
        scene_ood_confirmed=scene_ood_confirmed,
        scene_ood_not_confirmed=not scene_ood_confirmed,
        top_channels=top_channel_ranking,
    )

    report = {
        "generated_at_utc": utc_now(),
        "stage": "10D.12R-Fix2",
        "model_checkpoint_loaded": True,
        "inference_status": "real_model_execution_completed",
        "checkpoint_path": str(checkpoint_path),
        "capture_json_path": str(capture_json),
        "bc_ready_dir": str(bc_ready_dir),
        "tensor_shape": [1, 24, 24, 27],
        "baseline_inference": baseline_results,
        "b2_reference": {
            "split": b2_ref["split"],
            "sample_index": int(b2_ref["sample_index"]),
            "flat_index": int(b2_ref["flat_index"]),
            "x": int(b2_ref["x"]),
            "y": int(b2_ref["y"]),
            "l2_to_runtime_b2": float(b2_ref["l2_to_runtime_b2"]),
            "reference_prediction": b2_ref["reference_prediction"],
        },
        "c3_reference": {
            "split": c3_ref["split"],
            "sample_index": int(c3_ref["sample_index"]),
            "flat_index": int(c3_ref["flat_index"]),
            "x": int(c3_ref["x"]),
            "y": int(c3_ref["y"]),
            "l2_to_runtime_c3": float(c3_ref["l2_to_runtime_c3"]),
            "reference_prediction": c3_ref["reference_prediction"],
        },
        "b2_group_probe_results": b2_group_probe_results,
        "b2_reverse_group_probe_results": b2_reverse_group_probe_results,
        "b2_per_channel_probe_results": b2_per_channel_probe_results,
        "b2_per_channel_top_ranking": top_channel_ranking,
        "c3_radius_probe_results": c3_radius_probe_results,
        "c3_semantic_group_probe_results": c3_semantic_group_probe_results,
        "true_raw_scene_summary": runtime_scene_summary,
        "bc_reference_scene_summary": bc_reference_scene_summary,
        "scene_ood_deltas": scene_deltas,
        "classifications": classifications,
        "recommended_next_gate_candidate": recommended_next_gate,
        # Legacy aliases preserved for compatibility with existing readers.
        "b2_group_probes": b2_group_probe_results,
        "c3_radius_probes": c3_radius_probe_results,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")

    print("=" * 72)
    print(f"Wrote strict replay probe report: {output_path}")
    print(f"B2 baseline: {baseline_b2['predicted_action']} | C3 baseline: {baseline_c3['predicted_action']}")
    print(f"Recommended next gate: {recommended_next_gate}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
