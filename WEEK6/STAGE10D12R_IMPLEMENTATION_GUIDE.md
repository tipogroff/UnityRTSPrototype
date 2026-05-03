# Stage10D.12R - Full Raw Runtime Observation Capture

## Overview

Stage10D.12R implements **read-only diagnostic instrumentation** to capture the true full raw observation tensor [24,24,27] that Unity sends to the student policy model for inference. This is critical for validating that the observation contract is being honored and for debugging NoOp prediction issues.

## Key Points

- **Zero behavior changes** - Purely diagnostic
- **Zero checkpoint modifications** - Only observation capture
- **Exact capture point** - Right after observation validation, before Python bridge send
- **Complete validation** - Shape, values, semantics, focus cells
- **Ground truth** - True raw tensor serves as reference for all future diagnostics

## Implementation Details

### 1. Unity-Side Instrumentation

**File:** `Assets/Scripts/ML/Week6StudentPolicyAdapter.cs`

**Changes:**
- Added `CaptureFullRawObservationDiagnostic()` method (lines ~1200-1350)
- Invokes capture right after `WriteFloat32Buffer()` (lines ~610-622)
- Captures every inference step to artifacts directory

**What it captures:**
```
{
  "generated_at_utc": "2026-05-03T...",
  "step_index": 1,
  "controlled_player": "Player1",
  "capture_point": "after_observation_validation_before_python_bridge_send",
  "tensor_shape": [24, 24, 27],
  "cells": [
    {
      "flat_index": 0,
      "x": 0,
      "y": 0,
      "logical_label": "A1",
      "raw_channel_vector": [0.0, 0.0, 1.0, 0.0, 0.0, ...],  # 27 channels
      "decoded_owner": "neutral",
      "decoded_unit": "none",
      "decoded_current_action": "none"
    },
    ...
    {
      "flat_index": 25,  # B2
      "x": 1,
      "y": 1,
      "logical_label": "B2",
      "raw_channel_vector": [...],
      "decoded_owner": "player1_friendly",
      "decoded_unit": "worker",
      "decoded_current_action": "noop"
    },
    ...
  ]
}
```

**Channel Semantics (27 channels per cell):**
- `ch0`: hit_points
- `ch1`: resources
- `ch2-4`: owner (neutral, self/friendly, enemy)
- `ch5-11`: unit_type (resource, base, barracks, worker, light, heavy, ranged)
- `ch12-17`: current_action (noop, move, harvest, return, produce, attack)
- `ch18-21`: direction (north, east, south, west)
- `ch22-25`: produce_type (worker, light, heavy, ranged)
- `ch26`: attack_target_index

### 2. Python-Side Analysis

Four diagnostic scripts process and validate the captured tensor:

#### 2.1 Validation Script
**File:** `python/week6_student/stage10d12r_full_raw_observation_validation.py`

**Purpose:** Validate captured tensor integrity

**Checks:**
- Shape is exactly [24,24,27]
- Exactly 576 cells present
- All 27 channels per cell
- No NaN or Inf values
- Owner/unit/action channels are one-hot (or zero)
- Focus cells B2 and C3 present
- Channel semantics consistency

**Output:** `stage10d12r_full_raw_observation_validation.json`

#### 2.2 Comparison Script
**File:** `python/week6_student/stage10d12r_full_raw_vs_reconstructed_comparison.py`

**Purpose:** Compare true raw tensor with Stage10D.11/D.12 reconstructed fullmap

**Computes:**
- Per-cell L2 differences
- Per-channel mean absolute differences
- Top differing cells
- Top differing channels
- B2/C3 specific differences
- Classification: MATCHES / PARTIALLY_MATCHES / DIVERGES / UNAVAILABLE

**Output:** `stage10d12r_full_raw_vs_reconstructed_diff.json`

#### 2.3 Probe Script
**File:** `python/week6_student/stage10d12r_strict_replay_probe_on_true_raw.py`

**Purpose:** Run offline inference on true raw tensor (placeholder for model execution)

**Probes:**
- B2 baseline inference
- C3 baseline inference
- B2 group patches (current_action, direction)
- B2 per-channel isolation
- C3 context probes (3x3, 5x5, 7x7)
- C3 neighbor-only probe

**Output:** `stage10d12r_strict_replay_probe_results.json`

#### 2.4 Orchestration Script
**File:** `python/week6_student/stage10d12r_orchestrate_full_pipeline.py`

**Purpose:** Run all diagnostics and synthesize final comprehensive report

