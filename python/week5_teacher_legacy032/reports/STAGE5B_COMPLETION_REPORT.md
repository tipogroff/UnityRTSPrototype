# STAGE5B Completion Report

- Date: 2026-04-30
- run_id: legacy032_24x24_teacher_main_20260429T171506Z
- status: PASS_WITH_WARNINGS
- decision: READY_FOR_1M_WITH_WARNINGS

## Files Created / Updated

Created:
- python/week5_teacher_legacy032/reports/stage5b_24x24_contract_probe.json
- python/week5_teacher_legacy032/reports/stage5_24x24_training_20260429T171506Z.json
- python/week5_teacher_legacy032/reports/stage5_24x24_training_20260429T171506Z.md
- python/week5_teacher_legacy032/reports/stage5_gate_000500000_20260429T190313Z.json
- python/week5_teacher_legacy032/reports/stage5_gate_000500000_20260429T190313Z.md
- python/week5_teacher_legacy032/reports/STAGE5_100K_VS_500K_COMPARISON.md
- python/week5_teacher_legacy032/reports/STAGE5B_500K_TRAINING_REPORT.md
- python/week5_teacher_legacy032/reports/STAGE5B_COMPLETION_REPORT.md
- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260429T171506Z/stage_000500000/agent_final.pt
- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260429T171506Z/stage_000500000/model_metadata.json

Updated:
- python/week5_teacher_legacy032/LEGACY032_TEACHER_TRAINING_PLAN.md
- python/week5_teacher_legacy032/scripts/README.md
- python/week5_teacher_legacy032/reports/STAGE5A_100K_TRAINING_REPORT.md (restored Stage5A baseline context)
- python/week5_teacher_legacy032/reports/STAGE5A_COMPLETION_REPORT.md (restored Stage5A baseline context)

## Stage Checkpoint

- checkpoint_path: python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260429T171506Z/stage_000500000/agent_final.pt
- metadata_path: python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260429T171506Z/stage_000500000/model_metadata.json

## Gate Reports

- 500k gate json: python/week5_teacher_legacy032/reports/stage5_gate_000500000_20260429T190313Z.json
- 500k gate md: python/week5_teacher_legacy032/reports/stage5_gate_000500000_20260429T190313Z.md
- baseline 100k gate json: python/week5_teacher_legacy032/reports/stage5_gate_000100000_20260429T164521Z.json

## Comparison Report

- python/week5_teacher_legacy032/reports/STAGE5_100K_VS_500K_COMPARISON.md

## Current Status

- READY_FOR_1M_WITH_WARNINGS

## Exact Next Action

- Run Stage 5C at 1M on the same corrected 24x24 GridMode path only, and require a fresh 500k->1M comparison focused on deterministic noop collapse, return trend, and mask/contract stability.
