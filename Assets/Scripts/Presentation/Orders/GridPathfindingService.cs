using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.Presentation.Orders
{
    [DisallowMultipleComponent]
    public sealed class GridPathfindingService : MonoBehaviour
    {
        [SerializeField] private GridManager _gridManager;

        public bool TryFindPath(UnitRuntime unit, GridPosition targetCell, out List<GridPosition> path, out string reason)
        {
            path = new List<GridPosition>();
            reason = string.Empty;
            ResolveReferences();

            if (unit == null)
            {
                reason = "Cannot find path: unit is missing.";
                return false;
            }

            if (_gridManager == null)
            {
                reason = "Cannot find path: GridManager is unavailable.";
                return false;
            }

            GridPosition start = unit.GridPos;
            if (!_gridManager.IsInside(targetCell))
            {
                reason = $"Cannot move: target {targetCell} is outside the map.";
                return false;
            }

            if (targetCell == start)
            {
                return true;
            }

            if (!IsCellAvailableForMove(unit, targetCell))
            {
                reason = $"Cannot move: target {targetCell} is occupied.";
                return false;
            }

            var frontier = new Queue<GridPosition>();
            var visited = new HashSet<GridPosition> { start };
            var previous = new Dictionary<GridPosition, GridPosition>();
            frontier.Enqueue(start);

            while (frontier.Count > 0)
            {
                GridPosition current = frontier.Dequeue();
                foreach (GridPosition neighbour in GetCardinalNeighbours(current))
                {
                    if (visited.Contains(neighbour) || !IsCellAvailableForMove(unit, neighbour, allowCurrentUnitCell: true))
                    {
                        continue;
                    }

                    visited.Add(neighbour);
                    previous[neighbour] = current;
                    if (neighbour == targetCell)
                    {
                        ReconstructPath(start, targetCell, previous, path);
                        return true;
                    }

                    frontier.Enqueue(neighbour);
                }
            }

            reason = $"Cannot move: target {targetCell} is unreachable.";
            return false;
        }

        public bool TryGetDirection(GridPosition from, GridPosition to, out Direction direction)
        {
            int dx = to.X - from.X;
            int dy = to.Y - from.Y;
            if (dx == 1 && dy == 0)
            {
                direction = Direction.East;
                return true;
            }

            if (dx == -1 && dy == 0)
            {
                direction = Direction.West;
                return true;
            }

            if (dx == 0 && dy == 1)
            {
                direction = Direction.North;
                return true;
            }

            if (dx == 0 && dy == -1)
            {
                direction = Direction.South;
                return true;
            }

            direction = Direction.North;
            return false;
        }

        public bool TryFindPathToAdjacent(
            UnitRuntime unit,
            GridPosition targetCell,
            out List<GridPosition> path,
            out GridPosition adjacentCell,
            out string reason)
        {
            path = new List<GridPosition>();
            adjacentCell = default;
            reason = string.Empty;
            ResolveReferences();

            if (unit == null)
            {
                reason = "Cannot find interaction path: unit is missing.";
                return false;
            }

            if (_gridManager == null)
            {
                reason = "Cannot find interaction path: GridManager is unavailable.";
                return false;
            }

            if (!_gridManager.IsInside(targetCell))
            {
                reason = $"Cannot interact: target {targetCell} is outside the map.";
                return false;
            }

            List<GridPosition> bestPath = null;
            foreach (GridPosition candidate in GetCardinalNeighbours(targetCell))
            {
                if (!IsCellAvailableForMove(unit, candidate, allowCurrentUnitCell: true))
                {
                    continue;
                }

                if (!TryFindPath(unit, candidate, out List<GridPosition> candidatePath, out _))
                {
                    continue;
                }

                if (bestPath != null && candidatePath.Count >= bestPath.Count)
                {
                    continue;
                }

                bestPath = candidatePath;
                adjacentCell = candidate;
            }

            if (bestPath == null)
            {
                reason = $"Cannot interact: no reachable free cardinal-adjacent cell near {targetCell}.";
                return false;
            }

            path.AddRange(bestPath);
            return true;
        }

        public bool TryFindBuildApproachPath(
            UnitRuntime worker,
            GridPosition buildCell,
            out List<GridPosition> path,
            out GridPosition workerBuildPosition,
            out Direction buildDirection,
            out string reason)
        {
            path = new List<GridPosition>();
            workerBuildPosition = default;
            buildDirection = Direction.North;
            reason = string.Empty;
            ResolveReferences();

            if (worker == null)
            {
                reason = "Cannot build Barracks: worker is missing.";
                return false;
            }

            if (_gridManager == null)
            {
                reason = "Cannot build Barracks: GridManager is unavailable.";
                return false;
            }

            if (!_gridManager.IsInside(buildCell))
            {
                reason = $"Cannot build Barracks: build cell {buildCell} is outside the map.";
                return false;
            }

            if (_gridManager.IsCellOccupied(buildCell))
            {
                reason = $"Cannot build Barracks: build cell {buildCell} is occupied.";
                return false;
            }

            if (!TryFindPathToAdjacent(worker, buildCell, out path, out workerBuildPosition, out string pathReason))
            {
                reason = $"Cannot build Barracks: {pathReason}";
                return false;
            }

            if (!TryGetDirection(workerBuildPosition, buildCell, out buildDirection))
            {
                reason = $"Cannot build Barracks: approach cell {workerBuildPosition} is not cardinal-adjacent to {buildCell}.";
                path.Clear();
                return false;
            }

            return true;
        }

        public bool TryFindAttackApproachPath(
            UnitRuntime attacker,
            UnitRuntime target,
            out List<GridPosition> path,
            out GridPosition attackCell,
            out string reason)
        {
            path = new List<GridPosition>();
            attackCell = default;
            reason = string.Empty;
            ResolveReferences();

            if (!TryGetAttackRange(attacker, out int attackRange, out reason))
            {
                return false;
            }

            if (target == null || !target.IsAlive || target.Owner == attacker.Owner || target.Owner == Owner.Neutral)
            {
                reason = "Cannot attack: target is missing, destroyed, or not an enemy player unit.";
                return false;
            }

            if (attacker.GridPos.ChebyshevDistance(target.GridPos) <= attackRange)
            {
                attackCell = attacker.GridPos;
                return true;
            }

            List<GridPosition> bestPath = null;
            for (int y = target.GridPos.Y - attackRange; y <= target.GridPos.Y + attackRange; y++)
            {
                for (int x = target.GridPos.X - attackRange; x <= target.GridPos.X + attackRange; x++)
                {
                    GridPosition candidate = new GridPosition(x, y);
                    if (candidate == target.GridPos
                        || candidate.ChebyshevDistance(target.GridPos) > attackRange
                        || !IsCellAvailableForMove(attacker, candidate, allowCurrentUnitCell: true))
                    {
                        continue;
                    }

                    if (!TryFindPath(attacker, candidate, out List<GridPosition> candidatePath, out _))
                    {
                        continue;
                    }

                    if (bestPath != null && candidatePath.Count >= bestPath.Count)
                    {
                        continue;
                    }

                    bestPath = candidatePath;
                    attackCell = candidate;
                }
            }

            if (bestPath == null)
            {
                reason = $"Cannot attack: no reachable cell within range {attackRange} of target {target.GridPos}.";
                return false;
            }

            path.AddRange(bestPath);
            return true;
        }

        public bool IsTargetInAttackRange(UnitRuntime attacker, UnitRuntime target)
        {
            return TryGetAttackRange(attacker, out int attackRange, out _)
                   && target != null
                   && target.IsAlive
                   && target.Owner != attacker.Owner
                   && target.Owner != Owner.Neutral
                   && attacker.GridPos.ChebyshevDistance(target.GridPos) <= attackRange;
        }

        public bool CanUnitAttack(UnitRuntime attacker, out string reason)
        {
            return TryGetAttackRange(attacker, out _, out reason);
        }

        public bool IsCellAvailableForMove(UnitRuntime unit, GridPosition cell, bool allowCurrentUnitCell = false)
        {
            ResolveReferences();
            if (_gridManager == null || !_gridManager.IsInside(cell))
            {
                return false;
            }

            UnitRuntime occupant = _gridManager.GetOccupant(cell);
            return occupant == null || (allowCurrentUnitCell && occupant == unit && cell == unit.GridPos);
        }

        public IEnumerable<GridPosition> GetCardinalNeighbours(GridPosition cell)
        {
            ResolveReferences();
            if (_gridManager == null)
            {
                yield break;
            }

            foreach (Direction direction in System.Enum.GetValues(typeof(Direction)))
            {
                GridPosition neighbour = cell.Neighbour(direction);
                if (_gridManager.IsInside(neighbour))
                {
                    yield return neighbour;
                }
            }
        }

        private void ResolveReferences()
        {
            _gridManager ??= GridManager.Instance != null ? GridManager.Instance : FindFirstObjectByType<GridManager>();
        }

        public bool TryGetAttackRange(UnitRuntime attacker, out int attackRange, out string reason)
        {
            attackRange = 0;
            if (attacker == null || !attacker.IsAlive)
            {
                reason = "Cannot attack: attacker is missing or destroyed.";
                return false;
            }

            GameConfig config = MatchBootstrap.Instance != null ? MatchBootstrap.Instance.GetConfig() : null;
            UnitDefinition definition = config != null ? config.GetDefinition(attacker.Type) : null;
            if (definition == null || definition.attackDamage <= 0 || definition.attackRange <= 0)
            {
                reason = $"Cannot attack: {attacker.Type} has no runtime attack capability.";
                return false;
            }

            attackRange = definition.attackRange;
            reason = string.Empty;
            return true;
        }

        private static void ReconstructPath(
            GridPosition start,
            GridPosition target,
            IReadOnlyDictionary<GridPosition, GridPosition> previous,
            List<GridPosition> path)
        {
            GridPosition current = target;
            while (current != start)
            {
                path.Add(current);
                current = previous[current];
            }

            path.Reverse();
        }
    }
}
