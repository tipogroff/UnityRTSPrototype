# Week 4 Day 6: Baseline Reward Sanity-Check Report

**Date:** 2026-03-31 23:10:00
**Episodes:** 20
**Mode:** Baseline/Heuristic

## Executive Summary

⚠️  **3 sanity warnings detected.** See details below.

## Reward Statistics

| Metric | Value |
|--------|-------|
| Total Mean ± Std | 3,22 ± 0,00 |
| Total Range | [3,22, 3,22] |
| Economy | 3,19 |
| Combat | 0,28 |
| Terminal | -0,25 |
| Shaping | 0,00 (0,0% of total) |

## Episode Statistics

| Metric | Value |
|--------|-------|
| Avg Steps | 2000,0 |
| Step Range | [2000, 2000] |
| Avg Reward Events | 102,0 |

## Terminal Behavior

| Metric | Value |
|--------|-------|
| Terminal Events Processed | 20/20 (100,0%) |
| Terminal Reward Non-Zero | 0/20 (0,0%) |

### Terminal Reasons

| Reason | Count |
|--------|-------|
| Timeout | 20 |

### Outcome Distribution

| Outcome | Count | Percentage |
|---------|-------|------------|
| Timeout | 20 | 100,0% |

## Invalid Actions

| Metric | Value |
|--------|-------|
| Episodes With Measured Invalid Rate | 20/20 |
| Episodes With Unavailable Invalid Rate | 0/20 |
| Avg Invalid Rate (Measured Only) | 0,0% |
| Max Invalid Rate (Measured Only) | 0,0% |
| Episodes with High Rate (>15%, Measured Only) | 0 |

## Sanity Check Results

⚠️  **3 warnings:**

- ⚠️ Terminal reward often zero: 0,0% of processed events have non-zero reward (threshold: 30,0%). Terminal reward config may be disabled or too conservative.
- ⚠️ Outcome imbalance: Timeout = 100,0% of episodes (threshold: 80,0%). Agent may be stuck in a single state or pattern.
- ⚠️ Suspiciously long low-reward episodes: 100,0% of episodes exceeded 1000 steps with reward < 5 (threshold: 10,0%). May indicate agents stuck in passive play.

## Per-Episode Detail

| # | Reward | Steps | Economy | Combat | Terminal | Shaping | Outcome | Invalid % | Terminal? |
|---|--------|-------|---------|--------|----------|---------|---------|-----------|-----------|
| 12 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |
| 13 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |
| 14 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |
| 15 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |
| 16 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |
| 17 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |
| 18 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |
| 19 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |
| 20 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |
| 21 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |
| 22 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |
| 23 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |
| 24 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |
| 25 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |
| 26 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |
| 27 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |
| 28 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |
| 29 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |
| 30 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |
| 31 | 3,22 | 2000 | 3,19 | 0,28 | -0,25 | 0,00 | Timeout  | 0% | ✓ |

## Interpretation

### What This Report Includes
- Episode-level metrics: total reward, reward category breakdown, steps, invalid action rate, terminal reason
- Batch aggregates: means, standard deviations, ranges, distributions
- Sanity checks: flagged anomalies detected across reward magnitude, shaping dominance, invalid actions, terminal events, and outcome imbalance
- Invalid-action availability diagnostics (measured vs unavailable episodes)

### What This Report Does NOT Include
- Mathematical proofs of reward quality or learnability
- Policy optimization analysis
- Full transfer compatibility validation with Gym-μRTS
- Performance timing or computational efficiency analysis

### Interpretation Guidelines
- **Reward Magnitude:** Look for patterns in mean reward and individual episode traces. Stable, non-explosive ranges suggest no immediate reward hacking.
- **Shaping vs Terminal:** If shaping dominates, the learning signal may reward intermediate spurious behavior. Typically acceptable up to 50% of total.
- **Terminal Events:** High processed rate and non-zero reward indicate terminal pipeline is functioning. Low rates or zero rewards suggest terminal config may need review.
- **Invalid Actions:** Interpret invalid-rate only for measured episodes. N/A means action counts were unavailable for that decision-source path.
- **Outcome Distribution:** Imbalance (>80% one outcome) may indicate stuck state or deterministic heuristic behavior.

### Next Steps if Warnings Detected
1. Review specific episode traces where anomalies occurred
2. Check reward breakdown composition (economy vs combat vs terminal)
3. Validate action mask and decoder correctness
4. Examine terminal condition logic and reward assignment
5. Consider tuning reward coefficients or thresholds (only after investigation)

---
Generated by Day6RewardSanitySmokeTest at 2026-03-31 23:10:00
