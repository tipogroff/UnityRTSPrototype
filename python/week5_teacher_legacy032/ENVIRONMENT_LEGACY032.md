# Environment Specification: Legacy gym_microrts==0.3.2

**Status**: Stage 1 COMPLETE — confirmed by `legacy032_env_probe.py` on 24×24 map.  
Fields marked `[CONFIRMED]` have been validated.  
See `python/week5_teacher_legacy032/reports/legacy032_env_probe.json` for the raw probe artifact.

---

## Core dependency versions

| Package | Required version | Status |
|---------|-----------------|--------|
| Python | 3.9.13 | `[CONFIRMED — reference venv]` |
| `gym-microrts` | `== 0.3.2` | `[CONFIRMED — import OK]` |
| `gym` | `== 0.17.3` | `[CONFIRMED — reference venv]` |
| `stable-baselines3` | `== 1.0` | `[CONFIRMED — reference venv]` |
| `torch` | `1.8.0` (cpu build) | `[CONFIRMED — reference venv]` |
| `numpy` | `1.25.2` (compatibility fallback; pinned `1.21.6` not met) | `[CONFIRMED — fallback accepted, exact pin TBD]` |
| `JPype1` | `1.4.1` | `[CONFIRMED — reference venv]` |
| Java | OpenJDK 17.0.18 (Eclipse Temurin) | `[CONFIRMED — reference venv]` |
| `wandb` | NOT installed | `[CONFIRMED — reference venv; not required]` |

> **Note**: `exact_reference_pins: false` was recorded in the verify artifact.
> `numpy 1.21.6` (paper pin) could not be installed on this host; `1.25.2` was
> accepted as a fallback.  Stage 1 should record whether this affects
> trajectory reproducibility.

---

## Map and environment id

| Item | Value | Status |
|------|-------|--------|
| Training map | `maps/24x24/basesWorkers24x24.xml` | `[CONFIRMED — Stage 1 probe]` |
| Environment id | `MicrortsRandomEnemyShapedReward1-v1` | `[CONFIRMED — Stage 1 probe; used for teacher training]` |
| Opponent | Random enemy (random policy) | `[CONFIRMED — env name indicates random opponent]` |
| Working venv | `python/week5_teacher_reference/.venv_microrts032_reference/` | `[CONFIRMED — Stage 1 probe]` |

> **Note on env_id**: `MicrortsSelfPlayShapedReward-v1` is registered in the gym registry but
> fails with `AttributeError: module 'gym_microrts.envs' has no attribute
> 'GlobalAgentCombinedRewardSelfPlayEnv'` in this 0.3.2 build.  Use
> `MicrortsRandomEnemyShapedReward1-v1` instead.

---

## Observation space

| Item | Value | Status |
|------|-------|--------|
| Shape (training map 24×24) | `(24, 24, 27)` — H × W × C, no batch dim | `[CONFIRMED — Stage 1 probe direct measurement]` |
| Channels | 27 feature channels | `[CONFIRMED — Stage 1 probe + reference verify]` |

---

## Action space (expected for 24×24 map)

**CONFIRMED by Stage 1 probe on 24×24 map:**

```
action_space: MultiDiscrete([576   6   4   4   4   4   7  576])   # nvec length = 8
                              ^^^                          ^^^
                         src cell (24×24=576)     attack target (global flat, 576)
```


> **Critical finding**: `gym_microrts==0.3.2` uses a **GLOBAL SINGLE-ACTION-PER-STEP**
> representation.  The 8-element nvec encodes ONE action per game step for ONE unit:
>
> | nvec index | Meaning | Size |
> |---|---|---|
> | 0 | src_cell — which cell (unit) acts this step | 576 |
> | 1 | action_type | 6 |
> | 2 | move_dir | 4 |
> | 3 | harvest_dir | 4 |
> | 4 | return_dir | 4 |
> | 5 | produce_dir | 4 |
> | 6 | produce_unit_type | 7 |
> | 7 | attack_target_global — global flat cell index | 576 |
>
> This is **structurally different** from Unity v2's per-cell parallel actions
> (576 cells × 7 branches = 4032 total).  The adapter must handle both the
> single→parallel conversion AND the global→local 7×7 attack remap.
---

## Expected per-cell branch sizes (teacher side)

```python
# gym_microrts 0.3.2 native branch sizes (per cell, 24x24 map)
teacher_branch_sizes = [6, 4, 4, 4, 4, 7, 576]  # last = full-grid attack
```

---

## Target Unity v2 contract (adapter output)

```python
unity_v2_branch_sizes = [6, 4, 4, 4, 4, 7, 49]  # last = local 7x7 attack
```

| Branch | Meaning | Teacher (0.3.2) | Unity v2 | Delta |
|--------|---------|-----------------|----------|-------|
| 0 | action_type | 6 | 6 | none |
| 1 | move_dir | 4 | 4 | none |
| 2 | harvest_dir | 4 | 4 | none |
| 3 | return_dir | 4 | 4 | none |
| 4 | produce_dir | 4 | 4 | none |
| 5 | produce_unit_type | 7 | 7 | none |
| 6 | attack_target | 576 (global) | 49 (local 7×7) | **requires remap** |

The attack-target remap is a **known semantic gap** that the adapter must handle.
Stage 5 adapter work must address this explicitly.

---

## Expected BC-ready sample shape

```python
# After full adapter pipeline:
obs_shape    = [576, 27]   # flattened 24x24 grid, 27 channels each
action_shape = [576, 7]    # per-cell, 7 branches (Unity v2)
```

---

## To be verified by Stage 1 env probe

## Stage 1 verification status

- [x] Env_id confirmed: `MicrortsRandomEnemyShapedReward1-v1` with 24×24 map
- [x] Observation shape confirmed: `(24, 24, 27)` (no batch dim at single-env reset)
- [x] `action_space.nvec` confirmed: `[576, 6, 4, 4, 4, 4, 7, 576]` (global single-action format)
- [x] Action representation identified: `GYM_MICRORTS_032_GLOBAL_SINGLE_ACTION` (8-element)
- [x] Attack target confirmed: global flat 576 (NOT local 7×7 49)
- [x] Smoke episode: 128 steps PASS, no exception, reward=0.0
- [x] Java 17 compatibility: PASS (env created and stepped without JVM error)
- [x] VENV path confirmed: `python/week5_teacher_reference/.venv_microrts032_reference/`
- [ ] Action mask API: NOT FOUND via known APIs — must be confirmed by training script before teacher training (WARNING logged in probe)
- [ ] numpy fallback impact: not assessed in probe; `1.25.2` accepted; trajectory reproducibility TBD

---

## Virtual environment setup (reference)

The existing reference environment lives at:

```
python/week5_teacher_reference/.venv_microrts032_reference/
```

This venv was used for reference reproduction smoke tests.  A **separate** venv
should be created for the legacy032 teacher pipeline if training hyperparameters
or additional packages are needed.  Do not share the venv with
`python/week5_teacher/.venv_day2_py39/` (v0.6.1 runtime).

> **WARNING**: Do not mix v0.6.1 artifacts and legacy032 artifacts in the same
> output directory.
