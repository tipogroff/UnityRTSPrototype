using System;

namespace RTS.MLAgents.Stage7B.TeacherConversion
{
    [Serializable]
    public sealed class Stage7BTeacherConversionReport
    {
        public string status;
        public string mode;
        public string sourceDatasetPath;

        public int totalSamples;
        public int processedSamples;
        public int matchedSamples;
        public int droppedSamples;

        public int nonNoOpTotal;
        public int nonNoOpMatched;
        public int noOpTotal;
        public int noOpMatchedToCandidate0;

        public float matchRate;
        public float nonNoOpMatchRate;

        public int stage7BCandidateBranchSize = 128;
        public int stage7BAttackTargetSize = 49;
        public int stage7BAttackTargetCenterIndex = 24;

        public bool stateReconstructionReliable;
        public bool demoRecordingReadyForStage7B6B;
        public bool stage6B3BaselineTouched;
    }
}
