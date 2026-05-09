from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

import numpy as np
import torch

from load_student_checkpoint import load_student_transfer_checkpoint
from student_branch_contract import (
    ACTION_CONTRACT_VERSION,
    BRANCH_LOGITS_KEYS,
    BRANCH_SPECS,
    BRANCH_ORDER,
    EXPECTED_BC_BRANCH_SIZES,
    validate_student_branch_contract_consistency,
)

EXPECTED_OBS_SHAPE: tuple[int, int, int] = (24, 24, 27)
EXPECTED_OBS_DTYPE = np.float32
TOTAL_CELLS: int = 24 * 24
BRANCH_OFFSETS: tuple[int, ...] = (0, 6, 10, 14, 18, 22, 26)
ACTION_FLAT_SIZE_PER_CELL: int = int(sum(EXPECTED_BC_BRANCH_SIZES))
TOTAL_ACTION_FLAT_SIZE: int = TOTAL_CELLS * ACTION_FLAT_SIZE_PER_CELL
ACTION_TYPE_NAMES: tuple[str, ...] = ("NoOp", "Move", "Harvest", "Return", "Produce", "Attack")
PRODUCE_UNIT_TYPE_NAMES: tuple[str, ...] = ("Resource", "Base", "Barracks", "Worker", "Light", "Heavy", "Ranged")
OBS_CHANNEL_NAMES: tuple[str, ...] = (
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Week 6 Day 4 student inference adapter: "
            "Unity observation -> student checkpoint -> canonical action flat"
        )
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        required=True,
        help="Path to student_bc_transfer_best.pt",
    )
    parser.add_argument(
        "--observation-bin",
        type=Path,
        required=True,
        help="Path to raw float32 observation buffer with 24*24*27 values",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        required=True,
        help="Path to write dry-run adapter output JSON",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Torch device for inference (default: cpu)",
    )
    parser.add_argument(
        "--controlled-player",
        type=str,
        default="Player1",
        help="Controlled player for owner-relative diagnostics (Player1 or Player2)",
    )
    return parser.parse_args()


def _to_row_col(flat_index: int) -> tuple[int, int]:
    row = int(flat_index // EXPECTED_OBS_SHAPE[1])
    col = int(flat_index % EXPECTED_OBS_SHAPE[1])
    return row, col


def _logical_cell_label(row: int, col: int) -> str:
    return f"{chr(ord('A') + col)}{row + 1}"


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits)
    exp_values = np.exp(shifted)
    total = float(np.sum(exp_values))
    if total <= 0.0:
        return np.zeros_like(logits, dtype=np.float64)
    return exp_values / total


def _argmax(values: np.ndarray) -> int:
    return int(np.argmax(values).item())


def _owner_channel_for_player(controlled_player: str) -> int:
    normalized = (controlled_player or "Player1").strip().lower()
    return 4 if normalized == "player2" else 3


def _infer_owner_name(cell_channels: np.ndarray) -> str:
    owner_slice = cell_channels[2:5]
    owner_idx = int(np.argmax(owner_slice).item())
    if owner_idx == 1:
        return "Player1"
    if owner_idx == 2:
        return "Player2"
    return "Neutral"


def _infer_unit_type_name(cell_channels: np.ndarray) -> str:
    unit_slice = cell_channels[5:12]
    unit_idx = int(np.argmax(unit_slice).item())
    names = ("Resource", "Base", "Barracks", "Worker", "Light", "Heavy", "Ranged")
    return names[unit_idx]


