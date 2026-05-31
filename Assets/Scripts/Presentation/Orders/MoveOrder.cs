using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;

namespace RTS.Presentation.Orders
{
    public sealed class MoveOrder : HumanUnitOrder
    {
        private const int MaxReplans = 2;

        private readonly GridPathfindingService _pathfinding;
        private readonly PlayerCommandController _commandController;
        private readonly MatchManager _matchManager;
        private readonly List<GridPosition> _path = new List<GridPosition>();
        private int _nextWaypointIndex;
        private int _replanCount;
        private GridPosition? _queuedWaypoint;

        public MoveOrder(
            UnitRuntime unit,
            Owner owner,
            GridPosition targetCell,
            GridPathfindingService pathfinding,
            PlayerCommandController commandController,
            MatchManager matchManager)
            : base(unit, owner)
        {
            TargetCell = targetCell;
            _pathfinding = pathfinding;
            _commandController = commandController;
            _matchManager = matchManager;
        }

        public GridPosition TargetCell { get; }

        public override void TickAfterStep()
        {
            if (IsTerminal)
            {
                return;
            }

            if (Unit == null || !Unit.IsAlive)
            {
                Fail("unit is no longer alive.");
                return;
            }

            if (Owner != Owner.Player2 || Unit.Owner != Owner.Player2)
            {
                Fail("unit is no longer controlled by Player2.");
                return;
            }

            if (_matchManager == null || _matchManager.Phase != MatchPhase.Running)
            {
                Fail("match is not running.");
                return;
            }

            if (_queuedWaypoint.HasValue)
            {
                if (Unit.GridPos == _queuedWaypoint.Value)
                {
                    _nextWaypointIndex++;
                    _queuedWaypoint = null;
                }
                else
                {
                    _queuedWaypoint = null;
                    if (!TryReplan("queued move did not reach its waypoint"))
                    {
                        return;
                    }
                }
            }

            if (Unit.GridPos == TargetCell)
            {
                Complete($"Order completed: reached {TargetCell}.");
                return;
            }

            if (_path.Count == 0 && !TryReplan("initial path"))
            {
                return;
            }

            if (_nextWaypointIndex >= _path.Count)
            {
                if (!TryReplan("path ended before target"))
                {
                    return;
                }
            }

            GridPosition next = _path[_nextWaypointIndex];
            if (!_pathfinding.IsCellAvailableForMove(Unit, next))
            {
                if (!TryReplan($"next waypoint {next} became blocked"))
                {
                    return;
                }

                next = _path[_nextWaypointIndex];
            }

            if (!_pathfinding.TryGetDirection(Unit.GridPos, next, out Direction direction))
            {
                if (!TryReplan($"next waypoint {next} is not adjacent"))
                {
                    return;
                }

                next = _path[_nextWaypointIndex];
                if (!_pathfinding.TryGetDirection(Unit.GridPos, next, out direction))
                {
                    Fail("replanned path did not produce an adjacent waypoint.");
                    return;
                }
            }

            if (!_commandController.SubmitMoveForUnit(Unit, direction))
            {
                Fail(_commandController.LastCommandRejectedReason);
                return;
            }

            _queuedWaypoint = next;
            SetStatus(HumanOrderStatus.WaitingForStep, $"Order: waiting for next step toward {TargetCell}.");
        }

        private bool TryReplan(string context)
        {
            if (_replanCount >= MaxReplans)
            {
                Fail($"path blocked after {_replanCount} replans ({context}).");
                return false;
            }

            _replanCount++;
            _path.Clear();
            _nextWaypointIndex = 0;
            if (!_pathfinding.TryFindPath(Unit, TargetCell, out List<GridPosition> replanned, out string reason))
            {
                Fail(reason);
                return false;
            }

            _path.AddRange(replanned);
            if (_path.Count == 0)
            {
                Complete($"Order completed: reached {TargetCell}.");
                return false;
            }

            SetStatus(HumanOrderStatus.Moving, $"Order: moving to {TargetCell}.");
            return true;
        }
    }
}
