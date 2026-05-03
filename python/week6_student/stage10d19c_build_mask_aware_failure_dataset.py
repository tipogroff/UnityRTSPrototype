#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Mapping

import numpy as np

from stage10d19b_common import (
    ACTION_TYPE_MOVE,
    ACTION_TYPE_NAMES,
    ACTION_TYPE_NOOP,
    B2_FLAT,
    C3_FLAT,
    ensure_payload_defaults,
    get_observations_and_actions,
    load_split_payload,
    merge_original_and_augmented,
    pick_reference_action_vectors,
    resolve_path,
    save_split_npz,
    summarize_action_type_distribution,
    utc_dir_stamp,
    utc_now_iso,
    write_json,
    write_jsonl,
)
from stage10d19c_common import move_target


OBS_SHAPE = (576, 27)
ACTION_SHAPE = (576, 7)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.19C build mask-aware failure augmented BC dataset")
    p.add_argument(
        "--base-bc-ready-dir",
        type=Path,
        default=Path("python/week6_student/bc_ready/legacy032_v2_stage10d19b_valid_move_augmented_bc_ready_20260503T191829Z"),
    )
    p.add_argument(
        "--fallback-base-bc-ready-dir",
        type=Path,
        default=Path("python/week6_student/bc_ready/legacy032_v2_stage10d17_movement_augmented_bc_ready_20260503T162905Z"),
    )
    p.add_argument(
        "--failure-cases-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d19c_occupied_move_failure_cases.json"),
    )
    p.add_argument(
        "--output-root",
        type=Path,
        default=Path("python/week6_student/bc_ready"),
    )
    p.add_argument("--run-label", type=str, default="legacy032_v2_stage10d19c_mask_aware_failure_augmented_bc_ready")
    p.add_argument("--max-family-a-noop", type=int, default=1200)
    p.add_argument("--max-family-b-valid-alt", type=int, default=1800)
    p.add_argument("--max-family-c-hard-negative", type=int, default=1800)
    p.add_argument("--max-family-d-off-actor-negative", type=int, default=1800)
    p.add_argument("--max-family-f-preservation", type=int, default=1200)
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--seed", type=int, default=1919)
    return p.parse_args()


def _init_collector() -> Dict[str, List[np.ndarray]]:
    return {
        "observations": [],
        "actions": [],
        "episode_id": [],
        "step_id": [],
        "reward_t": [],
        "done_t": [],
        "terminated_t": [],
        "truncated_t": [],
        "action_mask_available_t": [],
    }


def _append_row(
    collector: Dict[str, List[np.ndarray]],
    *,
    observation: np.ndarray,
    action: np.ndarray,
    source_payload: Mapping[str, np.ndarray],
    source_sample_index: int,
) -> None:
    collector["observations"].append(np.asarray(observation, dtype=np.float32))
    collector["actions"].append(np.asarray(action, dtype=np.int16))
    collector["episode_id"].append(np.asarray(source_payload["episode_id"][source_sample_index], dtype=np.int32))
    collector["step_id"].append(np.asarray(source_payload["step_id"][source_sample_index], dtype=np.int32))
    collector["reward_t"].append(np.asarray(source_payload["reward_t"][source_sample_index], dtype=np.float32))
    collector["done_t"].append(np.asarray(source_payload["done_t"][source_sample_index], dtype=np.bool_))
    collector["terminated_t"].append(np.asarray(source_payload["terminated_t"][source_sample_index], dtype=np.bool_))
    collector["truncated_t"].append(np.asarray(source_payload["truncated_t"][source_sample_index], dtype=np.bool_))
    collector["action_mask_available_t"].append(np.asarray(source_payload["action_mask_available_t"][source_sample_index], dtype=np.bool_))


