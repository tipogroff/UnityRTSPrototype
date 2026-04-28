# Gridnet Visual Eval Summary

- visual_eval_status: active
- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_teacher_runs\gridnet_fresh_100k_v2_20260428T191104Z\agent_final.pt
- opponent: randomBiasedAI
- max_steps: 300
- steps_run: 300
- episode_done: True

## Actor-Level Metrics
- actor_level_move_share: 0.008032
- actor_noop_share: 0.954819
- effective_position_delta_count: 13
- no_effect_action_share: 0.976190
- ready_movable_actor_choice_count: 912

## Notes
- deterministic=True rollout (argmax policy).
- visual_eval_status=unavailable means render failed or no display; metrics are still valid.
