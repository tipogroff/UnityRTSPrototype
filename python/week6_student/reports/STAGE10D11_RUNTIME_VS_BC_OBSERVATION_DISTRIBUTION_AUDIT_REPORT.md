# STAGE10D11 Runtime-vs-BC Observation Distribution Audit

Generated at UTC: 2026-05-03T12:52:04Z

## Section 1 - Inputs and validation
- runtime cell table: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d10_global_runtime_cell_table_step0001.jsonl
- runtime logits snapshot: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d10_global_runtime_logits_snapshot_step0001.json
- runtime summary: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10d10_global_runtime_summary.json
- legacy runtime snapshot: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json
- bc ready dir: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/bc_ready/legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z
- checkpoint: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/runs/legacy032_v2_semantic_bc_stage10d8_20260503T093718Z/student_bc_semantic_best.pt
- runtime cell table rows: 576
- bc dataset loaded: train=79348, validation=8817
- checkpoint loaded: True
- mutation scope: read-only analysis; writes only to python/week6_student/reports

## Section 2 - Runtime focus cell channel audit
- B2: owner=Player1, unit=Worker, predicted=NoOp
  - probs: noop=0.785166, harvest=0.066120, produce=0.044780
  - critical_observation_encoding_mismatch=False
- C3: owner=Player1, unit=Base, predicted=NoOp
  - probs: noop=0.994620, harvest=0.001104, produce=0.001276
  - critical_observation_encoding_mismatch=False

## Section 3 - BC positive actor-cell statistics
- Worker+Harvest count: 86570
- Base+Produce count: 87645
- Worker owner pattern: {'pattern': [0, 1, 0], 'count': 86570}
- Base owner pattern: {'pattern': [0, 1, 0], 'count': 87645}

## Section 4 - Runtime-vs-BC channel deltas
- B2 nearest L2 27ch: 2.449490
- B2 nearest patch5 L2: 6.164414
- B2 nearest patch7 L2: 7.483315
- C3 nearest L2 27ch: 2.000000
- C3 nearest patch5 L2: 7.483315
- C3 nearest patch7 L2: 8.831761

## Section 5 - Full-map and local context comparison
- Runtime map summary: {'count_self_friendly_cells': 2, 'count_enemy_cells': 3, 'count_neutral_cells': 571, 'count_resources': 4, 'count_bases': 2, 'count_workers': 2, 'count_barracks': 1, 'count_combat_units': 0, 'count_empty_cells': 567, 'total_actor_cells': 5, 'friendly_actor_cells': 2, 'enemy_actor_cells': 3}
- BC worker representative summary: {'count_self_friendly_cells': 2, 'count_enemy_cells': 14, 'count_neutral_cells': 560, 'count_resources': 4, 'count_bases': 2, 'count_workers': 14, 'count_barracks': 0, 'count_combat_units': 0, 'count_empty_cells': 556, 'total_actor_cells': 16, 'friendly_actor_cells': 2, 'enemy_actor_cells': 14}
- BC base representative summary: {'count_self_friendly_cells': 2, 'count_enemy_cells': 4, 'count_neutral_cells': 570, 'count_resources': 4, 'count_bases': 2, 'count_workers': 3, 'count_barracks': 1, 'count_combat_units': 0, 'count_empty_cells': 566, 'total_actor_cells': 6, 'friendly_actor_cells': 2, 'enemy_actor_cells': 4}
- Local context deltas: {'B2_runtime_patch5_l2_vs_nearest_worker_patch5': 6.164414002968976, 'B2_runtime_patch7_l2_vs_nearest_worker_patch7': 7.483314773547883, 'C3_runtime_patch5_l2_vs_nearest_base_patch5': 7.483314773547883, 'C3_runtime_patch7_l2_vs_nearest_base_patch7': 8.831760866327848}

## Section 6 - Student confidence comparison
- Runtime B2: predicted=NoOp, p_noop=0.982008, p_harvest=0.004535
- Runtime C3: predicted=NoOp, p_noop=0.996549, p_produce=0.000756
- BC Worker+Harvest mean p_harvest=0.997898, mean p_noop=0.000000
- BC Base+Produce mean p_produce=0.997287, mean p_noop=0.000000

