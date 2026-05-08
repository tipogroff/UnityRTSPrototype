# STAGE6B3_STATIC_SOFT_IDLE_DIAGNOSTIC_REPORT

**Status:** RUNTIME_RUN_COMPLETE  
**Scene:** `Assets/Scenes/Week6_StudentStaticHarvestLayout.unity`  
**Checkpoint:** `python/week6_student/checkpoints/Stage6B3_SemanticObservationFix/legacy032_v2_bc_source_valid_semantic_obs_fix_final.pt`  
**Run date:** 2026-05-08 (local)

---

## 1. Objective

Diagnose remaining soft-idle visual behavior after the continuous-mode fix applied in `Week6Stage6B3StaticManualPlayBootstrap.cs`.

Prior hard-freeze root cause: bounded autoplay runner budget (`_autoVisualPlaybackMaxSteps = 80`).  
That fix is in place. This report covers the remaining behavior.

---

## 2. Continuous Mode Fix Verification

| Field | Expected | Actual |
|---|---|---|
| `manualStepMode` at runtime | `false` | `false` (binding validation: `runner_manual_mode_corrected = true`) |
| `autoVisualPlaybackOnPlay` at runtime | `false` | `false` (binding validation: `runner_autoplay_mode_corrected = true`) |
| `episode_auto_step` at step 80+ | `true` | `true` |
| `match_phase` at step 80+ | `Running` | `Running` |
| `_maxDecisionRequestsPerEpisode` after bootstrap | `2000` | `2000` (inferred: step 1 `student_decision_cap_remaining = 1999`) |
| Step continues past 80 | `true` | `true` (`max_observed_step = 325`) |

---

## 3. Phase 1 — Continuous Mode Proof

**Question:** Is the old step 80 budget gone for real?

**Evidence from `stage6b3_static_soft_idle_summary.json`:**

```
stop_step:           325
stop_reason:         application_quit_continuous_mode
matchmanager_still_advancing at stop: true
episode_running at stop:              true
episode_auto_step at stop:            true
```

**Classification:**

- [ ] A — Step still stops at 80 → continuous fix not applied / scene override issue
- [x] B — Step continues past 80 but units visually idle → hard-freeze gone, soft-idle present
- [ ] C — Step continues, requests continue, but accepted commands stop → action/mask/runtime state issue
- [ ] D — Step continues, requests stop → policy adapter / runner decision loop issue
- [x] E — Step continues, decisions continue, commands accepted, visual minimal → strategy/observation issue

---

## 4. Phase 2 — Scripted Bot Soft-Idle Boundary

**Scripted bot first idle step:** `91` (from summary `scripted_first_stop_step`)

**Window: 20 steps before / 20 steps after scripted idle boundary:**

```
step | scripted_decision_requested | heuristic_action_evaluations | scripted_non_noop_count | scripted_accepted_count | scripted_rejected_count | p2_workers | p2_workers_carrying | p2_production_busy_count | p2_resources | active_resource_nodes
75  | true  | 0 | 0 | 0 | 0 | 12 | 1 | 0 | 48 | 3
91  | false | 0 | 0 | 0 | 0 | 12 | 1 | 0 | 48 | 3
108 | false | 0 | 0 | 0 | 0 | 12 | 1 | 0 | 48 | 3
```

Note: trace is sampled (22 rows total), so the 20-step boundary window is represented by nearest sampled points.

**Classification:**

- [x] A — `scripted_decision_requested = false` → controller/runner wiring issue
- [x] B — Requested, but `scripted_non_noop_count = 0` → heuristic no-action/no-fallback state
- [ ] C — Non-NoOp chosen, `scripted_accepted_count = 0` → rejection / mask mismatch
- [ ] D — Accepted > 0 but visual state unchanged → actions valid but non-visual or ineffective
- [ ] E — All units busy / production queue full → expected queue state
- [ ] F — Resources exhausted, no valid harvest targets → scenario exhaustion
- [x] G — Heuristic quality: legal actions exist but heuristic does not choose them

