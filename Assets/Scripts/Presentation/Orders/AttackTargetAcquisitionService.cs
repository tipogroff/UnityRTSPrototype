using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.Presentation.Orders
{
    [DisallowMultipleComponent]
    public sealed class AttackTargetAcquisitionService : MonoBehaviour
    {
        [SerializeField] private UnitRegistry _unitRegistry;

        public bool TryFindBestEnemyNearCell(
            Owner attackerOwner,
            GridPosition clickedCell,
            int searchRadius,
            out UnitRuntime target,
            out string reason)
        {
            List<UnitRuntime> enemies = FindEnemiesInArea(attackerOwner, clickedCell, searchRadius);
            target = enemies.Count > 0 ? enemies[0] : null;
            reason = target != null ? string.Empty : "No enemy target in attack area.";
            return target != null;
        }

        public List<UnitRuntime> FindEnemiesInArea(Owner attackerOwner, GridPosition centerCell, int searchRadius)
        {
            ResolveReferences();
            var enemies = new List<UnitRuntime>();
            if (_unitRegistry == null || attackerOwner == Owner.Neutral)
            {
                return enemies;
            }

            int radius = Mathf.Max(0, searchRadius);
            IReadOnlyList<UnitRuntime> units = _unitRegistry.GetAllUnitsReadOnly();
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime candidate = units[i];
                if (IsValidEnemyTarget(attackerOwner, candidate)
                    && centerCell.ChebyshevDistance(candidate.GridPos) <= radius)
                {
                    enemies.Add(candidate);
                }
            }

            enemies.Sort((left, right) => CompareTargets(centerCell, left, right));
            return enemies;
        }

        public bool IsValidEnemyTarget(Owner attackerOwner, UnitRuntime candidate)
        {
            return candidate != null
                   && candidate.IsAlive
                   && candidate.gameObject.activeInHierarchy
                   && attackerOwner != Owner.Neutral
                   && candidate.Owner != Owner.Neutral
                   && candidate.Owner != attackerOwner
                   && candidate.Type != UnitType.Resource;
        }

        private void ResolveReferences()
        {
            _unitRegistry ??= UnitRegistry.Instance != null ? UnitRegistry.Instance : FindFirstObjectByType<UnitRegistry>();
        }

        private static int CompareTargets(GridPosition center, UnitRuntime left, UnitRuntime right)
        {
            int distance = center.ChebyshevDistance(left.GridPos).CompareTo(center.ChebyshevDistance(right.GridPos));
            if (distance != 0) return distance;

            int hp = left.HP.CompareTo(right.HP);
            if (hp != 0) return hp;

            int x = left.GridPos.X.CompareTo(right.GridPos.X);
            if (x != 0) return x;

            int y = left.GridPos.Y.CompareTo(right.GridPos.Y);
            if (y != 0) return y;

            return left.GetInstanceID().CompareTo(right.GetInstanceID());
        }
    }
}
