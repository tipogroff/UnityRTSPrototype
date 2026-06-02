# HUMAN PLAY 1R HOTKEY INPUT REPAIR REPORT

Date: 2026-05-13
Stage: HumanPlay-1R - GameSpeedController Hotkey Input Repair

## Root Cause

The controller was present in the Week7 scene, but two independent issues prevented keyboard control in Play Mode:
- the scene had `_enableOnlyInManualPlayMode` enabled while `MlAgentsTrainingBootstrap` was forced into `TrainerControlled` mode, which gated the controller off;
- the controller only listened to Legacy `Input.GetKeyDown`, while the project uses the New Input System backend for Play Mode input.

## Hotkey Repair Notes

- The controller now performs runtime/editor backend detection and distinguishes `NewInputOnly`, `LegacyOnly`, `Both`, and `Unknown`.
- In `NewInputOnly`, legacy polling is skipped entirely, so `UnityEngine.Input.GetKeyDown` is no longer called in this mode.
- The overlay now exposes `Keyboard.current`, last hotkey, last input source, and whether polling is active.

## Active Input Backend

Observed project configuration:
- `Packages/manifest.json` includes `com.unity.inputsystem`.
- `ProjectSettings/ProjectSettings.asset` has `activeInputHandler: 1`.

Result:
- New Input System is active in this project configuration.

## Legacy Warnings

- The warning pattern associated with the old path is the standard Unity Input-system warning:
	- `You are trying to read Input using the UnityEngine.Input class, but you have switched active Input Handling to Input System Package in Player Settings.`
- The call chain that triggered it before the fix was `GameSpeedController.WasKeyPressed(...) -> UnityEngine.Input.GetKeyDown(...)`.

## What Changed in GameSpeedController

Updated [Assets/Scripts/Presentation/GameSpeedController.cs](Assets/Scripts/Presentation/GameSpeedController.cs) to:
- add development-only diagnostics in the overlay;
- add a universal `WasKeyPressed(...)` path;
- support New Input System and Legacy Input Manager via conditional compilation;
- support keypad keys `Keypad1` to `Keypad4`;
- add OnGUI mouse buttons for speed, pause, and step;
- track `last hotkey`, `input polling active`, `current timeScale`, `current fixedDeltaTime`, and update ticks;
- preserve safe `Time.timeScale` / `Time.fixedDeltaTime` restore behavior.
- add explicit backend detection so Legacy polling is skipped in `NewInputOnly`.

## Supported Input Paths

Supported in the repaired controller:
- Legacy Input Manager
- New Input System
- Keypad keys
- OnGUI mouse fallback buttons
- Backend detection: `NewInputOnly`, `LegacyOnly`, `Both`, `Unknown`

## Overlay Buttons

Added buttons for:
- `1x`
- `0.5x`
- `0.25x`
- `0.1x`
- `Pause/Resume`
- `Step`

These invoke the same public methods as the keyboard path.

## Scene Safety Adjustment

Updated [Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity](Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity) so the scene-local controller is not blocked by the manual-play gate.

## Validation Results

Completed validations:
- `GameSpeedController.cs` compiles cleanly.
- Week7 scene contains `PresentationControls` with `GameSpeedController` attached.
- Scene-local gate was updated to allow hotkeys in the demo scene.
- Unity console check showed no new errors after the repair.

Remaining manual Play Mode checks:
- `1`, `2`, `3`, `4` should change speed.
- `Space` should pause and resume.
- `N` should step once while paused.
- OnGUI buttons should work even when keyboard focus is unreliable.

## Changed Files

- `Assets/Scripts/Presentation/GameSpeedController.cs`
- `Assets/Scripts/Presentation/GameSpeedController.cs.meta`
- `Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity`
- `HUMAN_PLAY_GAME_SPEED_CONTROLLER_REPORT.md`
- `HUMAN_PLAY_1R_HOTKEY_INPUT_REPAIR_REPORT.md`

## Semantics Safety Confirmation

No gameplay, AI, training, observation/action, reward, terminal, spawn, occupancy, or animation-binding semantics were changed.
