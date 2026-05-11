# VISUAL_INTEGRATION_LAYER

## Goal
Safe visual integration layer for UnityRTSPrototype with strict separation from gameplay/AI runtime semantics.

## Created Folders
- `Assets/Art/Materials`
- `Assets/Art/Prefabs/Visuals`
- `Assets/Art/Prefabs/VFX`
- `Assets/Art/AnimatorControllers`
- `Assets/Scripts/Presentation`

## Added Scripts
- `Assets/Scripts/Presentation/UnitVisualAnimator.cs`
- `Assets/Scripts/Presentation/VisualEventBridge.cs`

Editor utility used to generate visual assets safely:
- `Assets/Scripts/Editor/Presentation/VisualLayerAssetBuilder.cs`

## Materials Created
- `Assets/Art/Materials/Player1_Blue.mat`
- `Assets/Art/Materials/Player2_Red.mat`
- `Assets/Art/Materials/Neutral_Resource.mat`
- `Assets/Art/Materials/Ground_Grass.mat`
- `Assets/Art/Materials/Grid_Line.mat`
- `Assets/Art/Materials/Selection_Valid.mat`
- `Assets/Art/Materials/Selection_Invalid.mat`
- `Assets/Art/Materials/HP_Bar_Background.mat`
- `Assets/Art/Materials/HP_Bar_Fill.mat`

Material policy:
- Lightweight built-in creation through Unity Material asset API.
- No Shader Graph assets introduced.
- No render-pipeline reconfiguration applied.

## Prefab VisualRoot Integration
VisualRoot added as child layer (root object preserved):
- `Assets/Prefabs/Base.prefab` -> `Base/VisualRoot`
- `Assets/Prefabs/Worker.prefab` -> `Worker/VisualRoot`
- `Assets/Prefabs/Barracks.prefab` -> `Barracks/VisualRoot`
- `Assets/Prefabs/Heavy.prefab` -> `Heavy/VisualRoot`
- `Assets/Prefabs/Ranged.prefab` -> `Ranged/VisualRoot`

Requested prefabs not found (not auto-created):
- `Assets/Prefabs/Light.prefab` (missing)
- `Assets/Prefabs/ResourceNode.prefab` (missing)

## Animator Template
Created:
- `Assets/Art/AnimatorControllers/RTS_Unit_Template.controller`

States:
- Idle
- Walk
- Attack
- Harvest
- Death

Parameters:
- `IsMoving` (bool)
- `IsCarrying` (bool)
- `Attack` (trigger)
- `Harvest` (trigger)
- `Death` (trigger)
- `Spawn` (trigger)
- `Hit` (trigger)

Transitions:
- Idle -> Walk when `IsMoving == true`
- Walk -> Idle when `IsMoving == false`
- Any State -> Attack by `Attack`
- Any State -> Harvest by `Harvest`
- Any State -> Death by `Death`

Clip binding:
- Safe auto-attempt implemented via name-keyword scan.
- In current repository state there are no imported Quaternius animation clips as `.anim`; controller remains valid template with unbound motions (safe fallback).

## Placeholder VFX Prefabs
Created:
- `Assets/Art/Prefabs/VFX/VFX_AttackHit.prefab`
- `Assets/Art/Prefabs/VFX/VFX_Harvest.prefab`
- `Assets/Art/Prefabs/VFX/VFX_Spawn.prefab`
- `Assets/Art/Prefabs/VFX/VFX_Death.prefab`

VFX safety:
- ParticleSystem-based placeholders only.
- No gameplay colliders added.
- Optional references by design (null-safe in `UnitVisualAnimator`).
- No GridManager occupancy participation.

## Presentation Component Contracts
### UnitVisualAnimator
Public API implemented:
- `SetMoving(bool value)`
- `SetCarrying(bool value)`
- `PlayAttack()`
- `PlayHarvest()`
- `PlayDeath()`
- `PlaySpawn()`
- `PlayHit()`
- `SetOwnerVisual(Owner owner)`
- `SetVisible(bool value)`

Safety behavior:
- Null-safe when Animator/VFX/Renderer references are missing.
- Warnings emitted only once and only in Editor/Development build symbols.
- No gameplay command dispatch, no model mutation.

### VisualEventBridge
Behavior:
- Holds references to `UnitRuntime` and `UnitVisualAnimator`.
- Initial owner/carry sync on start.
- Poll-based visual state updates (movement latch from grid-position deltas).
- Optional visual-only hook methods (`OnVisualAttack`, `OnVisualHarvest`, etc.) for future wiring.
- No alternative gameplay logic introduced.

## How To Attach Quaternius Models to VisualRoot
1. Open target gameplay prefab (for example `Assets/Prefabs/Worker.prefab`).
2. Keep root object and root runtime components unchanged.
3. Put imported mesh object under child `VisualRoot`.
4. Keep local transform offsets on model child (not on root runtime object).
5. Ensure unit visual footprint remains visually close to one cell for unit prefabs.
6. Assign owner materials using `UnitVisualAnimator` renderer slots.

