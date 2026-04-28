# Gridnet Actor-Level Evaluation

- status: SUSPICIOUS
- verdict: Non-collapsed action mix detected, but effective movement evidence is weak.
- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_recipe_sweeps\gridnet_recipe_redesign_20260428T164010Z\A_low_entropy\A_low_entropy_20260428T164010Z\agent_final.pt
- episodes: 4
- map_path: maps/24x24/basesWorkers24x24.xml

## Key Metrics
- actor_level_move_share: 0.001304
- actor_noop_share: 0.990874
- effective_position_delta_count: 24
- no_effect_action_share: 1.000000
- ready_movable_actor_choice_count: 3008

## Notes
- Vocabulary is aligned with teacher_behavior_gate statuses (PASS/SUSPICIOUS/FAIL_*).
- PASS requires actor-level effective movement evidence, not full-tensor move share only.
