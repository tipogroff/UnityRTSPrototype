# FIRST_SUCCESSFUL_PIPELINE_BASELINE.md

## Baseline Identity

- Baseline name: Stage6B3_StaticHarvest_MaskedPolicy_FirstSuccessfulPipeline
- Status: FIRST_SUCCESSFUL_WORKING_PIPELINE
- Decision: GO
- Freeze date: 2026-05-08

## Final Components (Frozen)

- Final scene: Assets/Scenes/Week6_StudentStaticHarvestLayout.unity
- Final checkpoint: python/week6_student/checkpoints/Stage6B3_SemanticObservationFix/legacy032_v2_bc_source_valid_semantic_obs_fix_final.pt
- Student lineage evidence: python/week6_student/reports/stage6b3_semantic_observation_fix_final_report.json
- BC-ready dataset: python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_source_valid_semantic_obs_fix_bc_ready_20260507T085607Z
- Semantic adapter implementation path: python/week6_student/student_inference_adapter.py
- Semantic adapter rebuild/audit path: python/week6_student/stage10d6_run_semantic_adapter_rebuild.py
- Manual Play bootstrap: Assets/Scripts/ML/Week6Stage6B3StaticManualPlayBootstrap.cs
- Lifecycle artifacts (static masked): python/week6_student/tmp/stage6b3_static_harvest_masked_lifecycle_validation/

## Exact Final Runtime Configuration

- Stage6B3 final checkpoint is bound at runtime.
- Legal parameter-level mask is enabled.
- Auto start on Play is enabled for the visual runner path in final static scene.
- Fallback is disabled.
- Heuristic fallback is disabled.
- Fake logits are disabled.
- Static scene registration mode is used for authored entities.
- Authored scene objects are preserved before and after Play Mode start.
- No duplicate spawn after Play Mode start: true.

## Successful Validation Evidence

### Static lifecycle run

- Artifact dir: python/week6_student/tmp/stage6b3_static_harvest_masked_lifecycle_validation/
- Main report JSON: stage6b3_static_harvest_masked_lifecycle_report.json
- Main report MD: stage6b3_static_harvest_masked_lifecycle_report.md
- Manifest: stage6b3_static_harvest_masked_lifecycle_manifest.json

Confirmed in report:

- Scene: Week6_StudentStaticHarvestLayout
- Checkpoint: Stage6B3 final
- checkpoint_exists: true
- checkpoint_loaded: true
- legal_parameter_mask_enabled: true
- fallback_used: false
- heuristic_used: false
- fake_logits_used: false
- offline-vs-Unity parity prediction_mismatches: 0
- policy_non_noop_on_actor_cells: 320

Accepted command histogram (new static baseline):

- Move: 5
- Harvest: 11
- Return: 5
- Produce: 25
- Attack: 1
- NoOp: 0 accepted submissions

Invalid attempts:

- invalid_attempt_log_count: 0
- ActionApplier invalid attempt spam: absent

### Manual Play binding validation

- JSON: python/week6_student/tmp/stage6b3_static_manual_play_binding_validation.json

Confirmed:

- scene_matches_expected: true
- runner_found/enabled: true/true
- adapter_found/enabled: true/true
- checkpoint_exists: true
- legal_parameter_mask_enabled: true
- fallback_used: false
- heuristic_used: false
- fake_logits_used: false
- decision_loop: Week6VisualInspectionRunner_auto_playback

### Static-vs-visual comparison

- JSON: python/week6_student/tmp/stage6b3_static_harvest_masked_lifecycle_validation/stage6b3_static_vs_visual_comparison_report.json
- MD: python/week6_student/tmp/stage6b3_static_harvest_masked_lifecycle_validation/stage6b3_static_vs_visual_comparison_report.md

Confirmed:

- supports_stage6b3_static_demo_baseline: true
- same checkpoint binding: true
- parity_prediction_mismatches (new static): 0
- new non-NoOp present: true
- new harvest accepted: true
- new produce accepted: true
- new no invalid attempt spam: true

## What This Baseline Proves

- Student policy is integrated into Unity runtime path.
- Policy emits meaningful non-NoOp actions on actor cells.
- Action pipeline reaches decoder, applier, and runtime command submission.
- Runtime state changes occur (resource carrying, movement, production, combat-related events).
- Static authored scene functions in normal Unity Play Mode.
- Manual Play Mode idle issue is fixed via stale Stage6B2 binding replacement and manual bootstrap enforcement.

## What This Baseline Does NOT Prove

- It does not prove full Gym-Unity semantic parity.
- It does not claim direct checkpoint weight transfer equivalence.
- It does not claim that unmasked action-parameter lineage is fully clean.
- Parameter masking is a runtime mitigation/stabilization layer, not a proof that parameter labels are globally clean.
- Future clean-lineage claims still require explicit action-label remap and/or Unity geometry alignment evidence.

## No-Regression Checklist (Mandatory Before Further Changes)

Before changing anything after this baseline:

- Confirm current branch and working tree status.
- Preserve final checkpoint file and path unchanged.
- Preserve final static scene unchanged.
- Preserve manual Play bootstrap component and script.
- Run manual Play binding validation.
- Run short static lifecycle smoke.
- Verify fallback_used=false and heuristic_used=false.
- Verify prediction_mismatches=0 for parity check.
- Verify accepted Harvest and Produce commands are present.
- Verify invalid attempts remain 0.

## Suggested Git Metadata (Documentation Only)

- Suggested tag: stage6b3-first-successful-static-pipeline
- Suggested branch: baseline/stage6b3-static-masked-success

## Final Statement

This baseline is frozen as the first successful working Unity transfer pipeline.

This statement does NOT imply full Gym-Unity semantic parity and does NOT imply clean unmasked action-parameter lineage.
