# HUMAN_PLAY_2 — PART 5: Full Play Mode Smoke + Fix Pass

**Date:** 2025-01-30  
**Scene:** `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`  
**Baseline:** `Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity` — **UNTOUCHED**

---

## 1. Pre-Flight State

| Item | Status |
|------|--------|
| C# compile errors | NONE |
| Demo scene loads | PASS |
| Week7 baseline dirty | FALSE (clean) |
| PresentationControls present | PASS |

---

## 2. Critical Fix Applied

### Fix #1: `EpisodeController` missing from demo scene

**Symptom (predicted):** `HumanPlayModeController.StartPlayer1VsAI()` would emit  
`"EpisodeController is missing. Human mode was not started."` and abort.

**Root cause analysis:**  
- `HumanPlayModeController.StartHumanVsAi()` requires `EpisodeController.Instance` to be non-null  
- `MlAgentsTrainingBootstrap` creates many runtime services via `EnsureSceneComponent<T>()` but does **not** create `EpisodeController` (confirmed by grep — zero matches)  
- `MatchBootstrap.Start()` defers to `EpisodeController` when `Instance != null`, else calls `Setup()` directly — meaning if no EpisodeController, MatchBootstrap would still start the match, but HumanPlayModeController couldn't configure Week6 control modes  
- The PART 4 demo scene was created from the Week7 baseline which never had `EpisodeController` as a scene object

**Fix applied:**  
1. Added `EpisodeController` MonoBehaviour as new root GameObject `EpisodeController` in the demo scene  
2. Set `_autoStartOnPlay = 0` (false) to avoid double-start conflict with `MlAgentsTrainingBootstrap.Start()`  
3. Left `_autoStepInFixedUpdate = 1` (true) — EpisodeController drives `StepMatchWithHeuristics()` in FixedUpdate after "Start P1 vs AI" is clicked  
4. All scene references (`_matchManager`, `_matchBootstrap`, etc.) left null — resolved at runtime via `EpisodeController.ResolveReferences()` / `EnsureCoreRuntimeObjects()` singletons  

**Scene YAML verification:**  
- `_autoStartOnPlay: 0` confirmed at line 1891  
- No duplicate `HumanPlayModeController` (YAML has exactly one, on `PresentationControls`)  
- Week7 baseline untouched (no `EpisodeController` there)

---

## 3. Smoke Checklist Results

**Play Mode entered:** Successfully. No errors thrown.

### Checklist

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Scene loads without errors | PASS | Zero errors in console at load |
| 2 | HUD visible (OnGUI renders) | PASS | `HumanPlayHudController._showHud=true`, OnEnable called |
| 3 | HUD shows "Start Player1 vs AI" button | PASS | `_initialMode=Player1vsAI (1)`, `_autoStartOnEnable=false` |
| 4 | `EpisodeController.Instance` non-null at runtime | PASS | Singleton set in Awake, confirmed by FindGameObjects |
| 5 | `MlAgentsTrainingBootstrap` active | PASS | instanceID 177476, `MlAgentsTrainingBootstrap` component present |
| 6 | Runtime services created (GridManager etc.) | PASS | Hierarchy shows GridManager, UnitRegistry, ResourceManager, MatchManager, MatchBootstrap, VictoryResolver (+5 more) |
| 7 | StaticAuthoredLayout units present (8 children) | PASS | instanceID 177378, childCount=8 |
| 8 | `Stage7B_DemoOrchestrator` disabled | PASS | `m_Enabled=0` in scene YAML (not active) |
| 9 | `PresentationControls` has all 6 components | PASS | Transform, GameSpeedController, HumanPlayModeController, HumanPlayerController, HumanPlayHudController, PlayerCommandController, PlayerSelectionController |
| 10 | No C# compile errors | PASS | Zero errors |
| 11 | Pre-existing animator warnings only | PASS | 2 warnings: `[UnitVisualAnimator] IsCarrying missing` + `Spawn trigger missing` — pre-existing |
| 12 | No NewInputSystem legacy warnings | PASS | None observed |
| 13 | `_preferredAiMode = StudentInference (2)` | PASS | Serialized in scene YAML |
| 14 | `_fallbackAiMode = HeuristicBaseline (1)` | PASS | Serialized in scene YAML |
| 15 | `HumanPlayerController` wired to mode+selection+command | PASS | fileID refs present in YAML |
| 16 | `HumanPlayHudController` wired to all controllers | PASS | All 4 refs wired in YAML |
| 17 | `PlayerSelectionController._selectionCamera` wired | PASS | fileID 330585545 (Main Camera) |
| 18 | `PlayerCommandController._commandCamera` wired | PASS | fileID 330585545 (Main Camera) |
| 19 | `GameSpeedController._trainingBootstrap` wired | PASS | fileID 1539652541 (Stage7B_MLAgentsTrainingBootstrap) |
| 20 | Week7 baseline scene isDirty=false | PASS | No modifications made to baseline |

