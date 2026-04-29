# Stage 2 Smoke Training Report (legacy032)

## Summary

Stage 2 smoke training completed successfully with checkpoint output in legacy032-only directories.

- training_status: PASS
- stage3_readiness_decision: READY_FOR_STAGE3_BEHAVIOR_GATE
- run_id: legacy032_smoke_20260429T113844Z

Important:

- This Stage 2 checkpoint is a smoke artifact only.
- It is not a final teacher and is not a Unity v2 export-ready artifact.

---

## Command used

```powershell
$env:JAVA_HOME = 'C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path = "$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/train_teacher_legacy032.py `
  --run-label legacy032_smoke `
  --env-id MicrortsRandomEnemyShapedReward1-v1 `
  --map-path maps/24x24/basesWorkers24x24.xml `
  --seed 17 `
  --total-timesteps 10000 `
  --device cpu `
  --no-wandb `
  --allow-unmasked-smoke
```

---

## Environment

- wrapper env_id: MicrortsRandomEnemyShapedReward1-v1
- wrapper map_path: maps/24x24/basesWorkers24x24.xml
- preflight result: PASS
- preflight obs shape: (24, 24, 27)
- preflight action_space.nvec: [576, 6, 4, 4, 4, 4, 7, 576]

Reference training subprocess note:

- reference script constructs its own MicroRTSGridModeVecEnv and uses internal script configuration;
- metadata confirms subprocess training used 16x16 paper-style surface for this smoke run.

---

## Reference script used

- python/week5_teacher_reference/patched_paper_scripts/ppo_gridnet_diverse_encode_decode_local_save.py

---

## Training status

- process launch: PASS
- training loop progression observed: PASS
- episode lines observed in stdout: 6
- total_steps_observed from logs: 8430
- final_reward_mean (available metric): 17.199999968210857
- duration_seconds: 64.41

---

## Output artifacts

- summary json: python/week5_teacher_legacy032/reports/stage2_smoke_training_20260429T113844Z.json
- summary md: python/week5_teacher_legacy032/reports/stage2_smoke_training_20260429T113844Z.md
- stdout log: python/week5_teacher_legacy032/teacher_logs/legacy032_smoke_20260429T113844Z/training_stdout.log
- stderr log: python/week5_teacher_legacy032/teacher_logs/legacy032_smoke_20260429T113844Z/training_stderr.log
- metrics jsonl: python/week5_teacher_legacy032/teacher_logs/legacy032_smoke_20260429T113844Z/training_metrics.jsonl
- model dir: python/week5_teacher_legacy032/teacher_models/legacy032_smoke_20260429T113844Z

---

## Checkpoint status

- checkpoint_written: true
- checkpoint path:
  - python/week5_teacher_legacy032/teacher_models/legacy032_smoke_20260429T113844Z/agent_final.pt
- model metadata:
  - python/week5_teacher_legacy032/teacher_models/legacy032_smoke_20260429T113844Z/model_metadata.json

Post-training load test:

- checkpoint load via torch.load: PASS
- short env sanity steps (3 random actions after env creation): PASS
- policy-inference-step with loaded architecture: deferred to Stage 3 (non-blocking warning)

---

## Mask path investigation

Status: CONFIRMED

Confirmed path in reference script:

- masks retrieved through envs.vec_client.getMasks(0)
- masks applied via CategoricalMasked with torch.where on logits
- masks split per branch via envs.action_space.nvec[1:]

Interpretation:

- mask was not exposed by simple probe APIs in Stage 1;
- training pipeline still uses mask internally through vec-client path.

---

## Known warnings

- reference script may ignore wrapper env-id/map-path because env construction is internal to the script;
- policy inference with loaded checkpoint was not executed in Stage 2 and is deferred to Stage 3.

---

## Stage 3 readiness decision

READY_FOR_STAGE3_BEHAVIOR_GATE

Decision rationale:

- smoke training run completed;
- checkpoint saved under legacy032 model directory;
- mask path confirmed in reference training code.
