# STAGE5C 1M Standard Gate Report

## Summary

Stage 5C was started on the corrected 24x24 GridMode path with standard gate configuration (`target_24x24_gridmode`, `both`, `require-mask=true`, `episodes=8`, `max_steps_per_episode=6000`).

Final state:

- Preflight: PASS
- 1M training: PASS
- checkpoint/model metadata for Stage 5C run: produced
- standard gate: PASS

Decision for next prompt: `PASS_WITH_WARNINGS`

Rationale: required Stage 5C artifacts were generated and gate checks passed, but gate warning indicates episode horizon did not effectively reach configured 6000 due an additional internal cap.

## Preflight Result

- command: `python/week5_teacher_legacy032/scripts/verify_legacy032_24x24_training_contract.py`
- output json: `python/week5_teacher_legacy032/reports/stage5c_24x24_contract_probe.json`
- status: `PASS`
- map_path: `maps/24x24/basesWorkers24x24.xml`
- observation_space: `[24,24,27]`
- action_space_nvec: `[576,6,4,4,4,4,7,49]`
- mask_available: `true`
- policy_forward_ok: `true`

## Training Result

Executed command:

- script: `python/week5_teacher_legacy032/scripts/run_24x24_staged_teacher_training_legacy032.py`
- flags: `--stages 1000000 --seed 17 --device cpu --map-path maps/24x24/basesWorkers24x24.xml --episodes-per-gate 8 --max-steps-per-gate 6000 --evaluate-after-each --no-wandb --require-contract-check true`

Run id:

- `legacy032_24x24_teacher_main_20260429T195603Z`

Final output:

- status: `PASS`
- decision (orchestrator): `READY_FOR_500K`
- training env cap: `--max-steps 6000`
- training report json: `python/week5_teacher_legacy032/reports/stage5_24x24_training_20260429T195603Z.json`
- training report md: `python/week5_teacher_legacy032/reports/stage5_24x24_training_20260429T195603Z.md`

From-scratch statement:

- `1M is a from-scratch staged checkpoint with larger total_timesteps, not a resumed continuation from 500k.`

## Checkpoint Path

Produced:

- `python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260429T195603Z/stage_001000000/agent_final.pt`

## Metadata Path

Produced:

- `python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260429T195603Z/stage_001000000/model_metadata.json`

## Metadata Contract

Verified:

- architecture_name: `legacy032_resolution_aware_gridnet_v1`
- observation_space: `[24,24,27]`
- action_space_nvec: `[576,6,4,4,4,4,7,49]`
- map_path: `maps/24x24/basesWorkers24x24.xml`
- training_max_steps: `6000`
- env_max_steps: `6000`
- max_steps: `6000`

## Standard Gate Result

Completed.

Target gate config (already requested by command):

- env-mode: `target_24x24_gridmode`
- eval-mode: `both`
- require-mask: `true`
- episodes: `8`
- Gate horizon: `6000`

Produced machine outputs:

- `python/week5_teacher_legacy032/reports/stage5_24x24_training_20260429T195603Z.json`
- `python/week5_teacher_legacy032/reports/stage5_24x24_training_20260429T195603Z.md`
- `python/week5_teacher_legacy032/reports/stage5_gate_001000000_20260429T232455Z.json`
- `python/week5_teacher_legacy032/reports/stage5_gate_001000000_20260429T232455Z.md`

## Key Metrics

- gate_decision: `PASS`
- mean_return (stochastic): `-10.0`
- effective_activity_share (stochastic): `0.8337035574022056`
- noop_share (stochastic): `0.1662964425977944`
- move_share (stochastic): `0.16624726903870163`
- attack_action_count (stochastic): `817054`
- produce_action_count (stochastic): `824618`
- policy_entropy_proxy (stochastic): `0.0005863994307689476`
- observed_max_episode_length: `712`
- training_duration_seconds: `12529.892364025116`
- training_metrics_summary:
  - episode_count: `367`
  - last_global_step: `999042`
  - mean_episode_reward: `137.72097961259473`

## Warnings / Errors

- warning: selected_action_mask_valid_share and masked_invalid_prevented_count are null because mask bit semantics are ambiguous in this legacy runtime.
- warning: observed max episode length is `<= 2000` while `max_steps_per_episode=6000`; evaluator notes an additional internal cap.
- errors: none

## Decision

`PASS_WITH_WARNINGS`

Reason: required Stage 5C training + gate execution completed successfully with correct 24x24 contract and configured horizon fields at 6000, but the gate warning about effective episode length cap must be tracked before any stronger readiness claim.
