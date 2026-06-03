// CombatResolver.cs — отдельный сервис боевой логики.
// Этап 4: Бой. Неделя 2.

using System.Collections.Generic;
using UnityEngine;
using RTS.Core;
using RTS.Presentation;
using Unity.Profiling;

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
        private readonly bool _logCombatEvents;

        
        public int LastAttackersEvaluated { get; private set; }
        public int LastTargetCellChecks { get; private set; }
private static readonly ProfilerMarker ResolveCombatTickMarker = new ProfilerMarker("CombatResolver.ResolveCombatTick");

        public CombatResolver(
            GameConfig config,
            UnitRegistry unitRegistry,
            GridManager gridManager,
            MatchManager matchManager,
            bool logCombatEvents = false)
        {
            _config = config;
            _unitRegistry = unitRegistry;
            _gridManager = gridManager;
            _matchManager = matchManager;
            _logCombatEvents = logCombatEvents;
        }

        /// <summary>
        /// Выполняет боевую фазу одного тика.
        /// Каждый атакующий юнит может нанести один удар.
        /// </summary>
public int ResolveCombatTick(ISet<UnitRuntime> skipAttackers = null)
        {
            using var marker = ResolveCombatTickMarker.Auto();
            LastAttackersEvaluated = 0;
            LastTargetCellChecks = 0;
            if (_config == null || _unitRegistry == null) return 0;

            IReadOnlyList<UnitRuntime> unitsSnapshot = _unitRegistry.GetAllUnitsReadOnly();
            int attacksResolved = 0;

            foreach (var attacker in unitsSnapshot)
            {
                if (!CanActAsAttacker(attacker)) continue;
                if (skipAttackers != null && skipAttackers.Contains(attacker)) continue;

                LastAttackersEvaluated++;
                var target = FindTargetInRange(attacker);
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

            if (_logCombatEvents)
            {
                Debug.Log($"[CombatResolver] {attacker.Owner}.{attacker.Type} attacks {target.Owner}.{target.Type} damage={attackerDef.attackDamage} distance={GetDistance(attacker.GridPos, target.GridPos)}");
            }

            TryGetVisualBridge(attacker)?.OnVisualAttack();
            TryGetVisualBridge(target)?.OnVisualHit();

            bool died = target.TakeDamage(attackerDef.attackDamage);
            if (died)
            {
                HandleDeath(target, attacker.Owner);
            }

            return true;
        }

private UnitRuntime FindTargetInRange(UnitRuntime attacker)
        {
            var attackerDef = _config.GetDefinition(attacker.Type);
            if (attackerDef == null || _gridManager == null) return null;

            int range = attackerDef.attackRange;
            GridPosition origin = attacker.GridPos;
            UnitRuntime bestTarget = null;
            int bestDistance = int.MaxValue;
            int bestHp = int.MaxValue;

            int minX = Mathf.Max(0, origin.X - range);
            int maxX = Mathf.Min(_gridManager.Width - 1, origin.X + range);
            int minY = Mathf.Max(0, origin.Y - range);
            int maxY = Mathf.Min(_gridManager.Height - 1, origin.Y + range);

            for (int y = minY; y <= maxY; y++)
            {
                for (int x = minX; x <= maxX; x++)
                {
                    LastTargetCellChecks++;
                    GridPosition pos = new GridPosition(x, y);
                    if (!_gridManager.TryGetOccupant(pos, out UnitRuntime candidate))
                    {
                        continue;
                    }

                    if (!CanBeTarget(attacker, candidate)) continue;

                    int distance = GetDistance(origin, candidate.GridPos);
                    if (distance > range) continue;

                    if (distance < bestDistance || (distance == bestDistance && candidate.HP < bestHp))
                    {
                        bestTarget = candidate;
                        bestDistance = distance;
                        bestHp = candidate.HP;
                    }
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

            if (_logCombatEvents)
            {
                Debug.Log($"[CombatResolver] {deadUnit.Owner}.{deadUnit.Type} destroyed by {killerOwner} at {deadUnit.GridPos}");
            }

            TryGetVisualBridge(deadUnit)?.OnVisualDeath();
            VisualDeathPlaybackSpawner.TrySpawn(deadUnit, out _, out _);

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

            if (deadUnit.GetComponent<StaticSceneEntityAuthoring>() != null)
            {
                deadUnit.gameObject.SetActive(false);
                return;
            }

            Object.Destroy(deadUnit.gameObject);
        }

        private static VisualEventBridge TryGetVisualBridge(UnitRuntime unit)
        {
            if (unit == null)
            {
                return null;
            }

            return unit.GetComponent<VisualEventBridge>()
                   ?? unit.GetComponentInParent<VisualEventBridge>(true)
                   ?? unit.GetComponentInChildren<VisualEventBridge>(true);
        }

        private static bool IsPlayerUnit(Owner owner)
            => owner == Owner.Player1 || owner == Owner.Player2;
    }
}
