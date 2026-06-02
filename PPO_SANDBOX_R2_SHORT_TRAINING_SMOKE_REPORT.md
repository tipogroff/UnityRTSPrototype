# PPO_SANDBOX_R2_SHORT_TRAINING_SMOKE_REPORT

- result: GO
- selected run_id: PPO_SandboxContinuationSmoke_002

## Run Configuration
- sandbox scene path: Assets/Scenes/PPO_TrainingSandbox_Player1AI_vs_ScriptedBot.unity
- config file used: config/stage7b_ppo_finetune_smoke.yaml
- initialize-from checkpoint/run: Stage7B_ImitationSmoke_010_PostKickConfirm
- behavior name: Stage7B_RTS_Student
- max_steps used: 2000
- steps collected: 2000
- trainer exit code: 0

## Trainer/Unity Status
- trainer startup status: PASS
- Unity connection result: PASS (connected to Unity environment, comm 1.5.0)
- checkpoint initialization result: PASS (initialized from results/Stage7B_ImitationSmoke_010_PostKickConfirm/Stage7B_RTS_Student/checkpoint.pt)

## Contract/Agent Validation
- observation size: 15552 (PASS)
- candidate action branch size: 128 (scene serialized BranchSizes 80000000) (PASS)
- attack target contract result: local 7x7 / 49 (PASS)
- scripted opponent status: enabled in sandbox and active during run (PASS)
- duplicate Agent check result: no duplicate bare Unity.MLAgents.Agent on student object (PASS)
- BehaviorParameters and DecisionRequester presence: present (PASS)

## Runtime Diagnostics
- padding warning count: 0
- runtime exception count: 0 (for selected successful run)
- console error count: 0
- console warnings observed: 2 non-blocking UnitVisualAnimator warnings (presentation-only)

## Training Progress Snapshot
- step summaries observed: 250, 500, 750, 1000, 1250, 1500, 1750, 2000
- reward summary observed: step 500 mean reward 1.930 (std 0.000)
- episode count visibility: no completed episode in periodic trainer summaries during short smoke
- accepted/rejected command counts (from scripted opponent report): accepted 1500, rejected 0
- scripted opponent activity (from report): bot_decision_executed_count 54, bot_actions_attempted_after 54

## Exported Artifacts (Selected Run Only)
- results/PPO_SandboxContinuationSmoke_002/configuration.yaml
- results/PPO_SandboxContinuationSmoke_002/Stage7B_RTS_Student.onnx
- results/PPO_SandboxContinuationSmoke_002/Stage7B_RTS_Student/checkpoint.pt
- results/PPO_SandboxContinuationSmoke_002/Stage7B_RTS_Student/events.out.tfevents.1780362570.grozov.29500.0
- results/PPO_SandboxContinuationSmoke_002/Stage7B_RTS_Student/Stage7B_RTS_Student-1975.onnx
- results/PPO_SandboxContinuationSmoke_002/Stage7B_RTS_Student/Stage7B_RTS_Student-1975.pt
- results/PPO_SandboxContinuationSmoke_002/Stage7B_RTS_Student/Stage7B_RTS_Student-2039.onnx
- results/PPO_SandboxContinuationSmoke_002/Stage7B_RTS_Student/Stage7B_RTS_Student-2039.pt

## Protection Checks
- protected scene hash check result: PASS
  - Assets/Scenes/MainMenu.unity unchanged
  - Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity unchanged
  - Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity unchanged
- model/checkpoint overwrite protection result: PASS
  - current demo ONNX unchanged
  - pre-existing checkpoints/ONNX artifacts unchanged (hash compare count changed = 0)
- runtime semantic protection result: PASS
  - ActionDecoder unchanged
  - ActionApplier unchanged
  - MatchManager unchanged
- Python training script protection result: PASS
  - no python/**/*.py changes detected
- sandbox isolation from HumanPlay/UI/manual input dependencies: PASS (none found in sandbox scene serialization)

## Notes On Run-ID Selection
- Requested run_id PPO_SandboxContinuationSmoke_001 was created during an initial failed startup attempt (Unity handshake timeout).
- To avoid overwrite and satisfy non-destructive constraints, this smoke used PPO_SandboxContinuationSmoke_002.

## Blockers
- none for the successful selected run

## Safety Decision
- resulting PPO-smoke model safe for later evaluation: YES
  - scope remained sandbox-only
  - no protected scene/model/script semantic mutation detected
  - no integration into HumanPlay demo performed in this task

## Exact Recommended Next Task Name
- PPO-SANDBOX-R3

## Exact Recommended Next Prompt
Continue UnityRTSPrototype.

New task:
PPO-SANDBOX-R3 — evaluate PPO_SandboxContinuationSmoke_002 artifacts in sandbox-only inference validation.

Use only:
- Assets/Scenes/PPO_TrainingSandbox_Player1AI_vs_ScriptedBot.unity
- results/PPO_SandboxContinuationSmoke_002/Stage7B_RTS_Student.onnx

Hard constraints:
- Do not modify MainMenu, HumanPlay_Demo_PlayerVsAI, or Week7 baseline scene.
- Do not replace current demo model.
- Do not modify ActionDecoder/ActionApplier/MatchManager semantics.
- No long training.

Validation goals:
- run short inference smoke with PPO model in sandbox
- verify no padding/observation mismatch/runtime exception
- collect scripted-opponent activity and command acceptance stats
- produce report + json for readiness decision