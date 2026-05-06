# STAGE5P0 Existing Transfer Pipeline Audit

Date: 2026-05-06
Author: GitHub Copilot

## Classification
STAGE5P0_TRANSFER_PIPELINE_NEEDS_SMALL_FIXES

## Scope
Audit of existing Week 5 Legacy032 transfer pipeline before Stage5P rollout export.

## Summary
- Canonical training-compatible action path exists and is usable for final export stepping.
- Legacy032 policy/action helpers already expose deterministic and stochastic mask-aware selection paths.
- Adapter, validator, and packager are already Unity v2-safe for branch sizes [6,4,4,4,4,7,49].
- Blocking issue found by audit: exporter raw output schema mismatch with adapter expected schema.

## Required fix direction
- Exporter must write teacher_rollout_raw.npz and teacher_rollout_manifest.json.
- NPZ keys must be observation_t/per_cell_action_t episodic schema, not obs/action shorthand.
- Final export evidence path must remain training-compatible stepping; raw step path may remain diagnostic only.
- Stochastic export mode should be default for Stage5P main dataset source.

## Safety statements
- This audit does not claim direct Gym-to-Unity semantic parity.
- This audit does not claim direct model weight transfer.
- Masking is pre-sampling/diagnostic; Unity runtime validation remains authoritative.
