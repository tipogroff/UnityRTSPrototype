# LEGACY032 Unity V2 — Week 6 Stage 0 Handoff Verification Report

**Generated:** 2026-05-02  
**Author:** Copilot automated verification pass  
**Scope:** Static code and artifact inspection. No training, no Unity match, no dataset modification.

---

## 1. Executive Summary

| Field | Value |
|-------|-------|
| **Overall status** | `PASS_WITH_WARNINGS` |
| **Decision** | `GO_FOR_REMEDIATION` (minor, then `GO_FOR_BC_TRAINING_SMOKE`) |

### Decision rationale

The new canonical handoff dataset is structurally correct and complete. The Python Week 6 **loader**, **contract**, **metrics**, **transfer architecture**, and **inference adapter** all correctly reference the v2 contract `[6,4,4,4,4,7,49]`.

However, two **code defects** block safe BC training smoke on the new dataset without remediation:

1. **`student_bc_model_minimal.py`** (the Day-2 minimal model) hardcodes v1 head sizes — `produce_unit_type=4`, `attack_target_local=9` — while the active dataset has branch sizes 7 and 49. Running the default `--model-variant minimal` on the new dataset would produce a `cross_entropy` index-out-of-range crash.

2. **`train_student_bc_minimal.py`** `PINNED_BC_READY_RELATIVE` still points to the old (non-Legacy032) dataset path. Invoking the script without an explicit `--bc-ready-dir` override silently loads the wrong dataset.

The Unity/C# side (`ActionContract`, `ActionDecoder`, `ActionApplier`, `ActionContractMappings`) is fully v2-correct. The primary blocker for a Unity scene dry run is that no v2-compatible BC-trained checkpoint exists yet (the existing Day-3 checkpoint was trained on the old dataset).

**Required before BC training smoke:** Fix the two Python defects above (see Section 7-A).  
**Required before Unity scene dry run:** Complete one successful BC training smoke with the new dataset to produce a v2 checkpoint.

---

## 2. Canonical Week 5 → Week 6 Handoff

### Dataset path

```
python/week5_teacher_legacy032/teacher_exports_bc/
  day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z/
    bc_manifest.json
    bc_train.npz
    bc_validation.npz
    bc_debug.npz
    bc_summary.json
    bc_summary.md
```

### Split counts (from manifest)

| Split | Samples |
|-------|---------|
| train | 74 940 |
| validation | 13 225 |
| debug | 512 |

### Manifest contract (bc_manifest.json)

| Field | Value |
|-------|-------|
| `dataset_type` | `bc_ready_legacy032_unity_v2` |
| `teacher_lineage` | `legacy032` |
| `source_pipeline` | `gym_microrts==0.3.2` |
| `target_action_contract` | `unity_v2_legacy032_gridnet` |
| `observation_shape_per_sample` | `[576, 27]` |
| `action_shape_per_sample` | `[576, 7]` |
| `branch_sizes` | `[6, 4, 4, 4, 4, 7, 49]` |
| `flatten_order` | `row_major` |
| `global_vector_policy` | `excluded_from_strict_bc_encoder_path` |
| `attack_target_semantics` | `local_7x7_49` |
| `direct_weight_transfer_claim` | `false` |
| `semantic_parity_claim` | `false` |

### Explicit limitations (contractual)

- **No behavior quality proof:** teacher (Legacy032 gym-microrts) collapsed to near-NoOp on ready actors at 3M steps. The BC dataset reflects this behavior. Training will produce a student that mimics NoOp-dominant behavior.
- **No Gym-μRTS ↔ Unity semantic parity proof:** obs channel layout in gym-microrts `[HP-bands, Resources-bands, owner, unit_type, current_action]` differs from Unity `ObservationContract` `[HP scalar, Resources scalar, owner, unit_type, current_action, action_dir, produce_type, attack_target]`. No cross-environment semantic validation has been performed.
- **No direct weight transfer claim:** the BC-ready packaging step produces labels only; no teacher weights are embedded or transferred.

---

## 3. Python Week 6 Verification

### Verification table

