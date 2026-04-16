from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


UNITY_H = 24
UNITY_W = 24
UNITY_C = 27
UNITY_TOTAL_CELLS = UNITY_H * UNITY_W
UNITY_BRANCH_SIZES = (6, 4, 4, 4, 4, 4, 9)
DEFAULT_SOURCE_BRANCH_SIZES = (6, 4, 4, 4, 4, 7, 49)


@dataclass
class StepAdaptResult:
    episode_id: int
    step_id: int
    sample_status: str
    observation_status: str
    action_status: str
    reasons: List[str]
    converted_observation: Optional[np.ndarray]
    converted_action: Optional[np.ndarray]
    semantic_quality: str
    action_layout: str
    action_layout_support: str
    observed_events: List[str]
    action_cell_stats: Dict[str, int] = field(default_factory=dict)


@dataclass
class EpisodeAdaptResult:
    episode_id: int
    total_steps: int
    converted_steps: int
    dropped_steps: int
    sample_status_counts: Dict[str, int]
    output_path: Optional[Path]


@dataclass
class ActionLayoutInfo:
    layout: str
    support: str
    detail: str


@dataclass
class AdaptationConfig:
    allow_spatial_resize: bool
    write_debug_jsonl: bool
    hp_divisor: Optional[float]
    resource_divisor: Optional[float]


