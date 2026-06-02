# VISUAL_3D_OWNER_COLOR_READABILITY_REPORT

## Scope
Visual-3D Owner Color / Team Readability Pass was implemented as presentation-only changes.

Goals covered:
- Player1 vs Player2 visual distinction.
- Team color layer for Worker / Heavy / Ranged.
- Same approach prepared for Light visual (no Light gameplay prefab created).
- No gameplay/AI/runtime/training semantics changes.
- No breakage of Visual-3C-R2 visual scale compensation.

## Chosen Side-Differentiation Method
Selected method: visual-only team marker ring (thin cylinder disk) near unit feet.

Why this method:
- Does not recolor the entire Quaternius mesh.
- Keeps character readability and art quality.
- Is owner-dependent via material switch (Blue/Red).
- Is isolated to visual layer and does not affect occupancy/collisions/gameplay scripts.

## Team Marker Prefab
Created:
- Assets/Art/Prefabs/Visuals/Characters/TeamMarker_Ring.prefab

Properties:
- Low-profile cylinder disk (thin ring-like marker).
- Positioned close to feet level.
- Scale tuned for one tile readability.
- Components: Transform, MeshFilter, MeshRenderer.
- No collider, no Rigidbody, no gameplay scripts.
- Default material: Player1_Blue (runtime owner sync may override).

## Materials (Owner Colors)
Checked existing materials:
- Assets/Art/Materials/Player1_Blue.mat
- Assets/Art/Materials/Player2_Red.mat
- Assets/Art/Materials/Neutral_Resource.mat

Result:
- Existing owner materials are already URP-compatible (no magenta-inducing legacy shader mismatch detected in current pass).
- Compatible duplicates were not needed.

## Gameplay Prefabs Updated
Updated:
- Assets/Prefabs/Worker.prefab
- Assets/Prefabs/Heavy.prefab
- Assets/Prefabs/Ranged.prefab

For each prefab:
- Added TeamMarker_Ring under VisualRoot.
- Marker local transform kept visual-only and independent from character model scale compensation.
- Marker collider removed (no gameplay collision/occupancy participation).
- Root transform values preserved.
- Root collider preserved.
- Root placeholder MeshRenderer remained disabled.

## Owner Color Sync Logic
Reused existing presentation path:
- Assets/Scripts/Presentation/UnitVisualAnimator.cs (already had SetOwnerVisual(owner)).
- Assets/Scripts/Presentation/VisualEventBridge.cs (already had initial owner sync from UnitRuntime.Owner in Start).

Wiring added on Worker/Heavy/Ranged prefab roots:
- UnitVisualAnimator component attached.
- VisualEventBridge component attached.
- UnitVisualAnimator.materialRenderers points to TeamMarker_Ring renderer.
- UnitVisualAnimator materials wired:
  - Player1 -> Assets/Art/Materials/Player1_Blue.mat
  - Player2 -> Assets/Art/Materials/Player2_Red.mat
  - Neutral -> Assets/Art/Materials/Neutral_Resource.mat
- VisualEventBridge.unitVisualAnimator linked.
- unitRuntime left null-safe (resolved via GetComponent at runtime as designed).

Behavior note:
- This path remains presentation-only and does not mutate owner, HP, resources, grid position, command path, AI decisions, or runtime semantics.

## Light Status
Gameplay Light prefab status:
- Assets/Prefabs/Light.prefab is missing (intentionally not created).

Applied for visual layer:
- Added TeamMarker_Ring to final light visual prefab:
  - Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Light_Viking_Male.prefab
- In VisualPreview, Light is included in both Player1/Player2 rows with corresponding marker color.

## VisualPreview Update
Updated scene:
- Assets/Scenes/VisualPreview.unity

What changed:
- Kept original FinalCharacterSelection as Player1 row (blue markers).
- Added duplicated row: FinalCharacterSelection_Player2 (red markers).
- Added marker rings for Worker/Heavy/Ranged preview instances and colored by row.
- Light markers present in both rows.

## Week7 Scene Validation
Target scene:
- Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity

Checks performed:
- Scene load and screenshot validation.
- Play Mode smoke enter/exit executed.
- No gameplay scripts/colliders added to markers.
- Owner-color presentation pipeline prepared on unit prefabs for runtime owner sync.

## Validation Summary
- Unity compile/refresh: prefab/scene updates applied successfully.
- Root transform unchanged check:
  - Worker root scale remains (0.6, 0.8, 0.6).
  - Heavy root scale remains (0.8, 0.8, 0.8).
  - Ranged root scale remains (0.5, 1.2, 0.5).
- Root collider unchanged check:
  - Worker/Heavy/Ranged root CapsuleCollider preserved.
- Marker collider check:
  - TeamMarker_Ring under Worker/Heavy/Ranged has no CapsuleCollider.
- No gameplay collider under marker check: passed for updated unit prefabs.
- No gameplay script on marker check: passed.
- No magenta check: screenshots show expected non-magenta materials in this pass.
- Play Mode smoke: enter/exit done.

Console note:
- One non-gameplay warning observed from MCP transport layer:
  - "[WebSocket] Unexpected receive error: WebSocket is not initialised"
  - This is tooling/session transport noise, not project gameplay logic.

## Validation Screenshots
Created:
- Assets/Screenshots/Visual_3D_OwnerColors_VisualPreview.png
- Assets/Screenshots/Visual_3D_OwnerColors_Week7_Player1_Player2.png
- Assets/Screenshots/Visual_3D_OwnerColors_Closeup.png

## Changed Files
- Assets/Art/Prefabs/Visuals/Characters/TeamMarker_Ring.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Light_Viking_Male.prefab
- Assets/Prefabs/Worker.prefab
- Assets/Prefabs/Heavy.prefab
- Assets/Prefabs/Ranged.prefab
- Assets/Scenes/VisualPreview.unity
- Assets/Screenshots/Visual_3D_OwnerColors_VisualPreview.png
- Assets/Screenshots/Visual_3D_OwnerColors_Week7_Player1_Player2.png
- Assets/Screenshots/Visual_3D_OwnerColors_Closeup.png
- VISUAL_3D_OWNER_COLOR_READABILITY_REPORT.md

## Non-Changed (Guardrail Confirmation)
Not modified in this pass:
- MatchManager
- ActionApplier
- ActionDecoder
- ActionMaskBuilder
- ObservationBuilder
- GridManager occupancy logic
- UnitFactory spawn semantics
- UnitRegistry registration semantics
- ResourceManager / ResourceNode gameplay semantics
- ML-Agents training code
- Python BC/PPO/training scripts
- checkpoint paths
- inference bridge
- runtime command semantics
- gameplay colliders/occupancy semantics
- map coordinate system
- logical map size 24x24
- Base.prefab / Barracks.prefab / Resource.prefab

## Acceptance Criteria Check
- Player1 and Player2 units are visually distinguishable: PASS.
- Worker/Heavy/Ranged have team marker/color under VisualRoot: PASS.
- Marker has no collider/gameplay scripts in updated gameplay prefabs: PASS.
- Root transforms/colliders unchanged: PASS.
- Visual child scale compensation from Visual-3C-R2 not broken: PASS.
- Gameplay/AI/runtime/training behavior not changed by this pass: PASS (presentation-only modifications).
- VisualPreview shows owner color readability (two rows): PASS.
- VISUAL_3D_OWNER_COLOR_READABILITY_REPORT.md created: PASS.
