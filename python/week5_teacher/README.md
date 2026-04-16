# Week 5 Runtime and Day 3 Raw Export

This folder keeps the validated runtime path and extends it for Day 3 raw teacher export.

Canonical baseline remains fixed:

- `MicroRTS-Py v0.6.1`-compatible stack;
- 27-channel observation surface;
- no semantic parity claims;
- no Gym->Unity adapter conversion on Day 3.

Day 3 goal is raw teacher truth export per episode, not Unity-ready remap and not BC-ready shaping.

## Quick bootstrap script

To reduce manual setup steps, use:

```powershell
./setup_day2_env.ps1 -JavaHome "C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot" -AntBin "C:/Tools/apache-ant-1.10.14/bin"
```

Optional switches:

- `-InstallPrerequisites` to install Python 3.9 + JDK 17 via winget.
- `-Python39Exe <path>` to pin a specific Python 3.9 executable.
- `-RunSmokeCheck` to run the runtime rollout smoke test after bootstrap.

## Validated environment

Validated command was executed successfully in this workspace with:

- Python `3.9.13` (separate runtime venv)
- Java `Temurin 17`
- `gym-microrts` from git tag `v0.6.1` (editable install)
- `gym==0.23.1`, `gymnasium==0.29.1`
- `stable-baselines3==2.3.2`, `torch==2.8.0`, `numpy==1.26.4`

See `ENVIRONMENT_DAY2.md` for exact bootstrap/build steps and notes.

## Validated runtime command

```powershell
$env:JAVA_HOME='C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME/bin;$env:Path"

c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/run_teacher_rollout.py \
  --episodes 1 \
  --env-id MicrortsSelfPlayShapedReward-v1 \
  --map-path maps/24x24/basesWorkers24x24.xml \
  --seed 17 \
  --allow-random-policy-smoke-fallback \
  --rollout-step-limit 64
```

Validation status:

- runtime reached terminal: yes (`terminated` at step 64);
- observed shape: `[1, 24, 24, 27]`;
- observation surface verification: `27-channel compatible`;
- compatibility scope: `shape-only`;
- semantic parity verified: `false`.

## Day 3 quick export commands

Debug batch (small, readable, includes `.jsonl` by default):

```powershell
$env:JAVA_HOME='C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME/bin;$env:Path"

c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/run_teacher_rollout.py \
  --episodes 2 \
  --batch-mode debug \
  --batch-label day3_debug \
  --env-id MicrortsSelfPlayShapedReward-v1 \
  --map-path maps/24x24/basesWorkers24x24.xml \
  --seed 17 \
  --allow-random-policy-smoke-fallback \
  --rollout-step-limit 64
```

Training batch (larger raw export, `.npz` primary):

```powershell
$env:JAVA_HOME='C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME/bin;$env:Path"

c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/run_teacher_rollout.py \
  --episodes 20 \
  --batch-mode training \
  --batch-label day3_train \
  --env-id MicrortsSelfPlayShapedReward-v1 \
  --map-path maps/24x24/basesWorkers24x24.xml \
  --seed 101 \
  --allow-random-policy-smoke-fallback \
  --rollout-step-limit 256 \
  --write-jsonl never
```

## Current structure

- `run_teacher_rollout.py`: CLI, runtime bootstrap, environment/policy orchestration, batch loop.
- `teacher_export.py`: raw export helpers, validation helpers, serialization utilities.

This split is intentionally minimal and does not change saved artifact behavior.

## What run_teacher_rollout.py does now

- logs runtime versions, seeds, env/action/observation summaries;
- checks shape compatibility for SB3 checkpoint path (`observation_space` + `action_space`);
- runs rollout step-by-step until terminal or step-limit fail;
- exports raw per-episode trajectory into `teacher_rollouts/<batch_name>/episode_XXXXX.npz`;
- optionally exports per-step debug dump `episode_XXXXX.jsonl`;
- runs primary validation on in-memory records and on serialized `.npz` payload;
- writes:
  - run summary in `teacher_logs/teacher_rollout_<timestamp>.summary.json`;
  - batch summary in `teacher_rollouts/<batch_name>/batch.summary.json`.

## Day 3 raw export schema (per step)

Required fields:

- `episode_id`
- `step_id`
- `observation_t` (raw teacher-side representation)
- `action_t` (raw teacher-side representation)
- `reward_t`
- `done_t`

Diagnostic fields (saved when available):

