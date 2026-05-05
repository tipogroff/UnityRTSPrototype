# Stage5H Training vs Post-load Action Path Parity Audit

- timestamp_utc: 2026-05-05T18:14:52Z
- status: ERROR
- classification: STAGE5H_AUDIT_FAILED
- checkpoint_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_1m_20260504T231107Z\stage_001000000\agent_final.pt
- metadata_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_1m_20260504T231107Z\stage_001000000\model_metadata.json

## Commands

- python python/week5_teacher_legacy032/scripts/audit_stage5h_training_postload_parity.py --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/agent_final.pt --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/model_metadata.json --device cpu --seed 17

## Static Source Parity

- shared_feature_checks: {'same_output_channel_count_rule': False, 'same_split_rule_from_nvec1': True, 'same_mask_slice_rule': True, 'same_deterministic_rule': False, 'same_stochastic_rule': True}

## Same Observation/Mask Roundtrip

- same_process_reload: None
- fresh_object_reload: None

## Full Branch Validity

- summary: {}

## Visual Script Findings

- targeted_visual_script_audit: {'exists': True, 'file': 'python/week5_teacher_legacy032/scripts/run_legacy032_3m_visual_single_episode.py', 'has_3m_hardcoded_assumptions': True, 'default_checkpoint_is_3m': True, 'default_uses_agent_final_pt': True, 'default_uses_trainer_state_final_pt': False, 'metadata_driven_architecture': True, 'strict_load_default_true': True, 'deterministic_default': True, 'has_generic_exception_handlers': True, 'has_noop_fallback_hint': False, 'findings': ['Visual script defaults are pinned to stage_003000000 checkpoint path.', 'Visual script contains 3M-specific assumptions in defaults/naming.', 'Visual script uses broad exception handlers; failures may be softened into warnings.', 'strict_load default is True.', 'deterministic eval mode is default.']}

## Ranked Root Cause Candidates


## Recommended Fix Plan


## Errors

- Error(s) in loading state_dict for Legacy032Policy:
	Unexpected key(s) in state_dict: "critic.2.weight", "critic.2.bias", "critic.4.weight", "critic.4.bias". 
- Traceback (most recent call last):
  File "C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\scripts\audit_stage5h_training_postload_parity.py", line 833, in main
    policy.load_state_dict(state_dict, strict=True)
  File "C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_reference\.venv_microrts032_reference\lib\site-packages\torch\nn\modules\module.py", line 1223, in load_state_dict
    raise RuntimeError('Error(s) in loading state_dict for {}:\n\t{}'.format(
RuntimeError: Error(s) in loading state_dict for Legacy032Policy:
	Unexpected key(s) in state_dict: "critic.2.weight", "critic.2.bias", "critic.4.weight", "critic.4.bias". 

