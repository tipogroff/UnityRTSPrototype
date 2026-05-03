# STAGE10D10 Global Runtime NoOp Persistence Diagnostic Report

- generated_at_utc: 2026-05-03T15:20:19.2549713Z
- step: 1
- classification: MIXED_OR_INCONCLUSIVE
- rationale: Mixed evidence: actor_count=2, actor_noop=0, actor_non_noop=2, off_actor_non_noop=0, max_actor_non_noop_prob=1.000.

## Required Metrics
- total_cells: 576
- friendly_actor_cell_count: 2
- friendly_worker_count: 1
- friendly_base_count: 1
- global_predicted_noop_share: 0.996528
- actor_cell_predicted_noop_share: 0.000000
- worker_predicted_noop_share: 0.000000
- base_predicted_noop_share: 0.000000
- max_non_noop_probability_globally: 1.000000
- max_non_noop_probability_on_actor_cells: 1.000000
- non_noop_predictions_on_actor_cells: 2
- non_noop_predictions_off_actor_cells: 0
- commands_built: 2
- commands_submitted: 2
- commands_accepted: 1

## Top-K Non-NoOp Cells
- cell=25 (1,1) label=B2, score=1.000000, predicted=Harvest, runtime_actor=True
- cell=50 (2,2) label=C3, score=1.000000, predicted=Produce, runtime_actor=True
- cell=4 (4,0) label=E1, score=0.000969, predicted=NoOp, runtime_actor=False
- cell=527 (23,21) label=X22, score=0.000725, predicted=NoOp, runtime_actor=False
- cell=74 (2,3) label=C4, score=0.000692, predicted=NoOp, runtime_actor=False
- cell=2 (2,0) label=C1, score=0.000682, predicted=NoOp, runtime_actor=False
- cell=99 (3,4) label=D5, score=0.000593, predicted=NoOp, runtime_actor=False
- cell=574 (22,23) label=W24, score=0.000573, predicted=NoOp, runtime_actor=False

## Top-K Harvest Probability Cells
- cell=25 (1,1) label=B2, score=0.991691, predicted=Harvest, runtime_actor=True
- cell=50 (2,2) label=C3, score=0.004683, predicted=Produce, runtime_actor=True
- cell=4 (4,0) label=E1, score=0.000196, predicted=NoOp, runtime_actor=False
- cell=527 (23,21) label=X22, score=0.000170, predicted=NoOp, runtime_actor=False
- cell=2 (2,0) label=C1, score=0.000149, predicted=NoOp, runtime_actor=False
- cell=74 (2,3) label=C4, score=0.000145, predicted=NoOp, runtime_actor=False
- cell=99 (3,4) label=D5, score=0.000132, predicted=NoOp, runtime_actor=False
- cell=574 (22,23) label=W24, score=0.000126, predicted=NoOp, runtime_actor=False

## Top-K Produce Probability Cells
- cell=50 (2,2) label=C3, score=0.992233, predicted=Produce, runtime_actor=True
- cell=25 (1,1) label=B2, score=0.004075, predicted=Harvest, runtime_actor=True
- cell=4 (4,0) label=E1, score=0.000236, predicted=NoOp, runtime_actor=False
- cell=74 (2,3) label=C4, score=0.000173, predicted=NoOp, runtime_actor=False
- cell=527 (23,21) label=X22, score=0.000157, predicted=NoOp, runtime_actor=False
- cell=2 (2,0) label=C1, score=0.000153, predicted=NoOp, runtime_actor=False
- cell=27 (3,1) label=D2, score=0.000148, predicted=NoOp, runtime_actor=False
- cell=99 (3,4) label=D5, score=0.000132, predicted=NoOp, runtime_actor=False

## Top-K Attack Probability Cells
- cell=25 (1,1) label=B2, score=0.002849, predicted=Harvest, runtime_actor=True
- cell=50 (2,2) label=C3, score=0.000173, predicted=Produce, runtime_actor=True
- cell=4 (4,0) label=E1, score=0.000157, predicted=NoOp, runtime_actor=False
- cell=2 (2,0) label=C1, score=0.000125, predicted=NoOp, runtime_actor=False
- cell=74 (2,3) label=C4, score=0.000120, predicted=NoOp, runtime_actor=False
- cell=527 (23,21) label=X22, score=0.000117, predicted=NoOp, runtime_actor=False
- cell=48 (0,2) label=A3, score=0.000104, predicted=NoOp, runtime_actor=False
- cell=574 (22,23) label=W24, score=0.000097, predicted=NoOp, runtime_actor=False

## Decoder Reject Counts
- not_built_in_decoder_or_filter: 1

## Applier Reject Counts
- none

## Artifact Paths
- logits_snapshot_json: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python/week6_student/reports\stage10d10_global_runtime_logits_snapshot_step0001.json
- cell_table_jsonl: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python/week6_student/reports\stage10d10_global_runtime_cell_table_step0001.jsonl
- summary_json: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python/week6_student/reports\stage10d10_global_runtime_summary.json
