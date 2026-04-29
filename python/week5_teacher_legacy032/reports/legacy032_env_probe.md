# Legacy032 Stage 1 — Environment Probe Report

**Date**: 2026-04-29T10:41:29.860905+00:00  
**Overall status**: `PASS_WITH_WARNINGS`  
**Stage 2 readiness**: `INCONCLUSIVE_NEEDS_MANUAL_CHECK`

---

## Summary

| Item | Value |
|------|-------|
| gym_microrts | 0.3.2 |
| Python | 3.9.13 |
| Platform | Windows-10-10.0.26200-SP0 |
| Java | openjdk version "17.0.18" 2026-01-20 |
| Env created | SUCCESS |
| Obs shape | [24, 24, 27] |
| Branch sizes | [576, 6, 4, 4, 4, 4, 7, 576] |
| Matches Unity v2 | False |
| Mask available | False |
| Smoke steps | 128/128 |
| Smoke error | None |

---

## Package versions

| Package | Version |
|---------|---------|
| gym | 0.17.3 |
| gym_microrts | 0.3.2 |
| gym_microrts_alt | 0.3.2 |
| torch | 1.8.0+cpu |
| numpy | 1.25.2 |
| stable_baselines3 | 1.0 |
| stable_baselines | NOT_INSTALLED |
| sb3_contrib | NOT_INSTALLED |
| JPype1 | 1.4.1 |
| wandb | NOT_INSTALLED |

## Environment creation

- env_id: `MicrortsRandomEnemyShapedReward1-v1`
- map_path: `maps/24x24/basesWorkers24x24.xml`
- status: **SUCCESS**

  - `gym.make(env_id, map_path=map_path)` → **SUCCESS**

## Observation contract

| Item | Value |
|------|-------|
| shape | [24, 24, 27] |
| dtype | int32 |
| min/max | 0.0000 / 1.0000
| has_nan | False |
| has_inf | False |

## Action contract

| Item | Value |
|------|-------|
| nvec_length | 8 |
| cells_detected | 576 |
| branches_per_cell | None |
| branch_sizes | `[576, 6, 4, 4, 4, 4, 7, 576]` |
| uniform | None |
| matches Unity v2 `[6,4,4,4,4,7,49]` | **False** |

## Action mask

| Item | Value |
|------|-------|
| mask_available | **False** |
| mask_source | None |
| mask_shape | None |
| mask_dtype | None |
| mask_sum | None |

> ⚠️ Action mask was not found through known APIs; later training scripts must confirm mask path before teacher training.


## Runtime smoke

| Item | Value |
|------|-------|
| steps requested | 128 |
| steps executed | 128 |
| done reached | False |
| total reward | 0.0 |
| action method | action_space.sample() |
| error | None |

## Attack target semantics

> **gym_microrts 0.3.2 uses a GLOBAL single-action format. The attack_target at nvec index 7 has size 576 (global flat index over all 576 grid cells). This is STRUCTURALLY INCOMPATIBLE with Unity v2 local 7x7 (49). The Stage 6 adapter must: (1) remap global flat index → local 7x7 relative position, and (2) convert the entire single-action-per-step representation to per-cell parallel actions. This is a non-trivial transformation.**

| Item | Value |
|------|-------|
| observed attack branch size | 576 |
| matches Unity v2 size (49) | False |
| encoding hint | `BRANCH_SIZE_576_GLOBAL_FLAT` |
| semantic_parity_proven | **False** |

> Note: Unity v2 uses local 7×7 attack target (49 values).
> gym_microrts 0.3.2 may use global flat target.
> Stage 6 adapter must verify this before assuming direct mapping.

## Compatibility with Unity v2

Branch sizes `[576, 6, 4, 4, 4, 4, 7, 576]` differ from Unity v2 `[6,4,4,4,4,7,49]`.
The adapter pipeline is required to convert teacher trajectories.
If the attack branch is 576 (global flat), remap to local 7x7 is needed.

## Warnings

- ⚠️ Action branch layout [576, 6, 4, 4, 4, 4, 7, 576] does not match Unity v2 contract [6, 4, 4, 4, 4, 7, 49]. Adapter will be required.
- ⚠️ Action mask was not found through known APIs; later training scripts must confirm mask path before teacher training.

## Known gaps

- Attack target semantics (local vs global) not proven at Stage 1
- `validate_adapted_dataset.py` still has hardcoded v1 contract — must be migrated at Stage 7
- `build_bc_ready_dataset_day6.py` still has hardcoded v1 contract — must be migrated at Stage 7
- Adapter `adapt_teacher_dataset.py` default is `v1_mvp`; must use `--target-action-contract v2_gridnet_compatible`

## Stage 2 readiness decision

**`INCONCLUSIVE_NEEDS_MANUAL_CHECK`**

Manual verification required before Stage 2. Check warnings and errors above.

---

Full JSON report: `python/week5_teacher_legacy032/reports/legacy032_env_probe.json`