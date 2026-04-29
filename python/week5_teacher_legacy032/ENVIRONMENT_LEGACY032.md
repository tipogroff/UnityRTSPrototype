# Environment Specification: Legacy gym_microrts==0.3.2

**Status**: Stage 0 — partially confirmed from reference env probe (2026-04-27).  
Fields marked `[CONFIRMED]` have been validated by
`python/week5_teacher_reference/artifacts/reference_env_verify.json`.  
Fields marked `[TBD]` must be confirmed in Stage 1 env probe using the
24×24 training map.

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
| Training map | `maps/24x24/basesWorkers24x24.xml` | `[TBD — confirmed for reference training; must verify env_id for legacy032 teacher]` |
| Environment id | `MicrortsRandomEnemy*` family or custom | `[TBD — to be selected in Stage 1]` |
| Opponent | Random / self-play | `[TBD]` |

---

## Observation space

| Item | Value | Status |
|------|-------|--------|
| Shape (training map 24×24) | `[1, 24, 24, 27]` (per-env) or `[24, 24, 27]` (single) | `[TBD — probe confirmed 27 channels on 10×10; 24×24 follows same pattern]` |
| Channels | 27 feature channels | `[CONFIRMED — obs_surface_check: FULL_OBS_27_CHANNEL]` |

---

## Action space (expected for 24×24 map)

The reference env probe was run on a 10×10 map and returned:

```
action_space: MultiDiscrete([100   6   4   4   4   4   7 100])
```

(100 = 10×10 cells, last 100 = attack target over full grid)

For a **24×24 map** the expected shape is:

```
action_space: MultiDiscrete([576   6   4   4   4   4   7  576])
                              ^^^                          ^^^
                           24*24=576 cells            all-cell attack
```

> **Important**: `gym_microrts==0.3.2` uses a **global flat attack target** (all 576 cells),
> not a local 7×7 attack target.  The Unity v2 contract uses a **local 7×7 attack
> target (49 values)**.  The adapter must remap this correctly.  See the
> "Contract delta" section below.

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

- [ ] Confirm env_id for 24×24 multi-opponent teacher training
- [ ] Confirm actual observation tensor shape `[1, 24, 24, 27]`
- [ ] Confirm `action_space.nvec` for 24×24 map resolves to `[576, 6, 4, 4, 4, 4, 7, 576]`
- [ ] Confirm exact numpy version does not affect rollout trajectories
- [ ] Confirm Java 17 is compatible with MicroRTS-Py 0.3.2 JAR (already passing in verify artifact, but should be re-confirmed under teacher training load)
- [ ] Confirm opponent policy / env variant for primary teacher training run
- [ ] Record whether `exact_reference_pins: false` (numpy fallback) causes any observable diff in obs values
- [ ] Confirm VENV path and activation method for legacy032 runs

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
