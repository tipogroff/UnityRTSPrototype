# STAGE10T1 Teacher / Export / BC Behavior Truth Audit

Generated: 2026-05-03T12:21:06Z

## Section 1 - Checkpoint identity
- checkpoint: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/agent_final.pt
- training_steps_from_path: 3000000
- checkpoint_mtime_utc: 2026-04-30T22:55:44Z
- wrong_checkpoint_export_risk: False

## Section 2 - Teacher evaluation harness audit
- deterministic_mean_return: -10.0
- stochastic_mean_return: -10.0
- deterministic_noop_share_all_cells: 0.996565
- stochastic_noop_share_all_cells: 0.166238
- explanation: mean_return=-10 can be misleading in this harness because outcomes are logged as draws and terminal win/loss attribution is weak while all-cell noop share dilutes sparse actor actions.

## Section 3 - Teacher actor-cell behavior
- actor_cell_noop_share: 0.000717
- worker_harvest_share: 0.998904
- base_produce_share: 0.998576
- barracks_produce_share: 0.000000
- combat_attack_share: 0.000000
- mean_non_noop_actor_actions_per_step: 1.977088

## Section 4 - Raw export truth
- episodes: 16
- frames: 88165
- behavior_chain_episodes: 0

## Section 5 - Semantic adaptation truth
- frames_preserved: True
- actor_labels_preserved_exact_row_share: 1.000000
- out_of_range_total: 0

## Section 6 - BC-ready dataset truth
- train_actor_cell_noop_share: 0.000752
- val_actor_cell_noop_share: 0.000401
- train_positive_examples: {'Move': 0, 'Harvest': 77904, 'Return': 0, 'Produce': 78871, 'Attack': 88}
- val_positive_examples: {'Move': 0, 'Harvest': 8666, 'Return': 0, 'Produce': 8774, 'Attack': 7}

## Section 7 - Student offline truth
- actor_cell_action_type_accuracy: 0.999599
- actor_cell_non_noop_recall: 1.000000
- worker_harvest_recall: 1.000000
- base_produce_recall: 1.000000
- combat_attack_recall: 0.000000

## Section 8 - Unity runtime mismatch hypothesis
- B2 nearest L2 (27ch): 2.069190502166748
- C3 nearest L2 (27ch): 1.7320507764816284
- B2 local_5x5_l2: 6.578871250152588
- C3 local_5x5_l2: 7.549834251403809

## Section 9 - Classification
- TEACHER_VISUAL_METRICS_MISMATCH
- TEACHER_DETERMINISTIC_COLLAPSE_STOCHASTIC_ACTIVE
- STUDENT_OFFLINE_OK_RUNTIME_OOD

## Section 10 - Recommended next gate
- GO_FOR_STAGE10D11_RUNTIME_VS_BC_OBSERVATION_DISTRIBUTION_AUDIT
