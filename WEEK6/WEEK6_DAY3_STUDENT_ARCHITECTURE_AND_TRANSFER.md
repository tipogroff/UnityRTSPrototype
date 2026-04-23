# Week 6 Day 3 - Student Architecture and Partial Transfer Strategy

Date: 2026-04-22

## Scope and honesty

This Day 3 artifact defines architecture and transfer strategy only.

- No full direct transfer claim is made.
- No incompatible head transfer is claimed.
- No Unity runtime export implementation is included here.
- BC target mapping alignment is not equal to proven weight-transfer compatibility.

## 1) Brief architectural assessment

Day 2 baseline (`StudentBCModelMinimal`) is intentionally small and valid for proof-of-learning,
but it is too minimal as a transfer-aware architecture decision point.

For Day 3, the student architecture is made explicit as:

- `spatial_stem`: early local spatial extraction from primary input `[24,24,27]`
- `encoder_backbone`: shared spatial encoder for reusable policy features
- `shared_spatial_features`: final shared feature tensor consumed by all heads
- branch heads aligned to BC-ready branches:
  - `action_type_head`
  - `move_dir_head`
  - `harvest_dir_head`
  - `return_dir_head`
  - `produce_dir_head`
  - `produce_unit_type_head`
  - `attack_target_local_head`

Optional global features are allowed only as auxiliary diagnostics/ablation path and are not required by core policy contract.

Implemented in code:

- `python/week6_student/student_architecture_transfer.py`
- class: `StudentBCTransferModel`
- config: `StudentArchitectureTransferConfig`

## 2) Transfer-aware decomposition (what is transfer-candidate vs student-specific)

- Encoder/backbone-level candidates:
  - `spatial_stem` (partial candidate only)
  - `encoder_backbone` (primary candidate)
  - `shared_spatial_features` (inherits encoder compatibility constraints)

- Unity/student-specific contract heads:
  - all seven branch heads are student policy output interfaces aligned to current BC-ready supervision contract
  - structural head alignment does not automatically grant canonical direct transfer init

- Non-policy/no-transfer zones:
  - PPO value/critic equivalents
  - mask logic
  - optimizer/trainer state

## 3) Explicit partial transfer table

Source of truth in code:

- `python/week6_student/partial_transfer_strategy.py`
- `build_day3_transfer_rules()`

| module | transfer_mode | rationale |
|---|---|---|
| input_stem | partial_transfer_candidate | Only if early teacher conv filters can be tensor-aligned and channel semantics are compatible; otherwise initialize student stem from scratch. |
| spatial_backbone_encoder | direct_transfer_candidate | Primary transfer candidate when tensor shapes and feature semantics align without silent reshaping hacks. |
| action_type_head | partial_transfer_candidate | Possible only if class meaning and ordering exactly match and output dimensionality is compatible. |
| move_dir_head | partial_transfer_candidate | Candidate only when directional class ordering and gating semantics match exactly. |
| harvest_dir_head | partial_transfer_candidate | Candidate only when directional class ordering and branch intent are verified equivalent. |
| return_dir_head | partial_transfer_candidate | Candidate only when directional class ordering and branch intent are verified equivalent. |
| produce_dir_head | partial_transfer_candidate | Candidate only when produce-direction semantics and class order are proven aligned. |
| produce_unit_type_head | partial_transfer_candidate | Likely subset-only transfer because teacher may encode broader producible class space; clean subset mapping is required. |
| attack_target_local_head | no_direct_transfer | Treat as non-canonical for direct init unless target parameterization is proven equivalent. At most experimental_partial_only under explicit experiments. |
| value_or_critic_head | no_direct_transfer | PPO/value-specific tensors are not canonical student BC policy initialization targets. |
| mask_related_logic | no_direct_transfer | Mask logic is execution/training logic, not policy-weight transfer target. |
| global_feature_path | no_direct_transfer | Global feature path is optional auxiliary/diagnostic only in Day 3 and must not be mandatory. |
| optimizer_or_trainer_state | no_direct_transfer | Optimizer/trainer state is not valid student policy initialization. |

## 4) Honest transfer policy rules

Transfer is allowed only under explicit compatibility evidence.

1. Encoder/backbone transfer may be considered only if:
- teacher tensors align with student tensor shapes without silent reshape hacks;
- input channel semantics are compatible enough to preserve meaning;
- no hidden mismatch is ignored.

