// BaselineRolloutRunner.cs — Day 6 batch rollout orchestrator for baseline/heuristic mode.
//
// Orchestrates sequential episodic rollouts through the canonical RL loop without
// ML-Agent integration. Collects episode-level diagnostics and computes batch summaries.
// Used for reward distribution sanity-checking and baseline trace analysis.

using System;
using System.Collections.Generic;
using UnityEngine;
using RTS.Core;
using RTS.Gameplay;

namespace RTS.ML
{
    /// <summary>
    /// Runs a batch of baseline/heuristic episodes sequentially and collects diagnostics.
    ///
    /// Usage:
    ///   var runner = new BaselineRolloutRunner(episodeController);
    ///   RolloutBatchSummary summary = runner.StartBatchRollout(
    ///       episodeCount: 10,
    ///       verboseLogging: true
    ///   );
    ///
    /// Non-Goals:
    /// - Not a ML-Agent training runner (no tensor ops, no policy updates).
    /// - Not a performance benchmark (no timing analysis).
    /// - Only collects diagnostics available via EpisodeController public API.
    /// </summary>
    public class BaselineRolloutRunner
    {
        private readonly EpisodeController _episodeController;
        private readonly RewardSanityCheckConfig _sanityConfig;

        public BaselineRolloutRunner(EpisodeController episodeController, RewardSanityCheckConfig sanityConfig = null)
        {
            _episodeController = episodeController ?? throw new ArgumentNullException(nameof(episodeController));
            _sanityConfig = sanityConfig ?? new RewardSanityCheckConfig();
        }

        /// <summary>
        /// Run a batch of baseline rollout episodes and return aggregated summary.
        ///
        /// Each iteration:
        /// 1. StartNewEpisode() on the controller
        /// 2. Loop StepMatchWithHeuristics() until episode is not running
        /// 3. Capture RolloutEpisodeSummary from episode state
        /// 4. Aggregate into batch summary
        ///
        /// After batch completes, runs sanity checks and populates warnings.
        /// </summary>
        public RolloutBatchSummary StartBatchRollout(int episodeCount, bool verboseLogging = false)
        {
            if (episodeCount <= 0) throw new ArgumentException("episodeCount must be > 0", nameof(episodeCount));

            var summary = new RolloutBatchSummary
            {
                EpisodeCount = episodeCount,
                Episodes = new List<RolloutEpisodeSummary>(episodeCount)
            };

            if (verboseLogging)
            {
                Debug.Log($"[BaselineRolloutRunner] Starting batch: {episodeCount} episodes");
            }

            bool previousAutoStep = _episodeController.AutoStepInFixedUpdate;
            _episodeController.AutoStepInFixedUpdate = false;

            try
            {
                // ─── Run N episodes sequentially ───────────────────────────────
                for (int i = 0; i < episodeCount; i++)
                {
                    RolloutEpisodeSummary episodeSummary = RunSingleEpisode();
                    summary.Episodes.Add(episodeSummary);

                    if (verboseLogging)
                    {
                        Debug.Log($"[BaselineRolloutRunner] {episodeSummary.GetCompactLine()}");
                    }
                }

                // ─── Compute batch aggregates ──────────────────────────────────
                ComputeBatchAggregates(summary);

                // ─── Run sanity checks ────────────────────────────────────────
                RewardSanityChecker.CheckBatchSanity(summary, _sanityConfig);

                if (verboseLogging)
                {
                    Debug.Log($"[BaselineRolloutRunner] {summary.ToOneLine()}");
                    if (summary.SanityWarnings.Count > 0)
                    {
                        Debug.LogWarning($"[BaselineRolloutRunner] {summary.SanityWarnings.Count} sanity warnings:");
                        foreach (var warning in summary.SanityWarnings)
                        {
                            Debug.LogWarning($"  {warning}");
                        }
                    }
                    else
                    {
                        Debug.Log("[BaselineRolloutRunner] ✅ No sanity warnings detected");
                    }
                }

                return summary;
            }
            finally
            {
                _episodeController.AutoStepInFixedUpdate = previousAutoStep;
            }
        }

