using System;

namespace RTS.MLAgents.Stage7B.TeacherReplay
{
    [Serializable]
    public sealed class Stage7BTeacherTrajectoryStep
    {
        public int episodeId;
        public int stepId;
        public bool done;
        public bool terminated;
        public bool truncated;

        // Flattened per-cell action branches, expected shape [576, 7] => length 4032.
        public int[] perCellActionBranchesFlat;

        public bool HasActionPayload => perCellActionBranchesFlat != null && perCellActionBranchesFlat.Length > 0;
    }
}
