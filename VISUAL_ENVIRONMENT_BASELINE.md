# Visual Environment Baseline

Status: post-Visual-2T-S baseline
Date: 2026-05-12

## Core Visual Baseline

Base visual:
- TowerHouse_SecondAge

Barracks visual:
- Barracks_FirstAge_Level1

Resource visual:
- Resource_Gold_1

Ground material baseline:
- Ground_Stylized_Grass_Compatible.mat
- Shader: URP/Lit
- Primary grass texture: Grass_37_Albedo

## Week7 Scene Baseline

Active gameplay scene:
- Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity

Ground object:
- PresentationVisuals/Ground_Stylized_Grass_24x24
- Position: (11.5, -0.05, 11.5)
- Scale: (4, 1, 4)
- Collider: none
- Role: visual-only enlarged ground background

Grid overlay object:
- PresentationVisuals/Ground_Grid_Overlay_24x24
- Position: (11.5, -0.045, 11.5)
- Scale: (2.4, 1, 2.4)
- Collider: none
- Role: playable 24x24 area overlay only

Scene plane/orientation baseline:
- XZ gameplay map plane
- Y-up world

## Decorative Environment Baseline

Decorative environment props:
- rocks
- trees
- all environment decoration must remain presentation-only

## VisualPreview Baseline

VisualPreview status:
- updated
- uses the compatible non-magenta grass ground material
- remains a presentation/reference scene only

## Hard Invariants

Gameplay/AI/runtime/training modules were not modified in this visual baseline:
- MatchManager
- GridManager gameplay logic
- ActionApplier
- ActionDecoder
- ObservationBuilder
- ActionMaskBuilder
- UnitFactory
- UnitRegistry
- ML-Agents code
- Python scripts
- inference bridge code
- training/checkpoint/runtime command code

Logical map baseline:
- logical map remains 24x24
- enlarged ground background is visual-only
- grid overlay represents playable 24x24 area only

Collider / presentation rule:
- all visual objects must remain collider-free unless explicitly required by gameplay

Future visual work must not modify:
- MatchManager
- GridManager
- ActionApplier
- ActionDecoder
- ObservationBuilder
- ActionMaskBuilder
- UnitFactory
- UnitRegistry
- ML/Python/inference code

## Changed Files Summary

Current visual baseline is represented by the following visual-layer artifacts and scene files:
- Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity
- Assets/Scenes/VisualPreview.unity
- Assets/Art/Materials/Ground_Stylized_Grass_Compatible.mat
- Assets/Art/Materials/Ground_Grid_Overlay_Compatible.mat
- Assets/Art/Textures/Grid_Overlay_24x24.png
- Assets/Screenshots/visual_2t_s_week7_shader_extent_validation.png
- Assets/Screenshots/visual_2t_s_week7_final_validation.png
- Assets/Screenshots/visual_2t_s_week7_overlay_alpha_tuned.png
- Assets/Screenshots/visual_2t_s_week7_overlay_final.png
- Assets/Screenshots/visual_2t_s_week7_overlay_alpha008.png
- Assets/Screenshots/visual_2t_s_visualpreview_final_validation.png

## Related Reports

- VISUAL_2S_R_FALLBACK_RESOURCE_FIX_REPORT.md
- VISUAL_2T_R_ACTIVE_SCENE_GROUND_BINDING_REPORT.md
- VISUAL_2T_S_GROUND_SHADER_AND_EXTENT_FIX_REPORT.md

## Summary

This document defines the current approved visual environment baseline after the Visual-2T-S pass. All listed presentation objects, materials, and scene bindings are baseline-authoritative unless superseded by a later visual-only pass that preserves gameplay, AI, runtime, training, map size, and map-coordinate invariants.