# Week 3 Day 1 - Observation/Action Contract Spec (Draft)

Date: 2026-03-23  
Status: ✅ Approved and implemented (Finalized 2026-03-29)  
Scope: MVP_24x24_Symmetric, transfer-compatible with Gym-microRTS v0.6.1 reference semantics

## See Also

For complete Week 3 context including action masking, heuristic policy, compatibility gaps, and Week 4 readiness:
→ **[WEEK3_OBSERVATION_AND_ACTION_SUMMARY.md](WEEK3_OBSERVATION_AND_ACTION_SUMMARY.md)**

---

## 1) Goal

Fix a two-layer data contract before implementation:
- observation format;
- spatial channel order;
- global features composition;
- action branches;
- invalid action rules;
- Unity <-> Gym-microRTS mapping for observation/action semantics.

No code changes are allowed until this document is approved.

## 2) Two-Layer Contract Model

This spec defines two explicit layers:

- LegacyGymCompatibleSpec: reference-compatible layer used as Gym baseline.
- UnityMvpTransferSpec: practical Unity MVP layer used for transfer, debugging, and fine-tuning.

Operational rule:
- Any adaptation in UnityMvpTransferSpec must be explicitly documented relative to LegacyGymCompatibleSpec.

## 3) Observation Contract

### 3.1 LegacyGymCompatibleSpec (reference-compatible)

Spatial observation:

- Tensor shape: [H, W, C] = [24, 24, 27]
- Data type: float32
- Value range: [0, 1]
- Flatten order for ML-Agents vector: row-major by cell, then channel
  - flat_index = (row * W + col) * C + ch
- Source of truth in Unity: Assets/Scripts/ML/ObservationContract.cs

Spatial channel order (C=27):

- 0: hit_points (normalized)
- 1: resources (normalized)
- 2: owner_neutral (one-hot)
- 3: owner_player1 (one-hot)
- 4: owner_player2 (one-hot)
- 5: unit_resource (one-hot)
- 6: unit_base (one-hot)
- 7: unit_barracks (one-hot)
- 8: unit_worker (one-hot)
- 9: unit_light (one-hot)
- 10: unit_heavy (one-hot)
- 11: unit_ranged (one-hot)
- 12: action_noop (one-hot)
- 13: action_move (one-hot)
- 14: action_harvest (one-hot)
- 15: action_return (one-hot)
- 16: action_produce (one-hot)
- 17: action_attack (one-hot)
- 18: dir_north (one-hot)
- 19: dir_east (one-hot)
- 20: dir_south (one-hot)
- 21: dir_west (one-hot)
- 22: produce_worker (one-hot)
- 23: produce_light (one-hot)
- 24: produce_heavy (one-hot)
- 25: produce_ranged (one-hot)
- 26: attack_target_index (normalized scalar)

Reference-compatibility note:
- Channel order is aligned with Gym-microRTS v0.6.1 reference layout for the 27-channel setup used in this project baseline.
- This is semantic alignment for transfer experiments, not a guarantee of strict byte-identical environment parity.

### 3.2 UnityMvpTransferSpec (Unity adaptation)

Unity adaptation keeps the same 27-channel spatial tensor and adds a separate global vector for transfer/debug support.

Global vector is separated from spatial tensor and passed as an additional observation block.

- Shape: [10]
- Data type: float32
- Value range: [0, 1]

Indices:
- g0: step_norm = step / max_steps
- g1: remaining_norm = 1 - step_norm
- g2: own_resource_share = own_res / (own_res + enemy_res + 1)
- g3: enemy_resource_share = enemy_res / (own_res + enemy_res + 1)
- g4: own_unit_share = own_units / (own_units + enemy_units + 1)
- g5: enemy_unit_share = enemy_units / (own_units + enemy_units + 1)
- g6: own_base_alive = 1 if own_bases > 0 else 0
- g7: enemy_base_alive = 1 if enemy_bases > 0 else 0
- g8: invalid_rate_last_step = invalid / (accepted + invalid + 1)
- g9: pending_commands_norm = pending_commands / (H * W)

Notes:
- own/enemy are always relative to requested playerId.
- If max_steps <= 0, use step_norm = 0 and remaining_norm = 1.
- Global vector is Unity-only adaptation and is not part of LegacyGymCompatibleSpec.

## 4) Action Contract

Two spaces are fixed on Day 1:

### 4.1 v1_transfer_compatible_action_space (primary)

Per-cell multi-discrete action (one action vector for each grid cell).

- Number of cells per step: H * W = 576
- Branches per cell: 7
- Branch sizes: [6, 4, 4, 4, 4, 4, 9]

Branch semantics:
- b0 action_type: 0=NoOp, 1=Move, 2=Harvest, 3=Return, 4=Produce, 5=Attack
- b1 move_dir: 0=N, 1=E, 2=S, 3=W
- b2 harvest_dir: 0=N, 1=E, 2=S, 3=W
- b3 return_dir: 0=N, 1=E, 2=S, 3=W
- b4 produce_dir: 0=N, 1=E, 2=S, 3=W
- b5 produce_unit_type: 0=Worker, 1=Light, 2=Heavy, 3=Ranged
- b6 attack_target_local: 0..8 in 3x3 neighborhood (4=center)

