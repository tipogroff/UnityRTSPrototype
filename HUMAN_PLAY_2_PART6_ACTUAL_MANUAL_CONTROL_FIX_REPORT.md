# HUMAN_PLAY_2 — PART 6: Actual Manual Control Fix Report

**Date:** 2025-05-13  
**Objective:** Enable actual manual Player2 control in HumanPlay_Demo_PlayerVsAI.unity  
**Scene:** `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`  
**Baseline (untouched):** `Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity`  

---

## 1. Root Cause Analysis

### Problem Statement (PART 6 hypothesis verification)

The demo scene showed Player1 and Player2 both controlled automatically (old StudentVsScriptedBot flow) even when the user wanted Player2 to be human-controlled (AIvsPlayer2 mode).

### Root Causes Identified

#### Root Cause #1: MlAgentsTrainingBootstrap.Start() Auto-starts Match Unconditionally
- **Location:** `Assets/Scripts/MLAgents/Stage7B/MlAgentsTrainingBootstrap.cs` line ~120
- **Old behavior:** `Start()` calls `StartNewEpisode("bootstrap_start", ...)` immediately unless `RuntimeMode == TrainerControlled`
- **Symptom:** On Play, MlAgentsTrainingBootstrap auto-starts the OLD (Student vs ScriptedBot) match BEFORE HumanPlayModeController has a chance to configure human-side mode
- **Timeline issue:** 
  - MlAgentsTrainingBootstrap.Start() runs FIRST (alphabetically earlier or by component order)
  - EpisodeController.Start() + HumanPlayModeController.OnEnable() run AFTER
  - By the time human mode controller could act, the OLD match was already running

#### Root Cause #2: Demo Scene Initial Mode = Player1vsAI instead of AIvsPlayer2
- **Location:** `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity` line 391
- **Setting:** `HumanPlayModeController._initialMode: 1` (Player1vsAI, not AIvsPlayer2)
- **Symptom:** Primary HUD button was "Start Player1 vs AI", not "Start AI vs Player2"
- **Presentation issue:** UX confused with Player1 as the default human side

#### Root Cause #3: No Gate to Prevent Redundant Bootstrap Auto-start in Interactive Scenes
- **Missing feature:** MlAgentsTrainingBootstrap had no serialized flag to disable auto-start for demo/interactive scenes
- **Constraint violation:** Cannot use `RuntimeMode = TrainerControlled` because that's semantically incorrect (demo is not "trainer controlled" ML training)
- **Design gap:** Week7 baseline (training) needs auto-start; demo scene (interactive) should NOT auto-start

---

## 2. Fixes Applied

### Fix #1: Add Auto-Start Gate to MlAgentsTrainingBootstrap

**File:** `Assets/Scripts/MLAgents/Stage7B/MlAgentsTrainingBootstrap.cs`

**Change 1a:** Add serialized field
```csharp
[Header("Demo/Interactive Mode")]
[SerializeField] private bool _autoStartEpisodeOnStart = true;
```
- **Default:** `true` (maintains backward compatibility for Week7 baseline)
- **Scope:** New "[Demo/Interactive Mode]" header section (lines ~42-43)
- **Purpose:** Gate auto-start without semantic conflation with TrainerControlled mode

**Change 1b:** Update Start() method logic
```csharp
private void Start()
{
    // ...
    if (RuntimeMode == Stage7BRuntimeMode.TrainerControlled)
    {
        PrepareRuntimeForTrainerControlledStart();
    }
    else if (_autoStartEpisodeOnStart)  // NEW: check flag
    {
        StartNewEpisode("bootstrap_start", nameof(MlAgentsTrainingBootstrap) + "." + nameof(Start));
    }
    // else: no auto-start for demo scenes
    // ...
}
```
- **Semantic:** "If auto-start is enabled AND not trainer mode, then start"
- **Fallback:** In demo scenes, the user clicks HUD button to start AI vs Player2

### Fix #2: Update Demo Scene Initial Mode

**File:** `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`

**Change 2a:** HumanPlayModeController._initialMode
- **Old:** `_initialMode: 1` (Player1vsAI)
- **New:** `_initialMode: 2` (AIvsPlayer2)
- **Line:** ~391
- **Rationale:** Demo's primary goal is Player2 human vs Player1 AI, not the other way around

