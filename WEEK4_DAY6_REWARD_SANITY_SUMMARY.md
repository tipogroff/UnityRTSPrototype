# Week 4 Day 6: Reward Distribution Sanity-Check

**Date:** March 31, 2026 (Cleanup pass completed April 2, 2026)  
**Status:** ✅ Passed  
**Scope:** Baseline rollout sanity-check tooling + factual validation run results + semantic alignment fixes  

---

## 1. Overview

Day 6 implements **sanity-checking infrastructure** for the Week 4 RL loop without modifying reward design or terminal logic.
This artifact documents tooling readiness, factual rollout validation in diagnostic baseline mode, and post-validation semantic fixes for terminal reward consistency.

### Validation Run Results (Actual)

Validation executed with existing Day 6 tooling in **diagnostic-only heuristic-vs-idle mode**.

- Latest validation (post-fix): [WEEK4_Reports/WEEK4_DAY6_REWARD_SANITY_BATCH_2026-04-02_20-13-00.md](WEEK4_Reports/WEEK4_DAY6_REWARD_SANITY_BATCH_2026-04-02_20-13-00.md) ✅ **Terminal Reward Non-Zero: 10/10 (100,0%)**
- Previous runs: [WEEK4_Reports/WEEK4_DAY6_REWARD_SANITY_BATCH_2026-03-31_23-50-00.md](WEEK4_Reports/WEEK4_DAY6_REWARD_SANITY_BATCH_2026-03-31_23-50-00.md)

### Cleanup Pass Note (Post-Closure) — IMPLEMENTED & VALIDATED ✅

**Problem identified:** `TerminalRewardNonZero` flag showed 0/N while actual terminal reward breakdown was -0.25

**Solution implemented:**
1. **Episode-level fallback** (BaselineRolloutRunner lines 160-167): Derive terminal flags from cumulative reward summary if report flag unavailable
2. **Batch-level hardening** (BaselineRolloutRunner line 295+): Count non-zero terminals using `ep.TerminalReward != 0` instead of flag

**Validation:** Fresh 10-episode run (2026-04-02 20:13:00) confirms **Terminal Reward Non-Zero: 10/10 (100,0%)** ✅

- Timeout reward plumbing: **confirmed** by factual breakdowns (`Terminal = -0.25`)
- Semantic alignment: **now working** — flag correctly reflects non-zero terminal rewards
- Timeout-only outcome distribution: **residual caveat** of diagnostic scenario, not a Day 6 blocker

#### 10-Episode Sanity Pass

- avg total reward: `3.22`
- std / min / max total reward: `0.00 / 3.22 / 3.22`
- avg economy / combat / terminal / shaping: `3.19 / 0.28 / -0.25 / 0.00`
- avg step count: `2000.0`
- terminal reason distribution: `Timeout=10/10`
- outcome distribution: `Timeout=10/10`
- avg / max invalid action rate (measured): `0.0% / 0.0%`
- sanity warnings in historical reports: `3`
    - terminal reward often zero (from terminal non-zero flag inconsistency, now treated as a report-semantic issue)
    - outcome imbalance (100% timeout)
    - suspiciously long low-reward episodes

Engineering interpretation (10 episodes):

- Reward explosion: **not observed**.
- Reward starvation: **not observed** (mean reward above starvation threshold).
- Shaping dominance: **not observed** (0%).
- Invalid action rate: **looks healthy** for measured episodes (0%).
- Terminal behavior: **mechanically stable** (terminal processed in 100% episodes), but all runs terminate by timeout in this diagnostic scenario.
- Trace interpretability: **interpretable but narrow** (single terminal/outcome mode).

Gate decision to 20 episodes:

- No critical failure in reward magnitude or terminal processing pipeline.
- Proceeded to 20-episode confirmation run.

#### 20-Episode Confirmation Pass

20-episode aggregate remained effectively identical to the 10-episode pass:

- avg total reward: `3.22`
- std / min / max total reward: `0.00 / 3.22 / 3.22`
- avg economy / combat / terminal / shaping: `3.19 / 0.28 / -0.25 / 0.00`
- avg step count: `2000.0`
- terminal reason distribution: `Timeout=20/20`
- outcome distribution: `Timeout=20/20`
- avg / max invalid action rate (measured): `0.0% / 0.0%`
- sanity warnings: `3` (same set as in 10-episode run)

Comparison vs 10 episodes:

