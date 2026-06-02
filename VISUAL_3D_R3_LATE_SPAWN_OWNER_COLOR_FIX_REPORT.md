# VISUAL_3D_R3_LATE_SPAWN_OWNER_COLOR_FIX_REPORT

## Scope
Visual-3D-R3 repair-pass for runtime owner-color sync on late-spawned units.

Goals:
- Player1 units use blue marker.
- Player2 units use red marker.
- Works for initial and runtime-spawned units.
- Validator catches late-spawn mismatch over time.
- No gameplay/AI/training/command semantics changes.

## Why Previous Validator Produced False PASS
Previous validation sampled a single runtime snapshot and could pass when only initial units were present.
Late runtime-spawned units were not guaranteed to be observed, so Player2 late-spawn blue-marker regressions were missed.

## Root Cause
1. Owner-color sync in `VisualEventBridge` was lifecycle-sensitive and could miss post-init states for spawned/re-enabled objects.
2. Sync was considered complete too early, without persistent material verification for late lifecycle ordering.
3. Validator did not aggregate observations over time by instance id, so late spawns were not tracked as first-seen-after-initial.

## Implemented Changes

### 1) VisualEventBridge hardened for late spawn lifecycle
File: `Assets/Scripts/Presentation/VisualEventBridge.cs`

Changes:
- Added robust reference resolution in Awake/OnEnable/Update/LateUpdate (self/parent/child for UnitRuntime and UnitVisualAnimator).
- OnEnable resets sync state and clears stale lifecycle state (including last owner sentinel).
- Start now performs `TrySyncOwner("Start")`.
- Update/LateUpdate keep retrying owner sync until material matches expected owner material.
- Sync is re-run if owner changes or material no longer matches expected.
- Added explicit visual-only API: `NotifyRuntimeInitialized()`.
- Added debug/public state:
  - LastSyncedOwner
  - HasSyncedSuccessfully
  - LastSyncFrame
  - LastSyncReason
  - LastObservedOwner
  - LastObservedModelNull
  - LastMaterialMatchedExpected
  - LastMarkerMaterialName

Safety:
- No gameplay mutation.
- No MatchManager calls.
- No HP/resource/grid/AI changes.

### 2) UnitVisualAnimator made authoritative marker controller
File: `Assets/Scripts/Presentation/UnitVisualAnimator.cs`

Changes:
- Authoritative marker selection prefers `VisualRoot/TeamMarker_Ring`.
- Fallback searches nearest available `TeamMarker_Ring` under prefab root.
- If serialized `materialRenderers` is wrong/empty, it is replaced with authoritative marker renderer.
- If authoritative marker is inactive, it is activated.
- Duplicate markers are suppressed from visibility to avoid multiple visible rings.
- Added methods:
  - `ApplyOwnerVisualAndVerify(Owner owner, out string diagnostic)`
  - `IsMarkerMaterialCorrectForOwner(Owner owner)`
- `SetOwnerVisual(owner)` applies only to authoritative marker renderers.

Safety:
- Does not recolor full character mesh; only marker renderer(s).

### 3) Explicit post-init presentation refresh hook
File: `Assets/Scripts/Gameplay/Entities/UnitFactory.cs`

Change:
- After `unit.Init(...)`, factory resolves `VisualEventBridge` and calls `bridge.NotifyRuntimeInitialized()`.

Why this does not alter spawn semantics:
- It is a presentation-only notification after model/owner init.
- No changes to returned `UnitRuntime`.
- No changes to GridManager placement, UnitRegistry registration, owner/model data, or gameplay state.

### 4) Over-time validator extension
File: `Assets/Editor/Visual3DROwnerColorRuntimeValidator.cs`

Changes:
- Added menu mode: `RTS/Visual/Validate Owner Colors Over Time`.
- Over-time checkpoints collect multiple snapshots and aggregate by `UnitRuntime` instance id.
- Tracks firstSeenFrame/lastSeenFrame and flags late-spawned units.
- Captures initial-vs-late evidence and late-only mismatches.
- Adds bridge diagnostics and renderer path details in evidence.
- Outputs:
  - `Assets/Visual3DR3_LateSpawnOwnerColorEvidence.md`
  - `Assets/Visual3DR3_LateSpawnOwnerColorEvidence.json`
  - `Assets/Visual3DR3_OwnerColorValidation_OverTime.md`
  - `Assets/Visual3DR3_OwnerColorValidation_OverTime.json`
- Duplicate marker metric updated to count visible duplicates only.