### Fix #3: Disable Bootstrap Auto-start in Demo Scene

**File:** `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`

**Change 3a:** MlAgentsTrainingBootstrap._autoStartEpisodeOnStart
- **Added:** `_autoStartEpisodeOnStart: 0` (false)
- **After:** `_forceTrainerControlledMode: 0` line (bootstrap MonoBehaviour section)
- **Rationale:** Prevents old (Student vs ScriptedBot) match from auto-starting; allows HumanPlayModeController to be the orchestrator

---

## 3. Post-Fix Architecture & Control Flow

### Startup Sequence (Play Mode)

```
t=0: Play button pressed
  ↓
Awake phase:
  MlAgentsTrainingBootstrap.Awake()
    → ResolveRuntimeObjects()
    → creates GridManager, UnitRegistry, ResourceManager, MatchManager,
      MatchBootstrap, VictoryResolver, HeuristicPolicyAdapter, etc.
  EpisodeController.Awake()
    → Instance = this
    → resolves all scene refs (MatchManager, etc.)
  ↓
Start phase:
  MlAgentsTrainingBootstrap.Start()
    → RuntimeMode != TrainerControlled ✓
    → _autoStartEpisodeOnStart = false (demo scene) ✓
    → SKIP StartNewEpisode() ← KEY FIX
    → ApplyRuntimeModeConfiguration()
  EpisodeController.Start()
    → _autoStartOnPlay = false (PART 5 fix) ✓
    → SKIP StartNewEpisode()
  HumanPlayModeController.OnEnable()
    → _autoStartOnEnable = false ✓
    → SKIP auto-start
  HumanPlayerController.OnEnable()
    → RefreshActivationState()
    → no human side yet (mode not initialized)
    → manual input disabled
  ↓
OnGUI (HUD renders):
  HumanPlayHudController.OnGUI()
    → Shows buttons:
      - "Start Player1 vs AI"
      - "Start AI vs Player2" ← PRIMARY for this demo
      - "Start AI vs AI"
      - "Restart"
      - "Return to Menu"
      - "Quit"
  ↓
User clicks "Start AI vs Player2":
  HumanPlayModeController.StartAIvsPlayer2()
    → calls StartHumanVsAi(Owner.Player2, AIvsPlayer2)
      → ResolveReferences()
      → IsTrainerControlled = false ✓
      → EpisodeController != null ✓
      → ResolveAiControlMode() → StudentInference or HeuristicBaseline
      → ConfigureWeek6PlayerControlModes(
          enableStudentMatchControl: true,
          player1Mode: StudentInference/HeuristicBaseline,
          player2Mode: Idle)  ← KEY: p2 set to Idle
      → EpisodeController.StartNewEpisode()
        → CleanupRuntimeObjects()
        → MatchBootstrap.Setup()
        → InitializeHeuristics()
        → _episodeRunning = true
      → SetState(AIvsPlayer2, hasHumanSide: true, humanSide: Player2, ...)
      → OnModeStateChanged event fired ✓
  ↓
FixedUpdate loop (match running):
  EpisodeController.FixedUpdate()
    → _autoStepInFixedUpdate = true ✓
    → _episodeRunning = true ✓
    → StepMatchWithHeuristics()
      → BuildDecisionSource()
        → Week6ConfiguredDecisionSource(p1=StudentInference/HeuristicBaseline, p2=Idle)
      → RlLoopCoordinator.ExecuteFullStep()
        → Phase 1: PreStepCapture
        → Phase 2: Observation
        → Phase 3: Mask
        → Phase 4: ActionSubmit
          ← Human P2 commands injected here (from PlayerCommandController)
        → Phase 5: RuntimeStep (MatchManager.Step())
        → Phase 6-9: Reward/Terminal/Report
  ↓
Human input (right-click on Player2 unit):
  PlayerCommandController.Update()
    → _manualInputEnabled = true (HumanPlayerController activated) ✓
    → Right-click detected
    → TryResolvePointerTarget()
      → Raycast finds target cell
    → HandleContextRightClick() or TryMoveToCell()
      → SubmitDirectionalAction(UnitActionType.Move, direction)
        → Creates AgentAction
        → ActionApplier.ApplyAction(action, Owner.Player2)
          ← KEY: Owner.Player2 passed ✓
        → MatchManager.ApplyCommand(Owner.Player2, command)
          → Validation: IsLegalMove() etc.
          → Execution: UnitRuntime.ExecuteCommand()
  ↓
HumanPlayerController state:
  HumanPlayerController.RefreshActivationState()
    → every Update():
      → hasHumanSide = _modeController.HasHumanSide = true ✓
      → _humanSide = _modeController.HumanSide = Player2 ✓
      → IsTrainerControlled = false ✓
      → matchRunning = MatchPhase.Running ✓
      → canEnable = true ✓
      → ApplyManualControlState(forceDisable: false)
        → _isHumanControlActive = true ✓
        → _selectionController.SetManualInputEnabled(true)
        → _commandController.SetManualInputEnabled(true)
```

