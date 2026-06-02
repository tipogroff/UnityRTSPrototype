using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.Presentation.Orders
{
    [DisallowMultipleComponent]
    public sealed class GroupOrderPlanner : MonoBehaviour
    {
        [SerializeField] private GridPathfindingService _pathfinding;
        [SerializeField] private GridManager _gridManager;

        public bool TryPlanGroupMove(
            IReadOnlyList<UnitRuntime> units,
            GridPosition clickedCell,
            out Dictionary<UnitRuntime, GridPosition> assignedDestinations,
            out string reason)
        {
            ResolveReferences();
            assignedDestinations = new Dictionary<UnitRuntime, GridPosition>();
            List<UnitRuntime> remainingUnits = FilterMobilePlayer2Units(units);
            if (_pathfinding == null || _gridManager == null)
            {
                reason = "Group move services are unavailable.";
                return false;
            }

            if (remainingUnits.Count == 0)
            {
                reason = "No selected mobile units.";
                return false;
            }

            List<GridPosition> candidates = BuildFormationCandidates(clickedCell, remainingUnits);
            while (remainingUnits.Count > 0)
            {
                UnitRuntime bestUnit = null;
                GridPosition bestCell = default;
                int bestFormationDistance = int.MaxValue;
                int bestPathLength = int.MaxValue;
                for (int unitIndex = 0; unitIndex < remainingUnits.Count; unitIndex++)
                {
                    UnitRuntime unit = remainingUnits[unitIndex];
                    for (int cellIndex = 0; cellIndex < candidates.Count; cellIndex++)
                    {
                        GridPosition candidate = candidates[cellIndex];
                        if (!_pathfinding.TryFindPath(unit, candidate, out List<GridPosition> path, out _))
                        {
                            continue;
                        }

                        int formationDistance = candidate.ChebyshevDistance(clickedCell);
                        if (bestUnit == null
                            || formationDistance < bestFormationDistance
                            || (formationDistance == bestFormationDistance && path.Count < bestPathLength)
                            || (formationDistance == bestFormationDistance && path.Count == bestPathLength && CompareUnits(unit, bestUnit) < 0)
                            || (formationDistance == bestFormationDistance && path.Count == bestPathLength && unit == bestUnit && CompareCells(candidate, bestCell) < 0))
                        {
                            bestUnit = unit;
                            bestCell = candidate;
                            bestFormationDistance = formationDistance;
                            bestPathLength = path.Count;
                        }
                    }
                }

                if (bestUnit == null)
                {
                    assignedDestinations.Clear();
                    reason = "No free formation cells near target.";
                    return false;
                }

                assignedDestinations[bestUnit] = bestCell;
                remainingUnits.Remove(bestUnit);
                candidates.Remove(bestCell);
            }

            reason = string.Empty;
            return true;
        }

        public bool TryPlanGroupAttackApproach(
            IReadOnlyList<UnitRuntime> attackers,
            IReadOnlyList<UnitRuntime> targets,
            int attackAreaRadius,
            out Dictionary<UnitRuntime, UnitRuntime> assignedTargets,
            out Dictionary<UnitRuntime, GridPosition?> preferredAttackCells,
            out string reason)
        {
            ResolveReferences();
            assignedTargets = new Dictionary<UnitRuntime, UnitRuntime>();
            preferredAttackCells = new Dictionary<UnitRuntime, GridPosition?>();
            List<UnitRuntime> remainingAttackers = FilterAttackers(attackers);
            List<UnitRuntime> validTargets = FilterTargets(targets);
            if (_pathfinding == null || _gridManager == null)
            {
                reason = "Group attack services are unavailable.";
                return false;
            }

            if (remainingAttackers.Count == 0)
            {
                reason = "No selected units can attack.";
                return false;
            }

            if (validTargets.Count == 0)
            {
                reason = "No enemy target in attack area.";
                return false;
            }

            var assignedCounts = new Dictionary<UnitRuntime, int>();
            for (int i = 0; i < validTargets.Count; i++)
            {
                assignedCounts[validTargets[i]] = 0;
            }

            for (int i = 0; i < remainingAttackers.Count; i++)
            {
                UnitRuntime attacker = remainingAttackers[i];
                UnitRuntime target = FindBestTarget(attacker, validTargets, assignedCounts);
                assignedTargets[attacker] = target;
                assignedCounts[target]++;
            }

            foreach (UnitRuntime target in validTargets)
            {
                List<UnitRuntime> assignedAttackers = new List<UnitRuntime>();
                foreach (KeyValuePair<UnitRuntime, UnitRuntime> pair in assignedTargets)
                {
                    if (pair.Value == target)
                    {
                        assignedAttackers.Add(pair.Key);
                    }
                }

                assignedAttackers.Sort(CompareUnits);
                Dictionary<UnitRuntime, GridPosition?> targetSlots = AssignPreferredAttackSlotsForTarget(target, assignedAttackers);
                foreach (KeyValuePair<UnitRuntime, GridPosition?> slot in targetSlots)
                {
                    preferredAttackCells[slot.Key] = slot.Value;
                }
            }

            for (int i = 0; i < remainingAttackers.Count; i++)
            {
                UnitRuntime attacker = remainingAttackers[i];
                if (!preferredAttackCells.ContainsKey(attacker))
                {
                    preferredAttackCells[attacker] = null;
                }
            }

            reason = preferredAttackCells.ContainsValue(null)
                ? "Some attackers will use dynamic attack approach replanning."
                : string.Empty;
            return true;
        }

        public static bool IsMobilePlayer2Unit(UnitRuntime unit)
        {
            return unit != null
                   && unit.gameObject.activeInHierarchy
                   && unit.IsAlive
                   && unit.Owner == Owner.Player2
                   && !unit.IsBuilding
                   && unit.Type != UnitType.Resource;
        }

        private List<GridPosition> BuildFormationCandidates(GridPosition center, IReadOnlyList<UnitRuntime> units)
        {
            var candidates = new List<GridPosition>();
            var selectedCells = new HashSet<GridPosition>();
            for (int i = 0; i < units.Count; i++)
            {
                selectedCells.Add(units[i].GridPos);
            }

            int maxRadius = Mathf.Max(GameConstants.MapWidth, GameConstants.MapHeight);
            for (int radius = 0; radius <= maxRadius; radius++)
            {
                for (int y = center.Y - radius; y <= center.Y + radius; y++)
                {
                    for (int x = center.X - radius; x <= center.X + radius; x++)
                    {
                        GridPosition cell = new GridPosition(x, y);
                        if (cell.ChebyshevDistance(center) != radius || !_gridManager.IsInside(cell))
                        {
                            continue;
                        }

                        UnitRuntime occupant = _gridManager.GetOccupant(cell);
                        if (occupant == null || selectedCells.Contains(cell))
                        {
                            candidates.Add(cell);
                        }
                    }
                }
            }

            candidates.Sort((left, right) =>
            {
                int chebyshev = left.ChebyshevDistance(center).CompareTo(right.ChebyshevDistance(center));
                if (chebyshev != 0) return chebyshev;
                int manhattan = left.ManhattanDistance(center).CompareTo(right.ManhattanDistance(center));
                return manhattan != 0 ? manhattan : CompareCells(left, right);
            });
            return candidates;
        }

        private Dictionary<UnitRuntime, GridPosition?> AssignPreferredAttackSlotsForTarget(UnitRuntime target, List<UnitRuntime> attackers)
        {
            var result = new Dictionary<UnitRuntime, GridPosition?>();
            if (target == null || attackers == null || attackers.Count == 0)
            {
                return result;
            }

            var reservedSlots = new HashSet<GridPosition>();
            for (int i = 0; i < attackers.Count; i++)
            {
                result[attackers[i]] = null;
            }

            var pendingAttackers = new List<UnitRuntime>(attackers);
            while (pendingAttackers.Count > 0)
            {
                UnitRuntime bestAttacker = null;
                GridPosition bestCell = default;
                int bestPathLength = int.MaxValue;
                int bestTargetDistance = int.MaxValue;

                for (int i = 0; i < pendingAttackers.Count; i++)
                {
                    UnitRuntime attacker = pendingAttackers[i];
                    if (!_pathfinding.TryGetAttackRange(attacker, out int attackRange, out _))
                    {
                        continue;
                    }

                    List<GridPosition> attackerCandidates = BuildAttackCandidatesFor(attacker, target, attackRange);
                    for (int candidateIndex = 0; candidateIndex < attackerCandidates.Count; candidateIndex++)
                    {
                        GridPosition candidate = attackerCandidates[candidateIndex];
                        if (reservedSlots.Contains(candidate))
                        {
                            continue;
                        }

                        int pathLength;
                        if (candidate == attacker.GridPos)
                        {
                            pathLength = 0;
                        }
                        else if (!_pathfinding.TryFindPath(attacker, candidate, out List<GridPosition> path, out _))
                        {
                            continue;
                        }
                        else
                        {
                            pathLength = path.Count;
                        }

                        int targetDistance = candidate.ChebyshevDistance(target.GridPos);
                        if (bestAttacker == null
                            || pathLength < bestPathLength
                            || (pathLength == bestPathLength && targetDistance < bestTargetDistance)
                            || (pathLength == bestPathLength && targetDistance == bestTargetDistance && CompareUnits(attacker, bestAttacker) < 0)
                            || (pathLength == bestPathLength && targetDistance == bestTargetDistance && attacker == bestAttacker && CompareCells(candidate, bestCell) < 0))
                        {
                            bestAttacker = attacker;
                            bestCell = candidate;
                            bestPathLength = pathLength;
                            bestTargetDistance = targetDistance;
                        }
                    }
                }

                if (bestAttacker == null)
                {
                    break;
                }

                result[bestAttacker] = bestCell;
                reservedSlots.Add(bestCell);
                pendingAttackers.Remove(bestAttacker);
            }

            return result;
        }

        private List<GridPosition> BuildAttackCandidatesFor(UnitRuntime attacker, UnitRuntime target, int range)
        {
            var candidates = new List<GridPosition>();
            bool isMelee = range <= 1;
            if (_pathfinding.IsTargetInAttackRange(attacker, target))
            {
                candidates.Add(attacker.GridPos);
            }

            for (int y = target.GridPos.Y - range; y <= target.GridPos.Y + range; y++)
            {
                for (int x = target.GridPos.X - range; x <= target.GridPos.X + range; x++)
                {
                    GridPosition cell = new GridPosition(x, y);
                    if (cell == target.GridPos || cell.ChebyshevDistance(target.GridPos) > range)
                    {
                        continue;
                    }

                    if (isMelee && cell.ChebyshevDistance(target.GridPos) != 1)
                    {
                        continue;
                    }

                    if (!isMelee && cell.ChebyshevDistance(target.GridPos) == 1)
                    {
                        continue;
                    }

                    if (!_pathfinding.IsCellAvailableForMove(attacker, cell, allowCurrentUnitCell: true))
                    {
                        continue;
                    }

                    candidates.Add(cell);
                }
            }

            if (!isMelee)
            {
                for (int y = target.GridPos.Y - range; y <= target.GridPos.Y + range; y++)
                {
                    for (int x = target.GridPos.X - range; x <= target.GridPos.X + range; x++)
                    {
                        GridPosition cell = new GridPosition(x, y);
                        if (cell == target.GridPos
                            || cell.ChebyshevDistance(target.GridPos) > range
                            || !_pathfinding.IsCellAvailableForMove(attacker, cell, allowCurrentUnitCell: true)
                            || candidates.Contains(cell))
                        {
                            continue;
                        }

                        candidates.Add(cell);
                    }
                }
            }

            candidates.Sort((left, right) =>
            {
                int leftDistance = left.ChebyshevDistance(attacker.GridPos);
                int rightDistance = right.ChebyshevDistance(attacker.GridPos);
                int distanceComparison = leftDistance.CompareTo(rightDistance);
                if (distanceComparison != 0)
                {
                    return distanceComparison;
                }

                return CompareCells(left, right);
            });

            return candidates;
        }

        private List<UnitRuntime> FilterMobilePlayer2Units(IReadOnlyList<UnitRuntime> units)
        {
            var filtered = new List<UnitRuntime>();
            if (units != null)
            {
                for (int i = 0; i < units.Count; i++)
                {
                    if (IsMobilePlayer2Unit(units[i]) && !filtered.Contains(units[i]))
                    {
                        filtered.Add(units[i]);
                    }
                }
            }

            filtered.Sort(CompareUnits);
            return filtered;
        }

        private List<UnitRuntime> FilterAttackers(IReadOnlyList<UnitRuntime> attackers)
        {
            List<UnitRuntime> filtered = FilterMobilePlayer2Units(attackers);
            filtered.RemoveAll(unit => !_pathfinding.CanUnitAttack(unit, out _));
            return filtered;
        }

        private static List<UnitRuntime> FilterTargets(IReadOnlyList<UnitRuntime> targets)
        {
            var filtered = new List<UnitRuntime>();
            if (targets != null)
            {
                for (int i = 0; i < targets.Count; i++)
                {
                    UnitRuntime target = targets[i];
                    if (target != null
                        && target.gameObject.activeInHierarchy
                        && target.IsAlive
                        && target.Owner != Owner.Player2
                        && target.Owner != Owner.Neutral
                        && target.Type != UnitType.Resource)
                    {
                        filtered.Add(target);
                    }
                }
            }

            filtered.Sort(CompareUnits);
            return filtered;
        }

        private static UnitRuntime FindBestTarget(
            UnitRuntime attacker,
            IReadOnlyList<UnitRuntime> targets,
            IReadOnlyDictionary<UnitRuntime, int> assignedCounts)
        {
            UnitRuntime best = null;
            for (int i = 0; i < targets.Count; i++)
            {
                UnitRuntime candidate = targets[i];
                if (best == null
                    || assignedCounts[candidate] < assignedCounts[best]
                    || (assignedCounts[candidate] == assignedCounts[best]
                        && attacker.GridPos.ChebyshevDistance(candidate.GridPos) < attacker.GridPos.ChebyshevDistance(best.GridPos))
                    || (assignedCounts[candidate] == assignedCounts[best]
                        && attacker.GridPos.ChebyshevDistance(candidate.GridPos) == attacker.GridPos.ChebyshevDistance(best.GridPos)
                        && CompareUnits(candidate, best) < 0))
                {
                    best = candidate;
                }
            }

            return best;
        }

        private void ResolveReferences()
        {
            _pathfinding ??= FindFirstObjectByType<GridPathfindingService>();
            _gridManager ??= GridManager.Instance != null ? GridManager.Instance : FindFirstObjectByType<GridManager>();
        }

        private static int CompareUnits(UnitRuntime left, UnitRuntime right)
        {
            if (left == right) return 0;
            if (left == null) return 1;
            if (right == null) return -1;
            int cell = CompareCells(left.GridPos, right.GridPos);
            return cell != 0 ? cell : left.GetInstanceID().CompareTo(right.GetInstanceID());
        }

        private static int CompareCells(GridPosition left, GridPosition right)
        {
            int x = left.X.CompareTo(right.X);
            return x != 0 ? x : left.Y.CompareTo(right.Y);
        }
    }
}
