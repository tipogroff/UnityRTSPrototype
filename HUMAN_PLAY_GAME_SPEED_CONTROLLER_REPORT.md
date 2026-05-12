# HUMAN PLAY / DEMO GAME SPEED CONTROLLER REPORT

Date: 2026-05-13
Stage: HumanPlay-1 - Game Speed / Tactical Slowdown Controller

## 1) Loop Analysis (Task 1)

### Runtime step source
- Match logical step is executed in `MatchManager.StepMatch()`.
- Episode orchestration is in `EpisodeController.FixedUpdate()` when `_autoStepInFixedUpdate` and `_episodeRunning` are true.
- `EpisodeController.FixedUpdate()` calls `StepMatchWithHeuristics()`, which delegates to `RlLoopCoordinator.ExecuteFullStep(...)`.
- AI decision source is selected inside `EpisodeController.BuildDecisionSource()` and then applied through the canonical RL loop.

### Where speed comes from
- Runtime stepping is driven by Unity `FixedUpdate` cadence and `Time.fixedDeltaTime`.
- Optional pacing exists via `_decisionTickIntervalSeconds` accumulator in `EpisodeController` using `Time.fixedDeltaTime`.
- This means Play Mode speed perception is affected by:
  - fixed-step gameplay cadence,
  - visual animation progression,
  - decision loop cadence tied to fixed time.

### Existing safe single-step hook
- `EpisodeController.StepEpisodeOnce()` exists and calls the same canonical loop path for exactly one runtime step.
- This enables safe paused single-step without modifying action/observation/mask contracts.

## 2) Implemented Component (Tasks 2, 3, 4, 5)

Added new component:
- `Assets/Scripts/Presentation/GameSpeedController.cs`

Purpose:
- Presentation/human-play speed layer only.
- No changes to gameplay data model contracts and no ML training logic changes.

Implemented public API:
- `SetSpeed(float speed)`
- `Pause()`
- `Resume()`
- `TogglePause()`
- `StepOnce()`
- `ResetSpeed()`

Speed modes:
- `1.0x`
- `0.5x`
- `0.25x`
- `0.1x`
- `0.0x` pause

Hotkeys:
- `Space` -> pause/resume
- `1` -> 1.0x
- `2` -> 0.5x
- `3` -> 0.25x
- `4` -> 0.1x
- `N` -> single step while paused

Overlay:
- `OnGUI` debug overlay added:
  - current speed,
  - paused state,
  - controls help,
  - mode gate state.

## 3) Time.timeScale Safety (Task 3)

Implementation details:
- Captures baseline values on Awake:
  - `_baseTimeScale`
  - `_baseFixedDeltaTime`
- On speed set:
  - `Time.timeScale = speed`
  - `Time.fixedDeltaTime = _baseFixedDeltaTime * speed` (speed clamped to `>= 0.01`)
- On pause:
  - `Time.timeScale = 0`
  - `Time.fixedDeltaTime = _baseFixedDeltaTime * 0.01`
- On disable/destroy:
  - `Time.timeScale = 1`
  - `Time.fixedDeltaTime = _baseFixedDeltaTime`

Result:
- Prevents leaving Play Mode with stale timescale settings.

## 4) Step Mode Status (Task 4)

Step mode is implemented.
- `StepOnce()` is allowed only when paused.
- Uses existing safe hook `EpisodeController.StepEpisodeOnce()`.
- No direct MatchManager internals patching or core-loop rewiring required.

## 5) Week7 Scene Integration (Task 6)

Scene updated:
- `Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity`

Added GameObject:
- `PresentationControls`
  - component: `RTS.Presentation.GameSpeedController`

Mode guard for training safety:
- `_enableOnlyInManualPlayMode = true` by default.
- Controller auto-disables in `Stage7BRuntimeMode.TrainerControlled`.

## 6) Contract/Training Safety Summary

Confirmed unchanged:
- Observation/action contract
- `ActionDecoder`
- `ActionApplier`
- `ActionMaskBuilder`
- `ObservationBuilder`
- ML-Agents training code
- Python BC/PPO/training scripts
- checkpoint paths
- inference bridge
- reward/terminal semantics
- UnitFactory spawn semantics
- GridManager occupancy logic
- UnitRegistry semantics
- GameConfig_MVP training/evaluation assumptions
- existing visual animation binding

## 7) Validation Results (Task 7)

Executed validations:
- New C# script compiles (no syntax errors from editor diagnostics).
- Component successfully added to Week7 scene and scene saved.
- Unity console check after integration: no new error/warning entries.

Manual Play Mode checks expected from this implementation:
- 1x / 0.5x / 0.25x / 0.1x switching via hotkeys.
- Pause/resume via `Space`.
- Single-step via `N` while paused.
- Timescale reset on disable/destroy and Play Mode exit.

## 8) Changed Files (Task 8)

- `Assets/Scripts/Presentation/GameSpeedController.cs`
- `Assets/Scripts/Presentation/GameSpeedController.cs.meta`
- `Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity`
- `HUMAN_PLAY_GAME_SPEED_CONTROLLER_REPORT.md`

## Hotkey Repair Notes

- The backend-detection pass now distinguishes `NewInputOnly`, `LegacyOnly`, `Both`, and `Unknown` at runtime/editor time.
- In `NewInputOnly`, legacy polling is skipped entirely and the controller uses `Keyboard.current` only.

## Confirmed Working Controls


## Backend Notes

- Project setting `activeInputHandler: 1` indicates `NewInputOnly` for this workspace.
- Overlay diagnostics now show `Keyboard.current`, last hotkey, last input source, and whether legacy/new polling is enabled.
