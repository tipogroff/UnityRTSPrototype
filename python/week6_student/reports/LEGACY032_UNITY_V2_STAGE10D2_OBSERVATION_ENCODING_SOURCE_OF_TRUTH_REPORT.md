# LEGACY032 Unity v2 Stage 10D.2 Observation Encoding Source-of-Truth Report

## 1. Scope
- Read-only diagnostic only.
- No retraining.
- No PPO.
- No checkpoint mutation.
- No dataset mutation.
- No runtime semantics change.

## 2. Inputs
- repository commit hash: 5c86551f7429ddfdea6385f9b5da55fd0eaa7010
- checkpoint path: python/week6_student/runs/legacy032_v2_bc_minimal_20260501T195501Z/student_bc_transfer_best.pt
- BC dataset paths: python/week5_teacher_legacy032/teacher_exports_bc/day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z/bc_train.npz, python/week5_teacher_legacy032/teacher_exports_bc/day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z/bc_validation.npz
- Unity scene path: Assets/Scenes/Week6_StudentVisualInspection.unity
- Stage10D.1 report path: python/week6_student/reports/LEGACY032_UNITY_V2_STAGE10D1_DATASET_DISTRIBUTION_DIAGNOSTIC_REPORT.md
- Unity snapshot paths found: python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json, python/week6_student/reports/stage10v_visual_snapshot_step0001.json, python/week6_student/reports/stage10v_visual_snapshot_step0002.json, python/week6_student/reports/stage10v_visual_snapshot_step0003.json

## 3. Contract Recap
- observation shape: [24,24,27] (dataset stored as [N,576,27] and loader reshapes to [N,24,24,27])
- action shape: [576,7]
- branch sizes: [6,4,4,4,4,7,49]
- focus cells: B2(flat=25), C3(flat=50)
- flatten formula: flat_index = row * 24 + col

## 4. Source-of-Truth Channel Maps
| channel index or range | Unity source meaning | adapter/source meaning | manifest/spec meaning | Stage10D.1 assumed meaning | status |
|---|---|---|---|---|---|
| 2-4 owner | contract: neutral, player1, player2; builder(mvp): neutral, friendly, enemy | owner_neutral, owner_player1, owner_player2 | names missing; shape-only in manifest | absolute_player_channels | CONFLICT |
| 5-11 unit_type | resource/base/barracks/worker/light/heavy/ranged | unit_resource..unit_ranged | names missing; shape-only | assumed same indices | MATCH |
| 12-17 current_action | noop/move/harvest/return/produce/attack | action_noop..action_attack | names missing; shape-only | assumed same indices | MATCH |
| 18-21 direction | north/east/south/west | dir_north..dir_west | names missing; shape-only | assumed same indices | MATCH |
| 22-25 produce_type | worker/light/heavy/ranged | produce_worker..produce_ranged | names missing; shape-only | assumed same indices | MATCH |
| 26 attack_target | scalar local-7x7 diagnostic | attack_target_index | attack_target_semantics=local_7x7_49 | assumed scalar | MATCH |

## 5. BC Observation Empirical Semantics
Per-channel stats are in stage10d2_bc_channel_semantics_probe.json (train/validation).
- All 27 channels were profiled for min/max/mean/std/nonzero/uniques.
- One-hot group checks were computed for owner/unit_type/current_action/direction/produce_type ranges.
- Label-proxy groups were computed: own_worker_cells, own_base_cells, own_actor_cells, resource_like_cells, non_noop_label_cells, empty_noop_cells.
- Explicit samples were dumped for action_type==Harvest, action_type==Produce, flat=25, flat=50.

## 6. Unity Snapshot Empirical Semantics
- snapshot status: OK
- B2: raw 27-channel vector captured (see JSON artifact), flat_index=25
  unity-source interpretation owner=friendly ; stage10d1 interpretation owner=player1
- C3: raw 27-channel vector captured (see JSON artifact), flat_index=50
  unity-source interpretation owner=friendly ; stage10d1 interpretation owner=player1

## 7. Loader Roundtrip / Axis Audit
- Does flat 25 remain B2? True
- Does flat 50 remain C3? True
- Is there row/column transpose? False
- Is there channel order transpose? False
- Is there any hidden reshape corruption? False
- Is loader likely responsible? False

## 8. Stage10D.1 Assumption Audit
- Stage10D.1 assumed owner channels as absolute player channels (owner_player1 at index 3).
- Unity ObservationBuilder in UnityMvpTransfer path documents owner as neutral/friendly/enemy.
- Therefore Stage10D.1 owner-channel interpretation is potentially stale/wrong for the inspected runtime path.
- OBSERVATION_ENCODING_MISMATCH remains plausible, but its Stage10D.1 explanation must be corrected to source-of-truth owner semantics before remediation.

## 9. Root-Cause Classification
- primary: STAGE10D1_DIAGNOSTIC_CHANNEL_ASSUMPTION_ERROR
- secondary: CONTRACT_DOCUMENTATION_STALE_BUT_ARTIFACT_VALID, UNITY_OBSERVATION_CHANNEL_MAPPING_ERROR

## 10. Patch Plan
- If adapter is wrong: patch adapter channel semantics/naming or mapping, regenerate adapted dataset, rerun validation, rebuild BC-ready dataset, retrain BC student from corrected data.
- If Unity ObservationBuilder is wrong: patch ObservationBuilder owner/channel mapping or mode usage, rerun Unity snapshot, rerun Stage10R/10D.1.
- If loader is wrong: patch student_bc_loader reshape/layout path, rerun loader dry-run and checkpoint inference dry-run, then reassess retraining need.
- If Stage10D.1 diagnostics were wrong: patch Stage10D.1 channel assumptions and rerun Stage10D.1 before model/data changes.
- If docs are stale but artifacts are valid: update docs/spec only; do not retrain solely due to stale docs.
- If perspective encoding mismatch is real: define canonical perspective semantics and align adapter/Unity documentation and validation before retraining.

## 11. Gate Decision
- GO_FOR_STAGE10D1_DIAGNOSTIC_FIX_AND_RERUN

## 12. Explicit Non-Claims
- This report does not prove semantic parity between Gym-μRTS and Unity.
- This report does not claim direct weight transfer.
- This report does not validate final tactical behavior.
- This report does not authorize PPO or teacher retraining.
- This report does not change ActionApplier/MatchManager runtime semantics.
