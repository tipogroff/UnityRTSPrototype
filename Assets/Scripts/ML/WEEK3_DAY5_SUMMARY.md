# Week 3 Day 5: Heuristic Policy via Observation/Action/Mask Pipeline

## Status
Implemented.

## Goal
Day 5 introduced a heuristic adapter that runs matches without ML while still using the same agent pipeline intended for future ML-Agent integration.

The Day 5 heuristic is explicitly a debug/baseline integration tool:
- It validates observation/action/mask wiring end-to-end.
- It is **not** a reference-compatible semantics oracle.
- It is **not** a proof of transfer mapping correctness.

## What Was Added

### 1. Heuristic policy adapter over Day 2-4 artifacts
New file:
- `Assets/Scripts/ML/HeuristicPolicyAdapter.cs`

Key responsibilities:
- Build observation for `playerId` through `ObservationBuilder`.
- Build debug-compatible masks through `ActionMaskBuilder`.
- Select a debug action in `v1_debug_action_space` branches:
  - `actor_index_flat`
  - `action_type`
  - `direction`
  - `produce_unit_type`
  - `attack_target_local`
- Decode through `ActionDecoder.DecodeDebug(...)`.
- Apply through `ActionApplier.ApplyAction(...)` (authoritative validation preserved).

Important constraint satisfied:
- Heuristic policy does **not** call gameplay command application directly.
- No shortcut pipeline was introduced.

### 2. Episode integration for no-ML runs
Updated file:
- `Assets/Scripts/Gameplay/Match/EpisodeController.cs`

Added:
- `HeuristicExecutionPath` selector:
  - `LegacyDirectDriver`
  - `Day5PolicyPipeline` (default)
- Optional scene reference to `HeuristicPolicyAdapter`.
- Day 5 path now executes heuristic decisions via adapter pipeline before `StepMatch()`.

This enables running episodes without ML policy while preserving Day 3-4 downstream path.

### 3. Day 5 smoke/integration tests
New file:
- `Assets/Scripts/ML/HeuristicPolicyAdapterSmokeTest.cs`

Covers:
- worker harvest through new interface
- worker return through new interface
- building produce through new interface
- combat actor attack or move through new interface
- NoActor/NoOp safe fallback when no valid actor context
- short multi-step heuristic-vs-heuristic loop without ML policy

Each decision test validates that selection is done via debug branches and then passed through decoder/applier pipeline.

### 4. Editor menu hooks for Day 5
Updated file:
- `Assets/Scripts/Gameplay/Match/Editor/SmokeTestMenuRunner.cs`

Added menu actions:
- `SmokeTest/7 - Day5 Heuristic Pipeline Smoke Test`
- `SmokeTest/8 - Day5 Mode Heuristic vs Heuristic`
- `SmokeTest/9 - Day5 Mode Heuristic vs Idle`

## Heuristic decision policy (baseline)

Worker:
- if carrying cargo and return is masked -> `Return`
- else if carrying cargo and move masked -> move toward nearest base
- else if harvest masked with adjacent resource -> `Harvest`
- else if move masked -> move toward nearest resource
- else fallback `NoOp`

Building:
- if produce masked -> `Produce`
- prefer `Worker` produce type for stable deterministic baseline

Combat:
- if attack masked -> choose masked local attack target (prefer enemy occupant)
- else if move masked -> move toward nearest enemy
- else fallback `NoOp`

All selections are mask-gated and deterministic by flat-index scan order.

## Pipeline equivalence with future ML-Agent

Day 5 heuristic now executes through:
1. `ObservationBuilder`
2. `ActionMaskBuilder` (debug-adapted mask)
3. debug action branch selection
4. `ActionDecoder.DecodeDebug(...)`
5. `ActionApplier.ApplyAction(...)`
6. `MatchManager.ApplyCommand(...)`

This matches the intended downstream ML-Agent integration path.

## Diagnostic output

`HeuristicPolicyAdapter` outputs decision traces including:
- selected actor index
- selected action type and branch params
- selection reason
- decoded action summary
- accepted/rejected status and rejection reason from authoritative applier

This is designed for Play Mode pipeline debugging.

## Limits and non-goals

- Day 5 heuristic is intentionally simple and deterministic.
- It is not optimized strategy quality.
- It does not replace authoritative runtime validation.
- It does not redefine transfer/reference semantics.
