#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
using RTS.Core;
using RTS.Gameplay;
using UnityEditor;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RTS.ML.Editor
{
    [InitializeOnLoad]
    public static class Week6Stage10UnitySceneDryRunMenu
    {
        private const string MenuPath = "RTS/Week6/Stage10 Unity Scene Dry Run";
        private const string PendingKey = "RTS.Week6.Stage10.Pending";
        private const string PollCountKey = "RTS.Week6.Stage10.PollCount";
        private const int MaxPolls = 300;
        private const int BoundedMaxSteps = 200;

        private const string TargetScenePath = "Assets/Scenes/Week6_StudentVisualInspection.unity";
        private const string ReportRelativePath = "python/week6_student/reports/LEGACY032_UNITY_V2_STAGE10_UNITY_SCENE_DRY_RUN_REPORT.md";
        private const string ExpectedCheckpointRelativePath = "python/week6_student/runs/legacy032_v2_stage10d14_unity_like_augmented_bc_20260503T1455Z/student_bc_stage10d14_augmented_best.pt";

        static Week6Stage10UnitySceneDryRunMenu()
        {
            EditorApplication.playModeStateChanged -= HandlePlayModeStateChanged;
            EditorApplication.playModeStateChanged += HandlePlayModeStateChanged;
            EditorApplication.update -= PollPendingRun;
            EditorApplication.update += PollPendingRun;
        }

        [MenuItem(MenuPath)]
        public static void RunStage10DryRun()
        {
            Scene activeScene = SceneManager.GetActiveScene();
            if (!activeScene.IsValid() || !string.Equals(activeScene.path, TargetScenePath, StringComparison.Ordinal))
            {
                Debug.LogError($"[Stage10DryRun] Open target scene before running Stage 10: {TargetScenePath}");
                WriteFailureReportFromEditor("scene_wiring_issue", $"Active scene is '{activeScene.path}', expected '{TargetScenePath}'.");
                return;
            }

            SessionState.SetBool(PendingKey, true);
            SessionState.SetInt(PollCountKey, 0);

            if (Application.isPlaying)
            {
                ExecutePendingRun();
                return;
            }

            Debug.Log("[Stage10DryRun] Entering Play Mode for controlled Stage 10 dry-run...");
            EditorApplication.isPlaying = true;
        }

        private static void HandlePlayModeStateChanged(PlayModeStateChange change)
        {
            if (!SessionState.GetBool(PendingKey, false))
            {
                return;
            }

            if (change == PlayModeStateChange.EnteredPlayMode)
            {
                SessionState.SetInt(PollCountKey, 0);
                Debug.Log("[Stage10DryRun] Entered Play Mode. Waiting for runtime readiness...");
            }

            if (change == PlayModeStateChange.ExitingPlayMode || change == PlayModeStateChange.EnteredEditMode)
            {
                SessionState.EraseBool(PendingKey);
                SessionState.EraseInt(PollCountKey);
            }
        }

        private static void PollPendingRun()
        {
            if (!SessionState.GetBool(PendingKey, false) || !Application.isPlaying)
            {
                return;
            }

            int polls = SessionState.GetInt(PollCountKey, 0) + 1;
            SessionState.SetInt(PollCountKey, polls);

            if (!TryResolveRuntime(out _))
            {
                if (polls < MaxPolls)
                {
                    return;
                }

                SessionState.EraseBool(PendingKey);
                SessionState.EraseInt(PollCountKey);
                Debug.LogError("[Stage10DryRun] Runtime objects did not become ready in time.");
                WriteFailureReportFromEditor("scene_wiring_issue", "Runtime objects were not ready after entering Play Mode.");
                EditorApplication.isPlaying = false;
                return;
            }

            ExecutePendingRun();
        }

        private static void ExecutePendingRun()
        {
            SessionState.EraseBool(PendingKey);
            SessionState.EraseInt(PollCountKey);

            bool shouldExitPlayMode = Application.isPlaying;
            try
            {
                RunControlledDryRun();
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
                WriteFailureReportFromEditor("other", ex.ToString());
            }
            finally
            {
                if (shouldExitPlayMode && Application.isPlaying)
                {
                    EditorApplication.isPlaying = false;
                }
            }
        }

        private static void RunControlledDryRun()
        {
            if (!TryResolveRuntime(out RuntimeRefs runtime))
            {
                WriteFailureReportFromEditor("scene_wiring_issue", "Required runtime references are missing in Play Mode.");
                return;
            }

            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? string.Empty;
            string reportPath = Path.Combine(projectRoot, ReportRelativePath);
            string checkpointRelativePath = runtime.Adapter.CheckpointRelativePath;
            string checkpointPath = Path.GetFullPath(Path.Combine(projectRoot, checkpointRelativePath));
            string device = GetPrivateField(runtime.Adapter, "_device", "cpu");
            string artifactRelativePath = GetPrivateField(runtime.Adapter, "_artifactDirectoryRelativePath", string.Empty);
            string artifactPrefix = GetPrivateField(runtime.Adapter, "_artifactFilePrefix", "day5_sanity");

            int scenarioPreset = GetPrivateEnumInt(runtime.Bootstrap, "_scenarioPreset", 0);
            bool controllerAutoStart = GetPrivateField(runtime.Controller, "_autoStartOnPlay", false);
            bool runnerAutoStart = GetPrivateField(runtime.Runner, "_autoStartOnPlay", false);
            bool enableStudentControl = GetPrivateField(runtime.Controller, "_enableWeek6StudentMatchControl", false);
            Week6PlayerControlMode player1Mode = GetPrivateField(runtime.Controller, "_player1DecisionMode", Week6PlayerControlMode.Idle);
            Week6PlayerControlMode player2Mode = GetPrivateField(runtime.Controller, "_player2DecisionMode", Week6PlayerControlMode.Idle);

            var startupFindings = new List<Finding>();
            var aggregateActionTypeHistogram = CreateActionTypeHistogram();
            var aggregatePreMaskHistogram = CreateActionTypeHistogram();
            var rejectionReasonHistogram = new Dictionary<string, int>(StringComparer.Ordinal);
            var runtimeRejectedReasonHistogram = new Dictionary<string, int>(StringComparer.Ordinal);
            var acceptedCommandSamples = new List<string>(50);
            var rejectedCommandSamples = new List<string>(50);
            var decodedCommandSamples = new List<string>(50);
            var nonNoopDecodedSamples = new List<string>(20);
            var stepActionHistogramSamples = new List<string>(20);

            bool applyCommandCalled = false;
            bool advanceStepCalled = false;
            bool stepCountAdvanced = false;
            bool actionApplierReached = false;
            int acceptedCommandCount = 0;
            int rejectedCommandCount = 0;
            int ignoredCommandCount = 0;
            int totalAcceptedFromReports = 0;
            int totalRejectedFromReports = 0;
            int totalDecodedActions = 0;
            int totalMeaningfulAcceptedCommands = 0;
            int totalWrongOwnerAfterFilter = 0;
            int totalCommandsBuiltAfterFilter = 0;
            int totalCommandsSubmittedAfterFilter = 0;
            int totalEligibleOwnActorCells = 0;
            int totalCandidateCells = 0;
            int totalFallbackToNoop = 0;
            int totalMaskedOutChoices = 0;
            int stepsActuallyRun = 0;
            bool reachedTerminal = false;
            string terminalReason = "none";
            Owner winner = Owner.Neutral;
            string stopReason = $"bounded_step_cap_{BoundedMaxSteps}";
            string runtimeFailure = string.Empty;
            string failureCategory = string.Empty;

            int runtimeRunnerCount = CountObjects<Week6VisualInspectionRunner>();
            int runtimeAdapterCount = CountObjects<Week6StudentPolicyAdapter>();
            int runtimeControllerCount = CountObjects<EpisodeController>();
            int runtimeHeuristicAdapterCount = CountObjects<HeuristicPolicyAdapter>();

            bool previousAutoStep = runtime.Controller.AutoStepInFixedUpdate;
            runtime.Controller.AutoStepInFixedUpdate = false;

            runtime.MatchManager.OnCommandAccepted += OnCommandAccepted;
            runtime.MatchManager.OnCommandRejected += OnCommandRejected;
            runtime.MatchManager.OnStepAdvanced += OnStepAdvanced;

            try
            {
                runtime.Runner.StartVisualInspectionMatch();

                var startupPlacement = CapturePlacementSummary(runtime.Registry);
                ObservationSnapshot observationSnapshot = CaptureObservationSnapshot(runtime);
                AdapterArtifactSnapshot firstArtifact = default;

                ValidatePreflight(
                    startupFindings,
                    scenarioPreset,
                    controllerAutoStart,
                    runnerAutoStart,
                    enableStudentControl,
                    player1Mode,
                    player2Mode,
                    runtimeRunnerCount,
                    runtimeAdapterCount,
                    runtimeControllerCount,
                    runtimeHeuristicAdapterCount,
                    checkpointRelativePath,
                    checkpointPath,
                    startupPlacement,
                    observationSnapshot,
                    projectRoot,
                    artifactRelativePath,
                    artifactPrefix);

                for (int stepIndex = 0; stepIndex < BoundedMaxSteps && runtime.Controller.IsRunning; stepIndex++)
                {
                    int stepBefore = runtime.MatchManager.Step;
                    bool continueRunning = runtime.Controller.StepEpisodeOnce();
                    int stepAfter = runtime.MatchManager.Step;

                    stepsActuallyRun++;
                    if (stepAfter > stepBefore)
                    {
                        stepCountAdvanced = true;
                    }

                    if (!runtime.Controller.TryGetWeek6StudentExecutionReport(Owner.Player1, out StudentPolicyExecutionReport report))
                    {
                        runtimeFailure = "Student execution report is missing for current step.";
                        failureCategory = "scene_wiring_issue";
                        stopReason = "missing_student_report";
                        break;
                    }

                    actionApplierReached |= report.FilterDiagnostics.CommandsBuiltAfterFilter > 0;
                    applyCommandCalled |= report.AcceptedCount > 0 || report.RejectedCount > 0;
                    totalAcceptedFromReports += report.AcceptedCount;
                    totalRejectedFromReports += report.RejectedCount;
                    totalDecodedActions += report.DecodedActionCount;
                    totalCommandsBuiltAfterFilter += report.FilterDiagnostics.CommandsBuiltAfterFilter;
                    totalCommandsSubmittedAfterFilter += report.FilterDiagnostics.CommandsSubmittedAfterFilter;
                    totalWrongOwnerAfterFilter += report.FilterDiagnostics.WrongOwnerRejectionsAfterFilter;
                    totalEligibleOwnActorCells += report.FilterDiagnostics.EligibleOwnActorCells;
                    totalCandidateCells += report.FilterDiagnostics.CandidateCellsTotal;
                    totalFallbackToNoop += report.MaskAwareDiagnostics.FallbackToNoopCount;
                    totalMaskedOutChoices += report.MaskAwareDiagnostics.MaskedOutActionTypeChoicesCount;

                    if (!report.BridgeSucceeded)
                    {
                        runtimeFailure = string.IsNullOrWhiteSpace(report.Error) ? "Student bridge request failed." : report.Error;
                        failureCategory = ClassifyFailure(runtimeFailure);
                        stopReason = "fatal_runtime_error";
                        break;
                    }

                    if (TryReadLatestAdapterArtifact(projectRoot, artifactRelativePath, artifactPrefix, out AdapterArtifactSnapshot artifact))
                    {
                        if (!firstArtifact.IsAvailable)
                        {
                            firstArtifact = artifact;
                        }
                    }

                    var stepHistogram = CreateActionTypeHistogram();
                    MergeActionHistogram(stepHistogram, report.MaskAwareDiagnostics.PostMaskHistogram);
                    if (HistogramTotal(stepHistogram) == 0)
                    {
                        foreach (AgentAction action in report.DecodedActions)
                        {
                            IncrementAction(stepHistogram, action.ActionType, 1);
                        }
                    }

                    MergeActionHistogram(aggregateActionTypeHistogram, stepHistogram);
                    MergeActionHistogram(aggregatePreMaskHistogram, report.MaskAwareDiagnostics.PreMaskRawHistogram);

                    foreach (string reason in report.RejectionReasons)
                    {
                        IncrementString(rejectionReasonHistogram, NormalizeReason(reason), 1);
                    }

                    foreach (AgentAction action in report.DecodedActions)
                    {
                        if (decodedCommandSamples.Count < 50)
                        {
                            decodedCommandSamples.Add(action.ToString());
                        }

                        if (action.ActionType != UnitActionType.NoOp && nonNoopDecodedSamples.Count < 20)
                        {
                            nonNoopDecodedSamples.Add(action.ToString());
                        }
                    }

                    if (stepActionHistogramSamples.Count < 20)
                    {
                        stepActionHistogramSamples.Add($"step={stepAfter} {FormatActionHistogram(stepHistogram)} accepted={report.AcceptedCount} rejected={report.RejectedCount}");
                    }

                    if (stepIndex < 20)
                    {
                        Debug.Log($"[Stage10DryRun] step={stepAfter}, decoded={report.DecodedActionCount}, accepted={report.AcceptedCount}, rejected={report.RejectedCount}, hist={FormatActionHistogram(stepHistogram)}");
                    }

                    if (!continueRunning || !runtime.Controller.IsRunning)
                    {
                        reachedTerminal = true;
                        EpisodeEndReport endReport = runtime.Controller.LastTerminalReport;
                        terminalReason = endReport.TerminalReason.ToString();
                        winner = endReport.Winner;
                        stopReason = "runtime_terminal";
                        break;
                    }
                }

                if (!firstArtifact.IsAvailable)
                {
                    TryReadLatestAdapterArtifact(projectRoot, artifactRelativePath, artifactPrefix, out firstArtifact);
                }

                if (string.IsNullOrWhiteSpace(runtimeFailure) && !stepCountAdvanced)
                {
                    runtimeFailure = "Step count did not advance during the bounded run.";
                    failureCategory = "scene_wiring_issue";
                }

                if (!reachedTerminal && string.IsNullOrWhiteSpace(runtimeFailure))
                {
                    runtime.Controller.SetRunning(false);
                    terminalReason = "none";
                }

                StudentBridgeRuntimeSnapshot bridgeSnapshot = runtime.Adapter.GetRuntimeSnapshot();
                runtime.Adapter.ShutdownBridgeForSanity();

                totalMeaningfulAcceptedCommands = acceptedCommandCount;
                ignoredCommandCount = rejectedCommandCount;

                Decision decision = Decide(
                    runtimeFailure,
                    bridgeSnapshot,
                    stepCountAdvanced,
                    applyCommandCalled,
                    actionApplierReached,
                    totalMeaningfulAcceptedCommands);

                PopulateFindings(
                    startupFindings,
                    runtimeFailure,
                    failureCategory,
                    bridgeSnapshot,
                    stepCountAdvanced,
                    applyCommandCalled,
                    actionApplierReached,
                    totalMeaningfulAcceptedCommands,
                    aggregateActionTypeHistogram,
                    totalWrongOwnerAfterFilter,
                    rejectedCommandCount,
                    firstArtifact);

                string markdown = BuildMarkdownReport(new ReportModel
                {
                    Decision = decision,
                    FailureCategory = failureCategory,
                    RuntimeFailure = runtimeFailure,
                    SceneName = SceneManager.GetActiveScene().name,
                    ScenePath = TargetScenePath,
                    ScenarioPreset = scenarioPreset,
                    MapWidth = runtime.Bootstrap.GetConfig() != null ? runtime.Bootstrap.GetConfig().mapWidth : runtime.GridManager.Width,
                    MapHeight = runtime.Bootstrap.GetConfig() != null ? runtime.Bootstrap.GetConfig().mapHeight : runtime.GridManager.Height,
                    InitialPlacementLines = startupPlacement.PlacementLines,
                    DuplicateOccupancyLines = startupPlacement.DuplicateOccupancyLines,
                    CheckpointRelativePath = checkpointRelativePath,
                    CheckpointExists = File.Exists(checkpointPath),
                    ActiveRunner = nameof(Week6VisualInspectionRunner),
                    ManualTriggerMode = !runnerAutoStart,
                    ControllerAutoStart = controllerAutoStart,
                    RunnerAutoStart = runnerAutoStart,
                    EnableStudentControl = enableStudentControl,
                    Player1Mode = player1Mode,
                    Player2Mode = player2Mode,
                    Device = device,
                    StartupFindings = startupFindings,
                    Observation = observationSnapshot,
                    Artifact = firstArtifact,
                    BridgeSnapshot = bridgeSnapshot,
                    DecodedCommandSamples = decodedCommandSamples,
                    NonNoopDecodedSamples = nonNoopDecodedSamples,
                    AcceptedCommandSamples = acceptedCommandSamples,
                    RejectedCommandSamples = rejectedCommandSamples,
                    AcceptedCommandCount = acceptedCommandCount,
                    RejectedCommandCount = totalRejectedFromReports,
                    IgnoredCommandCount = ignoredCommandCount,
                    RejectionReasonHistogram = rejectionReasonHistogram,
                    RuntimeRejectedReasonHistogram = runtimeRejectedReasonHistogram,
                    ApplyCommandCalled = applyCommandCalled,
                    ActionApplierCalled = actionApplierReached,
                    AdvanceStepCalled = advanceStepCalled,
                    StepCountAdvanced = stepCountAdvanced,
                    EpisodesRun = 1,
                    MaxStepsConfigured = BoundedMaxSteps,
                    StepsActuallyRun = stepsActuallyRun,
                    ReachedTerminal = reachedTerminal,
                    TerminalReason = terminalReason,
                    Winner = winner,
                    StopReason = stopReason,
                    ActionHistogram = aggregateActionTypeHistogram,
                    PreMaskHistogram = aggregatePreMaskHistogram,
                    StepHistogramSamples = stepActionHistogramSamples,
                    TotalAcceptedFromReports = totalAcceptedFromReports,
                    TotalRejectedFromReports = totalRejectedFromReports,
                    TotalDecodedActions = totalDecodedActions,
                    TotalWrongOwnerAfterFilter = totalWrongOwnerAfterFilter,
                    TotalCommandsBuiltAfterFilter = totalCommandsBuiltAfterFilter,
                    TotalCommandsSubmittedAfterFilter = totalCommandsSubmittedAfterFilter,
                    TotalEligibleOwnActorCells = totalEligibleOwnActorCells,
                    TotalCandidateCells = totalCandidateCells,
                    TotalFallbackToNoop = totalFallbackToNoop,
                    TotalMaskedOutChoices = totalMaskedOutChoices,
                    RuntimeRunnerCount = runtimeRunnerCount,
                    RuntimeAdapterCount = runtimeAdapterCount,
                    RuntimeControllerCount = runtimeControllerCount,
                    RuntimeHeuristicAdapterCount = runtimeHeuristicAdapterCount,
                });

                Directory.CreateDirectory(Path.GetDirectoryName(reportPath) ?? projectRoot);
                File.WriteAllText(reportPath, markdown, Encoding.UTF8);
                Debug.Log($"[Stage10DryRun] Report written: {reportPath}");
            }
            finally
            {
                runtime.MatchManager.OnCommandAccepted -= OnCommandAccepted;
                runtime.MatchManager.OnCommandRejected -= OnCommandRejected;
                runtime.MatchManager.OnStepAdvanced -= OnStepAdvanced;
                runtime.Controller.AutoStepInFixedUpdate = previousAutoStep;
            }

            void OnCommandAccepted(MatchCommand command)
            {
                if (command.Owner != Owner.Player1)
                {
                    return;
                }

                applyCommandCalled = true;
                acceptedCommandCount++;
                if (command.ActionType != UnitActionType.NoOp)
                {
                    totalMeaningfulAcceptedCommands++;
                }

                if (acceptedCommandSamples.Count < 50)
                {
                    acceptedCommandSamples.Add(FormatMatchCommand(command));
                }
            }

            void OnCommandRejected(MatchCommand command, string reason)
            {
                if (command.Owner != Owner.Player1)
                {
                    return;
                }

                applyCommandCalled = true;
                rejectedCommandCount++;
                IncrementString(runtimeRejectedReasonHistogram, NormalizeReason(reason), 1);
                if (rejectedCommandSamples.Count < 50)
                {
                    rejectedCommandSamples.Add(FormatMatchCommand(command) + $" | reason={NormalizeReason(reason)}");
                }
            }

            void OnStepAdvanced(int _)
            {
                advanceStepCalled = true;
            }
        }

        private static void ValidatePreflight(
            List<Finding> findings,
            int scenarioPreset,
            bool controllerAutoStart,
            bool runnerAutoStart,
            bool enableStudentControl,
            Week6PlayerControlMode player1Mode,
            Week6PlayerControlMode player2Mode,
            int runtimeRunnerCount,
            int runtimeAdapterCount,
            int runtimeControllerCount,
            int runtimeHeuristicAdapterCount,
            string checkpointRelativePath,
            string checkpointPath,
            PlacementSummary placement,
            ObservationSnapshot observation,
            string projectRoot,
            string artifactRelativePath,
            string artifactPrefix)
        {
            findings.Add(new Finding(scenarioPreset == 4 ? Severity.Pass : Severity.Fail, $"Scenario preset = {scenarioPreset} (expected 4)."));
            findings.Add(new Finding(!controllerAutoStart ? Severity.Pass : Severity.Fail, $"EpisodeController auto-start = {controllerAutoStart}."));
            findings.Add(new Finding(!runnerAutoStart ? Severity.Pass : Severity.Fail, $"Week6VisualInspectionRunner auto-start = {runnerAutoStart}."));
            findings.Add(new Finding(enableStudentControl ? Severity.Pass : Severity.Fail, $"Week6 student match control enabled = {enableStudentControl}."));
            findings.Add(new Finding(player1Mode == Week6PlayerControlMode.StudentInference ? Severity.Pass : Severity.Fail, $"Player1 mode = {player1Mode}."));
            findings.Add(new Finding(player2Mode == Week6PlayerControlMode.HeuristicBaseline ? Severity.Pass : Severity.Fail, $"Player2 mode = {player2Mode}."));
            findings.Add(new Finding(runtimeRunnerCount == 1 ? Severity.Pass : Severity.Fail, $"Active Week6VisualInspectionRunner count = {runtimeRunnerCount}."));
            findings.Add(new Finding(runtimeAdapterCount == 1 ? Severity.Pass : Severity.Fail, $"Active Week6StudentPolicyAdapter count = {runtimeAdapterCount}."));
            findings.Add(new Finding(runtimeControllerCount == 1 ? Severity.Pass : Severity.Fail, $"Active EpisodeController count = {runtimeControllerCount}."));
            findings.Add(new Finding(runtimeHeuristicAdapterCount == 1 ? Severity.Pass : Severity.Warning, $"Active HeuristicPolicyAdapter count = {runtimeHeuristicAdapterCount}."));
            findings.Add(new Finding(string.Equals(checkpointRelativePath, ExpectedCheckpointRelativePath, StringComparison.Ordinal) ? Severity.Pass : Severity.Fail, $"Active checkpoint path = {checkpointRelativePath}."));
            findings.Add(new Finding(File.Exists(checkpointPath) ? Severity.Pass : Severity.Fail, $"Checkpoint exists = {File.Exists(checkpointPath)}."));
            findings.Add(new Finding(placement.DuplicateOccupancyLines.Count == 0 ? Severity.Pass : Severity.Fail, $"Duplicate occupancy count = {placement.DuplicateOccupancyLines.Count}."));
            findings.Add(new Finding(observation.ShapeMatchesContract ? Severity.Pass : Severity.Fail, $"Observation shape = [{observation.ShapeLabel}] (expected 24,24,27)."));
            findings.Add(new Finding(!observation.HasNaN && !observation.HasInf ? Severity.Pass : Severity.Fail, $"Observation NaN = {observation.HasNaN}, Inf = {observation.HasInf}."));
            findings.Add(new Finding(Directory.Exists(Path.Combine(projectRoot, artifactRelativePath)) || string.IsNullOrWhiteSpace(artifactRelativePath) ? Severity.Pass : Severity.Warning, $"Artifact directory = {artifactRelativePath}."));
            findings.Add(new Finding(!string.IsNullOrWhiteSpace(artifactPrefix) ? Severity.Pass : Severity.Warning, $"Artifact file prefix = {artifactPrefix}."));
        }

        private static void PopulateFindings(
            List<Finding> findings,
            string runtimeFailure,
            string failureCategory,
            StudentBridgeRuntimeSnapshot bridgeSnapshot,
            bool stepCountAdvanced,
            bool applyCommandCalled,
            bool actionApplierCalled,
            int totalMeaningfulAcceptedCommands,
            Dictionary<UnitActionType, int> aggregateActionTypeHistogram,
            int totalWrongOwnerAfterFilter,
            int runtimeRejectedCount,
            AdapterArtifactSnapshot artifact)
        {
            if (!string.IsNullOrWhiteSpace(runtimeFailure))
            {
                findings.Add(new Finding(Severity.Fail, $"Runtime failure ({failureCategory}): {runtimeFailure}"));
            }
            else
            {
                findings.Add(new Finding(bridgeSnapshot.DecisionRequestsSucceeded > 0 ? Severity.Pass : Severity.Fail, $"Successful bridge requests = {bridgeSnapshot.DecisionRequestsSucceeded}."));
            }

            findings.Add(new Finding(stepCountAdvanced ? Severity.Pass : Severity.Fail, $"Step count advanced = {stepCountAdvanced}."));
            findings.Add(new Finding(actionApplierCalled ? Severity.Pass : Severity.Warning, $"ActionApplier reached = {actionApplierCalled}."));
            findings.Add(new Finding(applyCommandCalled ? Severity.Pass : Severity.Warning, $"MatchManager.ApplyCommand path reached = {applyCommandCalled}."));
            findings.Add(new Finding(totalMeaningfulAcceptedCommands > 0 ? Severity.Pass : Severity.Warning, $"Meaningful accepted commands = {totalMeaningfulAcceptedCommands}."));

            IReadOnlyDictionary<UnitActionType, int> histogramForFindings = SelectHistogramForReporting(aggregateActionTypeHistogram, artifact);
            int totalActions = HistogramTotal(histogramForFindings);
            int noOpCount = GetActionCount(histogramForFindings, UnitActionType.NoOp);
            float noOpShare = totalActions > 0 ? noOpCount / (float)totalActions : 0f;
            findings.Add(new Finding(noOpShare < 0.90f ? Severity.Pass : Severity.Warning, $"NoOp share = {FormatRatio(noOpShare)}."));

            findings.Add(new Finding(totalWrongOwnerAfterFilter == 0 ? Severity.Pass : Severity.Warning, $"Wrong-owner rejections after filter = {totalWrongOwnerAfterFilter}."));
            findings.Add(new Finding(runtimeRejectedCount == 0 ? Severity.Pass : Severity.Warning, $"Runtime rejected commands = {runtimeRejectedCount}."));

            if (artifact.IsAvailable)
            {
                bool logitsPresent = artifact.LogitsShapes.Count == 7;
                findings.Add(new Finding(logitsPresent ? Severity.Pass : Severity.Warning, $"Model output logits shapes captured = {logitsPresent}."));
                findings.Add(new Finding(artifact.BranchSizesMatchExpected ? Severity.Pass : Severity.Fail, $"Branch sizes = [{string.Join(", ", artifact.BranchSizes)}]."));
            }
        }

        private static Decision Decide(
            string runtimeFailure,
            StudentBridgeRuntimeSnapshot bridgeSnapshot,
            bool stepCountAdvanced,
            bool applyCommandCalled,
            bool actionApplierCalled,
            int totalMeaningfulAcceptedCommands)
        {
            if (!string.IsNullOrWhiteSpace(runtimeFailure))
            {
                return Decision.GoForUnityRemediation;
            }

            if (!bridgeSnapshot.ServerStarted || bridgeSnapshot.DecisionRequestsSucceeded <= 0)
            {
                return Decision.GoForUnityRemediation;
            }

            if (!stepCountAdvanced || !actionApplierCalled)
            {
                return Decision.GoForUnityRemediation;
            }

            if (!applyCommandCalled && totalMeaningfulAcceptedCommands <= 0)
            {
                return Decision.GoForUnityRemediation;
            }

            return Decision.GoForExecutionSemanticsAnalysis;
        }

        private static PlacementSummary CapturePlacementSummary(UnitRegistry registry)
        {
            var allUnits = registry.GetAllUnits();
            allUnits.Sort((left, right) => string.CompareOrdinal(DescribeUnit(left), DescribeUnit(right)));

            var placementLines = new List<string>(allUnits.Count);
            var occupancy = new Dictionary<string, int>(StringComparer.Ordinal);
            var duplicates = new List<string>();

            foreach (UnitRuntime unit in allUnits)
            {
                string line = DescribeUnit(unit);
                placementLines.Add(line);

                string key = $"({unit.GridPos.X},{unit.GridPos.Y})";
                if (!occupancy.TryGetValue(key, out int count))
                {
                    count = 0;
                }

                count++;
                occupancy[key] = count;
                if (count == 2)
                {
                    duplicates.Add(key);
                }
            }

            return new PlacementSummary(placementLines, duplicates);
        }

        private static ObservationSnapshot CaptureObservationSnapshot(RuntimeRefs runtime)
        {
            var builder = new ObservationBuilder(runtime.GridManager, runtime.Registry, runtime.ResourceManager);
            ObservationPackage package = builder.BuildObservationPackage(Owner.Player1, ObservationMode.UnityMvpTransfer);
            ObservationValidationResult validation = builder.ValidateObservation(package.SpatialObservation);

            float min = float.PositiveInfinity;
            float max = float.NegativeInfinity;
            bool hasNaN = false;
            bool hasInf = false;

            float[] spatial = package.SpatialObservation ?? Array.Empty<float>();
            for (int i = 0; i < spatial.Length; i++)
            {
                float value = spatial[i];
                if (float.IsNaN(value))
                {
                    hasNaN = true;
                    continue;
                }

                if (float.IsInfinity(value))
                {
                    hasInf = true;
                    continue;
                }

                if (value < min)
                {
                    min = value;
                }

                if (value > max)
                {
                    max = value;
                }
            }

            if (float.IsPositiveInfinity(min))
            {
                min = 0f;
                max = 0f;
            }

            int ownUnits = 0;
            int enemyUnits = 0;
            int resources = 0;
            foreach (UnitRuntime unit in runtime.Registry.GetAllUnits())
            {
                if (unit.Owner == Owner.Player1)
                {
                    ownUnits++;
                }
                else if (unit.Owner == Owner.Player2)
                {
                    enemyUnits++;
                }
                else if (unit.Owner == Owner.Neutral && unit.Type == UnitType.Resource)
                {
                    resources++;
                }
            }

            return new ObservationSnapshot(
                ObservationContract.GridH,
                ObservationContract.GridW,
                ObservationContract.ChannelsPerCell,
                spatial.Length,
                min,
                max,
                hasNaN,
                hasInf,
                ownUnits,
                enemyUnits,
                resources,
                package.GlobalFeatures != null ? package.GlobalFeatures.Length : 0,
                validation.IsValid,
                validation.ToString());
        }

        private static bool TryReadLatestAdapterArtifact(
            string projectRoot,
            string artifactRelativePath,
            string artifactPrefix,
            out AdapterArtifactSnapshot snapshot)
        {
            snapshot = default;
            if (string.IsNullOrWhiteSpace(projectRoot) || string.IsNullOrWhiteSpace(artifactRelativePath))
            {
                return false;
            }

            string artifactDirectory = Path.GetFullPath(Path.Combine(projectRoot, artifactRelativePath));
            if (!Directory.Exists(artifactDirectory))
            {
                return false;
            }

            string[] files = Directory.GetFiles(artifactDirectory, string.IsNullOrWhiteSpace(artifactPrefix) ? "*_adapter.json" : artifactPrefix + "*_adapter.json", SearchOption.TopDirectoryOnly);
            if (files.Length == 0)
            {
                return false;
            }

            Array.Sort(files, (left, right) => File.GetLastWriteTimeUtc(right).CompareTo(File.GetLastWriteTimeUtc(left)));
            string latest = files[0];
            string json = File.ReadAllText(latest, Encoding.UTF8);
            var artifact = JsonUtility.FromJson<AdapterArtifactJson>(json);
            if (artifact == null)
            {
                return false;
            }

            snapshot = new AdapterArtifactSnapshot(
                true,
                latest,
                artifact.status ?? string.Empty,
                artifact.action_contract_version ?? string.Empty,
                artifact.checkpoint_model_variant ?? string.Empty,
                artifact.checkpoint_epoch,
                artifact.observation_shape ?? Array.Empty<int>(),
                artifact.branch_sizes ?? Array.Empty<int>(),
                artifact.logits_keys ?? Array.Empty<string>(),
                artifact.action_flat_size,
                artifact.action_flat ?? Array.Empty<int>(),
                ExtractLogitsShapes(json));

            return true;
        }

        private static Dictionary<string, int[]> ExtractLogitsShapes(string json)
        {
            var result = new Dictionary<string, int[]>(StringComparer.Ordinal);
            Match container = Regex.Match(
                json,
                "\"model_output_logits_shapes\"\\s*:\\s*\\{(?<body>.*?)\\}\\s*,",
                RegexOptions.Singleline);

            if (!container.Success)
            {
                return result;
            }

            MatchCollection shapes = Regex.Matches(
                container.Groups["body"].Value,
                "\"(?<key>[^\"]+)\"\\s*:\\s*\\[(?<values>[^\\]]*)\\]");

            foreach (Match match in shapes)
            {
                string key = match.Groups["key"].Value;
                string[] rawValues = match.Groups["values"].Value.Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
                var parsed = new List<int>(rawValues.Length);
                for (int i = 0; i < rawValues.Length; i++)
                {
                    if (int.TryParse(rawValues[i].Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out int value))
                    {
                        parsed.Add(value);
                    }
                }

                result[key] = parsed.ToArray();
            }

            return result;
        }

        private static bool TryResolveRuntime(out RuntimeRefs runtime)
        {
            runtime = default;

            runtime.Controller = EpisodeController.Instance ?? UnityEngine.Object.FindFirstObjectByType<EpisodeController>();
            runtime.MatchManager = MatchManager.Instance ?? UnityEngine.Object.FindFirstObjectByType<MatchManager>();
            runtime.Bootstrap = MatchBootstrap.Instance ?? UnityEngine.Object.FindFirstObjectByType<MatchBootstrap>();
            runtime.GridManager = GridManager.Instance ?? UnityEngine.Object.FindFirstObjectByType<GridManager>();
            runtime.Registry = UnitRegistry.Instance ?? UnityEngine.Object.FindFirstObjectByType<UnitRegistry>();
            runtime.ResourceManager = ResourceManager.Instance ?? UnityEngine.Object.FindFirstObjectByType<ResourceManager>();
            runtime.Runner = UnityEngine.Object.FindFirstObjectByType<Week6VisualInspectionRunner>();
            runtime.Adapter = UnityEngine.Object.FindFirstObjectByType<Week6StudentPolicyAdapter>();

            return runtime.Controller != null
                && runtime.MatchManager != null
                && runtime.Bootstrap != null
                && runtime.GridManager != null
                && runtime.Registry != null
                && runtime.ResourceManager != null
                && runtime.Runner != null
                && runtime.Adapter != null;
        }

        private static int CountObjects<T>() where T : UnityEngine.Object
        {
            return UnityEngine.Object.FindObjectsByType<T>(FindObjectsSortMode.None).Length;
        }

        private static string BuildMarkdownReport(ReportModel model)
        {
            IReadOnlyDictionary<UnitActionType, int> displayHistogram = SelectHistogramForReporting(model.ActionHistogram, model.Artifact);
            int totalActions = HistogramTotal(displayHistogram);
            int noOpCount = GetActionCount(displayHistogram, UnitActionType.NoOp);
            int moveCount = GetActionCount(displayHistogram, UnitActionType.Move);
            int harvestCount = GetActionCount(displayHistogram, UnitActionType.Harvest);
            int returnCount = GetActionCount(displayHistogram, UnitActionType.Return);
            int produceCount = GetActionCount(displayHistogram, UnitActionType.Produce);
            int attackCount = GetActionCount(displayHistogram, UnitActionType.Attack);

            float noOpShare = totalActions > 0 ? noOpCount / (float)totalActions : 0f;
            float nonNoOpShare = totalActions > 0 ? (totalActions - noOpCount) / (float)totalActions : 0f;
            float invalidShare = model.TotalDecodedActions > 0 ? model.TotalRejectedFromReports / (float)model.TotalDecodedActions : 0f;
            float ignoredShare = model.TotalDecodedActions > 0 ? model.IgnoredCommandCount / (float)model.TotalDecodedActions : 0f;

            var sb = new StringBuilder(16384);
            sb.AppendLine("# LEGACY032 UNITY V2 Stage 10 Unity Scene Dry-Run Report");
            sb.AppendLine();
            sb.AppendLine("Generated at: " + DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture));
            sb.AppendLine();
            sb.AppendLine("## 1. Scope");
            sb.AppendLine("- Controlled Unity scene dry-run only.");
            sb.AppendLine("- No PPO fine-tune.");
            sb.AppendLine("- No teacher training.");
            sb.AppendLine("- No dataset modification.");
            sb.AppendLine("- No checkpoint modification.");
            sb.AppendLine("- No semantic parity claim.");
            sb.AppendLine("- No behavior quality proof.");
            sb.AppendLine();
            sb.AppendLine("## 2. Scene and checkpoint");
            sb.AppendLine("- Scene path: " + model.ScenePath);
            sb.AppendLine("- Scene name: " + model.SceneName);
            sb.AppendLine("- Scenario preset: " + model.ScenarioPreset);
            sb.AppendLine($"- Map size: {model.MapWidth}x{model.MapHeight}");
            sb.AppendLine("- Active checkpoint path: " + model.CheckpointRelativePath);
            sb.AppendLine("- Checkpoint exists: " + model.CheckpointExists);
            sb.AppendLine("- Active runner/component: " + model.ActiveRunner);
            sb.AppendLine("- Manual trigger mode: " + model.ManualTriggerMode);
            sb.AppendLine("- EpisodeController auto-start: " + model.ControllerAutoStart);
            sb.AppendLine("- Visual runner auto-start: " + model.RunnerAutoStart);
            sb.AppendLine("- Device/backend: " + model.Device);
            sb.AppendLine("- Initial placement summary:");
            AppendIndentedLines(sb, model.InitialPlacementLines);
            sb.AppendLine();
            sb.AppendLine("## 3. Preflight results");
            sb.AppendLine("- Scene readiness:");
            AppendIndentedFindings(sb, model.StartupFindings);
            sb.AppendLine("- Runtime object counts:");
            sb.AppendLine($"  - Week6VisualInspectionRunner: {model.RuntimeRunnerCount}");
            sb.AppendLine($"  - Week6StudentPolicyAdapter: {model.RuntimeAdapterCount}");
            sb.AppendLine($"  - EpisodeController: {model.RuntimeControllerCount}");
            sb.AppendLine($"  - HeuristicPolicyAdapter: {model.RuntimeHeuristicAdapterCount}");
            sb.AppendLine($"- Week6 control modes: enableStudentMatchControl={model.EnableStudentControl}, Player1={model.Player1Mode}, Player2={model.Player2Mode}");
            sb.AppendLine($"- Duplicate occupancy count: {model.DuplicateOccupancyLines.Count}");
            if (model.DuplicateOccupancyLines.Count > 0)
            {
                AppendIndentedLines(sb, model.DuplicateOccupancyLines);
            }
            sb.AppendLine();
            sb.AppendLine("## 4. Runtime load result");
            sb.AppendLine("- Model loaded: " + (model.BridgeSnapshot.ServerStarted ? "yes" : "no"));
            sb.AppendLine("- Decision requests sent/succeeded/failed: " + model.BridgeSnapshot.DecisionRequestsSent + "/" + model.BridgeSnapshot.DecisionRequestsSucceeded + "/" + model.BridgeSnapshot.DecisionRequestsFailed);
            sb.AppendLine("- Bridge shutdown clean: " + model.BridgeSnapshot.ServerShutdownClean);
            sb.AppendLine("- Last bridge/runtime error: " + (string.IsNullOrWhiteSpace(model.BridgeSnapshot.LastError) ? "none" : model.BridgeSnapshot.LastError));
            sb.AppendLine("- Checkpoint metadata:");
            if (model.Artifact.IsAvailable)
            {
                sb.AppendLine("  - Checkpoint model variant: " + model.Artifact.CheckpointModelVariant);
                sb.AppendLine("  - Checkpoint epoch: " + model.Artifact.CheckpointEpoch);
                sb.AppendLine("  - Action contract version: " + model.Artifact.ActionContractVersion);
            }
            else
            {
                sb.AppendLine("  - Adapter artifact unavailable.");
            }
            sb.AppendLine();
            sb.AppendLine("## 5. Observation/inference result");
            sb.AppendLine($"- Observation shape: [{model.Observation.ShapeLabel}]");
            sb.AppendLine($"- Observation element count: {model.Observation.ElementCount}");
            sb.AppendLine($"- Observation min/max: {model.Observation.MinValue.ToString("F6", CultureInfo.InvariantCulture)} / {model.Observation.MaxValue.ToString("F6", CultureInfo.InvariantCulture)}");
            sb.AppendLine($"- Observation NaN/Inf: {model.Observation.HasNaN} / {model.Observation.HasInf}");
            sb.AppendLine($"- Observation validation: {model.Observation.IsValid}");
            sb.AppendLine($"- Controlled player id: {Owner.Player1}");
            sb.AppendLine($"- Own units / enemy units / resources: {model.Observation.OwnUnits} / {model.Observation.EnemyUnits} / {model.Observation.Resources}");
            sb.AppendLine($"- Global vector length in package: {model.Observation.GlobalFeaturesLength}");
            sb.AppendLine("- Strict BC path fed global vector into model: no (adapter writes SpatialObservation only).");
            if (model.Artifact.IsAvailable)
            {
                sb.AppendLine($"- Model input shape: [{string.Join(", ", model.Artifact.ObservationShape)}]");
                sb.AppendLine($"- Predicted action tensor shape: [{ActionContract.TotalCells}, {model.Artifact.BranchSizes.Length}]");
                sb.AppendLine($"- Flattened action payload size: {model.Artifact.ActionFlatSize}");
                sb.AppendLine($"- Branch sizes: [{string.Join(", ", model.Artifact.BranchSizes)}]");
                sb.AppendLine("- Logits shapes:");
                foreach (KeyValuePair<string, int[]> kvp in model.Artifact.LogitsShapes)
                {
                    sb.AppendLine("  - " + kvp.Key + ": [" + string.Join(", ", kvp.Value) + "]");
                }
                sb.AppendLine("- Branch bounds (first captured adapter artifact):");
                AppendIndentedLines(sb, ComputeBranchBounds(model.Artifact.ActionFlat));
            }
            else
            {
                sb.AppendLine("- Adapter artifact: unavailable.");
            }
            sb.AppendLine();
            sb.AppendLine("## 6. Decoder/applier result");
            sb.AppendLine("- Decoded command sample:");
            AppendIndentedLines(sb, model.DecodedCommandSamples);
            sb.AppendLine("- First non-NoOp decoded commands:");
            AppendIndentedLines(sb, model.NonNoopDecodedSamples);
            sb.AppendLine("- Accepted command samples:");
            AppendIndentedLines(sb, model.AcceptedCommandSamples);
            sb.AppendLine("- Rejected command samples:");
            AppendIndentedLines(sb, model.RejectedCommandSamples);
            sb.AppendLine($"- Accepted command count: {model.AcceptedCommandCount}");
            sb.AppendLine($"- Rejected command count: {model.RejectedCommandCount}");
            sb.AppendLine($"- Ignored command count: {model.IgnoredCommandCount}");
            sb.AppendLine($"- Invalid share: {FormatRatio(invalidShare)}");
            sb.AppendLine($"- Ignored share: {FormatRatio(ignoredShare)}");
            sb.AppendLine("- Rejection reason histogram:");
            AppendIndentedLines(sb, FormatStringHistogram(model.RejectionReasonHistogram));
            sb.AppendLine("- Runtime rejection reason histogram:");
            AppendIndentedLines(sb, FormatStringHistogram(model.RuntimeRejectedReasonHistogram));
            sb.AppendLine($"- ActionApplier called: {model.ActionApplierCalled}");
            sb.AppendLine($"- MatchManager.ApplyCommand called: {model.ApplyCommandCalled}");
            sb.AppendLine();
            sb.AppendLine("## 7. Episode/bounded run summary");
            sb.AppendLine($"- Episodes run: {model.EpisodesRun}");
            sb.AppendLine($"- Max steps configured: {model.MaxStepsConfigured}");
            sb.AppendLine($"- Steps actually run: {model.StepsActuallyRun}");
            sb.AppendLine($"- MatchManager.AdvanceStep called: {model.AdvanceStepCalled}");
            sb.AppendLine($"- Step count advanced: {model.StepCountAdvanced}");
            sb.AppendLine($"- Episode reached terminal: {model.ReachedTerminal}");
            if (model.ReachedTerminal)
            {
                sb.AppendLine($"- Terminal reason: {model.TerminalReason}");
                sb.AppendLine($"- Winner: {model.Winner}");
            }
            else
            {
                sb.AppendLine("- Stop reason: " + model.StopReason);
            }
            sb.AppendLine();
            sb.AppendLine("## 8. Action statistics");
            sb.AppendLine("- Aggregate action_type histogram: " + FormatActionHistogram(displayHistogram));
            sb.AppendLine("- Aggregate pre-mask action_type histogram: " + FormatActionHistogram(model.PreMaskHistogram));
            sb.AppendLine("- First steps action histograms:");
            AppendIndentedLines(sb, model.StepHistogramSamples);
            sb.AppendLine($"- NoOp share: {FormatRatio(noOpShare)}");
            sb.AppendLine($"- Non-NoOp share: {FormatRatio(nonNoOpShare)}");
            sb.AppendLine($"- Move / Harvest / Return counts: {moveCount} / {harvestCount} / {returnCount}");
            sb.AppendLine($"- Produce count/share: {produceCount} / {FormatRatio(totalActions > 0 ? produceCount / (float)totalActions : 0f)}");
            sb.AppendLine($"- Attack count/share: {attackCount} / {FormatRatio(totalActions > 0 ? attackCount / (float)totalActions : 0f)}");
            sb.AppendLine($"- Commands built after filter: {model.TotalCommandsBuiltAfterFilter}");
            sb.AppendLine($"- Commands submitted after filter: {model.TotalCommandsSubmittedAfterFilter}");
            sb.AppendLine($"- Candidate cells / eligible own actor cells: {model.TotalCandidateCells} / {model.TotalEligibleOwnActorCells}");
            sb.AppendLine($"- Wrong-owner rejections after filter: {model.TotalWrongOwnerAfterFilter}");
            sb.AppendLine($"- Masked-out action-type choices / fallback-to-NoOp: {model.TotalMaskedOutChoices} / {model.TotalFallbackToNoop}");
            sb.AppendLine();
            sb.AppendLine("## 9. Key findings");
            AppendIndentedFindings(sb, model.StartupFindings);
            sb.AppendLine();
            sb.AppendLine("## 10. Interpretation limits");
            sb.AppendLine("- This dry-run does not prove behavior quality.");
            sb.AppendLine("- This dry-run does not prove Gym-microRTS to Unity semantic parity.");
            sb.AppendLine("- This dry-run does not prove final transfer success.");
            sb.AppendLine("- The checkpoint is BC-only.");
            sb.AppendLine("- NoOp dominance may still reflect dataset bias or runtime mismatch.");
            sb.AppendLine("- Unity runtime semantic drift remains possible even if the technical path executes.");
            sb.AppendLine();
            sb.AppendLine("## 11. Decision");
            sb.AppendLine("- " + DecisionLabel(model.Decision));
            if (!string.IsNullOrWhiteSpace(model.FailureCategory))
            {
                sb.AppendLine("- Failure classification: " + model.FailureCategory);
            }
            if (!string.IsNullOrWhiteSpace(model.RuntimeFailure))
            {
                sb.AppendLine("- Runtime failure detail: " + model.RuntimeFailure);
            }

            return sb.ToString();
        }

        private static string DescribeUnit(UnitRuntime unit)
        {
            return $"- {unit.Owner} {unit.Type} @ ({unit.GridPos.X},{unit.GridPos.Y})";
        }

        private static string FormatMatchCommand(MatchCommand command)
        {
            string baseText = $"owner={command.Owner} actor=({command.UnitPosition.X},{command.UnitPosition.Y}) type={command.ActionType} dir={command.Direction}";
            if (command.ActionType == UnitActionType.Produce)
            {
                baseText += $" produce={command.ProduceUnitType}";
            }

            if (command.HasAttackTarget)
            {
                baseText += $" target=({command.AttackTarget.X},{command.AttackTarget.Y})";
            }

            return baseText;
        }

        private static string NormalizeReason(string reason)
        {
            if (string.IsNullOrWhiteSpace(reason))
            {
                return "other";
            }

            string lower = reason.ToLowerInvariant();
            if (lower.Contains("belongs to") || lower.Contains("another owner")) return "wrong_owner";
            if (lower.Contains("neutral")) return "actor_missing";
            if (lower.Contains("occupied")) return "occupied_target";
            if (lower.Contains("queue") || lower.Contains("already has a command")) return "production_queue_busy";
            if (lower.Contains("not enough resources") || lower.Contains("insufficient resources")) return "insufficient_resources";
            if (lower.Contains("cannot produce") || lower.Contains("does not support action")) return "unsupported_action";
            if (lower.Contains("not carrying") || lower.Contains("carrying 0")) return "no_resource";
            if (lower.Contains("cannot attack self") || lower.Contains("no enemy") || lower.Contains("no attack")) return "invalid_attack_target";
            if (lower.Contains("out of bounds") || lower.Contains("out of range")) return "target_out_of_range";
            if (lower.Contains("direction")) return "invalid_direction";
            return "other";
        }

        private static string ClassifyFailure(string message)
        {
            string lower = (message ?? string.Empty).ToLowerInvariant();
            if (lower.Contains("checkpoint") && lower.Contains("not found")) return "checkpoint_load_failure";
            if (lower.Contains("failed to load checkpoint")) return "checkpoint_load_failure";
            if (lower.Contains("bridge") || lower.Contains("timeout") || lower.Contains("stdout") || lower.Contains("stderr")) return "python_unity_bridge_failure";
            if (lower.Contains("observation shape mismatch")) return "observation_shape_mismatch";
            if (lower.Contains("observation dtype mismatch") || lower.Contains("element count")) return "model_input_shape_mismatch";
            if (lower.Contains("branch_sizes mismatch") || lower.Contains("branch_order mismatch") || lower.Contains("action flat size mismatch")) return "logits_action_branch_mismatch";
            if (lower.Contains("v1 action contract artifact") || lower.Contains("decode") || lower.Contains("decoder")) return "decoder_contract_mismatch";
            if (lower.Contains("wrong owner") || lower.Contains("occupied") || lower.Contains("insufficient resources") || lower.Contains("attack")) return "action_applier_runtime_rejection";
            return "other";
        }

        private static List<string> ComputeBranchBounds(int[] actionFlat)
        {
            var lines = new List<string>();
            if (actionFlat == null || actionFlat.Length != ActionContract.TotalActionFlatSize)
            {
                lines.Add("- unavailable");
                return lines;
            }

            int[] min = { int.MaxValue, int.MaxValue, int.MaxValue, int.MaxValue, int.MaxValue, int.MaxValue, int.MaxValue };
            int[] max = { int.MinValue, int.MinValue, int.MinValue, int.MinValue, int.MinValue, int.MinValue, int.MinValue };
            int[] offsets = { 0, 6, 10, 14, 18, 22, 29 };
            string[] names = { "action_type", "move_dir", "harvest_dir", "return_dir", "produce_dir", "produce_unit_type", "attack_target_local" };
            int stride = 78;

            for (int cell = 0; cell < ActionContract.TotalCells; cell++)
            {
                int baseIndex = cell * stride;
                for (int branch = 0; branch < offsets.Length; branch++)
                {
                    int chosen = actionFlat[baseIndex + offsets[branch]];

                    if (chosen < min[branch]) min[branch] = chosen;
                    if (chosen > max[branch]) max[branch] = chosen;
                }
            }

            for (int i = 0; i < names.Length; i++)
            {
                lines.Add($"- {names[i]}: min={min[i]}, max={max[i]}");
            }

            return lines;
        }

        private static void AppendIndentedLines(StringBuilder sb, IReadOnlyList<string> lines)
        {
            if (lines == null || lines.Count == 0)
            {
                sb.AppendLine("  - none");
                return;
            }

            for (int i = 0; i < lines.Count; i++)
            {
                sb.AppendLine("  " + lines[i]);
            }
        }

        private static void AppendIndentedFindings(StringBuilder sb, IReadOnlyList<Finding> findings)
        {
            if (findings == null || findings.Count == 0)
            {
                sb.AppendLine("  - none");
                return;
            }

            for (int i = 0; i < findings.Count; i++)
            {
                sb.AppendLine($"  - {SeverityLabel(findings[i].Severity)}: {findings[i].Message}");
            }
        }

        private static string FormatActionHistogram(IReadOnlyDictionary<UnitActionType, int> histogram)
        {
            var parts = new List<string>();
            foreach (UnitActionType actionType in new[]
                     {
                         UnitActionType.NoOp,
                         UnitActionType.Move,
                         UnitActionType.Harvest,
                         UnitActionType.Return,
                         UnitActionType.Produce,
                         UnitActionType.Attack,
                     })
            {
                parts.Add(actionType + "=" + GetActionCount(histogram, actionType));
            }

            return string.Join(", ", parts);
        }

        private static IReadOnlyList<string> FormatStringHistogram(Dictionary<string, int> histogram)
        {
            var lines = new List<string>();
            if (histogram == null || histogram.Count == 0)
            {
                return lines;
            }

            var entries = new List<KeyValuePair<string, int>>(histogram);
            entries.Sort((left, right) => right.Value.CompareTo(left.Value));
            for (int i = 0; i < entries.Count; i++)
            {
                lines.Add($"- {entries[i].Key}: {entries[i].Value}");
            }

            return lines;
        }

        private static string FormatRatio(float value)
        {
            return value.ToString("P2", CultureInfo.InvariantCulture);
        }

        private static Dictionary<UnitActionType, int> CreateActionTypeHistogram()
        {
            return new Dictionary<UnitActionType, int>
            {
                [UnitActionType.NoOp] = 0,
                [UnitActionType.Move] = 0,
                [UnitActionType.Harvest] = 0,
                [UnitActionType.Return] = 0,
                [UnitActionType.Produce] = 0,
                [UnitActionType.Attack] = 0,
            };
        }

        private static void MergeActionHistogram(Dictionary<UnitActionType, int> target, IReadOnlyDictionary<UnitActionType, int> source)
        {
            if (source == null)
            {
                return;
            }

            foreach (KeyValuePair<UnitActionType, int> kvp in source)
            {
                IncrementAction(target, kvp.Key, kvp.Value);
            }
        }

        private static void IncrementAction(Dictionary<UnitActionType, int> histogram, UnitActionType key, int amount)
        {
            if (!histogram.TryGetValue(key, out int current))
            {
                current = 0;
            }

            histogram[key] = current + amount;
        }

        private static void IncrementString(Dictionary<string, int> histogram, string key, int amount)
        {
            string normalized = string.IsNullOrWhiteSpace(key) ? "other" : key;
            if (!histogram.TryGetValue(normalized, out int current))
            {
                current = 0;
            }

            histogram[normalized] = current + amount;
        }

        private static int HistogramTotal(IReadOnlyDictionary<UnitActionType, int> histogram)
        {
            int total = 0;
            foreach (KeyValuePair<UnitActionType, int> kvp in histogram)
            {
                total += kvp.Value;
            }

            return total;
        }

        private static int GetActionCount(IReadOnlyDictionary<UnitActionType, int> histogram, UnitActionType actionType)
        {
            return histogram != null && histogram.TryGetValue(actionType, out int value) ? value : 0;
        }

        private static T GetPrivateField<T>(object source, string fieldName, T fallback)
        {
            if (source == null)
            {
                return fallback;
            }

            FieldInfo field = source.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            if (field == null)
            {
                return fallback;
            }

            object value = field.GetValue(source);
            return value is T typed ? typed : fallback;
        }

        private static int GetPrivateEnumInt(object source, string fieldName, int fallback)
        {
            if (source == null)
            {
                return fallback;
            }

            FieldInfo field = source.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            if (field == null)
            {
                return fallback;
            }

            object value = field.GetValue(source);
            if (value == null)
            {
                return fallback;
            }

            try
            {
                return Convert.ToInt32(value, CultureInfo.InvariantCulture);
            }
            catch
            {
                return fallback;
            }
        }

        private static IReadOnlyDictionary<UnitActionType, int> SelectHistogramForReporting(
            IReadOnlyDictionary<UnitActionType, int> aggregateHistogram,
            AdapterArtifactSnapshot artifact)
        {
            if (HistogramTotal(aggregateHistogram) > 0 || !artifact.IsAvailable)
            {
                return aggregateHistogram;
            }

            return ComputeActionTypeHistogramFromArtifact(artifact.ActionFlat);
        }

        private static Dictionary<UnitActionType, int> ComputeActionTypeHistogramFromArtifact(int[] actionFlat)
        {
            Dictionary<UnitActionType, int> histogram = CreateActionTypeHistogram();
            if (actionFlat == null || actionFlat.Length != ActionContract.TotalActionFlatSize)
            {
                return histogram;
            }

            int stride = 78;
            for (int cell = 0; cell < ActionContract.TotalCells; cell++)
            {
                int rawActionType = actionFlat[cell * stride];
                if (TryMapActionType(rawActionType, out UnitActionType actionType))
                {
                    IncrementAction(histogram, actionType, 1);
                }
            }

            return histogram;
        }

        private static bool TryMapActionType(int rawActionType, out UnitActionType actionType)
        {
            switch (rawActionType)
            {
                case 0:
                    actionType = UnitActionType.NoOp;
                    return true;
                case 1:
                    actionType = UnitActionType.Move;
                    return true;
                case 2:
                    actionType = UnitActionType.Harvest;
                    return true;
                case 3:
                    actionType = UnitActionType.Return;
                    return true;
                case 4:
                    actionType = UnitActionType.Produce;
                    return true;
                case 5:
                    actionType = UnitActionType.Attack;
                    return true;
                default:
                    actionType = UnitActionType.NoOp;
                    return false;
            }
        }

        private static void WriteFailureReportFromEditor(string failureCategory, string error)
        {
            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? string.Empty;
            string reportPath = Path.Combine(projectRoot, ReportRelativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(reportPath) ?? projectRoot);

            var findings = new List<Finding>
            {
                new Finding(Severity.Fail, error),
            };

            string markdown = BuildMarkdownReport(new ReportModel
            {
                Decision = Decision.GoForUnityRemediation,
                FailureCategory = failureCategory,
                RuntimeFailure = error,
                SceneName = SceneManager.GetActiveScene().name,
                ScenePath = TargetScenePath,
                ScenarioPreset = -1,
                MapWidth = 24,
                MapHeight = 24,
                InitialPlacementLines = new List<string>(),
                DuplicateOccupancyLines = new List<string>(),
                CheckpointRelativePath = ExpectedCheckpointRelativePath,
                CheckpointExists = File.Exists(Path.Combine(projectRoot, ExpectedCheckpointRelativePath)),
                ActiveRunner = nameof(Week6VisualInspectionRunner),
                ManualTriggerMode = true,
                ControllerAutoStart = false,
                RunnerAutoStart = false,
                EnableStudentControl = false,
                Player1Mode = Week6PlayerControlMode.Idle,
                Player2Mode = Week6PlayerControlMode.Idle,
                Device = "cpu",
                StartupFindings = findings,
                Observation = ObservationSnapshot.Empty,
                Artifact = default,
                BridgeSnapshot = default,
                DecodedCommandSamples = new List<string>(),
                NonNoopDecodedSamples = new List<string>(),
                AcceptedCommandSamples = new List<string>(),
                RejectedCommandSamples = new List<string>(),
                AcceptedCommandCount = 0,
                RejectedCommandCount = 0,
                IgnoredCommandCount = 0,
                RejectionReasonHistogram = new Dictionary<string, int>(StringComparer.Ordinal),
                RuntimeRejectedReasonHistogram = new Dictionary<string, int>(StringComparer.Ordinal),
                ApplyCommandCalled = false,
                ActionApplierCalled = false,
                AdvanceStepCalled = false,
                StepCountAdvanced = false,
                EpisodesRun = 0,
                MaxStepsConfigured = BoundedMaxSteps,
                StepsActuallyRun = 0,
                ReachedTerminal = false,
                TerminalReason = "none",
                Winner = Owner.Neutral,
                StopReason = "preflight_failure",
                ActionHistogram = CreateActionTypeHistogram(),
                PreMaskHistogram = CreateActionTypeHistogram(),
                StepHistogramSamples = new List<string>(),
                TotalAcceptedFromReports = 0,
                TotalRejectedFromReports = 0,
                TotalDecodedActions = 0,
                TotalWrongOwnerAfterFilter = 0,
                TotalCommandsBuiltAfterFilter = 0,
                TotalCommandsSubmittedAfterFilter = 0,
                TotalEligibleOwnActorCells = 0,
                TotalCandidateCells = 0,
                TotalFallbackToNoop = 0,
                TotalMaskedOutChoices = 0,
                RuntimeRunnerCount = 0,
                RuntimeAdapterCount = 0,
                RuntimeControllerCount = 0,
                RuntimeHeuristicAdapterCount = 0,
            });

            File.WriteAllText(reportPath, markdown, Encoding.UTF8);
            Debug.Log($"[Stage10DryRun] Failure report written: {reportPath}");
        }

        private struct RuntimeRefs
        {
            public EpisodeController Controller;
            public MatchManager MatchManager;
            public MatchBootstrap Bootstrap;
            public GridManager GridManager;
            public UnitRegistry Registry;
            public ResourceManager ResourceManager;
            public Week6VisualInspectionRunner Runner;
            public Week6StudentPolicyAdapter Adapter;
        }

        private readonly struct PlacementSummary
        {
            public PlacementSummary(List<string> placementLines, List<string> duplicateOccupancyLines)
            {
                PlacementLines = placementLines ?? new List<string>();
                DuplicateOccupancyLines = duplicateOccupancyLines ?? new List<string>();
            }

            public List<string> PlacementLines { get; }
            public List<string> DuplicateOccupancyLines { get; }
        }

        private readonly struct ObservationSnapshot
        {
            public static ObservationSnapshot Empty => new ObservationSnapshot(24, 24, 27, 0, 0f, 0f, false, false, 0, 0, 0, 0, false, "unavailable");

            public ObservationSnapshot(
                int height,
                int width,
                int channels,
                int elementCount,
                float minValue,
                float maxValue,
                bool hasNaN,
                bool hasInf,
                int ownUnits,
                int enemyUnits,
                int resources,
                int globalFeaturesLength,
                bool isValid,
                string validationSummary)
            {
                Height = height;
                Width = width;
                Channels = channels;
                ElementCount = elementCount;
                MinValue = minValue;
                MaxValue = maxValue;
                HasNaN = hasNaN;
                HasInf = hasInf;
                OwnUnits = ownUnits;
                EnemyUnits = enemyUnits;
                Resources = resources;
                GlobalFeaturesLength = globalFeaturesLength;
                IsValid = isValid;
                ValidationSummary = validationSummary ?? string.Empty;
            }

            public int Height { get; }
            public int Width { get; }
            public int Channels { get; }
            public int ElementCount { get; }
            public float MinValue { get; }
            public float MaxValue { get; }
            public bool HasNaN { get; }
            public bool HasInf { get; }
            public int OwnUnits { get; }
            public int EnemyUnits { get; }
            public int Resources { get; }
            public int GlobalFeaturesLength { get; }
            public bool IsValid { get; }
            public string ValidationSummary { get; }
            public string ShapeLabel => $"{Height},{Width},{Channels}";
            public bool ShapeMatchesContract => Height == 24 && Width == 24 && Channels == 27;
        }

        private readonly struct AdapterArtifactSnapshot
        {
            public AdapterArtifactSnapshot(
                bool isAvailable,
                string path,
                string status,
                string actionContractVersion,
                string checkpointModelVariant,
                int checkpointEpoch,
                int[] observationShape,
                int[] branchSizes,
                string[] logitsKeys,
                int actionFlatSize,
                int[] actionFlat,
                Dictionary<string, int[]> logitsShapes)
            {
                IsAvailable = isAvailable;
                Path = path ?? string.Empty;
                Status = status ?? string.Empty;
                ActionContractVersion = actionContractVersion ?? string.Empty;
                CheckpointModelVariant = checkpointModelVariant ?? string.Empty;
                CheckpointEpoch = checkpointEpoch;
                ObservationShape = observationShape ?? Array.Empty<int>();
                BranchSizes = branchSizes ?? Array.Empty<int>();
                LogitsKeys = logitsKeys ?? Array.Empty<string>();
                ActionFlatSize = actionFlatSize;
                ActionFlat = actionFlat ?? Array.Empty<int>();
                LogitsShapes = logitsShapes ?? new Dictionary<string, int[]>(StringComparer.Ordinal);
            }

            public bool IsAvailable { get; }
            public string Path { get; }
            public string Status { get; }
            public string ActionContractVersion { get; }
            public string CheckpointModelVariant { get; }
            public int CheckpointEpoch { get; }
            public int[] ObservationShape { get; }
            public int[] BranchSizes { get; }
            public string[] LogitsKeys { get; }
            public int ActionFlatSize { get; }
            public int[] ActionFlat { get; }
            public Dictionary<string, int[]> LogitsShapes { get; }
            public bool BranchSizesMatchExpected => BranchSizes.Length == 7
                                                    && BranchSizes[0] == 6
                                                    && BranchSizes[1] == 4
                                                    && BranchSizes[2] == 4
                                                    && BranchSizes[3] == 4
                                                    && BranchSizes[4] == 4
                                                    && BranchSizes[5] == 7
                                                    && BranchSizes[6] == 49;
        }

        [Serializable]
        private sealed class AdapterArtifactJson
        {
            public string status;
            public string action_contract_version;
            public string checkpoint_model_variant;
            public int checkpoint_epoch;
            public int[] observation_shape;
            public string[] branch_order;
            public int[] branch_sizes;
            public string[] logits_keys;
            public int action_flat_size;
            public int[] action_flat;
        }

        private readonly struct Finding
        {
            public Finding(Severity severity, string message)
            {
                Severity = severity;
                Message = message ?? string.Empty;
            }

            public Severity Severity { get; }
            public string Message { get; }
        }

        private enum Severity
        {
            Pass,
            Warning,
            Fail,
        }

        private enum Decision
        {
            GoForExecutionSemanticsAnalysis,
            GoForUnityRemediation,
            NoGo,
        }

        private sealed class ReportModel
        {
            public Decision Decision { get; set; }
            public string FailureCategory { get; set; }
            public string RuntimeFailure { get; set; }
            public string SceneName { get; set; }
            public string ScenePath { get; set; }
            public int ScenarioPreset { get; set; }
            public int MapWidth { get; set; }
            public int MapHeight { get; set; }
            public List<string> InitialPlacementLines { get; set; }
            public List<string> DuplicateOccupancyLines { get; set; }
            public string CheckpointRelativePath { get; set; }
            public bool CheckpointExists { get; set; }
            public string ActiveRunner { get; set; }
            public bool ManualTriggerMode { get; set; }
            public bool ControllerAutoStart { get; set; }
            public bool RunnerAutoStart { get; set; }
            public bool EnableStudentControl { get; set; }
            public Week6PlayerControlMode Player1Mode { get; set; }
            public Week6PlayerControlMode Player2Mode { get; set; }
            public string Device { get; set; }
            public List<Finding> StartupFindings { get; set; }
            public ObservationSnapshot Observation { get; set; }
            public AdapterArtifactSnapshot Artifact { get; set; }
            public StudentBridgeRuntimeSnapshot BridgeSnapshot { get; set; }
            public List<string> DecodedCommandSamples { get; set; }
            public List<string> NonNoopDecodedSamples { get; set; }
            public List<string> AcceptedCommandSamples { get; set; }
            public List<string> RejectedCommandSamples { get; set; }
            public int AcceptedCommandCount { get; set; }
            public int RejectedCommandCount { get; set; }
            public int IgnoredCommandCount { get; set; }
            public Dictionary<string, int> RejectionReasonHistogram { get; set; }
            public Dictionary<string, int> RuntimeRejectedReasonHistogram { get; set; }
            public bool ApplyCommandCalled { get; set; }
            public bool ActionApplierCalled { get; set; }
            public bool AdvanceStepCalled { get; set; }
            public bool StepCountAdvanced { get; set; }
            public int EpisodesRun { get; set; }
            public int MaxStepsConfigured { get; set; }
            public int StepsActuallyRun { get; set; }
            public bool ReachedTerminal { get; set; }
            public string TerminalReason { get; set; }
            public Owner Winner { get; set; }
            public string StopReason { get; set; }
            public Dictionary<UnitActionType, int> ActionHistogram { get; set; }
            public Dictionary<UnitActionType, int> PreMaskHistogram { get; set; }
            public List<string> StepHistogramSamples { get; set; }
            public int TotalAcceptedFromReports { get; set; }
            public int TotalRejectedFromReports { get; set; }
            public int TotalDecodedActions { get; set; }
            public int TotalWrongOwnerAfterFilter { get; set; }
            public int TotalCommandsBuiltAfterFilter { get; set; }
            public int TotalCommandsSubmittedAfterFilter { get; set; }
            public int TotalEligibleOwnActorCells { get; set; }
            public int TotalCandidateCells { get; set; }
            public int TotalFallbackToNoop { get; set; }
            public int TotalMaskedOutChoices { get; set; }
            public int RuntimeRunnerCount { get; set; }
            public int RuntimeAdapterCount { get; set; }
            public int RuntimeControllerCount { get; set; }
            public int RuntimeHeuristicAdapterCount { get; set; }
        }

        private static string SeverityLabel(Severity severity)
        {
            switch (severity)
            {
                case Severity.Pass:
                    return "PASS";
                case Severity.Warning:
                    return "WARNING";
                default:
                    return "FAIL";
            }
        }

        private static string DecisionLabel(Decision decision)
        {
            switch (decision)
            {
                case Decision.GoForExecutionSemanticsAnalysis:
                    return "GO_FOR_EXECUTION_SEMANTICS_ANALYSIS";
                case Decision.GoForUnityRemediation:
                    return "GO_FOR_UNITY_REMEDIATION";
                default:
                    return "NO_GO";
            }
        }
    }

}
#endif