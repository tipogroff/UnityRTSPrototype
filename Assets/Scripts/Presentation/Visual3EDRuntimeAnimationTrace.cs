using System;
using System.IO;
using System.Text;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.Presentation
{
    /// <summary>
    /// Development-only JSONL/Markdown trace for runtime animation events.
    /// </summary>
    public static class Visual3EDRuntimeAnimationTrace
    {
        private const string TraceJsonlFileName = "Visual3ED_RuntimeAnimationTrace.jsonl";
        private const string TraceMarkdownFileName = "Visual3ED_RuntimeAnimationTrace.md";

        private static readonly object Sync = new object();
        private static bool _initialized;
        private static int _eventCount;
        private static int _successCount;
        private static int _failureCount;

        public static void Reset(string reason)
        {
#if UNITY_EDITOR || DEVELOPMENT_BUILD
            lock (Sync)
            {
                _eventCount = 0;
                _successCount = 0;
                _failureCount = 0;
                _initialized = true;

                File.WriteAllText(GetTraceJsonlPath(), string.Empty, Encoding.UTF8);
                File.WriteAllText(GetTraceMarkdownPath(), BuildMarkdown(reason), Encoding.UTF8);
            }
#endif
        }

        public static void Record(
            UnitRuntime unit,
            string visualEvent,
            string animatorParameter,
            string source,
            bool success,
            string diagnostic,
            string cloneId = "")
        {
            Record(
                unit != null ? unit.GetInstanceID().ToString() : "0",
                unit != null ? unit.Type.ToString() : "Unknown",
                unit != null ? unit.Owner.ToString() : "Unknown",
                unit != null ? unit.GridPos : GridPosition.Zero,
                visualEvent,
                animatorParameter,
                source,
                success,
                diagnostic,
                cloneId);
        }

        public static void Record(
            string unitInstanceId,
            string unitType,
            string owner,
            GridPosition gridPosition,
            string visualEvent,
            string animatorParameter,
            string source,
            bool success,
            string diagnostic,
            string cloneId = "")
        {
#if UNITY_EDITOR || DEVELOPMENT_BUILD
            lock (Sync)
            {
                EnsureInitialized();

                int frame = Time.frameCount;
                int step = MatchManager.Instance != null ? MatchManager.Instance.Step : -1;

                string line =
                    "{" +
                    "\"frame\":" + frame + "," +
                    "\"step\":" + step + "," +
                    "\"unit_instance_id\":\"" + Escape(unitInstanceId) + "\"," +
                    "\"unit_type\":\"" + Escape(unitType) + "\"," +
                    "\"owner\":\"" + Escape(owner) + "\"," +
                    "\"grid_position\":{\"x\":" + gridPosition.X + ",\"y\":" + gridPosition.Y + "}," +
                    "\"visual_event\":\"" + Escape(visualEvent) + "\"," +
                    "\"animator_parameter_changed\":\"" + Escape(animatorParameter) + "\"," +
                    "\"clone_id\":\"" + Escape(cloneId) + "\"," +
                    "\"source\":\"" + Escape(source) + "\"," +
                    "\"success\":" + (success ? "true" : "false") + "," +
                    "\"diagnostic\":\"" + Escape(diagnostic ?? string.Empty) + "\"" +
                    "}";

                File.AppendAllText(GetTraceJsonlPath(), line + Environment.NewLine, Encoding.UTF8);

                _eventCount++;
                if (success)
                {
                    _successCount++;
                }
                else
                {
                    _failureCount++;
                }

                File.WriteAllText(GetTraceMarkdownPath(), BuildMarkdown("runtime update"), Encoding.UTF8);
            }
#endif
        }

        private static void EnsureInitialized()
        {
            if (_initialized)
            {
                return;
            }

            _initialized = true;
            if (!File.Exists(GetTraceJsonlPath()))
            {
                File.WriteAllText(GetTraceJsonlPath(), string.Empty, Encoding.UTF8);
            }

            File.WriteAllText(GetTraceMarkdownPath(), BuildMarkdown("auto-init"), Encoding.UTF8);
        }

        private static string GetTraceJsonlPath()
        {
            return Path.Combine(Application.dataPath, TraceJsonlFileName);
        }

        private static string GetTraceMarkdownPath()
        {
            return Path.Combine(Application.dataPath, TraceMarkdownFileName);
        }

        private static string BuildMarkdown(string reason)
        {
            var sb = new StringBuilder(256);
            sb.AppendLine("# Visual-3E-D Runtime Animation Trace");
            sb.AppendLine();
            sb.AppendLine("- Reason: " + reason);
            sb.AppendLine("- Updated UTC: " + DateTime.UtcNow.ToString("O"));
            sb.AppendLine("- Event count: " + _eventCount);
            sb.AppendLine("- Success count: " + _successCount);
            sb.AppendLine("- Failure count: " + _failureCount);
            sb.AppendLine("- Trace JSONL: Assets/" + TraceJsonlFileName);
            return sb.ToString();
        }

        private static string Escape(string value)
        {
            if (string.IsNullOrEmpty(value))
            {
                return string.Empty;
            }

            return value
                .Replace("\\", "\\\\")
                .Replace("\"", "\\\"")
                .Replace("\r", "\\r")
                .Replace("\n", "\\n");
        }
    }
}
