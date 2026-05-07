#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import torch
import torch.nn.functional as F

from load_student_checkpoint import load_student_transfer_checkpoint


H = 24
W = 24
C = 27
ACTION_NAMES = ("NoOp", "Move", "Harvest", "Return", "Produce", "Attack")
CHANNEL_NAMES = (
    "hit_points",
    "resources",
    "owner_neutral",
    "owner_player1",
    "owner_player2",
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
)
SIGNATURE_CHANNELS = tuple(range(0, 26))
LOCAL_REPORT_CHANNELS = tuple(range(0, 27))


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def flat_to_xy(flat: int) -> Tuple[int, int]:
    return int(flat % W), int(flat // W)


def xy_to_flat(x: int, y: int) -> int:
    return int(y * W + x)


def label_for_xy(x: int, y: int) -> str:
    return f"{chr(ord('A') + x)}{y + 1}"


def extract_obs_from_capture(capture: Mapping[str, Any]) -> np.ndarray:
    cells = capture.get("cells")
    if not isinstance(cells, list) or len(cells) != H * W:
        raise RuntimeError(f"capture cells must be length {H * W}, got {0 if cells is None else len(cells)}")
    flat = np.zeros((H * W, C), dtype=np.float32)
    for i, cell in enumerate(cells):
        if not isinstance(cell, Mapping):
            raise RuntimeError(f"capture cell {i} is not an object")
        vec = cell.get("raw_channel_vector")
        if not isinstance(vec, list) or len(vec) != C:
            raise RuntimeError(f"capture cell {i} raw_channel_vector must be length {C}")
        flat[i] = np.asarray(vec, dtype=np.float32)
    if not np.isfinite(flat).all():
        raise RuntimeError("capture observation contains NaN/Inf")
    return flat.reshape(H, W, C)


def load_bc_split(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    data = np.load(path, allow_pickle=False)
    obs = data["observations"].astype(np.float32, copy=False)
    actions = data["actions"].astype(np.int16, copy=False)
    if obs.ndim != 3 or obs.shape[1:] != (H * W, C):
        raise RuntimeError(f"{path}: expected observations [N,576,27], got {obs.shape}")
    if actions.ndim != 3 or actions.shape[1:] != (H * W, 7):
        raise RuntimeError(f"{path}: expected actions [N,576,7], got {actions.shape}")
    return obs, actions


def decode_owner(vec: np.ndarray) -> str:
    idx = int(np.argmax(vec[2:5]))
    if float(vec[2 + idx]) <= 0.5:
        return "none"
    return ("Neutral", "Player1", "Player2")[idx]


def decode_unit(vec: np.ndarray) -> str:
    idx = int(np.argmax(vec[5:12]))
    if float(vec[5 + idx]) <= 0.5:
        return "none"
    return ("Resource", "Base", "Barracks", "Worker", "Light", "Heavy", "Ranged")[idx]


def decode_current_action(vec: np.ndarray) -> str:
    idx = int(np.argmax(vec[12:18]))
    if float(vec[12 + idx]) <= 0.5:
        return "none"
    return ACTION_NAMES[idx]


def decode_direction(vec: np.ndarray) -> str:
    idx = int(np.argmax(vec[18:22]))
    if float(vec[18 + idx]) <= 0.5:
        return "none"
    return ("north", "east", "south", "west")[idx]


def active_channels(vec: np.ndarray) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for i, value in enumerate(vec.tolist()):
        if abs(float(value)) > 1e-6:
            rows.append({"channel": i, "name": CHANNEL_NAMES[i], "value": float(value)})
    return rows


def cell_summary(flat: int, vec: np.ndarray, action_row: Optional[np.ndarray] = None) -> Dict[str, Any]:
    x, y = flat_to_xy(flat)
    out: Dict[str, Any] = {
        "flat_index": int(flat),
        "x": int(x),
        "y": int(y),
        "logical_label": label_for_xy(x, y),
        "owner": decode_owner(vec),
        "unit": decode_unit(vec),
        "hp": float(vec[0]),
        "resources": float(vec[1]),
        "current_action": decode_current_action(vec),
        "direction": decode_direction(vec),
        "attack_target_index": float(vec[26]),
        "active_channels": active_channels(vec),
    }
    if action_row is not None:
        action_type = int(action_row[0])
        out["target_action_type"] = action_type
        out["target_action_type_name"] = ACTION_NAMES[action_type] if 0 <= action_type < len(ACTION_NAMES) else str(action_type)
        out["target_is_noop"] = bool(action_type == 0)
        out["target_branches"] = [int(x) for x in action_row.tolist()]
    return out


def neighborhood(obs_hwc: np.ndarray, center_flat: int, radius: int) -> List[Dict[str, Any]]:
    cx, cy = flat_to_xy(center_flat)
    rows: List[Dict[str, Any]] = []
    for y in range(max(0, cy - radius), min(H, cy + radius + 1)):
        for x in range(max(0, cx - radius), min(W, cx + radius + 1)):
            flat = xy_to_flat(x, y)
            vec = obs_hwc[y, x]
            rows.append(cell_summary(flat, vec))
    return rows


def actor_cells(obs_hwc: np.ndarray) -> List[Dict[str, Any]]:
    flat = obs_hwc.reshape(H * W, C)
    rows: List[Dict[str, Any]] = []
    for i, vec in enumerate(flat):
        owner = decode_owner(vec)
        unit = decode_unit(vec)
        if owner == "Player1" and unit in {"Base", "Barracks", "Worker", "Light", "Heavy", "Ranged"} and float(vec[0]) > 0:
            row = cell_summary(i, vec)
            row["neighborhood_3x3"] = neighborhood(obs_hwc, i, 1)
            row["neighborhood_5x5"] = neighborhood(obs_hwc, i, 2)
            rows.append(row)
    rows.sort(key=lambda r: int(r["flat_index"]))
    return rows


def run_model(checkpoint: Path, obs_hwc: np.ndarray, device: str) -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
    model, metadata = load_student_transfer_checkpoint(checkpoint, device=device)
    with torch.no_grad():
        x = torch.from_numpy(obs_hwc[None]).to(dtype=torch.float32, device=torch.device(device))
        logits_t = model(x)
        logits = {k: v.detach().cpu().numpy() for k, v in logits_t.items()}
    return logits, metadata


def softmax(v: np.ndarray) -> np.ndarray:
    return F.softmax(torch.from_numpy(v.astype(np.float64)), dim=-1).numpy()


def action_type_diag(logits: np.ndarray, flat: int) -> Dict[str, Any]:
    values = logits[0, flat].astype(np.float64)
    probs = softmax(values)
    order = np.argsort(-probs)
    return {
        "flat_index": int(flat),
        "predicted_action_type": int(order[0]),
        "predicted_action_type_name": ACTION_NAMES[int(order[0])],
        "probabilities": [float(x) for x in probs.tolist()],
        "top3": [
            {
                "class_id": int(i),
                "class_name": ACTION_NAMES[int(i)],
                "logit": float(values[int(i)]),
                "probability": float(probs[int(i)]),
            }
            for i in order[:3]
        ],
    }


def adapter_logit_parity(adapter: Mapping[str, Any], offline_action_logits: np.ndarray) -> Dict[str, Any]:
    debug = adapter.get("stage10r_debug", {})
    rows = debug.get("global_cell_action_type_diagnostics", []) if isinstance(debug, Mapping) else []
    if not isinstance(rows, list) or not rows:
        return {"status": "missing_adapter_global_action_type_logits"}

    max_abs = 0.0
    max_prob_abs = 0.0
    mismatches = 0
    checked = 0
    examples: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        flat = int(row.get("flat_index", -1))
        unity_logits = np.asarray(row.get("action_type_logits", []), dtype=np.float64)
        unity_probs = np.asarray(row.get("action_type_probabilities", []), dtype=np.float64)
        if flat < 0 or flat >= H * W or unity_logits.shape != (6,):
            continue
        offline_logits = offline_action_logits[0, flat].astype(np.float64)
        offline_probs = softmax(offline_logits)
        logit_abs = float(np.max(np.abs(unity_logits - offline_logits)))
        prob_abs = float(np.max(np.abs(unity_probs - offline_probs))) if unity_probs.shape == (6,) else float("nan")
        max_abs = max(max_abs, logit_abs)
        if np.isfinite(prob_abs):
            max_prob_abs = max(max_prob_abs, prob_abs)
        unity_pred = int(row.get("predicted_action_type", -1))
        offline_pred = int(np.argmax(offline_logits))
        if unity_pred != offline_pred:
            mismatches += 1
            if len(examples) < 8:
                examples.append({"flat_index": flat, "unity_pred": unity_pred, "offline_pred": offline_pred})
        checked += 1
    return {
        "status": "ok" if checked == H * W and mismatches == 0 and max_abs < 1e-4 else "mismatch_or_partial",
        "checked_cells": int(checked),
        "prediction_mismatches": int(mismatches),
        "max_abs_action_type_logit_delta": float(max_abs),
        "max_abs_action_type_probability_delta": float(max_prob_abs),
        "mismatch_examples": examples,
    }


def bc_action_name(actions: np.ndarray, sample: int, flat: int) -> str:
    a = int(actions[sample, flat, 0])
    return ACTION_NAMES[a] if 0 <= a < len(ACTION_NAMES) else str(a)


def resource_and_actor_positions(obs_flat: np.ndarray) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for flat, vec in enumerate(obs_flat):
        unit = decode_unit(vec)
        owner = decode_owner(vec)
        if unit == "none":
            continue
        if unit == "Resource" or owner in {"Player1", "Player2"}:
            rows.append(cell_summary(flat, vec))
    return rows


def patch_bounds(center_flat: int, radius: int) -> List[int]:
    cx, cy = flat_to_xy(center_flat)
    flats: List[int] = []
    for y in range(max(0, cy - radius), min(H, cy + radius + 1)):
        for x in range(max(0, cx - radius), min(W, cx + radius + 1)):
            flats.append(xy_to_flat(x, y))
    return flats


def nearest_patch(
    split: str,
    obs: np.ndarray,
    actions: np.ndarray,
    unity_flat: np.ndarray,
    center_flat: int,
    unit_channel: int,
    radius: int,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    unit_mask = obs[:, :, unit_channel] > 0.5
    owner_mask = obs[:, :, 3] > 0.5
    hp_mask = obs[:, :, 0] > 0.0
    candidates = np.argwhere(unit_mask & owner_mask & hp_mask)
    if candidates.size == 0:
        return []

    unity_patch_flats = patch_bounds(center_flat, radius)
    center_x, center_y = flat_to_xy(center_flat)
    dists: List[Tuple[float, float, int, int]] = []
    unity_patch = unity_flat[unity_patch_flats][:, LOCAL_REPORT_CHANNELS]
    for sample, flat in candidates:
        sample = int(sample)
        flat = int(flat)
        x, y = flat_to_xy(flat)
        if x - center_x != 0 or y - center_y != 0:
            # Compare same relative neighborhood around candidate actor, not absolute map cells.
            candidate_flats = []
            ok = True
            for uf in unity_patch_flats:
                ux, uy = flat_to_xy(uf)
                cx = x + (ux - center_x)
                cy = y + (uy - center_y)
                if not (0 <= cx < W and 0 <= cy < H):
                    ok = False
                    break
                candidate_flats.append(xy_to_flat(cx, cy))
            if not ok:
                continue
        else:
            candidate_flats = unity_patch_flats
        cand_patch = obs[sample, candidate_flats][:, LOCAL_REPORT_CHANNELS]
        diff = cand_patch.astype(np.float32) - unity_patch.astype(np.float32)
        dists.append((float(np.sum(np.abs(diff))), float(np.linalg.norm(diff)), sample, flat))

    dists.sort(key=lambda x: (x[1], x[0]))
    out: List[Dict[str, Any]] = []
    for l1, l2, sample, flat in dists[:limit]:
        out.append(
            {
                "split": split,
                "sample_index": int(sample),
                "flat_index": int(flat),
                "x": flat_to_xy(flat)[0],
                "y": flat_to_xy(flat)[1],
                "logical_label": label_for_xy(*flat_to_xy(flat)),
                "local_patch_radius": int(radius),
                "patch_l1": float(l1),
                "patch_l2": float(l2),
                "target_at_candidate": cell_summary(flat, obs[sample, flat], actions[sample, flat]),
                "nearby_entities": resource_and_actor_positions(obs[sample])[:20],
            }
        )
    return out


def exact_signature_matches(
    split: str,
    obs: np.ndarray,
    actions: np.ndarray,
    unity_vec: np.ndarray,
    same_flat: int,
    unit_channel: int,
    limit: int = 5,
) -> Dict[str, Any]:
    sig = unity_vec[list(SIGNATURE_CHANNELS)]
    same_flat_mask = np.all(obs[:, same_flat, :][:, list(SIGNATURE_CHANNELS)] == sig[None, :], axis=1)
    any_cell_candidates = np.argwhere(
        np.all(obs[:, :, :][:, :, list(SIGNATURE_CHANNELS)] == sig[None, None, :], axis=2)
    )
    same_unit = np.argwhere((obs[:, :, unit_channel] > 0.5) & (obs[:, :, 3] > 0.5))
    examples: List[Dict[str, Any]] = []
    for sample, flat in any_cell_candidates[:limit]:
        examples.append(
            {
                "sample_index": int(sample),
                "flat_index": int(flat),
                "logical_label": label_for_xy(*flat_to_xy(int(flat))),
                "target": cell_summary(int(flat), obs[int(sample), int(flat)], actions[int(sample), int(flat)]),
            }
        )
    return {
        "split": split,
        "same_flat_exact_signature_count": int(np.sum(same_flat_mask)),
        "any_cell_exact_signature_count": int(any_cell_candidates.shape[0]),
        "same_owner_unit_candidate_count": int(same_unit.shape[0]),
        "examples": examples,
    }


def full_observation_nearest(
    split: str,
    obs: np.ndarray,
    actions: np.ndarray,
    unity_flat: np.ndarray,
    actor_flats: Sequence[int],
    limit: int = 3,
) -> List[Dict[str, Any]]:
    diff = obs.astype(np.float32) - unity_flat[None].astype(np.float32)
    l1 = np.sum(np.abs(diff), axis=(1, 2))
    l2 = np.linalg.norm(diff.reshape(diff.shape[0], -1), axis=1)
    order = np.argsort(l2)[:limit]
    rows: List[Dict[str, Any]] = []
    for sample in order:
        actor_targets = []
        for flat in actor_flats:
            actor_targets.append(cell_summary(int(flat), obs[int(sample), int(flat)], actions[int(sample), int(flat)]))
        rows.append(
            {
                "split": split,
                "sample_index": int(sample),
                "full_l1": float(l1[int(sample)]),
                "full_l2": float(l2[int(sample)]),
                "targets_at_unity_actor_flats": actor_targets,
                "entities": resource_and_actor_positions(obs[int(sample)])[:30],
            }
        )
    return rows


def summarize_actor_against_bc(
    split: str,
    obs: np.ndarray,
    actions: np.ndarray,
    unity_flat: np.ndarray,
    actor: Mapping[str, Any],
) -> Dict[str, Any]:
    flat = int(actor["flat_index"])
    unit = str(actor["unit"])
    unit_channel = {"Base": 6, "Barracks": 7, "Worker": 8, "Light": 9, "Heavy": 10, "Ranged": 11}.get(unit, 8)
    unity_vec = unity_flat[flat]
    same_flat_actions = np.bincount(actions[:, flat, 0].astype(np.int64), minlength=6)
    return {
        "actor": {
            "flat_index": flat,
            "logical_label": actor["logical_label"],
            "unit": unit,
            "unity_cell": cell_summary(flat, unity_vec),
        },
        "same_flat_target_action_distribution": {
            ACTION_NAMES[i]: int(same_flat_actions[i]) for i in range(len(ACTION_NAMES))
        },
        "exact_actor_cell_signature": exact_signature_matches(split, obs, actions, unity_vec, flat, unit_channel),
        "nearest_3x3": nearest_patch(split, obs, actions, unity_flat, flat, unit_channel, radius=1),
        "nearest_5x5": nearest_patch(split, obs, actions, unity_flat, flat, unit_channel, radius=2),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage6B2 Unity observation NoOp root-cause probe")
    parser.add_argument(
        "--capture-json",
        type=Path,
        default=Path("python/week6_student/tmp/stage6b2_source_valid_noopfix_visual_inference/stage10d12r_full_raw_runtime_observation_step0001.json"),
    )
    parser.add_argument(
        "--adapter-json",
        type=Path,
        default=Path("python/week6_student/tmp/stage6b2_source_valid_noopfix_visual_inference/stage6b2_source_valid_noopfix_player1_slot00_adapter.json"),
    )
    parser.add_argument(
        "--bc-dir",
        type=Path,
        default=Path("python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_source_valid_noopfix_bc_ready_20260506T225434Z"),
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path("python/week6_student/runs/Stage6B2_SourceValidNoOpFix/legacy032_v2_bc_source_valid_noop_fix_best.pt"),
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("python/week6_student/tmp/stage6b2_unity_observation_noop_root_cause_probe"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = repo_root()
    capture_json = (root / args.capture_json).resolve()
    adapter_json = (root / args.adapter_json).resolve()
    bc_dir = (root / args.bc_dir).resolve()
    checkpoint = (root / args.checkpoint).resolve()
    output_dir = (root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    capture = load_json(capture_json)
    adapter = load_json(adapter_json) if adapter_json.exists() else {}
    obs_hwc = extract_obs_from_capture(capture)
    obs_flat = obs_hwc.reshape(H * W, C)

    actors = actor_cells(obs_hwc)
    actor_flats = [int(a["flat_index"]) for a in actors]

    npz_path = output_dir / "stage6b2_unity_observation_step0001_export.npz"
    np.savez_compressed(
        npz_path,
        observation_hwc=obs_hwc,
        observation_flat=obs_flat,
        actor_flat_indices=np.asarray(actor_flats, dtype=np.int32),
        channel_names=np.asarray(CHANNEL_NAMES),
    )

    logits, metadata = run_model(checkpoint, obs_hwc, args.device)
    action_logits = logits["action_type_logits"]
    parity = adapter_logit_parity(adapter, action_logits)

    offline_actor_logits = [action_type_diag(action_logits, flat) for flat in actor_flats]

    train_obs, train_actions = load_bc_split(bc_dir / "bc_train.npz")
    val_obs, val_actions = load_bc_split(bc_dir / "bc_validation.npz")
    bc_actor_comparison: Dict[str, Any] = {"train": [], "validation": []}
    for actor in actors:
        bc_actor_comparison["train"].append(summarize_actor_against_bc("train", train_obs, train_actions, obs_flat, actor))
        bc_actor_comparison["validation"].append(summarize_actor_against_bc("validation", val_obs, val_actions, obs_flat, actor))

    full_nearest = {
        "train": full_observation_nearest("train", train_obs, train_actions, obs_flat, actor_flats),
        "validation": full_observation_nearest("validation", val_obs, val_actions, obs_flat, actor_flats),
    }

    scene_path = str(capture.get("scene") or "")
    if not scene_path:
        manifest_path = capture_json.parent / "stage6b2_source_valid_noopfix_run_manifest.json"
        if manifest_path.exists():
            scene_path = str(load_json(manifest_path).get("scene", ""))

    report = {
        "generated_at_utc": utc_now(),
        "inputs": {
            "capture_json": str(capture_json),
            "adapter_json": str(adapter_json),
            "bc_train": str(bc_dir / "bc_train.npz"),
            "bc_validation": str(bc_dir / "bc_validation.npz"),
            "checkpoint": str(checkpoint),
        },
        "scene_used": {
            "capture_scene": capture.get("scene"),
            "manifest_scene": scene_path,
            "capture_scene_name": capture.get("scene_name"),
        },
        "observation_export": {
            "npz_path": str(npz_path),
            "shape_hwc": [int(x) for x in obs_hwc.shape],
            "shape_flat": [int(x) for x in obs_flat.shape],
            "flatten_order": capture.get("flatten_order", "flat = y * W + x"),
            "channel_names": list(CHANNEL_NAMES),
        },
        "unity_actor_cells": actors,
        "offline_model": {
            "checkpoint_epoch": metadata.get("epoch"),
            "checkpoint_model_variant": metadata.get("model_variant"),
            "actor_action_type_logits": offline_actor_logits,
        },
        "offline_vs_unity_adapter_logits": parity,
        "bc_nearest_comparison": {
            "actor_cell_comparison": bc_actor_comparison,
            "full_observation_nearest": full_nearest,
        },
    }

    report_path = output_dir / "stage6b2_unity_observation_noop_root_cause_probe_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps({
        "report": str(report_path),
        "observation_npz": str(npz_path),
        "scene": scene_path,
        "actor_flats": actor_flats,
        "parity": parity,
        "offline_actor_top1": [
            {
                "flat_index": r["flat_index"],
                "predicted_action_type_name": r["predicted_action_type_name"],
                "top3": r["top3"],
            }
            for r in offline_actor_logits
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
