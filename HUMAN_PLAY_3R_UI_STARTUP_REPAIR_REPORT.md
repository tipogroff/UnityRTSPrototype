# HumanPlay-3R UI / Startup / Pause Camera Repair Report

Date: 2026-05-17

## UI Layout Fixes

- Reworked `MainMenuController` runtime layout.
- Main menu panel is now centered and enlarged to `760x620`.
- Main buttons are in a `VerticalLayoutGroup` with consistent `440x70` button size and 26 px spacing.
- Buttons are placed in the lower-middle of the panel instead of near the bottom.
- Settings UI is now a modal overlay with a centered `620x420` panel.
- Settings content uses layout groups:
  - title row;
  - `Volume` label + slider row;
  - `Fullscreen` label + toggle row;
  - `Back` button below the controls.

Before: settings controls were manually positioned, causing toggle/label separation, slider overlap, and Back button collision.

After: rows are layout-driven and aligned consistently at 16:9 resolutions.

## Pause Camera Fix

- Updated `RtsCameraController`.
- Movement already used `Time.unscaledDeltaTime`.
- Smoothing now explicitly uses the `SmoothDamp(..., deltaTime: Time.unscaledDeltaTime)` overload for both position and orthographic zoom.
- Camera input continues while `Time.timeScale == 0`.
- Camera input is ignored while a UI text/input field is focused.
- Mouse wheel and middle-mouse drag still avoid pointer-over-UI conflicts.

## Demo Startup Fix

Root cause: the demo scene did not have one authoritative presentation startup owner for the final human demo flow. The old runtime services could be created, but `HumanPlayModeController` was not reliably starting the correct mode automatically, so the top-right `Start AI vs P2` button was required to repair roles after scene startup.

Fix:

- `MlAgentsTrainingBootstrap._autoStartEpisodeOnStart = false`
- `MlAgentsTrainingBootstrap._stepScriptedOpponent = false`
- `EpisodeController._autoStartOnPlay = false`
- `Stage7B_DemoOrchestrator` remains disabled.
- `HumanPlayModeController._initialMode = AIvsPlayer2`
- `HumanPlayModeController._autoStartOnEnable = true`
- Added delayed runtime-ready startup in `HumanPlayModeController`.
- Startup waits for `EpisodeController`, `MatchManager`, `MatchBootstrap`, and `GridManager`, then calls `StartAIvsPlayer2()`.
- Added startup diagnostics logging for auto-start flags, mode, p1/p2 decision modes, human side, demo orchestrator state, and scripted-opponent component state.

Validated runtime state after startup:

- `CurrentMode = AIvsPlayer2`
- `HumanSide = Player2`
- `EnableWeek6StudentMatchControl = true`
- `Player1DecisionMode = StudentInference`
- `Player2DecisionMode = Idle`
- `HumanPlayerController.IsHumanControlActive = true`

## Build Settings

Build settings are now ordered:

1. `Assets/Scenes/MainMenu.unity`
2. `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`
3. Existing additional scenes after those two.

Unity Editor behavior note: pressing Play while the demo scene is open still starts that currently open scene by Unity design. Final build/application startup uses build index 0, so it starts from `MainMenu`.

## Editor Utilities

Added menu items:

- `Tools/HumanPlay/Open Main Menu`
- `Tools/HumanPlay/Open Demo Scene`

## Validation Notes

- Unity compile: no C# errors.
- MainMenu play-mode smoke: no errors or warnings.
- Demo play-mode smoke: no C# errors.
- No New Input System legacy warnings observed.
- Demo runtime produced existing policy/action diagnostic warnings from Player1 inference attempts; these are not UI/input/compiler warnings and Player2 remained `Idle`.

## Constraints Confirmation

- No gameplay rules changed.
- No observation/action contract changes.
- `ActionDecoder` and `ActionApplier` semantics were not changed.
- No unit gameplay command path bypass was added.
- UI command buttons still route through `PlayerCommandController -> AgentAction -> ActionApplier -> MatchManager.ApplyCommand`.
- `Week7_MLAgents_StudentVsScriptedBot.unity` was not modified.
- No Python/training/checkpoint files were intentionally changed by this repair. Pre-existing dirty Python artifacts remain outside this stage's scope.
