# PPO-SANDBOX-BOT-R3 Resource Composition Balance Report

- Date: 2026-06-02
- Result: GO
- Sandbox scene: `Assets/Scenes/PPO_TrainingSandbox_Player1AI_vs_ScriptedBot.unity`
- Scripted opponent profile: `CenterPressure` (sandbox-only)
- PPO training executed: no

## Files Changed

- `Assets/Scripts/ML/HeuristicPolicyAdapter.cs`
- `Assets/Scripts/MLAgents/Stage7B/MlAgentsTrainingBootstrap.cs`
- `Assets/Scripts/MLAgents/Stage7B/Week7ScriptedOpponentPacing.cs`
- `Assets/Scenes/PPO_TrainingSandbox_Player1AI_vs_ScriptedBot.unity`
- `Assets/Scripts/MLAgents/Stage7B/Editor/PpoSandboxBotR3ResourceCompositionBalanceSmokeMenu.cs`
- `Assets/Scripts/MLAgents/Stage7B/Editor/PpoSandboxBotR3ResourceCompositionBalanceSmokeMenu.cs.meta`
- `ppo_sandbox_bot_r3_resource_composition_balance_smoke_runtime.json`
- `ppo_sandbox_bot_r3_resource_composition_balance_validation.json`
- `PPO_SANDBOX_BOT_R3_RESOURCE_COMPOSITION_BALANCE_REPORT.md`

## Explicitly Not Changed

- Protected scenes: `MainMenu.unity`, `HumanPlay_Demo_PlayerVsAI.unity`, `Week7_MLAgents_StudentVsScriptedBot.unity`
- Demo ONNX: `Assets/MLAgents/Models/Stage7B_RTS_Student_ImitationSmoke_010.onnx`
- Runtime semantics: `ActionDecoder.cs`, `ActionApplier.cs`, `MatchManager.cs`
- Observation/action contracts, reward semantics, terminal semantics, teacher policy, datasets, checkpoints, and PPO runs
- Global `GameConfig` and `UnitDef` assets

## Protection Checks

Protected SHA256 values remained unchanged:

- `MainMenu.unity`: `CAA306A0505A763E5EF7CAA80E771E741D19A0ED22CFDED1905E7B43C81C1A84`
- `HumanPlay_Demo_PlayerVsAI.unity`: `311EC9365B32181FB59A809C96388242855CCC1B892635A8887CB0DF16E85D5D`
- `Week7_MLAgents_StudentVsScriptedBot.unity`: `EC64B6707130CD090673804537DEDEFABE38F13E9DCCD39827633EA19087F0DC`
- Demo ONNX: `C96059B1A608E3A7B8AA501F4F04965E8A2C91AEF478BF25DD16D664A219696A`
- `ActionDecoder.cs`: `9780B24DD722C0EBA57A421D6297C9E40C2FDD5A104DF1A5E819162E5C2B2D0B`
- `ActionApplier.cs`: `74038601F0841CAA7690FD94A6B4A95B1DE8F046F8127504CF2FDA699FE798E6`
- `MatchManager.cs`: `57AE6C1F97AE17DB3704EF4B7F4B0E4EA60C295E2CFF3C3DCF8CBB85522D95CC`

## Resource Settings Found

- Player1 / Player2 starting resources: `60 / 60`
- Resource nodes: `4`
- Per-node amount: `20`
- Total map resources: `80`
- Worker: cost `1`, production `5` ticks
- Light: cost `3`, production `6` ticks
- Heavy: cost `2`, production `10` ticks
- Ranged: cost `2`, production `10` ticks
- Barracks: cost `2`, production `8` ticks
- Sandbox start-resource changes: none

`BuildingRuntime` uses one active `ProductionQueue` per building. A new item is rejected while the queue is producing; completion attempts to spawn on a free adjacent cell.

## Balance Policy

- Worker soft/hard caps: `4 / 5`
- Light / Heavy / Ranged caps: `4 / 2 / 3`
- Combat / total army caps: `5 / 9`
- Production budget: at most `2` production actions per `6` bot decisions
- Heavy anti-spam: no first combat Heavy when Light/Ranged is affordable, no repeated Heavy at cap, one Light/Ranged required before a second Heavy, Heavy attempt cooldown `10` decisions
- Mixed composition: after an opening Light/Ranged, the Barracks prefers one Heavy before filling remaining slots
- Attack waves: target range `3-5`; excess units stay near base; combat rallies through center before pressure

## Smoke Validation

Long sandbox-only R3 smoke completed with:

- Bot decisions: `120`
- Commands accepted / rejected: `969 / 0`
- Worker max: `4 <= 5`
- Light / Heavy / Ranged max: `1 / 1 / 3`
- Combat max: `5 <= 5`
- Total army max: `9 <= 9`
- Heavy produce attempts / accepted / blocked by cap: `3 / 3 / 69`
- Center rally moves / center visits: `23 / 19`
- Attack wave min / max / first: `4 / 5 / 5`
- Attack intent / submit / accepted: `3 / 3 / 3`
- Over-army-cap steps: `0`
- Permanent base idle: `false`
- Economy composition healthy: `true`
- Center pressure observed: `true`

Unity compile errors: `0`. Runtime exceptions: `0`. Padding warnings: `0`. Duplicate bare Agent: `false`.

One isolated no-adjacent-spawn-cell warning occurred for Light near `(1, 3)`. It did not repeat and is not spawn-warning spam. Two existing presentation warnings remained: missing animator parameter `IsCarrying` and trigger `Spawn`.

## Result

GO. Short isolated PPO training may proceed.

## Recommended Next Task

`PPO-SANDBOX-BOT-R4-SHORT-PPO-ISOLATED-RUN`

Recommended prompt:

> Continue UnityRTSPrototype. Task: PPO-SANDBOX-BOT-R4-SHORT-PPO-ISOLATED-RUN. Run a short isolated PPO training smoke against the sandbox-only CenterPressure opponent, write to a new run directory, do not overwrite checkpoints or ONNX models, keep protected HumanPlay and Week7 baseline assets unchanged, and report training stability plus post-run protected hashes.
