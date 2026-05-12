# Visual-3E-D — Runtime Animation Event Integration and Timing Validation

## Scope

Presentation-only runtime animation integration for Worker/Light/Heavy/Ranged visual layer.
No gameplay/AI/training/observation/action semantics were changed.

## 1) Runtime Signal Inventory (Task 1)

Signals were verified in these files:

- `Assets/Scripts/Presentation/UnitVisualAnimator.cs`
- `Assets/Scripts/Presentation/VisualEventBridge.cs`
- `Assets/Scripts/Gameplay/Entities/UnitRuntime.cs`
- `Assets/Scripts/Gameplay/Entities/BuildingRuntime.cs`
- `Assets/Scripts/Gameplay/Match/MatchManager.cs`
- `Assets/Scripts/ML/ActionApplier.cs`
- `Assets/Scripts/Gameplay/Combat/CombatResolver.cs`
- `Assets/Scripts/Gameplay/Entities/ResourceNode.cs`
- `Assets/Scripts/Gameplay/Economy/ResourceManager.cs`

Safe signal points used:

- Move start/end: `VisualEventBridge.Update` via runtime grid-position delta latch (`movementLatchSeconds`) and `IsMoving` transitions.
- Attack applied: `CombatResolver.TryAttack` (after `CanAttack` succeeds).
- Harvest applied: `MatchManager.TryExecuteHarvest` (only when resource transfer succeeds).
- Death lifecycle: `CombatResolver.HandleDeath` + existing `VisualEventBridge.Update` alive-state fallback.
- Spawn: existing visual-only notify path (`UnitFactory.Spawn -> VisualEventBridge.NotifyRuntimeInitialized` + `Start`).

## 2) Runtime Trace Integration (Task 2)

Added development-only trace utility:

- `Assets/Scripts/Presentation/Visual3EDRuntimeAnimationTrace.cs`

Artifacts:

- `Assets/Visual3ED_RuntimeAnimationTrace.jsonl`
- `Assets/Visual3ED_RuntimeAnimationTrace.md`

Each trace row records:

- frame, step;
- unit instance id/type/owner/grid position;
- visual event (Idle, MoveStart, MoveEnd, Attack, Harvest, Death, Hit);
- animator parameter changed;
- source method;
- success/failure;
- diagnostic string.

Trace is opt-in (`VisualEventBridge.enableRuntimeTrace`) and compiled for editor/development builds only.

## 3) Walk / IsMoving (Task 3)

Implementation:

- `VisualEventBridge.Update` already had a grid-based movement latch.
- Extended with explicit MoveStart/MoveEnd/Idle trace transitions.
- Added `PulseMoving(float)` for non-destructive manual validation.

Observed in live trace:

- `MoveStart` and `MoveEnd` entries present.
- Idle re-entry present after movement.
- No stuck-in-Walk observed in trace evidence.

## 4) Attack Trigger (Task 4)

Implementation:

- `CombatResolver.TryAttack` now calls:
  - attacker bridge `OnVisualAttack()`;
  - target bridge `OnVisualHit()`.
- Trigger happens only on applied runtime attack (after `CanAttack` gate), not on rejected action.

## 5) Harvest Trigger (Task 5)

Implementation:

- `MatchManager.TryExecuteHarvest` now calls `OnVisualHarvest()` only when:
  - node harvest > 0;
  - carried resources actually increased.

No gameplay resource semantics were modified.

Harvest visual fallback note:

- Harvest animation may use embedded PickUp clip fallback depending on controller clip mapping.

## 6) Death Trigger (Task 6)

Implementation:

- `CombatResolver.HandleDeath` now calls `OnVisualDeath()` before deactivation/destroy.
- Existing `VisualEventBridge` death fallback retained.

Current run limitation:

- In this live validation, no Death event occurred in trace.
- Lifecycle remains immediate (no destroy delay added), by design.

## 7) Manual Validator (Task 7)

Added:

- `Assets/Editor/Visual3EDRuntimeAnimationValidator.cs`

Menu commands:

- `RTS/Presentation/Visual-3E-D/Run Runtime Animation Validation`
- `RTS/Presentation/Visual-3E-D/Reset Runtime Animation Trace`

Outputs:

- `Assets/Visual3ED_RuntimeAnimationValidation.md`
- `Assets/Visual3ED_RuntimeAnimationValidation.json`

Latest validation snapshot:

- Play Mode: true
- Wiring: Worker/Light/Heavy/Ranged all OK
- Manual trigger test: executed on 43 active units
- Trace check: Move=true, Attack=true, Harvest=true, Death=false

## 8) Live Gameplay Validation (Task 8)

Performed in live Play Mode session.

Evidence from trace:

- Idle visible in trace (Idle events logged).
- Walk observed (MoveStart/MoveEnd logged).
- Harvest observed (Harvest trigger logged).
- Attack observed (Attack trigger logged; manual and runtime hook path active).
- Death not observed in this run (documented limitation/deferred evidence).

## 9) Screenshots (Task 9)

Captured:

- `Assets/Screenshots/Visual_3E_D_WalkRuntime.png`
- `Assets/Screenshots/Visual_3E_D_AttackTrigger.png`
- `Assets/Screenshots/Visual_3E_D_HarvestTrigger.png`
- `Assets/Screenshots/Visual_3E_D_OwnerColorStillCorrect.png`

Trace remains primary evidence for motion/timing events.

## 10) Console Diagnostics

Observed in Play Mode:

- Missing optional animator params on some units (`IsCarrying`, `Spawn`).

Mitigation applied:

- `UnitVisualAnimator` now checks parameter existence before `SetBool/SetTrigger`.
- Missing-parameter warnings are development-only and globally throttled.

## Changed Files

- `Assets/Scripts/Presentation/VisualEventBridge.cs`
- `Assets/Scripts/Presentation/Visual3EDRuntimeAnimationTrace.cs`
- `Assets/Scripts/Presentation/UnitVisualAnimator.cs`
- `Assets/Scripts/Gameplay/Match/MatchManager.cs`
- `Assets/Scripts/Gameplay/Combat/CombatResolver.cs`
- `Assets/Editor/Visual3EDRuntimeAnimationValidator.cs`
- `Assets/Visual3ED_RuntimeAnimationTrace.jsonl`
- `Assets/Visual3ED_RuntimeAnimationTrace.md`
- `Assets/Visual3ED_RuntimeAnimationValidation.md`
- `Assets/Visual3ED_RuntimeAnimationValidation.json`
- `VISUAL_3E_D_RUNTIME_ANIMATION_EVENT_INTEGRATION_REPORT.md`

## Guardrails (Not Changed)

- MatchManager command semantics.
- ActionApplier semantics.
- ActionDecoder / ActionMaskBuilder / ObservationBuilder.
- Grid occupancy / coordinate system / map size (24x24).
- UnitFactory gameplay spawn semantics.
- UnitRegistry / ResourceManager / ResourceNode gameplay semantics.
- ML-Agents, Python training scripts, checkpoint paths, inference bridge.
- Base/Barracks/Resource prefabs, UnitDef/GameConfig gameplay assets.
- Owner color synchronization semantics.
- Reward/terminal semantics.
