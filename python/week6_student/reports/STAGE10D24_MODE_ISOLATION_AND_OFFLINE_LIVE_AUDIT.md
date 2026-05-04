# STAGE10D24 — Mode Isolation and Offline-vs-Live Policy Audit

Generated: 2026-05-04T19:32:33.631795+00:00

## 1. Heuristic Mode Isolation Verdict

**Verdict: NOT_ISOLATED**

Failure evidence:

- checkpoint_path_identical=true: both modes use 'python/week6_student/runs/legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z/student_bc_stage10d14_augmented_best.pt'
- heuristic_checkpoint_path contains 'student_bc': student model loaded in heuristic mode
- heuristic_adapter_invoked=true (inference_count=1)
- action_type_logits identical at step=1 row=0
- actor cell logits identical at step=1
- all raw row hashes identical across 80 steps
- actor row hashes identical across 80 steps

### Telemetry

| Field | Value |
|---|---|
| mode | heuristic_baseline |
| policy_source | student_checkpoint |
| inference_source | python_adapter |
| uses_student_checkpoint | True |
| uses_python_adapter | True |
| uses_heuristic_policy | False |
| uses_scripted_injection | False |
| action_buffer_source | student_inference_logits |
| checkpoint_path_in_snapshot | python/week6_student/runs/legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z/student_bc_stage10d14_augmented_best.pt |
| student_checkpoint_path | python/week6_student/runs/legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z/student_bc_stage10d14_augmented_best.pt |
| adapter_invoked_in_snapshot | True |
| inference_request_count_in_snapshot | 1 |

**Action required**: The heuristic baseline must be re-implemented without student inference. Heuristic comparisons from Stage10D22/D23 are invalid as both modes use identical student logits.

## 2. Checkpoint Lineage and Loaded Checkpoint Confirmation

Current checkpoint: `C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week6_student\runs\legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z\student_bc_stage10d14_augmented_best.pt`

Checkpoint exists: True

BC validation dataset: `C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week6_student\bc_ready\legacy032_3m_unity_v2_stage10d14_unity_like_augmented_bc_ready_20260503T145301Z`

Validation samples: 8985

Actor cells in validation: 17775

| Name | Stage | Current | Exists | Val Loss | Val AccType | Val Recall | Train Attack# | Train Attack Acc |
|---|---|---|---|---|---|---|---|---|
| stage10d14_augmented_best | 10D.14 | True | True | 0.000448 | 1.0000 | 1.0000 | 88 | 0.1250 |
| stage10d17_movement_best | 10D.17 | False | True | 0.000272 | 0.9999 | 0.9999 | 12 | 0.9167 |
| stage10d19b_valid_move_best | 10D.19b | False | True | 0.000191 | 0.9980 | 0.9980 | 34 | 0.9706 |
| stage10d19c_mask_aware_best | 10D.19c | False | True | N/A | N/A | N/A | N/A | N/A |

## 3. Offline Validation Action Distribution

| Action | Label Count | Predicted Top1 Count | Precision | Recall |
|---|---|---|---|---|
| NoOp | 0 | 0 | 0.0000 | 0.0000 |
| Move | 0 | 0 | 0.0000 | 0.0000 |
| Harvest | 8830 | 8830 | 1.0000 | 1.0000 |
| Return | 0 | 0 | 0.0000 | 0.0000 |
| Produce | 8938 | 8938 | 1.0000 | 1.0000 |
| Attack | 7 | 7 | 1.0000 | 1.0000 |

Average Move rank (offline, actor cells): 3.943  |  Average Attack rank (offline, actor cells): 3.998

Average Move probability (offline): 0.000061  |  Average Attack probability (offline): 0.000253

Move rank distribution: {'1': 0, '2': 0, '3': 1012, '4': 16759, '5': 4, '6': 0}

Attack rank distribution: {'1': 7, '2': 126, '3': 8704, '4': 0, '5': 8938, '6': 0}

## 4. Offline Prediction Confusion Matrix

Rows = true label, columns = predicted label.

| True \ Pred | NoOp | Move | Harvest | Return | Produce | Attack |
|---|---|---|---|---|---|---|
| NoOp | 0 | 0 | 0 | 0 | 0 | 0 |
| Move | 0 | 0 | 0 | 0 | 0 | 0 |
| Harvest | 0 | 0 | 8830 | 0 | 0 | 0 |
| Return | 0 | 0 | 0 | 0 | 0 | 0 |
| Produce | 0 | 0 | 0 | 0 | 8938 | 0 |
| Attack | 0 | 0 | 0 | 0 | 0 | 7 |

## 5. Unity Live Prediction Distribution

Mode: student_live_policy, Steps: 80, Actor cells: 482

