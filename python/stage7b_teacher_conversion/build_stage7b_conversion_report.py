#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np


DEFAULT_DATASET_DIR = Path(
    "python/week5_teacher_legacy032/teacher_exports_bc/"
    "day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z"
)
DEFAULT_REPORT_JSON = Path("python/stage7b_teacher_conversion/stage7b_teacher_to_candidate_conversion_report.json")
DEFAULT_REPORT_MD = Path("python/stage7b_teacher_conversion/stage7b_teacher_to_candidate_conversion_report.md")
DEFAULT_SCHEMA_PROBE = Path("python/stage7b_teacher_conversion/stage7b_teacher_conversion_schema_probe.json")
DEFAULT_PREVIEW_JSONL = Path("python/stage7b_teacher_conversion/stage7b_teacher_candidate_dataset_preview.jsonl")

EXPECTED_BRANCH_SIZES = [6, 4, 4, 4, 4, 7, 49]
EXPECTED_ATTACK_TARGET_SIZE = 49
EXPECTED_ATTACK_TARGET_CENTER = 24
EXPECTED_CANDIDATE_BRANCH_SIZE = 128

ACTION_NAME_BY_INDEX = {
    0: "NoOp",
    1: "Move",
    2: "Harvest",
    3: "Return",
    4: "Produce",
    5: "Attack",
}

DROP_REASONS = [
    "teacher_noop",
    "no_nonnoop_actor",
    "multiple_nonnoop_actors",
    "no_matching_actor",
    "actor_not_owned",
    "actor_dead_or_missing",
    "action_type_unsupported",
    "action_not_legal_in_unity",
    "direction_mismatch",
    "produce_type_mismatch",
    "attack_target_mismatch",
    "candidate_overflow",
    "state_reconstruction_failed",
    "runtime_desync",
    "observation_contract_mismatch",
    "branch_contract_mismatch",
    "attack_target_contract_mismatch",
    "dataset_schema_unknown",
    "npz_array_missing",
    "manifest_missing_or_invalid",
    "unknown",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Stage7B teacher-to-candidate conversion preflight report.")
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--split", choices=["train", "validation", "debug"], default="debug")
    parser.add_argument("--max-samples", type=int, default=512)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    parser.add_argument("--schema-probe", type=Path, default=DEFAULT_SCHEMA_PROBE)
    parser.add_argument("--preview-jsonl", type=Path, default=DEFAULT_PREVIEW_JSONL)
    return parser.parse_args()


def _load_manifest(dataset_dir: Path) -> Tuple[Path, Dict[str, Any]]:
    manifest_path = dataset_dir / "bc_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest file: {manifest_path}")
    try:
        return manifest_path, json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid manifest JSON: {manifest_path}: {exc}") from exc


def _manifest_branch_sizes(manifest: Dict[str, Any]) -> List[int]:
    direct = manifest.get("branch_sizes")
    if isinstance(direct, list) and direct:
        return [int(v) for v in direct]

    schema = manifest.get("schema", {})
    sample_structure = schema.get("sample_structure", {})
    required = sample_structure.get("required", {})
    target = required.get("target_action_branches", {})
    nested = target.get("branch_sizes")
    if isinstance(nested, list) and nested:
        return [int(v) for v in nested]

    return []


def _load_split_npz(npz_path: Path) -> Tuple[np.ndarray, np.ndarray, Dict[str, np.ndarray], List[str]]:
    if not npz_path.exists():
        raise FileNotFoundError(f"Missing split file: {npz_path}")

    with np.load(npz_path, allow_pickle=True) as npz:
        keys = list(npz.keys())
        if "observations" not in npz or "actions" not in npz:
            raise KeyError(f"{npz_path.name}: missing required keys observations/actions, found {keys}")

        observations = np.asarray(npz["observations"])
        actions = np.asarray(npz["actions"])

        metadata: Dict[str, np.ndarray] = {}
        for key in ("episode_id", "step_id", "reward_t", "done_t", "terminated_t", "truncated_t", "action_mask_available_t"):
            if key in npz:
                metadata[key] = np.asarray(npz[key])

    return observations, actions, metadata, keys


def _obs_to_hwc(sample_obs: np.ndarray) -> np.ndarray:
    if sample_obs.shape == (24, 24, 27):
        return sample_obs.astype(np.float32, copy=False)
    if sample_obs.shape == (576, 27):
        return sample_obs.reshape(24, 24, 27).astype(np.float32, copy=False)
    if sample_obs.shape == (15552,):
        return sample_obs.reshape(24, 24, 27).astype(np.float32, copy=False)
    raise ValueError(f"Unsupported observation sample shape: {list(sample_obs.shape)}")


def _rate(numer: int, denom: int) -> float:
    return float(numer / denom) if denom > 0 else 0.0


