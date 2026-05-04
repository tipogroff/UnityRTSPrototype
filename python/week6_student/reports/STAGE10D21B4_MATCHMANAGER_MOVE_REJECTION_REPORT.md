# STAGE10D21B4 MatchManager Move Rejection Reason Audit

- Generated (UTC): 2026-05-03T23:18:08.477074+00:00
- Commands analyzed: 4
- Stage10D.21B4 gate: PASS
- Stage10D.21B5 gate: GO
- Stage10D.21C gate: NO-GO

## Reject Buckets
- target_occupied: 4

## Required Answers
- Q1 exact command_ids analyzed: cmd:78, cmd:106, cmd:120, cmd:142
- Q3 MatchManager rejected because target was occupied: True
- Q4 MatchManager rejected because unit was busy/already had action: False
- Q5 rejection phase: later_movement_execution_phase
- Q6 cause class: runtime_state_semantics_not_represented_in_mask
- Q7 next fix: legal mask enrichment
- Q8 Stage10D.21B5 gate: GO_FOR_STAGE10D21B5_TARGETED_FIX
- Q9 Stage10D.21C gate: NO-GO

## Artifacts
- Trace: python/week6_student/reports/stage10d21b4_matchmanager_move_rejection_trace.jsonl
- JSON: python/week6_student/reports/stage10d21b4_matchmanager_move_rejection_report.json
- Markdown: python/week6_student/reports/STAGE10D21B4_MATCHMANAGER_MOVE_REJECTION_REPORT.md