| File | Expected v2 assumption | Actual finding | Status | Required action |
|------|------------------------|----------------|--------|-----------------|
| `student_branch_contract.py` | `EXPECTED_BC_BRANCH_SIZES = (6,4,4,4,4,7,49)` | Correct. `produce_unit_type branch_size=7`, `attack_target_local branch_size=49`. `ACTION_CONTRACT_VERSION = "v2_gridnet_compatible"`. | **PASS** | None |
| `student_bc_loader.py` | No hardcoded dataset path; validates shapes and branch sizes from manifest | Correct. Validates input shape `[576,27]`, target shape `[576,7]`, branch sizes from manifest. No v1 constants. | **PASS** | None |
| `student_bc_contract.py` | Manifest-driven; no v1 shape hardcoding | Correct. All shapes read from manifest schema. No v1 constants embedded. | **PASS** | None |
| `student_bc_metrics.py` | Uses `BRANCH_SPECS`; correct active-gating per branch; loss/accuracy computed per-active-item | Correct. `compute_branchwise_loss` uses `BRANCH_SPECS` (7 classes for produce, 49 for attack). Active-gating by `action_type_gate_value`. | **PASS** | None |
| `inspect_bc_dataset.py` | No hardcoded dataset path; accepts `--bc-ready-dir` | Correct. Requires `--bc-ready-dir` at CLI. No v1 hardcoding. | **PASS** | Must be invoked with new canonical dataset path |
| `student_architecture_transfer.py` (code) | Branch heads built from `BRANCH_SPECS`: `produce_unit_type=7`, `attack_target_local=49` | Correct. `branch_heads = nn.ModuleDict({spec.head_name: nn.Conv2d(..., spec.branch_size, ...) for spec in BRANCH_SPECS})`. Actual head sizes are 7 and 49. | **PASS** | — |
| `student_architecture_transfer.py` (docstring) | Docstring must reflect v2 sizes | **Stale.** Docstring in `forward()` says `produce_unit_type_logits: [B, 576, 4]` and `attack_target_local_logits: [B, 576, 9]`. These are v1 values. Code is correct but doc is misleading. | **WARNING** | Update docstring to `[B,576,7]` and `[B,576,49]` |
| `student_bc_model_minimal.py` | Head sizes must match v2: `produce_unit_type=7`, `attack_target_local=49` | **FAIL.** `head_produce_unit_type = nn.Conv2d(..., 4, ...)` and `head_attack_target_local = nn.Conv2d(..., 9, ...)`. These are v1 values. Running this model on the v2 dataset will crash `cross_entropy` when target values exceed output size. | **FAIL** | Fix head sizes to 7 and 49, OR deprecate/mark this model as historical (not for v2 dataset). See Section 7-A. |
| `train_student_bc_minimal.py` | Default `PINNED_BC_READY_RELATIVE` must point to new canonical Legacy032 v2 dataset | **FAIL.** `PINNED_BC_READY_RELATIVE` = `python/week5_teacher/teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_hardened_v2_...` (old dataset, non-Legacy032). Invoking without `--bc-ready-dir` loads wrong data silently. | **FAIL** | Update `PINNED_BC_READY_RELATIVE` to the new canonical dataset path, OR mark script as deprecated for v2 lineage and add explicit `--bc-ready-dir` requirement. See Section 7-A. |
| `student_inference_adapter.py` | Uses `EXPECTED_BC_BRANCH_SIZES = (6,4,4,4,4,7,49)` | Correct. Imports `EXPECTED_BC_BRANCH_SIZES` from `student_branch_contract.py`, validates logits contract. No v1 constants. | **PASS** | Needs v2-compatible checkpoint when integrated |
| `load_student_checkpoint.py` | Loads `StudentBCTransferModel` (correct v2 architecture) | Correct. Calls `build_day3_student_model()` which uses BRANCH_SPECS. Strict state dict check. | **PASS** | Needs v2-compatible checkpoint when integrated |
| `partial_transfer_strategy.py` | No v1 assumptions | Correct. Transfer rules are architecture-aware and honesty-first. No v1 constants. | **PASS** | None |
| `analyze_move_signal_lineage.py` | No v1 contract usage in active lineage | Not verified in detail; diagnostic-only script. Not in active BC path. | **INFO** | No action required |
| Existing checkpoint `runs/day3_transfer_bc_main_20260423/` | Should be trained on new canonical Legacy032 v2 dataset | **WARNING.** Checkpoint was trained on OLD dataset (`day6_bc_ready_teacher_adapted_day5_hardened_v2...`, non-Legacy032). Architecture is v2-correct (`StudentBCTransferModel` via BRANCH_SPECS), but training data lineage is not Legacy032. | **WARNING** | Do not use this checkpoint as "Legacy032 v2 student". Train a new checkpoint on new canonical dataset. |
| No `reports/` directory | Directory must exist before writing Stage 0 report | Directory was missing; created as part of this verification. | **FIXED** | None |

