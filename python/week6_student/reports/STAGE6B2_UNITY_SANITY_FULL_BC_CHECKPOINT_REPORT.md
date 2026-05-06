# STAGE6B2 — Unity Sanity: Full BC Checkpoint Bound And Measured

**Classification:** `STAGE6B2_UNITY_SANITY_PASS_WITH_WARNINGS`

**Date:** 2026-05-07

---

## 1. Changed Files

| File | Change |
|------|--------|
| `Assets/Scripts/ML/Week6StudentPolicyAdapter.cs` | Added `CanonicalStage6B1CheckpointRelativePath` const; updated `_checkpointRelativePath` default to Stage6B1 |
| `Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs` | Added `CanonicalStage6B1CheckpointRelativePath` const; updated `_checkpointRelativePath` default to Stage6B1 |
| `Assets/Scenes/Week6_StudentVisualInspection.unity` | Updated scene serialized values via MCP: checkpoint path, artifact dir prefix, snapshot output dir, auto-playback enabled |

---

## 2. Exact Checkpoint Bound

```
python/week6_student/runs/legacy032_v2_full_bc_stage6b1/legacy032_v2_full_bc_stage6b1_best.pt
```

- Confirmed active at inference by `stage6r5c_scene_sanity_snapshot.json`
- Best epoch: 5 / 10 (early stop patience 5)
- Best val loss: 1.8362130231139502
- Model variant: `transfer`
- No stale Stage6A2 checkpoint used
- No stale Stage10D checkpoint used

---

## 3. Exact Scene / Run

| Field | Value |
|-------|-------|
| Scene | `Assets/Scenes/Week6_StudentVisualInspection.unity` |
| Mode | `student_live_policy` |
| Target steps | 80 |
| Steps completed | **55** |
| Terminal reason | **Loss** |
| uses_heuristic_policy | false |
| fake_policy_or_stub_seen | false |
| fallback_used | false |

---

## 4. Payload Contract Summary

| Check | Value | Pass |
|-------|-------|------|
| action_contract_version | v2_gridnet_compatible | ✓ |
| branch_sizes | [6,4,4,4,4,7,49] | ✓ |
| single_payload_action_flat_size | 44928 | ✓ |
| observation_shape | [24,24,27] | ✓ |
| model_input_shape | [24,24,27] | ✓ |
| produce_head_size | 7 | ✓ |
| attack_head_size | 49 | ✓ |
| v1_payload_seen | false | ✓ |
| fallback_used | false | ✓ |
| fake_policy_or_stub_seen | false | ✓ |
| uses_heuristic_policy | false | ✓ |

**All contract checks: PASS**

---

## 5. Terminal Outcome

Terminal at **step 55** — **Loss**. Two steps fewer than Stage6A2 (57 steps).

---

## 6. Actor-Cell Summary

| Metric | Stage6B2 (Stage6B1 checkpoint) |
|--------|-------------------------------|
| Steps run | 54 |
| Eligible own actor cells (total) | 108 |
| Commands built | 99 |
| Commands submitted | 99 |
| Commands accepted/applied | **0** |
| Commands rejected | **99** |
| Command acceptance rate | 0.000 |
| Actor cells (last step) | 2 (Base + Worker) |
| mask_constrained_enabled | false |
| masked_out_count | 0 |
| fallback_to_noop | 0 |

**Action distribution (submitted attempts):**

| Action Type | Count |
|-------------|-------|
| Attack | 48 |
| Harvest | 45 |
| Return | 6 |
| Move | 0 |
| Produce | 0 |
| NoOp | 0 |

---

## 7. Base vs Worker Summary

### Worker B2 (flat_index=25)

| Metric | Stage6B2 |
|--------|----------|
| Action predicted | Harvest/East |
| Commands submitted | 45 |
| Commands accepted | 0 |
| Rejection reason | No adjacent harvestable resource |
| Behavior vs Stage6A2 | REGRESSED (Stage6A2: Move East, 22/22 applied) |

### Base C3 (flat_index=50)

| Metric | Stage6B2 |
|--------|----------|
| Action predicted | Attack (48) / Return (6) |
| Commands submitted | 54 |
| Commands accepted | 0 |
| Rejection reason | No valid attack target; Base cannot Return resources |
| Behavior vs Stage6A2 | REGRESSED (Stage6A2: Move masked to NoOp, 56/56 masked, 0 submitted) |

---

## 8. Command Lifecycle Terminal Buckets

