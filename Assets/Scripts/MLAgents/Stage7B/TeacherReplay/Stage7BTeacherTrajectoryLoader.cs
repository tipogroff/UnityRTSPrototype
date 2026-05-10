using System;
using System.Collections.Generic;
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
        private const string DefaultReplayManifest = "replay_manifest.json";

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

        public bool TryLoadReplayManifest(string sourceDir, out Stage7BTeacherReplayManifest manifest, out string diagnostics)
        {
            manifest = null;
            diagnostics = string.Empty;

            if (string.IsNullOrWhiteSpace(sourceDir))
            {
                diagnostics = "sourceDir is empty";
                return false;
            }

            string manifestPath = Path.Combine(sourceDir, DefaultReplayManifest);
            if (!File.Exists(manifestPath))
            {
                diagnostics = "replay_manifest.json is missing: " + manifestPath;
                return false;
            }

            try
            {
                string json = File.ReadAllText(manifestPath);
                manifest = JsonUtility.FromJson<Stage7BTeacherReplayManifest>(json);
                if (manifest == null)
                {
                    diagnostics = "failed to parse replay_manifest.json";
                    return false;
                }

                diagnostics = manifestPath;
                return true;
            }
            catch (Exception ex)
            {
                diagnostics = ex.Message;
                return false;
            }
        }

        public bool TryLoadReplayReadyJsonl(string sourceDir, out List<Stage7BTeacherTrajectoryStep> steps, out string diagnostics)
        {
            steps = new List<Stage7BTeacherTrajectoryStep>();
            diagnostics = string.Empty;

            if (string.IsNullOrWhiteSpace(sourceDir) || !Directory.Exists(sourceDir))
            {
                diagnostics = "sourceDir does not exist";
                return false;
            }

            string[] jsonlFiles = Directory.GetFiles(sourceDir, "episode_*.replay_ready.jsonl", SearchOption.TopDirectoryOnly);
            if (jsonlFiles.Length == 0)
            {
                diagnostics = "episode_*.replay_ready.jsonl is missing";
                return false;
            }

            Array.Sort(jsonlFiles, StringComparer.OrdinalIgnoreCase);
            string path = jsonlFiles[0];

            try
            {
                string[] lines = File.ReadAllLines(path);
                for (int i = 0; i < lines.Length; i++)
                {
                    string line = lines[i];
                    if (string.IsNullOrWhiteSpace(line))
                    {
                        continue;
                    }

                    Stage7BTeacherReplayJsonlRow row = JsonUtility.FromJson<Stage7BTeacherReplayJsonlRow>(line);
                    if (row == null)
                    {
                        diagnostics = "failed to parse jsonl row " + i;
                        return false;
                    }

                    var step = new Stage7BTeacherTrajectoryStep
                    {
                        episodeId = row.episode_id,
                        stepId = row.step_id,
                        done = row.done_t,
                        terminated = row.terminated_t,
                        truncated = row.truncated_t,
                        initial_state_json = row.initial_state_json,
                        runtime_state_t_json = row.runtime_state_t_json,
                        runtime_state_tp1_json = row.runtime_state_tp1_json,
                        teacher_commands_list = row.teacher_commands,
                    };

                    steps.Add(step);
                }

                diagnostics = path;
                return true;
            }
            catch (Exception ex)
            {
                diagnostics = ex.Message;
                return false;
            }
        }

        [Serializable]
        private sealed class Stage7BTeacherReplayJsonlRow
        {
            public int episode_id;
            public int step_id;
            public bool done_t;
            public bool terminated_t;
            public bool truncated_t;
            public string initial_state_json;
            public string runtime_state_t_json;
            public string runtime_state_tp1_json;
            public Stage7BTeacherReplayTeacherCommand[] teacher_commands;
        }

        public bool TrySaveText(string path, string content, out string diagnostics)
        {
            diagnostics = string.Empty;
            if (string.IsNullOrWhiteSpace(path))
            {
                diagnostics = "invalid output path";
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

                File.WriteAllText(fullPath, content ?? string.Empty);
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
