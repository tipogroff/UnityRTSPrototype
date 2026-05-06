# Stage5N Post-Fix Behavior Metrics Revalidation

- status: OK
- timestamp_utc: 2026-05-06T03:43:34Z
- checkpoint_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_3m_from_1m_postfix\agent_final.pt
- model_metadata_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_3m_from_1m_postfix\model_metadata.json
- step_mode: training_compatible

## Strict Load

- strict_load: True
- checkpoint_format: weights_only_state_dict
- strict_load_status: STRICT_LOAD_ENFORCED
- missing_keys: []
- unexpected_keys: []

## Contract

- observation_space: [24, 24, 27]
- action_space_nvec: [576, 6, 4, 4, 4, 4, 7, 49]
- architecture_name: legacy032_resolution_aware_gridnet_v1
- map_path: maps/24x24/basesWorkers24x24.xml
- mask_source_expected: env.vec_client.getMasks(0)
- step_mode: training_compatible
- java_payload_used: True

## Evaluation Matrix

- deterministic_seed17: mode=deterministic seed=17 episodes=8 max_steps=6000
- stochastic_seed17: mode=stochastic seed=17 episodes=8 max_steps=6000
- stochastic_seed123: mode=stochastic seed=123 episodes=8 max_steps=6000

## Aggregate Metrics

### deterministic_seed17

- episodes_completed: 8
- mean_reward: 216.825
- median_reward: 220.2
- min_reward: 194.2
- max_reward: 235.2
- mean_episode_length: 5848.75
- max_episode_length: 6000
- mean_obs_changed_steps: 4802.25
- mean_obs_changed_share: 0.819202225017104
- win/loss/draw: 8/0/0
- win_rate: 1.0
- mean_source_valid_non_noop_share: 0.26603969190917404
- mean_source_valid_action_type_shares: {'noop': 0.7333979309857754, 'move': 0.21258880490294382, 'harvest': 0.0022519209479480574, 'return': 0.0021552044070353863, 'produce': 0.046595780189843325, 'attack': 0.0030103585664539353}
- terminal_counts: {'env_done': 8}
- mean_raw_rewards_components: [0.25, 98.125, 32.75, 1.0, 51.75, 7.875]
- env_step_error_count: 0

### stochastic_seed17

- episodes_completed: 8
- mean_reward: 211.575
- median_reward: 217.2
- min_reward: 164.2
- max_reward: 230.2
- mean_episode_length: 3036.25
- max_episode_length: 4770
- mean_obs_changed_steps: 2751.25
- mean_obs_changed_share: 0.8944376547040508
- win/loss/draw: 8/0/0
- win_rate: 1.0
- mean_source_valid_non_noop_share: 0.5346441100976961
- mean_source_valid_action_type_shares: {'noop': 0.4783396846040113, 'move': 0.46082071252901663, 'harvest': 0.0061647891366025725, 'return': 0.005752471183152725, 'produce': 0.042116371747319935, 'attack': 0.00680597079989683}
- terminal_counts: {'env_done': 8}
- mean_raw_rewards_components: [1.0, 101.125, 32.25, 1.0, 36.5, 7.875]
- env_step_error_count: 0

### stochastic_seed123

- episodes_completed: 8
- mean_reward: 202.85
- median_reward: 201.2
- min_reward: 190.2
- max_reward: 219.2
- mean_episode_length: 2310.0
- max_episode_length: 3197
- mean_obs_changed_steps: 2028.625
- mean_obs_changed_share: 0.8759030759153723
- win/loss/draw: 8/0/0
- win_rate: 1.0
- mean_source_valid_non_noop_share: 0.5360810040484956
- mean_source_valid_action_type_shares: {'noop': 0.47137873173804146, 'move': 0.45816172382063053, 'harvest': 0.00664540923025445, 'return': 0.006254213351835176, 'produce': 0.05027236090403153, 'attack': 0.007287560955206842}
- terminal_counts: {'env_done': 8}
- mean_raw_rewards_components: [1.0, 100.625, 33.75, 1.125, 29.75, 7.125]
- env_step_error_count: 0

## Deterministic vs Stochastic

- is_stochastic_better_than_deterministic: False
- deterministic_still_weaker_or_stranger: False
- rollout_export_policy: stochastic_or_deterministic
- is_1m_valid_teacher_candidate: True
- continue_to_2m_3m_before_bc: False

## Final

- classification: STAGE5N_1M_BEHAVIOR_METRICS_PASS
- recommendation: 1M checkpoint is a valid post-fix teacher candidate. You may export rollouts now; 2M/3M remains optional for stronger teacher quality.
