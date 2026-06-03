// BuildingRuntime.cs — MonoBehaviour для зданий с производством (базы).
// Этап 3: Экономика. Неделя 2.

using UnityEngine;
using RTS.Core;

namespace RTS.Gameplay
{
    /// <summary>
    /// MonoBehaviour-адаптер для зданий, которые могут производить юнитов.
    /// Содержит ProductionQueue и логику тика для AdvanceProduction().
    /// </summary>
    public class BuildingRuntime : MonoBehaviour
    {
        // ── Ссылки ─────────────────────────────────────────────────────────────

        private UnitRuntime _unitRuntime;
        private ProductionQueue _productionQueue;

        // ── Конфигурация ───────────────────────────────────────────────────────

        [Header("Production")]
        [SerializeField] private bool _canProduce = true;
        [SerializeField] private bool _logProductionEvents;

        // ── Events ──────────────────────────────────────────────────────────────

        /// <summary>Вызывается, когда производство завершено и юнит создан.</summary>
        public System.Action<UnitType> OnUnitProduced;

        // ── Unity lifecycle ───────────────────────────────────────────────────

        private void Start()
        {
            // Для объектов, созданных UnitFactory, UnitRuntime.Init вызывается
            // до Start, поэтому здесь безопасно инициализировать очередь.
            EnsureInitialized();
        }

        private void OnDestroy()
        {
            if (_productionQueue != null)
            {
                _productionQueue.OnProductionComplete -= HandleProductionComplete;
            }
        }

        // ── Tick logic (вызывается из EpisodeController или MatchManager) ────────

        /// <summary>
        /// Продвигает производство на один тик (вызывается каждый игровой шаг).
        /// </summary>
        public void TickProduction()
        {
            if (!EnsureInitialized()) return;
            if (!_canProduce || _productionQueue == null) return;

            if (_productionQueue.AdvanceProduction())
            {
                // Производство завершено — будет вызван OnProductionComplete
            }
        }

        // ── Public API ───────────────────────────────────────────────────────────

        /// <summary>
        /// Начать производство юнита. Проверяет ресурсы игрока.
        /// </summary>
        public bool StartProducingUnit(UnitType unitType, GameConfig config)
        {
            if (!EnsureInitialized()) return false;
            if (_unitRuntime == null || !_canProduce) return false;

            var definition = config.GetDefinition(unitType);
            if (definition == null)
            {
                LogProductionWarning($"[BuildingRuntime] UnitDefinition не найден для {unitType}");
                return false;
            }

            // Проверяем ресурсы
            var playerState = MatchManager.Instance?.GetPlayerState(_unitRuntime.Owner);
            if (playerState == null)
            {
                LogProductionWarning($"[BuildingRuntime] PlayerState не найден для {_unitRuntime.Owner}");
                return false;
            }

            if (!playerState.CanAfford(definition.productionCost))
            {
                if (_logProductionEvents)
                {
                    Debug.Log($"[BuildingRuntime] insufficient resources for {unitType} (cost {definition.productionCost})");
                }
                playerState.OnInsufficientResources?.Invoke(definition.productionCost);
                return false;
            }

                // Не начинаем новое производство, если уже идёт текущее
                if (_productionQueue.IsProducing)
                    return false;

                // Тратим ресурсы и начинаем производство
            playerState.SpendResources(definition.productionCost);
            _productionQueue.StartProduction(unitType, definition);

            if (_logProductionEvents)
            {
                Debug.Log($"[BuildingRuntime] {_unitRuntime.Owner} starts producing {unitType} ({definition.productionTime} ticks)");
            }
            return true;
        }

        /// <summary>
        /// Отменить текущее производство (без возврата ресурсов на Неделе 2).
        /// </summary>
        public void CancelProduction()
        {
            if (_productionQueue != null)
            {
                _productionQueue.CancelProduction();
            }
        }

