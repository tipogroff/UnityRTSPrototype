# Stage7B-7A Move / Harvest / Produce Mismatch Audit

- status: GO
- decision: HOLD_FOR_STAGE7B_7B_MAPPING_FIX
- generated_at_utc: 2026-05-10T20:10:34Z
- source: python/week5_teacher_legacy032/teacher_replay_exports/stage7b_replay_ready_stage7b6j_return_direction_audit_e8_s512_20260510T174822Z

## General Metrics

- episodes_scanned: 8
- steps_total: 4096
- teacher_commands_total: 2952
- candidate_match_count: 2396
- candidate_drop_count: 556
- candidate_match_rate: 0.811653
- runtime_apply_attempted_count: 2396
- runtime_apply_accepted_count: 2396
- runtime_apply_rejected_count: 0
- runtime_apply_accept_rate: 1
- state_sync_success_count: 4096
- state_sync_failed_count: 0

## Move

- move_commands_total: 2027
- move_commands_matched: 1805
- move_commands_dropped: 222
- move_match_rate: 0.890479
- move_direction_mismatch_count: 222
- move_direction_mismatch_rate: 0.109522
- y_axis_flip_count: 202
- x_axis_flip_count: 0
- mapping_like_candidate_target_count: 202
- legality_or_state_divergence_count: 222
- mismatch_by_teacher_dir: {South: 157, North: 65}
- mismatch_by_candidate_dir: {North: 157, East: 20, South: 45}
- first_10:
  - ep=0,step=130,cmd=0,actor=(1,0),teacher_dir=South,candidate_dir=North,teacher_target=(1,-1),unity_target=(1,1),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(1, 0), type=Move, teacher_dir=South, cand_dir=North)
  - ep=0,step=150,cmd=0,actor=(3,1),teacher_dir=North,candidate_dir=East,teacher_target=(3,2),unity_target=(4,1),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(3, 1), type=Move, teacher_dir=North, cand_dir=East)
  - ep=0,step=170,cmd=1,actor=(0,3),teacher_dir=South,candidate_dir=North,teacher_target=(0,2),unity_target=(0,4),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(0, 3), type=Move, teacher_dir=South, cand_dir=North)
  - ep=0,step=191,cmd=0,actor=(0,3),teacher_dir=South,candidate_dir=North,teacher_target=(0,2),unity_target=(0,4),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(0, 3), type=Move, teacher_dir=South, cand_dir=North)
  - ep=0,step=201,cmd=0,actor=(1,0),teacher_dir=South,candidate_dir=North,teacher_target=(1,-1),unity_target=(1,1),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(1, 0), type=Move, teacher_dir=South, cand_dir=North)
  - ep=0,step=213,cmd=1,actor=(1,3),teacher_dir=South,candidate_dir=North,teacher_target=(1,2),unity_target=(1,4),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(1, 3), type=Move, teacher_dir=South, cand_dir=North)
  - ep=0,step=220,cmd=1,actor=(0,3),teacher_dir=South,candidate_dir=North,teacher_target=(0,2),unity_target=(0,4),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(0, 3), type=Move, teacher_dir=South, cand_dir=North)
  - ep=0,step=270,cmd=1,actor=(0,3),teacher_dir=South,candidate_dir=North,teacher_target=(0,2),unity_target=(0,4),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(0, 3), type=Move, teacher_dir=South, cand_dir=North)
  - ep=0,step=311,cmd=2,actor=(2,3),teacher_dir=South,candidate_dir=North,teacher_target=(2,2),unity_target=(2,4),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(2, 3), type=Move, teacher_dir=South, cand_dir=North)
  - ep=0,step=321,cmd=0,actor=(1,0),teacher_dir=South,candidate_dir=North,teacher_target=(1,-1),unity_target=(1,1),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(1, 0), type=Move, teacher_dir=South, cand_dir=North)

## Harvest

- harvest_commands_total: 154
- harvest_commands_matched: 103
- harvest_commands_dropped: 51
- harvest_match_rate: 0.668831
- harvest_direction_mismatch_count: 51
- harvest_direction_mismatch_rate: 0.331169
- y_axis_flip_count: 51
- x_axis_flip_count: 0
- mapping_like_candidate_target_count: 51
- legality_or_state_divergence_count: 51
- mismatch_by_teacher_dir: {North: 51}
- mismatch_by_candidate_dir: {South: 51}
- first_10:
  - ep=0,step=130,cmd=2,actor=(0,2),teacher_dir=North,candidate_dir=South,teacher_target=(0,3),unity_target=(0,1),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(0, 2), type=Harvest, teacher_dir=North, cand_dir=South)
  - ep=0,step=170,cmd=0,actor=(0,2),teacher_dir=North,candidate_dir=South,teacher_target=(0,3),unity_target=(0,1),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(0, 2), type=Harvest, teacher_dir=North, cand_dir=South)
  - ep=0,step=220,cmd=0,actor=(0,2),teacher_dir=North,candidate_dir=South,teacher_target=(0,3),unity_target=(0,1),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(0, 2), type=Harvest, teacher_dir=North, cand_dir=South)
  - ep=0,step=270,cmd=0,actor=(0,2),teacher_dir=North,candidate_dir=South,teacher_target=(0,3),unity_target=(0,1),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(0, 2), type=Harvest, teacher_dir=North, cand_dir=South)
  - ep=0,step=320,cmd=0,actor=(0,2),teacher_dir=North,candidate_dir=South,teacher_target=(0,3),unity_target=(0,1),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(0, 2), type=Harvest, teacher_dir=North, cand_dir=South)
  - ep=0,step=361,cmd=1,actor=(0,2),teacher_dir=North,candidate_dir=South,teacher_target=(0,3),unity_target=(0,1),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(0, 2), type=Harvest, teacher_dir=North, cand_dir=South)
  - ep=0,step=452,cmd=0,actor=(0,2),teacher_dir=North,candidate_dir=South,teacher_target=(0,3),unity_target=(0,1),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(0, 2), type=Harvest, teacher_dir=North, cand_dir=South)
  - ep=1,step=131,cmd=0,actor=(0,2),teacher_dir=North,candidate_dir=South,teacher_target=(0,3),unity_target=(0,1),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(0, 2), type=Harvest, teacher_dir=North, cand_dir=South)
  - ep=1,step=201,cmd=1,actor=(0,2),teacher_dir=North,candidate_dir=South,teacher_target=(0,3),unity_target=(0,1),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(0, 2), type=Harvest, teacher_dir=North, cand_dir=South)
  - ep=1,step=241,cmd=1,actor=(0,2),teacher_dir=North,candidate_dir=South,teacher_target=(0,3),unity_target=(0,1),teacher_expected=False,unity_expected=True,nearest=direction_mismatch (actor=(0, 2), type=Harvest, teacher_dir=North, cand_dir=South)