def _build_focus_cell_diagnostic(
    obs_hwc: np.ndarray,
    logits_by_key: Dict[str, torch.Tensor],
    flat_index: int,
    logical_label: str,
) -> Dict[str, Any]:
    row, col = _to_row_col(flat_index)
    cell_channels = obs_hwc[row, col, :].astype(np.float64)

    action_type_logits = logits_by_key["action_type_logits"][0, flat_index, :].detach().cpu().numpy().astype(np.float64)
    action_type_probs = _softmax(action_type_logits)
    produce_unit_type_logits = logits_by_key["produce_unit_type_logits"][0, flat_index, :].detach().cpu().numpy().astype(np.float64)
    produce_unit_type_probs = _softmax(produce_unit_type_logits)
    ranked = np.argsort(-action_type_probs)
    produce_ranked = np.argsort(-produce_unit_type_probs)

    top3 = []
    for idx in ranked[:3]:
        class_id = int(idx)
        top3.append(
            {
                "class_id": class_id,
                "class_name": ACTION_TYPE_NAMES[class_id],
                "logit": float(action_type_logits[class_id]),
                "probability": float(action_type_probs[class_id]),
            }
        )

    produce_top3 = []
    for idx in produce_ranked[:3]:
        class_id = int(idx)
        produce_top3.append(
            {
                "class_id": class_id,
                "class_name": PRODUCE_UNIT_TYPE_NAMES[class_id],
                "logit": float(produce_unit_type_logits[class_id]),
                "probability": float(produce_unit_type_probs[class_id]),
            }
        )

    best_non_noop = float(np.max(action_type_probs[1:])) if action_type_probs.shape[0] > 1 else 0.0
    noop_prob = float(action_type_probs[0])
    noop_margin = float(noop_prob - best_non_noop)

    predicted_action_type = _argmax(action_type_logits)
    move_dir = _argmax(logits_by_key["move_dir_logits"][0, flat_index, :].detach().cpu().numpy())
    harvest_dir = _argmax(logits_by_key["harvest_dir_logits"][0, flat_index, :].detach().cpu().numpy())
    return_dir = _argmax(logits_by_key["return_dir_logits"][0, flat_index, :].detach().cpu().numpy())
    produce_dir = _argmax(logits_by_key["produce_dir_logits"][0, flat_index, :].detach().cpu().numpy())
    produce_unit_type = _argmax(logits_by_key["produce_unit_type_logits"][0, flat_index, :].detach().cpu().numpy())
    attack_target_local = _argmax(logits_by_key["attack_target_local_logits"][0, flat_index, :].detach().cpu().numpy())

    return {
        "logical_label": logical_label,
        "grid_position": [int(col), int(row)],
        "flat_index": int(flat_index),
        "owner_guess": _infer_owner_name(cell_channels),
        "unit_type_guess": _infer_unit_type_name(cell_channels),
        "eligible_actor_guess": bool(
            float(cell_channels[0]) > 0.0
            and float(cell_channels[5]) < 0.5
            and float(cell_channels[2]) < 0.5
        ),
        "predicted_action_type": int(predicted_action_type),
        "predicted_action_type_name": ACTION_TYPE_NAMES[predicted_action_type],
        "action_type_logits": [float(x) for x in action_type_logits.tolist()],
        "action_type_probabilities": [float(x) for x in action_type_probs.tolist()],
        "action_type_top3": top3,
        "produce_unit_type_logits": [float(x) for x in produce_unit_type_logits.tolist()],
        "produce_unit_type_probabilities": [float(x) for x in produce_unit_type_probs.tolist()],
        "produce_unit_type_top3": produce_top3,
        "produce_rank_light": int(np.where(produce_ranked == 4)[0][0]) + 1,
        "produce_rank_heavy": int(np.where(produce_ranked == 5)[0][0]) + 1,
        "produce_rank_ranged": int(np.where(produce_ranked == 6)[0][0]) + 1,
        "noop_probability": noop_prob,
        "best_non_noop_probability": best_non_noop,
        "noop_margin": noop_margin,
        "move_dir": int(move_dir),
        "harvest_dir": int(harvest_dir),
        "return_dir": int(return_dir),
        "produce_dir": int(produce_dir),
        "produce_unit_type": int(produce_unit_type),
        "attack_target_local": int(attack_target_local),
        "cell_observation_channels": [float(x) for x in cell_channels.tolist()],
    }


def _build_actor_summary(
    obs_hwc: np.ndarray,
    logits_by_key: Dict[str, torch.Tensor],
    controlled_player: str,
) -> list[Dict[str, Any]]:
    owner_channel = _owner_channel_for_player(controlled_player)
    action_logits = logits_by_key["action_type_logits"][0].detach().cpu().numpy().astype(np.float64)
    rows: list[Dict[str, Any]] = []

    for flat_index in range(TOTAL_CELLS):
        row, col = _to_row_col(flat_index)
        cell = obs_hwc[row, col, :]
        hp = float(cell[0])
        is_neutral = float(cell[2]) > 0.5
        is_own = float(cell[owner_channel]) > 0.5
        is_resource = float(cell[5]) > 0.5
        if hp <= 0.0 or is_neutral or is_resource or not is_own:
            continue

        probs = _softmax(action_logits[flat_index])
        ranked = np.argsort(-probs)
        top1 = int(ranked[0])
        top2 = int(ranked[1]) if ranked.shape[0] > 1 else top1
        best_non_noop = float(np.max(probs[1:])) if probs.shape[0] > 1 else 0.0

        rows.append(
            {
                "flat_index": int(flat_index),
                "grid_position": [int(col), int(row)],
                "logical_label": _logical_cell_label(row, col),
                "predicted_action_type": int(top1),
                "predicted_action_type_name": ACTION_TYPE_NAMES[top1],
                "top1_probability": float(probs[top1]),
                "top2_action_type": int(top2),
                "top2_action_type_name": ACTION_TYPE_NAMES[top2],
                "top2_probability": float(probs[top2]),
                "noop_margin": float(probs[0] - best_non_noop),
            }
        )

    rows.sort(key=lambda item: item["flat_index"])
    return rows


