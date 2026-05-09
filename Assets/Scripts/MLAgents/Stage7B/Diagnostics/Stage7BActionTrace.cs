using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using RTS.Core;
using RTS.MLAgents.Stage7B.CandidateActions;
using UnityEngine;

namespace RTS.MLAgents.Stage7B.Diagnostics
{
    [Serializable]
    public sealed class Stage7BActionTrace
    {
        private readonly Dictionary<string, int> _rejectReasonHistogram = new Dictionary<string, int>();

        private int _candidateCountSampleCount;
        private long _candidateCountSum;

        public string UnityVersion { get; set; } = Application.unityVersion;
        public string MlAgentsPackageVersion { get; set; } = "unknown";
        public string PythonVersion { get; set; } = "unavailable";
        public string MlAgentsPythonVersion { get; set; } = "unavailable";
        public string MlAgentsEnvsPythonVersion { get; set; } = "unavailable";
        public string DecisionSource { get; private set; } = "decision_requester";
        public string BehaviorName { get; private set; } = "unknown";
        public int DiscreteBranchCount { get; private set; } = 1;
        public int CandidateBranchSize { get; private set; } = MlAgentsCandidateActionList.BranchSize;
        public int AttackTargetSize { get; private set; } = MlAgentsCandidateActionList.AttackTargetSize;
        public int AttackTargetCenterIndex { get; private set; } = MlAgentsCandidateActionList.AttackTargetCenterIndex;

        public int ObservationLength { get; private set; }
        public int ObservationNanCount { get; private set; }
        public float ObservationMin { get; private set; }
        public float ObservationMax { get; private set; }
        public int CollectObservationsCalls { get; private set; }
        public int WriteMaskCalls { get; private set; }
        public int OnActionReceivedCalls { get; private set; }
        public int CandidateCountMin { get; private set; } = int.MaxValue;
        public float CandidateCountMean => _candidateCountSampleCount > 0
            ? _candidateCountSum / (float)_candidateCountSampleCount
            : 0f;
        public int CandidateCountMax { get; private set; }
        public int MaskedEmptySlotsCount { get; private set; }
        public int CandidateOverflowCount { get; private set; }
        public int InvalidCandidateIndexSelectedCount { get; private set; }
        public int EmptyCandidateSelectedCount { get; private set; }
        public int OutOfRangeCandidateSelectedCount { get; private set; }
        public int FallbackToNoOpCount { get; private set; }
        public int SelectedNoOpCount { get; private set; }
        public int SelectedNonNoOpCount { get; private set; }
        public int AcceptedCommands { get; private set; }
        public int RejectedCommands { get; private set; }
        public float RewardSum { get; private set; }
        public string TerminalReason { get; private set; } = "none";
        public int ResetCount { get; private set; }
        public bool DuplicateSpawnDetected { get; private set; }
        public bool Stage6B3FilesTouched { get; private set; }

        public void RecordDecisionSource(string decisionSource)
        {
            DecisionSource = string.IsNullOrWhiteSpace(decisionSource) ? "unknown" : decisionSource;
        }

        public void RecordBehaviorSpec(string behaviorName, int discreteBranchCount, int candidateBranchSize)
        {
            BehaviorName = string.IsNullOrWhiteSpace(behaviorName) ? "unknown" : behaviorName;
            DiscreteBranchCount = Mathf.Max(0, discreteBranchCount);
            CandidateBranchSize = Mathf.Max(0, candidateBranchSize);
        }

        public void RecordActionContract(int attackTargetSize, int attackTargetCenterIndex)
        {
            AttackTargetSize = Mathf.Max(0, attackTargetSize);
            AttackTargetCenterIndex = Mathf.Max(0, attackTargetCenterIndex);
        }

