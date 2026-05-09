# Stage7B Teacher-to-Candidate Conversion Preflight

## Status

- status: partial
- mode: partial_preflight
- source_dataset_path: python\week5_teacher_legacy032\teacher_exports_bc\day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z
- split: debug
- processed_samples_limit: 512

## Contract Detection

- manifest_branch_sizes: [6, 4, 4, 4, 4, 7, 49]
- branch_contract_detected: True
- branch_contract_matches_stage7b: True
- attack_target_size_detected: 49
- attack_target_center_index_detected: 24
- stage7b_attack_target_size: 49
- stage7b_attack_target_center_index: 24
- stage7b_candidate_branch_size: 128

## Metrics

- total_samples: 512
- processed_samples: 512
- matched_samples: 1
- dropped_samples: 511
- match_rate: 0.001953
- nonnoop_total: 511
- nonnoop_matched: 0
- nonnoop_match_rate: 0.000000
- noop_total: 1
- noop_matched_to_candidate0: 1

## Drop Reasons

- multiple_nonnoop_actors: 504
- state_reconstruction_failed: 7

## Reliability

- state_reconstruction_reliable: False
- state_reconstruction_reason: bc_ready observations/actions do not include full authoritative runtime state needed to reconstruct legal Unity ActionMaskBuilder candidate sets with reliability guarantees
- match_rate_scope: partial_preflight_only_no_runtime_state_reconstruction
- demo_recording_ready_for_stage7b_6b: False

## Notes

- No Unity training, no .demo recording, no PPO/imitation started in this preflight.
