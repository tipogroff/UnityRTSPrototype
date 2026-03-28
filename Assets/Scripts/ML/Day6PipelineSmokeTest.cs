using System;
using System.Collections.Generic;
using System.Text;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.ML
{
    /// <summary>
    /// Day 6 regression-oriented smoke suite for the production action pipeline:
    /// observation -> mask -> decoder -> applier -> MatchManager.ApplyCommand().
    ///
    /// This suite intentionally avoids shortcut execution paths.
    /// </summary>
    public sealed class Day6PipelineSmokeTest : MonoBehaviour
    {
        [SerializeField] private bool _runOnAwake = true;
        [SerializeField] private bool _verbose = true;
        [SerializeField] private bool _throwOnSuiteFailure = true;
        [SerializeField] private Owner _playerUnderTest = Owner.Player1;

        private GridManager _gridManager;
        private UnitRegistry _unitRegistry;
        private MatchManager _matchManager;
        private MatchBootstrap _matchBootstrap;
        private ResourceManager _resourceManager;

        private ObservationBuilder _observationBuilder;
        private ActionMaskBuilder _maskBuilder;
        private ActionDecoder _decoder;
        private ActionApplier _applier;

        private readonly List<InvalidActionAttemptLog> _invalidLogs = new List<InvalidActionAttemptLog>(32);
        private readonly List<ScenarioResult> _scenarioResults = new List<ScenarioResult>(8);

        private sealed class ScenarioFailureException : Exception
        {
            public ScenarioFailureException(string message) : base(message) { }
        }

        private sealed class ScenarioExecution
        {
            private readonly List<string> _notes = new List<string>(4);

            public ScenarioExecution(string name)
            {
                Name = name;
            }

            public string Name { get; }
            public bool UsedFallback { get; private set; }
            public IReadOnlyList<string> Notes => _notes;

            public void MarkPrepared(string note)
            {
                if (!string.IsNullOrWhiteSpace(note))
                {
                    _notes.Add($"prepared:{note}");
                }
            }

            public void MarkFallback(string note)
            {
                UsedFallback = true;
                if (!string.IsNullOrWhiteSpace(note))
                {
                    _notes.Add($"fallback:{note}");
                }
            }
        }

        private readonly struct ScenarioResult
        {
            public ScenarioResult(string name, bool passed, bool usedFallback, string details)
            {
                Name = name;
                Passed = passed;
                UsedFallback = usedFallback;
                Details = details;
            }

            public string Name { get; }
            public bool Passed { get; }
            public bool UsedFallback { get; }
            public string Details { get; }
        }

        private void Awake()
        {
            if (!_runOnAwake)
            {
                return;
            }

            ResolveReferences();
            RunTests();
        }

        [ContextMenu("Run Day6 Regression Smoke Suite")]
        private void RunFromInspectorContextMenu()
        {
            ResolveReferences();
            RunTests();
        }

        private void ResolveReferences()
        {
            _gridManager = GridManager.Instance;
            _unitRegistry = UnitRegistry.Instance;
            _matchManager = MatchManager.Instance;
            _matchBootstrap = MatchBootstrap.Instance;
            _resourceManager = ResourceManager.Instance;

            if (_gridManager == null || _unitRegistry == null || _matchManager == null)
            {
                Debug.LogError("[Day6PipelineSmokeTest] Missing required scene references");
                return;
            }

            _observationBuilder = new ObservationBuilder(_gridManager, _unitRegistry, _resourceManager);
            _maskBuilder = new ActionMaskBuilder(_matchManager, _gridManager, _resourceManager, _unitRegistry, _matchBootstrap);
            _decoder = new ActionDecoder(_gridManager, _unitRegistry);
            _applier = new ActionApplier(_gridManager, _unitRegistry, _matchManager, _resourceManager);
            _applier.OnInvalidActionAttempt += OnInvalidActionAttempt;
        }

        private void OnDestroy()
        {
            if (_applier != null)
            {
                _applier.OnInvalidActionAttempt -= OnInvalidActionAttempt;
            }
        }

        private void OnInvalidActionAttempt(InvalidActionAttemptLog logEntry)
        {
            _invalidLogs.Add(logEntry);
            if (_verbose)
            {
                Debug.LogWarning($"[Day6PipelineSmokeTest] InvalidAttempt {logEntry.ToCompactString()}");
            }
        }

        private void RunTests()
        {
            _scenarioResults.Clear();

            Debug.Log("[Day6PipelineSmokeTest] ===== Starting Day 6 Regression Smoke Suite =====");

            RunIsolated(TestMoveScenario, "Day6 Test 1 Move");
            RunIsolated(TestHarvestReturnScenario, "Day6 Test 2 HarvestReturn");
            RunIsolated(TestAttackScenario, "Day6 Test 3 Attack");
            RunIsolated(TestProductionScenario, "Day6 Test 4 Production");
            RunIsolated(TestInvalidFallbackScenario, "Day6 Test 5 InvalidFallback");

            int failed = 0;
            int fallbackOnly = 0;
            for (int i = 0; i < _scenarioResults.Count; i++)
            {
                ScenarioResult result = _scenarioResults[i];
                if (!result.Passed)
                {
                    failed++;
                }

                if (result.UsedFallback)
                {
                    fallbackOnly++;
                }

                string status = result.Passed ? "PASS" : "FAIL";
                string path = result.UsedFallback ? "fallback" : "prepared";
                Debug.Log($"[Day6PipelineSmokeTest] [{status}] {result.Name} path={path} details={result.Details}");
            }

            Debug.Log($"[Day6PipelineSmokeTest] Invalid attempts logged: {_invalidLogs.Count}");
            Debug.Log($"[Day6PipelineSmokeTest] Scenarios with fallback setup: {fallbackOnly}/{_scenarioResults.Count}");

            if (failed > 0)
            {
                string message = $"Day 6 regression smoke suite FAILED ({failed}/{_scenarioResults.Count} scenarios).";
                Debug.LogError($"[Day6PipelineSmokeTest] {message}");
                if (_throwOnSuiteFailure)
                {
                    throw new InvalidOperationException(message);
                }
            }

            Debug.Log("[Day6PipelineSmokeTest] ===== Day 6 Regression Smoke Suite Completed =====");
        }

        private void RunIsolated(Action<ScenarioExecution> testMethod, string label)
        {
            if (!ResetEpisodeAndResolve(label))
            {
                TrackScenarioResult(label, false, false, "missing runtime dependencies");
                return;
            }

            _invalidLogs.Clear();
            ScenarioExecution scenario = new ScenarioExecution(label);

            try
            {
                testMethod(scenario);
                TrackScenarioResult(label, true, scenario.UsedFallback, ComposeScenarioDetails(scenario));
            }
            catch (ScenarioFailureException ex)
            {
                Debug.LogError($"[Day6PipelineSmokeTest] {label} failed: {ex.Message}");
                TrackScenarioResult(label, false, scenario.UsedFallback, ComposeScenarioDetails(scenario, ex.Message));
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
                TrackScenarioResult(label, false, scenario.UsedFallback, ComposeScenarioDetails(scenario, ex.Message));
            }
        }

        private bool ResetEpisodeAndResolve(string label)
        {
            EpisodeController episodeController = EpisodeController.Instance;
            if (episodeController != null)
            {
                episodeController.ResetEpisode();
            }
            else
            {
                Debug.LogWarning($"[Day6PipelineSmokeTest] {label}: EpisodeController not found, running without explicit reset");
            }

            ResolveReferences();
            return _gridManager != null
                   && _unitRegistry != null
                   && _matchManager != null
                   && _observationBuilder != null
                   && _maskBuilder != null
                   && _decoder != null
                   && _applier != null;
        }

        private void TestMoveScenario(ScenarioExecution scenario)
        {
            PipelineSnapshot snapshot = BuildPipelineSnapshot(_playerUnderTest);
            Require(snapshot.ObservationValid, "Observation validation failed before move scenario");

            UnitRuntime actor = FindFirstActorWithAction(snapshot.TransferMask, _playerUnderTest, UnitActionType.Move);
            Require(actor != null, "No actor with Move in mask");
            scenario.MarkPrepared("move actor selected from prepared scene state");

            RequireObservationFriendlyActor(snapshot, actor, "move actor should be friendly in observation");

            ActorActionMask actorMask = snapshot.TransferMask.GetActorMask(actor.GridPos);
            Require(actorMask != null, "Move actor mask is missing");
            Require(TryFindEnabledDirection(actorMask.MoveDirectionMask, out Direction validDir), "No valid move direction in mask");

            GridPosition start = actor.GridPos;
            GridPosition expected = start.Neighbour(validDir);
            RequireObservationCellHasNoFriendlyClaim(snapshot, expected, "move target cell should not claim friendly occupancy before move");

            bool validApplied = ApplyDebugAction(snapshot.TransferMask, _playerUnderTest, actor.GridPos.ToFlatIndex(), ActionContract.ACTION_MOVE, (int)validDir, (int)ProducibleUnit.Worker, 4, "debug");
            Require(validApplied, "Valid move action was rejected before step execution");

            _matchManager.StepMatch();

            UnitRuntime moved = _gridManager.GetOccupant(expected);
            Require(moved != null && moved.Owner == _playerUnderTest, "Move command did not change state as expected");

            if (TryFindDisabledDirection(actorMask.MoveDirectionMask, out Direction invalidDir))
            {
                PipelineSnapshot invalidSnapshot = BuildPipelineSnapshot(_playerUnderTest);
                bool invalidApplied = ApplyDebugAction(invalidSnapshot.TransferMask, _playerUnderTest, moved.GridPos.ToFlatIndex(), ActionContract.ACTION_MOVE, (int)invalidDir, (int)ProducibleUnit.Worker, 4, "debug");
                Require(!invalidApplied, "Invalid move direction unexpectedly accepted");
                Require(_applier.RejectionReasonsLastStep.Count > 0, "Invalid move rejection reason is missing");
            }
        }

        private void TestHarvestReturnScenario(ScenarioExecution scenario)
        {
            bool readyHarvest = TryEnsureWorkerWithAdjacentResource(scenario, _playerUnderTest, out UnitRuntime worker, out Direction harvestDirection, out GridPosition resourcePos);
            Require(readyHarvest, "Cannot prepare worker/resource setup");

            worker.DropAllCarriedResources();

            PipelineSnapshot harvestSnapshot = BuildPipelineSnapshot(_playerUnderTest);
            Require(IsActionAllowedByMask(harvestSnapshot.TransferMask, worker.GridPos, UnitActionType.Harvest), "Harvest is not enabled by mask for prepared worker");
            RequireObservationFriendlyActor(harvestSnapshot, worker, "harvest actor should be friendly in observation");
            RequireObservationResourceSignal(harvestSnapshot, resourcePos, "resource-adjacent harvest scenario should be reflected in observation");

            bool harvestApplied = ApplyDebugAction(harvestSnapshot.TransferMask, _playerUnderTest, worker.GridPos.ToFlatIndex(), ActionContract.ACTION_HARVEST, (int)harvestDirection, (int)ProducibleUnit.Worker, 4, "debug");
            Require(harvestApplied, "Valid harvest action was rejected");

            _matchManager.StepMatch();
            Require(worker.CarriedResources > 0, "Harvest did not increase carried resources");

            worker.DropAllCarriedResources();
            PipelineSnapshot invalidReturnSnapshot = BuildPipelineSnapshot(_playerUnderTest);
            bool invalidReturnApplied = ApplyDebugAction(invalidReturnSnapshot.TransferMask, _playerUnderTest, worker.GridPos.ToFlatIndex(), ActionContract.ACTION_RETURN, (int)Direction.North, (int)ProducibleUnit.Worker, 4, "debug");
            Require(!invalidReturnApplied, "Return with empty carry unexpectedly accepted");
            Require(_applier.RejectionReasonsLastStep.Count > 0, "Return-with-empty-carry rejection reason is missing");

            bool readyReturn = TryEnsureWorkerWithAdjacentBase(scenario, _playerUnderTest, out UnitRuntime workerNearBase, out Direction returnDirection, out GridPosition basePos);
            Require(readyReturn, "Cannot prepare worker/base setup for valid return");

            int resourcesBefore = _matchManager.GetResources(_playerUnderTest);
            workerNearBase.DropAllCarriedResources();
            workerNearBase.AddCarriedResources(10);

            PipelineSnapshot returnSnapshot = BuildPipelineSnapshot(_playerUnderTest);
            Require(IsActionAllowedByMask(returnSnapshot.TransferMask, workerNearBase.GridPos, UnitActionType.Return), "Return is not enabled by mask for loaded worker");
            RequireObservationFriendlyActor(returnSnapshot, workerNearBase, "return actor should be friendly in observation");
            RequireObservationFriendlyBase(returnSnapshot, basePos, "adjacent base should be represented as friendly base in observation");

            bool returnApplied = ApplyDebugAction(returnSnapshot.TransferMask, _playerUnderTest, workerNearBase.GridPos.ToFlatIndex(), ActionContract.ACTION_RETURN, (int)returnDirection, (int)ProducibleUnit.Worker, 4, "debug");
            Require(returnApplied, "Valid return action was rejected");

            _matchManager.StepMatch();
            int resourcesAfter = _matchManager.GetResources(_playerUnderTest);
            Require(resourcesAfter > resourcesBefore && workerNearBase.CarriedResources == 0, "Return did not deposit resources as expected");
        }

        private void TestAttackScenario(ScenarioExecution scenario)
        {
            bool readyAttack = TryEnsureAdjacentEnemies(scenario, out UnitRuntime attacker, out UnitRuntime target);
            Require(readyAttack, "Cannot prepare attacker/target setup");

            PipelineSnapshot snapshot = BuildPipelineSnapshot(_playerUnderTest);
            RequireObservationFriendlyActor(snapshot, attacker, "attacker should be friendly in observation");
            RequireObservationEnemyPresence(snapshot, target.GridPos, "attack target cell should indicate enemy presence in observation");

            int attackLocal = AttackLocalIndex(attacker.GridPos, target.GridPos);
            Require(IsActionAllowedByMask(snapshot.TransferMask, attacker.GridPos, UnitActionType.Attack), "Attack not enabled by mask for attacker");

            int targetHpBefore = target.HP;
            bool attackApplied = ApplyDebugAction(snapshot.TransferMask, _playerUnderTest, attacker.GridPos.ToFlatIndex(), ActionContract.ACTION_ATTACK, (int)Direction.North, (int)ProducibleUnit.Worker, attackLocal, "debug");
            Require(attackApplied, "Valid attack command rejected before runtime step");

            _matchManager.StepMatch();
            bool targetDamagedOrDead = target == null || !target.IsAlive || target.HP < targetHpBefore;
            Require(targetDamagedOrDead, "Attack pipeline command did not produce runtime combat effect");

            // Limitation marker: this validates command submission + runtime combat effect.
            // It does not prove strict target-preserving semantics because CombatResolver currently applies automatic targeting.
            Debug.Log("[Day6PipelineSmokeTest] NOTE: Attack scenario validates pipeline submission plus combat effect, not strict target-preserving end-to-end semantics.");

            PipelineSnapshot invalidSnapshot = BuildPipelineSnapshot(_playerUnderTest);
            bool invalidAttackApplied = ApplyDebugAction(invalidSnapshot.TransferMask, _playerUnderTest, attacker.GridPos.ToFlatIndex(), ActionContract.ACTION_ATTACK, (int)Direction.North, (int)ProducibleUnit.Worker, 4, "debug");
            Require(!invalidAttackApplied, "Invalid self-target attack unexpectedly accepted");
            Require(_applier.RejectionReasonsLastStep.Count > 0, "Invalid attack rejection reason is missing");
        }

        private void TestProductionScenario(ScenarioExecution scenario)
        {
            UnitRuntime building = FindFirstActorWithAction(BuildPipelineSnapshot(_playerUnderTest).TransferMask, _playerUnderTest, UnitActionType.Produce);
            if (building == null)
            {
                scenario.MarkFallback("no producible building in prepared state; reconstructing with spawned base+runtime");
                Require(TrySpawnBuildingWithRuntime(_playerUnderTest, out building), "Cannot construct fallback building for production scenario");
            }
            else
            {
                scenario.MarkPrepared("production actor found in prepared state");
            }

            _matchManager.AddResources(_playerUnderTest, 1000);

            PipelineSnapshot snapshot = BuildPipelineSnapshot(_playerUnderTest);
            ActorActionMask actorMask = snapshot.TransferMask.GetActorMask(building.GridPos);
            Require(actorMask != null, "Production actor mask missing");
            Require(TryFindEnabledDirection(actorMask.ProduceDirectionMask, out Direction produceDir), "No produce direction enabled by mask");
            Require(TryFindEnabledProduceType(actorMask.ProduceUnitTypeMask, out ProducibleUnit produceType), "No produce unit type enabled by mask");

            RequireObservationFriendlyActor(snapshot, building, "production actor should be friendly in observation");

            bool produceApplied = ApplyDebugAction(snapshot.TransferMask, _playerUnderTest, building.GridPos.ToFlatIndex(), ActionContract.ACTION_PRODUCE, (int)produceDir, (int)produceType, 4, "debug");
            Require(produceApplied, "Valid produce action was rejected");

            _matchManager.StepMatch();

            BuildingRuntime runtime = building.GetComponent<BuildingRuntime>();
            ProductionQueue queue = runtime != null ? runtime.GetProductionQueue() : null;
            Require(queue != null && queue.IsProducing, "Production queue did not start after accepted produce command");

            PipelineSnapshot busySnapshot = BuildPipelineSnapshot(_playerUnderTest);
            bool busyApplied = ApplyDebugAction(busySnapshot.TransferMask, _playerUnderTest, building.GridPos.ToFlatIndex(), ActionContract.ACTION_PRODUCE, (int)produceDir, (int)produceType, 4, "debug");
            Require(!busyApplied, "Produce command accepted while queue was busy");
            Require(_applier.RejectionReasonsLastStep.Count > 0, "Busy queue rejection reason is missing");
        }

        private void TestInvalidFallbackScenario(ScenarioExecution scenario)
        {
            scenario.MarkPrepared("invalid input and fallback checks do not require scene reconstruction");

            PipelineSnapshot snapshot = BuildPipelineSnapshot(_playerUnderTest);
            int stepBefore = _matchManager.Step;

            AgentAction invalidDecoded = _decoder.DecodeDebug(-1, ActionContract.ACTION_MOVE, ActionContract.DIR_NORTH, (int)ProducibleUnit.Worker, 4);
            _applier.ResetDiagnostics();
            bool invalidApplied = _applier.ApplyAction(invalidDecoded, _playerUnderTest, snapshot.TransferMask, "debug");

            Require(!invalidApplied, "Decoder-invalid action unexpectedly accepted");
            Require(_applier.LastInvalidAttempt.HasValue, "Invalid attempt log is missing for invalid actor index");
            Require(_applier.LastInvalidAttempt.Value.Category == InvalidAttemptCategory.InvalidInput, "Invalid input category was not assigned for invalid actor index");

            AgentAction fallbackNoOp = _decoder.DecodeDebug(ActionContract.TotalCells, ActionContract.ACTION_NOOP, ActionContract.DIR_NORTH, (int)ProducibleUnit.Worker, 4);
            bool fallbackApplied = _applier.ApplyAction(fallbackNoOp, _playerUnderTest, snapshot.TransferMask, "debug");
            _matchManager.StepMatch();

            Require(fallbackApplied, "Explicit fallback NoOp should always be accepted");
            Require(_matchManager.Step == stepBefore + 1, "Fallback NoOp path broke normal step progression");
        }

        private PipelineSnapshot BuildPipelineSnapshot(Owner player)
        {
            float[] observation = _observationBuilder.BuildObservation(player, ObservationMode.UnityMvpTransfer);
            ObservationValidationResult validation = _observationBuilder.ValidateObservation(observation);
            ActionMaskSet transferMask = _maskBuilder.BuildTransferCompatibleMask(player);
            return new PipelineSnapshot(observation, validation.IsValid, validation, transferMask);
        }

        private bool ApplyDebugAction(ActionMaskSet transferMask, Owner player, int actorIndexFlat, int actionType, int direction, int produceType, int attackLocal, string sourceFormat)
        {
            AgentAction decoded = _decoder.DecodeDebug(actorIndexFlat, actionType, direction, produceType, attackLocal);
            _applier.ResetDiagnostics();
            bool accepted = _applier.ApplyAction(decoded, player, transferMask, sourceFormat);

            if (_verbose)
            {
                string firstReason = _applier.RejectionReasonsLastStep.Count > 0 ? _applier.RejectionReasonsLastStep[0] : "none";
                Debug.Log($"[Day6PipelineSmokeTest] apply source={sourceFormat}, accepted={accepted}, action={decoded.ActionType}, actor={decoded.ActorPosition}, reason={firstReason}");
            }

            return accepted;
        }

        private UnitRuntime FindFirstActorWithAction(ActionMaskSet mask, Owner owner, UnitActionType actionType)
        {
            if (mask == null)
            {
                return null;
            }

            for (int i = 0; i < ActionContract.TotalCells; i++)
            {
                if (!mask.ActorCellMask[i])
                {
                    continue;
                }

                ActorActionMask actorMask = mask.GetActorMaskByFlatIndex(i);
                if (actorMask == null || !actorMask.IsActionTypeEnabled(actionType))
                {
                    continue;
                }

                UnitRuntime actor = _gridManager.GetOccupant(GridPosition.FromFlatIndex(i));
                if (actor != null && actor.Owner == owner && actor.IsAlive)
                {
                    return actor;
                }
            }

            return null;
        }

        private bool IsActionAllowedByMask(ActionMaskSet mask, GridPosition actorPos, UnitActionType actionType)
        {
            ActorActionMask actorMask = mask != null ? mask.GetActorMask(actorPos) : null;
            return actorMask != null && actorMask.IsActionTypeEnabled(actionType);
        }

        private bool TryEnsureWorkerWithAdjacentResource(ScenarioExecution scenario, Owner owner, out UnitRuntime worker, out Direction dirToResource, out GridPosition resourcePos)
        {
            worker = null;
            dirToResource = Direction.North;
            resourcePos = GridPosition.Zero;

            IReadOnlyList<UnitRuntime> units = _unitRegistry.GetAllUnits();
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit == null || !unit.IsAlive || unit.Owner != owner || unit.Type != UnitType.Worker)
                {
                    continue;
                }

                for (int d = 0; d < ActionContract.SIZE_DIRECTION; d++)
                {
                    Direction dir = (Direction)d;
                    GridPosition near = unit.GridPos.Neighbour(dir);
                    ResourceNode node = _resourceManager != null ? _resourceManager.GetResourceNode(near) : null;
                    if (node != null && !node.IsExhausted)
                    {
                        worker = unit;
                        dirToResource = dir;
                        resourcePos = near;
                        scenario.MarkPrepared("worker+resource relation exists in prepared state");
                        return true;
                    }
                }
            }

            if (!FindFreeAdjacentPair(out GridPosition workerPos, out GridPosition spawnedResourcePos))
            {
                return false;
            }

            if (!TrySpawnUnit(UnitType.Worker, owner, workerPos, out worker))
            {
                return false;
            }

            _resourceManager?.RegisterResourceNode(new ResourceNode(spawnedResourcePos, 20));
            dirToResource = DirectionFromTo(workerPos, spawnedResourcePos);
            resourcePos = spawnedResourcePos;
            scenario.MarkFallback("worker/resource relation reconstructed via spawn+resource node registration");
            return true;
        }

        private bool TryEnsureWorkerWithAdjacentBase(ScenarioExecution scenario, Owner owner, out UnitRuntime worker, out Direction dirToBase, out GridPosition basePos)
        {
            worker = null;
            dirToBase = Direction.North;
            basePos = GridPosition.Zero;

            IReadOnlyList<UnitRuntime> units = _unitRegistry.GetAllUnits();
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit == null || !unit.IsAlive || unit.Owner != owner || unit.Type != UnitType.Worker)
                {
                    continue;
                }

                for (int d = 0; d < ActionContract.SIZE_DIRECTION; d++)
                {
                    Direction dir = (Direction)d;
                    GridPosition near = unit.GridPos.Neighbour(dir);
                    UnitRuntime target = _gridManager.GetOccupant(near);
                    if (target != null && target.Owner == owner && target.Type == UnitType.Base)
                    {
                        worker = unit;
                        dirToBase = dir;
                        basePos = near;
                        scenario.MarkPrepared("worker+base relation exists in prepared state");
                        return true;
                    }
                }
            }

            if (!FindFreeAdjacentPair(out GridPosition spawnedBasePos, out GridPosition workerPos))
            {
                return false;
            }

            if (!TrySpawnUnit(UnitType.Base, owner, spawnedBasePos, out _))
            {
                return false;
            }

            if (!TrySpawnUnit(UnitType.Worker, owner, workerPos, out worker))
            {
                return false;
            }

            dirToBase = DirectionFromTo(workerPos, spawnedBasePos);
            basePos = spawnedBasePos;
            scenario.MarkFallback("worker/base relation reconstructed via spawn helpers");
            return true;
        }

        private bool TryEnsureAdjacentEnemies(ScenarioExecution scenario, out UnitRuntime attacker, out UnitRuntime target)
        {
            attacker = null;
            target = null;

            IReadOnlyList<UnitRuntime> units = _unitRegistry.GetAllUnits();
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime candidate = units[i];
                if (candidate == null || !candidate.IsAlive || candidate.Owner != _playerUnderTest)
                {
                    continue;
                }

                for (int d = 0; d < ActionContract.SIZE_DIRECTION; d++)
                {
                    GridPosition near = candidate.GridPos.Neighbour((Direction)d);
                    UnitRuntime enemy = _gridManager.GetOccupant(near);
                    if (enemy != null && enemy.IsAlive && enemy.Owner != _playerUnderTest && enemy.Owner != Owner.Neutral)
                    {
                        attacker = candidate;
                        target = enemy;
                        scenario.MarkPrepared("adjacent enemies exist in prepared state");
                        return true;
                    }
                }
            }

            UnitDefinition lightDef = _matchBootstrap != null && _matchBootstrap.GetConfig() != null
                ? _matchBootstrap.GetConfig().GetDefinition(UnitType.Light)
                : null;

            UnitType attackerType = lightDef != null ? UnitType.Light : UnitType.Worker;

            if (!FindFreeAdjacentPair(out GridPosition attackerPos, out GridPosition targetPos))
            {
                return false;
            }

            if (!TrySpawnUnit(attackerType, _playerUnderTest, attackerPos, out attacker))
            {
                return false;
            }

            Owner enemyOwner = _playerUnderTest == Owner.Player1 ? Owner.Player2 : Owner.Player1;
            if (!TrySpawnUnit(UnitType.Worker, enemyOwner, targetPos, out target))
            {
                return false;
            }

            scenario.MarkFallback("adjacent enemies reconstructed via spawn helpers");
            return true;
        }

        private bool TrySpawnBuildingWithRuntime(Owner owner, out UnitRuntime building)
        {
            building = null;
            if (!FindFirstFreeCell(out GridPosition pos))
            {
                return false;
            }

            if (!TrySpawnUnit(UnitType.Base, owner, pos, out building))
            {
                return false;
            }

            if (building.GetComponent<BuildingRuntime>() == null)
            {
                building.gameObject.AddComponent<BuildingRuntime>();
            }

            return true;
        }

        private bool TrySpawnUnit(UnitType type, Owner owner, GridPosition pos, out UnitRuntime unit)
        {
            unit = null;
            if (_matchBootstrap == null)
            {
                return false;
            }

            GameConfig config = _matchBootstrap.GetConfig();
            if (config == null || config.GetDefinition(type) == null)
            {
                return false;
            }

            UnitFactory factory = new UnitFactory(config, _gridManager, null, _unitRegistry);
            unit = factory.Spawn(type, owner, pos);
            return unit != null;
        }

        private bool FindFirstFreeCell(out GridPosition position)
        {
            for (int y = 0; y < GameConstants.MapHeight; y++)
            {
                for (int x = 0; x < GameConstants.MapWidth; x++)
                {
                    GridPosition candidate = new GridPosition(x, y);
                    if (!_gridManager.IsCellOccupied(candidate))
                    {
                        position = candidate;
                        return true;
                    }
                }
            }

            position = GridPosition.Zero;
            return false;
        }

        private bool FindFreeAdjacentPair(out GridPosition first, out GridPosition second)
        {
            for (int y = 0; y < GameConstants.MapHeight; y++)
            {
                for (int x = 0; x < GameConstants.MapWidth; x++)
                {
                    GridPosition a = new GridPosition(x, y);
                    if (_gridManager.IsCellOccupied(a))
                    {
                        continue;
                    }

                    for (int d = 0; d < ActionContract.SIZE_DIRECTION; d++)
                    {
                        GridPosition b = a.Neighbour((Direction)d);
                        if (!_gridManager.IsInside(b) || _gridManager.IsCellOccupied(b))
                        {
                            continue;
                        }

                        first = a;
                        second = b;
                        return true;
                    }
                }
            }

            first = GridPosition.Zero;
            second = GridPosition.Zero;
            return false;
        }

        private static Direction DirectionFromTo(GridPosition from, GridPosition to)
        {
            int dx = to.X - from.X;
            int dy = to.Y - from.Y;

            if (dx == 1 && dy == 0) return Direction.East;
            if (dx == -1 && dy == 0) return Direction.West;
            if (dx == 0 && dy == 1) return Direction.North;
            return Direction.South;
        }

        private static bool TryFindEnabledDirection(bool[] mask, out Direction direction)
        {
            for (int i = 0; i < mask.Length; i++)
            {
                if (mask[i])
                {
                    direction = (Direction)i;
                    return true;
                }
            }

            direction = Direction.North;
            return false;
        }

        private static bool TryFindDisabledDirection(bool[] mask, out Direction direction)
        {
            for (int i = 0; i < mask.Length; i++)
            {
                if (!mask[i])
                {
                    direction = (Direction)i;
                    return true;
                }
            }

            direction = Direction.North;
            return false;
        }

        private static bool TryFindEnabledProduceType(bool[] mask, out ProducibleUnit unitType)
        {
            for (int i = 0; i < mask.Length; i++)
            {
                if (mask[i])
                {
                    unitType = (ProducibleUnit)i;
                    return true;
                }
            }

            unitType = ProducibleUnit.Worker;
            return false;
        }

        private static int AttackLocalIndex(GridPosition attacker, GridPosition target)
        {
            int dx = target.X - attacker.X;
            int dy = target.Y - attacker.Y;

            for (int i = 0; i < ActionContract.AttackOffsets.Length; i++)
            {
                var (odx, ody) = ActionContract.AttackOffsets[i];
                if (odx == dx && ody == dy)
                {
                    return i;
                }
            }

            return 4;
        }

        private void RequireObservationFriendlyActor(PipelineSnapshot snapshot, UnitRuntime actor, string message)
        {
            Require(actor != null, message + " (actor missing)");
            int baseIndex = ObservationContract.FlatIndex(actor.GridPos.Y, actor.GridPos.X, 0);
            float friendly = snapshot.Observation[baseIndex + ObservationContract.CH_OWNER_BASE + 1];
            Require(friendly > 0.5f, message);
        }

        private void RequireObservationResourceSignal(PipelineSnapshot snapshot, GridPosition pos, string message)
        {
            int baseIndex = ObservationContract.FlatIndex(pos.Y, pos.X, 0);
            float resource = snapshot.Observation[baseIndex + ObservationContract.CH_RESOURCES];
            Require(resource > 0f, message);
        }

        private void RequireObservationFriendlyBase(PipelineSnapshot snapshot, GridPosition basePos, string message)
        {
            int baseIndex = ObservationContract.FlatIndex(basePos.Y, basePos.X, 0);
            float friendly = snapshot.Observation[baseIndex + ObservationContract.CH_OWNER_BASE + 1];
            float baseType = snapshot.Observation[baseIndex + ObservationContract.CH_UNIT_TYPE_BASE + (int)UnitType.Base];
            Require(friendly > 0.5f && baseType > 0.5f, message);
        }

        private void RequireObservationEnemyPresence(PipelineSnapshot snapshot, GridPosition pos, string message)
        {
            int baseIndex = ObservationContract.FlatIndex(pos.Y, pos.X, 0);
            float enemy = snapshot.Observation[baseIndex + ObservationContract.CH_OWNER_BASE + 2];
            float tacticalEnemySignal = snapshot.Observation[baseIndex + ObservationContract.CH_ATTACK_TARGET];
            Require(enemy > 0.5f || tacticalEnemySignal > 0.5f, message);
        }

        private void RequireObservationCellHasNoFriendlyClaim(PipelineSnapshot snapshot, GridPosition pos, string message)
        {
            int baseIndex = ObservationContract.FlatIndex(pos.Y, pos.X, 0);
            float friendly = snapshot.Observation[baseIndex + ObservationContract.CH_OWNER_BASE + 1];
            Require(friendly < 0.5f, message);
        }

        private static void Require(bool condition, string message)
        {
            if (!condition)
            {
                throw new ScenarioFailureException(message);
            }
        }

        private static void Fail(string message)
        {
            throw new ScenarioFailureException(message);
        }

        private void TrackScenarioResult(string name, bool passed, bool usedFallback, string details)
        {
            _scenarioResults.Add(new ScenarioResult(name, passed, usedFallback, details));
        }

        private static string ComposeScenarioDetails(ScenarioExecution scenario, string failureMessage = null)
        {
            var sb = new StringBuilder(128);
            for (int i = 0; i < scenario.Notes.Count; i++)
            {
                if (i > 0)
                {
                    sb.Append(" | ");
                }

                sb.Append(scenario.Notes[i]);
            }

            if (!string.IsNullOrWhiteSpace(failureMessage))
            {
                if (sb.Length > 0)
                {
                    sb.Append(" | ");
                }

                sb.Append("failure:").Append(failureMessage);
            }

            return sb.Length > 0 ? sb.ToString() : "none";
        }

        private readonly struct PipelineSnapshot
        {
            public PipelineSnapshot(float[] observation, bool observationValid, ObservationValidationResult validation, ActionMaskSet transferMask)
            {
                Observation = observation;
                ObservationValid = observationValid;
                Validation = validation;
                TransferMask = transferMask;
            }

            public float[] Observation { get; }
            public bool ObservationValid { get; }
            public ObservationValidationResult Validation { get; }
            public ActionMaskSet TransferMask { get; }
        }
    }
}