        public void RecordObservation(float[] observation)
        {
            CollectObservationsCalls++;
            ObservationLength = observation != null ? observation.Length : 0;

            int nanCount = 0;
            float min = float.PositiveInfinity;
            float max = float.NegativeInfinity;

            if (observation != null)
            {
                for (int i = 0; i < observation.Length; i++)
                {
                    float value = observation[i];
                    if (float.IsNaN(value) || float.IsInfinity(value))
                    {
                        nanCount++;
                        continue;
                    }

                    if (value < min) min = value;
                    if (value > max) max = value;
                }
            }

            ObservationNanCount = nanCount;
            ObservationMin = float.IsInfinity(min) ? 0f : min;
            ObservationMax = float.IsInfinity(max) ? 0f : max;
        }

        public void RecordMask(int candidateCount, int maskedEmptySlots, int overflowCount)
        {
            WriteMaskCalls++;
            RecordCandidateCount(candidateCount);
            MaskedEmptySlotsCount += Mathf.Max(0, maskedEmptySlots);
            CandidateOverflowCount += Mathf.Max(0, overflowCount);
        }

        public void RecordActionSelected(bool isNoOp)
        {
            OnActionReceivedCalls++;
            if (isNoOp)
            {
                SelectedNoOpCount++;
            }
            else
            {
                SelectedNonNoOpCount++;
            }
        }

        public void RecordCandidateCount(int candidateCount)
        {
            if (candidateCount < CandidateCountMin) CandidateCountMin = candidateCount;
            if (candidateCount > CandidateCountMax) CandidateCountMax = candidateCount;
            _candidateCountSampleCount++;
            _candidateCountSum += candidateCount;
        }

        public void RecordApplyResult(int accepted, int rejected, IReadOnlyList<string> rejectionReasons)
        {
            AcceptedCommands += Mathf.Max(0, accepted);
            RejectedCommands += Mathf.Max(0, rejected);

            if (rejectionReasons == null)
            {
                return;
            }

            for (int i = 0; i < rejectionReasons.Count; i++)
            {
                string reason = string.IsNullOrWhiteSpace(rejectionReasons[i])
                    ? "unknown"
                    : rejectionReasons[i];
                if (_rejectReasonHistogram.TryGetValue(reason, out int count))
                {
                    _rejectReasonHistogram[reason] = count + 1;
                }
                else
                {
                    _rejectReasonHistogram.Add(reason, 1);
                }
            }
        }

        public void RecordCandidateFallback(bool invalidCandidateIndex, bool emptyCandidate, bool outOfRangeCandidate, bool fallbackToNoOp)
        {
            if (invalidCandidateIndex)
            {
                InvalidCandidateIndexSelectedCount++;
            }

            if (emptyCandidate)
            {
                EmptyCandidateSelectedCount++;
            }

            if (outOfRangeCandidate)
            {
                OutOfRangeCandidateSelectedCount++;
            }

            if (fallbackToNoOp)
            {
                FallbackToNoOpCount++;
            }
        }

        public void RecordReward(float reward)
        {
            if (!float.IsNaN(reward) && !float.IsInfinity(reward))
            {
                RewardSum += reward;
            }
        }

        public void RecordTerminal(string reason)
        {
            TerminalReason = string.IsNullOrWhiteSpace(reason) ? "unknown" : reason;
        }

        public void RecordReset(bool duplicateSpawnDetected)
        {
            ResetCount++;
            DuplicateSpawnDetected |= duplicateSpawnDetected;
        }

