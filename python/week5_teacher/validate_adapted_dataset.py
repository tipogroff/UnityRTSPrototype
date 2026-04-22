#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np


EXPECTED_OBS_SHAPE = (24, 24, 27)
EXPECTED_ACTION_SHAPE = (576, 7)
EXPECTED_ACTION_BRANCH_SIZES = (6, 4, 4, 4, 4, 4, 9)

OBS_ONE_HOT_SLICES = {
    "owner": (2, 5),
    "unit_type": (5, 12),
    "current_action": (12, 18),
    "action_direction": (18, 22),
    "produce_unit_type": (22, 26),
}

# Explicit spec-driven policy for channel slice validation.
# failure_level controls how violations are emitted: hard_failure or warning.
# spec_assumption marks rules that are not treated as absolute hard contract truth.
CHANNEL_VALIDATION_RULES: Dict[str, Dict[str, Any]] = {
    "owner": {
        "channel_range": (2, 5),
        "encoding_type": "one_hot_strict",
        "failure_level": "hard_failure",
        "spec_basis": "ObservationContract owner one-hot channels [2..4]",
        "spec_assumption": False,
    },
    "unit_type": {
        "channel_range": (5, 12),
        "encoding_type": "categorical_soft",
        "failure_level": "warning",
        "spec_basis": "ObservationContract unit_type block [5..11]",
        "spec_assumption": True,
    },
    "current_action": {
        "channel_range": (12, 18),
        "encoding_type": "categorical_soft",
        "failure_level": "warning",
        "spec_basis": "ObservationContract current_action block [12..17]",
        "spec_assumption": True,
    },
    "action_direction": {
        "channel_range": (18, 22),
        "encoding_type": "one_hot_strict",
        "failure_level": "hard_failure",
        "spec_basis": "ObservationContract action_direction one-hot channels [18..21]",
        "spec_assumption": False,
    },
    "produce_unit_type": {
        "channel_range": (22, 26),
        "encoding_type": "one_hot_strict",
        "failure_level": "hard_failure",
        "spec_basis": "ObservationContract produce_unit_type one-hot channels [22..25]",
        "spec_assumption": False,
    },
}

INACTIVE_BRANCH_SEVERITY_THRESHOLDS = {
    "high": 0.10,
    "medium": 0.03,
}

OBS_ATTACK_ALLOWED_VALUES = np.asarray([0.0] + [float(i + 1) / 9.0 for i in range(9)], dtype=np.float32)
DEFAULT_TOL = 1e-5


@dataclass
class EpisodeStats:
    episode_file: str
    episode_id: int
    steps: int
    action_type_histogram: Dict[str, int]
    attack_actions: int
    produce_actions: int
    inactive_branch_anomaly_count: int
    inactive_branch_anomaly_share: float
    hard_failure_count: int
    warning_count: int


@dataclass
class DebugEpisodeDiagnostics:
    episode_id: int
    total_steps: int = 0
    weakened_steps: int = 0
    dropped_steps: int = 0
    remap_to_noop_count: int = 0
    warning_reason_counts: Counter = None

    def __post_init__(self) -> None:
        if self.warning_reason_counts is None:
            self.warning_reason_counts = Counter()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Week 5 Day 5 validator: strict contract-level validation and sanity checks "
            "for Day 4 adapted teacher dataset artifacts."
        )
    )
    parser.add_argument(
        "--adapted-batch-dir",
        type=Path,
        required=True,
        help="Path to adapted batch directory with episode_*.adapted.npz, conversion_report.json, adapted_batch.summary.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Where to write Day 5 artifacts. Defaults to --adapted-batch-dir.",
    )
    parser.add_argument(
        "--sample-episodes",
        type=int,
        default=3,
        help="How many episodes to include in sanity sample section.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero exit code if any hard contract failures are found.",
    )
    return parser.parse_args()


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def safe_div(numerator: float, denominator: float) -> float:
    if denominator <= 0.0:
        return 0.0
    return float(numerator) / float(denominator)


def add_failure(failures: List[Dict[str, Any]], check: str, detail: str, context: Dict[str, Any] | None = None) -> None:
    entry: Dict[str, Any] = {"check": check, "detail": detail}
    if context:
        entry["context"] = context
    failures.append(entry)


def add_warning(warnings: List[Dict[str, Any]], check: str, detail: str, context: Dict[str, Any] | None = None) -> None:
    entry: Dict[str, Any] = {"check": check, "detail": detail}
    if context:
        entry["context"] = context
    warnings.append(entry)


def register_issue_by_level(
    *,
    level: str,
    failures: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]],
    check: str,
    detail: str,
    context: Dict[str, Any] | None = None,
) -> str:
    if level == "hard_failure":
        add_failure(failures, check, detail, context)
        return "hard_failure"
    add_warning(warnings, check, detail, context)
    return "warning"


