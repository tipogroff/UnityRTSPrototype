# Stage7B Candidate Action Contract

Stage7B uses a compact candidate action space over legal runtime-derived `AgentAction` choices.

## Candidate Slots

- `candidate[0]` is always `NoOp` and is never masked.
- `candidate[1..127]` are legal non-NoOp candidates built from the current Unity runtime state.
- Empty slots are masked in `WriteDiscreteActionMask`.
- If more than `127` legal non-NoOp candidates exist, overflow is recorded and candidates beyond the branch limit are not exposed.

## Source of Legality

`MlAgentsCandidateActionBuilder` builds candidates from the existing `ActionMaskBuilder` transfer-compatible mask. This avoids duplicating authoritative validation. Final validity still belongs to `ActionApplier` and `MatchManager`.

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
