# LEGACY032 UNITY V2 Stage 10 Unity Scene Dry-Run Report

Generated at: 2026-05-03T15:19:20.5075441Z

## 1. Scope
- Controlled Unity scene dry-run only.
- No PPO fine-tune.
- No teacher training.
- No dataset modification.
- No checkpoint modification.
- No semantic parity claim.
- No behavior quality proof.

## 2. Scene and checkpoint
- Scene path: Assets/Scenes/Week6_StudentVisualInspection.unity
- Scene name: Week6_StudentVisualInspection
- Scenario preset: 4
- Map size: 24x24
- Active checkpoint path: python/week6_student/runs/legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z/student_bc_stage10d14_augmented_best.pt
- Checkpoint exists: True
- Active runner/component: Week6VisualInspectionRunner
- Manual trigger mode: True
- EpisodeController auto-start: False
- Visual runner auto-start: False
- Device/backend: cpu
- Initial placement summary:
  - Neutral Resource @ (0,0)
  - Neutral Resource @ (1,0)
  - Neutral Resource @ (22,23)
  - Neutral Resource @ (23,23)
  - Player1 Base @ (2,2)
  - Player1 Worker @ (1,1)
  - Player2 Base @ (21,21)
  - Player2 Worker @ (22,22)

## 3. Preflight results
- Scene readiness:
  - PASS: Scenario preset = 4 (expected 4).
  - PASS: EpisodeController auto-start = False.
  - PASS: Week6VisualInspectionRunner auto-start = False.
  - PASS: Week6 student match control enabled = True.
  - PASS: Player1 mode = StudentInference.
  - PASS: Player2 mode = HeuristicBaseline.
  - PASS: Active Week6VisualInspectionRunner count = 1.
  - PASS: Active Week6StudentPolicyAdapter count = 1.
  - PASS: Active EpisodeController count = 1.
  - PASS: Active HeuristicPolicyAdapter count = 1.
  - PASS: Active checkpoint path = python/week6_student/runs/legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z/student_bc_stage10d14_augmented_best.pt.
  - PASS: Checkpoint exists = True.
  - PASS: Duplicate occupancy count = 0.
  - PASS: Observation shape = [24,24,27] (expected 24,24,27).
  - PASS: Observation NaN = False, Inf = False.
  - PASS: Artifact directory = python/week6_student/tmp/day5_sanity.
  - PASS: Artifact file prefix = day5_sanity.
  - PASS: Successful bridge requests = 200.
  - PASS: Step count advanced = True.
  - PASS: ActionApplier reached = True.
  - PASS: MatchManager.ApplyCommand path reached = True.
  - PASS: Meaningful accepted commands = 11.
  - PASS: NoOp share = 0.00 %.
  - PASS: Wrong-owner rejections after filter = 0.
  - PASS: Runtime rejected commands = 0.
  - PASS: Model output logits shapes captured = True.
  - PASS: Branch sizes = [6, 4, 4, 4, 4, 7, 49].
- Runtime object counts:
  - Week6VisualInspectionRunner: 1
  - Week6StudentPolicyAdapter: 1
  - EpisodeController: 1
  - HeuristicPolicyAdapter: 1
- Week6 control modes: enableStudentMatchControl=True, Player1=StudentInference, Player2=HeuristicBaseline
- Duplicate occupancy count: 0

## 4. Runtime load result
- Model loaded: yes
- Decision requests sent/succeeded/failed: 200/200/0
- Bridge shutdown clean: False
- Last bridge/runtime error: none
- Checkpoint metadata:
  - Checkpoint model variant: unknown
  - Checkpoint epoch: 1
  - Action contract version: v2_gridnet_compatible

## 5. Observation/inference result
- Observation shape: [24,24,27]
- Observation element count: 15552
- Observation min/max: 0.000000 / 1.000000
- Observation NaN/Inf: False / False
- Observation validation: True
- Controlled player id: Player1
- Own units / enemy units / resources: 2 / 2 / 4
- Global vector length in package: 7
- Strict BC path fed global vector into model: no (adapter writes SpatialObservation only).
- Model input shape: [24, 24, 27]
- Predicted action tensor shape: [576, 7]
- Flattened action payload size: 44928
- Branch sizes: [6, 4, 4, 4, 4, 7, 49]
- Logits shapes:
  - action_type_logits: [1, 576, 6]
  - move_dir_logits: [1, 576, 4]
  - harvest_dir_logits: [1, 576, 4]
  - return_dir_logits: [1, 576, 4]
  - produce_dir_logits: [1, 576, 4]
  - produce_unit_type_logits: [1, 576, 7]
  - attack_target_local_logits: [1, 576, 49]
