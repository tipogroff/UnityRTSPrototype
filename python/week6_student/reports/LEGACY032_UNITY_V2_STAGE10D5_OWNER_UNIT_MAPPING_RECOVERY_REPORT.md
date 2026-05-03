# LEGACY032 Unity v2 Stage10D.5 Owner/UnitType Mapping Recovery Report

## 1. Scope
- Stage10D.5 recovers owner/unit_type mapping using authoritative or semi-authoritative evidence.
- No retraining, PPO, checkpoint mutation, or ActionApplier/MatchManager changes were performed.

## 2. Stage10D.4 Recap
- Stage10D.4 report: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/LEGACY032_UNITY_V2_STAGE10D4_OBSERVATION_SEMANTIC_REMEDIATION_REPORT.md
- Stage10D.4 ended with critical unavailable owner/unit_type channels and NO_GO gate for retraining.

## 3. Source-code Encoder Audit
- source audit status: pass
- encoder file: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/envs/vec_env.py
- channels 0..26 named explicitly: False
- owner/unit declared at group-level: {'owner_declared_group_level': True, 'unit_type_declared_group_level': True, 'note': 'declared as grouped planes via num_planes, not as explicit Unity target channel IDs'}

## 4. Controlled Raw Observation Probe
- controlled probe status: pass
- env id: MicrortsDefeatCoacAIShaped-v3
- map path: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/microrts/maps/24x24/basesWorkers24x24.xml
- observation shape: [24, 24, 27]
- owner candidate: {'owner_neutral_channel': 10, 'owner_player0_channel': 11, 'owner_player1_channel': 12, 'confidence': 'high', 'full_analysis': {'top_windows': [{'window': [10, 12], 'neutral_argmax_local': 0, 'player0_argmax_local': 1, 'player1_argmax_local': 2, 'distinct_triplet': True, 'separation_margin_sum': 3.0, 'score': 4.0, 'means': {'neutral': [1.0, 0.0, 0.0], 'player0': [0.0, 1.0, 0.0], 'player1': [0.0, 0.0, 1.0]}}, {'window': [19, 21], 'neutral_argmax_local': 2, 'player0_argmax_local': 2, 'player1_argmax_local': 2, 'distinct_triplet': False, 'separation_margin_sum': 3.0, 'score': 3.0, 'means': {'neutral': [0.0, 0.0, 1.0], 'player0': [0.0, 0.0, 1.0], 'player1': [0.0, 0.0, 1.0]}}, {'window': [20, 22], 'neutral_argmax_local': 1, 'player0_argmax_local': 1, 'player1_argmax_local': 1, 'distinct_triplet': False, 'separation_margin_sum': 3.0, 'score': 3.0, 'means': {'neutral': [0.0, 1.0, 0.0], 'player0': [0.0, 1.0, 0.0], 'player1': [0.0, 1.0, 0.0]}}, {'window': [21, 23], 'neutral_argmax_local': 0, 'player0_argmax_local': 0, 'player1_argmax_local': 0, 'distinct_triplet': False, 'separation_margin_sum': 3.0, 'score': 3.0, 'means': {'neutral': [1.0, 0.0, 0.0], 'player0': [1.0, 0.0, 0.0], 'player1': [1.0, 0.0, 0.0]}}, {'window': [0, 2], 'neutral_argmax_local': 1, 'player0_argmax_local': 1, 'player1_argmax_local': 1, 'distinct_triplet': False, 'separation_margin_sum': 2.0, 'score': 2.0, 'means': {'neutral': [0.0, 1.0, 0.0], 'player0': [0.0, 0.5, 0.0], 'player1': [0.0, 0.5, 0.0]}}, {'window': [1, 3], 'neutral_argmax_local': 0, 'player0_argmax_local': 0, 'player1_argmax_local': 0, 'distinct_triplet': False, 'separation_margin_sum': 2.0, 'score': 2.0, 'means': {'neutral': [1.0, 0.0, 0.0], 'player0': [0.5, 0.0, 0.0], 'player1': [0.5, 0.0, 0.0]}}, {'window': [5, 7], 'neutral_argmax_local': 0, 'player0_argmax_local': 0, 'player1_argmax_local': 0, 'distinct_triplet': False, 'separation_margin_sum': 2.0, 'score': 2.0, 'means': {'neutral': [0.0, 0.0, 0.0], 'player0': [1.0, 0.0, 0.0], 'player1': [1.0, 0.0, 0.0]}}, {'window': [11, 13], 'neutral_argmax_local': 0, 'player0_argmax_local': 0, 'player1_argmax_local': 1, 'distinct_triplet': False, 'separation_margin_sum': 2.0, 'score': 2.0, 'means': {'neutral': [0.0, 0.0, 0.0], 'player0': [1.0, 0.0, 0.0], 'player1': [0.0, 1.0, 0.0]}}], 'best': {'window': [10, 12], 'neutral_argmax_local': 0, 'player0_argmax_local': 1, 'player1_argmax_local': 2, 'distinct_triplet': True, 'separation_margin_sum': 3.0, 'score': 4.0, 'means': {'neutral': [1.0, 0.0, 0.0], 'player0': [0.0, 1.0, 0.0], 'player1': [0.0, 0.0, 1.0]}}, 'inferred': {'owner_neutral_channel': 10, 'owner_player0_channel': 11, 'owner_player1_channel': 12, 'confidence': 'high'}}}
- unit_type candidate: {'unit_type_observed_raw_channels': {'Resource': 14, 'Base': 15, 'Worker': 17}, 'confidence': 'high', 'full_analysis': {'top_windows': [{'window': [13, 19], 'score': 3.0, 'observed_type_to_local_index': {'Resource': 1, 'Base': 2, 'Worker': 4}, 'means': {'Resource': [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'Base': [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0], 'Worker': [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0]}}, {'window': [14, 20], 'score': 3.0, 'observed_type_to_local_index': {'Resource': 0, 'Base': 1, 'Worker': 3}, 'means': {'Resource': [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'Base': [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'Worker': [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]}}, {'window': [3, 9], 'score': 2.0, 'observed_type_to_local_index': {'Resource': 6, 'Base': 1, 'Worker': 2}, 'means': {'Resource': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], 'Base': [0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0], 'Worker': [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]}}, {'window': [11, 17], 'score': 2.0, 'observed_type_to_local_index': {'Resource': 3, 'Base': 4, 'Worker': 6}, 'means': {'Resource': [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0], 'Base': [0.5, 0.5, 0.0, 0.0, 1.0, 0.0, 0.0], 'Worker': [0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 1.0]}}, {'window': [12, 18], 'score': 2.0, 'observed_type_to_local_index': {'Resource': 2, 'Base': 3, 'Worker': 5}, 'means': {'Resource': [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0], 'Base': [0.5, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0], 'Worker': [0.5, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]}}, {'window': [18, 24], 'score': 2.0, 'observed_type_to_local_index': {'Resource': 3, 'Base': 3, 'Worker': 3}, 'means': {'Resource': [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0], 'Base': [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0], 'Worker': [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]}}, {'window': [19, 25], 'score': 2.0, 'observed_type_to_local_index': {'Resource': 2, 'Base': 2, 'Worker': 2}, 'means': {'Resource': [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0], 'Base': [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0], 'Worker': [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]}}, {'window': [20, 26], 'score': 2.0, 'observed_type_to_local_index': {'Resource': 1, 'Base': 1, 'Worker': 1}, 'means': {'Resource': [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'Base': [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'Worker': [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]}}], 'best': {'window': [13, 19], 'score': 3.0, 'observed_type_to_local_index': {'Resource': 1, 'Base': 2, 'Worker': 4}, 'means': {'Resource': [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'Base': [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0], 'Worker': [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0]}}, 'inferred': {'unit_type_observed_raw_channels': {'Resource': 14, 'Base': 15, 'Worker': 17}, 'confidence': 'high'}, 'tracked_types': ['Resource', 'Base', 'Barracks', 'Worker', 'Light', 'Heavy', 'Ranged']}}

## 5. Rollout Entity Proxy Cross-check
- rollout crosscheck status: pass
- top owner window: {'window': [10, 12], 'onehot_metrics': {'share_sum_eq_1': 1.0, 'share_sum_eq_0': 0.0, 'share_sum_le_1': 1.0, 'share_sum_gt_1': 0.0}, 'actor_dominant_local': 1, 'actor_margin': 1.0, 'player0_peak_local': 1, 'player1_peak_local': 2, 'player_peaks_distinct': True, 'means': {'actor_cells': [0.0, 1.0, 0.0], 'player0_cells': [0.0, 1.0, 0.0], 'player1_cells': [0.32666015625, 0.0, 0.67333984375]}, 'score': 2.8}
- top unit_type window: {'window': [18, 24], 'onehot_metrics': {'share_sum_eq_1': 0.9991917080349393, 'share_sum_eq_0': 0.0008082919650607639, 'share_sum_le_1': 1.0, 'share_sum_gt_1': 0.0}, 'worker_proxy_peak_local': 3, 'base_proxy_peak_local': 3, 'combat_proxy_peak_local': 0, 'resource_proxy_peak_local': 3, 'worker_proxy_margin': 1.0, 'base_proxy_margin': 1.0, 'resource_proxy_margin': 0.97711181640625, 'means': {'harvest_actor': [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0], 'produce_actor': [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0], 'attack_actor': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'resource_cells': [0.0, 0.0, 0.0, 0.98565673828125, 0.008544921875, 0.00579833984375, 0.0], 'empty_cells': [0.0, 0.0, 0.0, 0.994140625, 0.005859375, 0.0, 0.0]}, 'score': 3.6862670898437497}

## 6. Candidate Owner Mapping
- owner candidate summary: {'raw_owner_neutral': 10, 'raw_owner_player0': 11, 'raw_owner_player1': 12, 'proxy_agreement': True}

## 7. Candidate UnitType Mapping
- unit_type candidate summary: {'raw_unit_type_channels': {'Resource': 14, 'Base': 15, 'Barracks': 16, 'Worker': 17, 'Light': 18, 'Heavy': 19, 'Ranged': 20}, 'controlled_observed_channels': {'Resource': 14, 'Base': 15, 'Worker': 17}, 'controlled_observed_agree_with_source_exact': True, 'proxy_window_agree_with_source_exact_start13': False}
- candidate mapping file: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_legacy032/observation_semantics/legacy032_to_unity_v2_observation_mapping.stage10d5_candidate.json

## 8. Candidate Adapter Dry-run
- dry-run status: pass
- worker_harvest_proxy: {'count': 4096, 'unit_type_mean': [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0], 'expected_unity_peak_index': 3, 'peak_index': 3, 'compatible': True}
- base_produce_proxy: {'count': 4096, 'unit_type_mean': [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'expected_unity_peak_index': 1, 'peak_index': 1, 'compatible': True}
- impossible patterns: {'resource_plus_ranged_multihot_share': 0.0}

## 9. Risk Assessment
- Remaining risk is mostly perspective-specific behavior if rollout perspective changes from player0.
- If future pipeline introduces self-play perspective switching, owner mapping must be re-validated.

## 10. Gate Decision
- classifications: ['OWNER_UNIT_MAPPING_RECOVERED_WITH_SOURCE_EVIDENCE']
- gate: GO_FOR_STAGE10D4_MAPPING_SPEC_PATCH
- mapping_complete_for_critical_groups: True
- dry_run_pass: True

## 11. Explicit Non-Claims
- No claim of semantic parity beyond demonstrated source/probe evidence.
- No claim that BC-ready full dataset rebuild is authorized in this stage by default.
- No claim that retraining is authorized before full semantic adapter validation after mapping patch.
