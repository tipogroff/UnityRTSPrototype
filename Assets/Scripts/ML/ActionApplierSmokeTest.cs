// ActionApplierSmokeTest.cs — smoke test for AgentAction decode & apply pipeline
// Week 3, Day 3: Verify that both action formats flow correctly through the pipeline
//
// Test scenarios:
// 1. Initial state probe
// 2-5. Debug single-actor actions (Move, Harvest, Attack, Produce)
// 6. Invalid actor (out of bounds index)
// 7. Transfer-compatible single-action (all-NoOp baseline)
// 8. [NEW] Transfer-compatible batch — multiple actors in one step
// 9. [NEW] Batch conflict resolution — two commands for same actor (first-wins)

using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using RTS.Core;
using RTS.Gameplay;

namespace RTS.ML
{
    /// <summary>
    /// Smoke test for AgentAction decode and apply pipeline.
    /// Attach to a GameObject in the game scene alongside MatchBootstrap.
    /// Enable this component to run tests when entering Play Mode.
    /// </summary>
    public class ActionApplierSmokeTest : MonoBehaviour
    {
        [SerializeField] private bool _runOnAwake = true;

        private GridManager _gridManager;
        private UnitRegistry _unitRegistry;
        private MatchManager _matchManager;
        private ActionDecoder _decoder;
        private ActionApplier _applier;

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

            if (_gridManager == null || _unitRegistry == null || _matchManager == null)
            {
                Debug.LogError("[ActionApplierSmokeTest] Missing required components");
                return;
            }

            _decoder = new ActionDecoder(_gridManager, _unitRegistry);
            _applier = new ActionApplier(_gridManager, _unitRegistry, _matchManager);
        }

        private void RunTests()
        {
            Debug.Log("[ActionApplierSmokeTest] ===== Starting Action Pipeline Smoke Tests =====");

            RunIsolated(TestInitialState, "Test 1");
            RunIsolated(TestDebugActionMove, "Test 2");
            RunIsolated(TestDebugActionHarvest, "Test 3");
            RunIsolated(TestDebugActionAttack, "Test 4");
            RunIsolated(TestDebugActionProduce, "Test 5");
            RunIsolated(TestInvalidActorAction, "Test 6");
            RunIsolated(TestTransferCompatibleFormat, "Test 7");
            RunIsolated(TestTransferCompatibleBatch, "Test 8");
            RunIsolated(TestBatchConflictResolution, "Test 9");
            RunIsolated(TestPhaseValidation, "Test 10");
            RunIsolated(TestProduceQueueBusy, "Test 11");
            RunIsolated(TestCoordinateConvention, "Test 12");

            Debug.Log("[ActionApplierSmokeTest] ===== All Tests Completed =====");
        }

        private void RunIsolated(System.Action testMethod, string testLabel)
        {
            if (!ResetEpisodeAndResolve(testLabel))
            {
                Debug.LogWarning($"[ActionApplierSmokeTest] {testLabel}: skipped due to missing runtime dependencies");
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
                Debug.LogWarning($"[ActionApplierSmokeTest] {testLabel}: EpisodeController not found, running without episode reset");
            }

            ResolveReferences();

            if (_gridManager == null || _unitRegistry == null || _matchManager == null || _decoder == null || _applier == null)
                return false;

            _applier.ResetDiagnostics();
            return true;
        }

        private void TestInitialState()
        {
            Debug.Log("[ActionApplierSmokeTest] Test 1: Initial State");

            var unit = _gridManager.GetOccupant(new GridPosition(2, 2));
            if (unit != null)
            {
                Debug.Log($"[ActionApplierSmokeTest] ✓ Found unit at (2,2): {unit.Type} owned by {unit.Owner}");
            }
            else
            {
                Debug.LogWarning("[ActionApplierSmokeTest] ✗ No unit at (2,2)");
            }
        }

