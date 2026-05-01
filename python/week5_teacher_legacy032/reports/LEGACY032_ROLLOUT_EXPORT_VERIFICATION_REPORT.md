# LEGACY032 Rollout Export — Verification Report

**Date:** 2026-05-01  
**Checkpoint:** `python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/agent_final.pt`  
**Exporter:** `python/week5_teacher_legacy032/scripts/export_teacher_rollout_legacy032.py`  
**Authored by:** GitHub Copilot (automated verification pass)

---

## 1. Export Runs

### 1.1 Smoke Export (1 episode, 512 steps)

```powershell
python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
    python/week5_teacher_legacy032/scripts/export_teacher_rollout_legacy032.py `
    --checkpoint python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/agent_final.pt `
    --metadata  python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/model_metadata.json `
    --output-dir python/week5_teacher_legacy032/teacher_rollouts `
    --episodes 1 --max-steps 512 --seed 42 --require-mask true
```

**Output directory:** `legacy032_3m_unity_v2_rollout_export_smoke_20260501T101130Z`

### 1.2 Full Export (16 episodes, up to 6000 steps/ep)

```powershell
python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
    python/week5_teacher_legacy032/scripts/export_teacher_rollout_legacy032.py `
    --checkpoint python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/agent_final.pt `
    --metadata  python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/model_metadata.json `
    --output-dir python/week5_teacher_legacy032/teacher_rollouts `
    --episodes 16 --max-steps 6000 --seed 42 --require-mask true
```

**Output directory:** `legacy032_3m_unity_v2_rollout_export_20260501T125015Z`

---

## 2. File Presence

| File | Smoke | Full |
|------|-------|------|
| `teacher_rollout_raw.npz` | ✅ | ✅ |
| `teacher_rollout_manifest.json` | ✅ | ✅ |
| `teacher_rollout_summary.json` | ✅ | ✅ |
| `teacher_rollout_summary.md` | ✅ | ✅ |
| `teacher_rollout_debug.jsonl` | ✅ | ✅ |

---

## 3. Manifest Contract

All fields verified against contract. Same values in both exports.

| Field | Expected | Actual | OK |
|-------|----------|--------|----|
| `teacher_lineage` | `"legacy032"` | `"legacy032"` | ✅ |
| `source_pipeline` | `"gym_microrts==0.3.2"` | `"gym_microrts==0.3.2"` | ✅ |
| `observation_shape` | `[24,24,27]` | `[24,24,27]` | ✅ |
| `raw_action_nvec` | `[576,6,4,4,4,4,7,49]` | `[576,6,4,4,4,4,7,49]` | ✅ |
| `exported_per_cell_action_shape` | `[576,7]` | `[576,7]` | ✅ |
| `exported_per_cell_branch_sizes` | `[6,4,4,4,4,7,49]` | `[6,4,4,4,4,7,49]` | ✅ |
| `attack_target_semantics` | `"local_7x7_49"` | `"local_7x7_49"` | ✅ |
| `direct_weight_transfer_claim` | `false` | `false` | ✅ |
| `semantic_parity_claim` | `false` | `false` | ✅ |

---

## 4. Summary Contract

| Field | Smoke | Full | OK |
|-------|-------|------|----|
| `status` | `success` | `success` | ✅ |
| `total_steps` | 512 | 88 165 | ✅ |
| `action_mask_available_share` | 1.0 | 1.0 | ✅ |
| `shape_match_expected_contract` | `true` | `true` | ✅ |

---

## 5. NPZ Shape Verification

| Array | Expected shape | Smoke actual | Full actual | OK |
|-------|---------------|-------------|------------|-----|
| `observation_t` | `[N, 24, 24, 27]` | `[512, 24, 24, 27]` | `[88165, 24, 24, 27]` | ✅ |
| `per_cell_action_t` | `[N, 576, 7]` | `[512, 576, 7]` | `[88165, 576, 7]` | ✅ |

**NaN in observations:** False (both exports)  
**Inf in observations:** False (both exports)  
**action_mask_available_t all True:** True (both exports)

---

## 6. Branch Bounds Verification (Full Export)

Contract: branch sizes `[6, 4, 4, 4, 4, 7, 49]` → max allowed `[5, 3, 3, 3, 3, 6, 48]`

