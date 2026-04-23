# Week 6 Day 4 - Student Inference Wiring Dry Run

Date: 2026-04-23

## Scope

Day 4 scope is technical wiring only:

- Unity observation -> student inference -> Unity decoder -> command submission.
- No gameplay quality evaluation.
- No transfer-success claim.

Pinned BC-ready lineage source remains unchanged:

- `python/week5_teacher/teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z`

## Checkpoint used

Student checkpoint used as inference source:

- `python/week6_student/runs/day3_transfer_bc_main_20260423/student_bc_transfer_best.pt`
- model variant: `transfer`
- best epoch: `23`
- best validation loss: `0.33216089120416353`

No teacher checkpoint was used for Day 4 inference wiring.

## Inference route selected

### Unity-side canonical route (unchanged)

- observation: `ObservationBuilder.BuildObservationPackage(...)`
- decode/apply path: `MlPolicyPipelineFacade.ExecuteTransferCompatible(...)`
- downstream: `ActionDecoder.DecodeTransferCompatibleBatch(...)` -> `ActionApplier.ApplyActions(...)` -> `MatchManager.ApplyCommand(...)`

### Day 4 bridge (minimal, explicit)

- Unity dry-run component:
  - `Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs`
- Python adapter:
  - `python/week6_student/student_inference_adapter.py`
- Python checkpoint loader:
  - `python/week6_student/load_student_checkpoint.py`

Bridge contract:

1. Unity writes one observation buffer (float32, 24*24*27) to binary file.
2. Python adapter loads student checkpoint and runs inference.
3. Adapter validates logits keys/order/shape against authoritative contract.
4. Adapter emits transfer-compatible `action_flat` (size 20160) without branch reorder.
5. Unity feeds `action_flat` to existing canonical decoder/apply pipeline.

This is intentionally a Day 4 adapter bridge, not a production deployment claim.

## Authoritative branch contract preservation

Authoritative source of truth remains:

- `python/week6_student/student_branch_contract.py`

Adapter imports and validates:

- canonical branch order:
  1. action_type
  2. move_dir
  3. harvest_dir
  4. return_dir
  5. produce_dir
  6. produce_unit_type
  7. attack_target_local
- branch sizes: `[6, 4, 4, 4, 4, 4, 9]`
- logits keys:
  - `action_type_logits`
  - `move_dir_logits`
  - `harvest_dir_logits`
  - `return_dir_logits`
  - `produce_dir_logits`
  - `produce_unit_type_logits`
  - `attack_target_local_logits`

Fail-fast rules:

- mismatch in observation size/dtype -> fail
- mismatch in logits keys/order -> fail
- mismatch in logits shape -> fail
- mismatch in branch size/index range -> fail
- mismatch in produced action flat size -> fail

No silent shape repair and no silent branch rearrangement are allowed.

## Validation status (Day 4)

### A) Observation contract

Validated in two places:

1. Unity dry-run component checks `ObservationBuilder.ValidateObservation(...)` and total length `15552`.
2. Python adapter checks exact shape `[24,24,27]` and dtype `float32` before inference.

### B) Model output reading

Python adapter enforces exact key set and order from authoritative contract and validates output shapes:

- `action_type_logits`: `[1,576,6]`
- `move_dir_logits`: `[1,576,4]`
- `harvest_dir_logits`: `[1,576,4]`
- `return_dir_logits`: `[1,576,4]`
- `produce_dir_logits`: `[1,576,4]`
- `produce_unit_type_logits`: `[1,576,4]`
- `attack_target_local_logits`: `[1,576,9]`

### C) Branch decoding agreement

Agreement checks are enforced by:

- authoritative branch contract validation in Python;
- transfer-compatible `action_flat` encoding with fixed branch offsets;
- Unity-side size verification against `ActionContract` and canonical decode/apply route.

## Dry run result

Executed technical dry run of the Python bridge adapter using the student checkpoint:

- input source for this run: one sample from pinned BC-ready `bc_validation.npz` (`input_tensor[0]`), shaped to `[24,24,27]` float32.
- command result: `PASS`
- produced `action_flat_size`: `20160`
- temporary artifact path used during local validation:
  - `python/week6_student/tmp/day4_adapter_result.json` (generated and cleaned up after verification)

Unity in-editor execution hook is implemented in:

- `Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs`

Confirmed Unity Play Mode smoke run (canonical path) completed with machine-readable report:

- report path:
  - `python/week6_student/tmp/day4_unity_playmode_smoke_report.json`
- report payload (compact):
  - `status`: `pass`
  - `checkpoint_path`: `python/week6_student/runs/day3_transfer_bc_main_20260423/student_bc_transfer_best.pt`
  - `observation_validated`: `true`
  - `python_adapter_status`: `ok`
  - `action_flat_size`: `20160`
  - `unity_decode_submit_status`: `pass`
  - `canonical_path_reached`: `true`
  - `error`: `""`

This run confirms Day 4 canonical Unity route invocation only; it does not make gameplay-quality or transfer-success claims.

## Known limitations and risks

1. Day 4 confirms technical wiring and contract alignment, not gameplay strength.
2. Adapter bridge uses Python process call (intentional interim integration step).
3. Runtime timing/mask semantic drift (Day 6 scope) is not solved by Day 4.
4. No claim is made that this dry run proves transfer correctness in matches.

## Explicit non-claims

- No gameplay strength claim.
- No runtime transfer correctness claim.
- No claim that Day 4 dry run validates full production deployment.
