# STAGE10D21B Authoritative Command Result Telemetry Cleanup Report

- Generated (UTC): 2026-05-03T22:49:47.570823+00:00
- Steps analyzed: 76 (last=76)
- Unique command IDs: 4
- Cleanup gate: NO-GO

## Required Questions
- Q1 command_id present: Per-command IDs are present
- Q2 authoritative status only: Statuses are authoritative
- Q3 accepted/rejected mutually exclusive: Rows exist with both accepted and rejected true
- Q4 same-command conflicts removed: Conflicts remain on command-level telemetry
- Q5 same-flat multi-command merge removed: No same-flat multi-command merges
- Q6 event provenance present: Event provenance fields populated
- Q7 Stage10D.21C gate: Cleanup NO-GO

## Key Counts
- move_candidate_rows: 4
- trace_rows: 4
- authoritative_status_rows: 4
- mutually_exclusive_rows: 0
- command_level_conflicts: 4
- same_flat_multi_command_pairs: 0

## Ratios
- authoritative_status_ratio: 1.000000
- mutually_exclusive_ratio: 0.000000

## Artifacts
- Trace JSONL: python/week6_student/reports/stage10d21b_command_status_trace.jsonl
- Report JSON: python/week6_student/reports/stage10d21b_command_status_report.json
- Report MD: python/week6_student/reports/STAGE10D21B_COMMAND_STATUS_REPORT.md
