# Gridnet Multi-Opponent Eval Summary

- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_recipe_sweeps\gridnet_recipe_redesign_20260428T165756Z\C_passive_warmup_entropy_decay\C_passive_warmup_entropy_decay_stage2_20260428T171458Z\agent_final.pt
- timestamp_utc: 2026-04-28T17:21:26Z
- deterministic_mode: False
- episodes_per_opponent: 4

## Aggregate Verdict: CANDIDATE_VIABLE

PASS on 4/4 opponents. Consider continuation training or BC export.

- pass_count: 4 / 4
- any_positive_position_delta: True

## Per-Opponent Results

| opponent | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |
|----------|--------|------------|------------|-----------|-----------|---------------|
| randomBiasedAI | PASS | 0.1853 | 0.5038 | 149 | 0.8698 | 479 |
| lightRushAI | PASS | 0.0992 | 0.5088 | 98 | 0.9354 | 292 |
| workerRushAI | PASS | 0.2799 | 0.4583 | 183 | 0.8464 | 518 |
| coacAI | PASS | 0.2769 | 0.5100 | 188 | 0.8369 | 548 |

## Notes
- Each opponent was evaluated in an independent subprocess (separate JVM).
- opponent-sampling=static within each subprocess.
- PASS requires: effective_position_delta_count > 0, actor_level_move_share > 0, no_effect_action_share < 1.0.
