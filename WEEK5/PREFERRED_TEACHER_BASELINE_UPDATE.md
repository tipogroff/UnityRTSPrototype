# PREFERRED_TEACHER_BASELINE_UPDATE

Date (UTC): 2026-04-22  
Status: Post-correction baseline switch — canonical references updated

---

## Baseline switch summary

```
baseline_switch          = true
switch_date_utc          = 2026-04-22
previous_preferred       = teacher_adapted_day5_first_nonrandom_meaningful
new_preferred            = teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z
switch_reason            = corrective rerun validated root-cause diagnosis and downstream comparison result=better
comparison_artifact      = python/week5_teacher/teacher_exports/COMPARE_TEACHER_BATCHES_DAY5_corrective_cpu_vs_preferred.json
```

---

## A. What is being compared

### Old lineage (previous preferred — now historical baseline)

| Artifact layer | Path / label |
|---|---|
| Raw rollout batch | `teacher_rollouts/teacher_raw_debug_day5_first_nonrandom_20260416T163458Z` |
| Adapted batch | `teacher_exports/teacher_adapted_day5_first_nonrandom_meaningful` |
| Validation report | `teacher_adapted_day5_first_nonrandom_meaningful/strict_validation_day5.json` |
| BC-ready package | `teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_first_nonrandom_meaningful_20260421T103641Z` |
| Loader dry run | `…/dry_run_bc_loader_report.json` (pass, 2026-04-21) |

Policy source for old lineage: `sb3:ppo:teacher_sb3_ppo.zip`  
This was the first non-random PPO checkpoint rollout with 2000-step single episode, debug mode, seed 7/8/9.

### New lineage (corrected preferred — now canonical)

| Artifact layer | Path / label |
|---|---|
| Raw rollout batch | `teacher_rollouts/teacher_raw_training_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z` |
| Adapted batch | `teacher_exports/teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z` |
| Validation report | `…/strict_validation_day5.json` (0 hard failures, 25 warnings) |
| BC-ready package | `teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z` |
| Loader dry run | `…/dry_run_bc_loader_report.json` (pass, 2026-04-22) |

Policy source for new lineage: `sb3:ppo:teacher_sb3_ppo.zip` (same checkpoint)  
Rollout used corrective Day 3 rollout regime: training mode, 8 episodes, 2000-step limit, multi-opponent pool (coacAI / workerRushAI / lightRushAI / passiveAI), per_episode sampling, seed 17/18/19, CPU backend (emergency_fallback_auto).

---

## B. Why the baseline update was needed

### History of comparison events

1. **First comparison (2026-04-19):**  
   Old preferred (`first_nonrandom_meaningful`) vs. new hardened teacher (`stronger_teacher_20260419T141742Z`).  
   Result: `not_better`. Old preferred remained canonical.

2. **Root cause diagnosis (2026-04-22):**  
   New hardened `v2` rollout (`20260422T074106Z`) was compared against old preferred.  
   Result: `mixed`. Improved some metrics (remap_to_noop_share, class_imbalance, inactive_branch_anomaly_share), degraded others (usable_samples, production_actions_survived_share, warning count). Old preferred remained canonical.

3. **Corrective rerun (2026-04-22):**  
   Root cause was identified as rollout-regime bias: the original new-lineage rollout used a single-episode single-opponent minimal regime that did not activate the hardened teacher's multi-opponent diversity. A corrective rollout was run with:  
   - 8 episodes instead of 1  
   - 2000-step limit per episode  
   - multi-opponent pool: coacAI, workerRushAI, lightRushAI, passiveAI  
   - per_episode opponent sampling  
   
   Result: `better`. Preferred candidate switched to corrective lineage.

This was not a new teacher training. The corrective rerun used the same checkpoint (`teacher_sb3_ppo.zip`), but ran the Day 3 rollout under the correct multi-episode multi-opponent regime that the hardened teacher was designed to be evaluated against.

---

## C. Detailed comparison — old vs. new

### C.1 Training and checkpoint provenance

