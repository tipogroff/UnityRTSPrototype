using RTS.Core;
using RTS.Gameplay;
using RTS.ML;
using UnityEngine;

namespace RTS.MLAgents.Stage7B.CandidateActions
{
    public sealed class MlAgentsActionAdapter
    {
        public bool LastInvalidCandidateIndexSelected { get; private set; }
        public bool LastEmptyCandidateSelected { get; private set; }
        public bool LastOutOfRangeCandidateSelected { get; private set; }
        public bool LastFallbackToNoOp { get; private set; }

        public AgentAction Resolve(MlAgentsCandidateActionList candidates, int candidateIndex, out MlAgentsCandidateAction candidate)
        {
            ResetLastDiagnostics();

            if (candidates == null)
            {
                return ResolveFallback(candidates, candidateIndex, out candidate, "candidate list is null or stale");
            }

            if (candidateIndex < 0 || candidateIndex >= MlAgentsCandidateActionList.BranchSize)
            {
                LastInvalidCandidateIndexSelected = true;
                LastOutOfRangeCandidateSelected = true;
                return ResolveFallback(
                    candidates,
                    candidateIndex,
                    out candidate,
                    $"candidate_action_index {candidateIndex} is outside [0,{MlAgentsCandidateActionList.BranchSize - 1}]");
            }

            candidate = candidates.GetOrEmpty(candidateIndex);

            if (candidate.IsEmpty)
            {
                LastInvalidCandidateIndexSelected = true;
                LastEmptyCandidateSelected = true;
                return ResolveFallback(
                    candidates,
                    candidateIndex,
                    out candidate,
                    $"candidate_action_index {candidateIndex} resolved to an empty candidate slot");
            }

            return candidate.Action;
        }

        private AgentAction ResolveFallback(
            MlAgentsCandidateActionList candidates,
            int candidateIndex,
            out MlAgentsCandidateAction candidate,
            string reason)
        {
            LastFallbackToNoOp = true;
            if (candidates != null && candidates.TryGetNoOpCandidate(out MlAgentsCandidateAction noOpCandidate))
            {
                candidate = noOpCandidate;
            }
            else
            {
                candidate = MlAgentsCandidateAction.CreateNoOpCandidate(MlAgentsCandidateActionList.NoOpCandidateIndex);
            }

            Debug.LogWarning($"[Stage7B] Falling back to NoOp for candidate_action_index {candidateIndex}: {reason}");
            return candidate.Action;
        }

        private void ResetLastDiagnostics()
        {
            LastInvalidCandidateIndexSelected = false;
            LastEmptyCandidateSelected = false;
            LastOutOfRangeCandidateSelected = false;
            LastFallbackToNoOp = false;
        }
    }
}
