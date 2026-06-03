# Game Speed Space Pause Regression Fix Report

## Summary

Simulation pause in HumanPlay demo is now owned by `GameSpeedController`, with source-aware pause reasons for hotkey, menu, and external validation callers. Pause no longer depends on `0 steps/sec` or `Time.timeScale`.

The runtime failure was not only UI state drift. The actual simulation kept advancing because `StudentMlAgent.OnActionReceived()` could call `MatchManager.StepMatch()` directly, bypassing the `EpisodeController.FixedUpdate()` pause gate.

Changed files:

- `Assets/Scripts/Presentation/GameSpeedController.cs`
- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
- `Assets/Scripts/Presentation/HumanPlayModeController.cs`
- `Assets/Scripts/Gameplay/Match/EpisodeController.cs`
- `Assets/Scripts/MLAgents/Stage7B/StudentMlAgent.cs`
- `Assets/Scripts/Presentation/Debug/DebugPauseValidationRunner.cs`
- `Assets/Scripts/Editor/Presentation/DebugPauseValidationMenu.cs`
- `GAME_SPEED_PAUSE_VALIDATION_RUNTIME_REPORT.md`

## Previous Implementation

The older implementation, inspected from commit `d29f340`, handled pause in `GameSpeedController`:

- `Space` was read in `GameSpeedController.Update()`.
- `Space` called `TogglePause()`.
- `Pause()` set a controller-owned `_isPaused` flag.
- `Resume()` cleared that same flag.
- The old pause implementation used `Time.timeScale = 0f`.
- The Pause Menu also called `GameSpeedController.Pause()` / `Resume()`.

So the previous architecture had one presentation-level pause owner: `GameSpeedController`.

## Regression Causes

After step-pacing, normal match speed is controlled through simulation steps/sec instead of `Time.timeScale`.

Important semantic change:

- `interval <= 0` means legacy pacing disabled mode;
- legacy pacing disabled mode steps every `FixedUpdate`;
- therefore `0 steps/sec` cannot represent pause.

The earlier quick UI fix made the Pause Menu directly call `EpisodeController.SetAutomaticSteppingPaused(...)` as a fallback. That stopped menu pause in some paths, but it split pause state between UI and `GameSpeedController`, so Space pause and Menu pause could conflict.

The forensic runtime issue was a bypass:

- `EpisodeController.FixedUpdate()` respected `_automaticSteppingPaused`;
- `StudentMlAgent.OnActionReceived()` also stepped the match directly through `_bootstrap.MatchManager.StepMatch()`;
- that direct path did not check the pause state, so ML-Agents decisions could keep advancing the simulation while Escape/Space had paused `EpisodeController`.

The first gate attempt exposed a second issue:

- returning `false` from the direct step gate made `OnActionReceived()` treat the paused state as terminal;
- the terminal path called `EndEpisode()`;
- ML-Agents then invoked `OnEpisodeBegin()`;
- `OnEpisodeBegin()` called `StartNewEpisode(...)`, resetting the match during pause validation.

The final fix makes `OnActionReceived()` return early while paused before it can step, end the episode, or reset the match.

## New Pause Owner

`GameSpeedController` is now the single source of truth for HumanPlay/demo pause state.

It exposes source-aware pause reasons through the public `SimulationPauseReason` flags enum:

- `Hotkey`
- `Menu`
- `External`

`GameSpeedController.IsPaused` is true when any reason is active. It applies the actual simulation stop by calling `EpisodeController.SetAutomaticSteppingPaused(IsPaused)`.

Public pause API:

- `TogglePauseFromHotkey()`
- `PauseFromMenu()`
- `ResumeFromMenu()`
- `RequestPause(SimulationPauseReason reason)`
- `ReleasePause(SimulationPauseReason reason)`
- `ClearAllPauseReasons(string source = null)`
- `ReapplyPauseState(string source = null)`
- `StepOnce()`

`ActiveReasons` is the authoritative pause state. UI and mode controllers do not store independent paused/not-paused simulation state.

## Runtime Stepping Gates

`EpisodeController.FixedUpdate()` still blocks automatic stepping before paced or legacy stepping can run.

`StudentMlAgent.OnActionReceived()` now also respects pause:

- it checks `EpisodeController.Instance.IsAutomaticSteppingPaused` at entry;
- if paused, it records scheduler trace and returns without stepping or ending the episode;
- both direct `MatchManager.StepMatch()` calls are protected by the same pause check;
- scripted opponent auto-decisions inside the agent path are also blocked while paused.

This closes the direct ML-Agents stepping path that bypassed `EpisodeController`.

`EpisodeController.ResolveReferences()` now invalidates stale cached runtime references when singleton instances change. That keeps `EpisodeController`, `MatchBootstrap`, and `MatchManager` aligned after mode changes and restarts.

## Space Pause

`Space` is handled by `GameSpeedController.Update()` and calls `TogglePauseFromHotkey()`.

Behavior:

- first Space adds `Hotkey`;
- second Space removes `Hotkey`;
- selected steps/sec is preserved;
- automatic simulation stepping resumes only when no pause reasons remain.

## Escape / Pause Menu