| Action | Live Predicted Top1 Count |
|---|---|
| NoOp | 272 |
| Move | 0 |
| Harvest | 124 |
| Return | 0 |
| Produce | 86 |
| Attack | 0 |

Move top1: 0 | top2: 0 | top3: 27

Attack top1: 0 | top2: 64 | top3: 84

Move avg rank: 4.834 | Move avg prob: 0.026522

Attack avg rank: 4.239 | Attack avg prob: 0.034751

Move legal but not selected: 391

Attack legal but not selected: 20

## 6. Offline-vs-Live Comparison

| Action | Offline Label# | Offline Pred Top1# | Live Pred Top1# | Off Avg Prob | Live Avg Prob | Off Avg Rank | Live Avg Rank |
|---|---|---|---|---|---|---|---|
| NoOp | 0 | 0 | 272 | N/A | N/A | N/A | N/A |
| Move | 0 | 0 | 0 | 6.1e-05 | 0.026522 | 3.943 | 4.834 |
| Harvest | 8830 | 8830 | 124 | N/A | N/A | N/A | N/A |
| Return | 0 | 0 | 0 | N/A | N/A | N/A | N/A |
| Produce | 8938 | 8938 | 86 | N/A | N/A | N/A | N/A |
| Attack | 7 | 7 | 0 | 0.000253 | 0.034751 | 3.998 | 4.239 |

## 7. Move Diagnosis

**CRITICAL**: BC validation dataset contains ZERO Move labels. The model cannot learn to predict Move from this dataset regardless of architecture or training hyperparameters. The high val_accuracy=1.0 is misleading — the model is perfectly predicting on a dataset that has no Move samples.

Move appears in top-2 live: 0, top-3 live: 27. Avg rank=4.834, avg prob=0.026522.

## 8. Attack Diagnosis

**Offline Attack top1=7** but **Live Attack top1=0**. Domain mismatch between BC dataset and Unity live observations.

Attack in top-2 live: 64, top-3 live: 84. Avg rank=4.239, avg prob=0.034751.

## 9. Selector Ablation Results

| Selector | Move# | Attack# | NoOp# | Invalid/Masked# | Move Share | Attack Share |
|---|---|---|---|---|---|---|
| greedy_argmax | 0 | 0 | 272 | 0 | 0.0000 | 0.0000 |
| legal_masked_argmax | 0 | 0 | 339 | 0 | 0.0000 | 0.0000 |
| topk_sampling_legal | 13 | 2 | 324 | 0 | 0.0270 | 0.0041 |
| temperature_sampling_legal | 13 | 3 | 325 | 0 | 0.0270 | 0.0062 |

**greedy_argmax**: Greedy argmax over all action logits, no mask

  Distribution: {'NoOp': 272, 'Move': 0, 'Harvest': 124, 'Return': 0, 'Produce': 86, 'Attack': 0}

**legal_masked_argmax**: Argmax over legal actions only (illegal masked to -inf)

  Distribution: {'NoOp': 339, 'Move': 0, 'Harvest': 80, 'Return': 0, 'Produce': 63, 'Attack': 0}

**topk_sampling_legal**: Top-k (k=3) sampling among legal actions by prob

  Distribution: {'NoOp': 324, 'Move': 13, 'Harvest': 70, 'Return': 0, 'Produce': 73, 'Attack': 2}

**temperature_sampling_legal**: Temperature (T=1.0) sampling among legal actions

  Distribution: {'NoOp': 325, 'Move': 13, 'Harvest': 74, 'Return': 0, 'Produce': 67, 'Attack': 3}

## 10. GO/NO-GO Recommendation

**Decisions**: RETRAIN_OR_ADJUST_BC_OBJECTIVE, TEST_NON_GREEDY_SELECTOR, FIX_HEURISTIC_MODE_WIRING

Reasoning:

- BC validation dataset has zero Move labels: model cannot learn Move from this data.
- Move appears as top2/top3 27 times live but never top1: greedy argmax may be suppressing Move due to NoOp/Harvest dominance.
- Heuristic baseline is NOT isolated: it uses the student checkpoint. Heuristic comparison is invalid until isolation is fixed.

| Decision | Meaning |
|---|---|
| CONTINUE_WITH_CURRENT_CHECKPOINT | Current checkpoint is adequate for current goals |
| SWITCH_CHECKPOINT | A different checkpoint predicts Move/Attack better offline |
| FIX_OBSERVATION_DOMAIN_MISMATCH | Offline predicts Move but live does not — fix observation semantics |
| RETRAIN_OR_ADJUST_BC_OBJECTIVE | BC dataset lacks Move/Attack or model is suppressing them — need retraining |
| TEST_NON_GREEDY_SELECTOR | Move appears in top2/top3 — non-greedy selector may expose it |
| FIX_HEURISTIC_MODE_WIRING | Heuristic mode incorrectly uses student inference — fix C# wiring |
