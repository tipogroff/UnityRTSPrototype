# STAGE5D LARGE MAP WIN DIAGNOSTICS REPORT

- checkpoint path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_main_20260430T130208Z\stage_003000000\agent_final.pt
- metadata path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_main_20260430T130208Z\stage_003000000\model_metadata.json
- max_steps_per_episode=6000
- eval mode: both
- episodes: 16

## Technical compatibility

- checkpoint_load_ok: True
- policy_architecture_load_ok: True
- inference_ok: True
- env_matches_target_24x24: True
- mask_used_during_eval: True

## Primary mode: stochastic

### Episode outcomes

- mean_return: -10.0
- win_count: 0
- loss_count: 0
- draw_count: 16
- terminal_types_unavailable_reason: None

### Base destruction

- {'enemy_base_destroyed_count': None, 'own_base_destroyed_count': None, 'episodes_with_enemy_base_destroyed': None, 'episodes_with_own_base_destroyed': None, 'first_enemy_base_destroyed_step': None, 'mean_enemy_base_destroyed_step': None, 'first_enemy_base_damage_step': None, 'enemy_base_detection_available': False, 'own_base_detection_available': False, 'enemy_base_damage_detection_available': False, 'unavailable_reason': 'base destruction cannot be determined exactly from available info payload; fields are null when not detectable.'}

### Economy/production

- {'first_harvest_step': 6, 'first_return_step': 6, 'first_produce_step': 6, 'first_barracks_or_unit_production_step': 6, 'harvest_action_count': 1464644, 'return_action_count': 1448789, 'produce_action_count': 1462346, 'economy_activity_present': True, 'worker_count_proxy': None, 'worker_count_proxy_reason': 'not present in env info payload', 'base_count_proxy': None, 'base_count_proxy_reason': 'not present in env info payload', 'barracks_count_proxy': None, 'barracks_count_proxy_reason': 'not present in env info payload', 'resource_proxy': None, 'resource_proxy_reason': 'not present in env info payload'}
- {'produce_action_count': 1462346, 'produce_action_share': 0.1675772368903557, 'produce_unit_type_distribution': {'0': 207006, '1': 207898, '2': 206418, '3': 220355, '4': 206937, '5': 207127, '6': 206605}, 'first_produce_step': 6, 'unit_production_diversity_proxy': 7, 'produce_unit_type_distribution_reason': 'derived from produce_type branch index (legacy032 gridmode)'}

### Combat/contact

- {'attack_action_count': 1449229, 'attack_action_share': 0.16607409699303263, 'episodes_with_attack_action': 16, 'first_attack_step': 6, 'contact_seen': None, 'first_contact_step': None, 'episodes_with_contact': None, 'timeout_or_no_contact_episode_count': 0, 'contact_limitation': 'contact cannot be determined exactly from available info; attack_action_count is used as weak proxy.'}

### Movement/aggression

- {'move_action_count': 1450353, 'move_share': 0.16620290154015402, 'first_move_step': 6, 'average_move_actions_before_first_attack': 0.0, 'movement_toward_enemy_base_proxy': None, 'movement_toward_enemy_base_proxy_reason': 'movement_toward_enemy_base_proxy cannot be determined safely because enemy-base direction semantics are unavailable.'}

### All-cell/source-cell

- {'global_noop_share_all_cells': 0.16628151356802348, 'global_non_noop_share_all_cells': 0.8337184864319765, 'action_type_share_all_cells': {'noop': 0.16628151356802348, 'move': 0.16620290154015402, 'harvest': 0.16784057572423908, 'return': 0.1660236752841951, 'produce': 0.1675772368903557, 'attack': 0.16607409699303263}, 'repeated_same_action_share': 0.19113433983493908, 'policy_entropy_proxy': 0.0006555096716573923, 'source_cell_valid_share_observed_mask_bit0': 0.003429134597005968}
- {'source_cell_valid_share_mean': None, 'source_cell_count_mean': None, 'noop_share_on_source_cells': None, 'non_noop_share_on_source_cells': None, 'action_type_share_on_source_cells': None, 'move_share_on_source_cells': None, 'harvest_share_on_source_cells': None, 'return_share_on_source_cells': None, 'produce_share_on_source_cells': None, 'attack_share_on_source_cells': None, 'unavailable_reason': 'source-cell metrics unavailable because mask bit semantics are ambiguous.'}

## Manual visual observation cross-check

- confirmed_by_metrics: partial
- matching evidence: ['economy/production timing detected']
- contradictions: ['stochastic mean_return remains -10.0']
- unresolved: ['exact enemy base destruction not confirmed by available metrics', 'exact contact timing unavailable; only attack proxy is available']

## Interpretation

- agent has economy/production activity with attack activity; contact/outcome observability remains limited

## Recommendation for next prompt

- Hold for reward or eval diagnostics: outcome/base-destruction instrumentation is insufficient for reliable 5M decision.

## Decision for next prompt

- HOLD_FOR_REWARD_OR_EVAL_DIAGNOSTICS

## Exact next action

- Improve evaluation instrumentation for terminal outcomes/base destruction/contact in the legacy032 diagnostics path and rerun Stage 5D diagnostics before any 5M decision.

## Limitations and warnings

- source-cell metrics unavailable because mask bit semantics are ambiguous.
- movement_toward_enemy_base_proxy cannot be determined safely because enemy-base direction semantics are unavailable.
- contact cannot be determined exactly from available info; attack_action_count is used as weak proxy.
- base destruction cannot be determined exactly from available info payload; fields are null when not detectable.

- json_output: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage5d_large_map_win_diagnostics_20260501T083049Z.json
- md_output: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage5d_large_map_win_diagnostics_20260501T083049Z.md
- action_trace_output: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage5d_large_map_action_trace_20260501T083049Z.jsonl