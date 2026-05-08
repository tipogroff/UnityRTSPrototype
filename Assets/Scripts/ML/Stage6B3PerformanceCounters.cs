using System;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;

namespace RTS.ML
{
    internal enum Stage6B3PerfMetric
    {
        VisualRunnerUpdate = 0,
        VisualDiagnosticsRefresh = 1,
        ObservationBuild = 2,
        LegalMaskBuild = 3,
        PolicyInference = 4,
        BridgeRoundTrip = 5,
        ActionDecode = 6,
        ActionApply = 7,
        HeuristicDecision = 8,
        OnGui = 9,
        Gizmos = 10,
        JsonWrite = 11,
        Count = 12
    }

    internal static class Stage6B3PerformanceCounters
    {
        private static readonly string[] MetricNames =
        {
            "Week6VisualInspectionRunner.Update",
            "Week6VisualInspectionRunner.DiagnosticsRefresh",
            "ObservationBuilder.BuildObservation",
            "ActionMaskBuilder.BuildTransferCompatibleMask",
            "Week6StudentPolicyAdapter.ExecuteDecision",
            "Week6StudentPolicyAdapter.BridgeRoundTrip",
            "ActionDecoder.Decode",
            "ActionApplier.ApplyActions",
            "HeuristicPolicyAdapter.ExecuteDecision",
            "Week6VisualInspectionRunner.OnGUI",
            "Week6VisualInspectionRunner.OnDrawGizmos",
            "JSON/File writes"
        };

        private static readonly long[] Counts = new long[(int)Stage6B3PerfMetric.Count];
        private static readonly long[] TotalTicks = new long[(int)Stage6B3PerfMetric.Count];
        private static readonly long[] MaxTicks = new long[(int)Stage6B3PerfMetric.Count];

        private static readonly object Sync = new object();
        private static readonly Stopwatch WallClock = new Stopwatch();

        private static bool _enabled;
        private static string _mode = "unconfigured";
        private static string _scene = string.Empty;
        private static int _targetFrameRate;
        private static float _decisionTickIntervalSeconds;
        private static int _frameCount;
        private static float _deltaTimeTotal;
        private static float _deltaTimeMax;
        private static long _gcStartBytes;
        private static TimeSpan _processCpuStart;
        private static int _processorCount = 1;

        public static bool Enabled => _enabled;

        public static void Configure(
            bool enabled,
            string mode,
            string scene,
            int targetFrameRate,
            float decisionTickIntervalSeconds)
        {
            lock (Sync)
            {
                Array.Clear(Counts, 0, Counts.Length);
                Array.Clear(TotalTicks, 0, TotalTicks.Length);
                Array.Clear(MaxTicks, 0, MaxTicks.Length);

                _enabled = enabled;
                _mode = string.IsNullOrWhiteSpace(mode) ? "unknown" : mode;
                _scene = scene ?? string.Empty;
                _targetFrameRate = targetFrameRate;
                _decisionTickIntervalSeconds = decisionTickIntervalSeconds;
                _frameCount = 0;
                _deltaTimeTotal = 0f;
                _deltaTimeMax = 0f;
                _gcStartBytes = GC.GetTotalMemory(false);
                _processorCount = Math.Max(1, Environment.ProcessorCount);
                _processCpuStart = GetProcessCpu();
                WallClock.Reset();
                WallClock.Start();
            }
        }

        public static long Begin(Stage6B3PerfMetric metric)
        {
            if (!_enabled)
            {
                return -1L;
            }

            Increment(metric);
            return Stopwatch.GetTimestamp();
        }

        public static void End(Stage6B3PerfMetric metric, long startTimestamp)
        {
            if (!_enabled || startTimestamp < 0L)
            {
                return;
            }

            int index = (int)metric;
            long elapsed = Stopwatch.GetTimestamp() - startTimestamp;
            if (index < 0 || index >= TotalTicks.Length || elapsed < 0L)
            {
                return;
            }

            lock (Sync)
            {
                TotalTicks[index] += elapsed;
                if (elapsed > MaxTicks[index])
                {
                    MaxTicks[index] = elapsed;
                }
            }
        }

        public static void Increment(Stage6B3PerfMetric metric)
        {
            if (!_enabled)
            {
                return;
            }

            int index = (int)metric;
            if (index < 0 || index >= Counts.Length)
            {
                return;
            }

            lock (Sync)
            {
                Counts[index]++;
            }
        }

        public static void RecordFrame(float unscaledDeltaTime)
        {
            if (!_enabled)
            {
                return;
            }

            lock (Sync)
            {
                _frameCount++;
                _deltaTimeTotal += Mathf.Max(0f, unscaledDeltaTime);
                if (unscaledDeltaTime > _deltaTimeMax)
                {
                    _deltaTimeMax = unscaledDeltaTime;
                }
            }
        }