def _stack_collector(collector: Mapping[str, List[np.ndarray]]) -> Dict[str, np.ndarray]:
    out: Dict[str, np.ndarray] = {}
    for key, vals in collector.items():
        if not vals:
            if key == "observations":
                out[key] = np.zeros((0, 576, 27), dtype=np.float32)
            elif key == "actions":
                out[key] = np.zeros((0, 576, 7), dtype=np.int16)
            elif key == "reward_t":
                out[key] = np.zeros((0,), dtype=np.float32)
            elif key in {"done_t", "terminated_t", "truncated_t", "action_mask_available_t"}:
                out[key] = np.zeros((0,), dtype=np.bool_)
            else:
                out[key] = np.zeros((0,), dtype=np.int32)
            continue

        if key in {"observations", "actions"}:
            out[key] = np.stack(vals, axis=0)
        elif key == "reward_t":
            out[key] = np.asarray(vals, dtype=np.float32)
        elif key in {"done_t", "terminated_t", "truncated_t", "action_mask_available_t"}:
            out[key] = np.asarray(vals, dtype=np.bool_)
        else:
            out[key] = np.asarray(vals, dtype=np.int32)
    return out


def _split_choice(rng: np.random.Generator, train_ratio: float) -> str:
    return "train" if float(rng.random()) < train_ratio else "validation"


def _set_target_action(
    action_map: np.ndarray,
    *,
    source_flat: int,
    action_type: int,
    move_dir: int,
    b2_vec: np.ndarray,
    c3_vec: np.ndarray,
) -> np.ndarray:
    out = np.asarray(action_map, dtype=np.int16).copy()
    out[source_flat, :] = 0
    out[source_flat, 0] = int(action_type)
    out[source_flat, 1] = int(move_dir)
    out[B2_FLAT, :] = np.asarray(b2_vec, dtype=np.int16)
    out[C3_FLAT, :] = np.asarray(c3_vec, dtype=np.int16)
    return out


