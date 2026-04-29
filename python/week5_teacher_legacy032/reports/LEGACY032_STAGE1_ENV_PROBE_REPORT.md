# Stage 1 Environment Probe Report — gym_microrts==0.3.2

**Status**: COMPLETE — `PASS_WITH_WARNINGS`  
**Date**: Stage 1  
**Probe script**: `python/week5_teacher_legacy032/scripts/legacy032_env_probe.py`  
**Probe artifact**: `python/week5_teacher_legacy032/reports/legacy032_env_probe.json`  

---

## Summary

The legacy gym_microrts==0.3.2 environment was successfully probed using the
24×24 training map.  Env creation succeeded, 128 smoke steps executed without
error, and all structural contracts were recorded.

**Status: PASS_WITH_WARNINGS** — two warnings remain (action layout mismatch
with Unity v2, mask not found via probe APIs).  Neither warning blocks Stage 2
smoke training; both must be addressed before Stage 3/6 work.

---

## Command used

```powershell
$env:JAVA_HOME = 'C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path = "$env:JAVA_HOME\bin;$env:Path"
.\python\week5_teacher_reference\.venv_microrts032_reference\Scripts\python.exe `
    python/week5_teacher_legacy032/scripts/legacy032_env_probe.py `
    --env-id MicrortsRandomEnemyShapedReward1-v1 `
    --map-path maps/24x24/basesWorkers24x24.xml `
    --steps 128 `
    --seed 17 `
    --output-json python/week5_teacher_legacy032/reports/legacy032_env_probe.json `
    --write-markdown-report
```

---

## Environment versions (confirmed)

| Package | Version |
|---------|---------|
| Python | 3.9.13 |
| `gym_microrts` | 0.3.2 |
| `gym` | 0.17.3 |
| `stable_baselines3` | 1.0 |
| `torch` | 1.8.0+cpu |
| `numpy` | 1.25.2 (fallback; exact pin 1.21.6 not available on this host) |
| `JPype1` | 1.4.1 |
| Java | OpenJDK 17.0.18 (Eclipse Temurin) |

---

## Env creation result

| Item | Result |
|------|--------|
| Env ID used | `MicrortsRandomEnemyShapedReward1-v1` |
| Map | `maps/24x24/basesWorkers24x24.xml` |
| Creation | **PASS** |
| Env IDs attempted and failed | `MicrortsSelfPlayShapedReward-v1` — `AttributeError: module 'gym_microrts.envs' has no attribute 'GlobalAgentCombinedRewardSelfPlayEnv'` |

---

## Observation contract

| Item | Confirmed value |
|------|----------------|
| obs space type | `Box` |
| obs shape at reset | `(24, 24, 27)` — H × W × C, **no batch dim** |
| channels | 27 feature channels |

---

## Action contract — CRITICAL FINDING

gym_microrts==0.3.2 uses a **GLOBAL SINGLE-ACTION-PER-STEP** representation,
NOT per-cell parallel actions.

```
action_space.nvec = [576, 6, 4, 4, 4, 4, 7, 576]   (length = 8)
```

| nvec index | Field | Size | Notes |
|---|---|---|---|
| 0 | `src_cell` | 576 | Which cell (unit) acts this step |
| 1 | `action_type` | 6 | |
| 2 | `move_dir` | 4 | |
| 3 | `harvest_dir` | 4 | |
| 4 | `return_dir` | 4 | |
| 5 | `produce_dir` | 4 | |
| 6 | `produce_unit_type` | 7 | |
| 7 | `attack_target_global` | 576 | Global flat index over all 576 cells |

**Action representation**: `GYM_MICRORTS_032_GLOBAL_SINGLE_ACTION`

This is structurally different from Unity v2's per-cell parallel MultiDiscrete
(576 cells × 7 branches = 4032 total).

---

## Action mask result

| Item | Result |
|------|--------|
| Mask available via probe APIs | **NOT FOUND** |
| APIs tested | `action_mask`, `get_action_mask()`, `info["action_mask"]`, `env.unwrapped.*`, 7+ others |
| Impact | WARNING — training script must locate mask API before teacher training |
| Blocking Stage 2? | No — can train without mask (unconstrained actions) for smoke purposes |
| Blocking Stage 3+? | Potentially — proper masked PPO requires the mask |

---

## Attack target semantics

| Item | Value |
|------|-------|
| Hint | `BRANCH_SIZE_576_GLOBAL_FLAT` |
| Attack target encoding | Global flat cell index (0..575) over the entire 24×24 grid |
| Unity v2 encoding | Local 7×7 window relative to acting unit (0..48) |
| Parity | **None — structurally incompatible** |

The Stage 6 adapter must perform two transformations for attack actions:
1. Convert the global flat attack target index to unit-relative coordinates
2. Clip to the local 7×7 window (49 values)

This is a non-trivial spatial remap. No direct weight transfer is possible for
the attack branch without this adapter.

---

## Smoke episode runtime

| Item | Result |
|------|--------|
| Steps executed | 128 |
| Episode done | False (game did not terminate in 128 steps) |
| Total reward | 0.000 |
| Exceptions | None |

---

## Unity v2 compatibility summary

| Branch | Teacher (0.3.2) | Unity v2 | Compatible? |
|--------|-----------------|----------|-------------|
| action_type | 6 | 6 | ✓ size match |
| move_dir | 4 | 4 | ✓ size match |
| harvest_dir | 4 | 4 | ✓ size match |
| return_dir | 4 | 4 | ✓ size match |
| produce_dir | 4 | 4 | ✓ size match |
| produce_unit_type | 7 | 7 | ✓ size match |
| attack_target | 576 (global flat) | 49 (local 7×7) | ✗ remap required |
| representation | global single-action | per-cell parallel | ✗ adapter required |

---

## Known gaps

1. **Action representation mismatch**: gym_microrts 0.3.2 single-action-per-step
   vs Unity v2 per-cell parallel requires adapter work (Stage 6).
2. **Attack target mismatch**: global flat 576 vs local 7×7 49 requires spatial
   remap in Stage 6 adapter.
3. **Action mask**: not found via probe; must be confirmed before Stage 3 masked
   PPO teacher training.
4. **numpy pin**: `1.25.2` used instead of paper's `1.21.6`; trajectory
   reproducibility relative to the paper has not been verified.

---

## Stage 2 readiness decision

**READY FOR STAGE 2 SMOKE TRAINING** — with the following conditions:

- Use env_id `MicrortsRandomEnemyShapedReward1-v1` with 24×24 map
- Action mask issue is acceptable for Stage 2 smoke (unconstrained actions OK for short smoke run)
- Do NOT claim teacher is trained or weights are transferable until Stage 3 gate passes
- The action representation and attack-target gaps are known and documented; they
  do not block smoke training but must be resolved before BC packaging (Stage 7)

---

## Files produced by Stage 1

| File | Purpose |
|------|---------|
| `reports/legacy032_env_probe.json` | Machine-readable probe artifact |
| `reports/legacy032_env_probe.md` | Auto-generated companion markdown |
| `reports/LEGACY032_STAGE1_ENV_PROBE_REPORT.md` | This document |
| `ENVIRONMENT_LEGACY032.md` | Updated with confirmed Stage 1 values |
