using System;
using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.ML
{
    [Serializable]
    public sealed class Week6CountEntry
    {
        public string key;
        public int value;
    }

    [Serializable]
    public sealed class Week6SideDiagnosticsReport
    {
        public string side;
        public Week6CountEntry[] action_attempts_by_type;
        public Week6CountEntry[] accepted_actions_by_type;
        public Week6CountEntry[] rejected_invalid_actions_by_type;
        public Week6CountEntry[] runtime_rejected_actions_by_type;
        public Week6CountEntry[] rejection_reason_histogram;
        public int move_attempts;
        public int accepted_moves;
        public float move_success_rate;
        public int produce_attempts;
        public int accepted_produces;
        public Week6CountEntry[] produced_unit_type_histogram;
        public int attack_attempts;
        public int accepted_attacks;
        public int accepted_total;
        public int rejected_total;
        public float invalid_share;
        public float ignored_share;
        public Week6CountEntry[] raw_chosen_action_type_histogram;
    }

    [Serializable]
    public sealed class Week6EpisodeDiagnosticsReport
    {
        public string report_version;
        public string generated_at_utc;
        public int episode_index;
        public int steps_run;
        public string terminal_reason;
        public Week6SideDiagnosticsReport student_side;
        public Week6SideDiagnosticsReport baseline_side;
        public int accepted_total;
        public int rejected_total;
        public float invalid_share;
        public float ignored_share;
        public string[] interpretation_hints;
    }

    internal sealed class Week6EpisodeDiagnosticsCollector
    {
        private sealed class SideAccumulator
        {
            public SideAccumulator(Owner owner)
            {
                Owner = owner;
            }

            public Owner Owner { get; }
            public readonly Dictionary<UnitActionType, int> RawChosenByType = new Dictionary<UnitActionType, int>();
            public readonly Dictionary<UnitActionType, int> RuntimeAcceptedByType = new Dictionary<UnitActionType, int>();
            public readonly Dictionary<UnitActionType, int> RuntimeRejectedByType = new Dictionary<UnitActionType, int>();
            public readonly Dictionary<string, int> RejectionReasons = new Dictionary<string, int>(StringComparer.Ordinal);
            public readonly Dictionary<string, int> RuntimeAcceptedProduceType = new Dictionary<string, int>(StringComparer.Ordinal);
        }

        private readonly SideAccumulator _student;
        private readonly SideAccumulator _baseline;

        private int _stepsRun;
        private string _terminalReason = "unknown";

        public Week6EpisodeDiagnosticsCollector(Owner studentOwner, Owner baselineOwner)
        {
            _student = new SideAccumulator(studentOwner);
            _baseline = new SideAccumulator(baselineOwner);
        }

        public void RecordStepCompleted()
        {
            _stepsRun++;
        }

        public void SetTerminalReason(string terminalReason)
        {
            _terminalReason = string.IsNullOrWhiteSpace(terminalReason) ? "unknown" : terminalReason;
        }

        public void RecordStudentDecodedActions(IReadOnlyList<AgentAction> actions)
        {
            if (actions == null)
            {
                return;
            }

            for (int i = 0; i < actions.Count; i++)
            {
                Increment(_student.RawChosenByType, actions[i].ActionType);
            }
        }

        public void RecordStudentRejectionReasons(IReadOnlyList<string> rejectionReasons)
        {
            if (rejectionReasons == null)
            {
                return;
            }

            for (int i = 0; i < rejectionReasons.Count; i++)
            {
                Increment(_student.RejectionReasons, NormalizeReason(rejectionReasons[i]));
            }
        }

        public void RecordHeuristicActionEvaluation(HeuristicActionEvaluation evaluation)
        {
            SideAccumulator side = GetSide(evaluation.PlayerId);
            Increment(side.RawChosenByType, evaluation.ActionType);

            if (!evaluation.Accepted)
            {
                Increment(side.RejectionReasons, NormalizeReason(evaluation.RejectionReason));
            }
        }

        public void RecordRuntimeAccepted(MatchCommand command)
        {
            SideAccumulator side = GetSide(command.Owner);
            Increment(side.RuntimeAcceptedByType, command.ActionType);

            if (command.ActionType == UnitActionType.Produce)
            {
                Increment(side.RuntimeAcceptedProduceType, command.ProduceUnitType.ToString());
            }
        }

        public void RecordRuntimeRejected(MatchCommand command, string reason)
        {
            SideAccumulator side = GetSide(command.Owner);
            Increment(side.RuntimeRejectedByType, command.ActionType);
            Increment(side.RejectionReasons, NormalizeReason(reason));
        }

        public Week6EpisodeDiagnosticsReport BuildEpisodeReport(int episodeIndex)
        {
            Week6SideDiagnosticsReport student = BuildSideReport(_student);
            Week6SideDiagnosticsReport baseline = BuildSideReport(_baseline);

            int acceptedTotal = student.accepted_total + baseline.accepted_total;
            int rejectedTotal = student.rejected_total + baseline.rejected_total;
            int totalAttempts = acceptedTotal + rejectedTotal;
            int runtimeRejectedTotal = Sum(student.runtime_rejected_actions_by_type) + Sum(baseline.runtime_rejected_actions_by_type);

            return new Week6EpisodeDiagnosticsReport
            {
                report_version = "week6_episode_diagnostics_v1",
                generated_at_utc = DateTime.UtcNow.ToString("O"),
                episode_index = episodeIndex,
                steps_run = _stepsRun,
                terminal_reason = _terminalReason,
                student_side = student,
                baseline_side = baseline,
                accepted_total = acceptedTotal,
                rejected_total = rejectedTotal,
                invalid_share = totalAttempts > 0 ? (float)rejectedTotal / totalAttempts : 0f,
                ignored_share = totalAttempts > 0 ? (float)runtimeRejectedTotal / totalAttempts : 0f,
                interpretation_hints = BuildInterpretationHints(student, baseline),
            };
        }

        private Week6SideDiagnosticsReport BuildSideReport(SideAccumulator side)
        {
            var attempts = BuildAttemptsByType(side);
            var acceptedFinal = BuildAcceptedFinalByType(side);
            var rejectedByType = BuildRejectedByType(attempts, acceptedFinal);

            int attemptsTotal = Sum(attempts);
            int acceptedTotal = Sum(acceptedFinal);
            int rejectedTotal = Sum(rejectedByType);
            int runtimeRejectedTotal = Sum(side.RuntimeRejectedByType);

            int moveAttempts = GetCount(attempts, UnitActionType.Move);
            int acceptedMoves = GetCount(acceptedFinal, UnitActionType.Move);
            int produceAttempts = GetCount(attempts, UnitActionType.Produce);
            int acceptedProduces = GetCount(acceptedFinal, UnitActionType.Produce);
            int attackAttempts = GetCount(attempts, UnitActionType.Attack);
            int acceptedAttacks = GetCount(acceptedFinal, UnitActionType.Attack);

            return new Week6SideDiagnosticsReport
            {
                side = side.Owner.ToString(),
                action_attempts_by_type = ToActionEntries(attempts),
                accepted_actions_by_type = ToActionEntries(acceptedFinal),
                rejected_invalid_actions_by_type = ToActionEntries(rejectedByType),
                runtime_rejected_actions_by_type = ToActionEntries(side.RuntimeRejectedByType),
                rejection_reason_histogram = ToStringEntries(side.RejectionReasons),
                move_attempts = moveAttempts,
                accepted_moves = acceptedMoves,
                move_success_rate = moveAttempts > 0 ? (float)acceptedMoves / moveAttempts : 0f,
                produce_attempts = produceAttempts,
                accepted_produces = acceptedProduces,
                produced_unit_type_histogram = ToStringEntries(side.RuntimeAcceptedProduceType),
                attack_attempts = attackAttempts,
                accepted_attacks = acceptedAttacks,
                accepted_total = acceptedTotal,
                rejected_total = rejectedTotal,
                invalid_share = attemptsTotal > 0 ? (float)rejectedTotal / attemptsTotal : 0f,
                ignored_share = attemptsTotal > 0 ? (float)runtimeRejectedTotal / attemptsTotal : 0f,
                raw_chosen_action_type_histogram = ToActionEntries(side.RawChosenByType),
            };
        }

        private static Dictionary<UnitActionType, int> BuildAttemptsByType(SideAccumulator side)
        {
            var attempts = CreateActionTypeMap();
            bool hasRaw = side.RawChosenByType.Count > 0;
            IReadOnlyDictionary<UnitActionType, int> source = hasRaw
                ? side.RawChosenByType
                : MergeRuntimeAttemptFallback(side);

            foreach (KeyValuePair<UnitActionType, int> kvp in source)
            {
                attempts[kvp.Key] = Mathf.Max(0, kvp.Value);
            }

            return attempts;
        }

        private static IReadOnlyDictionary<UnitActionType, int> MergeRuntimeAttemptFallback(SideAccumulator side)
        {
            var merged = CreateActionTypeMap();
            foreach (KeyValuePair<UnitActionType, int> kvp in side.RuntimeAcceptedByType)
            {
                merged[kvp.Key] += kvp.Value;
            }

            foreach (KeyValuePair<UnitActionType, int> kvp in side.RuntimeRejectedByType)
            {
                merged[kvp.Key] += kvp.Value;
            }

            return merged;
        }

        private static Dictionary<UnitActionType, int> BuildAcceptedFinalByType(SideAccumulator side)
        {
            var accepted = CreateActionTypeMap();
            foreach (KeyValuePair<UnitActionType, int> kvp in side.RuntimeAcceptedByType)
            {
                int runtimeRejected = GetCount(side.RuntimeRejectedByType, kvp.Key);
                accepted[kvp.Key] = Mathf.Max(0, kvp.Value - runtimeRejected);
            }

            return accepted;
        }

        private static Dictionary<UnitActionType, int> BuildRejectedByType(
            IReadOnlyDictionary<UnitActionType, int> attempts,
            IReadOnlyDictionary<UnitActionType, int> acceptedFinal)
        {
            var rejected = CreateActionTypeMap();
            foreach (KeyValuePair<UnitActionType, int> kvp in attempts)
            {
                int accepted = GetCount(acceptedFinal, kvp.Key);
                rejected[kvp.Key] = Mathf.Max(0, kvp.Value - accepted);
            }

            return rejected;
        }

        private static Dictionary<UnitActionType, int> CreateActionTypeMap()
        {
            return new Dictionary<UnitActionType, int>
            {
                [UnitActionType.NoOp] = 0,
                [UnitActionType.Move] = 0,
                [UnitActionType.Harvest] = 0,
                [UnitActionType.Return] = 0,
                [UnitActionType.Produce] = 0,
                [UnitActionType.Attack] = 0,
            };
        }

        private SideAccumulator GetSide(Owner owner)
        {
            return owner == _student.Owner ? _student : _baseline;
        }

        private static void Increment<TKey>(IDictionary<TKey, int> counts, TKey key)
        {
            if (!counts.TryGetValue(key, out int value))
            {
                value = 0;
            }

            counts[key] = value + 1;
        }

        private static int GetCount<TKey>(IReadOnlyDictionary<TKey, int> counts, TKey key)
        {
            return counts != null && counts.TryGetValue(key, out int value) ? value : 0;
        }

        private static int Sum(IReadOnlyDictionary<UnitActionType, int> counts)
        {
            int total = 0;
            foreach (KeyValuePair<UnitActionType, int> kvp in counts)
            {
                total += kvp.Value;
            }

            return total;
        }

        private static int Sum(Week6CountEntry[] entries)
        {
            int total = 0;
            for (int i = 0; i < entries.Length; i++)
            {
                total += entries[i].value;
            }

            return total;
        }

        private static Week6CountEntry[] ToActionEntries(IReadOnlyDictionary<UnitActionType, int> counts)
        {
            var entries = new List<Week6CountEntry>(counts.Count);
            foreach (KeyValuePair<UnitActionType, int> kvp in counts)
            {
                entries.Add(new Week6CountEntry
                {
                    key = kvp.Key.ToString(),
                    value = kvp.Value,
                });
            }

            entries.Sort((left, right) => right.value.CompareTo(left.value));
            return entries.ToArray();
        }

        private static Week6CountEntry[] ToStringEntries(IReadOnlyDictionary<string, int> counts)
        {
            var entries = new List<Week6CountEntry>(counts.Count);
            foreach (KeyValuePair<string, int> kvp in counts)
            {
                entries.Add(new Week6CountEntry
                {
                    key = kvp.Key,
                    value = kvp.Value,
                });
            }

            entries.Sort((left, right) => right.value.CompareTo(left.value));
            return entries.ToArray();
        }

        private static string NormalizeReason(string reason)
        {
            if (string.IsNullOrWhiteSpace(reason))
            {
                return "other";
            }

            string lower = reason.ToLowerInvariant();

            if (lower.Contains("belongs to") || lower.Contains("another owner")) return "wrong_owner";
            if (lower.Contains("neutral")) return "neutral_actor";
            if (lower.Contains("occupied")) return "occupied_target";
            if (lower.Contains("queue") || lower.Contains("already has a command")) return "queue_busy";
            if (lower.Contains("cannot produce") || lower.Contains("does not support action")) return "unsupported_action_for_unit_type";
            if (lower.Contains("not enough resources") || lower.Contains("insufficient resources")) return "no_resource";
            if (lower.Contains("not carrying") || lower.Contains("carrying 0")) return "no_carry";
            if (lower.Contains("no enemy") || lower.Contains("cannot attack self") || lower.Contains("no attack")) return "no_attack_target";
            if (lower.Contains("match is not") || lower.Contains("runtime") || lower.Contains("out of bounds")) return "runtime_only_constraint";
            if (lower.Contains("mask")) return "mask_mismatch";
            return "other";
        }

        private static string[] BuildInterpretationHints(Week6SideDiagnosticsReport student, Week6SideDiagnosticsReport baseline)
        {
            var hints = new List<string>(4);

            int studentMoveAttempts = student.move_attempts;
            int studentProduceAttempts = student.produce_attempts;
            if (studentProduceAttempts > studentMoveAttempts * 2 && studentMoveAttempts < 5)
            {
                hints.Add("student_policy_bias_possible: produce dominates while move is rarely selected");
            }

            if (studentMoveAttempts >= 5 && student.move_success_rate < 0.25f)
            {
                hints.Add("control_or_decoder_or_setup_possible: student move selected often but accepted rarely");
            }

            if (baseline.move_attempts >= 5 && baseline.move_success_rate < 0.35f)
            {
                hints.Add("baseline_pathing_or_runtime_possible: baseline move attempts are frequent but mostly unsuccessful");
            }

            if (hints.Count == 0)
            {
                hints.Add("no_strong_signal: inspect rejection histograms and side-level action mixes");
            }

            return hints.ToArray();
        }
    }
}