def check_contract_metadata(
    conversion_report: Dict[str, Any],
    failures: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]],
) -> None:
    contract = conversion_report.get("contract", {})
    target_obs_shape = tuple(contract.get("target_observation_shape", []))
    if target_obs_shape != EXPECTED_OBS_SHAPE:
        add_failure(
            failures,
            "metadata.observation_contract",
            "conversion_report target_observation_shape mismatch",
            {"expected": list(EXPECTED_OBS_SHAPE), "actual": list(target_obs_shape)},
        )

    target_action_shape = tuple(contract.get("target_action_shape_per_step", []))
    if target_action_shape != EXPECTED_ACTION_SHAPE:
        add_failure(
            failures,
            "metadata.action_shape_contract",
            "conversion_report target_action_shape_per_step mismatch",
            {"expected": list(EXPECTED_ACTION_SHAPE), "actual": list(target_action_shape)},
        )

    target_branch_sizes = tuple(contract.get("target_action_branch_sizes", []))
    if target_branch_sizes != EXPECTED_ACTION_BRANCH_SIZES:
        add_failure(
            failures,
            "metadata.action_branch_contract",
            "conversion_report target_action_branch_sizes mismatch",
            {"expected": list(EXPECTED_ACTION_BRANCH_SIZES), "actual": list(target_branch_sizes)},
        )

    global_vector_policy = str(contract.get("global_vector_policy", "")).strip()
    if global_vector_policy != "excluded_from_strict_bc_encoder_path":
        add_failure(
            failures,
            "metadata.global_vector_policy",
            "global vector exclusion policy not explicitly enforced",
            {"actual": global_vector_policy},
        )

    policy_rule = conversion_report.get("policy_rules", {}).get("global_vector_excluded_from_strict_bc_path", {})
    if not bool(policy_rule.get("enforced", False)):
        add_failure(
            failures,
            "metadata.policy_rules.global_vector_excluded",
            "policy_rules.global_vector_excluded_from_strict_bc_path.enforced must be true",
            {"actual": policy_rule},
        )

    notes = conversion_report.get("notes", [])
    parity_note_present = any("No semantic parity claim" in str(note) for note in notes)
    if not parity_note_present:
        add_warning(
            warnings,
            "metadata.parity_scope_note",
            "conversion_report notes do not explicitly mention non-parity scope",
        )


def validate_one_hot_slice(values: np.ndarray, tol: float) -> Tuple[int, int]:
    sums = np.sum(values, axis=-1)
    sum_valid = (np.abs(sums) <= tol) | (np.abs(sums - 1.0) <= tol)

    near_zero = np.abs(values) <= tol
    near_one = np.abs(values - 1.0) <= tol
    binary_valid = np.all(near_zero | near_one, axis=-1)

    invalid_sum_count = int(np.count_nonzero(~sum_valid))
    invalid_binary_count = int(np.count_nonzero(~binary_valid))
    return invalid_sum_count, invalid_binary_count


def validate_attack_observation_channel(channel: np.ndarray, tol: float) -> int:
    distance = np.abs(channel[..., None] - OBS_ATTACK_ALLOWED_VALUES[None, :])
    nearest = np.min(distance, axis=-1)
    return int(np.count_nonzero(nearest > tol))


def validate_categorical_soft_slice(values: np.ndarray, tol: float) -> Tuple[int, int]:
    sums = np.sum(values, axis=-1)
    invalid_negative_count = int(np.count_nonzero(values < -tol))
    invalid_above_one_count = int(np.count_nonzero(values > 1.0 + tol))
    invalid_sum_high_count = int(np.count_nonzero(sums > 1.0 + tol))
    return invalid_negative_count + invalid_above_one_count, invalid_sum_high_count


def validate_inactive_branches(actions: np.ndarray) -> Dict[str, int]:
    action_type = actions[..., 0]
    branch_nonzero: Dict[str, int] = {}

    def count_nonzero_for(action_id: int, branch_index: int, label: str) -> None:
        mask = action_type == action_id
        if np.count_nonzero(mask) == 0:
            return
        count = int(np.count_nonzero(actions[..., branch_index][mask] != 0))
        if count > 0:
            branch_nonzero[label] = count

    for branch_idx in (1, 2, 3, 4, 5, 6):
        count_nonzero_for(0, branch_idx, f"noop.branch_{branch_idx}_nonzero")

    for branch_idx in (2, 3, 4, 5, 6):
        count_nonzero_for(1, branch_idx, f"move.branch_{branch_idx}_nonzero")

    for branch_idx in (1, 3, 4, 5, 6):
        count_nonzero_for(2, branch_idx, f"harvest.branch_{branch_idx}_nonzero")

    for branch_idx in (1, 2, 4, 5, 6):
        count_nonzero_for(3, branch_idx, f"return.branch_{branch_idx}_nonzero")

    for branch_idx in (1, 2, 3, 6):
        count_nonzero_for(4, branch_idx, f"produce.branch_{branch_idx}_nonzero")

    for branch_idx in (1, 2, 3, 4, 5):
        count_nonzero_for(5, branch_idx, f"attack.branch_{branch_idx}_nonzero")

    return branch_nonzero


def inactive_branch_severity(share: float) -> str:
    if share >= INACTIVE_BRANCH_SEVERITY_THRESHOLDS["high"]:
        return "high"
    if share >= INACTIVE_BRANCH_SEVERITY_THRESHOLDS["medium"]:
        return "medium"
    return "low"


def extract_remap_to_noop_count_from_cell_stats(stats: Dict[str, Any]) -> int:
    if not isinstance(stats, dict):
        return 0
    keys = (
        "unsupported_action_type_to_noop",
        "invalid_produce_type_to_noop",
        "unsupported_produce_type_to_noop",
        "attack_target_outside_local_3x3_to_noop",
        "invalid_move_dir_to_noop",
        "invalid_harvest_dir_to_noop",
        "invalid_return_dir_to_noop",
        "invalid_produce_dir_to_noop",
    )
    total = 0
    for key in keys:
        total += int(stats.get(key, 0) or 0)
    return total


