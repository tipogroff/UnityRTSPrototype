using System;
using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;

namespace RTS.ML
{
    /// <summary>
    /// Execution report for one policy submission through the Week 3 pipeline.
    ///
    /// This report is diagnostic metadata only. Authoritative world-state changes still
    /// happen exclusively in ActionApplier and MatchManager.
    /// </summary>
    public readonly struct PolicyExecutionReport
    {
        private readonly AgentAction[] _decodedActions;
        private readonly string[] _rejectionReasons;

        public PolicyExecutionReport(
            IReadOnlyList<AgentAction> decodedActions,
            int acceptedCount,
            int rejectedCount,
            IReadOnlyList<string> rejectionReasons,
            InvalidActionAttemptLog? lastInvalidAttempt)
        {
            _decodedActions = Copy(decodedActions);
            _rejectionReasons = Copy(rejectionReasons);
            AcceptedCount = acceptedCount;
            RejectedCount = rejectedCount;
            LastInvalidAttempt = lastInvalidAttempt;
        }

        /// <summary>
        /// Actions produced by the decoder before authoritative apply-time validation.
        /// </summary>
        public IReadOnlyList<AgentAction> DecodedActions => _decodedActions;

        /// <summary>
        /// Number of commands accepted by ActionApplier during this submission.
        /// </summary>
        public int AcceptedCount { get; }

        /// <summary>
        /// Number of commands rejected by ActionApplier during this submission.
        /// </summary>
        public int RejectedCount { get; }

        /// <summary>
        /// Apply-time rejection reasons collected for the current submission.
        /// </summary>
        public IReadOnlyList<string> RejectionReasons => _rejectionReasons;

        /// <summary>
        /// Last structured invalid-attempt record emitted while applying this submission.
        /// </summary>
        public InvalidActionAttemptLog? LastInvalidAttempt { get; }

        /// <summary>
        /// Convenience accessor for the first rejection reason, if any.
        /// </summary>
        public string PrimaryRejectionReason => _rejectionReasons.Length > 0 ? _rejectionReasons[0] : string.Empty;

        /// <summary>
        /// Empty report with zero accepted/rejected actions and no rejection reasons.
        /// Used by decision sources that do not surface per-action counts at the IDecisionSource boundary.
        /// </summary>
        public static PolicyExecutionReport Empty => new PolicyExecutionReport(
            null, 0, 0, null, null);

        private static AgentAction[] Copy(IReadOnlyList<AgentAction> source)
        {
            if (source == null || source.Count == 0)
            {
                return Array.Empty<AgentAction>();
            }

            var copy = new AgentAction[source.Count];
            for (int i = 0; i < source.Count; i++)
            {
                copy[i] = source[i];
            }

            return copy;
        }

        private static string[] Copy(IReadOnlyList<string> source)
        {
            if (source == null || source.Count == 0)
            {
                return Array.Empty<string>();
            }

            var copy = new string[source.Count];
            for (int i = 0; i < source.Count; i++)
            {
                copy[i] = source[i];
            }

            return copy;
        }
    }

    /// <summary>
    /// Stable Week 3 facade for future policy consumers.
    ///
    /// This wrapper does not introduce a new execution path. It packages the existing
    /// pipeline entry points:
    /// observation -> mask -> decoder -> applier -> MatchManager.ApplyCommand().
    ///
    /// Semantic layers remain explicit:
    /// - observation modes distinguish reference-compatible and Unity transfer surfaces;
    /// - masks remain pre-sampling hints only;
    /// - ActionApplier remains the authoritative runtime gate.
    /// </summary>
    public sealed class MlPolicyPipelineFacade
    {
        private readonly ObservationBuilder _observationBuilder;
        private readonly ActionMaskBuilder _actionMaskBuilder;
        private readonly ActionDecoder _actionDecoder;
        private readonly ActionApplier _actionApplier;

        public MlPolicyPipelineFacade(
            GridManager gridManager,
            UnitRegistry unitRegistry,
            ResourceManager resourceManager,
            MatchManager matchManager,
            MatchBootstrap matchBootstrap = null)
        {
            if (gridManager == null) throw new ArgumentNullException(nameof(gridManager));
            if (unitRegistry == null) throw new ArgumentNullException(nameof(unitRegistry));
            if (matchManager == null) throw new ArgumentNullException(nameof(matchManager));

            _observationBuilder = new ObservationBuilder(gridManager, unitRegistry, resourceManager);
            _actionMaskBuilder = new ActionMaskBuilder(matchManager, gridManager, resourceManager, unitRegistry, matchBootstrap);
            _actionDecoder = new ActionDecoder(gridManager, unitRegistry);
            _actionApplier = new ActionApplier(gridManager, unitRegistry, matchManager, resourceManager);
        }