### Summary: manifest contract checks

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| `target_action_contract` | `unity_v2_legacy032_gridnet` | `unity_v2_legacy032_gridnet` | **PASS** |
| observation shape | `[576, 27]` | `[576, 27]` | **PASS** |
| action shape | `[576, 7]` | `[576, 7]` | **PASS** |
| branch sizes | `[6,4,4,4,4,7,49]` | `[6,4,4,4,4,7,49]` | **PASS** |
| `attack_target_semantics` | `local_7x7_49` | `local_7x7_49` | **PASS** |
| `direct_weight_transfer_claim` | `false` | `false` | **PASS** |
| `semantic_parity_claim` | `false` | `false` | **PASS** |
| v1 contract `[6,4,4,4,4,4,9]` used anywhere | Must not be active | Not used in loader/contract/metrics/transfer arch. Used only in old minimal model heads (flagged FAIL above). | **WARNING** |

---

## 4. Unity/C# Verification

### Verification table

| File / Component | Expected v2 assumption | Actual finding | Status | Required action |
|------------------|------------------------|----------------|--------|-----------------|
| `ActionContract.cs` | `SIZE_ATTACK_TARGET = 49`, `SIZE_PRODUCE_UNIT_TYPE = 7`, `ActionFlatSize = 78` | Correct. Constants confirmed: `SIZE_ATTACK_TARGET=49`, `SIZE_PRODUCE_UNIT_TYPE=7`, `ActionFlatSize=78`, `TotalCells=576`, `TotalActionFlatSize=44928`. Branch table `[6,4,4,4,4,7,49]` documented. | **PASS** | None |
| `ActionContractMappings.cs` `TryMapV2ProduceIndexToUnitType` | Maps 0..6 to UnitType (Resource..Ranged) | Correct. Mapping: 0→Resource, 1→Base, 2→Barracks, 3→Worker, 4→Light, 5→Heavy, 6→Ranged. Covers all 7 values. | **PASS** | None |
| `ActionContractMappings.cs` `ProducibleUnitToObservationIndex` | Observation-side helper only (4-value runtime enum), not action contract | Correct. This maps runtime ProducibleUnit (4-value) to observation channel index. It is NOT the action decode path. No confusion in caller code. | **PASS** | None |
| `ActionDecoder.cs` | Decodes `SIZE_PRODUCE_UNIT_TYPE` (7 values), `SIZE_ATTACK_TARGET` (49 values); no silent fallback | Correct. Extracts branch values with range check against `ActionContract.SIZE_PRODUCE_UNIT_TYPE` (7) and `ActionContract.SIZE_ATTACK_TARGET` (49). Uses `TryMapV2ProduceIndexToUnitType`. Has explicit `TryDecodeCell` path. No silent remap. | **PASS** | None |
| `ActionDecoder.cs` attack target 49 | No silent 49→9 fallback | Confirmed. Attack branch decoded from `SIZE_ATTACK_TARGET=49`. `TryGetAttackTargetPosition` called with validated index. ActionContractV2SmokeTest confirms index 49 is rejected. | **PASS** | None |
| `ActionDecoder.cs` produce type 7 | No silent 7→4 remap | Confirmed. Range check against `SIZE_PRODUCE_UNIT_TYPE=7`. Values 0-6 mapped via `TryMapV2ProduceIndexToUnitType`. Fallback to `ProducibleUnit.Worker` (index 3) with no silent remap. | **PASS** | Note: non-producible types (Resource=0, Base=1, Barracks=2) mapped by decoder but then gate-rejected by ActionApplier — this is documented behavior. |
| `ObservationContract.cs` | `GridH=24, GridW=24, ChannelsPerCell=27, TotalFloats=15552` | Correct. All constants confirmed. Spatial obs = `[24,24,27]` = 15552 floats. | **PASS** | None |
| `ObservationBuilder.cs` | Builds `[24,24,27]` spatial tensor; global features excluded from strict BC encoder path | Correct. `ObservationPackage` has `SpatialObservation` (15552 floats) and `GlobalFeatures` (zero-filled in `LegacyGymCompatible` mode). BC path uses spatial only; policy contract documented as `excluded_from_strict_bc_encoder_path`. | **PASS** | None |
| `ActionApplier.cs` | Authoritative runtime gate; ActionMask is pre-sampling diagnostic | Correct. ActionApplier validates actor existence, ownership, liveness before applying. Mask used as pre-submit filter only, not as final truth. `[DisallowMultipleComponent]` pattern maintained via callers. | **PASS** | None |
| `ActionMaskBuilder.cs` | Mask used as diagnostic/pre-sampling layer, NOT runtime truth | Correct. Mask built before action selection for filtering purposes. ActionApplier remains authoritative. SmokeTest confirms `ProduceUnitTypeMask.Length == 7` and `AttackTargetLocalMask.Length == 49`. | **PASS** | None |
| `Week6Day5SanityMatchRunner.cs` | One active student runner; DisallowMultipleComponent; bounded run; diagnostics output | Correct. `[DisallowMultipleComponent]` present. Has `_episodeCount`, `_maxStepsPerEpisode` bounds. Outputs JSON report. Logs action histogram, produce/attack frequency, invalid/ignored command share, episode summaries, first decoded commands. | **PASS** | None |
| `Week6Day4StudentInferenceDryRun.cs` | Checkpoint path must be updated to new v2-trained checkpoint | **WARNING.** Hardcoded default: `runs/day3_transfer_bc_main_20260423/student_bc_transfer_best.pt`. This checkpoint was trained on the OLD non-Legacy032 dataset. Has explicit "SKIPPED_CONFIG_REQUIRED" handling for v1 head mismatch (defensive, good). But no v2 Legacy032 checkpoint exists yet. | **WARNING** | Update `_checkpointRelativePath` Inspector field after new BC training smoke produces a v2 checkpoint. |
| `Week6StudentPolicyAdapter.cs` | Inference server integration; player control mode routing; no conflicting runner | Correct. `Week6PlayerControlMode` routing confirmed. No static autorun. Decision source configured via `Week6ConfiguredDecisionSource`. | **PASS** | None |
| `BaselineRolloutRunner.cs` / `Day6RewardSanitySmokeTest.cs` | Old Week4 runner; must not autorun alongside student | Correct. `Day6RewardSanitySmokeTest` reports to `WEEK4_Reports`. Not in Week6 runner chain. No shared `EpisodeController` conflict without explicit configuration. | **PASS** | Confirm not attached to same scene as Week6 sanity runners |
| `ActionContractV2SmokeTest.cs` / `ActionDecoderV2SmokeTest.cs` | Confirm branch sizes in code | Correct. Tests assert `SIZE_ATTACK_TARGET==49`, expected branches `[6,4,4,4,4,7,49]`, `AttackOffsets.Length==49`. No v1 sizes. | **PASS** | None |

