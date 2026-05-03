# Stage10D.20S Masked Selector Fix Report

- Generated (UTC): 2026-05-03T22:12:10.084100+00:00
- Steps analyzed: 76 (last=76)
- Overall pass: PASS

## Key Checks
- all_masked_move_dirs_legal: True
- decoder_received_move_dir_matches_masked: True
- decoder_received_move_dir_legal: True
- off_actor_masked_non_noop_zero: True
- legacy_conflicts_explicit_only: True

## Counts
- masked_move_events: 4
- masked_move_illegal_count: 0
- decoder_move_dir_mismatch_count: 0
- decoder_move_dir_illegal_count: 0
- off_actor_masked_non_noop: 0
- legacy_status_conflicts: 4
- move_accepted_count: 4
- move_with_displacement_count: 0
- move_without_displacement_count: 4
- move_missing_identity_next_step_count: 0

## Artifacts
- JSON report: python/week6_student/reports/stage10d20s_masked_selector_fix_report.json
- JSONL trace: python/week6_student/reports/stage10d20s_mask_move_trace.jsonl
- Unity rerun manifest: python/week6_student/reports/stage10d20s_unity_rerun_manifest.json
