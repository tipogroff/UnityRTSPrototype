# Gridnet Actor-Level Evaluation

- status: PASS
- verdict: Actor-level effective movement detected.
- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_teacher_runs\gridnet_fresh_100k_v2_20260428T191104Z\checkpoints\agent_step_000100000.pt
- episodes: 4
- map_path: maps/24x24/basesWorkers24x24.xml

## Key Metrics
- actor_level_move_share: 0.004098
- actor_noop_share: 0.945355
- effective_position_delta_count: 36
- no_effect_action_share: 0.972973
- ready_movable_actor_choice_count: 2884

## Notes
- Vocabulary is aligned with teacher_behavior_gate statuses (PASS/SUSPICIOUS/FAIL_*).
- PASS requires actor-level effective movement evidence, not full-tensor move share only.