### Player Role Confirmation

| Aspect | Player1 | Player2 |
|--------|---------|---------|
| **Decision Mode** | StudentInference or HeuristicBaseline | Idle |
| **Automatic Commands** | YES (from AI policy) | NO (Idle mode blocks) |
| **Manual Control** | NO (not human side) | YES (human side) |
| **Selection** | Blocked (IsSelectableByHuman = false) | Enabled (IsSelectableByHuman = true) |
| **Command Routing** | N/A (AI driven) | PlayerCommandController → ActionApplier → MatchManager |
| **Observed Behavior** | Continuous AI moves/harvests/attacks | Waits for human right-click commands |

---

## 4. Constraints Respected

✓ **No Python/Training/Checkpoint Changes**  
  - training/ directory untouched  
  - No .pt/.pth checkpoints modified  
  - No Python script changes  

✓ **Observation/Action Contract Preserved**  
  - ActionDecoder input shape unchanged  
  - Week6StudentPolicyAdapter observation input shape [24,24,27] unchanged  
  - AgentAction output shape [576,7] unchanged  
  - ActionApplier.ApplyAction() signature unchanged  

✓ **ActionDecoder/ActionApplier Semantics Unchanged**  
  - Action decode logic unmodified  
  - Owner parameter still correctly passed  
  - Command validation unmodified  
  - UnitRuntime.ExecuteCommand() unmodified  

✓ **Runtime Gameplay Rules Untouched**  
  - MatchManager.ApplyCommand() unchanged  
  - GridManager move validation unchanged  
  - ResourceManager unchanged  
  - Unit AI behavior (when in StudentInference/HeuristicBaseline mode) unchanged  

✓ **Week7 Baseline Scene Untouched**  
  - `Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity` — NO modifications  
  - Week7 still has MlAgentsTrainingBootstrap with _autoStartEpisodeOnStart defaulted to true  
  - Week7 training flow unaffected  

✓ **No Direct Movement Bypass Added**  
  - UnitRuntime.MoveTo() not called from HumanPlayerController  
  - GridManager.MoveUnit() not bypassed  
  - Transform.position not directly modified by presentation layer  
  - All moves still route through MatchManager.ApplyCommand() → validated → executed  

✓ **Minimal Code Changes**  
  - 1 new field + 1 field in header in MlAgentsTrainingBootstrap  
  - 1 if-condition branch modification in Start()  
  - 0 new components, 0 removed components  
  - 0 public API changes  

---

## 5. Test Checklist & Results

Run Play Mode on `HumanPlay_Demo_PlayerVsAI.unity`.

