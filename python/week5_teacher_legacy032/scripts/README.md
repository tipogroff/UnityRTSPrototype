# scripts/ — Planned Entrypoints for Legacy032 Teacher Pipeline

This directory will contain scripts developed specifically for the
`gym_microrts==0.3.2` teacher workflow.

**Stage 0 status**: No scripts have been created yet.  The files listed below
are planned entrypoints for future stages.

---

## Planned scripts (to be created in subsequent stages)

| Script | Stage | Purpose |
|--------|-------|---------|
| `legacy032_env_probe.py` | Stage 1 | Instantiate a 0.3.2 environment, print observation shape, action nvec, and map info |
| `train_teacher_legacy032.py` | Stage 2–3 | Run PPO training against `gym_microrts==0.3.2`; save checkpoints |
| `evaluate_teacher_legacy032.py` | Stage 3 | Evaluate a checkpoint; record action_type_distribution and behavior metrics |
| `export_teacher_rollout_legacy032.py` | Stage 4 | Export raw episode trajectories from a trained 0.3.2 checkpoint |
| `adapt_legacy032_to_unity_v2.py` | Stage 5 | Adapt 0.3.2 rollout to Unity v2 contract `[6,4,4,4,4,7,49]` |

## Note

Do **not** call scripts from `python/week5_teacher/` directly from within this
workspace without review.  Many of those scripts assume v0.6.1 runtime or may
have hardcoded v1 contract (`[6,4,4,4,4,4,9]`).  See `LEGACY032_STAGE0_AUDIT.md`
for the migration items that must be resolved before any script can be reused.