        /// <summary>
        /// Run a single episode from start to terminal, collecting diagnostics.
        /// </summary>
        private RolloutEpisodeSummary RunSingleEpisode()
        {
            // Start a fresh episode
            _episodeController.StartNewEpisode();

            int stepCount = 0;
            int validActionCount = 0;
            int invalidActionCount = 0;
            int invalidMeasuredStepCount = 0;
            int invalidUnavailableStepCount = 0;

            // Run steps until terminal or timeout
            while (_episodeController.IsRunning)
            {
                // Execute one RL loop cycle via public API
                bool continueRunning = _episodeController.StepEpisodeOnce();
                RlLoopStepReport stepReport = _episodeController.LastRlLoopStepReport;

                stepCount++;
                if (stepReport.ActionCountsAvailable)
                {
                    invalidMeasuredStepCount++;
                    validActionCount += stepReport.ActionsAccepted;
                    invalidActionCount += stepReport.ActionsRejected;
                }
                else
                {
                    invalidUnavailableStepCount++;
                }

                if (!continueRunning || stepCount > 100000)  // Safety limit
                {
                    break;
                }
            }

            // Capture post-episode state
            // Use CurrentRewardEpisodeSummary for cumulative episode totals.
            // LastRewardBreakdown is per-step only (the final step's values) — do NOT use for episode aggregates.
            EpisodeEndReport terminalReport = _episodeController.LastTerminalReport;
            RewardEpisodeSummary rewardSummary = _episodeController.CurrentRewardEpisodeSummary;

            // Terminal diagnostics are sourced primarily from EpisodeEndReport.
            // In diagnostic batches we also align them with the authoritative cumulative reward bucket,
            // because terminal callbacks may be observed before post-step reward accumulation completes.
            bool terminalEventProcessed = terminalReport.TerminalEventProcessed
                || (rewardSummary.TerminalReached && rewardSummary.TerminalReason != TerminalReason.None);
            bool terminalRewardNonZero = terminalReport.TerminalRewardNonZero
                || !Mathf.Approximately(rewardSummary.Breakdown.Terminal, 0f);

            // Construct episode summary
            var episodeSummary = new RolloutEpisodeSummary
            {
                EpisodeIndex = _episodeController.EpisodeIndex,
                StepCount = stepCount,

                    TotalReward = rewardSummary.Breakdown.Total,
                    EconomyReward = rewardSummary.Breakdown.Economy,
                    CombatReward = rewardSummary.Breakdown.Combat,
                    TerminalReward = rewardSummary.Breakdown.Terminal,
                    ShapingReward = rewardSummary.Breakdown.Shaping,

                RewardEventCount = rewardSummary.TotalEventCount,

                IsTerminal = terminalReport.IsTerminal,
                TerminalReason = terminalReport.TerminalReason,
                Winner = terminalReport.Winner,
                TerminalEventProcessed = terminalEventProcessed,
                TerminalRewardNonZero = terminalRewardNonZero,
                RuntimeEndReason = terminalReport.RuntimeEndReason,

                InvalidActionCount = invalidActionCount,
                InvalidActionRateMeasured = invalidMeasuredStepCount > 0,
                InvalidActionMeasuredStepCount = invalidMeasuredStepCount,
                InvalidActionUnavailableStepCount = invalidUnavailableStepCount,
                // Invalid rate is rejection ratio over measured action attempts, not per-step density.
                InvalidActionRate = (validActionCount + invalidActionCount) > 0
                    ? (float)invalidActionCount / (validActionCount + invalidActionCount)
                    : 0f,

                OutcomeLabel = DeriveOutcomeLabel(terminalReport, stepCount)
            };

            return episodeSummary;
        }

        /// <summary>
        /// Derive a human-readable outcome label from terminal report and runtime state.
        /// Examples: "Win", "Loss", "Draw", "Timeout", "InvalidRuntimeState"
        /// </summary>
        private string DeriveOutcomeLabel(EpisodeEndReport report, int stepCount)
        {
            if (!report.IsTerminal)
                return "Running";

            return report.TerminalReason switch
            {
                TerminalReason.None => "Unknown",
                TerminalReason.Win => "Win",
                TerminalReason.Loss => "Loss",
                TerminalReason.Draw => "Draw",
                TerminalReason.Timeout => "Timeout",
                TerminalReason.InvalidRuntimeState => "InvalidRuntimeState",
                _ => report.TerminalReason.ToString()
            };
        }

