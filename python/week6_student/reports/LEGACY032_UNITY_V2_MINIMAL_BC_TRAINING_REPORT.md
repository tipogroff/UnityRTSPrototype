# LEGACY032 UNITY V2 MINIMAL BC TRAINING REPORT

## 1. Scope
- supervised BC only
- no Unity scene
- no Unity match
- no PPO
- no teacher retraining
- no dataset modification
- no direct weight transfer claim
- no semantic parity claim
- no behavior quality proof

## 2. Command used
- full command: python python/week6_student/train_student_bc_minimal.py --bc-ready-dir python/week5_teacher_legacy032/teacher_exports_bc/day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z --model-variant transfer --epochs 20 --batch-size 32 --device cpu --output-dir python/week6_student/runs/legacy032_v2_bc_minimal_20260501T195501Z
- device: cpu
- epochs: 20
- batch size: 32
- output directory: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week6_student\runs\legacy032_v2_bc_minimal_20260501T195501Z

## 3. Dataset contract
- dataset path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_exports_bc\day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z
- target_action_contract: unity_v2_legacy032_gridnet
- BC-ready observations: [N,576,27]
- model input after loader reshape: [N,24,24,27]
- actions: [N,576,7]
- branch sizes: [6,4,4,4,4,7,49]
- direct_weight_transfer_claim: false
- semantic_parity_claim: false

## 4. Training results
- status: PASS
- epochs completed: 20/20
- final train_total_loss: 0.0004747612033489676
- final val_total_loss: 0.0006088157636729194
- best epoch (by val_total_loss): 15
- NaN/Inf status: no
- cross_entropy/index error status: no
- final branch-wise metrics (train/val + active_count where applicable):
{
  "train_action_type_loss": 4.7318366826909736e-07,
  "train_action_type_accuracy": 0.9999998841665926,
  "train_action_type_active_count": 43165440,
  "train_move_dir_loss": 0.0,
  "train_move_dir_accuracy": 0.0,
  "train_move_dir_active_count": 0,
  "train_harvest_dir_loss": 1.1661234507199657e-08,
  "train_harvest_dir_accuracy": 1.0,
  "train_harvest_dir_active_count": 73600,
  "train_return_dir_loss": 0.0,
  "train_return_dir_accuracy": 0.0,
  "train_return_dir_active_count": 0,
  "train_produce_dir_loss": 0.27623830635248653,
  "train_produce_dir_accuracy": 0.892749731471536,
  "train_produce_dir_active_count": 74480,
  "train_produce_unit_type_loss": 1.1504609334696426e-08,
  "train_produce_unit_type_accuracy": 1.0,
  "train_produce_unit_type_active_count": 74480,
  "train_attack_target_local_loss": 0.052709179036433275,
  "train_attack_target_local_accuracy": 1.0,
  "train_attack_target_local_active_count": 82,
  "train_total_loss": 0.0004747612033489676,
  "val_action_type_loss": 2.8255496966893905e-07,
  "val_action_type_accuracy": 0.9999998687250578,
  "val_action_type_active_count": 7617600,
  "val_move_dir_loss": 0.0,
  "val_move_dir_accuracy": 0.0,
  "val_move_dir_active_count": 0,
  "val_harvest_dir_loss": 6.985275528739507e-10,
  "val_harvest_dir_accuracy": 1.0,
  "val_harvest_dir_active_count": 12970,
  "val_return_dir_loss": 0.0,
  "val_return_dir_accuracy": 0.0,
  "val_return_dir_active_count": 0,
  "val_produce_dir_loss": 0.3539302775079524,
  "val_produce_dir_accuracy": 0.8951766046334979,
  "val_produce_dir_active_count": 13165,
  "val_produce_unit_type_loss": 3.169251558913128e-10,
  "val_produce_unit_type_accuracy": 1.0,
  "val_produce_unit_type_active_count": 13165,
  "val_attack_target_local_loss": 0.00037104985340892407,
  "val_attack_target_local_accuracy": 1.0,
  "val_attack_target_local_active_count": 13,
  "val_total_loss": 0.0006088157636729194
}

## 5. Checkpoint artifacts
- best checkpoint path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week6_student\runs\legacy032_v2_bc_minimal_20260501T195501Z\student_bc_transfer_best.pt
- latest checkpoint path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week6_student\runs\legacy032_v2_bc_minimal_20260501T195501Z\student_bc_transfer_latest.pt
- metrics history path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week6_student\runs\legacy032_v2_bc_minimal_20260501T195501Z\day2_minimal_metrics_history.json
- checkpoint epoch: 15
- checkpoint model_variant: transfer
- checkpoint source dataset path: python\week5_teacher_legacy032\teacher_exports_bc\day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z

## 6. Post-training checkpoint dry-run
- strict load result: PASS
- missing keys: []
- unexpected keys: []
- logits shapes: {"action_type_logits": [32, 576, 6], "move_dir_logits": [32, 576, 4], "harvest_dir_logits": [32, 576, 4], "return_dir_logits": [32, 576, 4], "produce_dir_logits": [32, 576, 4], "produce_unit_type_logits": [32, 576, 7], "attack_target_local_logits": [32, 576, 49]}
- predicted action tensor shape: [32, 576, 7]
- predicted action tensor dtype: torch.int64
- branch bounds result: {"action_type": {"min": 0, "max": 4, "branch_size": 6, "in_bounds": true}, "move_dir": {"min": 0, "max": 3, "branch_size": 4, "in_bounds": true}, "harvest_dir": {"min": 0, "max": 3, "branch_size": 4, "in_bounds": true}, "return_dir": {"min": 0, "max": 3, "branch_size": 4, "in_bounds": true}, "produce_dir": {"min": 0, "max": 3, "branch_size": 4, "in_bounds": true}, "produce_unit_type": {"min": 1, "max": 5, "branch_size": 7, "in_bounds": true}, "attack_target_local": {"min": 6, "max": 48, "branch_size": 49, "in_bounds": true}}
- action_type histogram: {"0": 18368, "2": 32, "4": 32}
- produce_unit_type histogram: {"1": 141, "3": 18276, "5": 15}
- attack_target_local histogram: {"6": 2, "17": 113, "19": 5, "22": 5642, "25": 6043, "29": 544, "31": 238, "36": 9, "38": 5431, "48": 405}

## 7. Interpretation limits
- checkpoint is BC-only
- does not prove Unity behavior quality
- does not prove Unity runtime compatibility
- does not prove semantic parity
- teacher/data are NoOp-dominant
- scene Inspector wiring remains unchecked

## 8. Decision
- GO_FOR_UNITY_SCENE_PREP
