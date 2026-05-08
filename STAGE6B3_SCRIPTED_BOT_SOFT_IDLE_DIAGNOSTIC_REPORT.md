# STAGE6B3_SCRIPTED_BOT_SOFT_IDLE_DIAGNOSTIC_REPORT

Status: CODE_PATCH_V2_APPLIED_RUNTIME_VALIDATION_PENDING
Date: 2026-05-08
Scene: Assets/Scenes/Week6_StudentStaticHarvestLayout.unity
Checkpoint: python/week6_student/checkpoints/Stage6B3_SemanticObservationFix/legacy032_v2_bc_source_valid_semantic_obs_fix_final.pt

---

## 1. Scope

Task: stabilize Player2 scripted movement (remove visual A<->B group ping-pong) with no changes to:
- Stage6B3 student model path
- checkpoint
- teacher/data/student/PPO/ML-Agents
- legal mask correctness
- ActionApplier validation semantics
- MatchManager semantics

---

## 2. Root Cause Update

Status: CONFIRMED (code-level)

Primary causes of remaining oscillation after v1 patch:
1. Reverse penalty still too weak in crowded local minima.
2. No strict goal lock/hysteresis, so goal can churn every decision tick.
3. No per-step reservation, so multiple units select the same/adjacent targets.
4. Group congestion amplifies mutual pushback.
5. Greedy local detour (single-step scoring only) can keep agents in short loops.

---

## 3. Applied v2 Patch

### 3.1 File: Assets/Scripts/ML/HeuristicPolicyAdapter.cs

Implemented Player2-only movement stabilization:

1. Goal lock / hysteresis
- per-unit retained goal in move memory
- lock duration clamped to 5..10 ticks (default 8)
- goal reused while still valid
- goal reset triggers:
  - invalid goal target (destroyed/exhausted/out-of-bounds)
  - useful non-move action (Harvest/Return/Attack/Produce)
  - goal unreachable threshold exceeded
  - stuck threshold exceeded

2. Hard anti-reverse cooldown
- reverse cooldown ticks after move (default 3)
- reverse receives very large penalty when cooldown is active
- reverse allowed only when:
  - no alternative legal move
  - stuck counter reached threshold
  - reverse enables immediate useful action (Harvest/Return/Attack)

3. Recent-cell ring memory (3..5)
- per-unit ring (capacity 5)
- penalties:
  - previous cell: very large
  - recent cells: large
  - visited 2 ticks ago: medium
  - not recently visited: bonus

4. Per-step reservation map
- Player2 per-tick reserved target set
- exact reserved target conflict gets high penalty
- adjacent-to-reserved target gets extra congestion penalty

5. Bounded BFS detour fallback
- when no strict distance-reducing move exists and goal exists:
  - bounded BFS depth 3..5 (default 4)
  - skips occupied/reserved nodes
  - returns first step from shortest successful frontier
- if BFS fails, scored detour remains active

### 3.2 File: Assets/Scripts/ML/Week6VisualInspectionRunner.cs

Extended scripted trace aggregation and jsonl schema for new v2 fields (Section 4).

---

## 4. Telemetry Fields (v2)

Added/verified:
- scripted_goal_locked
- scripted_goal_lock_ticks_remaining
- scripted_reverse_blocked_count
- scripted_recent_cell_penalty_count
- scripted_reserved_target_conflict_count
- scripted_bfs_detour_used_count
- scripted_bfs_detour_failed_count
- scripted_move_score_selected
- scripted_move_score_second_best
- scripted_move_selection_reason

Preserved from v1:
- scripted_reverse_move_count
- scripted_oscillation_detected
- scripted_same_two_cell_loop_count
- scripted_detour_used_count
- scripted_goal_type
- scripted_goal_cell
- scripted_selected_move_direction
- scripted_selected_target_cell

---

## 5. Regression Run Status

Play Mode regression target:
- minimum 300 steps, preferred 500

Current execution status:
- BLOCKED by Unity session availability in MCP
- tool response: no_unity_session (Start Unity and Start Session required)

Current measurable result:
- compile check for touched C# files: PASS

Pending runtime metrics:
- step_80_boundary_cleared
- Stage6B3 active
- Player2 active after old step 91
- Player2 accepted commands after step 91
- scripted_rejected_count
- scripted_reverse_move_count reduction
- scripted_same_two_cell_loop_count reduction
- scripted_oscillation_detected frequency
- visual A<->B ping-pong suppression

---

## 6. Changed Files

- Assets/Scripts/ML/HeuristicPolicyAdapter.cs
- Assets/Scripts/ML/Week6VisualInspectionRunner.cs
- STAGE6B3_SCRIPTED_BOT_SOFT_IDLE_DIAGNOSTIC_REPORT.md

---

## 7. GO/NO-GO

Current decision:
- GO for code-level patch readiness under all stated constraints.
- NO-GO for demo-readiness closure until 300+ step runtime validation is captured.
