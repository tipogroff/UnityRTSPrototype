# Week 6 Day 3.5 - Authoritative Branch Contract and Wiring Prep

Date: 2026-04-23

## Scope and intent

This step introduces one machine-readable source of truth for branch order and head mapping.

- No Unity export implementation is added.
- No RL or PPO logic is added.
- No transfer-success claim is added.
- Day 2 BC semantics remain unchanged.

## Authoritative contract module

New file:

- `python/week6_student/student_branch_contract.py`

Canonical branch order is fixed as:

1. action_type
2. move_dir
3. harvest_dir
4. return_dir
5. produce_dir
6. produce_unit_type
7. attack_target_local

Canonical sizes:

- [6, 4, 4, 4, 4, 4, 9]

The module exposes:

- `BRANCH_SPECS`
- `BRANCH_ORDER`
- `BRANCH_SIZES`
- `BRANCH_LOGITS_KEYS`
- `TARGET_INDEX_TO_HEAD`
- `HEAD_NAME_TO_TARGET_INDEX`
- `validate_student_branch_contract_consistency()`
- `render_branch_contract_markdown()`
- `dump_branch_contract_json(path)`

## Deduplication performed

Branch metadata/order duplication was removed from:

- `python/week6_student/student_bc_metrics.py`
- `python/week6_student/student_architecture_transfer.py`
- `python/week6_student/partial_transfer_strategy.py`
- `python/week6_student/student_bc_model_minimal.py`
- `python/week6_student/train_student_bc_minimal.py` (metric key print order only)

These files now consume branch metadata from `student_branch_contract.py`.

## Consistency checks added

`validate_student_branch_contract_consistency()` fails fast on:

- duplicate branch names;
- non-contiguous target indices (must be 0..6);
- branch size mismatch against expected BC contract [6,4,4,4,4,4,9];
- duplicate logits keys;
- duplicate head names;
- mismatched target->head mapping;
- mismatched model logits key order when provided.

Validation is called from:

- `student_bc_metrics.py` (module import)
- `student_architecture_transfer.py` (model init)
- `partial_transfer_strategy.py` (mapping helper)
- `train_student_bc_minimal.py` (startup)

## Day 4 wiring preparation value

This reduces the carry-over risk identified on Day 3:

- branch index/order mismatch between Python model outputs and future Unity decoder wiring.

A single authoritative module now provides branch order, target indices, head names, and logits keys for both training and future wiring.

## Next step readiness

Project is now ready for the next safe step:

- add training entrypoint support for `StudentBCTransferModel` on pinned BC-ready source,
  while preserving Day 2 objective semantics and no-transfer-claim policy.

Implemented wiring prep in existing entrypoint:

- `python/week6_student/train_student_bc_minimal.py` now supports
    `--model-variant minimal|transfer` (default remains `minimal`).
- Branch-wise BC objective and Day 2 gating semantics are unchanged.
- Pinned BC-ready lineage usage is unchanged.