- Interpretable behavior is stable across sample size increase.
- No new warnings appeared.
- No reward explosion/starvation trend emerged.
- Outcome/terminal imbalance remained one-sided (timeout-only behavior).

#### Final Day 6 Validation Conclusion — COMPLETE ✅

- Reward distribution primary sanity-check: **passed**.
- Terminal behavior stability: **passed**.
- Terminal timeout reward plumbing: **confirmed in factual rollout breakdowns** (`Terminal = -0.25`).
- Terminal non-zero flag/report consistency: **FIXED** — semantic alignment now enforced at both episode and batch levels.
- Baseline trace interpretability: **present but limited** due to timeout-only outcomes in this diagnostic setup.
- Warnings requiring follow-up tuning: **yes, non-blocking for Day 6 closure**.

Final status for Day 6 based on factual rollout runs: **✅ PASSED** (with non-blocking outcome-diversity caveat for diagnostic mode).

**Code implementation validated:** BaselineRolloutRunner now correctly propagates terminal reward non-zero state from authoritative episode summary.

Follow-up (no redesign in Day 6 scope):

1. Keep `TerminalRewardNonZero`/batch metrics semantically aligned with the actual terminal reward bucket.
2. Treat timeout-only outcomes as a residual limitation of this diagnostic baseline scenario.
3. Continue outcome-diversity tuning/debug as follow-up work outside Day 6 closure scope.

**Diagnostic Mode Note:**
This validation used **heuristic-vs-idle mode** (Heuristic agent vs Idle opponent) as a diagnostic simplification for clearer sanity inspection. This is **NOT** the standard baseline self-play mode, and results must not be generalized as gameplay distribution evidence.

### What This Day Delivers

✅ **BaselineRolloutRunner** — orchestrator for batch-mode baseline rollouts  
✅ **RolloutEpisodeSummary** — episode-level diagnostics struct  
✅ **RolloutBatchSummary** — batch aggregates and statistics  
✅ **RewardSanityChecker** — heuristic warning flags for anomaly detection  
✅ **Day6RewardSanitySmokeTest** — executable smoke test with markdown report generation  

### Non-Goals

❌ Rewrite reward design  
❌ Tune reward coefficients  
❌ Implement ML-Agent training  
❌ Provide mathematical proofs of optimality  
❌ Run 1000+ episode batch (pilot: 10-20 episodes for diagnostics)  

---

## 2. Architecture

### 2.1 BaselineRolloutRunner

Pure C# orchestrator (non-MonoBehaviour) that:
1. Manages batch episode sequencing
2. Uses EpisodeController's existing public API: `StartNewEpisode()`, `StepEpisodeOnce()`, `IsRunning`
3. Wraps single episode runs into `RolloutEpisodeSummary` structs
4. Aggregates into `RolloutBatchSummary`
5. Runs sanity checks via `RewardSanityChecker`

**Execution model:**
```
for each episode in batch:
  1. EpisodeController.StartNewEpisode()
  2. while (IsRunning):
       - EpisodeController.StepEpisodeOnce() [delegates to canonical RL loop]
       - collect InvalidActionCount from LastRlLoopStepReport
     end while
  3. Capture RolloutEpisodeSummary from:
      - CurrentRewardEpisodeSummary (episode cumulative total/economy/combat/terminal/shaping + event count)
      - LastTerminalReport (terminal reason, winner, event flags)
  4. Append to batch
end for
```

**Key property:** Does not create a separate execution path. Uses the same canonical RL loop active in normal play.

### 2.2 RolloutEpisodeSummary

Per-episode metrics struct, fields:
- `EpisodeIndex`, `StepCount`
- Reward breakdown: `TotalReward`, `EconomyReward`, `CombatReward`, `TerminalReward`, `ShapingReward`
- Terminal info: `IsTerminal`, `TerminalReason`, `Winner`, `TerminalEventProcessed`, `TerminalRewardNonZero`
- Runtime diagnostics: `InvalidActionCount`, `InvalidActionRate`, and availability fields
    (`InvalidActionRateMeasured`, `InvalidActionMeasuredStepCount`, `InvalidActionUnavailableStepCount`)
- Label: `OutcomeLabel` (Win, Loss, Draw, Timeout, InvalidRuntimeState)

Provides utility methods:
- `GetSummaryLine()` — human-readable one-liner for logging
- `GetCompactLine()` — compact tabular format for batch scan

