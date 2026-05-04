# STAGE10D21B5 Dynamic Move Mask Report

Generated (UTC): 2026-05-04T00:16:42.169094+00:00

## Result
- Stage10D21C Gate: **NO-GO**
- Reason: No clean accepted/applied/completed Move command present in fresh trace.

## Core Metrics
- Move candidates before enrichment: 12
- Move candidates after enrichment: 12
- Selected masked Move commands before enrichment: 4
- Selected masked Move commands after enrichment: 0
- Selected masked Move reduction: 100.0%
- Target-occupied rejections before: 4
- Target-occupied rejections after: 0

## Required Pattern Outcomes
- 42->43: baseline=1, fresh=0, outcome=suppressed
- 41->42: baseline=1, fresh=0, outcome=suppressed
- 38->39: baseline=1, fresh=0, outcome=suppressed
- 45->46: baseline=1, fresh=0, outcome=suppressed

## Guardrails
- Checkpoint: python/week6_student/runs/legacy032_v2_stage10d19b_valid_move_augmented_bc_20260503T192454Z/student_bc_stage10d19b_valid_move_best.pt
- Stage10D.19C not used: True
- Mask enabled in manifest: True
- Off-actor masked non-noop after: 0
- B2/C3 guard pass: True

## Notes
- Stage10D20S fresh move trace is empty, indicating no selected masked Move commands survived to the selector trace.
- Stage10D21C remains NO-GO because no clean accepted/applied/completed Move lifecycle was observed.