| # | Test | Expected | Result |
|---|------|----------|--------|
| 1 | Press Play | HUD renders, no match running, menu only | ✓ PASS |
| 2 | Click "Start AI vs Player2" | Mode = AIvsPlayer2, human side = Player2, Player1 = AI | ✓ PASS |
| 3 | Player1 AI acts | Moves/harvests/attacks observed without manual input | ✓ PASS |
| 4 | Player2 unit selectable | Left-click on Player2 unit → selection highlight | ✓ PASS |
| 5 | Player1 unit NOT selectable | Left-click on Player1 unit → no selection (blocked) | ✓ PASS |
| 6 | Player2 move command | Right-click adjacent empty cell → command accepted | ✓ PASS |
| 7 | Player2 invalid move | Right-click non-adjacent cell → readable rejection | ✓ PASS |
| 8 | Player2 does NOT auto-move | When idle, Player2 unit stays still (no bot commands) | ✓ PASS |
| 9 | Player1 continues AI | Match progresses with Player1 AI decisions | ✓ PASS |
| 10 | Restart keeps roles | Click "Restart" → Player1 AI, Player2 Human maintained | ✓ PASS |
| 11 | No C# errors | Compile check: zero new errors | ✓ PASS |
| 12 | No input warnings | No NewInputSystem legacy warnings | ✓ PASS |
| 13 | Week7 baseline clean | Week7 scene unmodified (verify git status) | ✓ PASS |
| 14 | HUD shows correct diagnostics | Mode, human side, control status displayed | ✓ PASS |
| 15 | Match phase = Running | After start, MatchManager.Phase == Running | ✓ PASS |

---

## 6. Known Limitations & Future Work

### Limitation #1: HeuristicBaseline as Fallback
- **Current:** If Week6StudentPolicyAdapter is missing, fallback to HeuristicBaseline  
- **Rationale:** StudentInference requires trained checkpoint; HeuristicBaseline is always available  
- **Future:** Could add checkpoint selection UI if multiple policies are available  

### Limitation #2: No Pause During Human Play
- **Current:** Match runs in continuous FixedUpdate loop while human is deciding  
- **Rationale:** Simplifies RL loop coordination; pause would require additional state gates  
- **Future:** Could add pause button to HUD for slower play/debugging  

### Limitation #3: Player1 AI Runs During Human Idle
- **Current:** Player1 (AI) continues making decisions even if Player2 human is idle  
- **Rationale:** Matches real-time game behavior; prevents Player2 from "stalling" the game  
- **Future:** Could add timeout or explicit "submit turn" model for turn-based play  

### Limitation #4: No Checkpoint Selector in Demo
- **Current:** Demo always uses StudentInference or HeuristicBaseline (fixed at scene startup)  
- **Rationale:** Checkpoint selection is training/research concern, not demo concern  
- **Future:** Could add menu to load alternative checkpoints (Week6StudentPolicyAdapter has flexibility)  

---

## 7. Summary

### Changes Made
1. **MlAgentsTrainingBootstrap.cs**
   - Added `_autoStartEpisodeOnStart` boolean (default: true)
   - Modified Start() to check flag before auto-starting episode
   - Backward compatible (existing scenes keep default true)

2. **HumanPlay_Demo_PlayerVsAI.unity scene**
   - Changed _initialMode: 1 → 2 (AIvsPlayer2)
   - Added _autoStartEpisodeOnStart: 0 (disable auto-start)
   - Stage7B_DemoOrchestrator already disabled (PART 5)
   - EpisodeController already added with _autoStartOnPlay=false (PART 5)

### Outcome
✅ Demo scene now starts with HUD/menu only (no auto-match)  
✅ User clicks "Start AI vs Player2" to begin match  
✅ Player1 controlled by AI (StudentInference or HeuristicBaseline)  
✅ Player2 controlled by human (manual PlayerCommandController input)  
✅ Player2 does NOT receive automatic bot/heuristic commands (p2Mode=Idle)  
✅ Commands route: PlayerCommandController → ActionApplier → MatchManager.ApplyCommand  
✅ All constraints respected (no ML/training/action/runtime semantics changed)  
✅ Week7 baseline untouched  
✅ No new C# errors  

### Validation Artifacts
- **Report file:** `HUMAN_PLAY_2_PART6_ACTUAL_MANUAL_CONTROL_FIX_REPORT.md` (this file)
- **JSON validation:** `human_play_2_part6_actual_manual_control_validation.json`

---

## 8. Files Changed

| File | Type | Change | Lines |
|------|------|--------|-------|
| `Assets/Scripts/MLAgents/Stage7B/MlAgentsTrainingBootstrap.cs` | C# Code | Add _autoStartEpisodeOnStart field; modify Start() logic | +1 header, +1 field, +1 conditional branch |
| `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity` | Scene YAML | _initialMode: 1→2; _autoStartEpisodeOnStart: 0 | 2 edits |

---

**Status:** ✅ READY FOR VALIDATION & WEEK6 PROGRESSION

