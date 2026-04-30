# STAGE5C Env Max Steps Fix Report

## Problem Summary

Stage 5C gate used `--max-steps-per-gate 6000` at orchestration level, but visual behavior suggested episodes were still restarting around `T=2000`.

## Root Cause

Only the outer evaluator loop horizon was controlled. Internal environment cap (`MicroRTSGridModeVecEnv(max_steps=...)`) was not independently configurable from CLI and could remain effectively aligned to older defaults depending on call path.

## Files Changed

- python/week5_teacher_legacy032/scripts/evaluate_teacher_legacy032.py
- python/week5_teacher_legacy032/scripts/run_24x24_staged_teacher_training_legacy032.py
- python/week5_teacher_legacy032/scripts/README.md
- python/week5_teacher_legacy032/reports/STAGE5C_ENV_MAX_STEPS_FIX_REPORT.md

## Old Behavior

- Gate could run with outer loop `max_steps_per_episode=6000`.
- Internal env cap was not separately exposed and could still be constrained by older assumptions.
- Result: apparent mismatch between requested gate horizon and observed episode lifecycle.

## New Behavior

- Evaluator now supports `--env-max-steps` and writes both horizons to report:
  - `max_steps_per_episode`
  - `env_max_steps`
- `target_24x24_gridmode` env creation now uses explicit `env_max_steps` value.
- Stage 5 orchestrator now passes both:
  - `--max-steps-per-episode <max-steps-per-gate>`
  - `--env-max-steps <max-steps-per-gate>`
- Evaluator report now includes:
  - `episode_end_reason_counts`
  - `observed_max_episode_length`
  - warning when requested long horizon is inconsistent with observed lengths.

## Smoke Evaluation Result

Command executed on existing Stage 5B 500k checkpoint (no training):
- run_label: `stage5c_env_max_steps_6000_smoke`
- episodes: `2`
- env_mode: `target_24x24_gridmode`
- require_mask: `true`
- max_steps_per_episode: `6000`
- env_max_steps: `6000`

Generated report:
- python/week5_teacher_legacy032/reports/stage3_smoke_checkpoint_behavior_gate_20260429T194125Z.json
- python/week5_teacher_legacy032/reports/stage3_smoke_checkpoint_behavior_gate_20260429T194125Z.md

Observed:
- `env_max_steps=6000` present in report.
- `max_steps_per_episode=6000` present in report.
- `episode_end_reason_counts`: env_done=2, outer_loop_limit=0, unknown=0.
- `observed_max_episode_length=505`.

## Whether Episode Lengths Exceeded 2000

- No, in this smoke run they did not exceed 2000.
- Episodes ended by `env_done` at length 505, not by outer loop limit.

## Remaining Suspected Caps / Constraints

Because this smoke run ended on `env_done` before long horizons were reached, it cannot alone prove long-episode traversal beyond 2000. Remaining suspects for short episodes in other runs:
- native MicroRTS match termination conditions (win/loss/draw) ending episodes early;
- task dynamics on this checkpoint causing fast terminal outcomes;
- other wrapper/runtime constraints in gym_microrts stack not hit in this 2-episode sample.

## Execution Safety Confirmation

- No 1M/3M/5M training launched.
- No rollout export/adaptation/BC dataset actions performed.
- No Unity/C# files changed.

## Exact Next Action

Run a longer Stage 5C gate-only validation (same checkpoint, more episodes and fixed `--env-max-steps 6000`) and inspect whether any episode reaches or exceeds 2000 before moving to the next Stage 5C training prompt.
