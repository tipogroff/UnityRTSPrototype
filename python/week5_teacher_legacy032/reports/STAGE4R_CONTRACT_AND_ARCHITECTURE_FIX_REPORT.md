# STAGE4R Contract And Architecture Fix Report

Date: 2026-04-29

## Correction Summary

- Stage 4 contract mismatch classification was caused by incorrect expected contract for GridMode.
- Observed GridMode 24x24 action nvec `[576,6,4,4,4,4,7,49]` is correct.
- Global single-action contract `[576,6,4,4,4,4,7,576]` remains valid only for gym.make/preflight-style env mode, not for GridMode teacher training.
- True blocker was actor output spatial shape mismatch on 24x24.

## Mode Separation (Fixed)

1. Legacy gym.make global single-action mode:
- nvec: `[576,6,4,4,4,4,7,576]`

2. Legacy MicroRTSGridModeVecEnv mode (teacher training):
- nvec: `[576,6,4,4,4,4,7,49]`
- attack target semantics: local 7x7

3. Unity v2 target branch sizes:
- `[6,4,4,4,4,7,49]`

## Implemented Code Fixes

### Verifier

File:
- `python/week5_teacher_legacy032/scripts/verify_legacy032_24x24_training_contract.py`

Changes:
- Added explicit constants for global-single, gridmode, and Unity v2 branch sizes.
- Corrected GridMode expected nvec to `[576,6,4,4,4,4,7,49]`.
- Added explicit representation fields in JSON output.
- Added resolution-aware decoder in probe policy.
- Status logic now distinguishes contract mismatch vs architecture mismatch.

### Patched trainer

File:
- `python/week5_teacher_legacy032/scripts/ppo_gridnet_legacy032_24x24_local_save.py`

Changes:
- Corrected GridMode expected nvec function to use attack branch 49.
- Added representation metadata:
  - representation_mode
  - gridmode_expected_nvec
  - unity_v2_branch_sizes
  - global_single_action_reference_nvec
  - attack_target_semantics
  - architecture_name = `legacy032_resolution_aware_gridnet_v1`
- Implemented resolution-aware actor head:
  - deconv backbone
  - interpolate to target HxW
  - final 1x1 conv projection
- Fixed critic shape for 24x24 by adding `AdaptiveAvgPool2d((1,1))` before flatten.

### Evaluator

File:
- `python/week5_teacher_legacy032/scripts/evaluate_teacher_legacy032.py`

Changes:
- Added split expected contracts:
  - preflight_24x24_global_single_expected_nvec = `[576,6,4,4,4,4,7,576]`
  - target_24x24_gridmode_expected_nvec = `[576,6,4,4,4,4,7,49]`
  - reference_internal_16x16_expected_nvec = `[256,6,4,4,4,4,7,49]`
- `env_matches_target_24x24` now checks 24x24 + `[...,49]`.
- Added architecture-aware policy reconstruction using metadata `architecture_name`.
- Added resolution-aware decoder path in evaluator policy model.
- Fixed critic shape for resolution-aware path with adaptive pooling.

## Stage 4R Probe Execution

Command run:

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe \
  python/week5_teacher_legacy032/scripts/verify_legacy032_24x24_training_contract.py \
  --map-path maps/24x24/basesWorkers24x24.xml \
  --num-bot-envs 6 --num-selfplay-envs 0 --seed 17 \
  --output-json python/week5_teacher_legacy032/reports/stage4r_24x24_contract_probe.json
```

Result:
- status: `PASS`
- observation_space: `[24,24,27]`
- action_space_nvec: `[576,6,4,4,4,4,7,49]`
- mask_available: true
- policy_forward_ok: true
- masked_action_sample_ok: true
- env_step_ok: true
- policy_actor_output_shape: `[6,24,24,78]`

Artifact:
- `python/week5_teacher_legacy032/reports/stage4r_24x24_contract_probe.json`

## Smoke Training (10k) After PASS Probe

Command run:

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe \
  python/week5_teacher_legacy032/scripts/train_teacher_legacy032_24x24.py \
  --run-label legacy032_24x24_smoke \
  --map-path maps/24x24/basesWorkers24x24.xml \
  --seed 17 --total-timesteps 10000 --device cpu --no-wandb --require-contract-check true
```

Result:
- PASS
- checkpoint saved
- metadata saved

Artifacts:
- `python/week5_teacher_legacy032/teacher_models/legacy032_24x24_smoke_20260429T133037Z/agent_final.pt`
- `python/week5_teacher_legacy032/teacher_models/legacy032_24x24_smoke_20260429T133037Z/model_metadata.json`
- `python/week5_teacher_legacy032/reports/stage4_24x24_smoke_training_20260429T133037Z.json`

## Behavior Gate on target_24x24_gridmode

Command run:

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe \
  python/week5_teacher_legacy032/scripts/evaluate_teacher_legacy032.py \
  --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_smoke_20260429T133037Z/agent_final.pt \
  --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_smoke_20260429T133037Z/model_metadata.json \
  --run-label stage4r_24x24_smoke_behavior_gate \
  --episodes 8 --seed 17 --device cpu \
  --output-dir python/week5_teacher_legacy032/reports \
  --eval-mode both --env-mode target_24x24_gridmode --require-mask true --max-steps-per-episode 2000
```

Result:
- gate_decision: `PASS`
- checkpoint_load_ok: true
- policy_architecture_load_ok: true
- inference_ok: true
- eval_observation_shape: `[24,24,27]`
- eval_action_space: `[576,6,4,4,4,4,7,49]`
- env_matches_target_24x24: true
- mask_used_during_eval: true
- action_type_distribution recorded

Artifact:
- `python/week5_teacher_legacy032/reports/stage3_smoke_checkpoint_behavior_gate_20260429T142601Z.json`

## Stage 4R Decision

`READY_FOR_24X24_100K_TRAINING`
