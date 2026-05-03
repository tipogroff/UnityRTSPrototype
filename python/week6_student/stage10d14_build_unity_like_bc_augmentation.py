#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import numpy as np

from stage10d14_common import (
    ACTION_SHAPE,
    ACTION_SLICE,
    ACTION_TYPE_HARVEST,
    ACTION_TYPE_NOOP,
    ACTION_TYPE_PRODUCE,
    ATTACK_TARGET_INDEX,
    B2_FLAT,
    BRANCH_SIZES,
    C3_FLAT,
    DEFAULT_BC_OUTPUT_ROOT,
    DEFAULT_BC_READY_DIR,
    DEFAULT_TRUE_RAW_CAPTURE,
    DIR_SLICE,
    MAP_H,
    MAP_W,
    OBS_SHAPE,
    OWNER_SELF_INDEX,
    PRODUCE_TYPE_SLICE,
    UNIT_BASE_INDEX,
    UNIT_TYPE_SLICE,
    UNIT_WORKER_INDEX,
    choose_nearest_reference,
    compute_action_distribution,
    flatten_obs,
    flat_to_xy,
    load_json,
    load_split_payload,
    load_true_raw_capture_tensor,
    normalize_empty_cells_unity_like,
    patch_local_action_context_from_runtime,
    repo_root,
    resolve_path,
    reshape_obs,
    select_reference_sample,
    set_action_noop_on_cell,
    utc_dir_stamp,
    utc_now_iso,
    validate_branch_bounds,
    write_json,
    write_jsonl,
)


@dataclass(frozen=True)
class CandidateCell:
    split_name: str
    source_sample_index: int
    target_flat: int
    action_type: int
    priority_key: tuple[int, int, int]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.14 targeted Unity-like BC augmentation builder")
    p.add_argument("--bc-ready-dir", type=Path, default=Path(DEFAULT_BC_READY_DIR))
    p.add_argument("--true-raw-capture", type=Path, default=Path(DEFAULT_TRUE_RAW_CAPTURE))
    p.add_argument("--output-root", type=Path, default=Path(DEFAULT_BC_OUTPUT_ROOT))
    p.add_argument("--run-label", type=str, default="legacy032_3m_unity_v2_stage10d14_unity_like_augmented_bc_ready")
    p.add_argument("--max-worker-aug-samples", type=int, default=256)
    p.add_argument("--max-base-aug-samples", type=int, default=256)
    p.add_argument("--negative-control-samples", type=int, default=64)
    p.add_argument("--true-raw-repeat-factor", type=int, default=32)
    p.add_argument("--worker-repeat-factor", type=int, default=1)
    p.add_argument("--base-repeat-factor", type=int, default=1)
    return p.parse_args()


def _load_split_arrays(split_path: Path) -> Dict[str, np.ndarray]:
    payload = load_split_payload(split_path)
    observations = np.asarray(payload.get("observations", payload.get("input_tensor")), dtype=np.float32)
    actions = np.asarray(payload.get("actions", payload.get("target_action_branches")), dtype=np.int16)
    payload = dict(payload)
    payload["observations"] = observations
    payload["actions"] = actions
    payload.setdefault("episode_id", np.arange(observations.shape[0], dtype=np.int32))
    payload.setdefault("step_id", np.zeros((observations.shape[0],), dtype=np.int32))
    payload.setdefault("reward_t", np.zeros((observations.shape[0],), dtype=np.float32))
    payload.setdefault("done_t", np.zeros((observations.shape[0],), dtype=np.bool_))
    payload.setdefault("terminated_t", np.zeros((observations.shape[0],), dtype=np.bool_))
    payload.setdefault("truncated_t", np.zeros((observations.shape[0],), dtype=np.bool_))
    payload.setdefault("action_mask_available_t", np.zeros((observations.shape[0],), dtype=np.bool_))
    return payload


