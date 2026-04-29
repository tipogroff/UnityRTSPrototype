# STAGE4 Completion Report

Date: 2026-04-29
Result: BLOCKED_CONTRACT_MISMATCH
Stage 4 alignment succeeded: no

Correction note (Stage 4R supersession):

This Stage 4 result is historical and was superseded by Stage 4R.
The original contract mismatch classification used an incorrect expected GridMode attack branch (576).
Correct GridMode 24x24 contract uses attack branch 49 (local 7x7).
Global single-action expected branch 576 applies to gym.make/global-single mode only.
Stage 4R addressed this and resolved the architecture blocker.

## Files Created / Updated

Created:

- `python/week5_teacher_legacy032/reports/STAGE4_24X24_ALIGNMENT_AUDIT.md`
- `python/week5_teacher_legacy032/scripts/ppo_gridnet_legacy032_24x24_local_save.py`
- `python/week5_teacher_legacy032/scripts/verify_legacy032_24x24_training_contract.py`
- `python/week5_teacher_legacy032/scripts/train_teacher_legacy032_24x24.py`
- `python/week5_teacher_legacy032/reports/stage4_24x24_contract_probe.json`
- `python/week5_teacher_legacy032/reports/STAGE4_24X24_ALIGNMENT_REPORT.md`
- `python/week5_teacher_legacy032/reports/STAGE4_COMPLETION_REPORT.md`

Updated:

- `python/week5_teacher_legacy032/scripts/evaluate_teacher_legacy032.py`
- `python/week5_teacher_legacy032/scripts/README.md`
- `python/week5_teacher_legacy032/LEGACY032_TEACHER_TRAINING_PLAN.md`

Generated validation artifact:

- `python/week5_teacher_legacy032/reports/stage4_target24_failfast_check_20260429T130423Z.json`

## Commands Run

1.

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe \
  python/week5_teacher_legacy032/scripts/verify_legacy032_24x24_training_contract.py \
  --map-path maps/24x24/basesWorkers24x24.xml \
  --num-bot-envs 6 --num-selfplay-envs 0 --seed 17 \
  --output-json python/week5_teacher_legacy032/reports/stage4_24x24_contract_probe.json
```

2. Re-run same command after fixing probe mask-call order.

3. Evaluator fail-fast check:

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe \
  python/week5_teacher_legacy032/scripts/evaluate_teacher_legacy032.py \
  --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_smoke_20260429T113844Z/agent_final.pt \
  --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_smoke_20260429T113844Z/model_metadata.json \
  --run-label stage4_target24_failfast_check \
  --episodes 2 --seed 17 --device cpu \
  --output-dir python/week5_teacher_legacy032/reports \
  --eval-mode deterministic --env-mode target_24x24_gridmode \
  --require-mask true --max-steps-per-episode 2000
```

## Output Paths

- Contract probe JSON:
  - `python/week5_teacher_legacy032/reports/stage4_24x24_contract_probe.json`
- Alignment report:
  - `python/week5_teacher_legacy032/reports/STAGE4_24X24_ALIGNMENT_REPORT.md`
- Completion report:
  - `python/week5_teacher_legacy032/reports/STAGE4_COMPLETION_REPORT.md`

## Why Stage 4 Is Blocked

- Requested target action contract for Stage 4: `[576,6,4,4,4,4,7,576]`
- Observed GridMode action contract on 24x24 map: `[576,6,4,4,4,4,7,49]`
- Superseded interpretation: not a real GridMode mismatch.
- Policy masked sampling on 24x24 currently fails with tensor shape mismatch.

## Exact Next Action

BLOCKED path:

1. Resolve contract definition mismatch for 24x24 target env mode (decide whether Stage 4 target should be GridMode `[...49]` or different env path that yields `[...576]`).
2. Apply minimal architecture fix so actor output spatial size matches env map HxW at 24x24.
3. Re-run Stage 4 contract probe.
4. Only after probe PASS run 24x24 10k smoke training and target_24x24 behavior gate.