        /// <summary>
        /// Builds the observation payload that a future ML-Agent policy will consume.
        /// </summary>
        public ObservationPackage BuildObservationPackage(Owner playerId, ObservationMode mode = ObservationMode.UnityMvpTransfer)
        {
            return _observationBuilder.BuildObservationPackage(playerId, mode);
        }

        /// <summary>
        /// Builds the transfer-compatible mask surface for the current player.
        ///
        /// This mask is a pre-sampling layer only. Any action selected from it may still be
        /// rejected by ActionApplier because runtime-authoritative validation is downstream.
        /// </summary>
        public ActionMaskSet BuildTransferCompatibleMask(Owner playerId, bool noOpOnlyWhenNotRunning = true)
        {
            return _actionMaskBuilder.BuildTransferCompatibleMask(playerId, noOpOnlyWhenNotRunning);
        }

        /// <summary>
        /// Decodes transfer-compatible multi-discrete branches into AgentAction values.
        ///
        /// The returned actions are not yet runtime-authoritative. Apply them through
        /// ApplyDecodedActions or ExecuteTransferCompatible to reach MatchManager.
        /// </summary>
        public IReadOnlyList<AgentAction> DecodeTransferCompatibleBatch(int[] actionFlat, Owner playerPerspective)
        {
            return _actionDecoder.DecodeTransferCompatibleBatch(actionFlat, playerPerspective);
        }

        /// <summary>
        /// Applies already-decoded actions through ActionApplier.
        ///
        /// Use this when a future policy consumer needs explicit inspection of decoded actions
        /// before they are submitted to the runtime.
        /// </summary>
        public PolicyExecutionReport ApplyDecodedActions(
            IReadOnlyList<AgentAction> actions,
            Owner playerPerspective,
            ActionMaskSet maskAtSelection = null,
            string sourceActionFormat = null)
        {
            int accepted = _actionApplier.ApplyActions(actions, playerPerspective, maskAtSelection, sourceActionFormat);
            return new PolicyExecutionReport(
                actions,
                accepted,
                _actionApplier.RejectedActionsLastStep,
                _actionApplier.RejectionReasonsLastStep,
                _actionApplier.LastInvalidAttempt);
        }

        /// <summary>
        /// Combined Week 4-ready entry point for transfer-compatible policy output.
        ///
        /// The method preserves the current Week 3 architecture: it decodes policy branches and
        /// then submits them through the same ActionApplier and MatchManager path used elsewhere.
        /// </summary>
        public PolicyExecutionReport ExecuteTransferCompatible(
            int[] actionFlat,
            Owner playerPerspective,
            ActionMaskSet maskAtSelection = null,
            string sourceActionFormat = "ml-policy")
        {
            var decodedActions = _actionDecoder.DecodeTransferCompatibleBatch(actionFlat, playerPerspective);
            return ApplyDecodedActions(decodedActions, playerPerspective, maskAtSelection, sourceActionFormat);
        }

        internal DebugActionMaskSet BuildDebugMask(Owner playerId, bool noOpOnlyWhenNotRunning = true)
        {
            return _actionMaskBuilder.BuildDebugMask(playerId, noOpOnlyWhenNotRunning);
        }

        internal PolicyExecutionReport ExecuteDebugSelection(
            DebugActionSelection selection,
            Owner playerPerspective,
            ActionMaskSet maskAtSelection = null,
            string sourceActionFormat = null)
        {
            AgentAction decodedAction = _actionDecoder.DecodeDebug(
                selection.ActorIndexFlat,
                selection.ActionType,
                selection.Direction,
                selection.ProduceUnitType,
                selection.AttackTargetLocal);

            bool accepted = _actionApplier.ApplyAction(decodedAction, playerPerspective, maskAtSelection, sourceActionFormat);
            return new PolicyExecutionReport(
                new[] { decodedAction },
                accepted ? 1 : 0,
                _actionApplier.RejectedActionsLastStep,
                _actionApplier.RejectionReasonsLastStep,
                _actionApplier.LastInvalidAttempt);
        }
    }
}