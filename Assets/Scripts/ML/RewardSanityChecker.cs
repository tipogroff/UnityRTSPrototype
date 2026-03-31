// RewardSanityChecker.cs — Day 6 sanity-check heuristics and warning validation.
//
// Provides warning thresholds and heuristic checks to detect rudimentary anomalies in
// baseline rollout batches. Not a definitive quality measure, but an engineering tool
// for identifying obvious issues before detailed investigation.

using System;
using System.Collections.Generic;
using UnityEngine;

namespace RTS.ML
{
    /// <summary>
    /// Configuration for sanity-check thresholds.
    /// Tunable for different environments and reward schemas.
    /// </summary>
    [System.Serializable]
    public class RewardSanityCheckConfig
    {
        [Header("Reward magnitude warnings")]
        public float RewardExplosionThreshold = 50.0f;        // Mean total reward > this
        public float RewardStarvationThreshold = 1.0f;        // Mean total reward < this
        public float MinNonZeroRewardFraction = 0.2f;         // Fraction of episodes with reward != 0

        [Header("Shaping dominance warnings")]
        public float ShapingDominanceThreshold = 0.5f;        // Avg shaping / mean total reward
        public float MaxShapingFraction = 0.7f;               // Fraction of total reward from shaping

        [Header("Invalid action warnings")]
        public float HighInvalidRateThreshold = 0.15f;        // Avg invalid action rate
        public float ExtremeInvalidRateThreshold = 0.3f;      // Max invalid rate in batch
        public float HighInvalidEpisodesFraction = 0.3f;      // Fraction of episodes with high invalid rate

        [Header("Terminal event warnings")]
        public float TerminalEventProcessedMinRate = 0.7f;    // At least 70% should be processed
        public float TerminalRewardNonZeroMinRate = 0.3f;     // At least 30% of terminal events should have non-zero reward

        [Header("Outcome imbalance warnings")]
        public float OutcomeImbalanceThreshold = 0.8f;        // One outcome > 80% suggests stuck state

        [Header("Episode length warnings")]
        public int SuspiciouslyLongEpisodeSteps = 1000;       // Episodes > this with reward < threshold
        public float SuspiciousLongEpisodeRewardThreshold = 5.0f;
        public float SuspiciousLongEpisodeFraction = 0.1f;    // > 10% of episodes
    }

    /// <summary>
    /// Performs sanity-check analysis on a baseline rollout batch.
    /// Detects basic anomalies that warrant manual review or investigation.
    /// </summary>
    public static class RewardSanityChecker
    {
        /// <summary>
        /// Analyze a batch summary and populate warning list.
        /// Returns the same summary with SanityWarnings filled.
        /// </summary>
        public static void CheckBatchSanity(RolloutBatchSummary summary, RewardSanityCheckConfig config = null)
        {
            if (summary == null) return;
            if (config == null) config = new RewardSanityCheckConfig();

            summary.SanityWarnings.Clear();

            // ─── Check reward magnitude ──────────────────────────────────────
            CheckRewardMagnitude(summary, config);

            // ─── Check shaping dominance ────────────────────────────────────
            CheckShapingDominance(summary, config);

            // ─── Check invalid actions ───────────────────────────────────────
            CheckInvalidActions(summary, config);

            // ─── Check terminal events ───────────────────────────────────────
            CheckTerminalEvents(summary, config);

            // ─── Check outcome distribution ──────────────────────────────────
            CheckOutcomeDistribution(summary, config);

            // ─── Check for suspiciously long low-reward episodes ──────────────
            CheckSuspiciousLongEpisodes(summary, config);
        }