def _build_global_cell_action_type_diagnostics(
    obs_hwc: np.ndarray,
    logits_by_key: Dict[str, torch.Tensor],
) -> list[Dict[str, Any]]:
    action_logits = logits_by_key["action_type_logits"][0].detach().cpu().numpy().astype(np.float64)
    produce_logits_by_cell = logits_by_key["produce_unit_type_logits"][0].detach().cpu().numpy().astype(np.float64)
    rows: list[Dict[str, Any]] = []

    for flat_index in range(TOTAL_CELLS):
        row, col = _to_row_col(flat_index)
        cell_channels = obs_hwc[row, col, :].astype(np.float64)
        logits = action_logits[flat_index]
        produce_logits = produce_logits_by_cell[flat_index]
        probs = _softmax(logits)
        produce_probs = _softmax(produce_logits)
        ranked = np.argsort(-probs)
        produce_ranked = np.argsort(-produce_probs)
        predicted_action_type = int(ranked[0])
        best_non_noop = float(np.max(probs[1:])) if probs.shape[0] > 1 else 0.0

        top3 = []
        for idx in ranked[:3]:
            class_id = int(idx)
            top3.append(
                {
                    "class_id": class_id,
                    "class_name": ACTION_TYPE_NAMES[class_id],
                    "logit": float(logits[class_id]),
                    "probability": float(probs[class_id]),
                }
            )

        produce_top3 = []
        for idx in produce_ranked[:3]:
            class_id = int(idx)
            produce_top3.append(
                {
                    "class_id": class_id,
                    "class_name": PRODUCE_UNIT_TYPE_NAMES[class_id],
                    "logit": float(produce_logits[class_id]),
                    "probability": float(produce_probs[class_id]),
                }
            )

        rows.append(
            {
                "flat_index": int(flat_index),
                "grid_position": [int(col), int(row)],
                "logical_label": _logical_cell_label(row, col),
                "owner_guess": _infer_owner_name(cell_channels),
                "unit_type_guess": _infer_unit_type_name(cell_channels),
                "action_type_logits": [float(x) for x in logits.tolist()],
                "action_type_probabilities": [float(x) for x in probs.tolist()],
                "predicted_action_type": int(predicted_action_type),
                "predicted_action_type_name": ACTION_TYPE_NAMES[predicted_action_type],
                "non_noop_probability": float(1.0 - probs[0]),
                "action_type_top3": top3,
                "produce_unit_type_logits": [float(x) for x in produce_logits.tolist()],
                "produce_unit_type_probabilities": [float(x) for x in produce_probs.tolist()],
                "produce_unit_type_top3": produce_top3,
                "produce_rank_light": int(np.where(produce_ranked == 4)[0][0]) + 1,
                "produce_rank_heavy": int(np.where(produce_ranked == 5)[0][0]) + 1,
                "produce_rank_ranged": int(np.where(produce_ranked == 6)[0][0]) + 1,
            }
        )

    return rows


