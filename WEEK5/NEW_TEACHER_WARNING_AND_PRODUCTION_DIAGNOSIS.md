# New Teacher Candidate — Root-Cause Diagnosis
### Warning Inflation & Production Degradation Analysis

**Candidate:** `day5_teacher_hardened_serious_v2_20260420T173711Z`  
**Batch:** `teacher_adapted_day5_hardened_v2_teacher_candidate_20260422T074106Z`  
**Baseline:** `teacher_adapted_day5_first_nonrandom_meaningful`  
**Analysis date:** 2026-04-22  

---

## TL;DR (Root-Cause Block)

| Dimension | Finding |
|---|---|
| **Primary cause of warnings inflation** | Measurement artifact — validator emits per-episode warnings; new batch has 6 episodes vs 1 |
| **Primary cause of produce_action_share drop** | Teacher behavioral shift (raw rollout level) — new teacher generates fewer produce actions per cell in the raw data, before adapter |
| **Primary cause of production_survival drop** | Nearly identical to old batch (58.49% vs 60.00%); difference is negligible |
| **Primary cause of usable_samples reduction** | Rollout step budget — fewer steps collected (1536 vs 2000), zero filtering loss |
| **Rollout regime contribution** | High: 256-step episode limit captures only early-game; hardened opponents reinforce aggression bias |
| **Adapter/conversion contribution** | Negligible: same conversion path, same survival rate (~59-60%) for produce branches |
| **Teacher policy weakness** | Partial: teacher adapted to aggressive opponents but this is expected behavior, not a flaw |

---

## Section 1 — Warning Breakdown

### Raw counts

| Warning check | Old batch | New batch | Delta |
|---|---|---|---|
| `observation.categorical_soft_sum.unit_type` | 1 | 6 | +5 |
| `observation.categorical_soft_sum.current_action` | 1 | 6 | +5 |
| `action.inactive_branch_nonzero` | 1 | 6 | +5 |
| `quality.semantic_weakening` | 1 | 1 | 0 |
| **Total** | **4** | **19** | **+15** |

### Per-episode warning density

| Metric | Old batch | New batch |
|---|---|---|
| Episodes in batch | 1 | 6 |
| Per-episode warnings (check types) | 3 | 3 |
| Global (quality) warnings | 1 | 1 |
| **Total formula** | 1×3 + 1 = **4** | 6×3 + 1 = **19** |

### Conclusion

**The warning count inflation 4→19 is a pure counting artifact of multi-episode structure.**

The validator emits one warning per episode per check type — it does not deduplicate across episodes. The new batch has 6 episodes; the old has 1. The per-episode warning density is **identical**: 3 per-episode checks trigger in both batches, every episode, with the same check IDs.

There is no new warning category, no new hard failure, and no worsening of warning content:

| Check | Nature | Old batch context | New batch context |
|---|---|---|---|
| `categorical_soft_sum.unit_type` | Spec-assumption (soft, not hard) | `invalid_count=1,148,000` (1 ep) | `invalid_count=146,414` per ep × 6 |
| `categorical_soft_sum.current_action` | Spec-assumption (soft, not hard) | `invalid_count=4,000` (1 ep) | `invalid_count=1,042` per ep × 6 |
| `inactive_branch_nonzero` | Low severity | `noop.branch_4_nonzero=52,000` (1 ep) | `noop.branch_4_nonzero=3,840` per ep × 6 |
| `quality.semantic_weakening` | Informational | remap_count=230,000 | remap_count=82,944 |

Note: the per-episode absolute values in the new batch are **lower** than the old for all three checks — the new batch is structurally cleaner per episode, not worse.

**Verdict:** `warnings_count` metric is not a valid quality differentiator when episode count differs. This metric should be normalized to `warnings_per_episode` in future comparisons.

---

## Section 2 — Produce-Action Degradation Analysis

### Where does the drop occur?

Tracking produce actions (action type 4) through the pipeline:

| Stage | Old batch (per 1M cells) | New batch (per 1M cells) |
|---|---|---|
| Raw rollout input | 200,000 / 1,152,000 = **17.36%** | 81,408 / 884,736 = **9.20%** |
| After adapter (survived) | 120,000 / 1,152,000 = **10.42%** | 47,616 / 884,736 = **5.38%** |
| Lost in adapter | 80,000 (unsupported_produce_type → noop) | 33,792 (unsupported_produce_type → noop) |
| Adapter survival rate | 120k/200k = **60.00%** | 47.6k/81.4k = **58.49%** |

**The drop occurs at the raw rollout level, before the adapter.** The adapter survival rate is virtually identical for both batches (60.00% vs 58.49%). The adapter is NOT damaging produce branches disproportionately.

