# Stage6R0 / Week6A0 Script Audit Report

## 1. Executive Summary

Final classification: `STAGE6R0_WEEK6_SCRIPT_AUDIT_BLOCKED_BY_PYTHON_CONTRACT_DRIFT`

Recommended next action: `FIX_WEEK6_PYTHON_STUDENT_PATH_FIRST`

Audit result in one sentence: the active Week 6 core contract code is mostly aligned to the current Legacy032 Unity v2 branch layout `[6,4,4,4,4,7,49]`, but the runnable Week 6 entrypoints are not yet aligned to the current canonical Stage5P4 BC-ready package, and the Unity bridge defaults are still pinned to older Week 6 checkpoint lineage.

Immediate blockers before any new BC smoke:

- `python/week6_student/train_student_bc_minimal.py` still defaults to a pre-Stage5P4 dataset path.
- `train_student_bc_minimal.py` still defaults to `--model-variant minimal`, while the Unity inference loader is strict about transfer-architecture checkpoints.
- `Assets/Scripts/ML/Week6StudentPolicyAdapter.cs` is pinned to an older Stage10D14 checkpoint path and filename allowlist.

Immediate blockers before Unity inference:

- `Week6StudentPolicyAdapter.cs` default checkpoint path and filename gating are stale.
- `Week6Day4StudentInferenceDryRun.cs` still points at an older May 1 checkpoint path and legacy dry-run assumptions.

Explicit non-actions during this audit:

- BC training was not run.
- Unity Editor was not launched.
- Unity Play Mode was not run by this audit.
- PPO fine-tuning was not run.
- Teacher training was not run.

## 2. Audit Scope And Constraints

Scope audited:

- `python/week6_student/`
- `python/week6_student/scripts/`
- `python/week6_student/reports/` as historical context only
- `Assets/Scripts/ML/`
- `Assets/Scripts/Gameplay/`
- `Assets/Scenes/`

Constraint handling:

- Static code inspection only.
- Safe Python checks only: `py_compile`, `--help`, dataset inspection, static scene-prep validator.
- No BC training, no PPO, no teacher training, no Unity launch, no Play Mode execution by this audit.
- No runtime C# behavior changes were made.
- No direct Gym-to-Unity semantic parity claim is made.
- No direct weight-transfer claim is made.
- No silent migration from v1 to v2 was performed.

## 3. Current Canonical Stage5P4 Input Contract

Canonical dataset directory:

- `python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_unity_v2_bc_ready_stage5p4_20260506T153632Z`

Canonical contract values verified from `bc_manifest.json`:

- `dataset_type`: `bc_ready_legacy032_unity_v2`
- `teacher_lineage`: `legacy032`
- `source_pipeline`: `gym_microrts==0.3.2`
- `target_action_contract`: `unity_v2_legacy032_gridnet`
- `observation_shape_per_sample`: `[576,27]`
- `action_shape_per_sample`: `[576,7]`
- `branch_sizes`: `[6,4,4,4,4,7,49]`
- `attack_target_semantics`: `local_7x7_49`
- `flatten_order`: `row_major`
- `flat_cell_index_formula`: `row * 24 + col`
- `direct_weight_transfer_claim`: `false`
- `semantic_parity_claim`: `false`

Verified split sizes from safe loader run:

- train: `31742`
- validation: `5601`
- observed train batch shape: `[8,24,24,27]`
- observed train target shape: `[8,576,7]`
- observed validation batch shape: `[8,24,24,27]`
- observed validation target shape: `[8,576,7]`

## 4. Files Discovered

The table below is intentionally scoped to files that are relevant to Week 6 Day 1-5 intent, not every later Stage10 artifact.