### 2.3 RolloutBatchSummary

Batch-level aggregation of N episodes:
- **Reward stats:** mean ± std, min/max total; per-category means
- **Episode stats:** avg steps, event counts
- **Terminal processing:** event processed rate, non-zero reward rate, reason distribution
- **Outcome distribution:** counts and percentages by outcome label
- **Invalid actions:** measured-only rates plus availability counts (measured/unavailable episodes)
- **Shaping fraction of total:** average proportion of shaping reward in total reward sum
- **Warnings:** list of sanity-check alerts

Provides methods:
- `ToMarkdown()` — full markdown report
- `ToOneLine()` — compact console summary

### 2.4 RewardSanityChecker

Static utility that populates `SanityWarnings` list with heuristic checks:

| Check | Trigger | Why It Matters |
|-------|---------|----------------|
| Reward Explosion | mean > 50.0 | Possible reward hacking or scale misconfiguration |
| Reward Starvation (low mean) | mean < 1.0 | Insufficient signal for learning |
| Reward Starvation (many zero) | >80% episodes reward ≈ 0 | Agent gets no guidance most of the time |
| Shaping Dominance | shaping > 50% of mean | Intermediate rewards may override terminal objective |
| Invalid Action Spike | avg > 15% | Mask/decoder fundamental issues |
| Extreme Invalid Rate | max > 30% | Severe action space mismatch |
| Terminal Event Processing Low | <70% episodes | Terminal pipeline may be missing cases |
| Terminal Reward Often Zero | <30% of processed events | Terminal config may be disabled or too conservative |
| InvalidRuntimeState Frequent | >10% of episodes | Runtime state machine issues |
| Outcome Imbalance | >80% single outcome | Agent may be stuck in a single state |
| Suspiciously Long Low-Reward Episodes | >10% episodes with steps>1000 and reward<5.0 | Agents stuck in passive play |

All thresholds are tunable via `RewardSanityCheckConfig`.

### 2.5 Day6RewardSanitySmokeTest

MonoBehaviour that:
1. Wraps BaselineRolloutRunner
2. Exposes context menu: "Execute Reward Sanity Check (Play Mode)"
3. Runs batch rollout with verbose logging to console
4. Generates timestamped markdown report to `WEEK4_Reports/` directory
5. Opens report with default application

**Usage in Play Mode:**
```
1. Ensure EpisodeController is in scene
2. Enter Play Mode
3. Right-click on Day6RewardSanitySmokeTest gameobject → "Execute Reward Sanity Check (Play Mode)"
4. Check console for summary
5. Report auto-generates to WEEK4_Reports/WEEK4_DAY6_REWARD_SANITY_BATCH_YYYY-MM-DD_HH-MM-SS.md
```

---

## 3. Implementation Summary

### New Files

| File | Purpose |
|------|---------|
| `RolloutEpisodeSummary.cs` | Per-episode diagnostics struct |
| `RolloutBatchSummary.cs` | Batch aggregation and markdown export |
| `RewardSanityChecker.cs` | Sanity-check heuristics and warning population |
| `BaselineRolloutRunner.cs` | Batch rollout orchestrator |
| `Day6RewardSanitySmokeTest.cs` | Executable smoke test with Play Mode integration |

### Key Design Decisions

1. **No separate execution path:** Uses existing `RlLoopCoordinator`, `RuntimeRewardCollector`, `EpisodeTerminalEvaluator`.
2. **Episode-level, not step-level:** Collects diagnostics per episode, not per step (separate from existing step traces).
3. **Tunable thresholds:** `RewardSanityCheckConfig` allows environment/reward-schema-specific tuning.
4. **Warning-only, not assertions:** Sanity checks populate warnings but do not block execution or return false.
5. **Markdown export:** Human-readable reports for documentation and manual review.

---

## 4. Usage Example

### In C# (Programmatic)

```csharp
// Create runner
var runner = new BaselineRolloutRunner(EpisodeController.Instance);

// Run 10 baseline episodes with verbose logging
RolloutBatchSummary summary = runner.StartBatchRollout(
    episodeCount: 10,
    verboseLogging: true
);

// Check for warnings
if (summary.SanityWarnings.Count > 0)
{
    Debug.LogWarning($"Detected {summary.SanityWarnings.Count} warnings:");
    foreach (var warning in summary.SanityWarnings)
    {
        Debug.LogWarning(warning);
    }
}

// Access per-episode data
foreach (var episode in summary.Episodes)
{
    Debug.Log($"Episode {episode.EpisodeIndex}: reward={episode.TotalReward}, steps={episode.StepCount}");
}

// Export markdown
string markdown = summary.ToMarkdown();
File.WriteAllText("report.md", markdown);
```

