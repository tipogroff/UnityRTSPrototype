# Legacy gym_microrts==0.3.2 Teacher Workspace

## Purpose

This directory is an **isolated workspace** for the legacy teacher pipeline based on
`gym_microrts==0.3.2`.  It exists alongside the primary Week 5 teacher pipeline
(`python/week5_teacher/`) but is **physically and logically separated** from it.

## Why is this separated from `python/week5_teacher/`?

`python/week5_teacher/` was developed primarily with the `MicroRTS-Py v0.6.1`
runtime (editable install).  That pipeline accumulates:

- v0.6.1-compatible training scripts
- historical v1 action-contract artifacts (`[6,4,4,4,4,4,9]`)
- in-progress v2 migration work (`[6,4,4,4,4,7,49]`)
- gridnet sweeps, retraining experiments, and recipe redesigns

Mixing `gym_microrts==0.3.2` artifacts into that directory would create
ambiguity about which runtime produced which checkpoint or dataset.
To prevent that, **all work related to the 0.3.2 teacher lives here**.

## Target environment

| Item | Value |
|------|-------|
| `gym_microrts` | `== 0.3.2` (required) |
| Java | TBD — see `ENVIRONMENT_LEGACY032.md` |
| Python | TBD — see `ENVIRONMENT_LEGACY032.md` |
| Map | `maps/24x24/basesWorkers24x24.xml` (to be confirmed) |

## Expected Unity v2 action contract

The current Unity side expects per-cell MultiDiscrete with 7 branches:

```
branch_sizes = [6, 4, 4, 4, 4, 7, 49]
```

| Branch | Meaning | Size |
|--------|---------|------|
| 0 | action_type | 6 |
| 1 | move_dir | 4 |
| 2 | harvest_dir | 4 |
| 3 | return_dir | 4 |
| 4 | produce_dir | 4 |
| 5 | produce_unit_type | 7 |
| 6 | attack_target (local 7×7) | 49 |

This is the **v2 contract**.  All adapter work in this workspace must target v2.

## Canonical transfer path

```
legacy teacher (0.3.2)
  └─> raw rollout export
        └─> adapter (to Unity v2)
              └─> BC-ready dataset
                    └─> student policy (BC or fine-tune)
                          └─> Unity inference
```

Direct weight transfer from `gym_microrts==0.3.2` to Unity is **not considered
proven**.  Semantic parity between the 0.3.2 observation space and Unity's
observation space requires separate validation before any weight-transfer claim
can be made.

## Current status

**Stage 0 — Scaffold only.  No training has been run.  No weights exist.**

See `LEGACY032_TEACHER_TRAINING_PLAN.md` for planned stages.

## Local Resume And Full Checkpointing

Current local trainer supports full training checkpoints for staged continuation.

See:

- `LEGACY032_LOCAL_RESUME_AND_CHECKPOINTING.md`

Historical caveat:

- Older weights-only checkpoints remain valid inference snapshots.
- That old limitation ("treat later stages as from-scratch if resume is not implemented") applies only to pre-resume artifacts.

---

> **WARNING**: Do not mix v0.6.1 artifacts and legacy032 artifacts in the same
> output directory.  All output paths for 0.3.2 work must stay inside
> `python/week5_teacher_legacy032/` or explicitly namespaced subdirectories of
> `WEEK5R/` with a `legacy032` prefix.

## Directory layout

```
python/week5_teacher_legacy032/
  README.md                           ← this file
  ENVIRONMENT_LEGACY032.md            ← environment spec (TBD fields)
  LEGACY032_STAGE0_AUDIT.md           ← Stage 0 audit findings
  LEGACY032_TEACHER_TRAINING_PLAN.md  ← skeleton plan for future stages
  scripts/                            ← future entrypoint scripts
  teacher_models/                     ← future checkpoints
  teacher_logs/                       ← training and evaluation logs
  teacher_rollouts/                   ← raw episode trajectories
  teacher_exports/                    ← adapted datasets (Unity v2)
  teacher_exports_bc/                 ← BC-ready packages
  reports/                            ← markdown/JSON reports
```
