# LEGACY032 Unity v2 Stage 10D.1R Corrected Owner Semantics Rerun Report

## 1. Scope
- Diagnostic/spec remediation only.
- No runtime semantics change.
- No dataset mutation.
- No checkpoint mutation.
- No retraining.
- No PPO.

## 2. Why Stage 10D.1R Was Needed
- Stage10D.2 found owner-channel interpretation conflict.
- Stage10D.1 assumed absolute_player_channels.
- UnityMvpTransfer path may use neutral/friendly/enemy.
- Therefore Stage10D.1 observation mismatch claim needed rerun.

## 3. Inputs
- Stage10D.1 scripts/artifacts: python/week6_student/stage10d1_*.py and python/week6_student/reports/stage10d1_*.json
- Stage10D.2 artifacts: python/week6_student/reports/stage10d2_*.json
- BC-ready dataset path: python/week5_teacher_legacy032/teacher_exports_bc/day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z
- Unity snapshot path: python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json
- checkpoint path: python/week6_student/runs/legacy032_v2_bc_minimal_20260501T195501Z/student_bc_transfer_best.pt
- scene path: Assets/Scenes/Week6_StudentVisualInspection.unity
- commit hash: 5c86551f7429ddfdea6385f9b5da55fd0eaa7010

## 4. Corrected Owner Semantics
| Mode | ch2 | ch3 | ch4 | Used for |
|---|---|---|---|---|
| absolute_player_channels | neutral | player1 | player2 | legacy/contract naming |
| perspective_friendly_enemy | neutral | friendly | enemy | UnityMvpTransfer perspective naming |

## 5. Recomputed Dataset Action Distribution
- Are actor-cell labels NoOp-dominant? No. own_actor_cells NoOp count = 0
- Are worker actor labels still mostly/only Harvest? Yes. own_worker_cells={'NoOp': 0, 'Move': 0, 'Harvest': 86570, 'Return': 0, 'Produce': 0, 'Attack': 0}
- Are base actor labels still mostly/only Produce? Yes. own_base_cells={'NoOp': 0, 'Move': 0, 'Harvest': 0, 'Return': 0, 'Produce': 87645, 'Attack': 0}
- Did owner semantics affect this distribution? No (label-proxy path unchanged).
- all_576_cells action_type distribution: {'NoOp': 50608730, 'Move': 0, 'Harvest': 86570, 'Return': 0, 'Produce': 87645, 'Attack': 95}

