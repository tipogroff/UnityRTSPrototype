# LEGACY032 UNITY V2 CHECKPOINT INFERENCE DRY-RUN REPORT

## 1) Scope
- checkpoint load / inference dry-run only
- no Unity scene run
- no Unity match
- no training
- no PPO
- no dataset modification
- no behavior quality proof
- no semantic parity claim
- no direct weight transfer claim

## 2) Input checkpoint
- checkpoint path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week6_student\runs\legacy032_v2_bc_smoke_20260501T181043Z\student_bc_transfer_best.pt
- epoch: 2
- model_variant: transfer
- training run dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week6_student\runs\legacy032_v2_bc_smoke_20260501T181043Z
- source dataset path from config: python\week5_teacher_legacy032\teacher_exports_bc\day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z
- source dataset path matches canonical: True
- checkpoint is old day3_transfer_bc_main_20260423: False
- metrics summary from checkpoint: {"train_total_loss": 0.0005923862235323872, "val_total_loss": 0.0005223389357535017, "train_action_type_accuracy": 0.9999980076653916, "val_action_type_accuracy": 0.999999474900231}

## 3) Contract verification
- expected branch sizes: [6, 4, 4, 4, 4, 7, 49]
- actual branch head sizes: {"action_type_logits": 6, "move_dir_logits": 4, "harvest_dir_logits": 4, "return_dir_logits": 4, "produce_dir_logits": 4, "produce_unit_type_logits": 7, "attack_target_local_logits": 49}
- expected model input shape: [24,24,27]
- actual batch input shape: [8, 24, 24, 27]
- source BC-ready observation shape: [13225, 576, 27]
- target shape: [8, 576, 7]
- expected logits shapes: {"action_type_logits": [8, 576, 6], "move_dir_logits": [8, 576, 4], "harvest_dir_logits": [8, 576, 4], "return_dir_logits": [8, 576, 4], "produce_dir_logits": [8, 576, 4], "produce_unit_type_logits": [8, 576, 7], "attack_target_local_logits": [8, 576, 49]}
- actual logits shapes: {"action_type_logits": [8, 576, 6], "move_dir_logits": [8, 576, 4], "harvest_dir_logits": [8, 576, 4], "return_dir_logits": [8, 576, 4], "produce_dir_logits": [8, 576, 4], "produce_unit_type_logits": [8, 576, 7], "attack_target_local_logits": [8, 576, 49]}

## 4) Load result
- strict load pass/fail: PASS
- missing keys: []
- unexpected keys: []
- strict=False needed: no (strict=True passed with exact key match)
- device used: cpu
- dtype notes: input=float32, predicted_actions=torch.int64, checkpoint tensors loaded on cpu

## 5) Forward/inference result
- batch size: 8
- logits finite yes/no: yes
- predicted action tensor shape: [8, 576, 7]
- predicted action tensor dtype: torch.int64
- predicted action branch bounds: {"action_type": {"min": 0, "max": 4, "branch_size": 6, "in_bounds": true}, "move_dir": {"min": 0, "max": 3, "branch_size": 4, "in_bounds": true}, "harvest_dir": {"min": 0, "max": 3, "branch_size": 4, "in_bounds": true}, "return_dir": {"min": 0, "max": 3, "branch_size": 4, "in_bounds": true}, "produce_dir": {"min": 0, "max": 3, "branch_size": 4, "in_bounds": true}, "produce_unit_type": {"min": 1, "max": 5, "branch_size": 7, "in_bounds": true}, "attack_target_local": {"min": 3, "max": 45, "branch_size": 49, "in_bounds": true}}
- action_type histogram: {"0": 4592, "2": 8, "4": 8}
- produce_unit_type histogram: {"1": 6, "2": 144, "3": 4426, "5": 32}
- attack_target_local histogram: {"3": 31, "6": 1, "7": 16, "17": 8, "19": 136, "25": 1257, "29": 22, "31": 177, "38": 2474, "44": 461, "45": 25}

## 6) Adapter readiness
- student_inference_adapter compatible: yes
- Unity scene required for this step: no
- checkpoint suitable for next Unity-side dry-run config: yes

## 7) Known limitations
- checkpoint is smoke-trained only
- does not prove behavior quality
- does not prove Unity runtime compatibility
- does not prove Gym-Unity semantic parity
- teacher/data are NoOp-dominant
- scene Inspector wiring remains unchecked

## 8) Decision
- GO_FOR_MINIMAL_BC_TRAINING_OR_UNITY_SCENE_PREP
