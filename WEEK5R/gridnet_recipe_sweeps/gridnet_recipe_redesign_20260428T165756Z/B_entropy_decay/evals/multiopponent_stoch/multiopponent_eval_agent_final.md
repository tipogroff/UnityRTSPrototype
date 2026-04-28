# Gridnet Multi-Opponent Eval Summary

- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_recipe_sweeps\gridnet_recipe_redesign_20260428T165756Z\B_entropy_decay\B_entropy_decay_20260428T165757Z\agent_final.pt
- timestamp_utc: 2026-04-28T17:09:01Z
- deterministic_mode: False
- episodes_per_opponent: 4

## Aggregate Verdict: CANDIDATE_VIABLE

PASS on 4/4 opponents. Consider continuation training or BC export.

- pass_count: 4 / 4
- any_positive_position_delta: True

## Per-Opponent Results

| opponent | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |
|----------|--------|------------|------------|-----------|-----------|---------------|
| randomBiasedAI | PASS | 0.2038 | 0.6242 | 158 | 0.8769 | 575 |
| lightRushAI | PASS | 0.1840 | 0.5251 | 143 | 0.9079 | 463 |
| workerRushAI | PASS | 0.2175 | 0.6065 | 164 | 0.8871 | 546 |
| coacAI | PASS | 0.3935 | 0.4911 | 218 | 0.7917 | 635 |

## Notes
- Each opponent was evaluated in an independent subprocess (separate JVM).
- opponent-sampling=static within each subprocess.
- PASS requires: effective_position_delta_count > 0, actor_level_move_share > 0, no_effect_action_share < 1.0.