- `terminated_t`, `truncated_t`, `terminal_type_t`
- `info_t_json`
- `action_mask_t_json`, `action_mask_available_t`
- metadata in batch summary: `policy_source_id`, `env_id`, `env_version`, `map_path`, seeds

Intentional raw action representation decision:

- `action_t` is intentionally stored in heterogeneous teacher-side form (`object` payload + JSON + hash).
- This is a raw truth layer decision for Day 3, not a normalized action tensor contract.
- Downstream adapter stages must treat `action_t` as raw teacher representation.

## Mask recording decision

Batch summary includes:

- `mask_recording_mode="explicit"` when all steps have mask
- `mask_recording_mode="unavailable"` when no mask is available
- `mask_recording_mode="partial"` when mask exists only for subset of steps

No mask reconstruction is performed.

Mask-source heterogeneity note:

- Mask can be sourced from `get_action_mask`, `action_masks`, or `info.*` depending on runtime path.
- `mask_capture.sources` in `batch.summary.json` is diagnostic metadata.
- Cross-batch semantic mask comparison should be treated with caution and belongs to later stages.

## Primary validation performed

- equal per-step lengths across exported fields
- contiguous `step_id` per episode
- no NaN/Inf in `observation_t` and `reward_t`
- correct terminal finalization (`done_t` must finish episode)
- no same-episode continuation after `done_t=True`
- action payload serialization stability via `action_t_json` + `action_t_hash`
- post-write `.npz` roundtrip integrity check

On validation failure, the run fails with an explicit error summary.

## Infrastructure validation vs canonical teacher quality

- Random fallback rollout is valid for infrastructure validation of export/validation plumbing.
- Random fallback rollout is not a canonical teacher supervision quality path.
- Canonical teacher dataset quality remains a later-stage concern.

## Day 3 scope boundaries

- current SB3-only checkpoint loader scope (`ppo`, `a2c`, `dqn`);
- strict scalar reward assumption (`coerce_scalar_reward`);
- scenario note is approximation-only (no full Unity parity claim);
- Day 3 export is raw teacher-side only.

Not included in Day 3:

- Gym->Unity action/observation adapter;
- BC-ready dataset shaping;
- teacher/student conversion;
- semantic parity validator.

## Batch-level statistics

`batch.summary.json` includes:

- number of episodes
- total steps
- mean episode length
- reward mean/std
- episode return mean/std
- terminal counts
- `action_surface_histogram` (payload-surface histogram, not semantic action taxonomy)

## Scenario approximation note

Default map (`maps/24x24/basesWorkers24x24.xml`) is treated only as nearest approximation to Unity `MVP_24x24_Symmetric`.

- `scenario_match_scope`: approximation-only
- `known_matches`: 24x24 size, bases/workers family, symmetric intent
- `known_unknowns`: exact starting resources, exact unit subset, reward shaping behavior, action semantics, step timing
- `parity_claim`: false

## CLI arguments

- `--policy-path`: teacher checkpoint path (current loader scope is SB3-only).
- `--policy-algorithm`: one of `ppo`, `a2c`, `dqn`.
- `--checkpoint-env-version`: required with `--policy-path`.
- `--episodes`: number of episodes.
- `--batch-mode`: `debug` or `training`.
- `--batch-label`: free-form artifact label.
- `--env-id`: requested gym/gymnasium env id.
- `--map-path`: map path (kept explicit to prevent scenario drift).
- `--seed`: base seed.
- `--env-seed`: optional env seed (`seed + 1` by default).
- `--rollout-seed`: optional rollout seed (`seed + 2` by default).
- `--device`: torch/SB3 device.
- `--allow-random-policy-smoke-fallback`: explicit non-canonical fallback mode.
- `--output-dir`: output root (defaults to `python/week5_teacher`).
- `--rollout-step-limit`: hard per-episode safety cap.
- `--write-jsonl`: `debug` / `always` / `never`.
- `--export-prefix`: artifact prefix.

## Output artifacts

Per run in `teacher_logs/`:

- `teacher_rollout_<timestamp>.log`
- `teacher_rollout_<timestamp>.summary.json`

Per batch in `teacher_rollouts/teacher_raw_<mode>_<label>_<timestamp>/`:

- `episode_00000.npz`, ... (primary raw export)
- `episode_00000.jsonl`, ... (debug step dump, if enabled)
- `batch.summary.json` (metadata + validation + statistics)