# Gridnet Teacher Rollout Export Summary

- batch_name: gridnet_fresh_100k_v2_stoch_ab
- checkpoint: agent_final.pt
- deterministic_mode: False
- opponent: randomBiasedAI
- episodes: 4
- total_steps: 2048

## Action Distribution (full grid)

- Attack: 196695 (0.1667)
- Harvest: 196037 (0.1662)
- Move: 196206 (0.1663)
- NoOp: 197870 (0.1677)
- Produce: 196625 (0.1667)
- Return: 196215 (0.1663)

## Per-Episode

| episode | steps | return | done |
|---------|-------|--------|------|
| 0 | 512 | 22.000 | True |
| 1 | 512 | 15.000 | True |
| 2 | 512 | 3.000 | True |
| 3 | 512 | 4.000 | True |

## Notes
- action_t shape per step: (576, 7) — matrix_576x7, supported_exact by adapter.
- observation_t shape per step: (24, 24, 27).
- Run adapt_teacher_dataset.py on this batch dir for Unity-contract-aligned output.
- Semantic weakening expected: Gridnet produce branch=7, attack branch=49 vs Unity 4/9.
