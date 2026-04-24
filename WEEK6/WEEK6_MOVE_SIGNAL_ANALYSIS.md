# Week 6 Move Signal Analysis

## Scope
- Primary source: python\week5_teacher\teacher_exports_bc\day6_bc_ready_teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z
- Offline data diagnostics only. No Unity run, no replay, no retraining.

## Canonical action_type mapping
- 0 -> NoOp
- 1 -> Move
- 2 -> Harvest
- 3 -> Return
- 4 -> Produce
- 5 -> Attack

## BC-ready overall action distribution: train
| Action | ID | Count | Share |
|---|---:|---:|---:|
| NoOp | 0 | 843181 | 40.106% |
| Move | 1 | 838202 | 39.869% |
| Harvest | 2 | 109469 | 5.207% |
| Return | 3 | 125398 | 5.965% |
| Produce | 4 | 113150 | 5.382% |
| Attack | 5 | 73000 | 3.472% |
| TOTAL | - | 2102400 | 100.000% |

## BC-ready overall action distribution: validation
| Action | ID | Count | Share |
|---|---:|---:|---:|
| NoOp | 0 | 90091 | 40.105% |
| Move | 1 | 89550 | 39.864% |
| Harvest | 2 | 11699 | 5.208% |
| Return | 3 | 13410 | 5.970% |
| Produce | 4 | 12090 | 5.382% |
| Attack | 5 | 7800 | 3.472% |
| TOTAL | - | 224640 | 100.000% |

## Move share summary
- Train Move: 838202 (39.869%)
- Validation Move: 89550 (39.864%)

## Produce vs Move contrast
- Train Produce/Move ratio: 0.135
- Validation Produce/Move ratio: 0.135

## Early-step distribution
### Train
- Window step_0_to_20, kept_samples=144
  Move=33114 (39.923%), Produce=4464 (5.382%)
- Window step_0_to_50, kept_samples=358
  Move=82193 (39.859%), Produce=11098 (5.382%)
### Validation
- Window step_0_to_20, kept_samples=24
  Move=5518 (39.916%), Produce=744 (5.382%)
- Window step_0_to_50, kept_samples=50
  Move=11479 (39.858%), Produce=1550 (5.382%)

## Adaptation input vs output
- conversion_report: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher\teacher_exports\teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z\conversion_report.json
- Move teacher_input -> adapted_output: 927752 (39.868%) -> 927752 (39.868%)

## Approximate meaningful actor-cell subset
- train: unavailable (Could not recover reliable owned controllable actor cells from BC-ready input_tensor encoding using strict one-hot assumptions; subset analysis skipped to avoid heuristic distortion.)
- validation: unavailable (Could not recover reliable owned controllable actor cells from BC-ready input_tensor encoding using strict one-hot assumptions; subset analysis skipped to avoid heuristic distortion.)

## Conclusion
- Move signal is clearly present in BC-ready supervision; issue is more likely downstream (student policy behavior/training dynamics) than complete absence of Move labels.
