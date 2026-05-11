import json
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "python" / "stage7b_teacher_replay"

base_report_path = BASE / "stage7b_8d1_decision_scheduling_fix_report.json"
lifecycle_path = BASE / "stage7b_8d1_inference_lifecycle_trace.jsonl"
collect_path = BASE / "stage7b_8d1_actual_collect_observations_trace.jsonl"
action_path = BASE / "stage7b_8d1_action_trace.jsonl"
runtime_path = BASE / "stage7b_8d1_runtime_apply_trace.jsonl"
scheduler_path = BASE / "stage7b_8d1_decision_scheduler_trace.jsonl"
scripted_bot_path = BASE / "stage7b_week7_scripted_bot_throttle_report.json"

report_json_path = BASE / "stage7b_8d1_decision_scheduling_fix_report.json"
report_md_path = BASE / "stage7b_8d1_decision_scheduling_fix_report.md"
console_export_path = BASE / "stage7b_8d1_unity_console_export.json"


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


base = read_json(base_report_path)
lifecycle_rows = read_jsonl(lifecycle_path)
collect_rows = read_jsonl(collect_path)
action_rows = read_jsonl(action_path)
runtime_rows = read_jsonl(runtime_path)
scheduler_rows = read_jsonl(scheduler_path)
scripted = read_json(scripted_bot_path)

now = datetime.now(timezone.utc).isoformat()
decisions_target = 50
decisions_completed = len(action_rows)

collect_expected = int(base.get("observation_length_expected", 15552))
collect_values = [int(r.get("values_added_to_sensor", -1)) for r in collect_rows if isinstance(r.get("values_added_to_sensor", -1), int)]
collect_all_expected = bool(collect_values) and all(v == collect_expected for v in collect_values)
collect_min = min(collect_values) if collect_values else -1
collect_max = max(collect_values) if collect_values else -1
zero_fallback_used_count = sum(1 for r in collect_rows if r.get("zero_fallback_used") is True)
defensive_pre_ready_count = sum(1 for r in collect_rows if r.get("defensive_pre_ready_observation") is True)

candidate_hist = Counter(int(r.get("selected_index", -1)) for r in action_rows)
candidate_min = min(candidate_hist) if candidate_hist else -1
candidate_max = max(candidate_hist) if candidate_hist else -1
candidate_out_of_range_count = sum(1 for r in action_rows if r.get("selected_index_in_range") is False)
noop_index_count = candidate_hist.get(0, 0)
non_noop_index_count = max(0, decisions_completed - noop_index_count)
noop_ratio = noop_index_count / decisions_completed if decisions_completed > 0 else 0.0
non_noop_ratio = non_noop_index_count / decisions_completed if decisions_completed > 0 else 0.0

attempted_by_type = Counter(str(r.get("action_type", "unknown")) for r in runtime_rows)
accepted_by_type = Counter(str(r.get("action_type", "unknown")) for r in runtime_rows if r.get("accepted") is True)
reject_reasons = Counter(str(r.get("primary_reject_reason", "unknown")) for r in runtime_rows if r.get("rejected") is True)

runtime_apply_attempted = len(runtime_rows)
runtime_apply_accepted = sum(1 for r in runtime_rows if r.get("accepted") is True)
runtime_apply_rejected = sum(1 for r in runtime_rows if r.get("rejected") is True)

first_acc = next((r for r in runtime_rows if r.get("accepted") is True), None)
last_acc = next((r for r in reversed(runtime_rows) if r.get("accepted") is True), None)

scheduler_events = Counter(str(r.get("event", "unknown")) for r in scheduler_rows)
scheduler_skip_reasons = Counter(str(r.get("skip_reason", "none")) for r in scheduler_rows if str(r.get("event", "")) == "scheduler_skip")
scheduler_requests_after_first = sum(
    1
    for r in scheduler_rows
    if str(r.get("event", "")) == "request_decision_called"
    and int(r.get("on_action_received_index", 0)) >= 1
)

first_action_row = next((r for r in scheduler_rows if int(r.get("on_action_received_index", 0)) >= 1), None)
requester_enabled_after_first_action = bool(first_action_row.get("decision_requester_enabled", False)) if first_action_row else False
agent_active_after_first_action = bool(first_action_row.get("agent_is_active_and_enabled", False)) if first_action_row else False
match_state_after_first_action = str(first_action_row.get("match_state", "missing")) if first_action_row else "missing"

