# STAGE5C Completion Report

## Scope closed

- Stage 5C 1M training evidence reviewed
- Stage 5C standard gate reviewed
- Stage 5C extended large-map diagnostics reviewed
- Final 100k vs 500k vs 1M comparison completed

## Run and artifact anchors

- run_id: `legacy032_24x24_teacher_main_20260429T195603Z`
- checkpoint path: `python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260429T195603Z/stage_001000000/agent_final.pt`
- standard gate report path: `python/week5_teacher_legacy032/reports/stage5_gate_001000000_20260429T232455Z.json`
- diagnostic report path: `python/week5_teacher_legacy032/reports/stage5c_large_map_diagnostics_20260430T123128Z.json`
- comparison report path: `python/week5_teacher_legacy032/reports/STAGE5_100K_500K_1M_COMPARISON.md`

## Files created/updated in this closure step

- created: `python/week5_teacher_legacy032/reports/STAGE5_100K_500K_1M_COMPARISON.md`
- created: `python/week5_teacher_legacy032/reports/STAGE5C_1M_TRAINING_AND_DIAGNOSTICS_REPORT.md`
- created: `python/week5_teacher_legacy032/reports/STAGE5C_COMPLETION_REPORT.md`
- updated: `python/week5_teacher_legacy032/LEGACY032_TEACHER_TRAINING_PLAN.md`
- updated: `python/week5_teacher_legacy032/scripts/README.md`

## Final decision

READY_FOR_3M_WITH_WARNINGS

## Exact next action

- Run Stage 5D 3M from-scratch on corrected 24x24 GridMode path.
- Use `training_max_steps=6000` and `max_steps_per_gate=6000`.
- Require extended large-map diagnostics after 3M before any 5M decision.
- Do not proceed to 5M unless 3M improves return/contact/behavior or diagnostics justify continuation.
