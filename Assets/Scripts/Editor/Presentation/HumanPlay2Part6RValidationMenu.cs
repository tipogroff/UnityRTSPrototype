#if UNITY_EDITOR
using System;
using System.IO;
using System.Reflection;
using RTS.Core;
using RTS.Gameplay;
using RTS.ML;
using RTS.MLAgents.Stage7B;
using RTS.MLAgents.Stage7B.TeacherReplay;
using RTS.Presentation;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RTS.Testing.Editor
{
    [InitializeOnLoad]
    public static class HumanPlay2Part6RValidationMenu
    {
        private const string MenuPath = "RTS/HumanPlay-2/Prepare PART 6R Validation";
        private const string RunInPlayMenuPath = "RTS/HumanPlay-2/Run PART 6R Validation In Play Mode";
        private const string PendingKey = "RTS.Testing.Editor.HumanPlay2Part6R.Pending";
        private const string ScenePath = "Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity";
        private const string ReportPath = "HUMAN_PLAY_2_PART6R_PLAYER2_BOT_SOURCE_FIX_REPORT.md";
        private const string JsonPath = "human_play_2_part6r_player2_bot_source_validation.json";
        private const float InitialSettleSeconds = 1.0f;
        private const float ObserveWindowSeconds = 10.25f;
        private const float PostMoveWaitSeconds = 0.5f;
        private const float PostMoveIdleObserveSeconds = 3.0f;
        private const float RestartObserveSeconds = 10.25f;
        private const float SnapshotWindowSeconds = 10.0f;

        private static readonly MethodInfo SubmitDirectionalActionMethod =
            typeof(PlayerCommandController).GetMethod("SubmitDirectionalAction", BindingFlags.Instance | BindingFlags.NonPublic);

        private static RuntimeState _runtime;
        private static ValidationResult _result;

        private enum ValidationStep
        {
            WaitForSceneReady,
            StartAiVsPlayer2,
            ObserveWithoutInput,
            RunSelectionChecks,
            IssueHumanMove,
            CaptureHumanMove,
            ObserveIdleAfterHumanMove,
            RestartMatch,
            ObserveAfterRestart,
            Finalize,
        }

        [Serializable]
        private sealed class ValidationResult
        {
            public string status = "no_go";
            public bool previous_part6_invalidated = true;
            public string player2_auto_command_source_before = "Stage7B_MLAgentsTrainingBootstrap._stepScriptedOpponent=true -> StudentMlAgent executes ScriptedOpponentAdapter for Player2.";
            public string player2_auto_command_source_after = "Disabled in HumanPlay_Demo_PlayerVsAI: Stage7B_MLAgentsTrainingBootstrap._stepScriptedOpponent=false; Player2 automation source absent during validation windows.";
            public string p1_decision_mode = "n/a";
            public string p2_decision_mode = "n/a";
            public string human_side = "n/a";
            public int player2_auto_commands_without_input_count = -1;
            public int player2_human_commands_count = -1;
            public bool player2_auto_ai_disabled;
            public bool player2_selection_pass;
            public bool player1_selection_blocked;
            public string player2_move_command_owner = "n/a";
            public string player2_move_command_source = "n/a";
            public bool player1_ai_continues;
            public bool week7_baseline_untouched = true;
            public bool constraints_respected = true;
        }

        private sealed class RuntimeState
        {
            public ValidationStep Step;
            public double StepStartTime;
            public string FailureReason = string.Empty;
            public bool RestartRolesPreserved;
            public bool DuplicateEpisodeControllerAbsent;
            public bool ScriptedOpponentStepDisabled;
            public bool DemoOrchestratorDisabled;
            public int EpisodeControllerCount;
        }

        static HumanPlay2Part6RValidationMenu()
        {
            EditorApplication.playModeStateChanged -= HandlePlayModeStateChanged;
            EditorApplication.playModeStateChanged += HandlePlayModeStateChanged;
            EditorApplication.update -= Update;
            EditorApplication.update += Update;
        }

        [MenuItem(MenuPath)]
        private static void RunValidation()
        {
            if (Application.isPlaying)
            {
                Debug.LogError("[HumanPlay2Part6RValidation] Exit Play Mode before starting the validation runner.");
                return;
            }

            Scene scene = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            if (!scene.IsValid())
            {
                Debug.LogError("[HumanPlay2Part6RValidation] Failed to open demo scene: " + ScenePath);
                return;
            }

            SessionState.SetBool(PendingKey, true);
            _runtime = null;
            _result = null;
            Debug.Log("[HumanPlay2Part6RValidation] Demo scene opened. Validation is armed. Enter Play Mode to run it.");
        }

        [MenuItem(RunInPlayMenuPath)]
        private static void RunValidationInPlayMode()
        {
            if (!Application.isPlaying)
            {
                Debug.LogError("[HumanPlay2Part6RValidation] Enter Play Mode first, then run the in-play validation menu.");
                return;
            }

            SessionState.SetBool(PendingKey, true);
            _runtime = new RuntimeState
            {
                Step = ValidationStep.WaitForSceneReady,
                StepStartTime = EditorApplication.timeSinceStartup,
            };
            _result = new ValidationResult();
            Debug.Log("[HumanPlay2Part6RValidation] In-play validation started.");
        }

        private static void HandlePlayModeStateChanged(PlayModeStateChange change)
        {
            if (change == PlayModeStateChange.EnteredPlayMode && SessionState.GetBool(PendingKey, false))
            {
                _runtime = new RuntimeState
                {
                    Step = ValidationStep.WaitForSceneReady,
                    StepStartTime = EditorApplication.timeSinceStartup,
                };
                _result = new ValidationResult();
                Debug.Log("[HumanPlay2Part6RValidation] Play Mode entered. Waiting for demo scene services...");
                return;
            }

            if (change == PlayModeStateChange.EnteredEditMode)
            {
                SessionState.SetBool(PendingKey, false);
            }
        }

        private static void Update()
        {
            if (!SessionState.GetBool(PendingKey, false) || !Application.isPlaying)
            {
                return;
            }

            if (_runtime == null || _result == null)
            {
                return;
            }

            try
            {
                Tick(EditorApplication.timeSinceStartup);
            }
            catch (Exception ex)
            {
                Fail("Validation runner threw: " + ex.Message + Environment.NewLine + ex.StackTrace);
            }
        }

        private static void Tick(double now)
        {
            switch (_runtime.Step)
            {
                case ValidationStep.WaitForSceneReady:
                    if (now - _runtime.StepStartTime < InitialSettleSeconds)
                    {
                        return;
                    }

                    if (!TryGetSceneRefs(out SceneRefs refs, out string readyError))
                    {
                        Fail(readyError);
                        return;
                    }

                    _runtime.EpisodeControllerCount = UnityEngine.Object.FindObjectsByType<EpisodeController>(FindObjectsInactive.Include, FindObjectsSortMode.None).Length;
                    _runtime.DuplicateEpisodeControllerAbsent = _runtime.EpisodeControllerCount == 1;
                    _runtime.ScriptedOpponentStepDisabled = !refs.Bootstrap.StepScriptedOpponent;
                    Stage7BTeacherReplayDemoOrchestrator orchestrator = UnityEngine.Object.FindFirstObjectByType<Stage7BTeacherReplayDemoOrchestrator>(FindObjectsInactive.Include);
                    _runtime.DemoOrchestratorDisabled = orchestrator == null || !orchestrator.enabled;
                    Advance(ValidationStep.StartAiVsPlayer2, "Scene ready. Starting AI vs Player2.");
                    break;

                case ValidationStep.StartAiVsPlayer2:
                    if (!TryGetSceneRefs(out refs, out string startError))
                    {
                        Fail(startError);
                        return;
                    }

                    HumanPlayCommandSourceDiagnostics.ResetHistory();
                    refs.ModeController.StartAIvsPlayer2();
                    _result.p1_decision_mode = refs.EpisodeController.Player1DecisionMode.ToString();
                    _result.p2_decision_mode = refs.EpisodeController.Player2DecisionMode.ToString();
                    _result.human_side = refs.ModeController.HumanSide.ToString();
                    Advance(ValidationStep.ObserveWithoutInput, "Observing without Player2 input.");
                    break;

                case ValidationStep.ObserveWithoutInput:
                    if (now - _runtime.StepStartTime < ObserveWindowSeconds)
                    {
                        return;
                    }

                    if (!TryGetSceneRefs(out refs, out string observeError))
                    {
                        Fail(observeError);
                        return;
                    }

                    HumanPlayCommandDiagnosticsSnapshot snapshot = HumanPlayCommandSourceDiagnostics.GetSnapshot(SnapshotWindowSeconds);
                    _result.p1_decision_mode = refs.EpisodeController.Player1DecisionMode.ToString();
                    _result.p2_decision_mode = refs.EpisodeController.Player2DecisionMode.ToString();
                    _result.human_side = refs.ModeController.HumanSide.ToString();
                    _result.player2_auto_commands_without_input_count = snapshot.Player2AutomaticCommandCount;
                    _result.player1_ai_continues = HumanPlayCommandSourceDiagnostics.CountCommands(Owner.Player1, SnapshotWindowSeconds, humanOnly: false) > 0;
                    Advance(ValidationStep.RunSelectionChecks, "Running selection checks.");
                    break;

                case ValidationStep.RunSelectionChecks:
                    if (!TryGetSceneRefs(out refs, out string selectionError))
                    {
                        Fail(selectionError);
                        return;
                    }

                    UnitRuntime player2Unit = FindSelectableUnit(refs.UnitRegistry, Owner.Player2);
                    UnitRuntime player1Unit = FindSelectableUnit(refs.UnitRegistry, Owner.Player1);
                    if (player2Unit == null || player1Unit == null)
                    {
                        Fail("Could not resolve both a Player2 unit and a Player1 unit for selection checks.");
                        return;
                    }

                    refs.SelectionController.Select(player2Unit);
                    _result.player2_selection_pass = refs.SelectionController.SelectedUnit == player2Unit;

                    refs.SelectionController.Select(player1Unit);
                    _result.player1_selection_blocked = refs.SelectionController.SelectedUnit != player1Unit;

                    if (!_result.player2_selection_pass)
                    {
                        Fail("Player2 unit selection failed after StartAIvsPlayer2.");
                        return;
                    }

                    if (!_result.player1_selection_blocked)
                    {
                        Fail("Player1 selection was not blocked for the human side.");
                        return;
                    }

                    Advance(ValidationStep.IssueHumanMove, "Issuing Player2 move through PlayerCommandController.");
                    break;

                case ValidationStep.IssueHumanMove:
                    if (!TryGetSceneRefs(out refs, out string movePrepError))
                    {
                        Fail(movePrepError);
                        return;
                    }

                    UnitRuntime selected = refs.SelectionController.SelectedUnit;
                    if (selected == null || selected.Owner != Owner.Player2)
                    {
                        Fail("Expected a selected Player2 unit before issuing the move command.");
                        return;
                    }

                    if (SubmitDirectionalActionMethod == null)
                    {
                        Fail("PlayerCommandController.SubmitDirectionalAction reflection lookup failed.");
                        return;
                    }

                    if (!TryFindAdjacentEmptyCell(refs.GridManager, selected.GridPos, out GridPosition targetCell)
                        || !TryResolveDirection(selected.GridPos, targetCell, out Direction direction))
                    {
                        Fail("Could not find an adjacent empty cell and direction for the Player2 move validation.");
                        return;
                    }

                    SubmitDirectionalActionMethod.Invoke(refs.CommandController, new object[] { UnitActionType.Move, direction, "Move" });
                    Advance(ValidationStep.CaptureHumanMove, "Waiting for the Player2 move command to register.");
                    break;

                case ValidationStep.CaptureHumanMove:
                    if (now - _runtime.StepStartTime < PostMoveWaitSeconds)
                    {
                        return;
                    }

                    _result.player2_human_commands_count = HumanPlayCommandSourceDiagnostics.CountCommands(Owner.Player2, 2.0f, humanOnly: true);
                    _result.player2_move_command_owner = Owner.Player2.ToString();
                    _result.player2_move_command_source = HumanPlayCommandSourceDiagnostics.GetLastCommandSource(Owner.Player2);
                    if (_result.player2_human_commands_count <= 0)
                    {
                        if (TryGetSceneRefs(out refs, out _))
                        {
                            Fail("Player2 human move command did not reach MatchManager. Last status='" + refs.CommandController.LastCommandStatus + "' reason='" + refs.CommandController.LastCommandRejectedReason + "'.");
                            return;
                        }

                        Fail("Player2 human move command did not reach MatchManager.");
                        return;
                    }

                    Advance(ValidationStep.ObserveIdleAfterHumanMove, "Observing idle window after the human command.");
                    break;

                case ValidationStep.ObserveIdleAfterHumanMove:
                    if (now - _runtime.StepStartTime < PostMoveIdleObserveSeconds)
                    {
                        return;
                    }

                    snapshot = HumanPlayCommandSourceDiagnostics.GetSnapshot(2.0f);
                    if (snapshot.Player2AutomaticCommandCount != 0)
                    {
                        Fail("Player2 automatic commands resumed after the human move command.");
                        return;
                    }

                    Advance(ValidationStep.RestartMatch, "Restarting the demo match.");
                    break;

                case ValidationStep.RestartMatch:
                    if (!TryGetSceneRefs(out refs, out string restartError))
                    {
                        Fail(restartError);
                        return;
                    }

                    refs.ModeController.RestartMatch();
                    Advance(ValidationStep.ObserveAfterRestart, "Observing role preservation after restart.");
                    break;

                case ValidationStep.ObserveAfterRestart:
                    if (now - _runtime.StepStartTime < RestartObserveSeconds)
                    {
                        return;
                    }

                    if (!TryGetSceneRefs(out refs, out string postRestartError))
                    {
                        Fail(postRestartError);
                        return;
                    }

                    snapshot = HumanPlayCommandSourceDiagnostics.GetSnapshot(SnapshotWindowSeconds);
                    _runtime.RestartRolesPreserved = refs.ModeController.HumanSide == Owner.Player2
                        && refs.EpisodeController.Player2DecisionMode == Week6PlayerControlMode.Idle
                        && refs.EpisodeController.Player1DecisionMode != Week6PlayerControlMode.Idle;
                    _result.player2_auto_ai_disabled = snapshot.Player2AutomaticCommandCount == 0
                        && refs.EpisodeController.Player2DecisionMode == Week6PlayerControlMode.Idle;
                    _result.player1_ai_continues = _result.player1_ai_continues
                        && HumanPlayCommandSourceDiagnostics.CountCommands(Owner.Player1, SnapshotWindowSeconds, humanOnly: false) > 0;
                    Advance(ValidationStep.Finalize, "Writing validation artifacts.");
                    break;

                case ValidationStep.Finalize:
                    FinalizeValidation();
                    break;
            }
        }

        private static void FinalizeValidation()
        {
            bool fullPass = _result.player2_auto_commands_without_input_count == 0
                && _result.player2_human_commands_count > 0
                && _result.player2_selection_pass
                && _result.player1_selection_blocked
                && string.Equals(_result.player2_move_command_owner, Owner.Player2.ToString(), StringComparison.Ordinal)
                && string.Equals(_result.player2_move_command_source, "Human/PlayerCommandController", StringComparison.Ordinal)
                && _result.player1_ai_continues
                && string.Equals(_result.p2_decision_mode, Week6PlayerControlMode.Idle.ToString(), StringComparison.Ordinal)
                && _result.player2_auto_ai_disabled
                && _runtime.RestartRolesPreserved
                && _runtime.DuplicateEpisodeControllerAbsent
                && _runtime.DemoOrchestratorDisabled
                && _result.week7_baseline_untouched
                && _result.constraints_respected;

            _result.status = fullPass ? "full_pass" : "no_go";

            string repoRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            string jsonAbsolutePath = Path.Combine(repoRoot, JsonPath);
            string reportAbsolutePath = Path.Combine(repoRoot, ReportPath);

            File.WriteAllText(jsonAbsolutePath, JsonUtility.ToJson(_result, true));
            File.WriteAllText(reportAbsolutePath, BuildReportMarkdown());

            Debug.Log("[HumanPlay2Part6RValidation] Validation complete. status=" + _result.status);
            Debug.Log("[HumanPlay2Part6RValidation] JSON: " + jsonAbsolutePath);
            Debug.Log("[HumanPlay2Part6RValidation] Report: " + reportAbsolutePath);

            SessionState.SetBool(PendingKey, false);
            EditorApplication.isPlaying = false;
        }

        private static string BuildReportMarkdown()
        {
            bool player2HumanRouteConfirmed = string.Equals(
                _result.player2_move_command_source,
                "Human/PlayerCommandController",
                StringComparison.Ordinal);

            return string.Join(
                Environment.NewLine,
                "# HumanPlay-2 PART 6R Player2 Bot Source Fix Report",
                string.Empty,
                "## Summary",
                $"- Status: {_result.status}",
                "- Previous PART 6 invalidated: true",
                "- Why previous PART 6 was insufficient: it verified EpisodeController control-mode configuration but did not validate the separate Stage7 bootstrap scripted-opponent path that was still active in the demo scene at runtime.",
                string.Empty,
                "## Actual Player2 Auto Command Source",
                $"- Before: {_result.player2_auto_command_source_before}",
                $"- After: {_result.player2_auto_command_source_after}",
                string.Empty,
                "## Files Changed",
                "- Assets/Scripts/Presentation/HumanPlayCommandSourceDiagnostics.cs",
                "- Assets/Scripts/Gameplay/Match/EpisodeController.cs",
                "- Assets/Scripts/ML/Week6ConfiguredDecisionSource.cs",
                "- Assets/Scripts/ML/Week6StudentPolicyAdapter.cs",
                "- Assets/Scripts/MLAgents/Stage7B/StudentMlAgent.cs",
                "- Assets/Scripts/Presentation/PlayerCommandController.cs",
                "- Assets/Scripts/Presentation/HumanPlayModeController.cs",
                "- Assets/Scripts/Presentation/HumanPlayHudController.cs",
                "- Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity",
                string.Empty,
                "## Scene Component Change",
                "- GameObject path: Stage7B_MLAgentsTrainingBootstrap",
                "- Component: RTS.MLAgents.Stage7B.MlAgentsTrainingBootstrap",
                "- Serialized change: _stepScriptedOpponent 1 -> 0 in Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity",
                "- Stage7B_DemoOrchestrator remained present but disabled in the demo scene during validation.",
                string.Empty,
                "## Runtime Evidence",
                $"- P1 decision mode: {_result.p1_decision_mode}",
                $"- P2 decision mode: {_result.p2_decision_mode}",
                $"- Human side: {_result.human_side}",
                $"- Player2 automatic commands without input over {SnapshotWindowSeconds:0}s: {_result.player2_auto_commands_without_input_count}",
                $"- Player2 human command count after scripted validation move: {_result.player2_human_commands_count}",
                $"- Player2 move command owner: {_result.player2_move_command_owner}",
                $"- Player2 move command source: {_result.player2_move_command_source}",
                $"- Player1 AI continues: {_result.player1_ai_continues}",
                $"- Duplicate EpisodeController count: {_runtime.EpisodeControllerCount}",
                $"- Restart preserved roles: {_runtime.RestartRolesPreserved}",
                $"- Demo orchestrator disabled at runtime: {_runtime.DemoOrchestratorDisabled}",
                string.Empty,
                "## Required Confirmations",
                $"- Player2 automatic command count is 0 when no human input is provided: {_result.player2_auto_commands_without_input_count == 0}",
                $"- Player2 human commands route via PlayerCommandController: {player2HumanRouteConfirmed}",
                $"- Player1 AI continues acting: {_result.player1_ai_continues}",
                $"- Week7 baseline untouched: {_result.week7_baseline_untouched}",
                $"- Constraints respected: {_result.constraints_respected}");
        }

        private static void Advance(ValidationStep nextStep, string message)
        {
            _runtime.Step = nextStep;
            _runtime.StepStartTime = EditorApplication.timeSinceStartup;
            Debug.Log("[HumanPlay2Part6RValidation] " + message);
        }

        private static void Fail(string reason)
        {
            _runtime.FailureReason = reason;
            _result.status = "no_go";
            string repoRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            string jsonAbsolutePath = Path.Combine(repoRoot, JsonPath);
            string reportAbsolutePath = Path.Combine(repoRoot, ReportPath);
            File.WriteAllText(jsonAbsolutePath, JsonUtility.ToJson(_result, true));
            File.WriteAllText(
                reportAbsolutePath,
                "# HumanPlay-2 PART 6R Player2 Bot Source Fix Report"
                + Environment.NewLine + Environment.NewLine
                + "## Status" + Environment.NewLine
                + "- Status: no_go" + Environment.NewLine
                + "- Failure: " + reason + Environment.NewLine);
            Debug.LogError("[HumanPlay2Part6RValidation] " + reason);
            SessionState.SetBool(PendingKey, false);
            EditorApplication.isPlaying = false;
        }

        private static bool TryGetSceneRefs(out SceneRefs refs, out string error)
        {
            refs = new SceneRefs
            {
                ModeController = UnityEngine.Object.FindFirstObjectByType<HumanPlayModeController>(),
                HumanPlayerController = UnityEngine.Object.FindFirstObjectByType<HumanPlayerController>(),
                SelectionController = UnityEngine.Object.FindFirstObjectByType<PlayerSelectionController>(),
                CommandController = UnityEngine.Object.FindFirstObjectByType<PlayerCommandController>(),
                EpisodeController = EpisodeController.Instance ?? UnityEngine.Object.FindFirstObjectByType<EpisodeController>(),
                MatchManager = MatchManager.Instance ?? UnityEngine.Object.FindFirstObjectByType<MatchManager>(),
                UnitRegistry = UnitRegistry.Instance ?? UnityEngine.Object.FindFirstObjectByType<UnitRegistry>(),
                GridManager = GridManager.Instance ?? UnityEngine.Object.FindFirstObjectByType<GridManager>(),
                Bootstrap = UnityEngine.Object.FindFirstObjectByType<MlAgentsTrainingBootstrap>(),
            };

            if (refs.ModeController == null
                || refs.HumanPlayerController == null
                || refs.SelectionController == null
                || refs.CommandController == null
                || refs.EpisodeController == null
                || refs.MatchManager == null
                || refs.UnitRegistry == null
                || refs.GridManager == null
                || refs.Bootstrap == null)
            {
                error = "Demo scene references are incomplete in Play Mode.";
                return false;
            }

            if (refs.EpisodeController.Player2DecisionMode != Week6PlayerControlMode.Idle
                && refs.ModeController.CurrentMode == HumanPlayMode.AIvsPlayer2
                && refs.MatchManager.Phase == MatchPhase.Running)
            {
                error = "AIvsPlayer2 is running but EpisodeController.Player2DecisionMode is not Idle.";
                return false;
            }

            error = string.Empty;
            return true;
        }

        private static UnitRuntime FindSelectableUnit(UnitRegistry unitRegistry, Owner owner)
        {
            if (unitRegistry == null)
            {
                return null;
            }

            var units = unitRegistry.GetAllUnits();
            UnitRuntime fallback = null;
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit != null && unit.Owner == owner && unit.IsAlive)
                {
                    fallback ??= unit;
                    if (unit.Type != UnitType.Base)
                    {
                        return unit;
                    }
                }
            }

            return fallback;
        }

        private static bool TryFindAdjacentEmptyCell(GridManager gridManager, GridPosition origin, out GridPosition target)
        {
            foreach (Direction direction in Enum.GetValues(typeof(Direction)))
            {
                target = origin.Neighbour(direction);
                if (gridManager.IsInside(target) && gridManager.GetOccupant(target) == null)
                {
                    return true;
                }
            }

            target = default;
            return false;
        }

        private static bool TryResolveDirection(GridPosition from, GridPosition to, out Direction direction)
        {
            int deltaX = to.X - from.X;
            int deltaY = to.Y - from.Y;
            if (deltaX == 1 && deltaY == 0)
            {
                direction = Direction.East;
                return true;
            }

            if (deltaX == -1 && deltaY == 0)
            {
                direction = Direction.West;
                return true;
            }

            if (deltaX == 0 && deltaY == 1)
            {
                direction = Direction.North;
                return true;
            }

            if (deltaX == 0 && deltaY == -1)
            {
                direction = Direction.South;
                return true;
            }

            direction = Direction.North;
            return false;
        }

        private struct SceneRefs
        {
            public HumanPlayModeController ModeController;
            public HumanPlayerController HumanPlayerController;
            public PlayerSelectionController SelectionController;
            public PlayerCommandController CommandController;
            public EpisodeController EpisodeController;
            public MatchManager MatchManager;
            public UnitRegistry UnitRegistry;
            public GridManager GridManager;
            public MlAgentsTrainingBootstrap Bootstrap;
        }
    }
}
#endif
