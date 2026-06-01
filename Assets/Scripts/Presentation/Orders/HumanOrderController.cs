using System;
using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.Presentation.Orders
{
    [DisallowMultipleComponent]
    public sealed class HumanOrderController : MonoBehaviour
    {
        [SerializeField] private GridPathfindingService _pathfinding;
        [SerializeField] private PlayerCommandController _commandController;
        [SerializeField] private PlayerSelectionController _selectionController;
        [SerializeField] private MatchManager _matchManager;
        [SerializeField] private UnitRegistry _unitRegistry;

        private readonly Dictionary<UnitRuntime, HumanUnitOrder> _activeOrders = new Dictionary<UnitRuntime, HumanUnitOrder>();
        private readonly Dictionary<UnitRuntime, HumanUnitOrder> _visibleTerminalOrders = new Dictionary<UnitRuntime, HumanUnitOrder>();
        private readonly List<UnitRuntime> _scratchUnits = new List<UnitRuntime>();

        public event Action<UnitRuntime, HumanUnitOrder> OnOrderStatusChanged;

        private void Awake()
        {
            ResolveReferences();
        }

        private void OnEnable()
        {
            ResolveReferences();
            Subscribe();
        }

        private void OnDisable()
        {
            Unsubscribe();
        }

        public void Configure(
            GridPathfindingService pathfinding,
            PlayerCommandController commandController,
            PlayerSelectionController selectionController,
            MatchManager matchManager)
        {
            Unsubscribe();
            _pathfinding = pathfinding;
            _commandController = commandController;
            _selectionController = selectionController;
            _matchManager = matchManager;
            ResolveReferences();
            Subscribe();
        }

        public bool IssueMove(UnitRuntime unit, GridPosition targetCell)
        {
            ResolveReferences();
            Debug.Log($"[HumanMove3G1R] IssueMove invoked unit={DescribeUnit(unit)} target={targetCell} matchPhase={_matchManager?.Phase}");
            if (!CanIssueMove(unit, targetCell, out string reason))
            {
                Debug.LogWarning($"[HumanMove3G1R] IssueMove rejected reason={reason}");
                PublishFailure(unit, reason);
                return false;
            }

            bool cancelledPrevious = unit != null && _activeOrders.ContainsKey(unit);
            CancelOrder(unit);
            Debug.Log($"[HumanMove3G1R] IssueMove previous order cancelled={cancelledPrevious}");
            _visibleTerminalOrders.Remove(unit);
            var order = new MoveOrder(unit, Owner.Player2, targetCell, _pathfinding, _commandController, _matchManager);
            _activeOrders[unit] = order;
            OnOrderStatusChanged?.Invoke(unit, order);
            Debug.Log("[HumanMove3G1R] IssueMove order created; immediate prime attempted=true");
            bool primed = order.TryPrime();
            OnOrderStatusChanged?.Invoke(unit, order);
            PublishAndRetainTerminal(unit, order);
            Debug.Log($"[HumanMove3G1R] IssueMove prime result={primed} status={order.Status} text={order.StatusText}");
            return primed;
        }

        public bool IssueHarvestLoop(UnitRuntime worker, ResourceNode resource, out string reason)
        {
            ResolveReferences();
            bool cancelledPrevious = worker != null && _activeOrders.ContainsKey(worker);
            Debug.Log($"[HumanHarvest3G2R] IssueHarvestLoop worker={DescribeUnit(worker)} carry={worker?.CarriedResources ?? 0} resourceGrid={(resource != null ? resource.GridPosition.ToString() : "<null>")} resourceAmount={resource?.CurrentResources ?? 0} previousOrderCancelled={cancelledPrevious}");
            if (worker == null || !worker.IsAlive || worker.Owner != Owner.Player2 || worker.Type != UnitType.Worker)
            {
                reason = "Gather requires a living Player2 Worker.";
                Debug.LogWarning($"[HumanHarvest3G2R] IssueHarvestLoop rejected reason={reason}");
                PublishFailure(worker, reason);
                return false;
            }

            if (resource == null)
            {
                reason = "Resource is unavailable.";
                Debug.LogWarning($"[HumanHarvest3G2R] IssueHarvestLoop rejected reason={reason}");
                PublishFailure(worker, reason);
                return false;
            }

            if (resource.IsExhausted)
            {
                reason = "Resource is exhausted.";
                Debug.LogWarning($"[HumanHarvest3G2R] IssueHarvestLoop rejected reason={reason}");
                PublishFailure(worker, reason);
                return false;
            }

            if (_pathfinding == null || _commandController == null || _matchManager == null || _unitRegistry == null)
            {
                reason = "Gather order services are unavailable.";
                Debug.LogWarning($"[HumanHarvest3G2R] IssueHarvestLoop rejected reason={reason}");
                PublishFailure(worker, reason);
                return false;
            }

            CancelOrder(worker);
            _visibleTerminalOrders.Remove(worker);
            var order = new HarvestLoopOrder(worker, resource, _pathfinding, _commandController, _matchManager, _unitRegistry);
            _activeOrders[worker] = order;
            OnOrderStatusChanged?.Invoke(worker, order);
            bool primed = order.TryPrime();
            OnOrderStatusChanged?.Invoke(worker, order);
            PublishAndRetainTerminal(worker, order);
            reason = primed ? string.Empty : order.FailureReason;
            Debug.Log($"[HumanHarvest3G2R] IssueHarvestLoop accepted={primed} reason={reason} status={order.Status} text={order.StatusText}");
            return primed;
        }

        public bool IssueBuildBarracks(UnitRuntime worker, GridPosition buildCell, out string reason)
        {
            ResolveReferences();
            if (worker == null || !worker.IsAlive || worker.Owner != Owner.Player2 || worker.Type != UnitType.Worker)
            {
                reason = "Build Barracks requires a living Player2 Worker.";
                PublishFailure(worker, reason);
                return false;
            }

            if (_pathfinding == null || _commandController == null || _matchManager == null || _unitRegistry == null)
            {
                reason = "Build Barracks order services are unavailable.";
                PublishFailure(worker, reason);
                return false;
            }

            if (!_pathfinding.TryFindBuildApproachPath(worker, buildCell, out _, out _, out _, out reason))
            {
                PublishFailure(worker, reason);
                return false;
            }

            CancelOrder(worker);
            _visibleTerminalOrders.Remove(worker);
            var order = new BuildBarracksOrder(worker, buildCell, _pathfinding, _commandController, _matchManager, _unitRegistry);
            _activeOrders[worker] = order;
            OnOrderStatusChanged?.Invoke(worker, order);
            bool primed = order.TryPrime();
            OnOrderStatusChanged?.Invoke(worker, order);
            PublishAndRetainTerminal(worker, order);
            reason = primed ? string.Empty : order.FailureReason;
            return primed;
        }

        public bool CancelOrder(UnitRuntime unit)
        {
            if (unit == null || !_activeOrders.TryGetValue(unit, out HumanUnitOrder order))
            {
                return false;
            }

            order.Cancel();
            _activeOrders.Remove(unit);
            _visibleTerminalOrders[unit] = order;
            OnOrderStatusChanged?.Invoke(unit, order);
            return true;
        }

        public void CancelAllSelectedOrders()
        {
            ResolveReferences();
            if (_selectionController == null)
            {
                return;
            }

            IReadOnlyList<UnitRuntime> selected = _selectionController.SelectedUnits;
            for (int i = 0; i < selected.Count; i++)
            {
                CancelOrder(selected[i]);
            }
        }

        public HumanUnitOrder GetOrderStatus(UnitRuntime unit)
        {
            if (unit == null)
            {
                return null;
            }

            if (_activeOrders.TryGetValue(unit, out HumanUnitOrder active))
            {
                return active;
            }

            _visibleTerminalOrders.TryGetValue(unit, out HumanUnitOrder terminal);
            return terminal;
        }

        public string GetOrderStatusText(UnitRuntime unit)
        {
            return GetOrderStatus(unit)?.StatusText ?? "Order: none.";
        }

        private void HandleStepCompleted(MatchStateSnapshot snapshot)
        {
            Debug.Log($"[HumanMove3G1R] OnStepCleanupCompleted step={snapshot.Step} activeOrders={_activeOrders.Count} pendingAfterCleanup={snapshot.PendingCommands}");
            Debug.Log($"[HumanHarvest3G2R] Step cleanup step={snapshot.Step} activeOrders={_activeOrders.Count} pendingAfterCleanup={snapshot.PendingCommands}");
            TickActiveOrdersAfterCompletedStep();
        }

        private void TickActiveOrdersAfterCompletedStep()
        {
            Debug.Log($"[HumanMove3G1R] Deferred post-step order tick activeOrders={_activeOrders.Count}");
            _scratchUnits.Clear();
            foreach (KeyValuePair<UnitRuntime, HumanUnitOrder> pair in _activeOrders)
            {
                _scratchUnits.Add(pair.Key);
            }

            for (int i = 0; i < _scratchUnits.Count; i++)
            {
                UnitRuntime unit = _scratchUnits[i];
                if (!_activeOrders.TryGetValue(unit, out HumanUnitOrder order))
                {
                    continue;
                }

                order.TickAfterStep();
                OnOrderStatusChanged?.Invoke(unit, order);
                PublishAndRetainTerminal(unit, order);
            }
        }

        private bool CanIssueMove(UnitRuntime unit, GridPosition targetCell, out string reason)
        {
            if (unit == null)
            {
                reason = "Select a unit first.";
                return false;
            }

            if (unit.Owner != Owner.Player2)
            {
                reason = "Move orders are available only for Player2 units.";
                return false;
            }

            if (!unit.IsAlive || unit.IsBuilding || unit.Type == UnitType.Resource)
            {
                reason = "Selected object cannot move.";
                return false;
            }

            if (_pathfinding == null)
            {
                reason = "Move orders unavailable: pathfinding service missing.";
                return false;
            }

            return _pathfinding.TryFindPath(unit, targetCell, out _, out reason);
        }

        private void PublishFailure(UnitRuntime unit, string reason)
        {
            var failure = new RejectedHumanOrder(unit, reason);
            if (unit != null)
            {
                _visibleTerminalOrders[unit] = failure;
            }

            OnOrderStatusChanged?.Invoke(unit, failure);
        }

        private void PublishAndRetainTerminal(UnitRuntime unit, HumanUnitOrder order)
        {
            if (!order.IsTerminal)
            {
                return;
            }

            _activeOrders.Remove(unit);
            if (unit != null)
            {
                _visibleTerminalOrders[unit] = order;
            }

            OnOrderStatusChanged?.Invoke(unit, order);
        }

        private void ResolveReferences()
        {
            _pathfinding ??= FindFirstObjectByType<GridPathfindingService>();
            _commandController ??= FindFirstObjectByType<PlayerCommandController>();
            _selectionController ??= FindFirstObjectByType<PlayerSelectionController>();
            _matchManager ??= MatchManager.Instance != null ? MatchManager.Instance : FindFirstObjectByType<MatchManager>();
            _unitRegistry ??= UnitRegistry.Instance != null ? UnitRegistry.Instance : FindFirstObjectByType<UnitRegistry>();
        }

        private void Subscribe()
        {
            if (_matchManager == null)
            {
                return;
            }

            _matchManager.OnStepCleanupCompleted -= HandleStepCompleted;
            _matchManager.OnStepCleanupCompleted += HandleStepCompleted;
        }

        private void Unsubscribe()
        {
            if (_matchManager != null)
            {
                _matchManager.OnStepCleanupCompleted -= HandleStepCompleted;
            }
        }

        private static string DescribeUnit(UnitRuntime unit)
        {
            return unit == null
                ? "<null>"
                : $"{unit.name} owner={unit.Owner} type={unit.Type} grid={unit.GridPos} alive={unit.IsAlive}";
        }

        private sealed class RejectedHumanOrder : HumanUnitOrder
        {
            public RejectedHumanOrder(UnitRuntime unit, string reason)
                : base(unit, Owner.Player2)
            {
                Fail(reason);
            }

            public override void TickAfterStep()
            {
            }
        }
    }
}