Unity runtime mapping target:
- policy output -> AgentAction -> ActionDecoder -> ActionApplier -> MatchManager.ApplyCommand().

Compatibility note:
- This is transfer-compatible and Gym-inspired, but intentionally adapted for MVP.
- Most important adaptation: local 3x3 attack target parameterization.

### 4.2 v1_debug_action_space (secondary)

Single-actor action for smoke/debug sessions.

Branches:
- b0 actor_index_flat: 0..(H*W), where last value means NoActor
- b1 action_type: 0..5
- b2 direction: 0..3
- b3 produce_unit_type: 0..3
- b4 attack_target_local: 0..8

Rule:
- Debug action is converted to the same AgentAction intermediate model, then uses exactly the same downstream pipeline.

## 5) Invalid Action Rules

Invalid rules are split into two layers:

1) mask layer (prevent invalid options before sampling)
2) server validation layer (authoritative fallback in ActionApplier/MatchManager)

### 5.1 Reference-compatible invalid semantics

Reference-compatible intent:
- actor must exist and belong to the acting player;
- action type must be valid for actor state and context;
- required target/direction/parameter must be valid for selected action.

### 5.2 Unity-authoritative invalid rules (runtime)

Action is invalid in Unity runtime if at least one condition is true:

- actor does not exist at selected cell;
- actor is dead;
- actor belongs to enemy player;
- actor already has command this step;
- action type is not supported by actor type;
- Move target is outside map or occupied;
- Harvest target has no active resource node;
- Harvest attempted by non-worker or worker without free carry capacity;
- Return attempted with zero carried resources;
- Return target is not own Base in selected direction;
- Produce attempted by non-building;
- Produce requested while production queue is busy;
- Produce requested without enough resources;
- Attack target is out of allowed target set;
- command is submitted when match phase is not Running.

Operational rule:
- Even with masks enabled, server validation stays mandatory.
- Unity mask construction must follow Unity-authoritative validation.
- Each mask rule should be tagged as either reference-compatible or Unity-only.

## 6) Unity <-> Gym-microRTS Mapping

### 6.1 Observation semantics

- Spatial tensor layout is mapped to Gym-microRTS v0.6.1 reference semantics for the 27-channel baseline.
- Unity owner encoding [neutral, player1, player2] is aligned with Gym conventions.
- UnitType, UnitActionType, Direction, ProducibleUnit enum integer order is contract-critical and must not change silently.
- Unity global vector is an explicit Unity adaptation layer and must be excluded from strict legacy-compatible comparisons.

### 6.2 Action semantics

- Action type and direction values are index-compatible (NoOp/Move/Harvest/Return/Produce/Attack and N/E/S/W).
- Produce unit type values are index-compatible (Worker/Light/Heavy/Ranged).
- Attack target is a known compatibility reduction in MVP:
  - Unity v1 uses local 3x3 target index (9 values).
  - Full Gym variants may use a larger target parameterization.
  - Adapter requirement: Gym dataset/actions must be transformed to local-target representation for this MVP contract.

### 6.3 Coordinate conventions

- Unity cell coordinate: (row, col) with row downward and col to the right.
- Flattened cell index: row * W + col.
- Any Gym-side transform must use the same row-major cell order.

## 7) Compatibility Gap List

The authoritative compatibility gap list is maintained in a separate document: [WEEK3_COMPATIBILITY_GAP_LIST.md](WEEK3_COMPATIBILITY_GAP_LIST.md).

This document is mandatory and must be:
- Reviewed and accepted during Day 1 approval.
- Updated throughout Week 3 as new adaptation details emerge.
- Finalized by end of Day 7.

Key gaps (see full list in linked document):
- Separate Unity global vector is added (10 features) for runtime telemetry and transfer diagnostics.
- Attack target branch is limited to local 3x3 indexing (9 values) in MVP transfer contract.
- Action semantics are transfer-compatible, not guaranteed to be fully head-identical to all Gym action heads.
- Unity runtime invalid rules include engine/state constraints not represented as-is in reference Gym abstractions.

## 8) Approval Checklist (Day 1 Exit Criteria)

The contract is approved only when all items are confirmed:

- LegacyGymCompatibleSpec is fixed and reviewed;
- UnityMvpTransferSpec is fixed and reviewed;
- compatibility gaps are explicitly documented and accepted;
- observation spatial shape and channel order accepted;
- global features list and normalization accepted;
- primary and debug action branches accepted;
- invalid action rule set accepted;
- Unity <-> Gym mapping constraints accepted.

Blocker policy:
- Do not implement ObservationBuilder/ActionDecoder/ActionMaskBuilder until this file is approved.