def _build_stage10r_debug_payload(
    obs_hwc: np.ndarray,
    logits_by_key: Dict[str, torch.Tensor],
    controlled_player: str,
) -> Dict[str, Any]:
    focus_cells = [
        _build_focus_cell_diagnostic(obs_hwc, logits_by_key, flat_index=25, logical_label="B2"),
        _build_focus_cell_diagnostic(obs_hwc, logits_by_key, flat_index=50, logical_label="C3"),
    ]

    flatten_checks = []
    for label, row, col, expected_unit in (("B2", 1, 1, "Worker"), ("C3", 2, 2, "Base")):
        expected_flat = row * EXPECTED_OBS_SHAPE[1] + col
        focus = focus_cells[0] if label == "B2" else focus_cells[1]
        flatten_checks.append(
            {
                "check": f"{label}_flat_formula",
                "pass": bool(focus["flat_index"] == expected_flat),
                "expected": int(expected_flat),
                "actual": int(focus["flat_index"]),
                "expected_text": str(expected_flat),
                "actual_text": str(focus["flat_index"]),
            }
        )
        flatten_checks.append(
            {
                "check": f"{label}_unit_type_alignment",
                "pass": bool(focus["unit_type_guess"] == expected_unit),
                "expected": -1,
                "actual": -1,
                "expected_text": expected_unit,
                "actual_text": str(focus["unit_type_guess"]),
            }
        )

    observation_vs_bc_expectation = []
    for focus in focus_cells:
        channels = focus["cell_observation_channels"]
        unit_type = focus["unit_type_guess"]
        expected_unit_channel = {
            "Worker": 8,
            "Base": 6,
        }.get(unit_type, -1)
        expected_ok = expected_unit_channel >= 0 and channels[expected_unit_channel] > 0.5
        owner_ok = channels[3] > 0.5 or channels[4] > 0.5
        observation_vs_bc_expectation.append(
            {
                "logical_label": focus["logical_label"],
                "unit_type_guess": unit_type,
                "owner_guess": focus["owner_guess"],
                "expected_unit_channel_active": bool(expected_ok),
                "owner_channel_active": bool(owner_ok),
                "suspicious": bool((not expected_ok) or (not owner_ok)),
            }
        )

    return {
        "controlled_player": controlled_player,
        "owner_encoding_mode": "absolute_player_channels",
        "flatten_formula": "flat_index = row * 24 + col",
        "observation_channel_names": list(OBS_CHANNEL_NAMES),
        "focus_cells": focus_cells,
        "own_actor_action_type_summary": _build_actor_summary(obs_hwc, logits_by_key, controlled_player),
        "global_cell_action_type_diagnostics": _build_global_cell_action_type_diagnostics(obs_hwc, logits_by_key),
        "flatten_alignment_checks": flatten_checks,
        "observation_vs_bc_expectation": observation_vs_bc_expectation,
    }


def _load_observation(path: Path) -> np.ndarray:
    arr = np.fromfile(path, dtype=EXPECTED_OBS_DTYPE)
    expected_count = int(np.prod(EXPECTED_OBS_SHAPE))
    if arr.size != expected_count:
        raise ValueError(
            "Observation element count mismatch. "
            f"Expected {expected_count}, got {arr.size}"
        )

    obs_hwc = arr.reshape(EXPECTED_OBS_SHAPE)
    if obs_hwc.dtype != EXPECTED_OBS_DTYPE:
        raise ValueError(f"Observation dtype mismatch. Expected {EXPECTED_OBS_DTYPE}, got {obs_hwc.dtype}")
    return obs_hwc


def _validate_logits_contract(logits_by_key: Dict[str, torch.Tensor]) -> None:
    validate_student_branch_contract_consistency(
        expected_bc_branch_sizes=EXPECTED_BC_BRANCH_SIZES,
        model_logits_keys=BRANCH_LOGITS_KEYS,
    )

    keys = tuple(logits_by_key.keys())
    if keys != BRANCH_LOGITS_KEYS:
        raise ValueError(
            "Model output keys mismatch. "
            f"Expected {BRANCH_LOGITS_KEYS}, got {keys}"
        )

    for spec in BRANCH_SPECS:
        tensor = logits_by_key[spec.logits_key]
        if tensor.ndim != 3:
            raise ValueError(
                f"{spec.logits_key} rank mismatch. Expected 3 [B,576,{spec.branch_size}], got {tensor.ndim}"
            )
        if tensor.shape[0] != 1:
            raise ValueError(f"{spec.logits_key} batch mismatch. Expected 1, got {tensor.shape[0]}")
        if tensor.shape[1] != TOTAL_CELLS:
            raise ValueError(
                f"{spec.logits_key} cell count mismatch. Expected {TOTAL_CELLS}, got {tensor.shape[1]}"
            )
        if tensor.shape[2] != spec.branch_size:
            raise ValueError(
                f"{spec.logits_key} branch size mismatch. Expected {spec.branch_size}, got {tensor.shape[2]}"
            )


def _build_action_flat_from_logits(logits_by_key: Dict[str, torch.Tensor]) -> list[int]:
    action_flat = [0] * TOTAL_ACTION_FLAT_SIZE

    for branch_index, spec in enumerate(BRANCH_SPECS):
        branch_logits = logits_by_key[spec.logits_key]
        branch_indices = torch.argmax(branch_logits, dim=-1).detach().cpu().numpy()
        if branch_indices.shape != (1, TOTAL_CELLS):
            raise ValueError(
                f"Argmax result shape mismatch for {spec.logits_key}. "
                f"Expected (1, {TOTAL_CELLS}), got {branch_indices.shape}"
            )

        branch_values = branch_indices[0]
        branch_offset = BRANCH_OFFSETS[branch_index]
        for cell_idx in range(TOTAL_CELLS):
            value = int(branch_values[cell_idx])
            if value < 0 or value >= spec.branch_size:
                raise ValueError(
                    f"Branch value out of range for {spec.branch_name} at cell {cell_idx}: {value}"
                )

            flat_index = cell_idx * ACTION_FLAT_SIZE_PER_CELL + branch_offset
            action_flat[flat_index] = value

    if len(action_flat) != TOTAL_ACTION_FLAT_SIZE:
        raise ValueError(
            f"Action flat size mismatch. Expected {TOTAL_ACTION_FLAT_SIZE}, got {len(action_flat)}"
        )
    return action_flat


