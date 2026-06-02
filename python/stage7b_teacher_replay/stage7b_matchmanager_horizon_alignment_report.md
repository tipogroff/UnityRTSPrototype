# Stage7B MatchManager Horizon Alignment

Scope: Stage7B-only.

## Objective
- Stage7B decision cap = 6000.
- MatchManager max step = 6000.

## Code Change
- File: Assets/Scripts/MLAgents/Stage7B/MlAgentsTrainingBootstrap.cs
- Added a Stage7B runtime-only max-step override (default 6000).
- Aligned StudentAgent.MaxStep with the same resolved horizon.
- Injected a runtime-cloned GameConfig into MatchBootstrap so shared assets are not modified.

## Validation Evidence
- Unity menu run: RTS/Week7/Stage7B/Run Extended ONNX Inference Smoke 8D.1
- Evidence report: python/stage7b_teacher_replay/stage7b_8d1_decision_scheduling_fix_report.json
- Fresh timestamp: 2026-05-11T16:11:46.4475352Z
- match_max_steps: 6000
- match_end_reason: None
- match_state_end: Running
- episode_terminal_reason: EnemyBaseDestroyed
- runtime_apply_attempted / accepted / rejected: 378 / 378 / 0
- unity_console_errors: 0
- Scene decision cap field: _stage7BMaxDecisionsPerEpisode: 6000

## Decision
- Alignment result: GO
- StepLimitReached at 2000: not observed in this validation.

## Notes
- GameConstants.MaxEpisodeSteps was not changed.
- Assets/ML/GameConfig_MVP.asset was not edited.
- Existing Stage7B 8D.1 report still marks NO_GO for an unrelated observation-contract blocker (code C).
