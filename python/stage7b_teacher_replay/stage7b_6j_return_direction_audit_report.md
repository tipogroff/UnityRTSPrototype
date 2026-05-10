# Stage7B-6J Return Direction Mismatch Audit Report

- status: GO
- generated_at_utc: 2026-05-10T18:16:11Z
- source: python/week5_teacher_legacy032/teacher_replay_exports/stage7b_replay_ready_stage7b6j_return_direction_audit_e8_s512_20260510T174822Z

## General Metrics

- episodes_scanned: 8
- episodes_replay_attempted: 8
- steps_total: 4096
- steps_replay_attempted: 4096
- teacher_commands_total: 2952
- teacher_nonnoop_commands_total: 2952
- no_teacher_command_steps: 2383
- state_sync_success_count: 4096
- state_sync_failed_count: 0
- candidate_count_min: 10
- candidate_count_mean: 36.13989
- candidate_count_max: 70
- candidate_match_count: 2334
- candidate_drop_count: 1101
- candidate_match_rate: 0.79065
- nonnoop_candidate_match_rate: 0.79065
- runtime_apply_attempted_count: 2334
- runtime_apply_accepted_count: 2334
- runtime_apply_rejected_count: 0
- runtime_apply_accept_rate: 1
- total_mismatches: 618
- no_matching_candidate_count: 618
- direction_mismatch_count: 447
- post_state_match_count: 1230
- post_state_mismatch_count: 483
- terminal_match_count: 1713
- terminal_mismatch_count: 0
- demo_recording_ready: true

## Return Direction Audit

- return_commands_total: 134
- return_commands_matched: 72
- return_commands_dropped: 62
- return_match_rate: 0.537314
- return_direction_mismatch_count: 62
- return_direction_mismatch_rate: 0.462687
- opposite_direction_count: 62
- y_axis_flip_suspected_count: 62
- x_axis_flip_suspected_count: 0
- teacher_target_outside_map_count: 0
- unity_target_outside_map_count: 0
- target_cell_has_base_teacher_side_count: 0
- target_cell_has_base_unity_side_count: 62
- pattern_hypothesis: y_axis_flip_systematic (all Return mismatches are North<->South)

### Mismatch by Action Type

- return: 62
- move: 222
- harvest: 51
- produce: 283

### Mismatch by Teacher Direction

- South: 356
- North: 116
- East: 116
- West: 30

### Return Mismatch by Teacher Direction

- South: 62

### Return Mismatch by Candidate Direction

- North: 62

## GO / HOLD Decision

**Decision: HOLD_FOR_STAGE7B_6K_FIX: return_direction_mismatch_rate=0.4627 exceeds 10% threshold. Pattern hypothesis: y_axis_flip_systematic (all Return mismatches are North<->South). Direction mapping fix required before large demo recording.**

## First Return Direction Mismatches (up to 10)

### Mismatch 1: episode=0 step=30
- actor: (2,1) flat=26
- teacher_dir: South | candidate_dir: North
- is_opposite: True | is_y_axis_flip: True | is_x_axis_flip: False
- nearest_candidate_reason: direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- teacher_target: (2,0) inside=True has_base=False
- unity_target: (2,2) inside=True has_base=True
- inversion_suggested: y=True x=False
- base_resource_nearby_summary: actor_adj_friendly_base=1,actor_adj_resource=0,teacher_target_adj_friendly_base=0,unity_target_adj_friendly_base=0

### Mismatch 2: episode=0 step=80
- actor: (2,1) flat=26
- teacher_dir: South | candidate_dir: North
- is_opposite: True | is_y_axis_flip: True | is_x_axis_flip: False
- nearest_candidate_reason: direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- teacher_target: (2,0) inside=True has_base=False
- unity_target: (2,2) inside=True has_base=True
- inversion_suggested: y=True x=False
- base_resource_nearby_summary: actor_adj_friendly_base=1,actor_adj_resource=0,teacher_target_adj_friendly_base=0,unity_target_adj_friendly_base=0

### Mismatch 3: episode=0 step=130
- actor: (2,1) flat=26
- teacher_dir: South | candidate_dir: North
- is_opposite: True | is_y_axis_flip: True | is_x_axis_flip: False
- nearest_candidate_reason: direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- teacher_target: (2,0) inside=True has_base=False
- unity_target: (2,2) inside=True has_base=True
- inversion_suggested: y=True x=False
- base_resource_nearby_summary: actor_adj_friendly_base=1,actor_adj_resource=0,teacher_target_adj_friendly_base=0,unity_target_adj_friendly_base=0

### Mismatch 4: episode=0 step=221
- actor: (2,1) flat=26
- teacher_dir: South | candidate_dir: North
- is_opposite: True | is_y_axis_flip: True | is_x_axis_flip: False
- nearest_candidate_reason: direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- teacher_target: (2,0) inside=True has_base=False
- unity_target: (2,2) inside=True has_base=True
- inversion_suggested: y=True x=False
- base_resource_nearby_summary: actor_adj_friendly_base=1,actor_adj_resource=0,teacher_target_adj_friendly_base=0,unity_target_adj_friendly_base=0

