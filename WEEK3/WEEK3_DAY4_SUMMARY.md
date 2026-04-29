# Week 3 Day 4: Invalid Action Masking

## Historical Note (2026-04-29)

This Day 4 summary reflects the Week 3 implementation stage.
Contract details here should be interpreted as historical unless explicitly aligned to current v2 contract documentation.

## Status
Implemented.

## Refinement Update (Permissive Rules Narrowed)
Day 4 masks were additionally tightened to better mirror actual runtime behavior and reduce semantic drift with ActionApplier + MatchManager.

Runtime facts used for refinement:
- Move: `MatchManager.TryExecuteMove()` rejects `unit.IsBuilding` (buildings are not movable).
- Attack: effective combat eligibility is defined by `CombatResolver` via `UnitDefinition.attackDamage > 0` and `attackRange > 0`.
- Produce: `MatchManager.TryExecuteProduce()` requires `BuildingRuntime` component; `BuildingRuntime.StartProducingUnit()` requires existing `UnitDefinition` and enough resources.
- Base vs Barracks produce-type split: no explicit per-building produce-type split exists in current runtime path; both use shared `BuildingRuntime.StartProducingUnit()` logic.

## What Was Added

### 1. ActionMaskBuilder
New file: `Assets/Scripts/ML/ActionMaskBuilder.cs`

Core additions:
- `ActionMaskBuilder`: builds masks from authoritative Unity world state
- `ActionMaskSet`: transfer-compatible per-cell mask output
- `ActorActionMask`: hierarchical masks per actor
- `DebugActionMaskSet`: adapted debug-format view

Main API:
- `BuildTransferCompatibleMask(Owner playerId, bool noOpOnlyWhenNotRunning = true)`
- `BuildDebugMask(Owner playerId, bool noOpOnlyWhenNotRunning = true)`

### 2. Hierarchical Masking Model
Mask hierarchy is:
- actor/cell mask
- action type mask (`NoOp`, `Move`, `Harvest`, `Return`, `Produce`, `Attack`)
- parameter masks:
  - move directions
  - harvest directions
  - return directions
  - produce directions
  - produce unit type
  - attack local target (3x3 local index)

This model supports transfer-compatible per-cell branching directly and provides adapted debug actor-index masks.

### 3. Manager Integration
Masking is computed from runtime world state through existing systems:
- `MatchManager`
- `GridManager`
- `ResourceManager`
- `UnitRegistry`
- `BuildingRuntime` and `ProductionQueue` when relevant
- `MatchBootstrap/GameConfig` for produce cost lookup

No architectural rewrite of Day 3 pipeline was introduced.

## Rule Layer Split

### Gym-semantics-compatible checks
Examples in implementation:
- actor exists on cell
- actor owner matches `playerId`
- actor is alive
- move target is in bounds and free
- harvest target has active resource
- return target is own base
- produce requires enough resources
- attack target exists, is in local 3x3 range, and is enemy

### Unity-only runtime checks
Examples in implementation:
- match phase gate (`MatchPhase.Running`)
- production queue busy gate (`ProductionQueue.IsProducing`)
- `BuildingRuntime` presence gate for produce actions
- commandable actor gate for current runtime contour
- move gate for non-building actors only
- attack gate via runtime combat definition (`attackDamage`/`attackRange`)

The split is explicit in code comments and method boundaries.

## Authoritative Validation Is Preserved

`ActionMaskBuilder` is pre-sampling filtering only.

`ActionApplier` remains mandatory authoritative fallback validation for runtime truth.

Even when mask says action is valid:
- action still goes through full `ActionApplier` validation
- `MatchManager.ApplyCommand()` remains final runtime acceptance gate

This is explicitly documented in code comments and smoke-test logs.

## Multi-command Semantics Compatibility

Masking is computed for decision space only.

Day 3 batch conflict behavior is unchanged:
- duplicate commands for same actor in one step are still resolved server-side (`first-wins`)
- mask builder does not attempt to be an execution planner

## Debug and Diagnostic Output

`ActionMaskSet.BuildSummaryDump(...)` provides:
- available actor count
- action types for sampled actors
- parameter mask slices
- count of empty masks
- recorded mask/runtime mismatch count

`ActionMaskSet.RecordValidationMismatch(...)` supports mismatch diagnostics when smoke tests detect divergence.

## Day 4 Smoke Test

New file: `Assets/Scripts/ML/ActionMaskBuilderSmokeTest.cs`

Implemented smoke scenarios:
- actor mask: friendly actor enabled, empty cell disabled
- move mask: free direction allowed, blocked/out-of-bounds direction denied
- move mask: building actor does not receive move action
- harvest mask: worker next to resource gets harvest direction
- return mask: worker with cargo next to own base gets return direction
- produce mask:
  - enabled for building with resources and free queue
  - disabled when queue is busy
- produce type mask: checked against current runtime semantics for Base and Barracks
- attack mask: checked against runtime combat eligibility from `UnitDefinition` (`attackDamage`/`attackRange`)
- phase gate: non-running phase returns actor-empty/no-op-safe mask state
- runtime consistency probe: sample masked actions and compare with ActionApplier acceptance

Tests are built as deterministic scene smoke checks with local spawn helpers and episode reset per case.

## Known Limits

- Masking intentionally does not resolve all batch-time conflicts.
- Runtime can still diverge due to state changes between mask build and command apply; this is expected and handled by authoritative validation.
- No explicit Base/Barracks produce-type specialization is present in current runtime; masks intentionally mirror this and do not invent extra restrictions.

## Ready For Next Step

Day 4 objective is complete:
- invalid action masking layer exists
- Day 3 architecture is preserved
- server-side authoritative validation remains intact
- transfer-compatible and debug formats are both supported
