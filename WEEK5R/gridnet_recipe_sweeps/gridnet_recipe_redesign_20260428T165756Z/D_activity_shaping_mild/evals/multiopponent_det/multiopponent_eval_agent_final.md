# Gridnet Multi-Opponent Eval Summary

- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_recipe_sweeps\gridnet_recipe_redesign_20260428T165756Z\D_activity_shaping_mild\D_activity_shaping_mild_20260428T172154Z\agent_final.pt
- timestamp_utc: 2026-04-28T17:32:17Z
- deterministic_mode: True
- episodes_per_opponent: 4

## Aggregate Verdict: CANDIDATE_VIABLE

PASS on 4/4 opponents. Consider continuation training or BC export.

- pass_count: 4 / 4
- any_positive_position_delta: True

## Per-Opponent Results

| opponent | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |
|----------|--------|------------|------------|-----------|-----------|---------------|
| randomBiasedAI | PASS | 0.0132 | 0.9326 | 52 | 0.9767 | 2564 |
| lightRushAI | PASS | 0.0132 | 0.9326 | 52 | 0.9767 | 2564 |
| workerRushAI | PASS | 0.0132 | 0.9326 | 52 | 0.9767 | 2564 |
| coacAI | PASS | 0.0132 | 0.9326 | 52 | 0.9767 | 2564 |

## Notes
- Each opponent was evaluated in an independent subprocess (separate JVM).
- opponent-sampling=static within each subprocess.
- PASS requires: effective_position_delta_count > 0, actor_level_move_share > 0, no_effect_action_share < 1.0.
