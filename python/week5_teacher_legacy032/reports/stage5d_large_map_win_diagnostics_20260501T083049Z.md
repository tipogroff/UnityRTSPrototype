# Stage5D Large-Map Win Diagnostics

- run_label: stage5d_large_map_win_diagnostics_003000000
- checkpoint_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_main_20260430T130208Z\stage_003000000\agent_final.pt
- model_metadata_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_main_20260430T130208Z\stage_003000000\model_metadata.json
- max_steps_per_episode: 6000
- eval_mode: both
- episodes: 16

## Technical compatibility

- checkpoint_load_ok: True
- policy_architecture_load_ok: True
- inference_ok: True
- observation_space: [24, 24, 27]
- action_space_nvec: [576, 6, 4, 4, 4, 4, 7, 49]
- env_matches_target_24x24: True
- mask_used_during_eval: True
- max_steps_per_episode: 6000

## deterministic

### Episode outcome metrics

- episode_end_reason_counts: {'env_done': 16, 'outer_loop_limit': 0, 'unknown': 0}
- episode_lengths: [505, 505, 712, 712, 505, 505, 712, 712, 505, 505, 505, 505, 712, 712, 505, 505]
- episode_returns: [-10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0]
- mean_return: -10.0
- terminal_types: None
- terminal_types_unavailable_reason: None
- win_count: 0
- loss_count: 0
- draw_count: 16

### Base destruction metrics

- {'enemy_base_destroyed_count': None, 'own_base_destroyed_count': None, 'episodes_with_enemy_base_destroyed': None, 'episodes_with_own_base_destroyed': None, 'first_enemy_base_destroyed_step': None, 'mean_enemy_base_destroyed_step': None, 'first_enemy_base_damage_step': None, 'enemy_base_detection_available': False, 'own_base_detection_available': False, 'enemy_base_damage_detection_available': False, 'unavailable_reason': 'base destruction cannot be determined exactly from available info payload; fields are null when not detectable.'}

### Economy/production timing

- economy_metrics: {'first_harvest_step': 6, 'first_return_step': None, 'first_produce_step': 6, 'first_barracks_or_unit_production_step': 6, 'harvest_action_count': 15070, 'return_action_count': 0, 'produce_action_count': 14774, 'economy_activity_present': True, 'worker_count_proxy': None, 'worker_count_proxy_reason': 'not present in env info payload', 'base_count_proxy': None, 'base_count_proxy_reason': 'not present in env info payload', 'barracks_count_proxy': None, 'barracks_count_proxy_reason': 'not present in env info payload', 'resource_proxy': None, 'resource_proxy_reason': 'not present in env info payload'}
- production_metrics: {'produce_action_count': 14774, 'produce_action_share': 0.001693023469013568, 'produce_unit_type_distribution': {'3': 14774}, 'first_produce_step': 6, 'unit_production_diversity_proxy': 1, 'produce_unit_type_distribution_reason': 'derived from produce_type branch index (legacy032 gridmode)'}

### Combat/contact metrics

- {'attack_action_count': 80, 'attack_action_share': 9.167583425009168e-06, 'episodes_with_attack_action': 16, 'first_attack_step': 3006, 'contact_seen': None, 'first_contact_step': None, 'episodes_with_contact': None, 'timeout_or_no_contact_episode_count': 0, 'contact_limitation': 'contact cannot be determined exactly from available info; attack_action_count is used as weak proxy.'}

### Movement/aggression proxy

- {'move_action_count': 0, 'move_share': 0.0, 'first_move_step': None, 'average_move_actions_before_first_attack': 0.0, 'movement_toward_enemy_base_proxy': None, 'movement_toward_enemy_base_proxy_reason': 'movement_toward_enemy_base_proxy cannot be determined safely because enemy-base direction semantics are unavailable.'}

### All-cell and source-cell metrics

- all_cell_metrics: {'global_noop_share_all_cells': 0.9965708654198753, 'global_non_noop_share_all_cells': 0.0034291345801247264, 'action_type_share_all_cells': {'noop': 0.9965708654198753, 'move': 0.0, 'harvest': 0.001726943527686102, 'return': 0.0, 'produce': 0.001693023469013568, 'attack': 9.167583425009168e-06}, 'repeated_same_action_share': 0.9999952178661569, 'policy_entropy_proxy': 0.0006511597396888872, 'source_cell_valid_share_observed_mask_bit0': 0.003429134597005968}
- source_cell_metrics: {'source_cell_valid_share_mean': None, 'source_cell_count_mean': None, 'noop_share_on_source_cells': None, 'non_noop_share_on_source_cells': None, 'action_type_share_on_source_cells': None, 'move_share_on_source_cells': None, 'harvest_share_on_source_cells': None, 'return_share_on_source_cells': None, 'produce_share_on_source_cells': None, 'attack_share_on_source_cells': None, 'unavailable_reason': 'source-cell metrics unavailable because mask bit semantics are ambiguous.'}

### Limitations

- source-cell metrics unavailable because mask bit semantics are ambiguous.
- movement_toward_enemy_base_proxy cannot be determined safely because enemy-base direction semantics are unavailable.
- contact cannot be determined exactly from available info; attack_action_count is used as weak proxy.
- base destruction cannot be determined exactly from available info payload; fields are null when not detectable.

## stochastic

### Episode outcome metrics

