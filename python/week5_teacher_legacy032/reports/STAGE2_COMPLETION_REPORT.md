# Stage 2 Completion Report (legacy032)

## Outcome

- Stage: 2 (short smoke training)
- Result: COMPLETE
- Training status: PASS
- Run id: legacy032_smoke_20260429T113844Z
- Stage 3 readiness: READY_FOR_STAGE3_BEHAVIOR_GATE

This run is a smoke validation artifact only; it is not a final teacher claim.

---

## Files created/updated

Created:

- python/week5_teacher_legacy032/scripts/train_teacher_legacy032.py
- python/week5_teacher_legacy032/reports/STAGE2_REFERENCE_SCRIPT_AUDIT.md
- python/week5_teacher_legacy032/reports/stage2_smoke_training_20260429T113844Z.json
- python/week5_teacher_legacy032/reports/stage2_smoke_training_20260429T113844Z.md
- python/week5_teacher_legacy032/reports/STAGE2_SMOKE_TRAINING_REPORT.md
- python/week5_teacher_legacy032/reports/STAGE2_COMPLETION_REPORT.md
- python/week5_teacher_legacy032/teacher_logs/legacy032_smoke_20260429T113844Z/training_stdout.log
- python/week5_teacher_legacy032/teacher_logs/legacy032_smoke_20260429T113844Z/training_stderr.log
- python/week5_teacher_legacy032/teacher_logs/legacy032_smoke_20260429T113844Z/training_metrics.jsonl
- python/week5_teacher_legacy032/teacher_models/legacy032_smoke_20260429T113844Z/agent_final.pt
- python/week5_teacher_legacy032/teacher_models/legacy032_smoke_20260429T113844Z/model_metadata.json

Updated:

- python/week5_teacher_legacy032/scripts/README.md
- python/week5_teacher_legacy032/LEGACY032_TEACHER_TRAINING_PLAN.md

---

## Commands run

Primary Stage 2 command:

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week5_teacher_legacy032/scripts/train_teacher_legacy032.py --run-label legacy032_smoke --env-id MicrortsRandomEnemyShapedReward1-v1 --map-path maps/24x24/basesWorkers24x24.xml --seed 17 --total-timesteps 10000 --device cpu --no-wandb --allow-unmasked-smoke
```

Post-training checkpoint load sanity command:

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe -c "import json,torch,gym,gym_microrts; ..."
```

Observed load sanity result:

- checkpoint_load_ok: true
- random_env_steps_ok: true
- steps: 3

---

## Key outputs

- checkpoint path:
  - python/week5_teacher_legacy032/teacher_models/legacy032_smoke_20260429T113844Z/agent_final.pt
- summary JSON path:
  - python/week5_teacher_legacy032/reports/stage2_smoke_training_20260429T113844Z.json
- canonical Stage 2 report:
  - python/week5_teacher_legacy032/reports/STAGE2_SMOKE_TRAINING_REPORT.md

---

## Can Stage 3 start?

Yes.

- readiness decision: READY_FOR_STAGE3_BEHAVIOR_GATE
- blocker check:
  - training launch: pass
  - checkpoint saved: pass
  - mask path investigation: confirmed

---

## Exact next action

Run Stage 3 behavior gate on the Stage 2 smoke checkpoint:

- input checkpoint:
  - python/week5_teacher_legacy032/teacher_models/legacy032_smoke_20260429T113844Z/agent_final.pt
- expected output:
  - python/week5_teacher_legacy032/reports/stage3_behavior_gate_*.json
