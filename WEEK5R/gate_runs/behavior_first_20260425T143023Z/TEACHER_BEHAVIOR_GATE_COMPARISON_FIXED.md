# Teacher Behavior Gate — Comparison Table

| checkpoint | status | actor_move | actor_noop | full_move | gap(full−actor) | pos_delta | no_eff_share |
|---|---|---|---|---|---|---|---|
| checkpoints/teacher_sb3_ppo_step_000005000.zip | **SUSPICIOUS** | 1.04% | 98.64% | 0.01% | -1.03% | 1 | 99.19% |
| checkpoints/teacher_sb3_ppo_step_000020000.zip | **SUSPICIOUS** | 0.07% | 99.63% | 0.00% | -0.07% | 1 | 99.25% |
| checkpoints/teacher_sb3_ppo_step_000010000.zip | **FAIL_COLLAPSED_NOOP** ← FAIL_COLLAPSED_NOOP; FAIL_NO_EFFECT_BEHAVIOR | 0.00% | 99.87% | 0.00% | 0.00% | 0 | 100.00% |

**Sort order**: PASS → SUSPICIOUS → FAIL_COLLAPSED_NOOP → FAIL_FALSE_FULL_TENSOR_MOVE → FAIL_NO_EFFECT_BEHAVIOR

**gap(full−actor)**: positive gap indicates spurious full-tensor Move signal not reflected in actor-level chosen behavior.

> **Note**: Actor-level Move share is the authoritative signal. Full-tensor Move share alone is NOT evidence of real movement. This table does not claim Gym→Unity semantic parity.
