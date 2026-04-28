# Gridnet Multi-Opponent Eval Summary

- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_recipe_sweeps\gridnet_recipe_redesign_20260428T164010Z\A_low_entropy\A_low_entropy_20260428T164010Z\agent_final.pt
- timestamp_utc: 2026-04-28T16:51:02Z
- deterministic_mode: False
- episodes_per_opponent: 4

## Aggregate Verdict: CANDIDATE_VIABLE

PASS on 4/4 opponents. Consider continuation training or BC export.

- pass_count: 4 / 4
- any_positive_position_delta: True

## Per-Opponent Results

| opponent | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |
|----------|--------|------------|------------|-----------|-----------|---------------|
| randomBiasedAI | PASS | 0.1128 | 0.4787 | 104 | 0.8979 | 379 |
| lightRushAI | PASS | 0.2420 | 0.5340 | 168 | 0.8678 | 497 |
| workerRushAI | PASS | 0.0912 | 0.5751 | 84 | 0.9421 | 275 |
| coacAI | PASS | 0.1727 | 0.5284 | 132 | 0.9155 | 393 |

## Notes
- Each opponent was evaluated in an independent subprocess (separate JVM).
- opponent-sampling=static within each subprocess.
- PASS requires: effective_position_delta_count > 0, actor_level_move_share > 0, no_effect_action_share < 1.0.
