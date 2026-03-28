using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.ML
{
    /// <summary>
    /// Day 5 smoke/integration test for heuristic policy adapter pipeline.
    ///
    /// Purpose:
    /// - Verify observation/mask/debug-action/decoder/applier flow works without ML policy.
    /// - Verify heuristic is integration baseline, not reference semantics oracle.
    /// </summary>
    public class HeuristicPolicyAdapterSmokeTest : MonoBehaviour
    {
        [SerializeField] private bool _runOnAwake = true;
        [SerializeField] private bool _verboseLogs = true;

        private int _lastRunFrame = -1;

        private GridManager _gridManager;
        private UnitRegistry _unitRegistry;
        private MatchManager _matchManager;
        private MatchBootstrap _matchBootstrap;
        private ResourceManager _resourceManager;
        private HeuristicPolicyAdapter _adapter;

        private void Awake()
        {
            if (!_runOnAwake)
            {
                return;
            }

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
            _adapter = FindFirstObjectByType<HeuristicPolicyAdapter>();

            if (_adapter == null)
            {
                GameObject host = new GameObject("HeuristicPolicyAdapter");
                _adapter = host.AddComponent<HeuristicPolicyAdapter>();
            }

            _adapter.Initialize(_gridManager, _unitRegistry, _resourceManager, _matchManager, _matchBootstrap);
            _adapter.SetPlayerControlModes(HeuristicControlMode.Heuristic, HeuristicControlMode.Heuristic);
        }

        private void RunTests()
        {
            if (_lastRunFrame == Time.frameCount)
            {
                Debug.Log("[HeuristicPolicyAdapterSmokeTest] RunTests skipped: already executed in current frame.");
                return;
            }

            _lastRunFrame = Time.frameCount;
            Debug.Log("[HeuristicPolicyAdapterSmokeTest] ===== Starting Day 5 Heuristic Pipeline Smoke Tests =====");

            RunIsolated(TestWorkerHarvestViaPipeline, "Test 1");
            RunIsolated(TestWorkerReturnViaPipeline, "Test 2");
            RunIsolated(TestBuildingProduceViaPipeline, "Test 3");
            RunIsolated(TestCombatAttackOrMoveViaPipeline, "Test 4");
            RunIsolated(TestNoActorNoOpFallback, "Test 5");
            RunIsolated(TestShortEpisodeLoopWithoutMlPolicy, "Test 6");

            Debug.Log("[HeuristicPolicyAdapterSmokeTest] ===== Day 5 Smoke Tests Completed =====");
        }

        private void RunIsolated(System.Action testMethod, string testLabel)
        {
            if (!ResetEpisodeAndResolve(testLabel))
            {
                Debug.LogWarning($"[HeuristicPolicyAdapterSmokeTest] {testLabel}: skipped due to missing runtime dependencies");
                return;
            }

            testMethod();
        }

        private bool ResetEpisodeAndResolve(string testLabel)
        {
            EpisodeController episodeController = EpisodeController.Instance;
            if (episodeController != null)
            {
                episodeController.ResetEpisode();
            }
            else
            {
                Debug.LogWarning($"[HeuristicPolicyAdapterSmokeTest] {testLabel}: EpisodeController not found, running without episode reset");
            }

            ResolveReferences();
            return _gridManager != null
                   && _unitRegistry != null
                   && _matchManager != null
                   && _resourceManager != null
                   && _adapter != null;
        }

        private void TestWorkerHarvestViaPipeline()
        {
            if (!TryEnsureWorkerWithAdjacentResource(Owner.Player1, out UnitRuntime worker))
            {
                Debug.LogWarning("[HeuristicPolicyAdapterSmokeTest] Test 1: cannot prepare worker+resource setup");
                return;
            }

            worker.DropAllCarriedResources();
            HeuristicDecisionTrace trace = _adapter.DecideAndApplyForActor(Owner.Player1, worker.GridPos);

            bool selectedHarvest = trace.SelectedDebugAction.ActionType == ActionContract.ACTION_HARVEST;
            bool usedPipeline = trace.UsedPipeline && trace.DecodedAction.SourceType == ActionSourceType.Debug;

            Debug.Log($"[HeuristicPolicyAdapterSmokeTest] {(selectedHarvest ? "✓" : "✗")} worker selected Harvest via debug branches");
            Debug.Log($"[HeuristicPolicyAdapterSmokeTest] {(usedPipeline ? "✓" : "✗")} action passed through decoder/applier pipeline");
            LogTrace("Test 1", trace);
        }

        private void TestWorkerReturnViaPipeline()
        {
            if (!TryEnsureWorkerWithAdjacentBase(Owner.Player1, out UnitRuntime worker))
            {
                Debug.LogWarning("[HeuristicPolicyAdapterSmokeTest] Test 2: cannot prepare worker+base setup");
                return;
            }

            worker.DropAllCarriedResources();
            worker.AddCarriedResources(10);

            HeuristicDecisionTrace trace = _adapter.DecideAndApplyForActor(Owner.Player1, worker.GridPos);

            bool selectedReturn = trace.SelectedDebugAction.ActionType == ActionContract.ACTION_RETURN;
            bool acceptedOrQueued = trace.ActionAccepted;

            Debug.Log($"[HeuristicPolicyAdapterSmokeTest] {(selectedReturn ? "✓" : "✗")} worker selected Return when carrying cargo");
            Debug.Log($"[HeuristicPolicyAdapterSmokeTest] {(acceptedOrQueued ? "✓" : "✗")} return command accepted by ActionApplier/MatchManager gate");
            LogTrace("Test 2", trace);
        }

        private void TestBuildingProduceViaPipeline()
        {
            _matchManager.AddResources(Owner.Player1, 1000);

            UnitRuntime building = FindActorByMaskRule(Owner.Player1, UnitActionType.Produce);
            if (building == null && TrySpawnBuildingWithFreeCell(Owner.Player1, out building))
            {
                BuildingRuntime runtime = building.GetComponent<BuildingRuntime>();
                if (runtime == null)
                {
                    building.gameObject.AddComponent<BuildingRuntime>();
                }
            }

            if (building == null)
            {
                Debug.LogWarning("[HeuristicPolicyAdapterSmokeTest] Test 3: no producible building available");
                return;
            }

            HeuristicDecisionTrace trace = _adapter.DecideAndApplyForActor(Owner.Player1, building.GridPos);
            bool selectedProduce = trace.SelectedDebugAction.ActionType == ActionContract.ACTION_PRODUCE;

            Debug.Log($"[HeuristicPolicyAdapterSmokeTest] {(selectedProduce ? "✓" : "✗")} building selected Produce through debug action format");
            LogTrace("Test 3", trace);
        }

        private void TestCombatAttackOrMoveViaPipeline()
        {
            UnitRuntime combat = EnsureCombatActor(Owner.Player1);
            if (combat == null)
            {
                Debug.LogWarning("[HeuristicPolicyAdapterSmokeTest] Test 4: combat actor unavailable");
                return;
            }

            HeuristicDecisionTrace trace = _adapter.DecideAndApplyForActor(Owner.Player1, combat.GridPos);
            bool isAttackOrMove = trace.SelectedDebugAction.ActionType == ActionContract.ACTION_ATTACK
                               || trace.SelectedDebugAction.ActionType == ActionContract.ACTION_MOVE;

            Debug.Log($"[HeuristicPolicyAdapterSmokeTest] {(isAttackOrMove ? "✓" : "✗")} combat actor selected Attack or Move via pipeline");
            LogTrace("Test 4", trace);
        }

        private void TestNoActorNoOpFallback()
        {
            HeuristicDecisionTrace trace = _adapter.DecideAndApply(Owner.Neutral);

            bool selectedNoActor = trace.SelectedDebugAction.ActorIndexFlat == ActionContract.TotalCells;
            bool selectedNoOp = trace.SelectedDebugAction.ActionType == ActionContract.ACTION_NOOP;

            Debug.Log($"[HeuristicPolicyAdapterSmokeTest] {(selectedNoActor ? "✓" : "✗")} NoActor fallback selected for neutral player");
            Debug.Log($"[HeuristicPolicyAdapterSmokeTest] {(selectedNoOp ? "✓" : "✗")} NoOp fallback selected when no valid actor/actions");
            LogTrace("Test 5", trace);
        }

        private void TestShortEpisodeLoopWithoutMlPolicy()
        {
            int startStep = _matchManager.Step;
            int executedSteps = 0;

            _adapter.SetPlayerControlModes(HeuristicControlMode.Heuristic, HeuristicControlMode.Heuristic);

            for (int i = 0; i < 8; i++)
            {
                if (_matchManager.Phase != MatchPhase.Running)
                {
                    break;
                }

                HeuristicDecisionTrace p1 = _adapter.DecideAndApply(Owner.Player1);
                HeuristicDecisionTrace p2 = _adapter.DecideAndApply(Owner.Player2);

                if (_verboseLogs)
                {
                    LogTrace("Test 6 P1", p1);
                    LogTrace("Test 6 P2", p2);
                }

                _matchManager.StepMatch();
                executedSteps++;
            }

            bool progressed = _matchManager.Step > startStep;
            bool noCrashSignal = executedSteps > 0;

            Debug.Log($"[HeuristicPolicyAdapterSmokeTest] {(progressed ? "✓" : "✗")} episode progressed for {executedSteps} steps without ML policy");
            Debug.Log($"[HeuristicPolicyAdapterSmokeTest] {(noCrashSignal ? "✓" : "✗")} heuristic-vs-heuristic loop remained stable");
        }

        private void LogTrace(string label, HeuristicDecisionTrace trace)
        {
            if (!_verboseLogs)
            {
                return;
            }

            Debug.Log($"[HeuristicPolicyAdapterSmokeTest] {label}: {trace.BuildLogLine()}");
        }

        private bool TryEnsureWorkerWithAdjacentResource(Owner owner, out UnitRuntime worker)
        {
            worker = FindWorkerWithAdjacentResource(owner);
            if (worker != null)
            {
                return true;
            }

            if (!FindFreeAdjacentPair(out GridPosition workerPos, out GridPosition resourcePos))
            {
                return false;
            }

            if (!TrySpawnUnit(UnitType.Worker, owner, workerPos, out worker))
            {
                return false;
            }

            _resourceManager.RegisterResourceNode(new ResourceNode(resourcePos, 20));
            return true;
        }

        private bool TryEnsureWorkerWithAdjacentBase(Owner owner, out UnitRuntime worker)
        {
            worker = FindWorkerWithAdjacentBase(owner);
            if (worker != null)
            {
                return true;
            }

            if (!FindFreeAdjacentPair(out GridPosition basePos, out GridPosition workerPos))
            {
                return false;
            }

            if (!TrySpawnUnit(UnitType.Base, owner, basePos, out _))
            {
                return false;
            }

            if (!TrySpawnUnit(UnitType.Worker, owner, workerPos, out worker))
            {
                return false;
            }

            return true;
        }

        private UnitRuntime FindActorByMaskRule(Owner owner, UnitActionType desiredAction)
        {
            ActionMaskBuilder builder = new ActionMaskBuilder(_matchManager, _gridManager, _resourceManager, _unitRegistry, _matchBootstrap);
            ActionMaskSet mask = builder.BuildTransferCompatibleMask(owner);

            for (int i = 0; i < ActionContract.TotalCells; i++)
            {
                if (!mask.ActorCellMask[i])
                {
                    continue;
                }

                ActorActionMask actorMask = mask.GetActorMaskByFlatIndex(i);
                if (actorMask == null || !actorMask.IsActionTypeEnabled(desiredAction))
                {
                    continue;
                }

                GridPosition pos = GridPosition.FromFlatIndex(i);
                UnitRuntime actor = _gridManager.GetOccupant(pos);
                if (actor != null && actor.Owner == owner)
                {
                    return actor;
                }
            }

            return null;
        }

        private bool TrySpawnBuildingWithFreeCell(Owner owner, out UnitRuntime building)
        {
            building = null;
            if (!FindFirstFreeCell(out GridPosition buildingPos))
            {
                return false;
            }

            return TrySpawnUnit(UnitType.Base, owner, buildingPos, out building);
        }

        private UnitRuntime EnsureCombatActor(Owner owner)
        {
            UnitRuntime existing = FindCombatUnit(owner);
            if (existing != null)
            {
                return existing;
            }

            if (!FindFreeAdjacentPair(out GridPosition friendlyPos, out GridPosition enemyPos))
            {
                return null;
            }

            if (!TrySpawnUnit(UnitType.Light, owner, friendlyPos, out UnitRuntime combat))
            {
                return null;
            }

            Owner enemyOwner = owner == Owner.Player1 ? Owner.Player2 : Owner.Player1;
            TrySpawnUnit(UnitType.Worker, enemyOwner, enemyPos, out _);
            return combat;
        }

        private UnitRuntime FindWorkerWithAdjacentResource(Owner owner)
        {
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
                    GridPosition near = unit.GridPos.Neighbour((Direction)d);
                    ResourceNode node = _resourceManager.GetResourceNode(near);
                    if (node != null && !node.IsExhausted)
                    {
                        return unit;
                    }
                }
            }

            return null;
        }

        private UnitRuntime FindWorkerWithAdjacentBase(Owner owner)
        {
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
                    GridPosition near = unit.GridPos.Neighbour((Direction)d);
                    UnitRuntime target = _gridManager.GetOccupant(near);
                    if (target != null && target.Owner == owner && target.Type == UnitType.Base)
                    {
                        return unit;
                    }
                }
            }

            return null;
        }

        private UnitRuntime FindCombatUnit(Owner owner)
        {
            IReadOnlyList<UnitRuntime> units = _unitRegistry.GetAllUnits();
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit == null || !unit.IsAlive || unit.Owner != owner)
                {
                    continue;
                }

                if (unit.Type == UnitType.Light || unit.Type == UnitType.Heavy || unit.Type == UnitType.Ranged)
                {
                    return unit;
                }
            }

            return null;
        }

        private bool TrySpawnUnit(UnitType type, Owner owner, GridPosition position, out UnitRuntime unit)
        {
            unit = null;
            GameConfig config = _matchBootstrap != null ? _matchBootstrap.GetConfig() : null;
            if (config == null || !_gridManager.IsInside(position) || _gridManager.IsCellOccupied(position))
            {
                return false;
            }

            UnitFactory factory = new UnitFactory(config, _gridManager, _gridManager.transform, _unitRegistry);
            unit = factory.Spawn(type, owner, position);
            return unit != null;
        }

        private bool FindFreeAdjacentPair(out GridPosition a, out GridPosition b)
        {
            for (int y = 1; y < _gridManager.Height - 1; y++)
            {
                for (int x = 1; x < _gridManager.Width - 1; x++)
                {
                    GridPosition first = new GridPosition(x, y);
                    GridPosition second = new GridPosition(x + 1, y);

                    if (_gridManager.IsCellOccupied(first) || _gridManager.IsCellOccupied(second))
                    {
                        continue;
                    }

                    a = first;
                    b = second;
                    return true;
                }
            }

            a = GridPosition.Zero;
            b = GridPosition.Zero;
            return false;
        }

        private bool FindFirstFreeCell(out GridPosition pos)
        {
            for (int i = 0; i < ActionContract.TotalCells; i++)
            {
                GridPosition candidate = GridPosition.FromFlatIndex(i);
                if (_gridManager.IsInside(candidate) && !_gridManager.IsCellOccupied(candidate))
                {
                    pos = candidate;
                    return true;
                }
            }

            pos = GridPosition.Zero;
            return false;
        }
    }
}