def _choose_off_actor_cells(obs: np.ndarray, anchors: List[int], limit: int = 4) -> List[int]:
    chosen: List[int] = []
    for a in anchors:
        if a < 0 or a >= 576:
            continue
        ax, ay = int(a % 24), int(a // 24)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx, ny = ax + dx, ay + dy
                if nx < 0 or nx >= 24 or ny < 0 or ny >= 24:
                    continue
                flat = int(ny * 24 + nx)
                has_unit = bool(np.sum(obs[flat, 5:12]) > 0.5)
                owner_self = bool(obs[flat, 3] > 0.5)
                if has_unit and owner_self:
                    continue
                if flat not in chosen:
                    chosen.append(flat)
                if len(chosen) >= limit:
                    return chosen
    return chosen


def _load_failure_cases(path: Path) -> List[Dict[str, Any]]:
    payload = __import__("json").loads(resolve_path(path).read_text(encoding="utf-8"))
    return list(payload.get("failure_cases", []))


def main() -> int:
    args = parse_args()
    rng = np.random.default_rng(int(args.seed))

    base_dir = resolve_path(args.base_bc_ready_dir)
    if not base_dir.exists():
        base_dir = resolve_path(args.fallback_base_bc_ready_dir)

    output_root = resolve_path(args.output_root)
    out_dir = output_root / f"{args.run_label}_{utc_dir_stamp()}"
    out_dir.mkdir(parents=True, exist_ok=False)

    train_raw = load_split_payload(base_dir / "bc_train.npz")
    val_raw = load_split_payload(base_dir / "bc_validation.npz")
    train_obs, train_actions = get_observations_and_actions(train_raw)
    val_obs, val_actions = get_observations_and_actions(val_raw)
    train_payload = ensure_payload_defaults(train_raw, train_obs.shape[0])
    val_payload = ensure_payload_defaults(val_raw, val_obs.shape[0])

    b2_vec, c3_vec = pick_reference_action_vectors(train_actions)

    failure_cases = _load_failure_cases(args.failure_cases_json)

    collectors = {"train": _init_collector(), "validation": _init_collector()}
    metadata = {"train": [], "validation": []}
    fam_counts: Counter[str] = Counter()
    skipped: Counter[str] = Counter()
    blocked_dir_counter: Counter[str] = Counter()
    chosen_alt_counter: Counter[str] = Counter()

    base_train_n = int(train_obs.shape[0])
    base_val_n = int(val_obs.shape[0])

    # Families A/B/C from failure cases.
    for case_idx, case in enumerate(failure_cases):
        src_flat = int((case.get("source_cell") or {}).get("flat", -1))
        if src_flat < 0 or src_flat >= 576:
            skipped["invalid_source_cell"] += 1
            continue

        alt_dirs = [int(d) for d in (case.get("alternative_free_dirs") or []) if int(d) in (0, 1, 2, 3)]
        pred_dir = int(case.get("predicted_move_dir", -1))
        if pred_dir in (0, 1, 2, 3):
            blocked_dir_counter[str(pred_dir)] += 1

        split = _split_choice(rng, float(args.train_ratio))
        src_index = int(rng.integers(0, base_train_n if split == "train" else base_val_n))
        base_obs = train_obs[src_index] if split == "train" else val_obs[src_index]
        base_act = train_actions[src_index] if split == "train" else val_actions[src_index]
        payload = train_payload if split == "train" else val_payload

        # Family A: no valid alternative -> NoOp, plus sparse justified NoOp controls
        # when alternatives exist to counter blocked-direction overconfidence.
        add_family_a = (not alt_dirs) or (bool(alt_dirs) and (case_idx % 6 == 0))
        if add_family_a and fam_counts["family_a_no_valid_alt_noop"] < int(args.max_family_a_noop):
            new_act = _set_target_action(
                base_act,
                source_flat=src_flat,
                action_type=ACTION_TYPE_NOOP,
                move_dir=0,
                b2_vec=b2_vec,
                c3_vec=c3_vec,
            )
            _append_row(collectors[split], observation=base_obs, action=new_act, source_payload=payload, source_sample_index=src_index)
            fam_a_reason = "no_valid_alternative_dir" if not alt_dirs else "policy_noop_control_for_blocked_dir"
            metadata[split].append(
                {
                    "augmentation_family": "family_a_no_valid_alt_noop",
                    "split": split,
                    "source_step": int(case.get("step", -1)),
                    "failure_case_id": case.get("case_id"),
                    "source_cell": src_flat,
                    "target_action_type": int(ACTION_TYPE_NOOP),
                    "chosen_move_dir": 0,
                    "reason": fam_a_reason,
                    "blocked_predicted_dir": pred_dir,
                    "blocked_target_occupancy": case.get("target_occupancy_type", "unknown"),
                    "target_move_legal_under_mask": False,
                    "off_actor_control": False,
                    "preservation_sample": False,
                }
            )
            fam_counts["family_a_no_valid_alt_noop"] += 1

        # Family B: valid alternative Move.
        if alt_dirs and fam_counts["family_b_valid_alt_move"] < int(args.max_family_b_valid_alt):
            # Deterministic ordering east, south, north, west with fallback first available.
            pref_order = [1, 2, 0, 3]
            chosen = next((d for d in pref_order if d in alt_dirs), alt_dirs[0])
            chosen_alt_counter[str(chosen)] += 1

            tgt, inb = move_target(src_flat, chosen)
            if (not inb) or tgt is None:
                skipped["family_b_alt_oob"] += 1
            else:
                new_act = _set_target_action(
                    base_act,
                    source_flat=src_flat,
                    action_type=ACTION_TYPE_MOVE,
                    move_dir=int(chosen),
                    b2_vec=b2_vec,
                    c3_vec=c3_vec,
                )
                _append_row(collectors[split], observation=base_obs, action=new_act, source_payload=payload, source_sample_index=src_index)
                metadata[split].append(
                    {
                        "augmentation_family": "family_b_valid_alt_move",
                        "split": split,
                        "source_step": int(case.get("step", -1)),
                        "failure_case_id": case.get("case_id"),
                        "source_cell": src_flat,
                        "target_action_type": int(ACTION_TYPE_MOVE),
                        "chosen_move_dir": int(chosen),
                        "chosen_target_cell": int(tgt),
                        "reason": "valid_alternative_dir_available",
                        "blocked_predicted_dir": pred_dir,
                        "blocked_target_occupancy": case.get("target_occupancy_type", "unknown"),
                        "target_move_legal_under_mask": True,
                        "target_cell_in_bounds": True,
                        "target_cell_free": True,
                        "target_adjacent": True,
                        "off_actor_control": False,
                        "preservation_sample": False,
                    }
                )
                fam_counts["family_b_valid_alt_move"] += 1

        # Family C: hard-negative for blocked direction.
        if fam_counts["family_c_blocked_dir_hard_negative"] < int(args.max_family_c_hard_negative):
            hard_action = ACTION_TYPE_NOOP
            hard_dir = 0
            if alt_dirs and fam_counts["family_b_valid_alt_move"] < int(args.max_family_b_valid_alt):
                # Keep as NoOp to avoid overfitting all negatives to Move.
                pass
            new_act = _set_target_action(
                base_act,
                source_flat=src_flat,
                action_type=hard_action,
                move_dir=hard_dir,
                b2_vec=b2_vec,
                c3_vec=c3_vec,
            )
            _append_row(collectors[split], observation=base_obs, action=new_act, source_payload=payload, source_sample_index=src_index)
            metadata[split].append(
                {
                    "augmentation_family": "family_c_blocked_dir_hard_negative",
                    "split": split,
                    "source_step": int(case.get("step", -1)),
                    "failure_case_id": case.get("case_id"),
                    "source_cell": src_flat,
                    "target_action_type": int(ACTION_TYPE_NOOP),
                    "chosen_move_dir": 0,
                    "reason": "blocked_predicted_direction_hard_negative",
                    "blocked_predicted_dir": pred_dir,
                    "blocked_target_occupancy": case.get("target_occupancy_type", "unknown"),
                    "target_move_legal_under_mask": False,
                    "off_actor_control": False,
                    "preservation_sample": False,
                }
            )
            fam_counts["family_c_blocked_dir_hard_negative"] += 1

        # Family D: off-actor hard negatives near congestion anchors.
        if fam_counts["family_d_off_actor_hard_negative"] < int(args.max_family_d_off_actor_negative):
            anchors = [
                src_flat,
                int((case.get("predicted_target_cell") or {}).get("flat", -1)),
                25,
                50,
            ]
            off_cells = _choose_off_actor_cells(base_obs, anchors, limit=3)
            for off_flat in off_cells:
                if fam_counts["family_d_off_actor_hard_negative"] >= int(args.max_family_d_off_actor_negative):
                    break
                new_act = np.asarray(base_act, dtype=np.int16).copy()
                new_act[off_flat, :] = 0
                new_act[off_flat, 0] = ACTION_TYPE_NOOP
                new_act[B2_FLAT, :] = np.asarray(b2_vec, dtype=np.int16)
                new_act[C3_FLAT, :] = np.asarray(c3_vec, dtype=np.int16)
                _append_row(collectors[split], observation=base_obs, action=new_act, source_payload=payload, source_sample_index=src_index)
                metadata[split].append(
                    {
                        "augmentation_family": "family_d_off_actor_hard_negative",
                        "split": split,
                        "source_step": int(case.get("step", -1)),
                        "failure_case_id": case.get("case_id"),
                        "source_cell": int(off_flat),
                        "target_action_type": int(ACTION_TYPE_NOOP),
                        "chosen_move_dir": 0,
                        "reason": "off_actor_hard_negative_near_failure_congestion",
                        "off_actor_control": True,
                        "target_move_legal_under_mask": False,
                        "preservation_sample": False,
                    }
                )
                fam_counts["family_d_off_actor_hard_negative"] += 1

    # Family F: preservation rows copied from base samples.
    preserve_target = int(args.max_family_f_preservation)
    for _ in range(preserve_target):
        split = _split_choice(rng, float(args.train_ratio))
        src_index = int(rng.integers(0, base_train_n if split == "train" else base_val_n))
        base_obs = train_obs[src_index] if split == "train" else val_obs[src_index]
        base_act = train_actions[src_index] if split == "train" else val_actions[src_index]
        payload = train_payload if split == "train" else val_payload

        _append_row(collectors[split], observation=base_obs, action=base_act, source_payload=payload, source_sample_index=src_index)
        metadata[split].append(
            {
                "augmentation_family": "family_f_preservation",
                "split": split,
                "source_step": int(payload["step_id"][src_index]) if "step_id" in payload else -1,
                "failure_case_id": None,
                "source_cell": -1,
                "target_action_type": -1,
                "chosen_move_dir": -1,
                "reason": "preservation_rows_b2_c3_movement_produce_attack",
                "off_actor_control": False,
                "target_move_legal_under_mask": True,
                "preservation_sample": True,
            }
        )
        fam_counts["family_f_preservation"] += 1

    aug_train = _stack_collector(collectors["train"])
    aug_val = _stack_collector(collectors["validation"])

    merged_train = merge_original_and_augmented(train_payload, aug_train, split_name="train")
    merged_val = merge_original_and_augmented(val_payload, aug_val, split_name="validation")

    save_split_npz(out_dir / "bc_train.npz", merged_train)
    save_split_npz(out_dir / "bc_validation.npz", merged_val)

    debug_n = min(128, int(merged_val["observations"].shape[0]))
    debug_payload = {k: np.asarray(v)[:debug_n] for k, v in merged_val.items() if np.asarray(v).shape[0] == merged_val["observations"].shape[0]}
    save_split_npz(out_dir / "bc_debug.npz", debug_payload)

    write_jsonl(out_dir / "stage10d19c_augmented_sample_metadata_train.jsonl", metadata["train"])
    write_jsonl(out_dir / "stage10d19c_augmented_sample_metadata_validation.jsonl", metadata["validation"])

    before_dist = {
        "train": summarize_action_type_distribution(train_obs, train_actions),
        "validation": summarize_action_type_distribution(val_obs, val_actions),
    }
    after_dist = {
        "train": summarize_action_type_distribution(merged_train["observations"], merged_train["actions"]),
        "validation": summarize_action_type_distribution(merged_val["observations"], merged_val["actions"]),
    }

    manifest = {
        "stage": "10D.19C",
        "task": "build_mask_aware_failure_dataset",
        "generated_at_utc": utc_now_iso(),
        "output_dataset_dir": str(out_dir.as_posix()),
        "base_dataset_path": str(base_dir.as_posix()),
        "failure_case_source_artifacts": {
            "failure_cases_json": str(resolve_path(args.failure_cases_json).as_posix()),
        },
        "counts": {
            "original_train": int(train_obs.shape[0]),
            "original_validation": int(val_obs.shape[0]),
            "merged_train_count": int(merged_train["observations"].shape[0]),
            "merged_validation_count": int(merged_val["observations"].shape[0]),
            "augmented_train_count": int(aug_train["observations"].shape[0]),
            "augmented_validation_count": int(aug_val["observations"].shape[0]),
        },
        "augmentation_family_counts": {k: int(v) for k, v in fam_counts.items()},
        "no_valid_alt_count": int(fam_counts.get("family_a_no_valid_alt_noop", 0)),
        "valid_alt_count": int(fam_counts.get("family_b_valid_alt_move", 0)),
        "hard_negative_count": int(fam_counts.get("family_c_blocked_dir_hard_negative", 0)),
        "off_actor_negative_count": int(fam_counts.get("family_d_off_actor_hard_negative", 0)),
        "preservation_count": int(fam_counts.get("family_f_preservation", 0)),
        "skipped_counts_and_reasons": {k: int(v) for k, v in skipped.items()},
        "label_distribution_before_after": {"before": before_dist, "after": after_dist},
        "move_dir_distribution": dict(
            Counter({k: int(v) for k, v in chosen_alt_counter.items()})
        ),
        "blocked_dir_distribution": {k: int(v) for k, v in blocked_dir_counter.items()},
        "chosen_alt_dir_distribution": {k: int(v) for k, v in chosen_alt_counter.items()},
        "explicit_non_claims": [
            "no PPO",
            "no teacher mutation",
            "no runtime semantic changes",
            "no force movement",
            "no attack augmentation",
            "no Unity rerun in Stage10D.19C",
        ],
        "config": {
            "max_family_a_noop": int(args.max_family_a_noop),
            "max_family_b_valid_alt": int(args.max_family_b_valid_alt),
            "max_family_c_hard_negative": int(args.max_family_c_hard_negative),
            "max_family_d_off_actor_negative": int(args.max_family_d_off_actor_negative),
            "max_family_f_preservation": int(args.max_family_f_preservation),
            "train_ratio": float(args.train_ratio),
            "seed": int(args.seed),
        },
    }

    write_json(out_dir / "bc_manifest.json", manifest)
    write_json(out_dir / "stage10d19c_mask_aware_failure_augmentation_manifest.json", manifest)

    print(out_dir.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
