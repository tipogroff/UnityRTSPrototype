# STAGE10D12 Runtime Channel and Context Fix Candidate Audit Report

Generated at UTC: 2026-05-03T13:02:12Z

## Section 1 - Inputs and raw observation availability
- Loaded inputs:
  - C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d10_global_runtime_cell_table_step0001.jsonl
  - C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d10_global_runtime_logits_snapshot_step0001.json
  - C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d10_global_runtime_summary.json
  - C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json
  - C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d11_runtime_focus_cell_channel_audit.json
  - C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d11_bc_positive_sample_channel_stats.json
  - C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d11_runtime_vs_bc_channel_delta.json
  - C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d11_full_map_context_comparison.json
  - C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d11_student_confidence_comparison.json
  - C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d11_counterfactual_probe_results.json
  - C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/bc_ready/legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z
  - C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/runs/legacy032_v2_semantic_bc_stage10d8_20260503T093718Z/student_bc_semantic_best.pt
- Raw availability classification: FOCUS_ONLY_RAW_AVAILABLE
- strict_probes=False
- probes_mode=preliminary (based_on_reconstructed_fullmap)
- Recommendation: GO_FOR_STAGE10D12R_FULL_RAW_OBSERVATION_CAPTURE

## Section 2 - B2 worker channel group isolation
- Baseline B2: predicted=NoOp, p_noop=0.982008, p_harvest=0.004535, p_produce=0.003566
- Worker reference: split=train, sample_index=0, flat=25, dist_l2=2.449490
- Group patch results:
  - scalars_only: pred=NoOp, p_noop=0.977692, p_harvest=0.005865, harvest_top1=False
  - owner_only: pred=NoOp, p_noop=0.982008, p_harvest=0.004535, harvest_top1=False
  - unit_type_only: pred=NoOp, p_noop=0.982008, p_harvest=0.004535, harvest_top1=False
  - current_action_only: pred=NoOp, p_noop=0.382317, p_harvest=0.220738, harvest_top1=False
  - direction_only: pred=NoOp, p_noop=0.863984, p_harvest=0.041661, harvest_top1=False
  - produce_type_only: pred=NoOp, p_noop=0.982008, p_harvest=0.004535, harvest_top1=False
  - current_action_plus_direction: pred=Harvest, p_noop=0.000802, p_harvest=0.544390, harvest_top1=True
  - scalars_plus_current_action_plus_direction: pred=Harvest, p_noop=0.000133, p_harvest=0.618501, harvest_top1=True
  - owner_plus_unit_type: pred=NoOp, p_noop=0.982008, p_harvest=0.004535, harvest_top1=False
  - owner_plus_unit_type_plus_current_action: pred=NoOp, p_noop=0.382317, p_harvest=0.220738, harvest_top1=False
  - owner_plus_unit_type_plus_direction: pred=NoOp, p_noop=0.863984, p_harvest=0.041661, harvest_top1=False
  - owner_plus_unit_type_plus_current_action_plus_direction: pred=Harvest, p_noop=0.000802, p_harvest=0.544390, harvest_top1=True
- Reverse ablation results:
  - scalars_only: pred=Harvest, p_noop=0.000000, p_harvest=0.994695, harvest_destroyed=False
  - owner_only: pred=Harvest, p_noop=0.000000, p_harvest=0.998567, harvest_destroyed=False
  - unit_type_only: pred=Harvest, p_noop=0.000000, p_harvest=0.998567, harvest_destroyed=False
  - current_action_only: pred=Harvest, p_noop=0.000000, p_harvest=0.983412, harvest_destroyed=False
  - direction_only: pred=Harvest, p_noop=0.000000, p_harvest=0.989865, harvest_destroyed=False
  - produce_type_only: pred=Harvest, p_noop=0.000000, p_harvest=0.998567, harvest_destroyed=False
  - current_action_plus_direction: pred=Harvest, p_noop=0.000000, p_harvest=0.857416, harvest_destroyed=False
  - scalars_plus_current_action_plus_direction: pred=Harvest, p_noop=0.020756, p_harvest=0.635399, harvest_destroyed=False
  - owner_plus_unit_type: pred=Harvest, p_noop=0.000000, p_harvest=0.998567, harvest_destroyed=False
  - owner_plus_unit_type_plus_current_action: pred=Harvest, p_noop=0.000000, p_harvest=0.983412, harvest_destroyed=False
  - owner_plus_unit_type_plus_direction: pred=Harvest, p_noop=0.000000, p_harvest=0.989865, harvest_destroyed=False
  - owner_plus_unit_type_plus_current_action_plus_direction: pred=Harvest, p_noop=0.000000, p_harvest=0.857416, harvest_destroyed=False