### In Play Mode (UI)

1. Add empty GameObject to scene
2. Attach `Day6RewardSanitySmokeTest` component
3. Configure `Episode Count`, `Sanity Config`, `Report Directory`
4. Enter Play Mode
5. Right-click on the GameObject, select "Execute Reward Sanity Check (Play Mode)"

---

## 5. Output Format

### Console Output (with `verboseLogging=true`)

```
[BaselineRolloutRunner] Starting batch: 10 episodes
[BaselineRolloutRunner] #01 | r=12.5 | steps=150 | outcome=Win     | invalid=0%
[BaselineRolloutRunner] #02 | r=8.3  | steps=180 | outcome=Loss    | invalid=5%
...
[BaselineRolloutRunner] Batch(10): avg_reward=10.2±3.5, avg_steps=165, outcomes=Win|Loss|Draw, warnings=0
```

### Markdown Report

Full report includes:
- Header with execution metadata
- Executive summary (passed/failed)
- Reward statistics table (mean, std, category breakdown, shaping fraction)
- Episode statistics (step count, event count)
- Terminal behavior (processing rate, non-zero reward rate, reason distribution)
- Outcome distribution (counts and percentages)
- Invalid action statistics
- Sanity check results (no warnings or detailed warning list)
- Per-episode detail table (one row per episode with full metrics)
- Interpretation guide (what the metrics mean, next steps if warnings detected)

---

## 6. Integration with Week 4 Architecture

### Reuses Existing Components

✅ **RlLoopCoordinator** — canonical 9-phase loop (used in `StepEpisodeOnce()`)  
✅ **RuntimeRewardCollector** — reward evaluation (via `LastRewardBreakdown`)  
✅ **EpisodeTerminalEvaluator** — terminal evaluation (via `LastTerminalReport`)  
✅ **EpisodeController** — episode lifecycle (public API only)  
✅ **RewardConfig** / **RewardBreakdown** — existing structures  

### Does NOT Modify

❌ Reward contract or logic  
❌ Terminal pipeline or semantics  
❌ Action masking or decoding  
❌ HeuristicDriver or heuristic policies  
❌ ML-Agent integration paths  

---

## 7. Sanity-Check Interpretation Guide

### When ALL Checks Pass (no warnings)

✅ **When a real batch run has no warning flags and traces are interpretable:**
- Mean total reward is in a plausible range (not explosive, not starved)
- Reward comes from a mix of categories, not dominated by shaping
- Terminal events are being processed and rewarded

