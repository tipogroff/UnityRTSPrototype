#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_INVENTORY = Path("python/stage7b_teacher_replay/stage7b_teacher_replay_source_inventory.json")
DEFAULT_REPORT_JSON = Path("python/stage7b_teacher_replay/stage7b_teacher_replay_prep_report.json")
DEFAULT_PREVIEW_JSONL = Path("python/stage7b_teacher_replay/stage7b_teacher_replay_candidate_preview.jsonl")

DROP_REASONS = [
    "source_schema_unknown",
    "missing_initial_state",
    "missing_runtime_state",
    "missing_teacher_action",
    "unsupported_action_format",
    "branch_contract_mismatch",
    "attack_target_contract_mismatch",
    "state_sync_failed",
    "observation_mismatch",
    "teacher_noop",
    "multiple_nonnoop_actors",
    "no_matching_actor",
    "action_type_unsupported",
    "action_not_legal_in_unity",
    "direction_mismatch",
    "produce_type_mismatch",
    "attack_target_mismatch",
    "candidate_overflow",
    "runtime_apply_rejected",
    "runtime_desync",
    "terminal_mismatch",
    "unknown",
]

ACTION_TYPE_NAMES = {
    0: "NoOp",
    1: "Move",
    2: "Harvest",
    3: "Return",
    4: "Produce",
    5: "Attack",
}


