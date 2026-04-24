# Week 6 Day 5 Sanity Matches

Generated: 2026-04-23 18:35:15
Student-controlled side: Player1
Baseline side: Player2
Checkpoint: python/week6_student/runs/day3_transfer_bc_main_20260423/student_bc_transfer_best.pt

## Framing

This run is a sanity-check of the transferred control path, not a gameplay strength claim.
The student side is driven per-step through Unity observation -> student inference bridge -> authoritative branch contract -> transfer-compatible decode -> ActionApplier -> MatchManager.ApplyCommand().

## Batch Summary

| Metric | Value |
|---|---|
| Episodes | 3 |
| Total steps | 6000 |
| Total decoded student actions | 126447 |
| Applier rejected share | 99,97% |
| Runtime rejected share | 0,00% |
| Average produce frequency / step | 16,0615 |
| Average attack frequency / step | 3,0105 |
| Average no-action step share | 0,00% |

## Action Histogram

| Action | Count |
|---|---|
| Produce | 96369 |
| Attack | 18063 |
| Return | 12003 |
| Harvest | 12 |

## Terminal Reasons

| Reason | Count |
|---|---|
| Timeout | 3 |

## Runtime Rejection Reasons

| Reason | Count |
|---|---|

## Episode Summaries

| Episode | Steps | Decoded | Produce | Attack | Applier Rejected | Runtime Rejected | No-action share | Winner | Terminal |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2000 | 42149 | 32123 | 6021 | 99,97% | 0,00% | 0,00% | Neutral | Timeout |
| 2 | 2000 | 42149 | 32123 | 6021 | 99,97% | 0,00% | 0,00% | Neutral | Timeout |
| 3 | 2000 | 42149 | 32123 | 6021 | 99,97% | 0,00% | 0,00% | Neutral | Timeout |

## Assessment Notes

- Rejected command share is non-trivial. This does not prove a broken pipeline, but it remains a candidate decoder/runtime semantics issue.

## Observed Failure Patterns

- Applier-level rejection dominated the run: 126408 of 126447 decoded student actions were rejected before reaching MatchManager runtime execution.
- Runtime rejected share stayed at 0.00%, which means the main failure surface was upstream of MatchManager command processing rather than inside the later step-phase executor.
- Editor log inspection for `source=week6-day5-student-live` showed repeated `MaskMismatch` cases where Player1 submissions targeted cells owned by Player2 or Neutral.
- Additional applier failures showed branch-semantic mismatches such as `Ranged` units attempting `Produce`, attacks with no enemy at the local target, and Barracks attempting to produce `Worker`.

## Honest Conclusion

The Day 5 run does confirm one important point: one side was genuinely student-controlled per step through the intended Unity observation -> student inference bridge -> transfer-compatible decode -> ActionApplier -> MatchManager path. This is no longer a one-shot Day 4 smoke wiring check.

However, the transferred control path is not yet behaviorally sane. The student policy is producing many non-NoOp commands, but almost all of them are invalid at the ActionApplier boundary. That pattern is too strong to call mere weak play. The most suspicious symptoms are owner-mismatched actor selections and action-type semantics that contradict the current Unity-side masks and unit capabilities.

Current Day 5 reading:

- Confirmed: per-step student control is active.
- Confirmed: canonical downstream decode/apply path is being exercised.
- Not confirmed: branch semantics are aligned closely enough for meaningful runtime behavior.
- Most likely remaining issue class: decoder / branch semantics / actor-selection alignment, not just weak policy quality.
