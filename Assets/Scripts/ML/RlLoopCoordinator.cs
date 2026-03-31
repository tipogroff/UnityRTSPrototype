// RlLoopCoordinator.cs — Week 4 Day 4: canonical RL loop phase coordinator.
//
// Execution order (canonical — enforced in RlLoopCoordinator.ExecuteFullStep):
//   Phase 1: PreStepCapture   — CaptureSnapshot (reward baseline, read pre-step runtime state)
//   Phase 2: Observation      — BuildObservationPackage (pre-step boundary start)
//   Phase 3: Mask             — BuildTransferCompatibleMask (same pre-step state as observation)
//   Phase 4: ActionSubmit     — IDecisionSource.Execute → production path →
//                               ActionDecoder → ActionApplier → MatchManager.ApplyCommand
//   Phase 5: RuntimeStep      — MatchManager.StepMatch() EXACTLY ONCE (anti-double-step guard)
//   Phase 6: PostStepCapture  — CaptureSnapshot (post-step state for reward delta)
//   Phase 7: RewardEval       — EvaluateStep (post-step runtime effects ONLY)
//   Phase 8: TerminalEval     — EpisodeTerminalEvaluator.Evaluate (post-step state ONLY)
//   Phase 9: StepReport       — Build RlLoopStepReport with per-phase diagnostics
//
// Pre-step boundary:  Phases 1–3 all read from game state BEFORE StepMatch.
// Post-step boundary: Phases 6–8 read from game state AFTER StepMatch.
//
// Anti-double-step guard: _runtimeStepAdvancedThisCycle, reset per cycle.
// If a second StepMatch is attempted within the same ExecuteFullStep call, the guard
// blocks it and logs an error. The flag DoubleStepPrevented is set in the report.
//
// IDecisionSource contract:
//   - Implementations submit actions through the production path.
//   - Implementations MUST NOT call MatchManager.StepMatch().
//   - Baseline path (BaselineDecisionSource) and future RL path (PolicyDecisionSource)
//     share identical phasing: both are callers of Phase 4, receive the same pre-step mask.
//
// Note on dual-build baseline path (residual technical debt, Day 4):
//   The coordinator creates its own MlPolicyPipelineFacade to build obs/mask in Phases 2-3.
//   BaselineDecisionSource routes through HeuristicPolicyAdapter, which has its own façade and
//   rebuilds equivalent obs/mask internally via DecideAndApplyInternal. This means two full
//   obs/mask builds happen per cycle in baseline mode.
//   Both facades read the same pre-step game state, so results are equivalent — correctness is
//   not affected. The double-build has been localised and documented but not eliminated.
//   Eliminating it requires refactoring HeuristicPolicyAdapter to accept pre-built obs/mask
//   from the coordinator — deferred to Day 5+ (see PolicyDecisionSource contract).

