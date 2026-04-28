# Gridnet Actor-Level Evaluation

- status: FAIL_COLLAPSED_NOOP
- verdict: Collapsed to NoOp on ready actors.
- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_teacher_runs\gridnet_fresh_100k_v2_20260428T191104Z\checkpoints\agent_step_000050000.pt
- episodes: 4
- map_path: maps/24x24/basesWorkers24x24.xml

## Key Metrics
- actor_level_move_share: 0.000000
- actor_noop_share: 0.957369
- effective_position_delta_count: 20
- no_effect_action_share: 0.970588
- ready_movable_actor_choice_count: 3044

## Notes
- Vocabulary is aligned with teacher_behavior_gate statuses (PASS/SUSPICIOUS/FAIL_*).
- PASS requires actor-level effective movement evidence, not full-tensor move share only.
