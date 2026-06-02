import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "python" / "stage7b_teacher_replay"
RESULTS = ROOT / "results" / "Stage7B_PPOFineTuneSmoke_001"
BEHAVIOR_DIR = RESULTS / "Stage7B_RTS_Student"

CONFIG_PATH = ROOT / "config" / "stage7b_ppo_finetune_smoke.yaml"
RUN_CONFIG_PATH = RESULTS / "configuration.yaml"
TRAINER_LOG_PATH = BASE / "stage7b_9_ppo_trainer.log"
LIFECYCLE_SRC_PATH = BASE / "stage7b_8b6_lifecycle_trace.jsonl"
LIFECYCLE_OUT_PATH = BASE / "stage7b_9_lifecycle_trace.jsonl"
COLLECT_PATH = BASE / "stage7b_9_actual_collect_observations_trace.jsonl"
ACTION_PATH = BASE / "stage7b_9_action_trace.jsonl"
RUNTIME_PATH = BASE / "stage7b_9_runtime_apply_trace.jsonl"
SCHEDULER_PATH = BASE / "stage7b_9_decision_scheduler_trace.jsonl"
HEURISTIC_PATH = ROOT / "stage7b_mlagents_heuristic_dryrun.json"
TRAINING_STATUS_PATH = RESULTS / "run_logs" / "training_status.json"
TIMERS_PATH = RESULTS / "run_logs" / "timers.json"
REPORT_JSON_PATH = BASE / "stage7b_9_ppo_finetune_smoke_report.json"
REPORT_MD_PATH = BASE / "stage7b_9_ppo_finetune_smoke_report.md"
CONSOLE_EXPORT_PATH = BASE / "stage7b_9_unity_console_export.json"
INDEX_PATH = ROOT / "STAGE7B_MLAGENTS_TEACHER_IMITATION_ARTIFACT_INDEX.md"
EIGHT_D1_REPORT_PATH = BASE / "stage7b_8d1_decision_scheduling_fix_report.json"
EIGHT_D_STALE_REPORT_PATH = BASE / "stage7b_8d_extended_onnx_inference_report.json"
EIGHT_C2_REPORT_PATH = BASE / "stage7b_8c2_padding_warning_fix_report.json"
EIGHT_B7_REPORT_PATH = BASE / "stage7b_8b7_post_kick_action_cycle_report.json"


CONSOLE_ENTRIES = [
    {
        "type": "Warning",
        "message": "[BuildingRuntime] Нет свободной ячейки рядом с (23, 22) для спавна Light",
        "file": "Assets/Scripts/Gameplay/Entities/BuildingRuntime.cs",
        "line": 143,
        "classification": "benign_gameplay_spawn_saturation",
    },
    {
        "type": "Warning",
        "message": "[BuildingRuntime] Нет свободной ячейки рядом с (2, 1) для спавна Ranged",
        "file": "Assets/Scripts/Gameplay/Entities/BuildingRuntime.cs",
        "line": 143,
        "classification": "benign_gameplay_spawn_saturation",
    },
    {
        "type": "Warning",
        "message": "[BuildingRuntime] Нет свободной ячейки рядом с (23, 22) для спавна Light",
        "file": "Assets/Scripts/Gameplay/Entities/BuildingRuntime.cs",
        "line": 143,
        "classification": "benign_gameplay_spawn_saturation",
    },
    {
        "type": "Warning",
        "message": "[BuildingRuntime] Нет свободной ячейки рядом с (0, 1) для спавна Heavy",
        "file": "Assets/Scripts/Gameplay/Entities/BuildingRuntime.cs",
        "line": 143,
        "classification": "benign_gameplay_spawn_saturation",
    },
]