        public string ToJson()
        {
            int min = CandidateCountMin == int.MaxValue ? 0 : CandidateCountMin;
            var sb = new StringBuilder(2048);
            sb.AppendLine("{");
            AppendJson(sb, "unity_version", UnityVersion, true);
            AppendJson(sb, "com.unity.ml-agents version", MlAgentsPackageVersion, true);
            AppendJson(sb, "python version if available", PythonVersion, true);
            AppendJson(sb, "mlagents version if available", MlAgentsPythonVersion, true);
            AppendJson(sb, "mlagents-envs version if available", MlAgentsEnvsPythonVersion, true);
            AppendJson(sb, "decision_source", DecisionSource, true);
            AppendJson(sb, "behavior_name", BehaviorName, true);
            AppendJson(sb, "discrete_branch_count", DiscreteBranchCount, true);
            AppendJson(sb, "candidate_branch_size", CandidateBranchSize, true);
            AppendJson(sb, "attack_target_size", AttackTargetSize, true);
            AppendJson(sb, "attack_target_center_index", AttackTargetCenterIndex, true);
            AppendJson(sb, "observation_length", ObservationLength, true);
            AppendJson(sb, "observation_nan_count", ObservationNanCount, true);
            AppendJson(sb, "observation_min", ObservationMin, true);
            AppendJson(sb, "observation_max", ObservationMax, true);
            AppendJson(sb, "collect_observations_calls", CollectObservationsCalls, true);
            AppendJson(sb, "write_mask_calls", WriteMaskCalls, true);
            AppendJson(sb, "on_action_received_calls", OnActionReceivedCalls, true);
            AppendJson(sb, "candidate_count_min", min, true);
            AppendJson(sb, "candidate_count_mean", CandidateCountMean, true);
            AppendJson(sb, "candidate_count_max", CandidateCountMax, true);
            AppendJson(sb, "masked_empty_slots_count", MaskedEmptySlotsCount, true);
            AppendJson(sb, "candidate_overflow_count", CandidateOverflowCount, true);
            AppendJson(sb, "invalid_candidate_index_selected_count", InvalidCandidateIndexSelectedCount, true);
            AppendJson(sb, "empty_candidate_selected_count", EmptyCandidateSelectedCount, true);
            AppendJson(sb, "out_of_range_candidate_selected_count", OutOfRangeCandidateSelectedCount, true);
            AppendJson(sb, "fallback_to_noop_count", FallbackToNoOpCount, true);
            AppendJson(sb, "selected_noop_count", SelectedNoOpCount, true);
            AppendJson(sb, "selected_non_noop_count", SelectedNonNoOpCount, true);
            AppendJson(sb, "accepted_commands", AcceptedCommands, true);
            AppendJson(sb, "rejected_commands", RejectedCommands, true);
            AppendHistogram(sb);
            AppendJson(sb, "reward_sum", RewardSum, true);
            AppendJson(sb, "terminal_reason", TerminalReason, true);
            AppendJson(sb, "reset_count", ResetCount, true);
            AppendJson(sb, "duplicate_spawn_detected", DuplicateSpawnDetected, true);
            AppendJson(sb, "stage6b3_files_touched", Stage6B3FilesTouched, false);
            sb.AppendLine("}");
            return sb.ToString();
        }

        private static void AppendJson(StringBuilder sb, string key, string value, bool comma)
        {
            sb.Append("  \"").Append(Escape(key)).Append("\": \"").Append(Escape(value)).Append('"');
            sb.AppendLine(comma ? "," : string.Empty);
        }

        private static void AppendJson(StringBuilder sb, string key, int value, bool comma)
        {
            sb.Append("  \"").Append(Escape(key)).Append("\": ").Append(value.ToString(CultureInfo.InvariantCulture));
            sb.AppendLine(comma ? "," : string.Empty);
        }

        private static void AppendJson(StringBuilder sb, string key, float value, bool comma)
        {
            sb.Append("  \"").Append(Escape(key)).Append("\": ").Append(value.ToString("R", CultureInfo.InvariantCulture));
            sb.AppendLine(comma ? "," : string.Empty);
        }

        private static void AppendJson(StringBuilder sb, string key, bool value, bool comma)
        {
            sb.Append("  \"").Append(Escape(key)).Append("\": ").Append(value ? "true" : "false");
            sb.AppendLine(comma ? "," : string.Empty);
        }

        private void AppendHistogram(StringBuilder sb)
        {
            sb.AppendLine("  \"reject_reason_histogram\": {");
            int index = 0;
            foreach (KeyValuePair<string, int> kv in _rejectReasonHistogram)
            {
                sb.Append("    \"").Append(Escape(kv.Key)).Append("\": ").Append(kv.Value);
                index++;
                sb.AppendLine(index < _rejectReasonHistogram.Count ? "," : string.Empty);
            }
            sb.AppendLine("  },");
        }

        private static string Escape(string value)
        {
            return (value ?? string.Empty)
                .Replace("\\", "\\\\")
                .Replace("\"", "\\\"");
        }
    }
}