| File path | Language | Likely stage/day | Purpose | Status | Reason |
|---|---|---|---|---|---|
| `python/week6_student/student_bc_contract.py` | Python | Day 1 | BC-ready manifest contract model | canonical | Manifest-driven contract logic; compatible with Stage5P4 flat manifest fields. |
| `python/week6_student/student_branch_contract.py` | Python | Day 2-3 | Authoritative student branch order and sizes | canonical | Uses v2 branch sizes `[6,4,4,4,4,7,49]`. |
| `python/week6_student/student_bc_loader.py` | Python | Day 1 | Load BC-ready train/validation artifacts | canonical | Accepts `observations/actions` naming, reshapes `[N,576,27] -> [N,24,24,27]`, validates branch sizes. |
| `python/week6_student/student_bc_metrics.py` | Python | Day 2 | Branch-wise objective and active/inactive gating | canonical | Correct action-type-gated branch loss behavior; no v1 branch sizes. |
| `python/week6_student/inspect_bc_dataset.py` | Python | Day 1 | Safe BC-ready loader inspection CLI | canonical | Requires explicit `--bc-ready-dir`; passed against Stage5P4. |
| `python/week6_student/student_architecture_transfer.py` | Python | Day 3 | Transfer-aware student architecture | probably current | Architecture and transfer posture are aligned; no direct transfer claim. |
| `python/week6_student/partial_transfer_strategy.py` | Python | Day 3 | Document partial-transfer rules | probably current | Explicitly honesty-first, no full direct transfer claim. |
| `python/week6_student/load_student_checkpoint.py` | Python | Day 4 | Strict transfer-checkpoint loader | probably current | Correctly enforces transfer architecture state-dict shape. |
| `python/week6_student/student_bc_model_minimal.py` | Python | Day 2 | Minimal BC model | probably current | Head sizes are v2-correct, but not canonical for later Unity bridge because inference loader expects transfer architecture. |
| `python/week6_student/train_student_bc_minimal.py` | Python | Day 2 | Main BC training entrypoint | stale | Default dataset path is pre-Stage5P4; default `model_variant=minimal` is not aligned to later Unity checkpoint loading. |
| `python/week6_student/student_inference_adapter.py` | Python | Day 4 | Offline adapter from Unity observation to flat action tensor | probably current | Validates v2 branch contract and row-major flatten assumptions. |
| `python/week6_student/student_inference_server.py` | Python | Day 5 | Persistent inference bridge server | probably current | Thin server around the adapter; no training behavior. |
| `python/week6_student/scripts/validate_week6_scene_prep.py` | Python | Day 4-5 | Static scene wiring validation | probably current | Read-only scene/config validator; safe and useful. |
| `python/week6_student/scripts/generate_stage10r_noop_collapse_report.py` | Python | Post-Day 5 | Later diagnostic report generator | historical | Not part of original Day 1-5 path. |
| `python/week6_student/reports/LEGACY032_UNITY_V2_WEEK6_STAGE0_HANDOFF_VERIFICATION.md` | Markdown | Historical handoff | Historical verification report | historical | Contains outdated findings that no longer match current code. |
| `python/week6_student/runs/*` | Data/artifacts | Historical runs | Old checkpoints and metrics histories | historical | Useful provenance only; not canonical input for new smoke. |
| `python/week6_student/bc_ready/*` | Data/artifacts | Post-Day 5 | Later augmented datasets | historical | Not part of original Day 1-5 baseline scope. |
| `Assets/Scripts/ML/ActionContract.cs` | C# | Shared core | Unity-side action branch contract | canonical | Authoritative v2 constants: 7 branches, `produce=7`, `attack=49`. |
| `Assets/Scripts/ML/ActionDecoder.cs` | C# | Day 4 | Decode per-cell action tensor into `AgentAction` | canonical | Uses v2 produce/attack branches and mask-aware diagnostics without heuristic fallback. |
| `Assets/Scripts/ML/ActionApplier.cs` | C# | Day 4-5 | Authoritative runtime validation and command submit | canonical | Keeps `ActionApplier -> MatchManager.ApplyCommand()` authoritative. |
| `Assets/Scripts/ML/MlPolicyPipelineFacade.cs` | C# | Day 4 | Canonical observation/mask/decode/apply façade | canonical | Preserves downstream path and documents masks as non-authoritative. |
| `Assets/Scripts/ML/ObservationBuilder.cs` | C# | Day 4 | Build runtime `[24,24,27]` observation | probably current | Runtime output shape is correct; comments still reference older naming concepts. |
| `Assets/Scripts/ML/ObservationContract.cs` | C# | Shared core | Observation tensor shape/channel contract | probably current | Runtime size/channel count correct, but top-level compatibility wording still references `v0.6.1`. |
| `Assets/Scripts/ML/Week6StudentPolicyAdapter.cs` | C# | Day 4-5 | Live Unity student bridge | stale | Uses older default checkpoint path and older filename allowlist; active bridge logic itself is v2-aware. |
| `Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs` | C# | Day 4 | Technical dry-run component | stale | Default checkpoint path is stale and hardwired to older checkpoint naming. |
| `Assets/Scripts/ML/Week6Day5SanityMatchRunner.cs` | C# | Day 5 | Collect action/invalid/ignored diagnostics | probably current | Metrics surface is still useful and broad enough for Day 5 sanity. |
| `Assets/Scripts/ML/Week6VisualInspectionRunner.cs` | C# | Day 5 | Visual and global behavior diagnostics | probably current | Still includes focus cells B2/C3, but also writes global runtime diagnostics and histogram-style outputs. |
| `Assets/Scripts/ML/Week6EpisodeDiagnosticsCollector.cs` | C# | Day 5 | Structured episode diagnostics aggregation | probably current | Used by Day 5 runner; no evidence of v1-only assumptions. |
| `Assets/Scripts/ML/Week6ConfiguredDecisionSource.cs` | C# | Day 5 | Route student vs heuristic decision source | probably current | Control glue rather than contract owner, but still active in Week 6 path. |
| `Assets/Scripts/Gameplay/Match/EpisodeController.cs` | C# | Day 5 | Enables Week 6 one-student-side control mode | probably current | Static configuration checks still valid and safe. |
| `Assets/Scripts/Gameplay/Match/MatchBootstrap.cs` | C# | Day 4-5 | Scenario preset support including Week 6 layouts | probably current | Contains Week 6-specific scenario presets. |
| `Assets/Scenes/Week6_StudentSanity.unity` | Unity scene | Day 5 | Sanity-match scene | probably current | Exists and participates in Day 5 runner usage. |
| `Assets/Scenes/Week6_StudentVisualInspection.unity` | Unity scene | Day 5 | Visual inspection scene | probably current | Scene-prep validator targets it explicitly. |

