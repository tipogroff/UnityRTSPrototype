# Gridnet Actor-Level Evaluation

- status: SUSPICIOUS
- verdict: Non-collapsed action mix detected, but effective movement evidence is weak.
- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_teacher_runs\gridnet_200k_continue_20260428T183153Z\checkpoints\agent_step_000200000.pt
- episodes: 4
- map_path: maps/24x24/basesWorkers24x24.xml

## Key Metrics
- actor_level_move_share: 0.014771
- actor_noop_share: 0.974889
- effective_position_delta_count: 52
- no_effect_action_share: 1.000000
- ready_movable_actor_choice_count: 2480

## Notes
- Vocabulary is aligned with teacher_behavior_gate statuses (PASS/SUSPICIOUS/FAIL_*).
- PASS requires actor-level effective movement evidence, not full-tensor move share only.
