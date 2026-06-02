# VISUAL_3C_R_UNIT_PROPORTION_REPAIR_REPORT

## Scope
Visual-3C-R repair-pass executed on presentation layer only.
No gameplay/AI/runtime/training semantics were modified.

## Problem Summary
Visual stretching came from multiplicative non-uniform scaling chain:
- gameplay root scale (non-uniform per unit), multiplied by
- gameplay visual child override scale, multiplied by
- nested final visual FBX child scale.

After Visual-3C-S, both gameplay visual child and final FBX child carried non-uniform Y-heavy values, causing compounded Y/XZ distortion.

## Diagnostic (Before Repair)
Chain measured from prefab YAML:
root -> VisualRoot -> Visual_*_Model instance override -> final wrapper -> nested FBX child override.

### Worker
- root scale: (0.6, 0.8, 0.6)
- VisualRoot scale: (1, 1, 1)
- gameplay visual child scale before repair: (0.6, 0.8, 0.6)
- final FBX child scale before repair: (0.6, 0.8, 0.6)
- approximate effective before: (0.216, 0.512, 0.216)

### Heavy
- root scale: (0.8, 0.8, 0.8)
- VisualRoot scale: (1, 1, 1)
- gameplay visual child scale before repair: (0.6, 0.8, 0.6)
- final FBX child scale before repair: (0.6, 0.8, 0.6)
- approximate effective before: (0.288, 0.512, 0.288)
- distortion source: Y significantly larger than X/Z.

### Ranged
- root scale: (0.5, 1.2, 0.5)
- VisualRoot scale: (1, 1, 1)
- gameplay visual child scale before repair: (0.6, 0.8, 0.6)
- final FBX child scale before repair: (0.6, 0.8, 0.6)
- approximate effective before: (0.18, 0.768, 0.18)
- distortion source: strong Y amplification from root and child stack.

## Repair Strategy
Chosen single-level compensation model (to avoid double-compensation):
- final visual prefabs reset to neutral uniform baseline on nested FBX child scale: (1, 1, 1)
- gameplay prefab visual child instance overrides carry per-root compensation
- target effective for gameplay visuals: near-uniform approx (0.6, 0.6, 0.6)

## Final Scales Applied
### Final visual prefabs (nested FBX child)
Updated to baseline uniform:
- Visual_Worker_Casual_Male.prefab -> (1, 1, 1)
- Visual_Light_Viking_Male.prefab -> (1, 1, 1)
- Visual_Heavy_Knight_Male.prefab -> (1, 1, 1)
- Visual_Ranged_Wizard.prefab -> (1, 1, 1)

### Gameplay prefab visual child instance overrides
- Worker visual child: (1.0, 0.75, 1.0)
- Heavy visual child: (0.75, 0.75, 0.75)
- Ranged visual child: (1.2, 0.5, 1.2)

### Approximate effective after repair
- Worker: root (0.6,0.8,0.6) * child (1.0,0.75,1.0) * final(1,1,1) -> (0.6, 0.6, 0.6)
- Heavy: 0.8 * 0.75 * 1 -> (0.6, 0.6, 0.6)
- Ranged: (0.5,1.2,0.5) * (1.2,0.5,1.2) * 1 -> (0.6, 0.6, 0.6)

## Light Handling
- Assets/Prefabs/Light.prefab is still missing.
- No gameplay Light prefab created.
- Final Light visual kept uniform (baseline 1,1,1 at final FBX child), with VisualPreview instance kept uniform display scale.

## VisualPreview Update
FinalCharacterSelection instance scales set to uniform display scale:
- Final_Worker_Casual_Male: (0.6, 0.6, 0.6)
- Final_Light_Viking_Male: (0.6, 0.6, 0.6)
- Final_Heavy_Knight_Male: (0.6, 0.6, 0.6)
- Final_Ranged_Wizard: (0.6, 0.6, 0.6)

## Root/Collider Safety
Root transforms intentionally not edited in this repair-pass.
- Heavy root unchanged
- Ranged root unchanged
- Worker root retained as-is (0.6, 0.8, 0.6)

Colliders:
- root colliders preserved on Worker/Heavy/Ranged
- no new gameplay colliders under visual children
- no occupancy logic changes

## Validation
- Unity refresh/compile check: executed
- prefab hierarchy check: executed for Worker/Heavy/Ranged and final prefabs
- renderer/material visibility: no magenta observed in available captures
- Play Mode smoke: enter/exit executed

### Screenshot artifacts
- Assets/Screenshots/Visual_3C_R_ProportionRepair_VisualPreview.png
- Assets/Screenshots/Visual_3C_R_ProportionRepair_Week7_Worker.png
- Assets/Screenshots/Visual_3C_R_ProportionRepair_Week7_AllUnits.png

Tooling limitation note:
- Unity MCP `manage_scene load` could not load `Assets/Scenes/VisualPreview.unity` by path in this session (only Build Settings scenes exposed), so the VisualPreview-named screenshot was captured from active scene context.

## Changed Files
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Worker_Casual_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Light_Viking_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Heavy_Knight_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Ranged_Wizard.prefab
- Assets/Prefabs/Worker.prefab
- Assets/Prefabs/Heavy.prefab
- Assets/Prefabs/Ranged.prefab
- Assets/Scenes/VisualPreview.unity
- Assets/Screenshots/Visual_3C_R_ProportionRepair_VisualPreview.png
- Assets/Screenshots/Visual_3C_R_ProportionRepair_Week7_Worker.png
- Assets/Screenshots/Visual_3C_R_ProportionRepair_Week7_AllUnits.png
- VISUAL_3C_R_UNIT_PROPORTION_REPAIR_REPORT.md

## Non-change Confirmation
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
- map coordinate system / logical map size 24x24
- Base.prefab
- Barracks.prefab
- Resource.prefab
