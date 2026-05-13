# HumanPlay-2 PART 2 Player Control Report

Date: 2026-05-13
Scope: PART 2.1-2.5 (manual player control layer)

## Changed files

- `Assets/Scripts/Presentation/PlayerSelectionController.cs`
- `Assets/Scripts/Presentation/PlayerCommandController.cs`
- `Assets/Scripts/Presentation/HumanPlayerController.cs`

No Python/training/checkpoint files were changed.
No observation/action contract files were changed.
No ActionDecoder/ActionApplier semantic code was changed.

## Command path proof

Manual command path implemented as:

1. Human input (right click / UI command mode) in `PlayerCommandController`.
2. Command translation to `AgentAction` (Move/Harvest/Return/Produce/Attack).
3. Submission through `ActionApplier.ApplyAction(action, humanSide)`.
4. `ActionApplier` performs authoritative runtime validation and submits `MatchCommand` to `MatchManager.ApplyCommand`.
5. Existing runtime step loop (`EpisodeController` / `MatchManager.StepMatch`) executes queued commands.

Important safety guarantees:

- No direct gameplay mutation through `UnitRuntime.MoveTo`, `transform.position`, or `GridManager.MoveUnit` from presentation input.
- `PlayerCommandController` does not call `MatchManager.StepMatch()`.

## Input backend

Selected backend:

- Primary: New Input System (`UnityEngine.InputSystem.Mouse.current`).
- Optional fallback: legacy input calls are guarded with `ENABLE_LEGACY_INPUT_MANAGER` and runtime `InvalidOperationException` safety flag.

UI click handling:

- Pointer-over-UI guard via `EventSystem.current.IsPointerOverGameObject()` before processing clicks.

## Implemented controls

### Selection

`PlayerSelectionController`:

- Left click selects only friendly `UnitRuntime` owned by current human side.
- Enemy and neutral objects are not selectable.
- Selection clears when:
  - selected object destroyed,
  - selected unit dead,
  - selected unit ownership no longer matches human side,
  - manual input disabled.
- Exposed API:
  - `SelectedUnit`, `HasSelection`
  - `OnSelectionChanged`
  - `Select(UnitRuntime)`
  - `ClearSelection()`
- Selection marker:
  - presentation-only generated primitive marker,
  - collider disabled,
  - hidden when no selection,
  - follows selected unit position.

### Commands

`PlayerCommandController` supports:

Required commands:

1. Move to adjacent empty cell (`UnitActionType.Move`).
2. Harvest adjacent resource with Worker (`UnitActionType.Harvest`).
3. Return carried resources to adjacent friendly Base (`UnitActionType.Return`).
4. Attack clicked enemy target (`UnitActionType.Attack`).

Optional preferred commands (implemented):

5. Produce Worker from Base (`UnitActionType.Produce`, `ProducibleUnit.Worker`).
6. Build Barracks from Worker through existing runtime produce mapping (`UnitActionType.Produce`, worker produce slot).
7. Produce Light/Heavy/Ranged from Barracks.

Right-click contextual behavior:

- Enemy target -> Attack.
- Resource target with selected Worker -> Harvest.
- Friendly Base target with carrying Worker -> Return.
- Empty adjacent cell -> Move.
- Non-adjacent/invalid target -> rejected with readable status, including:
  - "Target is not adjacent; command not submitted."

Direction semantics:

- North = +Y, East = +X, South = -Y, West = -X.
- Only orthogonal adjacent cells are accepted for direction-based commands.

Command mode API for HUD buttons:

- `TryMoveToClickedCell()` / `BeginMoveCommandMode()`
- `TryHarvestSelected()`
- `TryReturnSelected()`
- `TryAttackClickedTarget()` / `BeginAttackCommandMode()`
- `TryProduceWorker()`
- `TryBuildBarracks()`
- `TryProduceLight()`
- `TryProduceHeavy()`
- `TryProduceRanged()`

### Human control orchestration

`HumanPlayerController`:

- Subscribes to `HumanPlayModeController.OnModeStateChanged`.
- Tracks current human side.
- Enables selection/command input only when all conditions are true:
  - `HumanPlayModeController.HasHumanSide == true`,
  - runtime is not `TrainerControlled`,
  - match phase is `Running`.
- Disables manual input in AIvsAI / paused / trainer-controlled runtime.
- If `HumanPlayModeController` is missing:
  - no crash,
  - warning logged,
  - manual input remains disabled.

Exposed properties:

- `IsHumanControlActive`
- `HumanSide`
- `SelectedUnit`
- `LastCommandStatus`
- `LastCommandAccepted`
- `LastCommandRejectedReason`

## Known limitations

- Targeting relies on colliders + ground-plane/grid fallback; no advanced selection box or drag-select.
- Context command mode is single-click intent resolution; no full UX polish for mode cancellation prompts.
- Produce direction currently auto-selects first adjacent free cardinal cell.
- Detailed command timing/queue contention diagnostics versus AI submissions are not yet visualized in HUD (runtime queue path remains correct).

## Manual Play Mode checklist

1. Open `Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity` or a temporary scene with required runtime objects.
2. Add components:
   - `HumanPlayModeController`
   - `HumanPlayerController`
   - `PlayerSelectionController`
   - `PlayerCommandController`
3. Enter Play Mode.
4. Start Player1 vs AI via `HumanPlayModeController.StartPlayer1VsAI()`.
5. Left click friendly unit/building to select.
6. Right click adjacent empty cell -> Move command submitted.
7. Right click adjacent resource with Worker -> Harvest submitted or clear rejection reason.
8. Right click adjacent friendly Base with carrying Worker -> Return submitted or clear rejection reason.
9. Right click enemy unit target -> Attack submitted or clear rejection reason.
10. Verify enemy/neutral units are not selectable.
11. Verify AI side still submits automated decisions.
12. Verify no New Input System legacy warning spam appears.

## Acceptance summary for PART 2

- GO condition status (implementation-level):
  - Human selection/control layer implemented.
  - Command submission path uses ActionApplier -> MatchManager.
  - Move implemented through runtime validation path.
  - Harvest/Return implemented with runtime validation and readable rejection.
  - Attack implemented with runtime validation and readable rejection.
  - Produce commands implemented (optional preferred).
  - No direct transform/grid/unit mutation from presentation input.

Final runtime behavior must still be validated in Unity Play Mode using the checklist above.
