# STAGE10D10 Global Runtime NoOp Persistence Diagnostic Report

- generated_at_utc: 2026-05-03T11:53:35.6764376Z
- step: 1
- classification: MIXED_OR_INCONCLUSIVE
- rationale: Mixed evidence: actor_count=2, actor_noop=2, actor_non_noop=0, off_actor_non_noop=0, max_actor_non_noop_prob=0.215.

## Required Metrics
- total_cells: 576
- friendly_actor_cell_count: 2
- friendly_worker_count: 1
- friendly_base_count: 1
- global_predicted_noop_share: 1.000000
- actor_cell_predicted_noop_share: 1.000000
- worker_predicted_noop_share: 1.000000
- base_predicted_noop_share: 1.000000
- max_non_noop_probability_globally: 0.214834
- max_non_noop_probability_on_actor_cells: 0.214834
- non_noop_predictions_on_actor_cells: 0
- non_noop_predictions_off_actor_cells: 0
- commands_built: 0
- commands_submitted: 0
- commands_accepted: 0

## Top-K Non-NoOp Cells
- cell=25 (1,1) label=B2, score=0.214834, predicted=NoOp, runtime_actor=True
- cell=26 (2,1) label=C2, score=0.024269, predicted=NoOp, runtime_actor=False
- cell=2 (2,0) label=C1, score=0.015787, predicted=NoOp, runtime_actor=False
- cell=49 (1,2) label=B3, score=0.013456, predicted=NoOp, runtime_actor=False
- cell=72 (0,3) label=A4, score=0.009986, predicted=NoOp, runtime_actor=False
- cell=1 (1,0) label=B1, score=0.008099, predicted=NoOp, runtime_actor=False
- cell=527 (23,21) label=X22, score=0.008041, predicted=NoOp, runtime_actor=False
- cell=3 (3,0) label=D1, score=0.007918, predicted=NoOp, runtime_actor=False

## Top-K Harvest Probability Cells
- cell=25 (1,1) label=B2, score=0.066120, predicted=NoOp, runtime_actor=True
- cell=26 (2,1) label=C2, score=0.004488, predicted=NoOp, runtime_actor=False
- cell=2 (2,0) label=C1, score=0.003317, predicted=NoOp, runtime_actor=False
- cell=49 (1,2) label=B3, score=0.003069, predicted=NoOp, runtime_actor=False
- cell=72 (0,3) label=A4, score=0.002197, predicted=NoOp, runtime_actor=False
- cell=527 (23,21) label=X22, score=0.001901, predicted=NoOp, runtime_actor=False
- cell=1 (1,0) label=B1, score=0.001775, predicted=NoOp, runtime_actor=False
- cell=3 (3,0) label=D1, score=0.001676, predicted=NoOp, runtime_actor=False

## Top-K Produce Probability Cells
- cell=25 (1,1) label=B2, score=0.044780, predicted=NoOp, runtime_actor=True
- cell=26 (2,1) label=C2, score=0.007404, predicted=NoOp, runtime_actor=False
- cell=2 (2,0) label=C1, score=0.003603, predicted=NoOp, runtime_actor=False
- cell=49 (1,2) label=B3, score=0.002751, predicted=NoOp, runtime_actor=False
- cell=72 (0,3) label=A4, score=0.002105, predicted=NoOp, runtime_actor=False
- cell=1 (1,0) label=B1, score=0.001808, predicted=NoOp, runtime_actor=False
- cell=3 (3,0) label=D1, score=0.001796, predicted=NoOp, runtime_actor=False
- cell=527 (23,21) label=X22, score=0.001709, predicted=NoOp, runtime_actor=False

## Top-K Attack Probability Cells
- cell=25 (1,1) label=B2, score=0.036103, predicted=NoOp, runtime_actor=True
- cell=26 (2,1) label=C2, score=0.003313, predicted=NoOp, runtime_actor=False
- cell=2 (2,0) label=C1, score=0.002879, predicted=NoOp, runtime_actor=False
- cell=49 (1,2) label=B3, score=0.002379, predicted=NoOp, runtime_actor=False
- cell=72 (0,3) label=A4, score=0.001717, predicted=NoOp, runtime_actor=False
- cell=1 (1,0) label=B1, score=0.001385, predicted=NoOp, runtime_actor=False
- cell=3 (3,0) label=D1, score=0.001322, predicted=NoOp, runtime_actor=False
- cell=527 (23,21) label=X22, score=0.001309, predicted=NoOp, runtime_actor=False

## Decoder Reject Counts
- none

## Applier Reject Counts
- none

## Artifact Paths
- logits_snapshot_json: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python/week6_student/reports\stage10d10_global_runtime_logits_snapshot_step0001.json
- cell_table_jsonl: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python/week6_student/reports\stage10d10_global_runtime_cell_table_step0001.jsonl
- summary_json: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python/week6_student/reports\stage10d10_global_runtime_summary.json
