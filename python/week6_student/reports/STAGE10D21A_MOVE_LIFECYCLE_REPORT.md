# STAGE10D21A Move Lifecycle Report

- Generated (UTC): 2026-05-03T22:21:44.214869+00:00
- Source: Stage10D.20S rerun artifacts
- Steps analyzed: 76 (last=76)
- Acceptance pass: True

## Classification Coverage (A..I)
- all_events_classified_exactly_once: True
- category_A_count: 0
- category_B_count: 0
- category_C_count: 0
- category_D_count: 0
- category_E_count: 0
- category_F_count: 0
- category_G_count: 0
- category_H_count: 4
- category_I_count: 0

## Required Counts
- legal_masked_move_events_traced: 4
- clean_accepted_move_commands: 0
- legacy_conflict_move_commands: 4
- matchmanager_accepted_commands: 4
- commands_set_or_queued_on_unit: 4
- commands_with_displacement_within_plus1: 0
- commands_with_displacement_within_plus2_to_plus5: 0

## Canonical Status Counts
- accepted_pending: 4
- applied: 0
- applier_rejected: 0
- completed: 0
- decoder_rejected: 0
- matchmanager_rejected: 0
- not_submitted: 0

## First Failure Points
- telemetry_conflict: 4

## GO/NO-GO
- movement_application_fix: NO-GO
- command_status_telemetry_cleanup: NO-GO
- full_map_stage10d21_behavior_rerun: NO-GO

## Artifacts
- Trace JSONL: python/week6_student/reports/stage10d21a_move_lifecycle_trace.jsonl
- Report JSON: python/week6_student/reports/stage10d21a_move_lifecycle_report.json
- Report MD: python/week6_student/reports/STAGE10D21A_MOVE_LIFECYCLE_REPORT.md
