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

        // Replay-ready state bridge payloads (legacy032 Stage7B-6G+).
        public string initial_state_json;
        public string runtime_state_t_json;
        public string runtime_state_tp1_json;

        // Supports both replay-ready names seen in NPZ/JSONL exporters.
        public string teacher_commands_t_json;
        public string teacher_commands;

        // Flattened per-cell action branches, expected shape [576, 7] => length 4032.
        public int[] perCellActionBranchesFlat;

        public bool HasActionPayload => perCellActionBranchesFlat != null && perCellActionBranchesFlat.Length > 0;
        public bool HasInitialStateJson => !string.IsNullOrWhiteSpace(initial_state_json);
        public bool HasRuntimeStateTJson => !string.IsNullOrWhiteSpace(runtime_state_t_json);
        public bool HasRuntimeStateTp1Json => !string.IsNullOrWhiteSpace(runtime_state_tp1_json);
        public bool HasTeacherCommandsJson =>
            !string.IsNullOrWhiteSpace(teacher_commands_t_json) || !string.IsNullOrWhiteSpace(teacher_commands);
    }
}
