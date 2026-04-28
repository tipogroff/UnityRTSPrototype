# Gridnet Teacher Rollout Export Summary

- batch_name: gridnet_200k_stoch_ab
- checkpoint: agent_final.pt
- deterministic_mode: False
- opponent: randomBiasedAI
- episodes: 4
- total_steps: 2048

## Action Distribution (full grid)

- Attack: 196728 (0.1668)
- Harvest: 196022 (0.1662)
- Move: 196205 (0.1663)
- NoOp: 197783 (0.1677)
- Produce: 196661 (0.1667)
- Return: 196249 (0.1664)

## Per-Episode

| episode | steps | return | done |
|---------|-------|--------|------|
| 0 | 512 | 17.000 | True |
| 1 | 512 | 13.000 | True |
| 2 | 512 | 20.000 | True |
| 3 | 512 | 5.000 | True |

## Notes
- action_t shape per step: (576, 7) — matrix_576x7, supported_exact by adapter.
- observation_t shape per step: (24, 24, 27).
- Run adapt_teacher_dataset.py on this batch dir for Unity-contract-aligned output.
- Semantic weakening expected: Gridnet produce branch=7, attack branch=49 vs Unity 4/9.
