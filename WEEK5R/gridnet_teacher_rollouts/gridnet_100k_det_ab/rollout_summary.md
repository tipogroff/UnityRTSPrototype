# Gridnet Teacher Rollout Export Summary

- batch_name: gridnet_100k_det_ab
- checkpoint: agent_final.pt
- deterministic_mode: True
- opponent: randomBiasedAI
- episodes: 4
- total_steps: 2048

## Action Distribution (full grid)

- Harvest: 8 (0.0000)
- Move: 140 (0.0001)
- NoOp: 1179360 (0.9998)
- Produce: 140 (0.0001)

## Per-Episode

| episode | steps | return | done |
|---------|-------|--------|------|
| 0 | 512 | 2.000 | True |
| 1 | 512 | 2.000 | True |
| 2 | 512 | 2.000 | True |
| 3 | 512 | 2.000 | True |

## Notes
- action_t shape per step: (576, 7) — matrix_576x7, supported_exact by adapter.
- observation_t shape per step: (24, 24, 27).
- Run adapt_teacher_dataset.py on this batch dir for Unity-contract-aligned output.
- Semantic weakening expected: Gridnet produce branch=7, attack branch=49 vs Unity 4/9.