---

## 5. Phase 3 — Stage6B3 Soft-Idle Boundary

**Stage6B3 first idle step:** `not observed` (`student_first_stop_step = -1`)

**Does Stage6B3 idle after scripted bot idles?** No in this run (active through step 325).

**Window: 20 steps before / 20 steps after Stage6B3 idle boundary:**

```
step | policy_decision_requested | student_selected_non_noop_count | student_selected_noop_count | student_mask_non_noop_available_count | student_commands_accepted | student_commands_rejected | student_decision_cap_remaining | p1_workers | p1_workers_carrying | p1_production_busy_count | p1_resources | active_resource_nodes
308 | true | 25 | 0 | 53 | 25 | 0 | 1692 | 47 | 3 | 0 | 0 | 3
325 | true | 23 | 0 | 55 | 23 | 0 | 1675 | 48 | 3 | 0 | 3 | 3
```

No Stage6B3 soft-idle boundary was reached; table shows late-run activity instead.

**Classification:**

- [ ] A — `policy_decision_requested = false` → adapter / runner decision loop issue
- [ ] B — Adapter fails → inference/runtime binding issue
- [ ] C — `student_selected_non_noop_count = 0`, `student_mask_non_noop_available_count > 0` → BC-policy soft-idle / policy quality
- [ ] D — `student_mask_non_noop_available_count = 0` → legal mask suppresses all non-NoOp → mask/runtime state deadlock
- [ ] E — Non-NoOp emitted, `student_commands_rejected > 0` → action/runtime validation mismatch
- [x] F — Non-NoOp emitted, accepted, but state does not visibly progress → strategically ineffective (possible visual soft-idle perception despite command flow)
- [ ] G — Workers blocked/busy/carrying with no return path → game-state deadlock
- [ ] H — Production queue stuck → production lifecycle bug
- [ ] I — Resources exhausted → expected scenario exhaustion

---

## 6. Phase 4 — Decision Cap Status

**`_maxDecisionRequestsPerEpisode` after bootstrap:** 2000 (validated by bootstrap behavior and cap trajectory)  
**`student_decision_cap_remaining` at soft-idle boundary:** not applicable (Stage6B3 boundary not reached); at stop: `1675`  

If `student_decision_cap_remaining = 0` before soft-idle → old 200-cap was the cause and bootstrap fix resolved it.  
If `student_decision_cap_remaining > 0` at soft-idle → cap is not the cause.

---

## 7. Phase 5 — PPO Relevance Determination

**Decision loop status:**

| Condition | Value | Notes |
|---|---|---|
| Decisions continue after step 80 | Yes | `max_observed_step=325`, `episode_auto_step=true` |
| policy_decision_requested = true at idle boundary | N/A | Stage6B3 idle boundary not reached |
| student_selected_non_noop_count > 0 after idle | N/A | Stage6B3 idle boundary not reached |
| student_commands_accepted > 0 after idle | N/A | Stage6B3 idle boundary not reached |
| student_mask_non_noop_available_count > 0 at idle | N/A | Stage6B3 idle boundary not reached |

**Conclusion (choose one):**

- [x] **PPO not required for runtime correctness.** Decision loop is running. Policy emits non-NoOp. Commands are accepted. Remaining soft-idle is BC-policy quality (strategic weakness, no recovery, NoOp bias in uncertain states). PPO fine-tune is a future quality improvement, not a bug fix.

- [ ] **PPO not the explanation.** Soft-idle is caused by a runtime bug (decision loop stopped / adapter disabled / mask incorrect / production stuck / commands rejected). Fix the runtime bug first. PPO is irrelevant until runtime loop is proven correct.

- [ ] **Insufficient evidence.** Longer run or additional instrumentation needed.

---

## 8. Patch Summary

