# WEEK3 Day 6 Summary

Date: 2026-03-28

## Scope
Day 6 focused on smoke/integration coverage and contract consistency for the single production pipeline:

observation -> mask -> action -> decoder -> applier -> MatchManager.ApplyCommand()

No shortcut path was added. Tests and fixes reinforce the same downstream path planned for ML-Agent.

This final pass keeps Day 6 scope only (no Day 7 cleanup/polish).

## Added Smoke Scenarios
Implemented in Assets/Scripts/ML/Day6PipelineSmokeTest.cs and runnable from menu:

- SmokeTest/10 - Day6 Pipeline Smoke Test
- RTS/Smoke/Day6
- RTS/Smoke/Day6 From Cold Start

Suite hardening in final pass:

- Added assert-like guards via internal Require/Fail helpers.
- Scenario failures are now explicit and cannot be interpreted as green checks.
- Added scenario-level result tracking (PASS/FAIL) with per-scenario details.
- Added optional throw-on-failure at suite end for fail-fast CI/manual debugging.

Scenarios covered:

1. Move
- Valid: action allowed by mask, decoded by ActionDecoder, accepted by ActionApplier, and applied after StepMatch.
- Invalid edge: blocked/out-of-bounds direction is rejected with reason.
- Observation consistency checks: actor friendly ownership and target-cell consistency before command.

2. Harvest/Return
- Valid harvest: worker adjacent to active resource harvests and increases carried resources.
- Invalid return edge: return with empty carry is rejected with reason.
- Valid return: worker with carry adjacent to friendly base returns resources and increases player resources.
- Observation consistency checks: worker ownership, resource signal on harvest target cell, friendly-base signal on return target cell.

3. Attack
- Valid: attacker with enemy in local neighborhood passes mask/decode/apply and affects target state after step.
- Invalid edge: local attack target index = 4 (self target) is rejected explicitly.
- Observation consistency checks: friendly attacker + enemy presence signal at target cell.
- Explicit limitation marker retained (see residual gap section): this scenario validates command submission + runtime combat effect, not strict target-preserving semantics.

4. Production
- Valid: building with resources/free direction and producible type starts production queue.
- Invalid edge: second produce attempt while queue is busy is rejected by authoritative validation.
- Observation consistency checks: friendly production actor representation.

5. Invalid Action Fallback
- Invalid input: negative actor index decode produces invalid action and is rejected safely (diagnostic log emitted).
- Safe fallback: NoActor/NoOp remains a deterministic, safe no-op and does not break step progression.

Prepared vs fallback diagnostics:

- Each scenario now tracks whether it passed via prepared scene state or fallback reconstruction.
- Fallback path usage is explicitly recorded in scenario result notes.
- This prevents false confidence from auto-repair setup being indistinguishable from prepared-path success.

Cold-start runtime tooling added after the main Day 6 pass:

- Added editor menu `RTS/PlayMode/Enter` and `RTS/PlayMode/Exit` for deterministic Play Mode control in Unity.
- Added editor menu `RTS/Smoke/Day6 From Cold Start` that enters Play Mode first and then launches the Day 6 suite automatically.
- This provides a single entrypoint for validating runtime startup plus the Day 6 pipeline smoke in one flow.

## Invalid Attempt Logging Added
Extended ActionApplier diagnostics with structured invalid-attempt records:

- player
- actor position + flat index
- source action format (debug/transfer/heuristic)
- requested action type
- action parameters (direction, produce type, attack target)
- decoder validity + decoder reason
- mask state at selection moment
- accepted/rejected flag
- rejection reason
- mismatch category

Added category enum:

- ObservationMismatch
- MaskMismatch
- RuntimeOnlyConstraint
- InvalidInput
- ExpectedFallback

This logging is emitted on rejection through ActionApplier and available via LastInvalidAttempt and OnInvalidActionAttempt.

## Contract Mismatches Found and Fixed
1. Move capability drift (fixed)
- Issue: ActionApplier considered Move broadly supported, while runtime rejects building movement.
- Fix: ActionApplier unit-type support now blocks Move for Base/Barracks/Resource.
- Impact: reduced mask/runtime false-positive acceptance and clearer rejection behavior before MatchManager command queue.

2. Attack capability drift (fixed)
- Issue: ActionMaskBuilder gates attack on runtime unit definition (damage/range), but ActionApplier previously accepted broader attack types.
- Fix: ActionApplier attack validation now checks runtime definition capability (attackDamage > 0 && attackRange > 0) when config is available.
- Impact: mask and runtime alignment improved for attack eligibility.