        public static void WriteSummary(
            string outputPath,
            int currentStep,
            bool step80Cleared,
            bool legalMaskEnabled,
            string checkpointRelativePath,
            int acceptedCommands,
            int rejectedCommands,
            int decisionRequestsSent,
            int decisionRequestsSucceeded,
            string note)
        {
            if (!_enabled || string.IsNullOrWhiteSpace(outputPath))
            {
                return;
            }

            string directory = Path.GetDirectoryName(outputPath);
            if (!string.IsNullOrWhiteSpace(directory))
            {
                Directory.CreateDirectory(directory);
            }

            File.WriteAllText(
                outputPath,
                BuildSummaryJson(
                    currentStep,
                    step80Cleared,
                    legalMaskEnabled,
                    checkpointRelativePath,
                    acceptedCommands,
                    rejectedCommands,
                    decisionRequestsSent,
                    decisionRequestsSucceeded,
                    note),
                Encoding.UTF8);
        }

        private static string BuildSummaryJson(
            int currentStep,
            bool step80Cleared,
            bool legalMaskEnabled,
            string checkpointRelativePath,
            int acceptedCommands,
            int rejectedCommands,
            int decisionRequestsSent,
            int decisionRequestsSucceeded,
            string note)
        {
            long[] countsCopy;
            long[] totalCopy;
            long[] maxCopy;
            int frameCount;
            float deltaTimeTotal;
            float deltaTimeMax;
            double elapsedSeconds;
            TimeSpan cpuStart;
            int processorCount;
            long gcStartBytes;

            lock (Sync)
            {
                countsCopy = (long[])Counts.Clone();
                totalCopy = (long[])TotalTicks.Clone();
                maxCopy = (long[])MaxTicks.Clone();
                frameCount = _frameCount;
                deltaTimeTotal = _deltaTimeTotal;
                deltaTimeMax = _deltaTimeMax;
                elapsedSeconds = Math.Max(0.0001, WallClock.Elapsed.TotalSeconds);
                cpuStart = _processCpuStart;
                processorCount = _processorCount;
                gcStartBytes = _gcStartBytes;
            }

            TimeSpan cpuDelta = GetProcessCpu() - cpuStart;
            double cpuPctAllCores = 100.0 * cpuDelta.TotalSeconds / (elapsedSeconds * processorCount);
            double cpuPctSingleCoreEquivalent = cpuPctAllCores * processorCount;
            long gcDeltaBytes = Math.Max(0L, GC.GetTotalMemory(false) - gcStartBytes);
            double fps = frameCount / elapsedSeconds;
            double avgFrameMs = frameCount > 0 ? (deltaTimeTotal / frameCount) * 1000.0 : 0.0;
            double maxFrameMs = deltaTimeMax * 1000.0;

            var sb = new StringBuilder(8192);
            sb.AppendLine("{");
            AppendString(sb, "generated_at_utc", DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture), comma: true);
            AppendString(sb, "mode", _mode, comma: true);
            AppendString(sb, "scene", _scene, comma: true);
            AppendNumber(sb, "elapsed_seconds", elapsedSeconds, comma: true);
            AppendNumber(sb, "frames", frameCount, comma: true);
            AppendNumber(sb, "average_fps", fps, comma: true);
            AppendNumber(sb, "average_frame_ms", avgFrameMs, comma: true);
            AppendNumber(sb, "max_frame_ms", maxFrameMs, comma: true);
            AppendNumber(sb, "process_cpu_pct_all_cores", cpuPctAllCores, comma: true);
            AppendNumber(sb, "process_cpu_pct_single_core_equivalent", cpuPctSingleCoreEquivalent, comma: true);
            AppendNumber(sb, "gc_managed_heap_delta_bytes", gcDeltaBytes, comma: true);
            AppendNumber(sb, "target_frame_rate", _targetFrameRate, comma: true);
            AppendNumber(sb, "decision_tick_interval_seconds", _decisionTickIntervalSeconds, comma: true);
            AppendNumber(sb, "current_step", currentStep, comma: true);
            AppendBool(sb, "step_80_boundary_cleared", step80Cleared, comma: true);
            AppendBool(sb, "legal_mask_enabled", legalMaskEnabled, comma: true);
            AppendString(sb, "checkpoint_relative_path", checkpointRelativePath ?? string.Empty, comma: true);
            AppendNumber(sb, "accepted_commands", acceptedCommands, comma: true);
            AppendNumber(sb, "rejected_commands", rejectedCommands, comma: true);
            AppendNumber(sb, "decision_requests_sent", decisionRequestsSent, comma: true);
            AppendNumber(sb, "decision_requests_succeeded", decisionRequestsSucceeded, comma: true);
            AppendString(sb, "note", note ?? string.Empty, comma: true);