def _candidate_cells_for_split(
    split_name: str,
    observations: np.ndarray,
    actions: np.ndarray,
    target_action_type: int,
    target_unit_channel: int,
    max_samples: int,
) -> List[CandidateCell]:
    action_mask = np.asarray(actions[:, :, 0] == target_action_type, dtype=bool)
    actor_mask = np.asarray(observations[:, :, OWNER_SELF_INDEX] > 0.5, dtype=bool)
    unit_mask = np.asarray(observations[:, :, target_unit_channel] > 0.5, dtype=bool)
    valid = action_mask & actor_mask & unit_mask
    sample_indices, flat_indices = np.where(valid)
    candidates: List[CandidateCell] = []
    step_ids = np.zeros((observations.shape[0],), dtype=np.int64)
    for sample_idx, flat_idx in zip(sample_indices.tolist(), flat_indices.tolist()):
        x, y = flat_to_xy(int(flat_idx))
        candidates.append(
            CandidateCell(
                split_name=split_name,
                source_sample_index=int(sample_idx),
                target_flat=int(flat_idx),
                action_type=int(target_action_type),
                priority_key=(int(step_ids[sample_idx]), int(sample_idx), int(flat_idx)),
            )
        )
    candidates.sort(key=lambda item: item.priority_key)
    return candidates[: max(0, int(max_samples))]


def _negative_control_candidates(
    split_name: str,
    observations: np.ndarray,
    actions: np.ndarray,
    max_samples: int,
) -> List[CandidateCell]:
    action_mask = np.asarray(actions[:, :, 0] == ACTION_TYPE_NOOP, dtype=bool)
    actor_mask = np.asarray(observations[:, :, OWNER_SELF_INDEX] > 0.5, dtype=bool)
    unit_mask = np.asarray(
        (observations[:, :, UNIT_WORKER_INDEX] > 0.5) | (observations[:, :, UNIT_BASE_INDEX] > 0.5),
        dtype=bool,
    )
    valid = action_mask & actor_mask & unit_mask
    sample_indices, flat_indices = np.where(valid)
    candidates: List[CandidateCell] = []
    for sample_idx, flat_idx in zip(sample_indices.tolist(), flat_indices.tolist()):
        candidates.append(
            CandidateCell(
                split_name=split_name,
                source_sample_index=int(sample_idx),
                target_flat=int(flat_idx),
                action_type=ACTION_TYPE_NOOP,
                priority_key=(0, int(sample_idx), int(flat_idx)),
            )
        )
    candidates.sort(key=lambda item: item.priority_key)
    return candidates[: max(0, int(max_samples))]


def _base_arrays_like(observations: np.ndarray, actions: np.ndarray) -> Dict[str, np.ndarray]:
    return {
        "observations": np.asarray(observations, dtype=np.float32),
        "actions": np.asarray(actions, dtype=np.int16),
    }


def _build_true_raw_action_template(
    b2_reference_action: np.ndarray,
    c3_reference_action: np.ndarray,
) -> np.ndarray:
    action_map = np.zeros(ACTION_SHAPE, dtype=np.int16)
    action_map[:, 0] = ACTION_TYPE_NOOP
    action_map[B2_FLAT, :] = np.asarray(b2_reference_action, dtype=np.int16)
    action_map[C3_FLAT, :] = np.asarray(c3_reference_action, dtype=np.int16)
    return action_map


def _new_metadata(
    *,
    split_name: str,
    family: str,
    variant: str,
    source_split: str,
    source_sample_index: int,
    source_flat_index: int,
    target_cell_flat: int,
    target_action_type: int,
    generated_from_true_raw: bool,
    unity_like_channels_policy: str,
    sample_weight: float,
) -> Dict[str, Any]:
    return {
        "augmentation_family": family,
        "variant": variant,
        "source_split": source_split,
        "source_sample_index": int(source_sample_index),
        "source_flat_index": int(source_flat_index),
        "target_cell_flat": int(target_cell_flat),
        "target_action_type": int(target_action_type),
        "generated_from_true_raw": bool(generated_from_true_raw),
        "unity_like_channels_policy": unity_like_channels_policy,
        "sample_weight": float(sample_weight),
        "output_split": split_name,
    }


