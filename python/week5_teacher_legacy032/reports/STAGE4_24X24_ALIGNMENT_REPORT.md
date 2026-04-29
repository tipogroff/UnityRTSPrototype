# STAGE4 24x24 Alignment Report

Date: 2026-04-29
Decision: BLOCKED_CONTRACT_MISMATCH

Correction note (Stage 4R):

Stage 4 original `BLOCKED_CONTRACT_MISMATCH` classification was superseded by Stage 4R correction.
For `MicroRTSGridModeVecEnv` on 24x24 map, action nvec `[576,6,4,4,4,4,7,49]` is correct.
Global single-action `[576,6,4,4,4,4,7,576]` remains valid only for gym.make/preflight style mode, not GridMode teacher training.
The true blocker was policy architecture spatial shape mismatch.
Stage 4R resolved both documentation contract confusion and the architecture shape issue.

## Summary

Stage 4 alignment work was executed in legacy032 workspace only.
Reference source files remained unchanged.

Audit and probe results show that legacy032 GridMode on 24x24 map does not provide the requested action contract `[576,6,4,4,4,4,7,576]`.
Observed contract is `[576,6,4,4,4,4,7,49]`.

Additionally, policy forward with reference encoder/decoder topology fails on 24x24 due tensor shape mismatch during masked sampling.

## Audit Result

Audit report: `python/week5_teacher_legacy032/reports/STAGE4_24X24_ALIGNMENT_AUDIT.md`

Key findings:

- Reference training script has hardcoded 16x16 assumptions (map path, mapsize=256, fixed view=256, decoder channels=78).
- `--map-path` parameterization alone is unsafe.
- Separate patched script in legacy032 workspace is required.
- Architecture is resolution-sensitive and requires explicit shape compatibility checks.

## Patched 24x24 Script

Created:

- `python/week5_teacher_legacy032/scripts/ppo_gridnet_legacy032_24x24_local_save.py`

Implemented:

- `--map-path` (default `maps/24x24/basesWorkers24x24.xml`)
- `--max-steps` (default `2000`)
- `--expected-map-size` (default `24`)
- `--verify-contract` (default `true`)
- env creation via `MicroRTSGridModeVecEnv(..., map_path=args.map_path, max_steps=args.max_steps)`
- metadata includes env/map/obs/action/nvec/mapsize/num_envs/mask source/script name
- fail-fast contract failure report when mismatch is detected

## Contract Probe Result

Probe artifact:

- `python/week5_teacher_legacy032/reports/stage4_24x24_contract_probe.json`

Status: `BLOCKED_CONTRACT_MISMATCH`

Observed:

- observation_space: `[24,24,27]`
- action_space.nvec: `[576,6,4,4,4,4,7,49]`
- mask source: `env.vec_client.getMasks(0)` (available)
- mask shape: `[6,24,24,79]`
- policy_forward_ok: `false`
- masked_action_sample_ok: `false`
- env_step_ok: `false`

Primary blockers:

- Contract mismatch vs requested target attack branch (`49` observed vs `576` requested).
	Superseded interpretation: not a real GridMode mismatch.
- Policy masked sampling shape mismatch on 24x24.

## Smoke Training Result

Not executed.

Reason:

- Stage rule requires probe PASS before 10k smoke training.
- Probe returned `BLOCKED_CONTRACT_MISMATCH`.

## Behavior Gate Result

Not executed for Stage 4 smoke checkpoint.

Reason:

- No 24x24 smoke checkpoint was produced due probe block.

Validation of evaluator guard logic was executed on existing 16x16 checkpoint:

- `python/week5_teacher_legacy032/reports/stage4_target24_failfast_check_20260429T130423Z.json`
- Result: fail-fast in `target_24x24_gridmode` works as expected.

## Confirmed Env/Action Contract

For `MicroRTSGridModeVecEnv` with map `maps/24x24/basesWorkers24x24.xml`:

- observation: `[24,24,27]` confirmed
- action nvec: `[576,6,4,4,4,4,7,49]` confirmed

Requested Stage 4 target contract `[576,6,4,4,4,4,7,576]` is not met in this env mode.

## Mask Path Status

- mask retrieval path via `env.vec_client.getMasks(0)` is available in probe.
- evaluator and patched scripts preserve masked action path semantics.

## Architecture Compatibility

Current reference encoder/decoder topology is not shape-safe for 24x24 under this path.
Masked sampling encountered tensor size mismatch for logits vs mask flattening.

Minimal fix direction:

- redesign actor head to be resolution-aware and guarantee output HxW equals env map HxW;
- then re-run Stage 4 probe before any 10k/100k training.

## Warnings / Errors

- Stage 3 checkpoints are still reference-internal artifacts only.
- No direct transfer readiness claims can be made from Stage 3 or blocked Stage 4 outputs.

## Final Stage 4 Decision

`BLOCKED_CONTRACT_MISMATCH`
