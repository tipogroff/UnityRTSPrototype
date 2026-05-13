# HumanPlay-2 PART 6R Player2 Bot Source Fix Report

## Summary
- Status: partial_pass
- Previous PART 6 invalidated: true
- Why previous PART 6 was insufficient: it verified EpisodeController control-mode configuration but did not validate the separate Stage7 bootstrap scripted-opponent path that was still active in the demo scene at runtime.
- Current outcome: the actual Player2 auto-command source was identified and disabled in the demo scene, and runtime diagnostics showed Player2 automatic command count staying at 0 with p2 decision mode remaining Idle. Full end-to-end certification is still pending because the editor automation did not conclusively capture a Player2 human move command through PlayerCommandController in Unity.

## Actual Player2 Auto Command Source
- Before: Stage7B_MLAgentsTrainingBootstrap._stepScriptedOpponent=true -> StudentMlAgent executes ScriptedOpponentAdapter for Player2.
- After: Disabled in HumanPlay_Demo_PlayerVsAI: Stage7B_MLAgentsTrainingBootstrap._stepScriptedOpponent=false; Player2 automation source absent during validation windows.

## Files Changed
- Assets/Scripts/Presentation/HumanPlayCommandSourceDiagnostics.cs
- Assets/Scripts/Gameplay/Match/EpisodeController.cs
- Assets/Scripts/ML/Week6ConfiguredDecisionSource.cs
- Assets/Scripts/ML/Week6StudentPolicyAdapter.cs
- Assets/Scripts/MLAgents/Stage7B/StudentMlAgent.cs
- Assets/Scripts/Presentation/PlayerCommandController.cs
- Assets/Scripts/Presentation/HumanPlayModeController.cs
- Assets/Scripts/Presentation/HumanPlayHudController.cs
- Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity

## Scene Component Change
- GameObject path: Stage7B_MLAgentsTrainingBootstrap
- Component: RTS.MLAgents.Stage7B.MlAgentsTrainingBootstrap
- Serialized change: _stepScriptedOpponent 1 -> 0 in Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity
- Stage7B_DemoOrchestrator remained present but disabled in the demo scene during validation.

## Runtime Evidence
- P1 decision mode observed during validation: HeuristicBaseline
- P2 decision mode observed during validation: Idle
- Human side observed during validation: Player2
- Player2 automatic commands without input over 10s: 0
- Player2 selection succeeded: true
- Player1 selection was blocked for the human side: true
- Duplicate EpisodeController count: 1
- Restart preserved roles: true
- Demo orchestrator disabled at runtime: true

## Current Limits
- Player2 human command routing through PlayerCommandController was instrumented, but the Unity editor automation did not conclusively capture a successful Player2 move submission in the final artifact pass.
- Player1 AI continuation was not stable enough across the automated reruns to certify FULL PASS from automation alone.

## Required Confirmations
- Player2 automatic command count is 0 when no human input is provided: true
- Player2 human commands route via PlayerCommandController: not yet conclusively certified by automation
- Player1 AI continues acting: not yet conclusively certified by automation
- Week7 baseline untouched: true
- Constraints respected: true