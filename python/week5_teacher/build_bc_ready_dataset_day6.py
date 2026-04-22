#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np


SCHEMA_VERSION = "day6.bc_ready.v1"
DEFAULT_TRAIN_RATIO = 0.9
DEFAULT_VAL_RATIO = 0.1
DEFAULT_DEBUG_SIZE = 256
DEFAULT_SEED = 17
EXPECTED_OBS_SHAPE = (24, 24, 27)
EXPECTED_ACTION_SHAPE = (576, 7)
EXPECTED_BRANCH_SIZES = (6, 4, 4, 4, 4, 4, 9)


@dataclass
class LoadedEpisode:
    file_name: str
    episode_id: int
    step_id: np.ndarray
    observation: np.ndarray
    action: np.ndarray
    reward_t: np.ndarray | None
    done_t: np.ndarray | None
    optional_mask: np.ndarray | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Week 5 Day 6 BC-ready packager. Reads a validated Day 4 adapted dataset, "
            "builds train/validation/debug splits, and writes canonical BC-ready artifacts."
        )
    )
    parser.add_argument(
        "--adapted-batch-dir",
        type=Path,
        required=True,
        help="Path to adapted batch directory (must contain episode_*.adapted.npz).",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help=(
            "Output root directory. Defaults to <project>/python/week5_teacher/teacher_exports_bc. "
            "A new subdirectory for this run will be created."
        ),
    )
    parser.add_argument(
        "--output-name",
        type=str,
        default=None,
        help="Optional explicit output subdirectory name. Defaults to day6_bc_ready_<source>_<timestamp>.",
    )
    parser.add_argument("--train-ratio", type=float, default=DEFAULT_TRAIN_RATIO)
    parser.add_argument("--val-ratio", type=float, default=DEFAULT_VAL_RATIO)
    parser.add_argument("--debug-size", type=int, default=DEFAULT_DEBUG_SIZE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--allow-missing-day5-pass",
        action="store_true",
        help="Allow packaging even if strict_validation_day5.json is missing or not pass.",
    )
    return parser.parse_args()


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def infer_output_root(adapted_batch_dir: Path) -> Path:
    return adapted_batch_dir.parent.parent / "teacher_exports_bc"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def infer_output_name(adapted_batch_dir: Path) -> str:
    return f"day6_bc_ready_{adapted_batch_dir.name}_{utc_timestamp()}"


def validate_day5_status(adapted_batch_dir: Path, allow_missing_or_nonpass: bool) -> Dict[str, Any]:
    strict_path = adapted_batch_dir / "strict_validation_day5.json"
    if not strict_path.exists():
        if allow_missing_or_nonpass:
            return {
                "strict_validation_path": str(strict_path),
                "status": "missing_allowed",
                "pass_confirmed": False,
            }
        raise FileNotFoundError(
            f"Missing required Day 5 strict validation file: {strict_path}. "
            "Use --allow-missing-day5-pass only for controlled debug scenarios."
        )

    payload = read_json(strict_path)
    status = str(payload.get("validation", {}).get("status", "")).strip().lower()
    if status != "pass" and not allow_missing_or_nonpass:
        raise RuntimeError(
            f"Day 5 strict validation status is not pass (actual={status!r}). "
            "Refusing to package BC-ready dataset."
        )

    return {
        "strict_validation_path": str(strict_path),
        "status": status,
        "pass_confirmed": status == "pass",
    }


def load_episode(path: Path) -> LoadedEpisode:
    with np.load(path, allow_pickle=True) as data:
        required = {"episode_id", "step_id", "observation_adapted", "action_adapted"}
        missing = sorted(required - set(data.files))
        if missing:
            raise KeyError(f"{path.name}: missing required keys: {missing}")

        episode_id_raw = np.asarray(data["episode_id"])
        if episode_id_raw.size == 0:
            raise ValueError(f"{path.name}: episode_id is empty")
        episode_id = int(np.asarray(episode_id_raw).reshape(-1)[0])

        step_id = np.asarray(data["step_id"])
        obs = np.asarray(data["observation_adapted"])
        action = np.asarray(data["action_adapted"])

        reward_t = np.asarray(data["reward_t"]) if "reward_t" in data.files else None
        done_t = np.asarray(data["done_t"]) if "done_t" in data.files else None
        optional_mask = np.asarray(data["action_mask"]) if "action_mask" in data.files else None

    if obs.ndim != 4 or tuple(obs.shape[1:]) != EXPECTED_OBS_SHAPE:
        raise ValueError(f"{path.name}: observation_adapted shape mismatch: {obs.shape}")
    if action.ndim != 3 or tuple(action.shape[1:]) != EXPECTED_ACTION_SHAPE:
        raise ValueError(f"{path.name}: action_adapted shape mismatch: {action.shape}")

    steps = int(obs.shape[0])
    if action.shape[0] != steps or step_id.shape[0] != steps:
        raise ValueError(
            f"{path.name}: per-step length mismatch obs={obs.shape[0]} action={action.shape[0]} step_id={step_id.shape[0]}"
        )

    if reward_t is not None and reward_t.shape[0] != steps:
        raise ValueError(f"{path.name}: reward_t length mismatch: {reward_t.shape[0]} vs {steps}")
    if done_t is not None and done_t.shape[0] != steps:
        raise ValueError(f"{path.name}: done_t length mismatch: {done_t.shape[0]} vs {steps}")

    return LoadedEpisode(
        file_name=path.name,
        episode_id=episode_id,
        step_id=step_id.astype(np.int64, copy=False),
        observation=obs.astype(np.float32, copy=False),
        action=action.astype(np.int16, copy=False),
        reward_t=reward_t.astype(np.float32, copy=False) if reward_t is not None else None,
        done_t=done_t.astype(np.bool_, copy=False) if done_t is not None else None,
        optional_mask=optional_mask,
    )


