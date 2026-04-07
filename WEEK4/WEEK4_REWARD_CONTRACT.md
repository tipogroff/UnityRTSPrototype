# Week 4 Day 1 - Reward and Terminal Contract (v1)

Date: 2026-03-30
Status: Day 1 contract; implemented incrementally in Day 2 and Day 3 runtime layers
Scope: Contract-first specification only. No full reward collector or terminal loop implementation in this artifact.

Day 3 note:
- Terminal semantics are now implemented via runtime-authoritative terminal evaluation (EpisodeTerminalEvaluator),
  shared by RuntimeRewardCollector and EpisodeController.
- See WEEK4_DAY3_TERMINAL_PIPELINE_SUMMARY.md for implementation details and diagnostics surface.

## 1) Day 1 Goal and Non-Goals

Goal:
- Fix explicit reward/terminal semantics before broad Week 4 coding.
- Prevent semantic drift while extending the existing Week 3 RL pipeline.

Non-goals for Day 1:
- No full reward collector implementation.
- No ML-Agent reward wiring.
- No rewrite of agent loop.
- No replacement of runtime truth in `ActionApplier` / `MatchManager` / `VictoryResolver`.

## 2) Architecture Alignment with Week 3

Week 3 production path remains authoritative and unchanged:

`observation -> mask -> action -> decoder -> applier -> MatchManager.ApplyCommand()`

Rules:
- Reward logic is computed on top of runtime results, not inside mask/decode.
- Masking is pre-sampling only and never a reward source.
- Heuristic path is a control path for diagnostics, not a truth source for reward semantics.
- Terminal logic must read runtime-authoritative match state (MatchManager/VictoryResolver), not invent an independent RL truth.

## 3) Semantic Layer Separation

This project separates four layers:

1. Runtime events: what actually changed in game state.
2. Rewardable/punishable events: subset of runtime events mapped to scalar reward.
3. Terminal events: episode end states from runtime lifecycle.
4. Diagnostics-only metrics: logged for analysis, not added to reward.

### 3.1 Event Classification Matrix

| Runtime Event | World State Changed | Reward in v1 | Terminal in v1 | Diagnostics-only |
|---|---:|---:|---:|---:|
| Move accepted | Yes | No | No | Yes |
| Harvest success (resource extracted) | Yes | Yes | No | Yes |
| Return success (resource deposited) | Yes | Yes | No | Yes |
| Produce success (unit spawned) | Yes | Yes | No | Yes |
| Attack command accepted | Maybe | No | No | Yes |
| Damage dealt to enemy | Yes | Yes | No | Yes |
| Enemy unit destroyed | Yes | Yes | No | Yes |
| Own unit destroyed | Yes | Optional penalty | No | Yes |
| Own base destroyed | Yes | Optional penalty | Usually terminal by runtime | Yes |
| Match won/lost/draw | Yes | Yes (terminal reward) | Yes | Yes |
| Step limit reached | No direct tactical change | Optional terminal shaping | Yes | Yes |
| Invalid command rejected | No | Optional penalty (guarded) | No | Yes |

## 4) Reward Philosophy for Week 4 v1

v1 philosophy:
- Sparse-first with moderate shaping.
- Terminal outcome should dominate episode objective.
- Dense signals are support signals, not primary objective.
- Attribution is runtime-effect-first.

Policy choices for v1:
- Invalid action penalty: optional and small (default off, can be enabled for stability tuning).
- Per-step living penalty: optional and very small; keep off by default in first runs.
- Anti-passivity penalty: optional; do not enable before baseline trace inspection.

Tuning policy:
- Start with minimal working v1.
- Tune magnitudes only after baseline rollout traces (Day 6), not on Day 1.

## 5) Reward Attribution Contract (Intent vs Accepted vs Runtime Effect)

Default attribution decision by category:

| Category | Primary Attribution Basis | Allowed Optional Basis | v1 Decision |
|---|---|---|---|
| Move | Runtime effect (position changed) | Accepted command | No reward in v1 |
| Harvest | Runtime effect (resources actually extracted) | Accepted command (very weak shaping) | Runtime effect only |
| Return | Runtime effect (resources actually deposited) | Accepted command (very weak shaping) | Runtime effect only |
| Produce | Runtime effect (unit spawned and registered) | Accepted command (very weak shaping) | Runtime effect only |
| Attack | Runtime effect (damage dealt / kill) | Accepted command (discouraged) | Runtime effect only |
| Unit destroyed | Runtime effect | None | Runtime effect only |
| Match outcome | Runtime terminal result | None | Runtime effect only |