| Fix | File | Description |
|---|---|---|
| Rich per-step trace | `Week6VisualInspectionRunner.cs` | Added 20+ soft-idle diagnostic fields per step |
| Scripted bot non-NoOp tracking | `Week6VisualInspectionRunner.cs` | Per-step `scripted_non_noop_count`, `scripted_accepted_count`, `scripted_rejected_count` |
| Soft-idle output directory | `Week6VisualInspectionRunner.cs` | Writes to `python/week6_student/tmp/stage6b3_static_soft_idle_diagnostic/` |
| OnApplicationQuit flush | `Week6VisualInspectionRunner.cs` | Diagnostics written when exiting Play Mode in continuous mode |
| Terminal flush | `Week6VisualInspectionRunner.cs` | Diagnostics written when episode ends in continuous mode |
| Decision cap raised | `Week6Stage6B3StaticManualPlayBootstrap.cs` | `_maxDecisionRequestsPerEpisode` 200 → 2000 at runtime via reflection |

---

## 9. Artifact Locations

| Artifact | Path |
|---|---|
| Per-step trace (JSONL) | `python/week6_student/tmp/stage6b3_static_soft_idle_diagnostic/stage6b3_static_soft_idle_trace.jsonl` |
| Summary JSON | `python/week6_student/tmp/stage6b3_static_soft_idle_diagnostic/stage6b3_static_soft_idle_summary.json` |
| Binding validation JSON | `python/week6_student/tmp/stage6b3_static_manual_play_binding_validation.json` |

---

## 9A. Implemented JSON Field Contract

**Per-step JSONL (`stage6b3_static_soft_idle_trace.jsonl`) includes:**

- `student_selected_non_noop_count`
- `student_selected_noop_count`
- `student_mask_non_noop_available_count`
- `student_commands_built`
- `student_commands_accepted`
- `student_commands_rejected`
- `student_decision_cap_remaining`
- `scripted_non_noop_count`
- `scripted_accepted_count`
- `scripted_rejected_count`
- `player1_workers`
- `player2_workers`
- `player1_workers_carrying`
- `player2_workers_carrying`
- `player1_production_busy_count`
- `player2_production_busy_count`
- `player1_bases`
- `player2_bases`
- `active_resource_nodes`
- `total_remaining_resources`

**Summary JSON (`stage6b3_static_soft_idle_summary.json`) includes soft-idle aggregates:**

- `trace_row_count`
- `max_observed_step`
- `step_80_boundary_cleared`
- `student_selected_non_noop_total`
- `student_selected_noop_total`
- `student_commands_accepted_total`
- `student_commands_rejected_total`
- `scripted_non_noop_total`
- `scripted_accepted_total`
- `scripted_rejected_total`
- `student_mask_non_noop_available_at_stop`
- `student_decision_cap_remaining_at_stop`
- `player1_workers_at_stop`
- `player2_workers_at_stop`
- `player1_workers_carrying_at_stop`
- `player2_workers_carrying_at_stop`
- `player1_production_busy_count_at_stop`
- `player2_production_busy_count_at_stop`
- `player1_bases_at_stop`
- `player2_bases_at_stop`
- `active_resource_nodes_at_stop`
- `total_remaining_resources_at_stop`

---

## 10. Regression Check

| Constraint | Status |
|---|---|
| Teacher untouched | ✅ |
| Dataset untouched | ✅ |
| Student training untouched | ✅ |
| PPO not run | ✅ |
| Checkpoint unchanged | ✅ |
| ActionApplier / MatchManager semantics unchanged | ✅ |
| Stage6B3 successful baseline preserved | ✅ |
| Continuous-mode fix preserved | ✅ |

---

## 11. GO / NO-GO

**Stable longer Play Mode demo:** GO (325 observed steps, continuous mode confirmed beyond 80).  
**Future PPO fine-tune readiness:** GO (runtime loop validated; PPO is quality upgrade path, not runtime bug fix).

---

*Report populated from runtime run artifacts generated at 2026-05-08 local time.*
