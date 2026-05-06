# STAGE5P0 Small Fixes Report

Date: 2026-05-06
Author: GitHub Copilot

## 1. Executive summary
Stage5P0 follow-up fixes were applied to align the Legacy032 raw exporter with the existing Unity v2 adapter input contract while preserving the training-compatible action stepping path as the final export/evidence mode.

Final classification: STAGE5P0_TRANSFER_PIPELINE_READY

## 2. Files changed
- python/week5_teacher_legacy032/scripts/export_teacher_rollout_legacy032.py
- python/week5_teacher_legacy032/reports/LEGACY032_ROLLOUT_EXPORT_RUNBOOK.md
- python/week5_teacher_legacy032/reports/LEGACY032_WEEK5_PIPELINE_COMPATIBILITY_AUDIT.md
- python/week5_teacher_legacy032/reports/STAGE5P0_EXISTING_TRANSFER_PIPELINE_AUDIT.md
- python/week5_teacher_legacy032/reports/STAGE5P0_SMALL_FIXES_REPORT.md

## 3. Exporter schema before/after
Before:
- Exporter emitted single-file shorthand arrays: obs, action, reward, done.
- Output naming did not match adapter raw-rollout directory contract.

After:
- Exporter emits run directory:
  - <output_root>/<run_label_or_timestamp>/teacher_rollout_raw.npz
  - <output_root>/<run_label_or_timestamp>/teacher_rollout_manifest.json
- Required NPZ keys now emitted:
  - observation_t [T,24,24,27] float32
  - per_cell_action_t [T,576,7] int16
  - episode_id [T] int32
  - step_id [T] int32
  - reward_t [T] float32
  - done_t [T] bool
  - terminated_t [T] bool
  - truncated_t [T] bool
  - action_mask_available_t [T] bool
- Optional diagnostics emitted:
  - source_valid_action_count_t
  - selected_non_noop_count_t
  - source_valid_non_noop_count_t
  - mask_source_valid_count_t

## 4. Action path confirmation
Exporter final action stepping path remains training-compatible:
1. policy per-cell action [N,576,7]
2. source-indexed real action [N,576,8]
3. source-valid filtering via mask[:,:,0]
4. Java valid-action payload creation
5. env.step(java_valid_actions)

No teacher training code was changed.

## 5. Stored dataset action vs env.step action
- Stored dataset action (BC target): per_cell_action_t in policy branch format [T,576,7].
- env.step action (runtime execution): training-compatible Java payload built from source-valid filtered actions.
- Raw env.step([N,576,7]) is retained only as diagnostic mode, not final evidence mode.

## 6. Stochastic export support
Exporter CLI now supports:
- --export-mode deterministic
- --export-mode stochastic
- --export-mode both

Default is stochastic, matching Stage5P preference for higher source-valid non-noop activity.

## 7. Manifest fields added
Manifest now includes required Stage5P0 metadata including:
- schema_version: legacy032.teacher_rollout_raw.v2
- teacher_lineage: legacy032
- checkpoint_path
- model_metadata_path
- trainer_state_path
- architecture
- gym_microrts_version
- map_path
- observation_shape
- raw_action_nvec
- stored_action_format/stored_action_shape/stored_action_branch_sizes/stored_action_dtype
- env_step_action_format
- step_mode
- mask_required
- mask_source
- export_mode
- episodes
- total_steps
- seed
- created_utc
- semantic_parity_claim: false
- direct_weight_transfer_claim: false
- selected_source_valid_non_noop_share
- terminal counters
- CLI argument snapshot

Adapter compatibility helper field included:
- exported_per_cell_branch_sizes: [6,4,4,4,4,7,49]

## 8. Adapter compatibility confirmation
No adapter code change was required.

Existing adapter contract remains valid:
- Input file names: teacher_rollout_raw.npz + teacher_rollout_manifest.json
- Required arrays: observation_t/per_cell_action_t plus episodic fields
- Unity v2 branch sizes remain [6,4,4,4,4,7,49]

No downgrade to v1 branch layout was introduced.

## 9. Runbook updates
Updated runbook now:
- Points to preferred 3M checkpoint lineage (resume_3m_from_1m_postfix).
- Uses current exporter CLI flags.
- Recommends stochastic export as main Stage5P path.
- Includes deterministic export as optional baseline split.
- Explicitly states final export uses training_compatible step mode.
- Explicitly marks raw env.step([N,576,7]) as diagnostic only.
- Explains stored action vs env.step action distinction.
- Avoids direct Gym-to-Unity semantic parity claims.

## 10. Compile/smoke results
Executed commands:
- python -m py_compile python/week5_teacher_legacy032/scripts/legacy032_policy_action.py python/week5_teacher_legacy032/scripts/export_teacher_rollout_legacy032.py python/week5_teacher_legacy032/scripts/adapt_legacy032_to_unity_v2.py python/week5_teacher_legacy032/scripts/validate_legacy032_unity_v2_dataset.py python/week5_teacher_legacy032/scripts/build_bc_ready_dataset_legacy032_v2.py python/week5_teacher_legacy032/scripts/dry_run_bc_loader_legacy032_v2.py
- python python/week5_teacher_legacy032/scripts/export_teacher_rollout_legacy032.py --help

Result:
- py_compile: PASS (no syntax errors)
- exporter --help smoke: PASS

## 11. Remaining limitations
- No rollout export was executed in this patch pass.
- No BC training was executed.
- No Unity launch/runtime validation was executed.
- Semantic parity remains a runtime validation concern and is not claimed here.

## 12. Final recommendation for Stage5P
Proceed to Stage5P rollout export using stochastic mode and training-compatible stepping as the primary dataset source path.