- Minimal group classification: B2_INCONCLUSIVE

## Section 3 - B2 per-channel isolation
- Top channels by combined impact:
  - ch14 action_harvest: score=0.110582
  - ch21 dir_west: score=0.105816
  - ch12 action_noop: score=0.079228
  - ch1 resources: score=0.011472
  - ch20 dir_south: score=0.002190
  - ch13 action_move: score=0.000000
  - ch15 action_return: score=0.000000
  - ch16 action_produce: score=0.000000
- Minimal channel set candidate: [14, 21, 12]

## Section 4 - C3 base local context decomposition
- Baseline C3: predicted=NoOp, p_noop=0.996549, p_produce=0.000756
- Radius probes:
  - cell_only: pred=NoOp, p_noop=0.983484, p_produce=0.004401, produce_top1=False
  - patch_3x3: pred=Produce, p_noop=0.000000, p_produce=0.910148, produce_top1=True
  - patch_5x5: pred=Produce, p_noop=0.000000, p_produce=0.993449, produce_top1=True
  - patch_7x7: pred=Produce, p_noop=0.000000, p_produce=0.992678, produce_top1=True
- Minimal radius restoring Produce: 1
- 5x5 semantic group decomposition:
  - owner_only_all_cells_5x5: pred=NoOp, p_noop=0.996549, p_produce=0.000756, produce_top1=False
  - unit_type_only_all_cells_5x5: pred=NoOp, p_noop=0.996385, p_produce=0.000794, produce_top1=False
  - current_action_only_all_cells_5x5: pred=NoOp, p_noop=0.960940, p_produce=0.013427, produce_top1=False
  - direction_only_all_cells_5x5: pred=NoOp, p_noop=0.995321, p_produce=0.001110, produce_top1=False
  - scalar_only_all_cells_5x5: pred=NoOp, p_noop=0.979493, p_produce=0.006015, produce_top1=False
  - owner_plus_unit_type: pred=NoOp, p_noop=0.996385, p_produce=0.000794, produce_top1=False
  - owner_plus_unit_type_plus_current_action: pred=NoOp, p_noop=0.927044, p_produce=0.027328, produce_top1=False
  - owner_plus_unit_type_plus_current_action_plus_direction: pred=Produce, p_noop=0.180392, p_produce=0.473623, produce_top1=True
  - all_non_scalar_onehot_groups: pred=Produce, p_noop=0.001199, p_produce=0.732922, produce_top1=True
  - all_groups_except_center_c3: pred=Produce, p_noop=0.000012, p_produce=0.863191, produce_top1=True
  - only_neighbor_cells_excluding_center: pred=Produce, p_noop=0.000012, p_produce=0.863191, produce_top1=True
  - only_center_c3: pred=NoOp, p_noop=0.983484, p_produce=0.004401, produce_top1=False
- C3 classification: C3_CENTER_CELL_NOT_SUFFICIENT