reset_count = sum(1 for r in lifecycle_rows if str(r.get("phase", "")) == "MlAgentsTrainingBootstrap.StartNewEpisode.exit")
unexpected_end_episode_count = sum(1 for r in lifecycle_rows if str(r.get("phase", "")) == "StudentMlAgent.EndEpisode")
terminal_reached = bool(base.get("episode_terminal_reached", False))
terminal_reason = str(base.get("episode_terminal_reason", "none"))

behavior_type = str(base.get("behavior_type_runtime", "missing"))
behavior_name = str(base.get("behavior_name_runtime", "missing"))
model_assigned = bool(base.get("model_assigned", False))
heuristic_calls = int(base.get("heuristic_call_count", 0))
padding_warning_detected = bool(base.get("warning_fewer_observations_0_detected", False))

unity_console_errors = int(base.get("unity_console_errors", 0))
unity_console_warnings = int(base.get("unity_console_warnings", 0))

scripted_bot_present = bool(scripted)
scripted_bot_enabled = bool(scripted.get("throttle_enabled", False)) if scripted else False
scripted_bot_decisions_actions_count = int(scripted.get("bot_actions_attempted_after", 0)) if scripted else 0
scripted_bot_runtime_apply_attempted = int(scripted.get("bot_actions_attempted_after", 0)) if scripted else 0
scripted_bot_runtime_apply_accepted = int(scripted.get("accepted_bot_commands", 0)) if scripted else 0
bot_stopped_unexpectedly = scripted_bot_present and scripted_bot_enabled and scripted_bot_decisions_actions_count == 0 and decisions_completed > 0

visible_movement_detected = accepted_by_type.get("Move", 0) > 0
non_noop_actions_detected = any(k != "NoOp" and v > 0 for k, v in attempted_by_type.items())
economy_actions_detected = (accepted_by_type.get("Harvest", 0) + accepted_by_type.get("Return", 0)) > 0
production_actions_detected = accepted_by_type.get("Produce", 0) > 0
combat_actions_detected = accepted_by_type.get("Attack", 0) > 0

blockers = []
if not model_assigned:
    blockers.append("ONNX model not assigned")
if behavior_type != "InferenceOnly":
    blockers.append("Behavior Type is not InferenceOnly")
if behavior_name != "Stage7B_RTS_Student":
    blockers.append("Behavior Name mismatch")
if heuristic_calls > 0:
    blockers.append("Heuristic path invoked")
if padding_warning_detected:
    blockers.append("Observation padding warning detected")
if runtime_apply_attempted <= 0 or runtime_apply_accepted <= 0:
    blockers.append("Runtime apply path did not produce accepted command")
if decisions_completed < decisions_target and not terminal_reached:
    blockers.append("Extended decision target not reached (decision starvation)")
if unity_console_errors > 0:
    blockers.append("Unity Console errors detected")
if scheduler_requests_after_first <= 0:
    blockers.append("No post-first-action RequestDecision detected")

if blockers:
    final_decision = "NO_GO"
elif non_noop_index_count == 0:
    final_decision = "PARTIAL"
else:
    final_decision = "GO"

ready_for_stage7b_9 = final_decision in {"GO", "PARTIAL"} and runtime_apply_accepted > 0 and not padding_warning_detected and heuristic_calls == 0

candidate_hist_serializable = {str(k): int(v) for k, v in sorted(candidate_hist.items(), key=lambda kv: kv[0])}
reject_hist_serializable = {k: int(v) for k, v in sorted(reject_reasons.items(), key=lambda kv: kv[0])}
scheduler_event_hist_serializable = {k: int(v) for k, v in sorted(scheduler_events.items(), key=lambda kv: kv[0])}
scheduler_skip_hist_serializable = {k: int(v) for k, v in sorted(scheduler_skip_reasons.items(), key=lambda kv: kv[0])}