        /// <summary>
        /// Получить текущую очередь производства (для UI).
        /// </summary>
        public ProductionQueue GetProductionQueue() => _productionQueue;

        /// <summary>
        /// Сбросить производство (для reset эпизода).
        /// </summary>
        public void ResetProduction()
        {
            if (!EnsureInitialized()) return;

            _productionQueue.ResetForEpisode();
        }

        // ── Event handlers ───────────────────────────────────────────────────────

        private void HandleProductionComplete(UnitType producedType, GridPosition buildingPos)
        {
            if (_unitRuntime == null) return;

            // Ищем соседнюю свободную клетку для спавна
            var neighborPos = FindFreeNeighborCell(buildingPos);
            if (!neighborPos.HasValue)
            {
                LogProductionWarning($"[BuildingRuntime] Нет свободной ячейки рядом с {buildingPos} для спавна {producedType}");
                return;
            }

            // Спавним юнит через UnitFactory
            var gridMgr = GridManager.Instance;
            var config = MatchBootstrap.Instance?.GetConfig();

            if (config == null)
            {
                Debug.LogError("[BuildingRuntime] GameConfig не найден!");
                return;
            }

            var factory = new UnitFactory(config, gridMgr, gridMgr?.transform, UnitRegistry.Instance);
            var spawnedUnit = factory.Spawn(producedType, _unitRuntime.Owner, neighborPos.Value);
            if (spawnedUnit == null)
            {
                LogProductionWarning($"[BuildingRuntime] Не удалось заспавнить {producedType} в {neighborPos.Value}");
                return;
            }
            
            // Регистрируем в PlayerState
            var playerState = MatchManager.Instance?.GetPlayerState(_unitRuntime.Owner);
            if (playerState != null)
            {
                playerState.RegisterUnit();
            }

            OnUnitProduced?.Invoke(producedType);
            if (_logProductionEvents)
            {
                Debug.Log($"[BuildingRuntime] {_unitRuntime.Owner}: produced {producedType} at {neighborPos.Value}");
            }
        }

        /// <summary>
        /// Найти соседнюю свободную клетку (простой поиск в 3×3).
        /// </summary>
        private GridPosition? FindFreeNeighborCell(GridPosition center)
        {
            var gridMgr = GridManager.Instance;
            if (gridMgr == null) return null;

            // Проверяем соседей в 3×3 вокруг здания
            for (int dy = -1; dy <= 1; dy++)
            {
                for (int dx = -1; dx <= 1; dx++)
                {
                    if (dx == 0 && dy == 0) continue; // пропускаем саму позицию

                    var neighbor = new GridPosition(center.X + dx, center.Y + dy);

                    // Проверяем границы и занятость
                    if (gridMgr.IsInside(neighbor) && !gridMgr.IsCellOccupied(neighbor))
                    {
                        return neighbor;
                    }
                }
            }

            return null;
        }

        /// <summary>
        /// Ленивая инициализация ссылки на UnitRuntime и очереди производства.
        /// Позволяет корректно работать при добавлении компонента на prefab,
        /// где UnitRuntime добавляется позже фабрикой во время спавна.
        /// </summary>
        private bool EnsureInitialized()
        {
            _unitRuntime = GetComponent<UnitRuntime>();
            if (_unitRuntime == null)
                return false;

            if (_productionQueue == null ||
                _productionQueue.Owner != _unitRuntime.Owner ||
                _productionQueue.BuildingPosition != _unitRuntime.GridPos)
            {
                if (_productionQueue != null)
                {
                    _productionQueue.OnProductionComplete -= HandleProductionComplete;
                }

                _productionQueue = new ProductionQueue(_unitRuntime.Owner, _unitRuntime.GridPos);
                _productionQueue.OnProductionComplete += HandleProductionComplete;
            }

            return true;
        }

        private void LogProductionWarning(string message)
        {
            if (_logProductionEvents)
            {
                Debug.LogWarning(message);
            }
        }
    }
}
