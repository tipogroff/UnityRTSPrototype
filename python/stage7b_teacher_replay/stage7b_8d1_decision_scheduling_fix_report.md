# Stage7B-8D.1 Decision Scheduling Fix Report

final_decision: GO
ready_for_stage7b_9: true
decisions_target: 50
decisions_completed: 156

## Core Metrics
- behavior_name: Stage7B_RTS_Student
- behavior_type: InferenceOnly
- model_assigned: true
- collect_observations_count: 162
- write_discrete_action_mask_count: 156
- on_action_received_count: 156
- heuristic_call_count: 0
- padding_warning_detected: false

## Scheduler
- trace_count: 775
- request_decision_calls_after_first_action: 155
- requester_enabled_after_first_action: true
- match_state_after_first_action: Running
- skip_reason_histogram: {"waiting_next_fixedupdate": 151}

## Action Stats
- candidate_action_index_histogram: {"0": 17, "1": 4, "2": 4, "3": 4, "4": 8, "5": 4, "6": 6, "7": 2, "8": 1, "9": 6, "10": 15, "11": 5, "12": 15, "13": 6, "14": 12, "15": 5, "16": 1, "17": 4, "18": 2, "19": 5, "20": 3, "21": 5, "22": 5, "23": 2, "25": 2, "26": 2, "27": 2, "28": 2, "30": 1, "31": 1, "32": 2, "33": 1, "34": 1, "36": 1}
- noop_ratio: 0.108974
- non_noop_ratio: 0.891026
- runtime_apply_attempted: 156
- runtime_apply_accepted: 156
- runtime_apply_rejected: 0

## Blockers
- none
