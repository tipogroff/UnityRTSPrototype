# Week 5 Day 4 Adapter

This document defines the Day 4 adapter entrypoint and artifacts.

## Scope

Day 4 adapter performs only contract conversion of Day 3 raw rollout exports:

- input: Day 3 raw batch (`episode_*.npz` + `batch.summary.json`)
- output: adapted batch for Unity-side contract surface + explicit conversion report

Day 4 adapter does not perform:

- BC training
- student-side loading
- Unity runtime integration
- teacher quality validation claims

## Entrypoint

Run from project root:

```powershell
python/week5_teacher/.venv_day2_py39/Scripts/python.exe python/week5_teacher/adapt_teacher_dataset.py \
  --input-batch-dir python/week5_teacher/teacher_rollouts/teacher_raw_debug_day3smoke_20260416T121055Z \
  --write-debug-jsonl
```

Optional flags:

- `--allow-spatial-resize`: allows explicit approximate crop/pad to 24x24 when raw observation has other spatial size.
- `--hp-divisor <float>`: force channel[0] normalization divisor.
- `--resource-divisor <float>`: force channel[1] normalization divisor.
- `--output-root <path>` and `--output-batch-name <name>`: control output location and folder naming.

## Observation conversion policy

Target shape is `[24,24,27]`.

Rules:

- exact: raw observation can be represented directly as 24x24x27 with no approximation;
- approximate: channel trimming, explicit normalization, or optional spatial crop/pad was required;
- approximate_with_signal_loss: conversion succeeded but dropped potentially meaningful signal;
- dropped: conversion impossible without hidden imputation.

Global vector policy:

- Unity-only global vector is excluded from strict BC encoder path.

Normalization formula:

- channel[0] (HP): `clip(raw_hp / hp_divisor, 0, 1)`
- channel[1] (Resources): `clip(raw_res / resource_divisor, 0, 1)`

Divisors are inferred from observed maxima unless explicitly provided via CLI.

Signal-loss policy:

- if channels > 27, adapter trims to first 27 and marks event as signal-loss (`obs.extra_channels_dropped_signal_loss`);
- if spatial crop is needed (only with `--allow-spatial-resize`), this is also marked as signal-loss.

## Action conversion policy

Target action shape per step is `[576,7]` with branch sizes `[6,4,4,4,4,4,9]`.

Adapter first detects raw action layout, then normalizes payload only for explicitly supported layouts.

Supported layouts:

- `matrix_576x7` (exact)
- `flat_4032` (exact)
- `object_flat_4032` (approximate normalization)
- `batched_flat_1x4032` (approximate normalization)
- `batched_matrix_1x576x7` (approximate normalization)

Unsupported layouts:

- no guessing parser is applied;
- sample is dropped with explicit reason in report/debug (`drop:action:unsupported_layout:...`).

After layout normalization, adapter applies explicit gap mitigations:

- unsupported action types -> remap to NoOp and count reason;
- produce unit types outside MVP subset -> remap to NoOp and count reason;
- attack target reduced from source range (for example 49-way) to local 3x3 (9-way):
  - in-window targets are mapped;
  - out-of-window targets are remapped to NoOp and counted.

No silent filtering is used.

Semantic weakening policy:

- any remap-to-NoOp caused by incompatibility is counted as semantic weakening;
- report contains aggregated fields:
  - `remapped_to_noop_count`
  - `semantically_weak_action_count`
  - per-reason NoOp counters.

## Output artifacts

Each adapted batch directory contains:

- `episode_XXXXX.adapted.npz` (one file per episode with converted steps)
- `conversion_report.json` (mandatory report)
- `adapted_batch.summary.json` (artifact index)
- `conversion_debug.jsonl` (optional per-step debug trace)

## Conversion report schema (high-level)

`conversion_report.json` includes:

- `input` / `output` metadata
- `input.input_batch_kind` (`infrastructure_validation` / `teacher_candidate` / `unknown`)
- `contract` metadata (target shapes, branch sizes, normalization formula, source branch sizes)
- `policy_rules` (design decisions, not observed step-level events)
- `counters.samples` (`total`, `exact`, `adapted`, `dropped`)
- `counters.observation` (`exact`, `approximate`, `dropped`, `signal_loss_events`)
- `counters.action` (`exact`, `adapted`, `dropped`)
- `counters.observed_gap_events` (real observed conversion events only)
- `counters.action_layouts` (layout support usage)
- `counters.semantic_quality` (`exact`, `adapted`, `weakened`, `dropped`)
- `counters.semantic_weakening` (NoOp-remap totals and reasons)
- `counters.top_drop_reasons`
- `counters.top_adaptation_reasons`
- `action_histograms` (input and output action type distributions)
- `episodes` per-episode conversion summary

## Notes about teacher source

Adapter is teacher-source-agnostic because it consumes Day 3 raw dataset artifacts, not live policy objects.

If the raw batch comes from random fallback, adapter still runs and reports conversion integrity honestly, while policy quality remains out of Day 4 scope.

`input_batch_kind` is informational provenance only and must not be interpreted as teacher quality score.
