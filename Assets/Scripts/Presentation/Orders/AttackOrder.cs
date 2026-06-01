using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.Presentation.Orders
{
    public sealed class AttackOrder : HumanUnitOrder
    {
        private const string LogPrefix = "[HumanGroupAttack3G6R]";
        private const int MaxReplans = 24;
        private const int MaxRepeatedAttackRejections = 8;
        private const int MaxNoDamageRetries = 6;
        private const int MaxWaitForAttackPositionTicks = 50;
        private const int MaxMoveSubmissionRejections = 10;

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
        private GridPosition _lastKnownTargetCell;
        private int _pathIndex;
        private int _replans;
        private int _repeatedAttackRejections;
        private int _moveSubmissionRejections;
        private int _waitForAttackPositionTicks;
        private int _targetHpBeforeQueuedAttack;
        private int _attackRange;
        private bool _loggedPrime;

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
            _lastKnownTargetCell = target != null ? target.GridPos : default;
            _pathfinding.TryGetAttackRange(attacker, out _attackRange, out _);
        }

        public UnitRuntime Target => _target;

        public bool TryPrime()
        {
            if (!_loggedPrime)
            {
                _loggedPrime = true;
                LogState("Prime", "AttackOrder created and primed.");
            }

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
                _reservations?.ReleaseAttackSlot(Unit);
                LogState("Fail", reason);
                return false;
            }

            if (_target == null || !_target.IsAlive)
            {
                _reservations?.ReleaseAttackSlotsForTarget(_target);
                _reservations?.ReleaseAttackSlot(Unit);
                LogState("Complete", "Target already destroyed.");
                Complete("Order completed: target destroyed.");
                return true;
            }

            if (_target.GridPos != _lastKnownTargetCell)
            {
                _lastKnownTargetCell = _target.GridPos;
                ResetPath();
                _preferredAttackCell = null;
                _reservations?.ReleaseAttackSlot(Unit);
                SetStatus(HumanOrderStatus.WaitingForStep, BuildTargetStatus("Replanning attack position."));
                LogState("TargetMoved", "Target moved; cleared path and slot for re-evaluation.");
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

            if (!TryEnsureAttackSlot(out reason))
            {
                if (_waitForAttackPositionTicks >= MaxWaitForAttackPositionTicks)
                {
                    Fail(reason);
                    _reservations?.ReleaseAttackSlot(Unit);
                    LogState("Fail", reason);
                    return false;
                }

                SetStatus(HumanOrderStatus.WaitingForStep, BuildTargetStatus("Waiting for attack position."));
                LogState("WaitSlot", reason);
                return true;
            }

            if (!EnsureApproachPath(out reason))
            {
                if (_replans >= MaxReplans)
                {
                    Fail(reason);
                    _reservations?.ReleaseAttackSlot(Unit);
                    LogState("Fail", reason);
                    return false;
                }

                SetStatus(HumanOrderStatus.WaitingForStep, BuildTargetStatus("Replanning attack position."));
                LogState("ReplanWait", reason);
                return true;
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
                        _waitForAttackPositionTicks = 0;
                        _moveSubmissionRejections = 0;
                        LogState("MoveConfirmed", "Queued move waypoint reached.");
                        return true;
                    }

                    LogState("MoveStalled", "Queued move did not reach waypoint; forcing replan.");
                    ResetPath();
                    return true;

                case QueuedAction.Attack:
                    if (_target == null || !_target.IsAlive)
                    {
                        _reservations?.ReleaseAttackSlotsForTarget(_target);
                        _reservations?.ReleaseAttackSlot(Unit);
                        LogState("Complete", "Target destroyed during queued attack cleanup.");
                        Complete("Order completed: target destroyed.");
                        return false;
                    }

                    if (_target.HP < _targetHpBeforeQueuedAttack)
                    {
                        _repeatedAttackRejections = 0;
                        _waitForAttackPositionTicks = 0;
                        LogState("AttackConfirmed", "Target HP decreased after queued attack.");
                        return true;
                    }

                    _repeatedAttackRejections++;
                    if (_repeatedAttackRejections >= MaxNoDamageRetries)
                    {
                        Fail("Attack failed: target took no damage after bounded retries.");
                        _reservations?.ReleaseAttackSlot(Unit);
                        LogState("Fail", "Runtime attack produced no target damage repeatedly.");
                        return false;
                    }

                    SetStatus(HumanOrderStatus.WaitingForStep, BuildTargetStatus("Attacking target."));
                    LogState("AttackNoDamage", "Queued attack accepted but no target HP change yet; retrying.");
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
                SetStatus(HumanOrderStatus.MovingToAttackRange, BuildTargetStatus("Moving to attack position."));
                reason = string.Empty;
                LogState("PathPreferred", $"Preferred attack approach planned with pathLength={_path.Count}.");
                return _path.Count > 0;
            }

            _preferredAttackCell = null;
            if (!_pathfinding.TryFindAttackApproachPath(Unit, _target, out List<GridPosition> path, out _, out reason))
            {
                LogState("PathFail", $"Attack approach planning failed: {reason}");
                return false;
            }

            _path.AddRange(path);
            _plannedTargetCell = _target.GridPos;
            SetStatus(HumanOrderStatus.MovingToAttackRange, BuildTargetStatus("Moving to attack position."));
            LogState("PathDynamic", $"Dynamic attack approach planned with pathLength={_path.Count}.");
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
            bool nextOccupied = !_pathfinding.IsCellAvailableForMove(Unit, next);
            bool nextReservedByOther = _reservations != null && _reservations.IsReservedByOther(Unit, next);
            if (nextOccupied || nextReservedByOther)
            {
                _waitForAttackPositionTicks++;
                SetStatus(HumanOrderStatus.WaitingForStep, BuildTargetStatus("Waiting for attack position."));
                LogState("WaitWaypoint", $"Next waypoint blocked occupied={nextOccupied} reserved={nextReservedByOther} at {next}.");
                ResetPath();
                return true;
            }

            if (!_pathfinding.TryGetDirection(Unit.GridPos, next, out Direction direction))
            {
                ResetPath();
                _waitForAttackPositionTicks++;
                SetStatus(HumanOrderStatus.WaitingForStep, BuildTargetStatus("Replanning attack position."));
                LogState("ReplanNonAdjacent", $"Next waypoint {next} was not adjacent.");
                return true;
            }

            if (_reservations != null && !_reservations.TryReserveNextCell(Unit, next, out string reservationReason))
            {
                _waitForAttackPositionTicks++;
                SetStatus(HumanOrderStatus.WaitingForStep, BuildTargetStatus("Waiting for attack position."));
                LogState("WaitReserve", reservationReason);
                return true;
            }

            if (!_commands.SubmitMoveForUnit(Unit, direction))
            {
                _moveSubmissionRejections++;
                _waitForAttackPositionTicks++;
                LogState("MoveRejected", $"Low-level move rejected: {_commands.LastCommandRejectedReason}");
                if (_moveSubmissionRejections >= MaxMoveSubmissionRejections)
                {
                    Fail("Attack failed: move rejected repeatedly while approaching target.");
                    _reservations?.ReleaseAttackSlot(Unit);
                    LogState("Fail", "Move submission rejected repeatedly.");
                    return false;
                }

                ResetPath();
                SetStatus(HumanOrderStatus.WaitingForStep, BuildTargetStatus("Replanning attack position."));
                return true;
            }

            _queuedAction = QueuedAction.Move;
            _queuedMoveTarget = next;
            SetStatus(HumanOrderStatus.WaitingForStep, BuildTargetStatus("Moving to attack position."));
            LogState("MoveSubmitted", $"Submitted low-level move toward {next} direction={direction}.");
            return true;
        }

        private bool SubmitAttack()
        {
            if (!_commands.SubmitAttackForUnit(Unit, _target, out string reason))
            {
                _repeatedAttackRejections++;
                LogState("AttackRejected", $"Low-level attack rejected reason={reason}");
                if (reason != null && reason.ToLowerInvariant().Contains("range"))
                {
                    ResetPath();
                    _waitForAttackPositionTicks++;
                    SetStatus(HumanOrderStatus.WaitingForStep, BuildTargetStatus("Replanning attack position."));
                    return true;
                }

                if (_repeatedAttackRejections >= MaxRepeatedAttackRejections)
                {
                    Fail(string.IsNullOrWhiteSpace(reason) ? "Attack failed: runtime repeatedly rejected attack." : reason);
                    _reservations?.ReleaseAttackSlot(Unit);
                    LogState("Fail", FailureReason);
                    return false;
                }

                SetStatus(HumanOrderStatus.WaitingForStep, BuildTargetStatus("Replanning attack position."));
                return true;
            }

            _queuedAction = QueuedAction.Attack;
            _targetHpBeforeQueuedAttack = _target.HP;
            SetStatus(HumanOrderStatus.Attacking, BuildTargetStatus("Attacking target."));
            LogState("AttackSubmitted", "Submitted low-level attack action.");
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

        private bool TryEnsureAttackSlot(out string reason)
        {
            reason = string.Empty;
            if (!_pathfinding.TryGetAttackRange(Unit, out _attackRange, out reason))
            {
                return false;
            }

            if (_reservations == null)
            {
                return true;
            }

            if (_reservations.TryAcquireOrUpdateAttackSlot(Unit, _target, _attackRange, out GridPosition slot, out reason))
            {
                _preferredAttackCell = slot;
                _waitForAttackPositionTicks = 0;
                return true;
            }

            _waitForAttackPositionTicks++;
            string ring = _reservations.DescribeAttackRing(Unit, _target, _attackRange);
            reason = $"{reason} {ring}";
            return false;
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

        private void LogState(string stage, string message)
        {
            string pathLength = _path != null ? _path.Count.ToString() : "0";
            string nextWaypoint = _pathIndex >= 0 && _pathIndex < _path.Count ? _path[_pathIndex].ToString() : "<none>";
            bool nextOccupied = _pathIndex >= 0
                                && _pathIndex < _path.Count
                                && !_pathfinding.IsCellAvailableForMove(Unit, _path[_pathIndex], allowCurrentUnitCell: true);
            bool nextReserved = _pathIndex >= 0
                                && _pathIndex < _path.Count
                                && _reservations != null
                                && _reservations.IsReservedByOther(Unit, _path[_pathIndex]);
            string preferred = _preferredAttackCell.HasValue ? _preferredAttackCell.Value.ToString() : "<none>";
            string attacker = Unit == null ? "<null>" : $"{Unit.GetInstanceID()}/{Unit.name}/{Unit.Type}@{Unit.GridPos}";
            string target = _target == null
                ? "<null>"
                : $"{_target.GetInstanceID()}/{_target.name}/{_target.Type}@{_target.GridPos} hp={_target.HP}/{_target.MaxHP}";

            Debug.Log(
                $"{LogPrefix} AttackOrder {stage} attacker={attacker} target={target} range={_attackRange} preferred={preferred} state={Status} " +
                $"pathLength={pathLength} next={nextWaypoint} nextOccupied={nextOccupied} nextReserved={nextReserved} queuedAction={_queuedAction} " +
                $"moveSubmitted={_queuedAction == QueuedAction.Move} attackSubmitted={_queuedAction == QueuedAction.Attack} " +
                $"applierAccepted={_commands?.LastCommandAccepted} applierRejectReason={_commands?.LastCommandRejectedReason} message={message}");
        }

        public override void Cancel()
        {
            base.Cancel();
            _reservations?.ReleaseAttackSlot(Unit);
            LogState("Cancel", "Order cancelled and attack slot released.");
        }

    }
}
