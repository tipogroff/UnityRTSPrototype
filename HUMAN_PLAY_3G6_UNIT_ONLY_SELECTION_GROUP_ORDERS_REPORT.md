# HumanPlay-3G.6 Unit-Only Selection and Group Orders

## Status

`partial_pass`: Unity compile and static validation passed. Game View validation remains manual.

## UX Issue Fixed

- Drag selection now includes only living active Player2 mobile units: Worker, Light, Heavy, and Ranged.
- Base and Barracks remain selectable by single click for production.
- Shift-clicking a building makes it the single selection instead of adding it to a unit group.
- Shift-drag removes any previously selected building before adding eligible mobile units.

## Files Changed

- `Assets/Scripts/Presentation/Selection/SelectionManager.cs`
- `Assets/Scripts/Presentation/Orders/GroupOrderPlanner.cs`
- `Assets/Scripts/Presentation/Orders/GroupOrderReservationService.cs`
- `Assets/Scripts/Presentation/Orders/GridPathfindingService.cs`
- `Assets/Scripts/Presentation/Orders/HumanOrderController.cs`
- `Assets/Scripts/Presentation/Orders/MoveOrder.cs`
- `Assets/Scripts/Presentation/Orders/AttackOrder.cs`
- `Assets/Scripts/Presentation/PlayerCommandController.cs`
- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
- `Assets/Scripts/Presentation/UI/ContextActionMenuView.cs`
- `Assets/Scripts/Presentation/UI/CommandPanelView.cs`
- `Assets/Scripts/Presentation/UI/SelectionInfoPanelView.cs`

## Group Move Planning

`GroupOrderPlanner.TryPlanGroupMove` generates compact ring candidates around the clicked formation center. It filters occupied cells, sorts units deterministically, and greedily assigns unique reachable destinations using shortest path length with stable tie-breakers. `HumanOrderController.IssueGroupMove` creates one normal `MoveOrder` per assigned unit.

## Group Attack Planning

`GroupOrderPlanner.TryPlanGroupAttackApproach` filters living Player2 mobile attackers with runtime attack capability, spreads assignments across acquired enemy targets, and prefers the nearest target on ties. It attempts to assign unique reachable attack-range cells. `AttackOrder` uses the preferred cell while valid and falls back to existing dynamic attack approach replanning if needed.

## Reservation Behavior

`GroupOrderReservationService` holds a presentation-only `GridPosition -> UnitRuntime` map. `HumanOrderController` clears it before each active-order tick and before issuing a group batch. `MoveOrder` and `AttackOrder` reserve their next movement cell before submitting a low-level Move. On conflict, an order waits for the next cleanup tick. Runtime occupancy and validation remain authoritative.

## Context Priority

- Single Worker + Resource: Gather.
- Single carrying Worker + own Base: Return.
- Single Worker + free cell: Move and Build Barracks.
- Multiple selected units + free cell: Move Group.
- Single attacker + enemy area: Attack.
- Multiple selected attackers + enemy area: Attack Area.
- Single Base/Barracks selection: production remains available.

## Command Routing Proof

Group commands are presentation-side fan-out only:

`HumanOrderController -> MoveOrder / AttackOrder -> PlayerCommandController helper -> AgentAction -> ActionApplier.ApplyAction -> MatchManager.ApplyCommand -> runtime execution`

No runtime group command, direct transform move, HP mutation, destruction, direct spawn, resource mutation, or `MatchManager.StepMatch` call was added.

## Validation Performed

- Unity script compile: 0 C# errors.
- `git diff --check`: passed.
- Static scan of changed UI/order/group code: no direct movement, HP, destruction, resource, or step bypass.
- Scoped git status: no changes to `ActionDecoder.cs`, `ActionApplier.cs`, or `Week7_MLAgents_StudentVsScriptedBot.unity`.
- Existing unrelated Python/training and runtime trace modifications were not changed by this task.

## Manual Game View Checklist

1. Start Demo.
2. Drag-select over Player2 Base, Barracks, Worker, and combat units; confirm only mobile units are selected.
3. Single-click Base and Barracks; confirm production works.
4. Drag-select several Player2 units, RMB an empty cell, choose `Move Group`, and confirm distinct nearby destinations.
5. While moving, click Stop and confirm all selected units stop.
6. Select several combat units, RMB near an enemy cluster, choose `Attack Area`, and confirm distributed attacks without AoE.
7. Recheck Gather, Build Barracks, Production, single Attack, single Move, pause, and camera.

## Known Limitations

- Reservation is lightweight and presentation-only; it reduces same-tick conflicts but does not guarantee collision-free movement.
- Preferred attack cells are advisory. If unavailable or invalidated, `AttackOrder` uses normal dynamic replanning.
- Harvest and Build Barracks retain their existing movement behavior; reservation is applied to Group Move and Attack approach movement.

## Constraints Confirmation

No Python/training/checkpoint, observation/action contract, ActionDecoder semantics, ActionApplier semantics, combat runtime, movement runtime semantics, Player1 AI, Player2 bot control, or Week7 baseline scene changes were made for HumanPlay-3G.6.
