# HumanPlay-3G.0 Command Runtime Audit

## Scope

This is a read-only runtime capability audit. No gameplay semantics, decoder/applier
logic, Python, training data, checkpoints, or Week7 baseline scene were changed.

Human play is configured for `Owner.Player2`. `PlayerCommandController` constructs
debug-source `AgentAction` values and calls `ActionApplier.ApplyAction()` directly.

## Executive Summary

| Command | Runtime support | Human UI reliability | Key limitation |
| --- | --- | --- | --- |
| Move | Supported | Works only for one orthogonally adjacent empty cell | No high-level path order |
| Harvest | Supported | Works only while adjacent to an active resource | No move-to-resource order |
| Return | Supported | Works only while adjacent to own Base and carrying resources | No move-to-base order |
| Produce Worker | Supported by runtime | Currently broken from human UI | Human controller passes runtime enum `0`; `ActionApplier` expects v2 index `3` |
| Produce Light/Heavy/Ranged | Supported by runtime | Currently broken from human UI | Human controller passes runtime enum `1/2/3`; `ActionApplier` expects v2 index `4/5/6` |
| Build Barracks | Supported by runtime as Worker `Produce` | Currently broken from human UI | Human controller passes runtime enum `0`; worker build requires v2 index `2` |
| Attack | Supported | Supported subject to runtime definition and range checks | Outside the main 3G.0 economy audit |

The safest next step is to add human-side high-level order orchestration around the
existing low-level commands. Before exposing production orders as reliable human
features, 3G.4 must resolve the human `ProducibleUnit` versus v2 produce-index mismatch
without changing ML decoder/applier semantics.

## 1. Move

### Representation

`AgentAction` represents Move as:

- `ActorPosition`: source cell.
- `ActionType = UnitActionType.Move`.
- `Direction`: one of `North`, `East`, `South`, `West`.

The target is derived as `unit.GridPos.Neighbour(action.Direction)`. Move is therefore
one orthogonally adjacent cell only. There is no target-position Move action and no
multi-cell Move command.

### Final execution path

`PlayerCommandController` -> `ActionApplier.ApplyAction()` ->
`MatchManager.ApplyCommand()` -> pending queue -> next `MatchManager.StepMatch()` ->
`ExecuteMovementPhase()` -> `TryExecuteMove()` -> `UnitRuntime.MoveTo()` ->
`GridManager.MoveUnit()`.

### Rejection conditions

Submission or execution can reject/fail when:

- no selected unit, multi-selection is active, or clicked cell is not orthogonally adjacent;
- match is not running;
- actor cell is empty, actor owner differs from command owner, or actor is dead;
- unit type cannot move, including `Resource`, `Base`, and `Barracks`;
- target is out of bounds or occupied;
- the unit moved or disappeared before execution, the source occupancy changed, or the
  destination became occupied before the queued command executes.

## 2. Harvest

### Representation and adjacency

`AgentAction` represents Harvest with `ActorPosition`,
`ActionType = UnitActionType.Harvest`, and `Direction`. The target resource is
`worker.GridPos.Neighbour(direction)`, so the Worker must be orthogonally adjacent.

### Carry model

During `MatchManager.TryExecuteHarvest()`:

1. Free capacity is `GameConstants.MaxCarryCapacity - worker.CarriedResources`.
2. Requested harvest is `min(GameConstants.HarvestAmount, freeCapacity)`.
3. `ResourceNode.Harvest(requestAmount)` removes available resource.
4. `UnitRuntime.AddCarriedResources(harvested)` stores it in `UnitModel`.

Public state:

- has carried resource: `worker.CarriedResources > 0`;
- full carry: `worker.CarriedResources >= GameConstants.MaxCarryCapacity`;
- `ActionApplier` currently checks the equivalent hard-coded threshold `>= 100`.

### Rejection conditions

- actor is not a living owned Worker;
- target neighbor is outside the map;
- `ResourceManager` is unavailable;
- no resource node exists at target or it is exhausted;
- Worker has no free carry capacity;
- queued execution state changed before the next match step.

## 3. Return

### Representation and adjacency

`AgentAction` represents Return with `ActorPosition`,
`ActionType = UnitActionType.Return`, and `Direction`. The target is the adjacent
neighbor cell, which must contain an owned `UnitType.Base`.

