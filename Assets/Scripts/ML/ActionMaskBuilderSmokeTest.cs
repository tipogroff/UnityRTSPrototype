using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.ML
{
    /// <summary>
    /// Day 4 smoke test for invalid action masking.
    ///
    /// This verifies mask semantics, while authoritative runtime validation
    /// remains in ActionApplier.
    /// </summary>
    public class ActionMaskBuilderSmokeTest : MonoBehaviour
    {
        [SerializeField] private bool _runOnAwake = true;
        [SerializeField] private Owner _playerUnderTest = Owner.Player1;

        private GridManager _gridManager;
        private UnitRegistry _unitRegistry;
        private MatchManager _matchManager;
        private ResourceManager _resourceManager;
        private MatchBootstrap _matchBootstrap;

        private ActionMaskBuilder _maskBuilder;

        private void Awake()
        {
            if (!_runOnAwake)
                return;

            ResolveReferences();
            RunTests();
        }

        private void ResolveReferences()
        {
            _gridManager = FindFirstObjectByType<GridManager>();
            _unitRegistry = FindFirstObjectByType<UnitRegistry>();
            _matchManager = MatchManager.Instance;
            _resourceManager = ResourceManager.Instance;
            _matchBootstrap = MatchBootstrap.Instance;

            if (_gridManager == null || _unitRegistry == null || _matchManager == null)
            {
                Debug.LogError("[ActionMaskBuilderSmokeTest] Missing required scene components");
                return;
            }

            _maskBuilder = new ActionMaskBuilder(
                _matchManager,
                _gridManager,
                _resourceManager,
                _unitRegistry,
                _matchBootstrap);
        }

        private void RunTests()
        {
            Debug.Log("[ActionMaskBuilderSmokeTest] ===== Starting Day 4 Masking Smoke Tests =====");

            RunIsolated(TestActorMaskFriendlyVsEmpty, "Test 1");
            RunIsolated(TestMoveMaskFreeVsBlockedOrOutOfBounds, "Test 2");
            RunIsolated(TestBuildingDoesNotGetMoveMask, "Test 3");
            RunIsolated(TestHarvestMaskAdjacentResource, "Test 4");
            RunIsolated(TestReturnMaskWorkerWithCargoNearBase, "Test 5");
            RunIsolated(TestProduceMaskBuildingAndQueueGate, "Test 6");
            RunIsolated(TestProduceTypeMaskMatchesRuntimeSemantics, "Test 7");
            RunIsolated(TestAttackMaskMatchesRuntimeSemantics, "Test 8");
            RunIsolated(TestPhaseGateNotRunning, "Test 9");
            RunIsolated(TestMaskRuntimeConsistencyProbe, "Test 10");

            Debug.Log("[ActionMaskBuilderSmokeTest] ===== Day 4 Masking Smoke Tests Completed =====");
        }

        private void RunIsolated(System.Action testMethod, string testLabel)
        {
            if (!ResetEpisodeAndResolve(testLabel))
            {
                Debug.LogWarning($"[ActionMaskBuilderSmokeTest] {testLabel}: skipped due to missing dependencies");
                return;
            }

            testMethod();
        }

        private bool ResetEpisodeAndResolve(string testLabel)
        {
            var episodeController = EpisodeController.Instance;
            if (episodeController != null)
            {
                episodeController.ResetEpisode();
            }
            else
            {
                Debug.LogWarning($"[ActionMaskBuilderSmokeTest] {testLabel}: EpisodeController not found, no reset performed");
            }

            ResolveReferences();
            return _gridManager != null && _unitRegistry != null && _matchManager != null && _maskBuilder != null;
        }

        private void TestActorMaskFriendlyVsEmpty()
        {
            ActionMaskSet mask = _maskBuilder.BuildTransferCompatibleMask(_playerUnderTest);

            UnitRuntime friendly = FindFirstUnitByOwner(_playerUnderTest);
            GridPosition empty = FindFirstEmptyCell();

            bool friendlyEnabled = friendly != null && mask.ActorCellMask[friendly.GridPos.ToFlatIndex()];
            bool emptyDisabled = !mask.ActorCellMask[empty.ToFlatIndex()];

            Debug.Log($"[ActionMaskBuilderSmokeTest] {(friendlyEnabled ? "✓" : "✗")} actor mask enables friendly actor");
            Debug.Log($"[ActionMaskBuilderSmokeTest] {(emptyDisabled ? "✓" : "✗")} actor mask disables empty cell {empty}");
            Debug.Log(mask.BuildSummaryDump(4));
        }

        private void TestMoveMaskFreeVsBlockedOrOutOfBounds()
        {
            if (!TrySpawnUnit(UnitType.Worker, _playerUnderTest, new GridPosition(0, 0), out UnitRuntime worker))
            {
                Debug.LogWarning("[ActionMaskBuilderSmokeTest] Test 2: cannot spawn worker at (0,0), fallback to map actor");
                worker = FindFirstUnitByOwner(_playerUnderTest);
            }

            // Try to create a blocked direction deterministically for East.
            TrySpawnUnit(UnitType.Worker, _playerUnderTest, new GridPosition(1, 0), out _);

            ActionMaskSet mask = _maskBuilder.BuildTransferCompatibleMask(_playerUnderTest);
            ActorActionMask actorMask = worker != null ? mask.GetActorMask(worker.GridPos) : null;

            if (actorMask == null)
            {
                Debug.LogWarning("[ActionMaskBuilderSmokeTest] Test 2: no actor mask found");
                return;
            }

            bool northAllowed = actorMask.MoveDirectionMask[(int)Direction.North];
            bool eastAllowed = actorMask.MoveDirectionMask[(int)Direction.East];
            bool southAllowed = actorMask.MoveDirectionMask[(int)Direction.South];
            bool westAllowed = actorMask.MoveDirectionMask[(int)Direction.West];

            bool freeMoveExists = northAllowed || eastAllowed || southAllowed || westAllowed;
            bool blockedOrOobDetected = !southAllowed || !westAllowed || !eastAllowed;

            Debug.Log($"[ActionMaskBuilderSmokeTest] {(freeMoveExists ? "✓" : "✗")} move mask has at least one legal free direction");
            Debug.Log($"[ActionMaskBuilderSmokeTest] {(blockedOrOobDetected ? "✓" : "✗")} move mask blocks occupied or out-of-bounds direction");
        }

        private void TestBuildingDoesNotGetMoveMask()
        {
            if (!TrySpawnUnit(UnitType.Base, _playerUnderTest, new GridPosition(5, 5), out UnitRuntime building))
            {
                building = FindFirstBuildingByOwner(_playerUnderTest);
                if (building == null)
                {
                    Debug.LogWarning("[ActionMaskBuilderSmokeTest] Test 3: no building available");
                    return;
                }
            }

            ActionMaskSet mask = _maskBuilder.BuildTransferCompatibleMask(_playerUnderTest);
            ActorActionMask actorMask = mask.GetActorMask(building.GridPos);

            bool moveDisabled = actorMask != null && !actorMask.IsActionTypeEnabled(UnitActionType.Move);
            Debug.Log($"[ActionMaskBuilderSmokeTest] {(moveDisabled ? "✓" : "✗")} building does not receive Move mask");
        }

        private void TestHarvestMaskAdjacentResource()
        {
            if (!FindFreeAdjacentPair(out GridPosition workerPos, out GridPosition resourcePos))
            {
                Debug.LogWarning("[ActionMaskBuilderSmokeTest] Test 3: no free adjacent pair found");
                return;
            }

            if (!TrySpawnUnit(UnitType.Worker, _playerUnderTest, workerPos, out UnitRuntime worker))
            {
                Debug.LogWarning("[ActionMaskBuilderSmokeTest] Test 3: failed to spawn worker");
                return;
            }

            _resourceManager?.RegisterResourceNode(new ResourceNode(resourcePos, 20));

            ActionMaskSet mask = _maskBuilder.BuildTransferCompatibleMask(_playerUnderTest);
            ActorActionMask actorMask = mask.GetActorMask(worker.GridPos);

            Direction dirToResource = DirectionFromTo(workerPos, resourcePos);
            bool harvestEnabled = actorMask != null &&
                                  actorMask.IsActionTypeEnabled(UnitActionType.Harvest) &&
                                  actorMask.HarvestDirectionMask[(int)dirToResource];

            Debug.Log($"[ActionMaskBuilderSmokeTest] {(harvestEnabled ? "✓" : "✗")} harvest mask enables adjacent resource direction ({dirToResource})");
        }

        private void TestReturnMaskWorkerWithCargoNearBase()
        {
            if (!FindFreeAdjacentPair(out GridPosition basePos, out GridPosition workerPos))
            {
                Debug.LogWarning("[ActionMaskBuilderSmokeTest] Test 4: no free adjacent pair found");
                return;
            }

            if (!TrySpawnUnit(UnitType.Base, _playerUnderTest, basePos, out _))
            {
                Debug.LogWarning("[ActionMaskBuilderSmokeTest] Test 4: failed to spawn base");
                return;
            }

            if (!TrySpawnUnit(UnitType.Worker, _playerUnderTest, workerPos, out UnitRuntime worker))
            {
                Debug.LogWarning("[ActionMaskBuilderSmokeTest] Test 4: failed to spawn worker");
                return;
            }

            worker.AddCarriedResources(10);

            ActionMaskSet mask = _maskBuilder.BuildTransferCompatibleMask(_playerUnderTest);
            ActorActionMask actorMask = mask.GetActorMask(worker.GridPos);

            Direction dirToBase = DirectionFromTo(workerPos, basePos);
            bool returnEnabled = actorMask != null &&
                                 actorMask.IsActionTypeEnabled(UnitActionType.Return) &&
                                 actorMask.ReturnDirectionMask[(int)dirToBase];

            Debug.Log($"[ActionMaskBuilderSmokeTest] {(returnEnabled ? "✓" : "✗")} return mask enables carried-worker return to adjacent base ({dirToBase})");
        }

        private void TestProduceMaskBuildingAndQueueGate()
        {
            if (!TrySpawnUnit(UnitType.Base, _playerUnderTest, new GridPosition(3, 3), out UnitRuntime building))
            {
                building = FindFirstBuildingByOwner(_playerUnderTest);
                if (building == null)
                {
                    Debug.LogWarning("[ActionMaskBuilderSmokeTest] Test 5: no building found");
                    return;
                }
            }

            _matchManager.AddResources(_playerUnderTest, 1000);

            ActionMaskSet freeMask = _maskBuilder.BuildTransferCompatibleMask(_playerUnderTest);
            ActorActionMask freeActorMask = freeMask.GetActorMask(building.GridPos);
            bool produceEnabledWhenFree = freeActorMask != null && freeActorMask.IsActionTypeEnabled(UnitActionType.Produce);
            Debug.Log($"[ActionMaskBuilderSmokeTest] {(produceEnabledWhenFree ? "✓" : "✗")} produce mask enabled for building with free queue and resources");

            BuildingRuntime buildingRuntime = building.GetComponent<BuildingRuntime>();
            if (buildingRuntime == null)
            {
                buildingRuntime = building.gameObject.AddComponent<BuildingRuntime>();
            }

            if (_matchBootstrap?.GetConfig() == null)
            {
                Debug.LogWarning("[ActionMaskBuilderSmokeTest] Test 5: missing GameConfig, queue-busy subtest skipped");
                return;
            }

            bool productionStarted = buildingRuntime.StartProducingUnit(UnitType.Worker, _matchBootstrap.GetConfig());
            if (!productionStarted)
            {
                Debug.LogWarning("[ActionMaskBuilderSmokeTest] Test 5: could not start production; queue-busy subtest skipped");
                return;
            }

            ActionMaskSet busyMask = _maskBuilder.BuildTransferCompatibleMask(_playerUnderTest);
            ActorActionMask busyActorMask = busyMask.GetActorMask(building.GridPos);
            bool produceDisabledWhenBusy = busyActorMask != null && !busyActorMask.IsActionTypeEnabled(UnitActionType.Produce);
            Debug.Log($"[ActionMaskBuilderSmokeTest] {(produceDisabledWhenBusy ? "✓" : "✗")} produce mask disabled when production queue is busy");
        }

        private void TestProduceTypeMaskMatchesRuntimeSemantics()
        {
            if (!TrySpawnUnit(UnitType.Base, _playerUnderTest, new GridPosition(7, 7), out UnitRuntime baseBuilding))
            {
                baseBuilding = FindFirstBuildingByType(_playerUnderTest, UnitType.Base);
            }

            if (!TrySpawnUnit(UnitType.Barracks, _playerUnderTest, new GridPosition(9, 7), out UnitRuntime barracksBuilding))
            {
                barracksBuilding = FindFirstBuildingByType(_playerUnderTest, UnitType.Barracks);
            }

            _matchManager.AddResources(_playerUnderTest, 2000);
            ActionMaskSet mask = _maskBuilder.BuildTransferCompatibleMask(_playerUnderTest);

            if (baseBuilding != null)
            {
                ActorActionMask baseMask = mask.GetActorMask(baseBuilding.GridPos);
                bool baseMatches = baseMask != null && ProduceTypeMaskMatchesExpected(baseBuilding, baseMask.ProduceUnitTypeMask);
                Debug.Log($"[ActionMaskBuilderSmokeTest] {(baseMatches ? "✓" : "✗")} Base produce type mask matches runtime semantics");
            }

            if (barracksBuilding != null)
            {
                ActorActionMask barracksMask = mask.GetActorMask(barracksBuilding.GridPos);
                bool barracksMatches = barracksMask != null && ProduceTypeMaskMatchesExpected(barracksBuilding, barracksMask.ProduceUnitTypeMask);
                Debug.Log($"[ActionMaskBuilderSmokeTest] {(barracksMatches ? "✓" : "✗")} Barracks produce type mask matches runtime semantics");
            }

            if (baseBuilding != null && barracksBuilding != null)
            {
                ActorActionMask baseMask = mask.GetActorMask(baseBuilding.GridPos);
                ActorActionMask barracksMask = mask.GetActorMask(barracksBuilding.GridPos);

                bool sameMask = baseMask != null && barracksMask != null &&
                                BoolArrayEquals(baseMask.ProduceUnitTypeMask, barracksMask.ProduceUnitTypeMask);

                Debug.Log($"[ActionMaskBuilderSmokeTest] {(sameMask ? "✓" : "✗")} Base/Barracks produce masks are equal (current runtime has no per-building produce-type split)");
            }
        }

        private void TestAttackMaskMatchesRuntimeSemantics()
        {
            if (!FindFreeAdjacentPair(out GridPosition attackerPos, out GridPosition enemyPos))
            {
                Debug.LogWarning("[ActionMaskBuilderSmokeTest] Test 8: no free adjacent pair found");
                return;
            }

            if (!TrySpawnUnit(UnitType.Worker, _playerUnderTest, attackerPos, out UnitRuntime attacker))
            {
                Debug.LogWarning("[ActionMaskBuilderSmokeTest] Test 8: failed to spawn attacker");
                return;
            }

            Owner enemyOwner = _playerUnderTest == Owner.Player1 ? Owner.Player2 : Owner.Player1;
            if (!TrySpawnUnit(UnitType.Worker, enemyOwner, enemyPos, out _))
            {
                Debug.LogWarning("[ActionMaskBuilderSmokeTest] Test 8: failed to spawn enemy target");
                return;
            }

            ActionMaskSet mask = _maskBuilder.BuildTransferCompatibleMask(_playerUnderTest);
            ActorActionMask actorMask = mask.GetActorMask(attacker.GridPos);
            int localIndex = AttackLocalIndex(attackerPos, enemyPos);

            UnitDefinition attackerDef = GetDefinition(attacker.Type);
            bool expectedCanAttack = attackerDef != null && attackerDef.attackDamage > 0 && attackerDef.attackRange > 0;
            bool attackEnabled = localIndex >= 0 && actorMask != null &&
                                 actorMask.IsActionTypeEnabled(UnitActionType.Attack) &&
                                 actorMask.AttackTargetLocalMask[localIndex];

            bool attackMatchesRuntime = attackEnabled == expectedCanAttack;

            Debug.Log($"[ActionMaskBuilderSmokeTest] {(attackMatchesRuntime ? "✓" : "✗")} attack mask follows runtime attack definition (damage/range > 0)");

            if (TrySpawnUnit(UnitType.Base, _playerUnderTest, new GridPosition(attackerPos.X + 2, attackerPos.Y), out UnitRuntime baseUnit) &&
                TrySpawnUnit(UnitType.Worker, enemyOwner, new GridPosition(attackerPos.X + 3, attackerPos.Y), out UnitRuntime baseEnemy))
            {
                UnitDefinition baseDef = GetDefinition(UnitType.Base);
                bool expectedBaseCanAttack = baseDef != null && baseDef.attackDamage > 0 && baseDef.attackRange > 0;

                ActionMaskSet baseMaskSet = _maskBuilder.BuildTransferCompatibleMask(_playerUnderTest);
                ActorActionMask baseMask = baseMaskSet.GetActorMask(baseUnit.GridPos);
                int baseLocal = AttackLocalIndex(baseUnit.GridPos, baseEnemy.GridPos);
                bool baseAttackEnabled = baseLocal >= 0 && baseMask != null &&
                                         baseMask.IsActionTypeEnabled(UnitActionType.Attack) &&
                                         baseMask.AttackTargetLocalMask[baseLocal];

                bool baseMatchesRuntime = baseAttackEnabled == expectedBaseCanAttack;
                Debug.Log($"[ActionMaskBuilderSmokeTest] {(baseMatchesRuntime ? "✓" : "✗")} base attack mask matches runtime attack definition");
            }
        }

        private void TestPhaseGateNotRunning()
        {
            _matchManager.ResetMatch();
            ActionMaskSet mask = _maskBuilder.BuildTransferCompatibleMask(_playerUnderTest, noOpOnlyWhenNotRunning: true);

            bool actorMaskEmpty = mask.AvailableActorCount == 0;
            bool phaseRecorded = !mask.IsMatchRunning && mask.NoOpOnlyDueToPhaseGate;

            Debug.Log($"[ActionMaskBuilderSmokeTest] {(actorMaskEmpty ? "✓" : "✗")} actor mask empty when match is not running");
            Debug.Log($"[ActionMaskBuilderSmokeTest] {(phaseRecorded ? "✓" : "✗")} phase gate metadata recorded in mask set");
        }

        private void TestMaskRuntimeConsistencyProbe()
        {
            ActionMaskSet mask = _maskBuilder.BuildTransferCompatibleMask(_playerUnderTest);
            var applier = new ActionApplier(_gridManager, _unitRegistry, _matchManager, _resourceManager);

            int checkedCount = 0;
            for (int i = 0; i < ActionContract.TotalCells && checkedCount < 12; i++)
            {
                if (!mask.ActorCellMask[i])
                    continue;

                ActorActionMask actorMask = mask.GetActorMaskByFlatIndex(i);
                if (actorMask == null)
                    continue;

                if (!TryCreateRepresentativeAction(actorMask, out AgentAction representative))
                    continue;

                applier.ResetDiagnostics();
                bool applied = applier.ApplyAction(representative, _playerUnderTest);
                if (!applied)
                {
                    string reason = applier.RejectionReasonsLastStep.Count > 0
                        ? applier.RejectionReasonsLastStep[0]
                        : "Unknown rejection";
                    mask.RecordValidationMismatch($"actor={actorMask.ActorPosition} action={representative.ActionType} reason={reason}");
                }

                checkedCount++;
            }

            Debug.Log(mask.BuildSummaryDump(6));
            Debug.Log($"[ActionMaskBuilderSmokeTest] Consistency probe checked={checkedCount}, mismatches={mask.ValidationMismatches.Count}");
            Debug.Log("[ActionMaskBuilderSmokeTest] Note: ActionApplier remains authoritative even when mask says action is valid.");
        }

        private bool TryCreateRepresentativeAction(ActorActionMask actorMask, out AgentAction action)
        {
            // Prefer non-NoOp actions to probe runtime consistency.
            if (actorMask.IsActionTypeEnabled(UnitActionType.Move) && TryFirstTrue(actorMask.MoveDirectionMask, out int moveDir))
            {
                action = new AgentAction(actorMask.ActorPosition, UnitActionType.Move, (Direction)moveDir);
                return true;
            }

            if (actorMask.IsActionTypeEnabled(UnitActionType.Harvest) && TryFirstTrue(actorMask.HarvestDirectionMask, out int harvestDir))
            {
                action = new AgentAction(actorMask.ActorPosition, UnitActionType.Harvest, (Direction)harvestDir);
                return true;
            }

            if (actorMask.IsActionTypeEnabled(UnitActionType.Return) && TryFirstTrue(actorMask.ReturnDirectionMask, out int returnDir))
            {
                action = new AgentAction(actorMask.ActorPosition, UnitActionType.Return, (Direction)returnDir);
                return true;
            }

            if (actorMask.IsActionTypeEnabled(UnitActionType.Produce) &&
                TryFirstTrue(actorMask.ProduceDirectionMask, out int produceDir) &&
                TryFirstTrue(actorMask.ProduceUnitTypeMask, out int produceType))
            {
                action = new AgentAction(
                    actorMask.ActorPosition,
                    UnitActionType.Produce,
                    (Direction)produceDir,
                    (ProducibleUnit)produceType);
                return true;
            }

            if (actorMask.IsActionTypeEnabled(UnitActionType.Attack) && TryFirstTrue(actorMask.AttackTargetLocalMask, out int attackLocal))
            {
                GridPosition target = LocalAttackToAbsolute(actorMask.ActorPosition, attackLocal);
                action = new AgentAction(
                    actorMask.ActorPosition,
                    UnitActionType.Attack,
                    Direction.North,
                    ProducibleUnit.Worker,
                    target);
                return true;
            }

            action = AgentAction.CreateNoOp(ActionSourceType.Debug);
            return false;
        }

        private static bool TryFirstTrue(bool[] mask, out int index)
        {
            for (int i = 0; i < mask.Length; i++)
            {
                if (mask[i])
                {
                    index = i;
                    return true;
                }
            }

            index = -1;
            return false;
        }

        private bool TrySpawnUnit(UnitType type, Owner owner, GridPosition position, out UnitRuntime unit)
        {
            unit = null;
            if (_matchBootstrap?.GetConfig() == null)
                return false;

            if (!_gridManager.IsInside(position) || _gridManager.IsCellOccupied(position))
                return false;

            var factory = new UnitFactory(_matchBootstrap.GetConfig(), _gridManager, _gridManager.transform, _unitRegistry);
            unit = factory.Spawn(type, owner, position);
            return unit != null;
        }

        private bool FindFreeAdjacentPair(out GridPosition a, out GridPosition b)
        {
            for (int y = 1; y < _gridManager.Height - 1; y++)
            {
                for (int x = 1; x < _gridManager.Width - 1; x++)
                {
                    var p = new GridPosition(x, y);
                    var right = new GridPosition(x + 1, y);

                    if (_gridManager.IsCellOccupied(p) || _gridManager.IsCellOccupied(right))
                        continue;

                    a = p;
                    b = right;
                    return true;
                }
            }

            a = GridPosition.Zero;
            b = GridPosition.Zero;
            return false;
        }

        private GridPosition FindFirstEmptyCell()
        {
            for (int i = 0; i < ActionContract.TotalCells; i++)
            {
                GridPosition position = GridPosition.FromFlatIndex(i);
                if (!_gridManager.IsCellOccupied(position))
                    return position;
            }

            return GridPosition.Zero;
        }

        private UnitRuntime FindFirstUnitByOwner(Owner owner)
        {
            List<UnitRuntime> units = _unitRegistry.GetUnitsByOwner(owner);
            return units.Count > 0 ? units[0] : null;
        }

        private UnitRuntime FindFirstBuildingByOwner(Owner owner)
        {
            List<UnitRuntime> buildings = _unitRegistry.GetBuildingsByOwner(owner);
            return buildings.Count > 0 ? buildings[0] : null;
        }

        private UnitRuntime FindFirstBuildingByType(Owner owner, UnitType buildingType)
        {
            List<UnitRuntime> buildings = _unitRegistry.GetBuildingsByOwner(owner);
            for (int i = 0; i < buildings.Count; i++)
            {
                if (buildings[i] != null && buildings[i].Type == buildingType)
                    return buildings[i];
            }

            return null;
        }

        private bool ProduceTypeMaskMatchesExpected(UnitRuntime building, bool[] produceMask)
        {
            if (building == null)
                return false;

            for (int i = 0; i < ActionContract.SIZE_PRODUCE_UNIT_TYPE; i++)
            {
                ProducibleUnit produceType = (ProducibleUnit)i;
                bool expected = IsProduceTypeExpectedByRuntime(building, produceType);
                if (produceMask[i] != expected)
                    return false;
            }

            return true;
        }

        private bool IsProduceTypeExpectedByRuntime(UnitRuntime building, ProducibleUnit produceType)
        {
            // Current runtime uses shared BuildingRuntime.StartProducingUnit() path for Base/Barracks.
            // A produce type is expected when mapped UnitDefinition exists and is affordable.
            UnitType buildingType = building.Type;
            if (buildingType != UnitType.Base && buildingType != UnitType.Barracks)
                return false;

            BuildingRuntime buildingRuntime = building.GetComponent<BuildingRuntime>();
            if (buildingRuntime == null)
                return false;

            ProductionQueue queue = buildingRuntime.GetProductionQueue();
            if (queue != null && queue.IsProducing)
                return false;

            if (!TryMapProducibleUnitType(produceType, out UnitType producedType))
                return false;

            UnitDefinition definition = GetDefinition(producedType);
            if (definition == null)
                return false;

            return _matchManager.GetResources(_playerUnderTest) >= definition.productionCost;
        }

        private static bool TryMapProducibleUnitType(ProducibleUnit produceType, out UnitType unitType)
        {
            unitType = produceType switch
            {
                ProducibleUnit.Worker => UnitType.Worker,
                ProducibleUnit.Light => UnitType.Light,
                ProducibleUnit.Heavy => UnitType.Heavy,
                ProducibleUnit.Ranged => UnitType.Ranged,
                _ => UnitType.Worker
            };

            return produceType == ProducibleUnit.Worker ||
                   produceType == ProducibleUnit.Light ||
                   produceType == ProducibleUnit.Heavy ||
                   produceType == ProducibleUnit.Ranged;
        }

        private UnitDefinition GetDefinition(UnitType unitType)
        {
            GameConfig config = _matchBootstrap != null ? _matchBootstrap.GetConfig() : null;
            return config != null ? config.GetDefinition(unitType) : null;
        }

        private static bool BoolArrayEquals(bool[] left, bool[] right)
        {
            if (left == null || right == null || left.Length != right.Length)
                return false;

            for (int i = 0; i < left.Length; i++)
            {
                if (left[i] != right[i])
                    return false;
            }

            return true;
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

        private static int AttackLocalIndex(GridPosition actor, GridPosition target)
        {
            int dx = target.X - actor.X;
            int dy = target.Y - actor.Y;

            for (int i = 0; i < ActionContract.AttackOffsets.Length; i++)
            {
                var (offsetX, offsetY) = ActionContract.AttackOffsets[i];
                if (offsetX == dx && offsetY == dy)
                    return i;
            }

            return -1;
        }

        private static GridPosition LocalAttackToAbsolute(GridPosition actor, int localIndex)
        {
            var (dx, dy) = ActionContract.AttackOffsets[localIndex];
            return new GridPosition(actor.X + dx, actor.Y + dy);
        }
    }
}
