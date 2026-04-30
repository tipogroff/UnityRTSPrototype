# STAGE5C 1M Training and Diagnostics Report

## Summary

- 1M training completed on corrected 24x24 GridMode path.
- Standard gate completed and passed at machine gate level.
- Extended large-map diagnostics completed successfully.
- Final classification: READY_FOR_3M_WITH_WARNINGS.

## Artifacts

- checkpoint path: `python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260429T195603Z/stage_001000000/agent_final.pt`
- metadata path: `python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260429T195603Z/stage_001000000/model_metadata.json`
- training report JSON: `python/week5_teacher_legacy032/reports/stage5_24x24_training_20260429T195603Z.json`
- training report MD: `python/week5_teacher_legacy032/reports/stage5_24x24_training_20260429T195603Z.md`
- standard gate JSON: `python/week5_teacher_legacy032/reports/stage5_gate_001000000_20260429T232455Z.json`
- standard gate MD: `python/week5_teacher_legacy032/reports/stage5_gate_001000000_20260429T232455Z.md`
- diagnostics JSON: `python/week5_teacher_legacy032/reports/stage5c_large_map_diagnostics_20260430T123128Z.json`
- diagnostics MD: `python/week5_teacher_legacy032/reports/stage5c_large_map_diagnostics_20260430T123128Z.md`
- action trace: `python/week5_teacher_legacy032/reports/stage5c_large_map_action_trace_20260430T123128Z.jsonl`
- comparison report: `python/week5_teacher_legacy032/reports/STAGE5_100K_500K_1M_COMPARISON.md`

## Technical compatibility

- checkpoint load: pass
- policy architecture load: pass
- inference: pass
- target_24x24_gridmode compatibility: pass (`env_matches_target_24x24=true`)
- mask usage during eval: pass (`mask_used_during_eval=true`)
- metadata contract: pass (`[24,24,27]` and `[576,6,4,4,4,4,7,49]`, architecture `legacy032_resolution_aware_gridnet_v1`)
- training horizon config: pass (`training_max_steps=6000`, `env_max_steps=6000`, `max_steps=6000`)
- gate horizon config: pass (`max_steps_per_episode=6000`, `env_max_steps=6000`)

## Behavior interpretation

- deterministic mode remains very NoOp-heavy by all-cell metrics
- stochastic mode remains active and nonzero across move/harvest/return/produce/attack
- large-map diagnostics confirm economy/production activity
- combat/contact remains sparse and exact contact is not directly measurable from available info
- return has not shown strong improvement by 1M

## Decision

READY_FOR_3M_WITH_WARNINGS

Rationale:

- technical checks passed and remained stable
- economy and production activity are present in diagnostics
- stochastic activity remains nonzero and stable
- combat proxy is present (attack actions), though contact certainty is limited
- no fatal regression or compatibility failure detected
- warnings remain for weak return trend, very high deterministic all-cell noop_share, entropy decline, and source-cell/contact limitations

## Stale decision-label note

- `READY_FOR_500K` in Stage 5C orchestrator output is a stale generic decision label.
- Human review supersedes this stale label.
- Final Stage 5C decision is based on standard gate + extended large-map diagnostics + 100k/500k/1M comparison.

## Exact next action

- Run Stage 5D 3M from-scratch on corrected 24x24 GridMode path.
- Use `training_max_steps=6000`.
- Use `max_steps_per_gate=6000`.
- Require extended large-map diagnostics after 3M before any 5M decision.
- Do not proceed to 5M unless 3M improves return/contact/behavior or diagnostics clearly justify continuation.
