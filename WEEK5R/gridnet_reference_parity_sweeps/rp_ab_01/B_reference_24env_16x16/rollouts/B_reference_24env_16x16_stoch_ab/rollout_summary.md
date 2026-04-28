# Gridnet Teacher Rollout Export Summary

- batch_name: B_reference_24env_16x16_stoch_ab
- checkpoint: agent_final.pt
- deterministic_mode: False
- opponent: randomBiasedAI
- episodes: 4
- total_steps: 2048

## Action Distribution (full grid)

- Attack: 87111 (0.1662)
- Harvest: 86550 (0.1651)
- Move: 87231 (0.1664)
- NoOp: 88468 (0.1687)
- Produce: 87705 (0.1673)
- Return: 87223 (0.1664)

## Per-Episode

| episode | steps | return | done |
|---------|-------|--------|------|
| 0 | 512 | 14.000 | True |
| 1 | 512 | 20.000 | True |
| 2 | 512 | 26.000 | True |
| 3 | 512 | 14.000 | True |

## Notes
- action_t shape per step: (576, 7) — matrix_576x7, supported_exact by adapter.
- observation_t shape per step: (24, 24, 27).
- Run adapt_teacher_dataset.py on this batch dir for Unity-contract-aligned output.
- Semantic weakening expected: Gridnet produce branch=7, attack branch=49 vs Unity 4/9.
