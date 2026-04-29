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
- noop_share: 0.16780615824697756
- move_share: 0.1665479274611399
- effective_activity_share: 0.8321938417530225
- attack_action_count: 245199
- produce_action_count: 248728
- policy_entropy_proxy: 0.003074304424371049
- action_type_counts: {'noop': 248729, 'move': 246864, 'harvest': 247775, 'return': 244945, 'produce': 248728, 'attack': 245199}

## Gate reasons

- none

## Warnings

- Checkpoint is evaluable only on reference internal env/action space, not target 24x24 preflight env.
- selected_action_mask_valid_share and masked_invalid_prevented_count are set to null because mask bit semantics are ambiguous in this legacy runtime.
- selected_action_mask_valid_share and masked_invalid_prevented_count are set to null because mask bit semantics are ambiguous in this legacy runtime.

## Errors

- none

- json_report: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage3_smoke_checkpoint_behavior_gate_20260429T122008Z.json