## How To Attach Animation Clips to RTS_Unit_Template
1. Import Universal Animation Library clips into project as `AnimationClip` assets.
2. Open `Assets/Art/AnimatorControllers/RTS_Unit_Template.controller`.
3. Assign clips manually to states:
   - Idle -> idle clip candidate
   - Walk -> walk clip candidate
   - Attack -> attack clip candidate
   - Harvest -> harvest clip candidate
   - Death -> death clip candidate
4. Keep parameter names unchanged to stay API-compatible with `UnitVisualAnimator`.

## Explicitly Unchanged Gameplay/AI Modules
No edits were made to:
- `MatchManager`
- `ActionApplier`
- `ActionDecoder`
- `ActionMaskBuilder`
- `ObservationBuilder`
- `GridManager` occupancy logic
- `UnitFactory` spawn semantics
- `UnitRegistry` registration semantics
- ML-Agents training code
- Python training/BC/PPO scripts
- checkpoint paths
- inference bridge
- active scene binding of current working AI pipeline

## Validation Performed
- C# compile diagnostics for added scripts: no errors.
- Unity Play Mode smoke: enter/exit play mode succeeded.
- Active scene remained loadable in current Unity session (`Week7_MLAgents_StudentVsScriptedBot`).
- Prefab hierarchy checks confirm `VisualRoot` is a child layer and root component lists are preserved.

Observed non-blocking warning:
- Unity MCP plugin warning: `WebSocket is not initialised` (tooling channel warning, not gameplay runtime logic).

## Changed Files (visual integration scope)
- `ART_ASSET_INVENTORY.md`
- `VISUAL_INTEGRATION_LAYER.md`
- `Assets/Art/AnimatorControllers/RTS_Unit_Template.controller`
- `Assets/Art/AnimatorControllers/RTS_Unit_Template.controller.meta`
- `Assets/Art/Materials/Player1_Blue.mat`
- `Assets/Art/Materials/Player1_Blue.mat.meta`
- `Assets/Art/Materials/Player2_Red.mat`
- `Assets/Art/Materials/Player2_Red.mat.meta`
- `Assets/Art/Materials/Neutral_Resource.mat`
- `Assets/Art/Materials/Neutral_Resource.mat.meta`
- `Assets/Art/Materials/Ground_Grass.mat`
- `Assets/Art/Materials/Ground_Grass.mat.meta`
- `Assets/Art/Materials/Grid_Line.mat`
- `Assets/Art/Materials/Grid_Line.mat.meta`
- `Assets/Art/Materials/Selection_Valid.mat`
- `Assets/Art/Materials/Selection_Valid.mat.meta`
- `Assets/Art/Materials/Selection_Invalid.mat`
- `Assets/Art/Materials/Selection_Invalid.mat.meta`
- `Assets/Art/Materials/HP_Bar_Background.mat`
- `Assets/Art/Materials/HP_Bar_Background.mat.meta`
- `Assets/Art/Materials/HP_Bar_Fill.mat`
- `Assets/Art/Materials/HP_Bar_Fill.mat.meta`
- `Assets/Art/Prefabs/VFX/VFX_AttackHit.prefab`
- `Assets/Art/Prefabs/VFX/VFX_AttackHit.prefab.meta`
- `Assets/Art/Prefabs/VFX/VFX_Harvest.prefab`
- `Assets/Art/Prefabs/VFX/VFX_Harvest.prefab.meta`
- `Assets/Art/Prefabs/VFX/VFX_Spawn.prefab`
- `Assets/Art/Prefabs/VFX/VFX_Spawn.prefab.meta`
- `Assets/Art/Prefabs/VFX/VFX_Death.prefab`
- `Assets/Art/Prefabs/VFX/VFX_Death.prefab.meta`
- `Assets/Prefabs/Base.prefab`
- `Assets/Prefabs/Worker.prefab`
- `Assets/Prefabs/Barracks.prefab`
- `Assets/Prefabs/Heavy.prefab`
- `Assets/Prefabs/Ranged.prefab`
- `Assets/Scripts/Presentation/UnitVisualAnimator.cs`
- `Assets/Scripts/Presentation/VisualEventBridge.cs`
- `Assets/Scripts/Editor/Presentation/VisualLayerAssetBuilder.cs`

## Play Mode Checklist
- Confirm unit root gameplay components still stay on prefab root objects.
- Confirm `VisualRoot` remains child layer on patched prefabs.
- Confirm no gameplay collider was added to VFX prefabs.
- Confirm selecting/issuing commands behaves identically to baseline.
- Confirm AI inference decisions and command outcomes match previous baseline behavior.
