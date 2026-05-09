# Stage7B Candidate Action Contract

Stage7B uses a compact candidate action space over legal runtime-derived `AgentAction` choices.

The attack target contract is the current Stage6B3/v2-compatible local 7x7 contract:

- `attack_target_local` size: `49`
- local window: `7x7`
- center index: `24`
- source of truth: `RTS.ML.ActionContract.SIZE_ATTACK_TARGET` and `ActionContract.AttackOffsets`

## Candidate Slots

- `candidate[0]` is always `NoOp` and is never masked.
- `candidate[1..127]` are legal non-NoOp candidates built from the current Unity runtime state.
- Empty slots are masked in `WriteDiscreteActionMask`.
- If more than `127` legal non-NoOp candidates exist, overflow is recorded and candidates beyond the branch limit are not exposed.
- If a selected slot is out of range, empty, or stale, Stage7B falls back to `candidate[0]` `NoOp`.
- If `candidate[0]` is unexpectedly unavailable, Stage7B synthesizes a safe `NoOp` `AgentAction` and logs the anomaly.

## Source of Legality

`MlAgentsCandidateActionBuilder` builds candidates from the existing `ActionMaskBuilder` transfer-compatible mask. This avoids duplicating authoritative validation. Final validity still belongs to `ActionApplier` and `MatchManager`.

Attack candidates are built from `actorMask.AttackTargetLocalMask[0..48]` and resolved through `ActionContractMappings.TryGetAttackTargetPosition(...)`, so Stage7B does not maintain a parallel 3x3 target convention.

## Ordering

Candidates are sorted deterministically by:

1. `actor_flat_index` ascending
2. `action_type` ascending
3. `direction` ascending
4. `produce_unit_type` ascending
5. `attack_target_local` ascending

## Heuristic Dry Run

The Stage7B heuristic writes only a candidate index. It does not directly apply a command.

Preference order:

1. `Return` if a worker is carrying resources
2. `Harvest`
3. `Produce`
4. `Attack`
5. useful `Move`
6. `NoOp`

This heuristic is diagnostic only. It is not a teacher policy and is not the final student policy.

## Diagnostics

The heuristic dry-run artifact records:

- `candidate_branch_size = 128`
- `attack_target_size = 49`
- `attack_target_center_index = 24`
- `candidate_overflow_count`
- `invalid_candidate_index_selected_count`
- `empty_candidate_selected_count`
- `out_of_range_candidate_selected_count`
- `fallback_to_noop_count`