| Property | Old lineage | New lineage |
|---|---|---|
| Policy source | `sb3:ppo:teacher_sb3_ppo.zip` | `sb3:ppo:teacher_sb3_ppo.zip` (same) |
| Checkpoint provenance | Earlier PPO training run | Hardened training run (`day5_teacher_hardened_serious_v2`) |
| Policy architecture | SB3 PPO | SB3 PPO (MaskablePPO-compatible path) |
| Teacher training timesteps | Not specified in batch metadata | 100,000 (hardened serious v2) |
| Rollout backend | `emergency_fallback_auto` | `emergency_fallback_auto` (same) |

### C.2 Day 3 raw rollout regime

| Property | Old lineage | New lineage (corrective) |
|---|---|---|
| Batch mode | `debug` | `training` |
| Episode count | 1 | 8 |
| Total steps | 2,000 | 4,040 |
| Mean episode length | 2,000.0 | 505.0 |
| Mean episode return | 0.0 | 0.0 |
| Reward mean | 0.0 | 0.0 |
| Terminal type | terminated ×1 | terminated ×8 |
| Opponent pool | not specified (single static) | coacAI, workerRushAI, lightRushAI, passiveAI |
| Opponent sampling | static | per_episode |
| Mask recording mode | explicit | explicit |
| Available mask steps | 2,000 / 2,000 | 4,040 / 4,040 |
| Seeds | 7 / 8 / 9 | 17 / 18 / 19 |

**Key structural difference:** The old lineage was a single 2000-step episode in debug mode against an unspecified/default opponent. The new corrective lineage used 8 shorter episodes (mean 505 steps, all terminated) with per-episode opponent rotation across 4 AI types. Both used the emergency_fallback_auto backend (gym.make preferred but fell back to `MicroRTSGridModeVecEnv` due to NameNotFound).

### C.3 Day 4 adapter outcome

| Property | Old lineage | New lineage (corrective) |
|---|---|---|
| Episodes adapted | 1 | 8 |
| Usable samples | 2,000 | 4,040 |
| Dropped samples | 0 | 0 |
| Conversion loss share | 0.0 | 0.0 |
| remap_to_noop_count | 230,000 | 218,192 |
| remap_to_noop_share | **0.19965** | **0.09376** ✓ (−53%) |
| semantic_weakening_share | 1.0 | 1.0 (same) |
| observation_signal_loss_share | 0.0 | 0.0 (same) |
| production_actions_survived_share | **0.600** | **0.585** (−2.5%) |
| Source branch layout | [6,4,4,4,4,7,49] | [6,4,4,4,4,7,49] (same) |
| Target branch layout | [6,4,4,4,4,4,9] | [6,4,4,4,4,4,9] (same) |
| Conversion debug jsonl | present | not generated |

### C.4 Day 4 action type distribution comparison

| Action type | Old lineage share | New lineage share | Change |
|---|---|---|---|
| 0 (noop) | 0.3715 | 0.4011 | +2.96 pp |
| 1 (move) | 0.1580 | 0.3987 | +24.07 pp ⬆ |
| 2 (harvest) | 0.1701 | 0.0521 | −11.80 pp ⬇ |
| 3 (return) | 0.1771 | 0.0597 | −11.74 pp ⬇ |
| 4 (produce) | 0.1042 | 0.0538 | −5.04 pp ⬇ |
| 5 (attack) | 0.0191 | 0.0347 | +1.56 pp ⬆ |
| imbalance ratio (max:min) | **19.45** | **11.55** ✓ (−41%) |

The corrective rollout resulted in a substantially higher move action share and lower harvest/return share. This reflects multi-opponent diversity: against aggressive opponents (workerRushAI, coacAI), the hardened teacher generates more movement and combat actions relative to economic actions. The noop share increased slightly. Attack share nearly doubled. Imbalance ratio dropped from 19.45 to 11.55.

### C.5 Day 5 validation outcome

| Property | Old lineage | New lineage (corrective) |
|---|---|---|
| Validation status | pass | pass |
| Hard failures | 4 (unit_type one-hot, current_action one-hot) | 0 ✓ |
| Total warnings | 4 | 25 |
| Warning types | inactive_branch_nonzero, categorical_soft_sum ×2, semantic_weakening | same categories ×8 episodes |
| warnings_per_episode | 4.0 | **3.125** ✓ (−21.9%) |
| Episodes scanned | 1 | 8 |
| inactive_branch_anomaly_share | **0.04514** (medium severity) | **0.02604** ✓ (low severity, −42%) |
| inactive_branch_warning_severity | medium | **low** ✓ |