def _append_augmented_sample(
    collector: Dict[str, List[np.ndarray]],
    metadata_rows: List[Dict[str, Any]],
    *,
    observation_flat: np.ndarray,
    action_flat: np.ndarray,
    source_payload: Mapping[str, np.ndarray],
    source_sample_index: int,
    metadata: Mapping[str, Any],
) -> None:
    collector["observations"].append(np.asarray(observation_flat, dtype=np.float32))
    collector["actions"].append(np.asarray(action_flat, dtype=np.int16))
    collector["episode_id"].append(np.asarray(source_payload["episode_id"][source_sample_index], dtype=np.int32))
    collector["step_id"].append(np.asarray(source_payload["step_id"][source_sample_index], dtype=np.int32))
    collector["reward_t"].append(np.asarray(source_payload["reward_t"][source_sample_index], dtype=np.float32))
    collector["done_t"].append(np.asarray(source_payload["done_t"][source_sample_index], dtype=np.bool_))
    collector["terminated_t"].append(np.asarray(source_payload["terminated_t"][source_sample_index], dtype=np.bool_))
    collector["truncated_t"].append(np.asarray(source_payload["truncated_t"][source_sample_index], dtype=np.bool_))
    collector["action_mask_available_t"].append(np.asarray(source_payload["action_mask_available_t"][source_sample_index], dtype=np.bool_))
    metadata_rows.append(dict(metadata))


def _stack_augmented(collector: Mapping[str, List[np.ndarray]]) -> Dict[str, np.ndarray]:
    result: Dict[str, np.ndarray] = {}
    for key, values in collector.items():
        if key in {"observations", "actions"}:
            result[key] = np.stack(values, axis=0)
        elif key == "reward_t":
            result[key] = np.asarray(values, dtype=np.float32)
        elif key in {"done_t", "terminated_t", "truncated_t", "action_mask_available_t"}:
            result[key] = np.asarray(values, dtype=np.bool_)
        else:
            result[key] = np.asarray(values, dtype=np.int32)
    return result


def _merge_original_and_augmented(
    original: Mapping[str, np.ndarray],
    augmented: Mapping[str, np.ndarray],
    *,
    split_name: str,
) -> Dict[str, np.ndarray]:
    result: Dict[str, np.ndarray] = {}
    for key in (
        "observations",
        "actions",
        "episode_id",
        "step_id",
        "reward_t",
        "done_t",
        "terminated_t",
        "truncated_t",
        "action_mask_available_t",
    ):
        result[key] = np.concatenate([np.asarray(original[key]), np.asarray(augmented[key])], axis=0)

    n = int(result["observations"].shape[0])
    result["sample_id"] = np.arange(n, dtype=np.int64)
    result["source_episode_file"] = np.full((n,), f"stage10d14_{split_name}", dtype="<U32")
    result["target_action_branch_sizes"] = np.asarray(BRANCH_SIZES, dtype=np.int64)
    result["schema_version"] = np.asarray(["day6.bc_ready.v1"], dtype="<U32")
    result["split"] = np.asarray([split_name], dtype="<U16")
    result["input_tensor"] = np.asarray(result["observations"], dtype=np.float32)
    result["target_action_branches"] = np.asarray(result["actions"], dtype=np.int16)
    return result


def _save_split(path: Path, split_payload: Mapping[str, np.ndarray]) -> None:
    np.savez_compressed(path, **{k: np.asarray(v) for k, v in split_payload.items()})


