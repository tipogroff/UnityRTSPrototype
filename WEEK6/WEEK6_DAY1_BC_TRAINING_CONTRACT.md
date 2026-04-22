# Week 6 Day 1 - Student-side BC Training Contract

## Scope and Honesty

This artifact defines the Day 1 student-side contract over Week 5 BC-ready artifacts only.

- This is not Unity-side runtime integration.
- This is not proof of transfer correctness.
- This is not direct full weight transfer.
- This does not close all compatibility gaps.

Authoritative runtime truth remains in Unity runtime systems (ActionApplier / MatchManager).
Masking is treated as pre-sampling or diagnostic context and never as runtime authority.

## Canonical Input Artifacts (Day 1)

Required files in BC-ready run directory:

- `bc_manifest.json`
- `bc_train.npz`
- `bc_validation.npz`

Optional file for diagnostics only:

- `bc_debug.npz`

Day 1 student entrypoint reads only BC-ready artifacts and does not read raw rollout or adapted batch artifacts.
Day 1 does not modify Week 5 schema or file naming.

## A. Input Contract

- Primary model input is `input_tensor` from BC-ready splits.
- For current canonical schema, per-sample input shape is `[24, 24, 27]` and dtype is `float32`.
- If global features exist in future artifacts, they are optional auxiliary or diagnostic context only.
- Global features are not promoted to mandatory primary input on Day 1.

## B. Target Contract

- Supervised target key is `target_action_branches` from BC-ready splits.
- Day 1 uses stored canonical branch targets and does not invent a new action schema.
- Current per-sample target shape is `[576, 7]`, dtype `int16`, branch sizes `[6, 4, 4, 4, 4, 4, 9]`.
- Branch names are fixed to transfer-compatible semantics:
  - `action_type`
  - `move_dir`
  - `harvest_dir`
  - `return_dir`
  - `produce_dir`
  - `produce_unit_type`
  - `attack_target_local`
- If actor-selection is absent as explicit label, Day 1 does not invent or backfill it.
- Day 2 branch-wise objective must avoid penalizing inactive branches.

## C. Optional Mask Contract

- Optional mask is a training helper or diagnostic context only.
- Loader supports three states:
  - mask present (`optional_mask` exists and is consistent);
  - mask absent (no `optional_mask` array);
  - partial or unavailable marker via manifest metadata.
- Loader never synthesizes mask and never interprets missing mask as authoritative all-valid truth.
- Loader returns explicit split-level mask availability flags.

## D. Metadata Contract

Metadata is diagnostic/provenance context only and never supervision target.

Required metadata arrays per split:

- `sample_id`
- `episode_id`
- `step_id`
- `source_episode_file`

Manifest metadata usage is limited to:

- provenance;
- split description;
- diagnostics and warnings;
- class imbalance awareness;
- semantic weakening or remap-to-noop awareness;
- inactive-branch anomaly awareness.

Metadata is not auto-injected into model input.

## E. Failure Policy (Fail Fast)

Loader raises explicit error when any condition is violated:

- missing required file (`bc_manifest.json`, `bc_train.npz`, `bc_validation.npz`);
- unknown or unsupported schema/contract version;
- missing required arrays in split files;
- train/validation schema mismatch;
- dtype mismatch vs manifest contract;
- shape mismatch vs manifest contract;
- sample-count mismatch across required arrays;
- branch-size mismatch;
- split marker mismatch;
- manifest split path mismatch with canonical BC-ready run files.

No silent repair, remap, fallback, or synthetic reconstruction is allowed.

## F. Day 1 Entrypoints

- `python/week6_student/student_bc_contract.py`: typed dataclasses and contract definitions.
- `python/week6_student/student_bc_loader.py`: strict BC-ready loader and contract validation.
- `python/week6_student/inspect_bc_dataset.py`: CLI inspection entrypoint for Day 1 smoke.

Inspection entrypoint responsibility:

- load manifest/train/validation;
- validate contract and split consistency;
- iterate at least one batch for train/validation;
- print concise shape/dtype/targets/mask summary;
- print manifest diagnostic warnings if present.

## Carry-over Risks for Day 2

- Action class imbalance can bias supervised objective and metrics.
- Inactive-branch anomalies require explicit branch-wise loss gating policy.
- Semantic weakening and remap-to-noop pressure remain unresolved by Day 1 loading.
- Optional mask may be absent; Day 2 must not equate missing mask with runtime validity.
- Teacher quality drift remains a data-quality risk and is not solved by Day 1 contract validation.
