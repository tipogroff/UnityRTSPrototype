# HumanPlay-2 PART 3 HUD Report

Date: 2026-05-13
Scope: playable/demo HUD (OnGUI-based) for HumanPlay-2.

## Changed files

- `Assets/Scripts/Presentation/HumanPlayHudController.cs`
- `HUMAN_PLAY_2_PART3_HUD_REPORT.md`

## HUD data sources

`HumanPlayHudController` reads from:

- `HumanPlayModeController`
- `HumanPlayerController`
- `PlayerSelectionController`
- `PlayerCommandController`
- `GameSpeedController`
- `EpisodeController`
- `MatchManager`
- `UnitRegistry`
- `ResourceManager`
- `MlAgentsTrainingBootstrap`

Reference strategy:

- Serialized fields are supported.
- Missing references are auto-resolved periodically in `Update` (not in `OnGUI`).

## Displayed fields

### Demo/mode block

- Current `HumanPlayMode`
- `HasHumanSide`
- Human side owner
- Human control active flag
- TrainerControlled runtime flag
- Last mode diagnostics from `HumanPlayModeController`

### Match block

- Match phase
- Match step
- Episode index (if available)
- Winner (runtime/terminal)
- Terminal reason (runtime + episode terminal report when available)

### Resources block

- Player1 resources
- Player2 resources
- Optional alive unit counts per side (from `UnitRegistry`)

### Selected unit block

- Selection state
- Owner
- Unit type
- HP current/max
- Carried resources
- Grid position
- Alive flag

### Command block

- Current `HumanCommandMode`
- Last command status
- Accepted/rejected flag
- Rejection reason

### Speed block

- Current speed
- Pause state

## HUD button list

Mode/menu buttons:

- Start Player1 vs AI -> `HumanPlayModeController.StartPlayer1VsAI()`
- Start AI vs Player2 -> `HumanPlayModeController.StartAIvsPlayer2()`
- Start AI vs AI -> `HumanPlayModeController.StartAIvsAI()`
- Restart -> `HumanPlayModeController.RestartMatch()`
- Return to Menu -> `HumanPlayModeController.ReturnToMenu()`
- Quit -> `HumanPlayModeController.QuitApplication()`

Manual command buttons:

- Move -> `PlayerCommandController.BeginMoveCommandMode()`
- Attack -> `PlayerCommandController.BeginAttackCommandMode()`
- Harvest -> `PlayerCommandController.TryHarvestSelected()`
- Return -> `PlayerCommandController.TryReturnSelected()`
- Produce Worker -> `PlayerCommandController.TryProduceWorker()`
- Build Barracks -> `PlayerCommandController.TryBuildBarracks()`
- Produce Light -> `PlayerCommandController.TryProduceLight()`
- Produce Heavy -> `PlayerCommandController.TryProduceHeavy()`
- Produce Ranged -> `PlayerCommandController.TryProduceRanged()`

Speed buttons:

- Pause/Resume -> `GameSpeedController.TogglePause()`
- Step -> `GameSpeedController.StepOnce()`
- 1x / 0.5x / 0.25x / 0.1x -> `GameSpeedController.SetSpeed(...)`

## Availability and safety rules

Manual command buttons are disabled when:

- `PlayerCommandController` missing,
- `HumanPlayerController` missing,
- runtime is TrainerControlled,
- human control inactive,
- match phase is not Running,
- no selected unit.

Missing-reference behavior:

- No exceptions are thrown intentionally from HUD control path.
- HUD shows readable status (`Controller missing`, `Match not running`, etc.).

## Missing/unavailable fields handling

If values are unavailable through public runtime APIs, HUD shows `n/a`.
No new public API was added to core runtime for HUD-only values.

## Known limitations

- Current HUD uses `OnGUI` for rapid integration and reliability (not Canvas UI polish).
- Two fixed HUD panels are used; final scene composition/polish deferred to PART 4.
- Unit counts are refreshed on interval, not event-driven.

## Validation checklist

1. Open Week7 scene (or temporary scene with HumanPlay controllers).
2. Add `HumanPlayHudController` to a HUD/Presentation object.
3. Press Play and confirm HUD appears.
4. Start Player1 vs AI from HUD.
5. Confirm HUD mode and human side update.
6. Select friendly unit and verify selected-unit block.
7. Click Move, then right click adjacent cell.
8. Confirm command status and accepted/rejected state updates.
9. Attempt invalid non-adjacent move and verify rejection message.
10. Try Harvest/Return when scenario supports them.
11. Restart from HUD.
12. Validate Pause/Resume and speed buttons when `GameSpeedController` is present.
13. Confirm TrainerControlled mode displays human-play disabled state.
14. Confirm no direct gameplay mutation from HUD code path.

## Constraint confirmation

- No Python/training/checkpoint files were modified.
- No observation/action contract files were modified.
- No ActionDecoder/ActionApplier semantics were modified.
- No runtime gameplay rules were changed.
