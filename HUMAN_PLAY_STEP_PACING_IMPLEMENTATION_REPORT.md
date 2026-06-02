# Human Play Step Pacing Implementation Report

## Implementation

Interactive match pacing is implemented in `Assets/Scripts/Gameplay/Match/EpisodeController.cs`.

- `_decisionTickIntervalSeconds` remains `0` by default, preserving the historical every-`FixedUpdate` behavior for existing training and baseline scenes.
- When the interval is positive, automatic stepping uses a wall-clock accumulator based on `Time.unscaledDeltaTime`.
- Catch-up is limited by `_maxAutomaticStepsPerFixedUpdate` (`3` in the human-play demo) and backlog is clamped.
- Starting a new episode, changing the target rate, and pausing automatic stepping reset the accumulator.
- `StepEpisodeOnce()` remains available while automatic stepping is paused and executes exactly one canonical simulation step.

`Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity` enables pacing with `_decisionTickIntervalSeconds: 0.2`, giving the default human-readable rate of `5 steps/sec`.

## Speed Controls

`Assets/Scripts/Presentation/GameSpeedController.cs` now controls the simulation-step target instead of global Unity time.

| Mode | Simulation rate |
| --- | ---: |
| Slow | 2 steps/sec |
| Normal | 5 steps/sec |
| Fast | 10 steps/sec |
| Debug | 20 steps/sec |

- Pause stops automatic simulation steps and clears accumulated backlog.
- Step calls `StepEpisodeOnce()` only while paused.
- Resume continues automatic stepping at the previously selected simulation rate.
- Existing keyboard and HUD speed controls are reused.

`Time.timeScale` is not used for ordinary match slowdown. This keeps camera movement, input polling, drag selection, UI refreshes, context actions, and menu interaction responsive at normal presentation speed.

## HUD Status

The human-play metrics panel and legacy HUD show the current simulation rate as `steps/sec`, or `paused`.

## Verification

Completed:

- Confirmed the human-play demo scene enables `5 steps/sec` pacing.
- Confirmed the default interval in code remains `0`, so pacing is not globally enabled for training or baseline scenes.
- Confirmed `GameSpeedController` no longer writes `Time.timeScale` or `Time.fixedDeltaTime`.
- Confirmed protected gameplay, ML, training, checkpoint, ONNX, `ActionDecoder`, `ActionApplier`, `MatchManager`, and `Week7_MLAgents_StudentVsScriptedBot.unity` files were not edited.
- Requested Unity script compilation and confirmed `0` console errors.
- Ran the available EditMode test job successfully.
- Ran the available PlayMode test job successfully; the project reported no registered PlayMode test cases.
- Entered Play Mode from the active demo scene and confirmed the expected redirect to `MainMenu` when no launch mode has been selected, with `0` runtime errors and `0` warnings.

Not automated in this environment:

- Menu-driven manual interaction checks for AI vs player, AI vs bot, and AI vs AI.
- Visual responsiveness checks for camera WASD/zoom/middle drag, selection, drag selection, and context actions.
