# HumanPlay ML-Agents Inference Drop Fix Report

## Summary

This cleanup targets periodic HumanPlay FPS drops that continue while the simulation is paused or the game speed changes. The change keeps the ML-Agents behavior/action contract intact and avoids adding runtime diagnostics, spike samplers, file writes, or log spam.

## DecisionRequester Policy

- `StudentMlAgent` now has `_disableDecisionRequesterInInferenceOnly = true` as a serialized A/B flag.
- In `RuntimeMode == InferenceOnly`, the default policy keeps `DecisionRequester` disabled even after inference runtime services become ready.
- `_currentDecisionSource` remains `none` in that default InferenceOnly path, so the agent is not marked as DecisionRequester-driven.
- Setting `_disableDecisionRequesterInInferenceOnly` to `false` restores the previous readiness-based DecisionRequester path for A/B comparison.

## InferenceOnly Behavior

- InferenceOnly no longer relies on the automatic ML-Agents `DecisionRequester` cadence by default.
- AI is still allowed to request decisions through the existing controlled/manual inference scheduler in `StudentMlAgent`.
- The ONNX/model contract, observation shape, action masks, and action application semantics were not changed.

## Inference Throttling

- Added `_minInferenceDecisionIntervalSeconds = 0.2f`.
- In InferenceOnly, `RequestDecision()` is not called more often than this interval.
- The interval uses `Time.realtimeSinceStartup`, so it is independent of `Time.timeScale`.
- The first inference kick after episode/start reset is not throttled.
- Throttled requests clear pending continuous inference instead of accumulating queued requests.

## Pause-Aware Scheduling

- Inference kick, continuous inference, post-action scheduling, and the shared `RequestDecisionWithTracking()` path now check simulation pause before requesting decisions.
- When `EpisodeController.IsAutomaticSteppingPaused` is active:
  - `RequestDecision()` is not called;
  - pending continuous inference is cleared;
  - post-action scheduling does not queue a new inference decision.
- The existing `OnActionReceived` pause branch also clears pending continuous inference.
- The pause gate no longer emits periodic `Debug.Log` messages.

## ActionApplier Allocation Cleanup

- `ResolveDependencies()` no longer creates a new `ActionApplier` on every call.
- `ActionApplier` is rebuilt only when it is missing or one of its dependencies changes:
  - `GridManager`
  - `UnitRegistry`
  - `MatchManager`
  - `ResourceManager`
- `OnEpisodeBegin` can still reset `_actionApplier` as before.

## Files Changed

- `Assets/Scripts/MLAgents/Stage7B/StudentMlAgent.cs`
- `HUMAN_PLAY_MLAGENTS_INFERENCE_DROP_FIX_REPORT.md`

## Technical Checks

- Unity MCP structured script edits were applied with C# validation enabled on method replacements where practical.
- No new runtime file writes were added.
- No new frequent logs, spike samplers, per-frame counters, or performance monitor extensions were added.
- Manual HumanPlay FPS run was not performed; this is left for user verification.

## Manual Verification Requested

- Run HumanPlay / ML-Agents inference mode.
- Confirm `DecisionRequester` stays disabled in `InferenceOnly` with `_disableDecisionRequesterInInferenceOnly = true`.
- Pause the simulation and confirm the periodic CollectObservations / action loop stops.
- Compare FPS drop cadence before/after the change.
- For A/B, set `_disableDecisionRequesterInInferenceOnly = false` and compare behavior if needed.
