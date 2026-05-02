# LEGACY032 UNITY V2 SCENE PREP REPORT

## 1) Scope
- scene prep only
- no Unity match
- no BC training
- no PPO
- no teacher training
- no dataset modification
- no checkpoint modification

## 2) Scene
- scene name: Week 6_student Visual Inspection
- scene path: Assets/Scenes/Week6_StudentVisualInspection.unity
- original scene modified or copy created: original scene modified (no scene duplication)
- authoritative initial placement source:
  - runtime procedural spawn in Assets/Scripts/Gameplay/Match/MatchBootstrap.cs
  - active preset in scene: _scenarioPreset = Week6StudentMicroRtsMirror24x24 (enum value 4)
  - scene hierarchy does not store pre-placed UnitRuntime start objects; placement is authoritative in MatchBootstrap preset logic

## 3) Grid coordinate mapping
- Unity grid convention in project:
  - GridPosition.X maps to world X
  - GridPosition.Y maps to world Z
  - world conversion: (x, y) -> (x * CellSize, 0, y * CellSize)
  - evidence: Assets/Scripts/Gameplay/Grid/GridPosition.cs
- logical mapping used for this scene prep:
  - columns A..X -> x = 0..23
  - rows 1..24 (top-to-bottom notation) -> y = 0..23
  - therefore A1=(0,0), X24=(23,23)
- mirror rule used:
  - (x, y) -> (23 - x, 23 - y)

## 4) Final placement table

| Object | Owner | Logical cell | GridPosition | Prefab/definition used |
|---|---|---|---|---|
| Resource | Neutral | A1 | (0,0) | UnitDef_Resource (Assets/ML/UnitDefs/UnitDef_Resource.asset) -> Assets/Prefabs/Resource.prefab |
| Resource | Neutral | B1 | (1,0) | UnitDef_Resource (Assets/ML/UnitDefs/UnitDef_Resource.asset) -> Assets/Prefabs/Resource.prefab |
| Worker | Player1 | B2 | (1,1) | UnitDef_Worker (Assets/ML/UnitDefs/UnitDef_Worker.asset) -> Assets/Prefabs/Worker.prefab |
| Base | Player1 | C3 | (2,2) | UnitDef_Base (Assets/ML/UnitDefs/UnitDef_Base.asset) -> Assets/Prefabs/Base.prefab |
| Resource | Neutral | X24 | (23,23) | UnitDef_Resource (Assets/ML/UnitDefs/UnitDef_Resource.asset) -> Assets/Prefabs/Resource.prefab |
| Resource | Neutral | W24 | (22,23) | UnitDef_Resource (Assets/ML/UnitDefs/UnitDef_Resource.asset) -> Assets/Prefabs/Resource.prefab |
| Worker | Player2 | W23 | (22,22) | UnitDef_Worker (Assets/ML/UnitDefs/UnitDef_Worker.asset) -> Assets/Prefabs/Worker.prefab |
| Base | Player2 | V22 | (21,21) | UnitDef_Base (Assets/ML/UnitDefs/UnitDef_Base.asset) -> Assets/Prefabs/Base.prefab |

## 5) Scene safety checks
- map size 24x24: PASS
  - source: Assets/ML/GameConfig_MVP.asset (mapWidth=24, mapHeight=24)
- no duplicate/overlapping occupancy in target placement set: PASS (8 unique cells for 8 objects)
- no old layout objects remaining in saved scene hierarchy: PASS
  - startup units/resources are spawned at runtime by MatchBootstrap preset; no conflicting pre-placed UnitRuntime objects detected in scene YAML
- no conflicting active runners: PASS (static scene scan)
  - no Week4/legacy smoke autorun components detected as active scene objects
- no simultaneous student+baseline control for same player: PASS (configured split control path)
  - Week6 control modes in EpisodeController remain Player1=StudentInference, Player2=HeuristicBaseline
- inspector references valid (static wiring): PASS
  - scene references for GridManager/MatchManager/MatchBootstrap/UnitRegistry/ResourceManager are present
- checkpoint path not changed unless explicitly required: PASS
  - remains: python/week6_student/runs/day3_transfer_bc_main_20260423/student_bc_transfer_best.pt
  - this scene prep did not change checkpoint wiring
- ActionApplier/MatchManager unchanged: PASS
  - no edits were made to Assets/Scripts/ML/ActionApplier.cs
  - no edits were made to Assets/Scripts/Gameplay/Match/MatchManager.cs
- controlled-run safety improvement: PASS
  - Week6VisualInspectionRunner._autoStartOnPlay changed to false for safer manual dry-run control in next stage

## 6) Files changed
- Assets/Scripts/Gameplay/Match/MatchBootstrap.cs
- Assets/Scenes/Week6_StudentVisualInspection.unity
- python/week6_student/scripts/validate_week6_scene_prep.py
- python/week6_student/reports/LEGACY032_UNITY_V2_SCENE_PREP_VALIDATION.json
- python/week6_student/reports/LEGACY032_UNITY_V2_SCENE_PREP_REPORT.md

## 7) Remaining risks
- scene Inspector wiring still needs actual Play Mode dry-run later
- visual placement does not prove inference correctness
- scene prep does not prove behavior quality
- Unity runtime semantic drift still must be checked in Stage 10/11

## 8) Decision
GO_FOR_UNITY_SCENE_DRY_RUN
