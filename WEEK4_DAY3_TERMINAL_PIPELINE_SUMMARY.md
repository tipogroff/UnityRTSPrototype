# Week 4 Day 3 - Terminal Pipeline and Episode Lifecycle Consistency

Date: 2026-03-30
Status: Implemented — including finishing-pass semantic cleanup (TerminalEventProcessed/TerminalRewardNonZero, Timeout mapping, InvalidRuntimeState subtypes, mismatch diagnostics)
Scope: Explicit terminal pipeline over existing Week 3 production path and Day 2 reward layer.

## 1) What Was Added

Implemented explicit terminal-facing layer and integrated it into both reward and episode lifecycle:

- Assets/Scripts/ML/EpisodeTerminalPipeline.cs
  - TerminalEvaluationResult
  - EpisodeEndReport
  - EpisodeTerminalEvaluator
- Assets/Scripts/Gameplay/Match/EpisodeController.cs
  - LastTerminalReport
  - unified terminal finalization diagnostics
  - guarded stop handling on forced reset before runtime terminal transition
- Assets/Scripts/ML/RuntimeRewardCollector.cs
  - terminal reason mapping now uses EpisodeTerminalEvaluator
  - explicit InvalidRuntimeState terminal event support
- Assets/Scripts/ML/RewardTerminalContractTypes.cs
  - RewardConfig.TerminalInvalidRuntimeState

Week 3 production action pipeline was not rewritten:

observation -> mask -> action -> decoder -> applier -> MatchManager.ApplyCommand()

## 2) Terminal Truth Source

Runtime authority remains unchanged:

- MatchManager and VictoryResolver define actual match ending (phase, winner, end reason).
- RL-facing terminal reason is now derived from runtime snapshot only, via EpisodeTerminalEvaluator.

No separate RL victory system was introduced.

## 3) Supported Terminal Reasons (Day 3)

The Day 3 terminal layer supports:

- Win
- Loss
- Draw
- Timeout
- InvalidRuntimeState (with two named subtypes — see section 3a)

Mapping rules:

- Timeout is emitted only when runtime has ended and MatchEndReason is StepLimitReached.
- Draw is neutral winner with a non-StepLimitReached runtime end reason.
- InvalidRuntimeState covers anomalous or guarded terminal cases (see subtypes below).

### 3a) InvalidRuntimeState Subtypes (Day 3)

Two named subtypes are recorded in the DiagnosticDescription field prefix:

[AnomalousEndedState]
  When: runtime Phase == Ended but MatchEndReason == None.
  Cause: match lifecycle produced a terminal state without a valid end reason.
  Action: treat as conservative terminal to prevent undefined reward boundary.

[GuardedReset]
  When: EpisodeController.ResetEpisode() was called while runtime match was still Running.
  Cause: forced episode reset before the runtime match reached its own terminal state.
  Action: close episode defensively; EpisodeController logs a warning.
  Note: RuntimeWasTerminal is false for [GuardedReset], distinguishing it from all other terminal cases.

No other cases are currently mapped to InvalidRuntimeState. This list is intentionally bounded.

## 4) Runtime/Reward/EpisodeController Consistency

Consistency guarantees implemented:

- Reward collector and EpisodeController read the same terminal evaluator logic.
- EpisodeController terminal diagnostics are fixed before auto-restart of the next episode.
- Reset path clears reward/terminal state for the next episode.
- Baseline heuristic path and future RL path use the same terminal truth surface through EpisodeController.

Mismatch detection:

- EpisodeController logs a warning when reward terminal reason diverges from controller terminal evaluation.
- The warning includes full diagnostic context: RewardLayer reason, Controller reason, RuntimeEndReason,
  Winner, Step, TerminalRewardBucket, RuntimeWasTerminal, Diagnostic description.
- This remains a warning-level diagnostic — it does not stop or abort the production loop.
- Mismatch is expected and correct when a [GuardedReset] occurs, since the reward layer reflects the
  last live match state while the controller reports InvalidRuntimeState.

## 5) End-of-Episode Diagnostics

EpisodeController reports terminal details through LastTerminalReport and logs:

- RL-facing terminal reason
- runtime end reason
- winner
- TerminalEventProcessed flag (see section 5a)
- TerminalRewardNonZero flag (see section 5a)
- terminal step
- reward summary breakdown (total/economy/combat/terminal/shaping/events)
- diagnostic description (includes subtype marker for InvalidRuntimeState)

This output is intended to verify runtime-to-RL terminal alignment, not just announce episode end.

### 5a) TerminalEventProcessed vs TerminalRewardNonZero

EpisodeEndReport uses two distinct fields, not a single "terminal reward applied" flag:

TerminalEventProcessed
  True when the evaluator recognised a terminal case and ran the terminal path.
  Set regardless of whether the resulting reward magnitude is zero.
  Example: Draw or Timeout with default 0.0 config → TerminalEventProcessed=true, TerminalRewardNonZero=false.

TerminalRewardNonZero
  True only when the terminal reward bucket in RewardBreakdown contains a non-zero accumulated value.
  Governed by actual config magnitudes, not by whether a terminal case was detected.

This prevents the ambiguity where a neutral terminal outcome (reward=0) could be misread as
"terminal semantics did not run".

## 6) Timeout Semantics

Timeout is treated as a distinct terminal reason, not as a variant of Draw:

- Trigger: runtime Phase == Ended AND MatchEndReason == StepLimitReached AND winner == Neutral.
- RL-facing reason: TerminalReason.Timeout.
- Reward event: RewardEventType.TerminalTimeout with magnitude RewardConfig.TerminalTimeout.
- Default magnitude: 0.0 (neutral outcome — no reward and no penalty).
- Optional tuning: set TerminalTimeout to a small negative value to discourage passive play.

Timeout is NOT mapped through Draw semantics. Draw is reserved for game-logic neutral outcomes
(e.g. simultaneous base destruction) reported with a non-StepLimitReached end reason.

AddEvent skips zero-magnitude events, so with default config no TerminalTimeout event will appear
in the step trace — but TerminalEventProcessed will still be true.

RewardCollectorOptions.EnableTimeoutPenalty is now reserved for future use and is currently a no-op.
The entire optional/tunable character of timeout reward lives in RewardConfig.TerminalTimeout directly.

Guarded reset (forced episode close before step limit): this is NOT treated as Timeout.
It is mapped to InvalidRuntimeState [GuardedReset] with RuntimeWasTerminal=false.

## 7) Reset/New Episode Hygiene

On episode start:

- RuntimeRewardCollector.ResetEpisode() is called.
- LastRewardStepTrace, LastRewardBreakdown, and LastTerminalReport are reset.

On terminal finalization:

- terminal report is captured first;
- logger end hook is called;
- auto-restart can begin after report capture.

This prevents terminal state leakage into the next episode.

## 8) Day 3 Boundaries (Intentionally Not Done)

Not part of this change:

- full ML-Agents OnActionReceived wiring
- full policy integration rewrite
- attack_target[26] semantics expansion
- broader reward redesign beyond terminal semantics/lifecycle consistency

## 9) Residual Risks After Day 3 Finishing Pass

The following remain acknowledged residual risks at the end of Day 3:

AddEvent zero-magnitude suppression
  With default config (TerminalDraw=0, TerminalTimeout=0), no terminal event appears in the step trace
  for draw or timeout outcomes. TerminalEventProcessed=true correctly captures that the path executed,
  but the events list and EventCount will not reflect it. Acceptable for Day 3; visible via TerminalEventProcessed.

EnableTimeoutPenalty is a no-op
  The field is preserved for forward-compatibility but has no runtime effect.
  A future Day 4 caller who sets it will not observe the expected behaviour without revisiting AddTerminalEvents.
  Risk is low because the field defaults to false. Documented in code.

InvalidRuntimeState subtype taxonomy is flat
  Only two subtypes exist ([AnomalousEndedState] and [GuardedReset]) and they are encoded in the
  DiagnosticDescription string rather than a dedicated enum. If a third category emerges, it will need
  a new subtype marker. The bounded list is documented in section 3a.

Mismatch detection condition
  Mismatch is only detected when summary.TerminalReached is true AND summary.TerminalReason != None.
  If the reward collector never ran (e.g. _enableRuntimeRewardCollector=false), the mismatch check
  is silently skipped. This is acceptable; the log line will still record the controller-side reason.

## 10) Suggested Smoke Checks

Recommended focused checks in Play Mode:

- baseline win run: TerminalReason=Win, TerminalEventProcessed=true, TerminalRewardNonZero=true
- baseline loss run: TerminalReason=Loss, TerminalEventProcessed=true, TerminalRewardNonZero=true
- draw run: TerminalReason=Draw, TerminalEventProcessed=true, TerminalRewardNonZero=false (default config)
- max-step run: TerminalReason=Timeout, RuntimeEndReason=StepLimitReached, TerminalRewardNonZero=false
- forced reset mid-episode: TerminalReason=InvalidRuntimeState, DiagnosticDescription prefix=[GuardedReset],
  RuntimeWasTerminal=false, mismatch warning appears if reward layer saw a live match state
- post-terminal reset: new episode starts with clean reward/terminal state, no leaked LastTerminalReport