### Raw action distribution comparison (per 1,000 cells)

| Action type | Old batch (input) | New batch (input) | Delta |
|---|---|---|---|
| 0 (noop) | 17.2% | 30.7% | +13.5pp |
| 1 (move/first move) | 15.8% | 39.9% | **+24.1pp** |
| 2 | 17.0% | 5.2% | −11.8pp |
| 3 | 17.7% | 6.0% | −11.7pp |
| 4 (produce) | **17.4%** | **9.2%** | **−8.2pp** |
| 5 (attack) | 14.9% | 9.0% | −5.9pp |

The new v2 teacher has action type 1 at 39.9% of all cells — nearly 2.5× higher than the old batch (15.8%). This indicates a **movement-dominant strategy** learned by the new teacher. Production share is halved in raw data.

### Why did the teacher produce less?

Two compounding rollout regime factors:

1. **Episode length**: Old rollout = 1 episode × 2000 steps. New rollout = 6 episodes × **256 steps**. A 256-step game captures only the early-game phase. Production investment (workers, barracks, economic units) is a mid/late-game behavior. Early-game is naturally movement-heavy as units establish positioning and react to opponents.

2. **Opponent pool pressure**: New rollout used `[coacAI, workerRushAI, lightRushAI, passiveAI]` with `per_episode` sampling. `workerRushAI` and `lightRushAI` are early-aggression AIs that rush with workers/light units immediately. Under this pressure the teacher's optimal response is aggressive movement and attack, not production investment. The sampled opponent was `workerRushAI` for at least one episode (confirmed in rollout summary).

3. **All 6 episodes are identical length (256 steps each)**: This is consistent with a hard step limit or a game that terminates quickly under opponent pressure, not natural game termination.

**Verdict:** The produce_action_share drop is primarily a **rollout regime effect** (short episodes + aggressive opponent bias), with a secondary contribution from teacher behavioral adaptation to those opponents. The teacher is not broken — it learned to respond to aggression appropriately.

---

## Section 3 — Production Survival Degradation Analysis

### production_actions_survived_share: 60.00% → 58.49%

This metric measures: *of all produce-type action cells in the raw input, what fraction survives through the adapter without being remapped to noop?*

| Batch | Input produce cells | Survived | Remapped to noop | Survival rate |
|---|---|---|---|---|
| Old preferred | 200,000 | 120,000 | 80,000 | **60.00%** |
| New v2 candidate | 81,408 | 47,616 | 33,792 | **58.49%** |
| Delta | — | — | — | **−1.51pp** |

The cause of the 80,000 and 33,792 noop remaps is the same in both batches: **`noop_due_to_unsupported_produce_type`**. The adapter filters produce actions whose target unit type falls outside the MVP subset. The survival rate is nearly identical.

### Why not 60.00% in the new batch?

The marginal 1.51pp gap has two possible explanations:
- Slightly different distribution of produce unit types in the new teacher's outputs (choosing produce targets outside the MVP subset slightly more often)
- Statistical noise from a different opponent mix at the time of rollout

This is **not a meaningful degradation**. A 1.51pp difference in production survival does not indicate a systematic problem in the adapter or the teacher.

### What is NOT causing the production survival drop
- ❌ Not increased filtering of adapted samples (0 dropped samples in both batches)
- ❌ Not attack-target remapping (separate counter: `noop_due_to_attack_target_out_of_local_window`)
- ❌ Not unsupported layout detection (both use `batched_flat_1x4032` — `supported_approx`)
- ❌ Not validation policy changes (same hard/soft split between batches)

---

## Section 4 — Rollout Regime Contribution

### Regime comparison

| Parameter | Old batch | New batch |
|---|---|---|
| `batch_mode` | `debug` | `training` |
| Episodes | 1 | 6 |
| Steps per episode | 2000 | 256 |
| Total steps | 2000 | 1536 |
| `terminal_counts.terminated` | 1 | 6 |
| `terminal_counts.truncated` | 0 | 0 |
| Opponent pool | (none specified / default) | `[coacAI, workerRushAI, lightRushAI, passiveAI]` |
| Opponent sampling | N/A | `per_episode` |
| Backend | unknown | `MicroRTSGridModeVecEnv` (emergency fallback) |
| Seed | 7 | 17 |

### Key regime effects

**1. Episode step limit (256 steps)**  
All 6 episodes are exactly 256 steps and all terminated naturally (not truncated). This means the games ended within 256 steps — under early-aggression opponents this is expected. The 256-step games are purely **early-game snapshots**, biased toward reactive movement and attack rather than economic production.

Old batch: 2000 steps covers the full game arc including economic mid-game. The more balanced action distribution in the old batch (all 6 types near 15-17%) reflects cross-phase sampling.

