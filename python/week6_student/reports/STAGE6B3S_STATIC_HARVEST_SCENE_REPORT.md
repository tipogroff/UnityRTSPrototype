# STAGE6B3S Static Harvest Scene Report

- Generated (UTC): 2026-05-06T21:21:34.2542112Z
- Scene: Assets/Scenes/Week6_StudentStaticHarvestLayout.unity
- Classification: STAGE6B3S_PASS_STATIC_SCENE_READY
- Bootstrap mode: StaticSceneRegistration
- Objects present before Play Mode: true (scene-authored objects are stored in the scene).
- Duplicate spawn prevented after Play Mode start: True
- Play Mode validation file present: True

## Coordinates

### Player1
| Name | GridPosition |
|---|---|
| P1_Resource_1 | (1,1) |
| P1_Resource_2 | (1,2) |
| P1_Worker | (2,2) |
| P1_Base | (3,3) |

### Player2 mirrored (mirrorX = 23-x, mirrorY = 23-y)
| Name | GridPosition |
|---|---|
| P2_Resource_1 | (22,22) |
| P2_Resource_2 | (22,21) |
| P2_Worker | (21,21) |
| P2_Base | (20,20) |

## Worker (2,2) Harvest Direction

- North target (2,3): valid=False, mask=False
- East target (3,2): valid=False, mask=False
- South target (2,1): valid=False, mask=False
- West target (1,2): valid=True, mask=True
- Expected valid: West / 3
- Expected invalid: East / 1
- Direction check pass: True

## Overlay Focus

- Focus worker cell = (2,2)
- Focus base cell = (3,3)
- Week6VisualInspectionRunner now auto-switches focus labels/flat-indices for Week6_StudentStaticHarvestLayout.

## Files Changed

- Assets/Scenes/Week6_StudentStaticHarvestLayout.unity
- Assets/Scripts/Gameplay/Match/MatchBootstrap.cs
- Assets/Scripts/Gameplay/Match/StaticSceneEntityAuthoring.cs
- Assets/Scripts/ML/Week6VisualInspectionRunner.cs
- Assets/Scripts/ML/Stage6B3SPlayModeValidator.cs
- Assets/Scripts/ML/Editor/Week6StudentStaticHarvestSceneMenu.cs
- python/week6_student/reports/stage6b3s_static_scene_layout_snapshot.json
- python/week6_student/reports/stage6b3s_static_harvest_scene_report.json
- python/week6_student/reports/STAGE6B3S_STATIC_HARVEST_SCENE_REPORT.md
- python/week6_student/reports/stage6b3s_static_scene_playmode_validation.json (generated after Play Mode run)

## Notes

- Runtime authoritative path remains unchanged: Policy -> ActionDecoder -> ActionApplier -> MatchManager.ApplyCommand.
- No training steps were executed by this utility.
