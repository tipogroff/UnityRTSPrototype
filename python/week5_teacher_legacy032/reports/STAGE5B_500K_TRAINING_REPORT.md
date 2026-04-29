# STAGE5B 500K Training Report

- Date: 2026-04-30
- Stage: 5B (24x24 staged teacher training, checkpoint 500k)
- status: PASS_WITH_WARNINGS
- decision: READY_FOR_1M_WITH_WARNINGS

## Summary

- Stage 5B executed on corrected 24x24 GridMode pipeline only.
- Preflight contract probe passed.
- 500k training completed and saved checkpoint + metadata.
- Post-training behavior gate in target_24x24_gridmode passed technically.
- Comparison with Stage 5A 100k baseline shows technical stability but no clear behavior improvement.

## Commands Run

- Preflight:
  - c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week5_teacher_legacy032/scripts/verify_legacy032_24x24_training_contract.py --map-path maps/24x24/basesWorkers24x24.xml --num-bot-envs 6 --num-selfplay-envs 0 --seed 17 --output-json python/week5_teacher_legacy032/reports/stage5b_24x24_contract_probe.json
- Training + gate orchestration:
  - c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week5_teacher_legacy032/scripts/run_24x24_staged_teacher_training_legacy032.py --run-label legacy032_24x24_teacher_main --stages 500000 --seed 17 --device cpu --map-path maps/24x24/basesWorkers24x24.xml --episodes-per-gate 8 --evaluate-after-each --no-wandb --require-contract-check true

## Preflight Contract Probe Result

- report: python/week5_teacher_legacy032/reports/stage5b_24x24_contract_probe.json
- status: PASS
- observation_space: [24,24,27]
- action_space_nvec: [576,6,4,4,4,4,7,49]
- mask_available: true
- policy_forward_ok: true
- masked_action_sample_ok: true
- env_step_ok: true

## Training Result

- run_id: legacy032_24x24_teacher_main_20260429T171506Z
- machine_report_json: python/week5_teacher_legacy032/reports/stage5_24x24_training_20260429T171506Z.json
- machine_report_md: python/week5_teacher_legacy032/reports/stage5_24x24_training_20260429T171506Z.md
- training_exit_code: 0
- checkpoint_path: python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260429T171506Z/stage_000500000/agent_final.pt
- model_metadata_path: python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260429T171506Z/stage_000500000/model_metadata.json
- from-scratch note: 500k is a from-scratch staged checkpoint with larger total_timesteps, not a resumed continuation from 100k.

## Metadata Contract

- architecture_name: legacy032_resolution_aware_gridnet_v1
- observation_space: [24,24,27]
- action_space_nvec: [576,6,4,4,4,4,7,49]
- metadata_contract_ok: true

## Behavior Gate Result

- gate_json_report: python/week5_teacher_legacy032/reports/stage5_gate_000500000_20260429T190313Z.json
- gate_md_report: python/week5_teacher_legacy032/reports/stage5_gate_000500000_20260429T190313Z.md
- gate_decision: PASS
- checkpoint_load_ok: true
- policy_architecture_load_ok: true
- inference_ok: true
- env_matches_target_24x24: true
- mask_used_during_eval: true
- action_type_distribution recorded: true

## 500K Metrics

| metric | value |
|---|---:|
| stochastic mean_return | -7.5 |
| deterministic mean_return | -10.0 |
| stochastic noop_share | 0.16643518518518519 |
| deterministic noop_share | 0.9965651659384103 |
| stochastic effective_activity_share | 0.8335648148148148 |
| stochastic move_share | 0.16620255775577558 |
| stochastic attack_action_count | 579623 |
| stochastic produce_action_count | 584767 |
| stochastic policy_entropy_proxy | 0.0007871014947223818 |
| stochastic repeated_same_action_share | 0.19108094936576106 |

## Comparison Against 100K Baseline

- baseline run_id: legacy032_24x24_teacher_main_20260429T162331Z
- baseline checkpoint: python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260429T162331Z/stage_000100000/agent_final.pt
- baseline gate: python/week5_teacher_legacy032/reports/stage5_gate_000100000_20260429T164521Z.json
- detailed comparison report: python/week5_teacher_legacy032/reports/STAGE5_100K_VS_500K_COMPARISON.md

Key comparison outcome:

- technical checks remained green;
- returns stayed flat (stochastic: -7.5 -> -7.5, deterministic: -10.0 -> -10.0);
- deterministic noop_share remained extremely high;
- stochastic activity remained high and nonzero.

## Warnings / Errors

- warning: behavior quality remains weak for deterministic policy (noop-heavy).
- warning: no obvious return improvement versus 100k baseline.
- error: none.

## Decision

- Stage 5B classification: PASS_WITH_WARNINGS
- decision value: READY_FOR_1M_WITH_WARNINGS

## Recommendation

- Continue to Stage 5C (1M) only with warnings and explicit diagnostic monitoring.
- If deterministic noop collapse worsens at 1M, hold and run targeted diagnostics instead of pushing to 3M/5M.
