from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from load_student_checkpoint import load_student_transfer_checkpoint
from student_inference_adapter import run_inference_with_loaded_model

EXPECTED_LOGIT_SHAPES: dict[str, list[int]] = {
    "action_type_logits": [1, 576, 6],
    "move_dir_logits": [1, 576, 4],
    "harvest_dir_logits": [1, 576, 4],
    "return_dir_logits": [1, 576, 4],
    "produce_dir_logits": [1, 576, 4],
    "produce_unit_type_logits": [1, 576, 7],
    "attack_target_local_logits": [1, 576, 49],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage10D18R manual checkpoint binding verification")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--observation-json", type=Path, default=None)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--device", type=str, default="cpu")
    return parser.parse_args()


def _load_observation(path: Path | None) -> np.ndarray:
    if path is None:
        return np.zeros((24, 24, 27), dtype=np.float32)
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict) and "observation" in payload:
        payload = payload["observation"]
    arr = np.asarray(payload, dtype=np.float32)
    if arr.shape != (24, 24, 27):
        raise ValueError(f"Expected observation shape (24,24,27), got {arr.shape}")
    return arr


def main() -> int:
    args = parse_args()
    checkpoint_path = args.checkpoint.resolve()

    out: dict[str, Any] = {
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_exists": checkpoint_path.exists(),
        "checkpoint_size_bytes": checkpoint_path.stat().st_size if checkpoint_path.exists() else None,
        "load_status": "not_run",
        "load_exception_summary": None,
        "strict_load": True,
        "forward_status": "not_run",
        "logits_shapes": {},
        "logits_shapes_valid": False,
        "model_loaded": False,
        "classification_labels": [],
    }

    labels: list[str] = []
    if not checkpoint_path.exists():
        labels.extend([
            "STAGE10D18R_MANUAL_CHECKPOINT_LOAD_FAIL",
            "STAGE10D18R_STAGE10D17_STATE_DICT_INCOMPATIBLE",
        ])
        out["classification_labels"] = labels
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(out, ensure_ascii=True, indent=2), encoding="utf-8")
        return 0

    try:
        model, meta = load_student_transfer_checkpoint(checkpoint_path, device=args.device)
        out["load_status"] = "ok"
        out["model_loaded"] = True
        out["checkpoint_epoch"] = meta.get("epoch")
        out["checkpoint_model_variant"] = meta.get("model_variant")
        labels.append("STAGE10D18R_MANUAL_CHECKPOINT_LOAD_PASS")
    except Exception as exc:
        out["load_status"] = "fail"
        out["load_exception_summary"] = f"{type(exc).__name__}: {exc}"
        labels.extend([
            "STAGE10D18R_MANUAL_CHECKPOINT_LOAD_FAIL",
            "STAGE10D18R_STAGE10D17_STATE_DICT_INCOMPATIBLE",
        ])
        out["classification_labels"] = labels
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(out, ensure_ascii=True, indent=2), encoding="utf-8")
        return 0

    try:
        obs = _load_observation(args.observation_json)
        inference = run_inference_with_loaded_model(
            model,
            {"checkpoint_path": str(checkpoint_path), "epoch": out.get("checkpoint_epoch"), "model_variant": out.get("checkpoint_model_variant")},
            obs,
            device=args.device,
            controlled_player="Player1",
        )
        out["forward_status"] = str(inference.get("status"))
        logits_shapes = inference.get("model_output_logits_shapes") or {}
        out["logits_shapes"] = logits_shapes
        out["logits_shapes_valid"] = all(logits_shapes.get(k) == v for k, v in EXPECTED_LOGIT_SHAPES.items())
        if out["forward_status"] == "ok":
            labels.append("STAGE10D18R_MANUAL_FORWARD_PASS")
        if out["logits_shapes_valid"]:
            labels.append("STAGE10D18R_MANUAL_LOGITS_SHAPES_VALID")
    except Exception as exc:
        out["forward_status"] = "fail"
        out["load_exception_summary"] = f"{type(exc).__name__}: {exc}"

    out["classification_labels"] = labels
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(out, ensure_ascii=True, indent=2), encoding="utf-8")
    print(args.output_json.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