def _build_split_augmentations(
    *,
    split_name: str,
    split_payload: Mapping[str, np.ndarray],
    runtime_map: np.ndarray,
    b2_reference: Any,
    c3_reference: Any,
    worker_candidates: Sequence[CandidateCell],
    base_candidates: Sequence[CandidateCell],
    negative_candidates: Sequence[CandidateCell],
    worker_repeat_factor: int,
    base_repeat_factor: int,
    true_raw_repeat_factor: int,
) -> tuple[Dict[str, np.ndarray], List[Dict[str, Any]], Counter[str]]:
    collector: Dict[str, List[np.ndarray]] = defaultdict(list)
    metadata_rows: List[Dict[str, Any]] = []
    family_counter: Counter[str] = Counter()

    observations = np.asarray(split_payload["observations"], dtype=np.float32)
    actions = np.asarray(split_payload["actions"], dtype=np.int16)

    true_raw_action_flat = _build_true_raw_action_template(b2_reference.target_action_vector, c3_reference.target_action_vector)
    true_raw_obs_flat = flatten_obs(runtime_map)
    for focus_name, focus_flat in (("B2", B2_FLAT), ("C3", C3_FLAT)):
        for repeat_idx in range(max(1, int(true_raw_repeat_factor))):
            metadata = _new_metadata(
                split_name=split_name,
                family="family1_true_raw_unity_observation_teacher_labels",
                variant=f"true_raw_dual_target_focus_{focus_name.lower()}",
                source_split="true_raw_runtime",
                source_sample_index=0,
                source_flat_index=focus_flat,
                target_cell_flat=focus_flat,
                target_action_type=int(true_raw_action_flat[focus_flat, 0]),
                generated_from_true_raw=True,
                unity_like_channels_policy="exact_true_raw_runtime_observation_no_current_action_injection",
                sample_weight=4.0,
            )
            _append_augmented_sample(
                collector,
                metadata_rows,
                observation_flat=true_raw_obs_flat,
                action_flat=true_raw_action_flat,
                source_payload=split_payload,
                source_sample_index=0,
                metadata=metadata,
            )
            family_counter[metadata["augmentation_family"]] += 1

    for candidate in worker_candidates:
        source_obs_flat = observations[candidate.source_sample_index]
        source_action_flat = actions[candidate.source_sample_index]
        source_map = reshape_obs(source_obs_flat)

        variants = [
            (
                "family2_positive_worker_or_base_noop_state",
                "actor_current_action_noop_only",
                set_action_noop_on_cell(source_map, candidate.target_flat, clear_direction=False, clear_auxiliary=False),
                "actor_action_noop_only",
            ),
            (
                "family2_positive_worker_or_base_noop_state",
                "actor_current_action_noop_direction_unchanged",
                normalize_empty_cells_unity_like(set_action_noop_on_cell(source_map, candidate.target_flat, clear_direction=False, clear_auxiliary=False)),
                "actor_action_noop_plus_empty_cells_runtime_like",
            ),
            (
                "family2_positive_worker_or_base_noop_state",
                "actor_current_action_noop_direction_cleared",
                normalize_empty_cells_unity_like(set_action_noop_on_cell(source_map, candidate.target_flat, clear_direction=True, clear_auxiliary=True)),
                "actor_action_noop_direction_cleared_plus_empty_cells_runtime_like",
            ),
            (
                "family2_positive_worker_or_base_noop_state",
                "full_map_empty_action_convention_unity_like",
                normalize_empty_cells_unity_like(set_action_noop_on_cell(source_map, candidate.target_flat, clear_direction=True, clear_auxiliary=True)),
                "full_map_empty_cells_runtime_like_actor_noop",
            ),
        ]

        for family, variant, obs_variant, policy in variants:
            repeats = max(1, int(worker_repeat_factor))
            for _ in range(repeats):
                metadata = _new_metadata(
                    split_name=split_name,
                    family=family,
                    variant=variant,
                    source_split=split_name,
                    source_sample_index=candidate.source_sample_index,
                    source_flat_index=candidate.target_flat,
                    target_cell_flat=candidate.target_flat,
                    target_action_type=int(source_action_flat[candidate.target_flat, 0]),
                    generated_from_true_raw=False,
                    unity_like_channels_policy=policy,
                    sample_weight=1.5,
                )
                _append_augmented_sample(
                    collector,
                    metadata_rows,
                    observation_flat=flatten_obs(obs_variant),
                    action_flat=source_action_flat,
                    source_payload=split_payload,
                    source_sample_index=candidate.source_sample_index,
                    metadata=metadata,
                )
                family_counter[family] += 1

    for candidate in base_candidates:
        source_obs_flat = observations[candidate.source_sample_index]
        source_action_flat = actions[candidate.source_sample_index]
        source_map = reshape_obs(source_obs_flat)

        base_variants = [
            (
                "family2_positive_worker_or_base_noop_state",
                "actor_current_action_noop_only",
                set_action_noop_on_cell(source_map, candidate.target_flat, clear_direction=False, clear_auxiliary=False),
                "actor_action_noop_only",
            ),
            (
                "family2_positive_worker_or_base_noop_state",
                "actor_current_action_noop_direction_cleared",
                normalize_empty_cells_unity_like(set_action_noop_on_cell(source_map, candidate.target_flat, clear_direction=True, clear_auxiliary=True)),
                "actor_action_noop_direction_cleared_plus_empty_cells_runtime_like",
            ),
            (
                "family2_positive_worker_or_base_noop_state",
                "local_5x5_around_base_current_action_noop",
                patch_local_action_context_from_runtime(
                    set_action_noop_on_cell(source_map, candidate.target_flat, clear_direction=True, clear_auxiliary=True),
                    target_flat=candidate.target_flat,
                    runtime_map=runtime_map,
                    runtime_center_flat=C3_FLAT,
                    radius=2,
                ),
                "actor_noop_plus_local_5x5_runtime_action_context",
            ),
            (
                "family2_positive_worker_or_base_noop_state",
                "full_map_empty_action_convention_unity_like",
                normalize_empty_cells_unity_like(set_action_noop_on_cell(source_map, candidate.target_flat, clear_direction=True, clear_auxiliary=True)),
                "full_map_empty_cells_runtime_like_actor_noop",
            ),
            (
                "family3_base_local_context",
                "local_3x3_current_action_noop",
                patch_local_action_context_from_runtime(
                    set_action_noop_on_cell(source_map, candidate.target_flat, clear_direction=True, clear_auxiliary=True),
                    target_flat=candidate.target_flat,
                    runtime_map=runtime_map,
                    runtime_center_flat=C3_FLAT,
                    radius=1,
                ),
                "actor_noop_plus_local_3x3_runtime_action_context",
            ),
            (
                "family3_base_local_context",
                "local_5x5_current_action_noop",
                patch_local_action_context_from_runtime(
                    set_action_noop_on_cell(source_map, candidate.target_flat, clear_direction=True, clear_auxiliary=True),
                    target_flat=candidate.target_flat,
                    runtime_map=runtime_map,
                    runtime_center_flat=C3_FLAT,
                    radius=2,
                ),
                "actor_noop_plus_local_5x5_runtime_action_context",
            ),
        ]

        for family, variant, obs_variant, policy in base_variants:
            repeats = max(1, int(base_repeat_factor))
            for _ in range(repeats):
                metadata = _new_metadata(
                    split_name=split_name,
                    family=family,
                    variant=variant,
                    source_split=split_name,
                    source_sample_index=candidate.source_sample_index,
                    source_flat_index=candidate.target_flat,
                    target_cell_flat=candidate.target_flat,
                    target_action_type=int(source_action_flat[candidate.target_flat, 0]),
                    generated_from_true_raw=False,
                    unity_like_channels_policy=policy,
                    sample_weight=1.5,
                )
                _append_augmented_sample(
                    collector,
                    metadata_rows,
                    observation_flat=flatten_obs(obs_variant),
                    action_flat=source_action_flat,
                    source_payload=split_payload,
                    source_sample_index=candidate.source_sample_index,
                    metadata=metadata,
                )
                family_counter[family] += 1

    for candidate in negative_candidates:
        source_obs_flat = observations[candidate.source_sample_index]
        source_action_flat = actions[candidate.source_sample_index]
        source_map = reshape_obs(source_obs_flat)
        obs_variant = normalize_empty_cells_unity_like(
            set_action_noop_on_cell(source_map, candidate.target_flat, clear_direction=True, clear_auxiliary=True)
        )
        metadata = _new_metadata(
            split_name=split_name,
            family="family4_negative_controls",
            variant="unity_like_noop_actor_negative_control",
            source_split=split_name,
            source_sample_index=candidate.source_sample_index,
            source_flat_index=candidate.target_flat,
            target_cell_flat=candidate.target_flat,
            target_action_type=int(source_action_flat[candidate.target_flat, 0]),
            generated_from_true_raw=False,
            unity_like_channels_policy="actor_noop_plus_empty_cells_runtime_like_negative_control",
            sample_weight=0.75,
        )
        _append_augmented_sample(
            collector,
            metadata_rows,
            observation_flat=flatten_obs(obs_variant),
            action_flat=source_action_flat,
            source_payload=split_payload,
            source_sample_index=candidate.source_sample_index,
            metadata=metadata,
        )
        family_counter[metadata["augmentation_family"]] += 1

    augmented_payload = _stack_augmented(collector)
    return augmented_payload, metadata_rows, family_counter


