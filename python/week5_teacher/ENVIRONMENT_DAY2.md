# Day 2 Validated Environment (Week 5)

## Canonical requirement

Day 2 canonical teacher basis is fixed to:

- MicroRTS-Py v0.6.1-compatible stack
- 27-channel observation surface (no extra terrain/walls channel)
- runtime + shape smoke checks only

If only an observation format with an extra terrain/walls channel is available, this must be treated as incompatibility for Day 2 canonical baseline.

## Why Python 3.9 was required

In this workspace, Python 3.10 environment could not install MicroRTS-Py v0.6.1 directly (`python_requires <3.10`).

Therefore a dedicated Day 2 environment was created with Python 3.9.

## Validated stack

- Python: 3.9.13
- Java: Eclipse Temurin JDK 17.0.18
- gym-microrts: editable install from `MicroRTS-Py` git tag `v0.6.1` (distribution version reports as `0.0.0`)
- gym: 0.23.1
- gymnasium: 0.29.1
- stable-baselines3: 2.3.2
- torch: 2.8.0
- numpy: 1.26.4
- JPype1: 1.5.1

## One-command bootstrap

Use helper script in this folder:

```powershell
./setup_day2_env.ps1 -JavaHome "C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot" -AntBin "C:/Tools/apache-ant-1.10.14/bin"
```

Useful options:

- `-InstallPrerequisites` installs Python 3.9 and JDK 17 via winget.
- `-Python39Exe <path>` forces a specific Python 3.9 interpreter.
- `-RunSmokeCheck` runs `run_teacher_rollout.py` at the end.

## Bootstrap commands used

```powershell
winget install -e --id Python.Python.3.9 --accept-package-agreements --accept-source-agreements
winget install -e --id EclipseAdoptium.Temurin.17.JDK --accept-package-agreements --accept-source-agreements

C:/Users/grozo/AppData/Local/Programs/Python/Python39/python.exe -m venv c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe -m pip install --upgrade pip setuptools wheel
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe -m pip install -r c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/requirements_day2_canonical.txt

# Editable fixed-tag source install
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe -m pip install -e C:/Temp/MicroRTS-Py-v0.6.1
```

## Java artifact note

For this stack, `microrts.jar` must exist under `gym_microrts/microrts/`.
If missing, runtime fails with class loading errors (`rts.units.UnitTypeTable`).

Build path used:

```powershell
# Apache Ant was installed to C:/Tools/apache-ant-1.10.14
$env:JAVA_HOME='C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME/bin;C:/Tools/apache-ant-1.10.14/bin;$env:Path"

C:/Tools/apache-ant-1.10.14/bin/ant.bat -f C:/Temp/MicroRTS-Py-v0.6.1/gym_microrts/microrts/build.xml export_jar
Copy-Item -Force C:/Temp/MicroRTS-Py-v0.6.1/gym_microrts/microrts/build/microrts.jar C:/Temp/MicroRTS-Py-v0.6.1/gym_microrts/microrts/microrts.jar
```

## Validated smoke command

```powershell
$env:JAVA_HOME='C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME/bin;$env:Path"

c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/run_teacher_rollout.py \
  --episodes 1 \
  --env-id MicrortsSelfPlayShapedReward-v1 \
  --map-path maps/24x24/basesWorkers24x24.xml \
  --seed 17 \
  --allow-random-policy-smoke-fallback \
  --rollout-step-limit 64
```

## Validation status

- Environment creation: passed (legacy `gym_microrts.envs.vec_env.MicroRTSGridModeVecEnv` fallback used)
- Observation surface: passed (`[1,24,24,27]`, 27-channel compatible)
- Rollout terminal reached: passed (`terminated`)
- Runtime summary written: passed (`teacher_logs/teacher_rollout_*.summary.json`)

## Scope statement (honest)

This Day 2 validation proves:

- runtime environment can be created and stepped to terminal;
- observation surface matches 27-channel expectation at shape level;
- script-level smoke path is operational.

This Day 2 validation does not prove:

- semantic parity with Unity MVP environment;
- exact scenario equivalence beyond known approximation;
- rollout dataset readiness;
- exporter/adapter/BC pipeline correctness.
