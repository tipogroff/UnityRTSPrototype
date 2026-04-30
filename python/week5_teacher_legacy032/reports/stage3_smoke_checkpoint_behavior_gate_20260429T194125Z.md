# Stage 3 Behavior Gate Report

- run_label: stage5c_env_max_steps_6000_smoke
- checkpoint_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_main_20260429T171506Z\stage_000500000\agent_final.pt
- metadata_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_main_20260429T171506Z\stage_000500000\model_metadata.json
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
- max_steps_per_episode: 6000
- env_max_steps: 6000
- observed_max_episode_length: 505

## Behavior metrics (primary eval mode)

- episodes_requested: 2
- episodes_completed: 2
- episode_end_reason_counts: {'env_done': 2, 'outer_loop_limit': 0, 'unknown': 0}
- observed_max_episode_length: 505
- mean_return: -10.0
- std_return: 0.0
- noop_share: 0.1661681793179318
- move_share: 0.1662455308030803
- effective_activity_share: 0.8338318206820682
- attack_action_count: 289263
- produce_action_count: 292589
- policy_entropy_proxy: 0.0007943211457609097
- action_type_counts: {'noop': 290010, 'move': 290145, 'harvest': 293338, 'return': 289935, 'produce': 292589, 'attack': 289263}

## Gate reasons

- none

## Warnings

- selected_action_mask_valid_share and masked_invalid_prevented_count are set to null because mask bit semantics are ambiguous in this legacy runtime.
- Observed max episode length is <= 2000 while max_steps_per_episode=6000; this suggests an additional internal cap.

## Errors

- none

- json_report: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage3_smoke_checkpoint_behavior_gate_20260429T194125Z.json