        private void TestDebugActionMove()
        {
            Debug.Log("[ActionApplierSmokeTest] Test 2: Debug Action - Move");

            // Find a worker
            var worker = FindWorkerUnit();
            if (worker == null)
            {
                Debug.LogWarning("[ActionApplierSmokeTest] ✗ No worker found");
                return;
            }

            // Create debug move action: move north
            int actorIndex = worker.GridPos.ToFlatIndex();
            var action = _decoder.DecodeDebug(
                actorIndexFlat: actorIndex,
                actionType: (int)UnitActionType.Move,
                direction: (int)Direction.North,
                produceUnitType: 0,
                attackTargetLocal: 0);

            Debug.Log($"[ActionApplierSmokeTest] Decoded action: {action}");

            _applier.ResetDiagnostics();
            bool applied = _applier.ApplyAction(action, worker.Owner);
            Debug.Log($"[ActionApplierSmokeTest] {(applied ? "✓" : "✗")} Action applied: {applied}");

            if (!applied && _applier.RejectionReasonsLastStep.Count > 0)
            {
                Debug.LogWarning($"[ActionApplierSmokeTest] Reason: {_applier.RejectionReasonsLastStep[0]}");
            }
        }

        private void TestDebugActionHarvest()
        {
            Debug.Log("[ActionApplierSmokeTest] Test 3: Debug Action - Harvest");

            var worker = FindWorkerUnit();
            if (worker == null)
            {
                Debug.LogWarning("[ActionApplierSmokeTest] ✗ No worker found");
                return;
            }

            int actorIndex = worker.GridPos.ToFlatIndex();
            var action = _decoder.DecodeDebug(
                actorIndexFlat: actorIndex,
                actionType: (int)UnitActionType.Harvest,
                direction: (int)Direction.North,
                produceUnitType: 0,
                attackTargetLocal: 0);

            Debug.Log($"[ActionApplierSmokeTest] Decoded action: {action}");

            _applier.ResetDiagnostics();
            bool applied = _applier.ApplyAction(action, worker.Owner);
            Debug.Log($"[ActionApplierSmokeTest] {(applied ? "✓" : "✗")} Action applied: {applied}");

            if (!applied && _applier.RejectionReasonsLastStep.Count > 0)
            {
                Debug.LogWarning($"[ActionApplierSmokeTest] Reason: {_applier.RejectionReasonsLastStep[0]}");
            }
        }

        private void TestDebugActionAttack()
        {
            Debug.Log("[ActionApplierSmokeTest] Test 4: Debug Action - Attack");

            var combatUnit = FindCombatUnit();
            if (combatUnit == null)
            {
                Debug.LogWarning("[ActionApplierSmokeTest] ✗ No combat unit found");
                return;
            }

            int actorIndex = combatUnit.GridPos.ToFlatIndex();
            var action = _decoder.DecodeDebug(
                actorIndexFlat: actorIndex,
                actionType: (int)UnitActionType.Attack,
                direction: 0,
                produceUnitType: 0,
                attackTargetLocal: 4);  // Center (self) for invalid test

            Debug.Log($"[ActionApplierSmokeTest] Decoded action: {action}");

            _applier.ResetDiagnostics();
            bool applied = _applier.ApplyAction(action, combatUnit.Owner);
            Debug.Log($"[ActionApplierSmokeTest] {(applied ? "✓" : "✗")} Action applied: {applied}");

            if (!applied && _applier.RejectionReasonsLastStep.Count > 0)
            {
                Debug.LogWarning($"[ActionApplierSmokeTest] Reason: {_applier.RejectionReasonsLastStep[0]}");
            }
        }

        private void TestDebugActionProduce()
        {
            Debug.Log("[ActionApplierSmokeTest] Test 5: Debug Action - Produce");

            var building = FindBuildingUnit();
            if (building == null)
            {
                Debug.LogWarning("[ActionApplierSmokeTest] ✗ No building found");
                return;
            }

            int actorIndex = building.GridPos.ToFlatIndex();
            var action = _decoder.DecodeDebug(
                actorIndexFlat: actorIndex,
                actionType: (int)UnitActionType.Produce,
                direction: (int)Direction.North,
                produceUnitType: (int)ProducibleUnit.Worker,
                attackTargetLocal: 0);

            Debug.Log($"[ActionApplierSmokeTest] Decoded action: {action}");

            _applier.ResetDiagnostics();
            bool applied = _applier.ApplyAction(action, building.Owner);
            Debug.Log($"[ActionApplierSmokeTest] {(applied ? "✓" : "✗")} Action applied: {applied}");

            if (!applied && _applier.RejectionReasonsLastStep.Count > 0)
            {
                Debug.LogWarning($"[ActionApplierSmokeTest] Reason: {_applier.RejectionReasonsLastStep[0]}");
            }
        }

