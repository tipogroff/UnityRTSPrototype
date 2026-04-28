# Gridnet Actor-Level Evaluation

- status: SUSPICIOUS
- verdict: Non-collapsed action mix detected, but effective movement evidence is weak.
- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_recipe_sweeps\gridnet_recipe_redesign_20260428T165756Z\C_passive_warmup_entropy_decay\C_passive_warmup_entropy_decay_stage2_20260428T171458Z\checkpoints\agent_step_000100000.pt
- episodes: 4
- map_path: maps/24x24/basesWorkers24x24.xml

## Key Metrics
- actor_level_move_share: 0.013196
- actor_noop_share: 0.976540
- effective_position_delta_count: 52
- no_effect_action_share: 1.000000
- ready_movable_actor_choice_count: 2500

## Notes
- Vocabulary is aligned with teacher_behavior_gate statuses (PASS/SUSPICIOUS/FAIL_*).
- PASS requires actor-level effective movement evidence, not full-tensor move share only.