## 5. Static Stale Marker Scan Results

The following occurrences matter most for Day 1-5 readiness. Historical artifacts are listed separately from active blockers.

| Occurrence | Line/context | Severity | Why it matters | Recommended action |
|---|---|---|---|---|
| `Assets/Scripts/ML/ObservationContract.cs` | line 8: `Gym-µRTS v0.6.1` | warning | Active comment still frames compatibility around `v0.6.1`, while current canonical source lineage is `gym_microrts==0.3.2`. Runtime code is fine, but the doc string is stale and can mislead future work. | Update wording to historical/reference-only language. |
| `Assets/Scripts/ML/ObservationBuilder.cs` | lines 5-6: `LegacyGymCompatibleSpec`, `UnityMvpTransferSpec` | warning | Active comments still use old observation-layer naming; not a runtime blocker, but stale terminology can suggest older contract targets are still canonical. | Clarify that these are observation modes only, not the active Week 6 target contract. |
| `python/week6_student/train_student_bc_minimal.py` | lines 28-30: pinned dataset `day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z` | blocker | Default training entrypoint is not pinned to the current Stage5P4 canonical package. Running BC smoke naively would not use the current canonical input. | Update default to Stage5P4 or require explicit `--bc-ready-dir`. |
| `Assets/Scripts/ML/Week6StudentPolicyAdapter.cs` | line 492: default checkpoint path points to `legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z` | blocker | Live Unity bridge defaults to an older checkpoint lineage, not a future canonical Stage6 smoke artifact. | Replace with explicit configurable canonical path policy before Unity inference. |
| `Assets/Scripts/ML/Week6StudentPolicyAdapter.cs` | lines 1046-1054: hardcoded filename allowlist for `student_bc_transfer_best.pt`, `student_bc_semantic_best.pt`, `student_bc_stage10d14_augmented_best.pt`, `student_bc_stage10d17_movement_augmented_best.pt`, `student_bc_stage10d19b_valid_move_best.pt` | blocker | Filename gating is tied to older run families and may reject a fresh canonical Week 6 checkpoint name even when branch shapes are valid. | Replace with branch-contract validation as the primary gate, with path policy documented separately. |
| `Assets/Scripts/ML/Week6StudentPolicyAdapter.cs` | lines 441-445 and 1653-1656: explicit v1 payload rejection `[6,4,4,4,4,4,9]` | historical-ok | This is a good guard, not a regression. It proves v1 artifacts are actively rejected. | Keep; do not treat as active v1 usage. |
| `Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs` | line 80: old checkpoint path `legacy032_v2_bc_minimal_20260501T195501Z` | warning | Day 4 dry-run entrypoint is pinned to an old artifact and will mislead later validation if reused. | Update or clearly mark as historical. |
| `Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs` | line 259: explicit message for v1 head mismatch `produce=4, attack=9` | historical-ok | Useful guardrail proving the dry run rejects old head sizes. | Keep. |
| `python/week6_student/runs/day2_minimal_bc_proof_learning_20260422/day2_minimal_metrics_history.json` and related old run JSONs | `day6_bc_ready_teacher_adapted_day5_hardened_v2` / `corrective_sl2000` | historical-ok | Historical run outputs still reference old teacher-adapted datasets. They should not be treated as canonical Week 6 inputs now. | Preserve as history, exclude from canonical path. |
| `python/week6_student/reports/LEGACY032_UNITY_V2_WEEK6_STAGE0_HANDOFF_VERIFICATION.md` | older failure text about minimal model and old dataset path | historical-ok | This report is stale relative to current code and should not be used as source of truth. | Treat as historical context only. |
| `python/week6_student/stage10d14_*` and augmented dataset metadata | repeated `local_3x3` / `actor_noop_plus_local_3x3_runtime_action_context` | historical-ok | These are later augmentation experiments, not original Day 1-5 canonical contract definitions. | Keep out of baseline Day 1-5 BC smoke path. |
| `Assets/Scripts/ML/Week6VisualInspectionRunner.cs` | `predicted_noop`, focus-cell diagnostics, plus Stage10D10 global runtime report paths | warning | `predicted_noop` is diagnostic telemetry, not a heuristic fallback. The runner still highlights B2/C3, but it also emits global diagnostics. | Keep global diagnostics; optionally reduce narrative overemphasis on B2/C3 later. |

