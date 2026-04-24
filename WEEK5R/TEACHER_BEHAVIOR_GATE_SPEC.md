# Teacher Behavior Gate — Specification

## 1. Purpose

Before investing compute in retraining a teacher model, the gate provides a cheap, reproducible
quality-check that verifies the checkpoint exhibits non-collapsed, goal-directed behavior
**at the actor level** inside Gym-µRTS.

A collapsed teacher produces a defective BC dataset: spurious action labels inflate student
training but do not correspond to any effective game behavior.

---

## 2. Why reward / full-tensor action histogram is insufficient

| Signal | What it tells you | What it CANNOT tell you |
|---|---|---|
| Cumulative reward | Episode-level outcome | Whether individual actors moved, harvested, or attacked |
| Full-tensor Move % | Raw action array distribution over all 576 cells | Whether any teacher-controlled unit actually moved |
| Full-tensor NoOp % | Fraction of NoOp slots in the 576-cell output | How many of those cells belonged to teacher-owned ready units |

A checkpoint with **37% full-tensor Move** was found to have **0% actor-level Move** on
ready own actors. The 37% Move signal came entirely from cells that are not teacher-owned and
not controllable — their actions are masked/ignored by the env.

Reward can stay above baseline even if the teacher does nothing useful, because the opponent
may simply be worse.

---

## 3. Full-tensor action distribution vs actor-level chosen behavior

```
Full tensor                    Actor-level
────────────────────────       ────────────────────────
All 576 spatial cells          source_unit_mask == 1 cells only
All action branches            action_type branch (column 0 of action matrix)
576 × steps × episodes         N_ready_actors × steps × episodes
                               (typically 2–4 per step for basesWorkers24x24)

Includes:
  - teacher-owned ready units  ✓                         ✓
  - teacher units in cooldown  ✓ (pollutes histogram)    ✗
  - opponent-owned cells       ✓ (pollutes histogram)    ✗
  - empty cells                ✓ (pollutes histogram)    ✗
  - resource nodes             ✓ (pollutes histogram)    ✗
```

Actor-level behavior is the only signal that maps directly to what the teacher
**decides for units it can actually command this step**.

---

## 4. Why Move in full tensor does NOT prove real movement

In Gym-µRTS `MicroRTSGridModeVecEnv`, the action tensor is `[576, 7]`.
The env applies `source_unit_mask` to filter which cells are acted upon.
Cells without `source_unit_mask == 1` have their actions silently discarded.

A policy may output Move in the action array at row 42 (an empty cell or a
cooldown unit). The env ignores that row. No movement occurs.
The full-tensor Move counter still increments.

**The full-tensor Move share measures the distribution of output logits projected
onto the argmax of all cells, not the frequency of executed movements.**

---

## 5. Scripts used

| Script | Purpose |
|---|---|
| `python/week5_teacher/evaluate_teacher_actor_level.py` | Actor-level action distribution over ready own actors |
| `python/week5_teacher/audit_teacher_effective_behavior.py` | State-diff audit: obs_before vs obs_after per ready actor |
| `python/week5_teacher/teacher_behavior_gate.py` | **Gate**: runs both audits, merges results, issues a status verdict |
| `python/week5_teacher/compare_teacher_behavior_gates.py` | Comparison table across multiple gate JSON outputs |

---

## 6. What the gate does NOT claim

- The gate runs exclusively inside **Gym-µRTS**. It does NOT claim that teacher
  behavior in Gym-µRTS semantically matches what would happen in the Unity runtime.
- The gate does NOT prove Gym→Unity semantic parity.
- The gate does NOT verify BC dataset quality or student policy behavior.
- State-diff audit uses `obs_before` / `obs_after` as a proxy. It is an observation-based
  proxy, **not** a confirmed internal execution stream from the env.

---

## 7. Gate status codes

