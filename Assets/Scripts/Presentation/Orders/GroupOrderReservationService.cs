using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.Presentation.Orders
{
    [DisallowMultipleComponent]
    public sealed class GroupOrderReservationService : MonoBehaviour
    {
        private readonly Dictionary<GridPosition, UnitRuntime> _reservedCells = new Dictionary<GridPosition, UnitRuntime>();
        private readonly Dictionary<UnitRuntime, UnitRuntime> _attackTargetByAttacker = new Dictionary<UnitRuntime, UnitRuntime>();
        private readonly Dictionary<UnitRuntime, TargetSlots> _slotsByTarget = new Dictionary<UnitRuntime, TargetSlots>();

        [SerializeField] private GridPathfindingService _pathfinding;
        [SerializeField] private GridManager _gridManager;

        public void BeginTick()
        {
            _reservedCells.Clear();
        }

        public bool TryAcquireOrUpdateAttackSlot(
            UnitRuntime attacker,
            UnitRuntime target,
            int attackRange,
            out GridPosition slot,
            out string reason)
        {
            slot = default;
            reason = string.Empty;
            ResolveReferences();

            if (attacker == null || !attacker.IsAlive)
            {
                reason = "Cannot reserve attack slot: attacker is missing or dead.";
                return false;
            }

            if (target == null || !target.IsAlive)
            {
                reason = "Cannot reserve attack slot: target is missing or dead.";
                return false;
            }

            if (attackRange <= 0)
            {
                reason = "Cannot reserve attack slot: invalid attack range.";
                return false;
            }

            if (_pathfinding == null || _gridManager == null)
            {
                reason = "Cannot reserve attack slot: pathfinding or grid is unavailable.";
                return false;
            }

            if (_attackTargetByAttacker.TryGetValue(attacker, out UnitRuntime previousTarget) && previousTarget != target)
            {
                ReleaseAttackSlot(attacker);
            }

            TargetSlots slots = GetOrCreateTargetSlots(target);
            if (slots.LastKnownTargetCell != target.GridPos)
            {
                slots.SlotsByAttacker.Clear();
                slots.LastKnownTargetCell = target.GridPos;
            }

            if (slots.SlotsByAttacker.TryGetValue(attacker, out GridPosition existing)
                && IsAttackSlotStillValid(attacker, target, existing, attackRange))
            {
                slot = existing;
                _attackTargetByAttacker[attacker] = target;
                return true;
            }

            slots.SlotsByAttacker.Remove(attacker);
            List<GridPosition> candidates = BuildAttackCandidates(attacker, target, attackRange);
            if (candidates.Count == 0)
            {
                reason = "No candidate attack cells found around target.";
                return false;
            }

            bool found = TryPickBestUnclaimedSlot(attacker, slots, candidates, out slot);
            if (!found)
            {
                reason = "All attack cells are occupied, unreachable, or assigned to other attackers.";
                return false;
            }

            slots.SlotsByAttacker[attacker] = slot;
            _attackTargetByAttacker[attacker] = target;
            return true;
        }

        public void ReleaseAttackSlot(UnitRuntime attacker)
        {
            if (attacker == null)
            {
                return;
            }

            if (!_attackTargetByAttacker.TryGetValue(attacker, out UnitRuntime target))
            {
                return;
            }

            _attackTargetByAttacker.Remove(attacker);
            if (target == null || !_slotsByTarget.TryGetValue(target, out TargetSlots slots))
            {
                return;
            }

            slots.SlotsByAttacker.Remove(attacker);
            if (slots.SlotsByAttacker.Count == 0)
            {
                _slotsByTarget.Remove(target);
            }
        }

        public void ReleaseAttackSlotsForTarget(UnitRuntime target)
        {
            if (target == null || !_slotsByTarget.TryGetValue(target, out TargetSlots slots))
            {
                return;
            }

            foreach (KeyValuePair<UnitRuntime, GridPosition> pair in slots.SlotsByAttacker)
            {
                if (pair.Key != null)
                {
                    _attackTargetByAttacker.Remove(pair.Key);
                }
            }

            _slotsByTarget.Remove(target);
        }

        public bool TryGetAttackSlot(UnitRuntime attacker, UnitRuntime target, out GridPosition slot)
        {
            slot = default;
            return attacker != null
                   && target != null
                   && _slotsByTarget.TryGetValue(target, out TargetSlots slots)
                   && slots.SlotsByAttacker.TryGetValue(attacker, out slot);
        }

        public string DescribeAttackRing(UnitRuntime attacker, UnitRuntime target, int attackRange)
        {
            ResolveReferences();
            if (attacker == null || target == null || _gridManager == null)
            {
                return "occupied=[] reserved=[]";
            }

            List<GridPosition> ring = BuildAttackCandidates(attacker, target, attackRange);
            var occupied = new List<GridPosition>();
            var reserved = new List<GridPosition>();
            var reservedByOthers = new HashSet<GridPosition>();
            if (_slotsByTarget.TryGetValue(target, out TargetSlots slots))
            {
                foreach (KeyValuePair<UnitRuntime, GridPosition> pair in slots.SlotsByAttacker)
                {
                    if (pair.Key != null && pair.Key != attacker)
                    {
                        reservedByOthers.Add(pair.Value);
                    }
                }
            }

            for (int i = 0; i < ring.Count; i++)
            {
                GridPosition cell = ring[i];
                UnitRuntime occupant = _gridManager.GetOccupant(cell);
                if (occupant != null && occupant != attacker)
                {
                    occupied.Add(cell);
                }

                if (reservedByOthers.Contains(cell))
                {
                    reserved.Add(cell);
                }
            }

            return $"occupied=[{string.Join(", ", occupied)}] reserved=[{string.Join(", ", reserved)}]";
        }

        public bool TryReserveNextCell(UnitRuntime unit, GridPosition cell, out string reason)
        {
            if (unit == null)
            {
                reason = "Cannot reserve movement cell: unit is missing.";
                return false;
            }

            if (_reservedCells.TryGetValue(cell, out UnitRuntime existing) && existing != unit)
            {
                reason = $"Movement cell {cell} is reserved by another group unit.";
                return false;
            }

            _reservedCells[cell] = unit;
            reason = string.Empty;
            return true;
        }

        public bool IsReservedByOther(UnitRuntime unit, GridPosition cell)
        {
            return _reservedCells.TryGetValue(cell, out UnitRuntime existing) && existing != unit;
        }

        public void ClearForUnit(UnitRuntime unit)
        {
            if (unit == null)
            {
                return;
            }

            var cells = new List<GridPosition>();
            foreach (KeyValuePair<GridPosition, UnitRuntime> pair in _reservedCells)
            {
                if (pair.Value == unit)
                {
                    cells.Add(pair.Key);
                }
            }

            for (int i = 0; i < cells.Count; i++)
            {
                _reservedCells.Remove(cells[i]);
            }

            ReleaseAttackSlot(unit);
        }

        public void ClearAll()
        {
            _reservedCells.Clear();
            _attackTargetByAttacker.Clear();
            _slotsByTarget.Clear();
        }

        private TargetSlots GetOrCreateTargetSlots(UnitRuntime target)
        {
            if (!_slotsByTarget.TryGetValue(target, out TargetSlots slots))
            {
                slots = new TargetSlots
                {
                    LastKnownTargetCell = target.GridPos
                };
                _slotsByTarget[target] = slots;
            }

            return slots;
        }

        private bool IsAttackSlotStillValid(UnitRuntime attacker, UnitRuntime target, GridPosition slot, int range)
        {
            if (slot == target.GridPos || slot.ChebyshevDistance(target.GridPos) > range)
            {
                return false;
            }

            if (!_pathfinding.IsCellAvailableForMove(attacker, slot, allowCurrentUnitCell: true))
            {
                return false;
            }

            return slot == attacker.GridPos
                   || _pathfinding.TryFindPath(attacker, slot, out _, out _);
        }

        private List<GridPosition> BuildAttackCandidates(UnitRuntime attacker, UnitRuntime target, int attackRange)
        {
            var candidates = new List<GridPosition>();
            bool isMelee = attackRange <= 1;

            if (_pathfinding.IsTargetInAttackRange(attacker, target))
            {
                candidates.Add(attacker.GridPos);
            }

            for (int y = target.GridPos.Y - attackRange; y <= target.GridPos.Y + attackRange; y++)
            {
                for (int x = target.GridPos.X - attackRange; x <= target.GridPos.X + attackRange; x++)
                {
                    GridPosition cell = new GridPosition(x, y);
                    if (cell == target.GridPos || cell.ChebyshevDistance(target.GridPos) > attackRange)
                    {
                        continue;
                    }

                    if (isMelee && cell.ChebyshevDistance(target.GridPos) != 1)
                    {
                        continue;
                    }

                    if (!isMelee && cell.ChebyshevDistance(target.GridPos) == 1)
                    {
                        // Keep melee-adjacent cells free for melee units when possible.
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
                for (int y = target.GridPos.Y - attackRange; y <= target.GridPos.Y + attackRange; y++)
                {
                    for (int x = target.GridPos.X - attackRange; x <= target.GridPos.X + attackRange; x++)
                    {
                        GridPosition cell = new GridPosition(x, y);
                        if (cell == target.GridPos
                            || cell.ChebyshevDistance(target.GridPos) > attackRange
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

                int xComparison = left.X.CompareTo(right.X);
                return xComparison != 0 ? xComparison : left.Y.CompareTo(right.Y);
            });

            return candidates;
        }

        private bool TryPickBestUnclaimedSlot(UnitRuntime attacker, TargetSlots slots, List<GridPosition> candidates, out GridPosition best)
        {
            best = default;
            var claimedByOthers = new HashSet<GridPosition>();
            foreach (KeyValuePair<UnitRuntime, GridPosition> pair in slots.SlotsByAttacker)
            {
                if (pair.Key != null && pair.Key != attacker)
                {
                    claimedByOthers.Add(pair.Value);
                }
            }

            int bestPathLength = int.MaxValue;
            bool found = false;
            for (int i = 0; i < candidates.Count; i++)
            {
                GridPosition candidate = candidates[i];
                if (claimedByOthers.Contains(candidate))
                {
                    continue;
                }

                int pathLength = 0;
                if (candidate != attacker.GridPos)
                {
                    if (!_pathfinding.TryFindPath(attacker, candidate, out List<GridPosition> path, out _))
                    {
                        continue;
                    }

                    pathLength = path.Count;
                }

                if (!found
                    || pathLength < bestPathLength
                    || (pathLength == bestPathLength && CompareCells(candidate, best) < 0))
                {
                    best = candidate;
                    bestPathLength = pathLength;
                    found = true;
                }
            }

            return found;
        }

        private void ResolveReferences()
        {
            _pathfinding ??= FindFirstObjectByType<GridPathfindingService>();
            _gridManager ??= GridManager.Instance != null ? GridManager.Instance : FindFirstObjectByType<GridManager>();
        }

        private static int CompareCells(GridPosition left, GridPosition right)
        {
            int xComparison = left.X.CompareTo(right.X);
            return xComparison != 0 ? xComparison : left.Y.CompareTo(right.Y);
        }

        private sealed class TargetSlots
        {
            public GridPosition LastKnownTargetCell;
            public readonly Dictionary<UnitRuntime, GridPosition> SlotsByAttacker = new Dictionary<UnitRuntime, GridPosition>();
        }
    }
}
