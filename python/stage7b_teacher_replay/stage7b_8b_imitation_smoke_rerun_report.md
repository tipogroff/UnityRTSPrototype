# Stage7B-8B-Rerun ML-Agents Small Imitation Smoke Report

Date: 2026-05-11
Status: NO-GO
Run ID: Stage7B_ImitationSmoke_003

## Manual Precheck
- Scene opened manually: Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity (confirmed)
- Behavior Parameters precheck: confirmed by operator
  - Behavior Name: Stage7B_RTS_Student
  - Behavior Type: Default
  - Vector Observation Size: 15552
  - Discrete Branch Count: 1
  - Branch Size: 128
- Orchestrator conflict: confirmed off/no conflict
- Unity Console before run: 0 errors / 0 warnings

## Command
python/stage7b_mlagents/.venv_mlagents/Scripts/mlagents-learn.exe config/stage7b_imitation_smoke.yaml --run-id Stage7B_ImitationSmoke_003 --force

## Runtime Outcome
- Trainer started: yes
- Config loaded: yes (results/Stage7B_ImitationSmoke_003/configuration.yaml created)
- Unity connected: yes
- Handshake: package 4.0.2, communication 1.5.0
- Behavior name matched: Stage7B_RTS_Student
- training_steps_completed: 0
- Process exit code: 1
- Error: UnityTimeOutException during TrainerController._reset_env

## Artifacts
- results/Stage7B_ImitationSmoke_003/configuration.yaml
- results/Stage7B_ImitationSmoke_003/run_logs/timers.json
- results/Stage7B_ImitationSmoke_003/run_logs/training_status.json
- No checkpoint/model/tfevents artifacts found
- Trainer log capture:
  - python/stage7b_teacher_replay/stage7b_8b_imitation_smoke_rerun_trainer.log

## NaN Check
- No NaN evidence in logs before timeout

## Unity Console After Run
- Errors: 0
- Warnings: 0

## GO/NO-GO
NO-GO

Blocker:
- Unity environment connects but does not complete first reset/step cycle, causing UnityTimeOutException before any training step or checkpoint.

Next Fix:
- Inspect live scene components while in Play mode for communicator step flow:
  - Verify Student agent actually requests decisions and sends actions each Academy step.
  - Verify DecisionRequester is active and not disabled at runtime.
  - Verify no script forces Academy stepping pause.
  - Verify StudentMlAgent is not in demo/orchestrator-only path that bypasses trainer-driven action loop.
  - Verify episode reset path returns an observation/action-capable state immediately after reset.

## Safety/Scope Confirmation
- Stage6B3 baseline untouched: yes
- Long training started: no
- PPO fine-tune as full stage started: no
- Config/demo/reward/teacher/runtime semantics modified: no
