#if UNITY_EDITOR
using System.IO;
using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using RTS.Presentation;
using RTS.Presentation.Orders;
using UnityEditor;
using UnityEngine;

namespace RTS.EditorTools.Presentation
{
    [InitializeOnLoad]
    public static class HumanPlay3G1RMoveValidationMenu
    {
        private const string AdjacentMarker = "Temp/HumanPlay3G1RValidateAdjacent.flag";
        private const string FarMarker = "Temp/HumanPlay3G1RValidateFar.flag";
        private const string CancelMarker = "Temp/HumanPlay3G1RValidateCancel.flag";
        private const string EvidencePath = "Temp/HumanPlay3G1RValidationEvidence.txt";
        private static MatchManager _match;
        private static HumanOrderController _orders;
        private static UnitRuntime _worker;
        private static GridPosition _start;
        private static GridPosition _target;
        private static int _startStep;
        private static string _caseName;
        private static bool _cancelRequested;
        private static GridPosition _cancelGrid;
        private static int _cancelObserveUntilStep;

        static HumanPlay3G1RMoveValidationMenu()
        {
            EditorApplication.update += TryRunMarkerValidation;
        }

        [MenuItem("RTS/HumanPlay/3G1R Validate Adjacent Move")]
        public static void ValidateAdjacentMove()
        {
            BeginValidation(requireFarTarget: false);
        }

        [MenuItem("RTS/HumanPlay/3G1R Validate Far Move")]
        public static void ValidateFarMove()
        {
            BeginValidation(requireFarTarget: true);
        }

        [MenuItem("RTS/HumanPlay/3G1R Validate Cancel Move")]
        public static void ValidateCancelMove()
        {
            BeginValidation(requireFarTarget: true, cancelAfterFirstStep: true);
        }

        private static void BeginValidation(bool requireFarTarget, bool cancelAfterFirstStep = false)
        {
            Cleanup();
            WriteEvidence($"BEGIN requireFarTarget={requireFarTarget} playing={EditorApplication.isPlaying}");
            if (!EditorApplication.isPlaying)
            {
                Debug.LogError("[HumanMove3G1R][Validation] Enter Play Mode before running validation.");
                WriteEvidence("FAIL not_in_play_mode");
                return;
            }

            _match = Object.FindFirstObjectByType<MatchManager>();
            _orders = Object.FindFirstObjectByType<HumanOrderController>();
            HumanPlayModeController modeController = Object.FindFirstObjectByType<HumanPlayModeController>();
            GridPathfindingService pathfinding = Object.FindFirstObjectByType<GridPathfindingService>();
            UnitRegistry registry = UnitRegistry.Instance != null ? UnitRegistry.Instance : Object.FindFirstObjectByType<UnitRegistry>();
            GridManager grid = GridManager.Instance != null ? GridManager.Instance : Object.FindFirstObjectByType<GridManager>();

            if (_match == null || _orders == null || modeController == null || pathfinding == null || registry == null || grid == null)
            {
                Debug.LogError("[HumanMove3G1R][Validation] Missing runtime references.");
                WriteEvidence("FAIL missing_runtime_references");
                Cleanup();
                return;
            }

            modeController.StartAIvsPlayer2();
            WriteEvidence($"mode current={modeController.CurrentMode} hasHumanSide={modeController.HasHumanSide} humanSide={modeController.HumanSide}");

            _worker = FindPlayer2Worker(registry);
            if (_worker == null)
            {
                Debug.LogError("[HumanMove3G1R][Validation] No living Player2 Worker found.");
                WriteEvidence("FAIL no_player2_worker");
                Cleanup();
                return;
            }

            _start = _worker.GridPos;
            if (!TryFindTarget(_worker, grid, pathfinding, requireFarTarget, out _target))
            {
                Debug.LogError($"[HumanMove3G1R][Validation] No {(requireFarTarget ? "far" : "adjacent")} free target found for {_worker}.");
                WriteEvidence($"FAIL no_target requireFarTarget={requireFarTarget}");
                Cleanup();
                return;
            }

            _caseName = cancelAfterFirstStep ? "cancel" : requireFarTarget ? "far" : "adjacent";
            _startStep = _match.Step;
            _match.OnStepCompleted += HandleStepCompleted;
            bool accepted = _orders.IssueMove(_worker, _target);
            Debug.Log($"[HumanMove3G1R][Validation] {_caseName} IssueMove accepted={accepted} start={_start} target={_target} step={_startStep}");
            WriteEvidence($"{_caseName} IssueMove accepted={accepted} start={_start} target={_target} step={_startStep}");
            if (!accepted)
            {
                Cleanup();
            }
        }

