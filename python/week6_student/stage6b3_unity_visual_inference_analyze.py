#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

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


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def flat_to_xy(flat: int) -> tuple[int, int]:
    return int(flat % W), int(flat // W)


def label_for_flat(flat: int) -> str:
    x, y = flat_to_xy(flat)
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


def active_channels(vec: np.ndarray) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, value in enumerate(vec.tolist()):
        if abs(float(value)) > 1e-6:
            rows.append({"channel": i, "name": CHANNEL_NAMES[i], "value": float(value)})
    return rows


def softmax(v: np.ndarray) -> np.ndarray:
    return F.softmax(torch.from_numpy(v.astype(np.float64)), dim=-1).numpy()


def top3(logits: np.ndarray) -> list[dict[str, Any]]:
    probs = softmax(logits)
    order = np.argsort(-probs)
    return [
        {
            "class_id": int(i),
            "class_name": ACTION_NAMES[int(i)],
            "logit": float(logits[int(i)]),
            "probability": float(probs[int(i)]),
        }
        for i in order[:3]
    ]


def run_model(checkpoint: Path, obs_hwc: np.ndarray, device: str) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    model, metadata = load_student_transfer_checkpoint(checkpoint, device=device)
    with torch.no_grad():
        x = torch.from_numpy(obs_hwc[None]).to(dtype=torch.float32, device=torch.device(device))
        logits_t = model(x)
        logits = {k: v.detach().cpu().numpy() for k, v in logits_t.items()}
    return logits, metadata


def adapter_logit_parity(adapter: Mapping[str, Any], offline_action_logits: np.ndarray) -> dict[str, Any]:
    debug = adapter.get("stage10r_debug", {})
    rows = debug.get("global_cell_action_type_diagnostics", []) if isinstance(debug, Mapping) else []
    if not isinstance(rows, list) or not rows:
        return {"status": "missing_adapter_global_action_type_logits"}

    max_abs = 0.0
    max_prob_abs = 0.0
    mismatches = 0
    checked = 0
    examples: list[dict[str, Any]] = []
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


def branch_values(logits: Mapping[str, np.ndarray], flat: int) -> dict[str, int]:
    return {
        "action_type": int(np.argmax(logits["action_type_logits"][0, flat])),
        "move_dir": int(np.argmax(logits["move_dir_logits"][0, flat])),
        "harvest_dir": int(np.argmax(logits["harvest_dir_logits"][0, flat])),
        "return_dir": int(np.argmax(logits["return_dir_logits"][0, flat])),
        "produce_dir": int(np.argmax(logits["produce_dir_logits"][0, flat])),
        "produce_unit_type": int(np.argmax(logits["produce_unit_type_logits"][0, flat])),
        "attack_target_local": int(np.argmax(logits["attack_target_local_logits"][0, flat])),
    }


def focus_prediction(obs_hwc: np.ndarray, logits: Mapping[str, np.ndarray], flat: int) -> dict[str, Any]:
    vec = obs_hwc.reshape(H * W, C)[flat]
    action_logits = logits["action_type_logits"][0, flat].astype(np.float64)
    probs = softmax(action_logits)
    pred = int(np.argmax(action_logits))
    return {
        "flat_index": int(flat),
        "logical_label": label_for_flat(flat),
        "xy": list(flat_to_xy(flat)),
        "owner": decode_owner(vec),
        "unit": decode_unit(vec),
        "active_channels": active_channels(vec),
        "action_type_logits": [float(x) for x in action_logits.tolist()],
        "action_type_probabilities": [float(x) for x in probs.tolist()],
        "top3_action_type": top3(action_logits),
        "selected_action_type": pred,
        "selected_action_type_name": ACTION_NAMES[pred],
        "selected_branch_values": branch_values(logits, flat),
    }


def snapshot_focus(snapshot: Mapping[str, Any], flat: int) -> dict[str, Any]:
    rows = snapshot.get("actor_cells")
    if not isinstance(rows, list):
        return {"status": "missing_actor_cells"}
    for row in rows:
        if isinstance(row, Mapping) and int(row.get("flat_index", -1)) == flat:
            return {
                "status": "ok",
                "predicted_action_type": row.get("predicted_action_type"),
                "predicted_action_type_source": row.get("predicted_action_type_source"),
                "command_built": row.get("command_built"),
                "command_not_built_reason": row.get("command_not_built_reason"),
                "action_applier_reached": row.get("action_applier_reached"),
                "apply_command_reached": row.get("apply_command_reached"),
                "action_type_top3": row.get("action_type_top3"),
                "noop_probability": row.get("noop_probability"),
                "best_non_noop_probability": row.get("best_non_noop_probability"),
                "noop_margin": row.get("noop_margin"),
            }
    return {"status": "actor_not_found"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Stage6B3 Unity visual inference capture")
    parser.add_argument("--capture-json", type=Path, required=True)
    parser.add_argument("--adapter-json", type=Path, required=True)
    parser.add_argument("--snapshot-json", type=Path, required=True)
    parser.add_argument("--manifest-json", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = repo_root()
    capture_json = (root / args.capture_json).resolve()
    adapter_json = (root / args.adapter_json).resolve()
    snapshot_json = (root / args.snapshot_json).resolve()
    manifest_json = (root / args.manifest_json).resolve()
    checkpoint = (root / args.checkpoint).resolve()
    output_dir = (root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    capture = load_json(capture_json)
    adapter = load_json(adapter_json)
    snapshot = load_json(snapshot_json)
    manifest = load_json(manifest_json)
    obs_hwc = extract_obs_from_capture(capture)
    obs_flat = obs_hwc.reshape(H * W, C)
    actor_flats = np.asarray(
        [
            i
            for i, vec in enumerate(obs_flat)
            if decode_owner(vec) == "Player1" and decode_unit(vec) in {"Base", "Barracks", "Worker", "Light", "Heavy", "Ranged"}
        ],
        dtype=np.int32,
    )

    npz_path = output_dir / "stage6b3_unity_observation_step0001_export.npz"
    np.savez_compressed(
        npz_path,
        observation_hwc=obs_hwc,
        observation_flat=obs_flat,
        actor_flat_indices=actor_flats,
        channel_names=np.asarray(CHANNEL_NAMES),
    )

    logits, metadata = run_model(checkpoint, obs_hwc, args.device)
    parity = adapter_logit_parity(adapter, logits["action_type_logits"])

    focus_flats = {"B2": 25, "C3": 50}
    report = {
        "generated_at_utc": utc_now(),
        "inputs": {
            "capture_json": str(capture_json),
            "adapter_json": str(adapter_json),
            "snapshot_json": str(snapshot_json),
            "manifest_json": str(manifest_json),
            "checkpoint": str(checkpoint),
        },
        "checkpoint_binding": {
            "manifest_checkpoint": manifest.get("configured_checkpoint_relative_path"),
            "adapter_checkpoint": adapter.get("checkpoint_path"),
            "checkpoint_epoch": metadata.get("epoch"),
            "checkpoint_model_variant": metadata.get("model_variant"),
            "config": metadata.get("config", {}),
        },
        "scene": {
            "manifest_scene": manifest.get("scene"),
            "manifest_scene_name": manifest.get("scene_name"),
            "steps_completed": manifest.get("steps_completed"),
            "final_match_step": manifest.get("final_match_step"),
        },
        "observation_export": {
            "npz_path": str(npz_path),
            "shape_hwc": [int(x) for x in obs_hwc.shape],
            "shape_flat": [int(x) for x in obs_flat.shape],
            "actor_flat_indices": [int(x) for x in actor_flats.tolist()],
            "channel_names": list(CHANNEL_NAMES),
        },
        "offline_vs_unity_adapter_logits": parity,
        "focus_predictions": {
            label: {
                "offline": focus_prediction(obs_hwc, logits, flat),
                "unity_snapshot": snapshot_focus(snapshot, flat),
            }
            for label, flat in focus_flats.items()
        },
    }

    report_path = output_dir / "stage6b3_unity_visual_inference_analysis.json"
    write_json(report_path, report)
    print(json.dumps({
        "report": str(report_path),
        "observation_npz": str(npz_path),
        "parity": parity,
        "focus": {
            label: {
                "offline_action": row["offline"]["selected_action_type_name"],
                "snapshot_action": row["unity_snapshot"].get("predicted_action_type"),
                "command_built": row["unity_snapshot"].get("command_built"),
                "action_applier_reached": row["unity_snapshot"].get("action_applier_reached"),
            }
            for label, row in report["focus_predictions"].items()
        },
    }, indent=2))
    return 0 if parity.get("prediction_mismatches") == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
