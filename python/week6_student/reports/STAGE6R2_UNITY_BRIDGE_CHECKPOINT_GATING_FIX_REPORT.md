# Stage6R2 Unity Bridge Checkpoint Gating Fix Report

## 1. Executive summary

Final decision: `STAGE6R2_UNITY_BRIDGE_FIX_PASS_READY_FOR_DRY_RUN`

Stage6R2 completed a static/configuration fix of Unity bridge checkpoint defaults and filename gating policy so that the Stage6A2 transfer-compatible checkpoint can be used without relying on old Stage10D filename families. Acceptance is now contract-driven through bridge initialization and adapter payload validation (branch order/sizes/action contract), while explicit v1 rejection remains enforced.

## 2. Changed files

- `Assets/Scripts/ML/Week6StudentPolicyAdapter.cs`
- `Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs`

Reports added:

- `python/week6_student/reports/STAGE6R2_UNITY_BRIDGE_CHECKPOINT_GATING_FIX_REPORT.md`
- `python/week6_student/reports/stage6r2_unity_bridge_checkpoint_gating_fix_report.json`

## 3. Previous blockers

1. `Week6StudentPolicyAdapter` default checkpoint path was pinned to Stage10D14 artifact lineage.
2. `Week6StudentPolicyAdapter` acceptance used stale filename allowlist (`student_bc_stage10d14*`, `student_bc_stage10d17*`, `student_bc_stage10d19b*`, etc.).
3. `Week6Day4StudentInferenceDryRun` default checkpoint path was pinned to old minimal run artifact.

## 4. Stage6A2 checkpoint selected

Selected canonical checkpoint:

- `python/week6_student/runs/legacy032_v2_bc_short_stage6a2/legacy032_v2_bc_short_stage6a2_smoke_checkpoint.pt`

Old defaults replaced:

- Adapter old path: `python/week6_student/runs/legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z/student_bc_stage10d14_augmented_best.pt`
- Day4 old path: `python/week6_student/runs/legacy032_v2_bc_minimal_20260501T195501Z/student_bc_transfer_best.pt`

## 5. Week6StudentPolicyAdapter changes

1. Default `_checkpointRelativePath` updated to Stage6A2 checkpoint.
2. Stale filename allowlist removed as authoritative gate.
3. Startup policy now checks:
   - file exists;
   - checkpoint extension is `.pt`;
   - bridge ready handshake succeeds;
   - if `checkpoint_model_variant` is present, it must be `transfer`.
4. Compatibility enforcement remains payload/contract-based via `ValidateAdapterPayload`:
   - expected branch order;
   - expected branch sizes from `ActionContract` -> `[6,4,4,4,4,7,49]`;
   - expected `action_contract_version = v2_gridnet_compatible`;
   - expected flat size `44928`.

## 6. Week6Day4StudentInferenceDryRun changes

1. Default `_checkpointRelativePath` updated to Stage6A2 checkpoint.
2. Added explicit comment that Stage6A2 is the canonical checkpoint candidate for current dry-run wiring.
3. Removed stale strict filename check (`student_bc_transfer_best.pt`) and replaced with `.pt` extension guard.
4. Existing adapter payload validation path remains unchanged and still enforces v2 contract compatibility.

## 7. Checkpoint gating policy after fix

Policy summary:

1. Filename family is metadata only (not the compatibility truth source).
2. Adapter/server startup success is required.
3. Compatibility is validated using real adapter metadata/payload contract checks:
   - branch count 7;
   - branch sizes `[6,4,4,4,4,7,49]`;
   - produce head 7;
   - attack head 49;
   - action contract version `v2_gridnet_compatible`.
4. Incompatible payloads fail explicitly with diagnostics; no silent acceptance.

## 8. v1 rejection policy after fix

Preserved.

- `Week6StudentPolicyAdapter` still rejects legacy v1 branch layout `[6,4,4,4,4,4,9]` with explicit error: `v1 action contract artifact is incompatible with Unity v2 runtime`.
- `Week6Day4StudentInferenceDryRun` still includes explicit v1 mismatch handling (`produce=4, attack=9`) and v1 contract rejection in payload validation.

## 9. Runtime truth and mask policy preservation

No changes were made to runtime-authoritative path components.

Verified via static inspection:

- `MlPolicyPipelineFacade`: observation -> mask -> decoder -> applier -> `MatchManager.ApplyCommand()` path unchanged.
- `ActionApplier` remains authoritative runtime validation gate.
- Masking remains pre-submit/diagnostic helper; it does not replace runtime truth.
- No new heuristic/fake/random inference fallback was introduced in Stage6R2 edits.

## 10. Static validation checks

1. C# diagnostics check (`Problems`): no errors in edited files.
2. Requested stale-path search in `Assets/Scripts/ML/**/*.cs`:
   - old Stage10D and old minimal strings still exist in historical/editor helper files outside Stage6R2 target files;
   - target bridge files no longer carry old defaults.
3. Old v1-active assumptions scan:
   - no active branch size regression introduced;
   - v1-size references remain only as explicit rejection diagnostics.
4. Stage6A2 checkpoint default presence confirmed in both target files.
5. Scene prep validator executed (safe/static):
   - command: `c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week6_student/scripts/validate_week6_scene_prep.py`
   - result: report written to `python/week6_student/reports/LEGACY032_UNITY_V2_SCENE_PREP_VALIDATION.json`.

## 11. Remaining warnings

1. Historical Editor menu scripts and legacy helper scripts still contain old checkpoint path constants; they were not in Stage6R2 mandatory modification scope.
2. Scene-prep validation report may still reference historical checkpoint metadata in its own output payload, independent of the two bridge default fixes.

## 12. Final decision

`STAGE6R2_UNITY_BRIDGE_FIX_PASS_READY_FOR_DRY_RUN`

## 13. Recommended next stage

`Stage6R3 — Unity-side inference dry-run without match-quality claims`

## Explicit non-actions in Stage6R2

- Unity Play Mode was not run.
- BC training was not run.
- PPO fine-tuning was not run.
- Teacher training was not run.
- No Python training artifacts or Week 5 artifacts were modified as part of this fix scope.
