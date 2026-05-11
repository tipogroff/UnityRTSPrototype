# Stage7B Scripted Opponent Pacing Tuning Report

## Scope
Targeted tuning was applied to slow down the Week7 scripted opponent and reduce early aggression without changing core runtime semantics.

## Exact Changed Files
- Assets/Scripts/MLAgents/Stage7B/Week7ScriptedOpponentPacing.cs
- Assets/Scripts/ML/HeuristicPolicyAdapter.cs
- Assets/Scripts/MLAgents/Stage7B/MlAgentsTrainingBootstrap.cs

## Old vs New Pacing Values

### Old (baseline snapshot)
- bot_decision_interval_steps: 3
- bot_action_cooldown_seconds: 0.0
- opening_grace_steps: not present
- attack_action_cooldown_steps: not present
- max_aggressive_actions_per_window: not present

### New (tuned)
- bot_decision_interval_steps: 7
- bot_action_cooldown_seconds: 0.0
- opening_grace_steps: 80
- allow_economy_actions_during_grace: true
- allow_attack_during_grace: false
- aggression_delay_steps: 120
- attack_action_cooldown_steps: 30
- aggression_window_steps: 100
- max_aggressive_actions_per_window: 2

## Scripted Bot Presence and Activity
- scripted bot present: true
- scripted bot enabled: true
- not idle: true
- evidence: non-zero decisions/actions telemetry in tuned run

## Metrics

### Baseline snapshot (pre-tuning report)
- student_actions_attempted: 191
- bot_actions_attempted_after: 64
- actions_per_100_steps: 33.51
- accepted_bot_commands: 1600
- terminal_reason: EnemyBaseDestroyed

### Tuned snapshot
- student_actions_attempted: 256
- bot_decision_attempt_count: 256
- bot_decision_executed_count: 37
- bot_actions_attempted_after: 37
- actions_per_100_steps: 14.45
- accepted_bot_commands: 920
- rejected_bot_commands: 0
- action breakdown:
  - move: 852
  - harvest: 20
  - return: 6
  - produce: 42
  - attack: 0
  - noop: 0
  - other: 0
- first_attack_step: -1 (no attacks)
- opening_grace_worked: true
- terminal_reason: stage7b_decision_limit

### Pacing delta
- actions_per_100_steps before: 33.51
- actions_per_100_steps after: 14.45
- drop: 19.06
- drop percent: 56.88%

## Inference Path Integrity Check
Source: python/stage7b_teacher_replay/stage7b_8c2_padding_warning_fix_report.json

- Behavior Type (runtime): InferenceOnly
- heuristic_call_count: 0
- observation_zero_padding_warning_detected: false
- on_action_received_count: 1648 (> 0)
- runtime_apply_attempted: 1648 (> 0)
- runtime_apply_accepted: 1648
- runtime_apply_rejected: 0
- inference smoke final decision: GO

## Unity Console
- errors: 0
- warnings: 3
- warnings observed:
  - [BuildingRuntime] Нет свободной ячейки рядом с (2, 1) для спавна Heavy
  - [BuildingRuntime] Нет свободной ячейки рядом с (3, 0) для спавна Ranged
  - [BuildingRuntime] Нет свободной ячейки рядом с (2, 0) для спавна Ranged

## Hard Constraints Check
- Stage6B3 baseline untouched: yes
- teacher policy unchanged: yes
- clean demo dataset unchanged: yes
- reward semantics unchanged: yes
- ActionApplier unchanged: yes
- MatchManager unchanged: yes
- MlAgentsCandidateActionBuilder unchanged: yes
- observation/action contract unchanged: yes
- ONNX unchanged: yes
- training not run: yes
- PPO rerun not run: yes

## Final Decision
GO

Scripted opponent remains functional and active, but now runs at a slower effective pace with reduced early aggression. This makes upcoming Stage7B-9.1 and Stage7B-10 smoke/evaluation runs easier to interpret.
