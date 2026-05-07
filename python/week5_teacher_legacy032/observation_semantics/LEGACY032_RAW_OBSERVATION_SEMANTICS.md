# LEGACY032 Raw Observation Semantics (Empirical)

Status: source-confirmed production mapping (Stage6B3 semantic observation fix)
Source dataset: python/week5_teacher_legacy032/teacher_rollouts/legacy032_3m_unity_v2_rollout_export_20260501T125015Z/teacher_rollout_raw.npz
Input tensor shape: [N, 24, 24, 27]

## Scope

This document records what can be inferred from raw Gym-microRTS Legacy032 rollout observations.
It does not claim exact source-level parity with any specific gym-microRTS internal encoder implementation.

## Evidence Base

Primary evidence:
- Stage10D.3 raw probe: python/week6_student/reports/stage10d3_raw_gym_observation_channel_probe.json
- Stage10D.3 adapter trace: python/week6_student/reports/stage10d3_adapter_observation_transform_trace.json
- Stage10D.4 inference output: python/week6_student/reports/stage10d4_inferred_legacy032_raw_channel_semantics.json

Key Stage10D.3 findings preserved:
- Raw tensor is numerically valid (float32, no NaN/Inf).
- Declared Unity-style windows [2..4], [5..11], [12..17], [18..21] do not consistently behave as intended Unity semantic groups.
- Existing reshape-only adapter path performs no observation semantic channel remap.

## Empirical Channel Notes

Source-confirmed raw channel groups from `gym_microrts/envs/vec_env.py`:

| Raw channels | Raw meaning |
|---:|---|
| 0..4 | hit point discrete one-hot bin, clipped at 4 |
| 5..9 | resource/carry discrete one-hot bin, clipped at 4 |
| 10..12 | owner one-hot: neutral, player0, player1 |
| 13..20 | unit type one-hot: empty, Resource, Base, Barracks, Worker, Light, Heavy, Ranged |
| 21..26 | current action one-hot: NoOp, Move, Harvest, Return, Produce, Attack |

Important absence:
- Legacy032 raw observation has no facing/direction planes.
- Legacy032 raw observation has no active produce-unit-type planes.
- Legacy032 raw observation has no observation-side attack-target plane.

## Non-Claims

- No claim that Legacy032 raw channel index i equals Unity channel index i.
- No claim of exact parity between Gym-microRTS raw observation internals and Unity runtime ObservationBuilder semantics.
- No claim that unresolved channels can be safely remapped without explicit mapping specification and validation.

## Implication for Stage10D.4

Because inference-time deployment is in Unity, Unity runtime observation semantics are the canonical target.
Legacy032 raw observations require explicit, versioned semantic adaptation rules, not reshape-only passthrough.
