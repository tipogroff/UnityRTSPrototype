# STAGE5A 100K Training Report

- Date: 2026-05-05T03:44:48.313046+00:00
- run_id: legacy032_24x24_teacher_resume_1m_20260504T231107Z
- Stage 5A status: PASS
- Decision: READY_FOR_500K

## Summary

- Scope: Stage 5A only (100k checkpoint on corrected 24x24 GridMode path).
- Stages requested: 100000.
- 500k/1M/3M/5M not executed in this run.

## Commands Run

- preflight: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\scripts\verify_legacy032_24x24_training_contract.py
- train: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\scripts\ppo_gridnet_legacy032_24x24_local_save.py
- gate eval: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\scripts\evaluate_teacher_legacy032.py

## Preflight Contract Probe

- report: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage5a_24x24_contract_probe.json
- status: PASS
- observation_space: [24, 24, 27]
- action_space_nvec: [576, 6, 4, 4, 4, 4, 7, 49]
- mask_available: True
- policy_forward_ok: True
- masked_action_sample_ok: True
- env_step_ok: True

## Training Result

- checkpoint_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_1m_20260504T231107Z\stage_000100000\agent_final.pt
- model_metadata_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_1m_20260504T231107Z\stage_000100000\model_metadata.json
- machine_report_json: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage5_24x24_training_20260504T231107Z.json
- machine_report_md: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage5_24x24_training_20260504T231107Z.md

## Metadata Contract

- architecture_name_expected: legacy032_resolution_aware_gridnet_v1
- observation_space_expected: [24, 24, 27]
- action_space_nvec_expected: [576, 6, 4, 4, 4, 4, 7, 49]
- architecture_name_actual: legacy032_resolution_aware_gridnet_v1
- observation_space_actual: [24, 24, 27]
- action_space_nvec_actual: [576, 6, 4, 4, 4, 4, 7, 49]

## Behavior Gate Result

- gate_json_report: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage5_gate_000100000_20260504T234007Z.json
- gate_md_report: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage5_gate_000100000_20260504T234007Z.md
- gate_decision: PASS
- checkpoint_load_ok: True
- policy_architecture_load_ok: True
- inference_ok: True
- env_matches_target_24x24: True
- mask_used_during_eval: True

## Metrics Table

| metric | value |
|---|---|
| mean_return | -10.0 |
| effective_activity_share | 0.8335107238998127 |
| noop_share | 0.16648927610018727 |
| move_share | 0.16625397452403246 |
| attack_action_count | 817030 |
| produce_action_count | 823730 |
| policy_entropy_proxy | 0.0009899255336871177 |
| action_type_share | {'noop': 0.16648927610018727, 'move': 0.16625397452403246, 'harvest': 0.1678151334269663, 'return': 0.16604488529962547, 'produce': 0.16737907368393676, 'attack': 0.16601765696525178} |

## Warnings / Errors

- none

## Recommendation

- Continue to 500k stage: YES