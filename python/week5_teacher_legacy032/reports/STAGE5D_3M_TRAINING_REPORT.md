# STAGE5D 3M Training Report

## Summary

- Stage 5D 3M training status: PASS_WITH_WARNINGS
- run_id: `legacy032_24x24_teacher_main_20260430T130208Z`
- checkpoint path: `python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/agent_final.pt`
- metadata path: `python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/model_metadata.json`
- gate path: `python/week5_teacher_legacy032/reports/stage5_gate_003000000_20260430T225547Z.json`
- decision: READY_FOR_3M_DIAGNOSTICS

Stale-label note:

- The orchestrator machine report still emits `decision=READY_FOR_500K` as a generic legacy label.
- Stage 5D final decision in this report is based on the full Stage 5 policy and is set to `READY_FOR_3M_DIAGNOSTICS`.

## Preflight

- preflight report path: `python/week5_teacher_legacy032/reports/stage5d_24x24_contract_probe.json`
- status: PASS
- observation/action contract: `[24,24,27]` and `[576,6,4,4,4,4,7,49]`
- mask availability: true (`mask_source=env.vec_client.getMasks(0)`)
- policy_forward_ok: true
- masked_action_sample_ok: true
- env_step_ok: true

## Training

Command used:

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/run_24x24_staged_teacher_training_legacy032.py `
  --run-label legacy032_24x24_teacher_main `
  --stages 3000000 `
  --seed 17 `
  --device cpu `
  --map-path maps/24x24/basesWorkers24x24.xml `
  --training-max-steps 6000 `
  --episodes-per-gate 8 `
  --max-steps-per-gate 6000 `
  --evaluate-after-each `
  --no-wandb `
  --require-contract-check true
```

- total_timesteps: 3000000
- training_max_steps: 6000
- env_max_steps: 6000
- from-scratch statement: 3M is a from-scratch staged checkpoint with larger total_timesteps, not a resumed continuation from 1M.
- training duration: 35616.85 seconds (~9h 53m 37s)
- training metrics summary (from machine report):
  - episode_count: 1388
  - last_global_step: 2999382
  - mean_episode_reward: 155.85086187436877

## Standard gate

- gate report JSON path: `python/week5_teacher_legacy032/reports/stage5_gate_003000000_20260430T225547Z.json`
- gate report MD path: `python/week5_teacher_legacy032/reports/stage5_gate_003000000_20260430T225547Z.md`
- gate decision: PASS
- eval mode: both
- max_steps_per_episode: 6000
- env_max_steps: 6000
- checkpoint_load_ok: true
- policy_architecture_load_ok: true
- inference_ok: true
- eval_observation_shape: `[24,24,27]`
- eval_action_space: `[576,6,4,4,4,4,7,49]`
- env_matches_target_24x24: true
- mask_used_during_eval: true

Key deterministic metrics (3M):

- mean_return: -10.0
- noop_share: 0.9965651659384103
- effective_activity_share: 0.003434834061589731
- move_share: 0.0
- attack_action_count: 40
- produce_action_count: 8360
- policy_entropy_proxy: 0.0006490565462494426
- repeated_same_action_share: 0.9999958170197102
- observed_max_episode_length: 712

Key stochastic metrics (3M):

- mean_return: -10.0
- noop_share: 0.16623751560549313
- effective_activity_share: 0.8337624843945068
- move_share: 0.16624726903870163
- attack_action_count: 817054
- produce_action_count: 824908
- policy_entropy_proxy: 0.0006434021773641822
- repeated_same_action_share: 0.19113715945892684
- observed_max_episode_length: 712

## 1M vs 3M quick comparison

Baseline 1M source:

- run_id: `legacy032_24x24_teacher_main_20260429T195603Z`
- gate: `python/week5_teacher_legacy032/reports/stage5_gate_001000000_20260429T232455Z.json`

| metric | 1M | 3M | interpretation |
|---|---:|---:|---|
| stochastic mean_return | -10.0 | -10.0 | higher is better |
| deterministic mean_return | -10.0 | -10.0 | higher is better |
| stochastic noop_share | 0.1662964425977944 | 0.16623751560549313 | context-dependent |
| deterministic noop_share | 0.9965651659384103 | 0.9965651659384103 | lower is better but all-cell metric can mislead |
| stochastic effective_activity_share | 0.8337035574022056 | 0.8337624843945068 | should stay >0 |
| stochastic move_share | 0.16624726903870163 | 0.16624726903870163 | should remain nonzero |
| stochastic produce_action_count | 824618 | 824908 | raw count depends on horizon |
| stochastic attack_action_count | 817054 | 817054 | raw count depends on horizon |
| stochastic policy_entropy_proxy | 0.0005863994307689476 | 0.0006434021773641822 | monitor collapse |
| repeated_same_action_share | 0.19117079759209063 | 0.19113715945892684 | monitor collapse |
| env_matches_target_24x24 | true | true | must remain true |
| mask_used_during_eval | true | true | must remain true |

## Warnings

- deterministic all-cell noop_share remains high.
- return did not improve versus 1M.
- source-cell/contact diagnostics still pending (mask bit semantics are ambiguous in current runtime).
- 3M is from-scratch, not resumed from 1M.

Not-applicable warning from requested list:

- entropy declined: not observed between 1M and 3M on standard stochastic gate (`0.0005863994` to `0.0006434022`).

## Decision for next prompt

READY_FOR_3M_DIAGNOSTICS

Rationale:

- Training and standard gate completed successfully with stable technical compatibility.
- Checkpoint/metadata/gate artifacts are valid.
- Behavior remains warning-class (no return improvement and high deterministic all-cell noop share).
- Next mandatory step is extended large-map diagnostics on the 3M checkpoint before any 5M decision.
