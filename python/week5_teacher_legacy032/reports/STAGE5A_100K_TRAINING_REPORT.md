# STAGE5A 100K Training Report

- Date: 2026-04-29T16:46:12.787688+00:00
- run_id: legacy032_24x24_teacher_main_20260429T162331Z
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

- checkpoint_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_main_20260429T162331Z\stage_000100000\agent_final.pt
- model_metadata_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_main_20260429T162331Z\stage_000100000\model_metadata.json
- machine_report_json: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage5_24x24_training_20260429T162331Z.json
- machine_report_md: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage5_24x24_training_20260429T162331Z.md

## Metadata Contract

- architecture_name_expected: legacy032_resolution_aware_gridnet_v1
- observation_space_expected: [24, 24, 27]
- action_space_nvec_expected: [576, 6, 4, 4, 4, 4, 7, 49]
- architecture_name_actual: legacy032_resolution_aware_gridnet_v1
- observation_space_actual: [24, 24, 27]
- action_space_nvec_actual: [576, 6, 4, 4, 4, 4, 7, 49]

## Behavior Gate Result

- gate_json_report: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage5_gate_000100000_20260429T164521Z.json
- gate_md_report: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage5_gate_000100000_20260429T164521Z.md
- gate_decision: PASS
- checkpoint_load_ok: True
- policy_architecture_load_ok: True
- inference_ok: True
- env_matches_target_24x24: True
- mask_used_during_eval: True

## Metrics Table

| metric | value |
|---|---|
| mean_return | -7.5 |
| effective_activity_share | 0.8336504744224422 |
| noop_share | 0.16634952557755775 |
| move_share | 0.1662045631646498 |
| attack_action_count | 579601 |
| produce_action_count | 585077 |
| policy_entropy_proxy | 0.0009317503856508854 |
| action_type_share | {'noop': 0.16634952557755775, 'move': 0.1662045631646498, 'harvest': 0.16788853364503117, 'return': 0.16589229235423542, 'produce': 0.16761694398606528, 'attack': 0.1660481412724606} |

## Warnings / Errors

- none

## Recommendation

- Continue to 500k stage: YES