@dataclass
class ConversionReportBuilder:
    input_batch_dir: Path
    output_batch_dir: Path
    batch_summary: Dict[str, Any]
    source_branch_sizes: Tuple[int, ...]
    hp_divisor: float
    resource_divisor: float

    sample_total: int = 0
    sample_exact: int = 0
    sample_adapted: int = 0
    sample_dropped: int = 0

    observation_exact: int = 0
    observation_approx: int = 0
    observation_dropped: int = 0

    action_exact: int = 0
    action_adapted: int = 0
    action_dropped: int = 0

    semantic_quality_counts: Counter = field(default_factory=Counter)
    remapped_to_noop_count: int = 0
    semantically_weak_action_count: int = 0
    noop_remap_reason_counts: Counter = field(default_factory=Counter)
    observation_signal_loss_events: int = 0

    drop_reasons: Counter = field(default_factory=Counter)
    adaptation_reasons: Counter = field(default_factory=Counter)

    action_type_counter_input: Counter = field(default_factory=Counter)
    action_type_counter_output: Counter = field(default_factory=Counter)
    action_layout_counts: Counter = field(default_factory=Counter)
    observed_gap_events: Counter = field(default_factory=Counter)

    action_cell_stats_total: Counter = field(default_factory=Counter)

    input_batch_kind: str = "unknown"

    def register_step(self, result: StepAdaptResult) -> None:
        self.sample_total += 1
        if result.sample_status == "exact":
            self.sample_exact += 1
        elif result.sample_status == "adapted":
            self.sample_adapted += 1
        else:
            self.sample_dropped += 1

        if result.observation_status == "exact":
            self.observation_exact += 1
        elif result.observation_status in ("approximate", "approximate_with_signal_loss"):
            self.observation_approx += 1
        else:
            self.observation_dropped += 1

        if result.action_status == "exact":
            self.action_exact += 1
        elif result.action_status == "adapted":
            self.action_adapted += 1
        else:
            self.action_dropped += 1

        self.semantic_quality_counts[result.semantic_quality] += 1
        if result.semantic_quality == "weakened":
            self.semantically_weak_action_count += 1

        self.action_layout_counts[f"{result.action_layout_support}:{result.action_layout}"] += 1

        for event_name in result.observed_events:
            self.observed_gap_events[event_name] += 1
            if event_name == "obs.extra_channels_dropped_signal_loss":
                self.observation_signal_loss_events += 1
            if event_name == "obs.spatial_crop_signal_loss":
                self.observation_signal_loss_events += 1

        for reason in result.reasons:
            if reason.startswith("drop:"):
                self.drop_reasons[reason] += 1
            else:
                self.adaptation_reasons[reason] += 1

        for key, value in result.action_cell_stats.items():
            self.action_cell_stats_total[key] += int(value)

        noop_events = {
            "noop_due_to_unsupported_action_type": int(result.action_cell_stats.get("unsupported_action_type_to_noop", 0)),
            "noop_due_to_invalid_produce_type": int(result.action_cell_stats.get("invalid_produce_type_to_noop", 0)),
            "noop_due_to_unsupported_produce_type": int(result.action_cell_stats.get("unsupported_produce_type_to_noop", 0)),
            "noop_due_to_attack_target_out_of_local_window": int(result.action_cell_stats.get("attack_target_outside_local_3x3_to_noop", 0)),
            "noop_due_to_invalid_move_dir": int(result.action_cell_stats.get("invalid_move_dir_to_noop", 0)),
            "noop_due_to_invalid_harvest_dir": int(result.action_cell_stats.get("invalid_harvest_dir_to_noop", 0)),
            "noop_due_to_invalid_return_dir": int(result.action_cell_stats.get("invalid_return_dir_to_noop", 0)),
            "noop_due_to_invalid_produce_dir": int(result.action_cell_stats.get("invalid_produce_dir_to_noop", 0)),
        }
        for key, value in noop_events.items():
            if value > 0:
                self.noop_remap_reason_counts[key] += value
                self.remapped_to_noop_count += value

    def build(self, episode_results: List[EpisodeAdaptResult], npz_outputs: List[str], debug_jsonl: Optional[str]) -> Dict[str, Any]:
        top_drop_reasons = [
            {"reason": reason, "count": int(count)}
            for reason, count in self.drop_reasons.most_common(10)
        ]
        top_adaptation_reasons = [
            {"reason": reason, "count": int(count)}
            for reason, count in self.adaptation_reasons.most_common(20)
        ]

        return {
            "status": "success",
            "input": {
                "batch_dir": str(self.input_batch_dir),
                "batch_name": self.batch_summary.get("batch_name"),
                "batch_mode": self.batch_summary.get("batch_mode"),
                "policy_source_id": self.batch_summary.get("policy_source_id"),
                "input_batch_kind": self.input_batch_kind,
            },
            "output": {
                "batch_dir": str(self.output_batch_dir),
                "adapted_npz_files": npz_outputs,
                "conversion_debug_jsonl": debug_jsonl,
            },
            "contract": {
                "target_observation_shape": [UNITY_H, UNITY_W, UNITY_C],
                "target_action_shape_per_step": [UNITY_TOTAL_CELLS, 7],
                "target_action_branch_sizes": list(UNITY_BRANCH_SIZES),
                "source_action_branch_sizes": list(self.source_branch_sizes),
                "supported_raw_action_layouts": [
                    "matrix_576x7 (supported_exact)",
                    "flat_4032 (supported_exact)",
                    "object_flat_4032 (supported_approx)",
                    "batched_flat_1x4032 (supported_approx)",
                    "batched_matrix_1x576x7 (supported_approx)",
                ],
                "global_vector_policy": "excluded_from_strict_bc_encoder_path",
                "normalization_formula": {
                    "hp_channel": "clip(raw_hp / hp_divisor, 0, 1)",
                    "resource_channel": "clip(raw_res / resource_divisor, 0, 1)",
                    "hp_divisor": self.hp_divisor,
                    "resource_divisor": self.resource_divisor,
                },
            },
            "policy_rules": {
                "global_vector_excluded_from_strict_bc_path": {
                    "enforced": True,
                    "scope": "pipeline_design_rule",
                    "counted_as_observed_event": False,
                }
            },
            "counters": {
                "samples": {
                    "total": self.sample_total,
                    "exact": self.sample_exact,
                    "adapted": self.sample_adapted,
                    "dropped": self.sample_dropped,
                },
                "observation": {
                    "exact": self.observation_exact,
                    "approximate": self.observation_approx,
                    "dropped": self.observation_dropped,
                    "signal_loss_events": self.observation_signal_loss_events,
                },
                "action": {
                    "exact": self.action_exact,
                    "adapted": self.action_adapted,
                    "dropped": self.action_dropped,
                },
                "observed_gap_events": {str(k): int(v) for k, v in sorted(self.observed_gap_events.items())},
                "action_cells": {k: int(v) for k, v in self.action_cell_stats_total.items()},
                "action_layouts": {str(k): int(v) for k, v in sorted(self.action_layout_counts.items())},
                "semantic_quality": {
                    "exact": int(self.semantic_quality_counts.get("exact", 0)),
                    "adapted": int(self.semantic_quality_counts.get("adapted", 0)),
                    "weakened": int(self.semantic_quality_counts.get("weakened", 0)),
                    "dropped": int(self.semantic_quality_counts.get("dropped", 0)),
                },
                "semantic_weakening": {
                    "remapped_to_noop_count": int(self.remapped_to_noop_count),
                    "semantically_weak_action_count": int(self.semantically_weak_action_count),
                    "noop_reason_counts": {str(k): int(v) for k, v in sorted(self.noop_remap_reason_counts.items())},
                },
                "top_drop_reasons": top_drop_reasons,
                "top_adaptation_reasons": top_adaptation_reasons,
            },
            "action_histograms": {
                "input_action_type": {str(k): int(v) for k, v in sorted(self.action_type_counter_input.items())},
                "output_action_type": {str(k): int(v) for k, v in sorted(self.action_type_counter_output.items())},
            },
            "episodes": [
                {
                    "episode_id": item.episode_id,
                    "total_steps": item.total_steps,
                    "converted_steps": item.converted_steps,
                    "dropped_steps": item.dropped_steps,
                    "sample_status_counts": item.sample_status_counts,
                    "output_path": str(item.output_path) if item.output_path else None,
                }
                for item in episode_results
            ],
            "notes": [
                "Adapter is teacher-source-agnostic and operates on Day 3 raw exports.",
                "No silent filtering: all drop/remap events are counted in report.",
                "No semantic parity claim is made for Gym vs Unity action/mask runtime truth.",
                "Input batch kind classification is informational only and is not a teacher quality score.",
            ],
        }


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def classify_input_batch_kind(policy_source_id: Optional[str]) -> str:
    if not policy_source_id:
        return "unknown"

    source = str(policy_source_id).strip().lower()
    if "random-policy-fallback" in source or "random" in source:
        return "infrastructure_validation"

    teacher_candidate_hints = (
        "sb3:",
        "checkpoint",
        "ppo",
        "a2c",
        "dqn",
        "teacher",
        "canonical",
    )
    if any(token in source for token in teacher_candidate_hints):
        return "teacher_candidate"

    return "unknown"


