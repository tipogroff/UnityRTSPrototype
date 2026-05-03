# LEGACY032 Raw Observation Semantics (Empirical)

Status: empirical reconstruction only (Stage10D.4)
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

Observed per-channel behavior indicates binary/one-hot-like structure, but semantic labels remain partially uncertain.

High-confidence empirical statements:
- Raw channel values are mostly binary (0/1).
- Several shifted windows exhibit stronger one-hot behavior than Unity-declared windows.
- Legacy raw semantics are not directly interchangeable with Unity v2 runtime semantics.

Low-confidence or uncertain statements:
- Exact owner channel placement in raw Legacy032 remains unresolved.
- Exact unit_type channel placement in raw Legacy032 remains unresolved.
- Raw current_action and direction channels may be shifted relative to Unity contract indices.

## Non-Claims

- No claim that Legacy032 raw channel index i equals Unity channel index i.
- No claim of exact parity between Gym-microRTS raw observation internals and Unity runtime ObservationBuilder semantics.
- No claim that unresolved channels can be safely remapped without explicit mapping specification and validation.

## Implication for Stage10D.4

Because inference-time deployment is in Unity, Unity runtime observation semantics must be the canonical target.
Legacy032 raw observations require explicit, versioned adaptation rules, not reshape-only passthrough.
