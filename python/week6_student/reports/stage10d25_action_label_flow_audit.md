# Stage10D25 — BC Target Dataset Fix Preparation Report
Generated: 20260504T201410Z

---
## Part A — Heuristic Mode Isolation Audit

- Snapshots analysed: 80
- `adapter_invoked=true` count: 0
- `adapter_invoked=false` count: 0
- **Verdict (pre-fix):** `ISOLATED`
- **Verdict (post-fix):** `ISOLATED — after applying the C# fix above and re-running D22 capture, heuristic snapshots will show adapter_invoked=false, uses_heuristic_policy=true, policy_source=heuristic_policy, action_buffer_source=heuristic_policy_adapter.`

### Root Cause

> All snapshots show adapter_invoked=false (already fixed or not yet run).

### C# Fix Applied

**File 1:** `Assets/Scripts/ML/Week6VisualInspectionRunner.cs`
  Added SetCurrentCaptureModeContext(modeName, player1Mode, player2Mode) public method. Added 7 new
  fields to Stage10VisualSnapshot: mode, policy_source, inference_source, uses_student_checkpoint,
  uses_python_adapter, uses_heuristic_policy, action_buffer_source. Added IsHeuristicOnlyMode()
  helper: returns true when both players are HeuristicBaseline. ResolveAdapterInvoked() returns
  false when IsHeuristicOnlyMode(). Policy-source helpers populate correct telemetry per-mode.

**File 2:** `Assets/Scripts/ML/Editor/Week6Stage10D22GlobalActionLifecycleMenu.cs`
  RunSingleMode now accepts Week6StudentPolicyAdapter adapter parameter. Before each run:
  runner.SetCurrentCaptureModeContext(modeName, p1Mode, p2Mode). Before heuristic_baseline run:
  adapter.ResetEpisodeState() to clear stale diagnostics. All three RunSingleMode call-sites updated
  to pass adapter.

---
## Part B — Action Label Flow Audit

- **Stage 0 [legacy032_3m_raw_rollout]:** Move=0  actor_rate=0.000  ✗ **ZERO**
- **Stage 1 [legacy032_3m_semantic_adapted]:** Move=0  actor_rate=0.000  ✗ **ZERO**
- **Stage 2 [bc_ready_d7]:** Move=0  actor_rate=0.000  ✗ **ZERO**
- **Stage 3 [bc_ready_d14a]:** Move=0  actor_rate=0.000  ✗ **ZERO**
- **Stage 4 [bc_ready_d14b]:** Move=0  actor_rate=0.000  ✗ **ZERO**
- **Stage 5 [bc_ready_d17]:** Move=841  actor_rate=0.005  ✓
- **Stage 6 [bc_ready_d19b_a]:** Move=0  actor_rate=0.000  ✗ **ZERO**
- **Stage 7 [bc_ready_d19b_b]:** Move=3,470  actor_rate=0.020  ✓
- **Stage 8 [bc_ready_d19c_a]:** Move=4,657  actor_rate=0.025  ✓
- **Stage 9 [bc_ready_d19c_b]:** Move=4,663  actor_rate=0.025  ✓
- **Stage 10 [gridnet_stoch_adapted_episodes]:** Move=196,361  actor_rate=0.200  ✓

---
## Part C — Action Target Encoding Validation

**Verdict:** VALID — Move=1 in branch 0; move_dir in [0,3]; branch spec confirmed (N=7 branches, 576 cells).

- `legacy032_v2_stage10d17_movement_augmented_bc_ready_20260503T162905Z / train`: Move cells=841, move_dir_in_range=True
- `stoch_episode_00000 / episode`: Move cells=49,308, move_dir_in_range=True

---
## Part D — Movement-Positive Candidate Dataset

- Status: **OK**
- Episodes loaded: 4
- Total steps: 2,048
- Train samples: 1,639  Move: 157,180  actor_rate: 0.200
- Val samples: 409  Move: 39,181  actor_rate: 0.200
- Output: `C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week6_student\bc_ready\stage10d25_movement_positive_candidate_20260504T201410Z`

### Per-Unit-Type Move Stats

- **Worker**: actor_cells=971,034  move_cells=194,007  move_rate=0.200
- **Base**: actor_cells=4,066  move_cells=989  move_rate=0.243
- **Barracks**: actor_cells=0  move_cells=0  move_rate=0.000

---
## Part E — Acceptance Gate

**Overall verdict:** NO_GO — 1 gate(s) blocking: HEURISTIC_ISOLATED

- ✅ `TRAIN_MOVE_GT_ZERO`: 157180  ← required > 0
  > train_move_count=157180
- ✅ `VAL_MOVE_GT_ZERO`: 39181  ← required > 0
  > val_move_count=39181
- ✅ `MOVE_LABEL_IS_INDEX_1`: 1  ← required == 1
  > ACTION_TYPES[1] = 'Move' by spec; verified in Part C encoding check.
- ✅ `ENCODING_LEGAL`: VALID — Move=1 in branch 0; move_dir in [0,3]; branch spec confirmed (N=7 branches, 576 cells).  ← required VALID
  > Part C encoding validation verdict
- ❌ `HEURISTIC_ISOLATED`: ISOLATED  ← required ISOLATED
  > C# fix applied to Week6VisualInspectionRunner.cs and D22 menu. However existing D22 snapshots were captured PRE-FIX. Status will become PASS after D22 is re-run in Unity.

**Next step:** Re-run Stage10D22 capture in Unity after C# fix compiles, then re-run this script to confirm HEURISTIC_ISOLATED=PASS.
