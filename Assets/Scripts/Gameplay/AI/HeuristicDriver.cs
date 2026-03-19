// HeuristicDriver.cs — единая эвристическая AI для отладки матча без ML.
// Неделя 2, Этап 6.
// Координирует автоматические действия всех юнитов по простым эвристикам.

using System.Collections.Generic;
using UnityEngine;
using RTS.Core;

namespace RTS.Gameplay
{
    /// <summary>
    /// Singleton, управляющий автоматическими действиями всех юнитов по простым эвристикам.
    /// Позволяет запускать матч в автоматическом режиме без ML и без ручного управления.
    ///
    /// Эвристики по типам:
    /// - Worker: если несет ресурсы → идет к базе; если пусто и рядом ресурс → собирает;
    ///          иначе идет к ближайшему ресурсу
    /// - Base: если хватает ресурсов → производит рабочего до лимита
    /// - Combat: если враг в радиусе → атакует (в боевой фазе); иначе идет к ближайшему врагу
    /// </summary>
    [DisallowMultipleComponent]
    public class HeuristicDriver : MonoBehaviour
    {
        public static HeuristicDriver Instance { get; private set; }

        [SerializeField] private GameConfig _config;
        [SerializeField] private GridManager _gridManager;
        [SerializeField] private UnitRegistry _unitRegistry;
        [SerializeField] private ResourceManager _resourceManager;
        [SerializeField] private MatchManager _matchManager;

        [Header("Heuristic parameters")]
        [SerializeField] private float _nearbyResourceDistance = 2f;
        [SerializeField] private int _maxWorkerLimit = 5;
        [SerializeField] private bool _enableDebugLog = false;

        private Dictionary<UnitRuntime, GridPosition?> _unitTargets = new();

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
            ResolveReferences();
        }

        private void OnDestroy()
        {
            if (Instance == this)
                Instance = null;
        }

        /// <summary>
        /// Инициализирует ссылки после создания сцены.
        /// </summary>
        public void Initialize(GameConfig config, GridManager gridManager, UnitRegistry unitRegistry,
                               ResourceManager resourceManager, MatchManager matchManager)
        {
            _config = config;
            _gridManager = gridManager;
            _unitRegistry = unitRegistry;
            _resourceManager = resourceManager;
            _matchManager = matchManager;
        }

        /// <summary>
        /// Вызывается один раз перед началом матча для очистки состояния.
        /// </summary>
        public void ResetHeuristics()
        {
            _unitTargets.Clear();
        }

        /// <summary>
        /// Основной метод: принимает решения для всех юнитов.
        /// Вызывается из EpisodeController перед каждым StepMatch().
        /// </summary>
        public void MakeAllDecisions()
        {
            ResolveReferences();

            if (_gridManager == null || _unitRegistry == null || _matchManager == null || _config == null)
                return;

            var allUnits = _unitRegistry.GetAllUnits();
            foreach (var unit in allUnits)
            {
                if (unit == null || !unit.Model.IsAlive)
                    continue;

                MakeUnitDecision(unit);
            }
        }

        /// <summary>
        /// Принимает решение для одного юнита в зависимости от его типа.
        /// </summary>
        private void MakeUnitDecision(UnitRuntime unit)
        {
            if (unit.Type == UnitType.Worker)
            {
                DecideWorkerAction(unit);
            }
            else if (unit.Type == UnitType.Base)
            {
                DecideBaseAction(unit);
            }
            else if (unit.Type == UnitType.Light || unit.Type == UnitType.Heavy || unit.Type == UnitType.Ranged)
            {
                DecideCombatUnitAction(unit);
            }
        }

        /// <summary>
        /// Логика поведения рабочего:
        /// 1. Если несет ресурсы → идет к базе
        /// 2. Если пусто и есть ресурс рядом → собирает
        /// 3. Иначе движется к ближайшему ресурсу
        /// </summary>
        private void DecideWorkerAction(UnitRuntime worker)
        {
            var playerState = _matchManager?.GetPlayerState(worker.Owner);
            if (playerState == null)
                return;

            // 1. Если несет ресурсы → идет к базе
            if (worker.CarriedResources > 0)
            {
                var myBase = FindNearestBase(worker.GridPos, worker.Owner);
                if (myBase != null)
                {
                    // Рабочий не может стоять в клетке базы, поэтому сдаем при соседстве.
                    if (GetManhattanDistance(worker.GridPos, myBase.GridPos) <= 1)
                    {
                        DepositResources(worker, playerState);
                        _unitTargets.Remove(worker);
                    }
                    else
                    {
                        MoveTowards(worker, myBase.GridPos);
                    }
                }
                return;
            }

            // 2. Если ресурс в той же клетке, собираем
            var resourceHere = _resourceManager?.GetResourceNode(worker.GridPos);
            if (resourceHere != null && !resourceHere.IsExhausted)
            {
                HarvestResource(resourceHere, worker);
                return;
            }

            // 3А. Если пусто и есть ресурс рядом, пытаемся подойти
            var nearbyResource = FindNearestResourceInRange(worker.GridPos, _nearbyResourceDistance);
            if (nearbyResource != null)
            {
                MoveTowards(worker, nearbyResource.GridPosition);
                return;
            }

            // 3B. Иначе движется к ближайшему ресурсу
            var targetResource = FindNearestResource(worker.GridPos);
            if (targetResource != null)
            {
                MoveTowards(worker, targetResource.GridPosition);
            }
        }