### Mismatch 5: episode=0 step=271
- actor: (2,1) flat=26
- teacher_dir: South | candidate_dir: North
- is_opposite: True | is_y_axis_flip: True | is_x_axis_flip: False
- nearest_candidate_reason: direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- teacher_target: (2,0) inside=True has_base=False
- unity_target: (2,2) inside=True has_base=True
- inversion_suggested: y=True x=False
- base_resource_nearby_summary: actor_adj_friendly_base=1,actor_adj_resource=0,teacher_target_adj_friendly_base=0,unity_target_adj_friendly_base=0

### Mismatch 6: episode=0 step=321
- actor: (2,1) flat=26
- teacher_dir: South | candidate_dir: North
- is_opposite: True | is_y_axis_flip: True | is_x_axis_flip: False
- nearest_candidate_reason: direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- teacher_target: (2,0) inside=True has_base=False
- unity_target: (2,2) inside=True has_base=True
- inversion_suggested: y=True x=False
- base_resource_nearby_summary: actor_adj_friendly_base=1,actor_adj_resource=0,teacher_target_adj_friendly_base=0,unity_target_adj_friendly_base=0

### Mismatch 7: episode=0 step=431
- actor: (2,1) flat=26
- teacher_dir: South | candidate_dir: North
- is_opposite: True | is_y_axis_flip: True | is_x_axis_flip: False
- nearest_candidate_reason: direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- teacher_target: (2,0) inside=True has_base=False
- unity_target: (2,2) inside=True has_base=True
- inversion_suggested: y=True x=False
- base_resource_nearby_summary: actor_adj_friendly_base=1,actor_adj_resource=0,teacher_target_adj_friendly_base=0,unity_target_adj_friendly_base=0

### Mismatch 8: episode=1 step=30
- actor: (2,1) flat=26
- teacher_dir: South | candidate_dir: North
- is_opposite: True | is_y_axis_flip: True | is_x_axis_flip: False
- nearest_candidate_reason: direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- teacher_target: (2,0) inside=True has_base=False
- unity_target: (2,2) inside=True has_base=True
- inversion_suggested: y=True x=False
- base_resource_nearby_summary: actor_adj_friendly_base=1,actor_adj_resource=0,teacher_target_adj_friendly_base=0,unity_target_adj_friendly_base=0

### Mismatch 9: episode=1 step=80
- actor: (2,1) flat=26
- teacher_dir: South | candidate_dir: North
- is_opposite: True | is_y_axis_flip: True | is_x_axis_flip: False
- nearest_candidate_reason: direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- teacher_target: (2,0) inside=True has_base=False
- unity_target: (2,2) inside=True has_base=True
- inversion_suggested: y=True x=False
- base_resource_nearby_summary: actor_adj_friendly_base=1,actor_adj_resource=0,teacher_target_adj_friendly_base=0,unity_target_adj_friendly_base=0

### Mismatch 10: episode=1 step=130
- actor: (2,1) flat=26
- teacher_dir: South | candidate_dir: North
- is_opposite: True | is_y_axis_flip: True | is_x_axis_flip: False
- nearest_candidate_reason: direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- teacher_target: (2,0) inside=True has_base=False
- unity_target: (2,2) inside=True has_base=True
- inversion_suggested: y=True x=False
- base_resource_nearby_summary: actor_adj_friendly_base=1,actor_adj_resource=0,teacher_target_adj_friendly_base=0,unity_target_adj_friendly_base=0

## first_10_return_mismatches

- ep=0,step=30,actor=(2,1),teacher_dir=South,candidate_dir=North,nearest=direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- ep=0,step=80,actor=(2,1),teacher_dir=South,candidate_dir=North,nearest=direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- ep=0,step=130,actor=(2,1),teacher_dir=South,candidate_dir=North,nearest=direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- ep=0,step=221,actor=(2,1),teacher_dir=South,candidate_dir=North,nearest=direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- ep=0,step=271,actor=(2,1),teacher_dir=South,candidate_dir=North,nearest=direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- ep=0,step=321,actor=(2,1),teacher_dir=South,candidate_dir=North,nearest=direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- ep=0,step=431,actor=(2,1),teacher_dir=South,candidate_dir=North,nearest=direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- ep=1,step=30,actor=(2,1),teacher_dir=South,candidate_dir=North,nearest=direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- ep=1,step=80,actor=(2,1),teacher_dir=South,candidate_dir=North,nearest=direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- ep=1,step=130,actor=(2,1),teacher_dir=South,candidate_dir=North,nearest=direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
## Drop Reasons

- post_state_desync: 483
- no_matching_candidate: 618

## Notes

- Stage7B-6J: Return direction mismatch audit. Runtime apply enabled.
- ML-Agents training/PPO/imitation/.demo were not started by this runner.
- post_state_comparison_mode=partial: unit count, resource node count, player resources, terminal checked.
- no_teacher_command_steps classified separately, not counted in candidateDropCount.
- Stage6B3 baseline/checkpoint assets were not modified by this runner.
