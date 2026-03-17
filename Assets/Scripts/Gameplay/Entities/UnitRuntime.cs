// UnitRuntime.cs — MonoBehaviour-адаптер над UnitModel.
// Неделя 2, Этап 2 (Игровые сущности).

using UnityEngine;
using RTS.Core;

namespace RTS.Gameplay
{
    /// <summary>
    /// MonoBehaviour-компонент, прикреплённый к GameObject каждого юнита.
    ///
    /// Визуальный/сценовый слой хранится здесь,
    /// а все игровые данные — в <see cref="UnitModel"/>.
    /// Это разделяет логику данных и Unity-представление.
    ///
    /// GridManager является единственным, кто обновляет <see cref="GridPos"/> —
    /// напрямую записывать это свойство из других компонентов не следует.
    /// </summary>
    public class UnitRuntime : MonoBehaviour
    {
        [Header("View Sync")]
        [Tooltip("Если true, позиция transform синхронизируется с GridPos.")]
        [SerializeField] private bool syncTransformToGrid = true;

        [Tooltip("Вертикальный оффсет модели относительно поверхности клетки.")]
        [SerializeField] private float worldYOffset = 0f;

        [Header("Orientation")]
        [Tooltip("Начальное направление взгляда при Init().")]
        [SerializeField] private Direction initialFacing = Direction.South;

        // ── Data model ────────────────────────────────────────────────────────

        public UnitModel Model { get; private set; }

        // ── Совместимый API (обёртки над Model) ──────────────────────────────

        public UnitType Type => Model != null ? Model.Type : default;
        public Owner Owner => Model != null ? Model.Owner : Owner.Neutral;
        public int MaxHP => Model != null ? Model.MaxHP : 0;
        public int HP => Model != null ? Model.CurrentHP : 0;
        public int CarriedResources => Model != null ? Model.CarriedResources : 0;
        public bool IsBuilding => Model != null && Model.IsBuilding;
        public Direction Facing { get; private set; } = Direction.South;

        /// <summary>
        /// Текущая логическая позиция на сетке.
        /// Устанавливается только через GridManager.TryPlaceUnit / MoveUnit.
        /// </summary>
        public GridPosition GridPos
        {
            get => Model != null ? Model.GridPosition : GridPosition.Zero;
            internal set
            {
                if (Model == null) return;
                Model.SetGridPosition(value);
                SyncTransformToGrid();
            }
        }

        // ── Инициализация ─────────────────────────────────────────────────────

        /// <summary>
        /// Инициализирует рантайм-состояние из определения и стартовых параметров.
        /// Вызывается SpawnSystem / EpisodeManager сразу после Instantiate.
        /// </summary>
        public void Init(UnitDefinition def, Owner owner, GridPosition startPos)
        {
            if (def == null)
            {
                Debug.LogError("[UnitRuntime] Init: def == null");
                return;
            }

            Model = UnitModel.FromDefinition(def, owner, startPos);
            Facing = initialFacing;
            SyncTransformToGrid();
            ApplyFacingToTransform(Facing);

            name = $"{owner}_{def.unitType}_{startPos}";
        }

        // ── Команды юнита (без глобальной логики матча) ─────────────────────

        /// <summary>
        /// Команда перемещения в целевую клетку.
        /// Проверка валидности и обновление occupancy выполняются GridManager.
        /// </summary>
        public bool MoveTo(GridPosition target, GridManager gridManager = null)
        {
            if (Model == null)
            {
                Debug.LogError("[UnitRuntime] MoveTo: Model is null. Call Init first.");
                return false;
            }

            if (target == GridPos)
            {
                SyncTransformToGrid();
                return true;
            }

            gridManager ??= GridManager.Instance;
            if (gridManager == null)
            {
                Debug.LogError("[UnitRuntime] MoveTo: GridManager не найден.");
                return false;
            }

            var from = GridPos;
            var delta = target - from;
            if (delta.X > 0) SetFacing(Direction.East);
            else if (delta.X < 0) SetFacing(Direction.West);
            else if (delta.Y > 0) SetFacing(Direction.North);
            else if (delta.Y < 0) SetFacing(Direction.South);

            gridManager.MoveUnit(this, from, target);
            return GridPos == target;
        }

        /// <summary>
        /// Команда поворота юнита. Не влияет на глобальное состояние матча.
        /// </summary>
        public void SetFacing(Direction direction)
        {
            Facing = direction;
            ApplyFacingToTransform(direction);
        }

        // ── Урон / смерть ─────────────────────────────────────────────────────

        /// <summary>Применяет урон. Возвращает true, если юнит погиб.</summary>
        public bool TakeDamage(int amount)
        {
            if (Model == null)
            {
                Debug.LogError("[UnitRuntime] TakeDamage: Model is null. Call Init first.");
                return false;
            }

            return Model.TakeDamage(amount);
        }

        public bool IsAlive => Model != null && Model.IsAlive;

        public int AddCarriedResources(int amount)
        {
            if (Model == null) return 0;
            return Model.AddCarriedResources(amount);
        }

        public int DropAllCarriedResources()
        {
            if (Model == null) return 0;
            return Model.DropAllCarriedResources();
        }

        // ── Внутренняя синхронизация представления ───────────────────────────

        private void SyncTransformToGrid()
        {
            if (!syncTransformToGrid || Model == null) return;

            var world = GridPos.ToWorldPosition();
            world.y += worldYOffset;
            transform.position = world;
        }

        private void ApplyFacingToTransform(Direction direction)
        {
            float yaw = direction switch
            {
                Direction.North => 0f,
                Direction.East => 90f,
                Direction.South => 180f,
                Direction.West => 270f,
                _ => 0f
            };

            transform.rotation = Quaternion.Euler(0f, yaw, 0f);
        }

        // ── Удобства ──────────────────────────────────────────────────────────

        public override string ToString()
            => $"{Owner}.{Type}@{GridPos} HP={HP}/{MaxHP} Carry={CarriedResources}";

        private void OnDestroy()
        {
            if (UnitRegistry.Instance != null)
                UnitRegistry.Instance.Unregister(this);
        }
    }
}
