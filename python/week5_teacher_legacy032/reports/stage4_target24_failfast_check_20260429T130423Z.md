# Stage 3 Behavior Gate Report

- run_label: stage4_target24_failfast_check
- checkpoint_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_smoke_20260429T113844Z\agent_final.pt
- metadata_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_smoke_20260429T113844Z\model_metadata.json
- checkpoint_step: None
- gate_decision: FAIL

## Compatibility

- env_matches_training_metadata: False
- env_matches_target_24x24: False
- eval_env_id: None
- eval_map_path: None
- eval_observation_shape: None
- eval_action_space: None
- eval_action_representation: None

## Core checks

- checkpoint_load_ok: True
- policy_architecture_load_ok: True
- inference_ok: False
- mask_available: None
- mask_source: None
- mask_used_during_eval: False

## Behavior metrics (primary eval mode)

- episodes_requested: None
- episodes_completed: None
- mean_return: None
- std_return: None
- noop_share: None
- move_share: None
- effective_activity_share: None
- attack_action_count: None
- produce_action_count: None
- policy_entropy_proxy: None
- action_type_counts: None

## Gate reasons

- policy inference failed
- action distribution not recorded

## Warnings

- Checkpoint is evaluable only on reference internal env/action space, not target 24x24 preflight env.

## Errors

- Evaluation failed: target_24x24_gridmode requested but checkpoint metadata is 16x16 reference-internal. Checkpoint architecture/training metadata correspond to reference internal 16x16 grid mode (MultiDiscrete [256,6,4,4,4,4,7,49]), not preflight 24x24 global-single-action mode (MultiDiscrete [576,6,4,4,4,4,7,576]).

- json_report: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage4_target24_failfast_check_20260429T130423Z.json