        /// <summary>
        /// Compute batch aggregates: means, stds, distributions.
        /// </summary>
        private void ComputeBatchAggregates(RolloutBatchSummary summary)
        {
            if (summary.Episodes.Count == 0)
                return;

            int n = summary.Episodes.Count;

            // ─── Reward aggregates ──────────────────────────────────────────
            float rewardSum = 0f;
            float rewardSqSum = 0f;
            float economySum = 0f;
            float combatSum = 0f;
            float terminalSum = 0f;
            float shapingSum = 0f;
            float eventCountSum = 0f;
            float stepCountSum = 0f;

            summary.MinTotalReward = float.MaxValue;
            summary.MaxTotalReward = float.MinValue;

            summary.MinStepCount = int.MaxValue;
            summary.MaxStepCount = int.MinValue;

            float invalidRateMeasuredSum = 0f;
            float maxInvalidRateMeasured = 0f;

            int terminalEventProcessedCount = 0;
            int terminalRewardNonZeroCount = 0;
            int highInvalidRateEpisodeCount = 0;
            int measuredInvalidEpisodes = 0;
            int unavailableInvalidEpisodes = 0;
            int totalInvalidMeasuredSteps = 0;
            int totalInvalidUnavailableSteps = 0;

            foreach (var ep in summary.Episodes)
            {
                // Reward aggregation
                rewardSum += ep.TotalReward;
                rewardSqSum += ep.TotalReward * ep.TotalReward;
                summary.MinTotalReward = Mathf.Min(summary.MinTotalReward, ep.TotalReward);
                summary.MaxTotalReward = Mathf.Max(summary.MaxTotalReward, ep.TotalReward);

                economySum += ep.EconomyReward;
                combatSum += ep.CombatReward;
                terminalSum += ep.TerminalReward;
                shapingSum += ep.ShapingReward;
                eventCountSum += ep.RewardEventCount;

                // Step aggregation
                summary.MinStepCount = Mathf.Min(summary.MinStepCount, ep.StepCount);
                summary.MaxStepCount = Mathf.Max(summary.MaxStepCount, ep.StepCount);
                stepCountSum += ep.StepCount;

                // Invalid action aggregation
                totalInvalidMeasuredSteps += ep.InvalidActionMeasuredStepCount;
                totalInvalidUnavailableSteps += ep.InvalidActionUnavailableStepCount;
                if (ep.InvalidActionRateMeasured)
                {
                    measuredInvalidEpisodes++;
                    invalidRateMeasuredSum += ep.InvalidActionRate;
                    maxInvalidRateMeasured = Mathf.Max(maxInvalidRateMeasured, ep.InvalidActionRate);
                    if (ep.InvalidActionRate > _sanityConfig.HighInvalidRateThreshold)
                    {
                        highInvalidRateEpisodeCount++;
                    }
                }
                else
                {
                    unavailableInvalidEpisodes++;
                }

                // Terminal event aggregation
                if (ep.TerminalEventProcessed)
                {
                    terminalEventProcessedCount++;
                    // Keep non-zero terminal accounting aligned with the actual episode terminal bucket.
                    if (!Mathf.Approximately(ep.TerminalReward, 0f))
                    {
                        terminalRewardNonZeroCount++;
                    }
                }

                // Terminal reason distribution
                if (!summary.TerminalReasonCounts.ContainsKey(ep.TerminalReason))
                {
                    summary.TerminalReasonCounts[ep.TerminalReason] = 0;
                }
                summary.TerminalReasonCounts[ep.TerminalReason]++;

                // Outcome distribution
                if (!summary.OutcomeCounts.ContainsKey(ep.OutcomeLabel))
                {
                    summary.OutcomeCounts[ep.OutcomeLabel] = 0;
                }
                summary.OutcomeCounts[ep.OutcomeLabel]++;
            }

            // Compute means
            summary.AvgTotalReward = rewardSum / n;
            summary.AvgEconomyReward = economySum / n;
            summary.AvgCombatReward = combatSum / n;
            summary.AvgTerminalReward = terminalSum / n;
            summary.AvgShapingReward = shapingSum / n;
            summary.AvgStepCount = stepCountSum / n;
            summary.AvgRewardEventCount = eventCountSum / n;

            // Compute std
            float variance = (rewardSqSum / n) - (summary.AvgTotalReward * summary.AvgTotalReward);
            summary.StdTotalReward = Mathf.Sqrt(Mathf.Max(0f, variance));

            // Compute averages
            summary.EpisodesWithMeasuredInvalidRate = measuredInvalidEpisodes;
            summary.EpisodesWithUnavailableInvalidRate = unavailableInvalidEpisodes;
            summary.TotalInvalidMeasuredSteps = totalInvalidMeasuredSteps;
            summary.TotalInvalidUnavailableSteps = totalInvalidUnavailableSteps;
            summary.AvgInvalidActionRateMeasured = measuredInvalidEpisodes > 0
                ? invalidRateMeasuredSum / measuredInvalidEpisodes
                : 0f;
            summary.MaxInvalidActionRateMeasured = measuredInvalidEpisodes > 0
                ? maxInvalidRateMeasured
                : 0f;
            summary.EpisodesWithHighInvalidRateMeasured = highInvalidRateEpisodeCount;

            // Terminal event statistics
            summary.TerminalEventProcessedCount = terminalEventProcessedCount;
            summary.TerminalEventProcessedRate = n > 0 ? (float)terminalEventProcessedCount / n : 0f;
            summary.TerminalRewardNonZeroCount = terminalRewardNonZeroCount;
            summary.TerminalRewardNonZeroRate = terminalEventProcessedCount > 0
                ? (float)terminalRewardNonZeroCount / terminalEventProcessedCount
                : 0f;

            // Shaping fraction of total reward sum across the batch.
            summary.AvgShapingFractionOfTotal = Mathf.Abs(rewardSum) > 0.001f
                ? shapingSum / rewardSum
                : 0f;
        }
    }
}
