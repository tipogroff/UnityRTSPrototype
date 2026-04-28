# Gridnet Actor-Level Evaluation

- status: FAIL_COLLAPSED_NOOP
- verdict: Collapsed to NoOp on ready actors.
- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_recipe_sweeps\gridnet_recipe_redesign_20260428T165756Z\B_entropy_decay\B_entropy_decay_20260428T165757Z\checkpoints\agent_step_000020000.pt
- episodes: 4
- map_path: maps/24x24/basesWorkers24x24.xml

## Key Metrics
- actor_level_move_share: 0.000000
- actor_noop_share: 0.997972
- effective_position_delta_count: 0
- no_effect_action_share: 1.000000
- ready_movable_actor_choice_count: 948

## Notes
- Vocabulary is aligned with teacher_behavior_gate statuses (PASS/SUSPICIOUS/FAIL_*).
- PASS requires actor-level effective movement evidence, not full-tensor move share only.
