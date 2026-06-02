# HumanPlay-3G.1R Move Order Repair Report

## Status

`partial_pass`

The runtime MoveOrder pipeline is repaired and validated in Play Mode for adjacent,
far, and cancel cases. Physical pointer-driven RMB/LMB interaction in the Unity Game
View still requires a human validation pass because the available MCP transport does
not inject Game View mouse input.

## Root Cause

Two sequencing defects prevented reliable manual MoveOrder execution.

### Break 1: no initial low-level command

Before repair, `HumanOrderController.IssueMove()` created a `MoveOrder` but did not
submit its first low-level Move. Submission happened only from
`MatchManager.OnStepCompleted`. A newly issued manual order therefore waited for a
future match step before it queued any Move command.

### Break 2: continuation command cleared by the same step

The first repair attempt exposed a second break. `MatchManager.StepMatch()` invoked
`OnStepCompleted` before:

```text
_pendingCommands.Clear();
ClearPhaseCommandBuffers();
```

`MoveOrder` queued its next Move from the `OnStepCompleted` callback. When callback
execution returned, the same `StepMatch()` cleared that newly queued command. Adjacent
Move could succeed from the immediate prime, but multi-step Move stalled after its
first waypoint.

## Fix

`HumanOrderController.IssueMove()` now immediately calls `MoveOrder.TryPrime()`.
Prime performs pathfinding and queues the first adjacent Move through the existing
runtime pipeline.

`MatchManager` now exposes `OnStepCleanupCompleted`, invoked after its normal command
buffer cleanup. `HumanOrderController` subscribes to that event for continuation
ticks. The gameplay phase order and validation semantics are unchanged.

The context menu Move handler now invokes its captured action before closing the menu.

## Before and After

Before:

```text
IssueMove
-> create MoveOrder
-> wait for OnStepCompleted
-> queue first/next Move during callback
-> StepMatch clears pending commands after callback
-> visible movement absent or stalls
```

After:

```text
IssueMove
-> MoveOrder.TryPrime
-> PlayerCommandController.SubmitMoveForUnit
-> AgentAction Move
-> ActionApplier.ApplyAction
-> MatchManager.ApplyCommand
-> queued first Move
-> next StepMatch executes movement
-> OnStepCleanupCompleted
-> MoveOrder confirms UnitRuntime.GridPos
-> queue one next adjacent Move for the next step
```

## Diagnostics

Demo-safe `[HumanMove3G1R]` logs were added for:

- RMB receipt, pointer-over-UI state, selection count, primary selection, world hit,
  resolved grid cell, occupancy, and menu-open rejection reasons;
- context menu opening and Move button click;
- `IssueMove`, prior-order cancellation, order creation, and immediate prime result;
- pathfinding, path length, waypoint, direction, submit result, status, and step result;
- `SubmitMoveForUnit`, actor position, direction, and `ActionApplier` acceptance;
- `MatchManager` queue state, step start, movement result, and final grid position.

Logs are emitted on command/order/step transitions only, not every frame.

## Files Changed

- `Assets/Scripts/Gameplay/Match/MatchManager.cs`
- `Assets/Scripts/Presentation/Orders/HumanOrderController.cs`
- `Assets/Scripts/Presentation/Orders/MoveOrder.cs`
- `Assets/Scripts/Presentation/PlayerCommandController.cs`
- `Assets/Scripts/Presentation/UI/ContextActionMenuView.cs`
- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
- `Assets/Scripts/Editor/Presentation/HumanPlay3G1RMoveValidationMenu.cs`

The editor-only validation helper adds adjacent, far, and cancel probes under:

```text
RTS/HumanPlay/3G1R Validate Adjacent Move
RTS/HumanPlay/3G1R Validate Far Move
RTS/HumanPlay/3G1R Validate Cancel Move
```

## Runtime Validation Evidence

Validation was executed in Play Mode after explicitly calling `StartAIvsPlayer2()`:

```text
mode current=AIvsPlayer2 hasHumanSide=True humanSide=Player2
```

Adjacent Move:

```text
IssueMove accepted=True start=(22, 22) target=(23, 22) step=0
PASS adjacent Move start=(22, 22) target=(23, 22) final=(23, 22) steps=1
```

Far Move:

```text
IssueMove accepted=True start=(23, 22) target=(23, 18) step=0
step=1 current=(23, 21)
step=2 current=(23, 20)
step=3 current=(23, 19)
step=4 current=(23, 18)
PASS far Move start=(23, 22) target=(23, 18) final=(23, 18) steps=4
```

Cancel:

```text
cancel requested at step=1 grid=(22, 21)
step=2 current=(22, 21) status=Cancelled
step=3 current=(22, 21) status=Cancelled
step=4 current=(22, 21) status=Cancelled
PASS cancel grid remained=(22, 21) throughStep=4
```

## Command Routing Proof

Static scan confirms presentation/order code does not call:

- `transform.position` for movement;
- `UnitRuntime.MoveTo`;
- `GridManager.MoveUnit`;
- `MatchManager.StepMatch`.

The repaired path remains:

```text
HumanOrderController
-> MoveOrder
-> PlayerCommandController.SubmitMoveForUnit
-> AgentAction
-> ActionApplier.ApplyAction
-> MatchManager.ApplyCommand
-> normal MatchManager movement phase
```

## Manual Game View Check Still Required

Run this final pointer UX check in Unity:

1. Open MainMenu and start Demo.
2. Confirm `AIvsPlayer2`.
3. LMB-select a Player2 Worker.
4. RMB an adjacent free cell and verify the Move menu opens.
5. Click Move and verify one-cell movement.
6. RMB a far free cell, click Move, and verify step-by-step movement.
7. Press Stop and verify movement stops.
8. Confirm pause, camera controls, Player1 AI, and Player2 manual control.

The added `[HumanMove3G1R]` logs expose the exact failure stage if pointer UX still
fails.

## Constraints Confirmation

- No Python, training, checkpoint, or model-path changes retained.
- No observation/action contract changes.
- No `ActionDecoder` changes.
- No `ActionApplier` changes.
- No Week7 baseline scene changes.
- No fake movement or teleporting.
- No direct movement from UI/order logic.
- No auto-harvest, production, or Barracks behavior added.
- Player1 AI and Player2 bot-control configuration semantics remain unchanged.