`HumanPlayCanvasController` now uses the same `GameSpeedController` model:

- opening the Pause Menu calls `GameSpeedController.PauseFromMenu()`;
- Continue calls `GameSpeedController.ResumeFromMenu()`;
- Continue removes only the `Menu` reason.

Conflict behavior:

1. Press Space: `Hotkey` pause is active.
2. Press Escape: menu opens and adds `Menu`.
3. Press Continue: menu closes and removes only `Menu`.
4. Simulation remains paused because `Hotkey` is still active.
5. Press Space again: `Hotkey` is removed and simulation resumes.

## Step

The Pause Menu Step button calls `GameSpeedController.StepOnce()`.

`StepOnce()` requires `GameSpeedController.IsPaused == true`, calls `EpisodeController.StepEpisodeOnce()` exactly once, and does not remove any pause reason. Continuous automatic stepping remains blocked after the single step.

## Restart / Menu / Mode Changes

Pause reasons are cleared explicitly before starting or restarting HumanPlay modes:

- `HumanPlayModeController.StartAIvsAI()`
- `HumanPlayModeController.StartAIvsBot()`
- `HumanPlayModeController.StartHumanVsAi(...)`
- `HumanPlayModeController.RestartMatch()`
- `HumanPlayModeController.ReturnToMenu()`
- missing-launch-mode redirect to main menu
- `HumanPlayCanvasController.RestartMatch()`
- `HumanPlayCanvasController.ReturnToMainMenu()`

This prevents stale `Hotkey`, `Menu`, or `External` pause reasons from carrying into a new match or scene transition.

## Removed / Replaced Conflicts

The UI no longer calls `EpisodeController.SetAutomaticSteppingPaused(...)` directly.

Current direct calls to `SetAutomaticSteppingPaused(...)` are limited to:

- `EpisodeController` itself, as the automatic stepping owner;
- `GameSpeedController`, as the single presentation/demo pause owner.

The old UI fallback that independently paused/unpaused `EpisodeController` was removed from the Pause Menu path.

## Time Scale

Normal HumanPlay pause no longer uses `Time.timeScale`.

Existing `Time.timeScale = 1f` assignments remain only in scene transition/reset paths, such as restart and return to main menu.

## Dev-Only Runtime Validation

Added a Unity Editor-only runner and menu:

- Menu: `RTS/Debug/Pause Validation/Run All Modes`
- Runner: `DebugPauseValidationRunner`
- Report: `GAME_SPEED_PAUSE_VALIDATION_RUNTIME_REPORT.md`

The runner starts HumanPlay modes through the real mode controller, waits for the step counter to grow, applies `GameSpeedController.RequestPause(External)`, verifies that the step counter stops for 2 real-time seconds, verifies that `StepOnce()` advances exactly one step, verifies that the counter stays stopped after Step, then releases pause and verifies that simulation resumes.

Runtime validation result:

```text
Mode=AIvsPlayer After 2.0s step=35 PASS stopped
Mode=AIvsPlayer StepOnce returned=True step 35 -> 36 PASS single step
Mode=AIvsPlayer After Step wait 2.0s step=36 PASS still paused
Mode=AIvsPlayer After resume step=42 PASS resumed

Mode=AIvsBot After 2.0s step=25 PASS stopped
Mode=AIvsBot StepOnce returned=True step 25 -> 26 PASS single step
Mode=AIvsBot After Step wait 2.0s step=26 PASS still paused
Mode=AIvsBot After resume step=32 PASS resumed

Mode=AIvsAI After 2.0s step=22 PASS stopped
Mode=AIvsAI StepOnce returned=True step 22 -> 23 PASS single step
Mode=AIvsAI After Step wait 2.0s step=23 PASS still paused
Mode=AIvsAI After resume step=29 PASS resumed

RESULT: PASS
```

## Verification

Completed:

- Compared old pause architecture in git history at `d29f340`.
- Searched current code for `KeyCode.Space`, `TogglePause`, `Pause`, `Resume`, `SetAutomaticSteppingPaused`, `StepEpisodeOnce`, `StepMatch`, and `StepMatchWithHeuristics`.
- Identified and fixed direct runtime stepping bypasses in `StudentMlAgent.OnActionReceived()`.
- Fixed the pause-gated `EndEpisode()` / `OnEpisodeBegin()` reset path.
- Added stale singleton/reference invalidation in `EpisodeController.ResolveReferences()`.
- Compiled Unity scripts through Unity MCP refresh.
- Unity Console after compilation: 0 errors.
- Ran dev-only runtime validation for `AIvsPlayer`, `AIvsBot`, and `AIvsAI`.
- Runtime validation report: `RESULT: PASS`.

Manual Game View verification is still useful for physical key/UI input wiring:

- MainMenu -> Start -> AI vs player.
- Press Space and confirm step counter stops.
- Press Space again and confirm step counter resumes.
- Press Escape and confirm Pause Menu opens and step counter stops.
- Press Step and confirm exactly one simulation step.
- Press Continue and confirm simulation resumes if no Hotkey pause is active.
- Conflict check: Space, Escape, Continue should keep simulation paused until Space is pressed again.
