# Gridnet Teacher Rollout Export Summary

- batch_name: D_activity_shaping_mild_stoch_ab
- checkpoint: agent_final.pt
- deterministic_mode: False
- opponent: randomBiasedAI
- episodes: 4
- total_steps: 2048

## Action Distribution (full grid)

- Attack: 195886 (0.1661)
- Harvest: 196158 (0.1663)
- Move: 196261 (0.1664)
- NoOp: 197809 (0.1677)
- Produce: 196897 (0.1669)
- Return: 196637 (0.1667)

## Per-Episode

| episode | steps | return | done |
|---------|-------|--------|------|
| 0 | 512 | 8.000 | True |
| 1 | 512 | 18.000 | True |
| 2 | 512 | 6.000 | True |
| 3 | 512 | 4.000 | True |

## Notes
- action_t shape per step: (576, 7) — matrix_576x7, supported_exact by adapter.
- observation_t shape per step: (24, 24, 27).
- Run adapt_teacher_dataset.py on this batch dir for Unity-contract-aligned output.
- Semantic weakening expected: Gridnet produce branch=7, attack branch=49 vs Unity 4/9.
