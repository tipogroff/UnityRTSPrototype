# STAGE10D21B6 Post-Enrichment Move Starvation Report

Generated (UTC): 2026-05-04T00:25:30.916106+00:00

## Result
- Stage10D21B7 Gate: **GO**
- Stage10D21C Gate: **NO-GO**
- Stage10D21C Rationale: Post-enrichment runtime still has zero selected Move after mask and no clean move completion path.

## Coverage
- Actor evaluations classified: 335
- Exactly-one-category classification: True

## Metrics
- Runtime raw Move predictions: 12
- Runtime masked Move predictions: 12
- Runtime selected Move after mask: 0
- Safe move opportunities: 88
- Safe move but non-move selected: 88
- Selected move decoder rejected: 0
- Selected move submitted: 0
- Safe move starvation rate: 1.0000

## Classification Counts
- action_type_move_masked_out: 247
- raw_move_suppressed_by_move_dir_mask: 11
- safe_move_available_but_non_move_selected: 77

## Final Questions
- Q1 move candidates exist post-enrichment: True
- Q2 selected Move is zero post-enrichment: True
- Q3 safe-move opportunities present: True
- Q4 non-move chosen despite safe move: True
- Q5 move decoder rejections present: False
- Q6 move submission present: False
- Q7 dynamic dir mask contributes: True
- Q8 Stage10D21B7 gate: GO
- Q9 Stage10D21C gate: NO-GO
