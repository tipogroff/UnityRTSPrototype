# PPO_TRAINING_SANDBOX_R1_REPORT

- result: GO
- date: 2026-06-02

## Sandbox
- sandbox scene path: Assets/Scenes/PPO_TrainingSandbox_Player1AI_vs_ScriptedBot.unity
- source scene path: Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity
- creation method: direct file copy of source scene into isolated sandbox scene

## Freeze/Protected State Confirmation
From freeze docs inspected:
- main menu scene path: Assets/Scenes/MainMenu.unity
- current humanplay demo scene path: Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity
- old baseline ml-agents scene path: Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity
- current demo onnx path: Assets/MLAgents/Models/Stage7B_RTS_Student_ImitationSmoke_010.onnx
- current behavior name: Stage7B_RTS_Student
- current demo runtime mode: InferenceOnly
- demo sides: AI Player1 vs Human Player2

## Files Changed
Observed in this task run (new or runtime-generated while validating):
- Assets/Scenes/PPO_TrainingSandbox_Player1AI_vs_ScriptedBot.unity (new)
- Assets/Scenes/PPO_TrainingSandbox_Player1AI_vs_ScriptedBot.unity.meta (new, Unity import)
- Assets/ML-Agents/Timers/PPO_TrainingSandbox_Player1AI_vs_ScriptedBot_timers.json (new, runtime timer artifact)
- Assets/ML-Agents/Timers/PPO_TrainingSandbox_Player1AI_vs_ScriptedBot_timers.json.meta (new)
- python/stage7b_teacher_replay/stage7b_week7_scripted_bot_throttle_report.json (updated by sandbox smoke runtime)

## Files Explicitly Not Changed
Hash-verified unchanged:
- Assets/Scenes/MainMenu.unity
- Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity
- Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity
- Assets/Scripts/ML/ActionDecoder.cs
- Assets/Scripts/ML/ActionApplier.cs
- Assets/Scripts/Gameplay/Match/MatchManager.cs
- Assets/Scripts/MLAgents/Stage7B/MlAgentsTrainingBootstrap.cs
- Assets/Scripts/MLAgents/Stage7B/StudentMlAgent.cs
- Assets/MLAgents/Models/Stage7B_RTS_Student_ImitationSmoke_010.onnx

Git status checks:
- no python training .py scripts changed
- no checkpoint files changed
- no ONNX model assets changed

## Protected Scene Check Result
PASS
- MainMenu unchanged
- HumanPlay_Demo_PlayerVsAI unchanged
- Week7_MLAgents_StudentVsScriptedBot unchanged

## Model/Checkpoint Protection Result
PASS
- current demo model asset unchanged
- no checkpoint modification detected
- no overwrite of existing demo model

## Runtime Semantic Protection Result
PASS
- ActionDecoder unchanged
- ActionApplier unchanged
- MatchManager unchanged
- observation/action contracts unchanged
- no reward/terminal semantic edits
- no action validation bypass introduced

## Sandbox Configuration Validation
PASS
- student side/perspective: Player1 (`_playerPerspective: 1`)
- behavior name: Stage7B_RTS_Student
- behavior runtime mode in sandbox: TrainerControlled effective (`_stage7BRuntimeMode: 2`, `_forceTrainerControlledMode: 1`, `BehaviorParameters.m_BehaviorType: 0(Default)`)
- scripted opponent stepping in sandbox: enabled (`_stepScriptedOpponent: 1`)
- humanplay controller dependencies in sandbox scene YAML: not found
- no human manual input controller dependencies in sandbox scene YAML: not found

## Agent Component Validation
PASS
- exactly one RTS.MLAgents.Stage7B.StudentMlAgent component serialized
- no duplicate bare Unity.MLAgents.Agent component found
- DecisionRequester present
- BehaviorParameters present and valid

## Contract Validation
PASS
- observation size: 15552 (`VectorObservationSize: 15552`)
- candidate action branch size: 128 (scene YAML `BranchSizes: 80000000`, Unity serialized int-array format for 128)
- attack target contract: local 7x7 / 49 unchanged (ActionContract constants unchanged)

## Horizon/Max Step Values Found
- script default (`MlAgentsTrainingBootstrap`): `_stage7BMatchMaxSteps = 6000`
- sandbox scene serialized value: `_stage7BMatchMaxSteps: 6000`
- student agent serialized MaxStep in scene: `MaxStep: 0` (agent lifetime controlled by match/trainer flow)
- note: no silent reduction to 1500/2000 detected in stage match horizon

## Smoke Validation (Short, No Long Training)
PASS (short runtime smoke only)
- Unity compile/runtime error check: no console errors
- scene load: success (sandbox scene loaded)
- agent initializes: yes (Student agent active; student decision attempts recorded)
- no duplicate agent component detected
- observation/action spec present and valid in scene
- scripted bot acts: yes (runtime report shows bot decisions/accepted commands)
- no padding warnings found in captured smoke logs
- no runtime exceptions found in captured smoke logs

Smoke note (non-blocking warnings observed):
- UnitVisualAnimator missing parameter/trigger warnings
- inference engine CPUTensorData disposal warnings
- these did not block sandbox startup/decision loop and were not introduced by code edits in this task

## Blockers
- none blocking for sandbox preparation

## PPO Continuation Safety
- short PPO continuation in this sandbox: SAFE
- long training: NOT run in this task (per constraint)

## Exact Recommended Next Task Name
PPO-SANDBOX-R2

## Exact Recommended Next Prompt
Continue UnityRTSPrototype.

New task:
PPO-SANDBOX-R2 — run a short PPO continuation smoke on the isolated sandbox scene only.

Use only:
- Assets/Scenes/PPO_TrainingSandbox_Player1AI_vs_ScriptedBot.unity

Hard constraints:
- Do not modify MainMenu/HumanPlay_Demo/Week7 baseline scenes.
- Do not modify ActionDecoder/ActionApplier/MatchManager semantics.
- Do not overwrite existing models or prior runs.
- Use a new run_id: Stage7B_PPOFineTuneSmoke_003.
- Keep behavior name Stage7B_RTS_Student.
- Keep observation 15552 and attack target 7x7/49 contract.
- Keep candidate branch 128.
- Run short smoke only (no long training).

Command/config to prepare and execute (short smoke):
- Preferred command:
  mlagents-learn config/stage7b_ppo_finetune_smoke.yaml --run-id Stage7B_PPOFineTuneSmoke_003 --initialize-from Stage7B_ImitationSmoke_010_PostKickConfirm --force
- Ensure sandbox scene runtime is TrainerControlled and scripted opponent stepping remains enabled.
- Stop after short smoke validation and report results.