## Evidence Artifacts
Generated evidence files:
- `Assets/Visual3DR3_LateSpawnOwnerColorEvidence.md`
- `Assets/Visual3DR3_LateSpawnOwnerColorEvidence.json`

Generated validation files:
- `Assets/Visual3DR3_OwnerColorValidation_OverTime.md`
- `Assets/Visual3DR3_OwnerColorValidation_OverTime.json`

Key evidence from late-spawn run (captured UTC 2026-05-12T02:47:34Z):
- Initial Player1 correct: 1
- Initial Player2 correct: 1
- Late-spawned Player1 correct: 23
- Late-spawned Player2 correct: 41
- Late-spawn mismatches: 0
- Missing UnitVisualAnimator: 0
- Missing VisualEventBridge: 0
- Missing TeamMarker_Ring: 0

Post-filter validator sanity run (captured UTC 2026-05-12T02:50:27Z):
- Duplicate visible markers: 0
- Late-spawn mismatches: 0

## Prefab Wiring Verification (spawnable units)
Checked:
- `Assets/Prefabs/Worker.prefab`
- `Assets/Prefabs/Light.prefab`
- `Assets/Prefabs/Heavy.prefab`
- `Assets/Prefabs/Ranged.prefab`

Verified:
- UnitVisualAnimator present and discoverable.
- VisualEventBridge present and discoverable.
- `VisualRoot/TeamMarker_Ring` present.
- Marker renderer present.
- Player1_Blue, Player2_Red, Neutral_Resource material references assigned.
- Runtime owner override active via bridge sync.

## Production/Spawn Path Verification
Observed path:
- `BuildingRuntime` produces units through `UnitFactory.Spawn(...)`.
- `UnitFactory.Spawn(...)` calls `UnitRuntime.Init(...)` and then visual-only `NotifyRuntimeInitialized()`.
- VisualEventBridge retries sync until expected material is verified.

Result:
- Runtime-spawned Player2 units observed with red markers in over-time evidence.

## Runtime Scene Validation (Week7)
Scene:
- `Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity`

Screenshots:
- `Assets/Screenshots/Visual_3D_R3_InitialUnits_OwnerColors.png`
- `Assets/Screenshots/Visual_3D_R3_LateSpawnedUnits_OwnerColors.png`
- `Assets/Screenshots/Visual_3D_R3_Player2LateSpawnedRed_Closeup.png`

Visual confirmation:
- Initial Player1/Player2 units show correct blue/red markers.
- Late-spawned Player2 units show red markers (no stuck-blue late Player2 in evidence).
- Light visual remains Viking-based presentation.

## Changed Files
- `Assets/Scripts/Presentation/VisualEventBridge.cs`
- `Assets/Scripts/Presentation/UnitVisualAnimator.cs`
- `Assets/Scripts/Gameplay/Entities/UnitFactory.cs`
- `Assets/Editor/Visual3DROwnerColorRuntimeValidator.cs`
- `Assets/Visual3DR3_LateSpawnOwnerColorEvidence.md`
- `Assets/Visual3DR3_LateSpawnOwnerColorEvidence.json`
- `Assets/Visual3DR3_OwnerColorValidation_OverTime.md`
- `Assets/Visual3DR3_OwnerColorValidation_OverTime.json`
- `Assets/Screenshots/Visual_3D_R3_InitialUnits_OwnerColors.png`
- `Assets/Screenshots/Visual_3D_R3_LateSpawnedUnits_OwnerColors.png`
- `Assets/Screenshots/Visual_3D_R3_Player2LateSpawnedRed_Closeup.png`

## Guardrail Confirmation (unchanged semantics)
Not changed:
- MatchManager command semantics
- ActionApplier
- ActionDecoder
- ActionMaskBuilder
- ObservationBuilder
- GridManager occupancy logic
- UnitRegistry registration semantics
- ResourceManager / ResourceNode gameplay semantics
- ML-Agents training code
- Python BC/PPO scripts
- Checkpoint paths
- Inference bridge
- Map coordinate system and logical map size
- Base/Barracks/Resource gameplay prefabs and gameplay balance/stats

## Acceptance Summary
- Initial Player1/Player2 colors correct: PASS
- Late-spawned Player1/Player2 colors correct: PASS (over-time late-spawn evidence)
- Late-spawned Player2 units are red, not blue: PASS
- Over-time validator mismatches after stabilization: PASS (0)
- Missing components on target units: PASS (0)
- Duplicate visible markers: PASS (post-filter validator run reports 0)
- Report created: PASS