**Runs:**
1. Validation
2. Comparison
3. Probes
4. Report synthesis

**Output:**
- `STAGE10D12R_FULL_RAW_OBSERVATION_CAPTURE_REPORT.json` (comprehensive)
- `STAGE10D12R_FULL_RAW_OBSERVATION_CAPTURE_REPORT.md` (markdown summary)

## Usage Instructions

### Step 1: Compile Unity Changes

The instrumentation is already compiled into `Week6StudentPolicyAdapter.cs`. Just ensure you have the updated code.

### Step 2: Run a Match with Student Policy

1. Open the Unity scene
2. Enable student policy control (Week6ConfiguredDecisionSource.cs or similar)
3. Run a single-step or full match
4. The capture will be written to: `python/week6_student/tmp/day5_sanity/stage10d12r_full_raw_runtime_observation_step0001.json`

### Step 3: Copy Capture to Reports

```bash
cd c:\Projects\UnityRTSPrototype\UnityRTSPrototype
cp python/week6_student/tmp/day5_sanity/stage10d12r_full_raw_runtime_observation_step*.json \
   python/week6_student/reports/
```

### Step 4: Run Orchestration Pipeline

```bash
cd c:\Projects\UnityRTSPrototype\UnityRTSPrototype
python python/week6_student/stage10d12r_orchestrate_full_pipeline.py
```

This will:
1. Validate the captured tensor
2. Compare with reconstructed data
3. Run initial probes
4. Generate comprehensive report

### Step 5: Review Reports

Generated reports in `python/week6_student/reports/`:
- `stage10d12r_full_raw_observation_validation.json`
- `stage10d12r_full_raw_vs_reconstructed_diff.json`
- `stage10d12r_strict_replay_probe_results.json`
- `STAGE10D12R_FULL_RAW_OBSERVATION_CAPTURE_REPORT.json`
- `STAGE10D12R_FULL_RAW_OBSERVATION_CAPTURE_REPORT.md`

## Classification Labels

### Capture Quality Labels
- `FULL_RAW_576_CAPTURED` - Success, tensor valid
- `FULL_RAW_576_CAPTURE_FAILED` - Instrumentation failed
- `RAW_CAPTURE_SHAPE_INVALID` - Shape mismatch
- `RAW_CAPTURE_CONTAINS_NAN_INF` - Invalid values
- `RAW_CAPTURE_FOCUS_MISMATCH` - B2/C3 missing

### Comparison Labels
- `RECONSTRUCTION_MATCHES_RAW` - High fidelity
- `RECONSTRUCTION_PARTIALLY_MATCHES_RAW` - Moderate fidelity
- `RECONSTRUCTION_DIVERGES_FROM_RAW` - Low fidelity
- `RECONSTRUCTION_COMPARISON_UNAVAILABLE` - No reconstructed data

### Semantics Labels
- `VALID_NONOP_CAPABLE` - Valid type, action ≠ noop
- `VALID_BUT_NOOP_STATE` - Valid type, action = noop
- `INVALID_EXPECTATION_MISMATCH` - Type/owner mismatch

## Expected Next Gates

Based on true raw tensor findings:

### Primary (Single Selection)
1. **GO_FOR_UNITY_OBSERVATION_CHANNEL_REMAP_FIX**
   - If true raw proves channel semantics wrong

2. **GO_FOR_UNITY_SCENE_DISTRIBUTION_ALIGNMENT**
   - If true raw shows scene OOD vs BC

3. **GO_FOR_TARGETED_BC_AUGMENTATION_WITH_UNITY_LIKE_STATES**
   - If true raw valid but BC needs Unity-like states

4. **GO_FOR_STAGE10D13_MINIMAL_RUNTIME_OBSERVATION_FIX**
   - If minimal safe observation fix proven

5. **GO_FOR_STAGE10D12R_CAPTURE_FIX**
   - If capture fails or tensor invalid

6. **GO_FOR_STAGE10D12R_STRICT_PROBE_RERUN**
   - If capture succeeds, rerun probes with full model

## Integration with Previous Stages

### Stage10D.10 - Global Runtime Noop Diagnostic
- Provided snapshot of runtime cell data
- Showed B2/C3 predicted NoOp from runtime reconstructed observation
- Stage10D.12R uses true raw as reference

### Stage10D.11 - Runtime vs BC Distribution Audit
- Built reconstructed fullmap from cell snapshots
- Ran offline probes showing B2/C3 context requirements
- Stage10D.12R compares reconstruction accuracy