4. Capability-gate ambiguity in ActionApplier (fixed, minimal)
- Issue: capability truth between static type support and runtime capability checks was not explicitly separated.
- Fix: split into coarse type gate plus explicit runtime-authoritative capability gate.
- Impact: lower risk of reintroducing move/attack drift while preserving current architecture.

3. Invalid decode fallback ambiguity (fixed)
- Issue: structurally invalid decoded actions could be represented as NoOp and pass silently.
- Fix: ActionApplier now rejects actions with IsValid == false before NoOp early-exit and logs InvalidInput.
- Impact: semantic drift becomes visible; invalid inputs are diagnosable instead of silently ignored.

## Intentional Unity-only / Runtime Gaps (Not hidden)
1. Combat execution semantics remain runtime-driven
- MatchManager currently queues attack commands but CombatResolver resolves combat with automatic target selection each tick.
- Day 6 does not bypass or mask this behavior.
- Kept explicit as a Unity runtime behavior gap vs strict command-target semantics.
- Day 6 attack smoke therefore claims only: pipeline submission + runtime combat effect.
- Day 6 does not claim full target-preserving semantic parity end-to-end.

2. Observation attack_target channel in compat mode
- Legacy compat channel still contains placeholder semantics; UnityMvpTransfer uses tactical enemy-presence signal.
- Kept explicit as contract-layer distinction, not hidden by smoke heuristics.

## Why Pipeline Is Stable on Key Scenarios After Day 6
- All five scenarios are executed through the exact production action path (decoder/applier/match manager).
- Each scenario has valid and invalid edge checks with explicit fail conditions.
- Invalid attempts are now explicit, structured, and categorized.
- Two high-impact permissive drifts (Move and Attack capability checks) were removed.
- Invalid decoded input is no longer silently treated as a successful no-op.
- Scenario reports now differentiate prepared-path success from fallback-reconstructed success.
- Focused observation-side assertions now verify critical scenario facts.

## Runtime Startup Follow-up (completed after Day 6 core pass)
- `GameScene` now self-starts its core runtime graph in Play Mode without requiring the scene repair menu beforehand.
- `EpisodeController` now guarantees core runtime objects exist before resolving references:
	- `GridManager`
	- `UnitRegistry`
	- `ResourceManager`
	- `MatchBootstrap`
	- `MatchManager`
	- `VictoryResolver`
- When heuristic control is enabled, missing `HeuristicDriver` and `HeuristicPolicyAdapter` are created automatically during startup.
- `ExperimentLogger` continues to auto-create on demand.
- `MatchBootstrap` now self-heals core dependency lookup before config validation/setup.

Runtime validation result:

- Verified normal Play Mode startup without `RTS/Scene/Fix Current RTS Scene`.
- Verified automatic creation logs for `ExperimentLogger` and `HeuristicPolicyAdapter`.
- Re-ran Day 6 smoke on the self-started runtime path: `5/5 PASS`.
- Verified `RTS/Smoke/Day6 From Cold Start` end-to-end after Play Mode transition hardening: `5/5 PASS`.

Cold-start hardening note:

- `GridManager` now lazily initializes its occupancy storage on access, which removes a startup-order race exposed by the new cold-start smoke path.
- This prevents `NullReferenceException` in early mask/heuristic reads during Play Mode startup.

Noise reduction follow-up:

- `HeuristicPolicyAdapter` decision logs are now disabled by default to keep Play Mode console readable.
- Invalid attempts still remain visible through `ActionApplier` warning logs and Day 6 smoke diagnostics.

Files changed in this follow-up:

- `Assets/Scripts/Gameplay/Match/EpisodeController.cs`
- `Assets/Scripts/Gameplay/Match/MatchBootstrap.cs`
- `Assets/Scripts/Gameplay/Grid/GridManager.cs`
- `Assets/Scripts/Gameplay/Match/Editor/SmokeTestMenuRunner.cs`
- `Assets/Scripts/ML/HeuristicPolicyAdapter.cs`
- `Assets/Scripts/ML/WEEK3_DAY6_SUMMARY.md`

## Residual Risks
- Attack command semantics vs automatic CombatResolver targeting can still create transfer-side interpretation gaps.
- Some scene setups may lack required definitions/prefabs for specific unit types; tests fallback but coverage depth depends on configured assets.
- Observation-mask-runtime consistency for niche edge cases (e.g., simultaneous multi-actor contention) still needs broader regression matrix in Week 3 Day 7 polish.

## Claim Boundaries
- Day 6 closes stability for key smoke scenarios under the current Unity runtime model.
- Day 6 intentionally does not claim full semantic parity with Gym-μRTS.