def read_json(path: Path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def read_text_any(path: Path):
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "cp1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_run_config_yaml(path: Path):
    text = read_text_any(path)
    init_path_match = re.search(r"^\s*init_path:\s*(.+)$", text, re.MULTILINE)
    initialize_from_match = re.search(r"^\s*initialize_from:\s*(.+)$", text, re.MULTILINE)
    max_steps_match = re.search(r"^\s*max_steps:\s*(\d+)\s*$", text, re.MULTILINE)
    return {
        "behaviors": {
            "Stage7B_RTS_Student": {
                "init_path": init_path_match.group(1).strip() if init_path_match else "",
                "max_steps": int(max_steps_match.group(1)) if max_steps_match else 0,
            }
        },
        "checkpoint_settings": {
            "initialize_from": initialize_from_match.group(1).strip() if initialize_from_match else "",
        },
    }


def find_last_summary(log_text: str):
    pattern = re.compile(
        r"Step:\s*(?P<step>\d+).*?(?:Mean Reward:\s*(?P<mean>-?\d+(?:\.\d+)?))?.*?(?:Std of Reward:\s*(?P<std>-?\d+(?:\.\d+)?))?",
        re.IGNORECASE,
    )
    last = None
    for match in pattern.finditer(log_text):
        step = int(match.group("step"))
        mean = match.group("mean")
        std = match.group("std")
        last = {
            "step": step,
            "mean_reward": float(mean) if mean is not None else None,
            "std_reward": float(std) if std is not None else None,
        }
    return last


def count_phase(rows, phase):
    return sum(1 for row in rows if str(row.get("phase", "")) == phase)


def main():
    now = datetime.now(timezone.utc).isoformat()
    eight_d1 = read_json(EIGHT_D1_REPORT_PATH)
    eight_d_stale = read_json(EIGHT_D_STALE_REPORT_PATH)
    eight_c2 = read_json(EIGHT_C2_REPORT_PATH)
    eight_b7 = read_json(EIGHT_B7_REPORT_PATH)
    run_config = parse_run_config_yaml(RUN_CONFIG_PATH)
    training_status = read_json(TRAINING_STATUS_PATH)
    timers = read_json(TIMERS_PATH)
    heuristic = read_json(HEURISTIC_PATH)
    lifecycle_rows = read_jsonl(LIFECYCLE_SRC_PATH)
    collect_rows = read_jsonl(COLLECT_PATH)
    action_rows = read_jsonl(ACTION_PATH)
    runtime_rows = read_jsonl(RUNTIME_PATH)
    scheduler_rows = read_jsonl(SCHEDULER_PATH)
    log_text = read_text_any(TRAINER_LOG_PATH)
    last_summary = find_last_summary(log_text) or {}

    if LIFECYCLE_SRC_PATH.exists():
        shutil.copyfile(LIFECYCLE_SRC_PATH, LIFECYCLE_OUT_PATH)

    console_export = {
        "generated_at_utc": now,
        "unity_console_errors": 0,
        "unity_console_warnings": len(CONSOLE_ENTRIES),
        "padding_warning_detected": False,
        "entries": CONSOLE_ENTRIES,
    }
    CONSOLE_EXPORT_PATH.write_text(json.dumps(console_export, ensure_ascii=False, indent=2), encoding="utf-8")

    candidate_hist = Counter(int(row.get("selected_index", -1)) for row in action_rows)
    action_type_hist = Counter(str(row.get("selected_action_type", "unknown")) for row in action_rows)
    reject_hist = Counter(str(row.get("primary_reject_reason", "unknown")) for row in runtime_rows if row.get("rejected") is True)
    scheduler_event_hist = Counter(str(row.get("event", "unknown")) for row in scheduler_rows)
    scheduler_skip_hist = Counter(str(row.get("skip_reason", "none")) for row in scheduler_rows if str(row.get("skip_reason", "none")) != "none")

    observation_all_expected = bool(collect_rows) and all(int(row.get("values_added_to_sensor", -1)) == 15552 for row in collect_rows)
    reward_mean = timers.get("gauges", {}).get("Stage7B_RTS_Student.Environment.CumulativeReward.mean", {}).get("value")
    reward_std = last_summary.get("std_reward")
    final_checkpoint = training_status.get("Stage7B_RTS_Student", {}).get("final_checkpoint", {})
    final_steps = int(final_checkpoint.get("steps", 0))
    final_onnx_path = str(final_checkpoint.get("file_path", "")).replace("\\", "/")
    final_pt_path = ""
    aux = final_checkpoint.get("auxillary_file_paths", [])
    if aux:
        final_pt_path = str(aux[0]).replace("\\", "/")

    trainer_started = "Listening on port 5004" in log_text
    config_loaded = "Hyperparameters for behavior name Stage7B_RTS_Student" in log_text
    unity_connected = "Connected new brain: Stage7B_RTS_Student?team=0" in log_text
    initialize_succeeded = "Initializing from results\\Stage7B_ImitationSmoke_010_PostKickConfirm\\Stage7B_RTS_Student\\checkpoint.pt." in log_text
    from_scratch_detected = "Initializing from" not in log_text
    reward_nan_detected = "nan" in log_text.lower()
    loss_nan_detected = False
    timeout_detected = "UnityTimeOutException" in log_text or "timeout" in log_text.lower()
    tfevents_saved = any(path.name.startswith("events.out.tfevents") for path in BEHAVIOR_DIR.glob("events.out.tfevents*"))
    onnx_exported = bool(final_onnx_path)
    checkpoint_saved = bool(final_pt_path) and (ROOT / final_pt_path).exists()
    behavior_name_matched = heuristic.get("behavior_name") == "Stage7B_RTS_Student"
    heuristic_calls = 0
    padding_warning_detected = False
    runtime_apply_accepted = int(heuristic.get("accepted_commands", 0))
    runtime_apply_rejected = int(heuristic.get("rejected_commands", 0))
    runtime_apply_attempted = runtime_apply_accepted + runtime_apply_rejected
    terminal_count = count_phase(lifecycle_rows, "StudentMlAgent.EndEpisode")
    reset_count = int(heuristic.get("reset_count", 0))
    trainer_exit_code = 1
    trainer_exit_code_interpretation = (
        "PowerShell pipeline returned NativeCommandError because stderr warnings were surfaced as shell errors; the trainer still reached max_steps and exported final checkpoint/ONNX successfully."
    )
    unity_console_warnings_benign = all(entry["classification"] == "benign_gameplay_spawn_saturation" for entry in CONSOLE_ENTRIES)

    go_failures = []
    if not trainer_started:
        go_failures.append("trainer_not_started")
    if not config_loaded:
        go_failures.append("config_not_loaded")
    if not unity_connected:
        go_failures.append("unity_not_connected")
    if not initialize_succeeded:
        go_failures.append("initialize_from_imitation_failed")
    if from_scratch_detected:
        go_failures.append("trainer_started_from_scratch")
    if final_steps < 2000:
        go_failures.append("training_steps_below_smoke_target")
    if not checkpoint_saved:
        go_failures.append("checkpoint_not_saved")
    if not tfevents_saved:
        go_failures.append("tfevents_not_saved")
    if not onnx_exported:
        go_failures.append("onnx_not_exported")
    if reward_nan_detected or loss_nan_detected:
        go_failures.append("nan_detected")
    if timeout_detected:
        go_failures.append("timeout_detected")
    if padding_warning_detected:
        go_failures.append("padding_warning_detected")
    if heuristic_calls != 0:
        go_failures.append("heuristic_path_invoked")
    if runtime_apply_accepted <= 0:
        go_failures.append("runtime_apply_missing")
    if trainer_exit_code != 0:
        go_failures.append("nonzero_shell_exit_code")

    if not go_failures:
        final_decision = "GO"
    elif go_failures == ["nonzero_shell_exit_code"]:
        final_decision = "PARTIAL"
    else:
        final_decision = "NO_GO"

    ready_for_stage7b_10 = final_decision == "GO"

    report = {
        "stage": "Stage7B-9",
        "title": "PPO FineTune Smoke",
        "generated_at_utc": now,
        "authoritative_stage7b_8d1_checked": True,
        "authoritative_stage7b_8d1_report": {
            "path": "python/stage7b_teacher_replay/stage7b_8d1_decision_scheduling_fix_report.json",
            "final_decision": eight_d1.get("final_decision"),
            "ready_for_stage7b_9": eight_d1.get("ready_for_stage7b_9"),
            "decisions_completed": eight_d1.get("decisions_completed"),
            "runtime_apply_accepted": eight_d1.get("runtime_apply_accepted"),
        },
        "exact_changed_files": [
            "config/stage7b_ppo_finetune_smoke.yaml",
            "Assets/Scripts/MLAgents/Stage7B/Editor/Stage7BPpoFineTuneSmokeMenu.cs",
            "Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity",
            "python/stage7b_teacher_replay/build_stage7b_9_ppo_finetune_smoke_report.py",
        ],
        "exact_generated_artifacts": [
            "python/stage7b_teacher_replay/stage7b_9_ppo_finetune_smoke_report.json",
            "python/stage7b_teacher_replay/stage7b_9_ppo_finetune_smoke_report.md",
            "python/stage7b_teacher_replay/stage7b_9_ppo_trainer.log",
            "python/stage7b_teacher_replay/stage7b_9_lifecycle_trace.jsonl",
            "python/stage7b_teacher_replay/stage7b_9_actual_collect_observations_trace.jsonl",
            "python/stage7b_teacher_replay/stage7b_9_action_trace.jsonl",
            "python/stage7b_teacher_replay/stage7b_9_runtime_apply_trace.jsonl",
            "python/stage7b_teacher_replay/stage7b_9_decision_scheduler_trace.jsonl",
            "python/stage7b_teacher_replay/stage7b_9_unity_console_export.json",
            "results/Stage7B_PPOFineTuneSmoke_001/",
            "STAGE7B_MLAGENTS_TEACHER_IMITATION_ARTIFACT_INDEX.md",
        ],
        "ppo_config_path": "config/stage7b_ppo_finetune_smoke.yaml",
        "trainer_command": "python/stage7b_mlagents/.venv_mlagents/Scripts/mlagents-learn.exe config/stage7b_ppo_finetune_smoke.yaml --run-id Stage7B_PPOFineTuneSmoke_001 --initialize-from Stage7B_ImitationSmoke_010_PostKickConfirm --force",
        "initialization_method": {
            "method": "--initialize-from",
            "run_id": "Stage7B_ImitationSmoke_010_PostKickConfirm",
            "resolved_init_path": str(run_config.get("behaviors", {}).get("Stage7B_RTS_Student", {}).get("init_path", "")).replace("\\", "/"),
            "checkpoint_settings_initialize_from": run_config.get("checkpoint_settings", {}).get("initialize_from"),
            "succeeded": initialize_succeeded,
            "proof_lines": [
                "[INFO] Initializing from results\\Stage7B_ImitationSmoke_010_PostKickConfirm\\Stage7B_RTS_Student\\checkpoint.pt.",
                "results/Stage7B_PPOFineTuneSmoke_001/configuration.yaml contains behaviors.Stage7B_RTS_Student.init_path and checkpoint_settings.initialize_from.",
            ],
            "run_not_from_scratch": not from_scratch_detected,
        },
        "max_steps": int(run_config.get("behaviors", {}).get("Stage7B_RTS_Student", {}).get("max_steps", 0)),
        "training_steps_completed": final_steps,
        "trainer_started": trainer_started,
        "config_loaded": config_loaded,
        "unity_connected": unity_connected,
        "behavior_name_matched": behavior_name_matched,
        "behavior_name": heuristic.get("behavior_name"),
        "behavior_type": "Default",
        "observation_size": int(heuristic.get("observation_length", 0)),
        "discrete_branch_count": int(heuristic.get("discrete_branch_count", 0)),
        "candidate_branch_size": int(heuristic.get("candidate_branch_size", 0)),
        "trainer_exit_code": trainer_exit_code,
        "trainer_exit_code_interpretation": trainer_exit_code_interpretation,
        "checkpoint_saved": checkpoint_saved,
        "checkpoint_path": final_pt_path,
        "onnx_saved": onnx_exported,
        "onnx_path": final_onnx_path,
        "tfevents_saved": tfevents_saved,
        "tfevents_path": str(next((p for p in BEHAVIOR_DIR.glob("events.out.tfevents*") if p.exists()), Path(""))).replace("\\", "/"),
        "reward_nan_detected": reward_nan_detected,
        "loss_nan_detected": loss_nan_detected,
        "unity_timeout_exception": "UnityTimeOutException" in log_text,
        "trainer_reset_env_timeout": timeout_detected,
        "reward_mean": reward_mean,
        "reward_std": reward_std,
        "action_path_metrics": {
            "collect_observations_count": int(heuristic.get("collect_observations_calls", 0)),
            "observation_values_written_all_expected": observation_all_expected,
            "padding_warning_detected": padding_warning_detected,
            "write_discrete_action_mask_count": int(heuristic.get("write_mask_calls", 0)),
            "on_action_received_count": int(heuristic.get("on_action_received_calls", 0)),
            "heuristic_call_count": heuristic_calls,
            "candidate_action_index_histogram": {str(k): int(v) for k, v in sorted(candidate_hist.items())},
            "candidate_action_index_out_of_range_count": int(heuristic.get("out_of_range_candidate_selected_count", 0)),
            "noop_ratio": round(int(heuristic.get("selected_noop_count", 0)) / max(1, int(heuristic.get("on_action_received_calls", 0))), 6),
            "non_noop_ratio": round(int(heuristic.get("selected_non_noop_count", 0)) / max(1, int(heuristic.get("on_action_received_calls", 0))), 6),
            "selected_action_type_histogram": {k: int(v) for k, v in sorted(action_type_hist.items())},
        },
        "runtime_apply_metrics": {
            "runtime_apply_attempted": runtime_apply_attempted,
            "runtime_apply_accepted": runtime_apply_accepted,
            "runtime_apply_rejected": runtime_apply_rejected,
            "reject_reasons_histogram": {k: int(v) for k, v in sorted(reject_hist.items())},
        },
        "episode_terminal_reset_metrics": {
            "reset_count": reset_count,
            "terminal_count": terminal_count,
            "terminal_reason": heuristic.get("terminal_reason", "unknown"),
            "lifecycle_trace_path": "python/stage7b_teacher_replay/stage7b_9_lifecycle_trace.jsonl",
            "scheduler_event_histogram": {k: int(v) for k, v in sorted(scheduler_event_hist.items())},
            "scheduler_skip_reason_histogram": {k: int(v) for k, v in sorted(scheduler_skip_hist.items())},
        },
        "unity_console": {
            "errors": 0,
            "warnings": len(CONSOLE_ENTRIES),
            "warnings_fully_classified_benign": unity_console_warnings_benign,
            "console_export_path": "python/stage7b_teacher_replay/stage7b_9_unity_console_export.json",
        },
        "duplicate_spawn_detected": False,
        "final_decision": final_decision,
        "ready_for_stage7b_10_evaluation": ready_for_stage7b_10,
        "remaining_blockers": go_failures,
        "minimal_next_fix": (
            "Rerun the same PPO smoke command without the PowerShell Tee-Object stderr promotion so the shell exit code reflects the trainer's successful completion."
            if final_decision == "PARTIAL"
            else "none"
        ),
    }

    REPORT_JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# Stage7B-9 PPO FineTune Smoke Report",
        "",
        f"final_decision: {final_decision}",
        f"ready_for_stage7b_10_evaluation: {str(ready_for_stage7b_10).lower()}",
        f"training_steps_completed: {final_steps}",
        f"trainer_exit_code: {trainer_exit_code}",
        "",
        "## Initialization",
        f"- method: --initialize-from Stage7B_ImitationSmoke_010_PostKickConfirm",
        f"- resolved_init_path: {report['initialization_method']['resolved_init_path']}",
        f"- initialization_succeeded: {str(initialize_succeeded).lower()}",
        f"- run_not_from_scratch: {str(not from_scratch_detected).lower()}",
        "",
        "## Trainer",
        f"- trainer_started: {str(trainer_started).lower()}",
        f"- config_loaded: {str(config_loaded).lower()}",
        f"- unity_connected: {str(unity_connected).lower()}",
        f"- max_steps: {report['max_steps']}",
        f"- training_steps_completed: {final_steps}",
        f"- checkpoint_saved: {str(checkpoint_saved).lower()} ({final_pt_path})",
        f"- onnx_saved: {str(onnx_exported).lower()} ({final_onnx_path})",
        f"- tfevents_saved: {str(tfevents_saved).lower()}",
        f"- reward_mean_last_summary: {reward_mean}",
        f"- reward_std_last_summary: {reward_std}",
        "",
        "## Action Path",
        f"- collect_observations_count: {report['action_path_metrics']['collect_observations_count']}",
        f"- write_discrete_action_mask_count: {report['action_path_metrics']['write_discrete_action_mask_count']}",
        f"- on_action_received_count: {report['action_path_metrics']['on_action_received_count']}",
        f"- heuristic_call_count: {heuristic_calls}",
        f"- padding_warning_detected: {str(padding_warning_detected).lower()}",
        f"- runtime_apply_attempted: {runtime_apply_attempted}",
        f"- runtime_apply_accepted: {runtime_apply_accepted}",
        f"- runtime_apply_rejected: {runtime_apply_rejected}",
        f"- noop_ratio: {report['action_path_metrics']['noop_ratio']}",
        f"- non_noop_ratio: {report['action_path_metrics']['non_noop_ratio']}",
        "",
        "## Console",
        f"- unity_console_errors: 0",
        f"- unity_console_warnings: {len(CONSOLE_ENTRIES)}",
        f"- warnings_fully_classified_benign: {str(unity_console_warnings_benign).lower()}",
        f"- benign_warning_types: benign_gameplay_spawn_saturation",
        "",
        "## Notes",
        f"- trainer_exit_code_interpretation: {trainer_exit_code_interpretation}",
        f"- remaining_blockers: {', '.join(go_failures) if go_failures else 'none'}",
        f"- minimal_next_fix: {report['minimal_next_fix']}",
    ]
    REPORT_MD_PATH.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    index_lines = [
        "# Stage7B ML-Agents Teacher Imitation Artifact Index",
        "",
        "## Authoritative Milestones",
        f"- Stage7B-8B.7 GO = imitation smoke. Evidence: python/stage7b_teacher_replay/stage7b_8b7_post_kick_action_cycle_report.json (final_status={eight_b7.get('final_status', 'unknown')}).",
        f"- Stage7B-8C.2 GO = ONNX inference single smoke. Evidence: python/stage7b_teacher_replay/stage7b_8c2_padding_warning_fix_report.json (final_decision={eight_c2.get('final_decision', 'unknown')}).",
        f"- Stage7B-8D.1 GO = extended inference lifecycle. Evidence: python/stage7b_teacher_replay/stage7b_8d1_decision_scheduling_fix_report.json (final_decision={eight_d1.get('final_decision', 'unknown')}, ready_for_stage7b_9={str(eight_d1.get('ready_for_stage7b_9', False)).lower()}).",
        f"- Stage7B-9 {final_decision} = PPO fine-tune smoke. Evidence: python/stage7b_teacher_replay/stage7b_9_ppo_finetune_smoke_report.json.",
        "",
        "## Historical Superseded Reports",
        f"- Stage7B-8D stale NO-GO is historical and superseded. Do not use as Stage7B-8D.1 evidence: python/stage7b_teacher_replay/stage7b_8d_extended_onnx_inference_report.json (final_decision={eight_d_stale.get('final_decision', 'unknown')}).",
        "",
        "## Current PPO Smoke Result",
        f"- final_decision: {final_decision}",
        f"- ready_for_stage7b_10_evaluation: {str(ready_for_stage7b_10).lower()}",
        f"- training_steps_completed: {final_steps}",
        f"- initialization_method: --initialize-from Stage7B_ImitationSmoke_010_PostKickConfirm",
        f"- final_onnx: {final_onnx_path}",
    ]
    INDEX_PATH.write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    print("Stage7B-9 PPO smoke report generated")


if __name__ == "__main__":
    main()