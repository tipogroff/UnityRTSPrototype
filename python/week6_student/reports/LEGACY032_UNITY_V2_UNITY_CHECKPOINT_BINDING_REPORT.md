# LEGACY032 UNITY V2 UNITY CHECKPOINT BINDING REPORT

## 1) Scope
- Unity-side checkpoint binding verification only.
- No Unity scene run.
- No Play Mode run.
- No match run.
- No BC training.
- No PPO fine-tune.
- No teacher training continuation.
- No dataset/checkpoint modification.
- No runtime semantic changes (ActionApplier/MatchManager untouched).

## 2) Target checkpoint
- expected checkpoint path: `python/week6_student/runs/legacy032_v2_bc_minimal_20260501T195501Z/student_bc_transfer_best.pt`
- exists: yes
- model variant: transfer
- source training run: `python/week6_student/runs/legacy032_v2_bc_minimal_20260501T195501Z`
- relation to Stage 7 report: matches `LEGACY032_UNITY_V2_MINIMAL_BC_TRAINING_REPORT.md` as Stage 7 best checkpoint

Contract/metadata verification source:
- checkpoint payload `config.model_variant = transfer`
- source BC manifest: `python/week5_teacher_legacy032/teacher_exports_bc/day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z/bc_manifest.json`
- `target_action_contract = unity_v2_legacy032_gridnet`
- `branch_sizes = [6,4,4,4,4,7,49]`
- `direct_weight_transfer_claim = false`
- `semantic_parity_claim = false`

## 3) Binding source
Primary active binding (target scene):
- file/component/field: `Assets/Scenes/Week6_StudentVisualInspection.unity` -> `Week6StudentPolicyAdapter` -> `_checkpointRelativePath`
- binding type: serialized scene field (Inspector-serialized YAML value)

Additional sources checked:
- `Assets/Scripts/ML/Week6StudentPolicyAdapter.cs`: hardcoded default `_checkpointRelativePath`
- `Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs`: hardcoded default `_checkpointRelativePath`
- `Assets/Scripts/ML/ActionContractV2GlobalSmokeRunner.cs`: fallback default used by smoke helper reflection read
- `python/week6_student/checkpoint_inference_config.json` (root): not present
- `python/week6_student/student_inference_adapter.py`: checkpoint path is CLI argument, not hardcoded
- `python/week6_student/load_student_checkpoint.py`: loads path passed at runtime, not hardcoded

## 4) Changes made
1. `Assets/Scenes/Week6_StudentVisualInspection.unity`
- old value: `python/week6_student/runs/day3_transfer_bc_main_20260423/student_bc_transfer_best.pt`
- new value: `python/week6_student/runs/legacy032_v2_bc_minimal_20260501T195501Z/student_bc_transfer_best.pt`
- reason: active visual inspection scene was still bound to old day3 checkpoint

2. `Assets/Scripts/ML/Week6StudentPolicyAdapter.cs`
- old value: `python/week6_student/runs/day3_transfer_bc_main_20260423/student_bc_transfer_best.pt`
- new value: `python/week6_student/runs/legacy032_v2_bc_minimal_20260501T195501Z/student_bc_transfer_best.pt`
- reason: align script default with Stage 7 best checkpoint

3. `Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs`
- old value: `python/week6_student/runs/day3_transfer_bc_main_20260423/student_bc_transfer_best.pt`
- new value: `python/week6_student/runs/legacy032_v2_bc_minimal_20260501T195501Z/student_bc_transfer_best.pt`
- reason: avoid stale fallback in Day4 wiring/dry-run component

4. `Assets/Scripts/ML/ActionContractV2GlobalSmokeRunner.cs`
- old value: `python/week6_student/runs/day3_transfer_bc_main_20260423/student_bc_transfer_best.pt`
- new value: `python/week6_student/runs/legacy032_v2_bc_minimal_20260501T195501Z/student_bc_transfer_best.pt`
- reason: keep smoke helper fallback consistent with current Stage 7 binding baseline

## 5) Stale reference scan
Searched terms:
- `day3_transfer_bc_main_20260423`
- `legacy032_v2_bc_smoke_20260501T181043Z`
- `student_bc_transfer_best.pt`
- `student_bc_transfer_latest.pt`
- `checkpoint`, `checkpointPath`, `modelPath`, `inferenceConfig`

Results:
- `day3_transfer_bc_main_20260423`: found, inactive/historical (not active in target scene primary binding)
  - inactive other scenes: `Assets/Scenes/GameScene.unity`, `Assets/Scenes/Week6_StudentSanity.unity`
  - historical: `Assets/_Recovery/0.unity`, historical reports, `python/week6_student/tmp/day4_unity_playmode_smoke_report.json`
- `legacy032_v2_bc_smoke_20260501T181043Z`: found, inactive/historical
  - historical reports and run artifacts under `python/week6_student/runs/legacy032_v2_bc_smoke_20260501T181043Z`
  - not active as primary model in target scene
- v1/non-Legacy032 references: found only as historical/inactive artifacts and documentation context; not active in target scene binding

## 6) Static validation result
Validation script:
- `python/week6_student/validate_unity_checkpoint_binding.py`

Output artifact:
- `python/week6_student/reports/LEGACY032_UNITY_V2_UNITY_CHECKPOINT_BINDING_VALIDATION.json`

Checks:
- checkpoint path points to Stage 7 best checkpoint: PASS
- checkpoint file exists: PASS
- model variant transfer: PASS
- contract metadata verified via source BC manifest: PASS
  - `target_action_contract = unity_v2_legacy032_gridnet`
  - `branch_sizes = [6,4,4,4,4,7,49]`
  - `direct_weight_transfer_claim = false`
  - `semantic_parity_claim = false`
- scene preset still Stage 9 microRTS-like symmetric preset (`_scenarioPreset = 4`): PASS
- visual runner autostart remains disabled (`_autoStartOnPlay = 0`): PASS
- no conflicting runner re-enabled in target scene: PASS (only `Week6VisualInspectionRunner` found among inspected runner names)
- no Play Mode run performed by this stage: PASS (static-only work)
- no match started by this stage: PASS (static-only work)

## 7) Files changed
- `Assets/Scenes/Week6_StudentVisualInspection.unity`
- `Assets/Scripts/ML/Week6StudentPolicyAdapter.cs`
- `Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs`
- `Assets/Scripts/ML/ActionContractV2GlobalSmokeRunner.cs`
- `python/week6_student/validate_unity_checkpoint_binding.py`
- `python/week6_student/reports/LEGACY032_UNITY_V2_UNITY_CHECKPOINT_BINDING_VALIDATION.json`
- `python/week6_student/reports/LEGACY032_UNITY_V2_UNITY_CHECKPOINT_BINDING_REPORT.md`

## 8) Remaining risks
- static binding check does not prove runtime load in Unity
- scene Inspector references still need controlled Play Mode dry-run
- checkpoint is BC-only
- Unity runtime compatibility still not proven
- semantic parity still not proven

## 9) Decision
GO_FOR_UNITY_SCENE_DRY_RUN
