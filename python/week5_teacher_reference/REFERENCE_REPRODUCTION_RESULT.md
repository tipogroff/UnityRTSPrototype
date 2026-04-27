# Reference Reproduction Result

## Scope
This document records the outcome of the isolated reference reproduction branch under
`python/week5_teacher_reference/`.

This branch is a control experiment only.
It is not a Unity parity claim, not a BC-ready artifact, and not a direct teacher checkpoint.

---

## Environment Verification

**Status**: PASS

Verified environment snapshot:
- Python 3.9.13
- gym==0.17.3
- gym_microrts==0.3.2
- stable-baselines3==1.0
- torch==1.8.0+cpu
- torchvision==0.9.0+cpu
- numpy==1.25.2
- JPype1==1.4.1
- env_create: OK (`MicrortsMining-v1`)
- observation_space: `[10, 10, 27]`
- obs_surface_check: `FULL_OBS_27_CHANNEL`
- action_space: `MultiDiscrete([100, 6, 4, 4, 4, 4, 7, 100])`
- exact_reference_pins: `false`
- compatibility_fallback_used: `true`

Compatibility fallback note:
- Original paper stack expects older exact pins such as numpy 1.19.2.
- On Windows / Python 3.9, the isolated reference env uses numpy 1.25.2.
- Therefore `exact_reference_pins=false`, while `compatibility_fallback_used=true`.

---

## Smoke Run (10k)

**Status**: PASS

Run summary:
- script: `ppo_gridnet_diverse_encode_decode.py`
- total_timesteps: `10000`
- seed: `1`
- num_bot_envs: `6`
- exit_code: `0`
- videos_found: `false`
- checkpoints_found: `false`

Outcome:
- Python exception-free completion
- training loop confirmed via `global_step=...` lines
- smoke artifacts written successfully

Notes:
- `num_bot_envs=6` is required by the paper script's `ai2s` formula.
- Video remained disabled because ffmpeg was not required for the smoke success criteria.

---

## Staged Long Run (100k)

### First staged run
**Status**: PASS

Run summary:
- script: `ppo_gridnet_diverse_encode_decode.py`
- total_timesteps: `100000`
- seed: `1`
- num_bot_envs: `6`
- exit_code: `0`
- videos_found: `false`
- checkpoints_found: `false`

TensorBoard run found:
- `python/week5_teacher_reference/external/gym-microrts-paper/runs/MicrortsDefeatCoacAIShaped-v3__long_ref_20260427T185325Z__1__1777290806`

Why no checkpoint was produced:
- The original paper script saves `agent.pt` only inside the `prod_mode / wandb` branch.
- Reference runs intentionally avoid `wandb` and do not enable `prod_mode`.
- Therefore the original script produces TensorBoard logs but no local model artifact.

### Local-save sanity run
**Status**: PASS

Run summary:
- script: `ppo_gridnet_diverse_encode_decode_local_save.py`
- total_timesteps: `100000`
- seed: `1`
- num_bot_envs: `6`
- exit_code: `0`
- videos_found: `false`
- checkpoints_found: `true`

Local artifacts:
- final model: `python/week5_teacher_reference/artifacts/long_runs/20260427T192007Z/models/agent_final.pt`
- metadata: `python/week5_teacher_reference/artifacts/long_runs/20260427T192007Z/models/model_metadata.json`
- TensorBoard: `python/week5_teacher_reference/external/gym-microrts-paper/runs/MicrortsDefeatCoacAIShaped-v3__long_ref_20260427T192007Z__1__1777292410`

What this proves:
- Local checkpoint saving can be added without enabling wandb.
- This was done via a patched local copy under `patched_paper_scripts/`, not by modifying `external/gym-microrts-paper/` directly.

---

## Important Clarification: Verify Env vs Paper Training Env

Two successful checks exist in this branch and they are not the same scenario:

1. **Environment verification** validated reference package wiring on `MicrortsMining-v1` with:
   - observation surface `[10,10,27]`
   - action space `MultiDiscrete([100,6,4,4,4,4,7,100])`

2. **Paper training runs** used the paper script default gym id:
   - `MicrortsDefeatCoacAIShaped-v3`
   - 16x16 map / paper training task
   - local-save metadata observed:
     - observation surface `[16,16,27]`
     - action space `MultiDiscrete([256,6,4,4,4,4,7,49])`

This does not invalidate the control experiment.
It means:
- the reference environment stack is working,
- and the paper training recipe itself is also working,
- but they were validated through two different env/task surfaces inside the same reference branch.

---

## Visual Observation (User-confirmed)

User-confirmed visible behavior from the staged reference run:
- movement
- harvesting resources
- barracks construction
- unit production
- attacking

This is important because it demonstrates non-trivial agent behavior emerging in the isolated reference setup.

---

## Conclusion

The reference recipe works as a control experiment.

Specifically, the branch now demonstrates:
- environment verification success in the isolated old stack,
- successful 10k smoke run,
- successful 100k staged long run,
- visible in-game behavior,
- TensorBoard artifact generation,
- and successful local checkpoint saving without wandb.

This makes the reference branch a valid control baseline for comparing against the project-compatible training pipeline.

---

## Explicit Non-Claims

This result does **not** claim any of the following:
- not Unity parity
- not BC-ready
- not a direct teacher checkpoint for the main project
- not proof that old-env checkpoints can be dropped into the project-compatible branch
- not proof that the project-compatible branch should match behavior without architectural/action-semantics porting
