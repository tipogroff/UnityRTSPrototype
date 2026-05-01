# LEGACY032 -> Unity v2 Adaptation Report

**Date:** 2026-05-01  
**Adapter:** `python/week5_teacher_legacy032/scripts/adapt_legacy032_to_unity_v2.py`  
**Decision Scope:** strict validator readiness only (no training, no BC packaging)

---

## 1. Smoke Run Executed

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/adapt_legacy032_to_unity_v2.py `
  --raw-rollout-dir python/week5_teacher_legacy032/teacher_rollouts/legacy032_3m_unity_v2_rollout_export_20260501T125015Z `
  --run-label legacy032_3m_unity_v2_adapted `
  --output-dir python/week5_teacher_legacy032/teacher_adapted `
  --fail-on-contract-mismatch true `
  --write-debug-sample true
```

Smoke run result: **success**

---

## 2. Input and Output

- Input rollout directory: `python/week5_teacher_legacy032/teacher_rollouts/legacy032_3m_unity_v2_rollout_export_20260501T125015Z`
- Output adapted directory: `python/week5_teacher_legacy032/teacher_adapted/legacy032_3m_unity_v2_adapted_20260501T161820Z`

Output artifacts:
- `adapted_dataset.npz`
- `adapted_manifest.json`
- `adaptation_summary.json`
- `adaptation_summary.md`
- `adaptation_debug_sample.json` (because `--write-debug-sample true`)

---

## 3. Sample Count and Shapes

- Sample count: `source=88165`, `output=88165`
- Source observation shape: `[88165, 24, 24, 27]`
- Output observation shape: `[88165, 576, 27]`
- Source action shape: `[88165, 576, 7]`
- Output action shape: `[88165, 576, 7]`

Adaptation behavior confirmed:
- observations flattened row-major (`flat_cell_index = row * 24 + col`)
- actions preserved without semantic remap
- target branch sizes preserved as `[6,4,4,4,4,7,49]`

---

## 4. Branch Min/Max (All 7 Branches)

| Branch | Size | Min | Max | In Bounds |
|---|---:|---:|---:|:---:|
| 0 | 6 | 0 | 5 | ✅ |
| 1 | 4 | 0 | 2 | ✅ |
| 2 | 4 | 0 | 3 | ✅ |
| 3 | 4 | 0 | 0 | ✅ |
| 4 | 4 | 0 | 3 | ✅ |
| 5 (`produce_unit_type`) | 7 | 0 | 3 | ✅ |
| 6 (`attack_target_local_7x7`) | 49 | 0 | 31 | ✅ |

No v1 remap evidence:
- no `49 -> 9`
- no `7 -> 4`
- no historical `[6,4,4,4,4,4,9]` contract usage

---

## 5. Histograms and Diversity

### action_type histogram
- noop: 50,608,730
- harvest: 86,570
- produce: 87,645
- attack: 95

### produce_unit_type histogram
- 3: 87,645

### attack_target_local diversity
- count: 95
- unique_targets: 3
- max_target_index: 31
- histogram: {17: 5, 25: 35, 31: 55}

---

## 6. NaN/Inf and Mask Availability

- source observation NaN: `false`
- source observation Inf: `false`
- output observation NaN: `false`
- output observation Inf: `false`
- action_mask_available_share: `1.0`

---

## 7. Warnings and Hard Failures

Warnings:
- `high noop share: noop_share=0.996568`
- `produce_unit_type diversity is low`
- `attack_target_local diversity is low`

Hard failures:
- none

---

## 8. Decision for Next Step

## ✅ GO for strict validator step

Rationale:
- adapter completed successfully;
- tensor contract adaptation is correct (`[24,24,27] -> [576,27]`, actions `[576,7]` preserved);
- branch bounds valid under `[6,4,4,4,4,7,49]`;
- no NaN/Inf;
- no hard failures;
- manifest explicitly keeps `direct_weight_transfer_claim=false` and `semantic_parity_claim=false`.

This step delivered only the requested tensor adaptation artifacts. Validator and BC-ready packager remain out of scope and were not created.