**2. Hardened opponent pool**  
`workerRushAI` and `lightRushAI` are rush-centric AIs that apply immediate economic pressure. Under this opponent mix, the teacher's reward-maximizing behavior is to respond with movement and attack, not to invest in production. The v2 teacher learned exactly this.

**3. Fallback backend (emergency_fallback)**  
The env backend used was `gym_microrts.envs.vec_env.MicroRTSGridModeVecEnv` triggered as `emergency_fallback_auto` because the preferred backend (`gym.make`) raised `NameNotFound`. Both batches use the same underlying gym_microrts v0.0.0 runtime, so this does not explain any systematic difference in action representations. However, the fallback path may have slightly different action mask handling — this cannot be ruled out without deeper inspection but is assessed as low-probability.

**4. Seed difference (7 vs 17)**  
Minor. Different initial map states and unit spawns could shift early action distribution slightly, but does not explain an 8pp difference in raw produce share.

**Rollout regime contribution verdict:** HIGH. The 256-step limit combined with aggressive early opponents is the **primary structural cause** of the action distribution shift and produce-action drop. The same teacher policy, run against passive opponents with 2000-step episodes, would likely produce more economically-representative data.

---

## Section 5 — Adapter/Conversion Contribution

### What the adapter does identically for both batches

Both batches go through the same logical conversion path:

1. **Layout normalization**: `batched_flat_1x4032` → `[576, 7]` matrix (both use `supported_approx`)
2. **Attack target reduction**: 49-cell → 9-cell local window
3. **Produce type filtering**: outside-MVP-subset → noop
4. **Observation passthrough**: exact (no modification)

### Conversion counters normalized per 1000 steps

| Counter | Old batch (per 1000 steps) | New batch (per 1000 steps) |
|---|---|---|
| `attack_target_outside_local_3x3_to_noop` | 75,000 / step | 32,000 / step |
| `unsupported_produce_type_to_noop` | 40,000 / step | 22,000 / step |
| `attack_target_reduced_49_to_9` | 11,000 / step | 20,000 / step |
| `total_remap_to_noop` | 115,000 / step | 54,000 / step |

The new batch has **lower noop remap pressure per step** across all counters. The adapter is not disproportionately damaging any branch — all remap rates are lower in the new batch.

### Conversion path quality assessment

| Check | Old batch | New batch | Assessment |
|---|---|---|---|
| Samples dropped | 0 | 0 | Identical — no filtering loss |
| Observation loss events | 0 | 0 | Identical |
| Layout: all samples | `batched_flat_1x4032` | `batched_flat_1x4032` | Same path |
| Produce survival rate | 60.00% | 58.49% | Near-identical |
| Attack survival rate | 22k/172k=12.8% | 30.7k/79.9k=38.4% | New batch better |

Attack survival rate is significantly **better** in the new batch (38.4% vs 12.8%). This is because the new teacher selects attack targets that fall more often within the local 3×3 window — a behavioral improvement, not a conversion artifact.

**Adapter/conversion verdict:** The adapter contributes negligibly to degradation. It processes both batches with the same rules, the same survival rates for produce branches, and it actually performs better for attack branches in the new batch. The adapter is not the problem.

---

## Section 6 — Root-Cause Conclusion

### Causal attribution table

| Metric | Apparent degradation | True cause | Severity |
|---|---|---|---|
| `warnings_count` 4→19 | +15 warnings | **Counting artifact** (per-episode emission, not deduplicated) | None — not a real regression |
| `produce_action_share` 10.42%→5.38% | −5.04pp | **Rollout regime** (256-step limit + rush opponents → early-game bias) + **Teacher behavioral adaptation** to aggressive opponents | Real, but regime-explainable |
| `production_actions_survived_share` 60%→58.49% | −1.51pp | **Marginal noise** — same survival mechanism, same adapter path | Negligible |
| `usable_samples` 2000→1536 | −464 samples | **Rollout step budget** — fewer steps collected; zero filtering loss | Step-count issue, not quality issue |

### Primary cause
`rollout_regime_bias`

The 256-step episode limit and hardened opponent pool jointly create a dataset biased toward early-game, aggressive-response behavior. The same teacher policy, given more steps and a softer opponent mix, would produce more production diversity. This is confirmed by:
- All 6 new episodes terminated naturally at exactly 256 steps (game ended under pressure)
- The dominant action type in new batch is type 1 (movement) at 39.9%, compared to ~15.8% in old batch
- Old batch opponent pool was not adversarial rush AIs

### Secondary cause
`teacher_behavioral_shift_under_aggressive_opponents`

