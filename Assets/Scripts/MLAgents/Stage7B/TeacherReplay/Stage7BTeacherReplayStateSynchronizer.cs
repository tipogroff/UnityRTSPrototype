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

            // Stage7B-6B prep gate keeps this strict: without authoritative runtime state payload,
            // synchronization is not considered reliable.
            dropReason = Stage7BTeacherReplayDropReason.MissingRuntimeState;
            diagnostics = "trajectory source does not contain authoritative Unity runtime state fields";
            return false;
        }
    }
}
