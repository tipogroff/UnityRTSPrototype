# STAGE10D23 Policy Logits And Selection Audit

- Generated (UTC): 2026-05-04T06:48:49.527547+00:00
- Source run manifest: python/week6_student/tmp/stage10d22_global_lifecycle/stage10d22_run_manifest.json

## Checkpoint binding
- checkpoint path loaded: python/week6_student/runs/legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z/student_bc_stage10d14_augmented_best.pt
- model class: unknown_not_emitted
- model variant: unknown
- checkpoint epoch: 1
- branch sizes: [6, 4, 4, 4, 4, 7, 49]
- logits tensor keys: ['action_type_logits', 'move_dir_logits', 'harvest_dir_logits', 'return_dir_logits', 'produce_dir_logits', 'produce_unit_type_logits', 'attack_target_local_logits']
- action_type logits shape: [1, 576, 6]
- device: unknown_not_emitted
- fallback_used: False
- fake_logits_used: False
- heuristic_policy_path_used (student mode): False

## Policy source isolation
- student policy source: student_live_policy
- heuristic policy source: heuristic_baseline
- same checkpoint path used: True
- heuristic calls student inference likely: True

## Student action_type top-k summary
| Action | Top1 | Top2 | Top3 | AvgProb | AvgLogit |
|---|---|---|---|---|---|
| NoOp | 272 | 23 | 2 | 0.527294 | -1.096164 |
| Move | 0 | 0 | 27 | 0.026522 | -0.569501 |
| Harvest | 124 | 134 | 217 | 0.206895 | 0.762085 |
| Return | 0 | 0 | 49 | 0.025662 | -0.553554 |
| Produce | 86 | 261 | 103 | 0.178876 | 0.771835 |
| Attack | 0 | 64 | 84 | 0.034751 | -0.366119 |

## Move probability/rank analysis
- average Move rank: 4.8340
- Move top2 count: 0
- Move top3 count: 27

## Attack probability/rank analysis
- average Attack rank: 4.2386
- Attack top2 count: 64
- Attack top3 count: 148

## Legal-but-not-selected analysis
- Move legal but not selected: 391
- Attack legal but not selected: 20

## Student vs heuristic mode comparison
- raw distributions identical: True
- trace rows identical on friendly actor cells: True
- trace rows identical on all cells: True
- same checkpoint path used: True
- heuristic uses student inference likely: True

## Branch index mapping validation
- action_type_index_0_label: NoOp
- action_type_index_1_label: Move
- action_type_index_2_label: Harvest
- action_type_index_3_label: Return
- action_type_index_4_label: Produce
- action_type_index_5_label: Attack
- matches expected mapping: True

## First failing boundary update
- Move: raw_selected
- Attack: raw_selected

## GO/NO-GO verdict
- GO

## Artifact paths
- Trace JSONL: python/week6_student/reports/stage10d23_policy_logits_trace.jsonl
- Summary JSON: python/week6_student/reports/stage10d23_policy_logits_summary.json
- Markdown report: python/week6_student/reports/STAGE10D23_POLICY_LOGITS_AND_SELECTION_AUDIT.md
