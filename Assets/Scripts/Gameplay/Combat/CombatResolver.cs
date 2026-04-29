// CombatResolver.cs — отдельный сервис боевой логики.
// Этап 4: Бой. Неделя 2.

using System.Collections.Generic;
using UnityEngine;
using RTS.Core;

namespace RTS.Gameplay
{
    /// <summary>
    /// Сервис боевой фазы матча:
    /// - проверяет возможность атаки;
    /// - считает манхэттенское расстояние;
    /// - применяет урон;
    /// - удаляет юнита при смерти и синхронизирует реестры.
    ///
    /// Упрощение для Недели 2:
    /// - мгновенная атака без анимаций;
    /// - не более одного удара от юнита за тик.
    /// </summary>
    public sealed class CombatResolver
    {
        private readonly GameConfig _config;
        private readonly UnitRegistry _unitRegistry;
        private readonly GridManager _gridManager;
        private readonly MatchManager _matchManager;

        public CombatResolver(
            GameConfig config,
            UnitRegistry unitRegistry,
            GridManager gridManager,
            MatchManager matchManager)
        {
            _config = config;
            _unitRegistry = unitRegistry;
            _gridManager = gridManager;
            _matchManager = matchManager;
        }

        /// <summary>
        /// Выполняет боевую фазу одного тика.
        /// Каждый атакующий юнит может нанести один удар.
        /// </summary>
        public int ResolveCombatTick(ISet<UnitRuntime> skipAttackers = null)
        {
            if (_config == null || _unitRegistry == null) return 0;

            var unitsSnapshot = _unitRegistry.GetAllUnits();
            int attacksResolved = 0;

            foreach (var attacker in unitsSnapshot)
            {
                if (!CanActAsAttacker(attacker)) continue;
            if (skipAttackers != null && skipAttackers.Contains(attacker)) continue;

                var target = FindTargetInRange(attacker, unitsSnapshot);
                if (target == null) continue;

                if (TryAttack(attacker, target))
                    attacksResolved++;
            }

            return attacksResolved;
        }

        /// <summary>
        /// Проверяет, может ли атакующий ударить конкретную цель.
        /// </summary>
        public bool CanAttack(UnitRuntime attacker, UnitRuntime target)
        {
            if (!CanActAsAttacker(attacker)) return false;
            if (!CanBeTarget(attacker, target)) return false;

            var attackerDef = _config.GetDefinition(attacker.Type);
            if (attackerDef == null) return false;

            int distance = GetDistance(attacker.GridPos, target.GridPos);
            return distance <= attackerDef.attackRange;
        }

        /// <summary>
        /// Chebyshev-дистанция между клетками.
        ///
        /// Важно: должна совпадать с локальной target-семантикой в
        /// ActionContract/ActionDecoder/ActionApplier (диагонали валидны).
        /// </summary>
        public int GetDistance(GridPosition from, GridPosition to)
            => from.ChebyshevDistance(to);

        /// <summary>
        /// Применяет атаку: урон и обработку смерти цели.
        /// </summary>
        public bool TryAttack(UnitRuntime attacker, UnitRuntime target)
        {
            if (!CanAttack(attacker, target)) return false;

            var attackerDef = _config.GetDefinition(attacker.Type);
            if (attackerDef == null) return false;

            Debug.Log($"[CombatResolver] {attacker.Owner}.{attacker.Type} атакует {target.Owner}.{target.Type} с уроном {attackerDef.attackDamage} на дистанции {GetDistance(attacker.GridPos, target.GridPos)}");

            bool died = target.TakeDamage(attackerDef.attackDamage);
            if (died)
            {
                HandleDeath(target, attacker.Owner);
            }

            return true;
        }

        private UnitRuntime FindTargetInRange(UnitRuntime attacker, List<UnitRuntime> unitsSnapshot)
        {
            var attackerDef = _config.GetDefinition(attacker.Type);
            if (attackerDef == null) return null;

            UnitRuntime bestTarget = null;
            int bestDistance = int.MaxValue;
            int bestHp = int.MaxValue;

            foreach (var candidate in unitsSnapshot)
            {
                if (!CanBeTarget(attacker, candidate)) continue;

                int distance = GetDistance(attacker.GridPos, candidate.GridPos);
                if (distance > attackerDef.attackRange) continue;

                if (distance < bestDistance || (distance == bestDistance && candidate.HP < bestHp))
                {
                    bestTarget = candidate;
                    bestDistance = distance;
                    bestHp = candidate.HP;
                }
            }

            return bestTarget;
        }

        private bool CanActAsAttacker(UnitRuntime unit)
        {
            if (unit == null || !unit.IsAlive) return false;
            if (!IsPlayerUnit(unit.Owner)) return false;

            var def = _config.GetDefinition(unit.Type);
            if (def == null) return false;

            return def.attackDamage > 0 && def.attackRange > 0;
        }

        private static bool CanBeTarget(UnitRuntime attacker, UnitRuntime target)
        {
            if (attacker == null || target == null) return false;
            if (attacker == target) return false;
            if (!attacker.IsAlive || !target.IsAlive) return false;

            if (!IsPlayerUnit(attacker.Owner) || !IsPlayerUnit(target.Owner))
                return false;

            return attacker.Owner != target.Owner;
        }

        private void HandleDeath(UnitRuntime deadUnit, Owner killerOwner)
        {
            if (deadUnit == null) return;

            Debug.Log($"[CombatResolver] {deadUnit.Owner}.{deadUnit.Type} уничтожен игроком {killerOwner} на клетке {deadUnit.GridPos}");

            if (_gridManager != null &&
                _gridManager.TryGetOccupant(deadUnit.GridPos, out var occupant) &&
                occupant == deadUnit)
            {
                _gridManager.RemoveUnit(deadUnit.GridPos);
            }

            _unitRegistry?.Unregister(deadUnit);

            if (_matchManager != null)
            {
                if (IsPlayerUnit(killerOwner))
                    _matchManager.GetPlayerState(killerOwner)?.RegisterEnemyKill();

                if (IsPlayerUnit(deadUnit.Owner))
                    _matchManager.GetPlayerState(deadUnit.Owner)?.RegisterOwnLoss();
            }

            Object.Destroy(deadUnit.gameObject);
        }

        private static bool IsPlayerUnit(Owner owner)
            => owner == Owner.Player1 || owner == Owner.Player2;
    }
}
