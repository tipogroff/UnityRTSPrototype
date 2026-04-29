# Stage 3 Behavior Gate Report

- run_label: stage4r_24x24_smoke_behavior_gate
- checkpoint_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_smoke_20260429T133037Z\agent_final.pt
- metadata_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_smoke_20260429T133037Z\model_metadata.json
- checkpoint_step: None
- gate_decision: PASS

## Compatibility

- env_matches_training_metadata: True
- env_matches_target_24x24: True
- eval_env_id: MicrortsRandomEnemyShapedReward1-v1
- eval_map_path: maps/24x24/basesWorkers24x24.xml
- eval_observation_shape: [24, 24, 27]
- eval_action_space: [576, 6, 4, 4, 4, 4, 7, 49]
- eval_action_representation: GYM_MICRORTS_032_REFERENCE_GRIDMODE

## Core checks

- checkpoint_load_ok: True
- policy_architecture_load_ok: True
- inference_ok: True
- mask_available: True
- mask_source: env.vec_client.getMasks(0)
- mask_used_during_eval: True

## Behavior metrics (primary eval mode)

- episodes_requested: 8
- episodes_completed: 8
- mean_return: -7.5
- std_return: 4.330127018922194
- noop_share: 0.1671012674184085
- move_share: 0.16655493674367436
- effective_activity_share: 0.8328987325815915
- attack_action_count: 579601
- produce_action_count: 585352
- policy_entropy_proxy: 0.0013764507824204641
- action_type_counts: {'noop': 583277, 'move': 581370, 'harvest': 581903, 'return': 579057, 'produce': 585352, 'attack': 579601}

## Gate reasons

- none

## Warnings

- selected_action_mask_valid_share and masked_invalid_prevented_count are set to null because mask bit semantics are ambiguous in this legacy runtime.

## Errors

- none

- json_report: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage3_smoke_checkpoint_behavior_gate_20260429T142601Z.json