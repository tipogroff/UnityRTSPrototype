using System;
using System.IO;
using System.Text;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.Presentation
{
    /// <summary>
    /// Development-only trace for smooth visual movement interpolation.
    /// </summary>
    public static class Visual3EFSmoothMovementTrace
    {
        private const string TraceJsonlFileName = "Visual3EF_SmoothMovementTrace.jsonl";
        private const string TraceMarkdownFileName = "Visual3EF_SmoothMovementTrace.md";

        private static readonly object Sync = new object();
        private static bool _initialized;
        private static int _eventCount;
        private static int _startedCount;
        private static int _updatedCount;
        private static int _completedCount;
        private static int _snappedCount;
                public static bool Enabled { get; set; } = false;
private static int _interruptedCount;

public static void Reset(string reason)
        {
            if (!Enabled)
            {
                _eventCount = 0;
                _startedCount = 0;
                _updatedCount = 0;
                _completedCount = 0;
                _snappedCount = 0;
                _interruptedCount = 0;
                _initialized = false;
                return;
            }

#if UNITY_EDITOR || DEVELOPMENT_BUILD
            lock (Sync)
            {
                _eventCount = 0;
                _startedCount = 0;
                _updatedCount = 0;
                _completedCount = 0;
                _snappedCount = 0;
                _interruptedCount = 0;
                _initialized = true;

                File.WriteAllText(GetTraceJsonlPath(), string.Empty, Encoding.UTF8);
                File.WriteAllText(GetTraceMarkdownPath(), BuildMarkdown(reason), Encoding.UTF8);
            }
#endif
        }

        public static void RecordStarted(UnitRuntime unit, Vector3 previousWorldPosition, Vector3 currentWorldPosition, Vector3 initialOffset, float duration, string source, string diagnostic)
        {
            Record("VisualMoveInterpolationStarted", unit, previousWorldPosition, currentWorldPosition, initialOffset, duration, source, diagnostic, ref _startedCount);
        }

        public static void RecordUpdated(UnitRuntime unit, Vector3 previousWorldPosition, Vector3 currentWorldPosition, Vector3 initialOffset, float duration, string source, string diagnostic)
        {
            Record("VisualMoveInterpolationUpdated", unit, previousWorldPosition, currentWorldPosition, initialOffset, duration, source, diagnostic, ref _updatedCount);
        }

        public static void RecordCompleted(UnitRuntime unit, Vector3 previousWorldPosition, Vector3 currentWorldPosition, Vector3 initialOffset, float duration, string source, string diagnostic)
        {
            Record("VisualMoveInterpolationCompleted", unit, previousWorldPosition, currentWorldPosition, initialOffset, duration, source, diagnostic, ref _completedCount);
        }

        public static void RecordSnapped(UnitRuntime unit, Vector3 previousWorldPosition, Vector3 currentWorldPosition, Vector3 initialOffset, float duration, string source, string diagnostic)
        {
            RecordSnapped(unit, previousWorldPosition, currentWorldPosition, initialOffset, duration, source, diagnostic, false, Vector3.zero);
        }

        public static void RecordSnapped(UnitRuntime unit, Vector3 previousWorldPosition, Vector3 currentWorldPosition, Vector3 initialOffset, float duration, string source, string diagnostic, bool wasInterpolatingBeforeSnap, Vector3 visualOffsetBeforeSnap)
        {
            Record("VisualMoveInterpolationSnapped", unit, previousWorldPosition, currentWorldPosition, initialOffset, duration, source, diagnostic, ref _snappedCount, wasInterpolatingBeforeSnap, visualOffsetBeforeSnap);
        }

        public static void RecordInterrupted(UnitRuntime unit, Vector3 previousWorldPosition, Vector3 currentWorldPosition, Vector3 initialOffset, float duration, string source, string diagnostic)
        {
            Record("VisualMoveInterpolationInterrupted", unit, previousWorldPosition, currentWorldPosition, initialOffset, duration, source, diagnostic, ref _interruptedCount);
        }

private static void Record(
            string visualEvent,
            UnitRuntime unit,
            Vector3 previousWorldPosition,
            Vector3 currentWorldPosition,
            Vector3 initialOffset,
            float duration,
            string source,
            string diagnostic,
            ref int counter,
            bool wasInterpolatingBeforeSnap = false,
            Vector3 visualOffsetBeforeSnap = default)
        {
            if (!Enabled)
            {
                return;
            }

#if UNITY_EDITOR || DEVELOPMENT_BUILD
            lock (Sync)
            {
                EnsureInitialized();

                string unitInstanceId = unit != null ? unit.GetInstanceID().ToString() : "0";
                string unitType = unit != null ? unit.Type.ToString() : "Unknown";
                string owner = unit != null ? unit.Owner.ToString() : "Unknown";
                int frame = Time.frameCount;
                int step = MatchManager.Instance != null ? MatchManager.Instance.Step : -1;

                string line =
                    "{" +
                    "\"frame\":" + frame + "," +
                    "\"step\":" + step + "," +
                    "\"unit_instance_id\":\"" + Escape(unitInstanceId) + "\"," +
                    "\"unit_type\":\"" + Escape(unitType) + "\"," +
                    "\"owner\":\"" + Escape(owner) + "\"," +
                    "\"previous_world_position\":{" + Vector3Json(previousWorldPosition) + "}," +
                    "\"current_world_position\":{" + Vector3Json(currentWorldPosition) + "}," +
                    "\"initial_offset\":{" + Vector3Json(initialOffset) + "}," +
                    "\"was_interpolating_before_snap\":" + (wasInterpolatingBeforeSnap ? "true" : "false") + "," +
                    "\"visual_offset_before_snap\":{" + Vector3Json(visualOffsetBeforeSnap) + "}," +
                    "\"duration\":" + duration.ToString("0.000", System.Globalization.CultureInfo.InvariantCulture) + "," +
                    "\"visual_event\":\"" + Escape(visualEvent) + "\"," +
                    "\"source\":\"" + Escape(source) + "\"," +
                    "\"diagnostic\":\"" + Escape(diagnostic ?? string.Empty) + "\"" +
                    "}";

                File.AppendAllText(GetTraceJsonlPath(), line + Environment.NewLine, Encoding.UTF8);

                _eventCount++;
                counter++;
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
            sb.AppendLine("# Visual-3F Smooth Movement Trace");
            sb.AppendLine();
            sb.AppendLine("- Reason: " + reason);
            sb.AppendLine("- Updated UTC: " + DateTime.UtcNow.ToString("O"));
            sb.AppendLine("- Event count: " + _eventCount);
            sb.AppendLine("- Started count: " + _startedCount);
            sb.AppendLine("- Updated count: " + _updatedCount);
            sb.AppendLine("- Completed count: " + _completedCount);
            sb.AppendLine("- Snapped count: " + _snappedCount);
            sb.AppendLine("- Interrupted count: " + _interruptedCount);
            sb.AppendLine("- Trace JSONL: Assets/" + TraceJsonlFileName);
            return sb.ToString();
        }

        private static string Vector3Json(Vector3 value)
        {
            return "\"x\":" + value.x.ToString("0.000", System.Globalization.CultureInfo.InvariantCulture) +
                   ",\"y\":" + value.y.ToString("0.000", System.Globalization.CultureInfo.InvariantCulture) +
                   ",\"z\":" + value.z.ToString("0.000", System.Globalization.CultureInfo.InvariantCulture);
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