        private static void CheckRewardMagnitude(RolloutBatchSummary summary, RewardSanityCheckConfig config)
        {
            // Reward explosion
            if (summary.AvgTotalReward > config.RewardExplosionThreshold)
            {
                summary.SanityWarnings.Add(
                    $"⚠️ Reward explosion risk: mean total reward = {summary.AvgTotalReward:F2} (threshold: {config.RewardExplosionThreshold})");
            }

            // Reward starvation (mean too low)
            if (summary.AvgTotalReward < config.RewardStarvationThreshold)
            {
                summary.SanityWarnings.Add(
                    $"⚠️ Reward starvation: mean total reward = {summary.AvgTotalReward:F2} (threshold: {config.RewardStarvationThreshold})");
            }

            // Reward starvation (too many zero episodes)
            int zeroRewardCount = 0;
            foreach (var ep in summary.Episodes)
            {
                if (Mathf.Abs(ep.TotalReward) < 0.001f)
                {
                    zeroRewardCount++;
                }
            }

            float zeroRewardFraction = (float)zeroRewardCount / summary.EpisodeCount;
            if (zeroRewardFraction > (1f - config.MinNonZeroRewardFraction))
            {
                summary.SanityWarnings.Add(
                    $"⚠️ High zero-reward rate: {zeroRewardFraction:P1} episodes with reward ≈ 0 " +
                    $"(threshold: {1f - config.MinNonZeroRewardFraction:P1})");
            }
        }

        private static void CheckShapingDominance(RolloutBatchSummary summary, RewardSanityCheckConfig config)
        {
            if (summary.AvgTotalReward < 0.01f) return; // Avoid division issues

            float shapingFraction = summary.AvgShapingReward / summary.AvgTotalReward;
            if (shapingFraction > config.MaxShapingFraction)
            {
                summary.SanityWarnings.Add(
                    $"⚠️ Shaping dominance: shaping reward = {shapingFraction:P1} of mean total " +
                    $"(threshold: {config.MaxShapingFraction:P1}). " +
                    $"LLM may learn spurious intermediate rewards instead of terminal outcome.");
            }

            // Also check if shaping dominates economy+combat+terminal combined
            float nonShapingMean = summary.AvgEconomyReward + summary.AvgCombatReward + summary.AvgTerminalReward;
            if (nonShapingMean > 0.01f)
            {
                if (summary.AvgShapingReward > config.ShapingDominanceThreshold * nonShapingMean)
                {
                    summary.SanityWarnings.Add(
                        $"⚠️ Shaping equals or exceeds core reward: " +
                        $"shaping={summary.AvgShapingReward:F2} vs core={nonShapingMean:F2}");
                }
            }
        }

        private static void CheckInvalidActions(RolloutBatchSummary summary, RewardSanityCheckConfig config)
        {
            if (summary.EpisodesWithMeasuredInvalidRate == 0)
            {
                summary.SanityWarnings.Add(
                    "⚠️ Invalid action rate unavailable for this batch: action counts were not provided by the active decision source.");
                return;
            }

            if (summary.EpisodesWithUnavailableInvalidRate > 0)
            {
                summary.SanityWarnings.Add(
                    $"ℹ️ Invalid action checks are partial: measured episodes = {summary.EpisodesWithMeasuredInvalidRate}/{summary.EpisodeCount}, " +
                    $"unavailable episodes = {summary.EpisodesWithUnavailableInvalidRate}.");
            }

            // High average invalid rate (measured episodes only)
            if (summary.AvgInvalidActionRateMeasured > config.HighInvalidRateThreshold)
            {
                summary.SanityWarnings.Add(
                    $"⚠️ High invalid action rate (measured only): avg = {summary.AvgInvalidActionRateMeasured:P1} " +
                    $"(threshold: {config.HighInvalidRateThreshold:P1}). " +
                    $"Action mask or decoder may be poorly configured.");
            }

            // Extreme invalid rate in any measured episode
            if (summary.MaxInvalidActionRateMeasured > config.ExtremeInvalidRateThreshold)
            {
                summary.SanityWarnings.Add(
                    $"⚠️ Extreme invalid rate detected (measured only): max = {summary.MaxInvalidActionRateMeasured:P1} " +
                    $"(threshold: {config.ExtremeInvalidRateThreshold:P1})");
            }

            // Many measured episodes with high invalid rate
            float highInvalidFraction = summary.EpisodesWithMeasuredInvalidRate > 0
                ? (float)summary.EpisodesWithHighInvalidRateMeasured / summary.EpisodesWithMeasuredInvalidRate
                : 0f;
            if (highInvalidFraction > config.HighInvalidEpisodesFraction)
            {
                summary.SanityWarnings.Add(
                    $"⚠️ Many measured episodes with high invalid rate: {highInvalidFraction:P1} of measured episodes " +
                    $"(threshold: {config.HighInvalidEpisodesFraction:P1})");
            }
        }

