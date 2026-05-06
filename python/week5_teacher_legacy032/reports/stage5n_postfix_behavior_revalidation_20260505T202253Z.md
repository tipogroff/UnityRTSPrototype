# Stage5N Post-Fix Behavior Metrics Revalidation

- status: OK
- timestamp_utc: 2026-05-05T20:22:53Z
- checkpoint_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_1m_20260504T231107Z\stage_001000000\agent_final.pt
- model_metadata_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_1m_20260504T231107Z\stage_001000000\model_metadata.json
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
- mean_reward: 99.45
- median_reward: 97.2
- min_reward: 86.2
- max_reward: 109.2
- mean_episode_length: 6000.0
- max_episode_length: 6000
- mean_obs_changed_steps: 3203.0
- mean_obs_changed_share: 0.5338333333333334
- win/loss/draw: 8/0/0
- win_rate: 1.0
- mean_source_valid_non_noop_share: 0.12987839582845154
- mean_source_valid_action_type_shares: {'noop': 0.8701791635285733, 'move': 0.09462614871794421, 'harvest': 0.001536164457478212, 'return': 0.0014931026391621753, 'produce': 0.030210941392865273, 'attack': 0.0019544792639768554}
- terminal_counts: {'env_done': 8}
- mean_raw_rewards_components: [0.0, 50.0, 14.5, 1.0, 14.75, 5.0]
- env_step_error_count: 0

### stochastic_seed17

- episodes_completed: 8
- mean_reward: 209.7
- median_reward: 216.7
- min_reward: 157.2
- max_reward: 235.2
- mean_episode_length: 5371.125
- max_episode_length: 6000
- mean_obs_changed_steps: 5096.375
- mean_obs_changed_share: 0.9472384206523738
- win/loss/draw: 8/0/0
- win_rate: 1.0
- mean_source_valid_non_noop_share: 0.4598215711420733
- mean_source_valid_action_type_shares: {'noop': 0.5423454855363536, 'move': 0.40167149591094375, 'harvest': 0.004127492048914932, 'return': 0.003955299681341624, 'produce': 0.04200981291504254, 'attack': 0.005890413907403554}
- terminal_counts: {'env_done': 8}
- mean_raw_rewards_components: [0.375, 95.0, 37.125, 1.0, 54.125, 4.875]
- env_step_error_count: 0

### stochastic_seed123

- episodes_completed: 8
- mean_reward: 208.2
- median_reward: 212.7
- min_reward: 171.2
- max_reward: 231.2
- mean_episode_length: 5380.625
- max_episode_length: 6000
- mean_obs_changed_steps: 5100.375
- mean_obs_changed_share: 0.9468711111624742
- win/loss/draw: 8/0/0
- win_rate: 1.0
- mean_source_valid_non_noop_share: 0.46570623039976633
- mean_source_valid_action_type_shares: {'noop': 0.5348200140063863, 'move': 0.40934499026133797, 'harvest': 0.004254955520392257, 'return': 0.004068334664234703, 'produce': 0.041846289240718315, 'attack': 0.005665416306930411}
- terminal_counts: {'env_done': 8}
- mean_raw_rewards_components: [0.375, 99.25, 38.75, 1.0, 46.25, 5.0]
- env_step_error_count: 0

## Deterministic vs Stochastic

- is_stochastic_better_than_deterministic: True
- deterministic_still_weaker_or_stranger: True
- rollout_export_policy: stochastic
- is_1m_valid_teacher_candidate: True
- continue_to_2m_3m_before_bc: True

## Final

- classification: STAGE5N_1M_STOCHASTIC_PASS_DETERMINISTIC_WEAK
- recommendation: Use stochastic sampling for behavior evidence and rollout export. Continue to 2M/3M to improve deterministic stability before BC decisions.
