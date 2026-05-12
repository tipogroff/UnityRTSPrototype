# HUMAN PLAY 1R2 NEW INPUT HOTKEY FIX REPORT

Date: 2026-05-13
Stage: HumanPlay-1R2 - New Input System Hotkey Fix

## Root Cause

The hotkeys were still not working because the controller path could still reach `UnityEngine.Input.GetKeyDown(...)` in a project configured for the New Input System backend. In this workspace, `ProjectSettings/ProjectSettings.asset` has `activeInputHandler: 1`, which corresponds to `NewInputOnly`.

In addition, the old input path was sensitive to backend/focus state, so pressing keys could produce warnings while the overlay buttons remained usable.

## Exact Warning Before Fix

The warning text associated with the legacy input call path is the standard Unity message for New Input System-only projects:

- `You are trying to read Input using the UnityEngine.Input class, but you have switched active Input Handling to Input System Package in Player Settings.`

The previous call chain was:
- `GameSpeedController.WasKeyPressed(...)`
- `UnityEngine.Input.GetKeyDown(...)`

## Active Input Backend

Detected backend:
- `NewInputOnly`

Evidence:
- `Packages/manifest.json` includes `com.unity.inputsystem`.
- `ProjectSettings/ProjectSettings.asset` has `activeInputHandler: 1`.

## What Changed in GameSpeedController

Updated [Assets/Scripts/Presentation/GameSpeedController.cs](Assets/Scripts/Presentation/GameSpeedController.cs) to:
- detect backend at runtime/editor time;
- distinguish `NewInputOnly`, `LegacyOnly`, `Both`, and `Unknown`;
- skip Legacy polling entirely when backend is `NewInputOnly`;
- use `Keyboard.current` only for the New Input path;
- keep keypad support for `Keypad1` to `Keypad4`;
- expose overlay diagnostics for backend, `Keyboard.current`, last hotkey, and last input source;
- keep OnGUI mouse buttons as a fallback path;
- preserve safe `Time.timeScale` / `Time.fixedDeltaTime` restore behavior.

## Legacy Polling in NewInputOnly

Yes, legacy polling is now skipped in `NewInputOnly`.

## Controls

Working control paths implemented in the controller:
- `Space` -> pause/resume
- `1` -> `1.0x`
- `2` -> `0.5x`
- `3` -> `0.25x`
- `4` -> `0.1x`
- `N` -> single-step while paused
- OnGUI buttons -> same actions

## Validation Results

Completed in this session:
- `GameSpeedController.cs` compiles cleanly.
- Week7 scene still contains `PresentationControls` with `GameSpeedController` attached.
- Scene-local safety gate remains disabled for the demo scene, so hotkeys are not blocked there.
- Unity console after the repair shows no new errors from this change.

Not directly executable from the available tools in this session:
- physical Game View keypress testing for `1/2/3/4/Space/N`;
- confirming the exact on-screen `last hotkey` transitions after real keypresses.

## Console After Validation

- No new compiler errors were reported for `GameSpeedController.cs`.
- Remaining console entries are pre-existing warnings unrelated to this repair pass.

## Changed Files

- [Assets/Scripts/Presentation/GameSpeedController.cs](Assets/Scripts/Presentation/GameSpeedController.cs)
- [Assets/Scripts/Presentation/GameSpeedController.cs.meta](Assets/Scripts/Presentation/GameSpeedController.cs.meta)
- [Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity](Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity)
- [HUMAN_PLAY_GAME_SPEED_CONTROLLER_REPORT.md](HUMAN_PLAY_GAME_SPEED_CONTROLLER_REPORT.md)
- [HUMAN_PLAY_1R_HOTKEY_INPUT_REPAIR_REPORT.md](HUMAN_PLAY_1R_HOTKEY_INPUT_REPAIR_REPORT.md)
- [HUMAN_PLAY_1R2_NEW_INPUT_HOTKEY_FIX_REPORT.md](HUMAN_PLAY_1R2_NEW_INPUT_HOTKEY_FIX_REPORT.md)

## Semantics Safety

No gameplay, AI, training, observation/action, reward, terminal, spawn, occupancy, or visual animation semantics were changed.