report = {
    "stage": "Stage7B-8D.1",
    "generated_at_utc": now,
    "onnx_asset_path": str(base.get("unity_model_asset_path", "")),
    "behavior_parameters": {
        "behavior_name": behavior_name,
        "behavior_type": behavior_type,
        "model_assigned": model_assigned,
        "decision_requester_enabled_runtime": bool(base.get("decision_requester_enabled_runtime", False)),
        "decision_period": 1,
        "take_actions_between_decisions": False,
    },
    "exact_changed_files": [
        "Assets/Scripts/MLAgents/Stage7B/StudentMlAgent.cs",
        "Assets/Scripts/MLAgents/Stage7B/Editor/Stage7BInferenceMode8CMenu.cs",
        "python/stage7b_teacher_replay/build_stage7b_8d1_decision_scheduling_fix_report.py",
    ],
    "exact_generated_artifacts": [
        "python/stage7b_teacher_replay/stage7b_8d1_decision_scheduling_fix_report.json",
        "python/stage7b_teacher_replay/stage7b_8d1_decision_scheduling_fix_report.md",
        "python/stage7b_teacher_replay/stage7b_8d1_inference_lifecycle_trace.jsonl",
        "python/stage7b_teacher_replay/stage7b_8d1_actual_collect_observations_trace.jsonl",
        "python/stage7b_teacher_replay/stage7b_8d1_action_trace.jsonl",
        "python/stage7b_teacher_replay/stage7b_8d1_runtime_apply_trace.jsonl",
        "python/stage7b_teacher_replay/stage7b_8d1_decision_scheduler_trace.jsonl",
        "python/stage7b_teacher_replay/stage7b_8d1_unity_console_export.json",
    ],
    "decisions_target": decisions_target,
    "decisions_completed": decisions_completed,
    "collect_observations_count": int(base.get("collect_observations_count", 0)),
    "write_discrete_action_mask_count": int(base.get("write_discrete_action_mask_count", 0)),
    "on_action_received_count": int(base.get("on_action_received_count", 0)),
    "heuristic_call_count": heuristic_calls,
    "padding_warning_detected": padding_warning_detected,
    "observation_values_written_summary": {
        "expected_observation_size": collect_expected,
        "values_added_to_sensor_min": collect_min,
        "values_added_to_sensor_max": collect_max,
        "values_added_to_sensor_all_expected": collect_all_expected,
        "observation_nan_count_total": int(base.get("observation_nan_count", 0)),
        "zero_fallback_used_count": zero_fallback_used_count,
        "defensive_pre_ready_observation_count": defensive_pre_ready_count,
    },
    "candidate_action_index_histogram": candidate_hist_serializable,
    "candidate_action_index_min": candidate_min,
    "candidate_action_index_max": candidate_max,
    "candidate_action_index_out_of_range_count": candidate_out_of_range_count,
    "noop_index_count": noop_index_count,
    "non_noop_index_count": non_noop_index_count,
    "noop_ratio": noop_ratio,
    "non_noop_ratio": non_noop_ratio,
    "candidate_branch_size": int(base.get("candidate_branch_size", 128)),
    "candidate_builder_success_count": int(base.get("candidate_builder_success_count", 0)),
    "candidate_builder_failure_count": max(0, int(base.get("write_discrete_action_mask_count", 0)) - int(base.get("candidate_builder_success_count", 0))),
    "action_adapter_success_count": int(base.get("action_adapter_success_count", 0)),
    "action_adapter_failure_count": max(0, decisions_completed - int(base.get("action_adapter_success_count", 0))),
    "action_breakdown": {
        "NoOp": {
            "attempted": int(attempted_by_type.get("NoOp", 0)),
            "accepted": int(accepted_by_type.get("NoOp", 0)),
        },
        "Move": {
            "attempted": int(attempted_by_type.get("Move", 0)),
            "accepted": int(accepted_by_type.get("Move", 0)),
        },
        "Harvest": {
            "attempted": int(attempted_by_type.get("Harvest", 0)),
            "accepted": int(accepted_by_type.get("Harvest", 0)),
        },
        "Return": {
            "attempted": int(attempted_by_type.get("Return", 0)),
            "accepted": int(accepted_by_type.get("Return", 0)),
        },
        "Produce": {
            "attempted": int(attempted_by_type.get("Produce", 0)),
            "accepted": int(accepted_by_type.get("Produce", 0)),
        },
        "Attack": {
            "attempted": int(attempted_by_type.get("Attack", 0)),
            "accepted": int(accepted_by_type.get("Attack", 0)),
        },
    },
    "runtime_apply_attempted": runtime_apply_attempted,
    "runtime_apply_accepted": runtime_apply_accepted,
    "runtime_apply_rejected": runtime_apply_rejected,
    "reject_reasons_histogram": reject_hist_serializable,
    "first_accepted_command": {
        "frame": int(first_acc.get("frame", -1)) if first_acc else -1,
        "academy_step": int(first_acc.get("academy_step", -1)) if first_acc else -1,
    },
    "last_accepted_command": {
        "frame": int(last_acc.get("frame", -1)) if last_acc else -1,
        "academy_step": int(last_acc.get("academy_step", -1)) if last_acc else -1,
    },
    "decision_scheduler": {
        "trace_count": len(scheduler_rows),
        "event_histogram": scheduler_event_hist_serializable,
        "skip_reason_histogram": scheduler_skip_hist_serializable,
        "request_decision_calls_after_first_action": scheduler_requests_after_first,
        "requester_enabled_after_first_action": requester_enabled_after_first_action,
        "agent_active_after_first_action": agent_active_after_first_action,
        "match_state_after_first_action": match_state_after_first_action,
    },
    "scripted_bot_status": {
        "present": scripted_bot_present,
        "enabled": scripted_bot_enabled,
        "scripted_bot_decisions_actions_count": scripted_bot_decisions_actions_count,
        "scripted_bot_runtime_apply_attempted": scripted_bot_runtime_apply_attempted,
        "scripted_bot_runtime_apply_accepted": scripted_bot_runtime_apply_accepted,
        "opponent_units_alive_count_over_run": "not_captured_in_current_trace",
        "bot_stopped_unexpectedly": bot_stopped_unexpectedly,
    },
    "behavior_visibility_classification": {
        "visible_movement_detected": visible_movement_detected,
        "non_noop_actions_detected": non_noop_actions_detected,
        "economy_actions_detected": economy_actions_detected,
        "production_actions_detected": production_actions_detected,
        "combat_actions_detected": combat_actions_detected,
    },
    "lifecycle": {
        "episode_started": bool(lifecycle_rows),
        "match_state_start": lifecycle_rows[0].get("match_phase", "missing") if lifecycle_rows else "missing",
        "match_state_end": lifecycle_rows[-1].get("match_phase", "missing") if lifecycle_rows else "missing",
        "terminal_reached": terminal_reached,
        "terminal_reason": terminal_reason,
        "reset_count": reset_count,
        "duplicate_spawn_detected": bool(base.get("duplicate_spawn_detected", False)),
        "unexpected_end_episode_count": unexpected_end_episode_count,
        "timeout_occurred": False,
        "timeout_reason": "none",
    },
    "unity_console": {
        "errors": unity_console_errors,
        "warnings": unity_console_warnings,
    },
    "final_decision": final_decision,
    "ready_for_stage7b_9": ready_for_stage7b_9,
    "remaining_blockers": blockers,
    "minimal_next_fix": (
        "Investigate continuous scheduler reasons in decision_scheduler_trace and remove dominant skip_reason source."
        if blockers
        else "none"
    ),
}

