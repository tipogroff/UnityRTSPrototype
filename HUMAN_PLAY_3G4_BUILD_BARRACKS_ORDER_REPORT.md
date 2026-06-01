# HumanPlay-3G.4 Build Barracks Context Order Report

## Result

Status: `partial_pass`. Implementation, static audits, and Unity compilation passed. Manual Game View validation remains for the user.

## Previous Limitation

Runtime already supported Worker construction through `Produce`, but the human side had no target-aware high-level order. The old button could not carry a selected build cell, move the Worker near a distant site, or confirm construction after the runtime step.

## Runtime Audit

- Worker -> Build Barracks uses raw v2 produce payload index `2`.
- `ActionApplier.ValidateWorkerBuildBarracks()` requires index `2`, an orthogonally adjacent target derived from `Direction`, a configured Barracks definition, enough resources, and no existing living Barracks.
- `MatchManager.TryWorkerBuildBarracks()` spends resources and spawns the Barracks through the normal runtime `UnitFactory` path.
- `GameConfig_MVP.asset` references `UnitDef_Barracks.asset`.
- `UnitDef_Barracks.asset` exposes cost `2` and production/build timing `8`.

## Files Changed

- `Assets/Scripts/Presentation/Orders/BuildBarracksOrder.cs`
- `Assets/Scripts/Presentation/Orders/BuildBarracksOrder.cs.meta`
- `Assets/Scripts/Presentation/Orders/GridPathfindingService.cs`
- `Assets/Scripts/Presentation/Orders/HumanOrderController.cs`
- `Assets/Scripts/Presentation/Orders/HumanOrderStatus.cs`
- `Assets/Scripts/Presentation/Orders/ProductionCommandHelper.cs`
- `Assets/Scripts/Presentation/PlayerCommandController.cs`
- `Assets/Scripts/Presentation/UI/ContextActionMenuView.cs`
- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
- `HUMAN_PLAY_3G4_BUILD_BARRACKS_ORDER_REPORT.md`
- `human_play_3g4_build_barracks_order_validation.json`

## Build Payload Mapping

`ProductionCommandHelper.TryCreateBuildBarracksAction()` creates:

- `ActorPosition = worker.GridPos`
- `ActionType = UnitActionType.Produce`
- `Direction = direction from Worker toward selected build cell`
- `ProduceUnitType = (ProducibleUnit)2`

## Order Lifecycle

1. `HumanOrderController.IssueBuildBarracks()` validates services and planning.
2. `GridPathfindingService.TryFindBuildApproachPath()` validates the free build cell and finds a reachable cardinal-adjacent Worker cell.
3. `BuildBarracksOrder` submits one existing low-level Move action per cleanup tick while approaching the site.
4. Once adjacent, it submits the low-level Produce action with raw index `2`.
5. On the next cleanup callback, it confirms an owned living Barracks at the requested build cell.
6. The HUD receives statuses such as `Order: moving to build site.`, `Order: building Barracks.`, completion, cancellation, or a readable failure.

## Context Menu

- RMB on a free cell with a selected Player2 Worker shows `Move` and `Build Barracks`.
- RMB on a free cell with a combat unit shows `Move` only.
- Occupied cells do not open the free-cell Move/Build menu.
- Every menu reopen clears captured callbacks and target data before assigning the current clicked cell.

## Command Routing Proof

`ContextActionMenuView -> HumanPlayCanvasController -> HumanOrderController.IssueBuildBarracks -> BuildBarracksOrder -> PlayerCommandController.SubmitBuildBarracksForWorker -> ProductionCommandHelper -> AgentAction -> ActionApplier.ApplyAction(..., Owner.Player2) -> MatchManager.ApplyCommand -> MatchManager.TryWorkerBuildBarracks -> runtime UnitFactory.Spawn`

Presentation code does not instantiate Barracks, mutate resources, call `UnitRuntime.MoveTo`, call `GridManager.MoveUnit`, or write `transform.position`.

## Validation Performed

- Unity compilation: `0` C# errors.
- Unity script validation: no errors in changed scripts.
- `git diff --check`: no whitespace errors.
- Static scans confirmed raw payload index `2` and no prohibited presentation-layer bypass.
- No `ActionDecoder`, `ActionApplier`, Week7 baseline, Python, training, or checkpoint files were changed by this task.
- Existing Move, HarvestLoopOrder, and Base/Barracks production implementations were not rewritten.

## Known Limitations

- Cells are not reserved while the Worker approaches the build site. If the cell becomes occupied later, runtime validation rejects the build with a readable reason.
- Cancel stops the high-level order before build submission. Once the low-level runtime command has already been queued, the existing runtime has no command withdrawal API.
- Runtime intentionally permits only one living Barracks per owner.

## Manual Checklist

1. Start the game from MainMenu and start Demo.
2. Confirm AI vs Player2 mode.
3. Select a Player2 Worker and RMB an adjacent free cell.
4. Confirm `Move` and `Build Barracks` are shown.
5. Click `Build Barracks`; confirm runtime resource spending and Barracks spawn on the selected cell.
6. Start a fresh match, select a Worker, RMB a far free cell, and click `Build Barracks`.
7. Confirm the Worker walks near the site and builds.
8. Test occupied-cell rejection and insufficient-resources rejection.
9. Confirm an existing living Barracks produces a clear rejection.
10. Confirm Stop cancels an approaching build order.
11. Confirm RMB Move, Gather loop, Base -> Worker, Barracks -> Light/Heavy/Ranged, pause menu, and camera still work.