---

## 5. Scene Readiness Verification

**Finding:** No `.unity` scene files were found by file system search in this workspace. The Unity scene asset files may not be tracked in git or may reside outside the searched paths.

The runtime components (`Week6Day5SanityMatchRunner`, `Week6StudentPolicyAdapter`, `Week6ConfiguredDecisionSource`) are implemented and compiled, but their Inspector wiring and scene attachment cannot be verified statically.

| Scene object / component | Expected | Actual | Status | Required action |
|--------------------------|----------|--------|--------|-----------------|
| `.unity` scene file | Must exist for sanity run | Not found in file search | **UNVERIFIED** | Confirm scene file exists in Unity Editor. Identify scene name. |
| Map size | 24×24 | `GameConstants.MapHeight=24, MapWidth=24` in C# — confirmed by `ObservationContract.TotalCells=576`. Actual Unity scene map not verifiable statically. | **UNVERIFIED** | Open scene in Editor; confirm map is 24×24 |
| Active student runner | One `Week6Day5SanityMatchRunner` (or equivalent) attached | `[DisallowMultipleComponent]` guards against duplicates. Not verifiable statically. | **UNVERIFIED** | Confirm component is attached to one GameObject only |
| Opponent/baseline runner | Must not conflict with student-controlled player | `Week6ConfiguredDecisionSource` routes by `Owner` — architectural separation confirmed. Not verifiable statically. | **UNVERIFIED** | Confirm `_player1Mode` and `_player2Mode` Inspector settings don't double-assign players |
| Bounded run | max steps / max episodes configured | `_maxStepsPerEpisode=200`, `_episodeCount=1` are [SerializeField] defaults. | **UNVERIFIED** | Confirm Inspector values are set appropriately for sanity run |
| Diagnostics output path | `_jsonReportRelativePath` set | Default: `python/week6_student/tmp/day5_sanity/...` | **UNVERIFIED** | Confirm path is correct and writable |
| Checkpoint / model path | Must point to v2-compatible Legacy032 BC checkpoint | No v2 checkpoint exists yet. Day4 component hardcodes old Day-3 path. | **FAIL (blocked)** | Produce v2 checkpoint first (after BC training smoke) |
| Contract logged at start | Contract version should appear in Unity logs | `ActionContract.cs` and `Week6Day4StudentInferenceDryRun.cs` validate `action_contract_version == "v2_gridnet_compatible"` from adapter JSON output. | **PASS (architecture)** | Confirm log output on first run |
| No old smoke runners active | No Week4/Week5 autorun components | Static: `Day6RewardSanitySmokeTest` is a separate component with `WEEK4_Reports` output. Not linked to Week6 runner. | **PASS (architecture)** | Confirm no such component is attached in the Week6 scene |
| Inspector references valid | All [SerializeField] references resolved | Not verifiable statically without Editor access. | **UNVERIFIED** | Open scene in Editor; run validation |
| Inference path adapter | Connected to Legacy032 v2 adapter/decoder | `Week6StudentPolicyAdapter` → `student_inference_adapter.py` → `load_student_checkpoint.py` → `StudentBCTransferModel`. Architecture is v2-correct. Checkpoint missing (see above). | **WARNING** | Wire correct checkpoint after BC training smoke |

