# Stage 2 Smoke Training Report

- run_id: legacy032_smoke_20260429T113844Z
- training_status: PASS
- stage3_readiness_decision: READY_FOR_STAGE3_BEHAVIOR_GATE

## Summary

Stage 2 smoke training executed under legacy032 scope. This checkpoint is a smoke artifact only and is not a final teacher.

## Command used

```text
C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_reference\.venv_microrts032_reference\Scripts\python.exe C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_reference\patched_paper_scripts\ppo_gridnet_diverse_encode_decode_local_save.py --total-timesteps 10000 --seed 17 --exp-name legacy032_smoke_20260429T113844Z --num-bot-envs 6 --num-selfplay-envs 0 --local-save-model true --local-save-dir C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_smoke_20260429T113844Z --local-save-every 0 --cuda false
```

## Environment

- env_id (wrapper preflight): MicrortsRandomEnemyShapedReward1-v1
- map_path (wrapper preflight): maps/24x24/basesWorkers24x24.xml
- env_preflight_status: PASS

## Reference script used

- C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_reference\patched_paper_scripts\ppo_gridnet_diverse_encode_decode_local_save.py

## Output artifacts

- model_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_smoke_20260429T113844Z
- log_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_logs\legacy032_smoke_20260429T113844Z
- stdout: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_logs\legacy032_smoke_20260429T113844Z\training_stdout.log
- stderr: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_logs\legacy032_smoke_20260429T113844Z\training_stderr.log
- metrics_jsonl: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_logs\legacy032_smoke_20260429T113844Z\training_metrics.jsonl
- summary_json: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage2_smoke_training_20260429T113844Z.json

## Checkpoint status

- checkpoint_written: True
- checkpoint_paths: ['C:\\Projects\\UnityRTSPrototype\\UnityRTSPrototype\\python\\week5_teacher_legacy032\\teacher_models\\legacy032_smoke_20260429T113844Z\\agent_final.pt']
- load_test: {'checkpoint_load_ok': True, 'inference_steps_ok': False, 'random_env_steps_ok': True, 'steps': 3, 'error': 'model inference with loaded policy is deferred to Stage 3 (non-blocking in Stage 2)'}

## Mask path investigation

- mask_path_status: CONFIRMED
- details: Mask path confirmed in reference training script: masks are retrieved via envs.vec_client.getMasks(0), split by action branches, and applied in CategoricalMasked through torch.where(...) before sampling/log-prob.This explains why probe APIs did not expose mask directly.

## Known warnings

- Reference script uses internal MicroRTSGridModeVecEnv configuration and may ignore --env-id/--map-path passed to wrapper.
- Checkpoint inference-step test was not completed in Stage 2; deferred to Stage 3 as non-blocking warning.

## Known errors

- none

## Stage 3 readiness decision

READY_FOR_STAGE3_BEHAVIOR_GATE
