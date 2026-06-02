# Stage7B-6G Bridge Patch Report

Date: 2026-05-10

## Objective

Apply a small runtime-state JSON bridge patch for legacy032 without touching Stage6B3 baseline/checkpoint and without any training workflows.

## Constraints Status

- Stage6B3 baseline/checkpoint modified: no
- ML-Agents training/PPO/imitation/.demo executed: no
- Runtime state fabricated from observation: no
- Java patch style: read-only serializer over current GameState/PhysicalGameState
- Active venv wrapper patch timing: after successful patched jar build and backup

## Patched Files

- python/week5_teacher_legacy032/third_party/gym_microrts_legacy032_source/gym_microrts/microrts/src/tests/JNIGridnetClient.java
- python/week5_teacher_legacy032/third_party/gym_microrts_legacy032_source/gym_microrts/microrts/src/tests/JNIGridnetVecClient.java
- python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/envs/vec_env.py
- python/week5_teacher_legacy032/scripts/probe_legacy032_runtime_state_api_stage7b.py
- python/week5_teacher_legacy032/scripts/export_replay_ready_teacher_rollout_stage7b.py

## Build and Deployment

- Isolated patched jar:
  - python/week5_teacher_legacy032/third_party/gym_microrts_legacy032_source/build_stage7b_state_patch/microrts.jar
- Deployed runtime overlay jar:
  - python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/microrts/stage7b_state_patch.jar
- Deployment mode: overlay_jar
- Wrapper backup:
  - python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/envs/vec_env.py.stage7b6g_backup

## ABI Safety (javap)

Source: python/week5_teacher_legacy032/reports/stage7b_6g_javap_method_check.json

- No runtime public methods were removed from patched classes.
- Added methods:
  - JNIGridnetClient: getRuntimeStateJSON()
  - JNIGridnetVecClient: getRuntimeStateJSON(int), getRuntimeStateBatchJSON(), getInitialStateJSON(int)

## Runtime Probe Validation

Source: python/week5_teacher_legacy032/reports/stage7b_6g_runtime_state_probe_after_patch.json

- runtime_state_api_found: true
- info payload includes:
  - initial_state_json
  - runtime_state_t_json
  - runtime_state_tp1_json
- JSON parseability: success
- Sample parsed counts: players=2, units=8, resource_nodes=4
- Sample terminal: done=false, winner=null, reason=null

## Export Smoke Validation

Source: python/week5_teacher_legacy032/reports/stage7b_6g_export_smoke_report.json

- replay_ready: true
- contains_initial_state: true
- contains_pre_state: true
- contains_post_state: true
- validation_errors_count: 0

## Rollback Instructions

1. Remove overlay jar:
   - python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/microrts/stage7b_state_patch.jar
2. Restore wrapper from backup:
   - copy python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/envs/vec_env.py.stage7b6g_backup python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/envs/vec_env.py

## Final Status

Stage7B-6G objective achieved: small bridge runtime-state JSON patch is active, probe and replay-ready smoke both pass, and Stage6B3 baseline remains untouched.
