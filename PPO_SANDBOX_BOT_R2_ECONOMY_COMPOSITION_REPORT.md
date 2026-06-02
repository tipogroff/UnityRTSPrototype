# PPO-SANDBOX-BOT-R2 Economy + Composition Report

- Date: 2026-06-02
- Result: PARTIAL
- Sandbox scene: Assets/Scenes/PPO_TrainingSandbox_Player1AI_vs_ScriptedBot.unity
- Scripted opponent profile: CenterPressure (sandbox-only)

## Scope

Objective for R2 was to tune scripted-opponent economy/composition behavior and add attack-phase diagnostics fidelity (intent/submit/accepted), while preserving runtime authority and protected semantics.

No PPO training run was executed.

## Code Changes Applied

- Assets/Scripts/ML/HeuristicPolicyAdapter.cs
  - Added CenterPressure economy/composition controls and counters:
    - worker soft/hard cap controls and cap-block telemetry,
    - barracks/combat production preference telemetry,
    - worker activity counters (idle/gather/build),
    - attack diagnostics split into intent/submit/accepted + first-step markers,
    - center attack subset counters.
  - Fixed local variable shadowing compile issue in center-pressure state sampling.
- Assets/Scripts/MLAgents/Stage7B/MlAgentsTrainingBootstrap.cs
  - Added serialized scripted-opponent tactic profile and applied it via adapter bootstrap hookup.
- Assets/Scripts/MLAgents/Stage7B/Week7ScriptedOpponentPacing.cs
  - Extended report payload with R2 center-pressure economy/composition and attack diagnostics fields.
- Assets/Scripts/MLAgents/Stage7B/Editor/PpoSandboxBotR2EconomyCompositionSmokeMenu.cs
  - Added R2 smoke menu harness and runtime artifact writer.
  - Added fallback artifact write on EditMode return for resilience.

## Protected Hash Verification

Compared against R1 baseline hashes; all unchanged:

- Assets/Scenes/MainMenu.unity: unchanged (CAA306A0505A763E5EF7CAA80E771E741D19A0ED22CFDED1905E7B43C81C1A84)
- Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity: unchanged (311EC9365B32181FB59A809C96388242855CCC1B892635A8887CB0DF16E85D5D)
- Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity: unchanged (EC64B6707130CD090673804537DEDEFABE38F13E9DCCD39827633EA19087F0DC)
- Assets/MLAgents/Models/Stage7B_RTS_Student_ImitationSmoke_010.onnx: unchanged (C96059B1A608E3A7B8AA501F4F04965E8A2C91AEF478BF25DD16D664A219696A)
- Assets/Scripts/ML/ActionDecoder.cs: unchanged (9780B24DD722C0EBA57A421D6297C9E40C2FDD5A104DF1A5E819162E5C2B2D0B)
- Assets/Scripts/ML/ActionApplier.cs: unchanged (74038601F0841CAA7690FD94A6B4A95B1DE8F046F8127504CF2FDA699FE798E6)
- Assets/Scripts/Gameplay/Match/MatchManager.cs: unchanged (57AE6C1F97AE17DB3704EF4B7F4B0E4EA60C295E2CFF3C3DCF8CBB85522D95CC)

## Compile / Runtime Validation

- File-level compile diagnostics on modified scripts: 0 errors.
- Unity console errors: 0.
- Unity console warnings observed (non-fatal):
  - UnitVisualAnimator missing Animator parameter `IsCarrying`.
  - UnitVisualAnimator missing Animator trigger `Spawn`.
  - BuildingRuntime warning: no adjacent free spawn cell for Ranged near (0, 1).

## R2 Runtime Artifacts

- Primary smoke artifact:
  - ppo_sandbox_bot_r2_economy_composition_smoke_runtime.json
- Adapter metrics snapshot:
  - python/stage7b_teacher_replay/stage7b_center_pressure_runtime_metrics.json

Snapshot highlights from stage7b_center_pressure_runtime_metrics.json:

- center_pressure_enabled: true
- bot_decisions_executed: 3
- bot_actions_attempted: 10
- bot_commands_accepted: 10
- bot_commands_rejected: 0
- worker_soft_cap / hard_cap: 4 / 5
- worker_produce_attempts: 3
- worker_produce_blocked_by_cap: 0
- barracks_build_attempts / accepted: 1 / 1
- combat_unit_produce_attempts / accepted: 1 / 1
- center_rally_moves: 0
- center_area_visits: 0
- attack_intent_count / submit / accepted: 0 / 0 / 0
- center_pressure_observed: false
- economy_composition_healthy: true

## Assessment vs R2 Intent

Validated:

- Economy/composition tuning code is present and wired into sandbox profile.
- Worker-cap, barracks/combat, and attack-stage telemetry are now explicit and separated.
- Protected files and runtime contract surfaces remained unchanged.

Not yet validated in smoke behavior evidence:

- Center-pressure movement dominance (center moves/visits) did not appear in captured short run.
- Attack progression (intent/submit/accepted) remained zero in captured short run.
- The smoke run completed with very low decision count, limiting behavioral confidence.

## Result

PARTIAL.

R2 implementation is in place and safe, but runtime evidence is insufficient to claim full economy/composition and center-attack convergence in the sampled run.

## Recommended Next Task

PPO-SANDBOX-BOT-R2R

Recommended prompt:

"Continue UnityRTSPrototype. Task: PPO-SANDBOX-BOT-R2R — rerun and stabilize sandbox-only R2 validation to obtain >=120 bot decisions and verify center movement/attack progression metrics (center_rally_moves > 0, center_area_visits > 0, and attack_intent_count or attack_submit_count > 0) while keeping protected hashes unchanged and runtime authority semantics intact."
