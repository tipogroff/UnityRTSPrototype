# Stage5I Canonical Action Path Validation

- status: ERROR
- classification: STAGE5I_VALIDATION_FAILED
- checkpoint_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_1m_20260504T231107Z\stage_001000000\agent_final.pt
- model_metadata_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_1m_20260504T231107Z\stage_001000000\model_metadata.json

## Checks

- A_canonical_import: {'passed': True}
- B_strict_load_1m: {'passed': True, 'load_report': {'checkpoint_path': 'C:\\Projects\\UnityRTSPrototype\\UnityRTSPrototype\\python\\week5_teacher_legacy032\\teacher_models\\legacy032_24x24_teacher_resume_1m_20260504T231107Z\\stage_001000000\\agent_final.pt', 'checkpoint_format': 'weights_only_state_dict', 'strict': True, 'strict_load_status': 'STRICT_LOAD_ENFORCED', 'missing_keys': [], 'unexpected_keys': []}}

## Errors

- reset() got an unexpected keyword argument 'seed'