def discover_episode_files(batch_dir: Path) -> List[Path]:
    return sorted(batch_dir.glob("episode_*.npz"))


def infer_log_summary_path(batch_dir: Path, batch_summary: Dict[str, Any]) -> Optional[Path]:
    timestamp = batch_summary.get("timestamp_utc")
    if not timestamp:
        return None
    root = batch_dir.parent.parent
    candidate = root / "teacher_logs" / f"teacher_rollout_{timestamp}.summary.json"
    return candidate if candidate.exists() else None


def infer_source_branch_sizes(
    batch_dir: Path,
    batch_summary: Dict[str, Any],
    episode_path: Path,
) -> Tuple[int, ...]:
    log_summary_path = infer_log_summary_path(batch_dir, batch_summary)
    if log_summary_path and log_summary_path.exists():
        log_summary = load_json(log_summary_path)
        nvec = log_summary.get("environment", {}).get("action_space", {}).get("nvec")
        if isinstance(nvec, list) and len(nvec) >= 7:
            return tuple(int(x) for x in nvec[:7])

    with np.load(episode_path, allow_pickle=True) as data:
        action = np.asarray(data["action_t"][0])
        if action.ndim == 1 and action.size % 7 == 0:
            action = action.reshape((-1, 7))
        if action.ndim == 2 and action.shape[1] == 7:
            inferred = []
            for idx in range(7):
                branch_max = int(np.max(action[:, idx])) if action.shape[0] > 0 else 0
                inferred.append(branch_max + 1)
            if inferred[0] >= 6 and inferred[1] >= 4 and inferred[6] >= 9:
                return tuple(inferred)

    return DEFAULT_SOURCE_BRANCH_SIZES