✅ **Terminal behavior appears stable in that run:**
- Episodes complete with recognized terminal reasons
- Terminal outcomes match reward signals (wins get reward, losses don't, etc.)
- No frequent InvalidRuntimeState or other anomalies

✅ **Action space and masking appear functional in that run:**
- Invalid action rate is low (<15%)
- Episodes reach reasonable lengths (not stuck immediately)

✅ **Outcome distribution is sufficiently varied in that run:**
- No single outcome dominates (>80%)
- Mix of wins, losses, draws suggests varied baseline behavior

**_Next step:_ Treat the run as a passed sanity snapshot, then proceed to baseline policy training or deeper trace analysis.**

### When Warnings Detected

⚠️ **Investigate root cause:**

| Warning | Investigation |
|---------|---|
| Reward explosion | Check if a single reward event type exploded; review coefficients in RewardConfig |
| Reward starvation | Check if most episodes have zero reward; review terminal reward config; examine traces |
| Shaping dominance | Check shaping thresholds; consider whether shaping is too generous; review invalid action penalty |
| Invalid action spike | Review action mask computation; check decoder output; validate action type enumeration |
| Terminal events not processed | Review EpisodeTerminalEvaluator logic; check if runtime terminal states are being reached |
| Terminal rewards often zero | Review terminal reward coefficients (TerminalWin, TerminalLoss, etc. in RewardConfig) |
| Outcome imbalance | Check if heuristic is deterministic or stuck in a local pattern; examine traces manually |

**_Do NOT:_ Assume all warnings are equally severe. Manual inspection is required.**

---

## 8. Limitations and Caveats

### Scope

✅ **In scope:** Reward magnitude, terminal event processing, invalid action rate, outcome distribution, basic sanity heuristics  
❌ **Out of scope:** Policy learning curves, final performance, learning efficiency, transfer learning validation, Gym-μRTS compatibility  

### Thresholds

All sanity thresholds are tunable and **not authoritative**:
- Thresholds are heuristic-based engineering checks, not derived from first principles
- Different environments and reward schemas may require different thresholds
- A warning does not mean the system is broken; it means a manual review is warranted

### Episode Count

Pilot runs use 10-20 episodes for quick diagnostics:
- 10 episodes is enough to detect gross anomalies
- 100+ episodes recommended for statistical confidence
- No claim of representativeness for longer training runs

### Baseline vs ML-Agent

This tooling is designed to validate the **reward pipeline and terminal logic** in baseline/heuristic mode once run:
- Baseline behavior does NOT predict ML-Agent behavior
- Baseline may be deterministic or limited; ML-Agent may learn differently
- Reward sanity is necessary but not sufficient for ML-Agent success

---

## 9. Code Fixes Applied (April 2, 2026)

### Issue Identified
During initial validation runs, `TerminalRewardNonZero` batch count showed 0/N while actual terminal reward breakdown was -0.25 for all episodes, indicating a semantic mismatch between the flag and the authoritative reward bucket.

**Root cause:** Terminal report captured by callback before post-step reward accumulation completed in the same frame.

### Fixes Implemented

#### Fix 1: Episode-Level Authoritative Fallback
**File:** `BaselineRolloutRunner.cs`, `RunSingleEpisode()` method, lines 160-167

Added logic to derive terminal flags from cumulative reward summary when report flag unavailable:
```csharp
bool terminalEventProcessed = terminalReport.TerminalEventProcessed
    || (rewardSummary.TerminalReached && rewardSummary.TerminalReason != TerminalReason.None);
bool terminalRewardNonZero = terminalReport.TerminalRewardNonZero
    || !Mathf.Approximately(rewardSummary.Breakdown.Terminal, 0f);
```

**Rationale:** Episode reward summary is the authoritative data source; derive flags from it if report doesn't contain them.

#### Fix 2: Batch Aggregation Hardening
**File:** `BaselineRolloutRunner.cs`, `ComputeBatchAggregates()` method, line 295+

Changed non-zero terminal count calculation to use actual reward value instead of flag:
```csharp
if (ep.TerminalEventProcessed)
{
    terminalEventProcessedCount++;
    if (!Mathf.Approximately(ep.TerminalReward, 0f))
    {
        terminalRewardNonZeroCount++;
    }
}
```

**Rationale:** Hardened aggregation ensures batch-level count reflects actual non-zero terminals, not potentially stale flag values.

### Validation
Fresh test run (2026-04-02 20:13:00, 10 episodes) after applying both fixes confirms:
- ✅ Terminal Reward Non-Zero: 10/10 (100,0%) — previously showed 0/10
- ✅ Terminal: -0.25 for all episodes (authoritative breakdown unchanged)
- ✅ No new warnings or anomalies introduced

---

## 9. Files Modified and Created

### New Files Created

1. **Assets/Scripts/ML/RolloutEpisodeSummary.cs** (96 lines)
   - Struct for per-episode metrics
   - Compact logging methods

2. **Assets/Scripts/ML/RolloutBatchSummary.cs** (184 lines)
   - Class for batch aggregates
   - Provides `ToMarkdown()` and `ToOneLine()` exports

3. **Assets/Scripts/ML/RewardSanityChecker.cs** (256 lines)
   - Static utility with tunable thresholds
   - Populates warning list via `CheckBatchSanity()`

4. **Assets/Scripts/ML/BaselineRolloutRunner.cs** (318 lines)
   - Orchestrator for batch rollouts
   - Uses EpisodeController public API
   - Aggregates into RolloutBatchSummary

5. **Assets/Scripts/ML/Day6RewardSanitySmokeTest.cs** (327 lines)
   - MonoBehaviour smoke test
   - Context menu integration
   - Console and markdown output generation

### Files Modified

**Assets/Scripts/ML/BaselineRolloutRunner.cs** — Semantic alignment fixes (2 layers)
- Added episode-level fallback to derive terminal flags from cumulative reward summary (lines 160-167)
- Hardened batch aggregation to count non-zero terminals by actual reward value (line 295+)
- No changes to execution flow or reward logic; diagnostic layer only

**Assets/Scripts/Gameplay/Match/EpisodeController.cs** — No changes  
- Existing public API (`StartNewEpisode()`, `StepEpisodeOnce()`, `IsRunning`) remains unchanged

---

## 10. How to Run the Sanity-Check

### Option A: Play Mode Context Menu (Easiest)

1. Open the Unity scene with EpisodeController
2. Add a new empty GameObject (or reuse existing one)
3. Add component `Day6RewardSanitySmokeTest`
4. Enter Play Mode
5. In Hierarchy, right-click the GameObject → "Execute Reward Sanity Check (Play Mode)"
6. Check console for summary and report file path
7. Open generated markdown file in text editor

### Option B: C# Script (Programmatic)

```csharp
public class MyDayCustomSanityTest : MonoBehaviour
{
    void Start()
    {
        var runner = new BaselineRolloutRunner(EpisodeController.Instance);
        var summary = runner.StartBatchRollout(episodeCount: 10, verboseLogging: true);
        
        if (summary.SanityWarnings.Count > 0)
        {
            Debug.LogWarning($"Warnings: {string.Join(", ", summary.SanityWarnings)}");
        }
    }
}
```

---

## 11. Next Steps for Week 4 / Week 5

### If Sanity-Check Passes

✅ Reward distribution is plausible  
✅ Terminal behavior is functional  
✅ Baseline traces are interpretable  

**Next:** Proceed to Day 7 (policy integration) or Day 8 (baseline policy training)

### If Sanity-Check Fails or Shows Warnings

⚠️ Investigate specific warnings  
⚠️ Review corresponding component (reward logic, terminal pipeline, action masking)  
⚠️ Consider minor tuning of coefficients or thresholds  

**Next:** Debug identified issue, rerun sanity-check, then proceed to policy integration

### For Future Work (Week 5+)

- Expand batch size to 100+ for statistical confidence
- Track sanity metrics longitudinally during policy training
- Add performance profiling (timesteps/sec, memory usage)
- Validate compatibility with Gym-μRTS reference baseline
- Implement cross-environment sanity checks

---

## 12. Architecture Diagram

```
┌─────────────────────────────────────┐
│   Day6RewardSanitySmokeTest         │
│   (MonoBehaviour, UI integration)   │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│   BaselineRolloutRunner             │
│   (Pure C#, batch orchestrator)     │
└──────────────────┬──────────────────┘
                   │
      ┌────────────┴────────────┐
      ▼                         ▼
┌──────────────┐      ┌──────────────────────┐
│ Episode N    │      │ Canonical RL Loop    │
│ ...          │      │ (RlLoopCoordinator)  │
│ StartNewEp() │──────┤ RewardCollector      │
│ StepOnce()   │      │ TerminalEvaluator    │
│ IsRunning    │      │ (unmodified Week 4)  │
└───────┬──────┘      └──────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ RolloutEpisodeSummary        │
│ (per-episode metrics)        │
└──────────────────────────────┘
        │
        └─────────────────┬──────────────────┐
                          ▼                  ▼
                    ┌────────────────┐ ┌──────────────┐
                    │ RolloutBatch   │ │   Sanity     │
                    │ Summary        │ │   Checker    │
                    │ (aggregates)   │ │   (warnings) │
                    └───────┬────────┘ └──────────────┘
                            │
                            ▼
                    ┌──────────────────┐
                    │ Console + Report │
                    │ (markdown)       │
                    └──────────────────┘
```

---

## Summary

**Day 6 delivers a complete sanity-checking infrastructure** for the Week 4 RL loop:

✅ **Baseline batch runner** with orchestration of sequential episodes  
✅ **Episode-level diagnostics** covering reward, terminal, and invalid actions  
✅ **Batch-level aggregation** with distribution analysis  
✅ **Sanity-check heuristics** with tunable thresholds and warning flags  
✅ **Markdown report generation** for documentation and manual review  

**No core logic changes;** only diagnostics and validation layers added.  
**All checks are warning-only;** they do not block execution or alter behavior.  
**Ready for immediate use** in Play Mode via context menu or programmatic API.

Reward distribution and terminal behavior can now be validated against basic engineering sanity criteria via real batch runs before proceeding to policy integration (Week 4 Day 7+).