| Status | Meaning |
|---|---|
| **PASS** | actor_level_move_share ≥ 5%, effective_position_delta_count > 0, no FAIL flags |
| **SUSPICIOUS** | actor_noop_share > 75% OR no_effect_action_share > 60%; no FAIL-level conditions met |
| **FAIL_COLLAPSED_NOOP** | ready_movable_actor_count > 0, actor_level_move_share == 0, effective_position_delta_count == 0, actor_noop_share > 90% |
| **FAIL_NO_EFFECT_BEHAVIOR** | ready own actors exist, no_effect_action_share > 80%, effective_position_delta_count == 0 |
| **FAIL_FALSE_FULL_TENSOR_MOVE** | full_tensor_move_share ≥ 10% but actor_level_move_share < 5% (gap indicates spurious tensor signal) |

Priority of FAIL codes (highest to lowest):
1. `FAIL_COLLAPSED_NOOP`
2. `FAIL_FALSE_FULL_TENSOR_MOVE`
3. `FAIL_NO_EFFECT_BEHAVIOR`

If multiple FAILs are detected, all are reported in `fail_reasons`.

---

## 8. Decision rule reference

```
FAIL_COLLAPSED_NOOP:
  ready_movable_actor_count > 0
  AND actor_level_move_share == 0
  AND effective_position_delta_count == 0
  AND actor_noop_share > 0.90

FAIL_FALSE_FULL_TENSOR_MOVE:
  full_tensor_move_share >= 0.10
  AND actor_level_move_share < 0.05

FAIL_NO_EFFECT_BEHAVIOR:
  chosen_ready_own_actor_count > 0
  AND no_effect_action_share > 0.80
  AND effective_position_delta_count == 0

SUSPICIOUS:
  actor_noop_share > 0.75
  OR no_effect_action_share > 0.60

PASS:
  actor_level_move_share >= 0.05
  AND effective_position_delta_count > 0
  AND no FAIL flags
```

---

## 9. Collapsed checkpoint reference (80k steps, basesWorkers24x24)

Empirically measured values from the Week 6 audit:

```
full_tensor_move_share      = 0.373   (37.3% — spurious, from non-teacher cells)
actor_level_move_share      = 0.000   (0 out of 53 ready choices)
actor_noop_share            = 0.943   (50/53 choices were NoOp)
effective_position_delta_count = 0    (zero position changes observed)
no_effect_action_share      ≈ 1.0     (all actions were NoOp or masked-out Harvest)
```

Expected gate verdict for this checkpoint: **FAIL_COLLAPSED_NOOP** (+ **FAIL_FALSE_FULL_TENSOR_MOVE**)

If a gate run on this checkpoint returns PASS, the gate thresholds are miscalibrated
or the metric extraction is reading the wrong tensor dimension.

---

## 10. Sampling and Metric Clarifications

- `opponent_sampling=per_episode` must re-sample opponent per actor-level audit episode,
  not once per full gate run.
- `opponent_sampling=static` always uses the first opponent from `opponent_pool`.
- Effective-behavior audit may run against either the first pool opponent or a dedicated
  deterministic opponent pick; whichever strategy is used must be recorded in gate metadata.

### ready_movable metrics

- `ready_movable_actor_count` is retained for backward compatibility.
- Historical meaning of `ready_movable_actor_count`: a step-level proxy (count of steps with
  at least one ready movable actor), not an actor-choice count.
- Preferred explicit fields:
  - `steps_with_movable_ready_actors`
  - `ready_movable_actor_choice_count`
- Authoritative FAIL condition remains unchanged: movable opportunity existed (`> 0`) and
  movement/effective behavior stayed collapsed according to gate thresholds.

---

## 11. Visual Replay Layer

- Visual replay is a human-readable sanity check and does not replace actor-level gate logic.
- Visual replay artifacts are optional and non-blocking for gate completion.
- Gate status and thresholds remain authoritative; replay generation failures should produce
  warnings only.
- Visual replay does not prove Gym->Unity semantic parity.
