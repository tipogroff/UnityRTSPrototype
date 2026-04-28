# Gridnet Teacher Rollout Export Summary

- batch_name: gridnet_100k_stoch_ab
- checkpoint: agent_final.pt
- deterministic_mode: False
- opponent: randomBiasedAI
- episodes: 4
- total_steps: 2048

## Action Distribution (full grid)

- Attack: 196753 (0.1668)
- Harvest: 196013 (0.1662)
- Move: 196361 (0.1665)
- NoOp: 197713 (0.1676)
- Produce: 196576 (0.1666)
- Return: 196232 (0.1663)

## Per-Episode

| episode | steps | return | done |
|---------|-------|--------|------|
| 0 | 512 | 12.000 | True |
| 1 | 512 | 19.000 | True |
| 2 | 512 | 15.000 | True |
| 3 | 512 | 5.000 | True |

## Notes
- action_t shape per step: (576, 7) — matrix_576x7, supported_exact by adapter.
- observation_t shape per step: (24, 24, 27).
- Run adapt_teacher_dataset.py on this batch dir for Unity-contract-aligned output.
- Semantic weakening expected: Gridnet produce branch=7, attack branch=49 vs Unity 4/9.
