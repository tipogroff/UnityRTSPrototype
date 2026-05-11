# Visual-2 Model Binding Report

Date: 2026-05-12
Project: UnityRTSPrototype
Stage: Visual-2 (Quaternius model import + safe visual binding)

## 1) Source archives used

Used archives (only these):
- `drive-download-20260511T185405Z-3-001.zip` (Quaternius Ultimate Fantasy RTS)
- `Universal Animation Library[Standard].zip` (Quaternius Universal Animation Library)

Not used:
- Ultimate Buildings Pack
- Kenney assets

## 2) Extraction layout and policy

Created/extracted into:
- `Assets/Art/Quaternius/UltimateFantasyRTS/`
- `Assets/Art/Quaternius/UniversalAnimationLibrary/`

Extraction policy applied:
- Ultimate Fantasy RTS: extracted FBX + PNG/JPG preview + license only.
- Blend sources were intentionally not imported.
- Universal Animation Library: extracted Unity FBX and minimal companion files (license/setup images).

## 3) Selected FBX models

Selected candidates bound in this stage:
- Base visual: `TownCenter_FirstAge_Level1.fbx`
- Barracks visual: `Barracks_FirstAge_Level1.fbx`
- Gold resource visual: `Resource_Gold_1.fbx`
- Rock resource visual: `Resource_Rock_1.fbx`
- Tree resource visual: `Resource_Tree1.fbx`

## 4) Visual-only prefabs created

Created visual-only prefabs (presentation components only: Transform + MeshFilter + MeshRenderer):
- `Assets/Art/Prefabs/Visuals/Visual_Base_TownCenter.prefab`
- `Assets/Art/Prefabs/Visuals/Visual_Barracks.prefab`
- `Assets/Art/Prefabs/Visuals/Visual_Resource_Gold.prefab`
- `Assets/Art/Prefabs/Visuals/Visual_Resource_Rock.prefab`
- `Assets/Art/Prefabs/Visuals/Visual_Resource_Tree.prefab`

Safety checks:
- No gameplay scripts added.
- No gameplay colliders in created visual-only prefabs.
- No GridManager references.
- No UnitRuntime, MatchManager, AI components.

## 5) Gameplay prefab binding (VisualRoot-only)

Updated gameplay prefabs:
- `Assets/Prefabs/Base.prefab`
  - `VisualRoot` child added: `Visual_TownCenter_Model` (MeshFilter/MeshRenderer + TownCenter mesh)
  - Legacy primitive root MeshRenderer disabled (visual-only change).
- `Assets/Prefabs/Barracks.prefab`
  - `VisualRoot` child added: `Visual_Barracks_Model` (MeshFilter/MeshRenderer + Barracks mesh)
  - Legacy primitive root MeshRenderer disabled (visual-only change).

Non-changes guaranteed:
- No changes to gameplay runtime scripts/components on roots.
- No collider changes.
- No occupancy/pathfinding semantic changes.

## 6) Worker / Heavy / Ranged status

Current status:
- `Assets/Prefabs/Worker.prefab`, `Assets/Prefabs/Heavy.prefab`, `Assets/Prefabs/Ranged.prefab` still keep placeholder visual flow (`VisualRoot` present, no model child bound in this stage).

Character mesh check:
- No obvious humanoid/worker/combatant character mesh set identified in extracted RTS FBX set suitable for blind binding in this pass.
- Character binding intentionally deferred to avoid unsafe/random mapping.

## 7) ResourceNode gameplay prefab status

- No dedicated `ResourceNode` gameplay prefab asset found by name pattern.
- Existing `Assets/Prefabs/Resource.prefab` was not converted into new gameplay semantics.
- Only visual resource prefabs were created.
- Binding of a dedicated ResourceNode gameplay prefab remains out-of-scope until a separate gameplay-side decision exists.

## 8) Owner material support (UnitVisualAnimator)

`Assets/Scripts/Presentation/UnitVisualAnimator.cs` already supports owner material mapping via:
- `player1Material`
- `player2Material`
- `neutralMaterial`