**Critical improvement:** The old lineage had 4 hard failures (observation one-hot sum mismatches in unit_type and current_action slices). The new corrective lineage has 0 hard failures. Both produce the same warning categories, but the new lineage produces fewer warnings per episode and achieves low (vs. medium) inactive branch anomaly severity.

**Warning count comparability note:** The 25 total warnings vs. 4 total warnings is not directly comparable because the new lineage ran 8 episodes (one warning-set per episode per check). The per-episode rate (3.125 vs. 4.0) is the comparable metric and shows improvement.

### C.6 Day 6 BC-ready packaging

| Property | Old lineage | New lineage (corrective) |
|---|---|---|
| Packaging status | success | success |
| BC-ready run directory | `day6_bc_ready_…first_nonrandom_meaningful_20260421T103641Z` | `day6_bc_ready_…corrective_sl2000_ep8_cpu_20260422T085809Z` |
| Schema version | `day6.bc_ready.v1` | `day6.bc_ready.v1` (same) |
| Total samples | 2,000 | **4,040** ✓ (+102%) |
| Train split | 1,804 | **3,650** ✓ |
| Validation split | 196 | **390** ✓ |
| Debug split | 256 | 256 (same) |
| has_optional_mask | false | false (same) |
| Loader dry run status | pass | pass |
| input_shape per sample | [24, 24, 27] | [24, 24, 27] (same) |
| target_shape per sample | [576, 7] | [576, 7] (same) |
| branch_sizes | [6,4,4,4,4,4,9] | [6,4,4,4,4,4,9] (same) |
| Packaging warnings | [] | [] (same) |

The new lineage BC-ready package is fully schema-compatible with the old lineage package. All shapes, branch sizes, and split structure are identical. The new package contains 2× more samples.

---

## D. Why the new lineage is now preferred

The following improvements in the new corrective lineage drove the `better` comparison result:

1. **Zero hard validation failures** (vs. 4 hard failures in old lineage). This removes a downstream BC training concern around observation contract compliance.

2. **remap_to_noop_share reduced from 0.1997 to 0.0938** (−53%). Less semantic pressure from source-to-target action gap. The hardened teacher under multi-opponent regime generates action distributions that convert more cleanly to the Unity MVP action space.

3. **class_imbalance_ratio reduced from 19.45 to 11.55** (−41%). Better action diversity means less weighting/oversampling burden in BC training. Action type 1 (move) increased from 15.8% to 39.9%, partially displacing the extreme noop dominance in the old lineage.

4. **inactive_branch_anomaly_share reduced from 0.04514 to 0.02604** (−42%), severity downgraded from medium to low. Decoder robustness concern reduced.

5. **usable_samples doubled from 2,000 to 4,040**. Larger training corpus for BC without additional teacher training.

6. **warnings_per_episode improved from 4.0 to 3.125** (−21.9%). Fewer anomalies per episode at comparable evaluation criteria.

7. **Opponent diversity in rollout**. The corrective lineage covers 4 opponent AIs with per-episode sampling, providing behavioral diversity that better represents the range of game states the hardened teacher policy navigates. This is structurally superior for BC generalization.

**One trade-off retained:** `production_actions_survived_share` slightly degraded from 0.600 to 0.585. This is a minor reduction (−2.5 percentage points) and was judged acceptable given the improvements across all other metrics. The comparison decision explicitly captured this as the only worsened metric.

---

## E. What is still not proven

The following limitations remain after the baseline switch and must not be smoothed over in dissertation Chapter 3:

1. **BC success is not proven.** The new preferred BC-ready package provides structurally better input to Week 6, but whether a student policy will learn from it is not known. Week 6 must validate BC learning.

2. **Direct weight transfer remains blocked.** Architecture mismatch between Gym-microRTS SB3 policy and Unity ML-Agents is not resolved. The teacher provides observation/action pairs only.

3. **Mask semantics are optional/diagnostic.** Both old and new BC-ready packages have `has_optional_mask=false`. Mask absence is not a blocker for basic BC but means the student cannot use teacher mask guidance during training.

