# Gridnet Multi-Opponent Eval Summary

- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_recipe_sweeps\gridnet_recipe_redesign_20260428T165756Z\D_activity_shaping_mild\D_activity_shaping_mild_20260428T172154Z\agent_final.pt
- timestamp_utc: 2026-04-28T17:32:43Z
- deterministic_mode: False
- episodes_per_opponent: 4

## Aggregate Verdict: CANDIDATE_VIABLE

PASS on 4/4 opponents. Consider continuation training or BC export.

- pass_count: 4 / 4
- any_positive_position_delta: True

## Per-Opponent Results

| opponent | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |
|----------|--------|------------|------------|-----------|-----------|---------------|
| randomBiasedAI | PASS | 0.2549 | 0.5499 | 170 | 0.8400 | 531 |
| lightRushAI | PASS | 0.2024 | 0.5022 | 142 | 0.8722 | 512 |
| workerRushAI | PASS | 0.0777 | 0.5322 | 74 | 0.9499 | 268 |
| coacAI | PASS | 0.2398 | 0.5426 | 172 | 0.8597 | 460 |

## Notes
- Each opponent was evaluated in an independent subprocess (separate JVM).
- opponent-sampling=static within each subprocess.
- PASS requires: effective_position_delta_count > 0, actor_level_move_share > 0, no_effect_action_share < 1.0.
