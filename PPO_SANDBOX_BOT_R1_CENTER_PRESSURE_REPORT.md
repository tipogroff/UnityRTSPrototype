# PPO-SANDBOX-BOT-R1 Center Pressure Report

- Date: 2026-06-02
- Result: PARTIAL
- Sandbox scene: Assets/Scenes/PPO_TrainingSandbox_Player1AI_vs_ScriptedBot.unity
- Scripted opponent profile enabled: CenterPressure (sandbox-only)

## Scope and Constraints

Implemented opponent-behavior correction for sandbox scripted bot only. No PPO training run was executed.

Protected constraints were respected:
- MainMenu scene not modified.
- HumanPlay demo scene not modified.
- Week7 baseline scene not modified.
- Demo ONNX model not modified.
- ActionDecoder semantics not modified.
- ActionApplier semantics not modified.
- MatchManager semantics not modified.
- Observation/action contract semantics not modified.
- Reward/terminal semantics not modified.

## Files Changed

Intentional code/scene changes:
- Assets/Scripts/ML/HeuristicPolicyAdapter.cs
- Assets/Scripts/MLAgents/Stage7B/MlAgentsTrainingBootstrap.cs
- Assets/Scripts/MLAgents/Stage7B/Week7ScriptedOpponentPacing.cs
- Assets/Scripts/MLAgents/Stage7B/Editor/PpoSandboxBotR1CenterPressureSmokeMenu.cs
- Assets/Scenes/PPO_TrainingSandbox_Player1AI_vs_ScriptedBot.unity

Generated runtime artifacts during smoke:
- ppo_sandbox_bot_r1_center_pressure_smoke_runtime.json
- python/stage7b_teacher_replay/stage7b_center_pressure_runtime_metrics.json

## Files Explicitly Not Changed (Protected)

SHA256 pre/post matched:
- Assets/Scenes/MainMenu.unity: CAA306A0505A763E5EF7CAA80E771E741D19A0ED22CFDED1905E7B43C81C1A84
- Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity: 311EC9365B32181FB59A809C96388242855CCC1B892635A8887CB0DF16E85D5D
- Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity: EC64B6707130CD090673804537DEDEFABE38F13E9DCCD39827633EA19087F0DC
- Assets/MLAgents/Models/Stage7B_RTS_Student_ImitationSmoke_010.onnx: C96059B1A608E3A7B8AA501F4F04965E8A2C91AEF478BF25DD16D664A219696A
- Assets/Scripts/ML/ActionDecoder.cs: 9780B24DD722C0EBA57A421D6297C9E40C2FDD5A104DF1A5E819162E5C2B2D0B
- Assets/Scripts/ML/ActionApplier.cs: 74038601F0841CAA7690FD94A6B4A95B1DE8F046F8127504CF2FDA699FE798E6
- Assets/Scripts/Gameplay/Match/MatchManager.cs: 57AE6C1F97AE17DB3704EF4B7F4B0E4EA60C295E2CFF3C3DCF8CBB85522D95CC

## CenterPressure Design Summary

Implemented a sandbox-selectable scripted-opponent tactic profile:
- Profile name: CenterPressure.
- Preserves legacy behavior by default (`Legacy`).
- Enabled only in sandbox scene via `MlAgentsTrainingBootstrap._scriptedOpponentTacticProfile = CenterPressure`.

Behavior implemented:
1. Opening phase:
- Economy/production kept active.
- Combat attacks blocked in early decisions (opening gate).

2. Center rally phase:
- Player2 combat units are rallied toward center rally cells around map center (24x24 center around (12,12)).
- Move intent is still emitted through normal policy path and ActionApplier/MatchManager.

3. Center attack phase:
- Attack unlock after center presence or timeout gate.
- Attack still validated through existing masks and ActionApplier validation path.

4. Re-pressure phase:
- If combat clusters near own base for too long, re-rally to center is re-issued.
- Anti-oscillation and move-memory logic preserved.

## Bot Movement Diagnostics (Short Smoke)

Source: python/stage7b_teacher_replay/stage7b_center_pressure_runtime_metrics.json

- bot_decisions_executed: 80
- bot_actions_attempted: 2473
- bot_commands_accepted: 2473
- bot_commands_rejected: 0
- center_rally_moves: 319
- center_area_visits: 60
- edge_lane_moves: 162
- base_idle_steps: 3
- first_center_move_step: 20
- first_attack_step: -1
- avg_combat_distance_to_center: 7.911
- permanent_base_idle: false
- center_pressure_observed: false

Interpretation:
- Center routing improved: center rally moves (319) exceeded edge-lane moves (162).
- Base-idle behavior improved (only 3 idle steps observed in this smoke window).
- Accepted command count is high and rejection is low (0).

## Bot Attack Diagnostics

- Accepted attack from center was not observed in this short smoke window (`first_attack_step = -1`).
- This blocks full GO for the requested center-attack phase requirement in the sampled run.

## Unity Compile and Smoke Validation

- Unity compile check: 0 errors (script diagnostics and Unity console error filter).
- Console warnings observed (non-fatal):
  - UnitVisualAnimator missing Animator params/triggers.
  - BuildingRuntime no free adjacent spawn cell warning.
- Runtime exceptions: 0
- Padding warnings: 0
- Duplicate bare Unity.MLAgents.Agent: not found
- Sandbox scene loaded: yes
- Student agent initialized: yes
- Scripted opponent active: yes

## Runtime Semantic Protection Result

Preserved runtime authority path:
- AgentAction -> ActionApplier -> MatchManager

No changes made to:
- ActionDecoder semantics
- ActionApplier semantics
- MatchManager runtime semantics
- observation/action contracts
- reward/terminal semantics

## Blockers

- Short smoke did not produce a validated attack execution in center-pressure phase (`first_attack_step = -1`), so center-pressure observation remains incomplete for full acceptance.

## Proceed Recommendation

- PPO-SANDBOX-R3 short training/evaluation can proceed: NO (recommended to complete one follow-up opponent tuning pass first).

Exact recommended next task name:
- PPO-SANDBOX-BOT-R2

Exact recommended next prompt:
- "Continue UnityRTSPrototype. New task: PPO-SANDBOX-BOT-R2 — finalize CenterPressure attack-phase convergence in sandbox scripted opponent. Keep all previous hard constraints unchanged. Require short sandbox-only smoke with first_attack_step >= 0, center_pressure_observed = true, center_rally_moves > edge_lane_moves, accepted commands > 0, low rejections, and protected hash checks unchanged. Output PPO_SANDBOX_BOT_R2_CENTER_PRESSURE_ATTACK_REPORT.md and ppo_sandbox_bot_r2_center_pressure_attack_validation.json."
