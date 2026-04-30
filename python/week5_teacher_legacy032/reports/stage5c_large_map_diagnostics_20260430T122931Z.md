# Stage5C Large-Map Diagnostics

- run_label: stage5c_large_map_diagnostics_001000000
- checkpoint_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_main_20260429T195603Z\stage_001000000\agent_final.pt
- model_metadata_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_main_20260429T195603Z\stage_001000000\model_metadata.json
- max_steps_per_episode: 6000
- eval_mode: both

## deterministic

### All-cell metrics

- {'global_noop_share_all_cells': 0.9965651659384103, 'global_non_noop_share_all_cells': 0.003434834061589731, 'action_type_share_all_cells': {'noop': 0.9965651659384103, 'move': 0.0, 'harvest': 0.0017279832501040366, 'return': 0.0, 'produce': 0.0016987229504785684, 'attack': 8.127861007074491e-06}, 'repeated_same_action_share': 0.9999970951525765, 'policy_entropy_proxy': 0.0005879673805660725, 'source_cell_valid_share_observed_mask_bit0': 0.003434834079659973}

### Source-cell metrics

- {'source_cell_valid_share_mean': None, 'source_cell_count_mean': None, 'noop_share_on_source_cells': None, 'non_noop_share_on_source_cells': None, 'action_type_share_on_source_cells': None, 'move_share_on_source_cells': None, 'harvest_share_on_source_cells': None, 'return_share_on_source_cells': None, 'produce_share_on_source_cells': None, 'attack_share_on_source_cells': None, 'unavailable_reason': 'source-cell metrics unavailable because mask bit semantics are ambiguous.'}

### Economy metrics

- {'harvest_action_count': 8504, 'return_action_count': 0, 'produce_action_count': 8360, 'first_produce_step': 6, 'economy_activity_present': True, 'worker_count_proxy': None, 'worker_count_proxy_reason': 'not present in env info payload', 'base_count_proxy': None, 'base_count_proxy_reason': 'not present in env info payload', 'barracks_count_proxy': None, 'barracks_count_proxy_reason': 'not present in env info payload', 'resource_proxy': None, 'resource_proxy_reason': 'not present in env info payload', 'first_barracks_or_unit_production_step': 6}

### Production metrics

- {'produce_action_count': 8360, 'produce_action_share': 0.0016987229504785684, 'produce_unit_type_distribution': {'3': 8360}, 'first_produce_step': 6, 'unit_production_diversity_proxy': 1, 'produce_unit_type_distribution_reason': 'derived from produce_type branch index (legacy032 gridmode)'}

### Combat/contact metrics

- {'attack_action_count': 40, 'attack_action_share': 8.127861007074491e-06, 'first_attack_step': 3006, 'episodes_with_attack_action': 8, 'combat_activity_present': True, 'contact_seen': None, 'first_contact_step': None, 'episodes_with_contact': None, 'timeout_or_no_contact_episode_count': 0, 'contact_limitation': 'contact cannot be determined exactly from available info; attack_action_count is used as weak proxy.'}

### Limitations

- source-cell metrics unavailable because mask bit semantics are ambiguous.
- contact cannot be determined exactly from available info; attack_action_count is used as weak proxy.

## stochastic

### All-cell metrics

- {'global_noop_share_all_cells': 0.16629786497347065, 'global_non_noop_share_all_cells': 0.8337021350265293, 'action_type_share_all_cells': {'noop': 0.16629786497347065, 'move': 0.16624726903870163, 'harvest': 0.16782935718372868, 'return': 0.16604488529962547, 'produce': 0.16755808982261755, 'attack': 0.16602253368185602}, 'repeated_same_action_share': 0.1911697808954924, 'policy_entropy_proxy': 0.000587696784248365, 'source_cell_valid_share_observed_mask_bit0': 0.003434834079659973}

### Source-cell metrics

- {'source_cell_valid_share_mean': None, 'source_cell_count_mean': None, 'noop_share_on_source_cells': None, 'non_noop_share_on_source_cells': None, 'action_type_share_on_source_cells': None, 'move_share_on_source_cells': None, 'harvest_share_on_source_cells': None, 'return_share_on_source_cells': None, 'produce_share_on_source_cells': None, 'attack_share_on_source_cells': None, 'unavailable_reason': 'source-cell metrics unavailable because mask bit semantics are ambiguous.'}

### Economy metrics

- {'harvest_action_count': 825946, 'return_action_count': 817164, 'produce_action_count': 824611, 'first_produce_step': 6, 'economy_activity_present': True, 'worker_count_proxy': None, 'worker_count_proxy_reason': 'not present in env info payload', 'base_count_proxy': None, 'base_count_proxy_reason': 'not present in env info payload', 'barracks_count_proxy': None, 'barracks_count_proxy_reason': 'not present in env info payload', 'resource_proxy': None, 'resource_proxy_reason': 'not present in env info payload', 'first_barracks_or_unit_production_step': 6}

### Production metrics

- {'produce_action_count': 824611, 'produce_action_share': 0.16755808982261755, 'produce_unit_type_distribution': {'0': 116803, '1': 116875, '2': 116293, '3': 124251, '4': 116696, '5': 116989, '6': 116704}, 'first_produce_step': 6, 'unit_production_diversity_proxy': 7, 'produce_unit_type_distribution_reason': 'derived from produce_type branch index (legacy032 gridmode)'}

### Combat/contact metrics

- {'attack_action_count': 817054, 'attack_action_share': 0.16602253368185602, 'first_attack_step': 6, 'episodes_with_attack_action': 8, 'combat_activity_present': True, 'contact_seen': None, 'first_contact_step': None, 'episodes_with_contact': None, 'timeout_or_no_contact_episode_count': 0, 'contact_limitation': 'contact cannot be determined exactly from available info; attack_action_count is used as weak proxy.'}

### Limitations

- source-cell metrics unavailable because mask bit semantics are ambiguous.
- contact cannot be determined exactly from available info; attack_action_count is used as weak proxy.

## Interpretation

- agent has economy/production activity but sparse combat

## Recommendation for final comparison

- For final comparison, prioritize economy/production progression and first-attack timing, not only all-cell noop_share or return.

## Warnings

- source-cell metrics unavailable because mask bit semantics are ambiguous.

## Errors

- none