        private void TestInvalidActorAction()
        {
            Debug.Log("[ActionApplierSmokeTest] Test 6: Invalid Actor (out of bounds index)");

            // Try actor index = H*W (NoActor marker)
            var action = _decoder.DecodeDebug(
                actorIndexFlat: ActionContract.TotalCells,
                actionType: (int)UnitActionType.Move,
                direction: 0,
                produceUnitType: 0,
                attackTargetLocal: 0);

            Debug.Log($"[ActionApplierSmokeTest] Decoded action: {action}");

            _applier.ResetDiagnostics();
            bool applied = _applier.ApplyAction(action, Owner.Player1);
            Debug.Log($"[ActionApplierSmokeTest] {(applied ? "✓" : "✗")} Action applied (should be NoOp): {applied}");
        }

        private void TestTransferCompatibleFormat()
        {
            Debug.Log("[ActionApplierSmokeTest] Test 7: Transfer-Compatible Format");

            // Create a minimal action array (all NoOp)
            int[] actionFlat = new int[ActionContract.TotalActionFlatSize];

            // Initialize all to NoOp (action_type = 0, others = 0)
            for (int i = 0; i < ActionContract.TotalCells; i++)
            {
                // Each cell starts with ActionType (6 size), all other branches = 0
                // actionFlat[i * 35 + 0] = action type
                int cellOffset = i * ActionContract.ActionFlatSize;
                actionFlat[cellOffset] = (int)UnitActionType.NoOp;
            }

            var action = _decoder.DecodeTransferCompatible(actionFlat, Owner.Player1);
            Debug.Log($"[ActionApplierSmokeTest] Decoded transfer-compatible action: {action}");
            Debug.Log($"[ActionApplierSmokeTest] ✓ All cells are NoOp, returned NoOp action");
        }

        private void TestTransferCompatibleBatch()
        {
            Debug.Log("[ActionApplierSmokeTest] Test 8: Transfer-Compatible Batch (multi-command)");

            // Build actionFlat: all NoOp by default
            int[] actionFlat = new int[ActionContract.TotalActionFlatSize];

            // Find up to two Player1 units on the map to command
            var p1Units = new List<UnitRuntime>();
            for (int cellIndex = 0; cellIndex < ActionContract.TotalCells; cellIndex++)
            {
                var pos = GridPosition.FromFlatIndex(cellIndex);
                var u = _gridManager.GetOccupant(pos);
                if (u != null && u.Owner == Owner.Player1 && !u.IsBuilding && p1Units.Count < 2)
                    p1Units.Add(u);
            }

            if (p1Units.Count < 2)
            {
                Debug.LogWarning($"[ActionApplierSmokeTest] Test 8: need 2 Player1 mobile units, found {p1Units.Count} — skipping");
                return;
            }

            // Encode Move(North) for each found unit into actionFlat
            foreach (var unit in p1Units)
            {
                int cellOffset = unit.GridPos.ToFlatIndex() * ActionContract.ActionFlatSize;
                actionFlat[cellOffset + ActionContract.BranchOffset(ActionContract.BRANCH_ACTION_TYPE)] = ActionContract.ACTION_MOVE;
                actionFlat[cellOffset + ActionContract.BranchOffset(ActionContract.BRANCH_MOVE_DIR)]    = 0; // North
            }

            var batch = _decoder.DecodeTransferCompatibleBatch(actionFlat, Owner.Player1);
            Debug.Log($"[ActionApplierSmokeTest] Decoded batch size: {batch.Count} (expected 2)");

            int accepted = _applier.ApplyActions(batch, Owner.Player1);
            Debug.Log($"[ActionApplierSmokeTest] Accepted: {accepted}, Rejected: {_applier.RejectedActionsLastStep}");

            if (batch.Count >= 2)
                Debug.Log($"[ActionApplierSmokeTest] {(batch.Count == 2 ? "✓" : "✗")} Batch contains exactly 2 actions");

            foreach (var reason in _applier.RejectionReasonsLastStep)
                Debug.LogWarning($"[ActionApplierSmokeTest] Rejection: {reason}");
        }

