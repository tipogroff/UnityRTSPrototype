# Stage7B-7B Move / Harvest / Produce Mismatch Audit

- status: GO
- decision: GO_TO_STAGE7B_8_SMALL_IMITATION_SMOKE
- generated_at_utc: 2026-05-10T20:42:56Z
- source: python/week5_teacher_legacy032/teacher_replay_exports/stage7b_replay_ready_stage7b6j_return_direction_audit_e8_s512_20260510T174822Z
- cardinal_direction_mapping_mode: invert_y_for_legacy032_teacher
- demo_recording_ready_after_7b: true

## Before / After

| Metric | Before 7A | After 7B |
|---|---:|---:|
| overall candidate_match_rate | 0.811653 | 0.91294 |
| candidate_match_count | 2396 | 2695 |
| Move match_rate | 0.890479 | 1 |
| Move direction_mismatch_count | 222 | 0 |
| Harvest match_rate | 0.668831 | 1 |
| Harvest direction_mismatch_count | 51 | 0 |
| Produce match_rate | 0.55573 | 0.596546 |
| Produce direction_mismatch_count | 26 | 0 |
| Return match_rate | n/a | 1 |
| Return direction_mismatch_count | n/a | 0 |
| runtime_apply_accept_rate | 1 | 1 |

## Mapping Diagnostics

- mapping_applied_action_types: {harvest: 154, produce: 637, move: 2027, return: 134}
- move_mapping_applied_count: 2027
- harvest_mapping_applied_count: 154
- return_mapping_applied_count: 134
- produce_mapping_applied_count: 637

## General Metrics

- episodes_scanned: 8
- steps_total: 4096
- teacher_commands_total: 2952
- candidate_match_count: 2695
- candidate_drop_count: 257
- candidate_match_rate: 0.91294
- runtime_apply_attempted_count: 2695
- runtime_apply_accepted_count: 2695
- runtime_apply_rejected_count: 0
- runtime_apply_accept_rate: 1
- state_sync_success_count: 4096
- state_sync_failed_count: 0

## Move

- move_commands_total: 2027
- move_commands_matched: 2027
- move_commands_dropped: 0
- move_match_rate: 1
- move_direction_mismatch_count: 0
- move_direction_mismatch_rate: 0
- y_axis_flip_count: 0
- x_axis_flip_count: 0
- mapping_like_candidate_target_count: 0
- legality_or_state_divergence_count: 0
- mismatch_by_teacher_dir: {}
- mismatch_by_candidate_dir: {}
- first_10:
  - (none)

## Harvest

- harvest_commands_total: 154
- harvest_commands_matched: 154
- harvest_commands_dropped: 0
- harvest_match_rate: 1
- harvest_direction_mismatch_count: 0
- harvest_direction_mismatch_rate: 0
- y_axis_flip_count: 0
- x_axis_flip_count: 0
- mapping_like_candidate_target_count: 0
- legality_or_state_divergence_count: 0
- mismatch_by_teacher_dir: {}
- mismatch_by_candidate_dir: {}
- first_10:
  - (none)

## Produce

- produce_commands_total: 637
- produce_commands_matched: 380
- produce_commands_dropped: 257
- produce_match_rate: 0.596546
- produce_direction_mismatch_count: 0
- produce_direction_mismatch_rate: 0
- y_axis_flip_count: 0
- x_axis_flip_count: 0
- mapping_like_candidate_target_count: 0
- legality_or_state_divergence_count: 0
- mismatch_by_teacher_dir: {North: 111, East: 116, West: 30}
- mismatch_by_candidate_dir: {North: 34, East: 43, none: 171, West: 9}
- first_10:
  - ep=0,step=351,cmd=3,actor=(3,11),teacher_dir=North,candidate_dir=North,teacher_target=(3,12),unity_target=(3,12),teacher_expected=True,unity_expected=True,nearest=produce_type_mismatch (teacher=Light, cand=Heavy)
  - ep=0,step=358,cmd=0,actor=(3,6),teacher_dir=East,candidate_dir=East,teacher_target=(4,6),unity_target=(4,6),teacher_expected=True,unity_expected=True,nearest=produce_type_mismatch (teacher=Light, cand=Heavy)
  - ep=0,step=359,cmd=0,actor=(3,6),teacher_dir=East,candidate_dir=East,teacher_target=(4,6),unity_target=(4,6),teacher_expected=True,unity_expected=True,nearest=produce_type_mismatch (teacher=Light, cand=Heavy)
  - ep=0,step=401,cmd=4,actor=(0,5),teacher_dir=North,candidate_dir=none,teacher_target=(0,6),unity_target=(-1,-1),teacher_expected=True,unity_expected=False,nearest=action_type_missing_from_candidates (actor=(0, 5), type=Produce)
  - ep=0,step=406,cmd=0,actor=(5,6),teacher_dir=North,candidate_dir=none,teacher_target=(5,7),unity_target=(-1,-1),teacher_expected=True,unity_expected=False,nearest=action_type_missing_from_candidates (actor=(5, 6), type=Produce)
  - ep=0,step=407,cmd=0,actor=(5,6),teacher_dir=North,candidate_dir=none,teacher_target=(5,7),unity_target=(-1,-1),teacher_expected=True,unity_expected=False,nearest=action_type_missing_from_candidates (actor=(5, 6), type=Produce)
  - ep=1,step=338,cmd=2,actor=(5,2),teacher_dir=North,candidate_dir=North,teacher_target=(5,3),unity_target=(5,3),teacher_expected=True,unity_expected=True,nearest=produce_type_mismatch (teacher=Light, cand=Heavy)
  - ep=1,step=339,cmd=0,actor=(5,2),teacher_dir=North,candidate_dir=North,teacher_target=(5,3),unity_target=(5,3),teacher_expected=True,unity_expected=True,nearest=produce_type_mismatch (teacher=Light, cand=Heavy)
  - ep=1,step=340,cmd=0,actor=(5,2),teacher_dir=North,candidate_dir=North,teacher_target=(5,3),unity_target=(5,3),teacher_expected=True,unity_expected=True,nearest=produce_type_mismatch (teacher=Light, cand=Heavy)
  - ep=1,step=340,cmd=1,actor=(3,5),teacher_dir=East,candidate_dir=East,teacher_target=(4,5),unity_target=(4,5),teacher_expected=True,unity_expected=True,nearest=produce_type_mismatch (teacher=Light, cand=Heavy)

- produce_type_mismatch_count: 86
- action_type_missing_from_candidates: 171

## Return

- return_commands_total: 134
- return_commands_matched: 134
- return_commands_dropped: 0
- return_match_rate: 1
- return_direction_mismatch_count: 0

## Direction Pattern Conclusion

- y_axis_flip_count: 0
- y_axis_flip_rate: null
- x_axis_flip_count: 0
- x_axis_flip_rate: null
- opposite_direction_count: 0
- conclusion: no_direction_mismatches
- remaining_mismatch_reason_histogram: {produce_type_mismatch: 86, action_type_missing_from_candidates: 171}

## Notes

- Mapping-only validation: no ML-Agents training, PPO, imitation learning, or large .demo recording was started.
- Teacher policy, reward, ActionApplier, MatchManager, and MlAgentsCandidateActionBuilder were not modified by this runner.
- Teacher Replay resolver maps Move/Harvest/Return/Produce cardinal direction branches with legacy032 vertical-axis conversion.
- Stage7B-7B GO criteria met for Stage7B-8 small imitation smoke.
- Stage6B3 baseline/checkpoint assets were not modified by this runner.