def deterministic_bucket(sample_id: str, seed: int) -> float:
    digest = hashlib.sha1(f"{seed}:{sample_id}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16)
    return float(bucket) / float(0xFFFFFFFF)


def deterministic_rank(sample_id: str, seed: int, salt: str) -> int:
    digest = hashlib.sha1(f"{seed}:{salt}:{sample_id}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def assign_split(sample_id: str, train_prob: float, seed: int) -> str:
    return "train" if deterministic_bucket(sample_id, seed) < train_prob else "validation"


def compute_train_prob(train_ratio: float, val_ratio: float) -> float:
    total = train_ratio + val_ratio
    if total <= 0.0:
        raise ValueError("train_ratio + val_ratio must be > 0")
    train_prob = train_ratio / total
    if train_prob <= 0.0 or train_prob >= 1.0:
        raise ValueError("train_ratio/val_ratio combination must produce 0 < train_prob < 1")
    return float(train_prob)


def build_dataset_arrays(episodes: Sequence[LoadedEpisode]) -> Dict[str, np.ndarray]:
    input_tensor_parts: List[np.ndarray] = []
    target_parts: List[np.ndarray] = []
    sample_ids: List[str] = []
    episode_ids: List[int] = []
    step_ids: List[int] = []
    source_episode_files: List[str] = []
    reward_parts: List[np.ndarray] = []
    done_parts: List[np.ndarray] = []

    for episode in episodes:
        steps = int(episode.observation.shape[0])
        input_tensor_parts.append(episode.observation)
        target_parts.append(episode.action)

        if episode.reward_t is not None:
            reward_parts.append(episode.reward_t)
        if episode.done_t is not None:
            done_parts.append(episode.done_t)

        for idx in range(steps):
            step = int(episode.step_id[idx])
            sample_ids.append(f"ep{episode.episode_id:05d}_step{step:06d}")
            episode_ids.append(episode.episode_id)
            step_ids.append(step)
            source_episode_files.append(episode.file_name)

    input_tensor = np.concatenate(input_tensor_parts, axis=0)
    target_action = np.concatenate(target_parts, axis=0)

    payload: Dict[str, np.ndarray] = {
        "input_tensor": input_tensor,
        "target_action_branches": target_action,
        "sample_id": np.asarray(sample_ids, dtype="U32"),
        "episode_id": np.asarray(episode_ids, dtype=np.int32),
        "step_id": np.asarray(step_ids, dtype=np.int32),
        "source_episode_file": np.asarray(source_episode_files, dtype="U128"),
    }

    if reward_parts:
        payload["diagnostic_reward_t"] = np.concatenate(reward_parts, axis=0).astype(np.float32, copy=False)
    if done_parts:
        payload["diagnostic_done_t"] = np.concatenate(done_parts, axis=0).astype(np.bool_, copy=False)

    return payload


def check_supervised_target_readiness(
    sample_id: np.ndarray,
    target_action_branches: np.ndarray,
    split_index: Dict[str, np.ndarray],
) -> Dict[str, Any]:
    sid_list = sample_id.tolist()
    seen: Dict[str, str] = {}
    duplicate_count = 0
    conflict_count = 0

    for idx, sid in enumerate(sid_list):
        digest = hashlib.sha1(target_action_branches[idx].tobytes()).hexdigest()
        prev = seen.get(sid)
        if prev is None:
            seen[sid] = digest
            continue
        duplicate_count += 1
        if prev != digest:
            conflict_count += 1

    action_type = target_action_branches[..., 0].astype(np.int32, copy=False).reshape(-1)
    hist = np.bincount(action_type, minlength=EXPECTED_BRANCH_SIZES[0])
    total_cells = int(np.sum(hist))
    dominant_count = int(np.max(hist)) if total_cells > 0 else 0
    dominant_share = float(dominant_count) / float(total_cells) if total_cells > 0 else 0.0

    warnings: List[str] = []
    if dominant_share > 0.95:
        warnings.append(
            f"Action distribution appears degenerate: dominant action share={dominant_share:.4f} (>0.95)."
        )

    split_consistency_issues: List[str] = []
    total_samples = int(sample_id.shape[0])
    for split_name, indices in split_index.items():
        if indices.ndim != 1:
            split_consistency_issues.append(f"{split_name}: split indices must be 1D")
            continue
        if np.any(indices < 0) or np.any(indices >= total_samples):
            split_consistency_issues.append(f"{split_name}: indices out of dataset range")

    if set(split_index.keys()) != {"train", "validation", "debug"}:
        split_consistency_issues.append("Split index keys mismatch expected {train, validation, debug}")

    source_link_checks = {
        "sample_ids_unique": duplicate_count == 0,
        "sample_id_conflicts": conflict_count,
        "split_index_issues": split_consistency_issues,
    }

    if conflict_count > 0:
        warnings.append(f"Detected {conflict_count} conflicting labels for duplicate sample_id entries.")

    if split_consistency_issues:
        warnings.extend(split_consistency_issues)

    return {
        "deterministic_target_branches": conflict_count == 0,
        "duplicate_sample_id_count": duplicate_count,
        "conflicting_label_count": conflict_count,
        "action_distribution": {
            "histogram_action_type_branch0": {str(i): int(v) for i, v in enumerate(hist.tolist())},
            "dominant_action_share": dominant_share,
            "dominant_action_type": int(np.argmax(hist)) if total_cells > 0 else None,
            "degenerate_distribution": dominant_share > 0.95,
        },
        "split_structural_consistency": len(split_consistency_issues) == 0,
        "metadata_source_links": source_link_checks,
        "warnings": warnings,
    }


def compute_shape_summary(payload: Dict[str, np.ndarray], indices: np.ndarray) -> Dict[str, Any]:
    x = payload["input_tensor"][indices]
    y = payload["target_action_branches"][indices]
    return {
        "samples": int(indices.shape[0]),
        "input_tensor_shape": list(x.shape),
        "input_tensor_dtype": str(x.dtype),
        "target_action_branches_shape": list(y.shape),
        "target_action_branches_dtype": str(y.dtype),
        "target_action_branch_sizes": list(EXPECTED_BRANCH_SIZES),
        "mask_present": False,
    }


def save_split(
    split_name: str,
    indices: np.ndarray,
    payload: Dict[str, np.ndarray],
    output_dir: Path,
    source_batch_name: str,
    source_batch_dir: str,
) -> Path:
    split_path = output_dir / f"bc_{split_name}.npz"
    arrays: Dict[str, Any] = {
        "schema_version": np.asarray([SCHEMA_VERSION], dtype="U32"),
        "split": np.asarray([split_name], dtype="U16"),
        "input_tensor": payload["input_tensor"][indices],
        "target_action_branches": payload["target_action_branches"][indices],
        "sample_id": payload["sample_id"][indices],
        "episode_id": payload["episode_id"][indices],
        "step_id": payload["step_id"][indices],
        "source_episode_file": payload["source_episode_file"][indices],
        "target_action_branch_sizes": np.asarray(EXPECTED_BRANCH_SIZES, dtype=np.int32),
        "has_optional_mask": np.asarray([False], dtype=np.bool_),
        "source_batch_name": np.asarray([source_batch_name], dtype="U128"),
        "source_batch_dir": np.asarray([source_batch_dir], dtype="U512"),
    }

    if "diagnostic_reward_t" in payload:
        arrays["diagnostic_reward_t"] = payload["diagnostic_reward_t"][indices]
    if "diagnostic_done_t" in payload:
        arrays["diagnostic_done_t"] = payload["diagnostic_done_t"][indices]

    np.savez_compressed(split_path, **arrays)
    return split_path


def main() -> int:
    args = parse_args()

    adapted_batch_dir = args.adapted_batch_dir.resolve()
    if not adapted_batch_dir.exists():
        raise FileNotFoundError(f"Adapted batch dir does not exist: {adapted_batch_dir}")

    output_root = args.output_root.resolve() if args.output_root else infer_output_root(adapted_batch_dir)
    output_name = args.output_name or infer_output_name(adapted_batch_dir)
    output_dir = (output_root / output_name).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)

    day5_gate = validate_day5_status(
        adapted_batch_dir=adapted_batch_dir,
        allow_missing_or_nonpass=bool(args.allow_missing_day5_pass),
    )

    episode_paths = sorted(adapted_batch_dir.glob("episode_*.adapted.npz"))
    if not episode_paths:
        raise FileNotFoundError(f"No episode_*.adapted.npz files found in {adapted_batch_dir}")

    episodes = [load_episode(path) for path in episode_paths]
    payload = build_dataset_arrays(episodes)

    total_samples = int(payload["sample_id"].shape[0])
    if total_samples == 0:
        raise RuntimeError("No samples available in adapted batch")

    train_prob = compute_train_prob(float(args.train_ratio), float(args.val_ratio))

    train_indices: List[int] = []
    val_indices: List[int] = []
    for idx, sid in enumerate(payload["sample_id"].tolist()):
        split = assign_split(sid, train_prob=train_prob, seed=int(args.seed))
        if split == "train":
            train_indices.append(idx)
        else:
            val_indices.append(idx)

    if len(val_indices) == 0 and len(train_indices) > 1:
        val_indices.append(train_indices.pop())
    if len(train_indices) == 0 and len(val_indices) > 1:
        train_indices.append(val_indices.pop())

    debug_size = max(0, int(args.debug_size))
    ranked_train = sorted(
        train_indices,
        key=lambda i: deterministic_rank(str(payload["sample_id"][i]), int(args.seed), salt="debug"),
    )
    debug_indices = ranked_train[: min(debug_size, len(ranked_train))]

    split_index = {
        "train": np.asarray(train_indices, dtype=np.int64),
        "validation": np.asarray(val_indices, dtype=np.int64),
        "debug": np.asarray(debug_indices, dtype=np.int64),
    }

    split_files = {
        split: str(
            save_split(
                split_name=split,
                indices=indices,
                payload=payload,
                output_dir=output_dir,
                source_batch_name=adapted_batch_dir.name,
                source_batch_dir=str(adapted_batch_dir),
            )
        )
        for split, indices in split_index.items()
    }

    readiness = check_supervised_target_readiness(
        sample_id=payload["sample_id"],
        target_action_branches=payload["target_action_branches"],
        split_index=split_index,
    )

    split_summary = {
        split: compute_shape_summary(payload, indices)
        for split, indices in split_index.items()
    }

    schema = {
        "schema_version": SCHEMA_VERSION,
        "sample_structure": {
            "required": {
                "input_tensor": {
                    "dtype": "float32",
                    "shape": [24, 24, 27],
                },
                "target_action_branches": {
                    "dtype": "int16",
                    "shape": [576, 7],
                    "branch_sizes": list(EXPECTED_BRANCH_SIZES),
                },
                "metadata": {
                    "sample_id": "string",
                    "episode_id": "int32",
                    "step_id": "int32",
                    "source_episode_file": "string",
                    "split": "enum(train|validation|debug)",
                },
            },
            "optional": {
                "optional_mask": {
                    "present": False,
                    "note": "Not available in current preferred adapted batch; loader must handle absence.",
                },
            },
            "diagnostic_only": {
                "diagnostic_reward_t": "float32 per step (if available)",
                "diagnostic_done_t": "bool per step (if available)",
            },
        },
    }

    manifest = {
        "status": "success",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema_version": SCHEMA_VERSION,
        "source": {
            "adapted_batch_dir": str(adapted_batch_dir),
            "adapted_batch_name": adapted_batch_dir.name,
            "adapted_batch_summary": str(adapted_batch_dir / "adapted_batch.summary.json"),
            "conversion_report": str(adapted_batch_dir / "conversion_report.json"),
            "strict_validation": day5_gate,
        },
        "split_policy": {
            "train_ratio": float(args.train_ratio),
            "val_ratio": float(args.val_ratio),
            "derived_train_probability": train_prob,
            "debug_split_policy": "deterministic_subset_of_train",
            "debug_size_requested": int(args.debug_size),
            "seed": int(args.seed),
        },
        "schema": schema,
        "split_files": split_files,
        "split_summary": split_summary,
        "supervised_target_readiness": readiness,
    }

    write_json(output_dir / "bc_manifest.json", manifest)

    summary = {
        "status": "success",
        "output_dir": str(output_dir),
        "schema_version": SCHEMA_VERSION,
        "total_samples": total_samples,
        "split_counts": {k: int(v.shape[0]) for k, v in split_index.items()},
        "warnings": readiness.get("warnings", []),
    }
    write_json(output_dir / "bc_summary.json", summary)

    print(json.dumps(summary, ensure_ascii=True, indent=2))
    print(f"Manifest: {output_dir / 'bc_manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
