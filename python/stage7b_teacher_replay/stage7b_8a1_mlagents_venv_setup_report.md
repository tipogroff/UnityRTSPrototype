# Stage7B-8A.1 Dedicated ML-Agents Venv Setup Report

- status: GO
- generated_at_utc: 2026-05-10T22:48:30Z

## Dedicated Venv

- venv_path: python/stage7b_mlagents/.venv_mlagents
- python_executable: python/stage7b_mlagents/.venv_mlagents/Scripts/python.exe
- python_version: 3.9.13
- pip_version: 26.0.1

## Installation Summary

Primary requested pin attempt:
- mlagents==1.1.0 -> FAILED (no matching distribution found on current index)

Compatible pin set applied in dedicated venv:
- mlagents==0.30.0
- mlagents_envs==0.30.0
- protobuf==3.20.3
- torch==2.2.2

Installed package versions:
- mlagents: 0.30.0
- mlagents-envs: 0.30.0
- torch: 2.2.2
- numpy: 1.21.2
- protobuf: 3.20.3
- grpcio: 1.80.0

## Trainer CLI Availability

- python -m mlagents.trainers.learn --help: OK
- python/stage7b_mlagents/.venv_mlagents/Scripts/mlagents-learn.exe --help: OK
- mlagents_learn_available: true
- mlagents_learn_help_ok: true

## Demo and Config Validation

- demo_file_path: Assets/Demonstrations/stage7b_teacher_replay_clean_smoke.demo
- demo_file_exists: true
- demo_file_size_bytes: 15068229
- config_path: config/stage7b_imitation_smoke.yaml
- config_exists: true
- behavior_name: Stage7B_RTS_Student

## Stage7B-8B Readiness

- ready_for_stage7b_8b: true
- stage6b3_baseline_touched: false
- no_training_started: true
- no_ppo_started: true
- no_imitation_started: true
- active_project_venv_modified: false

## Decision

GO for Stage7B-8B small imitation smoke pre-start checks.
