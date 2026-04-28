# Gridnet Visual Eval Summary

- visual_eval_status: active
- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_teacher_runs\gridnet_100k_20260427T221123Z\agent_final.pt
- opponent: randomBiasedAI
- max_steps: 300
- steps_run: 300
- episode_done: True

## Actor-Level Metrics
- actor_level_move_share: 0.013684
- actor_noop_share: 0.947368
- effective_position_delta_count: 17
- no_effect_action_share: 0.978723
- ready_movable_actor_choice_count: 805

## Notes
- deterministic=True rollout (argmax policy).
- visual_eval_status=unavailable means render failed or no display; metrics are still valid.