### Deposit model

During `MatchManager.TryExecuteDeposit()`:

1. `worker.DropAllCarriedResources()` clears carry and returns the dropped amount.
2. `MatchManager.AddResources(worker.Owner, dropped)` updates `PlayerState`.
3. `PlayerState.AddResources(amount)` increases `CurrentResources`.

### Rejection conditions

- actor is not a living owned Worker;
- Worker carries `<= 0`;
- target neighbor is outside the map;
- target has no friendly Base;
- queued execution state changed before the next match step.

## 4. Produce

### Runtime representation

Produce uses:

- `ActorPosition`;
- `ActionType = UnitActionType.Produce`;
- `Direction`;
- `ProduceUnitType`.

For ML Action Contract v2, `AgentAction.ProduceUnitType` intentionally carries a raw
v2 branch index cast to `ProducibleUnit`:

| v2 index | Meaning | Runtime producer |
| --- | --- | --- |
| `2` | Barracks | Worker build path |
| `3` | Worker | Base |
| `4` | Light | Barracks |
| `5` | Heavy | Barracks |
| `6` | Ranged | Barracks |

`ProducibleUnit` itself is a separate runtime enum: `Worker=0`, `Light=1`, `Heavy=2`,
`Ranged=3`.

### Supported producers

Runtime supports:

- Base -> Worker;
- Barracks -> Light;
- Barracks -> Heavy;
- Barracks -> Ranged;
- Worker -> Barracks construction through the special Produce path.

### Direction and spawning

Normal building production carries a direction, but `BuildingRuntime` does not use it
to choose the final spawn cell. Production starts in a single-slot `ProductionQueue`.
Each match step ticks production. On completion, `BuildingRuntime.FindFreeNeighborCell()`
automatically scans the surrounding 3x3 cells, including diagonals, and spawns in the
first free cell.

The human controller currently performs an extra pre-submit scan for an orthogonally
adjacent free cell and includes that direction. This is stricter than normal runtime
production requires.

Worker Barracks construction is different: its supplied direction is required and the
Barracks is spawned immediately in that exact orthogonally adjacent cell during the
production phase.

### Rejection conditions

Common validation:

- match not running, actor missing, wrong owner, actor dead;
- producer is not Base, Barracks, or Worker;
- raw v2 produce index is outside `0..6` or disallowed for producer type.

Base/Barracks unit production:

- produced definition missing;
- insufficient resources;
- production queue busy;
- config or `BuildingRuntime` unavailable during execution;
- produced unit may fail to appear at completion if all surrounding 3x3 cells are occupied.

Human UI limitation:

`PlayerCommandController.TryProduce()` passes the runtime `ProducibleUnit` enum directly.
`ActionApplier.ValidateProduceAction()` interprets the underlying value as a v2 index.
Therefore the current human calls submit `0/1/2/3` where runtime validation expects
`3/4/5/6`, and Build Barracks submits `0` where validation expects `2`.

## 5. Build Barracks

Barracks construction is implemented in runtime. There is no separate `Build`
`UnitActionType`; construction is Worker `Produce` with raw v2 produce index `2`.

Execution path:

`ActionApplier.ValidateWorkerBuildBarracks()` ->
`MatchManager.TryWorkerBuildBarracks()` -> spend resources ->
`UnitFactory.Spawn(UnitType.Barracks, owner, adjacentCell)`.

Required preconditions:

- selected actor is a living owned Worker;
- produce payload is raw v2 index `2`;
- owner has no living Barracks already;
- active `GameConfig` contains `UnitType.Barracks`;
- requested adjacent target is inside map and empty;
- player can afford Barracks cost.

Configuration audit:

- `Assets/ML/UnitDefs/UnitDef_Barracks.asset` exists.
- `Assets/ML/GameConfig_MVP.asset` references it by GUID.
- Definition values include `unitType: 2`, `productionCost: 2`, `productionTime: 8`,
  and `isBuilding: 1`.

The runtime feature exists, but the current human UI path cannot reach it because it
submits `ProducibleUnit.Worker` (`0`) instead of raw v2 index `2`.

## 6. Command Timing

`PlayerCommandController.SubmitAgentAction()` applies validation immediately through
`ActionApplier`, but accepted non-NoOp commands are only appended to
`MatchManager._pendingCommands`. Gameplay effects wait for the next `StepMatch()`.

