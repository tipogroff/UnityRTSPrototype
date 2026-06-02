# PPO-SANDBOX-R3 CenterPressure Short Training Report

- Date: 2026-06-02
- Result: GO
- Run ID: `PPO_CenterPressureSmoke_001`
- Sandbox scene: `Assets/Scenes/PPO_TrainingSandbox_Player1AI_vs_ScriptedBot.unity`
- Config: `config/ppo_center_pressure_smoke.yaml`
- Initialize from: `Stage7B_ImitationSmoke_010_PostKickConfirm`

## Training Scope

The isolated PPO smoke completed without a long run. A copied config was added so the existing smoke config remained unchanged. The copied config uses `max_steps: 4096`; the trainer collected `4153` steps before final export.

The first attempted launch used the system `python.exe` and failed before training because that interpreter does not contain `mlagents`. The successful launch used:

```text
python/stage7b_mlagents/.venv_mlagents/Scripts/mlagents-learn.exe config/ppo_center_pressure_smoke.yaml --run-id PPO_CenterPressureSmoke_001 --initialize-from Stage7B_ImitationSmoke_010_PostKickConfirm
```

## Preflight

- Active scene: sandbox scene confirmed
- `CenterPressure` profile: enabled only in sandbox
- Runtime mode: effective `TrainerControlled`
- Scripted opponent stepping: enabled
- HumanPlay UI/manual dependency: none required
- Duplicate bare `Unity.MLAgents.Agent`: false
- `BehaviorParameters` and `DecisionRequester`: present
- Observation size: `15552`
- Candidate action branch size: `128`
- Attack target contract: local `7x7 / 49`
- Requested run ID availability: `PPO_CenterPressureSmoke_001` was free

## Trainer Result

- Trainer startup: successful
- Unity connection: successful, package `4.0.2`, communication protocol `1.5.0`
- Brain: `Stage7B_RTS_Student?team=0`
- Checkpoint initialization: successful from `results/Stage7B_ImitationSmoke_010_PostKickConfirm/Stage7B_RTS_Student/checkpoint.pt`
- Trainer exit code: `0`
- Steps collected: `4153`
- Episode count visible in timers: `3`
- Reward summaries: `1.1550`, `7.6300`, `6.7200`
- Final reported reward: `6.7200`
- Padding warnings: `0`
- Runtime exceptions: `0`
- Console errors: `0`

## Exported Artifacts

Checkpoints:

- `results/PPO_CenterPressureSmoke_001/Stage7B_RTS_Student/checkpoint.pt`
- `results/PPO_CenterPressureSmoke_001/Stage7B_RTS_Student/Stage7B_RTS_Student-3961.pt`
- `results/PPO_CenterPressureSmoke_001/Stage7B_RTS_Student/Stage7B_RTS_Student-4153.pt`

ONNX:

- `results/PPO_CenterPressureSmoke_001/Stage7B_RTS_Student.onnx`
- `results/PPO_CenterPressureSmoke_001/Stage7B_RTS_Student/Stage7B_RTS_Student-3961.onnx`
- `results/PPO_CenterPressureSmoke_001/Stage7B_RTS_Student/Stage7B_RTS_Student-4153.onnx`

TensorBoard:

- `results/PPO_CenterPressureSmoke_001/Stage7B_RTS_Student/events.out.tfevents.1780367004.grozov.79756.0`

## CenterPressure Diagnostics

- Bot decisions: `596`
- Bot commands accepted / rejected: `4891 / 0`
- Center rally moves / center visits: `101 / 67`
- Attack intent / submit / accepted: `30 / 30 / 30`
- Worker max: `4`
- Heavy max: `1`
- Combat max: `5`
- Total army max: `9`
- Over-army-cap steps: `0`
- Economy composition healthy: `true`
- Center pressure observed: `true`
- Permanent base idle: `false`

## Runtime Warnings

Two existing presentation warnings remained for missing animator parameter `IsCarrying` and trigger `Spawn`.

Four no-adjacent-spawn-cell warnings occurred for Heavy near `(2, 0)` and `(0, 2)`. These coordinates are on the Player1/student side. They did not deactivate CenterPressure, cause rejected bot commands, produce exceptions, or block training completion.

## Protection Audit

Pre-run and post-run SHA256 matched for:

- `Assets/Scenes/MainMenu.unity`
- `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`
- `Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity`
- `Assets/MLAgents/Models/Stage7B_RTS_Student_ImitationSmoke_010.onnx`
- `Assets/Scripts/ML/ActionDecoder.cs`
- `Assets/Scripts/ML/ActionApplier.cs`
- `Assets/Scripts/Gameplay/Match/MatchManager.cs`
- `Assets/ML/GameConfig_MVP.asset`
- Worker, Light, Heavy, Ranged, and Barracks `UnitDef` assets

Python training scripts and the original `config/stage7b_ppo_finetune_smoke.yaml` remained unchanged. New model artifacts belong only to `results/PPO_CenterPressureSmoke_001`. The new model was not integrated into HumanPlay.

## Result

GO. The resulting PPO model is safe for sandbox-only inference evaluation.

## Recommended Next Task

`PPO-SANDBOX-R4-CENTER-PRESSURE-INFERENCE-EVAL`

Recommended prompt:

> Continue UnityRTSPrototype. Task: PPO-SANDBOX-R4-CENTER-PRESSURE-INFERENCE-EVAL. Evaluate `results/PPO_CenterPressureSmoke_001/Stage7B_RTS_Student.onnx` in sandbox-only inference mode against the balanced CenterPressure opponent. Do not integrate the model into HumanPlay, do not overwrite existing ONNX/checkpoints, keep protected hashes unchanged, and report inference runtime stability, episode outcomes, CenterPressure diagnostics, and comparison against the imitation baseline.
