# Stage7B Episode Duration Tuning v2

## Final Decision
- GO

## Scope
- Stage7B-only tuning change set.
- No global max-step change; global cap remains 2000.

## Exact Parameter Changes
- stage7b_decision_limit: 512 -> 1500
  - Source: Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity
- extended inference smoke target: 300 -> 1000
  - Source: Assets/Scripts/MLAgents/Stage7B/Editor/Stage7BInferenceMode8CMenu.cs
- extended inference timeout: 900 -> 1200 seconds
  - Source: Assets/Scripts/MLAgents/Stage7B/Editor/Stage7BInferenceMode8CMenu.cs

## v2 Run Result (8D.1)
Source: python/stage7b_teacher_replay/stage7b_8d1_decision_scheduling_fix_report.json

- decisions_completed: 1000 (target reached)
- episode_terminal_reached: false
- episode_terminal_reason: none
- on_episode_begin_count: 2 (reset proxy: 1)
- runtime_apply_attempted/accepted/rejected: 1000 / 1000 / 0
- behavior_type_runtime: InferenceOnly
- heuristic_call_count: 0
- observation_values_written_by_agent: 15552 (expected 15552)
- duplicate_spawn_detected: false

## Student Action Breakdown
- move: 892
- noop: 41
- harvest: 22
- return: 2
- produce: 41
- attack: 2
- move ratio: 89.2%

## Scripted Opponent Pacing Status
Source: python/stage7b_teacher_replay/stage7b_scripted_opponent_pacing_tuning_report.json

- scripted bot present/enabled: yes
- tuned actions_per_100_steps: 14.45
- baseline actions_per_100_steps: 33.51
- reduction: 56.88%
- first_attack_step: -1 (opening grace respected)
- terminal_reason in pacing run: stage7b_decision_limit

Note: v2 8D.1 runtime report schema does not include scripted pacing counters, so latest dedicated pacing report is used as authoritative scripted-side evidence.

## Movement/Mid-Map Diagnostic
- Status: PARTIAL
- Reason: action/runtime/scheduler traces for v2 include counters and action types but no per-step unit positions or distance-to-enemy-base fields.
- Fallback evidence: movement-dominant policy (892/1000 moves), non-idle mixed action profile, no runtime rejections.

## Console Health
- errors: 0
- warnings: 1
- warning classification: benign spawn saturation (non-fatal unit spawn placement saturation in BuildingRuntime)

## Acceptance Matrix
- decision_limit_512_to_1500: PASS
- target_300_to_1000: PASS
- timeout_900_to_1200: PASS
- reached_1000_decisions: PASS
- inference_only_no_heuristic: PASS
- runtime_apply_no_rejects: PASS
- scripted_pacing_preserved: PASS
- quantified_far_progress_midmap: PARTIAL

## Conclusion
- GO for duration tuning v2.
- Residual gap: exact spatial far-progress/mid-map threshold verification requires additional positional telemetry fields in trace schema.
