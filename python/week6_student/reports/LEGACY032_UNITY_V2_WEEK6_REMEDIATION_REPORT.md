# Legacy032 Unity V2 — Week 6 Remediation Report

**Generated:** 2026-05-02  
**Scope:** Python defect remediation from Stage 0 handoff verification.  
No BC training, no Unity scene run, no teacher training, no dataset modification.

---

## 1. Files Changed

| File | Defect fixed |
|------|-------------|
| `python/week6_student/student_bc_model_minimal.py` | v1 head sizes `produce_unit_type=4`, `attack_target_local=9` updated to v2 `7` and `49` |
| `python/week6_student/train_student_bc_minimal.py` | `PINNED_BC_READY_RELATIVE` updated to new canonical Legacy032 v2 dataset; fail-fast manifest contract checks added |
| `python/week6_student/student_architecture_transfer.py` | Stale docstring `[B,576,4]`/`[B,576,9]` corrected to `[B,576,7]`/`[B,576,49]` |

---

## 2. Defects Fixed

### Fix 1 — `student_bc_model_minimal.py`: v1 head sizes (FAIL → PASS)

**Root cause:** `head_produce_unit_type` and `head_attack_target_local` Conv2d layers had output channels 4 and 9 respectively (v1 contract). The v2 canonical dataset has branch sizes 7 and 49. Running the minimal model with v2 targets would crash `cross_entropy` with an index-out-of-range error.

**Change:**
```python
# Before (v1):
self.head_produce_unit_type = nn.Conv2d(cfg.hidden_channels, 4, kernel_size=1)
self.head_attack_target_local = nn.Conv2d(cfg.hidden_channels, 9, kernel_size=1)

# After (v2):
# v2 branch sizes: produce_unit_type=7 (Gym/Gridnet order), attack_target_local=49 (7x7 local)
self.head_produce_unit_type = nn.Conv2d(cfg.hidden_channels, 7, kernel_size=1)
self.head_attack_target_local = nn.Conv2d(cfg.hidden_channels, 49, kernel_size=1)
```

A note was added to the class docstring that the transfer model variant (`StudentBCTransferModel`) is preferred for the Legacy032 v2 dataset.

**No remap performed:** values are not remapped 49→9 or 7→4. Actual head output sizes are 7 and 49.

---

### Fix 2 — `train_student_bc_minimal.py`: stale PINNED path + no manifest checks (FAIL → PASS)

**Root cause (path):** `PINNED_BC_READY_RELATIVE` pointed to the old non-Legacy032 dataset. Running the script without `--bc-ready-dir` would silently load the wrong data.

**Root cause (manifest checks):** `_validate_contract_for_day2` only checked `schema_version`. A wrong-lineage dataset (e.g. old v1 `[6,4,4,4,4,4,9]`) would pass undetected and produce silent wrong-branch-size training failures downstream.

**Changes:**

1. `PINNED_BC_READY_RELATIVE` updated:
```python
# Before:
PINNED_BC_READY_RELATIVE = Path(
    "python/week5_teacher/teacher_exports_bc/"
    "day6_bc_ready_teacher_adapted_day5_hardened_v2_..."
)

# After:
PINNED_BC_READY_RELATIVE = Path(
    "python/week5_teacher_legacy032/teacher_exports_bc/"
    "day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z"
)
```

2. Fail-fast manifest checks added to `_validate_contract_for_day2` — all six conditions checked before training loop:

| Field | Expected |
|-------|----------|
| `target_action_contract` | `"unity_v2_legacy032_gridnet"` |
| `observation_shape_per_sample` | `[576, 27]` |
| `action_shape_per_sample` | `[576, 7]` |
| `branch_sizes` | `[6, 4, 4, 4, 4, 7, 49]` |
| `direct_weight_transfer_claim` | `false` |
| `semantic_parity_claim` | `false` |