        private static void HandleStepCompleted(MatchStateSnapshot snapshot)
        {
            if (_worker == null || _orders == null)
            {
                Cleanup();
                return;
            }

            HumanUnitOrder order = _orders.GetOrderStatus(_worker);
            Debug.Log($"[HumanMove3G1R][Validation] {_caseName} step={snapshot.Step} start={_start} current={_worker.GridPos} target={_target} status={order?.Status} text={order?.StatusText}");
            WriteEvidence($"{_caseName} step={snapshot.Step} start={_start} current={_worker.GridPos} target={_target} status={order?.Status} text={order?.StatusText}");
            if (_caseName == "cancel")
            {
                if (!_cancelRequested)
                {
                    _orders.CancelOrder(_worker);
                    _cancelRequested = true;
                    _cancelGrid = _worker.GridPos;
                    _cancelObserveUntilStep = snapshot.Step + 3;
                    WriteEvidence($"cancel requested at step={snapshot.Step} grid={_cancelGrid}");
                    return;
                }

                if (_worker.GridPos != _cancelGrid)
                {
                    WriteEvidence($"FAIL cancel grid changed after cancel expected={_cancelGrid} current={_worker.GridPos}");
                    Cleanup();
                    return;
                }

                if (snapshot.Step >= _cancelObserveUntilStep)
                {
                    WriteEvidence($"PASS cancel grid remained={_cancelGrid} throughStep={snapshot.Step}");
                    Cleanup();
                }

                return;
            }

            if (_worker.GridPos == _target)
            {
                Debug.Log($"[HumanMove3G1R][Validation] PASS {_caseName} Move start={_start} target={_target} final={_worker.GridPos} steps={snapshot.Step - _startStep}");
                WriteEvidence($"PASS {_caseName} Move start={_start} target={_target} final={_worker.GridPos} steps={snapshot.Step - _startStep}");
                Cleanup();
                return;
            }

            if (order == null || order.IsTerminal)
            {
                Debug.LogError($"[HumanMove3G1R][Validation] FAIL {_caseName} Move status={order?.Status} reason={order?.FailureReason}");
                WriteEvidence($"FAIL {_caseName} terminal status={order?.Status} reason={order?.FailureReason}");
                Cleanup();
                return;
            }

            if (snapshot.Step - _startStep > 32)
            {
                Debug.LogError($"[HumanMove3G1R][Validation] FAIL {_caseName} Move timeout current={_worker.GridPos} target={_target}");
                WriteEvidence($"FAIL {_caseName} timeout current={_worker.GridPos} target={_target}");
                Cleanup();
            }
        }

        private static UnitRuntime FindPlayer2Worker(UnitRegistry registry)
        {
            List<UnitRuntime> units = registry.GetUnitsByOwner(Owner.Player2);
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit != null && unit.IsAlive && unit.Type == UnitType.Worker)
                {
                    return unit;
                }
            }

            return null;
        }

        private static bool TryFindTarget(
            UnitRuntime worker,
            GridManager grid,
            GridPathfindingService pathfinding,
            bool requireFarTarget,
            out GridPosition target)
        {
            if (!requireFarTarget)
            {
                foreach (Direction direction in System.Enum.GetValues(typeof(Direction)))
                {
                    GridPosition neighbour = worker.GridPos.Neighbour(direction);
                    if (grid.IsWalkable(neighbour))
                    {
                        target = neighbour;
                        return true;
                    }
                }

                target = default;
                return false;
            }

            int bestDistance = int.MaxValue;
            GridPosition bestTarget = default;
            bool found = false;
            for (int y = 0; y < grid.Height; y++)
            {
                for (int x = 0; x < grid.Width; x++)
                {
                    var candidate = new GridPosition(x, y);
                    int distance = worker.GridPos.ManhattanDistance(candidate);
                    if (distance < 4 || distance >= bestDistance || !grid.IsWalkable(candidate))
                    {
                        continue;
                    }

                    if (pathfinding.TryFindPath(worker, candidate, out List<GridPosition> path, out _) && path.Count >= 4)
                    {
                        bestDistance = distance;
                        bestTarget = candidate;
                        found = true;
                    }
                }
            }

            target = bestTarget;
            return found;
        }

        private static void Cleanup()
        {
            if (_match != null)
            {
                _match.OnStepCompleted -= HandleStepCompleted;
            }

            _match = null;
            _orders = null;
            _worker = null;
            _caseName = null;
            _cancelRequested = false;
        }

        private static void TryRunMarkerValidation()
        {
            if (!EditorApplication.isPlaying || _match != null)
            {
                return;
            }

            if (File.Exists(AdjacentMarker))
            {
                File.Delete(EvidencePath);
                File.Delete(AdjacentMarker);
                ValidateAdjacentMove();
                return;
            }

            if (File.Exists(FarMarker))
            {
                File.Delete(EvidencePath);
                File.Delete(FarMarker);
                ValidateFarMove();
                return;
            }

            if (File.Exists(CancelMarker))
            {
                File.Delete(EvidencePath);
                File.Delete(CancelMarker);
                ValidateCancelMove();
            }
        }

        private static void WriteEvidence(string text)
        {
            Directory.CreateDirectory("Temp");
            File.AppendAllText(EvidencePath, text + System.Environment.NewLine);
        }
    }
}
#endif
