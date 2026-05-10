namespace RTS.MLAgents.Stage7B.TeacherReplay
{
    public sealed class Stage7BTeacherReplayStateSynchronizer
    {
        public bool TrySynchronizeInitialState(
            Stage7BTeacherTrajectoryStep initialStep,
            out Stage7BTeacherReplayDropReason dropReason,
            out string diagnostics)
        {
            if (initialStep == null)
            {
                dropReason = Stage7BTeacherReplayDropReason.MissingInitialState;
                diagnostics = "initial trajectory step is missing";
                return false;
            }

            if (!initialStep.HasInitialStateJson)
            {
                dropReason = Stage7BTeacherReplayDropReason.MissingInitialState;
                diagnostics = "initial_state_json is missing";
                return false;
            }

            if (!initialStep.HasRuntimeStateTJson)
            {
                dropReason = Stage7BTeacherReplayDropReason.MissingRuntimeStateT;
                diagnostics = "runtime_state_t_json is missing";
                return false;
            }

            if (!initialStep.HasRuntimeStateTp1Json)
            {
                dropReason = Stage7BTeacherReplayDropReason.MissingRuntimeStateTp1;
                diagnostics = "runtime_state_tp1_json is missing";
                return false;
            }

            // Stage7B-6B prep gate keeps this strict: without authoritative runtime state payload,
            // synchronization is not considered reliable until full deterministic reconstruction is implemented.
            dropReason = Stage7BTeacherReplayDropReason.StateSyncFailed;
            diagnostics = "authoritative state payload is present, but deterministic Unity state reconstruction is not implemented in this synchronizer yet";
            return false;
        }
    }
}