def parse_conversion_debug_jsonl(path: Path) -> Dict[int, DebugEpisodeDiagnostics]:
    diagnostics: Dict[int, DebugEpisodeDiagnostics] = {}
    if not path.exists():
        return diagnostics

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue

            episode_id = int(payload.get("episode_id", -1))
            if episode_id < 0:
                continue
            item = diagnostics.setdefault(episode_id, DebugEpisodeDiagnostics(episode_id=episode_id))
            item.total_steps += 1

            sample_status = str(payload.get("sample_status", ""))
            semantic_quality = str(payload.get("semantic_quality", ""))
            if sample_status == "dropped":
                item.dropped_steps += 1
            if semantic_quality == "weakened":
                item.weakened_steps += 1

            action_cell_stats = payload.get("action_cell_stats", {})
            item.remap_to_noop_count += extract_remap_to_noop_count_from_cell_stats(action_cell_stats)

            for reason in payload.get("reasons", []):
                item.warning_reason_counts[str(reason)] += 1

    return diagnostics


def build_markdown_summary(
    strict_payload: Dict[str, Any],
    quality_payload: Dict[str, Any],
    output_path: Path,
) -> None:
    hard_failures = strict_payload["validation"]["hard_failures"]
    warnings = strict_payload["validation"]["warnings"]
    quality = quality_payload["quality"]
    sanity = quality_payload["sanity"]
    inactive_branch = quality_payload["quality"].get("inactive_branch_anomalies", {})
    bc_readiness = quality_payload.get("bc_readiness_interpretation", {})

    lines: List[str] = []
    lines.append("# Day 5 Adapted Dataset Validation Summary")
    lines.append("")
    lines.append(f"- Adapted batch dir: {strict_payload['run']['adapted_batch_dir']}")
    lines.append(f"- Validation status: {strict_payload['validation']['status']}")
    lines.append(f"- Hard failures: {len(hard_failures)}")
    lines.append(f"- Warnings: {len(warnings)}")
    lines.append("")
    lines.append("## Quality Snapshot")
    lines.append("")
    lines.append(f"- Usable samples: {quality['usable_samples']}")
    lines.append(f"- Dropped samples: {quality['dropped_samples']}")
    lines.append(f"- Conversion loss share: {quality['conversion_loss_share']:.6f}")
    lines.append(f"- Remap-to-noop share: {quality['remap_to_noop_share']:.6f}")
    lines.append(f"- Semantic weakening share: {quality['semantic_weakening_share']:.6f}")
    lines.append(f"- Observation signal loss share: {quality['observation_signal_loss_share']:.6f}")
    lines.append(f"- Usable vs dropped ratio: {quality['usable_vs_dropped_ratio']:.6f}")
    lines.append(f"- Inactive branch anomaly share: {inactive_branch.get('inactive_branch_anomaly_share', 0.0):.6f}")
    lines.append(f"- Inactive branch warning severity: {inactive_branch.get('inactive_branch_warning_severity', 'low')}")
    lines.append("")
    lines.append("## Action Distribution")
    lines.append("")
    for action_id, count in sanity["action_type_distribution"].items():
        lines.append(f"- action_type={action_id}: {count}")
    lines.append(f"- Imbalance ratio (max/min non-zero share): {quality['class_imbalance']['imbalance_ratio_max_to_min_nonzero']:.6f}")
    lines.append("")
    lines.append("## Weak Spots")
    lines.append("")
    for item in quality["main_weak_spots_detected"]:
        lines.append(f"- {item}")

    episode_diag = sanity.get("episode_level_diagnostics", {})
    top_problematic = episode_diag.get("top_problematic_episodes", [])
    if top_problematic:
        lines.append("")
        lines.append("## Top Problematic Episodes")
        lines.append("")
        for item in top_problematic:
            lines.append(
                "- episode_id={episode_id}, score={score:.4f}, remap_share={remap_share:.6f}, weakened_share={weakened_share:.6f}, dropped_share={dropped_share:.6f}".format(
                    episode_id=item.get("episode_id"),
                    score=float(item.get("problem_score", 0.0)),
                    remap_share=float(item.get("action_remap_concentration", {}).get("remap_to_noop_share_per_action_cell", 0.0)),
                    weakened_share=float(item.get("semantic_weakening", {}).get("weakened_step_share", 0.0)),
                    dropped_share=float(item.get("dropped_step_share", 0.0)),
                )
            )

    if hard_failures:
        lines.append("")
        lines.append("## Hard Failures")
        lines.append("")
        for item in hard_failures:
            lines.append(f"- {item['check']}: {item['detail']}")

    if warnings:
        lines.append("")
        lines.append("## Warnings")
        lines.append("")
        for item in warnings:
            lines.append(f"- {item['check']}: {item['detail']}")

    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append("- This validator proves contract-level consistency and sanity metrics only.")
    lines.append("- It does not prove full Gym<->Unity semantic parity and does not replace BC evaluation.")

    if bc_readiness:
        lines.append("")
        lines.append("## BC Readiness Interpretation")
        lines.append("")
        for text in bc_readiness.get("day5_proves", []):
            lines.append(f"- Proves: {text}")
        for text in bc_readiness.get("day5_does_not_prove", []):
            lines.append(f"- Does not prove: {text}")
        for text in bc_readiness.get("next_decision_options", []):
            lines.append(f"- Next decision option: {text}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()

    adapted_batch_dir = args.adapted_batch_dir.resolve()
    output_dir = (args.output_dir.resolve() if args.output_dir else adapted_batch_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    conversion_report_path = adapted_batch_dir / "conversion_report.json"
    adapted_summary_path = adapted_batch_dir / "adapted_batch.summary.json"
    episode_paths = sorted(adapted_batch_dir.glob("episode_*.adapted.npz"))

    hard_failures: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    if not conversion_report_path.exists():
        add_failure(hard_failures, "input.conversion_report", "Missing conversion_report.json")
    if not adapted_summary_path.exists():
        add_failure(hard_failures, "input.adapted_batch_summary", "Missing adapted_batch.summary.json")
    if not episode_paths:
        add_failure(hard_failures, "input.episodes", "No episode_*.adapted.npz files found")

    if hard_failures:
        strict_payload = {
            "run": {
                "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "adapted_batch_dir": str(adapted_batch_dir),
                "output_dir": str(output_dir),
            },
            "validation": {
                "status": "hard_fail",
                "hard_failures": hard_failures,
                "warnings": warnings,
            },
        }
        strict_path = output_dir / "strict_validation_day5.json"
        write_json(strict_path, strict_payload)
        print(f"Validation failed before dataset scan. See: {strict_path}")
        return 2 if args.strict else 0

    conversion_report = read_json(conversion_report_path)
    adapted_summary = read_json(adapted_summary_path)

    channel_validation_policy = {
        name: {
            "encoding_type": str(rule.get("encoding_type", "unchecked")),
            "failure_level": str(rule.get("failure_level", "warning")),
            "channel_range": list(rule.get("channel_range", ())),
            "spec_basis": str(rule.get("spec_basis", "")),
            "spec_assumption": bool(rule.get("spec_assumption", False)),
        }
        for name, rule in CHANNEL_VALIDATION_RULES.items()
    }

    check_contract_metadata(conversion_report, hard_failures, warnings)

    total_steps = 0
    total_action_cells = 0
    action_type_hist = np.zeros(EXPECTED_ACTION_BRANCH_SIZES[0], dtype=np.int64)
    attack_actions = 0
    produce_actions = 0

    episode_stats: List[EpisodeStats] = []
    warning_pattern_counts: Counter = Counter()
    inactive_branch_anomaly_counts: Counter = Counter()
    total_inactive_branch_anomaly_count = 0

    conversion_debug_jsonl_path = Path(str(adapted_summary.get("conversion_debug_jsonl_path"))) if adapted_summary.get("conversion_debug_jsonl_path") else None
    debug_episode_diagnostics = parse_conversion_debug_jsonl(conversion_debug_jsonl_path) if conversion_debug_jsonl_path else {}

    episode_contract_hard_counts: Dict[str, int] = {}
    episode_contract_warning_counts: Dict[str, int] = {}

    policy_semantics = {
        "observation_contract_consistency": True,
        "global_vector_excluded_rule_respected": True,
        "action_decoder_assumption_consistency": True,
        "mask_semantics_treated_as_diagnostic_only": True,
    }

    for episode_path in episode_paths:
        with np.load(episode_path, allow_pickle=True) as data:
            episode_hard_before = len(hard_failures)
            episode_warn_before = len(warnings)
            required_keys = {
                "episode_id",
                "step_id",
                "observation_adapted",
                "action_adapted",
                "reward_t",
                "done_t",
            }
            keys = set(data.files)
            missing_keys = sorted(required_keys - keys)
            if missing_keys:
                add_failure(
                    hard_failures,
                    "episode.keys.required",
                    "Missing required keys in adapted NPZ",
                    {"episode_file": episode_path.name, "missing_keys": missing_keys},
                )
                continue

            global_like_keys = sorted(k for k in keys if "global" in k.lower())
            if global_like_keys:
                add_failure(
                    hard_failures,
                    "observation.global_vector_excluded",
                    "Detected unexpected global-like keys in adapted NPZ",
                    {"episode_file": episode_path.name, "keys": global_like_keys},
                )
                policy_semantics["global_vector_excluded_rule_respected"] = False

            step_id = np.asarray(data["step_id"], dtype=np.int64)
            obs = np.asarray(data["observation_adapted"])
            act = np.asarray(data["action_adapted"])
            reward_t = np.asarray(data["reward_t"], dtype=np.float32)
            done_t = np.asarray(data["done_t"], dtype=np.bool_)

            step_count = int(step_id.shape[0])
            if obs.shape != (step_count,) + EXPECTED_OBS_SHAPE:
                add_failure(
                    hard_failures,
                    "observation.shape",
                    "observation_adapted shape mismatch",
                    {
                        "episode_file": episode_path.name,
                        "expected": [step_count] + list(EXPECTED_OBS_SHAPE),
                        "actual": list(obs.shape),
                    },
                )
                policy_semantics["observation_contract_consistency"] = False

            if act.shape != (step_count,) + EXPECTED_ACTION_SHAPE:
                add_failure(
                    hard_failures,
                    "action.shape",
                    "action_adapted shape mismatch",
                    {
                        "episode_file": episode_path.name,
                        "expected": [step_count] + list(EXPECTED_ACTION_SHAPE),
                        "actual": list(act.shape),
                    },
                )
                policy_semantics["action_decoder_assumption_consistency"] = False

            if reward_t.shape != (step_count,):
                add_failure(
                    hard_failures,
                    "reward.shape",
                    "reward_t shape mismatch",
                    {"episode_file": episode_path.name, "expected": [step_count], "actual": list(reward_t.shape)},
                )

            if done_t.shape != (step_count,):
                add_failure(
                    hard_failures,
                    "done.shape",
                    "done_t shape mismatch",
                    {"episode_file": episode_path.name, "expected": [step_count], "actual": list(done_t.shape)},
                )

            if step_count > 0:
                expected_step_id = np.arange(step_id[0], step_id[0] + step_count, dtype=np.int64)
                if np.any(step_id != expected_step_id):
                    add_failure(
                        hard_failures,
                        "episode.step_id_contiguous",
                        "step_id sequence is not contiguous",
                        {"episode_file": episode_path.name},
                    )

            if not np.issubdtype(obs.dtype, np.floating):
                add_failure(
                    hard_failures,
                    "observation.dtype",
                    "observation_adapted must be float",
                    {"episode_file": episode_path.name, "dtype": str(obs.dtype)},
                )

            if not np.issubdtype(act.dtype, np.integer):
                rounded = np.round(act)
                if np.any(np.abs(act - rounded) > DEFAULT_TOL):
                    add_failure(
                        hard_failures,
                        "action.integrality",
                        "action_adapted contains non-integer values",
                        {"episode_file": episode_path.name, "dtype": str(act.dtype)},
                    )
                    policy_semantics["action_decoder_assumption_consistency"] = False
                act = rounded.astype(np.int64)
            else:
                act = act.astype(np.int64, copy=False)

            if np.any(~np.isfinite(obs)):
                add_failure(
                    hard_failures,
                    "observation.finite",
                    "observation_adapted contains NaN or Inf",
                    {"episode_file": episode_path.name},
                )

            if np.any(~np.isfinite(reward_t)):
                add_failure(
                    hard_failures,
                    "reward.finite",
                    "reward_t contains NaN or Inf",
                    {"episode_file": episode_path.name},
                )

            if obs.size > 0:
                obs_min = float(np.min(obs))
                obs_max = float(np.max(obs))
                if obs_min < -DEFAULT_TOL or obs_max > 1.0 + DEFAULT_TOL:
                    add_failure(
                        hard_failures,
                        "observation.range",
                        "observation_adapted values out of [0,1]",
                        {"episode_file": episode_path.name, "min": obs_min, "max": obs_max},
                    )
                    policy_semantics["observation_contract_consistency"] = False

            if obs.shape == (step_count,) + EXPECTED_OBS_SHAPE and step_count > 0:
                for slice_name, rule in CHANNEL_VALIDATION_RULES.items():
                    start_idx, end_idx = tuple(rule.get("channel_range", (0, 0)))
                    encoding_type = str(rule.get("encoding_type", "unchecked"))
                    failure_level = str(rule.get("failure_level", "warning"))
                    slice_values = obs[..., start_idx:end_idx]
                    if encoding_type == "one_hot_strict":
                        invalid_sum_count, invalid_binary_count = validate_one_hot_slice(slice_values, tol=DEFAULT_TOL)
                        if invalid_sum_count > 0:
                            register_issue_by_level(
                                level=failure_level,
                                failures=hard_failures,
                                warnings=warnings,
                                check=f"observation.one_hot_sum.{slice_name}",
                                detail="one-hot slice has invalid sum (must be 0 or 1)",
                                context={
                                    "episode_file": episode_path.name,
                                    "invalid_count": invalid_sum_count,
                                    "encoding_type": encoding_type,
                                    "spec_assumption": bool(rule.get("spec_assumption", False)),
                                },
                            )
                            if failure_level == "hard_failure":
                                policy_semantics["observation_contract_consistency"] = False
                        if invalid_binary_count > 0:
                            register_issue_by_level(
                                level=failure_level,
                                failures=hard_failures,
                                warnings=warnings,
                                check=f"observation.one_hot_binary.{slice_name}",
                                detail="one-hot slice has non-binary values",
                                context={
                                    "episode_file": episode_path.name,
                                    "invalid_count": invalid_binary_count,
                                    "encoding_type": encoding_type,
                                    "spec_assumption": bool(rule.get("spec_assumption", False)),
                                },
                            )
                            if failure_level == "hard_failure":
                                policy_semantics["observation_contract_consistency"] = False
                    elif encoding_type == "categorical_soft":
                        invalid_range_count, invalid_sum_high_count = validate_categorical_soft_slice(slice_values, tol=DEFAULT_TOL)
                        if invalid_range_count > 0:
                            register_issue_by_level(
                                level=failure_level,
                                failures=hard_failures,
                                warnings=warnings,
                                check=f"observation.categorical_soft_range.{slice_name}",
                                detail="categorical_soft slice has values outside [0,1] tolerance",
                                context={
                                    "episode_file": episode_path.name,
                                    "invalid_count": invalid_range_count,
                                    "encoding_type": encoding_type,
                                    "spec_assumption": bool(rule.get("spec_assumption", False)),
                                },
                            )
                        if invalid_sum_high_count > 0:
                            register_issue_by_level(
                                level=failure_level,
                                failures=hard_failures,
                                warnings=warnings,
                                check=f"observation.categorical_soft_sum.{slice_name}",
                                detail="categorical_soft slice sum exceeds 1; potential multi-hot overlap",
                                context={
                                    "episode_file": episode_path.name,
                                    "invalid_count": invalid_sum_high_count,
                                    "encoding_type": encoding_type,
                                    "spec_assumption": bool(rule.get("spec_assumption", False)),
                                },
                            )

                attack_channel = obs[..., 26]
                invalid_attack_obs = validate_attack_observation_channel(attack_channel, tol=2e-3)
                if invalid_attack_obs > 0:
                    add_failure(
                        hard_failures,
                        "observation.attack_target_encoding",
                        "attack_target observation channel is outside allowed encoded values",
                        {"episode_file": episode_path.name, "invalid_count": invalid_attack_obs},
                    )
                    policy_semantics["observation_contract_consistency"] = False

            if act.shape == (step_count,) + EXPECTED_ACTION_SHAPE and step_count > 0:
                branch_limits = {
                    0: EXPECTED_ACTION_BRANCH_SIZES[0],
                    1: EXPECTED_ACTION_BRANCH_SIZES[1],
                    2: EXPECTED_ACTION_BRANCH_SIZES[2],
                    3: EXPECTED_ACTION_BRANCH_SIZES[3],
                    4: EXPECTED_ACTION_BRANCH_SIZES[4],
                    5: EXPECTED_ACTION_BRANCH_SIZES[5],
                    6: EXPECTED_ACTION_BRANCH_SIZES[6],
                }

                for branch_idx, branch_size in branch_limits.items():
                    branch = act[..., branch_idx]
                    invalid = int(np.count_nonzero((branch < 0) | (branch >= branch_size)))
                    if invalid > 0:
                        add_failure(
                            hard_failures,
                            f"action.branch_range.{branch_idx}",
                            "branch values are outside allowed range",
                            {
                                "episode_file": episode_path.name,
                                "branch": branch_idx,
                                "branch_size": branch_size,
                                "invalid_count": invalid,
                            },
                        )
                        policy_semantics["action_decoder_assumption_consistency"] = False

                inactive_branch_nonzero = validate_inactive_branches(act)
                if inactive_branch_nonzero:
                    local_inactive_count = int(sum(int(v) for v in inactive_branch_nonzero.values()))
                    total_inactive_branch_anomaly_count += local_inactive_count
                    for key, value in inactive_branch_nonzero.items():
                        inactive_branch_anomaly_counts[str(key)] += int(value)
                        warning_pattern_counts[f"inactive_branch:{key}"] += int(value)
                    add_warning(
                        warnings,
                        "action.inactive_branch_nonzero",
                        "inactive branches contain non-zero values (decoder should ignore them, but this is non-canonical)",
                        {
                            "episode_file": episode_path.name,
                            "counts": inactive_branch_nonzero,
                            "local_anomaly_count": local_inactive_count,
                        },
                    )
                else:
                    local_inactive_count = 0

                action_type_flat = act[..., 0].reshape(-1)
                hist = np.bincount(action_type_flat, minlength=EXPECTED_ACTION_BRANCH_SIZES[0])
                action_type_hist += hist[: EXPECTED_ACTION_BRANCH_SIZES[0]]
                attack_actions += int(np.count_nonzero(action_type_flat == 5))
                produce_actions += int(np.count_nonzero(action_type_flat == 4))
                per_episode_hist = {str(i): int(hist[i]) for i in range(EXPECTED_ACTION_BRANCH_SIZES[0])}
                per_episode_attack_actions = int(np.count_nonzero(action_type_flat == 5))
                per_episode_produce_actions = int(np.count_nonzero(action_type_flat == 4))
            else:
                per_episode_hist = {str(i): 0 for i in range(EXPECTED_ACTION_BRANCH_SIZES[0])}
                per_episode_attack_actions = 0
                per_episode_produce_actions = 0

            total_steps += step_count
            total_action_cells += step_count * EXPECTED_ACTION_SHAPE[0]

            episode_id = int(np.asarray(data["episode_id"]).reshape(-1)[0]) if step_count >= 0 else -1
            episode_hard_after = len(hard_failures)
            episode_warn_after = len(warnings)
            episode_contract_hard_counts[episode_path.name] = max(0, episode_hard_after - episode_hard_before)
            episode_contract_warning_counts[episode_path.name] = max(0, episode_warn_after - episode_warn_before)

            local_inactive_share = safe_div(float(local_inactive_count), float(max(step_count * EXPECTED_ACTION_SHAPE[0], 1)))
            episode_stats.append(
                EpisodeStats(
                    episode_file=episode_path.name,
                    episode_id=episode_id,
                    steps=step_count,
                    action_type_histogram=per_episode_hist,
                    attack_actions=per_episode_attack_actions,
                    produce_actions=per_episode_produce_actions,
                    inactive_branch_anomaly_count=local_inactive_count,
                    inactive_branch_anomaly_share=local_inactive_share,
                    hard_failure_count=episode_contract_hard_counts.get(episode_path.name, 0),
                    warning_count=episode_contract_warning_counts.get(episode_path.name, 0),
                )
            )

    counters = conversion_report.get("counters", {})
    sample_counters = counters.get("samples", {})
    semantic_weakening = counters.get("semantic_weakening", {})
    obs_counters = counters.get("observation", {})
    action_hist_report = conversion_report.get("action_histograms", {})

    total_samples_report = int(sample_counters.get("total", total_steps))
    dropped_samples = int(sample_counters.get("dropped", 0))
    usable_samples = max(0, total_samples_report - dropped_samples)

    remapped_to_noop_count = int(semantic_weakening.get("remapped_to_noop_count", 0))
    semantically_weak_action_count = int(semantic_weakening.get("semantically_weak_action_count", 0))
    signal_loss_events = int(obs_counters.get("signal_loss_events", 0))

    input_hist = {str(k): int(v) for k, v in action_hist_report.get("input_action_type", {}).items()}
    output_hist = {str(k): int(v) for k, v in action_hist_report.get("output_action_type", {}).items()}

    input_produce = int(input_hist.get("4", 0))
    output_produce = int(output_hist.get("4", int(action_type_hist[4])))

    distribution = {str(i): int(action_type_hist[i]) for i in range(EXPECTED_ACTION_BRANCH_SIZES[0])}
    total_actions = int(np.sum(action_type_hist))
    shares = {
        str(i): safe_div(float(action_type_hist[i]), float(total_actions))
        for i in range(EXPECTED_ACTION_BRANCH_SIZES[0])
    }
    nonzero_shares = [value for value in shares.values() if value > 0.0]
    imbalance_ratio = safe_div(max(nonzero_shares) if nonzero_shares else 0.0, min(nonzero_shares) if nonzero_shares else 1.0)

    if remapped_to_noop_count > 0:
        add_warning(
            warnings,
            "quality.semantic_weakening",
            "conversion includes remap-to-noop events (semantic weakening present)",
            {"remapped_to_noop_count": remapped_to_noop_count},
        )
        warning_pattern_counts["quality:semantic_weakening"] += 1

    if dropped_samples > 0:
        add_warning(
            warnings,
            "quality.dropped_samples",
            "adapted dataset contains dropped samples",
            {"dropped_samples": dropped_samples},
        )
        warning_pattern_counts["quality:dropped_samples"] += 1

    total_contract_warning_count = len(warnings)
    total_contract_hard_failure_count = len(hard_failures)
    inactive_branch_anomaly_share = safe_div(float(total_inactive_branch_anomaly_count), float(max(total_action_cells, 1)))
    inactive_severity = inactive_branch_severity(inactive_branch_anomaly_share)

    debug_by_episode = {
        episode_id: item
        for episode_id, item in debug_episode_diagnostics.items()
    }

    episode_level_rows: List[Dict[str, Any]] = []
    for item in episode_stats:
        debug_item = debug_by_episode.get(item.episode_id)
        dropped_share = 0.0
        weakened_share = 0.0
        remap_share = 0.0
        top_reasons: List[Dict[str, Any]] = []
        if debug_item is not None and debug_item.total_steps > 0:
            dropped_share = safe_div(float(debug_item.dropped_steps), float(debug_item.total_steps))
            weakened_share = safe_div(float(debug_item.weakened_steps), float(debug_item.total_steps))
            remap_share = safe_div(
                float(debug_item.remap_to_noop_count),
                float(max(debug_item.total_steps * EXPECTED_ACTION_SHAPE[0], 1)),
            )
            top_reasons = [
                {"reason": reason, "count": int(count)}
                for reason, count in debug_item.warning_reason_counts.most_common(5)
            ]

        problem_score = (
            item.hard_failure_count * 3.0
            + item.warning_count * 1.0
            + remap_share * 10.0
            + weakened_share * 4.0
            + dropped_share * 5.0
            + item.inactive_branch_anomaly_share * 5.0
        )

        episode_level_rows.append(
            {
                "episode_file": item.episode_file,
                "episode_id": item.episode_id,
                "steps": item.steps,
                "contract_issues": {
                    "hard_failure_count": item.hard_failure_count,
                    "warning_count": item.warning_count,
                },
                "dropped_step_share": dropped_share,
                "semantic_weakening": {
                    "weakened_step_share": weakened_share,
                },
                "action_remap_concentration": {
                    "remap_to_noop_share_per_action_cell": remap_share,
                },
                "inactive_branch_anomaly": {
                    "count": item.inactive_branch_anomaly_count,
                    "share": item.inactive_branch_anomaly_share,
                },
                "top_warning_reasons": top_reasons,
                "problem_score": problem_score,
            }
        )

    top_problematic_episodes = sorted(
        episode_level_rows,
        key=lambda row: float(row.get("problem_score", 0.0)),
        reverse=True,
    )[:5]

    top_warning_patterns = [
        {"pattern": key, "count": int(value)}
        for key, value in warning_pattern_counts.most_common(10)
    ]

    bc_readiness_interpretation = {
        "day5_proves": [
            "Adapted dataset was checked for contract-level structural consistency against explicit Day5 validation policy.",
            "Hard contract failures and soft warnings are separated and reproducible.",
            "Batch-level and limited episode-level diagnostics are available for next decision point.",
        ],
        "day5_does_not_prove": [
            "No BC training quality guarantee or policy performance guarantee is established.",
            "No full Gym<->Unity semantic parity is proven by this validator.",
            "No Unity runtime behavior equivalence claim is made.",
        ],
        "next_decision_options": [
            "Run the same validator on newer stronger adapted teacher batches.",
            "If hard failures remain, fix adapter/contract assumptions before BC smoke.",
            "If hard failures are resolved, proceed with a short BC smoke in a separate stage.",
        ],
    }

    quality_main_weak_spots: List[str] = []
    if remapped_to_noop_count > 0:
        quality_main_weak_spots.append("High remap-to-noop volume indicates semantic weakening pressure from source-to-target action gap.")
    if safe_div(float(output_produce), float(max(input_produce, 1))) < 0.8:
        quality_main_weak_spots.append("Produce actions survival share is limited; conversion keeps only MVP subset semantics.")
    if safe_div(float(action_type_hist[5]), float(max(total_actions, 1))) < 0.05:
        quality_main_weak_spots.append("Attack action share is low after conversion and may weaken combat supervision density.")
    if imbalance_ratio > 3.0:
        quality_main_weak_spots.append("Action class imbalance is strong and may require weighting/oversampling in BC.")
    if signal_loss_events > 0:
        quality_main_weak_spots.append("Observation signal-loss events detected during conversion.")

    if inactive_severity in ("medium", "high"):
        quality_main_weak_spots.append(
            f"Inactive-branch anomalies are {inactive_severity} severity and should be monitored before BC."
        )

    if not quality_main_weak_spots:
        quality_main_weak_spots.append("No dominant weak spot detected in this batch-level sanity scan.")

    validation_status = "pass" if not hard_failures else "hard_fail"

    strict_payload: Dict[str, Any] = {
        "run": {
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "adapted_batch_dir": str(adapted_batch_dir),
            "output_dir": str(output_dir),
            "based_on_current_available_meaningful_batch": True,
            "ongoing_long_teacher_training_not_blocking_this_run": True,
        },
        "validation": {
            "status": validation_status,
            "hard_failures": hard_failures,
            "warnings": warnings,
            "hard_checks_implemented": [
                "observation shape/value/finite/one-hot/attack-channel encoding",
                "action shape/branch sizes/branch ranges/attack local target range",
                "global vector excluded rule (metadata + NPZ key scan)",
                "policy-side contract consistency assumptions (no parity overclaim)",
            ],
            "channel_validation_policy": channel_validation_policy,
            "policy_side_semantics_checks": policy_semantics,
            "scope_statement": {
                "contract_level_consistency_only": True,
                "full_gym_unity_semantic_parity_proof": False,
                "mask_runtime_truth_claim": False,
            },
        },
    }

    quality_payload: Dict[str, Any] = {
        "run": strict_payload["run"],
        "quality": {
            "usable_samples": usable_samples,
            "dropped_samples": dropped_samples,
            "conversion_loss_share": safe_div(float(dropped_samples), float(max(total_samples_report, 1))),
            "usable_vs_dropped_ratio": safe_div(float(usable_samples), float(max(dropped_samples, 1))),
            "remap_to_noop_count": remapped_to_noop_count,
            "remap_to_noop_share": safe_div(float(remapped_to_noop_count), float(max(total_action_cells, 1))),
            "semantic_weakening_share": safe_div(float(semantically_weak_action_count), float(max(total_samples_report, 1))),
            "observation_signal_loss_share": safe_div(float(signal_loss_events), float(max(total_samples_report, 1))),
            "production_actions_survived_share": safe_div(float(output_produce), float(max(input_produce, 1))),
            "class_imbalance": {
                "distribution_share_by_action_type": shares,
                "imbalance_ratio_max_to_min_nonzero": imbalance_ratio,
            },
            "inactive_branch_anomalies": {
                "inactive_branch_anomaly_count": total_inactive_branch_anomaly_count,
                "inactive_branch_anomaly_share": inactive_branch_anomaly_share,
                "inactive_branch_warning_severity": inactive_severity,
                "inactive_branch_counts": {str(k): int(v) for k, v in sorted(inactive_branch_anomaly_counts.items())},
                "severity_thresholds": INACTIVE_BRANCH_SEVERITY_THRESHOLDS,
            },
            "main_weak_spots_detected": quality_main_weak_spots,
        },
        "sanity": {
            "episodes_scanned": len(episode_stats),
            "steps_scanned": total_steps,
            "action_type_distribution": distribution,
            "attack_local_target_cases": {
                "attack_action_count": int(attack_actions),
                "attack_action_share": safe_div(float(attack_actions), float(max(total_actions, 1))),
            },
            "produce_cases": {
                "produce_action_count": int(produce_actions),
                "produce_action_share": safe_div(float(produce_actions), float(max(total_actions, 1))),
            },
            "conversion_report_observed_gaps": counters.get("observed_gap_events", {}),
            "sampled_episodes": [
                {
                    "episode_file": item.episode_file,
                    "episode_id": item.episode_id,
                    "steps": item.steps,
                    "action_type_histogram": item.action_type_histogram,
                    "attack_actions": item.attack_actions,
                    "produce_actions": item.produce_actions,
                    "inactive_branch_anomaly_count": item.inactive_branch_anomaly_count,
                    "inactive_branch_anomaly_share": item.inactive_branch_anomaly_share,
                }
                for item in episode_stats[: max(0, args.sample_episodes)]
            ],
            "episode_level_diagnostics": {
                "episodes": episode_level_rows,
                "top_problematic_episodes": top_problematic_episodes,
                "top_warning_patterns": top_warning_patterns,
            },
        },
        "bc_readiness_interpretation": bc_readiness_interpretation,
    }

    strict_path = output_dir / "strict_validation_day5.json"
    quality_json_path = output_dir / "quality_report_day5.json"
    quality_md_path = output_dir / "quality_report_day5.md"

    write_json(strict_path, strict_payload)
    write_json(quality_json_path, quality_payload)
    build_markdown_summary(strict_payload, quality_payload, quality_md_path)

    print("Day 5 validation completed.")
    print(f"Strict validation: {strict_path}")
    print(f"Quality report JSON: {quality_json_path}")
    print(f"Quality report Markdown: {quality_md_path}")
    print(f"Validation status: {validation_status}")
    print(f"Hard failures: {len(hard_failures)}")
    print(f"Warnings: {len(warnings)}")

    if args.strict and hard_failures:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
