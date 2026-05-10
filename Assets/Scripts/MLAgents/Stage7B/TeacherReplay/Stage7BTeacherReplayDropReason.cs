namespace RTS.MLAgents.Stage7B.TeacherReplay
{
    public enum Stage7BTeacherReplayDropReason
    {
        None = 0,
        SourceSchemaUnknown,
        MissingInitialState,
        MissingRuntimeState,
        MissingTeacherAction,
        UnsupportedActionFormat,
        BranchContractMismatch,
        AttackTargetContractMismatch,
        StateSyncFailed,
        ObservationMismatch,
        TeacherNoOp,
        MultipleNonNoOpActors,
        NoMatchingActor,
        ActionTypeUnsupported,
        ActionNotLegalInUnity,
        DirectionMismatch,
        ProduceTypeMismatch,
        AttackTargetMismatch,
        CandidateOverflow,
        RuntimeApplyRejected,
        RuntimeDesync,
        TerminalMismatch,
        Unknown,
    }
}
