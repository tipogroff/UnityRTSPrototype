using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.Presentation.Orders
{
    public sealed class HarvestLoopOrder : HumanUnitOrder
    {
        private const int MaxReplans = 3;
        private const int MaxRepeatedFailures = 3;

        private enum LoopStage
        {
            ToResource,
            Harvest,
            ToBase,
            Return
        }

        private enum QueuedAction
        {
            None,
            Move,
            Harvest,
            Return
        }

        private readonly ResourceNode _resource;
        private readonly GridPathfindingService _pathfinding;
        private readonly PlayerCommandController _commands;
        private readonly MatchManager _match;
        private readonly UnitRegistry _registry;
        private readonly List<GridPosition> _path = new List<GridPosition>();

        private LoopStage _stage = LoopStage.ToResource;
        private QueuedAction _queuedAction;
        private GridPosition? _queuedMoveTarget;
        private int _carryBeforeQueuedAction;
        private int _resourcesBeforeQueuedAction;
        private int _playerResourcesBeforeQueuedAction;
        private int _pathIndex;
        private int _replans;
        private int _repeatedFailures;
        private UnitRuntime _base;

        public HarvestLoopOrder(
            UnitRuntime worker,
            ResourceNode resource,
            GridPathfindingService pathfinding,
            PlayerCommandController commands,
            MatchManager match,
            UnitRegistry registry)
            : base(worker, Owner.Player2)
        {
            _resource = resource;
            _pathfinding = pathfinding;
            _commands = commands;
            _match = match;
            _registry = registry;
        }

        public ResourceNode Resource => _resource;

        public bool TryPrime()
        {
            Debug.Log($"[HumanHarvest3G2R] Prime worker={DescribeUnit(Unit)} resource={DescribeResource()}");
            if (Unit != null && Unit.CarriedResources > 0)
            {
                TransitionTo(LoopStage.ToBase, "new Gather order starts by depositing existing cargo.");
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

            if (!ValidateWorkerAndMatch(out string reason))
            {
                StopFailed(reason);
                return false;
            }

            if (!ConfirmQueuedAction())
            {
                return false;
            }

            switch (_stage)
            {
                case LoopStage.ToResource:
                    return AdvanceToResource();
                case LoopStage.Harvest:
                    return AdvanceHarvest();
                case LoopStage.ToBase:
                    return AdvanceToBase();
                case LoopStage.Return:
                    return AdvanceReturn();
                default:
                    StopFailed("unknown harvest-loop stage.");
                    return false;
            }
        }

        private bool AdvanceToResource()
        {
            if (_resource == null || _resource.IsExhausted)
            {
                return FinishOrReturnCargo("resource exhausted.");
            }

            if (TryGetInteractionDirection(Unit.GridPos, _resource.GridPosition, out _))
            {
                TransitionTo(LoopStage.Harvest, "worker is adjacent to resource.");
                ResetPath();
                return AdvanceHarvest();
            }

            if (!EnsureInteractionPath(_resource.GridPosition, "resource", out string reason))
            {
                StopFailed(reason);
                return false;
            }

            SetStatus(HumanOrderStatus.MovingToResource, "Order: moving to resource.");
            return SubmitNextMove("resource");
        }

        private bool AdvanceHarvest()
        {
            if (_resource == null || _resource.IsExhausted)
            {
                return FinishOrReturnCargo("resource exhausted.");
            }

            if (Unit.CarriedResources >= GameConstants.MaxCarryCapacity)
            {
                TransitionTo(LoopStage.ToBase, "carry capacity reached before Harvest submission.");
                ResetPath();
                return AdvanceToBase();
            }

            if (!TryGetInteractionDirection(Unit.GridPos, _resource.GridPosition, out Direction direction))
            {
                TransitionTo(LoopStage.ToResource, "worker is not adjacent to resource.");
                ResetPath();
                return AdvanceToResource();
            }

            Debug.Log($"[HumanHarvest3G2R] Harvest submit adjacent=true direction={direction} carryBefore={Unit.CarriedResources} resourceBefore={_resource.CurrentResources}");
            if (!_commands.SubmitHarvestForUnit(Unit, direction, out string reason))
            {
                Debug.LogWarning($"[HumanHarvest3G2R] Harvest rejected reason={reason}");
                return HandleRepeatedFailure($"Harvest rejected: {reason}");
            }

            _queuedAction = QueuedAction.Harvest;
            _carryBeforeQueuedAction = Unit.CarriedResources;
            _resourcesBeforeQueuedAction = _resource.CurrentResources;
            SetStatus(HumanOrderStatus.Harvesting, "Order: harvesting.");
            Debug.Log($"[HumanHarvest3G2R] Harvest accepted queued worker={DescribeUnit(Unit)} resource={DescribeResource()} direction={direction}");
            return true;
        }

        private bool AdvanceToBase()
        {
            _base = FindNearestOwnBase();
            if (_base == null)
            {
                StopFailed("No friendly base available.");
                return false;
            }

            Debug.Log($"[HumanHarvest3G2R] Base selected worker={DescribeUnit(Unit)} base={DescribeUnit(_base)}");
            if (TryGetInteractionDirection(Unit.GridPos, _base.GridPos, out _))
            {
                TransitionTo(LoopStage.Return, "worker is adjacent to friendly Base.");
                ResetPath();
                return AdvanceReturn();
            }

            if (!EnsureInteractionPath(_base.GridPos, "friendly Base", out string reason))
            {
                StopFailed(reason);
                return false;
            }

            SetStatus(HumanOrderStatus.MovingToBase, "Order: moving to base.");
            return SubmitNextMove("friendly Base");
        }

        private bool AdvanceReturn()
        {
            if (Unit.CarriedResources <= 0)
            {
                _repeatedFailures = 0;
                if (_resource == null || _resource.IsExhausted)
                {
                    StopCompleted("Order completed: Resource exhausted.");
                    return true;
                }

                TransitionTo(LoopStage.ToResource, "cargo deposited; resource remains active.");
                ResetPath();
                SetStatus(HumanOrderStatus.Pending, "Order: gathering loop.");
                return AdvanceToResource();
            }

            _base = FindNearestOwnBase();
            if (_base == null)
            {
                StopFailed("No friendly base available.");
                return false;
            }

            if (!TryGetInteractionDirection(Unit.GridPos, _base.GridPos, out Direction direction))
            {
                TransitionTo(LoopStage.ToBase, "worker is not adjacent to friendly Base.");
                ResetPath();
                return AdvanceToBase();
            }

            _playerResourcesBeforeQueuedAction = GetPlayer2Resources();
            Debug.Log($"[HumanHarvest3G2R] Return submit adjacent=true direction={direction} carryBefore={Unit.CarriedResources} playerResourcesBefore={_playerResourcesBeforeQueuedAction}");
            if (!_commands.SubmitReturnForUnit(Unit, direction, out string reason))
            {
                Debug.LogWarning($"[HumanHarvest3G2R] Return rejected reason={reason}");
                return HandleRepeatedFailure($"Return rejected: {reason}");
            }

            _queuedAction = QueuedAction.Return;
            _carryBeforeQueuedAction = Unit.CarriedResources;
            SetStatus(HumanOrderStatus.ReturningToBase, "Order: returning resources.");
            Debug.Log($"[HumanHarvest3G2R] Return accepted queued worker={DescribeUnit(Unit)} base={DescribeUnit(_base)} direction={direction}");
            return true;
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
                    Debug.Log($"[HumanHarvest3G2R] Move cleanup workerGrid={Unit.GridPos} expected={_queuedMoveTarget}");
                    if (_queuedMoveTarget.HasValue && Unit.GridPos == _queuedMoveTarget.Value)
                    {
                        _pathIndex++;
                        _queuedMoveTarget = null;
                        _repeatedFailures = 0;
                        return true;
                    }

                    _queuedMoveTarget = null;
                    return HandleRepeatedFailure("queued Move did not reach its waypoint.", replan: true);

                case QueuedAction.Harvest:
                    Debug.Log($"[HumanHarvest3G2R] Harvest cleanup carryBefore={_carryBeforeQueuedAction} carryAfter={Unit.CarriedResources} resourceBefore={_resourcesBeforeQueuedAction} resourceAfter={_resource?.CurrentResources} increased={Unit.CarriedResources > _carryBeforeQueuedAction} exhausted={_resource == null || _resource.IsExhausted}");
                    if (Unit.CarriedResources > _carryBeforeQueuedAction)
                    {
                        _repeatedFailures = 0;
                        if (Unit.CarriedResources >= GameConstants.MaxCarryCapacity || _resource.IsExhausted)
                        {
                            TransitionTo(LoopStage.ToBase, Unit.CarriedResources >= GameConstants.MaxCarryCapacity
                                ? "carry capacity reached after Harvest cleanup."
                                : "resource exhausted after Harvest cleanup; deposit final cargo.");
                            ResetPath();
                        }
                        return true;
                    }

                    if (_resource != null && _resource.IsExhausted)
                    {
                        return FinishOrReturnCargo("resource exhausted.");
                    }

                    return HandleRepeatedFailure($"Harvest produced no carried resources (resource before={_resourcesBeforeQueuedAction}).");

                case QueuedAction.Return:
                    int playerResourcesAfter = GetPlayer2Resources();
                    Debug.Log($"[HumanHarvest3G2R] Return cleanup carryBefore={_carryBeforeQueuedAction} carryAfter={Unit.CarriedResources} playerResourcesBefore={_playerResourcesBeforeQueuedAction} playerResourcesAfter={playerResourcesAfter} deposited={Unit.CarriedResources == 0 && playerResourcesAfter > _playerResourcesBeforeQueuedAction}");
                    if (Unit.CarriedResources == 0 && playerResourcesAfter > _playerResourcesBeforeQueuedAction)
                    {
                        _repeatedFailures = 0;
                        return true;
                    }

                    return HandleRepeatedFailure($"Return did not confirm deposit (carry before={_carryBeforeQueuedAction}, now={Unit.CarriedResources}; player resources before={_playerResourcesBeforeQueuedAction}, now={playerResourcesAfter}).");

                default:
                    return true;
            }
        }

        private bool SubmitNextMove(string destination)
        {
            if (_pathIndex >= _path.Count)
            {
                return HandleRepeatedFailure($"path to {destination} ended before adjacency.", replan: true);
            }

            GridPosition next = _path[_pathIndex];
            if (!_pathfinding.IsCellAvailableForMove(Unit, next)
                || !_pathfinding.TryGetDirection(Unit.GridPos, next, out Direction direction))
            {
                return HandleRepeatedFailure($"next waypoint to {destination} is blocked.", replan: true);
            }

            if (!_commands.SubmitMoveForUnit(Unit, direction))
            {
                Debug.LogWarning($"[HumanHarvest3G2R] Move rejected destination={destination} worker={DescribeUnit(Unit)} nextWaypoint={next} direction={direction} reason={_commands.LastCommandRejectedReason}");
                return HandleRepeatedFailure($"Move to {destination} rejected: {_commands.LastCommandRejectedReason}", replan: true);
            }

            _queuedAction = QueuedAction.Move;
            _queuedMoveTarget = next;
            Debug.Log($"[HumanHarvest3G2R] Move accepted queued destination={destination} worker={DescribeUnit(Unit)} nextWaypoint={next} direction={direction}");
            return true;
        }

        private bool EnsureInteractionPath(GridPosition target, string label, out string reason)
        {
            if (_pathIndex < _path.Count)
            {
                reason = string.Empty;
                return true;
            }

            if (_replans >= MaxReplans)
            {
                reason = $"path to {label} remained blocked after {_replans} replans.";
                return false;
            }

            _replans++;
            _path.Clear();
            _pathIndex = 0;
            if (!_pathfinding.TryFindPathToAdjacent(Unit, target, out List<GridPosition> path, out GridPosition adjacent, out reason))
            {
                reason = $"no reachable {label}-adjacent cell: {reason}";
                return false;
            }

            _path.AddRange(path);
            Debug.Log($"[HumanHarvest3G2R] Path requested destination={label} worker={DescribeUnit(Unit)} target={target} selectedAdjacent={adjacent} length={_path.Count}");
            return true;
        }

        private bool FinishOrReturnCargo(string completionReason)
        {
            if (Unit.CarriedResources > 0)
            {
                TransitionTo(LoopStage.ToBase, "resource exhausted; deposit final cargo.");
                ResetPath();
                return AdvanceToBase();
            }

            StopCompleted($"Order completed: {completionReason}");
            return true;
        }

        private bool HandleRepeatedFailure(string reason, bool replan = false)
        {
            _repeatedFailures++;
            Debug.LogWarning($"[HumanHarvest3G2R] Failure {_repeatedFailures}/{MaxRepeatedFailures}: {reason}");
            if (_repeatedFailures >= MaxRepeatedFailures)
            {
                StopFailed(reason);
                return false;
            }

            if (replan)
            {
                ResetPath(resetReplans: false);
            }

            return true;
        }

        private UnitRuntime FindNearestOwnBase()
        {
            if (_registry == null)
            {
                return null;
            }

            List<UnitRuntime> units = _registry.GetUnitsByOwner(Owner.Player2);
            UnitRuntime nearest = null;
            int bestDistance = int.MaxValue;
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime candidate = units[i];
                if (candidate == null || !candidate.IsAlive || candidate.Type != UnitType.Base)
                {
                    continue;
                }

                int distance = Unit.GridPos.ManhattanDistance(candidate.GridPos);
                if (distance < bestDistance)
                {
                    bestDistance = distance;
                    nearest = candidate;
                }
            }

            return nearest;
        }

        private bool ValidateWorkerAndMatch(out string reason)
        {
            if (Unit == null || !Unit.IsAlive)
            {
                reason = "worker is no longer alive.";
                return false;
            }

            if (Unit.Owner != Owner.Player2 || Unit.Type != UnitType.Worker)
            {
                reason = "harvest loop requires a Player2 Worker.";
                return false;
            }

            if (_match == null || _match.Phase != MatchPhase.Running)
            {
                reason = "match is not running.";
                return false;
            }

            reason = string.Empty;
            return true;
        }

        private static bool TryGetInteractionDirection(GridPosition from, GridPosition target, out Direction direction)
        {
            int dx = target.X - from.X;
            int dy = target.Y - from.Y;
            if (dx == 1 && dy == 0) { direction = Direction.East; return true; }
            if (dx == -1 && dy == 0) { direction = Direction.West; return true; }
            if (dx == 0 && dy == 1) { direction = Direction.North; return true; }
            if (dx == 0 && dy == -1) { direction = Direction.South; return true; }
            direction = Direction.North;
            return false;
        }

        private void ResetPath(bool resetReplans = true)
        {
            _path.Clear();
            _pathIndex = 0;
            _queuedMoveTarget = null;
            if (resetReplans)
            {
                _replans = 0;
            }
        }

        public override void Cancel()
        {
            base.Cancel();
            LogTerminal("Cancelled", "player cancelled order.");
        }

        private void TransitionTo(LoopStage next, string reason)
        {
            LoopStage previous = _stage;
            _stage = next;
            Debug.Log($"[HumanHarvest3G2R] Transition {previous}->{next} workerGrid={Unit?.GridPos} carry={Unit?.CarriedResources ?? 0} resourceRemaining={_resource?.CurrentResources ?? 0} baseGrid={(_base != null ? _base.GridPos.ToString() : "<none>")} reason={reason}");
        }

        private void StopCompleted(string text)
        {
            Complete(text);
            LogTerminal("Completed", text);
        }

        private void StopFailed(string reason)
        {
            Fail(reason);
            LogTerminal("Failed", reason);
        }

        private void LogTerminal(string status, string reason)
        {
            Debug.Log($"[HumanHarvest3G2R] Terminal status={status} reason={reason} workerCarry={Unit?.CarriedResources ?? 0} resourceRemaining={_resource?.CurrentResources ?? 0} player2Resources={GetPlayer2Resources()}");
        }

        private int GetPlayer2Resources()
        {
            return _match != null ? _match.GetResources(Owner.Player2) : 0;
        }

        private static string DescribeUnit(UnitRuntime unit)
            => unit == null ? "<null>" : $"{unit.name} owner={unit.Owner} type={unit.Type} grid={unit.GridPos} carry={unit.CarriedResources}";

        private string DescribeResource()
            => _resource == null ? "<null>" : $"{_resource.GridPosition} remaining={_resource.CurrentResources}";
    }
}
