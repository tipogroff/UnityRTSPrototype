# Stage7B-6E Bridge Patch Plan Report

- generated_at_utc: 2026-05-10T02:22:00Z
- decision: CONDITIONAL_GO

## Required booleans

- java_source_found: false
- active_python_wrapper_found: true
- build_path_found: true
- game_state_access_likely: true

## Go/No-Go

- Immediate large patch from current installed package: NO-GO
- Controlled patch after obtaining bridge source tree: GO

## Why game-state access appears possible

javap signatures confirm:
- tests.JNIGridnetClient exposes internal fields gs (GameState) and pgs (PhysicalGameState)
- rts.GameState/PhysicalGameState/Unit/Player expose getters needed for serialization

So authoritative runtime snapshot can likely be serialized in bridge layer without changing core engine semantics.

## Patch scope

- patch_scope: java_bridge_only
- estimated_risk: medium
- recommended_next_step: fetch_original_gym_microrts_source

## Exact files to patch (if GO)

Java:
- microrts/src/tests/JNIGridnetClient.java
- microrts/src/tests/JNIGridnetVecClient.java

Python wrapper:
- python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/envs/vec_env.py

Exporter:
- python/week5_teacher_legacy032/scripts/export_replay_ready_teacher_rollout_stage7b.py

## Exact methods to add

Java side:
- JNIGridnetClient:
  - public String getRuntimeStateJSON()
- JNIGridnetVecClient:
  - public String getRuntimeStateJSON(int envIdx)
  - public String[] getRuntimeStateBatchJSON()
  - public String getInitialStateJSON(int envIdx) (optional)

Python side:
- get_runtime_state_json(self, env_index=0)
- get_runtime_state_batch_json(self)
- reset(): persist initial_state_json
- step_wait(): capture runtime_state_t_json before gameStep
- step_wait(): capture runtime_state_tp1_json after gameStep
- infos[i] should carry all three fields

## Validation plan after patch

1. Run probe again:
   - python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week5_teacher_legacy032/scripts/probe_legacy032_runtime_state_api_stage7b.py
2. Expect runtime API visibility.
3. Run smoke export:
   - python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week5_teacher_legacy032/scripts/export_replay_ready_teacher_rollout_stage7b.py --episodes 1 --max-steps-per-episode 64
4. Expect:
   - contains_initial_state=true
   - contains_pre_state=true
   - contains_post_state=true
   - replay_ready=true
5. Rerun Stage7B-6B Prep and confirm state_sync attempt with non-null candidate stats.

## Rollback

- Restore original vec_env.py.
- Restore original microrts.jar (or remove overlay patch jar).
- Re-run probe/export smoke and confirm pre-patch behavior.
