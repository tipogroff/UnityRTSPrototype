using System;
using System.Collections.Generic;

namespace RTS.MLAgents.Stage7B.TeacherReplay
{
    [Serializable]
    public sealed class Stage7BTeacherReplayMetricEntry
    {
        public string key;
        public int value;
    }

    [Serializable]
    public sealed class Stage7BTeacherReplayReport
    {
        public string generatedAtUtc;
        public string status;
        public string summary;

        public string selectedSourcePath;
        public string selectedSourceFormat;

        public int episodesScanned;
        public int episodesReplayAttempted;
        public int stepsTotal;
        public int stepsReplayAttempted;
        public int teacherCommandsTotal;
        public int teacherNonNoOpCommandsTotal;

        public int stateSyncSuccessCount;
        public int stateSyncFailedCount;
        public int preObservationMatchCount;
        public int preObservationMismatchCount;

        public int candidateMatchCount;
        public int candidateDropCount;
        public float candidateMatchRate;

        public int nonNoOpTotal;
        public int nonNoOpCandidateMatchCount;
        public float nonNoOpCandidateMatchRate;

        public int runtimeApplyAttemptedCount;
        public int runtimeApplyAcceptedCount;
        public int runtimeApplyRejectedCount;
        public float runtimeApplyAcceptRate;

        public int postStateMatchCount;
        public int postStateMismatchCount;

        public int candidateCountMin;
        public float candidateCountMean;
        public int candidateCountMax;
        public int candidateOverflowCount;

        public int terminalMatchCount;
        public int terminalMismatchCount;

        public bool demoRecordingReady;

        public List<Stage7BTeacherReplayMetricEntry> dropReasonHistogram = new List<Stage7BTeacherReplayMetricEntry>();
        public List<Stage7BTeacherReplayMetricEntry> matchByActionType = new List<Stage7BTeacherReplayMetricEntry>();
        public List<Stage7BTeacherReplayMetricEntry> dropByActionType = new List<Stage7BTeacherReplayMetricEntry>();
        public List<string> notes = new List<string>();

        public static Stage7BTeacherReplayReport CreateDefault()
        {
            return new Stage7BTeacherReplayReport
            {
                generatedAtUtc = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                status = "NO_GO",
                summary = "Stage7B-6B prep not executed yet.",
                candidateMatchRate = -1f,
                nonNoOpCandidateMatchRate = -1f,
                runtimeApplyAcceptRate = -1f,
                candidateCountMin = -1,
                candidateCountMean = -1f,
                candidateCountMax = -1,
            };
        }

        public void IncrementDrop(Stage7BTeacherReplayDropReason reason)
        {
            candidateDropCount++;
            string key = ToSnakeCase(reason);
            for (int i = 0; i < dropReasonHistogram.Count; i++)
            {
                if (dropReasonHistogram[i].key == key)
                {
                    dropReasonHistogram[i].value++;
                    return;
                }
            }

            dropReasonHistogram.Add(new Stage7BTeacherReplayMetricEntry { key = key, value = 1 });
        }

        public void RecomputeRates(bool stateSyncReliable)
        {
            if (teacherCommandsTotal > 0 && stateSyncReliable)
            {
                candidateMatchRate = (float)candidateMatchCount / teacherCommandsTotal;
            }
            else
            {
                candidateMatchRate = -1f;
            }

            if (teacherNonNoOpCommandsTotal > 0 && stateSyncReliable)
            {
                nonNoOpCandidateMatchRate = (float)nonNoOpCandidateMatchCount / teacherNonNoOpCommandsTotal;
            }
            else
            {
                nonNoOpCandidateMatchRate = -1f;
            }

            if (runtimeApplyAttemptedCount > 0)
            {
                runtimeApplyAcceptRate = (float)runtimeApplyAcceptedCount / runtimeApplyAttemptedCount;
            }
            else
            {
                runtimeApplyAcceptRate = -1f;
            }
        }

        private static string ToSnakeCase(Stage7BTeacherReplayDropReason reason)
        {
            switch (reason)
            {
                case Stage7BTeacherReplayDropReason.SourceNotReplayReady: return "source_not_replay_ready";
                case Stage7BTeacherReplayDropReason.ManifestContractMismatch: return "manifest_contract_mismatch";
                case Stage7BTeacherReplayDropReason.SourceSchemaUnknown: return "source_schema_unknown";
                case Stage7BTeacherReplayDropReason.MissingInitialState: return "missing_initial_state";
                case Stage7BTeacherReplayDropReason.MissingRuntimeState: return "missing_runtime_state";
                case Stage7BTeacherReplayDropReason.MissingRuntimeStateT: return "missing_runtime_state_t";
                case Stage7BTeacherReplayDropReason.MissingRuntimeStateTp1: return "missing_runtime_state_tp1";
                case Stage7BTeacherReplayDropReason.MissingTeacherCommands: return "missing_teacher_commands";
                case Stage7BTeacherReplayDropReason.MissingTeacherAction: return "missing_teacher_action";
                case Stage7BTeacherReplayDropReason.UnsupportedActionFormat: return "unsupported_action_format";
                case Stage7BTeacherReplayDropReason.BranchContractMismatch: return "branch_contract_mismatch";
                case Stage7BTeacherReplayDropReason.AttackTargetContractMismatch: return "attack_target_contract_mismatch";
                case Stage7BTeacherReplayDropReason.StateSyncFailed: return "state_sync_failed";
                case Stage7BTeacherReplayDropReason.UnityStateApiMissing: return "unity_state_api_missing";
                case Stage7BTeacherReplayDropReason.ObservationMismatch: return "observation_mismatch";
                case Stage7BTeacherReplayDropReason.TeacherNoOp: return "teacher_noop";
                case Stage7BTeacherReplayDropReason.MultipleNonNoOpActors: return "multiple_nonnoop_actors";
                case Stage7BTeacherReplayDropReason.ActorNotFound: return "actor_not_found";
                case Stage7BTeacherReplayDropReason.ActorTypeMismatch: return "actor_type_mismatch";
                case Stage7BTeacherReplayDropReason.ActorOwnerMismatch: return "actor_owner_mismatch";
                case Stage7BTeacherReplayDropReason.NoMatchingActor: return "no_matching_actor";
                case Stage7BTeacherReplayDropReason.NoMatchingCandidate: return "no_matching_candidate";
                case Stage7BTeacherReplayDropReason.ActionTypeUnsupported: return "action_type_unsupported";
                case Stage7BTeacherReplayDropReason.ActionNotLegalInUnity: return "action_not_legal_in_unity";
                case Stage7BTeacherReplayDropReason.DirectionMismatch: return "direction_mismatch";
                case Stage7BTeacherReplayDropReason.ProduceTypeMismatch: return "produce_type_mismatch";
                case Stage7BTeacherReplayDropReason.AttackTargetMismatch: return "attack_target_mismatch";
                case Stage7BTeacherReplayDropReason.CandidateOverflow: return "candidate_overflow";
                case Stage7BTeacherReplayDropReason.RuntimeApplyRejected: return "runtime_apply_rejected";
                case Stage7BTeacherReplayDropReason.RuntimeDesync: return "runtime_desync";
                case Stage7BTeacherReplayDropReason.PostStateDesync: return "post_state_desync";
                case Stage7BTeacherReplayDropReason.TerminalMismatch: return "terminal_mismatch";
                case Stage7BTeacherReplayDropReason.DuplicateSpawnDetected: return "duplicate_spawn_detected";
                case Stage7BTeacherReplayDropReason.Unknown: return "unknown";
                default: return "none";
            }
        }
    }
}