## 6. Python Student-Side Audit

### Findings

What is correct now:

- `student_bc_loader.py` successfully loaded the canonical Stage5P4 package through `inspect_bc_dataset.py` and reshaped observations to `[N,24,24,27]`.
- Loader compatibility is explicit: it accepts canonical arrays named `observations/actions` and normalizes them to `input_tensor/target_action_branches`.
- Target shapes and branch sizes are correct: `[B,576,7]` with `[6,4,4,4,4,7,49]`.
- `student_bc_metrics.py` uses explicit action-type-gated branch-wise loss, so inactive branches are not penalized.
- `student_architecture_transfer.py` is aligned to the v2 branch contract and explicitly avoids full direct-transfer claims.
- `load_student_checkpoint.py` is strict and only accepts transfer-architecture checkpoints for inference.

What is stale or blocking:

- `train_student_bc_minimal.py` still defaults to a pre-Stage5P4 dataset path.
- `train_student_bc_minimal.py` still defaults to `--model-variant minimal`, while `load_student_checkpoint.py` only supports transfer checkpoints for inference.
- There is no dedicated canonical Stage6 smoke wrapper yet that bakes in Stage5P4 plus transfer architecture together.

### Per-requirement audit

| Requirement | Result | Evidence |
|---|---|---|
| Loader expects current Stage5P4 package schema | pass | `inspect_bc_dataset.py --bc-ready-dir <Stage5P4>` passed; loader treated flat manifest as compatible `day6.bc_ready.v1`. |
| Loader reads `observations/actions` as needed | pass | `student_bc_loader.py` maps `observations -> input_tensor` and `actions -> target_action_branches` when needed. |
| Loader supports observations `[N,576,27]` | pass | Loader explicitly reshapes `[N,576,27]` to `[N,24,24,27]`. |
| Reshape to `[N,24,24,27]` explicit and correct | pass | Implemented in loader with row-major 24x24 assumption. |
| Model outputs 7 heads `[6,4,4,4,4,7,49]` | pass | `student_architecture_transfer.py` and `student_bc_model_minimal.py` are v2-correct. |
| No old produce head size 4 | pass in active models | Both inspected model files now use 7 for produce. |
| No old attack head size 9 | pass in active models | Both inspected model files now use 49 for attack. |
| Branch-wise loss uses correct semantics | pass | `student_bc_metrics.py` gates branches by action type target. |
| Target shape `[B,576,7]` | pass | Verified by Stage5P4 loader run. |
| Inactive branch logic explicit | pass | Implemented in `compute_branchwise_loss`. |
| Masks not treated as runtime truth | pass | Loader/metrics path is mask-agnostic; optional mask is not authoritative. |
| Train script points to Stage5P4 or accepts `--bc-ready-dir` | pass-with-warning | CLI accepts `--bc-ready-dir`, but default path is stale. |
| No hardcoded old BC-ready directory | fail | Default pinned path is not Stage5P4. |
| No hidden direct weight transfer path | pass | Partial-transfer policy is explicit and conservative. |
| Checkpoint save/load path is clear | pass-with-warning | Save/load mechanics are clear, but default training and inference variants are misaligned. |
| Validation loop present | pass | `train_student_bc_minimal.py` runs validation each epoch. |
| Dry-run/smoke mode exists or can be safely added later | pass-with-warning | `inspect_bc_dataset.py` gives safe loader smoke; no dedicated Stage5P4 training smoke wrapper yet. |

