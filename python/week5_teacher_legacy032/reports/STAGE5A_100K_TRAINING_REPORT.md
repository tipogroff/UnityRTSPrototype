# STAGE5A 100K Training Report

- Date: 2026-04-30T12:56:15.979633+00:00
- run_id: stage5d_cpu_smoke_compare_20260430T125352Z
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

- checkpoint_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\stage5d_cpu_smoke_compare_20260430T125352Z\stage_000010000\agent_final.pt
- model_metadata_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\stage5d_cpu_smoke_compare_20260430T125352Z\stage_000010000\model_metadata.json
- machine_report_json: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage5_24x24_training_20260430T125352Z.json
- machine_report_md: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage5_24x24_training_20260430T125352Z.md

## Metadata Contract

- architecture_name_expected: legacy032_resolution_aware_gridnet_v1
- observation_space_expected: [24, 24, 27]
- action_space_nvec_expected: [576, 6, 4, 4, 4, 4, 7, 49]
- architecture_name_actual: legacy032_resolution_aware_gridnet_v1
- observation_space_actual: [24, 24, 27]
- action_space_nvec_actual: [576, 6, 4, 4, 4, 4, 7, 49]

## Behavior Gate Result

- gate_json_report: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage5_gate_000010000_20260430T125555Z.json
- gate_md_report: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage5_gate_000010000_20260430T125555Z.md
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
| effective_activity_share | 0.8329929867986798 |
| noop_share | 0.16700701320132014 |
| move_share | 0.16664890447378072 |
| attack_action_count | 289256 |
| produce_action_count | 292618 |
| policy_entropy_proxy | 0.0013906632716039029 |
| action_type_share | {'noop': 0.16700701320132014, 'move': 0.16664890447378072, 'harvest': 0.16682022368903557, 'return': 0.16612520627062707, 'produce': 0.16766249541620828, 'attack': 0.16573615694902824} |

## Warnings / Errors

- none

## Recommendation

- Continue to 500k stage: YES