## Section 5 - C3 neighbor importance
- Most important neighbor cells by delta p_produce:
  - xy=[1, 1]: delta_p_produce=0.003139, delta_p_noop=-0.009036, pred=NoOp
  - xy=[2, 1]: delta_p_produce=0.000174, delta_p_noop=-0.000741, pred=NoOp
  - xy=[1, 2]: delta_p_produce=0.000117, delta_p_noop=-0.000479, pred=NoOp
  - xy=[0, 1]: delta_p_produce=0.000095, delta_p_noop=-0.000378, pred=NoOp
  - xy=[4, 2]: delta_p_produce=0.000082, delta_p_noop=-0.000350, pred=NoOp
  - xy=[4, 1]: delta_p_produce=0.000070, delta_p_noop=-0.000271, pred=NoOp
  - xy=[2, 3]: delta_p_produce=0.000067, delta_p_noop=-0.000273, pred=NoOp
  - xy=[1, 0]: delta_p_produce=0.000065, delta_p_noop=-0.000297, pred=NoOp
- Combination probes:
  - top_1_neighbor: patched=1, pred=NoOp, p_produce=0.003895, produce_top1=False
  - top_2_neighbors: patched=2, pred=NoOp, p_produce=0.018839, produce_top1=False
  - top_3_neighbors: patched=3, pred=NoOp, p_produce=0.035845, produce_top1=False
  - same_row_as_c3: patched=4, pred=NoOp, p_produce=0.001295, produce_top1=False
  - same_column_as_c3: patched=4, pred=NoOp, p_produce=0.001078, produce_top1=False
  - resource_cells_only: patched=2, pred=NoOp, p_produce=0.000824, produce_top1=False
  - worker_cells_only: patched=1, pred=NoOp, p_produce=0.003895, produce_top1=False
  - empty_free_cells_only: patched=21, pred=NoOp, p_produce=0.001415, produce_top1=False
  - friendly_cells_only: patched=1, pred=NoOp, p_produce=0.003895, produce_top1=False
  - enemy_cells_only: patched=0, pred=NoOp, p_produce=0.000756, produce_top1=False
  - neutral_or_resource_cells_only: patched=23, pred=NoOp, p_produce=0.002330, produce_top1=False
- small_subset_sufficient=False, produce_requires_full_5x5_context=True

## Section 6 - Scene distribution check
- Runtime scene summary: {'friendly_actor_count': 2, 'enemy_actor_count': 3, 'workers_count': 2, 'bases_count': 2, 'barracks_count': 1, 'resources_count': 4, 'empty_cells_count': 567, 'distance_worker_to_resource_min': 1.0, 'distance_worker_to_base_min': 1.4142135381698608, 'base_surrounding_free_cells_mean': 7.0, 'base_adjacent_resources_mean': 0.0, 'base_adjacent_workers_mean': 1.0, 'enemy_presence_around_b2_patch5': 0, 'enemy_presence_around_c3_patch5': 0}
- BC worker reference scene summary: {'friendly_actor_count': 2, 'enemy_actor_count': 14, 'workers_count': 14, 'bases_count': 2, 'barracks_count': 0, 'resources_count': 4, 'empty_cells_count': 556, 'distance_worker_to_resource_min': 1.0, 'distance_worker_to_base_min': 1.4142135381698608, 'base_surrounding_free_cells_mean': 7.0, 'base_adjacent_resources_mean': 0.0, 'base_adjacent_workers_mean': 1.0, 'enemy_presence_around_b2_patch5': 0, 'enemy_presence_around_c3_patch5': 0}
- BC base reference scene summary: {'friendly_actor_count': 2, 'enemy_actor_count': 4, 'workers_count': 3, 'bases_count': 2, 'barracks_count': 1, 'resources_count': 4, 'empty_cells_count': 566, 'distance_worker_to_resource_min': 1.0, 'distance_worker_to_base_min': 1.4142135381698608, 'base_surrounding_free_cells_mean': 7.0, 'base_adjacent_resources_mean': 0.0, 'base_adjacent_workers_mean': 1.0, 'enemy_presence_around_b2_patch5': 0, 'enemy_presence_around_c3_patch5': 0}
- runtime_vs_worker_delta: {'friendly_actor_count': 0.0, 'enemy_actor_count': 11.0, 'workers_count': 12.0, 'bases_count': 0.0, 'barracks_count': 1.0, 'resources_count': 0.0, 'empty_cells_count': 11.0, 'enemy_presence_around_c3_patch5': 0.0, 'enemy_presence_around_b2_patch5': 0.0, 'distance_worker_to_resource_min': 0.0, 'distance_worker_to_base_min': 0.0, 'base_surrounding_free_cells_mean': 0.0, 'base_adjacent_resources_mean': 0.0, 'base_adjacent_workers_mean': 0.0}
- runtime_vs_base_delta: {'friendly_actor_count': 0.0, 'enemy_actor_count': 1.0, 'workers_count': 1.0, 'bases_count': 0.0, 'barracks_count': 0.0, 'resources_count': 0.0, 'empty_cells_count': 1.0, 'enemy_presence_around_c3_patch5': 0.0, 'enemy_presence_around_b2_patch5': 0.0, 'distance_worker_to_resource_min': 0.0, 'distance_worker_to_base_min': 0.0, 'base_surrounding_free_cells_mean': 0.0, 'base_adjacent_resources_mean': 0.0, 'base_adjacent_workers_mean': 0.0}
- scene_delta_score=38.000000, scene_ood_likely=True

