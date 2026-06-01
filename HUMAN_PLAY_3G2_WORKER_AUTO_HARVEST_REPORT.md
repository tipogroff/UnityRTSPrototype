# HumanPlay-3G.2 Worker Auto-Harvest Report

Status: `partial_pass`. Implementation is complete and compiles. Final Game View acceptance is intentionally left for manual verification.

## Files Changed

- `Assets/Scripts/Presentation/Orders/GridPathfindingService.cs`
- `Assets/Scripts/Presentation/Orders/HarvestLoopOrder.cs`
- `Assets/Scripts/Presentation/Orders/HumanOrderStatus.cs`
- `Assets/Scripts/Presentation/Orders/HumanOrderController.cs`
- `Assets/Scripts/Presentation/PlayerCommandController.cs`
- `Assets/Scripts/Presentation/UI/ContextActionMenuView.cs`
- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`

No production, Barracks, group-order, Python/training, action-contract, `ActionDecoder`, `ActionApplier`, or Week7 baseline changes were made.

## Lifecycle

`HarvestLoopOrder` validates a living Player2 Worker, active resource, running match, and required services. It then cycles:

1. Find a free cardinal-adjacent interaction cell and queue one Move per cleanup tick.
2. When adjacent to the resource, queue Harvest and confirm carry increased after the next cleanup.
3. At carry capacity or resource exhaustion, find the nearest living Player2 Base.
4. Move to a free cardinal-adjacent Base cell one step at a time.
5. Queue Return and confirm carry becomes zero after cleanup.
6. Return to the resource while it remains active.

The order stops on cancel, dead Worker, exhausted resource after cargo return, missing Base, blocked path, stopped match, or repeated low-level failure.

## Routing Proof

The high-level order only submits low-level actions:

`HumanOrderController -> HarvestLoopOrder -> PlayerCommandController helper -> AgentAction -> ActionApplier.ApplyAction -> MatchManager normal step execution`

`SubmitHarvestForUnit` and `SubmitReturnForUnit` construct `AgentAction` from the Worker's current grid position and required direction. They do not call `StepMatch` and do not mutate movement, resources, carry, or `PlayerState`.

Continuation uses `MatchManager.OnStepCleanupCompleted`, so accepted actions are treated as queued and their effects are confirmed after cleanup.

## UI Integration

With a single Player2 Worker selected, RMB on a `ResourceNode` raises a Gather context request. The context menu shows `Gather`; clicking it calls `IssueHarvestLoop` and closes the menu. RMB on an empty cell continues to show `Move`. Multi-selection gather is rejected with a readable limitation.

The existing Stop button cancels either Move or Gather orders. Existing HUD status rendering receives lifecycle text such as moving to resource, harvesting, moving to base, returning resources, failure, and cancellation.

## Validation

- Unity script compilation: `0` C# errors.
- Static bypass audit: no direct movement, resource amount, carry, or player-resource mutation added in UI/order code.
- Auxiliary runtime probe completed before manual-only validation was requested:
  - far path helper found a cardinal-adjacent path of length `43`;
  - Harvest increased carry from `0` to `5`;
  - Return increased Player2 resources from `60` to `65`;
  - Worker harvested again after Return;
  - Cancel changed status to `Order cancelled.`

Manual Game View acceptance remains required:

1. Start `AI vs P2`.
2. LMB-select a Player2 Worker.
3. RMB a Resource and confirm `Gather` appears near the cursor.
4. Click `Gather`; observe lifecycle HUD text and the Worker cycle.
5. Click `Stop`; confirm no further low-level gather actions are submitted.
6. RMB an empty cell and confirm existing `Move` still works.

## Known Limitations

- Group gather orders are intentionally unsupported.
- Pathfinding is cardinal BFS with bounded replans; it does not reserve cells.
- A teardown `MissingReferenceException` from `SelectionBoxView` was observed when exiting Play Mode. It predates this order flow and was not changed because it is outside 3G.2 semantics.
- Physical pointer/menu interaction has not been manually accepted yet.

