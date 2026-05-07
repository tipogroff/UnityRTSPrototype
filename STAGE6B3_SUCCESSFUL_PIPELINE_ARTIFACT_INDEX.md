# STAGE6B3_SUCCESSFUL_PIPELINE_ARTIFACT_INDEX.md

## Baseline

- Name: Stage6B3_StaticHarvest_MaskedPolicy_FirstSuccessfulPipeline
- Status: FIRST_SUCCESSFUL_WORKING_PIPELINE / GO

## Core Runtime Assets

1. Final checkpoint

- python/week6_student/checkpoints/Stage6B3_SemanticObservationFix/legacy032_v2_bc_source_valid_semantic_obs_fix_final.pt

2. Final static scene

- Assets/Scenes/Week6_StudentStaticHarvestLayout.unity

3. Manual Play bootstrap

- Assets/Scripts/ML/Week6Stage6B3StaticManualPlayBootstrap.cs

## Static Masked Lifecycle Artifacts

4. Static masked lifecycle artifact dir

- python/week6_student/tmp/stage6b3_static_harvest_masked_lifecycle_validation/

5. Static lifecycle reports

- python/week6_student/tmp/stage6b3_static_harvest_masked_lifecycle_validation/stage6b3_static_harvest_masked_lifecycle_report.json
- python/week6_student/tmp/stage6b3_static_harvest_masked_lifecycle_validation/stage6b3_static_harvest_masked_lifecycle_report.md

6. Static-vs-visual comparison

- python/week6_student/tmp/stage6b3_static_harvest_masked_lifecycle_validation/stage6b3_static_vs_visual_comparison_report.json
- python/week6_student/tmp/stage6b3_static_harvest_masked_lifecycle_validation/stage6b3_static_vs_visual_comparison_report.md

## Manual Play Validation Artifacts

7. Manual Play binding validation

- python/week6_student/tmp/stage6b3_static_manual_play_binding_validation.json

8. Manual Play smoke artifact dir

- python/week6_student/tmp/stage6b3_static_manual_play_smoke/

## Dataset and Checkpoint Lineage

9. BC-ready dataset

- python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_source_valid_semantic_obs_fix_bc_ready_20260507T085607Z

10. Stage6B3 final report

- python/week6_student/reports/stage6b3_semantic_observation_fix_final_report.json

## Related Supporting Evidence

- python/week6_student/reports/stage6b3s_static_scene_playmode_validation.json
- python/week6_student/tmp/stage6b3_static_harvest_masked_lifecycle_validation/stage6b3_static_harvest_masked_lifecycle_manifest.json
- python/week6_student/tmp/stage6b3_static_harvest_masked_lifecycle_validation/stage6b3_static_harvest_masked_lifecycle_command_acceptance_histogram.json
- python/week6_student/tmp/stage6b3_static_harvest_masked_lifecycle_validation/stage6b3_static_harvest_masked_lifecycle_invalid_attempt_report.json

## Scope Guardrails

- No teacher retraining.
- No dataset rebuild.
- No student retraining.
- No PPO.
- No checkpoint changes.
- No runtime semantic changes in ActionApplier/MatchManager.
- No heuristic fallback injection.
- No claim of full Gym-Unity semantic parity.
- No claim of clean unmasked action-parameter lineage.