Material assets available:
- `Assets/Art/Materials/Player1_Blue.mat`
- `Assets/Art/Materials/Player2_Red.mat`
- `Assets/Art/Materials/Neutral_Resource.mat`

Note:
- If renderer arrays are not assigned in inspector for a prefab using UnitVisualAnimator, owner tint updates are skipped by design.
- Renderer references should be explicitly assigned on animator-bearing prefabs during Visual-3 character integration.

## 9) Universal Animation Library import status

Asset extracted/imported:
- `Assets/Art/Quaternius/UniversalAnimationLibrary/Unity/UAL1_Standard.fbx`

Observed importer state (from `.meta`):
- `importAnimation: 1`
- `animationType: 2` (Humanoid)
- `clipAnimations: []` (no explicit extracted clips configured yet)

Interpretation:
- FBX is imported with animation import enabled.
- No explicit extracted clip assets were created in this stage.
- Safe next step is to inspect available takes in Unity and decide whether to extract clip assets or reference clips directly from FBX.
- No Worker/Light/Heavy/Ranged animation binding was performed (intentionally deferred without confirmed humanoid mesh binding target).

## 10) Visual smoke scene / preview status

- A dedicated `Assets/Scenes/VisualPreview.unity` scene was **not** created in this pass.
- Reason: this stage prioritized zero-risk prefab/pipeline changes and avoided touching scene composition of active project flow.
- Validation was done via prefab-level binding checks and compile/console checks.

## 11) Validation results

Validation checks run:
- Unity asset refresh + compile request executed.
- Console errors/warnings query returned no entries in the final check window.
- Prefab hierarchy checks confirmed:
  - Base/Barracks now have model child under `VisualRoot`.
  - Visual-only prefabs contain only presentation components.
  - Worker/Heavy/Ranged remained unchanged structurally (no blind character binding).

## 12) Changed files (high-level)

Gameplay prefabs changed:
- `Assets/Prefabs/Base.prefab`
- `Assets/Prefabs/Barracks.prefab`

New visual-prefab assets:
- `Assets/Art/Prefabs/Visuals/Visual_Base_TownCenter.prefab`
- `Assets/Art/Prefabs/Visuals/Visual_Barracks.prefab`
- `Assets/Art/Prefabs/Visuals/Visual_Resource_Gold.prefab`
- `Assets/Art/Prefabs/Visuals/Visual_Resource_Rock.prefab`
- `Assets/Art/Prefabs/Visuals/Visual_Resource_Tree.prefab`

New extracted art content:
- `Assets/Art/Quaternius/UltimateFantasyRTS/**` (FBX + PNG + license/preview)
- `Assets/Art/Quaternius/UniversalAnimationLibrary/**` (UAL FBX + minimal companion files)

Report file:
- `VISUAL_MODEL_BINDING_REPORT.md`

## 13) Visual-3 backlog

Recommended next steps for Visual-3:
1. Create dedicated VisualPreview scene for top-down readability tuning.
2. Finalize per-prefab scale/rotation/offset after in-editor look review.
3. Select proper character asset pack (or validated humanoid meshes) for Worker/Light/Heavy/Ranged.
4. Bind UnitVisualAnimator renderer arrays/material slots on character prefabs.
5. Decide UAL clip extraction strategy (`.anim` extracted assets vs direct FBX clip references).
6. Add non-invasive smoke checklist for play mode visual regression.

## 14) Acceptance criteria mapping

- Unity project compiles: PASS (no final console errors/warnings observed in this pass).
- Play mode smoke not broken: NOT EXECUTED in this pass (no runtime script semantics changed; recommended explicit smoke run).
- Base/Barracks visually use Quaternius models: PASS (bound under `VisualRoot`).
- Resource visual prefabs created: PASS.
- Gameplay root scripts preserved: PASS.
- Gameplay colliders/occupancy unchanged: PASS.
- AI/runtime behavior unchanged: PASS by scope (no AI/runtime code touched).
- Character binding not done blindly without proper character meshes: PASS.
- `VISUAL_MODEL_BINDING_REPORT.md` created: PASS.
