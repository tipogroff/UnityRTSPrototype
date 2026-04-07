# Week 4 Day 6 Scene-Focused Follow-up Summary

Date: 2026-03-31
Scope: Scene/config pass for baseline sanity-rollout quality.

## 1) Problem Statement (Observed Baseline Pattern)

Observed in Day 6 baseline runs:
- 10/10 episodes ended by Timeout.
- Economy reward signal remained weak.
- Terminal sanity surface looked low-information.

Scene-level interpretation of the degenerate pattern:
- Opening combat spike was too front-loaded (early light-unit contact), often becoming the only meaningful combat event.
- After the early contact, episode tempo dropped and long stretches of low-interaction steps dominated.
- Economy progression existed, but opening conditions did not reliably push the match into sustained harvest-return-production pressure.
- On a 24x24 map, a low-activity opening can amplify "empty-time" behavior and push traces toward timeout-only outcomes.

This follow-up intentionally treats the issue as a scene/scenario setup problem, not a canonical RL loop bug.

## 2) What Was Changed

Primary modified files:
- Assets/Scripts/Gameplay/Match/MatchBootstrap.cs
- Assets/Scenes/GameScene.unity

### 2.1 MatchBootstrap: Added sanity-focused scenario preset

Introduced `BootstrapScenarioPreset` with two modes:
- `LegacyMvpSymmetric` (historical baseline setup)
- `Day6Sanity24x24` (new sanity-friendly setup)

For `Day6Sanity24x24`:
- Kept map size at 24x24 (no observation grid contract change).
- Set opening units per player to:
  - 1 Base
  - 2 Workers
  - 1 Light
- Repositioned starting Light units away from immediate one-step contact to avoid instant one-off trade behavior.
- Kept resource patches near each side but tuned placement to improve worker access and reduce idle/open-loop travel.
- Added preset-scoped start resource override (`_day6SanityStartResources = 60`) to make production-path reachability more practical in baseline rollouts.

### 2.2 GameScene: Enabled Day6 sanity preset

In scene component configuration:
- Enabled MatchBootstrap preset `Day6Sanity24x24`.
- Set sanity preset start resources to 60.
- Raised legacy HeuristicDriver worker cap from 1 to 3 as fallback-friendly safety for non-pipeline runs.

### 2.3 Post-pass runtime hotfixes (same Day 6 follow-up)

After live playtesting, additional minimal fixes were applied to remove behavior regressions where combat looked stalled and only one unit appeared to act:

- Multi-actor baseline submission in `HeuristicPolicyAdapter`:
  - baseline now submits decisions for all available actors per player per step,
  - not just a single selected actor.
- Combat command execution in `MatchManager`:
  - explicit queued attack commands are executed first,
  - then auto-combat runs for remaining attackers only.
- Combat range semantics alignment in `CombatResolver`:
  - changed combat distance check to Chebyshev to match 3x3 local attack-target contract.
- Attack target consistency across mask/heuristic/runtime:
  - attack masks exclude neutral targets,
  - heuristic attack selection no longer falls back to arbitrary local target index,
  - runtime attack validation explicitly rejects neutral targets.
- Worker movement/oscillation stabilisation:
  - direction-towards helper now requires strict distance reduction.
- Worker-production balance tuning:
  - `HeuristicPolicyAdapter` worker-limit threshold lowered to 2,
  - helps earlier transition from worker-only growth to combat-capable production.

## 3) Production Availability Check (Current Setup)

Production path itself was not rewritten.

What this pass confirms/fixes on scene/config side:
- Production is still governed by existing runtime/action pipeline.
- Opening economy conditions are now more production-friendly (2-worker start + nearby resources + higher sanity start resources).
- Scenario no longer depends on an immediate combat exchange as the only meaningful progression event.

Note:
- This summary does not claim production frequency is already "solved" in statistics.
- Final validation requires a fresh Day 6 rerun batch.

## 4) Why This Setup Is Better for Sanity-Check

Compared to the previous opening behavior, the new setup should:
- Increase probability of meaningful harvest/return loops early in the episode.
- Increase practical chance to reach production decisions in baseline traces.
- Reduce the pathological "single early combat event then long inactivity" pattern.
- Improve terminal trace informativeness (more varied progression before timeout/win/loss resolution).

## 5) Sanity-Only Positioning

This is a sanity-focused scenario configuration for baseline rollout diagnostics.
It is not asserted as the final "main" project map balance.

## 6) Explicit Non-Goals Kept Intact

This pass did NOT change:
- canonical RL loop architecture,
- reward collector logic,
- terminal pipeline semantics,
- observation/action/mask contracts,
- 24x24 observation grid size.

Even with runtime hotfixes above, all changes stayed inside existing production execution paths.
No alternative RL architecture path was introduced.

No scripted-win behavior was introduced.

## 7) Next Step

Run a new Week 4 Day 6 baseline batch on this scene preset and compare against prior timeout-only baseline reports:
- outcome distribution,
- economy/production event presence,
- terminal sanity quality.