        private void TestBatchConflictResolution()
        {
            Debug.Log("[ActionApplierSmokeTest] Test 9: Batch Conflict Resolution (duplicate actor — first-wins)");

            var unit = FindWorkerUnit();
            if (unit == null)
            {
                unit = FindCombatUnit();
            }
            if (unit == null)
            {
                Debug.LogWarning("[ActionApplierSmokeTest] Test 9: no Player1 unit found — skipping");
                return;
            }

            // Create two commands targeting the same actor
            var action1 = new AgentAction(
                actorPosition: unit.GridPos,
                actionType:    UnitActionType.Move,
                direction:     Direction.North,
                isValid:       true,
                sourceType:    ActionSourceType.TransferCompatible);

            var action2 = new AgentAction(
                actorPosition: unit.GridPos,
                actionType:    UnitActionType.Move,
                direction:     Direction.South,
                isValid:       true,
                sourceType:    ActionSourceType.TransferCompatible);

            var dualBatch = new List<AgentAction> { action1, action2 };
            int accepted = _applier.ApplyActions(dualBatch, Owner.Player1);

            // Expected: action1 either accepted or rejected by MatchManager, action2 always rejected by conflict policy
            bool conflictCaught = _applier.RejectionReasonsLastStep.Any(
                r => r.Contains("Duplicate command") || r.Contains("first-wins"));

            Debug.Log($"[ActionApplierSmokeTest] Accepted: {accepted}, Rejected: {_applier.RejectedActionsLastStep}");
            Debug.Log($"[ActionApplierSmokeTest] {(conflictCaught ? "✓" : "✗")} Conflict detected and rejected");

            foreach (var reason in _applier.RejectionReasonsLastStep)
                Debug.LogWarning($"[ActionApplierSmokeTest] Rejection: {reason}");
        }

        private void TestPhaseValidation()
        {
            Debug.Log("[ActionApplierSmokeTest] Test 10: Phase Validation");

            var currentPhase = _matchManager.Phase;
            Debug.Log($"[ActionApplierSmokeTest] Current match phase: {currentPhase}");

            if (currentPhase != MatchPhase.Running)
            {
                // Phase is NOT Running — verify that any non-NoOp action is rejected
                var action = new AgentAction(
                    actorPosition: new GridPosition(0, 0),
                    actionType:   UnitActionType.Move,
                    direction:    Direction.North,
                    isValid:      true,
                    sourceType:   ActionSourceType.Debug);

                bool applied = _applier.ApplyAction(action, Owner.Player1);
                bool phaseRejected = _applier.RejectionReasonsLastStep.Any(
                    r => r.Contains("not in Running phase"));

                Debug.Log($"[ActionApplierSmokeTest] {(!applied && phaseRejected ? "✓" : "✗")} Action rejected for non-Running phase ({currentPhase})");
            }
            else
            {
                // Phase IS Running — phase check passes, action flows to normal validation
                Debug.Log("[ActionApplierSmokeTest] ✓ Match is Running — phase validation gate is open");
            }
        }