Hard rule:
- Intent-only reward is forbidden in v1 for core economy/combat signals.

## 6) Reward Signal Catalog (v1 Contract)

Magnitudes below are suggested starting values for Week 4 v1 and are intentionally conservative.

### 6.1 Economy Rewards

| Signal ID | Source Event | Trigger Moment | Sign | Suggested Magnitude | One-Time / Repeatable | Stack Rule | Attribution Basis | Reward Hacking Risk | v1 Status |
|---|---|---|---|---:|---|---|---|---|---|
| ECON_HARVEST_SUCCESS | Runtime harvest produced amount > 0 | Post-step runtime result | + | +0.02 per successful harvest event | Repeatable | Sum per successful event in step; cap per-step optional | Runtime effect only | Worker oscillation near rich nodes | Required |
| ECON_RETURN_SUCCESS | Runtime deposit increased own resources | Post-step runtime result | + | +0.05 per successful return event | Repeatable | Sum per successful event in step | Runtime effect only | Farming returns without strategic pressure | Required |
| ECON_PRODUCE_SUCCESS | Runtime spawn completed and unit appears | Post-step runtime result | + | +0.03 per produced unit | Repeatable | Sum per produced unit; optional soft cap | Runtime effect only | Meaningless overproduction loops | Required |

### 6.2 Combat Rewards

| Signal ID | Source Event | Trigger Moment | Sign | Suggested Magnitude | One-Time / Repeatable | Stack Rule | Attribution Basis | Reward Hacking Risk | v1 Status |
|---|---|---|---|---:|---|---|---|---|---|
| COMBAT_DAMAGE_DEALT | Runtime confirms enemy HP reduction | Post-step runtime result | + | +0.01 per normalized damage unit | Repeatable | Sum all dealt damage for step | Runtime effect only | Safe poke farming without win progress | Required |
| COMBAT_ENEMY_DESTROYED | Runtime enemy unit death | Post-step runtime result | + | +0.20 per unit destroyed | Repeatable | Sum all enemy losses in step | Runtime effect only | Targeting easy units over objective | Required |
| COMBAT_SELF_UNIT_LOST | Runtime own unit death | Post-step runtime result | - | -0.12 per own unit lost | Repeatable | Sum all own losses in step | Runtime effect only | Overly risk-averse behavior if too strong | Optional |
| COMBAT_SELF_BASE_LOST | Runtime own base destroyed | Post-step runtime result | - | -0.50 | Typically one-time | Apply once when event occurs | Runtime effect only | Can over-dominate if combined with terminal loss too strongly | Optional |

### 6.3 Terminal Rewards

| Signal ID | Source Event | Trigger Moment | Sign | Suggested Magnitude | One-Time / Repeatable | Stack Rule | Attribution Basis | Reward Hacking Risk | v1 Status |
|---|---|---|---|---:|---|---|---|---|---|
| TERM_MATCH_WIN | MatchManager terminal with winner=self | Episode end | + | +1.00 | One-time | Apply once at terminal transition | Runtime effect only | None (target objective) | Required |
| TERM_MATCH_LOSS | MatchManager terminal with winner=enemy | Episode end | - | -1.00 | One-time | Apply once at terminal transition | Runtime effect only | None (target objective) | Required |
| TERM_MATCH_DRAW | MatchManager terminal with neutral winner | Episode end | 0 or - | 0.00 (start) or -0.10 | One-time | Apply once at terminal transition | Runtime effect only | Encouraging passive draw if neutral reward is too high | Required |
| TERM_TIMEOUT | MatchEndReason.StepLimitReached | Episode end | 0 or - | 0.00 (start) or -0.05 | One-time | Apply once at terminal transition | Runtime effect only | Timeout camping if no downside | Optional |

### 6.4 Optional Shaping Penalties / Auxiliary Signals