def detect_action_layout(raw_action: Any) -> ActionLayoutInfo:
    arr = np.asarray(raw_action)

    if arr.ndim == 2 and arr.shape == (UNITY_TOTAL_CELLS, 7):
        return ActionLayoutInfo(layout="matrix_576x7", support="supported_exact", detail="already_shaped_per_cell")

    if arr.ndim == 1 and arr.shape[0] == UNITY_TOTAL_CELLS * 7:
        if arr.dtype == object:
            return ActionLayoutInfo(layout="object_flat_4032", support="supported_approx", detail="reshape_object_flat_to_matrix")
        return ActionLayoutInfo(layout="flat_4032", support="supported_exact", detail="reshape_flat_to_matrix")

    if arr.ndim == 2 and arr.shape == (1, UNITY_TOTAL_CELLS * 7):
        return ActionLayoutInfo(layout="batched_flat_1x4032", support="supported_approx", detail="squeeze_then_reshape")

    if arr.ndim == 3 and arr.shape == (1, UNITY_TOTAL_CELLS, 7):
        return ActionLayoutInfo(layout="batched_matrix_1x576x7", support="supported_approx", detail="squeeze_batch_dimension")

    detail = f"shape={list(arr.shape)},dtype={arr.dtype}"
    return ActionLayoutInfo(layout="unsupported", support="unsupported", detail=detail)


def normalize_action_payload(raw_action: Any, layout_info: ActionLayoutInfo) -> Tuple[Optional[np.ndarray], List[str]]:
    reasons: List[str] = []

    if layout_info.support == "unsupported":
        return None, [f"drop:action:unsupported_layout:{layout_info.detail}"]

    arr = np.asarray(raw_action)
    if layout_info.layout == "matrix_576x7":
        normalized = arr
    elif layout_info.layout == "flat_4032":
        normalized = arr.reshape((UNITY_TOTAL_CELLS, 7))
    elif layout_info.layout == "object_flat_4032":
        normalized = arr.reshape((UNITY_TOTAL_CELLS, 7))
        reasons.append("action:layout_object_flat_reshaped")
    elif layout_info.layout == "batched_flat_1x4032":
        normalized = np.squeeze(arr, axis=0).reshape((UNITY_TOTAL_CELLS, 7))
        reasons.append("action:layout_batched_flat_squeezed")
    elif layout_info.layout == "batched_matrix_1x576x7":
        normalized = np.squeeze(arr, axis=0)
        reasons.append("action:layout_batched_matrix_squeezed")
    else:
        return None, [f"drop:action:unsupported_layout:{layout_info.detail}"]

    try:
        normalized_i64 = np.asarray(normalized, dtype=np.int64)
    except (TypeError, ValueError):
        return None, ["drop:action:non_numeric_payload"]

    if normalized_i64.shape != (UNITY_TOTAL_CELLS, 7):
        return None, [f"drop:action:normalized_shape_mismatch:{list(normalized_i64.shape)}"]

    return normalized_i64, reasons


def compute_channel_divisors(episode_paths: Sequence[Path], hp_override: Optional[float], res_override: Optional[float]) -> Tuple[float, float]:
    if hp_override is not None and res_override is not None:
        return float(hp_override), float(res_override)

    hp_max = 1.0
    res_max = 1.0

    for episode_path in episode_paths:
        with np.load(episode_path, allow_pickle=True) as data:
            observations = np.asarray(data["observation_t"])
            if observations.ndim < 4:
                continue
            if observations.ndim == 5 and observations.shape[1] == 1:
                observations = observations[:, 0]
            if observations.shape[-1] < 2:
                continue
            hp_max = max(hp_max, float(np.max(observations[..., 0])))
            res_max = max(res_max, float(np.max(observations[..., 1])))

    hp_divisor = float(hp_override) if hp_override is not None else hp_max
    res_divisor = float(res_override) if res_override is not None else res_max

    return max(1.0, hp_divisor), max(1.0, res_divisor)


def _squeeze_observation(raw_obs: Any) -> Optional[np.ndarray]:
    obs = np.asarray(raw_obs)
    while obs.ndim > 3 and obs.shape[0] == 1:
        obs = np.squeeze(obs, axis=0)
    if obs.ndim != 3:
        return None
    return obs