            sb.AppendLine("  \"metrics\": {");
            for (int i = 0; i < MetricNames.Length; i++)
            {
                double totalMs = TicksToMilliseconds(totalCopy[i]);
                double maxMs = TicksToMilliseconds(maxCopy[i]);
                double avgMs = countsCopy[i] > 0 ? totalMs / countsCopy[i] : 0.0;
                double perSecond = countsCopy[i] / elapsedSeconds;

                sb.Append("    \"").Append(Escape(MetricNames[i])).AppendLine("\": {");
                AppendNumber(sb, "count", countsCopy[i], comma: true, indent: 6);
                AppendNumber(sb, "per_second", perSecond, comma: true, indent: 6);
                AppendNumber(sb, "total_ms", totalMs, comma: true, indent: 6);
                AppendNumber(sb, "avg_ms", avgMs, comma: true, indent: 6);
                AppendNumber(sb, "max_ms", maxMs, comma: false, indent: 6);
                sb.Append("    }");
                sb.AppendLine(i + 1 < MetricNames.Length ? "," : string.Empty);
            }
            sb.AppendLine("  },");

            sb.AppendLine("  \"top_instrumented_methods_by_total_ms\": [");
            int[] order = BuildMetricOrderByTotalMs(totalCopy);
            int printed = 0;
            for (int i = 0; i < order.Length && printed < 10; i++)
            {
                int metricIndex = order[i];
                if (totalCopy[metricIndex] <= 0L && countsCopy[metricIndex] <= 0L)
                {
                    continue;
                }

                if (printed > 0)
                {
                    sb.AppendLine(",");
                }

                sb.AppendLine("    {");
                AppendString(sb, "name", MetricNames[metricIndex], comma: true, indent: 6);
                AppendNumber(sb, "count", countsCopy[metricIndex], comma: true, indent: 6);
                AppendNumber(sb, "total_ms", TicksToMilliseconds(totalCopy[metricIndex]), comma: true, indent: 6);
                AppendNumber(sb, "avg_ms", countsCopy[metricIndex] > 0 ? TicksToMilliseconds(totalCopy[metricIndex]) / countsCopy[metricIndex] : 0.0, comma: false, indent: 6);
                sb.Append("    }");
                printed++;
            }
            if (printed > 0)
            {
                sb.AppendLine();
            }
            sb.AppendLine("  ]");
            sb.AppendLine("}");
            return sb.ToString();
        }

        private static int[] BuildMetricOrderByTotalMs(long[] totalTicks)
        {
            var order = new int[MetricNames.Length];
            for (int i = 0; i < order.Length; i++)
            {
                order[i] = i;
            }

            Array.Sort(order, (left, right) => totalTicks[right].CompareTo(totalTicks[left]));
            return order;
        }

        private static TimeSpan GetProcessCpu()
        {
            try
            {
                return Process.GetCurrentProcess().TotalProcessorTime;
            }
            catch
            {
                return TimeSpan.Zero;
            }
        }

        private static double TicksToMilliseconds(long ticks)
        {
            return ticks * 1000.0 / Stopwatch.Frequency;
        }

        private static void AppendString(StringBuilder sb, string name, string value, bool comma, int indent = 2)
        {
            AppendIndent(sb, indent);
            sb.Append('"').Append(Escape(name)).Append("\": \"").Append(Escape(value)).Append('"');
            sb.AppendLine(comma ? "," : string.Empty);
        }

        private static void AppendBool(StringBuilder sb, string name, bool value, bool comma, int indent = 2)
        {
            AppendIndent(sb, indent);
            sb.Append('"').Append(Escape(name)).Append("\": ").Append(value ? "true" : "false");
            sb.AppendLine(comma ? "," : string.Empty);
        }

        private static void AppendNumber(StringBuilder sb, string name, double value, bool comma, int indent = 2)
        {
            AppendIndent(sb, indent);
            sb.Append('"').Append(Escape(name)).Append("\": ")
                .Append(value.ToString("0.####", CultureInfo.InvariantCulture));
            sb.AppendLine(comma ? "," : string.Empty);
        }

        private static void AppendNumber(StringBuilder sb, string name, long value, bool comma, int indent = 2)
        {
            AppendIndent(sb, indent);
            sb.Append('"').Append(Escape(name)).Append("\": ")
                .Append(value.ToString(CultureInfo.InvariantCulture));
            sb.AppendLine(comma ? "," : string.Empty);
        }

        private static void AppendIndent(StringBuilder sb, int spaces)
        {
            for (int i = 0; i < spaces; i++)
            {
                sb.Append(' ');
            }
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
