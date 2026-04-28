# Gridnet Visual Eval Summary

- visual_eval_status: active
- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_teacher_runs\gridnet_200k_continue_20260428T183153Z\agent_final.pt
- opponent: randomBiasedAI
- max_steps: 300
- steps_run: 300
- episode_done: True

## Actor-Level Metrics
- actor_level_move_share: 0.019890
- actor_noop_share: 0.972376
- effective_position_delta_count: 17
- no_effect_action_share: 1.000000
- ready_movable_actor_choice_count: 760

## Notes
- deterministic=True rollout (argmax policy).
- visual_eval_status=unavailable means render failed or no display; metrics are still valid.