using System;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.ML
{
    // ─────────────────────────────────────────────────────────────────────────────
    // Step report
    // ─────────────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Canonical per-cycle step diagnostic produced by <see cref="RlLoopCoordinator.ExecuteFullStep"/>.
    ///
    /// Records which phases executed, whether each succeeded, and the full reward
    /// and terminal traces produced in the post-step window.
    ///
    /// Useful for catching:
    /// - double-step: <see cref="DoubleStepPrevented"/> == true
    /// - wrong-phase reward read: reward trace should always carry non-stale data
    /// - wrong-phase terminal read: <see cref="TerminalEvaluated"/> reflects post-step state
    /// - obs/mask boundary mismatch: <see cref="ObservationBuilt"/> and <see cref="MaskBuilt"/>
    ///   are both set in the same pre-step window
    /// - source-mode mismatch: <see cref="SourceMode"/> labels each cycle
    /// </summary>
    public readonly struct RlLoopStepReport
    {
        public RlLoopStepReport(
            int stepIndex,
            string sourceMode,
            bool observationBuilt,
            bool maskBuilt,
            bool actionApplied,
            int actionsAccepted,
            int actionsRejected,
            bool actionCountsAvailable,
            bool runtimeStepAdvanced,
            bool doubleStepPrevented,
            int matchStepDelta,
            bool rewardEmitted,
            float rewardTotal,
            bool terminalEvaluated,
            bool isTerminal,
            TerminalReason terminalReason,
            RewardStepTrace rewardTrace,
            TerminalEvaluationResult terminalResult)
        {
            StepIndex = stepIndex;
            SourceMode = sourceMode ?? "unknown";
            ObservationBuilt = observationBuilt;
            MaskBuilt = maskBuilt;
            ActionApplied = actionApplied;
            ActionsAccepted = actionsAccepted;
            ActionsRejected = actionsRejected;
            ActionCountsAvailable = actionCountsAvailable;
            RuntimeStepAdvanced = runtimeStepAdvanced;
            DoubleStepPrevented = doubleStepPrevented;
            MatchStepDelta = matchStepDelta;
            RewardEmitted = rewardEmitted;
            RewardTotal = rewardTotal;
            TerminalEvaluated = terminalEvaluated;
            IsTerminal = isTerminal;
            TerminalReason = terminalReason;
            RewardTrace = rewardTrace;
            TerminalResult = terminalResult;
        }

        // ── Cycle identity ──────────────────────────────────────────────────────

        /// <summary>Cumulative step counter within the current episode (1-based after first step).</summary>
        public int StepIndex { get; }

        /// <summary>Action source mode label. E.g. "baseline-heuristic", "baseline-legacy", "idle", "ml-policy".</summary>
        public string SourceMode { get; }

        // ── Pre-step phase diagnostics (Phases 1–3) ─────────────────────────────

        /// <summary>
        /// True when the coordinator built an observation package at the pre-step boundary (Phase 2).
        /// Both ObservationBuilt and MaskBuilt should be true together — a mismatch indicates
        /// that one of the pre-step builds failed or was skipped.
        /// </summary>
        public bool ObservationBuilt { get; }

        /// <summary>True when the coordinator built a valid action mask at the pre-step boundary (Phase 3).</summary>
        public bool MaskBuilt { get; }

        // ── Action submit phase diagnostics (Phase 4) ───────────────────────────

        /// <summary>
        /// True when the decision source reported at least one accepted action.
        /// For baseline-heuristic, this is a synthetic flag derived from the source report
        /// (exact counts are tracked internally by ActionApplier; see MatchManager.InvalidCommandsLastStep).
        /// </summary>
        public bool ActionApplied { get; }

        /// <summary>
        /// Actions accepted this cycle as reported by the decision source.
        /// For baseline sources the value may be 0 (source didn't surface per-action counts).
        /// </summary>
        public int ActionsAccepted { get; }

        /// <summary>
        /// Actions rejected this cycle as reported by the decision source.
        /// When ActionCountsAvailable=false, this is 0 by convention — not "truly zero rejected".
        /// Use MatchManager.InvalidCommandsLastStep for authoritative rejected counts.
        /// </summary>
        public int ActionsRejected { get; }

        /// <summary>
        /// True when ActionsAccepted and ActionsRejected carry real pipeline counts.
        /// False when counts are unavailable at this boundary (LegacyDecisionSource,
        /// IdleDecisionSource) — those sources return PolicyExecutionReport.Empty.
        /// BaselineDecisionSource always surfaces real counts (one per enabled player).
        /// When false, see MatchManager.InvalidCommandsLastStep for partial authoritative counts.
        /// </summary>
        public bool ActionCountsAvailable { get; }

        // ── Runtime step phase diagnostics (Phase 5) ──────────────────────────────────────────

        /// <summary>True when MatchManager.StepMatch() was called this cycle (Phase 5).</summary>
        public bool RuntimeStepAdvanced { get; }

        /// <summary>
        /// True when the anti-double-step guard blocked a second StepMatch attempt.
        /// If this is true, RuntimeStepAdvanced is false and an error was logged.
        //
        /// GUARANTEE: the guard prevents a second MatchManager.StepMatch() within the same
        /// ExecuteFullStep invocation. It does NOT detect external mutations (e.g. a direct
        /// StepMatch call outside the coordinator from another MonoBehaviour).
        /// </summary>
        public bool DoubleStepPrevented { get; }

        /// <summary>
        /// Change in MatchManager's internal step counter from before Phase 5 to after Phase 5.
        /// Expected value: 1 when the runtime step advanced normally.
        /// 0 when RuntimeStepAdvanced=false (double-step prevented or match not running).
        /// Any value other than 0 or 1 indicates an anomalous MatchManager state transition
        /// (silent no-op or multi-step advance) and triggers a LogWarning in the coordinator.
        /// </summary>
        public int MatchStepDelta { get; }

        // ── Post-step phase diagnostics (Phases 6–8) ────────────────────────────

        /// <summary>True when at least one reward event was recorded post-step.</summary>
        public bool RewardEmitted { get; }

        /// <summary>Accumulated reward total for this cycle (post-step effects only).</summary>
        public float RewardTotal { get; }

        /// <summary>True when terminal evaluation ran (always true when RuntimeStepAdvanced).</summary>
        public bool TerminalEvaluated { get; }

        /// <summary>True when the evaluator found a terminal state post-step.</summary>
        public bool IsTerminal { get; }

        public TerminalReason TerminalReason { get; }

        // ── Full trace payloads ────────────────────────────────────────────────

        /// <summary>Full reward step trace. Valid only after RuntimeStep phase.</summary>
        public RewardStepTrace RewardTrace { get; }

        /// <summary>
        /// Full terminal evaluation result. Valid only after RuntimeStep phase.
        /// IsTerminal=false when the match is still running.
        /// </summary>
        public TerminalEvaluationResult TerminalResult { get; }

        /// <summary>Compact single-line diagnostic string for console logging.</summary>
        public string BuildDiagnosticLine()
        {
            string countStr = ActionCountsAvailable
                ? $"accepted:{ActionsAccepted}/rejected:{ActionsRejected}"
                : "unavailable";
            return $"[RlLoop] step={StepIndex} src={SourceMode}" +
                   $" obs={ObservationBuilt} mask={MaskBuilt}" +
                   $" action={countStr}" +
                   $" runtimeStep={RuntimeStepAdvanced}(delta={MatchStepDelta}) doubleGuard={DoubleStepPrevented}" +
                   $" reward={RewardTotal:F4} terminal={IsTerminal}({TerminalReason})";
        }
    }

    // ─────────────────────────────────────────────────────────────────────────────
    // Pre-step context bundle
    // ─────────────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Thin pre-step context bundle passed from <see cref="RlLoopCoordinator"/> to
    /// <see cref="IDecisionSource.Execute"/> at the Phase 4 boundary.
    ///
    /// Created once per <see cref="RlLoopCoordinator.ExecuteFullStep"/> cycle after Phases 1–3.
    /// Carries the coordinator's canonical pre-step obs/mask artifacts so that decision sources
    /// have access to them without rebuilding.
    ///
    /// Dual-build status (residual technical debt):
    /// - <see cref="BaselineDecisionSource"/> still routes through HeuristicPolicyAdapter, which
    ///   rebuilds compatible obs/mask internally via DecideAndApplyInternal. The double-build
    ///   has been localised and documented but NOT eliminated. Both facades read the same
    ///   pre-step state, so results are equivalent — runtime correctness is unaffected.
    /// - This bundle creates a named, explicit transfer point and narrows where the debt lives.
    /// - Future <c>PolicyDecisionSource</c> MUST use <see cref="CanonicalMask"/> directly —
    ///   no mask rebuild allowed. Eliminating the baseline double-build requires refactoring
    ///   HeuristicPolicyAdapter to consume pre-built artifacts (deferred to Day 5+).
    /// </summary>
    public readonly struct RlLoopStepInput
    {
        public RlLoopStepInput(
            int stepIndex,
            Owner perspective,
            ObservationPackage canonicalObservation,
            ActionMaskSet canonicalMask,
            MlPolicyPipelineFacade facade)
        {
            StepIndex = stepIndex;
            Perspective = perspective;
            CanonicalObservation = canonicalObservation;
            CanonicalMask = canonicalMask;
            Facade = facade;
        }

        public int StepIndex { get; }
        public Owner Perspective { get; }

        /// <summary>
        /// Coordinator-built observation package from Phase 2 (pre-step boundary).
        /// Baseline sources may reference this for alignment; future PolicyDecisionSource
        /// will consume it directly as the policy input tensor.
        /// </summary>
        public ObservationPackage CanonicalObservation { get; }

        /// <summary>
        /// Coordinator-built action mask from Phase 3 (same pre-step state as CanonicalObservation).
        /// Future PolicyDecisionSource MUST use this directly — no mask rebuild.
        /// Baseline sources build equivalent masks internally (same pre-step state → same result).
        /// </summary>
        public ActionMaskSet CanonicalMask { get; }

        /// <summary>Production pipeline facade. Available for sources that need additional operations.</summary>
        public MlPolicyPipelineFacade Facade { get; }
    }

    // ─────────────────────────────────────────────────────────────────────────────
    // Decision source interface and built-in implementations
    // ─────────────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Swappable action source for Phase 4 of the RL loop.
    ///
    /// Contract:
    /// - Implementations submit actions through the production path:
    ///   obs/mask → decode → ActionApplier → MatchManager.ApplyCommand().
    /// - Implementations MUST NOT call MatchManager.StepMatch().
    /// - All sources (baseline, legacy, idle, future ML-Agent) share identical phase ordering.
    ///
    /// The coordinator passes a <see cref="RlLoopStepInput"/> bundle at the Phase 4 boundary
    /// carrying the canonical pre-step obs/mask. Baseline sources may reference CanonicalMask
    /// or build equivalent masks internally (same pre-step state → same result). Future
    /// <c>PolicyDecisionSource</c> MUST consume <see cref="RlLoopStepInput.CanonicalMask"/> directly.
    /// </summary>
    public interface IDecisionSource
    {
        /// <summary>Short source mode label for RlLoopStepReport.SourceMode.</summary>
        string SourceMode { get; }

        /// <summary>
        /// Execute one decision cycle through the production pipeline.
        /// Must not call MatchManager.StepMatch().
        /// </summary>
        /// <param name="stepInput">
        /// Pre-step context bundle from the coordinator. Contains canonical obs/mask from
        /// Phases 2–3. Baseline sources may reference CanonicalMask; future PolicyDecisionSource
        /// must use it directly without rebuilding.
        /// </param>
        PolicyExecutionReport Execute(RlLoopStepInput stepInput);
    }

    /// <summary>
    /// Baseline decision source: routes through HeuristicPolicyAdapter (Week 3 Day 5 pipeline).
    ///
    /// Handles both Player1 and Player2 in a single call via ExecuteDecisionStepWithCounts(),
    /// ensuring the same production path used by future ML-Agent consumers.
    ///
    /// Action counts: each enabled player submits at most one decision per call (0 or 1 per player,
    /// max 2 accepted for self-play). Counts are surfaced via HeuristicDecisionTrace.ActionAccepted.
    /// Authoritative totals are also in MatchManager.InvalidCommandsLastStep.
    ///
    /// Dual-build status (Day 5): the adapter now consumes canonical obs/mask from stepInput for
    /// stepInput.Perspective, which removes one rebuild path in baseline mode.
    /// For the second player in self-play baseline, adapter still rebuilds via its own facade.
    /// Full elimination across both players requires wider HeuristicPolicyAdapter refactor.
    /// </summary>
    public sealed class BaselineDecisionSource : IDecisionSource
    {
        private readonly HeuristicPolicyAdapter _adapter;

        /// <param name="adapter">
        /// HeuristicPolicyAdapter wired in scene. May be null — if null, Execute is a no-op.
        /// </param>
        public BaselineDecisionSource(HeuristicPolicyAdapter adapter)
        {
            _adapter = adapter;
        }

        public string SourceMode => "baseline-heuristic";

        public PolicyExecutionReport Execute(RlLoopStepInput stepInput)
        {
            if (_adapter == null)
            {
                return PolicyExecutionReport.Empty;
            }

            // Production path: both Player1 and Player2 decisions routed through
            // observation → mask → debug-action-selection → ActionDecoder → ActionApplier → MatchManager.ApplyCommand.
            // Day 5 integration: pass canonical pre-step artifacts from the coordinator.
            // The adapter consumes them for stepInput.Perspective to avoid rebuilding this part.
            // Self-play still has residual rebuild for the non-perspective player.
            var (accepted, rejected) = _adapter.ExecuteDecisionStepWithCounts(stepInput);
            return new PolicyExecutionReport(null, accepted, rejected, null, null);
        }
    }

    /// <summary>
    /// Legacy decision source: routes through HeuristicDriver (pre-Day5 direct path).
    ///
    /// Used as fallback when HeuristicPolicyAdapter is not available and HeuristicExecutionPath
    /// is set to LegacyDirectDriver. Maintains the same phase contract as BaselineDecisionSource.
    /// </summary>
    public sealed class LegacyDecisionSource : IDecisionSource
    {
        private readonly HeuristicDriver _driver;

        public LegacyDecisionSource(HeuristicDriver driver)
        {
            _driver = driver;
        }

        public string SourceMode => "baseline-legacy";

        public PolicyExecutionReport Execute(RlLoopStepInput stepInput)
        {
            if (_driver == null)
            {
                return PolicyExecutionReport.Empty;
            }

            // Legacy direct driver path. HeuristicDriver.MakeAllDecisions() does not surface
            // per-action counts at this boundary. PolicyExecutionReport.Empty is returned
            // (CountsAvailable=false), which BuildDiagnosticLine reports as "unavailable".
            _driver.MakeAllDecisions();
            return PolicyExecutionReport.Empty;
        }
    }

    /// <summary>
    /// Idle decision source: submits no actions.
    ///
    /// Used when heuristic AI is disabled or in passive observation mode.
    /// Satisfies the same phase contract as active sources without any pipeline call.
    /// This allows the RL loop to still advance the runtime step, collect reward,
    /// and evaluate terminal state without submitting any action.
    /// </summary>
    public sealed class IdleDecisionSource : IDecisionSource
    {
        public static readonly IdleDecisionSource Instance = new IdleDecisionSource();

        private IdleDecisionSource() { }

        public string SourceMode => "idle";

        public PolicyExecutionReport Execute(RlLoopStepInput stepInput)
        {
            return PolicyExecutionReport.Empty;
        }
    }

    /// <summary>
    /// [FUTURE INTEGRATION POINT — NOT IMPLEMENTED]
    ///
    /// Placeholder for the ML-Agent policy decision source (Week 4 Day 5+).
    ///
    /// When implemented, this class will:
    /// - Accept ActionBuffers from the ML-Agent OnActionReceived callback.
    /// - Decode actions through ActionDecoder using the canonical production path.
    /// - Apply decoded actions through ActionApplier → MatchManager.ApplyCommand.
    /// - Consume <see cref="RlLoopStepInput.CanonicalMask"/> directly (no mask rebuild).
    /// - NOT call MatchManager.StepMatch() (IDecisionSource contract).
    ///
    /// This class exists only to clearly mark the future integration surface.
    /// Instantiating it throws <see cref="NotImplementedException"/>.
    /// Until implemented, all RL loop cycles use BaselineDecisionSource or IdleDecisionSource.
    ///
    /// Tracking: Week 4 Day 5 — ML-Agent sensor/actuator wiring.
    /// </summary>
    public sealed class PolicyDecisionSource : IDecisionSource
    {
        public PolicyDecisionSource()
        {
            throw new NotImplementedException(
                "PolicyDecisionSource is a future integration point (Week 4 Day 5+). " +
                "ML-Agent policy wiring is not yet implemented. " +
                "Use BaselineDecisionSource for control mode or IdleDecisionSource for passive observation.");
        }

        public string SourceMode => "ml-policy";

        public PolicyExecutionReport Execute(RlLoopStepInput stepInput)
        {
            throw new NotImplementedException(
                "PolicyDecisionSource.Execute: future ML-Agent integration. Not yet implemented.");
        }
    }

    // ─────────────────────────────────────────────────────────────────────────────
    // Coordinator
    // ─────────────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Canonical RL loop phase coordinator (Week 4 Day 4).
    ///
    /// Formalises the 9-phase execution order for every agent decision cycle.
    /// Its single responsibility is to sequence the existing pipeline components
    /// in a deterministic, diagnosable order — it does not introduce new execution paths.
    ///
    /// Phase summary:
    ///   1  PreStepCapture   — CaptureSnapshot for reward delta baseline
    ///   2  Observation      — BuildObservationPackage (pre-step boundary start)
    ///   3  Mask             — BuildTransferCompatibleMask (same pre-step state)
    ///   4  ActionSubmit     — IDecisionSource.Execute → ActionApplier → MatchManager.ApplyCommand
    ///   5  RuntimeStep      — MatchManager.StepMatch EXACTLY ONCE
    ///   6  PostStepCapture  — CaptureSnapshot (post-step state)
    ///   7  RewardEval       — EvaluateStep (post-step effects)
    ///   8  TerminalEval     — EpisodeTerminalEvaluator.Evaluate (post-step)
    ///   9  StepReport       — RlLoopStepReport with all diagnostics
    ///
    /// Invariants:
    /// - Observation and mask are ALWAYS captured before StepMatch.
    /// - Reward and terminal are ALWAYS read after StepMatch.
    /// - StepMatch is called at most once per ExecuteFullStep invocation (double-step guard).
    ///
    /// This class is not a MonoBehaviour. It is owned and reset by EpisodeController.
    /// </summary>
    public sealed class RlLoopCoordinator
    {
        private readonly MlPolicyPipelineFacade _facade;
        private readonly RuntimeRewardCollector _rewardCollector;
        private readonly MatchManager _matchManager;
        private readonly UnitRegistry _unitRegistry;

        // Anti-double-step guard. Reset at the end of each ExecuteFullStep cycle.
        private bool _runtimeStepAdvancedThisCycle;

        // Episode-scoped step counter. Reset in ResetLoop().
        private int _episodeStepIndex;

        public RlLoopCoordinator(
            MlPolicyPipelineFacade facade,
            RuntimeRewardCollector rewardCollector,
            MatchManager matchManager,
            UnitRegistry unitRegistry)
        {
            _facade = facade ?? throw new ArgumentNullException(nameof(facade));
            _rewardCollector = rewardCollector ?? throw new ArgumentNullException(nameof(rewardCollector));
            _matchManager = matchManager ?? throw new ArgumentNullException(nameof(matchManager));
            _unitRegistry = unitRegistry;
        }

        /// <summary>Most recent step report. Default struct until the first ExecuteFullStep call.</summary>
        public RlLoopStepReport LastStepReport { get; private set; }

        /// <summary>
        /// Resets episode-scoped coordinator state.
        /// Call at the start of each new episode (EpisodeController.StartNewEpisode).
        /// </summary>
        public void ResetLoop()
        {
            _episodeStepIndex = 0;
            _runtimeStepAdvancedThisCycle = false;
            LastStepReport = default;
        }

        /// <summary>
        /// Execute one complete RL loop cycle in canonical phase order.
        ///
        /// Precondition: MatchManager.Phase == Running. If the match is not running
        /// a warning is logged and the report has RuntimeStepAdvanced=false.
        ///
        /// Postcondition: all 9 phases have run in order; LastStepReport is updated.
        /// </summary>
        /// <param name="perspective">
        /// Owner perspective for observation, mask, reward evaluation, and terminal evaluation.
        /// For baseline self-play, both players act in Phase 4 (inside the decision source),
        /// but reward/terminal are evaluated from this single perspective.
        /// </param>
        /// <param name="decisionSource">Action source for Phase 4. Must not call StepMatch.</param>
        public RlLoopStepReport ExecuteFullStep(Owner perspective, IDecisionSource decisionSource)
        {
            if (decisionSource == null) throw new ArgumentNullException(nameof(decisionSource));

            if (_matchManager.Phase != MatchPhase.Running)
            {
                Debug.LogWarning(
                    $"[RlLoopCoordinator] ExecuteFullStep called with phase={_matchManager.Phase}. " +
                    $"Expected Running. Step not executed. source={decisionSource.SourceMode}");
                return default;
            }

            // ── Phase 1: Pre-step capture (reward baseline) ────────────────────
            // Reads pre-step runtime state: resources, units, buildings.
            // INVARIANT: No StepMatch may occur between Phase 1 and Phase 3.
            RewardRuntimeSnapshot preSnapshot = _rewardCollector.CaptureSnapshot(_matchManager, _unitRegistry);

            // ── Phase 2: Build observation (pre-step boundary) ─────────────────
            // Anchored to same runtime state as Phase 1 (pre-step).
            ObservationPackage preObs = _facade.BuildObservationPackage(perspective, ObservationMode.UnityMvpTransfer);
            bool observationBuilt = preObs.SpatialObservation != null && preObs.SpatialObservation.Length > 0;

            // ── Phase 3: Build mask (same pre-step state as observation) ────────
            // INVARIANT: Observation (Phase 2) and mask (Phase 3) must be read from
            // the same runtime state. No mutation between them.
            ActionMaskSet preMask = _facade.BuildTransferCompatibleMask(perspective);
            bool maskBuilt = preMask != null;

            // ── Phase 4: Submit action (through production path) ─────────────────
            // Build the pre-step context bundle. This carries canonical obs/mask to the
            // decision source without requiring a rebuild. Baseline sources still build
            // equivalent artifacts internally (same pre-step state → same result).
            // Future PolicyDecisionSource MUST use stepInput.CanonicalMask directly.
            var stepInput = new RlLoopStepInput(
                stepIndex: _episodeStepIndex + 1,
                perspective: perspective,
                canonicalObservation: preObs,
                canonicalMask: preMask,
                facade: _facade);

            // Decision source routes through ActionDecoder → ActionApplier → MatchManager.ApplyCommand.
            // MUST NOT call MatchManager.StepMatch().
            PolicyExecutionReport actionReport = decisionSource.Execute(stepInput);
            bool actionApplied = actionReport.AcceptedCount > 0;

            // ── Phase 5: Advance runtime step (EXACTLY ONCE — guarded) ──────────
            // Capture match step index for post-step delta invariant check ([StepInvariant]).
            int matchStepBefore = _matchManager.GetMatchState().Step;
            bool doubleStepPrevented = false;
            bool runtimeStepAdvanced = false;

            if (_runtimeStepAdvancedThisCycle)
            {
                // [DoubleStepGuard] The runtime step was already advanced this cycle.
                // A second StepMatch was attempted — this is a logic error.
                // Check whether any code path calls MatchManager.StepMatch() independently.
                doubleStepPrevented = true;
                Debug.LogError(
                    $"[RlLoopCoordinator][DoubleStepGuard] StepMatch blocked at step={_episodeStepIndex + 1}. " +
                    $"A runtime step was already advanced in this cycle. " +
                    $"source={decisionSource.SourceMode}. " +
                    $"Investigate: check EpisodeController FixedUpdate, StepEpisodeOnce, " +
                    $"or any other caller that may advance MatchManager.StepMatch() outside the coordinator.");
            }
            else
            {
                _runtimeStepAdvancedThisCycle = true;
                runtimeStepAdvanced = true;
                // The single authoritative runtime step for this cycle.
                // MatchManager.OnMatchEnded fires synchronously here if the match just ended.
                _matchManager.StepMatch();
            }

            // [StepInvariant] Verify exactly one step was consumed by StepMatch.
            // GUARANTEE: the guard above prevents a second StepMatch within ExecuteFullStep.
            // LIMITATION: this does NOT detect external StepMatch calls from other components.
            // delta=1 is the normal case. delta=0 is a silent no-op. Any other value is anomalous.
            int matchStepDelta = runtimeStepAdvanced ? (_matchManager.GetMatchState().Step - matchStepBefore) : 0;
            if (runtimeStepAdvanced && matchStepDelta != 1)
            {
                Debug.LogWarning(
                    $"[RlLoopCoordinator][StepInvariant] Expected match step delta=1 after StepMatch, " +
                    $"got delta={matchStepDelta} (matchBefore={matchStepBefore}). " +
                    $"episode_step={_episodeStepIndex + 1}, source={decisionSource.SourceMode}. " +
                    $"Investigate MatchManager.StepMatch (possible silent no-op or multi-step advance).");
            }

            // ── Phase 6: Post-step capture ──────────────────────────────────────
            // INVARIANT: Only reached after Phase 5. Pre-step state is no longer valid here.
            // Reward delta is computed as post minus pre in Phase 7.
            RewardRuntimeSnapshot postSnapshot = _rewardCollector.CaptureSnapshot(_matchManager, _unitRegistry);

            // ── Phase 7: Reward evaluation (post-step runtime effects) ──────────
            // INVARIANT: EvaluateStep reads effects that materialised after StepMatch.
            //            Calling before StepMatch would produce stale (pre-step) reward.
            RewardStepTrace rewardTrace = _rewardCollector.EvaluateStep(preSnapshot, postSnapshot, perspective);
            bool rewardEmitted = rewardTrace.Events != null && rewardTrace.Events.Count > 0;
            float rewardTotal = rewardTrace.Breakdown.Total;

            // ── Phase 8: Terminal evaluation (post-step state) ──────────────────
            // INVARIANT: Terminal is read from runtime state after Phase 5.
            //            Pre-step terminal reads would produce wrong episode boundaries
            //            (a match that ended during StepMatch would appear non-terminal).
            MatchStateSnapshot matchState = _matchManager.GetMatchState();
            TerminalEvaluationResult terminalResult = EpisodeTerminalEvaluator.Evaluate(matchState, perspective);

            // ── Phase 9: Build step report ──────────────────────────────────────
            _episodeStepIndex++;
            _runtimeStepAdvancedThisCycle = false; // Reset guard for next cycle.

            var report = new RlLoopStepReport(
                stepIndex: _episodeStepIndex,
                sourceMode: decisionSource.SourceMode,
                observationBuilt: observationBuilt,
                maskBuilt: maskBuilt,
                actionApplied: actionApplied,
                actionsAccepted: actionReport.AcceptedCount,
                actionsRejected: actionReport.RejectedCount,
                actionCountsAvailable: actionReport.CountsAvailable,
                runtimeStepAdvanced: runtimeStepAdvanced,
                doubleStepPrevented: doubleStepPrevented,
                matchStepDelta: matchStepDelta,
                rewardEmitted: rewardEmitted,
                rewardTotal: rewardTotal,
                terminalEvaluated: true,
                isTerminal: terminalResult.IsTerminal,
                terminalReason: terminalResult.TerminalReason,
                rewardTrace: rewardTrace,
                terminalResult: terminalResult);

            LastStepReport = report;
            return report;
        }
    }
}