- Branch bounds (first captured adapter artifact):
  - action_type: min=0, max=4
  - move_dir: min=0, max=3
  - harvest_dir: min=0, max=3
  - return_dir: min=0, max=2
  - produce_dir: min=2, max=3
  - produce_unit_type: min=2, max=3
  - attack_target_local: min=0, max=0

## 6. Decoder/applier result
- Decoded command sample:
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(2, 2) type=Produce dir=South produce=Ranged source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(2, 2) type=Produce dir=South produce=Ranged source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(2, 2) type=Produce dir=South produce=Ranged source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(2, 2) type=Produce dir=South produce=Ranged source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 2) type=Produce dir=South produce=Ranged source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(2, 2) type=Produce dir=South produce=Ranged source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 2) type=Produce dir=South produce=Ranged source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(2, 2) type=Produce dir=South produce=Ranged source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
- First non-NoOp decoded commands:
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(2, 2) type=Produce dir=South produce=Ranged source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(2, 2) type=Produce dir=South produce=Ranged source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(2, 2) type=Produce dir=South produce=Ranged source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(1, 1) type=Harvest dir=West source=TransferCompatible
  [AgentAction] actor=(2, 2) type=Produce dir=South produce=Ranged source=TransferCompatible
- Accepted command samples:
  owner=Player1 actor=(2,2) type=Produce dir=South produce=Worker
  owner=Player1 actor=(2,2) type=Produce dir=South produce=Worker
  owner=Player1 actor=(2,2) type=Produce dir=South produce=Worker
  owner=Player1 actor=(2,2) type=Produce dir=South produce=Worker
  owner=Player1 actor=(2,2) type=Produce dir=South produce=Worker
  owner=Player1 actor=(2,2) type=Produce dir=South produce=Worker
  owner=Player1 actor=(2,2) type=Produce dir=South produce=Worker
  owner=Player1 actor=(2,2) type=Produce dir=South produce=Worker
  owner=Player1 actor=(2,2) type=Produce dir=South produce=Worker
  owner=Player1 actor=(2,2) type=Produce dir=South produce=Worker
  owner=Player1 actor=(2,2) type=Produce dir=South produce=Worker
- Rejected command samples:
  - none
- Accepted command count: 11
- Rejected command count: 211
- Ignored command count: 0
- Invalid share: 95.05 %
- Ignored share: 0.00 %
- Rejection reason histogram:
  - other: 211
- Runtime rejection reason histogram:
  - none
- ActionApplier called: True
- MatchManager.ApplyCommand called: True

## 7. Episode/bounded run summary
- Episodes run: 1
- Max steps configured: 200
- Steps actually run: 200
- MatchManager.AdvanceStep called: True
- Step count advanced: True
- Episode reached terminal: False
- Stop reason: bounded_step_cap_200