def main() -> int:
    args = parse_args()
    root = repo_root()
    bc_ready_dir = resolve_path(args.bc_ready_dir).resolve()
    true_raw_capture = resolve_path(args.true_raw_capture).resolve()
    output_root = resolve_path(args.output_root).resolve()
    output_dir = output_root / f"{args.run_label}_{utc_dir_stamp()}"

    if output_dir.exists():
        raise RuntimeError(f"Refusing overwrite of existing output dir: {output_dir}")

    train_payload = _load_split_arrays(bc_ready_dir / "bc_train.npz")
    val_payload = _load_split_arrays(bc_ready_dir / "bc_validation.npz")
    original_manifest = load_json(bc_ready_dir / "bc_manifest.json")
    runtime_map = load_true_raw_capture_tensor(true_raw_capture)
    runtime_vec_b2 = runtime_map.reshape(OBS_SHAPE)[B2_FLAT]
    runtime_vec_c3 = runtime_map.reshape(OBS_SHAPE)[C3_FLAT]

    b2_reference = choose_nearest_reference(
        [
            select_reference_sample(train_payload["observations"], train_payload["actions"], split_name="train", runtime_vec=runtime_vec_b2, target_action_type=ACTION_TYPE_HARVEST, target_unit_channel=UNIT_WORKER_INDEX),
            select_reference_sample(val_payload["observations"], val_payload["actions"], split_name="validation", runtime_vec=runtime_vec_b2, target_action_type=ACTION_TYPE_HARVEST, target_unit_channel=UNIT_WORKER_INDEX),
        ]
    )
    c3_reference = choose_nearest_reference(
        [
            select_reference_sample(train_payload["observations"], train_payload["actions"], split_name="train", runtime_vec=runtime_vec_c3, target_action_type=ACTION_TYPE_PRODUCE, target_unit_channel=UNIT_BASE_INDEX),
            select_reference_sample(val_payload["observations"], val_payload["actions"], split_name="validation", runtime_vec=runtime_vec_c3, target_action_type=ACTION_TYPE_PRODUCE, target_unit_channel=UNIT_BASE_INDEX),
        ]
    )

    train_worker_candidates = _candidate_cells_for_split(
        "train",
        train_payload["observations"],
        train_payload["actions"],
        ACTION_TYPE_HARVEST,
        UNIT_WORKER_INDEX,
        args.max_worker_aug_samples,
    )
    val_worker_candidates = _candidate_cells_for_split(
        "validation",
        val_payload["observations"],
        val_payload["actions"],
        ACTION_TYPE_HARVEST,
        UNIT_WORKER_INDEX,
        max(1, args.max_worker_aug_samples // 8),
    )
    train_base_candidates = _candidate_cells_for_split(
        "train",
        train_payload["observations"],
        train_payload["actions"],
        ACTION_TYPE_PRODUCE,
        UNIT_BASE_INDEX,
        args.max_base_aug_samples,
    )
    val_base_candidates = _candidate_cells_for_split(
        "validation",
        val_payload["observations"],
        val_payload["actions"],
        ACTION_TYPE_PRODUCE,
        UNIT_BASE_INDEX,
        max(1, args.max_base_aug_samples // 8),
    )
    train_negative = _negative_control_candidates(
        "train",
        train_payload["observations"],
        train_payload["actions"],
        args.negative_control_samples,
    )
    val_negative = _negative_control_candidates(
        "validation",
        val_payload["observations"],
        val_payload["actions"],
        max(1, args.negative_control_samples // 8),
    )

    train_augmented, train_metadata_rows, train_family_counts = _build_split_augmentations(
        split_name="train",
        split_payload=train_payload,
        runtime_map=runtime_map,
        b2_reference=b2_reference,
        c3_reference=c3_reference,
        worker_candidates=train_worker_candidates,
        base_candidates=train_base_candidates,
        negative_candidates=train_negative,
        worker_repeat_factor=args.worker_repeat_factor,
        base_repeat_factor=args.base_repeat_factor,
        true_raw_repeat_factor=args.true_raw_repeat_factor,
    )
    val_augmented, val_metadata_rows, val_family_counts = _build_split_augmentations(
        split_name="validation",
        split_payload=val_payload,
        runtime_map=runtime_map,
        b2_reference=b2_reference,
        c3_reference=c3_reference,
        worker_candidates=val_worker_candidates,
        base_candidates=val_base_candidates,
        negative_candidates=val_negative,
        worker_repeat_factor=1,
        base_repeat_factor=1,
        true_raw_repeat_factor=max(1, args.true_raw_repeat_factor // 8),
    )

    merged_train = _merge_original_and_augmented(train_payload, train_augmented, split_name="train")
    merged_val = _merge_original_and_augmented(val_payload, val_augmented, split_name="validation")

    output_dir.mkdir(parents=True, exist_ok=False)
    _save_split(output_dir / "bc_train.npz", merged_train)
    _save_split(output_dir / "bc_validation.npz", merged_val)
    _save_split(output_dir / "bc_debug.npz", {k: np.asarray(v[: min(1024, v.shape[0])]) for k, v in merged_val.items()})

    train_metadata_path = write_jsonl(output_dir / "stage10d14_augmented_sample_metadata_train.jsonl", train_metadata_rows)
    val_metadata_path = write_jsonl(output_dir / "stage10d14_augmented_sample_metadata_validation.jsonl", val_metadata_rows)

    original_train_distribution = compute_action_distribution(train_payload["observations"], train_payload["actions"])
    original_val_distribution = compute_action_distribution(val_payload["observations"], val_payload["actions"])
    merged_train_distribution = compute_action_distribution(merged_train["observations"], merged_train["actions"])
    merged_val_distribution = compute_action_distribution(merged_val["observations"], merged_val["actions"])

    family_counts = Counter(train_family_counts)
    family_counts.update(val_family_counts)

    detailed_manifest: Dict[str, Any] = {
        "stage": "10D.14",
        "task": "targeted_bc_augmentation_with_unity_like_observations",
        "generated_at_utc": utc_now_iso(),
        "original_dataset_path": bc_ready_dir.as_posix(),
        "output_dataset_path": output_dir.as_posix(),
        "input_artifacts": {
            "bc_train": (bc_ready_dir / "bc_train.npz").as_posix(),
            "bc_validation": (bc_ready_dir / "bc_validation.npz").as_posix(),
            "true_raw_capture": true_raw_capture.as_posix(),
        },
        "counts": {
            "original_train_count": int(train_payload["observations"].shape[0]),
            "original_validation_count": int(val_payload["observations"].shape[0]),
            "augmented_train_count": int(train_augmented["observations"].shape[0]),
            "augmented_validation_count": int(val_augmented["observations"].shape[0]),
            "output_train_count": int(merged_train["observations"].shape[0]),
            "output_validation_count": int(merged_val["observations"].shape[0]),
        },
        "family_counts": dict(sorted(family_counts.items())),
        "target_positive_counts_before_after": {
            "train_before": original_train_distribution,
            "validation_before": original_val_distribution,
            "train_after": merged_train_distribution,
            "validation_after": merged_val_distribution,
        },
        "branch_bounds": list(BRANCH_SIZES),
        "observation_shape": list(OBS_SHAPE),
        "action_shape": list(ACTION_SHAPE),
        "exact_channel_policy_used": {
            "family1_true_raw": "exact true raw Unity observation retained; B2 current_action=noop and C3 current_action=noop remain untouched in observation",
            "family2_positive_variants": [
                "actor_current_action_noop_only",
                "actor_current_action_noop_direction_unchanged",
                "actor_current_action_noop_direction_cleared",
                "local_5x5_around_base_current_action_noop",
                "full_map_empty_action_convention_unity_like",
            ],
            "family3_base_local_context": [
                "local_3x3_current_action_noop",
                "local_5x5_current_action_noop",
            ],
            "family4_negative_controls": "small set of noop-labeled actor samples rendered Unity-like to reduce shortcut risk",
        },
        "references": {
            "b2_worker_harvest_reference": {
                "split": b2_reference.split_name,
                "sample_index": b2_reference.sample_index,
                "flat_index": b2_reference.flat_index,
                "l2_distance": b2_reference.l2_distance,
                "target_action": int(b2_reference.target_action_vector[0]),
                "harvest_dir": int(b2_reference.target_action_vector[2]),
            },
            "c3_base_produce_reference": {
                "split": c3_reference.split_name,
                "sample_index": c3_reference.sample_index,
                "flat_index": c3_reference.flat_index,
                "l2_distance": c3_reference.l2_distance,
                "target_action": int(c3_reference.target_action_vector[0]),
                "produce_dir": int(c3_reference.target_action_vector[4]),
                "produce_unit_type": int(c3_reference.target_action_vector[5]),
            },
        },
        "metadata_sidecars": {
            "train": train_metadata_path.as_posix(),
            "validation": val_metadata_path.as_posix(),
        },
        "builder_config": {
            "max_worker_aug_samples": int(args.max_worker_aug_samples),
            "max_base_aug_samples": int(args.max_base_aug_samples),
            "negative_control_samples": int(args.negative_control_samples),
            "true_raw_repeat_factor": int(args.true_raw_repeat_factor),
            "worker_repeat_factor": int(args.worker_repeat_factor),
            "base_repeat_factor": int(args.base_repeat_factor),
        },
        "branch_bounds_valid_output": {
            "train": validate_branch_bounds(merged_train["actions"]),
            "validation": validate_branch_bounds(merged_val["actions"]),
        },
        "explicit_non_claims": [
            "No PPO run.",
            "No Gym teacher checkpoint change.",
            "No Unity runtime mutation.",
            "No ActionDecoder change.",
            "No ActionApplier change.",
            "No MatchManager change.",
            "No runtime current_action remap deployed.",
            "No semantic parity claim made.",
        ],
    }

    bc_manifest: Dict[str, Any] = dict(original_manifest)
    bc_manifest.update(
        {
            "generated_at_utc": utc_now_iso(),
            "schema_version": "day6.bc_ready.v1",
            "dataset_kind": "semantic_bc_ready_stage10d14_augmented",
            "source_stage": "10D.14",
            "source_bc_ready_dir": bc_ready_dir.as_posix(),
            "observation_shape": list(OBS_SHAPE),
            "action_shape": list(ACTION_SHAPE),
            "observation_shape_per_sample": list(OBS_SHAPE),
            "action_shape_per_sample": list(ACTION_SHAPE),
            "branch_sizes": list(BRANCH_SIZES),
            "num_train": int(merged_train["observations"].shape[0]),
            "num_validation": int(merged_val["observations"].shape[0]),
            "num_debug": int(min(1024, merged_val["observations"].shape[0])),
            "stage10d14_augmentation_manifest": (output_dir / "stage10d14_augmentation_manifest.json").as_posix(),
            "stage10d14_metadata_sidecars": {
                "train": train_metadata_path.as_posix(),
                "validation": val_metadata_path.as_posix(),
            },
            "notes": "Stage10D.14 targeted supervised BC augmentation with Unity-like NoOp-state observations.",
        }
    )

    write_json(output_dir / "stage10d14_augmentation_manifest.json", detailed_manifest)
    write_json(output_dir / "bc_manifest.json", bc_manifest)

    print((output_dir / "bc_train.npz").as_posix())
    print((output_dir / "bc_validation.npz").as_posix())
    print((output_dir / "bc_manifest.json").as_posix())
    print((output_dir / "stage10d14_augmentation_manifest.json").as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())