        private static void CheckTerminalEvents(RolloutBatchSummary summary, RewardSanityCheckConfig config)
        {
            // Terminal events not being processed frequently enough
            if (summary.TerminalEventProcessedRate < config.TerminalEventProcessedMinRate)
            {
                summary.SanityWarnings.Add(
                    $"⚠️ Low terminal event processing rate: {summary.TerminalEventProcessedRate:P1} " +
                    $"(threshold: {config.TerminalEventProcessedMinRate:P1}). " +
                    $"Terminal pipeline may be missing cases.");
            }

            // Terminal rewards rarely non-zero (only for processed events)
            if (summary.TerminalEventProcessedCount > 0 &&
                summary.TerminalRewardNonZeroRate < config.TerminalRewardNonZeroMinRate)
            {
                summary.SanityWarnings.Add(
                    $"⚠️ Terminal reward often zero: {summary.TerminalRewardNonZeroRate:P1} of processed events " +
                    $"have non-zero reward (threshold: {config.TerminalRewardNonZeroMinRate:P1}). " +
                    $"Terminal reward config may be disabled or too conservative.");
            }

            // Check for InvalidRuntimeState being frequent
            if (summary.TerminalReasonCounts.TryGetValue(TerminalReason.InvalidRuntimeState, out int invalidCount))
            {
                float invalidFraction = (float)invalidCount / summary.EpisodeCount;
                if (invalidFraction > 0.1f)
                {
                    summary.SanityWarnings.Add(
                        $"⚠️ InvalidRuntimeState frequent: {invalidFraction:P1} of episodes. " +
                        $"May indicate runtime state machine issues.");
                }
            }
        }

        private static void CheckOutcomeDistribution(RolloutBatchSummary summary, RewardSanityCheckConfig config)
        {
            // Check if any single outcome dominates
            foreach (var kvp in summary.OutcomeCounts)
            {
                float fraction = (float)kvp.Value / summary.EpisodeCount;
                if (fraction > config.OutcomeImbalanceThreshold)
                {
                    summary.SanityWarnings.Add(
                        $"⚠️ Outcome imbalance: {kvp.Key} = {fraction:P1} of episodes " +
                        $"(threshold: {config.OutcomeImbalanceThreshold:P1}). " +
                        $"Agent may be stuck in a single state or pattern.");
                }
            }
        }

        private static void CheckSuspiciousLongEpisodes(RolloutBatchSummary summary, RewardSanityCheckConfig config)
        {
            int suspiciousCount = 0;
            foreach (var ep in summary.Episodes)
            {
                if (ep.StepCount > config.SuspiciouslyLongEpisodeSteps &&
                    ep.TotalReward < config.SuspiciousLongEpisodeRewardThreshold)
                {
                    suspiciousCount++;
                }
            }

            float suspiciousFraction = (float)suspiciousCount / summary.EpisodeCount;
            if (suspiciousFraction > config.SuspiciousLongEpisodeFraction)
            {
                summary.SanityWarnings.Add(
                    $"⚠️ Suspiciously long low-reward episodes: {suspiciousFraction:P1} of episodes " +
                    $"exceeded {config.SuspiciouslyLongEpisodeSteps} steps with reward < {config.SuspiciousLongEpisodeRewardThreshold} " +
                    $"(threshold: {config.SuspiciousLongEpisodeFraction:P1}). " +
                    $"May indicate agents stuck in passive play.");
            }
        }
    }
}
