# Gridnet 100k Rollout A/B Review

**Checkpoint**: `gridnet_100k_20260427T221123Z/agent_final.pt`  
**Policy**: Gridnet Branch B PPO, 100k training steps  
**Review type**: Pre-BC rollout quality gate — raw export + adapter dry run  
**Scope**: Gym-side only. No Unity runtime, no BC encoder, no teacher-ready declaration.

---

## 1. Rollout Export

Exporter: `python/week5_teacher_gridnet/export_gridnet_teacher_rollout.py`  
Output format: `episode_*.npz` + `batch.summary.json` (Day 3 adapter contract)  
JVM constraint: Single fixed opponent per process (no per-episode opponent switching).

| Parameter | Batch A (det) | Batch B (stoch) |
|-----------|---------------|-----------------|
| batch_label | `gridnet_100k_det_ab` | `gridnet_100k_stoch_ab` |
| deterministic | true | false |
| episodes | 4 | 4 |
| max_steps | 512 | 512 |
| opponent | randomBiasedAI | randomBiasedAI |
| total steps exported | 2048 | 2048 |

---

## 2. Episode Returns

| Episode | Det return | Stoch return |
|---------|-----------|--------------|
| 0 | 2.0 | 12.0 |
| 1 | 2.0 | 19.0 |
| 2 | 2.0 | 15.0 |
| 3 | 2.0 | 5.0 |
| **Mean** | **2.0** | **12.75** |
| **Std** | **0.0** | **5.3** |

Deterministic returns are completely flat (no variance) — consistent with an argmax policy
that outputs the same action everywhere. Stochastic returns are 6× higher on average,
with meaningful variance, indicating the stochastic sampling explores different strategies.

---

## 3. Input Action Distribution (per-cell across grid, 2048 steps × 576 cells = 1,179,648 cell-actions)

| Action type | Det count | Det share | Stoch count | Stoch share |
|-------------|-----------|-----------|-------------|-------------|
| 0 NoOp | 1,179,360 | **99.97%** | 197,713 | 16.76% |
| 1 Move | 140 | 0.012% | 196,361 | 16.65% |
| 2 Harvest | 8 | 0.001% | 196,013 | 16.62% |
| 3 Return | 0 | 0.000% | 196,232 | 16.64% |
| 4 Produce | 140 | 0.012% | 196,576 | 16.66% |
| 5 Attack | 0 | 0.000% | 196,753 | 16.68% |

**Key observations:**
- **Det**: argmax collapses to NoOp for 99.97% of cell-action slots. The policy's mode is
  overwhelmingly NoOp. Only 288 non-NoOp cell-actions across 2048 steps (0.024%).
- **Stoch**: sampling produces a near-uniform distribution across all 6 action types
  (~196,608 expected per type under pure uniform; actual values deviate by <1%).
  This indicates very high policy entropy — the learned logits are near-zero/equal for
  most active cells. The policy has not yet converged to concentrated action intent.

---

## 4. Adapter Dry Run Results

Adapter: `python/week5_teacher/adapt_teacher_dataset.py` (day4_dataset_adapter)  
Source→Target branch map: `[6,4,4,4,4,7,49]` → `[6,4,4,4,4,4,9]`  
Semantic mismatch points: produce branch 7→4 (types ≥4 → NoOp), attack 49→9 (outside 3×3 → NoOp).

### Batch A — Deterministic

| Metric | Value |
|--------|-------|
| total samples | 2048 |
| exact | 2048 (100%) |
| adapted | 0 (0%) |
| dropped | 0 (0%) |
| semantic_weakened | **0** |
| remapped_to_noop | 0 |
| action layout detected | `matrix_576x7 (supported_exact)` |

**Adapter path: CLEAN.** No semantic remap required because the deterministic policy
never emits produce_type ≥4 or attack targets outside local 3×3 at argmax.
Input and output action histograms are identical.

### Batch B — Stochastic

| Metric | Value |
|--------|-------|
| total samples | 2048 |
| exact | 0 (0%) |
| adapted | 2048 (100%) |
| dropped | 0 (0%) |
| semantic_weakened | **2048 (100%)** |
| remapped_to_noop (cell-actions) | 244,877 of 1,179,648 (**20.76%**) |
| → attack target outside 3×3 | 160,414 cells (13.60%) |
| → unsupported produce type | 84,463 cells (7.16%) |
| attack target reduced (49→9) | 36,339 cells |
| action layout detected | `matrix_576x7 (supported_exact)` |

**Output histogram after remap:**

| Action | Input | Output | Delta |
|--------|-------|--------|-------|
| 0 NoOp | 197,713 | 442,590 | +244,877 (all remaps land here) |
| 1 Move | 196,361 | 196,361 | — |
| 2 Harvest | 196,013 | 196,013 | — |
| 3 Return | 196,232 | 196,232 | — |
| 4 Produce | 196,576 | 112,113 | −84,463 (produce_type ≥4 → NoOp) |
| 5 Attack | 196,753 | 36,339 | −160,414 (attack outside 3×3 → NoOp) |

Post-adaptation NoOp share: 442,590 / 1,179,648 = **37.52%** (input was 16.76%).
Effective non-NoOp share after remap: **62.48%** — still high absolute diversity.

