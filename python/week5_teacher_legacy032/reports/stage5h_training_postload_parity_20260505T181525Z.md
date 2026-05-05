# Stage5H Training vs Post-load Action Path Parity Audit

- timestamp_utc: 2026-05-05T18:15:25Z
- status: ERROR
- classification: STAGE5H_AUDIT_FAILED
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

- summary: {}

## Visual Script Findings

- targeted_visual_script_audit: {'exists': True, 'file': 'python/week5_teacher_legacy032/scripts/run_legacy032_3m_visual_single_episode.py', 'has_3m_hardcoded_assumptions': True, 'default_checkpoint_is_3m': True, 'default_uses_agent_final_pt': True, 'default_uses_trainer_state_final_pt': False, 'metadata_driven_architecture': True, 'strict_load_default_true': True, 'deterministic_default': True, 'has_generic_exception_handlers': True, 'has_noop_fallback_hint': False, 'findings': ['Visual script defaults are pinned to stage_003000000 checkpoint path.', 'Visual script contains 3M-specific assumptions in defaults/naming.', 'Visual script uses broad exception handlers; failures may be softened into warnings.', 'strict_load default is True.', 'deterministic eval mode is default.']}

## Ranked Root Cause Candidates


## Recommended Fix Plan


## Errors

- JVM cannot be restarted
- Traceback (most recent call last):
  File "C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\scripts\audit_stage5h_training_postload_parity.py", line 985, in main
    probe_train = _env_step_probe(metadata=metadata, seed=int(args.seed), action_np=action_training_np, max_steps=int(args.max_steps))
  File "C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\scripts\audit_stage5h_training_postload_parity.py", line 421, in _env_step_probe
    env = _create_24x24_env(metadata=metadata, max_steps=max_steps)
  File "C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\scripts\audit_stage5h_training_postload_parity.py", line 278, in _create_24x24_env
    env = MicroRTSGridModeVecEnv(
  File "C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_reference\.venv_microrts032_reference\lib\site-packages\gym_microrts\envs\vec_env.py", line 174, in __init__
    super().__init__(**kwargs)
  File "C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_reference\.venv_microrts032_reference\lib\site-packages\gym_microrts\envs\vec_env.py", line 61, in __init__
    jpype.startJVM(convertStrings=False)
  File "C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_reference\.venv_microrts032_reference\lib\site-packages\jpype\_core.py", line 169, in startJVM
    raise OSError('JVM cannot be restarted')
OSError: JVM cannot be restarted

