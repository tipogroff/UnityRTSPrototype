# STAGE5C Training Max Steps Fix Report

## Problem Summary

Stage 5C evaluator/gate horizon had already been fixed to 6000, but training episodes were still ending at T=2000 during visual observation. This indicated a separate horizon cap in the training path.

## Root Cause

The Stage 5 24x24 orchestrator was only controlling gate horizon (`--max-steps-per-gate`) and did not pass trainer env horizon. The trainer default remained `--max-steps 2000`, so `MicroRTSGridModeVecEnv(max_steps=...)` in training still used 2000.

## Files Changed

- python/week5_teacher_legacy032/scripts/run_24x24_staged_teacher_training_legacy032.py
- python/week5_teacher_legacy032/scripts/ppo_gridnet_legacy032_24x24_local_save.py
- python/week5_teacher_legacy032/scripts/README.md

## Old Behavior

- Gate/evaluator env horizon fixed to 6000 (`--max-steps-per-episode 6000`, `--env-max-steps 6000`).
- Training env still used internal `max_steps=2000` due to trainer default and missing pass-through from Stage 5 orchestrator.

## New Behavior

- Stage 5 orchestrator now supports `--training-max-steps` (default 6000).
- Stage 5 orchestrator passes trainer horizon as `--max-steps <training_max_steps>`.
- Stage report JSON now records:
  - `config.training_max_steps`
  - `config.max_steps_per_gate`
  - `stages[].training_config.max_steps`
  - existing `stages[].gate_config.max_steps_per_episode` and `stages[].gate_config.env_max_steps`
- Trainer metadata now explicitly records:
  - `training_max_steps`
  - `env_max_steps`
  - `max_steps`
  - plus contract metadata (`map_path`, `expected_map_size`, `action_space_nvec`, `observation_space`, `architecture_name`).

## Smoke Result

Short training smoke was executed (2000 timesteps only; no long training):

- command script: `python/week5_teacher_legacy032/scripts/ppo_gridnet_legacy032_24x24_local_save.py`
- key flags: `--max-steps 6000`, `--map-path maps/24x24/basesWorkers24x24.xml`, `--expected-map-size 24`
- result: success (exit code 0)
- artifacts:
  - `python/week5_teacher_legacy032/teacher_models/stage5c_training_max_steps_6000_smoke/agent_final.pt`
  - `python/week5_teacher_legacy032/teacher_models/stage5c_training_max_steps_6000_smoke/model_metadata.json`

## Metadata Verification

Verified in `model_metadata.json`:

- `training_max_steps: 6000`
- `env_max_steps: 6000`
- `max_steps: 6000`
- `map_path: maps/24x24/basesWorkers24x24.xml`
- `expected_map_size: 24`
- `observation_space: [24, 24, 27]`
- `action_space_nvec: [576, 6, 4, 4, 4, 4, 7, 49]`
- `architecture_name: legacy032_resolution_aware_gridnet_v1`

## Exact Next Action

Restart Stage 5C 1M with --training-max-steps 6000 and --max-steps-per-gate 6000.
