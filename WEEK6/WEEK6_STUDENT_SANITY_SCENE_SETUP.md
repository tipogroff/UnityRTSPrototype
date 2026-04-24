# Week 6 Student Sanity Scene Setup

## Safe sanity scene
- `Assets/Scenes/Week6_StudentSanity.unity`

## Visual inspection scene
- `Assets/Scenes/Week6_StudentVisualInspection.unity`

## Included root objects/components
- `GridManager` (`RTS.Gameplay.GridManager`)
- `MatchManager` (`RTS.Gameplay.MatchManager`)
- `MatchBootstrap` (`RTS.Gameplay.MatchBootstrap`)
- `UnitRegistry` (`RTS.Gameplay.UnitRegistry`)
- `ResourceManager` (`RTS.Gameplay.ResourceManager`)
- `EpisodeController` (`RTS.Gameplay.EpisodeController`)
- `VictoryResolver` (`RTS.Gameplay.VictoryResolver`)
- `HeuristicDriver` (`RTS.Gameplay.HeuristicDriver`)
- `HeuristicPolicyAdapter` (`RTS.ML.HeuristicPolicyAdapter`)
- `Week6StudentPolicyAdapter` (`RTS.ML.Week6StudentPolicyAdapter`)
- `Week6Day5SanityMatchRunner` (`RTS.ML.Week6Day5SanityMatchRunner`)
- `Main Camera`
- `Directional Light`

## Visual scene runner/component delta
- `Week6_StudentSanity.unity`: keeps `Week6Day5SanityMatchRunner` for bounded technical checks.
- `Week6_StudentVisualInspection.unity`: uses `Week6VisualInspectionRunner` (`RTS.ML.Week6VisualInspectionRunner`) with explicit visual start entrypoint.

## Removed from this scene (legacy/non-essential)
- `ManualStepController`
- `SmokeTestRunner_BHR` (`BarracksHeavyRangedSmokeTest`)
- Static debug `Resource` object
- Static scene prefab instances `Base` and `Worker`

## Scene-local safe defaults
- `EpisodeController._autoStartOnPlay = false`
- `EpisodeController._autoStepInFixedUpdate = false`
- `EpisodeController._enableWeek6StudentMatchControl = false`
- `EpisodeController._player1DecisionMode = StudentInference`
- `EpisodeController._player2DecisionMode = HeuristicBaseline`
- `MatchManager._logStepEvents = false`
- `Week6Day5SanityMatchRunner._episodeCount = 1`
- `Week6Day5SanityMatchRunner._maxStepsPerEpisode = 200`
- `Week6Day5SanityMatchRunner._maxDecisionSubmissionsPerEpisode = 200`
- `Week6Day5SanityMatchRunner._studentControlledPlayer = Player1`

## Canonical path preserved
- `ObservationBuilder -> student inference bridge -> MlPolicyPipelineFacade -> ActionDecoder -> ActionApplier -> MatchManager.ApplyCommand`

## Visual inspection defaults
- `EpisodeController._autoStartOnPlay = false` (explicit manual start)
- `EpisodeController._autoStepInFixedUpdate = true` (observable realtime stepping)
- `EpisodeController._enableWeek6StudentMatchControl = true`
- `EpisodeController._player1DecisionMode = StudentInference`
- `EpisodeController._player2DecisionMode = HeuristicBaseline`
- `EpisodeController._autoRestartEpisodes = false` (final state remains until manual restart)
- `Week6VisualInspectionRunner._showOverlay = true`

## How to start visual inspection match
- Open `Assets/Scenes/Week6_StudentVisualInspection.unity`.
- Enter Play Mode.
- On `Week6VisualInspectionRunner`, invoke `Start Visual Inspection Match` from component context menu.
- Use `Restart Visual Inspection Match` when you need a manual rerun.

## Visual diagnostics (minimal)
- student-controlled side and baseline side
- checkpoint path currently wired in `Week6StudentPolicyAdapter`
- student decision requests (`sent/succeeded/failed`)
- student accepted/invalid command counters
- runtime rejected command counter for student side
- last terminal reason

## Manual inspector verification before first run
- Confirm `EpisodeController` references:
  - `_heuristicPolicyAdapter` -> scene `HeuristicPolicyAdapter`
  - `_week6StudentPolicyAdapter` -> scene `Week6StudentPolicyAdapter`
- Confirm `Week6StudentPolicyAdapter` paths are valid in your workspace:
  - `.venv/Scripts/python.exe`
  - `python/week6_student/student_inference_server.py`
  - `python/week6_student/runs/day3_transfer_bc_main_20260423/student_bc_transfer_best.pt`
- Confirm `Week6Day5SanityMatchRunner` is used as explicit entrypoint (ContextMenu/explicit call), not automatic Play startup.
