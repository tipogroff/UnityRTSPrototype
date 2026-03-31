# Week 4 Day 6 - Updated Checklist

Date: 2026-03-31
Status: Scene/runtime follow-up implemented, rerun-ready

## 1) Scope Kept

- Kept 24x24 observation contract unchanged.
- Kept canonical RL loop architecture unchanged.
- Kept reward collector semantics unchanged.
- Kept terminal pipeline semantics unchanged.
- Kept baseline rollout path unchanged (no alternate runtime architecture path).

## 2) Implemented Changes (Current State)

### Scene/scenario setup

- Enabled Day 6 sanity preset in scene.
- Start setup tuned for progression:
  - 1 Base + 2 Workers + 1 Light per side.
  - Initial lights placed to avoid immediate one-off opening trade.
  - Resource access tuned for early harvest/return loop stability.
- Sanity start resources set to 60 for practical production reachability.

### Baseline decision behavior

- Heuristic policy now submits decisions for all available actors per player per step (not single-actor only).
- Decision priority cycling added (worker/combat/building rotation) to avoid role starvation.
- Worker production preference tuned (`_maxWorkerLimit = 2`) to avoid worker-only growth and unlock earlier combat-unit production.

### Combat/attack consistency

- Combat range metric aligned to attack contract semantics (Chebyshev in 3x3 local neighborhood).
- Explicit queued attack commands are now executed first in combat phase.
- Auto-combat then runs for remaining attackers only.
- Attack target selection/validation aligned across layers:
  - neutral targets excluded from attack mask,
  - heuristic attack target no longer falls back to arbitrary local index,
  - runtime validation rejects neutral attack targets.

### Movement stability

- Direction-towards helper requires strict progress (distance reduction), reducing oscillation.

## 3) Validation Outcome (Manual Playtest)

- Play Mode compile blocker resolved.
- Production is observed (new units appear).
- Baseline no longer collapses to immediate degenerate opening pattern.
- Previous issues with single active warrior were addressed by multi-actor decision submission.

Note: final quantitative confirmation still requires rerun batch metrics, not visual-only claims.

## 4) Known Remaining Work

- Run new Day 6 batch report after all runtime fixes.
- Compare against prior timeout-only baseline reports:
  - outcome distribution,
  - economy and production event frequency,
  - terminal trace informativeness.

## 5) Primary References

- Scene follow-up summary: WEEK4_DAY6_SCENE_FOLLOWUP_SUMMARY.md
- Latest baseline report artifacts: WEEK4_Reports/

## 6) Current Verdict

- Day 6 scene-focused follow-up pass: implemented.
- Runtime behavior fixes for baseline sanity readability: implemented.
- Batch rerun and quantitative confirmation: pending next step.