## 6. Corrected Unity vs BC Channel Comparison
### B2
- Unity raw vector: [1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
- owner included (absolute): player1; owner included (perspective): friendly
- owner excluded distance (absolute): 3.0
- owner excluded distance (perspective): 3.0
- unit_type mismatch flags: abs=True pers=True
- current_action mismatch flags: abs=True pers=True
- direction mismatch flags: abs=True pers=True
- final B2 interpretation: owner semantics conflict exists; non-owner channels decide whether mismatch persists.

### C3
- Unity raw vector: [1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
- owner included (absolute): player1; owner included (perspective): friendly
- owner excluded distance (absolute): 2.8284271313969085
- owner excluded distance (perspective): 2.8284271313969085
- unit_type mismatch flags: abs=True pers=True
- current_action mismatch flags: abs=True pers=True
- direction mismatch flags: abs=True pers=True
- final C3 interpretation: owner semantics conflict exists; non-owner channels decide whether mismatch persists.

## 7. Corrected Nearest Neighbor Analysis
### B2
- all_27: {'best_distance': 2.8284271247461903, 'neighbor_sample_index': 7482, 'neighbor_flat_index': 50, 'label_action_type': {'id': 4, 'name': 'Produce'}, 'interpreted_owner_by_mode': {'absolute_player_channels': 'player1', 'perspective_friendly_enemy': 'friendly'}, 'interpreted_unit_type': 'Resource', 'interpreted_current_action': 'Return', 'semantically_compatible': False}
- exclude_owner_2_4: {'best_distance': 2.8284271247461903, 'neighbor_sample_index': 0, 'neighbor_flat_index': 50, 'label_action_type': {'id': 4, 'name': 'Produce'}, 'interpreted_owner_by_mode': {'absolute_player_channels': 'player2', 'perspective_friendly_enemy': 'enemy'}, 'interpreted_unit_type': 'Resource', 'interpreted_current_action': 'Return', 'semantically_compatible': False}
- exclude_current_action_12_17: {'best_distance': 2.449489742783178, 'neighbor_sample_index': 7482, 'neighbor_flat_index': 50, 'label_action_type': {'id': 4, 'name': 'Produce'}, 'interpreted_owner_by_mode': {'absolute_player_channels': 'player1', 'perspective_friendly_enemy': 'friendly'}, 'interpreted_unit_type': 'Resource', 'interpreted_current_action': 'Return', 'semantically_compatible': False}
- exclude_owner_and_current_action: {'best_distance': 2.449489742783178, 'neighbor_sample_index': 0, 'neighbor_flat_index': 50, 'label_action_type': {'id': 4, 'name': 'Produce'}, 'interpreted_owner_by_mode': {'absolute_player_channels': 'player2', 'perspective_friendly_enemy': 'enemy'}, 'interpreted_unit_type': 'Resource', 'interpreted_current_action': 'Return', 'semantically_compatible': False}
- semantic compatibility verdict taken from best-neighbor records above.

### C3
- all_27: {'best_distance': 2.8284271247461903, 'neighbor_sample_index': 7482, 'neighbor_flat_index': 50, 'label_action_type': {'id': 4, 'name': 'Produce'}, 'interpreted_owner_by_mode': {'absolute_player_channels': 'player1', 'perspective_friendly_enemy': 'friendly'}, 'interpreted_unit_type': 'Resource', 'interpreted_current_action': 'Return', 'semantically_compatible': False}
- exclude_owner_2_4: {'best_distance': 2.8284271247461903, 'neighbor_sample_index': 0, 'neighbor_flat_index': 50, 'label_action_type': {'id': 4, 'name': 'Produce'}, 'interpreted_owner_by_mode': {'absolute_player_channels': 'player2', 'perspective_friendly_enemy': 'enemy'}, 'interpreted_unit_type': 'Resource', 'interpreted_current_action': 'Return', 'semantically_compatible': False}
- exclude_current_action_12_17: {'best_distance': 2.449489742783178, 'neighbor_sample_index': 7482, 'neighbor_flat_index': 50, 'label_action_type': {'id': 4, 'name': 'Produce'}, 'interpreted_owner_by_mode': {'absolute_player_channels': 'player1', 'perspective_friendly_enemy': 'friendly'}, 'interpreted_unit_type': 'Resource', 'interpreted_current_action': 'Return', 'semantically_compatible': False}
- exclude_owner_and_current_action: {'best_distance': 2.449489742783178, 'neighbor_sample_index': 0, 'neighbor_flat_index': 50, 'label_action_type': {'id': 4, 'name': 'Produce'}, 'interpreted_owner_by_mode': {'absolute_player_channels': 'player2', 'perspective_friendly_enemy': 'enemy'}, 'interpreted_unit_type': 'Resource', 'interpreted_current_action': 'Return', 'semantically_compatible': False}
- semantic compatibility verdict taken from best-neighbor records above.

## 8. Training Objective Audit
- action_type loss on all 576 cells: True
- actor-cell weighting used: False
- class weights used: False
- non-NoOp oversampling used: False
- validation may be NoOp-dominated: True
- This remains secondary unless observation mismatch is cleared.

## 9. Corrected Root-Cause Classification
- primary: UNITY_AND_BC_PERSPECTIVE_ENCODING_MISMATCH_CONFIRMED

## 10. Gate Decision
- NO_GO_RETRAINING_UNTIL_OBSERVATION_FIXED

## 11. Explicit Non-Claims
- This report does not prove semantic parity between Gym-μRTS and Unity.
- This report does not claim direct weight transfer.
- This report does not validate final tactical behavior.
- This report does not authorize PPO or teacher retraining.
- This report does not change ActionApplier/MatchManager runtime semantics.
- This report does not mutate dataset/checkpoint files.