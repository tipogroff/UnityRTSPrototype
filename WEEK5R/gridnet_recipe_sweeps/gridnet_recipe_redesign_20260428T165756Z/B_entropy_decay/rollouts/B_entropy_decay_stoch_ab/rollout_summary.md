# Gridnet Teacher Rollout Export Summary

- batch_name: B_entropy_decay_stoch_ab
- checkpoint: agent_final.pt
- deterministic_mode: False
- opponent: randomBiasedAI
- episodes: 4
- total_steps: 2048

## Action Distribution (full grid)

- Attack: 195860 (0.1660)
- Harvest: 196100 (0.1662)
- Move: 196095 (0.1662)
- NoOp: 198245 (0.1681)
- Produce: 196811 (0.1668)
- Return: 196537 (0.1666)

## Per-Episode

| episode | steps | return | done |
|---------|-------|--------|------|
| 0 | 512 | 9.000 | True |
| 1 | 512 | 14.000 | True |
| 2 | 512 | 2.000 | True |
| 3 | 512 | 3.000 | True |

## Notes
- action_t shape per step: (576, 7) — matrix_576x7, supported_exact by adapter.
- observation_t shape per step: (24, 24, 27).
- Run adapt_teacher_dataset.py on this batch dir for Unity-contract-aligned output.
- Semantic weakening expected: Gridnet produce branch=7, attack branch=49 vs Unity 4/9.
