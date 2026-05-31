# HumanPlay-3G.1 Human Move Order Report

## Result

Implemented presentation-side high-level Move orders for Player2. A distant move is
planned with cardinal BFS and executed as one queued adjacent runtime Move command
after each `MatchManager.OnStepCompleted`.

No gameplay rules, ML contracts, Python, checkpoints, or Week7 baseline scene were
changed.

## Files Changed

Created:

- `Assets/Scripts/Presentation/Orders/GridPathfindingService.cs`
- `Assets/Scripts/Presentation/Orders/HumanOrderStatus.cs`
- `Assets/Scripts/Presentation/Orders/HumanUnitOrder.cs`
- `Assets/Scripts/Presentation/Orders/MoveOrder.cs`
- `Assets/Scripts/Presentation/Orders/HumanOrderController.cs`
- `Assets/Scripts/Presentation/UI/ContextActionMenuView.cs`
- generated Unity `.meta` files for the new scripts and folder
- `HUMAN_PLAY_3G1_HUMAN_MOVE_ORDER_REPORT.md`
- `human_play_3g1_human_move_order_validation.json`

Updated:

- `Assets/Scripts/Presentation/PlayerCommandController.cs`
- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
- `Assets/Scripts/Presentation/UI/CommandPanelView.cs`

Intentionally unchanged:

- `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`
- `Assets/Prefabs/UI/HumanPlayCanvas.prefab`
- `Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity`
- `Assets/Scripts/ML/ActionDecoder.cs`
- `Assets/Scripts/ML/ActionApplier.cs`
- Python, training, model, and checkpoint files

## Pathfinding

`GridPathfindingService` performs BFS over four-directional neighbors only.

- Bounds use `GridManager.IsInside`.
- Occupancy uses `GridManager.GetOccupant`.
- The moving unit may occupy its start cell.
- A Move target must be inside the map and free.
- Returned waypoints exclude the start cell and include the target.
- Occupied, outside-map, and unreachable targets return readable reasons.
- The service never mutates runtime state.

## Order Design

`HumanOrderController` owns at most one active `HumanUnitOrder` per `UnitRuntime`.
Issuing a new order cancels the previous order for that unit. Terminal status remains
available for HUD display after the active entry is removed.

`MoveOrder` lifecycle:

1. Starts as `Pending`.
2. On `MatchManager.OnStepCompleted`, validates match, ownership, unit lifetime, and
   current position.
3. Builds or rebuilds a BFS path.
4. Submits one adjacent Move step.
5. Marks itself `WaitingForStep`.
6. On the next completed match step, confirms movement by reading `UnitRuntime.GridPos`.
7. Completes at the target or fails with a readable reason.

Blocked paths are replanned with a bounded retry count. Cancel prevents future
submissions and does not attempt to undo an already queued runtime command.

## Command Routing Proof

High-level order code does not call `transform.position`, `UnitRuntime.MoveTo`,
`GridManager.MoveUnit`, or `MatchManager.StepMatch`.

The Move route is:

`MoveOrder.TickAfterStep()`
-> `PlayerCommandController.SubmitMoveForUnit()`
-> `AgentAction(ActionType=Move, Direction=cardinal)`
-> `ActionApplier.ApplyAction()`
-> `MatchManager.ApplyCommand()`
-> queued runtime command
-> normal next-step gameplay execution.

Acceptance is treated as queued, not completed. Completion is confirmed only after a
later `OnStepCompleted` callback.

## Context Menu and HUD

`HumanPlayCanvasController` creates presentation components at runtime because the
existing HUD is already runtime-built:

- `GridPathfindingService`
- `HumanOrderController`
- inactive `ContextActionMenuView`

RMB on empty ground with one selected mobile Player2 unit opens a small `Move` context
menu near the pointer. Clicking `Move` issues the high-level order. Clicking outside
or pressing `Esc` closes the menu. `Esc` opens pause only when the context menu is not
open.

The command panel displays order status and includes a `Stop` button. `Stop` cancels
future steps for the selected unit.

Occupied targets do not start a fake Move. Existing enemy/resource contextual behavior
remains in place. Multi-selection remains rejected with a readable formation message.

## Validation

Automated checks completed:

- Unity scripts compile with zero C# errors after full asset refresh.
- Play Mode starts and stops successfully in `HumanPlay_Demo_PlayerVsAI`.
- Runtime-created `HumanOrderController` exists in Play Mode.
- Runtime-created `GridPathfindingService` exists in Play Mode.
- Inactive runtime-created `ContextActionMenuView` exists in Play Mode.
- Static search confirms no direct `MoveTo`, `MoveUnit`, or `StepMatch` call in the
  order/UI implementation.
- Static git check confirms Week7 baseline, `ActionDecoder`, and `ActionApplier` are
  unchanged.
- Play Mode generated trace files were reverted after validation.

Observed during Play Mode stop:

- Unity logged a `MissingReferenceException` from existing
  `SelectionBoxView.cs:64` after the runtime HUD was destroyed. A clean compile-only
  refresh afterward reported zero errors. The selection-box lifecycle issue was not
  modified in 3G.1 and remains a separate follow-up.

Manual in-editor validation remains required for pointer-driven UX:

- LMB-select a Player2 Worker.
- RMB a distant free cell and verify the `Move` menu.
- Click `Move` and watch adjacent step progression.
- Press `Stop` during movement.
- Verify pause and camera behavior interactively.
- Verify Player1 AI continues and Player2 receives no automatic bot commands.

## Known Limitations

- Only MoveOrder is implemented. Auto-harvest, Return orchestration, production fixes,
  and Barracks construction UX are deferred.
- Movement is single-unit only. Group formations and cell reservations are deferred.
- Replanning is bounded and intentionally simple.
- Existing occupied-target contextual commands remain low-level and may reject distant
  Harvest/Attack attempts according to runtime validation.

## Constraints Confirmation

- No teleporting or fake movement.
- No direct runtime movement from UI/order code.
- No gameplay semantic changes.
- No observation/action contract changes.
- No `ActionDecoder` or `ActionApplier` semantic changes.
- No Python/training/checkpoint changes retained.
- No Week7 baseline scene changes.
- Player2 bot policy wiring was not modified.
- Player1 AI wiring was not modified.
