#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_SOURCE_DIR = Path(
    "python/week5_teacher_legacy032/teacher_replay_exports/stage7b_replay_ready_stage7b6g_smoke_20260510T131624Z"
)
DEFAULT_OUTPUT_DIR = Path("python/stage7b_teacher_replay")
DEFAULT_SUFFIX = "after_6g"

EXPECTED_BRANCH_SIZES = [6, 4, 4, 4, 4, 7, 49]
EXPECTED_ATTACK_TARGET_SIZE = 49
EXPECTED_ATTACK_TARGET_CENTER = 24
EXPECTED_OBSERVATION_SHAPE = [24, 24, 27]
EXPECTED_ACTION_SHAPE = [576, 7]

DROP_REASONS = [
    "source_not_replay_ready",
    "manifest_contract_mismatch",
    "missing_initial_state",
    "missing_runtime_state_t",
    "missing_runtime_state_tp1",
    "missing_teacher_commands",
    "state_sync_failed",
    "actor_not_found",
    "actor_type_mismatch",
    "actor_owner_mismatch",
    "action_type_unsupported",
    "action_not_legal_in_unity",
    "direction_mismatch",
    "produce_type_mismatch",
    "attack_target_mismatch",
    "candidate_overflow",
    "no_matching_candidate",
    "runtime_apply_rejected",
    "post_state_desync",
    "observation_mismatch",
    "terminal_mismatch",
    "unknown",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage7B-6B rerun prep on replay-ready export source.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--suffix", type=str, default=DEFAULT_SUFFIX)
    parser.add_argument("--preview-limit", type=int, default=2048)
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing json file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def parse_json_value(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    text = str(raw).strip()
    if text == "":
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def canonical_terminal_type(done: bool, terminated: bool, truncated: bool) -> str:
    if terminated:
        return "terminated"
    if truncated:
        return "truncated"
    if done:
        return "done"
    return "none"


def validate_manifest_contract(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if bool(manifest.get("replay_ready")) is not True:
        errors.append("replay_ready != true")
    if list(manifest.get("branch_sizes") or []) != EXPECTED_BRANCH_SIZES:
        errors.append("branch_sizes mismatch")
    if int(manifest.get("attack_target_size", -1)) != EXPECTED_ATTACK_TARGET_SIZE:
        errors.append("attack_target_size mismatch")
    if int(manifest.get("attack_target_center_index", -1)) != EXPECTED_ATTACK_TARGET_CENTER:
        errors.append("attack_target_center_index mismatch")
    if list(manifest.get("observation_shape") or []) != EXPECTED_OBSERVATION_SHAPE:
        errors.append("observation_shape mismatch")
    if list(manifest.get("action_shape") or []) != EXPECTED_ACTION_SHAPE:
        errors.append("action_shape mismatch")
    return errors


def build_markdown(report: dict[str, Any]) -> str:
    metrics = report.get("metrics", {})
    lines: list[str] = []
    lines.append("# Stage7B Teacher Replay Prep Report (After 6G)")
    lines.append("")
    lines.append("## Status")
    lines.append("")
    lines.append(f"- stage: {report.get('stage')}")
    lines.append(f"- status: {report.get('status')}")
    lines.append(f"- generated_at_utc: {report.get('generated_at_utc')}")
    lines.append(f"- summary: {report.get('summary')}")
    lines.append("")
    lines.append("## Source")
    lines.append("")
    lines.append(f"- source_dir: {report.get('selected_source_path')}")
    lines.append(f"- replay_ready: {report.get('selected_source_replay_ready')}")
    lines.append(f"- replay_manifest: {report.get('replay_manifest_path')}")
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    ordered = [
        "episodes_scanned",
        "episodes_replay_attempted",
        "steps_total",
        "steps_replay_attempted",
        "teacher_commands_total",
        "teacher_nonnoop_commands_total",
        "state_sync_success_count",
        "state_sync_failed_count",
        "pre_observation_match_count",
        "pre_observation_mismatch_count",
        "candidate_count_min",
        "candidate_count_mean",
        "candidate_count_max",
        "candidate_overflow_count",
        "candidate_match_count",
        "candidate_drop_count",
        "candidate_match_rate",
        "nonoop_candidate_match_count",
        "nonoop_candidate_match_rate",
        "runtime_apply_attempted_count",
        "runtime_apply_accepted_count",
        "runtime_apply_rejected_count",
        "runtime_apply_accept_rate",
        "post_state_match_count",
        "post_state_mismatch_count",
        "terminal_match_count",
        "terminal_mismatch_count",
        "demo_recording_ready",
    ]
    for key in ordered:
        lines.append(f"- {key}: {metrics.get(key)}")

    lines.append("")
    lines.append("## Drop Reason Histogram")
    lines.append("")
    hist = metrics.get("drop_reason_histogram", {})
    if hist:
        for key in sorted(hist.keys()):
            lines.append(f"- {key}: {hist[key]}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    for note in report.get("notes", []):
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    source_dir = resolve(args.source_dir)
    output_dir = resolve(args.output_dir)
    suffix = str(args.suffix).strip() or "after_6g"
    preview_limit = max(1, int(args.preview_limit))

    manifest_path = source_dir / "replay_manifest.json"
    report_path = source_dir / "stage7b_replay_ready_export_report.json"
    manifest = load_json(manifest_path)
    source_report = load_json(report_path)

    episode_npz_paths = sorted(source_dir.glob("episode_*.replay_ready.npz"))
    episode_jsonl_paths = sorted(source_dir.glob("episode_*.replay_ready.jsonl"))
    jsonl_by_stem = {p.stem.replace(".replay_ready", ""): p for p in episode_jsonl_paths}

    inventory_output = output_dir / f"stage7b_teacher_replay_source_inventory_{suffix}.json"
    prep_report_output = output_dir / f"stage7b_teacher_replay_prep_report_{suffix}.json"
    prep_md_output = output_dir / f"stage7b_teacher_replay_prep_report_{suffix}.md"
    preview_output = output_dir / f"stage7b_teacher_replay_candidate_preview_{suffix}.jsonl"

    manifest_errors = validate_manifest_contract(manifest)
    replay_ready = bool(manifest.get("replay_ready", False))

    source_inventory = {
        "generated_at_utc": now_iso(),
        "selected_source_path": source_dir.as_posix(),
        "selected_source_format": "legacy032_replay_ready_export",
        "selected_source_replay_ready": replay_ready,
        "source_report_replay_ready": bool(source_report.get("replay_ready", False)),
        "manifest_validation_errors": manifest_errors,
        "episode_npz_count": len(episode_npz_paths),
        "episode_jsonl_count": len(episode_jsonl_paths),
        "replay_manifest_path": manifest_path.as_posix(),
        "stage7b_export_report_path": report_path.as_posix(),
        "required_files": {
            "replay_manifest_json": manifest_path.exists(),
            "episode_replay_ready_npz": len(episode_npz_paths) > 0,
            "episode_replay_ready_jsonl": len(episode_jsonl_paths) > 0,
            "stage7b_replay_ready_export_report": report_path.exists(),
        },
    }

    metrics: dict[str, Any] = {
        "episodes_scanned": len(episode_npz_paths),
        "episodes_replay_attempted": len(episode_npz_paths),
        "steps_total": 0,
        "steps_replay_attempted": 0,
        "teacher_commands_total": 0,
        "teacher_nonnoop_commands_total": 0,
        "state_sync_success_count": 0,
        "state_sync_failed_count": 0,
        "pre_observation_match_count": 0,
        "pre_observation_mismatch_count": 0,
        "candidate_count_min": None,
        "candidate_count_mean": None,
        "candidate_count_max": None,
        "candidate_overflow_count": 0,
        "candidate_match_count": 0,
        "candidate_drop_count": 0,
        "candidate_match_rate": None,
        "nonoop_candidate_match_count": 0,
        "nonoop_candidate_match_rate": None,
        "runtime_apply_attempted_count": 0,
        "runtime_apply_accepted_count": 0,
        "runtime_apply_rejected_count": 0,
        "runtime_apply_accept_rate": None,
        "post_state_match_count": 0,
        "post_state_mismatch_count": 0,
        "terminal_match_count": 0,
        "terminal_mismatch_count": 0,
        "demo_recording_ready": False,
    }
    drop_hist = Counter({k: 0 for k in DROP_REASONS})

    preview_output.parent.mkdir(parents=True, exist_ok=True)
    preview_written = 0
    preview_limit = int(preview_limit)

    with preview_output.open("w", encoding="utf-8") as handle:
        for episode_npz in episode_npz_paths:
            episode_stem = episode_npz.stem.replace(".replay_ready", "")
            _ = jsonl_by_stem.get(episode_stem)

            with np.load(episode_npz, allow_pickle=True) as npz:
                step_id = np.asarray(npz["step_id"]) if "step_id" in npz else np.arange(0, dtype=np.int32)
                episode_id = np.asarray(npz["episode_id"]) if "episode_id" in npz else np.zeros_like(step_id)
                done_t = np.asarray(npz["done_t"]) if "done_t" in npz else np.zeros_like(step_id, dtype=np.bool_)
                terminated_t = np.asarray(npz["terminated_t"]) if "terminated_t" in npz else np.zeros_like(step_id, dtype=np.bool_)
                truncated_t = np.asarray(npz["truncated_t"]) if "truncated_t" in npz else np.zeros_like(step_id, dtype=np.bool_)
                terminal_type_t = np.asarray(npz["terminal_type_t"]) if "terminal_type_t" in npz else np.array(["none"] * step_id.shape[0], dtype=object)

                initial_state_json = np.asarray(npz["initial_state_json"], dtype=object) if "initial_state_json" in npz else np.array([], dtype=object)
                runtime_state_t_json = np.asarray(npz["runtime_state_t_json"], dtype=object) if "runtime_state_t_json" in npz else np.array([], dtype=object)
                runtime_state_tp1_json = np.asarray(npz["runtime_state_tp1_json"], dtype=object) if "runtime_state_tp1_json" in npz else np.array([], dtype=object)
                teacher_cmds_json = np.asarray(npz["teacher_commands_t_json"], dtype=object) if "teacher_commands_t_json" in npz else np.array([], dtype=object)

                step_count = int(step_id.shape[0])
                metrics["steps_total"] += step_count
                metrics["steps_replay_attempted"] += step_count

                for i in range(step_count):
                    initial_state = parse_json_value(initial_state_json[i]) if i < initial_state_json.shape[0] else None
                    runtime_state_t = parse_json_value(runtime_state_t_json[i]) if i < runtime_state_t_json.shape[0] else None
                    runtime_state_tp1 = parse_json_value(runtime_state_tp1_json[i]) if i < runtime_state_tp1_json.shape[0] else None
                    teacher_commands = parse_json_value(teacher_cmds_json[i]) if i < teacher_cmds_json.shape[0] else None

                    has_initial = isinstance(initial_state, dict)
                    has_t = isinstance(runtime_state_t, dict)
                    has_tp1 = isinstance(runtime_state_tp1, dict)
                    if not has_initial:
                        drop_hist["missing_initial_state"] += 1
                    if not has_t:
                        drop_hist["missing_runtime_state_t"] += 1
                    if not has_tp1:
                        drop_hist["missing_runtime_state_tp1"] += 1

                    if not isinstance(teacher_commands, list):
                        teacher_commands = []
                        drop_hist["missing_teacher_commands"] += 1

                    metrics["teacher_commands_total"] += len(teacher_commands)
                    nonnoop = 0
                    for cmd in teacher_commands:
                        action_type = int(cmd.get("action_type", 0)) if isinstance(cmd, dict) else 0
                        if action_type != 0:
                            nonnoop += 1
                    metrics["teacher_nonnoop_commands_total"] += nonnoop

                    # This rerun is a prep-only offline pass; Unity runtime reconstruction is not executed here.
                    metrics["state_sync_failed_count"] += 1
                    if teacher_commands:
                        drop_hist["state_sync_failed"] += len(teacher_commands)

                    terminal_obj = runtime_state_tp1.get("terminal") if isinstance(runtime_state_tp1, dict) else None
                    terminal_done = bool(terminal_obj.get("done", False)) if isinstance(terminal_obj, dict) else False
                    expected_done = bool(done_t[i]) if i < done_t.shape[0] else False
                    expected_term_type = canonical_terminal_type(
                        done=bool(done_t[i]) if i < done_t.shape[0] else False,
                        terminated=bool(terminated_t[i]) if i < terminated_t.shape[0] else False,
                        truncated=bool(truncated_t[i]) if i < truncated_t.shape[0] else False,
                    )
                    actual_term_type = str(terminal_type_t[i]).strip().lower() if i < terminal_type_t.shape[0] else "none"

                    terminal_match = (terminal_done == expected_done) and (actual_term_type == expected_term_type)
                    if terminal_match:
                        metrics["terminal_match_count"] += 1
                    else:
                        metrics["terminal_mismatch_count"] += 1
                        drop_hist["terminal_mismatch"] += 1

                    if preview_written < preview_limit:
                        preview_row = {
                            "episode_id": int(episode_id[i]) if i < episode_id.shape[0] else 0,
                            "step_id": int(step_id[i]),
                            "teacher_command_count": len(teacher_commands),
                            "state_sync_success": False,
                            "candidate_match": False,
                            "runtime_apply_success": False,
                            "drop_reason": "state_sync_failed" if teacher_commands else "missing_teacher_commands",
                        }
                        if teacher_commands:
                            first = teacher_commands[0]
                            if isinstance(first, dict):
                                preview_row["teacher_command_preview"] = {
                                    "actor_flat": first.get("actor_flat"),
                                    "action_type": first.get("action_type"),
                                    "attack_target_local": first.get("attack_target_local"),
                                }
                        handle.write(json.dumps(preview_row, ensure_ascii=True) + "\n")
                        preview_written += 1

    metrics["candidate_drop_count"] = int(metrics["teacher_commands_total"])

    if metrics["teacher_commands_total"] > 0 and metrics["state_sync_success_count"] > 0:
        metrics["candidate_match_rate"] = float(metrics["candidate_match_count"]) / float(metrics["teacher_commands_total"])
    else:
        metrics["candidate_match_rate"] = None

    if metrics["teacher_nonnoop_commands_total"] > 0 and metrics["state_sync_success_count"] > 0:
        metrics["nonoop_candidate_match_rate"] = (
            float(metrics["nonoop_candidate_match_count"]) / float(metrics["teacher_nonnoop_commands_total"])
        )
    else:
        metrics["nonoop_candidate_match_rate"] = None

    if metrics["runtime_apply_attempted_count"] > 0:
        metrics["runtime_apply_accept_rate"] = (
            float(metrics["runtime_apply_accepted_count"]) / float(metrics["runtime_apply_attempted_count"])
        )
    else:
        metrics["runtime_apply_accept_rate"] = None

    no_go_reasons: list[str] = []
    if not replay_ready:
        no_go_reasons.append("source_not_replay_ready")
        drop_hist["source_not_replay_ready"] += 1
    if manifest_errors:
        no_go_reasons.append("manifest_contract_mismatch")
        drop_hist["manifest_contract_mismatch"] += len(manifest_errors)
    if metrics["state_sync_failed_count"] > 0:
        no_go_reasons.append("state_sync_failed")

    report = {
        "generated_at_utc": now_iso(),
        "stage": "Stage7B-6B-Rerun",
        "status": "NO_GO" if no_go_reasons else "GO",
        "summary": (
            "Replay-ready source validated; offline prep pass completed. Unity runtime state synchronization/candidate matching were not executed in this run."
        ),
        "selected_source_path": source_dir.as_posix(),
        "selected_source_format": "legacy032_replay_ready_export",
        "selected_source_replay_ready": replay_ready,
        "replay_manifest_path": manifest_path.as_posix(),
        "metrics": {
            **metrics,
            "drop_reason_histogram": {k: int(v) for k, v in drop_hist.items()},
        },
        "contract": {
            "branch_sizes": manifest.get("branch_sizes"),
            "attack_target_size": manifest.get("attack_target_size"),
            "attack_target_center_index": manifest.get("attack_target_center_index"),
            "observation_shape": manifest.get("observation_shape"),
            "action_shape": manifest.get("action_shape"),
            "validation_errors": manifest_errors,
        },
        "artifacts": {
            "source_inventory_json": inventory_output.as_posix(),
            "prep_report_json": prep_report_output.as_posix(),
            "prep_report_md": prep_md_output.as_posix(),
            "candidate_preview_jsonl": preview_output.as_posix(),
        },
        "no_go_reasons": no_go_reasons,
        "notes": [
            "ML-Agents training/PPO/imitation/.demo were not started.",
            "Stage6B3 baseline/checkpoint files were not modified by this script.",
            "Candidate truth must be measured from Unity MlAgentsCandidateActionBuilder on synchronized runtime state; this offline pass only validates replay-ready source and measures source-side counters.",
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    inventory_output.write_text(json.dumps(source_inventory, ensure_ascii=True, indent=2), encoding="utf-8")
    prep_report_output.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    prep_md_output.write_text(build_markdown(report), encoding="utf-8")

    print(f"[Stage7B][TeacherReplay] Source inventory written: {inventory_output.as_posix()}")
    print(f"[Stage7B][TeacherReplay] Prep report written: {prep_report_output.as_posix()}")
    print(f"[Stage7B][TeacherReplay] Prep markdown written: {prep_md_output.as_posix()}")
    print(f"[Stage7B][TeacherReplay] Candidate preview written: {preview_output.as_posix()}")
    print(f"[Stage7B][TeacherReplay] status={report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
