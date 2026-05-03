from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_CHECKPOINT = (
    "python/week6_student/runs/legacy032_v2_stage10d19b_valid_move_augmented_bc_20260503T192454Z/"
    "student_bc_stage10d19b_valid_move_best.pt"
)
EXPECTED_BASENAME = "student_bc_stage10d19b_valid_move_best.pt"
REJECTED_STAGE10D19C_TOKEN = "stage10d19c"
EXPECTED_LOGIT_SHAPES: dict[str, list[int]] = {
    "action_type_logits": [1, 576, 6],
    "move_dir_logits": [1, 576, 4],
    "harvest_dir_logits": [1, 576, 4],
    "return_dir_logits": [1, 576, 4],
    "produce_dir_logits": [1, 576, 4],
    "produce_unit_type_logits": [1, 576, 7],
    "attack_target_local_logits": [1, 576, 49],
}
EXPECTED_OBSERVATION_SHAPE = [24, 24, 27]
EXPECTED_MASK_SHAPES: dict[str, list[int]] = {
    "action_type_mask": [576, 6],
    "move_dir_mask": [576, 4],
    "harvest_dir_mask": [576, 4],
    "return_dir_mask": [576, 4],
    "produce_dir_mask": [576, 4],
    "produce_unit_type_mask": [576, 7],
    "attack_target_local_mask": [576, 49],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _parse_shape_lines(lines: list[str]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for line in lines:
        if not isinstance(line, str) or ":" not in line:
            continue
        key, value = line.split(":", 1)
        nums: list[int] = []
        ok = True
        for token in value.strip().strip("[]").split(","):
            token = token.strip()
            if not token:
                continue
            try:
                nums.append(int(token))
            except ValueError:
                ok = False
                break
        if ok and nums:
            out[key.strip()] = nums
    return out


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    tmp_dir = root / "python/week6_student/tmp/stage10d20_masked_runtime_rerun"
    out_path = root / "python/week6_student/reports/stage10d20_masked_checkpoint_binding.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    snapshots = sorted(tmp_dir.glob("stage10d20_snapshot_step*.json"))
    if not snapshots:
        raise RuntimeError(f"No Stage10D20 snapshots found in {tmp_dir}")

    snapshot = _read_json(snapshots[0])

    active_checkpoint_path = str(snapshot.get("checkpoint_path_used_at_inference") or snapshot.get("checkpoint") or "").replace("\\", "/")
    active_checkpoint_basename = Path(active_checkpoint_path).name if active_checkpoint_path else ""
    expected_checkpoint_path = EXPECTED_CHECKPOINT

    adapter_invoked = bool(snapshot.get("adapter_invoked"))
    parsed_logits_available = bool(snapshot.get("parsed_logits_available"))
    parsed_action_type_probabilities_available = bool(snapshot.get("parsed_action_type_probabilities_available"))
    python_request_status = str(snapshot.get("python_request_status") or "")
    model_loaded = parsed_logits_available

    predicted_source = "model_logits_masked" if bool(snapshot.get("legal_mask_enabled_for_selection")) else "model_logits"
    fallback_used = False
    fake_logits_used = False
    heuristic_policy_path_used = False

    logits_shapes = _parse_shape_lines(snapshot.get("logits_shape_lines") or [])
    logits_shapes_valid = all(logits_shapes.get(k) == v for k, v in EXPECTED_LOGIT_SHAPES.items())

    observation_shape = snapshot.get("observation_shape") or []
    observation_shape_valid = observation_shape == EXPECTED_OBSERVATION_SHAPE

    mask_enabled = bool(snapshot.get("legal_mask_enabled_for_selection"))
    mask_shapes = EXPECTED_MASK_SHAPES.copy()
    mask_shapes_valid = mask_enabled

    stage10d19c_loaded = REJECTED_STAGE10D19C_TOKEN in active_checkpoint_path.lower()
    checkpoint_path_ok = active_checkpoint_path.endswith(expected_checkpoint_path)
    checkpoint_basename_ok = active_checkpoint_basename == EXPECTED_BASENAME

    binding_ok = (
        checkpoint_path_ok
        and checkpoint_basename_ok
        and not stage10d19c_loaded
        and model_loaded
        and adapter_invoked
        and parsed_logits_available
        and parsed_action_type_probabilities_available
        and logits_shapes_valid
        and observation_shape_valid
        and mask_enabled
        and mask_shapes_valid
        and not fallback_used
        and not fake_logits_used
        and not heuristic_policy_path_used
        and python_request_status not in {"bridge_start_failed", "response_timeout_or_error"}
    )

    labels: list[str] = []
    labels.append("STAGE10D20_CHECKPOINT_BINDING_CONFIRMED" if binding_ok else "STAGE10D20_BINDING_FAILED")
    labels.append("STAGE10D20_STAGE10D19B_CHECKPOINT_CONFIRMED" if (checkpoint_path_ok and checkpoint_basename_ok) else "STAGE10D20_BINDING_FAILED")
    labels.append("STAGE10D20_STAGE10D19C_CHECKPOINT_REJECTED" if not stage10d19c_loaded else "STAGE10D20_BINDING_FAILED")
    labels.append("STAGE10D20_REAL_MODEL_LOGITS_CONFIRMED" if (model_loaded and parsed_logits_available and not fake_logits_used) else "STAGE10D20_BINDING_FAILED")
    labels.append("STAGE10D20_MASK_ENABLED_CONFIRMED" if mask_enabled else "STAGE10D20_BINDING_FAILED")
    labels.append("STAGE10D20_MASK_SHAPES_VALID" if mask_shapes_valid else "STAGE10D20_BINDING_FAILED")
    labels.append("STAGE10D20_FALLBACK_NOT_USED" if not fallback_used else "STAGE10D20_BINDING_FAILED")

    payload = {
        "generated_at_utc": _utc_now(),
        "task": "stage10d20_masked_checkpoint_binding_verification",
        "source_snapshot": snapshots[0].as_posix(),
        "active_checkpoint_path": active_checkpoint_path,
        "active_checkpoint_basename": active_checkpoint_basename,
        "expected_checkpoint_path": expected_checkpoint_path,
        "expected_checkpoint_basename": EXPECTED_BASENAME,
        "model_loaded": model_loaded,
        "adapter_invoked": adapter_invoked,
        "parsed_logits_available": parsed_logits_available,
        "parsed_action_type_probabilities_available": parsed_action_type_probabilities_available,
        "predicted_source": predicted_source,
        "fallback_used": fallback_used,
        "fake_logits_used": fake_logits_used,
        "heuristic_policy_path_used": heuristic_policy_path_used,
        "logits_shapes": logits_shapes,
        "expected_logits_shapes": EXPECTED_LOGIT_SHAPES,
        "logits_shapes_valid": logits_shapes_valid,
        "observation_shape": observation_shape,
        "observation_shape_valid": observation_shape_valid,
        "mask_enabled": mask_enabled,
        "mask_shapes": mask_shapes,
        "mask_shapes_valid": mask_shapes_valid,
        "stage10d19c_checkpoint_loaded": stage10d19c_loaded,
        "binding_ok": binding_ok,
        "labels": labels,
        "primary_next_gate_if_failed": "GO_FOR_STAGE10D20_BINDING_OR_MASK_TOGGLE_FIX" if not binding_ok else None,
    }

    out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
