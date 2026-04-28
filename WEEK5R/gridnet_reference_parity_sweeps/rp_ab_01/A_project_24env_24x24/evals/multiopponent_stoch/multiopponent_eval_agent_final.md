# Gridnet Multi-Opponent Eval Summary

- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_reference_parity_sweeps\rp_ab_01\A_project_24env_24x24\A_project_24env_24x24_20260428T142235Z\agent_final.pt
- timestamp_utc: 2026-04-28T14:33:26Z
- deterministic_mode: False
- episodes_per_opponent: 4

## Aggregate Verdict: CANDIDATE_VIABLE

PASS on 4/4 opponents. Consider continuation training or BC export.

- pass_count: 4 / 4
- any_positive_position_delta: True

## Per-Opponent Results

| opponent | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |
|----------|--------|------------|------------|-----------|-----------|---------------|
| randomBiasedAI | PASS | 0.2615 | 0.5408 | 174 | 0.8424 | 585 |
| lightRushAI | PASS | 0.3846 | 0.5007 | 214 | 0.8074 | 638 |
| workerRushAI | PASS | 0.2390 | 0.5624 | 159 | 0.8925 | 537 |
| coacAI | PASS | 0.2271 | 0.5707 | 166 | 0.8750 | 488 |

## Notes
- Each opponent was evaluated in an independent subprocess (separate JVM).
- opponent-sampling=static within each subprocess.
- PASS requires: effective_position_delta_count > 0, actor_level_move_share > 0, no_effect_action_share < 1.0.