### Python conclusion

Core contract support is good enough for Stage5P4, but the canonical Week 6 BC smoke entrypoint is not yet safe because its defaults still point at older artifacts and older workflow assumptions.

## 7. Unity Inference-Side Audit

### Findings

What is correct now:

- `ActionContract.cs` is fully v2-correct: 7 branches, produce size 7, attack size 49, total flat size `44928`.
- `ActionDecoder.cs` decodes v2 produce and local 7x7 attack parameters.
- `ActionApplier.cs` remains authoritative and still submits through `MatchManager.ApplyCommand()`.
- `MlPolicyPipelineFacade.cs` keeps the intended runtime path: observation -> mask -> decoder -> applier.
- `Week6StudentPolicyAdapter.cs` rejects v1 branch sizes and validates adapter branch sizes/order/action contract version.
- `Week6Day5SanityMatchRunner.cs` still exports action histogram, `produce_frequency`, `attack_frequency`, `invalid_command_share`, `ignored_command_share`.
- `Week6VisualInspectionRunner.cs` still emits focus-cell diagnostics but also writes global runtime diagnostic artifacts (`stage10d10_global_runtime_*`).

What is stale or blocking:

- `Week6StudentPolicyAdapter.cs` default checkpoint path points at an older Stage10D14 checkpoint.
- `Week6StudentPolicyAdapter.cs` filename allowlist is tailored to old run families and may block a new canonical checkpoint name.
- `Week6Day4StudentInferenceDryRun.cs` is pinned to an older checkpoint path and older validation target.

### Per-requirement audit