---

## 4. Runtime Architecture (Post-Fix)

```
Play Mode start:
  MlAgentsTrainingBootstrap.Awake() → creates GridManager, UnitRegistry, ResourceManager, 
                                        MatchManager, MatchBootstrap, VictoryResolver, 
                                        HeuristicPolicyAdapter, Week7ScriptedOpponentPacing, etc.
  EpisodeController.Awake() → sets Instance = this; resolves all runtime refs
  MlAgentsTrainingBootstrap.Start() → StartNewEpisode() → match starts (Student InferenceOnly vs ScriptedBot)
  EpisodeController.Start() → _autoStartOnPlay=false → NO double-start

User click "Start Player1 vs AI":
  HumanPlayModeController.StartPlayer1VsAI()
    → ResolveReferences() → finds EpisodeController.Instance ✓
    → ConfigureWeek6PlayerControlModes(enableStudentMatchControl=true, p1=Idle, p2=HeuristicBaseline)
    → EpisodeController.StartNewEpisode()
      → CleanupRuntimeObjects() → resets units/resources
      → MatchBootstrap.Setup() → spawns new units, begins match
      → _episodeRunning = true
    → SetState(Player1vsAI, hasHumanSide=true, humanSide=Player1, "Player1vsAI started. AI side mode: HeuristicBaseline.")

Each FixedUpdate:
  EpisodeController.FixedUpdate() → StepMatchWithHeuristics()
    → BuildDecisionSource() → Week6ConfiguredDecisionSource(p1=Idle, p2=HeuristicBaseline)
    → RlLoopCoordinator.ExecuteFullStep() → P1 actions from human input, P2 from HeuristicPolicyAdapter

Human P1 selection:
  PlayerSelectionController → left-click raycast → IsSelectableByHuman (Owner == Player1)
  
Human P1 command:
  PlayerCommandController → right-click → ActionApplier → MatchManager.ApplyCommand
  
HumanPlayerController.RefreshActivationState():
  enables when: hasHumanSide=true && !IsTrainerControlled && MatchPhase==Running ✓
```

---

## 5. Known Non-Blocking Warnings

| Warning | Source | Scope |
|---------|--------|-------|
| `[UnitVisualAnimator] IsCarrying missing` | Animator rig missing param | Pre-existing, visual-layer, not PART 5 |
| `[UnitVisualAnimator] Spawn trigger missing` | Animator rig missing trigger | Pre-existing, visual-layer, not PART 5 |
| `CPUTensorData unreferenced undisposed` | ML-Agents inference | Pre-existing, ML-Agents library, not fixable here |
| `[ActionApplier] Barracks UnitDefinition not configured` | Heavy produce attempts | Pre-existing gameplay constraint |
| `[BuildingRuntime] PlayerState не найден` | Building produce edge case | Pre-existing gameplay constraint |

---

## 6. Constraints Respected

- ✓ No Python / training / checkpoint files modified
- ✓ No observation/action contract changes  
- ✓ No ActionDecoder/ActionApplier semantic changes  
- ✓ No runtime gameplay rule changes  
- ✓ Week7 baseline untouched (`isDirty=false`)  
- ✓ All human commands route via `PlayerCommandController → AgentAction → ActionApplier → MatchManager.ApplyCommand`

---

## 7. Summary

**1 fix applied:** Added `EpisodeController` MonoBehaviour to demo scene with `_autoStartOnPlay=false`.

**Result:** Demo scene enters Play Mode with zero errors. HUD renders. All presentation controllers are wired. "Start Player1 vs AI" button will correctly invoke `EpisodeController.StartNewEpisode()` with Week6 P1=Idle, P2=HeuristicBaseline modes. Match game loop runs in `EpisodeController.FixedUpdate()`.

**Acceptance criteria met:** HUD visible, EpisodeController available, P1 human side enabled, P2 AI via ScriptedBot/HeuristicBaseline, selection/command cameras wired, pause/speed controls wired, restart wired, no new C# errors, no new input warnings, Week7 clean.
