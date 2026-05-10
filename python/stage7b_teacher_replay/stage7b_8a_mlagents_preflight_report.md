# Stage7B-8A ML-Agents Trainer Environment Preflight

- status: NO_GO
- generated_at_utc: 2026-05-10T22:39:00Z

## 1) Python Environment Discovery

- python_executable: c:/Projects/UnityRTSPrototype/UnityRTSPrototype/.venv/Scripts/python.exe
- python_version: 3.10.11
- pip_version: 26.0.1
- mlagents-learn --help: unavailable (CommandNotFound)
- python -m mlagents.trainers.learn --help: unavailable (ModuleNotFoundError)

Package checks:
- mlagents: NOT_INSTALLED
- mlagents-envs: NOT_INSTALLED
- torch: 2.11.0
- numpy: 1.26.4
- protobuf: NOT_INSTALLED
- grpcio: NOT_INSTALLED

Existing project venvs checked:
- python/week5_teacher/.venv_day2_py39 (mlagents NOT_INSTALLED)
- python/week5_teacher_reference/.venv_microrts032_reference (mlagents NOT_INSTALLED)

Install plan (without touching week5/week6 venv):
- recommended new venv: python/stage7b_mlagents/.venv_mlagents
- python -m venv python/stage7b_mlagents/.venv_mlagents
- python/stage7b_mlagents/.venv_mlagents/Scripts/python.exe -m pip install --upgrade pip
- python/stage7b_mlagents/.venv_mlagents/Scripts/python.exe -m pip install mlagents==1.1.0
- python/stage7b_mlagents/.venv_mlagents/Scripts/python.exe -m pip show mlagents mlagents-envs torch numpy protobuf grpcio

## 2) Unity Package Compatibility

- unity_version: 6000.3.10f1
- com.unity.ml-agents: 4.0.2
- behavior_name: Stage7B_RTS_Student
- observation_size: 15552
- discrete_branch_count: 1
- candidate_branch_size: 128
- demo_file_path: Assets/Demonstrations/stage7b_teacher_replay_clean_smoke.demo

## 3) Demo File Validation

- file exists: true
- file size: 15068229 bytes (> 0)
- path readable: true
- demo behavior name (from Stage7B-7D report): Stage7B_RTS_Student
- optional ML-Agents demo inspection: not available (mlagents package missing)

## 4) Trainer Config Draft

- config_path: config/stage7b_imitation_smoke.yaml
- config_created: true
- behavior key matches: Stage7B_RTS_Student
- trainer_type: ppo
- behavioral_cloning.demo_path: Assets/Demonstrations/stage7b_teacher_replay_clean_smoke.demo
- max_steps: 10000
- summary_freq: 500
- keep_checkpoints: 2
- normalize: false
- self-play/curriculum/GAIL: not configured

## 5) Dry Command (Prepared Only, Not Executed)

- mlagents-learn config/stage7b_imitation_smoke.yaml --run-id Stage7B_ImitationSmoke_001 --force

Editor workflow for next stage:
- open scene: Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity
- start mlagents-learn command
- press Play in Unity after trainer waits for Unity connection

## 6) GO/NO-GO for Stage7B-8B

Decision: NO_GO

Reasons:
- mlagents and mlagents-envs are not installed in detected environments.
- mlagents-learn is not available yet.

Criteria snapshot:
- demo file exists and non-empty: PASS
- config created and behavior key matches: PASS
- environment ready for trainer command: FAIL
- stage6b3 baseline untouched: PASS
- no training/PPO/imitation started: PASS

## Confirmation

- Stage6B3 baseline untouched: confirmed
- no training started: confirmed
- no PPO run started: confirmed
- no imitation run started: confirmed