EXPECTED_BRANCH_SIZES = [6, 4, 4, 4, 4, 7, 49]
EXPECTED_ATTACK_TARGET_SIZE = 49
EXPECTED_ATTACK_TARGET_CENTER = 24
EXPECTED_CANDIDATE_BRANCH_SIZE = 128


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Stage7B teacher replay prep report package.")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--preview-jsonl", type=Path, default=DEFAULT_PREVIEW_JSONL)
    parser.add_argument("--preview-limit", type=int, default=512)
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def load_inventory(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing source inventory: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_teacher_action(actions: np.ndarray) -> tuple[dict[str, Any], str | None]:
    if actions.ndim != 2 or actions.shape[0] != 576 or actions.shape[1] != 7:
        return {}, "unsupported_action_format"

    action_type = actions[:, 0]
    nonnoop = np.flatnonzero(action_type != 0)

    if nonnoop.size == 0:
        return {
            "action_type": "NoOp",
            "actor_flat": None,
        }, "teacher_noop"

    if nonnoop.size > 1:
        return {
            "action_type": "Mixed",
            "nonnoop_actor_count": int(nonnoop.size),
        }, "multiple_nonnoop_actors"

    actor_flat = int(nonnoop[0])
    at = int(action_type[actor_flat])
    summary = {
        "actor_flat": actor_flat,
        "action_type": ACTION_TYPE_NAMES.get(at, f"Unknown({at})"),
        "move_dir": int(actions[actor_flat, 1]),
        "harvest_dir": int(actions[actor_flat, 2]),
        "return_dir": int(actions[actor_flat, 3]),
        "produce_dir": int(actions[actor_flat, 4]),
        "produce_type": int(actions[actor_flat, 5]),
        "attack_target_local": int(actions[actor_flat, 6]),
    }

    if at < 0 or at >= EXPECTED_BRANCH_SIZES[0]:
        return summary, "action_type_unsupported"

    return summary, None


def build_preview_and_stats(npz_path: Path, preview_path: Path, limit: int) -> dict[str, Any]:
    drop_hist = Counter({r: 0 for r in DROP_REASONS})
    match_by_action = Counter()
    drop_by_action = Counter()

    steps_total = 0
    nonnoop_total = 0

    with np.load(npz_path, allow_pickle=True) as npz:
        if "per_cell_action_t" in npz:
            actions_t = np.asarray(npz["per_cell_action_t"])
        elif "actions" in npz:
            actions_t = np.asarray(npz["actions"])
        else:
            raise KeyError("Missing action array: expected per_cell_action_t or actions")

        episode_id = np.asarray(npz["episode_id"]) if "episode_id" in npz else np.zeros((actions_t.shape[0],), dtype=np.int32)
        step_id = np.asarray(npz["step_id"]) if "step_id" in npz else np.arange(actions_t.shape[0], dtype=np.int32)
        done_t = np.asarray(npz["done_t"]) if "done_t" in npz else np.zeros((actions_t.shape[0],), dtype=np.bool_)
        terminated_t = np.asarray(npz["terminated_t"]) if "terminated_t" in npz else np.zeros((actions_t.shape[0],), dtype=np.bool_)
        truncated_t = np.asarray(npz["truncated_t"]) if "truncated_t" in npz else np.zeros((actions_t.shape[0],), dtype=np.bool_)

        steps_total = int(actions_t.shape[0])
        limit = min(limit, steps_total)

        preview_path.parent.mkdir(parents=True, exist_ok=True)
        with preview_path.open("w", encoding="utf-8") as handle:
            for i in range(limit):
                action_summary, action_drop = _resolve_teacher_action(np.asarray(actions_t[i]))
                action_name = action_summary.get("action_type", "Unknown")

                preview_item: dict[str, Any] = {
                    "sample_index": int(i),
                    "episode_id": int(episode_id[i]),
                    "step_id": int(step_id[i]),
                    "done_t": bool(done_t[i]),
                    "terminated_t": bool(terminated_t[i]),
                    "truncated_t": bool(truncated_t[i]),
                    "teacher_action": action_summary,
                    "state_sync_success": False,
                    "candidate_match": False,
                    "runtime_apply_success": False,
                }

                if action_drop is None:
                    drop_hist["missing_initial_state"] += 1
                    drop_by_action[action_name] += 1
                    nonnoop_total += 1
                    preview_item["drop_reason"] = "missing_initial_state"
                else:
                    drop_hist[action_drop] += 1
                    if action_drop == "multiple_nonnoop_actors":
                        nonnoop_total += 1
                        drop_by_action[action_name] += 1
                    elif action_drop == "teacher_noop":
                        pass
                    else:
                        drop_by_action[action_name] += 1
                    preview_item["drop_reason"] = action_drop

                handle.write(json.dumps(preview_item, ensure_ascii=True) + "\n")

    return {
        "steps_total": steps_total,
        "steps_replay_attempted": 0,
        "state_sync_success_count": 0,
        "state_sync_failed_count": 0,
        "candidate_match_count": 0,
        "candidate_drop_count": int(sum(drop_hist.values())),
        "candidate_match_rate": None,
        "nonoop_total": int(nonnoop_total),
        "nonoop_candidate_match_count": 0,
        "nonoop_candidate_match_rate": None,
        "runtime_apply_attempted_count": 0,
        "runtime_apply_accepted_count": 0,
        "runtime_apply_rejected_count": 0,
        "runtime_apply_accept_rate": None,
        "candidate_count_min": None,
        "candidate_count_mean": None,
        "candidate_count_max": None,
        "candidate_overflow_count": 0,
        "drop_reason_histogram": {k: int(v) for k, v in drop_hist.items()},
        "match_by_action_type": {k: int(v) for k, v in match_by_action.items()},
        "drop_by_action_type": {k: int(v) for k, v in drop_by_action.items()},
        "terminal_match_count": 0,
        "terminal_mismatch_count": 0,
    }


def main() -> int:
    args = parse_args()
    inventory_path = resolve(args.inventory)
    report_path = resolve(args.report_json)
    preview_path = resolve(args.preview_jsonl)

    inventory = load_inventory(inventory_path)

    selected_source_path = inventory.get("selected_source_path")
    selected_source_format = inventory.get("selected_source_format")
    selected_ready = bool(inventory.get("selected_source_replay_ready", False))

    selected_item = None
    for item in inventory.get("sources", []):
        if item.get("path") == selected_source_path:
            selected_item = item
            break

    if not selected_item:
        raise RuntimeError("Selected source was not found in source inventory")

    source_dir = resolve(Path(selected_source_path))
    npz_name = selected_item.get("npz_file")
    if not npz_name:
        raise RuntimeError("Selected source has no NPZ file")

    npz_path = source_dir / npz_name
    if not npz_path.exists():
        raise FileNotFoundError(f"Missing selected NPZ: {npz_path}")

    preview_stats = build_preview_and_stats(npz_path, preview_path, int(max(1, args.preview_limit)))

    episodes_scanned = int(selected_item.get("episodes_count") or 0)

    # Stage7B-6B prep gate stays honest: without authoritative runtime state, replay cannot be attempted.
    replay_attempt_possible = selected_ready

    report: dict[str, Any] = {
        "generated_at_utc": now_iso(),
        "status": "GO" if replay_attempt_possible else "NO_GO",
        "stage": "Stage7B-6B Prep",
        "summary": (
            "Selected source is replay-ready for Unity trajectory replay."
            if replay_attempt_possible
            else "No replay-ready trajectory source with authoritative runtime state; new export with replay fields required."
        ),
        "source_inventory": inventory,
        "selected_source_path": selected_source_path,
        "selected_source_format": selected_source_format,
        "episodes_scanned": episodes_scanned,
        "episodes_replay_attempted": 0,
        "metrics": {
            "source_inventory": inventory_path.as_posix(),
            "selected_source_path": selected_source_path,
            "selected_source_format": selected_source_format,
            "episodes_scanned": episodes_scanned,
            "episodes_replay_attempted": 0,
            **preview_stats,
            "demo_recording_ready": False,
        },
        "contract": {
            "candidate_branch_size": EXPECTED_CANDIDATE_BRANCH_SIZE,
            "candidate_noop_index": 0,
            "attack_target_size": EXPECTED_ATTACK_TARGET_SIZE,
            "attack_target_center_index": EXPECTED_ATTACK_TARGET_CENTER,
            "branch_sizes": EXPECTED_BRANCH_SIZES,
        },
        "artifacts": {
            "source_inventory_json": inventory_path.as_posix(),
            "prep_report_json": report_path.as_posix(),
            "candidate_preview_jsonl": preview_path.as_posix(),
            "prep_report_md": "python/stage7b_teacher_replay/stage7b_teacher_replay_prep_report.md",
        },
        "no_go_reasons": (
            [
                "missing_initial_state",
                "missing_runtime_state",
                "state_sync_failed",
            ]
            if not replay_attempt_possible
            else []
        ),
        "notes": [
            "ML-Agents training/PPO/imitation/demo were not started in this prep package build.",
            "Candidate truth must come from Unity runtime MlAgentsCandidateActionBuilder on synchronized state.",
            "This package is a prep gate artifact, not a training artifact.",
        ],
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"[Stage7B][TeacherReplay] Prep report written: {report_path.as_posix()}")
    print(f"[Stage7B][TeacherReplay] Candidate preview written: {preview_path.as_posix()}")
    print(f"[Stage7B][TeacherReplay] status={report['status']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
