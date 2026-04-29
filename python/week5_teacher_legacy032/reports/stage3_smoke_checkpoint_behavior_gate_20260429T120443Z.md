# Stage 3 Behavior Gate Report

- run_label: stage3_smoke_checkpoint_behavior_gate
- checkpoint_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_smoke_20260429T113844Z\agent_final.pt
- metadata_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_smoke_20260429T113844Z\model_metadata.json
- checkpoint_step: None
- gate_decision: PASS_WITH_WARNINGS

## Compatibility

- env_matches_training_metadata: True
- env_matches_target_24x24: False
- eval_env_id: MicrortsDefeatCoacAIShaped-v3
- eval_map_path: maps/16x16/basesWorkers16x16.xml
- eval_observation_shape: [16, 16, 27]
- eval_action_space: [256, 6, 4, 4, 4, 4, 7, 49]
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
- noop_share: 0.16780345962867013
- move_share: 0.16654860211571676
- effective_activity_share: 0.8321965403713298
- attack_action_count: 245199
- produce_action_count: 248730
- policy_entropy_proxy: 0.0030738902936926008
- action_type_counts: {'noop': 248725, 'move': 246865, 'harvest': 247776, 'return': 244945, 'produce': 248730, 'attack': 245199}

## Gate reasons

- none

## Warnings

- Checkpoint is evaluable only on reference internal env/action space, not target 24x24 preflight env.

## Errors

- none

- json_report: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage3_smoke_checkpoint_behavior_gate_20260429T120443Z.json