### Stage10D.12 - Channel & Context Fix Candidate Audit
- Ran probes on reconstructed fullmap
- Identified channel and context issues
- Stage10D.12R confirms findings with true raw

## Key Metrics

### Validation
- **Tensor shape:** [24,24,27]
- **Cell count:** 576
- **Channels per cell:** 27
- **Valid values:** No NaN, no Inf
- **Semantics:** Owner/unit/action one-hot

### Comparison (if reconstructed available)
- **Mean L2 difference:** < 0.01 (matches), 0.01-0.1 (partial), > 0.1 (diverges)
- **Per-channel differences:** Show which channels diverge
- **Focus cells:** B2 and C3 specific L2

### Semantics
- **B2 expected:** Player1, Worker
- **C3 expected:** Player1, Base
- **Action classification:** NoOp vs non-NoOp

## Troubleshooting

### Issue: Capture file not generated
- **Cause:** Instrumentation not compiled
- **Solution:** Rebuild Unity project
- **Check:** Verify CaptureFullRawObservationDiagnostic in Week6StudentPolicyAdapter.cs

### Issue: Validation fails with NaN/Inf
- **Cause:** Observation builder issue
- **Solution:** Check ObservationBuilder for encoding errors
- **Check:** Run LEGACY032_UNITY_V2_STAGE10D2_OBSERVATION_ENCODING_SOURCE_OF_TRUTH_REPORT

### Issue: Comparison shows divergence
- **Cause:** Reconstructed fullmap was inaccurate
- **Solution:** Indicates Stage10D.11/D.12 reconstruction had errors
- **Action:** Focus on true raw tensor, not reconstruction

### Issue: Probes incomplete
- **Cause:** Model checkpoint not loaded
- **Solution:** Ensure Stage10D.8 checkpoint exists at expected path
- **Checkpoint:** `python/week6_student/runs/legacy032_v2_semantic_bc_stage10d8_*/student_bc_semantic_best.pt`

## Important Constraints

✓ **Allowed:**
- Read-only instrumentation
- Observation capture and serialization
- Validation and audit
- Offline inference on captured tensor
- Report generation

✗ **Not Allowed:**
- Runtime behavior changes
- Checkpoint modifications
- Policy retraining
- PPO execution
- Observation manipulation
- Action changes
- Fallback heuristics

## Files Modified

### C# (Unity)
- `Assets/Scripts/ML/Week6StudentPolicyAdapter.cs`
  - Added: `CaptureFullRawObservationDiagnostic()` method
  - Modified: `ExecuteDecision()` to invoke capture

### Python
- Created: `stage10d12r_full_raw_observation_validation.py`
- Created: `stage10d12r_full_raw_vs_reconstructed_comparison.py`
- Created: `stage10d12r_strict_replay_probe_on_true_raw.py`
- Created: `stage10d12r_orchestrate_full_pipeline.py`

## Generated Artifacts

### Step 0001 (Minimal Set)
1. `stage10d12r_full_raw_runtime_observation_step0001.json` - Raw capture
2. `stage10d12r_full_raw_observation_validation.json` - Validation report
3. `stage10d12r_full_raw_vs_reconstructed_diff.json` - Comparison
4. `stage10d12r_strict_replay_probe_results.json` - Probes
5. `STAGE10D12R_FULL_RAW_OBSERVATION_CAPTURE_REPORT.json` - Final report
6. `STAGE10D12R_FULL_RAW_OBSERVATION_CAPTURE_REPORT.md` - Summary

### Optional (All Steps)
- `stage10d12r_full_raw_runtime_observation_step0002.json`, etc. for additional steps

## Success Criteria

✓ Capture instrumentation compiles without errors
✓ Capture executed during match (file generated)
✓ Tensor shape validated as [24,24,27]
✓ All 576 cells present
✓ All 27 channels per cell
✓ No NaN/Inf values
✓ B2 and C3 cells present with valid semantics
✓ Comparison report generated (or unavailable noted)
✓ Final report synthesized with classification and next gate

## Next Steps (After Stage10D.12R)

The true raw observation tensor becomes the ground truth for:
- Stage10D.13: Minimal runtime observation fix (if needed)
- Stage10D.14: Channel remap validation (if needed)
- Future offline training with Unity-like distributions
- Continued runtime behavior analysis

---

**Report:** `STAGE10D12R_FULL_RAW_OBSERVATION_CAPTURE_REPORT.md`

**Date Generated:** See report header

**Stage:** Stage10D.12R - Full Raw Runtime Observation Capture

**Status:** Ready for execution