def convert_observation(
    raw_obs: Any,
    hp_divisor: float,
    res_divisor: float,
    allow_spatial_resize: bool,
) -> Tuple[str, Optional[np.ndarray], List[str], List[str]]:
    reasons: List[str] = []
    observed_events: List[str] = []
    obs = _squeeze_observation(raw_obs)
    if obs is None:
        return "dropped", None, ["drop:obs:unsupported_rank"], observed_events

    h, w, c = obs.shape
    converted = obs.astype(np.float32, copy=True)

    if h != UNITY_H or w != UNITY_W:
        if not allow_spatial_resize:
            return "dropped", None, [f"drop:obs:spatial_mismatch_{h}x{w}"], observed_events

        target = np.zeros((UNITY_H, UNITY_W, c), dtype=np.float32)
        copy_h = min(h, UNITY_H)
        copy_w = min(w, UNITY_W)
        target[:copy_h, :copy_w, :] = converted[:copy_h, :copy_w, :]
        converted = target
        if h > UNITY_H or w > UNITY_W:
            reasons.append("obs:spatial_crop_signal_loss")
            observed_events.append("obs.spatial_crop_signal_loss")
        else:
            reasons.append("obs:spatial_zero_pad_structural")
            observed_events.append("obs.spatial_zero_pad_structural")

    if c < UNITY_C:
        return "dropped", None, [f"drop:obs:channel_count_lt_{UNITY_C}"], observed_events

    if c > UNITY_C:
        converted = converted[:, :, :UNITY_C]
        reasons.append("obs:extra_channels_dropped_signal_loss")
        observed_events.append("obs.extra_channels_dropped_signal_loss")

    hp_channel = converted[:, :, 0]
    res_channel = converted[:, :, 1]

    if hp_divisor > 1.0 or np.max(hp_channel) > 1.0 or np.min(hp_channel) < 0.0:
        converted[:, :, 0] = np.clip(hp_channel / hp_divisor, 0.0, 1.0)
        reasons.append("obs:normalize_hp")
        observed_events.append("obs.normalization_applied")
    else:
        converted[:, :, 0] = np.clip(hp_channel, 0.0, 1.0)

    if res_divisor > 1.0 or np.max(res_channel) > 1.0 or np.min(res_channel) < 0.0:
        converted[:, :, 1] = np.clip(res_channel / res_divisor, 0.0, 1.0)
        reasons.append("obs:normalize_resources")
        if "obs.normalization_applied" not in observed_events:
            observed_events.append("obs.normalization_applied")
    else:
        converted[:, :, 1] = np.clip(res_channel, 0.0, 1.0)

    if any("signal_loss" in reason for reason in reasons):
        status = "approximate_with_signal_loss"
    elif reasons:
        status = "approximate"
    else:
        status = "exact"
    return status, converted.astype(np.float32, copy=False), reasons, observed_events


def map_attack_target_to_local_3x3(source_target: int, source_size: int) -> Optional[int]:
    if source_size <= 0 or source_target < 0 or source_target >= source_size:
        return None
    if source_size == 9:
        return int(source_target)

    side = int(round(math.sqrt(source_size)))
    if side * side != source_size or side % 2 == 0:
        return None

    center = side // 2
    row = source_target // side
    col = source_target % side
    d_row = row - center
    d_col = col - center

    if abs(d_row) > 1 or abs(d_col) > 1:
        return None

    return int((d_row + 1) * 3 + (d_col + 1))


