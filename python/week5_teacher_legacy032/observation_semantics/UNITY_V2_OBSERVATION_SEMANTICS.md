# Unity v2 Observation Semantics (Canonical Target)

Status: canonical target for Stage10D.4 adapter remediation

## Canonical Target Layout

Per-cell channels (27 total):
- [0] hit_points (scalar, [0,1])
- [1] resources (scalar, [0,1])
- [2-4] owner (one-hot)
- [5-11] unit_type (one-hot)
- [12-17] current_action (one-hot)
- [18-21] direction (one-hot)
- [22-25] produce_unit_type (one-hot or all-zero when not applicable)
- [26] attack_target (scalar, [0,1], observation-side diagnostic signal)

## Canonical Owner Mode Decision

Chosen canonical target mode: perspective_friendly_enemy.

Reason:
- Student BC inference executes in Unity from player perspective.
- Runtime inference semantics should be stable and perspective-consistent for deployed policy behavior.

Owner one-hot interpretation for canonical target:
- owner[0] = neutral
- owner[1] = friendly (same as observing player)
- owner[2] = enemy

## Spec Reconciliation Note

Current codebase has a known documentation/runtime split:
- ObservationContract documentation currently describes owner as absolute [neutral, player1, player2].
- ObservationBuilder UnityMvpTransfer path uses perspective [neutral, friendly, enemy].

Stage10D.4 records this as spec reconciliation required; it does not change Unity runtime behavior.

## Non-Claims

- This document does not claim Gym raw parity.
- This document does not authorize retraining.
- This document does not mutate ActionApplier, MatchManager, or runtime inference logic.
