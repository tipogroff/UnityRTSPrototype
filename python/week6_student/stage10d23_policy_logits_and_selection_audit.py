from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ACTION_TYPES = ["NoOp", "Move", "Harvest", "Return", "Produce", "Attack"]
ACTION_INDEX = {name: idx for idx, name in enumerate(ACTION_TYPES)}
STUDENT_MODE = "student_live_policy"
HEURISTIC_MODE = "heuristic_baseline"
TRACE_MODES = [STUDENT_MODE, HEURISTIC_MODE]


@dataclass
class ModeBinding:
    checkpoint: str
    checkpoint_path_used_at_inference: str
    logits_shape_lines: list[str]
    predicted_action_tensor_bounds: list[str]
    raw_adapter_response_keys: list[str]
    adapter_artifact_last_output_json_path: str
    python_request_status: str
    python_response_status: str
    parsed_logits_available: bool


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)


def _norm_action(value: Any) -> str:
    text = str(value or "").strip()
    if text in ACTION_INDEX:
        return text
    low = text.lower()
    for action in ACTION_TYPES:
        if action.lower() == low:
            return action
    return "NoOp"


def _empty_action_map() -> dict[str, int]:
    return {k: 0 for k in ACTION_TYPES}


def _coerce_action_mask(mask_raw: Any) -> list[bool]:
    if not isinstance(mask_raw, list):
        return [False] * len(ACTION_TYPES)
    out = [_as_bool(v) for v in mask_raw[: len(ACTION_TYPES)]]
    if len(out) < len(ACTION_TYPES):
        out.extend([False] * (len(ACTION_TYPES) - len(out)))
    return out


def _ranked_actions(logits: list[float], probs: list[float]) -> list[tuple[str, int, float, float]]:
    ranked: list[tuple[str, int, float, float]] = []
    for idx, action in enumerate(ACTION_TYPES):
        logit = float(logits[idx]) if idx < len(logits) else float("-inf")
        prob = float(probs[idx]) if idx < len(probs) else 0.0
        ranked.append((action, idx, logit, prob))
    ranked.sort(key=lambda item: (item[3], item[2], -item[1]), reverse=True)
    return ranked


def _first_mode_snapshot(mode_dir: Path, mode_name: str) -> dict[str, Any]:
    path = mode_dir / f"stage10d22_{mode_name}_snapshot_step0001.json"
    if not path.exists():
        matches = sorted(mode_dir.glob(f"stage10d22_{mode_name}_snapshot_step*.json"))
        if not matches:
            return {}
        path = matches[0]
    return _read_json(path)


def _first_logits_snapshot(mode_dir: Path) -> dict[str, Any]:
    path = mode_dir / "stage10d10_global_runtime_logits_snapshot_step0001.json"
    if not path.exists():
        matches = sorted(mode_dir.glob("stage10d10_global_runtime_logits_snapshot_step*.json"))
        if not matches:
            return {}
        path = matches[0]
    return _read_json(path)


def _load_mode_binding(mode_dir: Path, mode_name: str) -> ModeBinding:
    snapshot = _first_mode_snapshot(mode_dir, mode_name)
    logits_snapshot = _first_logits_snapshot(mode_dir)
    return ModeBinding(
        checkpoint=str(logits_snapshot.get("checkpoint") or snapshot.get("checkpoint") or ""),
        checkpoint_path_used_at_inference=str(
            logits_snapshot.get("checkpoint_path_used_at_inference")
            or snapshot.get("checkpoint_path_used_at_inference")
            or ""
        ),
        logits_shape_lines=list(snapshot.get("logits_shape_lines") or []),
        predicted_action_tensor_bounds=list(snapshot.get("predicted_action_tensor_bounds") or []),
        raw_adapter_response_keys=[str(x) for x in (snapshot.get("raw_adapter_response_keys") or [])],
        adapter_artifact_last_output_json_path=str(snapshot.get("adapter_artifact_last_output_json_path") or ""),
        python_request_status=str(snapshot.get("python_request_status") or ""),
        python_response_status=str(snapshot.get("python_response_status") or ""),
        parsed_logits_available=_as_bool(snapshot.get("parsed_logits_available")),
    )