def _to_json_safe_metrics(metrics: Any) -> Dict[str, float | int]:
    if not isinstance(metrics, dict):
        return {}

    safe: Dict[str, float | int] = {}
    for key, value in metrics.items():
        if isinstance(value, (int, float)):
            safe[str(key)] = value
    return safe


def run_inference_with_loaded_model(
    model: torch.nn.Module,
    checkpoint_meta: Dict[str, Any],
    obs_hwc: np.ndarray,
    device: str,
    controlled_player: str = "Player1",
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "status": "fail",
        "action_contract_version": ACTION_CONTRACT_VERSION,
        "observation_shape": list(EXPECTED_OBS_SHAPE),
        "observation_dtype": "float32",
        "branch_order": list(BRANCH_ORDER),
        "branch_sizes": list(EXPECTED_BC_BRANCH_SIZES),
        "logits_keys": list(BRANCH_LOGITS_KEYS),
    }

    input_tensor = torch.from_numpy(obs_hwc).unsqueeze(0).to(device=torch.device(device))

    with torch.no_grad():
        logits_by_key = model(input_tensor)

    _validate_logits_contract(logits_by_key)
    action_flat = _build_action_flat_from_logits(logits_by_key)

    logits_shapes = {
        key: list(logits_by_key[key].shape) for key in BRANCH_LOGITS_KEYS
    }

    result.update(
        {
            "status": "ok",
            "checkpoint_epoch": checkpoint_meta.get("epoch"),
            "checkpoint_model_variant": checkpoint_meta.get("model_variant"),
            "checkpoint_metrics": _to_json_safe_metrics(checkpoint_meta.get("metrics")),
            "observation_element_count": int(obs_hwc.size),
            "model_output_logits_shapes": logits_shapes,
            "action_flat_size": len(action_flat),
            "action_flat": action_flat,
            "stage10r_debug": _build_stage10r_debug_payload(obs_hwc, logits_by_key, controlled_player),
        }
    )
    return result


def run_inference_from_observation_bin(
    checkpoint_path: Path,
    observation_bin: Path,
    device: str,
    controlled_player: str = "Player1",
) -> Dict[str, Any]:
    obs_hwc = _load_observation(observation_bin)
    model, checkpoint_meta = load_student_transfer_checkpoint(checkpoint_path, device=device)

    result = run_inference_with_loaded_model(
        model,
        checkpoint_meta,
        obs_hwc,
        device=device,
        controlled_player=controlled_player,
    )
    result["checkpoint_path"] = str(checkpoint_path.resolve())
    result["observation_bin"] = str(observation_bin.resolve())
    return result


def main() -> int:
    args = parse_args()

    result: Dict[str, Any] = {
        "status": "fail",
        "action_contract_version": ACTION_CONTRACT_VERSION,
        "checkpoint_path": str(args.checkpoint.resolve()),
        "observation_bin": str(args.observation_bin.resolve()),
        "observation_shape": list(EXPECTED_OBS_SHAPE),
        "observation_dtype": "float32",
        "branch_order": list(BRANCH_ORDER),
        "branch_sizes": list(EXPECTED_BC_BRANCH_SIZES),
        "logits_keys": list(BRANCH_LOGITS_KEYS),
    }

    try:
        result.update(
            run_inference_from_observation_bin(
                checkpoint_path=args.checkpoint,
                observation_bin=args.observation_bin,
                device=args.device,
                controlled_player=args.controlled_player,
            )
        )
    except Exception as exc:  # pragma: no cover - fail-fast diagnostics for wiring
        result["error"] = str(exc)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")

    if result["status"] != "ok":
        print(f"[FAIL] Day4 student inference adapter failed: {result.get('error', 'unknown error')}")
        return 1

    print("[PASS] Day4 student inference adapter succeeded")
    print(f"checkpoint={result['checkpoint_path']}")
    print(f"action_contract_version={result['action_contract_version']}")
    print(f"branch_sizes={result['branch_sizes']}")
    print(f"action_flat_size={result['action_flat_size']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