def convert_action(
    raw_action: Any,
    source_branch_sizes: Tuple[int, ...],
    report: ConversionReportBuilder,
) -> Tuple[str, Optional[np.ndarray], List[str], Dict[str, int], str, str, List[str], str]:
    reasons: List[str] = []
    observed_events: List[str] = []
    layout_info = detect_action_layout(raw_action)
    action, layout_reasons = normalize_action_payload(raw_action, layout_info)
    reasons.extend(layout_reasons)
    if action is None:
        return "dropped", None, reasons, {}, layout_info.layout, layout_info.support, observed_events, "dropped"

    source_sizes = source_branch_sizes if len(source_branch_sizes) == 7 else DEFAULT_SOURCE_BRANCH_SIZES
    output = np.zeros((UNITY_TOTAL_CELLS, 7), dtype=np.int16)

    cell_stats: Counter = Counter()
    action_was_adapted = False

    for cell_idx in range(UNITY_TOTAL_CELLS):
        src = action[cell_idx]
        src_type = int(src[0])
        report.action_type_counter_input[src_type] += 1

        if src_type < 0 or src_type >= source_sizes[0] or src_type >= UNITY_BRANCH_SIZES[0]:
            output[cell_idx, 0] = 0
            action_was_adapted = True
            cell_stats["unsupported_action_type_to_noop"] += 1
            observed_events.append("action.unsupported_action_type_filtered")
            continue

        output[cell_idx, 0] = int(src_type)

        if src_type == 1:
            move_dir = int(src[1])
            if move_dir < 0 or move_dir >= source_sizes[1]:
                output[cell_idx, 0] = 0
                action_was_adapted = True
                cell_stats["invalid_move_dir_to_noop"] += 1
            else:
                output[cell_idx, 1] = int(np.clip(move_dir, 0, 3))

        elif src_type == 2:
            harvest_dir = int(src[2])
            if harvest_dir < 0 or harvest_dir >= source_sizes[2]:
                output[cell_idx, 0] = 0
                action_was_adapted = True
                cell_stats["invalid_harvest_dir_to_noop"] += 1
            else:
                output[cell_idx, 2] = int(np.clip(harvest_dir, 0, 3))

        elif src_type == 3:
            return_dir = int(src[3])
            if return_dir < 0 or return_dir >= source_sizes[3]:
                output[cell_idx, 0] = 0
                action_was_adapted = True
                cell_stats["invalid_return_dir_to_noop"] += 1
            else:
                output[cell_idx, 3] = int(np.clip(return_dir, 0, 3))

        elif src_type == 4:
            produce_dir = int(src[4])
            if produce_dir < 0 or produce_dir >= source_sizes[4]:
                output[cell_idx, 0] = 0
                action_was_adapted = True
                cell_stats["invalid_produce_dir_to_noop"] += 1
            else:
                output[cell_idx, 4] = int(np.clip(produce_dir, 0, 3))

            src_produce = int(src[5])
            if src_produce < 0 or src_produce >= source_sizes[5]:
                output[cell_idx, 0] = 0
                action_was_adapted = True
                cell_stats["invalid_produce_type_to_noop"] += 1
                observed_events.append("action.produce_type_invalid_filtered")
            elif src_produce >= UNITY_BRANCH_SIZES[5]:
                output[cell_idx, 0] = 0
                action_was_adapted = True
                cell_stats["unsupported_produce_type_to_noop"] += 1
                observed_events.append("action.produce_type_outside_subset_filtered")
            else:
                output[cell_idx, 5] = int(src_produce)

        elif src_type == 5:
            mapped = map_attack_target_to_local_3x3(int(src[6]), source_sizes[6])
            if mapped is None:
                output[cell_idx, 0] = 0
                action_was_adapted = True
                cell_stats["attack_target_outside_local_3x3_to_noop"] += 1
                observed_events.append("action.attack_target_outside_local_3x3_filtered")
            else:
                output[cell_idx, 6] = int(mapped)
                if source_sizes[6] != 9:
                    action_was_adapted = True
                    cell_stats["attack_target_reduced_49_to_9"] += 1
                    observed_events.append("action.attack_target_reduced")

        report.action_type_counter_output[int(output[cell_idx, 0])] += 1

    if cell_stats:
        if cell_stats.get("unsupported_action_type_to_noop", 0) > 0:
            reasons.append("action:unsupported_action_type_filtered")
        if cell_stats.get("unsupported_produce_type_to_noop", 0) > 0:
            reasons.append("action:produce_type_outside_mvp_subset_filtered")
        if cell_stats.get("attack_target_outside_local_3x3_to_noop", 0) > 0:
            reasons.append("action:attack_target_outside_local_3x3_filtered")
        if cell_stats.get("attack_target_reduced_49_to_9", 0) > 0:
            reasons.append("action:attack_target_reduced_49_to_9")

    status = "adapted" if action_was_adapted else "exact"

    remapped_to_noop_total = int(
        cell_stats.get("unsupported_action_type_to_noop", 0)
        + cell_stats.get("invalid_produce_type_to_noop", 0)
        + cell_stats.get("unsupported_produce_type_to_noop", 0)
        + cell_stats.get("attack_target_outside_local_3x3_to_noop", 0)
        + cell_stats.get("invalid_move_dir_to_noop", 0)
        + cell_stats.get("invalid_harvest_dir_to_noop", 0)
        + cell_stats.get("invalid_return_dir_to_noop", 0)
        + cell_stats.get("invalid_produce_dir_to_noop", 0)
    )
    if remapped_to_noop_total > 0:
        semantic_quality = "weakened"
    elif status == "adapted":
        semantic_quality = "adapted"
    else:
        semantic_quality = "exact"

    dedup_events = sorted(set(observed_events))
    return (
        status,
        output,
        reasons,
        {k: int(v) for k, v in cell_stats.items()},
        layout_info.layout,
        layout_info.support,
        dedup_events,
        semantic_quality,
    )


