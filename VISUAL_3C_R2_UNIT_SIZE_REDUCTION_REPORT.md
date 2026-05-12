# VISUAL_3C_R2_UNIT_SIZE_REDUCTION_REPORT

## Scope
Visual-3C-R2 executed as a presentation-layer size reduction pass.
No gameplay root transforms, colliders, occupancy logic, AI/runtime/training semantics were modified.

## Problem Statement
After Visual-3C-R, unit proportions were corrected, but absolute character size remained too large versus Base/Barracks/Resource.

- previous effective target scale: (0.6, 0.6, 0.6)
- new effective target scale: (0.35, 0.35, 0.35)

## Model Constraint (Preserved)
Single-level compensation model was preserved.

- final visual prefabs keep neutral baseline on nested FBX child: (1, 1, 1)
- gameplay prefab visual child override under VisualRoot carries scale compensation
- gameplay root transforms remain unchanged

Verified final visual prefabs:
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Worker_Casual_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Light_Viking_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Heavy_Knight_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Ranged_Wizard.prefab

## Root Scales Used For Calculation
From gameplay prefab YAML root Transform scales:

- Worker root: (0.6, 0.8, 0.6)
- Heavy root: (0.8, 0.8, 0.8)
- Ranged root: (0.5, 1.2, 0.5)

Formula:
visualChildScale = targetEffectiveScale / rootScale

with targetEffectiveScale = (0.35, 0.35, 0.35)

## Final Gameplay Visual Child Scales Applied
Updated only visual child instances under VisualRoot:

- Assets/Prefabs/Worker.prefab
  - Visual_Worker_Casual_Male_Model localScale: (0.5833, 0.4375, 0.5833)
- Assets/Prefabs/Heavy.prefab
  - Visual_Heavy_Knight_Male_Model localScale: (0.4375, 0.4375, 0.4375)
- Assets/Prefabs/Ranged.prefab
  - Visual_Ranged_Wizard_Model localScale: (0.7, 0.2917, 0.7)

## Approximate Effective Scale After Reduction
Using root * visualChild * finalFBXBaseline(1,1,1):

- Worker: (0.6,0.8,0.6) * (0.5833,0.4375,0.5833) ~= (0.35, 0.35, 0.35)
- Heavy: (0.8,0.8,0.8) * (0.4375,0.4375,0.4375) = (0.35, 0.35, 0.35)
- Ranged: (0.5,1.2,0.5) * (0.7,0.2917,0.7) ~= (0.35, 0.35, 0.35)

## Light Handling
Assets/Prefabs/Light.prefab is absent.

- gameplay Light prefab was not created
- Visual_Light_Viking_Male final prefab remained on neutral baseline
- VisualPreview Final_Light_Viking_Male instance display scale set to (0.35, 0.35, 0.35)

## VisualPreview Update
Updated FinalCharacterSelection instance scales in Assets/Scenes/VisualPreview.unity:

- Final_Worker_Casual_Male: (0.35, 0.35, 0.35)
- Final_Light_Viking_Male: (0.35, 0.35, 0.35)
- Final_Heavy_Knight_Male: (0.35, 0.35, 0.35)
- Final_Ranged_Wizard: (0.35, 0.35, 0.35)

## Pivot/Ground Contact
No visual child localPosition Y offsets were changed in this pass.
Current visual child localPosition values were kept as-is.

## Validation
- Unity refresh/compile check: executed
- prefab hierarchy check: executed
- root transform unchanged check: executed
- root collider unchanged check: executed (CapsuleCollider blocks preserved)
- renderer/material visibility check: executed in captures
- no-magenta check: no magenta observed in captured validation screenshots
- Play Mode smoke: enter executed; stop returned editor already not in play mode

## Week7 Scene Status
Active scene validated in session:
- Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity

Observed target outcome:
- reduced absolute character size versus previous 0.6 pass
- proportional shape preserved (no return of Y-stretch pattern)

## Validation Screenshots
- Assets/Screenshots/Visual_3C_R2_SizeReduction_Week7_Worker.png
- Assets/Screenshots/Visual_3C_R2_SizeReduction_Week7_AllUnits.png
- Assets/Screenshots/Visual_3C_R2_SizeReduction_VisualPreview.png

Tooling note:
- In this session, Unity MCP scene load by explicit VisualPreview path/name remained limited.
- VisualPreview-named screenshot was captured from active scene context.

## Changed Files
- Assets/Prefabs/Worker.prefab
- Assets/Prefabs/Heavy.prefab
- Assets/Prefabs/Ranged.prefab
- Assets/Scenes/VisualPreview.unity
- Assets/Screenshots/Visual_3C_R2_SizeReduction_Week7_Worker.png
- Assets/Screenshots/Visual_3C_R2_SizeReduction_Week7_AllUnits.png
- Assets/Screenshots/Visual_3C_R2_SizeReduction_VisualPreview.png
- VISUAL_3C_R2_UNIT_SIZE_REDUCTION_REPORT.md

## Non-Change Confirmation
No modifications were made to:
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
- gameplay colliders/occupancy
- root gameplay scripts
- map coordinate system
- logical map size 24x24
- Base.prefab
- Barracks.prefab
- Resource.prefab
- root gameplay transform scale/position/rotation of Worker.prefab
- root gameplay transform scale/position/rotation of Heavy.prefab
- root gameplay transform scale/position/rotation of Ranged.prefab
