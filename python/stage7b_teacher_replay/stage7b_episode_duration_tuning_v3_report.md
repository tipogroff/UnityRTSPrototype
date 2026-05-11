# Stage7B Episode Duration Tuning v3

Scope: Stage7B-only.

## What Changed
- `Assets/Scripts/MLAgents/Stage7B/Editor/Stage7BInferenceMode8CMenu.cs`
  - `Timeout8DSeconds`: `1200` -> `1800`
  - `DefaultDecisionsTarget8D`: `1000` -> `3000`
  - Added `FullHorizonDecisionsTarget8D = 6000`
  - Added `Run Full Horizon ONNX Inference Smoke 8D.2`
- `Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity`
  - `_stage7BMaxDecisionsPerEpisode`: `1500` -> `6000`
- `Assets/Scripts/MLAgents/Stage7B/Diagnostics/Stage7BInferenceSmokeDiagnostics.cs`
  - Added end-state and base telemetry to the smoke snapshot.
  - New fields include `match_state_end`, `match_step`, `match_max_steps`, `match_end_reason`, `player1_base_count`, `player2_base_count`, `player1_base_alive`, and `player2_base_alive`.

## Validation Snapshot
- Decisions completed: `2542`
- `on_action_received_count`: `2542`
- `actual_collect_calls`: `2544`
- `episode_terminal_reached`: `false`
- `episode_terminal_reason`: `none`
- `run_end_reason`: manual stop after the 2000+ band
- `match_state_end`: `Running`
- `match_step`: `542`
- `match_end_reason`: `None`
- `reset_count`: `3`
- Base state: Player1 `1 / alive`, Player2 `1 / alive`

## Action Mix
- `noop`: `109`
- `move`: `2269`
- `harvest`: `41`
- `return`: `5`
- `produce`: `109`
- `attack`: `9`

## Pacing And Health
- `decision_requester_enabled_runtime`: `true`
- `inference_kick_decision_request_count`: `3`
- `manual_loop_enabled`: `false`
- `watchdog_manual_fallback_enabled`: `false`
- `demo_mode_active`: `false`
- `runtime_apply_attempted`: `2542`
- `runtime_apply_accepted`: `2542`
- `runtime_apply_rejected`: `0`
- `no_heuristic_fallback`: `true`
- Unity Console: `0` errors, `0` warnings

## Notes
- The run crossed the old 1500 decision ceiling and continued cleanly.
- ML-Agents MaxStep did not limit the episode; the limiting Stage7B control remained the Stage7B-specific decision cap.
- The scene-level `MatchManager` max step remains `2000`; this tuning pass only raised the Stage7B episode decision cap.
