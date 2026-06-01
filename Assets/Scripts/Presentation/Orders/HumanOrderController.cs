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

        public void CancelOrder(UnitRuntime unit)
        {
            if (unit == null || !_activeOrders.TryGetValue(unit, out HumanUnitOrder order))
            {
                return;
            }

            order.Cancel();
            _activeOrders.Remove(unit);
            _visibleTerminalOrders[unit] = order;
            OnOrderStatusChanged?.Invoke(unit, order);
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

        private void HandleStepCompleted(MatchStateSnapshot snapshot)
        {
            Debug.Log($"[HumanMove3G1R] OnStepCleanupCompleted step={snapshot.Step} activeOrders={_activeOrders.Count} pendingAfterCleanup={snapshot.PendingCommands}");
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