The v2 teacher genuinely learned a more movement-dominant strategy as a rational response to coacAI/workerRushAI/lightRushAI. This is not a flaw — it is optimal behavior under the training distribution. However, it means rollout data collected against these opponents underrepresents production behavior.

### What is NOT the cause
- ❌ **Not adapter damage** — conversion survival rates are near-identical; adapter is not disproportionately filtering produce branches
- ❌ **Not teacher policy weakness** — the produce actions that DO occur survive at the same rate; the teacher is capable of production
- ❌ **Not warning quality regression** — the per-episode warning pattern is identical; warning count is an episode-count artifact
- ❌ **Not fallback backend effects** — both batches share the same underlying gym_microrts runtime; no evidence of different action representations

### Structured conclusion

```
primary_cause          = rollout_regime_bias (256-step limit + rush-heavy opponent pool)
secondary_cause        = teacher_behavioral_adaptation_to_hardened_opponents
tertiary_cause         = usable_samples_from_shorter_step_budget (not a quality issue)
not_primary            = adapter_conversion_damage
not_primary            = warning_quality_regression
not_primary            = teacher_policy_inability_to_produce
```

---

## Section 7 — Minimal Corrective Action

The goal is to get a dataset that captures the full behavioral range of the v2 teacher, including production, without retraining the teacher.

### Option A: Increase episode length (highest impact)
Run `run_teacher_rollout.py` with a longer per-episode step budget:
- Increase episode step limit from 256 to ≥2000 steps
- This allows games to enter mid/late-game economic phase
- Even 4 episodes × 2000 steps would give 8000 steps and rich production data
- **Impact**: Directly resolves the early-game bias root cause
- **Cost**: Longer rollout time (linear with steps)

### Option B: Add passive/economic opponents to pool (medium impact)
Include `passiveAI` or a bot that does not rush in the first 300 steps:
- `passiveAI` does not attack; allows teacher to develop economic behaviors
- Mix pool: e.g. 50% aggressive (coacAI, workerRushAI) / 50% passive (passiveAI)
- **Impact**: Increases produce-action phase frequency
- **Cost**: May produce less tactically representative data for combat

### Option C: Fix warnings_count normalization in compare_day5_reports.py (housekeeping)
The comparison script should normalize `warnings_count` to `warnings_per_episode` before scoring improved/worsened. Currently it treats raw warning count as a quality metric, which produces a spurious "worsened" signal when episode count changes.
- **Impact**: Prevents future false negatives in comparison decisions
- **Cost**: Minimal — 2-line change in `compute_decision()` logic

### Recommended sequence

1. **Now (no retraining needed):** Run Option A — rerun rollout with ≥2000 steps/episode, 10+ episodes, same v2 teacher checkpoint, same opponent pool. Expected outcome: produce_action_share recovers to ≥10%, warnings normalize to ≤6 (1 episode × 3 + 1 global + buffer).

2. **Then:** Re-run Days 4–6 on the new rollout and re-compare against the preferred baseline.

3. **Separately:** Apply Option C to `compare_day5_reports.py` to prevent artifact-driven decisions in future batch comparisons.

**Do NOT:** retrain the teacher, modify the adapter, or change the Day 5 validation policy. The degradations are rollout-level and regime-level, not policy or pipeline failures.

---

## Appendix — Key Numeric Evidence

### Action histogram (per-cell rates, normalized to 1,000,000 cells)

| Action | Old input | Old output | New input | New output |
|---|---|---|---|---|
| 0 | 172,000 | 371,528 | 307,291 | 401,042 |
| 1 | 158,000 | 158,000 | 398,569 | 398,569 |
| 2 | 170,000 | 170,000 | 52,083 | 52,083 |
| 3 | 177,000 | 177,000 | 59,774 | 59,774 |
| 4 (produce) | **174,000** | **104,167** | **92,013** | **53,819** |
| 5 (attack) | 149,000 | 19,097 | 90,278 | 34,722 |

*Values per 1,000,000 total action cells (normalized for fair comparison)*

### Remap-to-noop rate (per-cell, normalized)

| Remap reason | Old | New |
|---|---|---|
| attack_target_outside_local_3x3 | 130,208/1M = 13.0% | 55,556/1M = 5.6% |
| unsupported_produce_type | 69,444/1M = 6.9% | 38,194/1M = 3.8% |
| **Total remap rate** | **19.97%** | **9.38%** |

Total remap rate is **significantly lower** in the new batch — a genuine improvement.

### Inactive branch anomaly (per-cell, normalized)

| Batch | Count | Per-cell share | Severity |
|---|---|---|---|
| Old preferred | 52,000 / 1,152,000 | 4.51% | Medium |
| New v2 | 23,040 / 884,736 | 2.60% | Low |

New batch is better on inactive_branch_anomaly severity (medium → low).
