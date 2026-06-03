# Game Speed Pause Actual Fix Report

## Summary

The pause bug was caused by treating simulation pause as a speed value instead of as a separate automatic-stepping state. In the step-pacing model, `0 steps/sec` and `interval <= 0` still mean legacy pacing-disabled mode: automatic stepping runs once per `FixedUpdate`. Therefore using `0` as pause can leave the match advancing.

The current fix separates those states:

- pacing disabled: `DecisionTickIntervalSeconds <= 0`, legacy/debug behavior, step every `FixedUpdate`;
- simulation paused: `EpisodeController.IsAutomaticSteppingPaused == true`, no automatic steps;
- manual single-step: `GameSpeedController.StepOnce()` calls `EpisodeController.StepEpisodeOnce()` only while paused and does not resume continuous stepping.

## Actual Cause

Yes, the suspected `0 steps/sec` / `interval <= 0` interpretation was the relevant failure mode. `EpisodeController` preserves legacy behavior for `_decisionTickIntervalSeconds <= 0f` by calling `StepMatchWithHeuristics()` every `FixedUpdate`. Pause therefore cannot be represented by setting the target rate to zero.

## EpisodeController

`EpisodeController` now owns the actual pause state through:

- `_automaticSteppingPaused`;
- `IsAutomaticSteppingPaused`;
- `SetAutomaticSteppingPaused(bool paused)`.

`SetAutomaticSteppingPaused` always clears `_decisionTickAccumulatorSeconds`, so paused time does not accumulate a backlog that would be processed after Continue.

In the automatic loop, `FixedUpdate` checks pause before evaluating the interval branch:

- `_autoStepInFixedUpdate`;
- `_episodeRunning`;
- match phase `Running`;
- `_automaticSteppingPaused`;
- paced accumulator or legacy `interval <= 0` stepping.

That ordering is the important part: pause is checked before the `interval <= 0` legacy path.

## GameSpeedController

`GameSpeedController.Pause()` sets `_isPaused = true` and calls `EpisodeController.SetAutomaticSteppingPaused(true)`. It does not convert pause into a zero target rate.

`GameSpeedController.Resume()` clears the pause flag with `SetAutomaticSteppingPaused(false)` and reapplies `_activeStepsPerSecond`, preserving the selected speed such as Slow, Normal, Fast, or Debug.

`GameSpeedController.StepOnce()` requires `IsPaused == true`, calls `EpisodeController.StepEpisodeOnce()`, and does not call `Resume()`.

## HumanPlayCanvasController

The Pause Menu path calls the same simulation controller path:

- opening the menu calls `PauseSimulation()`;
- `PauseSimulation()` calls `GameSpeedController.Pause()` and also sets `EpisodeController.SetAutomaticSteppingPaused(true)` as a fallback;
- closing the menu calls `ResumeSimulation()`;
- `ResumeSimulation()` calls `GameSpeedController.Resume()` when the speed controller is paused, otherwise it clears the episode pause fallback;
- the Step button calls `GameSpeedController.StepOnce()` when available, otherwise it calls `EpisodeController.StepEpisodeOnce()` only while the Pause Menu is active.

No UI display logic was needed for the actual fix.

## Scene Reference Check

Checked the active scene `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity` through Unity MCP:

- `GameSpeedController`: 1 instance, on `PresentationControls`;
- `EpisodeController`: 1 instance, on `EpisodeController`;
- `HumanPlayCanvasController`: 1 instance, on `HumanPlayCanvas`;
- `GameSpeedController.CurrentStepsPerSecond`: `5`;
- `EpisodeController.DecisionTickIntervalSeconds`: `0.2`;
- `EpisodeController.TargetStepsPerSecond`: `5`;
- `EpisodeController.IsAutomaticSteppingPaused`: `false` before opening pause.

This confirms the UI, speed controller, and episode controller are not duplicated in the active scene.

## Verification

Static verification:

- `EpisodeController.FixedUpdate` checks `_automaticSteppingPaused` before the legacy `interval <= 0` branch.
- `Pause()` sets the episode pause flag instead of relying on `0 steps/sec`.
- `Resume()` restores `_activeStepsPerSecond`.
- `StepOnce()` does exactly one `StepEpisodeOnce()` call and leaves pause enabled.

Unity Editor verification:

- Console error query after inspection returned 0 errors.
- Active scene inspection found one instance of each required controller.

Manual runtime verification still to run in the game window:

- MainMenu -> Start -> AI vs player;
- wait until the step counter increases;
- press Escape and confirm the Pause Menu opens;
- confirm the step counter does not change for 1 second of real time;
- press Step and confirm the counter increases by exactly 1;
- wait another second and confirm it does not change again;
- press Continue and confirm the counter resumes at the selected speed;
- repeat for AI vs bot and AI vs AI;
- confirm no `NullReferenceException` or `MissingReferenceException` appears in Console.
