using System.Collections.Generic;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.Presentation.Orders
{
    [DisallowMultipleComponent]
    public sealed class GroupOrderReservationService : MonoBehaviour
    {
        private readonly Dictionary<GridPosition, UnitRuntime> _reservedCells = new Dictionary<GridPosition, UnitRuntime>();

        public void BeginTick()
        {
            _reservedCells.Clear();
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
        }

        public void ClearAll()
        {
            _reservedCells.Clear();
        }
    }
}
