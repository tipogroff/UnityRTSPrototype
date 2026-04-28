# Gridnet Multi-Opponent Eval Summary

- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_recipe_sweeps\gridnet_recipe_redesign_20260428T164010Z\A_low_entropy\A_low_entropy_20260428T164010Z\agent_final.pt
- timestamp_utc: 2026-04-28T16:50:35Z
- deterministic_mode: True
- episodes_per_opponent: 4

## Aggregate Verdict: FAIL_ALL

No PASS on any of 4 opponents.

- pass_count: 0 / 4
- any_positive_position_delta: True

## Per-Opponent Results

| opponent | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |
|----------|--------|------------|------------|-----------|-----------|---------------|
| randomBiasedAI | SUSPICIOUS | 0.0013 | 0.9909 | 24 | 1.0000 | 3008 |
| lightRushAI | SUSPICIOUS | 0.0013 | 0.9909 | 24 | 1.0000 | 3008 |
| workerRushAI | SUSPICIOUS | 0.0013 | 0.9909 | 24 | 1.0000 | 3008 |
| coacAI | SUSPICIOUS | 0.0013 | 0.9909 | 24 | 1.0000 | 3008 |

## Notes
- Each opponent was evaluated in an independent subprocess (separate JVM).
- opponent-sampling=static within each subprocess.
- PASS requires: effective_position_delta_count > 0, actor_level_move_share > 0, no_effect_action_share < 1.0.
