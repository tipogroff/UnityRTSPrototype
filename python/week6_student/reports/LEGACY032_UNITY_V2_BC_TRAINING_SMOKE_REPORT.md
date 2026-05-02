# Legacy032 Unity V2 — Week 6 BC Training Smoke Report

Generated at: 2026-05-02 (UTC context)

## 1) Smoke Scope

- supervised BC only
- no RL / PPO fine-tune
- no Unity scene run
- no behavior-quality proof
- no semantic parity claim (Gym vs Unity)
- no direct weight transfer claim

## 2) Command Used

Full command executed:

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/.venv/Scripts/python.exe \
  python/week6_student/train_student_bc_minimal.py \
  --bc-ready-dir python/week5_teacher_legacy032/teacher_exports_bc/day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z \
  --model-variant transfer \
  --epochs 3 \
  --batch-size 32 \
  --device cpu \
  --output-dir python/week6_student/runs/legacy032_v2_bc_smoke_20260501T181043Z
```

Run parameters:

- device: `cpu`
- epochs: `3`
- batch size: `32`
- output dir: `python/week6_student/runs/legacy032_v2_bc_smoke_20260501T181043Z`

## 3) Dataset Contract Confirmation

Dataset path:

- `python/week5_teacher_legacy032/teacher_exports_bc/day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z`

Manifest confirmation:

- `target_action_contract = unity_v2_legacy032_gridnet` (PASS)
- `observation_shape_per_sample = [576,27]` (PASS)
- `action_shape_per_sample = [576,7]` (PASS)
- `branch_sizes = [6,4,4,4,4,7,49]` (PASS)
- `direct_weight_transfer_claim = false` (PASS)
- `semantic_parity_claim = false` (PASS)

## 4) Preflight Result

Preflight checks were executed before training.

- environment import (`torch`, `numpy`): PASS
- dataset files present:
  - `bc_manifest.json`: PASS
  - `bc_train.npz`: PASS
  - `bc_validation.npz`: PASS
- manifest safety checks: PASS (all required fields matched)
- first batch shape:
  - input: `[2,24,24,27]`
  - target: `[2,576,7]`
- logits shapes:
  - `action_type_logits`: `[2,576,6]`
  - `move_dir_logits`: `[2,576,4]`
  - `harvest_dir_logits`: `[2,576,4]`
  - `return_dir_logits`: `[2,576,4]`
  - `produce_dir_logits`: `[2,576,4]`
  - `produce_unit_type_logits`: `[2,576,7]`
  - `attack_target_local_logits`: `[2,576,49]`
- branch-wise loss computation: PASS
- `total_loss` finite: PASS (`1.7720415592`)

Preflight artifact:

- `python/week6_student/reports/legacy032_v2_preflight_result.json`

## 5) Training Result

Status: **PASS**

- epochs completed: `3/3`
- final `train_total_loss`: `0.0005395199`
- final `val_total_loss`: `0.0006088145`

Final epoch branch-wise losses/accuracies:

- train:
  - action_type: loss `0.0000231556`, acc `0.9999981930`
  - move_dir: loss `0.0`, acc `0.0` (active_count=0)
  - harvest_dir: loss `0.0000000176`, acc `1.0`
  - return_dir: loss `0.0`, acc `0.0` (active_count=0)
  - produce_dir: loss `0.3004061797`, acc `0.8920649839`
  - produce_unit_type: loss `0.0000193345`, acc `1.0`
  - attack_target_local: loss `0.4087479010`, acc `0.8780487805`
- val:
  - action_type: loss `0.0000051155`, acc `1.0`
  - move_dir: loss `0.0`, acc `0.0` (active_count=0)
  - harvest_dir: loss `0.0000000087`, acc `1.0`
  - return_dir: loss `0.0`, acc `0.0` (active_count=0)
  - produce_dir: loss `0.3510520739`, acc `0.8951006457`
  - produce_unit_type: loss `0.0000002049`, acc `1.0`
  - attack_target_local: loss `0.0822143505`, acc `1.0`

Stability checks:

- NaN/Inf detected: **NO**
- cross_entropy / index errors: **NO**

Artifacts created:

- `python/week6_student/runs/legacy032_v2_bc_smoke_20260501T181043Z/student_bc_transfer_latest.pt`
- `python/week6_student/runs/legacy032_v2_bc_smoke_20260501T181043Z/student_bc_transfer_best.pt`
- `python/week6_student/runs/legacy032_v2_bc_smoke_20260501T181043Z/day2_minimal_metrics_history.json`

## 6) Known Interpretation Limits

- smoke does not prove behavior quality
- smoke does not prove Unity runtime compatibility
- smoke does not prove Gym-Unity semantic parity
- NoOp-dominant teacher data may produce NoOp-dominant student
- Unity scene remains unverified until scene dry-run

## 7) Decision

**GO_FOR_CHECKPOINT_EXPORT_DRY_RUN**

Rationale:

- preflight passed (env + dataset files + manifest + first-batch forward + finite loss)
- smoke training completed without crashes
- expected checkpoint and metrics artifacts were produced
- no forbidden actions were executed (no Unity scene, no PPO, no teacher training, no dataset rewrite)
