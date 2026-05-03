from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_CHECKPOINT = "python/week6_student/runs/legacy032_v2_semantic_bc_stage10d8_20260503T093718Z/student_bc_semantic_best.pt"
EXPECTED_OBS_SHAPE = [24, 24, 27]
EXPECTED_LOGIT_SHAPES = {
    "action_type_logits": [1, 576, 6],
    "move_dir_logits": [1, 576, 4],
    "harvest_dir_logits": [1, 576, 4],
    "return_dir_logits": [1, 576, 4],
    "produce_dir_logits": [1, 576, 4],
    "produce_unit_type_logits": [1, 576, 7],
    "attack_target_local_logits": [1, 576, 49],
}


class CheckResult(dict):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return {}


def _check(name: str, ok: bool, details: Any) -> CheckResult:
    return CheckResult(name=name, ok=bool(ok), details=details)


def _focus(snapshot: dict[str, Any], label: str) -> dict[str, Any]:
    rows = snapshot.get("focus_cell_diagnostics")
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if isinstance(row, dict) and str(row.get("logical_label")) == label:
            return row
    return {}


def _normalize_checkpoint(value: Any) -> str:
    text = str(value or "").replace("\\", "/")
    if text.endswith(EXPECTED_CHECKPOINT):
        return EXPECTED_CHECKPOINT
    return text


def _extract_logit_shape_map(snapshot: dict[str, Any]) -> dict[str, list[int]]:
    shape_lines = snapshot.get("logits_shape_lines")
    if not isinstance(shape_lines, list):
        return {}

    result: dict[str, list[int]] = {}
    for line in shape_lines:
        if not isinstance(line, str):
            continue
        if ":" not in line:
            continue
        left, right = line.split(":", 1)
        key = left.strip()
        raw = right.strip().lstrip("[").rstrip("]")
        if not key or not raw:
            continue
        values: list[int] = []
        for token in raw.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                values.append(int(token))
            except ValueError:
                values = []
                break
        if values:
            result[key] = values
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage10D.9R verifier for Unity runtime inference artifact capture.")
    parser.add_argument(
        "--snapshot-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d9r_unity_stage10r_rerun_snapshot_step0001.json"),
    )
    parser.add_argument(
        "--episode-diagnostics-json",
        type=Path,
        default=Path("python/week6_student/tmp/week6_visual/week6_visual_episode_diagnostics.json"),
    )
    parser.add_argument(
        "--checkpoint-binding-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d9_checkpoint_binding_verification.json"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d9r_inference_artifact_verification.json"),
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    snapshot = _read_json(root / args.snapshot_json)
    episode = _read_json(root / args.episode_diagnostics_json)
    binding = _read_json(root / args.checkpoint_binding_json)

    checks: list[CheckResult] = []

    binding_status = str(binding.get("status", ""))
    checks.append(_check("checkpoint_binding_status_pass", binding_status == "pass", binding_status))

    obs_shape = snapshot.get("observation_shape")
    checks.append(_check("runtime_observation_shape_24x24x27", obs_shape == EXPECTED_OBS_SHAPE, obs_shape))

    inference_request_count = int(snapshot.get("inference_request_count") or 0)
    checks.append(_check("inference_request_count_gt_zero", inference_request_count > 0, inference_request_count))

    adapter_invoked = bool(snapshot.get("adapter_invoked"))
    checks.append(_check("adapter_invoked_true", adapter_invoked, adapter_invoked))

    checkpoint_used = _normalize_checkpoint(snapshot.get("checkpoint_path_used_at_inference") or snapshot.get("checkpoint"))
    checks.append(_check("checkpoint_path_used_matches_stage10d8", checkpoint_used == EXPECTED_CHECKPOINT, checkpoint_used))

    logits_shapes_captured = bool(snapshot.get("logits_shapes_captured"))
    checks.append(_check("logits_shapes_captured_true", logits_shapes_captured, logits_shapes_captured))

    shape_map = _extract_logit_shape_map(snapshot)
    for key, expected in EXPECTED_LOGIT_SHAPES.items():
        checks.append(_check(f"{key}_shape", shape_map.get(key) == expected, {"actual": shape_map.get(key), "expected": expected}))

    b2 = _focus(snapshot, "B2")
    c3 = _focus(snapshot, "C3")

    b2_probs = b2.get("action_type_probabilities") if isinstance(b2.get("action_type_probabilities"), list) else []
    c3_probs = c3.get("action_type_probabilities") if isinstance(c3.get("action_type_probabilities"), list) else []
    b2_top3 = b2.get("action_type_top3") if isinstance(b2.get("action_type_top3"), list) else []
    c3_top3 = c3.get("action_type_top3") if isinstance(c3.get("action_type_top3"), list) else []

    checks.append(_check("b2_action_type_probabilities_len_6", len(b2_probs) == 6, len(b2_probs)))
    checks.append(_check("b2_action_type_top3_len_ge_3", len(b2_top3) >= 3, len(b2_top3)))
    checks.append(_check("c3_action_type_probabilities_len_6", len(c3_probs) == 6, len(c3_probs)))
    checks.append(_check("c3_action_type_top3_len_ge_3", len(c3_top3) >= 3, len(c3_top3)))

    b2_reason = str(b2.get("command_not_built_reason") or "")
    c3_reason = str(c3.get("command_not_built_reason") or "")
    checks.append(_check("b2_reason_not_no_adapter_artifact", b2_reason != "no_adapter_artifact", b2_reason))
    checks.append(_check("c3_reason_not_no_adapter_artifact", c3_reason != "no_adapter_artifact", c3_reason))

    b2_source = str(b2.get("predicted_action_type_source") or "")
    c3_source = str(c3.get("predicted_action_type_source") or "")
    checks.append(_check("b2_predicted_action_source_model_logits", b2_source == "model_logits", b2_source))
    checks.append(_check("c3_predicted_action_source_model_logits", c3_source == "model_logits", c3_source))

    parsed_logits_available = bool(snapshot.get("parsed_logits_available"))
    parsed_probs_available = bool(snapshot.get("parsed_action_type_probabilities_available"))
    checks.append(_check("no_fake_or_fallback_logits", parsed_logits_available and parsed_probs_available, {
        "parsed_logits_available": parsed_logits_available,
        "parsed_action_type_probabilities_available": parsed_probs_available,
    }))

    status = "pass" if all(bool(item.get("ok")) for item in checks) else "fail"

    report = {
        "stage": "10D.9R",
        "task": "runtime_inference_artifact_verification",
        "generated_at_utc": _utc_now(),
        "status": status,
        "inputs": {
            "snapshot_json": args.snapshot_json.as_posix(),
            "episode_diagnostics_json": args.episode_diagnostics_json.as_posix(),
            "checkpoint_binding_json": args.checkpoint_binding_json.as_posix(),
        },
        "summary": {
            "checkpoint_binding_status": binding_status,
            "runtime_observation_shape": obs_shape,
            "inference_request_count": inference_request_count,
            "adapter_invoked": adapter_invoked,
            "checkpoint_path_used": checkpoint_used,
            "logits_shapes_captured": logits_shapes_captured,
            "episode_terminal_reason": episode.get("terminal_reason"),
            "episode_steps_run": episode.get("steps_run"),
        },
        "checks": checks,
    }

    out_path = root / args.output_json
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")

    print(out_path.as_posix())
    print(f"status={status}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
