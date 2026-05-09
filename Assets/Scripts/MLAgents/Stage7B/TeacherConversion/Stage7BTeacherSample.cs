using System;

namespace RTS.MLAgents.Stage7B.TeacherConversion
{
    [Serializable]
    public sealed class Stage7BTeacherSample
    {
        public string sampleId;
        public int episodeId;
        public int stepId;

        // Expected shape is either [576,27], [24,24,27], or flat [15552].
        public float[] observationFlat;

        // Per-cell action branches [576,7].
        public short[] targetActionBranchesFlat;

        public int[] targetActionShape;
        public int[] observationShape;
    }
}