def adapt_episode(
    episode_path: Path,
    output_dir: Path,
    report: ConversionReportBuilder,
    config: AdaptationConfig,
) -> Tuple[EpisodeAdaptResult, List[Dict[str, Any]]]:
    debug_lines: List[Dict[str, Any]] = []

    with np.load(episode_path, allow_pickle=True) as data:
        episode_id = int(np.asarray(data["episode_id"]).reshape(-1)[0])
        step_ids = np.asarray(data["step_id"], dtype=np.int64)
        rewards = np.asarray(data["reward_t"], dtype=np.float32)
        dones = np.asarray(data["done_t"], dtype=np.bool_)
        observations = data["observation_t"]
        actions = data["action_t"]

        converted_obs: List[np.ndarray] = []
        converted_actions: List[np.ndarray] = []
        kept_step_ids: List[int] = []
        kept_rewards: List[float] = []
        kept_dones: List[bool] = []

        sample_status_counts: Counter = Counter()
        dropped_steps = 0

        for idx in range(step_ids.shape[0]):
            step_id = int(step_ids[idx])

            obs_status, obs_payload, obs_reasons, obs_events = convert_observation(
                observations[idx],
                hp_divisor=report.hp_divisor,
                res_divisor=report.resource_divisor,
                allow_spatial_resize=config.allow_spatial_resize,
            )

            (
                act_status,
                act_payload,
                act_reasons,
                cell_stats,
                action_layout,
                action_layout_support,
                action_events,
                action_semantic_quality,
            ) = convert_action(
                actions[idx],
                source_branch_sizes=report.source_branch_sizes,
                report=report,
            )

            reasons = obs_reasons + act_reasons
            observed_events = obs_events + action_events

            if obs_status == "dropped" or act_status == "dropped":
                sample_status = "dropped"
                semantic_quality = "dropped"
                dropped_steps += 1
            elif obs_status == "exact" and act_status == "exact":
                sample_status = "exact"
                semantic_quality = "exact"
            else:
                sample_status = "adapted"
                if action_semantic_quality == "weakened":
                    semantic_quality = "weakened"
                else:
                    semantic_quality = "adapted"

            if obs_status == "approximate_with_signal_loss" and semantic_quality == "exact":
                semantic_quality = "adapted"

            result = StepAdaptResult(
                episode_id=episode_id,
                step_id=step_id,
                sample_status=sample_status,
                observation_status=obs_status,
                action_status=act_status,
                reasons=reasons,
                converted_observation=obs_payload,
                converted_action=act_payload,
                semantic_quality=semantic_quality,
                action_layout=action_layout,
                action_layout_support=action_layout_support,
                observed_events=sorted(set(observed_events)),
                action_cell_stats=cell_stats,
            )
            report.register_step(result)
            sample_status_counts[sample_status] += 1

            debug_lines.append(
                {
                    "episode_id": episode_id,
                    "step_id": step_id,
                    "sample_status": sample_status,
                    "semantic_quality": semantic_quality,
                    "observation_status": obs_status,
                    "action_status": act_status,
                    "action_layout": action_layout,
                    "action_layout_support": action_layout_support,
                    "reasons": reasons,
                    "observed_events": sorted(set(observed_events)),
                    "action_cell_stats": cell_stats,
                }
            )

            if sample_status == "dropped":
                continue

            converted_obs.append(obs_payload)
            converted_actions.append(act_payload)
            kept_step_ids.append(step_id)
            kept_rewards.append(float(rewards[idx]))
            kept_dones.append(bool(dones[idx]))

    output_path: Optional[Path] = None
    if converted_obs:
        output_path = output_dir / f"episode_{episode_id:05d}.adapted.npz"
        np.savez_compressed(
            output_path,
            episode_id=np.asarray([episode_id], dtype=np.int64),
            step_id=np.asarray(kept_step_ids, dtype=np.int64),
            observation_adapted=np.asarray(converted_obs, dtype=np.float32),
            action_adapted=np.asarray(converted_actions, dtype=np.int16),
            reward_t=np.asarray(kept_rewards, dtype=np.float32),
            done_t=np.asarray(kept_dones, dtype=np.bool_),
        )

    result = EpisodeAdaptResult(
        episode_id=episode_id,
        total_steps=int(len(debug_lines)),
        converted_steps=int(len(converted_obs)),
        dropped_steps=dropped_steps,
        sample_status_counts={k: int(v) for k, v in sample_status_counts.items()},
        output_path=output_path,
    )
    return result, debug_lines


