# Week 5 Day 5 - Contract Validation and Sanity Checks

This document describes Day 5 validator scope for adapted teacher datasets.

## Purpose

Day 5 validates contract-level consistency of Day 4 adapted artifacts and generates a first quality report for BC readiness triage.

It is intentionally not:

- BC training
- Unity runtime import/run
- RL benchmark scoring of teacher
- full Gym<->Unity semantic parity proof

## Entrypoint

Run from project root:

```powershell
python/week5_teacher/.venv_day2_py39/Scripts/python.exe python/week5_teacher/validate_adapted_dataset.py \
  --adapted-batch-dir python/week5_teacher/teacher_exports/teacher_adapted_day5_first_nonrandom_meaningful \
  --strict
```

Optional flags:

- `--output-dir <path>`: where Day 5 artifacts are written (default: same adapted batch dir)
- `--sample-episodes <int>`: number of episodes in sanity sample section (default: 3)
- `--strict`: non-zero exit when hard failures are present

## Input Artifacts

Validator reads:

- `episode_*.adapted.npz`
- `conversion_report.json`
- `adapted_batch.summary.json`

## Hard Contract Checks

Validator uses explicit channel validation policy (`channel_validation_policy` in strict report), not implicit defaults.

Validation rule dimensions:

- `encoding_type`: `one_hot_strict`, `categorical_soft`, `bounded_continuous`, `unchecked`
- `failure_level`: `hard_failure` or `warning`
- `spec_assumption`: `true/false` to mark assumption-sensitive checks

### Observation checks

- expected shape `[steps,24,24,27]`
- finite values only (no NaN/Inf)
- value range in `[0,1]`
- spec-driven channel policy on slices:
  - owner `[2:5]`: `one_hot_strict` / `hard_failure`
  - unit_type `[5:12]`: `categorical_soft` / `warning` (assumption-sensitive)
  - current_action `[12:18]`: `categorical_soft` / `warning` (assumption-sensitive)
  - action_direction `[18:22]`: `one_hot_strict` / `hard_failure`
  - produce_unit_type `[22:26]`: `one_hot_strict` / `hard_failure`
- attack target observation channel `[26]` uses only allowed encoded values: `0` or `(localIndex+1)/9`
- global-vector exclusion rule:
  - `conversion_report.contract.global_vector_policy` must be `excluded_from_strict_bc_encoder_path`
  - adapted NPZ must not contain unexpected global-like keys

### Action checks

- expected shape `[steps,576,7]`
- integer-valued branches
- per-branch range constraints:
  - branch 0 (action type): `[0..5]`
  - branches 1..5 (dirs/produce type): `[0..3]`
  - branch 6 (attack local target): `[0..8]`
- unsupported action values are rejected as hard failures
- branch contract consistency for decoder assumptions

Inactive branches are checked and reported as warnings (non-canonical payload pattern), with severity added to quality report.

## Policy-side Semantics Checks

Validator reports contract-level consistency flags for:

- `observation_contract_consistency`
- `global_vector_excluded_rule_respected`
- `action_decoder_assumption_consistency`
- `mask_semantics_treated_as_diagnostic_only`

Important: these checks validate consistency with Week 3/4 assumptions at contract level only.

## Sanity and Quality Metrics

Quality report includes:

- usable samples
- dropped samples
- conversion loss share
- usable vs dropped ratio
- remap-to-noop count/share
- semantic weakening share
- observation signal-loss share
- production actions survived share
- action type distribution and class imbalance ratio
- attack/local-target case share
- sampled episode statistics
- main weak spots detected
- inactive branch anomaly summary:
  - `inactive_branch_anomaly_count`
  - `inactive_branch_anomaly_share`
  - `inactive_branch_warning_severity` (`low|medium|high`)
- episode-level diagnostics:
  - per-episode contract issue counts
  - dropped/weakened shares
  - remap concentration
  - `top_problematic_episodes`
  - `top_warning_patterns`

## Inactive Branch Severity

`inactive_branch_warning_severity` is derived from `inactive_branch_anomaly_share` thresholds:

- `low`: share < 0.03
- `medium`: 0.03 <= share < 0.10
- `high`: share >= 0.10

Severity is diagnostic and does not auto-promote warnings to hard failures.

Hard failures and warnings are separated.

## Output Artifacts

Per validator run:

- `strict_validation_day5.json`
- `quality_report_day5.json`
- `quality_report_day5.md`

New required sections:

- `strict_validation_day5.json.validation.channel_validation_policy`
- `quality_report_day5.json.quality.inactive_branch_anomalies`
- `quality_report_day5.json.sanity.episode_level_diagnostics`
- `quality_report_day5.json.bc_readiness_interpretation`

## Interpretation Guide

- `usable_samples`: samples that remain after adapter conversion
- `dropped_samples`: samples removed by explicit conversion rules
- `conversion_loss_share`: `dropped_samples / total_samples`
- `class_imbalance`: action type share skew in converted action labels
- `remap_to_noop_share`: proportion of action cells remapped to NoOp by compatibility rules
- `semantic_weakening_share`: fraction of samples marked weakened by conversion
- `observation_signal_loss_share`: fraction of samples with explicit observation signal-loss events

These metrics are intended for BC dataset readiness triage, not final teacher quality claims.

## BC Readiness Boundary

Day 5 report now includes explicit `bc_readiness_interpretation` with:

- what Day 5 proves (contract-level consistency and diagnostics)
- what Day 5 does not prove (BC quality/performance, full semantic parity)
- next decision options (revalidate stronger batch, fix contract issues, then separate BC smoke stage)

## Reusability and Ongoing Training

Day 5 validator is batch-oriented and reusable.

- Current Day 5 run can be executed immediately on the currently available meaningful adapted batch.
- Ongoing long teacher training is not required to finish before Day 5 validation.
- Future stronger teacher batches can be validated with the same entrypoint.