## Section 7 - Candidate fix decision matrix
- Candidate_A_Unity_observation_channel_semantic_remap_fix
  - evidence_for: ['B2 classification=B2_INCONCLUSIVE', 'No strong B2 semantic evidence']
  - evidence_against: ['Full raw 576 observation not available', 'C3 issue appears context-driven']
  - risk: medium
  - expected_effort: medium
  - recommendation: not recommended
- Candidate_B_Unity_full_raw_observation_extraction_fix_first
  - evidence_for: ['raw availability classification=FOCUS_ONLY_RAW_AVAILABLE', 'Current probes rely on reconstructed full-map for non-focus cells']
  - evidence_against: ['Would delay runtime fix implementation']
  - risk: low
  - expected_effort: low
  - recommendation: recommended
- Candidate_C_Unity_scene_distribution_alignment
  - evidence_for: ['scene_delta_score=38.000', 'C3 classification=C3_CENTER_CELL_NOT_SUFFICIENT']
  - evidence_against: ['No strong contradictory signal']
  - risk: medium
  - expected_effort: medium
  - recommendation: not recommended
- Candidate_D_Targeted_BC_augmentation_with_Unity_like_states
  - evidence_for: ['Relevant when observations are valid but state distribution differs', 'scene_ood_likely=True']
  - evidence_against: ['Not first action when channel semantics are unresolved', 'Not first action while full raw is unavailable']
  - risk: medium
  - expected_effort: high
  - recommendation: not recommended
- Candidate_E_Student_objective_reweighting
  - evidence_for: ['Use only after data+observation validity confirmed']
  - evidence_against: ['Current stage still indicates observation/context mismatch candidates', 'Offline BC confidence already high on positive samples']
  - risk: high
  - expected_effort: high
  - recommendation: not recommended
- Candidate_F_Inconclusive_deeper_probes
  - evidence_for: ['Use when signals conflict', 'Selected if no decisive candidate is recommended']
  - evidence_against: ['Can extend timeline']
  - risk: low
  - expected_effort: medium
  - recommendation: not recommended

## Section 8 - Evidence-based classification
- FULL_RAW_OBSERVATION_CAPTURE_REQUIRED
- C3_NEIGHBOR_CONTEXT_REQUIRED
- UNITY_SCENE_DISTRIBUTION_MISMATCH_CONFIRMED
- TARGETED_BC_AUGMENTATION_LIKELY_REQUIRED

## Section 9 - Primary next gate
- GO_FOR_STAGE10D12R_FULL_RAW_OBSERVATION_CAPTURE
- Why: full raw 576 observation tensor is unavailable; non-focus context probes are preliminary and based on reconstructed full-map.