A high-level order layer can safely submit one low-level command per unit per match
tick if it synchronizes on `MatchManager.OnStepCompleted` and re-checks live state
before submitting the next action.

Completion signals:

- Move: compare `UnitRuntime.GridPos` after `OnStepCompleted`.
- Harvest: compare `CarriedResources` and resource-node state after the step.
- Return: verify `CarriedResources == 0` and player resource increase.
- Build Barracks: verify an owned living Barracks exists after the step.
- Normal production: inspect `BuildingRuntime.GetProductionQueue().IsProducing`,
  observe queue completion, and verify spawned unit presence.

`MatchManager.TryGetLastAppliedCommand()` is diagnostic, not a durable completion
signal. The dictionary is cleared at the beginning of every `StepMatch()`, filled while
pending commands are bucketed, and may contain a command even if later phase execution
fails.

## 7. Existing Helpers

### Grid and navigation

- `GridManager.GetFreeAdjacentCell`: **does not exist**.
- Public grid helpers: `IsInside`, `IsCellOccupied`, `IsWalkable`, `GetOccupant`,
  `TryGetOccupant`, `GetNeighbour`, and `GetValidNeighbours`.
- Production-only free spawn helper:
  `BuildingRuntime.FindFreeNeighborCell()` is private and scans 3x3 cells.
- Shared public pathfinding service: **does not exist**.
- `HeuristicDriver` has private `FindPathStep()`, but it is a local greedy helper,
  not a reusable pathfinding API.
- `HeuristicDriver` also has private `FindNearestBase()` and `FindNearestResource()`.
- `ResourceManager.GetAllResourceNodes()` is public and can support a new human-order
  nearest-resource helper.
- `UnitRegistry` ownership queries can support a new nearest-owned-base helper.

### Public unit state

`UnitRuntime` publicly exposes:

- `GridPos`;
- `Owner`;
- `Type`;
- `HP`, `MaxHP`, and `IsAlive`;
- `CarriedResources`;
- `IsBuilding`;
- `Facing`.

## Limitations

- Human Move, Harvest, and Return are intentionally low-level adjacent actions.
- No public reusable pathfinder or human-order queue exists.
- Multi-selection commands are rejected by `PlayerCommandController`.
- Human production and Build Barracks are blocked by the produce-payload contract mismatch.
- Normal production can consume resources and finish its queue without spawning a unit
  if no surrounding 3x3 cell is free at completion.
- Human controller acceptance means queued, not executed successfully.

## Recommended Plan

### 3G.1: Human Order State and Tick Driver

Add a presentation-side high-level order component for Player2 only. Subscribe to
`MatchManager.OnStepCompleted`, submit at most one adjacent low-level action per unit
per tick, and re-evaluate live state after each step. Do not modify `ActionDecoder`,
`ActionApplier`, or match semantics.

### 3G.2: Move-To and Economy Orders

Implement human orders for move-to-cell, gather-resource, and return-to-base using a
new reusable cardinal-grid path helper. Gather should move until adjacent, Harvest
until full or exhausted, move to nearest owned Base, Return until empty, then repeat
or finish according to UI intent.

### 3G.3: Reliable Contextual UX

Route contextual clicks into high-level orders instead of requiring adjacency. Show
order state and rejection reason. Keep single-selection scope unless formation and
reservation behavior are explicitly designed.

### 3G.4: Production and Barracks Human Adapter

Add a human-side adapter that constructs the v2 produce payload expected by the
existing runtime: Worker-build `2`, Base Worker `3`, Barracks units `4/5/6`. Preserve
`ActionDecoder` and `ActionApplier`. For normal production, display queue progress and
completion failure when no 3x3 spawn cell is free.

## Safe Implementation Boundary

Safe for follow-up work:

- presentation-side order state;
- cardinal path helper;
- nearest-resource and nearest-owned-base helpers;
- Player2 contextual order UX;
- human-side conversion from UI production choice to existing v2 produce payload.

Not safe to treat as already solved:

- arbitrary-distance runtime Move;
- public reusable pathfinding;
- group formations;
- reliable human production before the payload adapter;
- guaranteed produced-unit spawn when the building is surrounded.
