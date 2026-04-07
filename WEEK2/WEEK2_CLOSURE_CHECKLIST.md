# Week 2 Closure Checklist

Last update: 2026-03-19

> 📄 See also: [WEEK2_GAME_FOUNDATION_SUMMARY.md](WEEK2_GAME_FOUNDATION_SUMMARY.md) — итоговый engineering summary Week 2.

This file tracks what must be fixed and completed so Week 2 can be considered closed.

## 1) Critical blockers (must fix first)

### 1.1 Remove double match startup
- [ ] Ensure match initialization happens exactly once per episode.
- [ ] Remove duplicate startup path between MatchBootstrap and EpisodeController.
- [ ] Verify there are no duplicate resource node registrations at play start.

Expected result:
- No repeated warnings like "Resource node already exists" right after entering Play Mode.
- No occupancy drift caused by duplicate spawn/setup.

### 1.2 Restore stable worker movement/occupancy consistency
- [ ] Fix occupancy desync that triggers GridManager MoveUnit mismatch errors.
- [ ] Ensure unit references in occupancy map are consistent after spawn, move, death, reset.

Expected result:
- No repeating GridManager errors about "registered different unit" during normal simulation.

### 1.3 Fix harvest/deposit loop for auto-play (no ML)
- [ ] Align HeuristicDriver worker logic with MatchManager harvest/deposit contract.
- [ ] Worker should harvest from valid target cell and return resources to own base.
- [ ] Confirm resource carry increases and then drops to player balance.

Expected result:
- Closed economy loop works in auto mode: harvest -> accumulate -> produce.

### 1.4 Add reliable multi-episode auto loop
- [ ] Implement automatic next-episode start after terminal state.
- [ ] Add configurable total episode count for continuous runs.
- [ ] Ensure run can execute multiple episodes without manual reset.

Expected result:
- Episodes run back-to-back automatically until configured count is reached.

### 1.5 Connect and validate CSV logging
- [ ] Add ExperimentLogger component to scene and wire references.
- [ ] Ensure episode begin/end are always logged.
- [ ] Ensure per-episode CSV rows are written for continuous runs.

Expected result:
- CSV file is created and updated with one row per completed episode.

### 1.6 Remove runtime Input exceptions in debug controller
- [ ] Update ManualStepController to work with active Input System configuration.
- [ ] Remove per-frame InvalidOperationException spam.

Expected result:
- Clean console (no recurring Input exceptions during play).

### 1.7 Fix smoke-test helper logic
- [ ] Fix SmokeTestAutomation state logic so test continues until terminal + reset checks.
- [ ] Fix SmokeTestMenuRunner StepMatch interpretation (running vs terminal semantics).
- [ ] Keep one deterministic smoke path for CI/manual verification.

Expected result:
- Smoke test accurately reports PASS/FAIL for full lifecycle.

## 2) Week 2 readiness criteria (all must be true)

- [ ] Scene starts from a single GameConfig.
- [ ] Map is generated deterministically the same way every run.
- [ ] All starting units spawn in correct grid cells.
- [ ] Worker can harvest resources and return them to base.
- [ ] Base can produce at least one new worker.
- [ ] Basic attack works and destroyed units are removed.
- [ ] Match ends by victory condition or step limit.
- [ ] Reset restores initial state with no manual scene cleanup.
- [ ] Multiple episodes can run automatically in sequence.
- [ ] CSV logger writes episode metrics for the full run.

## 3) Verification protocol before marking Week 2 done

### 3.1 Clean startup check
- [ ] Enter Play Mode once.
- [ ] Confirm no duplicate setup warnings/errors in console.

### 3.2 Economy and production check
- [ ] Observe worker harvest and deposit events.
- [ ] Confirm player resource balance increases.
- [ ] Confirm base produces at least one worker after resources accumulate.

### 3.3 Combat and terminal check
- [ ] Confirm at least one attack interaction happens.
- [ ] Confirm destroyed unit removal from scene and registry.
- [ ] Confirm terminal state is reached (victory or step limit).

### 3.4 Reset and multi-episode check
- [ ] Confirm reset restores initial state correctly.
- [ ] Run at least 5 episodes automatically in one launch.

### 3.5 Logging check
- [ ] Confirm CSV file exists for the run.
- [ ] Confirm CSV has one line per completed episode.
- [ ] Confirm key fields are populated (episode, steps, win, invalid_rate).

## 4) Definition of done for Week 2

Week 2 is considered closed only when:
- Every item in section 1 is checked.
- Every readiness criterion in section 2 is checked.
- Verification protocol in section 3 passes without critical errors.
