# Stage6R1 Python Entrypoint Drift Fix Report

## 1. Executive Summary

Final decision: `STAGE6R1_PYTHON_ENTRYPOINT_FIX_PASS_READY_FOR_WEEK6A_BC_SMOKE`

Stage6R1 fixed Python-side runnable entrypoint drift by adding a canonical Week 6 smoke/preflight wrapper that is pinned to the Stage5P4 BC-ready package and defaults to transfer architecture. The wrapper enforces non-training contract-check mode for this stage, validates manifest and tensor contracts, and confirms transfer-head output shapes `[6,4,4,4,4,7,49]` without optimizer updates.

## 2. Changed Files

- `python/week6_student/scripts/train_student_bc_smoke_legacy032_v2.py` (new)
- `python/week6_student/train_student_bc_minimal.py` (minimal help-text guidance update only)

Runtime-generated preflight artifact (not source code):

- `python/week6_student/runs/legacy032_v2_bc_smoke_stage6r1_preflight/legacy032_v2_bc_smoke_stage6r1_preflight_contract_check_report.json`

## 3. Previous Blockers From Stage6R0

- `train_student_bc_minimal.py` defaulted to old dataset lineage (`day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z`).
- `train_student_bc_minimal.py` defaulted to `model_variant=minimal`.
- No dedicated canonical Stage5P4 smoke wrapper existed to pin path + transfer + short smoke defaults + no-Unity/non-training preflight behavior.

## 4. Entrypoint Strategy Chosen

Chosen strategy: add a dedicated wrapper with explicit canonical policy and preflight-only mode.

- New wrapper: `python/week6_student/scripts/train_student_bc_smoke_legacy032_v2.py`
- Reuses existing Week 6 loader/model/training utilities where safe:
  - `load_bc_ready_dataset` from `student_bc_loader.py`
  - `build_day3_student_model` from `student_architecture_transfer.py`
  - `create_dataloader` from `train_student_bc_minimal.py`
- No Unity dependency.
- No training step in Stage6R1 wrapper mode.

## 5. Exact CLI/Help After Fix

Command:

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe \
  python/week6_student/scripts/train_student_bc_smoke_legacy032_v2.py --help
```

Key flags now exposed:

- `--bc-ready-dir`
- `--device`
- `--epochs`
- `--batch-size`
- `--max-train-batches`
- `--max-validation-batches`
- `--seed`
- `--output-dir`
- `--run-label`
- `--save-checkpoint`
- `--model-variant {transfer,minimal}`
- `--contract-check-only`
- `--dry-run-only`

Defaults relevant to Stage6R1:

- `--bc-ready-dir` => canonical Stage5P4 path
- `--model-variant` => `transfer`
- `--device` => `cpu`
- `--batch-size` => `8`
- `--contract-check-only` => `true`
- `--dry-run-only` => `true`

## 6. Canonical Stage5P4 Path Policy

Wrapper constants are explicit and visible:

- `CANONICAL_STAGE5P4_BC_READY_DIR = python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_unity_v2_bc_ready_stage5p4_20260506T153632Z`
- `CANONICAL_BRANCH_SIZES = [6,4,4,4,4,7,49]`
- `CANONICAL_TARGET_ACTION_CONTRACT = unity_v2_legacy032_gridnet`
- `CANONICAL_ATTACK_TARGET_SEMANTICS = local_7x7_49`

No silent hidden path indirection was introduced.

## 7. Model Variant Policy

Canonical smoke wrapper default is transfer architecture.

- Default: `--model-variant transfer`
- Wrapper preflight hard-fails when `model_variant` is not `transfer` for Stage6R1 canonical mode.
- This avoids accidental fallback to historical minimal default in canonical smoke path.

## 8. Preflight/Contract-Check Result

Executed (non-training):

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe \
  python/week6_student/scripts/train_student_bc_smoke_legacy032_v2.py \
  --bc-ready-dir python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_unity_v2_bc_ready_stage5p4_20260506T153632Z \
  --device cpu \
  --batch-size 8 \
  --seed 17 \
  --output-dir python/week6_student/runs/legacy032_v2_bc_smoke_stage6r1_preflight \
  --run-label legacy032_v2_bc_smoke_stage6r1_preflight \
  --contract-check-only true
```

Result: `PASS`

Verified:

- manifest loaded
- `dataset_type = bc_ready_legacy032_unity_v2`
- `target_action_contract = unity_v2_legacy032_gridnet`
- `branch_sizes = [6,4,4,4,4,7,49]`
- `attack_target_semantics = local_7x7_49`
- `semantic_parity_claim = false`
- `direct_weight_transfer_claim = false`
- train/validation splits loaded
- first train batch built (`[8,24,24,27]`, targets `[8,576,7]`)
- first validation batch built (`[8,24,24,27]`, targets `[8,576,7]`)
- transfer model initialized
- forward pass succeeded with shapes:
  - `[8,576,6]`
  - `[8,576,4]`
  - `[8,576,4]`
  - `[8,576,4]`
  - `[8,576,4]`
  - `[8,576,7]`
  - `[8,576,49]`
- no NaN/Inf in input batches
- no v1 branch regression
- `optimizer_step_executed = false`
- `weights_updated = false`

## 9. py_compile/help Check Results

Used executable:

- `c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe`

Checks:

1. `py_compile` on:
   - `python/week6_student/train_student_bc_minimal.py`
   - `python/week6_student/scripts/train_student_bc_smoke_legacy032_v2.py`

   Result: pass

2. `--help` on wrapper script:

   Result: pass

3. preflight/contract-check-only run:

   Result: pass

## 10. Remaining Python Blockers

None blocking Week6A BC smoke preflight entrypoint policy after Stage6R1.

Notes:

- Legacy `train_student_bc_minimal.py` still retains historical defaults by design; canonical smoke path is now the wrapper.

## 11. Remaining Unity Blockers

Deferred to Stage6R2 (not changed in Stage6R1):

- `Assets/Scripts/ML/Week6StudentPolicyAdapter.cs` stale default checkpoint path / allowlist policy.
- `Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs` stale default checkpoint path.

## 12. Final Decision

`STAGE6R1_PYTHON_ENTRYPOINT_FIX_PASS_READY_FOR_WEEK6A_BC_SMOKE`

Reason:

- Canonical Python smoke entrypoint now pins Stage5P4 path and transfer default.
- Contract-check-only mode validates required manifest/tensor/head constraints.
- Stage6R1 checks passed without training and without Unity modifications.

## 13. Recommended Next Action

Proceed to Week6A BC smoke stage using the new wrapper in non-training preflight first, then controlled training smoke in the next stage plan only.
