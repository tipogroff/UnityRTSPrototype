using System;

namespace RTS.MLAgents.Stage7B.TeacherReplay
{
    [Serializable]
    public sealed class Stage7BTeacherReplayManifest
    {
        public bool replay_ready;
        public int[] branch_sizes;
        public int attack_target_size;
        public int attack_target_center_index;
        public int[] observation_shape;
        public int[] action_shape;
    }

    [Serializable]
    public sealed class Stage7BTeacherReplayTeacherCommand
    {
        public int actor_flat;
        public int actor_x;
        public int actor_y;
        public int action_type;
        public int move_dir;
        public int harvest_dir;
        public int return_dir;
        public int produce_dir;
        public int produce_unit_type;
        public int attack_target_local;
        public int target_x;
        public int target_y;
    }

    [Serializable]
    public sealed class Stage7BTeacherReplayPlayerState
    {
        public int player_id;
        public int resources;
    }

    [Serializable]
    public sealed class Stage7BTeacherReplayUnitState
    {
        public int id;
        public string type;
        public int owner;
        public int x;
        public int y;
        public int hp;
        public int resources;
        public int carried_resources;
        public string current_action;
        public string pending_action;
    }

    [Serializable]
    public sealed class Stage7BTeacherReplayResourceNodeState
    {
        public int x;
        public int y;
        public int remaining;
    }

    [Serializable]
    public sealed class Stage7BTeacherReplayTerminalState
    {
        public bool done;
        public int winner;
        public string reason;
    }

    [Serializable]
    public sealed class Stage7BTeacherReplayRuntimeState
    {
        public int map_width;
        public int map_height;
        public int step;
        public Stage7BTeacherReplayPlayerState[] players;
        public Stage7BTeacherReplayUnitState[] units;
        public Stage7BTeacherReplayResourceNodeState[] resource_nodes;
        public object[] building_queues;
        public Stage7BTeacherReplayTerminalState terminal;
    }

    [Serializable]
    internal sealed class Stage7BTeacherReplayTeacherCommandArrayWrapper
    {
        public Stage7BTeacherReplayTeacherCommand[] items;
    }
}
