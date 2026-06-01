using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;

namespace RTS.Presentation.Orders
{
    public sealed class AttackOrder : HumanUnitOrder
    {
        private const int MaxReplans = 3;
        private const int MaxRepeatedAttackRejections = 3;

        private enum QueuedAction
        {
            None,
            Move,
            Attack
        }

        private readonly UnitRuntime _target;
        private readonly GridPathfindingService _pathfinding;
        private readonly PlayerCommandController _commands;
        private readonly MatchManager _match;
        private readonly GroupOrderReservationService _reservations;
        private readonly List<GridPosition> _path = new List<GridPosition>();

        private QueuedAction _queuedAction;
        private GridPosition? _preferredAttackCell;
        private GridPosition? _queuedMoveTarget;
        private GridPosition _plannedTargetCell;
        private int _pathIndex;
        private int _replans;
        private int _repeatedAttackRejections;
        private int _targetHpBeforeQueuedAttack;

        public AttackOrder(
            UnitRuntime attacker,
            UnitRuntime target,
            GridPathfindingService pathfinding,
            PlayerCommandController commands,
            MatchManager match,
            GridPosition? preferredAttackCell = null,
            GroupOrderReservationService reservations = null)
            : base(attacker, Owner.Player2)
        {
            _target = target;
            _pathfinding = pathfinding;
            _commands = commands;
            _match = match;
            _preferredAttackCell = preferredAttackCell;
            _reservations = reservations;
        }

        public UnitRuntime Target => _target;

        public bool TryPrime()
        {
            return TryAdvance();
        }

        public override void TickAfterStep()
        {
            TryAdvance();
        }

        private bool TryAdvance()
        {
            if (IsTerminal)
            {
                return Status == HumanOrderStatus.Completed;
            }

            if (!ValidateAttackerAndMatch(out string reason))
            {
                Fail(reason);
                return false;
            }

            if (_target == null || !_target.IsAlive)
            {
                Complete("Order completed: target destroyed.");
                return true;
            }

            if (!ConfirmQueuedAction())
            {
                return false;
            }

            if (_pathfinding.IsTargetInAttackRange(Unit, _target))
            {
                ResetPath();
                return SubmitAttack();
            }

            if (!EnsureApproachPath(out reason))
            {
                Fail(reason);
                return false;
            }

            return SubmitNextMove();
        }

        private bool ConfirmQueuedAction()
        {
            if (_queuedAction == QueuedAction.None)
            {
                return true;
            }

            QueuedAction completed = _queuedAction;
            _queuedAction = QueuedAction.None;
            switch (completed)
            {
                case QueuedAction.Move:
                    if (_queuedMoveTarget.HasValue && Unit.GridPos == _queuedMoveTarget.Value)
                    {
                        _pathIndex++;
                        _queuedMoveTarget = null;
                        return true;
                    }

                    ResetPath();
                    return true;

                case QueuedAction.Attack:
                    if (_target == null || !_target.IsAlive)
                    {
                        Complete("Order completed: target destroyed.");
                        return false;
                    }

                    if (_target.HP < _targetHpBeforeQueuedAttack)
                    {
                        _repeatedAttackRejections = 0;
                        return true;
                    }

                    _repeatedAttackRejections++;
                    if (_repeatedAttackRejections >= MaxRepeatedAttackRejections)
                    {
                        Fail("Runtime attack produced no target damage repeatedly.");
                        return false;
                    }

                    return true;

                default:
                    return true;
            }
        }

