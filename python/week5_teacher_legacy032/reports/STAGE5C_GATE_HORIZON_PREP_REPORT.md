# STAGE5C Gate Horizon Prep Report

## Files Updated

- python/week5_teacher_legacy032/scripts/run_24x24_staged_teacher_training_legacy032.py
- python/week5_teacher_legacy032/scripts/README.md
- python/week5_teacher_legacy032/reports/STAGE5C_GATE_HORIZON_PREP_REPORT.md

## What Changed

- Added Stage 5 orchestrator CLI flag: `--max-steps-per-gate` (default `6000`).
- Stage 5 gate invocation now forwards this value to evaluator as `--max-steps-per-episode <value>`.
- Removed Stage 5 orchestrator dependence on hardcoded gate horizon `2000`.
- Added per-stage machine-readable gate configuration block in `stage5_24x24_training_<timestamp>.json`:

```json
"gate_config": {
  "episodes": 8,
  "eval_mode": "both",
  "env_mode": "target_24x24_gridmode",
  "require_mask": true,
  "max_steps_per_episode": 6000
}
```

- Updated scripts README with:
  - `--max-steps-per-gate` description.
  - Stage 5C 1M command example including `--max-steps-per-gate 6000`.
  - Rationale for 6000-step gate horizon on 24x24 large-map evaluation.
  - Comparison warning for Stage 5A/5B (old horizon) vs Stage 5C (new horizon).

## Old Behavior

- Stage 5 orchestrator always passed `--max-steps-per-episode 2000` to gate evaluator.
- Gate horizon was not explicitly recorded per stage in a dedicated machine-readable `gate_config` block.

## New Stage 5C Behavior

- Stage 5 orchestrator explicitly controls gate horizon via `--max-steps-per-gate`.
- Default Stage 5C gate horizon is `6000` and is always forwarded to evaluator.
- Per-stage report data now records gate execution configuration including `max_steps_per_episode`.

## Execution Confirmation

- No training was run.
- No 1M/3M/5M run was started.
- No diagnostics were run.

## Exact Next Action

Run Stage 5C 1M training with --max-steps-per-gate 6000.
