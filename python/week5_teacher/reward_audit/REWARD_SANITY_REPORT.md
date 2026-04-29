# REWARD_SANITY_REPORT

- Decision: PARTIAL_PASS_REWARD_SANITY
- Modes present: combat_probe, economy_probe, mixed_probe, noop, production_probe, random_valid, scripted_probe

## Mode Summary
- combat_probe: status=ok, reward_total=0.000000, reward_nonzero_steps=0, done=2, terminal=0, timeout=0, invalid_action_attempts=14400
  probe_diagnostics={'move_towards_resource_count': 0, 'move_towards_base_count': 0, 'move_towards_enemy_count': 0, 'harvest_chosen_count': 0, 'return_chosen_count': 0, 'produce_chosen_count': 0, 'attack_chosen_count': 0, 'fallback_valid_move_count': 0, 'fallback_noop_count': 3200, 'no_target_found_count': 0, 'no_attack_window_reached_count': 1601, 'missing_barracks_or_build_path': 0}
- economy_probe: status=ok, reward_total=0.000000, reward_nonzero_steps=0, done=2, terminal=0, timeout=0, invalid_action_attempts=9000
  probe_diagnostics={'move_towards_resource_count': 0, 'move_towards_base_count': 0, 'move_towards_enemy_count': 0, 'harvest_chosen_count': 0, 'return_chosen_count': 0, 'produce_chosen_count': 0, 'attack_chosen_count': 0, 'fallback_valid_move_count': 0, 'fallback_noop_count': 2000, 'no_target_found_count': 0, 'no_attack_window_reached_count': 0, 'missing_barracks_or_build_path': 0}
- mixed_probe: status=ok, reward_total=0.000000, reward_nonzero_steps=0, done=2, terminal=0, timeout=0, invalid_action_attempts=14400
  probe_diagnostics={'move_towards_resource_count': 0, 'move_towards_base_count': 0, 'move_towards_enemy_count': 0, 'harvest_chosen_count': 0, 'return_chosen_count': 0, 'produce_chosen_count': 0, 'attack_chosen_count': 0, 'fallback_valid_move_count': 0, 'fallback_noop_count': 3200, 'no_target_found_count': 0, 'no_attack_window_reached_count': 0, 'missing_barracks_or_build_path': 0}
- noop: status=ok, reward_total=0.000000, reward_nonzero_steps=0, done=2, terminal=0, timeout=0, invalid_action_attempts=5400
  probe_diagnostics={'move_towards_resource_count': 0, 'move_towards_base_count': 0, 'move_towards_enemy_count': 0, 'harvest_chosen_count': 0, 'return_chosen_count': 0, 'produce_chosen_count': 0, 'attack_chosen_count': 0, 'fallback_valid_move_count': 0, 'fallback_noop_count': 0, 'no_target_found_count': 0, 'no_attack_window_reached_count': 0, 'missing_barracks_or_build_path': 0}
- production_probe: status=ok, reward_total=0.000000, reward_nonzero_steps=0, done=2, terminal=0, timeout=0, invalid_action_attempts=14400
  probe_diagnostics={'move_towards_resource_count': 0, 'move_towards_base_count': 0, 'move_towards_enemy_count': 0, 'harvest_chosen_count': 0, 'return_chosen_count': 0, 'produce_chosen_count': 0, 'attack_chosen_count': 0, 'fallback_valid_move_count': 0, 'fallback_noop_count': 3200, 'no_target_found_count': 0, 'no_attack_window_reached_count': 0, 'missing_barracks_or_build_path': 1600}
- random_valid: status=ok, reward_total=5.000000, reward_nonzero_steps=5, done=2, terminal=0, timeout=0, invalid_action_attempts=2167
  probe_diagnostics={'move_towards_resource_count': 0, 'move_towards_base_count': 0, 'move_towards_enemy_count': 0, 'harvest_chosen_count': 0, 'return_chosen_count': 0, 'produce_chosen_count': 0, 'attack_chosen_count': 0, 'fallback_valid_move_count': 0, 'fallback_noop_count': 0, 'no_target_found_count': 0, 'no_attack_window_reached_count': 0, 'missing_barracks_or_build_path': 0}
- scripted_probe: status=ok, reward_total=0.000000, reward_nonzero_steps=0, done=4, terminal=0, timeout=0, invalid_action_attempts=18000

## Decision Vocabulary
- PASS_REWARD_SANITY
- PARTIAL_PASS_REWARD_SANITY
- FAIL_REWARD_ALL_ZERO
- FAIL_REWARD_ENV_ERROR
- INCONCLUSIVE_NEEDS_MANUAL_CHECK
