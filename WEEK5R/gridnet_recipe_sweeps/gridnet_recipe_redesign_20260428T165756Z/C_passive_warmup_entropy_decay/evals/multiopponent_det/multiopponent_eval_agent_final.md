# Gridnet Multi-Opponent Eval Summary

- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_recipe_sweeps\gridnet_recipe_redesign_20260428T165756Z\C_passive_warmup_entropy_decay\C_passive_warmup_entropy_decay_stage2_20260428T171458Z\agent_final.pt
- timestamp_utc: 2026-04-28T17:20:59Z
- deterministic_mode: True
- episodes_per_opponent: 4

## Aggregate Verdict: FAIL_ALL

No PASS on any of 4 opponents.

- pass_count: 0 / 4
- any_positive_position_delta: True

## Per-Opponent Results

| opponent | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |
|----------|--------|------------|------------|-----------|-----------|---------------|
| randomBiasedAI | SUSPICIOUS | 0.0132 | 0.9765 | 52 | 1.0000 | 2500 |
| lightRushAI | SUSPICIOUS | 0.0132 | 0.9765 | 52 | 1.0000 | 2500 |
| workerRushAI | SUSPICIOUS | 0.0132 | 0.9765 | 52 | 1.0000 | 2500 |
| coacAI | SUSPICIOUS | 0.0132 | 0.9765 | 52 | 1.0000 | 2500 |

## Notes
- Each opponent was evaluated in an independent subprocess (separate JVM).
- opponent-sampling=static within each subprocess.
- PASS requires: effective_position_delta_count > 0, actor_level_move_share > 0, no_effect_action_share < 1.0.