---

## 5. Analysis

### 5.1 Deterministic Batch — BC Quality Assessment

**Verdict: DEGENERATE for BC**

- 99.97% NoOp is not a useful BC training signal. A BC model trained on this data will
  learn to suppress all action output.
- The 288 non-NoOp cell-actions across 4 full episodes are insufficient to train any
  meaningful BC spatial distribution.
- Clean adapter path (0 remaps) is a positive quality indicator for the *format* but
  does not rescue the underlying policy quality issue.
- Root cause: at 100k training steps the policy argmax has converged to conservative
  passivity — the high-value action under argmax is NoOp almost everywhere.

### 5.2 Stochastic Batch — BC Quality Assessment

**Verdict: MARGINAL — high semantic noise, near-random distribution**

- Near-uniform action distribution (std ≈ 350 from expected per-type uniform) means the
  policy entropy is not yet well-structured. A BC model cannot learn meaningful spatial
  conditioning from near-random teacher trajectories.
- 20.76% of all cell-actions are remapped to NoOp by the adapter — this is the semantic
  mismatch overhead (Gym action space exceeds Unity contract). This inflates NoOp
  post-adaptation to 37.52% — manageable but non-trivial noise.
- Higher episode returns (mean 12.75 vs det 2.0) suggest the *reward signal* is healthy —
  the environment is responsive and the policy does receive meaningful game feedback.
  This is a positive indicator for continued training.
- The mismatch between high stochastic return and near-uniform action distribution is
  explained by masked sampling: even near-uniform logits over non-masked cells can
  produce useful game actions because the mask itself encodes spatial structure.

### 5.3 Comparison Table

| Criterion | Det | Stoch |
|-----------|-----|-------|
| BC-usable action diversity | FAIL (99.97% NoOp) | MARGINAL (near-uniform) |
| Adapter clean path | PASS (0 remap) | PARTIAL (20.76% remap) |
| Episode return quality | FAIL (2.0 flat) | PASS (5–19, mean 12.75) |
| Policy entropy state | Too low (collapsed) | Too high (diffuse) |
| Format contract compliance | PASS | PASS |
| Zero drops | PASS | PASS |
| Recommended for BC now | **NO** | **NO** |

---

## 6. Decision

**BOTH BATCHES: NOT READY FOR BC EXPORT**

The checkpoint at 100k training steps has not yet reached the policy distribution quality
required for meaningful imitation learning:

- The deterministic argmax is degenerate (NoOp-collapsed).
- The stochastic sample is near-uniform (high-entropy diffuse).
- A well-trained teacher should show: deterministic argmax with <70% NoOp, stochastic
  sampling with concentrated non-uniform action type distributions.

**Recommended next action: Continue training to 200k–500k steps.**

Continuation training indicators to watch:
1. Det batch NoOp share drops below 85% → policy argmax developing intent.
2. Stoch action distribution becomes non-uniform (NoOp dominant but other types peaking
   at specific spatial conditions).
3. Stoch episode mean return ≥ 20 (currently 12.75) with lower std (currently 5.3).
4. Adapter remap share below 15% (currently 20.76%) — achievable if produce/attack
   logits concentrate within the Unity-compatible range.

**This checkpoint is NOT blocked from continuation training. The training signal is healthy
(stochastic env return = 5–19). The issue is entropy/convergence, not environment failure.**

---

## 7. Artifacts

### Raw rollout batches

| Artifact | Path |
|----------|------|
| Det batch dir | `WEEK5R/gridnet_teacher_rollouts/gridnet_100k_det_ab/` |
| Stoch batch dir | `WEEK5R/gridnet_teacher_rollouts/gridnet_100k_stoch_ab/` |

### Adapted batches (adapter output)

| Artifact | Path |
|----------|------|
| Det adapted dir | `WEEK5R/teacher_exports/teacher_adapted_gridnet_100k_det_ab_20260427T164117Z/` |
| Det conversion_report | `...teacher_adapted_gridnet_100k_det_ab.../conversion_report.json` |
| Stoch adapted dir | `WEEK5R/teacher_exports/teacher_adapted_gridnet_100k_stoch_ab_20260427T164124Z/` |
| Stoch conversion_report | `...teacher_adapted_gridnet_100k_stoch_ab.../conversion_report.json` |

### Exporter

| Artifact | Path |
|----------|------|
| Rollout exporter | `python/week5_teacher_gridnet/export_gridnet_teacher_rollout.py` |

---

## 8. Pipeline Status

| Stage | Status |
|-------|--------|
| Visual eval (render) | COMPLETE — `visual_eval_agent_final.json` |
| Multi-opponent eval (det) | COMPLETE — PASS 4/4 |
| Multi-opponent eval (stoch) | COMPLETE — PASS 4/4 |
| Rollout export (det + stoch) | COMPLETE — 4 episodes × 2 batches |
| Adapter dry run (det) | COMPLETE — 0 remaps, 0 drops |
| Adapter dry run (stoch) | COMPLETE — 20.76% remap, 0 drops |
| **BC export** | **BLOCKED — continue training first** |
| **Unity parity claim** | **NOT MADE** |