        /// <summary>
        /// Логика базы:
        /// Если хватает ресурсов → производит рабочего до лимита
        /// </summary>
        private void DecideBaseAction(UnitRuntime baseUnit)
        {
            var playerState = _matchManager?.GetPlayerState(baseUnit.Owner);
            if (playerState == null)
                return;

            // Получаем компонент BuildingRuntime для производства
            var building = baseUnit.GetComponent<BuildingRuntime>();
            if (building == null)
                return;

            // Проверяем текущий лимит рабочих
            var myUnits = _unitRegistry.GetUnitsByOwner(baseUnit.Owner);
            int currentWorkerCount = 0;
            foreach (var u in myUnits)
            {
                if (u.Type == UnitType.Worker)
                    currentWorkerCount++;
            }

            // Если есть слоты и ресурсов хватает → производим рабочего
            if (currentWorkerCount < _maxWorkerLimit)
            {
                var workerDef = _config.GetDefinition(UnitType.Worker);
                if (workerDef != null && playerState.CanAfford(workerDef.productionCost))
                {
                    building.StartProducingUnit(UnitType.Worker, _config);
                }
            }
        }

        /// <summary>
        /// Логика боевого юнита:
        /// 1. Если враг в радиусе атаки → остается на месте и атакует в боевой фазе
        /// 2. Иначе идет к ближайшему врагу
        /// </summary>
        private void DecideCombatUnitAction(UnitRuntime combatUnit)
        {
            var definition = _config?.GetDefinition(combatUnit.Type);
            if (definition == null)
                return;

            // Ищем врагов в радиусе атаки
            var enemyInRange = FindNearestEnemyInRange(combatUnit.GridPos, combatUnit.Owner, definition.attackRange);

            if (enemyInRange != null)
            {
                // Если враг уже в радиусе, остаемся на месте: атака пройдет в CombatResolver.
                return;
            }

            // Ищем ближайшего врага на карте
            var nearestEnemy = FindNearestEnemy(combatUnit.GridPos, combatUnit.Owner);
            if (nearestEnemy != null)
            {
                MoveTowards(combatUnit, nearestEnemy.GridPos);
            }
        }

        // ── Вспомогательные методы поиска ────────────────────────────────────────

        /// <summary>
        /// Находит ближайшую базу (здание) принадлежащее игроку от заданной позиции.
        /// </summary>
        private UnitRuntime FindNearestBase(GridPosition from, Owner owner)
        {
            var buildings = _unitRegistry.GetBuildingsByOwner(owner);
            if (buildings == null || buildings.Count == 0)
                return null;

            UnitRuntime nearest = null;
            int minDist = int.MaxValue;

            foreach (var building in buildings)
            {
                if (building.Type != UnitType.Base)
                    continue;

                int dist = GetManhattanDistance(from, building.GridPos);
                if (dist < minDist)
                {
                    minDist = dist;
                    nearest = building;
                }
            }

            return nearest;
        }

        /// <summary>
        /// Находит ближайший ресурс в заданном диапазоне.
        /// </summary>
        private ResourceNode FindNearestResourceInRange(GridPosition from, float range)
        {
            var allResources = _resourceManager?.GetAllResourceNodes();
            if (allResources == null)
                return null;

            ResourceNode nearest = null;
            int minDist = int.MaxValue;

            foreach (var res in allResources)
            {
                if (res.IsExhausted)
                    continue;

                int dist = GetManhattanDistance(from, res.GridPosition);
                if (dist <= range && dist < minDist)
                {
                    minDist = dist;
                    nearest = res;
                }
            }

            return nearest;
        }

        /// <summary>
        /// Находит ближайший ресурс на карте.
        /// </summary>
        private ResourceNode FindNearestResource(GridPosition from)
        {
            var allResources = _resourceManager?.GetAllResourceNodes();
            if (allResources == null)
                return null;

            ResourceNode nearest = null;
            int minDist = int.MaxValue;

            foreach (var res in allResources)
            {
                if (res.IsExhausted)
                    continue;

                int dist = GetManhattanDistance(from, res.GridPosition);
                if (dist < minDist)
                {
                    minDist = dist;
                    nearest = res;
                }
            }

            return nearest;
        }

        /// <summary>
        /// Находит ближайшего врага в заданном радиусе атаки.
        /// </summary>
        private UnitRuntime FindNearestEnemyInRange(GridPosition from, Owner owner, int attackRange)
        {
            var allUnits = _unitRegistry.GetAllUnits();
            if (allUnits == null || allUnits.Count == 0)
                return null;

            UnitRuntime nearest = null;
            int minDist = int.MaxValue;

            foreach (var unit in allUnits)
            {
                if (!IsEnemy(unit, owner))
                    continue;

                int dist = GetManhattanDistance(from, unit.GridPos);
                if (dist <= attackRange && dist < minDist)
                {
                    minDist = dist;
                    nearest = unit;
                }
            }

            return nearest;
        }

