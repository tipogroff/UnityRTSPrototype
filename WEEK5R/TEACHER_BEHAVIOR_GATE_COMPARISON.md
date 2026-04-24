# Teacher Behavior Gate — Comparison Table

| checkpoint | status | actor_move | actor_noop | full_move | gap(full−actor) | pos_delta | no_eff_share |
|---|---|---|---|---|---|---|---|
| checkpoints/teacher_sb3_ppo_step_000080000.zip | **FAIL_COLLAPSED_NOOP** ← FAIL_COLLAPSED_NOOP; FAIL_FALSE_FULL_TENSOR_MOVE; FAIL_NO_EFFECT_BEHAVIOR | 0.00% | 95.24% | 37.33% | 37.33% | 0 | 100.00% |

**Sort order**: PASS → SUSPICIOUS → FAIL_COLLAPSED_NOOP → FAIL_FALSE_FULL_TENSOR_MOVE → FAIL_NO_EFFECT_BEHAVIOR

**gap(full−actor)**: positive gap indicates spurious full-tensor Move signal not reflected in actor-level chosen behavior.

> **Note**: Actor-level Move share is the authoritative signal. Full-tensor Move share alone is NOT evidence of real movement. This table does not claim Gym→Unity semantic parity.