## Section 7 - Counterfactual probe results
- Probe A: {'B2': {'flat_index': 25, 'predicted_action': 'Harvest', 'p_noop': 0.00013337770360521972, 'p_harvest': 0.6185013651847839, 'p_produce': 0.13644418120384216, 'probabilities': [0.00013337770360521972, 0.06715962290763855, 0.6185013651847839, 0.09174622595310211, 0.13644418120384216, 0.0860152468085289]}, 'C3': {'flat_index': 50, 'predicted_action': 'NoOp', 'p_noop': 0.9834836721420288, 'p_harvest': 0.003431223798543215, 'p_produce': 0.004401414655148983, 'probabilities': [0.9834836721420288, 0.002707978943362832, 0.003431223798543215, 0.0035207790788263083, 0.004401414655148983, 0.002454860834404826]}}
- Probe B: {'B2': {'flat_index': 25, 'predicted_action': 'Harvest', 'p_noop': 1.579849770437577e-27, 'p_harvest': 0.9960970282554626, 'p_produce': 0.0033990349620580673, 'probabilities': [1.579849770437577e-27, 0.00013411800318863243, 0.9960970282554626, 0.00011243809422012419, 0.0033990349620580673, 0.0002574308018665761]}, 'C3': {'flat_index': 50, 'predicted_action': 'Produce', 'p_noop': 1.1212570528062671e-20, 'p_harvest': 0.004751839209347963, 'p_produce': 0.9934493899345398, 'probabilities': [1.1212570528062671e-20, 0.0006966134533286095, 0.004751839209347963, 0.0010064954403787851, 0.9934493899345398, 9.563771163811907e-05]}}
- Probe C: {'B2': {'flat_index': 25, 'predicted_action': 'Harvest', 'p_noop': 2.637380502906033e-29, 'p_harvest': 0.9974570870399475, 'p_produce': 0.002265235874801874, 'probabilities': [2.637380502906033e-29, 7.573575567221269e-05, 0.9974570870399475, 5.3010720876045525e-05, 0.002265235874801874, 0.00014892456238158047]}, 'C3': {'flat_index': 50, 'predicted_action': 'Produce', 'p_noop': 1.1003055533984506e-20, 'p_harvest': 0.00573623226955533, 'p_produce': 0.9926778078079224, 'probabilities': [1.1003055533984506e-20, 0.000727399077732116, 0.00573623226955533, 0.0007748611969873309, 0.9926778078079224, 8.370160503545776e-05]}}
- Probe D: {'worker_reference': {'split': 'train', 'sample_index': 0, 'flat_index': 25, 'predicted_action': 'Harvest', 'p_noop': 1.8848051710802153e-29, 'p_harvest': 0.9985673427581787, 'p_produce': 0.0011941972188651562}, 'base_reference': {'split': 'train', 'sample_index': 6, 'flat_index': 50, 'predicted_action': 'Produce', 'p_noop': 1.1058978274830632e-20, 'p_harvest': 0.006601983681321144, 'p_produce': 0.99201899766922}}
- Probe E: {'B2': {'flat_index': 25, 'predicted_action': 'Harvest', 'p_noop': 0.000801681715529412, 'p_harvest': 0.5443900227546692, 'p_produce': 0.16135011613368988, 'probabilities': [0.000801681715529412, 0.08448278903961182, 0.5443900227546692, 0.10853433609008789, 0.16135011613368988, 0.1004411056637764]}, 'C3': {'flat_index': 50, 'predicted_action': 'NoOp', 'p_noop': 0.9945089221000671, 'p_harvest': 0.0011581496801227331, 'p_produce': 0.0012583710486069322, 'probabilities': [0.9945089221000671, 0.0010228421306237578, 0.0011581496801227331, 0.0011741797206923366, 0.0012583710486069322, 0.0008775655878707767]}}

## Section 8 - Evidence-based classification
- RUNTIME_CURRENT_ACTION_OR_DIRECTION_MISMATCH
- STUDENT_REQUIRES_BC_CONTEXT_NOT_PRESENT_IN_UNITY
- UNITY_SCENE_DISTRIBUTION_MISMATCH

## Section 9 - Recommended next gate
- Primary next gate: GO_FOR_RUNTIME_CHANNEL_SEMANTIC_REMAP_FIX
