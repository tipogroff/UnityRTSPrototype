# Stage7B-7C Produce Semantics Report

- status: GO
- decision: GO_TO_STAGE7B_7D_RERECORD_CLEAN_DEMO
- generated_at_utc: 2026-05-10T21:07:51Z
- source: python/week5_teacher_legacy032/teacher_replay_exports/stage7b_replay_ready_stage7b6j_return_direction_audit_e8_s512_20260510T174822Z
- fix_applied: diagnostic/classification only; no runtime legality change

## Produce Type Mapping

| raw | legacy032 name | Unity v2 UnitType | current AgentAction label | expected Stage7B mapping |
|---:|---|---|---|---|
| 0 | Resource | Resource | Worker | Resource |
| 1 | Base | Base | Light | Base |
| 2 | Barracks | Barracks | Heavy | Barracks |
| 3 | Worker | Worker | Ranged | Worker |
| 4 | Light | Light | 4 | Light |
| 5 | Heavy | Heavy | 5 | Heavy |
| 6 | Ranged | Ranged | 6 | Ranged |

## Root Causes

- produce_type_mismatch: All 86 old produce_type_mismatch rows are Worker raw=1. In legacy032/v2 raw=1 is Base, but old diagnostics printed it as Light because raw v2 values were formatted through ProducibleUnit. Unity current runtime supports Worker->Barracks only, not Worker->Base.
- action_type_missing_from_candidates: All 171 rows are Worker raw=2 Barracks while the owner already has an alive Barracks. Unity CandidateBuilder masks Worker->Barracks in that state via HasAliveBarracks, matching ActionApplier/MatchManager.

## Before / After

| metric | before | after_7c |
|---|---:|---:|
| candidate_match_rate | 0.912940 | 0.912940 |
| produce_match_rate exact candidate match | 0.596546 | 0.596546 |
| produce_type_mismatch unclassified | 86 | 0 |
| action_type_missing_from_candidates unclassified | 171 | 0 |
| runtime_apply_accept_rate | 1.000000 | 1.000000 |

## Produce Classification

- produce_commands_total: 637
- produce_commands_matched_after_7c_exact_candidate_match: 380
- produce_commands_dropped_after_7c: 257
- produce_commands_classified_after_7c: 257
- produce_unclassified_remaining_after_7c: 0
- classified_reason_histogram: {'runtime_state_semantics_gap': 171, 'unsupported_worker_build_base': 86}

## Regression Checks

- Move match_rate: 1.000000, direction_mismatch=0
- Harvest match_rate: 1.000000, direction_mismatch=0
- Return match_rate: 1.000000, direction_mismatch=0
- state_sync_failed_count_after_7c: 0
- runtime_apply_rejected_count_after_7c: 0
- demo_recording_ready_after_7c: true

## Notes

- Candidate truth remains MlAgentsCandidateActionBuilder; runtime truth remains ActionApplier/MatchManager.
- MlAgentsCandidateActionBuilder is not missing runtime-legal Produce for these rows.
- Unsupported Worker->Base and Unity one-Barracks-cap rows should be dropped before clean demo recording.