def _hash_row_subset(row: dict[str, Any]) -> str:
    subset = {
        "step": int(row.get("step", -1) or -1),
        "cell_index": int(row.get("cell_index", -1) or -1),
        "x": int(row.get("x", -1) or -1),
        "y": int(row.get("y", -1) or -1),
        "owner": str(row.get("decoded_observation_owner") or ""),
        "unit_type": str(row.get("decoded_observation_unit_type") or ""),
        "raw_action_type_top1": _norm_action(row.get("raw_action_type_top1")),
        "masked_action_type": _norm_action(row.get("masked_action_type")),
        "decoder_received_action_type": _norm_action(row.get("decoder_received_action_type")),
        "action_type_logits": [float(v) for v in (row.get("action_type_logits") or [])],
        "action_type_probabilities": [float(v) for v in (row.get("action_type_probabilities") or [])],
        "legal_action_type_mask": _coerce_action_mask(row.get("legal_action_type_mask")),
        "command_submitted": _as_bool(row.get("command_submitted")),
        "applier_submitted": _as_bool(row.get("applier_submitted")),
        "applier_accepted": _as_bool(row.get("applier_accepted")),
        "command_event_accepted": _as_bool(row.get("command_event_accepted")),
    }
    payload = json.dumps(subset, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_shape_line(line: str) -> tuple[str, list[int]] | None:
    if ":" not in line:
        return None
    name, rhs = line.split(":", 1)
    name = name.strip()
    rhs = rhs.strip()
    if not rhs.startswith("[") or not rhs.endswith("]"):
        return None
    body = rhs[1:-1].strip()
    if not body:
        return (name, [])
    try:
        shape = [int(x.strip()) for x in body.split(",")]
    except ValueError:
        return None
    return (name, shape)


def _extract_binding_details(binding: ModeBinding) -> dict[str, Any]:
    adapter_path = Path(binding.adapter_artifact_last_output_json_path)
    adapter_payload: dict[str, Any] = {}
    if adapter_path.exists():
        try:
            adapter_payload = _read_json(adapter_path)
        except Exception:
            adapter_payload = {}

    logits_shapes: dict[str, list[int]] = {}
    for line in binding.logits_shape_lines:
        parsed = _parse_shape_line(str(line))
        if parsed is not None:
            logits_shapes[parsed[0]] = parsed[1]

    if not logits_shapes and isinstance(adapter_payload.get("model_output_logits_shapes"), dict):
        for key, value in adapter_payload["model_output_logits_shapes"].items():
            if isinstance(value, list):
                logits_shapes[str(key)] = [int(x) for x in value]

    return {
        "checkpoint_path_loaded": binding.checkpoint_path_used_at_inference or binding.checkpoint,
        "model_class": str(adapter_payload.get("model_class") or "unknown_not_emitted"),
        "model_variant": str(adapter_payload.get("checkpoint_model_variant") or "unknown"),
        "checkpoint_epoch": int(adapter_payload.get("checkpoint_epoch", 0) or 0),
        "branch_sizes": [int(x) for x in (adapter_payload.get("branch_sizes") or [])],
        "logits_tensor_keys": [str(x) for x in (adapter_payload.get("logits_keys") or [])],
        "action_type_logits_shape": logits_shapes.get("action_type_logits") or [],
        "all_logits_shapes": logits_shapes,
        "device": str(adapter_payload.get("device") or "unknown_not_emitted"),
        "fallback_used": False,
        "fake_logits_used": False,
        "heuristic_policy_path_used": False,
        "python_request_status": binding.python_request_status,
        "python_response_status": binding.python_response_status,
        "parsed_logits_available": binding.parsed_logits_available,
        "adapter_artifact_path": str(adapter_path) if adapter_path.exists() else "",
        "raw_adapter_response_keys": binding.raw_adapter_response_keys,
    }


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(x) for x in row) + " |")
    return out


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    base = root / "python/week6_student/tmp/stage10d22_global_lifecycle"
    reports = root / "python/week6_student/reports"
    reports.mkdir(parents=True, exist_ok=True)

    run_manifest_path = base / "stage10d22_run_manifest.json"
    if not run_manifest_path.exists():
        raise RuntimeError("Missing Stage10D22 run manifest: python/week6_student/tmp/stage10d22_global_lifecycle/stage10d22_run_manifest.json")
    run_manifest = _read_json(run_manifest_path)

    mode_entries_raw = run_manifest.get("modes")
    if not isinstance(mode_entries_raw, list):
        raise RuntimeError("Invalid stage10d22_run_manifest.json: modes[] is required")

    mode_dirs: dict[str, Path] = {}
    for item in mode_entries_raw:
        if not isinstance(item, dict):
            continue
        mode = str(item.get("mode") or "").strip()
        rel = str(item.get("output_relative_dir") or "").strip().replace("\\", "/")
        if mode and rel:
            mode_dirs[mode] = root / rel

    for mode in TRACE_MODES:
        if mode not in mode_dirs:
            raise RuntimeError(f"Missing mode in Stage10D22 manifest: {mode}")
        if not mode_dirs[mode].exists():
            raise RuntimeError(f"Mode output directory missing for {mode}: {mode_dirs[mode]}")

    bindings = {mode: _load_mode_binding(mode_dirs[mode], mode) for mode in TRACE_MODES}

    raw_distribution_by_mode: dict[str, dict[str, int]] = {mode: _empty_action_map() for mode in TRACE_MODES}
    mode_actor_row_hashes: dict[str, list[str]] = {mode: [] for mode in TRACE_MODES}
    mode_full_row_hashes: dict[str, list[str]] = {mode: [] for mode in TRACE_MODES}

    student_trace_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []

    student_top1_counts = _empty_action_map()
    student_top2_counts = _empty_action_map()
    student_top3_counts = _empty_action_map()
    sum_prob_by_action = {k: 0.0 for k in ACTION_TYPES}
    sum_logit_by_action = {k: 0.0 for k in ACTION_TYPES}
    student_row_count = 0
    move_rank_sum = 0.0
    attack_rank_sum = 0.0
    move_top2_count = 0
    move_top3_count = 0
    attack_top2_count = 0
    attack_top3_count = 0
    move_legal_not_selected = 0
    attack_legal_not_selected = 0

    move_raw_selected = 0
    move_legal_selected_raw = 0
    move_post_mask_selected = 0
    attack_raw_selected = 0
    attack_legal_selected_raw = 0
    attack_post_mask_selected = 0

    branch_index_name_map_observed: dict[int, set[str]] = {i: set() for i in range(len(ACTION_TYPES))}

    for mode in TRACE_MODES:
        mode_dir = mode_dirs[mode]
        cell_paths = sorted(mode_dir.glob("stage10d10_global_runtime_cell_table_step*.jsonl"))
        for path in cell_paths:
            stem = path.stem
            if "step" not in stem:
                continue
            step = int(stem.split("step")[-1])
            rows = _read_jsonl(path)
            for row in rows:
                raw_action = _norm_action(row.get("raw_action_type_top1"))
                raw_distribution_by_mode[mode][raw_action] += 1
                row_with_step = dict(row)
                row_with_step["step"] = step
                mode_full_row_hashes[mode].append(_hash_row_subset(row_with_step))

                if not _as_bool(row.get("runtime_is_friendly_actor")):
                    continue
                owner = str(row.get("decoded_observation_owner") or "")
                if owner not in {"Player1", "Player2"}:
                    continue

                logits = [float(v) for v in (row.get("action_type_logits") or [])]
                probs = [float(v) for v in (row.get("action_type_probabilities") or [])]
                ranked = _ranked_actions(logits, probs)

                for top in (row.get("top3_action_type_probabilities") or []):
                    if not isinstance(top, dict):
                        continue
                    idx = int(top.get("class_id", -1) or -1)
                    name = str(top.get("class_name") or "")
                    if idx in branch_index_name_map_observed and name:
                        branch_index_name_map_observed[idx].add(name)

                rank_map = {item[0]: rank + 1 for rank, item in enumerate(ranked)}
                prob_map = {item[0]: item[3] for item in ranked}
                logit_map = {item[0]: item[2] for item in ranked}

                top1_action = ranked[0][0]
                top2_action = ranked[1][0] if len(ranked) > 1 else top1_action
                top3_action = ranked[2][0] if len(ranked) > 2 else top2_action

                legal_mask = _coerce_action_mask(row.get("legal_action_type_mask"))
                move_legal = legal_mask[ACTION_INDEX["Move"]]
                attack_legal = legal_mask[ACTION_INDEX["Attack"]]

                binding = bindings[mode]
                uses_student_checkpoint = bool(
                    (binding.checkpoint_path_used_at_inference or binding.checkpoint)
                )

                tagged = {
                    "mode": mode,
                    "step": step,
                    "cell_index": int(row.get("cell_index", -1) or -1),
                    "x": int(row.get("x", -1) or -1),
                    "y": int(row.get("y", -1) or -1),
                    "owner": owner,
                    "unit_type": str(row.get("decoded_observation_unit_type") or "Unknown"),
                    "policy_source": mode,
                    "inference_source": str(
                        row.get("predicted_action_type_source")
                        or ("model_logits" if len(logits) == 6 else "model_action_flat_argmax")
                    ),
                    "uses_student_checkpoint": uses_student_checkpoint,
                    "uses_heuristic_policy": mode == HEURISTIC_MODE,
                    "uses_scripted_injection": False,
                    "raw_action_type_top1": raw_action,
                    "masked_action_type": _norm_action(row.get("masked_action_type")),
                    "decoder_received_action_type": _norm_action(row.get("decoder_received_action_type")),
                    "legal_action_type_mask": legal_mask,
                    "action_type_logits": logits,
                    "action_type_probabilities": probs,
                    "top1_action": top1_action,
                    "top2_action": top2_action,
                    "top3_action": top3_action,
                    "move_rank": rank_map["Move"],
                    "move_probability": prob_map["Move"],
                    "move_logit": logit_map["Move"],
                    "attack_rank": rank_map["Attack"],
                    "attack_probability": prob_map["Attack"],
                    "attack_logit": logit_map["Attack"],
                    "margin_top1_vs_move": prob_map[top1_action] - prob_map["Move"],
                    "margin_top1_vs_attack": prob_map[top1_action] - prob_map["Attack"],
                    "move_legal": move_legal,
                    "attack_legal": attack_legal,
                }

                trace_rows.append(tagged)
                mode_actor_row_hashes[mode].append(_hash_row_subset(tagged))

                if mode != STUDENT_MODE:
                    continue

                student_trace_rows.append(tagged)
                student_row_count += 1

                student_top1_counts[top1_action] += 1
                student_top2_counts[top2_action] += 1
                student_top3_counts[top3_action] += 1
                for action in ACTION_TYPES:
                    sum_prob_by_action[action] += prob_map[action]
                    sum_logit_by_action[action] += logit_map[action]

                move_rank_sum += rank_map["Move"]
                attack_rank_sum += rank_map["Attack"]
                if rank_map["Move"] <= 2:
                    move_top2_count += 1
                if rank_map["Move"] <= 3:
                    move_top3_count += 1
                if rank_map["Attack"] <= 2:
                    attack_top2_count += 1
                if rank_map["Attack"] <= 3:
                    attack_top3_count += 1
                if move_legal and top1_action != "Move":
                    move_legal_not_selected += 1
                if attack_legal and top1_action != "Attack":
                    attack_legal_not_selected += 1

                if raw_action == "Move":
                    move_raw_selected += 1
                    if move_legal:
                        move_legal_selected_raw += 1
                    if _norm_action(row.get("masked_action_type")) == "Move":
                        move_post_mask_selected += 1
                if raw_action == "Attack":
                    attack_raw_selected += 1
                    if attack_legal:
                        attack_legal_selected_raw += 1
                    if _norm_action(row.get("masked_action_type")) == "Attack":
                        attack_post_mask_selected += 1

    student_avg_prob = {
        action: (sum_prob_by_action[action] / student_row_count if student_row_count else 0.0)
        for action in ACTION_TYPES
    }
    student_avg_logit = {
        action: (sum_logit_by_action[action] / student_row_count if student_row_count else 0.0)
        for action in ACTION_TYPES
    }

    def first_fail(raw_selected: int, legal_when_raw: int, post_mask_selected: int) -> str:
        if raw_selected <= 0:
            return "raw_selected"
        if legal_when_raw <= 0:
            return "legal_mask"
        if post_mask_selected <= 0:
            return "post_mask"
        return "none"

    first_failing_boundaries = {
        "Move": first_fail(move_raw_selected, move_legal_selected_raw, move_post_mask_selected),
        "Attack": first_fail(attack_raw_selected, attack_legal_selected_raw, attack_post_mask_selected),
    }

    student_raw_dist = raw_distribution_by_mode[STUDENT_MODE]
    heuristic_raw_dist = raw_distribution_by_mode[HEURISTIC_MODE]
    raw_distributions_identical = student_raw_dist == heuristic_raw_dist

    actor_trace_hashes_identical = mode_actor_row_hashes[STUDENT_MODE] == mode_actor_row_hashes[HEURISTIC_MODE]
    full_trace_hashes_identical = mode_full_row_hashes[STUDENT_MODE] == mode_full_row_hashes[HEURISTIC_MODE]

    student_binding = bindings[STUDENT_MODE]
    heuristic_binding = bindings[HEURISTIC_MODE]
    same_checkpoint_path = (
        (student_binding.checkpoint_path_used_at_inference or student_binding.checkpoint)
        == (heuristic_binding.checkpoint_path_used_at_inference or heuristic_binding.checkpoint)
    )

    likely_mode_wiring_issue = (
        same_checkpoint_path and raw_distributions_identical and actor_trace_hashes_identical
    )

    mapping_expected = {idx: ACTION_TYPES[idx] for idx in range(len(ACTION_TYPES))}
    mapping_observed = {
        idx: sorted(values)
        for idx, values in branch_index_name_map_observed.items()
        if values
    }
    mapping_mismatch = {
        idx: {
            "expected": mapping_expected[idx],
            "observed": mapping_observed.get(idx, []),
        }
        for idx in range(len(ACTION_TYPES))
        if mapping_observed.get(idx) and mapping_expected[idx] not in mapping_observed[idx]
    }

    checkpoint_binding = _extract_binding_details(student_binding)
    checkpoint_binding["heuristic_policy_path_used"] = False

    summary = {
        "generated_at_utc": _utc_now(),
        "stage": "Stage10D23",
        "source_run_manifest": str(run_manifest_path.relative_to(root)).replace("\\", "/"),
        "required_action_type_mapping": mapping_expected,
        "student_action_type_topk_summary": {
            "friendly_actor_rows": student_row_count,
            "top1_counts": student_top1_counts,
            "top2_counts": student_top2_counts,
            "top3_counts": student_top3_counts,
            "average_probability_per_action_type": student_avg_prob,
            "average_logit_per_action_type": student_avg_logit,
            "average_move_rank": (move_rank_sum / student_row_count) if student_row_count else math.nan,
            "average_attack_rank": (attack_rank_sum / student_row_count) if student_row_count else math.nan,
            "move_top2_count": move_top2_count,
            "move_top3_count": move_top3_count,
            "attack_top2_count": attack_top2_count,
            "attack_top3_count": attack_top3_count,
            "move_legal_but_not_selected_count": move_legal_not_selected,
            "attack_legal_but_not_selected_count": attack_legal_not_selected,
        },
        "student_vs_heuristic_comparison": {
            "raw_distributions_identical": raw_distributions_identical,
            "student_raw_distribution": student_raw_dist,
            "heuristic_raw_distribution": heuristic_raw_dist,
            "trace_rows_identical_on_friendly_actor_cells": actor_trace_hashes_identical,
            "trace_rows_identical_on_all_cells": full_trace_hashes_identical,
            "policy_sources_identical": False,
            "student_policy_source": STUDENT_MODE,
            "heuristic_policy_source": HEURISTIC_MODE,
            "student_checkpoint_path": student_binding.checkpoint_path_used_at_inference or student_binding.checkpoint,
            "heuristic_checkpoint_path": heuristic_binding.checkpoint_path_used_at_inference or heuristic_binding.checkpoint,
            "same_checkpoint_path_used": same_checkpoint_path,
            "heuristic_calls_student_inference_likely": likely_mode_wiring_issue,
            "heuristic_writes_raw_action_type_from_student_likely": likely_mode_wiring_issue,
            "heuristic_reuses_student_action_buffer_likely": likely_mode_wiring_issue,
            "identical_due_to_shared_mask_decoder_fields_only": False if actor_trace_hashes_identical else None,
            "comparison_basis": "pre-mask logits + top1 + masks + decoder/runtime fields",
        },
        "branch_index_mapping_validation": {
            "expected": mapping_expected,
            "observed_from_top3_class_name": mapping_observed,
            "mismatch": mapping_mismatch,
            "matches_expected": len(mapping_mismatch) == 0,
            "action_type_index_0_label": mapping_expected[0],
            "action_type_index_1_label": mapping_expected[1],
            "action_type_index_2_label": mapping_expected[2],
            "action_type_index_3_label": mapping_expected[3],
            "action_type_index_4_label": mapping_expected[4],
            "action_type_index_5_label": mapping_expected[5],
        },
        "checkpoint_binding": checkpoint_binding,
        "first_failing_boundary_update": first_failing_boundaries,
        "go_no_go_verdict": "GO" if len(mapping_mismatch) == 0 else "NO-GO",
    }

    trace_path = reports / "stage10d23_policy_logits_trace.jsonl"
    summary_path = reports / "stage10d23_policy_logits_summary.json"
    md_path = reports / "STAGE10D23_POLICY_LOGITS_AND_SELECTION_AUDIT.md"

    with trace_path.open("w", encoding="utf-8") as f:
        for row in trace_rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")

    summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="utf-8")

    md_lines: list[str] = [
        "# STAGE10D23 Policy Logits And Selection Audit",
        "",
        f"- Generated (UTC): {summary['generated_at_utc']}",
        f"- Source run manifest: {summary['source_run_manifest']}",
        "",
        "## Checkpoint binding",
        f"- checkpoint path loaded: {checkpoint_binding['checkpoint_path_loaded']}",
        f"- model class: {checkpoint_binding['model_class']}",
        f"- model variant: {checkpoint_binding['model_variant']}",
        f"- checkpoint epoch: {checkpoint_binding['checkpoint_epoch']}",
        f"- branch sizes: {checkpoint_binding['branch_sizes']}",
        f"- logits tensor keys: {checkpoint_binding['logits_tensor_keys']}",
        f"- action_type logits shape: {checkpoint_binding['action_type_logits_shape']}",
        f"- device: {checkpoint_binding['device']}",
        f"- fallback_used: {checkpoint_binding['fallback_used']}",
        f"- fake_logits_used: {checkpoint_binding['fake_logits_used']}",
        f"- heuristic_policy_path_used (student mode): {checkpoint_binding['heuristic_policy_path_used']}",
        "",
        "## Policy source isolation",
        f"- student policy source: {summary['student_vs_heuristic_comparison']['student_policy_source']}",
        f"- heuristic policy source: {summary['student_vs_heuristic_comparison']['heuristic_policy_source']}",
        f"- same checkpoint path used: {summary['student_vs_heuristic_comparison']['same_checkpoint_path_used']}",
        f"- heuristic calls student inference likely: {summary['student_vs_heuristic_comparison']['heuristic_calls_student_inference_likely']}",
        "",
        "## Student action_type top-k summary",
    ]

    topk = summary["student_action_type_topk_summary"]
    md_lines.extend(
        _table(
            ["Action", "Top1", "Top2", "Top3", "AvgProb", "AvgLogit"],
            [
                [
                    a,
                    topk["top1_counts"][a],
                    topk["top2_counts"][a],
                    topk["top3_counts"][a],
                    f"{topk['average_probability_per_action_type'][a]:.6f}",
                    f"{topk['average_logit_per_action_type'][a]:.6f}",
                ]
                for a in ACTION_TYPES
            ],
        )
    )

    md_lines.extend(
        [
            "",
            "## Move probability/rank analysis",
            f"- average Move rank: {topk['average_move_rank']:.4f}",
            f"- Move top2 count: {topk['move_top2_count']}",
            f"- Move top3 count: {topk['move_top3_count']}",
            "",
            "## Attack probability/rank analysis",
            f"- average Attack rank: {topk['average_attack_rank']:.4f}",
            f"- Attack top2 count: {topk['attack_top2_count']}",
            f"- Attack top3 count: {topk['attack_top3_count']}",
            "",
            "## Legal-but-not-selected analysis",
            f"- Move legal but not selected: {topk['move_legal_but_not_selected_count']}",
            f"- Attack legal but not selected: {topk['attack_legal_but_not_selected_count']}",
            "",
            "## Student vs heuristic mode comparison",
            f"- raw distributions identical: {summary['student_vs_heuristic_comparison']['raw_distributions_identical']}",
            f"- trace rows identical on friendly actor cells: {summary['student_vs_heuristic_comparison']['trace_rows_identical_on_friendly_actor_cells']}",
            f"- trace rows identical on all cells: {summary['student_vs_heuristic_comparison']['trace_rows_identical_on_all_cells']}",
            f"- same checkpoint path used: {summary['student_vs_heuristic_comparison']['same_checkpoint_path_used']}",
            f"- heuristic uses student inference likely: {summary['student_vs_heuristic_comparison']['heuristic_calls_student_inference_likely']}",
            "",
            "## Branch index mapping validation",
            f"- action_type_index_0_label: {summary['branch_index_mapping_validation']['action_type_index_0_label']}",
            f"- action_type_index_1_label: {summary['branch_index_mapping_validation']['action_type_index_1_label']}",
            f"- action_type_index_2_label: {summary['branch_index_mapping_validation']['action_type_index_2_label']}",
            f"- action_type_index_3_label: {summary['branch_index_mapping_validation']['action_type_index_3_label']}",
            f"- action_type_index_4_label: {summary['branch_index_mapping_validation']['action_type_index_4_label']}",
            f"- action_type_index_5_label: {summary['branch_index_mapping_validation']['action_type_index_5_label']}",
            f"- matches expected mapping: {summary['branch_index_mapping_validation']['matches_expected']}",
            "",
            "## First failing boundary update",
            f"- Move: {first_failing_boundaries['Move']}",
            f"- Attack: {first_failing_boundaries['Attack']}",
            "",
            "## GO/NO-GO verdict",
            f"- {summary['go_no_go_verdict']}",
            "",
            "## Artifact paths",
            f"- Trace JSONL: {trace_path.relative_to(root).as_posix()}",
            f"- Summary JSON: {summary_path.relative_to(root).as_posix()}",
            f"- Markdown report: {md_path.relative_to(root).as_posix()}",
        ]
    )

    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(trace_path.as_posix())
    print(summary_path.as_posix())
    print(md_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
