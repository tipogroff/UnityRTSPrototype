# Week 5 Runtime and Day 3 Raw Export

> STATUS: HISTORICAL BASELINE / DO NOT USE AS CURRENT PIPELINE
> NOTE: This README contains historical v1/non-legacy and migration-era material. For current canonical Week5/Week6 lineage, use PIPELINE_AUDIT_WEEK5_WEEK6.md and CURRENT_PIPELINE_RUNBOOK.md.

## Current Status Update (2026-04-29)

- This folder contains both historical v1 artifacts and current migration work.
- Current Unity action contract is v2 `[6,4,4,4,4,7,49]` (7x7 attack target, 7 produce-unit slots).
- Legacy `gym_microrts==0.3.2` reference path may be used as a primary teacher-source when it shows stable and reproducible behavior.
- Transfer remains safety-first: teacher trajectories -> adapter -> BC dataset -> student policy -> Unity inference/fine-tune.
- Direct weight transfer is not considered automatically proven by branch-size alignment alone.

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

### Backend/opponent control symmetry

`run_teacher_rollout.py` now exposes the same backend/opponent routing knobs used by the hardened training path:

- `--backend-mode allow_fallback|preferred_only`
- `--force-legacy-backend`
- `--opponent-pool <comma-separated names>`
- `--opponent-sampling static|per_reset|per_episode`
- `--opponent-seed <int>`

Scope honesty:

- rollout script is runtime/export only; it does not perform training;
- preferred backend is `gym.make`; legacy backend is controlled emergency/diagnostic fallback;
- opponent-pool controls are most meaningful in legacy fallback/backend-managed regimes.

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

Preferred rollout path example (preferred backend first, controlled fallback allowed):

```powershell
$env:JAVA_HOME='C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME/bin;$env:Path"

c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/run_teacher_rollout.py \
  --episodes 2 \
  --batch-mode debug \
  --batch-label day3_preferred_route \
  --env-id MicrortsSelfPlayShapedReward-v1 \
  --map-path maps/24x24/basesWorkers24x24.xml \
  --backend-mode allow_fallback \
  --opponent-pool passiveAI \
  --opponent-sampling static \
  --seed 17 \
  --allow-random-policy-smoke-fallback \
  --rollout-step-limit 64
```

Forced legacy diagnostic path example (explicit emergency route):

```powershell
$env:JAVA_HOME='C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME/bin;$env:Path"

c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/run_teacher_rollout.py \
  --episodes 2 \
  --batch-mode debug \
  --batch-label day3_legacy_diag \
  --env-id MicrortsSelfPlayShapedReward-v1 \
  --map-path maps/24x24/basesWorkers24x24.xml \
  --backend-mode preferred_only \
  --force-legacy-backend \
  --opponent-pool passiveAI,workerRushAI,lightRushAI \
  --opponent-sampling per_episode \
  --opponent-seed 77 \
  --seed 17 \
  --allow-random-policy-smoke-fallback \
  --rollout-step-limit 64
```

## Current structure

- `run_teacher_rollout.py`: CLI, runtime bootstrap, environment/policy orchestration, batch loop.
- `teacher_export.py`: raw export helpers, validation helpers, serialization utilities.

This split is intentionally minimal and does not change saved artifact behavior.

## Day 4 adapter command

Day 4 consumes Day 3 raw exports and produces adapted artifacts with explicit reporting:

```powershell
$env:JAVA_HOME='C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME/bin;$env:Path"

c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/adapt_teacher_dataset.py \
  --input-batch-dir c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/teacher_rollouts/teacher_raw_debug_day3smoke_20260416T121055Z \
  --write-debug-jsonl
```

Important scope notes:

- Day 4 adapter is teacher-source-agnostic and reads only exported raw dataset artifacts.
- No BC training, no student loader, and no Unity-side import are performed in this stage.
- No silent filtering: drops/remaps are always counted in `conversion_report.json`.
- Raw action layout is explicitly detected and only supported layouts are normalized.
- Extra observation channels are treated as signal-loss adaptation events, not neutral trimming.

## Day 4 output artifacts

Per adapted batch in `teacher_exports/teacher_adapted_<raw_batch>_<timestamp>/`:

- `episode_00000.adapted.npz`, ... (primary adapted output)
- `conversion_report.json` (mandatory conversion accounting)
- `adapted_batch.summary.json` (artifact index)
- `conversion_debug.jsonl` (optional per-step diagnostics)

