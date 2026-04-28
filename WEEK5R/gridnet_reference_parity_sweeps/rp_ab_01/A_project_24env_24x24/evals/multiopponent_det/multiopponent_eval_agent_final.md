# Gridnet Multi-Opponent Eval Summary

- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_reference_parity_sweeps\rp_ab_01\A_project_24env_24x24\A_project_24env_24x24_20260428T142235Z\agent_final.pt
- timestamp_utc: 2026-04-28T14:33:01Z
- deterministic_mode: True
- episodes_per_opponent: 4

## Aggregate Verdict: FAIL_ALL

No PASS on any of 4 opponents.

- pass_count: 0 / 4
- any_positive_position_delta: True

## Per-Opponent Results

| opponent | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |
|----------|--------|------------|------------|-----------|-----------|---------------|
| randomBiasedAI | FAIL_COLLAPSED_NOOP | 0.0000 | 0.9969 | 8 | 1.0000 | 1768 |
| lightRushAI | FAIL_COLLAPSED_NOOP | 0.0000 | 0.9969 | 8 | 1.0000 | 1768 |
| workerRushAI | FAIL_COLLAPSED_NOOP | 0.0000 | 0.9969 | 8 | 1.0000 | 1768 |
| coacAI | FAIL_COLLAPSED_NOOP | 0.0000 | 0.9969 | 8 | 1.0000 | 1768 |

## Notes
- Each opponent was evaluated in an independent subprocess (separate JVM).
- opponent-sampling=static within each subprocess.
- PASS requires: effective_position_delta_count > 0, actor_level_move_share > 0, no_effect_action_share < 1.0.