2. Direction heads (`move/harvest/return/produce_dir`) may be considered only if:
- branch semantics are equivalent;
- class ordering is equivalent;
- gating semantics are equivalent.

3. `produce_unit_type_head` is subset-sensitive:
- if teacher class space is broader, only cleanly mapped subset may be considered;
- canonical full-head direct transfer is not assumed.

4. `attack_target_local_head` has strict caution:
- if target parameterization differs materially, direct transfer is disallowed;
- only explicit experiments may attempt partial init;
- default Day 3 classification stays `no_direct_transfer`.

5. PPO/value/critic/trainer internals are excluded from canonical student policy transfer.

6. Mask logic is not a weight-transfer target.

7. Optimizer state is not transferable student initialization.

## 5) Week 5 BC target -> student head mapping (explicit)

Current BC-ready target tensor per sample is `[576,7]`, branch sizes `[6,4,4,4,4,4,9]`.

1:1 supervision mapping:

- `target_action_branches[...,0] -> action_type_head`
- `target_action_branches[...,1] -> move_dir_head`
- `target_action_branches[...,2] -> harvest_dir_head`
- `target_action_branches[...,3] -> return_dir_head`
- `target_action_branches[...,4] -> produce_dir_head`
- `target_action_branches[...,5] -> produce_unit_type_head`
- `target_action_branches[...,6] -> attack_target_local_head`

Additional explicit note:

- actor selection is not a separate Day 3 supervised head in current BC-ready contract.
- current Day 3 student architecture is per-cell branch prediction aligned to BC-ready packaging.

Structured mapping source in code:

- `python/week6_student/partial_transfer_strategy.py`
- `get_week5_bc_to_student_head_mapping()`

## 6) Unresolved constraints / no-transfer zones

Still unresolved by Day 3 (intentionally):

- proven tensor-level checkpoint compatibility for direct import from current teacher checkpoints;
- proven class-order equivalence for all directional and action branches;
- proven target-parameterization equivalence for attack-target head;
- runtime semantic equivalence in Unity execution path;
- PPO/value/critic migration assumptions;
- optimizer-state carry-over assumptions.

No-transfer zones for canonical initialization:

- attack-target head by default
- value/critic heads
- mask logic
- optimizer/trainer state
- optional global-feature path

## 7) Carry-over risks for Day 4

Day 4 focuses on Unity-side inference path wiring, so the following risks carry over:

- branch index/order mismatch risk between model outputs and Unity decoder;
- shape-contract mismatch risk (`[B,576,branch]` expectations);
- attack-target semantics drift risk during decode/apply;
- overclaim risk: BC mapping compatibility can be mistaken for verified transfer correctness;
- optional auxiliary global path misuse risk (must remain optional and non-blocking).

Day 3 is considered successful when:

- architecture is clearly defined in contract terms;
- transfer candidates are explicitly and honestly classified;
- no-transfer zones are explicit;
- no false full-transfer claim is made.

## 8) Proof-run wording correction (2026-04-23)

This section clarifies interpretation wording for the supervised BC proof run with
`StudentBCTransferModel` on the pinned BC-ready lineage.

### 8.1 Optional mask interpretation

- Optional mask is absent in the pinned BC-ready lineage.
- Training remains intentionally mask-agnostic.
- Missing mask does not imply runtime all-valid truth.
- Optional mask is not a student input in this proof run.

### 8.2 Shape interpretation wording

To avoid ambiguity, keep these two shape categories separate:

- **Output logits layout (forward outputs):**
  - `action_type_logits`: `[B, 576, 6]`
  - direction/produce logits: `[B, 576, 4]`
  - `attack_target_local_logits`: `[B, 576, 9]`

- **Head parameter tensor shapes (state_dict / Conv2d 1x1 weights):**
  - `branch_heads.action_type_head.weight`: `[6, 96, 1, 1]`
  - direction/produce head weights: `[4, 96, 1, 1]`
  - `branch_heads.attack_target_local_head.weight`: `[9, 96, 1, 1]`

Therefore, values such as `576`, `384`, and `864` are parameter counts for selected
head tensors, not tensor shapes themselves.

### 8.3 Scope honesty retained

- No Day 2 objective semantics were changed.
- No branch-contract order/sizes were changed.
- No pinned lineage source was changed.
- No runtime transfer-success claim is made from this supervised BC result.
