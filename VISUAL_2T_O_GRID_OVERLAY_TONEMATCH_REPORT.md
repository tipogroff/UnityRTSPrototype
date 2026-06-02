# Visual-2T-O Grid Overlay Tone Match Fix Report

Date: 2026-05-12
Scene: Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity
Task: Reduce playable-area tone mismatch while preserving 24x24 grid readability, presentation layer only.

## Scope and Safety
- Changed only presentation-layer overlay material settings.
- No gameplay/AI/runtime scripts modified.
- No ML-Agents training code, Python, checkpoints, inference bridge, or map semantics modified.

## Task 1: Overlay Material Audit (Before)
Material: Assets/Art/Materials/Ground_Grid_Overlay_Compatible.mat
- Shader: Universal Render Pipeline/Unlit
- Surface mode: Transparent (_Surface = 1)
- Base map texture: null
- Base color/tint: RGBA (1.00, 1.00, 1.00, 0.08)
- Overlay effect assessment: texture was not assigned, causing a broad transparent tone layer that made the 24x24 area read as a separate light panel.

Reference ground material for comparison:
- Assets/Art/Materials/Ground_Stylized_Grass_Compatible.mat
- Shader: Universal Render Pipeline/Lit
- Base color: RGBA (0.85, 0.85, 0.80, 1.00)
- Main texture: Grass_37_Albedo

## Task 2: Overlay Visibility Reduction (Applied)
Material updated: Assets/Art/Materials/Ground_Grid_Overlay_Compatible.mat

Applied changes:
- Assigned overlay texture:
  - _BaseMap = Grid_Overlay_24x24 (Assets/Art/Textures/Grid_Overlay_24x24.png)
  - _MainTex = Grid_Overlay_24x24 (Assets/Art/Textures/Grid_Overlay_24x24.png)
- Updated tint/alpha to muted dark green-gray:
  - _BaseColor = RGBA (0.42, 0.48, 0.42, 0.09)
  - _Color = RGBA (0.42, 0.48, 0.42, 0.09)

Rationale:
- Keeps overlay transparent and low-contrast.
- Reduces bright/gray slab appearance in playable area.
- Preserves subtle grid readability through line texture + low alpha.

## Task 3: Tone Match vs Ground
Comparison outcome:
- Playable center now visually blends with surrounding stylized grass more closely.
- Prior panel-like tone separation is significantly reduced.
- Grid remains visible but subdued (non-contrasty).

## Task 4: Week7 Scene Validation
Validated in:
- Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity

Visual checks:
- Boundary between playable area and background is less pronounced.
- Base/Barracks/resources/units remain readable on background.
- No gameplay component or logical map-size changes performed.

## Task 5: VisualPreview Check
Search result:
- Compatible overlay material GUID usage was found in Week7 scene only.
- No VisualPreview scene binding to this compatible overlay material was detected.

Action:
- No VisualPreview update required for this specific compatible overlay pass.

## Task 6: Validation Screenshots
Captured screenshots:
- Assets/Screenshots/Visual_2T_O_before.png
- Assets/Screenshots/Visual_2T_O_validation_01_top.png
- Assets/Screenshots/Visual_2T_O_validation_02_midheight.png
- Assets/Screenshots/Visual_2T_O_validation_03_oblique.png

Optional intermediate captures:
- Assets/Screenshots/Visual_2T_O_after_top.png
- Assets/Screenshots/Visual_2T_O_after_zoom.png

## Final Parameters
- Final alpha: 0.09
- Final tint color: RGB (0.42, 0.48, 0.42)
- Final shader: Universal Render Pipeline/Unlit (Transparent surface)
- Overlay texture changed: Yes (assigned existing Grid_Overlay_24x24.png)

## Changed Files
- Assets/Art/Materials/Ground_Grid_Overlay_Compatible.mat
- VISUAL_2T_O_GRID_OVERLAY_TONEMATCH_REPORT.md
- Assets/Screenshots/Visual_2T_O_before.png
- Assets/Screenshots/Visual_2T_O_validation_01_top.png
- Assets/Screenshots/Visual_2T_O_validation_02_midheight.png
- Assets/Screenshots/Visual_2T_O_validation_03_oblique.png
- Assets/Screenshots/Visual_2T_O_after_top.png
- Assets/Screenshots/Visual_2T_O_after_zoom.png

## Acceptance Criteria Status
- Playable area 24x24 less different in tone from background ground: PASS
- Grid lines remain readable: PASS (subtle, low-contrast)
- Overlay no longer reads as separate light/gray backing: PASS
- Gameplay/AI/runtime behavior changed: NO
- VISUAL_2T_O_GRID_OVERLAY_TONEMATCH_REPORT.md created: PASS