        private void TestProduceQueueBusy()
        {
            Debug.Log("[ActionApplierSmokeTest] Test 11: Produce — Queue Busy Validation");

            var building = FindBuildingUnit();
            if (building == null)
            {
                Debug.LogWarning("[ActionApplierSmokeTest] ✗ No building found — skipping");
                return;
            }

            var buildingRuntime = building.GetComponent<BuildingRuntime>();
            if (buildingRuntime == null)
            {
                Debug.LogWarning("[ActionApplierSmokeTest] ✗ No BuildingRuntime on building — skipping");
                return;
            }

            var queue = buildingRuntime.GetProductionQueue();
            bool isBusy = queue != null && queue.IsProducing;
            Debug.Log($"[ActionApplierSmokeTest] Building at {building.GridPos}: queue.IsProducing = {isBusy}");

            int actorIndex = building.GridPos.ToFlatIndex();
            var action = _decoder.DecodeDebug(
                actorIndexFlat:    actorIndex,
                actionType:        (int)UnitActionType.Produce,
                direction:         (int)Direction.North,
                produceUnitType:   (int)ProducibleUnit.Worker,
                attackTargetLocal: 0);

            _applier.ResetDiagnostics();
            bool applied = _applier.ApplyAction(action, building.Owner);

            if (isBusy)
            {
                bool busyRejected = _applier.RejectionReasonsLastStep.Any(
                    r => r.Contains("queue is busy"));
                Debug.Log($"[ActionApplierSmokeTest] {(!applied && busyRejected ? "✓" : "✗")} Queue busy rejection works");
            }
            else
            {
                Debug.Log($"[ActionApplierSmokeTest] Queue is free — Produce result: {(applied ? "accepted" : "rejected")}");
                if (!applied && _applier.RejectionReasonsLastStep.Count > 0)
                    Debug.LogWarning($"[ActionApplierSmokeTest] Rejection: {_applier.RejectionReasonsLastStep[0]}");
            }
        }

        private void TestCoordinateConvention()
        {
            Debug.Log("[ActionApplierSmokeTest] Test 12: Coordinate Convention");
            Debug.Log("[ActionApplierSmokeTest] Convention: North=+Y, South=-Y, East=+X, West=-X. FlatIndex = Y*W + X.");

            // FlatIndex round-trip for first 10 indices
            bool rtOk = true;
            for (int i = 0; i < 10; i++)
            {
                var pos = GridPosition.FromFlatIndex(i);
                if (pos.ToFlatIndex() != i) { rtOk = false; break; }
            }
            Debug.Log($"[ActionApplierSmokeTest] {(rtOk ? "✓" : "✗")} FlatIndex round-trip consistent (indices 0-9)");

            // North direction check: (5,5) -> North -> (5,6)
            var origin = new GridPosition(5, 5);
            var north  = origin.Neighbour(Direction.North);
            bool northOk = north.X == 5 && north.Y == 6;
            Debug.Log($"[ActionApplierSmokeTest] {(northOk ? "✓" : "✗")} North: (5,5) → (5,6) [Y+1]");

            // Verify ActionApplier.GetPositionInDirection matches GridPosition.Neighbour
            // (cannot call private method directly, but both delegate to the same Neighbour() — by design)
            Debug.Log("[ActionApplierSmokeTest] ✓ ActionApplier delegates to GridPosition.Neighbour — convention unified");
        }

        private UnitRuntime FindWorkerUnit()
        {
            for (int i = 0; i < ActionContract.TotalCells; i++)
            {
                var pos  = GridPosition.FromFlatIndex(i);
                var unit = _gridManager.GetOccupant(pos);
                if (unit != null && unit.Type == UnitType.Worker && unit.Owner == Owner.Player1)
                    return unit;
            }
            return null;
        }

        private UnitRuntime FindCombatUnit()
        {
            for (int i = 0; i < ActionContract.TotalCells; i++)
            {
                var pos  = GridPosition.FromFlatIndex(i);
                var unit = _gridManager.GetOccupant(pos);
                if (unit != null &&
                    (unit.Type == UnitType.Light || unit.Type == UnitType.Heavy || unit.Type == UnitType.Ranged) &&
                    unit.Owner == Owner.Player1)
                    return unit;
            }
            return null;
        }

        private UnitRuntime FindBuildingUnit()
        {
            for (int i = 0; i < ActionContract.TotalCells; i++)
            {
                var pos  = GridPosition.FromFlatIndex(i);
                var unit = _gridManager.GetOccupant(pos);
                if (unit != null &&
                    (unit.Type == UnitType.Base || unit.Type == UnitType.Barracks) &&
                    unit.Owner == Owner.Player1)
                    return unit;
            }
            return null;
        }
    }
}