| Bucket | Count |
|--------|-------|
| submitted | 99 |
| applied_by_match_manager | 0 |
| rejected_by_applier | 0 |
| rejected_by_match_manager | 0 |
| expired_or_unresolved_at_capture_end | 99 |

---

## 9. Telemetry Invariant

**Expression:** `99 == 0 + 0 + 0 + 99`

**Result: HOLDS**

**Note:** All 99 commands ended in `expired_or_unresolved_at_capture_end` because the MatchManager rejection events for Harvest/Attack/Return action types did not link back via `command_event_key` into the R5C lifecycle chain. The episode diagnostics independently confirms 99 invalid rejections (Attack=48, Harvest=45, Return=6). The arithmetic invariant is satisfied. This is a known telemetry linkage gap for rejected (non-applied) commands — the same gap fixed in Stage6R5C for applied commands.

---

## 10. Stage6A2 vs Stage6B1 Comparison

| Metric | Stage6A2 (smoke) | Stage6B1 (full BC) | Delta |
|--------|-----------------|-------------------|-------|
| steps_completed | 57 | 55 | −2 |
| terminal | Loss | Loss | same |
| submitted | 22 | 99 | +77 |
| applied_by_mm | 22 | 0 | −22 |
| apply_rate | 1.000 | 0.000 | −1.000 |
| Worker action | Move East (valid) | Harvest East (invalid) | REGRESSED |
| Base action | Move → masked_to_noop | Attack/Return (rejected) | REGRESSED |
| actor_cells_total | 83 | 108 | +25 |
| masked_to_noop_total | 60 | 0 (no masking) | Stage6B1 not masked but all rejected |
| v1_regression | false | false | same |
| fallback_used | false | false | same |

**Behavior direction: REGRESSED**

Stage6B1 generates more commands (99 vs 22) but all are semantically invalid in the current scene state. Stage6A2 Worker correctly predicted Move which was a valid and accepted action. Stage6B1 full BC has learned to predict Harvest/Attack/Return but the model does not yet generalize to scene context where those actions are illegal.

**Important:** No improvement is required for PASS. PASS_WITH_WARNINGS means the checkpoint is correctly bound and measurable. Improvement/no-improvement is reported separately and does not change the binding classification.

---

## 11. Final Classification

```
STAGE6B2_UNITY_SANITY_PASS_WITH_WARNINGS
```

### PASS criteria met:
- [x] Stage6B1 best checkpoint is active
- [x] Bridge starts (55 steps produced)
- [x] Payload validates (all 11 contract checks pass)
- [x] v2 branch sizes [6,4,4,4,4,7,49] preserved at runtime
- [x] No v1 regression
- [x] No fake/heuristic fallback
- [x] Stage6R5C invariant holds (99 == 0+0+0+99)
- [x] Actor-cell metrics generated

### Warnings:
- [ ] Behavior weak: all 99 commands rejected (0/99 applied)
- [ ] Terminal still Loss at step 55
- [ ] Stage6B1 behavior regressed vs Stage6A2 in Unity scene
- [ ] Offline metrics (action_type_acc≈0.17, entropy_norm≈0.95) flagged weak quality

### Hard fails: NONE

---

## 12. Recommended Next Stage

**Stage6B3R — BC Training Quality Diagnosis And Data/Loss Review**

Stage6B2 passes binding and contract verification, but behavior regressed compared to Stage6A2:
- 0/99 commands applied (vs 22/22 in Stage6A2)
- Worker predicts Harvest with no resource; Base predicts Attack with no valid target
- All predicted action types (Harvest, Attack, Return) are semantically invalid in the current early-game scene state

Before further BC training or fine-tuning, diagnosis is required:
- BC dataset action distribution audit (is Harvest/Attack over-represented?)
- Per-branch loss decomposition (is action_type head loss dominating? Is the model collapsing to wrong modes?)
- Dataset scene-state coverage (does the training data contain early-game states where Move is the dominant action?)
- Potential curriculum imbalance in the teacher's exported actions

---

## 13. Safety Boundaries Confirmed

- No BC training run
- No PPO fine-tuning
- No teacher training
- No semantic parity claim between Gym-µRTS and Unity
- No direct weight transfer claim
- No final behavior quality claim
- No fake/heuristic/random fallback introduced
- v1 rejection not weakened
- Action semantics unchanged
- Mask semantics unchanged
- Runtime truth remains: `ActionApplier / MatchManager.ApplyCommand`
- Masks remain pre-submit/diagnostic only