---

## 6. Remaining Risks

### Semantic drift risks

- **Obs channel layout mismatch (known, documented):** gym-microrts Legacy032 obs uses HP/resource one-hot bands `[HP×5, Res×5, owner×3, unit_type×8, current_action×6]` (27ch). Unity `ObservationContract` uses scalar HP, scalar resources, then different one-hot encodings. The student trained on gym-microrts data will receive a Unity-format tensor at inference time. The `semantic_parity_claim: false` is contractually correct and explicitly stated. This is a **known risk** and should produce degraded behavior rather than crashes; however it means BC accuracy metrics on the gym-microrts validation set are not predictive of Unity behavior.
- **Spurious Move signal in dataset:** ~37% of dataset labels are Move actions from non-controlled cells (non-ready, non-teacher cells). Student will learn to produce Move from cells it doesn't control. This is a known dataset quality issue documented in the Day-6 effective behavior audit.

### Timing / mask risks

- **Mask is diagnostic only:** Action mask built in Unity is used as a pre-sampling filter. It does not guarantee ActionApplier acceptance. The Day-5 sanity run showed 126408/126447 actions rejected (owner mismatch, produce/attack semantics). BC training may not address this without explicit actor-targeting alignment.
- **Actor-selection alignment defect (known from Day 5):** student submissions targeting wrong-owner cells were the primary rejection cause in Day-5. This is a behavioral issue, not a contract issue.

### Attack target 7×7 runtime interpretation risks

- **49-value local index:** the attack branch encodes a 7×7 local offset from the actor cell. The decoder maps index → `GridPosition` via `TryGetAttackTargetPosition`. If the target cell is out of map bounds, the decoder silently produces an invalid action (subsequently rejected by ActionApplier). No silent fallback to 3×3/9 happens.
- **Center (index 24) = self-attack:** local index 24 maps to the actor's own cell. ActionApplier may reject self-attack depending on game rules. This is expected behavior.

### No-op dominance risk

- The Legacy032 3M teacher is behaviorally collapsed (confirmed in Day-6 audit: ready-actor NoOp=94.3%). Student trained on this data will be NoOp-dominant. This is a **behavioral quality risk**, not a structural/contract risk. Stage 0 verification does not require behavioral quality.

### Produce / attack low diversity risk

- Very low produce and attack frequency in teacher data means student heads for those branches will be under-trained. Metrics like `produce_frequency` and `attack_frequency` in Unity sanity run will likely be near-zero.

### Old v1 artifacts accidentally reused risk

- **`student_bc_model_minimal.py`**: active v1 head sizes (4, 9). Must be fixed before training.
- **`train_student_bc_minimal.py`**: default pinned dataset is old v1 non-Legacy032. Must be updated.
- **`runs/day3_transfer_bc_main_20260423/`**: existing checkpoint trained on old dataset. Do not label as "Legacy032 v2 student checkpoint."
- **`student_architecture_transfer.py` docstring**: stale v1 output sizes in docstring. Minor risk if future developer reads docstring as authoritative. Fix recommended.

---

## 7. Required Remediation

### A. Python fixes (required before BC training smoke)

#### Fix 1: `student_bc_model_minimal.py` — v1 head sizes (FAIL)

