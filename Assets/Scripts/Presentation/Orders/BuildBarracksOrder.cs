using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.Presentation.Orders
{
    public sealed class BuildBarracksOrder : HumanUnitOrder
    {
        private const string LogPrefix = "[HumanBuildBarracks]";
        private const int MaxReplans = 3;

        private enum QueuedAction
        {
            None,
            Move,
            Build
        }

        private readonly GridPosition _buildCell;
        private readonly GridPathfindingService _pathfinding;
        private readonly PlayerCommandController _commands;
        private readonly MatchManager _match;
        private readonly UnitRegistry _registry;
        private readonly List<GridPosition> _path = new List<GridPosition>();

        private QueuedAction _queuedAction;
        private GridPosition? _queuedMoveTarget;
        private int _pathIndex;
        private int _replans;
        private Direction _lastSubmittedBuildDirection;
        private string _lastSubmitBuildReason = string.Empty;

        public BuildBarracksOrder(
            UnitRuntime worker,
            GridPosition buildCell,
            GridPathfindingService pathfinding,
            PlayerCommandController commands,
            MatchManager match,
            UnitRegistry registry)
            : base(worker, Owner.Player2)
        {
            _buildCell = buildCell;
            _pathfinding = pathfinding;
            _commands = commands;
            _match = match;
            _registry = registry;
        }

        public GridPosition BuildCell => _buildCell;

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
            LogBuildPath("TryAdvance.enter");
            if (IsTerminal)
            {
                return Status == HumanOrderStatus.Completed;
            }

            if (_queuedAction == QueuedAction.Build)
            {
                return ConfirmQueuedAction();
            }

            if (!ValidateWorkerAndMatch(out string reason))
            {
                Fail(reason);
                return false;
            }

            if (!ConfirmQueuedAction())
            {
                return false;
            }

            bool hasBuildDirection = TryGetBuildDirection(Unit.GridPos, _buildCell, out Direction buildDirection);
            LogBuildPath($"TryGetBuildDirection result={hasBuildDirection} direction={buildDirection}");
            if (hasBuildDirection)
            {
                return SubmitBuild(buildDirection);
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
            LogBuildPath("ConfirmQueuedAction.enter");
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
                        LogBuildPath("ConfirmQueuedAction.move_completed");
                        return true;
                    }

                    _queuedMoveTarget = null;
                    ResetPath();
                    LogBuildPath("ConfirmQueuedAction.move_not_at_target_replan");
                    return true;

                case QueuedAction.Build:
                    UnitRuntime barracks = FindOwnedBarracksAtBuildCell();
                    if (barracks != null && barracks.IsAlive && barracks.Owner == Owner.Player2 && barracks.Type == UnitType.Barracks)
                    {
                        Complete("Order completed: Barracks built.");
                        return false;
                    }

                    Fail(ResolveBuildFailureReasonAfterStep());
                    return false;

                default:
                    return true;
            }
        }

        private bool EnsureApproachPath(out string reason)
        {
            if (_pathIndex < _path.Count)
            {
                reason = string.Empty;
                return true;
            }

            if (_replans >= MaxReplans)
            {
                reason = $"Cannot build Barracks: approach path remained blocked after {_replans} replans.";
                return false;
            }

            _replans++;
            _path.Clear();
            _pathIndex = 0;
            if (!_pathfinding.TryFindBuildApproachPath(Unit, _buildCell, out List<GridPosition> path, out _, out _, out reason))
            {
                return false;
            }

            _path.AddRange(path);
            LogBuildPath("EnsureApproachPath.planned");
            if (_path.Count == 0)
            {
                reason = "Cannot build Barracks: worker is not adjacent to build cell.";
                return false;
            }

            SetStatus(HumanOrderStatus.MovingToBuildSite, "Order: moving to build site.");
            return true;
        }

        private bool SubmitNextMove()
        {
            LogBuildPath("SubmitNextMove.enter");
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

            if (!_commands.SubmitMoveForUnit(Unit, direction))
            {
                Fail("Move to build site rejected: " + _commands.LastCommandRejectedReason);
                return false;
            }

            _queuedAction = QueuedAction.Move;
            _queuedMoveTarget = next;
            SetStatus(HumanOrderStatus.WaitingForStep, "Order: moving to build site.");
            LogBuildPath($"SubmitNextMove.accepted next={next} direction={direction}");
            return true;
        }

        private bool SubmitBuild(Direction direction)
        {
            LogBuildPath($"SubmitBuild.called direction={direction}");
            bool accepted = _commands.SubmitBuildBarracksForWorker(Unit, direction, out string reason);
            _lastSubmittedBuildDirection = direction;
            _lastSubmitBuildReason = reason ?? string.Empty;
            LogBuildPath($"SubmitBuild.result accepted={accepted} reason={_lastSubmitBuildReason}");
            if (!accepted)
            {
                Fail(reason);
                return false;
            }

            _queuedAction = QueuedAction.Build;
            SetStatus(HumanOrderStatus.BuildingBarracks, "Order: building Barracks.");
            return true;
        }

        private string ResolveBuildFailureReasonAfterStep()
        {
            UnitRuntime barracks = FindOwnedBarracksAtBuildCell();
            if (barracks != null && barracks.IsAlive && barracks.Owner == Owner.Player2 && barracks.Type == UnitType.Barracks)
            {
                return string.Empty;
            }

            if (Unit == null || !Unit.IsAlive)
            {
                return "Barracks construction failed: worker is no longer alive.";
            }

            if (Unit.Owner != Owner.Player2 || Unit.Type != UnitType.Worker)
            {
                return $"Barracks construction failed: unit is {Unit.Owner} {Unit.Type}, expected Player2 Worker.";
            }

            if (!TryGetBuildDirection(Unit.GridPos, _buildCell, out Direction currentDirection))
            {
                return $"Barracks construction failed: worker is not cardinal-adjacent to build cell {_buildCell} from {Unit.GridPos}.";
            }

            if (currentDirection != _lastSubmittedBuildDirection)
            {
                return $"Barracks construction failed: build direction changed from {_lastSubmittedBuildDirection} to {currentDirection}.";
            }

            GridManager grid = GridManager.Instance;
            if (grid == null)
            {
                return "Barracks construction failed: GridManager is unavailable.";
            }

            if (!grid.IsInside(_buildCell))
            {
                return $"Barracks construction failed: build cell {_buildCell} is outside the grid.";
            }

            if (grid.TryGetOccupant(_buildCell, out UnitRuntime occupant) && occupant != null)
            {
                return $"Barracks construction failed: build cell {_buildCell} is occupied by {occupant.Owner} {occupant.Type}.";
            }

            GameConfig config = MatchBootstrap.Instance != null ? MatchBootstrap.Instance.GetConfig() : null;
            UnitDefinition barracksDefinition = config != null ? config.GetDefinition(UnitType.Barracks) : null;
            if (barracksDefinition == null)
            {
                return "Barracks construction failed: UnitDef_Barracks is missing from GameConfig.";
            }

            if (_match != null)
            {
                int resources = _match.GetResources(Owner.Player2);
                int cost = barracksDefinition.productionCost;
                if (resources < cost)
                {
                    return $"Barracks construction failed: Player2 has {resources} resources, needs {cost}.";
                }
            }

            if (!string.IsNullOrWhiteSpace(_lastSubmitBuildReason))
            {
                return "Barracks construction failed: " + _lastSubmitBuildReason;
            }

            return $"Barracks construction was not confirmed after runtime step. buildCell={_buildCell}, worker={Unit.GridPos}, direction={_lastSubmittedBuildDirection}.";
        }

        private bool ValidateWorkerAndMatch(out string reason)
        {
            if (Unit == null || !Unit.IsAlive)
            {
                reason = "Worker is no longer alive.";
                return false;
            }

            if (Unit.Owner != Owner.Player2 || Unit.Type != UnitType.Worker)
            {
                reason = "Build Barracks requires a Player2 Worker.";
                return false;
            }

            if (_match == null || _match.Phase != MatchPhase.Running)
            {
                reason = "Match is not running.";
                return false;
            }

            if (_registry == null)
            {
                reason = "UnitRegistry is unavailable.";
                return false;
            }

            List<UnitRuntime> ownedUnits = _registry.GetUnitsByOwner(Owner.Player2);
            for (int i = 0; i < ownedUnits.Count; i++)
            {
                UnitRuntime owned = ownedUnits[i];
                if (owned != null && owned.IsAlive && owned.Type == UnitType.Barracks)
                {
                    reason = "Cannot build Barracks: owner already has one alive Barracks.";
                    return false;
                }
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

        private UnitRuntime FindOwnedBarracksAtBuildCell()
        {
            if (_registry == null)
            {
                return null;
            }

            List<UnitRuntime> ownedUnits = _registry.GetUnitsByOwner(Owner.Player2);
            for (int i = 0; i < ownedUnits.Count; i++)
            {
                UnitRuntime owned = ownedUnits[i];
                if (owned != null && owned.IsAlive && owned.Type == UnitType.Barracks && owned.GridPos == _buildCell)
                {
                    return owned;
                }
            }

            return null;
        }

        private void LogBuildPath(string message)
        {
            string workerCell = Unit != null ? Unit.GridPos.ToString() : "<null>";
            Debug.Log($"{LogPrefix} {message} buildCell={_buildCell} worker={workerCell} path.Count={_path.Count} pathIndex={_pathIndex} queuedAction={_queuedAction}");
        }

        private static bool TryGetBuildDirection(GridPosition workerCell, GridPosition buildCell, out Direction direction)
        {
            int dx = buildCell.X - workerCell.X;
            int dy = buildCell.Y - workerCell.Y;
            if (dx == 1 && dy == 0) { direction = Direction.East; return true; }
            if (dx == -1 && dy == 0) { direction = Direction.West; return true; }
            if (dx == 0 && dy == 1) { direction = Direction.North; return true; }
            if (dx == 0 && dy == -1) { direction = Direction.South; return true; }
            direction = Direction.North;
            return false;
        }
    }
}
