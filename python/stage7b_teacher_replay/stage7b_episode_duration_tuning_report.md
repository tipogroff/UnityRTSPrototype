# Stage7B Episode Duration Tuning Report

## Summary
Stage7B/Week7 episode duration was increased in a targeted way by raising the Stage7B decision cap and expanding extended inference smoke decision coverage.

Final decision: GO

## Exact Changed Files
- Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity
- Assets/Scripts/MLAgents/Stage7B/Editor/Stage7BInferenceMode8CMenu.cs

## Exact Generated Artifacts
- python/stage7b_teacher_replay/stage7b_episode_duration_tuning_report.json
- python/stage7b_teacher_replay/stage7b_episode_duration_tuning_report.md
- python/stage7b_teacher_replay/stage7b_episode_duration_tuning_trace.jsonl

## Old and New Values

### Stage7B episode decision limit
- old: 256
- new: 512
- reason: reduce premature episode truncation by stage7b_decision_limit and allow longer contiguous behavior windows
- scope: Stage7B-only

### Stage7B episode step limit
- old: 2000
- new: 2000
- reason: already sufficient; not dominant truncation factor
- scope: global constant used by Stage7B runtime

### Extended inference smoke decisions target
- old: 50
- new: 300
- reason: ensure short smoke runs can cover at least 250 decisions before stop
- scope: Stage7B-only

### Extended inference smoke timeout
- old: 900 seconds
- new: 900 seconds
- reason: already enough for longer target
- scope: Stage7B-only

## Root Cause
Observed dominant early-stop cause: stage7b_decision_limit at 256 decisions per episode.

Evidence before tuning:
- source: python/stage7b_teacher_replay/stage7b_8d_extended_onnx_inference_report.json
- episode_terminal_reason: stage7b_decision_limit
- on_action_received_count: 1678
- runtime_apply_attempted: 1678

## Episode Duration Before/After

### Before
- terminal reason: stage7b_decision_limit (dominant in runtime episodes)
- short smoke target: 50 decisions (extended menu target)

### After
- source: python/stage7b_teacher_replay/stage7b_8d1_decision_scheduling_fix_report.json
- on_action_received_count: 300
- episode_terminal_reached: false
- episode_terminal_reason: none
- runtime_apply_attempted: 300
- runtime_apply_accepted: 300
- reset proxy (on_episode_begin_count): 1

Interpretation:
- short smoke is no longer dominated by too-short stage7b_decision_limit
- one run now covers >= 250 decisions without forced early terminal

## Inference Path Health Check
Source: python/stage7b_teacher_replay/stage7b_8d1_decision_scheduling_fix_report.json

- Behavior Type: InferenceOnly
- Heuristic call count: 0
- Padding warning: false
- CollectObservations writes 15552: true
- WriteDiscreteActionMask > 0: true
- OnActionReceived > 0: true
- runtime_apply_attempted > 0: true
- runtime_apply_accepted > 0: true
- duplicate_spawn_detected: false

## Scripted Bot Pacing Health Check
Source: python/stage7b_teacher_replay/stage7b_week7_scripted_bot_throttle_report.json

- scripted bot decisions/actions > 0: true
- bot_decision_executed_count: 37
- bot_actions_attempted_after: 37
- actions per 100 student steps: 14.45
- pre-tuning baseline actions per 100: 33.51
- remains lower than baseline: true
- accepted_bot_attack_actions: 0
- opening_grace_worked: true

## Action Breakdowns

### Student (after duration tuning run)
- noop: 17
- move: 251
- harvest: 9
- return: 0
- produce: 21
- attack: 2

### Scripted bot (latest pacing telemetry)
- move: 846
- harvest: 20
- return: 6
- produce: 42
- attack: 0
- noop: 0
- other: 0

## Unity Console
- errors: 0
- warnings: 0
- warning classification: none

## Constraint Compliance
- Stage6B3 baseline untouched
- Stage6B3 checkpoint unchanged
- teacher policy unchanged
- clean demo dataset unchanged
- reward semantics unchanged
- ActionApplier/MatchManager semantics unchanged
- candidate builder/contract unchanged
- observation/action semantics unchanged
- ONNX not re-exported
- no long training and no PPO rerun in this step
- terminal logic not disabled

## GO/NO-GO
GO

Stage7B episodes are now long enough for meaningful smoke/evaluation interpretation while preserving previously validated inference and runtime behavior contracts.