Any mismatch raises `BCContractError` immediately, before any model construction or dataloader creation.

---

### Fix 3 — `student_architecture_transfer.py`: stale docstring (WARNING → PASS)

**Change:**
```python
# Before (stale v1 values):
#     - produce_unit_type_logits: [B, 576, 4]
#     - attack_target_local_logits: [B, 576, 9]

# After (correct v2 values):
#     - produce_unit_type_logits: [B, 576, 7]
#     - attack_target_local_logits: [B, 576, 49]
```

Actual code was already correct (heads built from `BRANCH_SPECS`). Only the docstring was wrong.

---

## 3. Static Verification

```
python -m py_compile python/week6_student/student_bc_model_minimal.py   → OK
python -m py_compile python/week6_student/train_student_bc_minimal.py   → OK
python -m py_compile python/week6_student/student_architecture_transfer.py  → OK
```

Existing dry-run BC loader smoke check:
```
dry_run_bc_loader_legacy032_v2.py
  --bc-ready-dir day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z
  --batch-size 32 --fail-on-contract-mismatch true

Result: status=pass, hard_failures_count=0
```

---

## 4. Confirmations

| Confirmation | Status |
|--------------|--------|
| BC training NOT run | **CONFIRMED** — no training command executed |
| Unity scene NOT run | **CONFIRMED** — no Unity match or scene dry run executed |
| PPO fine-tune NOT run | **CONFIRMED** |
| Teacher training NOT continued | **CONFIRMED** |
| Dataset NOT modified | **CONFIRMED** — only Python scripts changed |
| No remap 49→9 added | **CONFIRMED** — `attack_target_local` head size is 49, no remap logic added |
| No remap 7→4 added | **CONFIRMED** — `produce_unit_type` head size is 7, no remap logic added |
| No `direct_weight_transfer_claim` added | **CONFIRMED** |
| No `semantic_parity_claim` added | **CONFIRMED** |
| Old v1 lineage not broken | **CONFIRMED** — old `runs/day3_transfer_bc_main_20260423` checkpoint still present; this remediation only updates defaults and adds guards |

---

## 5. Remaining pre-smoke conditions

Before running BC training smoke the following must be confirmed at the command line:

1. Python environment available with `torch`, `numpy` — verify with `python -c "import torch, numpy; print('ok')"` in the target venv.
2. Canonical dataset files present:
   - `python/week5_teacher_legacy032/teacher_exports_bc/day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z/bc_manifest.json`
   - `bc_train.npz`, `bc_validation.npz`
3. Recommended smoke command (no training output committed):
   ```
   python python/week6_student/train_student_bc_minimal.py \
     --bc-ready-dir python/week5_teacher_legacy032/teacher_exports_bc/day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z \
     --model-variant transfer \
     --epochs 3 \
     --device cpu \
     --output-dir python/week6_student/runs/legacy032_v2_bc_smoke_YYYYMMDDTHHMMSSZ
   ```
   The `--model-variant transfer` is recommended over `minimal` for Legacy032 v2 (noted in class docstring).

---

## 6. Final Decision

> **GO_FOR_BC_TRAINING_SMOKE**

All Stage 0 FAIL and WARNING items in the Python layer have been resolved:

| Original status | Item | New status |
|-----------------|------|------------|
| FAIL | `student_bc_model_minimal.py` v1 head sizes | **PASS** |
| FAIL | `train_student_bc_minimal.py` stale PINNED path | **PASS** |
| FAIL | `train_student_bc_minimal.py` no manifest checks | **PASS** |
| WARNING | `student_architecture_transfer.py` stale docstring | **PASS** |

Unity/C# layer was already PASS in Stage 0 and is unchanged.  
Unity scene readiness remains UNVERIFIED (no scene file found statically) — this is a pre-condition for `GO_FOR_SCENE_DRY_RUN`, not for `GO_FOR_BC_TRAINING_SMOKE`.
