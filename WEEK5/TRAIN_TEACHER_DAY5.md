# TRAIN_TEACHER_DAY5.md

Date: 2026-04-16
Stage: Week 5 intermediate step (after teacher source selection)

## Goal

Produce the first operational meaningful non-random teacher checkpoint in canonical MicroRTS stack for:
- rollout export,
- adapter,
- Day 5 validation.

This is a minimal smoke path, not a final benchmark setup.

## Backend and scope

Training backend:
- stable_baselines3 PPO via wrapper script:
  - python/week5_teacher/train_teacher_smoke.py

Scope limits:
- one seed
- short timesteps budget
- checkpoint save
- checkpoint load validation
- handoff to existing run_teacher_rollout.py with --policy-path

Out of scope now:
- BC training
- Unity import
- large hyperparameter sweeps
- final quality claims

## Canonical assumptions fixed for this step

- Python: use Day 2 validated environment (Python 3.9 venv in this workspace)
- MicroRTS stack: Day 2 canonical line (v0.6.1-compatible setup)
- Env id: MicrortsSelfPlayShapedReward-v1
- Map assumption: maps/24x24/basesWorkers24x24.xml
- Algorithm: PPO (stable_baselines3)
- Seed: 17 (env_seed=18, rollout_seed=19 by default)

Important honesty note:
- This smoke setup is a practical minimal teacher source path and is not claimed to be the final research-grade training configuration.

## Expected artifacts

From training script:
- Checkpoint zip:
  - python/week5_teacher/teacher_models/<run_id>/teacher_sb3_ppo.zip
- Training metadata:
  - python/week5_teacher/teacher_logs/<run_id>.training.json
- Training log:
  - python/week5_teacher/teacher_logs/<run_id>.log
- Latest checkpoint pointer:
  - python/week5_teacher/teacher_models/LATEST_DAY5_TEACHER_CHECKPOINT.txt

## Training smoke command (minimal)

PowerShell:

~~~powershell
$env:JAVA_HOME='C:/Program Files/ojdkbuild/java-11-openjdk-11.0.15-1'
$env:Path="$env:JAVA_HOME/bin;$env:Path"

c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/train_teacher_smoke.py \
  --env-id MicrortsSelfPlayShapedReward-v1 \
  --map-path maps/24x24/basesWorkers24x24.xml \
  --num-bot-envs 4 \
  --seed 17 \
  --total-timesteps 8192 \
  --policy MlpPolicy
~~~

## Checkpoint load and rollout handoff command

After training, use produced checkpoint path and run non-random rollout export:

~~~powershell
$env:JAVA_HOME='C:/Program Files/ojdkbuild/java-11-openjdk-11.0.15-1'
$env:Path="$env:JAVA_HOME/bin;$env:Path"

$CKPT = Get-Content c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/teacher_models/LATEST_DAY5_TEACHER_CHECKPOINT.txt

c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/run_teacher_rollout.py \
  --policy-path $CKPT \
  --policy-algorithm ppo \
  --checkpoint-env-version 0.0.0 \
  --episodes 2 \
  --batch-mode debug \
  --batch-label day5_meaningful \
  --env-id MicrortsSelfPlayShapedReward-v1 \
  --map-path maps/24x24/basesWorkers24x24.xml \
  --seed 17 \
  --rollout-step-limit 128
~~~

Notes:
- Keep `$env:Path="$env:JAVA_HOME/bin;$env:Path"` in the same shell session. JPype starts JVM directly and may fail to resolve `instrument.dll` dependencies when `JAVA_HOME/bin` is not on PATH.
- Use `--num-bot-envs > 1` to enable parallel rollout collection during training (the main throughput lever in this pipeline).
- Use checkpoint_env_version that matches runtime from Day 2 stack; in this workspace docs, editable v0.6.1 install reports 0.0.0.
- Do not pass allow-random-policy-smoke-fallback for this run.

## Overnight run profile (safe extension)

