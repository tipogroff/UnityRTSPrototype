using System;
using System.IO;
using UnityEngine;

namespace RTS.MLAgents.Stage7B.TeacherReplay
{
    [Serializable]
    public sealed class Stage7BTeacherReplaySourceInventoryBrief
    {
        public string selected_source_path;
        public string selected_source_format;
        public bool selected_source_replay_ready;
        public string selected_source_replay_ready_reason;
        public int source_count;
        public bool no_go_required;
        public string no_go_reason;
    }

    public sealed class Stage7BTeacherTrajectoryLoader
    {
        public bool TryLoadSourceInventory(string path, out Stage7BTeacherReplaySourceInventoryBrief inventory, out string diagnostics)
        {
            inventory = null;
            diagnostics = string.Empty;

            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
                diagnostics = "source inventory json is missing";
                return false;
            }

            try
            {
                string json = File.ReadAllText(path);
                inventory = JsonUtility.FromJson<Stage7BTeacherReplaySourceInventoryBrief>(json);
                if (inventory == null)
                {
                    diagnostics = "source inventory json could not be parsed";
                    return false;
                }

                diagnostics = "ok";
                return true;
            }
            catch (Exception ex)
            {
                diagnostics = ex.Message;
                return false;
            }
        }

        public bool TrySaveRuntimeReport(string path, Stage7BTeacherReplayReport report, out string diagnostics)
        {
            diagnostics = string.Empty;
            if (string.IsNullOrWhiteSpace(path) || report == null)
            {
                diagnostics = "invalid output path or report";
                return false;
            }

            try
            {
                string fullPath = Path.GetFullPath(path);
                string dir = Path.GetDirectoryName(fullPath);
                if (!string.IsNullOrWhiteSpace(dir))
                {
                    Directory.CreateDirectory(dir);
                }

                string json = JsonUtility.ToJson(report, true);
                File.WriteAllText(fullPath, json);
                diagnostics = fullPath;
                return true;
            }
            catch (Exception ex)
            {
                diagnostics = ex.Message;
                return false;
            }
        }
    }
}