## Produce

- produce_commands_total: 637
- produce_commands_matched: 354
- produce_commands_dropped: 283
- produce_match_rate: 0.55573
- produce_direction_mismatch_count: 26
- produce_direction_mismatch_rate: 0.040816
- y_axis_flip_count: 31
- x_axis_flip_count: 0
- mapping_like_candidate_target_count: 31
- legality_or_state_divergence_count: 45
- mismatch_by_teacher_dir: {South: 137, East: 116, West: 30}
- mismatch_by_candidate_dir: {North: 31, South: 29, East: 43, none: 171, West: 9}
- first_10:
  - ep=0,step=202,cmd=1,actor=(2,3),teacher_dir=South,candidate_dir=North,teacher_target=(2,2),unity_target=(2,4),teacher_expected=False,unity_expected=True,nearest=produce_direction_mismatch (teacher_dir=South, cand_dir=North)
  - ep=0,step=351,cmd=3,actor=(3,11),teacher_dir=South,candidate_dir=South,teacher_target=(3,10),unity_target=(3,10),teacher_expected=True,unity_expected=True,nearest=produce_type_mismatch (teacher=Light, cand=Heavy)
  - ep=0,step=358,cmd=0,actor=(3,6),teacher_dir=East,candidate_dir=East,teacher_target=(4,6),unity_target=(4,6),teacher_expected=True,unity_expected=True,nearest=produce_type_mismatch (teacher=Light, cand=Heavy)
  - ep=0,step=359,cmd=0,actor=(3,6),teacher_dir=East,candidate_dir=East,teacher_target=(4,6),unity_target=(4,6),teacher_expected=True,unity_expected=True,nearest=produce_type_mismatch (teacher=Light, cand=Heavy)
  - ep=0,step=401,cmd=4,actor=(0,5),teacher_dir=South,candidate_dir=none,teacher_target=(0,4),unity_target=(-1,-1),teacher_expected=True,unity_expected=False,nearest=action_type_missing_from_candidates (actor=(0, 5), type=Produce)
  - ep=0,step=406,cmd=0,actor=(5,6),teacher_dir=South,candidate_dir=none,teacher_target=(5,5),unity_target=(-1,-1),teacher_expected=True,unity_expected=False,nearest=action_type_missing_from_candidates (actor=(5, 6), type=Produce)
  - ep=0,step=407,cmd=0,actor=(5,6),teacher_dir=South,candidate_dir=none,teacher_target=(5,5),unity_target=(-1,-1),teacher_expected=True,unity_expected=False,nearest=action_type_missing_from_candidates (actor=(5, 6), type=Produce)
  - ep=1,step=302,cmd=2,actor=(2,3),teacher_dir=South,candidate_dir=North,teacher_target=(2,2),unity_target=(2,4),teacher_expected=False,unity_expected=True,nearest=produce_direction_mismatch (teacher_dir=South, cand_dir=North)
  - ep=1,step=338,cmd=2,actor=(5,2),teacher_dir=South,candidate_dir=South,teacher_target=(5,1),unity_target=(5,1),teacher_expected=True,unity_expected=True,nearest=produce_type_mismatch (teacher=Light, cand=Heavy)
  - ep=1,step=339,cmd=0,actor=(5,2),teacher_dir=South,candidate_dir=South,teacher_target=(5,1),unity_target=(5,1),teacher_expected=True,unity_expected=True,nearest=produce_type_mismatch (teacher=Light, cand=Heavy)

- produce_type_mismatch_count: 81

## Direction Pattern Conclusion

- y_axis_flip_count: 284
- y_axis_flip_rate: 0.949833
- x_axis_flip_count: 0
- x_axis_flip_rate: 0
- opposite_direction_count: 284
- conclusion: dominant_y_axis_flip

## Notes

- Audit-only: no ML-Agents training, PPO, imitation learning, or large .demo recording was started.
- Teacher policy, reward, ActionApplier, MatchManager, and MlAgentsCandidateActionBuilder were not modified by this runner.
- Return direction mapping remains the Stage7B-6K return-only fix; Move/Harvest/Produce mapping is only measured.
- M/H/P direction mismatches show a dominant Y-axis pattern; hold before large dataset and run Stage7B-7B mapping fix proposal.
- Stage6B3 baseline/checkpoint assets were not modified by this runner.
