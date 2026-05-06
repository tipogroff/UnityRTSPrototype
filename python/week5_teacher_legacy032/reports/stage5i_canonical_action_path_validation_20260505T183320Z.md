# Stage5I Canonical Action Path Validation

- status: OK
- classification: STAGE5I_CANONICAL_MODULE_CREATED_BUT_NOT_FULLY_WIRED
- checkpoint_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_1m_20260504T231107Z\stage_001000000\agent_final.pt
- model_metadata_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_1m_20260504T231107Z\stage_001000000\model_metadata.json

## Checks

- A_canonical_import: {'passed': True}
- B_strict_load_1m: {'passed': True, 'load_report': {'checkpoint_path': 'C:\\Projects\\UnityRTSPrototype\\UnityRTSPrototype\\python\\week5_teacher_legacy032\\teacher_models\\legacy032_24x24_teacher_resume_1m_20260504T231107Z\\stage_001000000\\agent_final.pt', 'checkpoint_format': 'weights_only_state_dict', 'strict': True, 'strict_load_status': 'STRICT_LOAD_ENFORCED', 'missing_keys': [], 'unexpected_keys': []}}
- C_fixed_obs_mask_inference: {'passed': True, 'logits_shape': [2, 24, 24, 78], 'mask_source': 'env.vec_client.getMasks(0)'}
- D_deterministic_shape: {'passed': True, 'action_shape': [2, 576, 7]}
- E_format_env_action: {'passed': True, 'dtype': 'int32', 'shape': [2, 576, 7], 'contiguous': True}
- F_branch_bounds: {'passed': True}
- G_fresh_reload_parity: {'passed': True, 'logits_max_abs_diff': 0.0, 'logits_mean_abs_diff': 0.0, 'action_tensor_equal': True}
- H_wiring_old_scripts: {'python/week5_teacher_legacy032/scripts/evaluate_teacher_legacy032.py': {'exists': True, 'imports_canonical': True, 'contains_stale_stage_003000000': False}, 'python/week5_teacher_legacy032/scripts/evaluate_teacher_large_map_diagnostics.py': {'exists': True, 'imports_canonical': True, 'contains_stale_stage_003000000': False}, 'python/week5_teacher_legacy032/scripts/evaluate_teacher_large_map_win_diagnostics.py': {'exists': True, 'imports_canonical': True, 'contains_stale_stage_003000000': False}, 'python/week5_teacher_legacy032/scripts/export_teacher_rollout_legacy032.py': {'exists': True, 'imports_canonical': True, 'contains_stale_stage_003000000': False}, 'python/week5_teacher_legacy032/scripts/run_legacy032_visual_single_episode.py': {'exists': True, 'imports_canonical': True, 'contains_stale_stage_003000000': False}, 'python/week5_teacher_legacy032/scripts/run_legacy032_3m_visual_single_episode.py': {'exists': True, 'imports_canonical': False, 'contains_stale_stage_003000000': True}}
- I_no_stale_3m_default: {'passed': False, 'stale_files': ['python/week5_teacher_legacy032/scripts/run_legacy032_3m_visual_single_episode.py']}
- J_visual_smoke: {'requested': True, 'deterministic': {'ok': True, 'mode': 'deterministic', 'steps': 16, 'total_reward': 0.0, 'first_step': {'mask_source': 'env.vec_client.getMasks(0)', 'summary': {'all_cell_action_type_counts': {'0': 1148, '1': 0, '2': 2, '3': 0, '4': 2, '5': 0}, 'all_cell_action_type_shares': {'0': 0.9965277777777778, '1': 0.0, '2': 0.001736111111111111, '3': 0.0, '4': 0.001736111111111111, '5': 0.0}, 'source_valid_action_type_counts': {'0': 0, '1': 0, '2': 2, '3': 0, '4': 2, '5': 0}, 'source_valid_action_type_shares': {'0': 0.0, '1': 0.0, '2': 0.5, '3': 0.0, '4': 0.5, '5': 0.0}, 'source_valid_non_noop_count': 4, 'source_valid_total': 4}, 'effective_noop_candidate_count': 0}}, 'stochastic': {'ok': False, 'mode': 'stochastic', 'error': 'JVM cannot be restarted'}, 'no_noop_fallback_string': True}
