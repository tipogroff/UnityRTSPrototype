# STAGE10D21B2 Same-Command Accepted/Rejected Conflict Root-Cause Audit

- Generated (UTC): 2026-05-03T22:58:24.724779+00:00
- Conflict commands analyzed: 4
- Reclassification pass: PASS
- Stage10D.21B3 gate: GO_FOR_STAGE10D21B3_STATUS_MAPPING_FIX
- Stage10D.21C gate: NO-GO

## Reclassified Status Counts
- matchmanager_rejected: 4

## Required Answers
- Q3 ActionApplier accept while MatchManager reject: False
- Q4 MatchManager directly rejected Move: True
- Q5 Any command reached unit_action_set_or_queue: True
- Q6 Modeling vs gameplay: gameplay_rejection_with_telemetry_modeling_collapse

## Per-Command Canonical Status
- cmd:78: matchmanager_rejected (accepted_stage=matchmanager_applycommand, rejected_stage=matchmanager_applycommand)
- cmd:106: matchmanager_rejected (accepted_stage=matchmanager_applycommand, rejected_stage=matchmanager_applycommand)
- cmd:120: matchmanager_rejected (accepted_stage=matchmanager_applycommand, rejected_stage=matchmanager_applycommand)
- cmd:142: matchmanager_rejected (accepted_stage=matchmanager_applycommand, rejected_stage=matchmanager_applycommand)

## Artifacts
- Timeline trace: python/week6_student/reports/stage10d21b2_command_event_timeline_trace.jsonl
- JSON report: python/week6_student/reports/stage10d21b2_same_command_conflict_report.json
- Markdown report: python/week6_student/reports/STAGE10D21B2_SAME_COMMAND_CONFLICT_REPORT.md