`conversion_report.json` now separates:

- observed conversion events (step/sample level);
- policy-level enforced rules (design constraints);
- semantic weakening counters for remap-to-NoOp behavior;
- input batch provenance kind (`infrastructure_validation` / `teacher_candidate` / `unknown`).

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
- `--backend-mode`: prefer primary backend with optional controlled fallback.
- `--force-legacy-backend`: explicit emergency/diagnostic legacy route.
- `--opponent-pool`: opponent pool for backend-managed regimes (comma-separated).
- `--opponent-sampling`: opponent sampling mode.
- `--opponent-seed`: optional seed for opponent sampling.
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

## Day 5 validator (contract-level)

Use Day 5 validator on any adapted batch directory produced by Day 4:

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/validate_adapted_dataset.py \
  --adapted-batch-dir c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/teacher_exports/teacher_adapted_day5_first_nonrandom_meaningful \
  --strict
```

Validator outputs:

- `strict_validation_day5.json` (hard failures + warnings split)
- `quality_report_day5.json` (sanity metrics + weak spots)
- `quality_report_day5.md` (human-readable summary)

Day 5 validator now includes:

- explicit `channel_validation_policy` (spec-driven, assumption-sensitive checks are marked)
- inactive-branch anomaly summary + severity (`low|medium|high`)
- lightweight `episode_level_diagnostics` and `top_warning_patterns`
- explicit `bc_readiness_interpretation` boundary block

Detailed Day 5 checks and report interpretation are documented in `DAY5_VALIDATION.md`.

## Day 7 official entrypoints (Week 5 closure)

The following scripts are the official Week 5 public entrypoints:

1. Rollout/export: `run_teacher_rollout.py`
2. Adapter: `adapt_teacher_dataset.py`
3. Validator: `validate_adapted_dataset.py`
4. BC-ready packaging: `build_bc_ready_dataset_day6.py`
5. BC loader dry run: `dry_run_bc_loader.py`

Expected output roots by stage:

- Day 3 rollout/export: `teacher_rollouts/`, `teacher_logs/`
- Day 4 adapter: `teacher_exports/` (`conversion_report.json`, `adapted_batch.summary.json`)
- Day 5 validation: adapted batch local outputs (`strict_validation_day5.json`, `quality_report_day5.*`)
- Day 6 packaging: `teacher_exports_bc/` (`bc_manifest.json`, split `.npz`, dry-run report)

Current preferred BC-ready dataset (updated 2026-04-22 — post-correction baseline switch):

- `teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z`

Previous preferred (now historical baseline only — do not delete):

- `teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_first_nonrandom_meaningful_20260421T103641Z`

Baseline switch reason: corrective rerun confirmed root-cause diagnosis; comparison result=better.  
Detailed comparison: `../../WEEK5/PREFERRED_TEACHER_BASELINE_UPDATE.md`

## Week 5 explicit limitations (Day 7 fixed record)

- Teacher quality remains bounded by available teacher candidate quality.
- Adapter path includes approximation and non-bijective mapping.
- Action filtering/remapping exists, including remap-to-noop pressure.
- Mask semantics are diagnostic/pre-sampling context, not full runtime-truth transfer.
- Direct Gym->Unity semantic parity is not proven by Week 5.
- Direct weight transfer remains blocked and was not a Week 5 goal.
- BC-ready packaging and dry run do not prove BC training success.

## Week 6 bridge (input contract handoff)

Canonical Week 6 student-side inputs (updated 2026-04-22 — post-correction baseline switch):

Preferred BC-ready run:

- `teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z/`

Expected files within that directory:

- `bc_train.npz` (3,650 samples)
- `bc_validation.npz` (390 samples)
- optional `bc_debug.npz` (256 samples)
- `bc_manifest.json`
- `dry_run_bc_loader_report.json`

Previous preferred BC-ready run (historical baseline only):

- `teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_first_nonrandom_meaningful_20260421T103641Z/`

These files are produced by `build_bc_ready_dataset_day6.py` and verified by `dry_run_bc_loader.py`.

For full Week 5 closure summary and baseline switch documentation, see:

- `../../WEEK5/WEEK5_TEACHER_PIPELINE_SUMMARY.md`
- `../../WEEK5/PREFERRED_TEACHER_BASELINE_UPDATE.md`