def _write_markdown(path: Path, report: Dict[str, Any]) -> None:
    metrics = report["metrics"]
    contract = report["contract_detection"]
    lines: List[str] = []
    lines.append("# Stage7B Teacher-to-Candidate Conversion Preflight")
    lines.append("")
    lines.append("## Status")
    lines.append("")
    lines.append(f"- status: {report['status']}")
    lines.append(f"- mode: {report['preflight_mode']}")
    lines.append(f"- source_dataset_path: {report['source_dataset_path']}")
    lines.append(f"- split: {report['split']}")
    lines.append(f"- processed_samples_limit: {report['max_samples_requested']}")
    lines.append("")
    lines.append("## Contract Detection")
    lines.append("")
    lines.append(f"- manifest_branch_sizes: {contract['manifest_branch_sizes']}")
    lines.append(f"- branch_contract_detected: {contract['branch_contract_detected']}")
    lines.append(f"- branch_contract_matches_stage7b: {contract['branch_contract_matches_stage7b']}")
    lines.append(f"- attack_target_size_detected: {contract['attack_target_size_detected']}")
    lines.append(f"- attack_target_center_index_detected: {contract['attack_target_center_index_detected']}")
    lines.append(f"- stage7b_attack_target_size: {contract['stage7b_attack_target_size']}")
    lines.append(f"- stage7b_attack_target_center_index: {contract['stage7b_attack_target_center_index']}")
    lines.append(f"- stage7b_candidate_branch_size: {contract['stage7b_candidate_branch_size']}")
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    lines.append(f"- total_samples: {metrics['total_samples']}")
    lines.append(f"- processed_samples: {metrics['processed_samples']}")
    lines.append(f"- matched_samples: {metrics['matched_samples']}")
    lines.append(f"- dropped_samples: {metrics['dropped_samples']}")
    lines.append(f"- match_rate: {metrics['match_rate']:.6f}")
    lines.append(f"- nonnoop_total: {metrics['nonnoop_total']}")
    lines.append(f"- nonnoop_matched: {metrics['nonnoop_matched']}")
    lines.append(f"- nonnoop_match_rate: {metrics['nonnoop_match_rate']:.6f}")
    lines.append(f"- noop_total: {metrics['noop_total']}")
    lines.append(f"- noop_matched_to_candidate0: {metrics['noop_matched_to_candidate0']}")
    lines.append("")
    lines.append("## Drop Reasons")
    lines.append("")
    for reason, value in metrics["drop_reason_histogram"].items():
        if value > 0:
            lines.append(f"- {reason}: {value}")
    lines.append("")
    lines.append("## Reliability")
    lines.append("")
    lines.append(f"- state_reconstruction_reliable: {report['state_reconstruction']['reliable']}")
    lines.append(f"- state_reconstruction_reason: {report['state_reconstruction']['reason']}")
    lines.append(f"- match_rate_scope: {report['match_rate_scope']}")
    lines.append(f"- demo_recording_ready_for_stage7b_6b: {report['demo_recording_ready_for_stage7b_6b']}")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    for note in report["notes"]:
        lines.append(f"- {note}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()

    files_read: List[str] = []
    status = "ok"
    preflight_mode = "partial_preflight"
    notes: List[str] = []

    drop_hist = Counter({reason: 0 for reason in DROP_REASONS})
    match_by_action_type = Counter({name: 0 for name in ("Move", "Harvest", "Return", "Produce", "Attack")})
    drop_by_action_type = Counter({name: 0 for name in ("Move", "Harvest", "Return", "Produce", "Attack")})

    total_samples = 0
    processed_samples = 0
    matched_samples = 0
    dropped_samples = 0
    nonnoop_total = 0
    nonnoop_matched = 0
    noop_total = 0
    noop_matched = 0

    observation_contract_mismatch_count = 0
    observation_out_of_range_count = 0
    observation_nan_inf_count = 0

    candidate_overflow_count = 0
    runtime_desync_count = 0

    observation_shape_detected: List[int] = []
    action_shape_detected: List[int] = []

    manifest_branch_sizes: List[int] = []
    branch_contract_detected = False
    branch_contract_matches_stage7b = False
    branch_contract_mismatch = False
    attack_target_contract_mismatch = False

    npz_keys_discovered: Dict[str, List[str]] = {}

    try:
        manifest_path, manifest = _load_manifest(args.dataset_dir)
        files_read.append(str(manifest_path))
        manifest_branch_sizes = _manifest_branch_sizes(manifest)
        branch_contract_detected = len(manifest_branch_sizes) > 0
        branch_contract_matches_stage7b = manifest_branch_sizes == EXPECTED_BRANCH_SIZES
        branch_contract_mismatch = branch_contract_detected and not branch_contract_matches_stage7b

        if not branch_contract_detected:
            status = "partial"
            notes.append("Manifest does not expose branch_sizes explicitly.")

        split_path = args.dataset_dir / f"bc_{args.split}.npz"
        files_read.append(str(split_path))
        observations, actions, _, keys = _load_split_npz(split_path)
        npz_keys_discovered[args.split] = keys

        total_samples = int(min(max(0, int(args.max_samples)), observations.shape[0]))
        action_shape_detected = [int(v) for v in actions.shape]
        observation_shape_detected = [int(v) for v in observations.shape]

        if branch_contract_mismatch:
            status = "partial"
            dropped_samples = total_samples
            processed_samples = total_samples
            drop_hist["branch_contract_mismatch"] += total_samples
            notes.append("Branch contract mismatch detected. Conversion preflight stopped before action matching.")
        else:
            for idx in range(total_samples):
                sample_obs_raw = np.asarray(observations[idx])
                sample_actions = np.asarray(actions[idx])

                processed_samples += 1

                try:
                    obs_hwc = _obs_to_hwc(sample_obs_raw)
                except ValueError:
                    dropped_samples += 1
                    observation_contract_mismatch_count += 1
                    drop_hist["observation_contract_mismatch"] += 1
                    continue

                if sample_actions.shape != (576, 7):
                    dropped_samples += 1
                    drop_hist["branch_contract_mismatch"] += 1
                    continue

                if np.isnan(obs_hwc).any() or np.isinf(obs_hwc).any():
                    observation_nan_inf_count += 1
                if (obs_hwc < 0.0).any() or (obs_hwc > 1.0).any():
                    observation_out_of_range_count += 1

                # Validate branch value ranges for each branch.
                branch_bad = False
                for b, size in enumerate(EXPECTED_BRANCH_SIZES):
                    branch_values = sample_actions[:, b]
                    if (branch_values < 0).any() or (branch_values >= size).any():
                        branch_bad = True
                        break

                if branch_bad:
                    dropped_samples += 1
                    drop_hist["branch_contract_mismatch"] += 1
                    continue

                action_type = sample_actions[:, 0]
                nonnoop_indices = np.flatnonzero(action_type != 0)

                if nonnoop_indices.size == 0:
                    noop_total += 1
                    matched_samples += 1
                    noop_matched += 1
                    continue

                nonnoop_total += 1

                if nonnoop_indices.size > 1:
                    dropped_samples += 1
                    drop_hist["multiple_nonnoop_actors"] += 1
                    unique_types = set(int(action_type[i]) for i in nonnoop_indices.tolist())
                    for at in unique_types:
                        aname = ACTION_NAME_BY_INDEX.get(at, "")
                        if aname in drop_by_action_type:
                            drop_by_action_type[aname] += 1
                    continue

                actor_flat = int(nonnoop_indices[0])
                actor_action_type = int(action_type[actor_flat])
                actor_action_name = ACTION_NAME_BY_INDEX.get(actor_action_type, "")

                if actor_action_name not in ("Move", "Harvest", "Return", "Produce", "Attack"):
                    dropped_samples += 1
                    drop_hist["action_type_unsupported"] += 1
                    continue

                # Offline bc_ready sample does not contain sufficient runtime state to rebuild
                # legal Stage7B candidate list with ActionMaskBuilder truth guarantees.
                dropped_samples += 1
                drop_hist["state_reconstruction_failed"] += 1
                drop_by_action_type[actor_action_name] += 1

            if drop_hist["state_reconstruction_failed"] > 0:
                status = "partial"

    except FileNotFoundError as exc:
        status = "partial"
        preflight_mode = "blocked_preflight"
        drop_hist["manifest_missing_or_invalid"] += 1
        notes.append(str(exc))
    except (ValueError, KeyError) as exc:
        status = "partial"
        preflight_mode = "blocked_preflight"
        drop_hist["dataset_schema_unknown"] += 1
        notes.append(str(exc))

    if dropped_samples == 0 and processed_samples > 0:
        preflight_mode = "full_preflight"

    match_rate = _rate(matched_samples, processed_samples)
    nonnoop_match_rate = _rate(nonnoop_matched, nonnoop_total)

    attack_target_size_detected = int(manifest_branch_sizes[6]) if len(manifest_branch_sizes) >= 7 else None
    attack_target_center_index_detected = int(attack_target_size_detected // 2) if attack_target_size_detected else None
    if attack_target_size_detected is not None and attack_target_size_detected != EXPECTED_ATTACK_TARGET_SIZE:
        attack_target_contract_mismatch = True

    state_reconstruction_reliable = False
    state_reconstruction_reason = (
        "bc_ready observations/actions do not include full authoritative runtime state needed "
        "to reconstruct legal Unity ActionMaskBuilder candidate sets with reliability guarantees"
    )

    if not notes:
        notes.append("No Unity training, no .demo recording, no PPO/imitation started in this preflight.")

    report: Dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "preflight_mode": preflight_mode,
        "source_dataset_path": str(args.dataset_dir),
        "split": args.split,
        "max_samples_requested": int(args.max_samples),
        "files_read": files_read,
        "artifacts": {
            "schema_probe_json": str(args.schema_probe),
            "preview_jsonl": str(args.preview_jsonl),
            "report_json": str(args.report_json),
            "report_md": str(args.report_md),
        },
        "schema_probe_exists": args.schema_probe.exists(),
        "preview_exists": args.preview_jsonl.exists(),
        "contract_detection": {
            "npz_keys_discovered": npz_keys_discovered,
            "manifest_branch_sizes": manifest_branch_sizes,
            "branch_contract_detected": branch_contract_detected,
            "branch_contract_matches_stage7b": branch_contract_matches_stage7b,
            "branch_contract_mismatch": branch_contract_mismatch,
            "attack_target_contract_mismatch": attack_target_contract_mismatch,
            "attack_target_size_detected": attack_target_size_detected,
            "attack_target_center_index_detected": attack_target_center_index_detected,
            "stage7b_attack_target_size": EXPECTED_ATTACK_TARGET_SIZE,
            "stage7b_attack_target_center_index": EXPECTED_ATTACK_TARGET_CENTER,
            "stage7b_candidate_branch_size": EXPECTED_CANDIDATE_BRANCH_SIZE,
            "observation_shape_detected": observation_shape_detected,
            "action_shape_detected": action_shape_detected,
        },
        "state_reconstruction": {
            "reliable": state_reconstruction_reliable,
            "reason": state_reconstruction_reason,
        },
        "match_rate_scope": (
            "partial_preflight_only_no_runtime_state_reconstruction"
            if not state_reconstruction_reliable
            else "full"
        ),
        "metrics": {
            "total_samples": total_samples,
            "processed_samples": processed_samples,
            "matched_samples": matched_samples,
            "dropped_samples": dropped_samples,
            "match_rate": match_rate,
            "nonnoop_total": nonnoop_total,
            "nonnoop_matched": nonnoop_matched,
            "nonnoop_match_rate": nonnoop_match_rate,
            "noop_total": noop_total,
            "noop_matched_to_candidate0": noop_matched,
            "drop_reason_histogram": {k: int(drop_hist[k]) for k in DROP_REASONS},
            "match_by_action_type": {k: int(match_by_action_type[k]) for k in ("Move", "Harvest", "Return", "Produce", "Attack")},
            "drop_by_action_type": {k: int(drop_by_action_type[k]) for k in ("Move", "Harvest", "Return", "Produce", "Attack")},
            "candidate_count_min": None,
            "candidate_count_mean": None,
            "candidate_count_max": None,
            "candidate_overflow_count": int(candidate_overflow_count),
            "observation_mismatch_count": None,
            "observation_max_abs_diff": None,
            "observation_mean_abs_diff": None,
            "runtime_desync_count": int(runtime_desync_count),
            "observation_contract_mismatch_count": int(observation_contract_mismatch_count),
            "observation_out_of_range_count": int(observation_out_of_range_count),
            "observation_nan_inf_count": int(observation_nan_inf_count),
            "branch_contract_detected": branch_contract_detected,
            "attack_target_size_detected": attack_target_size_detected,
            "attack_target_center_index_detected": attack_target_center_index_detected,
            "stage7b_attack_target_size": EXPECTED_ATTACK_TARGET_SIZE,
            "stage7b_attack_target_center_index": EXPECTED_ATTACK_TARGET_CENTER,
        },
        "demo_recording_ready_for_stage7b_6b": False if not state_reconstruction_reliable else True,
        "recommendation": (
            "switch_stage7b_6b_to_unity_replay_from_raw_or_adapted_teacher_trajectories"
            if not state_reconstruction_reliable
            else "stage7b_6b_demo_recording_can_proceed"
        ),
        "stage6b3_baseline_touched": False,
        "notes": notes,
    }

    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    _write_markdown(args.report_md, report)

    print(json.dumps(
        {
            "status": report["status"],
            "preflight_mode": report["preflight_mode"],
            "processed_samples": report["metrics"]["processed_samples"],
            "match_rate": report["metrics"]["match_rate"],
            "nonnoop_match_rate": report["metrics"]["nonnoop_match_rate"],
            "drop_reason_histogram_nonzero": {
                k: v for k, v in report["metrics"]["drop_reason_histogram"].items() if v > 0
            },
            "report_json": str(args.report_json),
            "report_md": str(args.report_md),
        },
        ensure_ascii=True,
        indent=2,
    ))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
