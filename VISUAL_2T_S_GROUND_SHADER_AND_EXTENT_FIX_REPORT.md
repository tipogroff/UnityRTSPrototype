# Visual-2T-S Ground Shader Compatibility and Background Extent Fix Report

Date: 2026-05-12
Pass: Visual-2T-S - Ground Shader Compatibility and Background Extent Fix

## 1. Render Pipeline Detection

Detected pipeline:
- Universal Render Pipeline (URP)
- Pipeline asset: Assets/Settings/PC_RPAsset.asset
- Graphics pipeline type: UniversalRenderPipelineAsset

Conclusion:
- Project is on URP, not Built-in.

## 2. Root Cause of Magenta

Magenta cause in Week7 ground was shader incompatibility:
- Previous ground shader: Standard (Built-in pipeline shader)
- Previous overlay shader: Standard (Built-in pipeline shader)
- In URP this is unsupported in current render context and leads to magenta fallback.

## 3. Shader/Material Compatibility Fix

Created compatible URP materials (without changing project pipeline settings):
- Assets/Art/Materials/Ground_Stylized_Grass_Compatible.mat
  - Shader: Universal Render Pipeline/Lit
  - Texture source: Grass_37_Albedo from package "25+ Free Stylized Textures - Grass, Ground, Floors, Walls & More"
  - Bound texture slot(s): URP BaseMap (+ MainTex compatibility mirror)
  - Base color: (0.85, 0.85, 0.80, 1)
  - Metallic: 0
  - Smoothness: 0.15
  - Tiling: 16 x 16

- Assets/Art/Materials/Ground_Grid_Overlay_Compatible.mat
  - Shader: Universal Render Pipeline/Unlit
  - Transparent surface enabled
  - Blend: Alpha, ZWrite off
  - Overlay tint alpha tuned for readability and non-obstruction

Texture assets used:
- Existing grass texture set:
  - Assets/Game Buffs/Free Stylized Textures/Textures/Grass_37/Grass_37_Albedo.png
- Additional overlay helper texture generated during pass:
  - Assets/Art/Textures/Grid_Overlay_24x24.png

## 4. Week7 Active Gameplay Scene Updates

Scene:
- Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity

Applied on visual-only objects under PresentationVisuals:

### Ground
- Object: PresentationVisuals/Ground_Stylized_Grass_24x24
- Components: Transform, MeshFilter, MeshRenderer
- Collider: none
- Gameplay scripts: none
- Material: Assets/Art/Materials/Ground_Stylized_Grass_Compatible.mat
- Final transform:
  - Position: (11.5, -0.05, 11.5)
  - Rotation: (0, 0, 0)
  - Scale: (4.0, 1.0, 4.0)
- Final visual size:
  - Unity Plane equivalent ~40 x 40 (background larger than playable 24x24)

### Grid Overlay
- Object: PresentationVisuals/Ground_Grid_Overlay_24x24
- Components: Transform, MeshFilter, MeshRenderer
- Collider: none
- Material: Assets/Art/Materials/Ground_Grid_Overlay_Compatible.mat
- Final transform:
  - Position: (11.5, -0.045, 11.5)
  - Rotation: (0, 0, 0)
  - Scale: (2.4, 1.0, 2.4)
- Final overlay size:
  - Unity Plane equivalent ~24 x 24 (kept as playable-area overlay)

## 5. Render Order and Height

Kept presentation layering:
- Ground background: Y = -0.05
- Grid overlay: Y = -0.045
- Gameplay actors remain above (Y >= 0)

No gameplay root transforms were changed.

## 6. VisualPreview Update

Scene:
- Assets/Scenes/VisualPreview.unity

Updated preview ground to same compatible non-magenta grass material:
- Object: PresentationVisuals/Ground_Stylized_Grass_24x24
- Material: Assets/Art/Materials/Ground_Stylized_Grass_Compatible.mat
- Final transform:
  - Position: (-3.0, -0.05, 3.0)
  - Rotation: (0, 0, 0)
  - Scale: (2.5, 1.0, 2.0)

Result:
- VisualPreview ground renders non-magenta with grass texture.

## 7. Validation

Validation performed:
- Opened Week7 active gameplay scene.
- Verified ground no longer magenta and grass texture visible.
- Verified background extent enlarged beyond playable field.
- Verified overlay remains constrained to playable 24x24 plane equivalent.
- Verified Base/Barracks/Resource units remain visible over ground.
- Performed Play Mode smoke (enter/exit).

Play mode notes:
- One warning observed during smoke:
  - [BuildingRuntime] No free adjacent cell near (21,21) for Worker spawn
  - This warning is runtime/gameplay behavior and not introduced by this presentation pass.

Validation screenshots:
- Assets/Screenshots/visual_2t_s_week7_shader_extent_validation.png
- Assets/Screenshots/visual_2t_s_week7_final_validation.png
- Assets/Screenshots/visual_2t_s_week7_overlay_alpha_tuned.png
- Assets/Screenshots/visual_2t_s_week7_overlay_final.png
- Assets/Screenshots/visual_2t_s_week7_overlay_alpha008.png
- Assets/Screenshots/visual_2t_s_visualpreview_final_validation.png

## 8. Changed Files

- Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity
- Assets/Scenes/VisualPreview.unity
- Assets/Art/Materials/Ground_Stylized_Grass_Compatible.mat
- Assets/Art/Materials/Ground_Stylized_Grass_Compatible.mat.meta
- Assets/Art/Materials/Ground_Grid_Overlay_Compatible.mat
- Assets/Art/Materials/Ground_Grid_Overlay_Compatible.mat.meta
- Assets/Art/Textures/Grid_Overlay_24x24.png
- Assets/Art/Textures/Grid_Overlay_24x24.png.meta
- Assets/Screenshots/visual_2t_s_week7_shader_extent_validation.png
- Assets/Screenshots/visual_2t_s_week7_final_validation.png
- Assets/Screenshots/visual_2t_s_week7_overlay_alpha_tuned.png
- Assets/Screenshots/visual_2t_s_week7_overlay_final.png
- Assets/Screenshots/visual_2t_s_week7_overlay_alpha008.png
- Assets/Screenshots/visual_2t_s_visualpreview_final_validation.png
- VISUAL_2T_S_GROUND_SHADER_AND_EXTENT_FIX_REPORT.md

## 9. Scope Guard Confirmation

Confirmed unchanged by this pass:
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
- Python scripts
- checkpoint paths
- inference bridge
- runtime command semantics
- gameplay colliders/occupancy logic
- root gameplay scripts
- map coordinate system
- logical map size 24x24

This pass only changed presentation-layer scene objects/materials/textures and produced validation artifacts.