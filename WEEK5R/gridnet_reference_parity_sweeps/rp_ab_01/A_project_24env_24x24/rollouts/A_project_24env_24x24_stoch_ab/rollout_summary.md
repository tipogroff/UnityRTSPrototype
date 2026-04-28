# Gridnet Teacher Rollout Export Summary

- batch_name: A_project_24env_24x24_stoch_ab
- checkpoint: agent_final.pt
- deterministic_mode: False
- opponent: randomBiasedAI
- episodes: 4
- total_steps: 2048

## Action Distribution (full grid)

- Attack: 195939 (0.1661)
- Harvest: 196166 (0.1663)
- Move: 196092 (0.1662)
- NoOp: 198025 (0.1679)
- Produce: 196803 (0.1668)
- Return: 196623 (0.1667)

## Per-Episode

| episode | steps | return | done |
|---------|-------|--------|------|
| 0 | 512 | 9.000 | True |
| 1 | 512 | 21.000 | True |
| 2 | 512 | 7.000 | True |
| 3 | 512 | 7.000 | True |

## Notes
- action_t shape per step: (576, 7) — matrix_576x7, supported_exact by adapter.
- observation_t shape per step: (24, 24, 27).
- Run adapt_teacher_dataset.py on this batch dir for Unity-contract-aligned output.
- Semantic weakening expected: Gridnet produce branch=7, attack branch=49 vs Unity 4/9.
