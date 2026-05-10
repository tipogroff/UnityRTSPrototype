# Stage7B-8B ML-Agents Small Imitation Smoke Report

Date: 2026-05-11
Status: NO-GO
Run ID: Stage7B_ImitationSmoke_001

## Command
python/stage7b_mlagents/.venv_mlagents/Scripts/mlagents-learn.exe config/stage7b_imitation_smoke.yaml --run-id Stage7B_ImitationSmoke_001 --force

## Environment
- Python executable: python/stage7b_mlagents/.venv_mlagents/Scripts/python.exe
- ml-agents: 0.30.0
- ml-agents-envs: 0.30.0
- Scene target: Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity
- Behavior name: Stage7B_RTS_Student

## Inputs
- Config: config/stage7b_imitation_smoke.yaml (exists)
- Demo: Assets/Demonstrations/stage7b_teacher_replay_clean_smoke.demo (exists, 15068229 bytes)

## Trainer Start Result
- Trainer process started successfully.
- Config loaded successfully (results/Stage7B_ImitationSmoke_001/configuration.yaml created).
- Trainer reached listening state on port 5004.

## Unity Connection Result
- Unity connected successfully.
- Log line: Connected to Unity environment with package version 4.0.2 and communication version 1.5.0.

## Smoke Run Outcome
- Run terminated with exit code 1.
- Failure type: UnityTimeOutException during environment reset.
- Error summary: Unity environment took too long to respond after handshake.
- Training steps completed: 0
- NaN detected (loss/reward): no evidence in logs before timeout.

## Artifacts
Created under results/Stage7B_ImitationSmoke_001:
- configuration.yaml
- run_logs/timers.json
- run_logs/training_status.json

Checkpoint artifacts:
- None found (.pt/.onnx/.nn/checkpoint/tfevents absent)

Trainer log capture:
- python/stage7b_teacher_replay/stage7b_8b_imitation_smoke_trainer.log

## Unity Console
- Error count: 2
- Warning count: 0
- Errors observed were MCP menu-item open-scene command failures, not protocol mismatch errors.

## GO/NO-GO Decision
NO-GO

Reason:
- Although trainer startup, config parse, and Unity communicator handshake succeeded, smoke criteria failed because no training progress/checkpoint was produced and run ended with UnityTimeOutException.

## Constraints Compliance
- Stage6B3 baseline untouched: yes (no stage6b3 path modifications detected in git status)
- Long training started: no
- PPO fine-tune full stage started: no
- Teacher policy changed: no
- Reward changed: no
- Unity runtime semantics changed: no
- Clean demo changed: no

## Recommendation
Before Stage7B-8C, rerun Stage7B-8B with confirmed active scene loading in Unity Editor (explicitly open Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity before Play) and verify that the student Behavior Parameters is set to Default at runtime for trainer control.
