# LEGACY032 UNITY V2 STAGE10R NOOP COLLAPSE ANALYSIS REPORT

Generated at: 2026-05-02T14:57:17.643343+00:00
Snapshot source: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json

## 1) Scope
- NoOp collapse analysis only.
- No training.
- No PPO.
- No checkpoint changes.
- No dataset changes.
- No runtime semantic changes.

## 2) Input context
- Scene path: Assets/Scenes/Week6_StudentVisualInspection.unity
- Checkpoint path: python/week6_student/runs/legacy032_v2_bc_minimal_20260501T195501Z/student_bc_transfer_best.pt
- Controlled player: Player1
- Focus cells: B2 (flat 25), C3 (flat 50)
- Contract branch sizes: [6,4,4,4,4,7,49]

## 3) Bridge diagnostic extension
- Added debug payload with focus-cell action_type logits/probabilities/top3 and branch argmax values.
- Added own-actor action_type summary with top1/top2 and NoOp margin.
- Added focus-cell 27-channel observation slices.
- Added flatten and observation-vs-BC expectation checks.
- Inference behavior changed: no (argmax path unchanged).

## 4) Focus cell diagnostics
| Cell | GridPosition | Flat | Unit | Owner | Eligible | Predicted | Top-3 | NoOp p | Best non-NoOp p | NoOp margin | Command built | Reason |
|---|---|---:|---|---|---|---|---|---:|---:|---:|---|---|
| B2 | (1,1) | 25 | Worker | Player1 | True | NoOp | NoOp(0, p=1.0000) > Produce(4, p=0.0000) > Harvest(2, p=0.0000) | 1.0000 | 0.0000 | 1.0000 | False | predicted_noop |
| C3 | (2,2) | 50 | Base | Player1 | True | NoOp | NoOp(0, p=1.0000) > Produce(4, p=0.0000) > Harvest(2, p=0.0000) | 1.0000 | 0.0000 | 1.0000 | False | predicted_noop |

## 5) Observation channel verification
### B2
- 00 hit_points: 1.000000
- 03 owner_player1: 1.000000
- 08 unit_worker: 1.000000
- 12 action_noop: 1.000000
- 20 dir_south: 1.000000
### C3
- 00 hit_points: 1.000000
- 03 owner_player1: 1.000000
- 06 unit_base: 1.000000
- 12 action_noop: 1.000000
- 20 dir_south: 1.000000

## 6) Flatten/cell alignment check
- Formula: row * 24 + col
- B2 formula check: expected=25, actual=25, pass=True
- C3 formula check: expected=50, actual=50, pass=True
- B2 observation unit alignment: expected=Worker, actual=Worker, pass=True
- C3 observation unit alignment: expected=Base, actual=Base, pass=True
- B2 predicted row alignment: pass=True
- C3 predicted row alignment: pass=True
- bridge::B2_flat_formula: pass=True, expected=25, actual=25
- bridge::B2_unit_type_alignment: pass=True, expected=Worker, actual=Worker
- bridge::C3_flat_formula: pass=True, expected=50, actual=50
- bridge::C3_unit_type_alignment: pass=True, expected=Base, actual=Base

## 7) Offline/bridge consistency check
- status: not_implemented

## 8) Root cause classification
- MODEL_CONFIDENT_NOOP_ON_UNITY_OBSERVATION

## 9) Interpretation
- This report evaluates observation->logits->action_type argmax diagnostics only.
- It does not claim transfer success, semantic parity proof, or behavior quality proof.
- Observation-vs-BC expectation summary:
  - B2: unit=Worker, owner=Player1, unitChannelOk=True, ownerChannelOk=True, suspicious=False
  - C3: unit=Base, owner=Player1, unitChannelOk=True, ownerChannelOk=True, suspicious=False
- Own actor summary:
  - flat=25 B2: top1=NoOp (1.0000), top2=Produce (0.0000), noop_margin=1.0000
  - flat=50 C3: top1=NoOp (1.0000), top2=Produce (0.0000), noop_margin=1.0000

## 10) Decision
- GO_FOR_MODEL_DATA_REMEDIATION