| Requirement | Result | Evidence |
|---|---|---|
| Observation builder outputs `24x24x27` | pass | `ObservationContract.TotalFloats = 15552`; builder and visual runner use `[24,24,27]`. |
| Bridge expects correct input layout | pass | Python adapter expects `24x24x27` observation buffer and validates shape. |
| Flatten order is row-major `row * 24 + col` | pass | Stage5P4 manifest, visual runner fallback string, and adapter diagnostics all use row-major indexing. |
| Decoder expects 7 branches | pass | `ActionContract.ActionBranchCount = 7`; decoder uses all 7 branches. |
| Branch 5 is produce size 7 | pass | `ActionContract.SIZE_PRODUCE_UNIT_TYPE = 7`; decoder and applier follow it. |
| Branch 6 is attack size 49 | pass | `ActionContract.SIZE_ATTACK_TARGET = 49`; decoder and applier follow it. |
| No active decoder path assumes 3x3 attack target | pass | Active runtime contract is 7x7/49; 3x3 appears only in historical augmentation artifacts or old terminology. |
| No active contract forces 9-way attack target | pass | Active code explicitly rejects v1 `[...4,9]` payloads. |
| Mask policy explicit and non-authoritative | pass | Decoder and pipeline comments state masks are pre-submit hints; `ActionApplier` remains final truth. |
| Runtime still goes through `ActionApplier / MatchManager.ApplyCommand` | pass | `MlPolicyPipelineFacade` and `ActionApplier` preserve this path. |
| No heuristic/fake/random fallback silently used | pass-with-warning | No heuristic/random fallback found in active student path; masked-out choices fall back to NoOp explicitly and diagnostically. |
| Checkpoint/model filename gating accepts current student checkpoint names or is documented | fail | Active allowlist is stale and tied to older names only. |
| Visual inspection runner can collect global diagnostics | pass-with-warning | It still has B2/C3 focus cells, but also emits global runtime snapshots and summaries. |
| Action histogram / produce / attack / invalid / ignored share observable | pass | Day 5 runner still computes all requested aggregates. |
| `command_built=false` / `predicted_noop` / rejection reasons observable | pass | Visual runner and day 5 pipeline retain these diagnostics. |

### Unity conclusion

The active Unity-side contract and runtime decode/apply path are not the main source of drift. The stale layer is the bridge configuration surface: default checkpoint path selection and filename gating.

## 8. Day 1-5 Readiness Matrix

| Day | Scope | Status | Evidence | Blockers | Required fixes |
|---|---|---|---|---|---|
| Day 1 | Student-side loader and BC contract | `PASS_WITH_WARNINGS` | Stage5P4 dataset inspection passed; loader supports `[576,27]` and `[576,7]`; contract and branch sizes are correct. | Canonical training entrypoint does not default to Stage5P4. | Point canonical entrypoint at Stage5P4 or require explicit `--bc-ready-dir`. |
| Day 2 | Minimal BC training loop | `FAIL` | Training loop, branch losses, validation loop, and v2 branch sizes are present. | Default dataset path is stale; default model variant is `minimal`, but later inference loader expects transfer checkpoints. | Update canonical smoke entrypoint to Stage5P4 + `--model-variant transfer`, or create a dedicated smoke wrapper. |
| Day 3 | Student architecture and partial transfer strategy | `PASS` | `student_architecture_transfer.py`, `partial_transfer_strategy.py`, and checkpoint loader are conservative and v2-aligned. | None at architecture-contract level. | None before audit close. |
| Day 4 | Unity-side inference path | `FAIL` | Core Unity contract is v2-correct and rejects v1 payloads. | Student bridge default checkpoint path and filename allowlist are stale; Day4 dry-run component is stale. | Update bridge path policy and filename gating to future canonical checkpoint naming. |
| Day 5 | Behavior sanity diagnostics | `PASS_WITH_WARNINGS` | Day5 runner still collects invalid/ignored share, action histogram, produce frequency, attack frequency; visual runner also has global diagnostics. | Inherits Day4 bridge/checkpoint staleness; visual narrative still leans on B2/C3 focus cells. | Fix Day4 bridge path/gating first; optionally rebalance visual reporting toward global diagnostics. |

## 9. Blockers

- `train_student_bc_minimal.py` default BC-ready dataset path is not the current canonical Stage5P4 package.
- `train_student_bc_minimal.py` default model variant is not aligned with the later Unity inference loader.
- `Week6StudentPolicyAdapter.cs` default checkpoint path is stale.
- `Week6StudentPolicyAdapter.cs` checkpoint filename allowlist is stale and may reject a valid new canonical checkpoint name.
- `Week6Day4StudentInferenceDryRun.cs` is pinned to an older checkpoint path and should not be treated as canonical Day 4 validation in its current form.

## 10. Warnings

