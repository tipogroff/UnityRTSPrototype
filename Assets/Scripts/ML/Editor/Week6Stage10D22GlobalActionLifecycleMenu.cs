#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using RTS.Core;
using RTS.Gameplay;
using RTS.ML;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RTS.ML.Editor
{
    [InitializeOnLoad]
    public static class Week6Stage10D22GlobalActionLifecycleMenu
    {
        private const string MenuPath = "RTS/Week6/Stage10D22/Run Global Action Lifecycle (All Modes)";
        private const string PendingKey = "RTS.Week6.Stage10D22.Pending";
        private const string PollCountKey = "RTS.Week6.Stage10D22.PollCount";
        private const int MaxPolls = 300;

        private const string TargetScenePath = "Assets/Scenes/Week6_StudentVisualInspection.unity";
        private const string OutputRelativeDir = "python/week6_student/tmp/stage10d22_global_lifecycle";
        private const int TargetSteps = 80;

        static Week6Stage10D22GlobalActionLifecycleMenu()
        {
            EditorApplication.playModeStateChanged -= HandlePlayModeStateChanged;
            EditorApplication.playModeStateChanged += HandlePlayModeStateChanged;
            EditorApplication.update -= PollPendingRun;
            EditorApplication.update += PollPendingRun;
        }

        [Serializable]
        private sealed class ScriptedActionCount
        {
            public string action;
            public int attempted;
            public int accepted;
        }

        [Serializable]
        private sealed class ModeManifest
        {
            public string mode;
            public int target_steps;
            public int steps_completed;
            public int final_match_step;
            public bool terminal;
            public string terminal_reason;
            public int scripted_attempted;
            public int scripted_accepted;
            public int scripted_direct_matchmanager_attempted;
            public int scripted_direct_matchmanager_accepted;
            public int scripted_canonical_actionapplier_attempted;
            public int scripted_canonical_actionapplier_accepted;
            public ScriptedActionCount[] scripted_per_action;
            public ScriptedActionCount[] scripted_direct_per_action;
            public ScriptedActionCount[] scripted_canonical_per_action;
            public int scripted_move_attempted;
            public int scripted_move_accepted;
            public bool scripted_move_caused_position_delta;
            public string scripted_move_delta_evidence;
            public bool scripted_direct_matchmanager_bypasses_decoder_actionapplier;
            public bool scripted_canonical_uses_actionapplier;
            public bool scripted_completed;
            public string output_relative_dir;
        }

        [Serializable]
        private sealed class RunManifest
        {
            public string generated_at_utc;
            public string scene;
            public string output_relative_dir;
            public ModeManifest[] modes;
        }

        [MenuItem(MenuPath)]
        public static void Run()
        {
            EnsureTargetSceneLoaded();

            SessionState.SetBool(PendingKey, true);
            SessionState.SetInt(PollCountKey, 0);

            if (Application.isPlaying)
            {
                ExecutePendingRun();
                return;
            }

            Debug.Log("[Stage10D22] Entering Play Mode for global action lifecycle diagnostics...");
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

            Week6VisualInspectionRunner runner = UnityEngine.Object.FindFirstObjectByType<Week6VisualInspectionRunner>();
            EpisodeController controller = UnityEngine.Object.FindFirstObjectByType<EpisodeController>();
            MatchManager matchManager = UnityEngine.Object.FindFirstObjectByType<MatchManager>();
            UnitRegistry unitRegistry = UnityEngine.Object.FindFirstObjectByType<UnitRegistry>();

            if (runner == null || controller == null || matchManager == null || unitRegistry == null)
            {
                if (polls < MaxPolls)
                {
                    return;
                }

                SessionState.EraseBool(PendingKey);
                SessionState.EraseInt(PollCountKey);
                Debug.LogError("[Stage10D22] Runtime references not ready in Play Mode.");
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
                RunControlledCapture();
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
            }
            finally
            {
                if (shouldExitPlayMode && Application.isPlaying)
                {
                    EditorApplication.isPlaying = false;
                }
            }
        }

        private static void RunControlledCapture()
        {
            Week6VisualInspectionRunner runner = UnityEngine.Object.FindFirstObjectByType<Week6VisualInspectionRunner>();
            EpisodeController controller = UnityEngine.Object.FindFirstObjectByType<EpisodeController>();
            MatchManager matchManager = UnityEngine.Object.FindFirstObjectByType<MatchManager>();
            UnitRegistry unitRegistry = UnityEngine.Object.FindFirstObjectByType<UnitRegistry>();
            GridManager gridManager = UnityEngine.Object.FindFirstObjectByType<GridManager>();
            ResourceManager resourceManager = UnityEngine.Object.FindFirstObjectByType<ResourceManager>();
            Week6StudentPolicyAdapter adapter = UnityEngine.Object.FindFirstObjectByType<Week6StudentPolicyAdapter>();

            if (runner == null || controller == null || matchManager == null || unitRegistry == null || gridManager == null)
            {
                Debug.LogError("[Stage10D22] Missing runtime components.");
                return;
            }

            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? string.Empty;
            string outputRoot = Path.GetFullPath(Path.Combine(projectRoot, OutputRelativeDir));
            Directory.CreateDirectory(outputRoot);

            if (adapter != null)
            {
                SetPrivateBool(adapter, "_enableLegalActionMaskForSelection", true);
            }

            var modeManifests = new List<ModeManifest>(3)
            {

                RunSingleMode(
                    modeName: "student_live_policy",
                    runner: runner,
                    adapter: adapter,
                    controller: controller,
                    matchManager: matchManager,
                    gridManager: gridManager,
                    unitRegistry: unitRegistry,
                    resourceManager: resourceManager,
                    outputRoot: outputRoot,
                    player1Mode: Week6PlayerControlMode.StudentInference,
                    player2Mode: Week6PlayerControlMode.HeuristicBaseline,
                    scriptedCommands: false),
                RunSingleMode(
                    modeName: "heuristic_baseline",
                    runner: runner,
                    adapter: adapter,
                    controller: controller,
                    matchManager: matchManager,
                    gridManager: gridManager,
                    unitRegistry: unitRegistry,
                    resourceManager: resourceManager,
                    outputRoot: outputRoot,
                    player1Mode: Week6PlayerControlMode.HeuristicBaseline,
                    player2Mode: Week6PlayerControlMode.HeuristicBaseline,
                    scriptedCommands: false),
                RunSingleMode(
                    modeName: "scripted_deterministic_commands",
                    runner: runner,
                    adapter: adapter,
                    controller: controller,
                    matchManager: matchManager,
                    gridManager: gridManager,
                    unitRegistry: unitRegistry,
                    resourceManager: resourceManager,
                    outputRoot: outputRoot,
                    player1Mode: Week6PlayerControlMode.Idle,
                    player2Mode: Week6PlayerControlMode.HeuristicBaseline,
                    scriptedCommands: true),
            };

            var runManifest = new RunManifest
            {
                generated_at_utc = DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture),
                scene = SceneManager.GetActiveScene().path.Replace("\\", "/"),
                output_relative_dir = OutputRelativeDir.Replace("\\", "/"),
                modes = modeManifests.ToArray(),
            };

            string runManifestPath = Path.Combine(outputRoot, "stage10d22_run_manifest.json");
            File.WriteAllText(runManifestPath, JsonUtility.ToJson(runManifest, true));
            Debug.Log("[Stage10D22] Global lifecycle capture complete: " + runManifestPath);
        }

        private static ModeManifest RunSingleMode(
            string modeName,
            Week6VisualInspectionRunner runner,
            Week6StudentPolicyAdapter adapter,
            EpisodeController controller,
            MatchManager matchManager,
            GridManager gridManager,
            UnitRegistry unitRegistry,
            ResourceManager resourceManager,
            string outputRoot,
            Week6PlayerControlMode player1Mode,
            Week6PlayerControlMode player2Mode,
            bool scriptedCommands)
        {
            string modeOutputDir = Path.Combine(outputRoot, modeName);
            Directory.CreateDirectory(modeOutputDir);

            string relativeModeDir = (OutputRelativeDir + "/" + modeName).Replace("\\", "/");
            SetPrivateString(runner, "_stepSnapshotOutputDirectoryRelativePath", relativeModeDir);
            SetPrivateString(runner, "_stepSnapshotFilePrefix", "stage10d22_" + modeName + "_snapshot_step");

            controller.ConfigureWeek6PlayerControlModes(
                enableStudentMatchControl: true,
                player1Mode: player1Mode,
                player2Mode: player2Mode);

            bool previousUseHeuristic = GetPrivateField(controller, "_useHeuristicAI", true);
            if (scriptedCommands)
            {
                SetPrivateBool(controller, "_useHeuristicAI", false);
            }

            int scriptedAttempted = 0;
            int scriptedAccepted = 0;
            int scriptedDirectAttempted = 0;
            int scriptedDirectAccepted = 0;
            int scriptedCanonicalAttempted = 0;
            int scriptedCanonicalAccepted = 0;
            int scriptedMoveAttempted = 0;
            int scriptedMoveAccepted = 0;
            bool scriptedMoveCausedPositionDelta = false;
            string scriptedMoveDeltaEvidence = "none";

            var scriptedPerAction = new Dictionary<UnitActionType, ScriptedActionCount>(6);
            var scriptedDirectPerAction = new Dictionary<UnitActionType, ScriptedActionCount>(6);
            var scriptedCanonicalPerAction = new Dictionary<UnitActionType, ScriptedActionCount>(6);
            int stepsCompleted = 0;

            // Stage10D25: set mode-isolation context on the runner so snapshots carry correct telemetry.
            // Also reset student adapter diagnostics to prevent stale data from previous mode leaking
            // into heuristic-only snapshots (root cause of NOT_ISOLATED verdict in D24).
            runner.SetCurrentCaptureModeContext(modeName, player1Mode, player2Mode);
            if (adapter != null
                && player1Mode == Week6PlayerControlMode.HeuristicBaseline
                && player2Mode == Week6PlayerControlMode.HeuristicBaseline)
            {
                adapter.ResetEpisodeState();
            }

            runner.StartVisualInspectionMatch(true);

            for (int i = 0; i < TargetSteps; i++)
            {
                if (!controller.IsRunning)
                {
                    break;
                }

                if (scriptedCommands)
                {
                    if (TryBuildScriptedIntent(matchManager, unitRegistry, Owner.Player1, i, out ScriptedIntent intent))
                    {
                        bool useCanonicalPath = (i % 2) == 1;
                        bool accepted;
                        GridPosition preStepPos = intent.ActorUnit != null ? intent.ActorUnit.GridPos : GridPosition.Zero;

                        scriptedAttempted++;
                        IncrementScriptedActionCount(scriptedPerAction, intent.ActionType, attemptedDelta: 1, acceptedDelta: 0);

                        if (useCanonicalPath)
                        {
                            scriptedCanonicalAttempted++;
                            IncrementScriptedActionCount(scriptedCanonicalPerAction, intent.ActionType, attemptedDelta: 1, acceptedDelta: 0);
                            accepted = TrySubmitScriptedCommandCanonical(intent, gridManager, unitRegistry, matchManager, resourceManager);
                            if (accepted)
                            {
                                scriptedCanonicalAccepted++;
                                IncrementScriptedActionCount(scriptedCanonicalPerAction, intent.ActionType, attemptedDelta: 0, acceptedDelta: 1);
                            }
                        }
                        else
                        {
                            scriptedDirectAttempted++;
                            IncrementScriptedActionCount(scriptedDirectPerAction, intent.ActionType, attemptedDelta: 1, acceptedDelta: 0);
                            accepted = TrySubmitScriptedCommandDirect(matchManager, intent);
                            if (accepted)
                            {
                                scriptedDirectAccepted++;
                                IncrementScriptedActionCount(scriptedDirectPerAction, intent.ActionType, attemptedDelta: 0, acceptedDelta: 1);
                            }
                        }

                        if (accepted)
                        {
                            scriptedAccepted++;
                            IncrementScriptedActionCount(scriptedPerAction, intent.ActionType, attemptedDelta: 0, acceptedDelta: 1);
                        }

                        if (intent.ActionType == UnitActionType.Move)
                        {
                            scriptedMoveAttempted++;
                            if (accepted)
                            {
                                scriptedMoveAccepted++;
                            }
                        }

                        runner.StepManualOnce();
                        runner.DumpCurrentStepDiagnostics();
                        stepsCompleted++;

                        if (accepted && intent.ActionType == UnitActionType.Move && intent.ActorUnit != null && intent.ActorUnit.IsAlive)
                        {
                            GridPosition postStepPos = intent.ActorUnit.GridPos;
                            bool moved = postStepPos.X != preStepPos.X || postStepPos.Y != preStepPos.Y;
                            if (moved)
                            {
                                scriptedMoveCausedPositionDelta = true;
                                scriptedMoveDeltaEvidence = $"step={i}, from=({preStepPos.X},{preStepPos.Y}), to=({postStepPos.X},{postStepPos.Y}), path={(useCanonicalPath ? "scripted_canonical_actionapplier" : "scripted_direct_matchmanager")}";
                            }
                        }

                        if (!controller.IsRunning)
                        {
                            break;
                        }

                        continue;
                    }
                }

                runner.StepManualOnce();
                runner.DumpCurrentStepDiagnostics();
                stepsCompleted++;

                if (!controller.IsRunning)
                {
                    break;
                }
            }

            if (scriptedCommands)
            {
                SetPrivateBool(controller, "_useHeuristicAI", previousUseHeuristic);
            }

            EpisodeEndReport terminal = controller.LastTerminalReport;
            var modeManifest = new ModeManifest
            {
                mode = modeName,
                target_steps = TargetSteps,
                steps_completed = stepsCompleted,
                final_match_step = matchManager.Step,
                terminal = terminal.IsTerminal,
                terminal_reason = terminal.IsTerminal ? terminal.TerminalReason.ToString() : "none",
                scripted_attempted = scriptedAttempted,
                scripted_accepted = scriptedAccepted,
                scripted_direct_matchmanager_attempted = scriptedDirectAttempted,
                scripted_direct_matchmanager_accepted = scriptedDirectAccepted,
                scripted_canonical_actionapplier_attempted = scriptedCanonicalAttempted,
                scripted_canonical_actionapplier_accepted = scriptedCanonicalAccepted,
                scripted_per_action = BuildScriptedActionCounts(scriptedPerAction),
                scripted_direct_per_action = BuildScriptedActionCounts(scriptedDirectPerAction),
                scripted_canonical_per_action = BuildScriptedActionCounts(scriptedCanonicalPerAction),
                scripted_move_attempted = scriptedMoveAttempted,
                scripted_move_accepted = scriptedMoveAccepted,
                scripted_move_caused_position_delta = scriptedMoveCausedPositionDelta,
                scripted_move_delta_evidence = scriptedMoveDeltaEvidence,
                scripted_direct_matchmanager_bypasses_decoder_actionapplier = scriptedCommands,
                scripted_canonical_uses_actionapplier = scriptedCommands,
                scripted_completed = !scriptedCommands || scriptedAttempted > 0,
                output_relative_dir = relativeModeDir,
            };

            string modeManifestPath = Path.Combine(modeOutputDir, "stage10d22_mode_manifest.json");
            File.WriteAllText(modeManifestPath, JsonUtility.ToJson(modeManifest, true));
            Debug.Log($"[Stage10D22] Mode '{modeName}' complete: steps={stepsCompleted}, scriptedAccepted={scriptedAccepted}, scriptedMoveAttempted={scriptedMoveAttempted}, scriptedMoveDelta={scriptedMoveCausedPositionDelta}.");

            return modeManifest;
        }

        private readonly struct ScriptedIntent
        {
            public ScriptedIntent(UnitRuntime actorUnit, Owner owner, UnitActionType actionType, Direction direction, ProducibleUnit produceUnitType, GridPosition attackTarget)
            {
                ActorUnit = actorUnit;
                Owner = owner;
                ActionType = actionType;
                Direction = direction;
                ProduceUnitType = produceUnitType;
                AttackTarget = attackTarget;
            }

            public UnitRuntime ActorUnit { get; }
            public Owner Owner { get; }
            public UnitActionType ActionType { get; }
            public Direction Direction { get; }
            public ProducibleUnit ProduceUnitType { get; }
            public GridPosition AttackTarget { get; }
        }

        private static bool TryBuildScriptedIntent(MatchManager matchManager, UnitRegistry unitRegistry, Owner owner, int scriptedStep, out ScriptedIntent intent)
        {
            intent = default;

            if (matchManager == null || unitRegistry == null)
            {
                return false;
            }

            List<UnitRuntime> ownUnits = unitRegistry.GetUnitsByOwner(owner);
            if (ownUnits == null || ownUnits.Count == 0)
            {
                return false;
            }

            UnitRuntime worker = null;
            UnitRuntime baseUnit = null;
            UnitRuntime enemy = null;
            for (int i = 0; i < ownUnits.Count; i++)
            {
                UnitRuntime unit = ownUnits[i];
                if (unit == null || !unit.IsAlive)
                {
                    continue;
                }

                if (unit.Type == UnitType.Worker && worker == null)
                {
                    worker = unit;
                }

                if (unit.Type == UnitType.Base && baseUnit == null)
                {
                    baseUnit = unit;
                }
            }

            List<UnitRuntime> all = unitRegistry.GetAllUnits();
            for (int i = 0; i < all.Count; i++)
            {
                UnitRuntime unit = all[i];
                if (unit == null || !unit.IsAlive || unit.Owner == owner || unit.Owner == Owner.Neutral)
                {
                    continue;
                }

                enemy = unit;
                break;
            }

            if (worker != null)
            {
                int phase = Mathf.Abs(scriptedStep) % 8;

                // Force a varied action mix so all lifecycle boundaries can be observed.
                if ((phase == 0 || phase == 5) && enemy != null && TryFindDirectionToward(worker.GridPos, enemy.GridPos, out Direction moveDirPhase))
                {
                    intent = new ScriptedIntent(worker, owner, UnitActionType.Move, moveDirPhase, ProducibleUnit.Worker, GridPosition.Zero);
                    return true;
                }

                if (phase == 1 && enemy != null && TryFindDirectionToward(worker.GridPos, enemy.GridPos, out Direction attackDir))
                {
                    intent = new ScriptedIntent(worker, owner, UnitActionType.Attack, attackDir, ProducibleUnit.Worker, worker.GridPos.Neighbour(attackDir));
                    return true;
                }

                if (phase == 2 && worker.CarriedResources < 100 && TryFindAdjacentResource(worker.GridPos, out Direction harvestDirPhase))
                {
                    intent = new ScriptedIntent(worker, owner, UnitActionType.Harvest, harvestDirPhase, ProducibleUnit.Worker, GridPosition.Zero);
                    return true;
                }

                if (phase == 3 && worker.CarriedResources > 0 && TryFindAdjacentOwnedBase(worker.GridPos, owner, out Direction returnDirPhase))
                {
                    intent = new ScriptedIntent(worker, owner, UnitActionType.Return, returnDirPhase, ProducibleUnit.Worker, GridPosition.Zero);
                    return true;
                }

                if (phase == 4 && baseUnit != null && matchManager.GetResources(owner) >= 50 && TryFindFirstFreeDirection(baseUnit.GridPos, out Direction produceDirPhase))
                {
                    intent = new ScriptedIntent(baseUnit, owner, UnitActionType.Produce, produceDirPhase, ProducibleUnit.Worker, GridPosition.Zero);
                    return true;
                }

                if (worker.CarriedResources > 0 && TryFindAdjacentOwnedBase(worker.GridPos, owner, out Direction returnDir))
                {
                    intent = new ScriptedIntent(worker, owner, UnitActionType.Return, returnDir, ProducibleUnit.Worker, GridPosition.Zero);
                    return true;
                }

                if (worker.CarriedResources < 100 && TryFindAdjacentResource(worker.GridPos, out Direction harvestDir))
                {
                    intent = new ScriptedIntent(worker, owner, UnitActionType.Harvest, harvestDir, ProducibleUnit.Worker, GridPosition.Zero);
                    return true;
                }

                if (enemy != null && TryFindDirectionToward(worker.GridPos, enemy.GridPos, out Direction moveDir))
                {
                    intent = new ScriptedIntent(worker, owner, UnitActionType.Move, moveDir, ProducibleUnit.Worker, GridPosition.Zero);
                    return true;
                }
            }

            if (baseUnit != null && matchManager.GetResources(owner) >= 50)
            {
                if (TryFindFirstFreeDirection(baseUnit.GridPos, out Direction produceDir))
                {
                    intent = new ScriptedIntent(baseUnit, owner, UnitActionType.Produce, produceDir, ProducibleUnit.Worker, GridPosition.Zero);
                    return true;
                }
            }

            return false;
        }

        private static bool TrySubmitScriptedCommandDirect(MatchManager matchManager, ScriptedIntent intent)
        {
            if (matchManager == null || intent.ActorUnit == null || !intent.ActorUnit.IsAlive)
            {
                return false;
            }

            MatchCommand command = intent.ActionType == UnitActionType.Attack
                ? new MatchCommand(intent.Owner, intent.ActorUnit.GridPos, intent.ActionType, intent.Direction, attackTarget: intent.AttackTarget, hasAttackTarget: true)
                : new MatchCommand(intent.Owner, intent.ActorUnit.GridPos, intent.ActionType, intent.Direction, intent.ProduceUnitType);
            return matchManager.ApplyCommand(command);
        }

        private static bool TrySubmitScriptedCommandCanonical(
            ScriptedIntent intent,
            GridManager gridManager,
            UnitRegistry unitRegistry,
            MatchManager matchManager,
            ResourceManager resourceManager)
        {
            if (intent.ActorUnit == null || !intent.ActorUnit.IsAlive || gridManager == null || unitRegistry == null || matchManager == null)
            {
                return false;
            }

            var applier = new ActionApplier(gridManager, unitRegistry, matchManager, resourceManager);
            var action = new AgentAction(
                actorPosition: intent.ActorUnit.GridPos,
                actionType: intent.ActionType,
                direction: intent.Direction,
                produceUnitType: intent.ProduceUnitType,
                attackTargetPosition: intent.AttackTarget,
                isValid: true,
                invalidationReason: string.Empty,
                sourceType: ActionSourceType.Debug);
            return applier.ApplyAction(action, intent.Owner);
        }

        private static void IncrementScriptedActionCount(Dictionary<UnitActionType, ScriptedActionCount> counts, UnitActionType action, int attemptedDelta, int acceptedDelta)
        {
            if (!counts.TryGetValue(action, out ScriptedActionCount entry))
            {
                entry = new ScriptedActionCount
                {
                    action = action.ToString(),
                    attempted = 0,
                    accepted = 0,
                };
                counts[action] = entry;
            }

            entry.attempted += attemptedDelta;
            entry.accepted += acceptedDelta;
        }

        private static ScriptedActionCount[] BuildScriptedActionCounts(Dictionary<UnitActionType, ScriptedActionCount> counts)
        {
            var result = new List<ScriptedActionCount>(counts.Count);
            foreach (UnitActionType action in Enum.GetValues(typeof(UnitActionType)))
            {
                if (!counts.TryGetValue(action, out ScriptedActionCount entry))
                {
                    continue;
                }

                result.Add(new ScriptedActionCount
                {
                    action = entry.action,
                    attempted = entry.attempted,
                    accepted = entry.accepted,
                });
            }

            return result.ToArray();
        }

        private static bool TryFindAdjacentResource(GridPosition from, out Direction direction)
        {
            Direction[] dirs = { Direction.North, Direction.East, Direction.South, Direction.West };
            GridManager grid = GridManager.Instance;
            ResourceManager resources = ResourceManager.Instance;
            for (int i = 0; i < dirs.Length; i++)
            {
                GridPosition to = from.Neighbour(dirs[i]);
                if (!to.IsInsideMap())
                {
                    continue;
                }

                if (resources != null && resources.GetResourceNode(to) != null)
                {
                    direction = dirs[i];
                    return true;
                }
            }

            direction = Direction.North;
            return false;
        }

        private static bool TryFindAdjacentOwnedBase(GridPosition from, Owner owner, out Direction direction)
        {
            Direction[] dirs = { Direction.North, Direction.East, Direction.South, Direction.West };
            GridManager grid = GridManager.Instance;
            for (int i = 0; i < dirs.Length; i++)
            {
                GridPosition to = from.Neighbour(dirs[i]);
                if (!to.IsInsideMap())
                {
                    continue;
                }

                UnitRuntime occupant = grid != null ? grid.GetOccupant(to) : null;
                if (occupant != null && occupant.Owner == owner && occupant.Type == UnitType.Base)
                {
                    direction = dirs[i];
                    return true;
                }
            }

            direction = Direction.North;
            return false;
        }

        private static bool TryFindFirstFreeDirection(GridPosition from, out Direction direction)
        {
            Direction[] dirs = { Direction.North, Direction.East, Direction.South, Direction.West };
            GridManager grid = GridManager.Instance;
            for (int i = 0; i < dirs.Length; i++)
            {
                GridPosition to = from.Neighbour(dirs[i]);
                if (!to.IsInsideMap())
                {
                    continue;
                }

                if (grid == null || !grid.IsCellOccupied(to))
                {
                    direction = dirs[i];
                    return true;
                }
            }

            direction = Direction.North;
            return false;
        }

        private static bool TryFindDirectionToward(GridPosition from, GridPosition to, out Direction direction)
        {
            int dx = to.X - from.X;
            int dy = to.Y - from.Y;

            if (Mathf.Abs(dx) >= Mathf.Abs(dy))
            {
                if (dx > 0)
                {
                    direction = Direction.East;
                    return true;
                }

                if (dx < 0)
                {
                    direction = Direction.West;
                    return true;
                }
            }

            if (dy > 0)
            {
                direction = Direction.North;
                return true;
            }

            if (dy < 0)
            {
                direction = Direction.South;
                return true;
            }

            direction = Direction.North;
            return false;
        }

        private static void EnsureTargetSceneLoaded()
        {
            Scene scene = SceneManager.GetActiveScene();
            if (scene.IsValid() && string.Equals(scene.path, TargetScenePath, StringComparison.Ordinal))
            {
                return;
            }

            if (Application.isPlaying)
            {
                throw new InvalidOperationException("Cannot switch scene while in Play Mode.");
            }

            if (EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo())
            {
                EditorSceneManager.OpenScene(TargetScenePath, OpenSceneMode.Single);
            }
            else
            {
                throw new InvalidOperationException("Scene switch canceled by user.");
            }
        }

        private static void SetPrivateString(object target, string fieldName, string value)
        {
            FieldInfo field = target.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            if (field == null || field.FieldType != typeof(string))
            {
                throw new MissingFieldException(target.GetType().Name, fieldName);
            }

            field.SetValue(target, value ?? string.Empty);
        }

        private static void SetPrivateBool(object target, string fieldName, bool value)
        {
            FieldInfo field = target.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            if (field == null || field.FieldType != typeof(bool))
            {
                throw new MissingFieldException(target.GetType().Name, fieldName);
            }

            field.SetValue(target, value);
        }

        private static T GetPrivateField<T>(object target, string fieldName, T fallback)
        {
            if (target == null)
            {
                return fallback;
            }

            FieldInfo field = target.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            if (field == null)
            {
                return fallback;
            }

            object value = field.GetValue(target);
            if (value is T cast)
            {
                return cast;
            }

            return fallback;
        }
    }
}
#endif