**File:** `python/week6_student/student_bc_model_minimal.py`

Change:
```python
self.head_produce_unit_type = nn.Conv2d(cfg.hidden_channels, 4, kernel_size=1)
self.head_attack_target_local = nn.Conv2d(cfg.hidden_channels, 9, kernel_size=1)
```
To:
```python
self.head_produce_unit_type = nn.Conv2d(cfg.hidden_channels, 7, kernel_size=1)
self.head_attack_target_local = nn.Conv2d(cfg.hidden_channels, 49, kernel_size=1)
```

Alternatively, add a module-level deprecation comment and a runtime `raise NotImplementedError` guard if this model variant is selected with a v2 dataset. The `transfer` variant (Day-3 architecture) is unaffected and should be preferred.

#### Fix 2: `train_student_bc_minimal.py` — stale PINNED_BC_READY_RELATIVE (FAIL)

**File:** `python/week6_student/train_student_bc_minimal.py`

Change:
```python
PINNED_BC_READY_RELATIVE = Path(
    "python/week5_teacher/teacher_exports_bc/"
    "day6_bc_ready_teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z"
)
```
To:
```python
PINNED_BC_READY_RELATIVE = Path(
    "python/week5_teacher_legacy032/teacher_exports_bc/"
    "day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z"
)
```

Also add a manifest `target_action_contract` check at load time to fail fast if a wrong dataset is provided via `--bc-ready-dir`.

### B. Unity fixes (required before Unity scene dry run)

#### Fix 3: `Week6Day4StudentInferenceDryRun.cs` — stale checkpoint path (WARNING)

After BC training smoke produces a v2 checkpoint, update the `_checkpointRelativePath` Inspector field (or the default in code) from:
```
python/week6_student/runs/day3_transfer_bc_main_20260423/student_bc_transfer_best.pt
```
To the new Legacy032 v2 checkpoint path.

This is a post-training fix; do not update before training.

### C. Scene fixes

- Locate or create the Unity scene for Week6 Legacy032 v2 sanity.
- Verify `Week6Day5SanityMatchRunner` is attached; confirm Inspector field values.
- Confirm `_checkpointRelativePath` in `Week6StudentPolicyAdapter` (or `Week6Day4StudentInferenceDryRun`) points to the post-training v2 checkpoint.
- Confirm `_player1Mode` / `_player2Mode` do not double-assign a player.
- Confirm no Week4/Week5 autorun components are in the same scene.

### D. Documentation / runbook fixes

#### Fix 4: `student_architecture_transfer.py` docstring (WARNING)

In the `forward()` docstring, update:
```
- produce_unit_type_logits: [B, 576, 4]
- attack_target_local_logits: [B, 576, 9]
```
To:
```
- produce_unit_type_logits: [B, 576, 7]
- attack_target_local_logits: [B, 576, 49]
```

---

## 8. Final Decision

> **GO_FOR_REMEDIATION**

**Gate sequence:**

```
Stage 0 (this report)
  └─ GO_FOR_REMEDIATION
       └─ Fix Python defects (Section 7-A)
            └─ GO_FOR_BC_TRAINING_SMOKE
                 └─ Produce v2 Legacy032 checkpoint
                      └─ Fix Unity scene / checkpoint path (Section 7-B/C)
                           └─ GO_FOR_SCENE_DRY_RUN
```

**Conditions for advancing to `GO_FOR_BC_TRAINING_SMOKE`:**
1. `student_bc_model_minimal.py` head sizes fixed (or model marked deprecated).
2. `train_student_bc_minimal.py` default path updated to new canonical dataset.
3. Smoke command: `python train_student_bc_minimal.py --bc-ready-dir <new_canonical_path> --model-variant transfer --epochs 3 --device cpu`

**Conditions for advancing to `GO_FOR_SCENE_DRY_RUN`:**
1. BC training smoke passes.
2. `student_bc_transfer_best.pt` exists in a new run directory with Legacy032 v2 lineage.
3. `Week6Day4StudentInferenceDryRun.cs` / `Week6StudentPolicyAdapter` checkpoint paths updated.
4. Unity scene verified in Editor (Section 5 UNVERIFIED items resolved).

**No-go conditions (none triggered at this time):**
- No hidden 49→9 or 7→4 remaps found in active code paths.
- No old v1 contract is in use in loader/metrics/transfer arch.
- ActionApplier remains authoritative runtime gate.
- No conflicting autorun runners detected architecturally.