Goal:
- Run a longer training session overnight on the same validated path.
- Preserve recoverability through periodic checkpoints.

Recommended profile:
- run_profile: overnight
- policy: MlpPolicy
- seed: 17
- num_bot_envs: 4
- total_timesteps: 100000 (safer first night) or 300000 (longer run)
- checkpoint_interval: 20000
- device: cuda (fallback to cpu if unavailable)

Ready-to-run overnight command (GPU):

~~~powershell
$env:JAVA_HOME='C:/Program Files/ojdkbuild/java-11-openjdk-11.0.15-1'
$env:Path="$env:JAVA_HOME/bin;$env:Path"

c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/train_teacher_smoke.py \
  --run-profile overnight \
  --run-label day5_teacher_overnight \
  --env-id MicrortsSelfPlayShapedReward-v1 \
  --map-path maps/24x24/basesWorkers24x24.xml \
  --num-bot-envs 4 \
  --seed 17 \
  --total-timesteps 100000 \
  --checkpoint-interval 20000 \
  --policy MlpPolicy \
  --device cuda
~~~

CPU-safe variant (if CUDA is unavailable):

~~~powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/train_teacher_smoke.py \
  --run-profile overnight \
  --run-label day5_teacher_overnight \
  --env-id MicrortsSelfPlayShapedReward-v1 \
  --map-path maps/24x24/basesWorkers24x24.xml \
  --num-bot-envs 4 \
  --seed 17 \
  --total-timesteps 100000 \
  --checkpoint-interval 20000 \
  --policy MlpPolicy \
  --device cpu
~~~

Expected overnight artifacts:
- Final checkpoint pointer:
  - python/week5_teacher/teacher_models/LATEST_DAY5_TEACHER_CHECKPOINT.txt
- Final checkpoint file:
  - python/week5_teacher/teacher_models/<run_id>/teacher_sb3_ppo.zip (or *_interrupted.zip)
- Interval checkpoints:
  - python/week5_teacher/teacher_models/<run_id>/checkpoints/teacher_sb3_ppo_step_<timesteps>.zip
- Interval latest pointer:
  - python/week5_teacher/teacher_models/<run_id>/checkpoints/LATEST_INTERVAL_CHECKPOINT.txt
- Extended metadata:
  - python/week5_teacher/teacher_logs/<run_id>.training.json

## Morning validation command (non-random rollout)

Use final/latest checkpoint pointer and run canonical rollout without random fallback:

~~~powershell
$env:JAVA_HOME='C:/Program Files/ojdkbuild/java-11-openjdk-11.0.15-1'
$env:Path="$env:JAVA_HOME/bin;$env:Path"

$CKPT = Get-Content c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/teacher_models/LATEST_DAY5_TEACHER_CHECKPOINT.txt

c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/run_teacher_rollout.py \
  --policy-path $CKPT \
  --policy-algorithm ppo \
  --checkpoint-env-version 0.0.0 \
  --episodes 2 \
  --batch-mode debug \
  --batch-label day5_overnight_morning_check \
  --env-id MicrortsSelfPlayShapedReward-v1 \
  --map-path maps/24x24/basesWorkers24x24.xml \
  --seed 17
~~~

## Optional adapter handoff command

~~~powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/adapt_teacher_dataset.py \
  --input-batch-dir <PATH_TO_TEACHER_ROLLOUT_BATCH> \
  --write-debug-jsonl
~~~

## Pass criteria for this step

This step is successful when all conditions are true:
1. train_teacher_smoke.py finishes and writes checkpoint zip.
2. checkpoint reload validation inside script passes (no space mismatch).
3. run_teacher_rollout.py works with --policy-path on that checkpoint.
4. resulting batch is produced without random fallback.

## If smoke fails

Record as blocker with:
- exact failing command,
- phase (env create / train / save / load / rollout),
- first error line,
- minimal required fix.

Do not claim teacher checkpoint obtained until all pass criteria above are met.
