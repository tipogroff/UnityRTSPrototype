# Stage 1 Completion Report — Legacy gym_microrts==0.3.2 Env Probe

**Status**: COMPLETE  
**Outcome**: `PASS_WITH_WARNINGS` — environment verified, contracts documented, ready for Stage 2

---

## Objective

Stage 1 goal: Instantiate the legacy `gym_microrts==0.3.2` environment on the 24×24
training map, verify obs/action/mask contracts, run a smoke episode, and produce
a machine-readable probe artifact.

---

## Files created / updated

| File | Action | Notes |
|------|--------|-------|
| `scripts/legacy032_env_probe.py` | **Created** | Full probe script with action representation detection |
| `reports/legacy032_env_probe.json` | **Created** | Machine-readable probe artifact — `PASS_WITH_WARNINGS` |
| `reports/legacy032_env_probe.md` | **Created** | Auto-generated companion markdown |
| `reports/LEGACY032_STAGE1_ENV_PROBE_REPORT.md` | **Created** | This human-readable Stage 1 report |
| `ENVIRONMENT_LEGACY032.md` | **Updated** | All TBD fields filled with confirmed Stage 1 values |
| `scripts/README.md` | **Updated** | Added probe description, example command, troubleshooting |

---

## Probe command

```powershell
$env:JAVA_HOME = 'C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path = "$env:JAVA_HOME\bin;$env:Path"
.\python\week5_teacher_reference\.venv_microrts032_reference\Scripts\python.exe `
    python/week5_teacher_legacy032/scripts/legacy032_env_probe.py `
    --env-id MicrortsRandomEnemyShapedReward1-v1 `
    --map-path maps/24x24/basesWorkers24x24.xml `
    --steps 128 --seed 17 `
    --output-json python/week5_teacher_legacy032/reports/legacy032_env_probe.json `
    --write-markdown-report
```

---

## Probe outcome summary

| Check | Result |
|-------|--------|
| Env creation | ✅ PASS — `MicrortsRandomEnemyShapedReward1-v1` |
| Observation shape | ✅ `(24, 24, 27)` — H × W × C |
| Action space nvec | ✅ `[576, 6, 4, 4, 4, 4, 7, 576]` (len=8) |
| Action representation | ✅ `GYM_MICRORTS_032_GLOBAL_SINGLE_ACTION` |
| Smoke episode (128 steps) | ✅ PASS — no exceptions |
| Action mask | ⚠️ NOT FOUND via probe APIs |
| Action layout matches Unity v2 | ⚠️ NO — adapter required (expected gap) |
| Java 17 compatibility | ✅ PASS |
| Overall status | **PASS_WITH_WARNINGS** |

---

## Critical contract finding

gym_microrts==0.3.2 uses a **GLOBAL SINGLE-ACTION-PER-STEP** format — one action
per game step for one selected unit:

```
nvec = [576, 6, 4, 4, 4, 4, 7, 576]
        ^^^                    ^^^
   src cell               attack target (global flat)
```

Unity v2 uses **per-cell parallel actions** (576 cells × 7 branches = 4032 total).

These are structurally incompatible.  The adapter pipeline (Stage 6) must handle:
1. Single-action → per-cell parallel conversion
2. Global flat attack target (576) → local 7×7 (49) spatial remap

No direct weight transfer is possible for the attack branch without this remap.

---

## Env ID note

`MicrortsSelfPlayShapedReward-v1` is registered in the gym registry but fails with:
```
AttributeError: module 'gym_microrts.envs' has no attribute 'GlobalAgentCombinedRewardSelfPlayEnv'
```
Use `MicrortsRandomEnemyShapedReward1-v1` for all Stage 2+ work.

---

## Stage 2 readiness decision

**READY FOR STAGE 2 SMOKE TRAINING**

- Env creates reliably; 128 smoke steps passed
- Action representation is known and documented
- Known gaps (mask, adapter) do not block smoke training
- Proceed with `train_teacher_legacy032.py` (to be created in Stage 2)

### Exact next action for Stage 2

Create `python/week5_teacher_legacy032/scripts/train_teacher_legacy032.py` —
short PPO smoke training run (e.g., 50k steps) using:
- `MicrortsRandomEnemyShapedReward1-v1` + `maps/24x24/basesWorkers24x24.xml`
- venv: `python/week5_teacher_reference/.venv_microrts032_reference/`
- `JAVA_HOME = C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot`
- Save checkpoint to `models/legacy032_smoke/`
- No wandb required; stdout metrics only

Do **not** start Stage 3 behavior gate until the Stage 2 smoke checkpoint is saved
and the action_type_distribution is recorded.