| Signal ID | Source Event | Trigger Moment | Sign | Suggested Magnitude | One-Time / Repeatable | Stack Rule | Attribution Basis | Reward Hacking Risk | v1 Status |
|---|---|---|---|---:|---|---|---|---|---|
| SHAPE_INVALID_COMMAND | Command rejected by authoritative runtime | Same step | - | -0.005 each (small, clipped) | Repeatable | Sum with hard per-step cap | Accepted command failure (runtime rejection) | Over-penalizes exploration if too large | Optional (default off) |
| SHAPE_IDLE_STEP | No meaningful progress event in step | Post-step | - | -0.001 | Repeatable | At most once per step | Runtime effect summary | Can punish legitimate waiting tactics | Optional (default off) |
| SHAPE_LONG_EPISODE | Very long episode without objective progress | Post-step | - | very small schedule | Repeatable | Scheduled per-step tiny penalty | Runtime effect summary | Distorts strategy toward speed-only play | Optional (default off) |

### 6.5 Pure Diagnostics (Not Reward)

These values are logged and analyzed but must not be added to reward in v1:

- accepted command count per step/episode;
- invalid command count and invalid rate;
- economy contribution trace (raw event counts and magnitudes);
- combat contribution trace (damage/kills/losses);
- terminal reason code and end details;
- pending commands and phase snapshots;
- per-episode step count and resource curves.

## 7) Terminal Contract (Day 1 Semantics)

Terminal states in RL must map to runtime terminal lifecycle.

### 7.1 Terminal Reasons (RL-facing)

| RL Terminal Reason | Runtime Source | Terminal? | Reward Handling in v1 |
|---|---|---:|---|
| Win | `MatchManager` ended, winner=self | Yes | `TERM_MATCH_WIN` |
| Loss | `MatchManager` ended, winner=enemy | Yes | `TERM_MATCH_LOSS` |
| Draw | `MatchManager` ended, winner=neutral | Yes | `TERM_MATCH_DRAW` |
| Timeout | `MatchEndReason.StepLimitReached` | Yes | `TERM_TIMEOUT` (optional separate shaping) |
| InvalidRuntimeState | Runtime guard condition (if implemented later) | Yes (guarded) | Usually loss-like or neutral-safe stop; to be finalized later |

### 7.2 Mapping Constraints

- No independent RL victory resolver is allowed.
- RL terminal flag must reflect runtime-authoritative state (`MatchManager.Phase`, `MatchResolution`, `MatchEndReason`).
- If runtime is still running, RL episode must not be forced terminal by separate policy-side logic.
- Timeout is terminal because runtime says so, not because RL side wants shorter episodes.

## 8) Risks, Failure Modes, and Week 4 v1 Mitigations

| Risk | Why It Can Happen | Week 4 v1 Mitigation |
|---|---|---|
| Safe shaping spam | Dense rewards may be farmed by low-risk loops | Keep dense magnitudes low; inspect baseline traces on Day 6 |
| Harvest dominates win objective | Economy rewards can outweigh terminal outcome | Keep terminal +/-1.0 dominant; cap or reduce economy terms if needed |
| Damage farming without strategic value | Agent can poke enemy repeatedly without closing game | Keep damage reward small vs kill and terminal outcome |
| Produce spam | Reward for production can incentivize useless units | Keep produce reward low; consider soft per-step cap |
| Timeout camping | Neutral/zero timeout encourages passivity | Optional slight timeout penalty; monitor draw/timeout rates |
| Invalid penalty blocks exploration | Strong penalties suppress action discovery | Keep invalid penalty optional, tiny, and clipped |
| Terminal too weak | Dense rewards dominate objective | Enforce terminal dominance and compare episode reward decomposition |
| Semantic drift from runtime truth | Reward computed from intent instead of effects | Runtime-effect-first attribution and explicit prohibition of intent-only reward |

## 9) Minimal Implementation Preparation (Allowed for Day 1)

To support Day 2 implementation without semantic drift, minimal skeleton contracts are allowed:

- `RewardEventType` enum;
- `RewardCategory` enum;
- `RewardAttributionBasis` enum;
- `TerminalReason` enum (RL-facing, mapped to runtime reasons);
- `RewardBreakdown` data struct;
- `RewardConfig` data struct with v1 default magnitudes.

Strict Day 1 boundary:
- No event collection logic yet.
- No integration with `OnActionReceived` or ML-Agent reward APIs yet.
- No Week 3 pipeline rewrite.

## 10) Day 1 Exit Criteria

Day 1 is complete when:
- reward/terminal contract is explicit and concrete;
- runtime events vs reward vs diagnostics are separated;
- attribution basis is fixed (runtime-effect-first);
- terminal semantics are mapped to `MatchManager`/`VictoryResolver` lifecycle;
- major reward hacking risks and mitigations are documented;
- Day 2 implementation can proceed without ambiguity.