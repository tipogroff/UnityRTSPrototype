using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

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

        public bool TryPrime()
        {
            Debug.Log($"[HumanMove3G1R] MoveOrder prime requested unit={DescribeUnit()} target={TargetCell}");
            return TryAdvanceAfterStep(isPrime: true);
        }

        public override void TickAfterStep()
        {
            TryAdvanceAfterStep(isPrime: false);
        }

        private bool TryAdvanceAfterStep(bool isPrime)
        {
            if (IsTerminal)
            {
                Debug.Log($"[HumanMove3G1R] MoveOrder tick ignored terminal status={Status}");
                return Status == HumanOrderStatus.Completed;
            }

            if (Unit == null || !Unit.IsAlive)
            {
                Fail("unit is no longer alive.");
                return false;
            }

            if (Owner != Owner.Player2 || Unit.Owner != Owner.Player2)
            {
                Fail("unit is no longer controlled by Player2.");
                return false;
            }

            if (_matchManager == null || _matchManager.Phase != MatchPhase.Running)
            {
                Fail("match is not running.");
                return false;
            }

            if (_queuedWaypoint.HasValue)
            {
                Debug.Log($"[HumanMove3G1R] MoveOrder step result unit={DescribeUnit()} expected={_queuedWaypoint.Value} changed={Unit.GridPos == _queuedWaypoint.Value}");
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
                        return false;
                    }
                }
            }

            if (Unit.GridPos == TargetCell)
            {
                Complete($"Order completed: reached {TargetCell}.");
                Debug.Log($"[HumanMove3G1R] MoveOrder completed unit={DescribeUnit()}");
                return true;
            }

            if (_path.Count == 0 && !TryReplan("initial path"))
            {
                return Status == HumanOrderStatus.Completed;
            }

            if (_nextWaypointIndex >= _path.Count)
            {
                if (!TryReplan("path ended before target"))
                {
                    return Status == HumanOrderStatus.Completed;
                }
            }

            GridPosition next = _path[_nextWaypointIndex];
            if (!_pathfinding.IsCellAvailableForMove(Unit, next))
            {
                if (!TryReplan($"next waypoint {next} became blocked"))
                {
                    return false;
                }

                next = _path[_nextWaypointIndex];
            }

            if (!_pathfinding.TryGetDirection(Unit.GridPos, next, out Direction direction))
            {
                if (!TryReplan($"next waypoint {next} is not adjacent"))
                {
                    return false;
                }

                next = _path[_nextWaypointIndex];
                if (!_pathfinding.TryGetDirection(Unit.GridPos, next, out direction))
                {
                    Fail("replanned path did not produce an adjacent waypoint.");
                    return false;
                }
            }

            Debug.Log($"[HumanMove3G1R] MoveOrder submit stage prime={isPrime} pathLength={_path.Count} nextIndex={_nextWaypointIndex} nextWaypoint={next} direction={direction} actor={Unit.GridPos}");
            if (!_commandController.SubmitMoveForUnit(Unit, direction))
            {
                Fail(_commandController.LastCommandRejectedReason);
                Debug.LogWarning($"[HumanMove3G1R] MoveOrder SubmitMoveForUnit rejected reason={FailureReason}");
                return false;
            }

            _queuedWaypoint = next;
            SetStatus(HumanOrderStatus.WaitingForStep, $"Order: waiting for next step toward {TargetCell}.");
            Debug.Log($"[HumanMove3G1R] MoveOrder low-level AgentAction accepted/queued status={Status} queuedWaypoint={_queuedWaypoint.Value}");
            return true;
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
                Debug.LogWarning($"[HumanMove3G1R] MoveOrder pathfinding rejected context={context} reason={reason}");
                return false;
            }

            _path.AddRange(replanned);
            Debug.Log($"[HumanMove3G1R] MoveOrder pathfinding success context={context} pathLength={_path.Count} unit={DescribeUnit()} target={TargetCell}");
            if (_path.Count == 0)
            {
                Complete($"Order completed: reached {TargetCell}.");
                return false;
            }

            SetStatus(HumanOrderStatus.Moving, $"Order: moving to {TargetCell}.");
            return true;
        }

        private string DescribeUnit()
        {
            return Unit == null
                ? "<null>"
                : $"{Unit.name} owner={Unit.Owner} type={Unit.Type} grid={Unit.GridPos} alive={Unit.IsAlive}";
        }
    }
}
