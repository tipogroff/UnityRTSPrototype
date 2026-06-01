# HumanPlay-3G.2R Worker Auto-Harvest Repair Report

Status: `partial_pass`. The repair compiles and passes static constraints. Final Game View acceptance is intentionally left for manual verification.

## Root Cause

The observed stop is primarily resource exhaustion, not a global gather lock:

- Each `ResourceNode` has finite `CurrentResources`.
- `HarvestLoopOrder` correctly drains the selected source and stops after returning final cargo.
- `ResourceManager.GetResourceNode()` intentionally continues returning exhausted nodes.
- Before this repair, RMB on an exhausted node still opened the Gather flow and `IssueHarvestLoop()` returned a generic unavailable-or-exhausted message.
- After both visible sources were depleted, both remained clickable but neither could start Gather. This appeared to be a lifecycle failure.

There was also a lifecycle gap when starting a new Gather while the Worker already carried resources: the order initially moved toward the selected resource. It now deposits existing cargo first.

Static inspection found no stale active order lock. Terminal orders are removed from `_activeOrders`, and issuing a new Gather cancels an active prior order and removes visible terminal state before creating the replacement.

## Files Changed

- `Assets/Scripts/Presentation/Orders/HarvestLoopOrder.cs`
- `Assets/Scripts/Presentation/Orders/HumanOrderController.cs`
- `Assets/Scripts/Presentation/PlayerCommandController.cs`
- `Assets/Scripts/Presentation/UI/ContextActionMenuView.cs`
- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`

The uncommitted 3G.2 files remain part of the same working tree.

## Lifecycle Changes

Before:

- Exhausted resources could still enter RMB Gather UX.
- Exhausted-resource rejection was generic.
- A new Gather with carried cargo began toward the clicked resource.
- Return confirmation checked carry reset but did not explicitly confirm Player2 resource increase.

After:

- RMB exhausted resource immediately reports `Resource is exhausted.`
- `IssueHarvestLoop()` independently rejects exhausted nodes with the same clear reason.
- Starting Gather with cargo transitions to Base first, deposits, then proceeds to the clicked active resource.
- Return cleanup confirms both `CarriedResources == 0` and Player2 resources increased.
- Existing capacity checks remain in place before Harvest submission and after Harvest cleanup.
- New Gather cancels an active prior order, removes stale visible terminal state, and uses the currently clicked `ResourceNode`.
- Context menu pending callbacks and captured resource are cleared on hide and before every reopen.

## Diagnostics

Demo-safe lifecycle logging now uses `[HumanHarvest3G2R]` and records:

- Gather issue, replacement, acceptance, and rejection.
- State transitions with Worker grid, carry, resource remaining, Base grid, and reason.
- Path target, selected adjacent cell, waypoint, and Move cleanup.
- Harvest submission and cleanup deltas.
- Return submission and cleanup deltas including Player2 resources.
- Exact Completed, Failed, and Cancelled terminal reasons.

## Routing Proof

No gameplay mutation was added to presentation/order code. Low-level actions still route:

`HarvestLoopOrder -> PlayerCommandController SubmitMove/SubmitHarvest/SubmitReturn -> AgentAction -> ActionApplier.ApplyAction -> MatchManager normal step execution`

The order treats acceptance as queued and confirms effects after `OnStepCleanupCompleted`.

## Validation

- Unity script compilation: `0` C# errors.
- `git diff --check`: no whitespace errors.
- Static bypass audit: no direct movement, resource, carry, or `PlayerState` mutation added.
- `ActionDecoder`, `ActionApplier`, action contract, Week7 baseline scene, and Python/training code were not changed by this repair.
- Play Mode was not run for this repair, per manual-validation workflow.

## Manual Game View Checklist

1. Start `AI vs P2`.
2. Select the Player2 Worker and Gather Resource1 until it exhausts.
3. Confirm final cargo is deposited and HUD reports completion due to resource exhaustion.
4. RMB exhausted Resource1 and confirm `Resource is exhausted.`
5. Gather active Resource2 and confirm the loop starts normally.
6. While carrying cargo, click Gather on another active resource and confirm the Worker deposits first.
7. Start Gather again while another order is active and confirm replacement uses the newly clicked source.
8. Click Stop and confirm future low-level gather submissions stop.
9. Confirm RMB empty-cell Move still works for adjacent, far, and cancelled movement.
10. Inspect `[HumanHarvest3G2R]` logs if any unexpected stop remains.

## Known Limitations

- Resource nodes remain visible after exhaustion by existing runtime design.
- Group gather orders remain intentionally unsupported.
- Cardinal BFS uses bounded replans and does not reserve cells.
- Existing generated trace/Python report modifications from prior manual runs were preserved and not edited.

