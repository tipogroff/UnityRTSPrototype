# Gridnet Actor-Level Evaluation

- status: PASS
- verdict: Actor-level effective movement detected.
- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_teacher_runs\gridnet_100k_20260427T221123Z\agent_final.pt
- episodes: 4
- map_path: maps/24x24/basesWorkers24x24.xml

## Key Metrics
- actor_level_move_share: 0.013196
- actor_noop_share: 0.932551
- effective_position_delta_count: 52
- no_effect_action_share: 0.976744
- ready_movable_actor_choice_count: 2500

## Notes
- Vocabulary is aligned with teacher_behavior_gate statuses (PASS/SUSPICIOUS/FAIL_*).
- PASS requires actor-level effective movement evidence, not full-tensor move share only.
