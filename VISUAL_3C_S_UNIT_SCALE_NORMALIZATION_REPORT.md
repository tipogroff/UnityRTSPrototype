# VISUAL_3C_S_UNIT_SCALE_NORMALIZATION_REPORT

## Goal
Normalize selected unit visuals to target scale on presentation layer only.

Target scale:
- X = 0.6
- Y = 0.8
- Z = 0.6

## Final Mapping
- Worker -> Casual_Male
- Light -> Viking_Male
- Heavy -> Knight_Male
- Ranged -> Wizard

## Updated Final Visual Prefabs
Updated visible FBX child override scale in:
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Worker_Casual_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Light_Viking_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Heavy_Knight_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Ranged_Wizard.prefab

All four final visual prefabs now use child local scale (0.6, 0.8, 0.6).
Rotation was preserved (facing preserved, m_LocalRotation.y=1 on model child). Position was preserved (model child local Y=0).

## Updated Gameplay Prefab Visual Children
Updated VisualRoot child instance overrides to enforce effective visible scale (0.6, 0.8, 0.6):
- Assets/Prefabs/Worker.prefab -> Visual_Worker_Casual_Male_Model
- Assets/Prefabs/Heavy.prefab -> Visual_Heavy_Knight_Male_Model
- Assets/Prefabs/Ranged.prefab -> Visual_Ranged_Wizard_Model

No gameplay scripts/components were added.
No gameplay collider was added under visual children.

## Light Handling
- Assets/Prefabs/Light.prefab is missing.
- No gameplay Light prefab was created.
- Only final visual prefab and preview instance were scaled.

Explicit status:
Light gameplay prefab missing; only final visual prefab and preview instance were scaled.

## VisualPreview Update
Updated FinalCharacterSelection instance overrides in:
- Assets/Scenes/VisualPreview.unity

Scaled to (0.6, 0.8, 0.6):
- Final_Worker_Casual_Male
- Final_Light_Viking_Male
- Final_Heavy_Knight_Male
- Final_Ranged_Wizard

## Final Visual Child Transforms
Worker visual child:
- localScale: (0.6, 0.8, 0.6)
- localPosition: (0, 0, 0)
- localRotation: preserved (Y facing preserved)

Light visual child (final visual prefab):
- localScale: (0.6, 0.8, 0.6)
- localPosition: (0, 0, 0)
- localRotation: preserved (Y facing preserved)

Heavy visual child:
- localScale: (0.6, 0.8, 0.6)
- localPosition: (0, 0, 0)
- localRotation: preserved (Y facing preserved)

Ranged visual child:
- localScale: (0.6, 0.8, 0.6)
- localPosition: (0, 0, 0)
- localRotation: preserved (Y facing preserved)

## Root Safety Checks
- Root colliders preserved on Worker/Heavy/Ranged (CapsuleCollider still present, unchanged).
- No gameplay collider additions under visual children.
- Root transforms:
  - Heavy root unchanged: localScale (0.8, 0.8, 0.8), localPosition (0,1,0)
  - Ranged root unchanged: localScale (0.5, 1.2, 0.5), localPosition (0,1,0)
  - Worker root currently reads localScale (0.6, 0.8, 0.6) in file before this pass. This was pre-existing external drift detected at the start of Visual-3C-S; this pass did not modify Worker root transform intentionally.

## Validation
- Unity refresh + compile request executed.
- Console errors from tooling checks: none captured.
- Warnings observed were gameplay runtime warnings (no free spawn cell) from active Week7 play context, not from scale patch.
- Prefab hierarchy checks for Worker/Heavy/Ranged: PASS (VisualRoot + correct visual child present).
- Renderer/material visibility: no magenta observed in captured screenshots.
- Play Mode smoke enter/exit attempted: enter PASS; stop state confirmed by tool response.

## Validation Screenshots
- Assets/Screenshots/Visual_3C_S_FinalScale_VisualPreview.png
- Assets/Screenshots/Visual_3C_S_Week7_Gameplay_Units.png

Note: MCP scene-routing remained on Week7 active scene during capture. VisualPreview YAML instance overrides are updated in scene file; screenshot naming is kept per task.

## Changed Files
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Worker_Casual_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Light_Viking_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Heavy_Knight_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Ranged_Wizard.prefab
- Assets/Prefabs/Worker.prefab
- Assets/Prefabs/Heavy.prefab
- Assets/Prefabs/Ranged.prefab
- Assets/Scenes/VisualPreview.unity
- Assets/Screenshots/Visual_3C_S_FinalScale_VisualPreview.png
- Assets/Screenshots/Visual_3C_S_Week7_Gameplay_Units.png
- VISUAL_3C_S_UNIT_SCALE_NORMALIZATION_REPORT.md

## Non-Change Confirmation
Gameplay/AI/runtime/training semantics were not modified in this pass:
- no changes to MatchManager, ActionApplier, ActionDecoder, ActionMaskBuilder, ObservationBuilder
- no GridManager occupancy changes
- no UnitFactory/UnitRegistry semantic changes
- no ResourceManager/ResourceNode gameplay semantic changes
- no ML-Agents or Python training script changes
- no checkpoint/inference bridge/runtime command semantic changes
- no Base/Barracks/Resource prefab changes
