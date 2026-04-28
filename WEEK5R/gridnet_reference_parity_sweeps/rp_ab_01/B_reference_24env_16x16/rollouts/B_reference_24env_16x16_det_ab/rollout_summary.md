# Gridnet Teacher Rollout Export Summary

- batch_name: B_reference_24env_16x16_det_ab
- checkpoint: agent_final.pt
- deterministic_mode: True
- opponent: randomBiasedAI
- episodes: 4
- total_steps: 2048

## Action Distribution (full grid)

- Harvest: 4 (0.0000)
- NoOp: 524148 (0.9997)
- Produce: 136 (0.0003)

## Per-Episode

| episode | steps | return | done |
|---------|-------|--------|------|
| 0 | 512 | 1.000 | True |
| 1 | 512 | 1.000 | True |
| 2 | 512 | 1.000 | True |
| 3 | 512 | 1.000 | True |

## Notes
- action_t shape per step: (576, 7) — matrix_576x7, supported_exact by adapter.
- observation_t shape per step: (24, 24, 27).
- Run adapt_teacher_dataset.py on this batch dir for Unity-contract-aligned output.
- Semantic weakening expected: Gridnet produce branch=7, attack branch=49 vs Unity 4/9.
