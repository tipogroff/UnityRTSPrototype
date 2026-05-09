using System;

namespace RTS.MLAgents.Stage7B.TeacherConversion
{
    public enum Stage7BDropReason
    {
        None = 0,
        TeacherNoOp,
        NoNonNoOpActor,
        MultipleNonNoOpActors,
        NoMatchingActor,
        ActorNotOwned,
        ActorDeadOrMissing,
        ActionTypeUnsupported,
        ActionNotLegalInUnity,
        DirectionMismatch,
        ProduceTypeMismatch,
        AttackTargetMismatch,
        CandidateOverflow,
        StateReconstructionFailed,
        RuntimeDesync,
        ObservationContractMismatch,
        BranchContractMismatch,
        AttackTargetContractMismatch,
        DatasetSchemaUnknown,
        NpzArrayMissing,
        ManifestMissingOrInvalid,
        Unknown,
    }
}
