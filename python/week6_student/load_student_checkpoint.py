from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import torch
from torch import nn

from student_architecture_transfer import build_day3_student_model


def load_student_transfer_checkpoint(
    checkpoint_path: str | Path,
    *,
    device: str = "cpu",
) -> tuple[nn.Module, Dict[str, Any]]:
    """Load Week 6 student transfer checkpoint for inference.

    This loader is intentionally strict for Day 4 wiring:
    - only student checkpoint is accepted;
    - transfer model architecture is used;
    - state dict must match exactly.
    """

    ckpt_path = Path(checkpoint_path).resolve()
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")

    payload = torch.load(ckpt_path, map_location=torch.device(device))
    if not isinstance(payload, dict):
        raise ValueError(f"Checkpoint payload must be a dict, got {type(payload)!r}")

    model_state = payload.get("model_state_dict")
    if not isinstance(model_state, dict):
        raise ValueError("Checkpoint is missing model_state_dict")

    config = payload.get("config")
    model_variant = None
    if isinstance(config, dict):
        model_variant = config.get("model_variant")
    if model_variant not in (None, "transfer"):
        raise ValueError(
            "Day 4 inference expects transfer student checkpoint. "
            f"Got model_variant={model_variant!r}"
        )

    model = build_day3_student_model()
    missing, unexpected = model.load_state_dict(model_state, strict=True)
    if missing or unexpected:
        raise ValueError(
            "Checkpoint/model mismatch. "
            f"missing={missing}, unexpected={unexpected}"
        )

    model.eval()
    model.to(torch.device(device))

    metadata: Dict[str, Any] = {
        "checkpoint_path": str(ckpt_path),
        "epoch": payload.get("epoch"),
        "metrics": payload.get("metrics", {}),
        "config": config if isinstance(config, dict) else {},
        "model_variant": model_variant if model_variant is not None else "unknown",
    }
    return model, metadata