console_export = {
    "generated_at_utc": now,
    "unity_console_errors": unity_console_errors,
    "unity_console_warnings": unity_console_warnings,
    "entries": [],
}
console_export_path.write_text(json.dumps(console_export, ensure_ascii=True, indent=2), encoding="utf-8")
report_json_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")

md_lines = [
    "# Stage7B-8D.1 Decision Scheduling Fix Report",
    "",
    f"final_decision: {final_decision}",
    f"ready_for_stage7b_9: {str(ready_for_stage7b_9).lower()}",
    f"decisions_target: {decisions_target}",
    f"decisions_completed: {decisions_completed}",
    "",
    "## Core Metrics",
    f"- behavior_name: {behavior_name}",
    f"- behavior_type: {behavior_type}",
    f"- model_assigned: {str(model_assigned).lower()}",
    f"- collect_observations_count: {report['collect_observations_count']}",
    f"- write_discrete_action_mask_count: {report['write_discrete_action_mask_count']}",
    f"- on_action_received_count: {report['on_action_received_count']}",
    f"- heuristic_call_count: {heuristic_calls}",
    f"- padding_warning_detected: {str(padding_warning_detected).lower()}",
    "",
    "## Scheduler",
    f"- trace_count: {len(scheduler_rows)}",
    f"- request_decision_calls_after_first_action: {scheduler_requests_after_first}",
    f"- requester_enabled_after_first_action: {str(requester_enabled_after_first_action).lower()}",
    f"- match_state_after_first_action: {match_state_after_first_action}",
    f"- skip_reason_histogram: {json.dumps(scheduler_skip_hist_serializable, ensure_ascii=True)}",
    "",
    "## Action Stats",
    f"- candidate_action_index_histogram: {json.dumps(candidate_hist_serializable, ensure_ascii=True)}",
    f"- noop_ratio: {noop_ratio:.6f}",
    f"- non_noop_ratio: {non_noop_ratio:.6f}",
    f"- runtime_apply_attempted: {runtime_apply_attempted}",
    f"- runtime_apply_accepted: {runtime_apply_accepted}",
    f"- runtime_apply_rejected: {runtime_apply_rejected}",
    "",
    "## Blockers",
]

if blockers:
    md_lines.extend([f"- {b}" for b in blockers])
else:
    md_lines.append("- none")

report_md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
print("Stage7B-8D.1 report generated")
