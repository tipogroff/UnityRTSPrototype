# Stage5H Training vs Post-load Action Path Parity Audit

- timestamp_utc: 2026-05-05T18:16:22Z
- status: OK
- classification: STAGE5H_ACTION_FORMATTING_MISMATCH
- checkpoint_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_1m_20260504T231107Z\stage_001000000\agent_final.pt
- metadata_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_1m_20260504T231107Z\stage_001000000\model_metadata.json

## Commands

- python python/week5_teacher_legacy032/scripts/audit_stage5h_training_postload_parity.py --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/agent_final.pt --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/model_metadata.json --device cpu --seed 17

## Static Source Parity

- shared_feature_checks: {'same_output_channel_count_rule': True, 'same_split_rule_from_nvec1': True, 'same_mask_slice_rule': True, 'same_deterministic_rule': False, 'same_stochastic_rule': True}

## Same Observation/Mask Roundtrip

- same_process_reload: {'logits_max_abs_diff': 0.0, 'logits_mean_abs_diff': 0.0, 'logits_allclose_exact': True, 'logits_allclose_atol_1e-7': True, 'action_tensor_equal': True, 'action_type_equal': True, 'branch_equal': {'action_type': True, 'move_dir': True, 'harvest_dir': True, 'return_dir': True, 'produce_dir': True, 'produce_unit_type': True, 'attack_target': True}, 'source_valid_action_equal': True, 'source_valid_branch_equal': {'action_type': True, 'move_dir': True, 'harvest_dir': True, 'return_dir': True, 'produce_dir': True, 'produce_unit_type': True, 'attack_target': True}, 'stochastic_action_tensor_equal': True}
- fresh_object_reload: {'logits_max_abs_diff': 0.0, 'logits_mean_abs_diff': 0.0, 'logits_allclose_exact': True, 'logits_allclose_atol_1e-7': True, 'action_tensor_equal': True, 'action_type_equal': True, 'branch_equal': {'action_type': True, 'move_dir': True, 'harvest_dir': True, 'return_dir': True, 'produce_dir': True, 'produce_unit_type': True, 'attack_target': True}, 'source_valid_action_equal': True, 'source_valid_branch_equal': {'action_type': True, 'move_dir': True, 'harvest_dir': True, 'return_dir': True, 'produce_dir': True, 'produce_unit_type': True, 'attack_target': True}, 'stochastic_action_tensor_equal': True}

## Full Branch Validity

- summary: {'selected_source_valid_cells': 12, 'source_valid_total': 12, 'non_noop_source_valid_total': 12, 'effective_noop_candidate_count': 0, 'effective_noop_candidate_share': 0.0}

## Visual Script Findings

- targeted_visual_script_audit: {'exists': True, 'file': 'python/week5_teacher_legacy032/scripts/run_legacy032_3m_visual_single_episode.py', 'has_3m_hardcoded_assumptions': True, 'default_checkpoint_is_3m': True, 'default_uses_agent_final_pt': True, 'default_uses_trainer_state_final_pt': False, 'metadata_driven_architecture': True, 'strict_load_default_true': True, 'deterministic_default': True, 'has_generic_exception_handlers': True, 'has_noop_fallback_hint': False, 'findings': ['Visual script defaults are pinned to stage_003000000 checkpoint path.', 'Visual script contains 3M-specific assumptions in defaults/naming.', 'Visual script uses broad exception handlers; failures may be softened into warnings.', 'strict_load default is True.', 'deterministic eval mode is default.']}

## Ranked Root Cause Candidates

1. Action tensor formatting mismatch before env.step.
2. Per-branch value bounds/shape mismatch despite parity in logits.

## Recommended Fix Plan

1. Extract a single canonical policy-action module and replace duplicated action-selection implementations.
2. Patch visual script defaults to target explicit input checkpoint/metadata and remove stale 3M assumptions.
3. Keep strict_load=True and add one fixed obs/mask parity smoke-test to CI before visual runs.
4. Only after parity fix: rerun visual single-episode verification, then decide on further training/export/BC/Unity transfer.
