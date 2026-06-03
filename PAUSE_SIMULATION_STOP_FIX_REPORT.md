# Pause Simulation Stop Fix Report

## Summary

Pause Menu opened correctly, but simulation could keep advancing because the menu visibility path only controlled UI state and did not explicitly stop `EpisodeController` automatic stepping in all cases.

The fix connects Pause Menu open/close to simulation pause/resume through `GameSpeedController` and an explicit `EpisodeController.SetAutomaticSteppingPaused(...)` fallback.

## Changed Files

- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
- `Assets/Scripts/Presentation/GameSpeedController.cs`
- `Assets/Scripts/ML/Editor/Week6VisualInspectionRunnerMenu.cs`

## Pause Open

`HumanPlayCanvasController.SetPauseMenuVisible(true)` now calls:

- `PauseSimulation()`
- `GameSpeedController.Pause()`
- `EpisodeController.SetAutomaticSteppingPaused(true)`

This stops automatic simulation steps while the Pause Menu is active.

## Continue / Pause Close

`HumanPlayCanvasController.SetPauseMenuVisible(false)` now calls:

- `ResumeSimulation()`
- `GameSpeedController.Resume()` when the speed controller is paused
- `EpisodeController.SetAutomaticSteppingPaused(false)` as fallback

`GameSpeedController.Resume()` keeps the currently selected steps/sec value through `_activeStepsPerSecond`, so Continue does not reset Slow/Fast speed selection to default.

## Step On Pause

The Pause Menu now includes a `Step` button.

`HumanPlayCanvasController.StepPausedSimulation()` calls:

- `GameSpeedController.StepOnce()` when available
- `EpisodeController.StepEpisodeOnce()` only as fallback and only while the Pause Menu is active

`GameSpeedController.StepOnce()` still requires paused state, so a single step does not re-enable continuous automatic stepping.

## Keyboard Fix

Editor menu shortcuts were removed from `Week6VisualInspectionRunnerMenu`:

- `_SPACE`
- `_RIGHT`
- `_L`

This prevents editor-only Week6 visual inspection commands from intercepting gameplay keys and printing warnings when the runner is not present in the scene.

## Time Scale

Normal match pause/resume does not use `Time.timeScale`.

Existing `Time.timeScale = 1f` assignments remain only in scene transition/reset paths such as restart/main menu return.

## Verification

- Unity script compilation completed successfully.
- Unity Console error check after compilation: 0 errors.
- Entered Play Mode from `HumanPlay_Demo_PlayerVsAI.unity`; startup produced 0 console errors.
- Code path verification:
  - Pause Menu active calls automatic stepping pause.
  - Continue resumes automatic stepping through the selected speed controller state.
  - Step button performs a single step while paused and does not resume continuous stepping.
  - Camera input remains blocked only by existing pause/settings menu visibility checks.

Manual in-window checks still recommended:

- `MainMenu -> Start -> AI против игрока`
- `AI против бота`
- `AI против AI`
- confirm step counter stops on Escape pause, advances once on Step, and resumes on Continue
- confirm no `NullReferenceException` or `MissingReferenceException`