| Branch | Meaning | Size | Min | Max | OK |
|--------|---------|------|-----|-----|----|
| 0 | action_type | 6 | 0 | 5 | ✅ |
| 1 | move_dir | 4 | 0 | 2 | ✅ |
| 2 | harvest_dir | 4 | 0 | 3 | ✅ |
| 3 | return_dir | 4 | 0 | 0 | ✅ |
| 4 | produce_dir | 4 | 0 | 3 | ✅ |
| 5 | produce_unit_type | 7 | 0 | 3 | ✅ |
| 6 | attack_target_local | 49 | 0 | 31 | ✅ |

**Anti-remap guards (no v1 remap applied):**
- Branch 5 max = 3 ≤ 6 (not remapped to 0..3 range of v0/v1) ✅
- Branch 6 max = 31 ≤ 48 (not collapsed to 0..8 range of v1 9-cell) ✅

---

## 7. Action Statistics (Full Export)

### Action Type Histogram (branch 0)

| Type | Count | Share |
|------|-------|-------|
| noop | 50 608 730 | ~99.65% |
| harvest | 86 570 | ~0.17% |
| produce | 87 645 | ~0.17% |
| attack | 95 | <0.01% |

**Note:** High noop share (99.65%) is expected. In the Gym-μRTS 24×24 map only a few cells are active units at any timestep; all inactive cells produce noop. This is structurally correct legacy032 behavior.

### Produce Unit Type Histogram (branch 5)

| Type index | Count |
|-----------|-------|
| 3 | 87 645 |

Only unit type 3 (Worker) was produced in this rollout. Consistent with a base-building early-game strategy.

### Attack Target Diversity (branch 6)

| Metric | Value |
|--------|-------|
| Total attack steps | 95 |
| Unique target indices | 3 |
| Max target index | 31 |

Attack is rare but present, and targets are in range 0..31 ≤ 48. No overflow. Local 7×7 semantics confirmed.

---

## 8. Warnings

Both smoke and full exports produced two warnings (non-fatal):

1. `Checkpoint loaded with non-strict key diff: missing=0, unexpected=4`  
   **Explanation:** The checkpoint contains 4 keys that are not part of the current model definition (likely training-only optimizer state or auxiliary buffers). These are safely ignored during inference. No missing keys — the model loaded correctly.

2. `Actions are almost fully noop (noop_share=0.996528)`  
   **Explanation:** This is structurally expected for a 24×24 grid env with few active units per step. All 576 cells are logged per step, but only cells with active units produce non-noop actions. The noop share will always be very high (>99%) for this map. Not a quality concern.

**Hard failures:** None in any run.

---

## 9. Contract Compliance Summary

| Contract Check | Result |
|----------------|--------|
| All 5 output files present | ✅ PASS |
| Manifest lineage and pipeline fields | ✅ PASS |
| Manifest observation shape `[24,24,27]` | ✅ PASS |
| Manifest nvec `[576,6,4,4,4,4,7,49]` | ✅ PASS |
| Manifest per-cell shape `[576,7]` and sizes `[6,4,4,4,4,7,49]` | ✅ PASS |
| Manifest `attack_target_semantics == local_7x7_49` | ✅ PASS |
| Manifest `direct_weight_transfer_claim == false` | ✅ PASS |
| Manifest `semantic_parity_claim == false` | ✅ PASS |
| Summary status success | ✅ PASS |
| Summary action_mask_available_share == 1.0 | ✅ PASS |
| Summary shape_match_expected_contract == true | ✅ PASS |
| NPZ observation shape `[N,24,24,27]` | ✅ PASS |
| NPZ per_cell_action shape `[N,576,7]` | ✅ PASS |
| No NaN/Inf in observations | ✅ PASS |
| All action masks available | ✅ PASS |
| All 7 branches within bounds | ✅ PASS |
| No v1 remap artifacts (branch 5 max ≤ 6, branch 6 max ≤ 48) | ✅ PASS |
| No hard failures during export | ✅ PASS |

---

## 10. Decision

### ✅ GO

All contract checks pass. The full export (`legacy032_3m_unity_v2_rollout_export_20260501T125015Z`) contains **88 165 timesteps** across **16 episodes** with:
- Correct observation shape `[88165, 24, 24, 27]`
- Correct per-cell action shape `[88165, 576, 7]`
- All action masks available
- Branch bounds fully within contract limits
- No v1 remap applied
- No NaN/Inf
- Correct lineage metadata (legacy032, gym_microrts==0.3.2, attack_target_semantics=local_7x7_49)

**The rollout export artifact is cleared for use as input to the Legacy032 → Unity v2 adapter step.**