- `ObservationContract.cs` and `ObservationBuilder.cs` still contain older compatibility terminology (`v0.6.1`, `LegacyGymCompatibleSpec`, `UnityMvpTransferSpec`) in comments.
- `Week6VisualInspectionRunner.cs` still foregrounds B2/C3 focus diagnostics, though it does also emit global runtime diagnostics.
- Historical Week 6 reports in `python/week6_student/reports/` include stale conclusions and should not be used as source of truth.
- Historical run artifacts in `python/week6_student/runs/` and later augmented datasets in `python/week6_student/bc_ready/` are not canonical inputs for a fresh Stage6 BC smoke.

## 11. Historical / Stale Scripts And Artifacts

- `python/week6_student/reports/LEGACY032_UNITY_V2_WEEK6_STAGE0_HANDOFF_VERIFICATION.md`
- `python/week6_student/runs/*`
- `python/week6_student/bc_ready/*` under Stage10D14/17/19 augmentation families
- `python/week6_student/scripts/generate_stage10r_noop_collapse_report.py`
- `Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs` in its current default configuration

## 12. Canonical Scripts List

For the original Week 6 Day 1-5 intent, the closest current canonical set is:

- `python/week6_student/student_bc_contract.py`
- `python/week6_student/student_branch_contract.py`
- `python/week6_student/student_bc_loader.py`
- `python/week6_student/student_bc_metrics.py`
- `python/week6_student/student_architecture_transfer.py`
- `python/week6_student/load_student_checkpoint.py`
- `python/week6_student/inspect_bc_dataset.py`
- `python/week6_student/student_inference_adapter.py`
- `python/week6_student/student_inference_server.py`
- `python/week6_student/scripts/validate_week6_scene_prep.py`
- `Assets/Scripts/ML/ActionContract.cs`
- `Assets/Scripts/ML/ActionDecoder.cs`
- `Assets/Scripts/ML/ActionApplier.cs`
- `Assets/Scripts/ML/MlPolicyPipelineFacade.cs`
- `Assets/Scripts/ML/ObservationBuilder.cs`
- `Assets/Scripts/ML/Week6Day5SanityMatchRunner.cs`
- `Assets/Scripts/ML/Week6VisualInspectionRunner.cs`
- `Assets/Scripts/Gameplay/Match/EpisodeController.cs`
- `Assets/Scenes/Week6_StudentSanity.unity`
- `Assets/Scenes/Week6_StudentVisualInspection.unity`

## 13. Recommended Next Action

Recommended action code: `FIX_WEEK6_PYTHON_STUDENT_PATH_FIRST`

Why this is the next entrypoint instead of going directly to BC smoke:

- The core loader already proves it can read Stage5P4 correctly.
- The runnable BC smoke entrypoint still defaults to an older dataset path and the wrong default architecture variant for later Unity inference.
- Fixing those Python-side entrypoint defaults first is the shortest safe path to a meaningful BC smoke.

Secondary action after that, before Unity inference:

- Fix `Week6StudentPolicyAdapter.cs` default checkpoint path and filename gating.

## 14. Final Classification

`STAGE6R0_WEEK6_SCRIPT_AUDIT_BLOCKED_BY_PYTHON_CONTRACT_DRIFT`

Justification:

- The active Week 6 contract implementation is not blocked by a v1 branch-layout regression.
- The active Unity runtime decode/apply path is v2-aware.
- The earliest hard blocker before the requested next phase is Python-side entrypoint drift from the current Stage5P4 canonical package.

## Safe Checks Run

Executed during this audit:

- `py_compile` over the active Week 6 Python entrypoints and support modules: pass.
- `--help` on `train_student_bc_minimal.py`: pass.
- `--help` on `inspect_bc_dataset.py`: pass.
- `--help` on `student_inference_adapter.py`: pass.
- `--help` on `student_inference_server.py`: pass.
- `python/week6_student/scripts/validate_week6_scene_prep.py`: pass and wrote `python/week6_student/reports/LEGACY032_UNITY_V2_SCENE_PREP_VALIDATION.json`.
- `inspect_bc_dataset.py --bc-ready-dir python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_unity_v2_bc_ready_stage5p4_20260506T153632Z --batch-size 8 --json`: pass.
- Problems-panel check on key Python and C# files: no errors found.