- episode_end_reason_counts: {'env_done': 16, 'outer_loop_limit': 0, 'unknown': 0}
- episode_lengths: [505, 505, 712, 712, 505, 505, 712, 712, 505, 505, 505, 505, 712, 712, 505, 505]
- episode_returns: [-10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0, -10.0]
- mean_return: -10.0
- terminal_types: None
- terminal_types_unavailable_reason: None
- win_count: 0
- loss_count: 0
- draw_count: 16

### Base destruction metrics

- {'enemy_base_destroyed_count': None, 'own_base_destroyed_count': None, 'episodes_with_enemy_base_destroyed': None, 'episodes_with_own_base_destroyed': None, 'first_enemy_base_destroyed_step': None, 'mean_enemy_base_destroyed_step': None, 'first_enemy_base_damage_step': None, 'enemy_base_detection_available': False, 'own_base_detection_available': False, 'enemy_base_damage_detection_available': False, 'unavailable_reason': 'base destruction cannot be determined exactly from available info payload; fields are null when not detectable.'}

### Economy/production timing

- economy_metrics: {'first_harvest_step': 6, 'first_return_step': 6, 'first_produce_step': 6, 'first_barracks_or_unit_production_step': 6, 'harvest_action_count': 1464644, 'return_action_count': 1448789, 'produce_action_count': 1462346, 'economy_activity_present': True, 'worker_count_proxy': None, 'worker_count_proxy_reason': 'not present in env info payload', 'base_count_proxy': None, 'base_count_proxy_reason': 'not present in env info payload', 'barracks_count_proxy': None, 'barracks_count_proxy_reason': 'not present in env info payload', 'resource_proxy': None, 'resource_proxy_reason': 'not present in env info payload'}
- production_metrics: {'produce_action_count': 1462346, 'produce_action_share': 0.1675772368903557, 'produce_unit_type_distribution': {'0': 207006, '1': 207898, '2': 206418, '3': 220355, '4': 206937, '5': 207127, '6': 206605}, 'first_produce_step': 6, 'unit_production_diversity_proxy': 7, 'produce_unit_type_distribution_reason': 'derived from produce_type branch index (legacy032 gridmode)'}

### Combat/contact metrics

- {'attack_action_count': 1449229, 'attack_action_share': 0.16607409699303263, 'episodes_with_attack_action': 16, 'first_attack_step': 6, 'contact_seen': None, 'first_contact_step': None, 'episodes_with_contact': None, 'timeout_or_no_contact_episode_count': 0, 'contact_limitation': 'contact cannot be determined exactly from available info; attack_action_count is used as weak proxy.'}

### Movement/aggression proxy

- {'move_action_count': 1450353, 'move_share': 0.16620290154015402, 'first_move_step': 6, 'average_move_actions_before_first_attack': 0.0, 'movement_toward_enemy_base_proxy': None, 'movement_toward_enemy_base_proxy_reason': 'movement_toward_enemy_base_proxy cannot be determined safely because enemy-base direction semantics are unavailable.'}

### All-cell and source-cell metrics

- all_cell_metrics: {'global_noop_share_all_cells': 0.16628151356802348, 'global_non_noop_share_all_cells': 0.8337184864319765, 'action_type_share_all_cells': {'noop': 0.16628151356802348, 'move': 0.16620290154015402, 'harvest': 0.16784057572423908, 'return': 0.1660236752841951, 'produce': 0.1675772368903557, 'attack': 0.16607409699303263}, 'repeated_same_action_share': 0.19113433983493908, 'policy_entropy_proxy': 0.0006555096716573923, 'source_cell_valid_share_observed_mask_bit0': 0.003429134597005968}
- source_cell_metrics: {'source_cell_valid_share_mean': None, 'source_cell_count_mean': None, 'noop_share_on_source_cells': None, 'non_noop_share_on_source_cells': None, 'action_type_share_on_source_cells': None, 'move_share_on_source_cells': None, 'harvest_share_on_source_cells': None, 'return_share_on_source_cells': None, 'produce_share_on_source_cells': None, 'attack_share_on_source_cells': None, 'unavailable_reason': 'source-cell metrics unavailable because mask bit semantics are ambiguous.'}

### Limitations

- source-cell metrics unavailable because mask bit semantics are ambiguous.
- movement_toward_enemy_base_proxy cannot be determined safely because enemy-base direction semantics are unavailable.
- contact cannot be determined exactly from available info; attack_action_count is used as weak proxy.
- base destruction cannot be determined exactly from available info payload; fields are null when not detectable.

## Manual visual observation cross-check

- confirmed_by_metrics: partial
- manual observation context:
  - manual observation indicates late-training improvement
  - agent eventually destroyed enemy base
  - later episodes appeared to destroy enemy base by T~2000 or earlier
- matching evidence:
  - economy/production timing detected
- contradictions:
  - stochastic mean_return remains -10.0
- unresolved:
  - exact enemy base destruction not confirmed by available metrics
  - exact contact timing unavailable; only attack proxy is available

## Interpretation

- agent has economy/production activity with attack activity; contact/outcome observability remains limited

## Recommendation for next prompt

- Hold for reward or eval diagnostics: outcome/base-destruction instrumentation is insufficient for reliable 5M decision.

## Warnings

- source-cell metrics unavailable because mask bit semantics are ambiguous.
- contact cannot be determined exactly from available info; attack_action_count is used as weak proxy.
- base destruction cannot be determined exactly from available info payload; fields are null when not detectable.
- movement_toward_enemy_base_proxy cannot be determined safely because enemy-base direction semantics are unavailable.

## Errors

- none