## 8. Action statistics
- Aggregate action_type histogram: NoOp=0, Move=0, Harvest=200, Return=0, Produce=22, Attack=0
- Aggregate pre-mask action_type histogram: NoOp=0, Move=0, Harvest=365, Return=0, Produce=208, Attack=0
- First steps action histograms:
  step=1 NoOp=0, Move=0, Harvest=1, Return=0, Produce=1, Attack=0 accepted=1 rejected=1
  step=2 NoOp=0, Move=0, Harvest=1, Return=0, Produce=0, Attack=0 accepted=0 rejected=1
  step=3 NoOp=0, Move=0, Harvest=1, Return=0, Produce=0, Attack=0 accepted=0 rejected=1
  step=4 NoOp=0, Move=0, Harvest=1, Return=0, Produce=0, Attack=0 accepted=0 rejected=1
  step=5 NoOp=0, Move=0, Harvest=1, Return=0, Produce=0, Attack=0 accepted=0 rejected=1
  step=6 NoOp=0, Move=0, Harvest=1, Return=0, Produce=1, Attack=0 accepted=1 rejected=1
  step=7 NoOp=0, Move=0, Harvest=1, Return=0, Produce=0, Attack=0 accepted=0 rejected=1
  step=8 NoOp=0, Move=0, Harvest=1, Return=0, Produce=0, Attack=0 accepted=0 rejected=1
  step=9 NoOp=0, Move=0, Harvest=1, Return=0, Produce=0, Attack=0 accepted=0 rejected=1
  step=10 NoOp=0, Move=0, Harvest=1, Return=0, Produce=0, Attack=0 accepted=0 rejected=1
  step=11 NoOp=0, Move=0, Harvest=1, Return=0, Produce=1, Attack=0 accepted=1 rejected=1
  step=12 NoOp=0, Move=0, Harvest=1, Return=0, Produce=0, Attack=0 accepted=0 rejected=1
  step=13 NoOp=0, Move=0, Harvest=1, Return=0, Produce=0, Attack=0 accepted=0 rejected=1
  step=14 NoOp=0, Move=0, Harvest=1, Return=0, Produce=0, Attack=0 accepted=0 rejected=1
  step=15 NoOp=0, Move=0, Harvest=1, Return=0, Produce=0, Attack=0 accepted=0 rejected=1
  step=16 NoOp=0, Move=0, Harvest=1, Return=0, Produce=1, Attack=0 accepted=1 rejected=1
  step=17 NoOp=0, Move=0, Harvest=1, Return=0, Produce=1, Attack=0 accepted=0 rejected=2
  step=18 NoOp=0, Move=0, Harvest=1, Return=0, Produce=0, Attack=0 accepted=0 rejected=1
  step=19 NoOp=0, Move=0, Harvest=1, Return=0, Produce=0, Attack=0 accepted=0 rejected=1
  step=20 NoOp=0, Move=0, Harvest=1, Return=0, Produce=0, Attack=0 accepted=0 rejected=1
- NoOp share: 0.00 %
- Non-NoOp share: 100.00 %
- Move / Harvest / Return counts: 0 / 200 / 0
- Produce count/share: 22 / 9.91 %
- Attack count/share: 0 / 0.00 %
- Commands built after filter: 222
- Commands submitted after filter: 222
- Candidate cells / eligible own actor cells: 115200 / 1436
- Wrong-owner rejections after filter: 0
- Masked-out action-type choices / fallback-to-NoOp: 351 / 351

## 9. Key findings
  - PASS: Scenario preset = 4 (expected 4).
  - PASS: EpisodeController auto-start = False.
  - PASS: Week6VisualInspectionRunner auto-start = False.
  - PASS: Week6 student match control enabled = True.
  - PASS: Player1 mode = StudentInference.
  - PASS: Player2 mode = HeuristicBaseline.
  - PASS: Active Week6VisualInspectionRunner count = 1.
  - PASS: Active Week6StudentPolicyAdapter count = 1.
  - PASS: Active EpisodeController count = 1.
  - PASS: Active HeuristicPolicyAdapter count = 1.
  - PASS: Active checkpoint path = python/week6_student/runs/legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z/student_bc_stage10d14_augmented_best.pt.
  - PASS: Checkpoint exists = True.
  - PASS: Duplicate occupancy count = 0.
  - PASS: Observation shape = [24,24,27] (expected 24,24,27).
  - PASS: Observation NaN = False, Inf = False.
  - PASS: Artifact directory = python/week6_student/tmp/day5_sanity.
  - PASS: Artifact file prefix = day5_sanity.
  - PASS: Successful bridge requests = 200.
  - PASS: Step count advanced = True.
  - PASS: ActionApplier reached = True.
  - PASS: MatchManager.ApplyCommand path reached = True.
  - PASS: Meaningful accepted commands = 11.
  - PASS: NoOp share = 0.00 %.
  - PASS: Wrong-owner rejections after filter = 0.
  - PASS: Runtime rejected commands = 0.
  - PASS: Model output logits shapes captured = True.
  - PASS: Branch sizes = [6, 4, 4, 4, 4, 7, 49].

## 10. Interpretation limits
- This dry-run does not prove behavior quality.
- This dry-run does not prove Gym-microRTS to Unity semantic parity.
- This dry-run does not prove final transfer success.
- The checkpoint is BC-only.
- NoOp dominance may still reflect dataset bias or runtime mismatch.
- Unity runtime semantic drift remains possible even if the technical path executes.

## 11. Decision
- GO_FOR_EXECUTION_SEMANTICS_ANALYSIS
