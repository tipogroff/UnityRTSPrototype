using RTS.Core;
using RTS.Gameplay;
using RTS.ML;
using RTS.MLAgents.Stage7B.CandidateActions;
using UnityEngine;

namespace RTS.MLAgents.Stage7B.TeacherReplay
{
    [DisallowMultipleComponent]
    public sealed class Stage7BTeacherTrajectoryReplayRunner : MonoBehaviour
    {
        [SerializeField] private string _sourceInventoryPath = "python/stage7b_teacher_replay/stage7b_teacher_replay_source_inventory.json";
        [SerializeField] private string _runtimeProbeReportPath = "python/stage7b_teacher_replay/stage7b_teacher_replay_runtime_probe_report.json";
        [SerializeField] private Owner _playerPerspective = Owner.Player1;
        [SerializeField] private bool _runOnStart;

        private readonly Stage7BTeacherTrajectoryLoader _loader = new Stage7BTeacherTrajectoryLoader();

        private void Start()
        {
            if (_runOnStart)
            {
                RunPrepProbe();
            }
        }

        [ContextMenu("Run Stage7B-6B Prep Probe")]
        public void RunPrepProbe()
        {
            var report = Stage7BTeacherReplayReport.CreateDefault();

            if (_loader.TryLoadSourceInventory(_sourceInventoryPath, out Stage7BTeacherReplaySourceInventoryBrief inventory, out string invDiagnostics))
            {
                report.selectedSourcePath = inventory.selected_source_path;
                report.selectedSourceFormat = inventory.selected_source_format;
                report.summary = inventory.selected_source_replay_ready
                    ? "Selected source is marked replay-ready by inventory."
                    : "Selected source is not replay-ready for authoritative Unity state sync.";

                if (inventory.no_go_required)
                {
                    report.notes.Add("Inventory NO_GO: " + inventory.no_go_reason);
                    report.IncrementDrop(Stage7BTeacherReplayDropReason.MissingRuntimeState);
                }
            }
            else
            {
                report.notes.Add("Failed to load source inventory: " + invDiagnostics);
                report.IncrementDrop(Stage7BTeacherReplayDropReason.SourceSchemaUnknown);
            }

            if (TryBuildRuntimeCandidates(out int candidateCount, out int overflowCount, out string runtimeDiagnostics))
            {
                report.episodesReplayAttempted = 1;
                report.stepsReplayAttempted = 1;
                report.candidateCountMin = candidateCount;
                report.candidateCountMax = candidateCount;
                report.candidateCountMean = candidateCount;
                report.candidateOverflowCount = overflowCount;
                if (overflowCount > 0)
                {
                    report.IncrementDrop(Stage7BTeacherReplayDropReason.CandidateOverflow);
                }

                report.notes.Add("Candidate builder called on live Unity runtime state.");
                report.notes.Add(runtimeDiagnostics);
            }
            else
            {
                report.notes.Add("Runtime candidate probe skipped: " + runtimeDiagnostics);
                report.IncrementDrop(Stage7BTeacherReplayDropReason.MissingRuntimeState);
            }

            // Prep gate remains strict: without authoritative trajectory state synchronization,
            // candidate match metrics and demo readiness cannot be claimed.
            report.status = "NO_GO";
            report.demoRecordingReady = false;
            report.RecomputeRates(stateSyncReliable: false);

            if (_loader.TrySaveRuntimeReport(_runtimeProbeReportPath, report, out string reportPath))
            {
                Debug.Log("[Stage7B][TeacherReplay] Runtime prep probe report written: " + reportPath);
            }
            else
            {
                Debug.LogWarning("[Stage7B][TeacherReplay] Failed to write runtime prep probe report: " + reportPath);
            }
        }

        private bool TryBuildRuntimeCandidates(out int candidateCount, out int overflowCount, out string diagnostics)
        {
            candidateCount = 0;
            overflowCount = 0;
            diagnostics = string.Empty;

            MatchManager match = MatchManager.Instance;
            GridManager grid = GridManager.Instance;
            UnitRegistry registry = UnitRegistry.Instance;
            MatchBootstrap bootstrap = MatchBootstrap.Instance;
            ResourceManager resources = ResourceManager.Instance;

            if (match == null || grid == null || registry == null || bootstrap == null)
            {
                diagnostics = "required runtime services are missing (MatchManager/GridManager/UnitRegistry/MatchBootstrap)";
                return false;
            }

            if (match.Phase != MatchPhase.Running)
            {
                diagnostics = "match is not in Running phase";
                return false;
            }

            var maskBuilder = new ActionMaskBuilder(match, grid, resources, registry, bootstrap);
            var candidateBuilder = new MlAgentsCandidateActionBuilder(maskBuilder);
            MlAgentsCandidateActionList candidates = candidateBuilder.Build(_playerPerspective);

            candidateCount = candidates.CandidateCount;
            overflowCount = candidates.OverflowCount;
            diagnostics = "candidate_count=" + candidateCount + ", overflow=" + overflowCount;
            return true;
        }
    }
}
