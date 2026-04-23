from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

import numpy as np
import torch

from load_student_checkpoint import load_student_transfer_checkpoint
from student_branch_contract import (
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
ACTION_FLAT_SIZE_PER_CELL: int = 35
TOTAL_ACTION_FLAT_SIZE: int = TOTAL_CELLS * ACTION_FLAT_SIZE_PER_CELL


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
    return parser.parse_args()


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


def main() -> int:
    args = parse_args()

    result: Dict[str, Any] = {
        "status": "fail",
        "checkpoint_path": str(args.checkpoint.resolve()),
        "observation_bin": str(args.observation_bin.resolve()),
        "observation_shape": list(EXPECTED_OBS_SHAPE),
        "observation_dtype": "float32",
        "branch_order": list(BRANCH_ORDER),
        "branch_sizes": list(EXPECTED_BC_BRANCH_SIZES),
        "logits_keys": list(BRANCH_LOGITS_KEYS),
    }

    try:
        obs_hwc = _load_observation(args.observation_bin)

        model, checkpoint_meta = load_student_transfer_checkpoint(args.checkpoint, device=args.device)

        input_tensor = torch.from_numpy(obs_hwc).unsqueeze(0).to(device=torch.device(args.device))

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
            }
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
    print(f"action_flat_size={result['action_flat_size']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
