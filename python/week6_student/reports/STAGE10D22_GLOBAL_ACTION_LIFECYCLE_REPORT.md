# STAGE10D22 Global Action Lifecycle Diagnostic Report

- Generated (UTC): 2026-05-04T02:21:46.678617+00:00
- Source run manifest: (auto-discovered)
- GO/NO-GO verdict: NO-GO

## Per-Action Lifecycle Table
| Action | Raw | MaskAllowed | PostMask | Decoded | ApplierAccepted | RuntimeApplied | StateDelta |
|---|---:|---:|---:|---:|---:|---:|---:|
| NoOp | 283 | 270 | 402 | 402 | 0 | 0 | 0 |
| Move | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Harvest | 92 | 92 | 92 | 92 | 0 | 0 | 0 |
| Return | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Produce | 23 | 23 | 23 | 23 | 14 | 14 | 0 |
| Attack | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## First Failing Boundaries
- Move: raw_selected
- Attack: raw_selected
- Harvest/Return: applier_accepted
- Produce: applier_accepted

## Produce Comparison
- Produce decoded_count: 23
- Produce runtime_applied_count: 14
- Produce state_delta_count: 0

## Success Criterion Evidence
- Clean Move lifecycle examples found: 0

## Artifact Paths
- Trace JSONL: python/week6_student/reports/stage10d22_global_action_lifecycle_trace.jsonl
- Summary JSON: python/week6_student/reports/stage10d22_global_action_lifecycle_summary.json
- Markdown report: python/week6_student/reports/STAGE10D22_GLOBAL_ACTION_LIFECYCLE_REPORT.md