def run_adaptation(
    input_batch_dir: Path,
    output_batch_dir: Path,
    config: AdaptationConfig,
) -> Dict[str, Any]:
    batch_summary_path = input_batch_dir / "batch.summary.json"
    if not batch_summary_path.exists():
        raise FileNotFoundError(f"Missing required batch summary: {batch_summary_path}")

    batch_summary = load_json(batch_summary_path)
    episode_paths = discover_episode_files(input_batch_dir)
    if not episode_paths:
        raise RuntimeError(f"No episode_*.npz files found in {input_batch_dir}")

    source_branch_sizes = infer_source_branch_sizes(input_batch_dir, batch_summary, episode_paths[0])
    hp_divisor, res_divisor = compute_channel_divisors(
        episode_paths,
        hp_override=config.hp_divisor,
        res_override=config.resource_divisor,
    )

    output_batch_dir.mkdir(parents=True, exist_ok=True)

    report = ConversionReportBuilder(
        input_batch_dir=input_batch_dir,
        output_batch_dir=output_batch_dir,
        batch_summary=batch_summary,
        source_branch_sizes=source_branch_sizes,
        hp_divisor=hp_divisor,
        resource_divisor=res_divisor,
    )
    report.input_batch_kind = classify_input_batch_kind(batch_summary.get("policy_source_id"))

    episode_results: List[EpisodeAdaptResult] = []
    debug_records: List[Dict[str, Any]] = []

    for episode_path in episode_paths:
        ep_result, ep_debug = adapt_episode(
            episode_path=episode_path,
            output_dir=output_batch_dir,
            report=report,
            config=config,
        )
        episode_results.append(ep_result)
        debug_records.extend(ep_debug)

    converted_npz = [str(item.output_path) for item in episode_results if item.output_path is not None]

    debug_jsonl_path: Optional[Path] = None
    if config.write_debug_jsonl:
        debug_jsonl_path = output_batch_dir / "conversion_debug.jsonl"
        with debug_jsonl_path.open("w", encoding="utf-8") as handle:
            for line in debug_records:
                handle.write(json.dumps(line, ensure_ascii=True))
                handle.write("\n")

    report_payload = report.build(
        episode_results=episode_results,
        npz_outputs=converted_npz,
        debug_jsonl=str(debug_jsonl_path) if debug_jsonl_path else None,
    )
    write_json(output_batch_dir / "conversion_report.json", report_payload)

    index_payload = {
        "status": "success",
        "input_batch_dir": str(input_batch_dir),
        "input_batch_kind": report.input_batch_kind,
        "output_batch_dir": str(output_batch_dir),
        "converted_episode_files": converted_npz,
        "conversion_report_path": str(output_batch_dir / "conversion_report.json"),
        "conversion_debug_jsonl_path": str(debug_jsonl_path) if debug_jsonl_path else None,
    }
    write_json(output_batch_dir / "adapted_batch.summary.json", index_payload)

    return index_payload