4. **Semantic weakening share is 1.0 in both lineages.** Every adapted sample involves some semantic weakening via remap-to-noop or action branch truncation. This is a design-level constant of the Day 4 adapter and is not resolved by this baseline switch.

5. **Reward signal is absent from the BC package.** Both lineages show `mean_episode_return=0.0` (raw Gym reward not captured by the export path). BC training relies on imitation only, not reward-augmented supervised learning.

6. **observation one-hot soft-sum warnings persist in the new lineage.** The `categorical_soft_sum` warnings (unit_type and current_action) are present in all 8 episodes and represent known observation contract ambiguity. They are warnings, not hard failures, but they are still present.

7. **Teacher quality is not externally benchmarked.** The `teacher_sb3_ppo.zip` checkpoint has not been evaluated against baseline AIs with quantitative win-rate measurement. The "hardened" label refers to training regime hardening, not externally validated play quality.

---

## F. Canonical Week 6 starting point (updated)

### F.1 New canonical BC-ready input for Week 6

```
python/week5_teacher/teacher_exports_bc/
  day6_bc_ready_teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z/
    bc_train.npz       (3,650 samples)
    bc_validation.npz  (390 samples)
    bc_debug.npz       (256 samples)
    bc_manifest.json
    bc_summary.json
    dry_run_bc_loader_report.json
```

Schema: `day6.bc_ready.v1`  
input shape per sample: `[24, 24, 27]`  
target shape per sample: `[576, 7]`  
branch sizes: `[6, 4, 4, 4, 4, 4, 9]`

### F.2 New canonical adapted source for Week 6

```
python/week5_teacher/teacher_exports/
  teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z/
```

### F.3 Old preferred — now historical baseline only

```
python/week5_teacher/teacher_exports_bc/
  day6_bc_ready_teacher_adapted_day5_first_nonrandom_meaningful_20260421T103641Z/
```

Status: retained as previous baseline / comparison reference.  
Do not delete. Do not use as default input for Week 6.

### F.4 Summary of all BC-ready runs (all retained)

| Run | Total samples | Train | Status |
|---|---|---|---|
| `day6_bc_ready_…first_nonrandom_meaningful_20260421T103641Z` | 2,000 | 1,804 | Historical baseline |
| `day6_bc_ready_…hardened_v2_teacher_candidate_20260422T074106Z` | — | — | Intermediate comparison run |
| `day6_bc_ready_…corrective_sl2000_ep8_cpu_20260422T085809Z` | 4,040 | 3,650 | **Canonical preferred (Week 6 input)** |

---

## G. Why the old baseline is still kept

The old preferred lineage (`first_nonrandom_meaningful`) is not deleted because:

1. It represents the first validated end-to-end pipeline run with a real (non-random) teacher policy.
2. It serves as the historical anchor point for baseline comparison. Without it, the `better` comparison result for the corrective lineage has no reference.
3. It is referenced in `COMPARE_TEACHER_BATCHES_DAY5.md` and `COMPARE_TEACHER_BATCHES_DAY5_corrective_cpu_vs_preferred.json` as the explicit comparison target.
4. If BC training on the new lineage fails in Week 6, the old lineage remains available for ablation comparison.
5. Dissertation Chapter 3 traces the lineage of comparison decisions; removing the old baseline would break that traceability chain.

---

## H. Reproducibility reference

To reproduce the corrective rollout from scratch (same checkpoint, same regime):

```powershell
$env:JAVA_HOME='C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME/bin;$env:Path"

python/week5_teacher/.venv_day2_py39/Scripts/python.exe `
  python/week5_teacher/run_teacher_rollout.py `
  --episodes 8 `
  --batch-mode training `
  --batch-label day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu `
  --env-id MicrortsSelfPlayShapedReward-v1 `
  --map-path maps/24x24/basesWorkers24x24.xml `
  --backend-mode allow_fallback `
  --opponent-pool coacAI,workerRushAI,lightRushAI,passiveAI `
  --opponent-sampling per_episode `
  --seed 17 `
  --rollout-step-limit 2000 `
  --write-jsonl never
```

Note: 2000-step rollout episodes may exceed 30-minute terminal timeout. Use async monitoring.

---

*This document was created as part of the post-correction baseline update on 2026-04-22.*  
*It is intended as a primary reference for Week 6 handoff and dissertation Chapter 3 documentation.*