        private bool EnsureApproachPath(out string reason)
        {
            if (_plannedTargetCell == _target.GridPos && _pathIndex < _path.Count)
            {
                reason = string.Empty;
                return true;
            }

            if (_replans >= MaxReplans)
            {
                reason = $"Cannot attack: target unreachable after {_replans} replans.";
                return false;
            }

            _replans++;
            _path.Clear();
            _pathIndex = 0;
            if (TryPlanPreferredAttackCell(out List<GridPosition> preferredPath))
            {
                _path.AddRange(preferredPath);
                _plannedTargetCell = _target.GridPos;
                SetStatus(HumanOrderStatus.MovingToAttackRange, BuildTargetStatus("Order: moving to reserved attack approach."));
                reason = string.Empty;
                return _path.Count > 0;
            }

            _preferredAttackCell = null;
            if (!_pathfinding.TryFindAttackApproachPath(Unit, _target, out List<GridPosition> path, out _, out reason))
            {
                return false;
            }

            _path.AddRange(path);
            _plannedTargetCell = _target.GridPos;
            SetStatus(HumanOrderStatus.MovingToAttackRange, BuildTargetStatus("Order: moving to attack range."));
            return _path.Count > 0;
        }

        private bool SubmitNextMove()
        {
            if (_pathIndex >= _path.Count)
            {
                ResetPath();
                return TryAdvance();
            }

            GridPosition next = _path[_pathIndex];
            if (!_pathfinding.IsCellAvailableForMove(Unit, next)
                || !_pathfinding.TryGetDirection(Unit.GridPos, next, out Direction direction))
            {
                ResetPath();
                return TryAdvance();
            }

            if (_reservations != null && !_reservations.TryReserveNextCell(Unit, next, out _))
            {
                SetStatus(HumanOrderStatus.WaitingForStep, BuildTargetStatus("Order: waiting for reserved attack approach cell."));
                return true;
            }

            if (!_commands.SubmitMoveForUnit(Unit, direction))
            {
                ResetPath();
                return TryAdvance();
            }

            _queuedAction = QueuedAction.Move;
            _queuedMoveTarget = next;
            SetStatus(HumanOrderStatus.WaitingForStep, BuildTargetStatus("Order: moving to attack range."));
            return true;
        }

        private bool SubmitAttack()
        {
            if (!_commands.SubmitAttackForUnit(Unit, _target, out string reason))
            {
                _repeatedAttackRejections++;
                if (_repeatedAttackRejections >= MaxRepeatedAttackRejections)
                {
                    Fail(reason);
                    return false;
                }

                SetStatus(HumanOrderStatus.WaitingForStep, BuildTargetStatus("Order: runtime rejected attack; retrying."));
                return true;
            }

            _queuedAction = QueuedAction.Attack;
            _targetHpBeforeQueuedAttack = _target.HP;
            SetStatus(HumanOrderStatus.Attacking, BuildTargetStatus("Order: attacking target."));
            return true;
        }

        private bool ValidateAttackerAndMatch(out string reason)
        {
            if (Unit == null || !Unit.IsAlive)
            {
                reason = "Attacker is no longer alive.";
                return false;
            }

            if (Unit.Owner != Owner.Player2)
            {
                reason = "Attack order requires a Player2 unit.";
                return false;
            }

            if (_match == null || _match.Phase != MatchPhase.Running)
            {
                reason = "Match is not running.";
                return false;
            }

            reason = string.Empty;
            return true;
        }

        private void ResetPath()
        {
            _path.Clear();
            _pathIndex = 0;
            _queuedMoveTarget = null;
        }

        private bool TryPlanPreferredAttackCell(out List<GridPosition> path)
        {
            path = null;
            if (!_preferredAttackCell.HasValue
                || !_pathfinding.TryGetAttackRange(Unit, out int range, out _)
                || _preferredAttackCell.Value.ChebyshevDistance(_target.GridPos) > range
                || !_pathfinding.IsCellAvailableForMove(Unit, _preferredAttackCell.Value, allowCurrentUnitCell: true))
            {
                return false;
            }

            return _pathfinding.TryFindPath(Unit, _preferredAttackCell.Value, out path, out _);
        }

        private string BuildTargetStatus(string prefix)
        {
            return _target == null
                ? prefix
                : $"{prefix}\nTarget: {_target.Owner} {_target.Type}\nTarget HP: {_target.HP}/{_target.MaxHP}";
        }
    }
}