        /// <summary>
        /// Находит ближайшего врага на карте.
        /// </summary>
        private UnitRuntime FindNearestEnemy(GridPosition from, Owner owner)
        {
            var allUnits = _unitRegistry.GetAllUnits();
            if (allUnits == null || allUnits.Count == 0)
                return null;

            UnitRuntime nearest = null;
            int minDist = int.MaxValue;

            foreach (var unit in allUnits)
            {
                if (!IsEnemy(unit, owner))
                    continue;

                int dist = GetManhattanDistance(from, unit.GridPos);
                if (dist < minDist)
                {
                    minDist = dist;
                    nearest = unit;
                }
            }

            return nearest;
        }

        // ── Действия юнитов ──────────────────────────────────────────────────────

        /// <summary>
        /// Движется в сторону целевой позиции (жадный алгоритм в сторону цели).
        /// </summary>
        private void MoveTowards(UnitRuntime unit, GridPosition target)
        {
            if (_gridManager == null || !_gridManager.IsInside(target))
                return;

            // Если уже в целевой позиции, очищаем цель
            if (unit.GridPos == target)
            {
                _unitTargets.Remove(unit);
                return;
            }

            // Выбираем соседнюю клетку в сторону целевой позиции
            var nextStep = FindPathStep(unit.GridPos, target);
            if (nextStep.HasValue && _gridManager.IsWalkable(nextStep.Value))
            {
                try
                {
                    _gridManager.MoveUnit(unit, unit.GridPos, nextStep.Value);
                    _unitTargets[unit] = target;

                    if (_enableDebugLog)
                        Debug.Log($"[HeuristicDriver] {unit.Owner}_{unit.Type} moved to {nextStep.Value}");
                }
                catch (System.Exception ex)
                {
                    Debug.LogWarning($"[HeuristicDriver] Move failed: {ex.Message}");
                }
            }
        }

        /// <summary>
        /// Простой поиск соседней клетки в сторону целевой позиции (жадно).
        /// </summary>
        private GridPosition? FindPathStep(GridPosition from, GridPosition to)
        {
            GridPosition? bestNeighbor = null;
            int bestDist = int.MaxValue;

            // Проверяем все 8 соседей (диагональные тоже)
            for (int dy = -1; dy <= 1; dy++)
            {
                for (int dx = -1; dx <= 1; dx++)
                {
                    if (dx == 0 && dy == 0) continue;

                    var neighbor = new GridPosition(from.X + dx, from.Y + dy);

                    if (!_gridManager.IsWalkable(neighbor))
                        continue;

                    int dist = GetManhattanDistance(neighbor, to);
                    if (dist < bestDist)
                    {
                        bestDist = dist;
                        bestNeighbor = neighbor;
                    }
                }
            }

            return bestNeighbor;
        }

        /// <summary>
        /// Сбор ресурсов из узла.
        /// </summary>
        private void HarvestResource(ResourceNode resourceNode, UnitRuntime unit)
        {
            if (resourceNode == null || unit == null)
                return;

            int harvestedAmount = resourceNode.Harvest(GameConstants.HarvestAmount);
            if (harvestedAmount > 0)
            {
                int added = unit.Model.AddCarriedResources(harvestedAmount);
                if (_enableDebugLog)
                    Debug.Log($"[HeuristicDriver] {unit.Owner}_{unit.Type} harvested {harvestedAmount} at {resourceNode.GridPosition}");
            }
        }

        /// <summary>
        /// Сдача ресурсов на базу.
        /// </summary>
        private void DepositResources(UnitRuntime unit, PlayerState playerState)
        {
            if (playerState == null)
                return;

            int dropped = unit.Model.DropAllCarriedResources();
            playerState.AddResources(dropped);

            if (_enableDebugLog)
                Debug.Log($"[HeuristicDriver] {unit.Owner}_{unit.Type} deposited {dropped} resources");
        }

        // ── Утилиты ────────────────────────────────────────────────────────────────

        private bool IsEnemy(UnitRuntime unit, Owner myOwner)
        {
            return unit != null && unit.Owner != myOwner && unit.Owner != Owner.Neutral;
        }

        private int GetManhattanDistance(GridPosition a, GridPosition b)
        {
            return Mathf.Abs(a.X - b.X) + Mathf.Abs(a.Y - b.Y);
        }

        private void ResolveReferences()
        {
            if (_gridManager == null)
                _gridManager = GridManager.Instance;

            if (_unitRegistry == null)
                _unitRegistry = UnitRegistry.Instance;

            if (_resourceManager == null)
                _resourceManager = ResourceManager.Instance;

            if (_matchManager == null)
                _matchManager = MatchManager.Instance;

            if (_config == null)
                _config = MatchBootstrap.Instance?.GetConfig();
        }
    }
}
