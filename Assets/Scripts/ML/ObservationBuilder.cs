// ObservationBuilder.cs — сборка тензора наблюдений для ML-агента.
// Неделя 3, День 2: Построение наблюдений с поддержкой двух режимов.
//
// РЕЖИМЫ:
// - compat-mode (LegacyGymCompatibleSpec): тензор совместим с Gym-μRTS.
// - extended/debug-mode (UnityMvpTransferSpec): расширенная форма для MVP.
//
// API: BuildObservation(playerId, mode) -> float[] длины TotalFloats.
// Включает валидацию размерности, encoding, стабильности формата.

using System;
using System.Collections.Generic;
using UnityEngine;
using RTS.Core;
using RTS.Gameplay;

namespace RTS.ML
{
    /// <summary>
    /// Режимы наблюдения целевой спецификации.
    /// </summary>
    public enum ObservationMode
    {
        /// <summary>
        /// Режим для тестирования совместимости с Gym-μRTS.
        /// Строго следует спецификации ObservationContract.
        /// </summary>
        LegacyGymCompatible = 0,

        /// <summary>
        /// Расширённый режим для MVP в Unity.
        /// Совместим с transfer pipeline, но может содержать доп. каналы/инфу.
        /// На текущий момент идентичен LegacyGymCompatible, но оставляется
        /// для будущих расширений (например, дополнительных global features).
        /// </summary>
        UnityMvpTransfer = 1,
    }

    /// <summary>
    /// Result of observation validation.
    ///
    /// This is a diagnostic contract-checking artifact. It does not change runtime behavior.
    /// </summary>
    public struct ObservationValidationResult
    {
        public bool IsValid;
        public List<string> Issues;

        public static ObservationValidationResult CreateValid()
        {
            return new ObservationValidationResult
            {
                IsValid = true,
                Issues = new List<string>()
            };
        }

        public static ObservationValidationResult Invalid(string issue)
        {
            var result = CreateValid();
            result.IsValid = false;
            result.Issues.Add(issue);
            return result;
        }

        public void Merge(ObservationValidationResult other)
        {
            if (!other.IsValid) IsValid = false;
            Issues.AddRange(other.Issues);
        }

        public override string ToString()
        {
            if (IsValid) return "✓ Valid";
            return $"✗ Invalid ({Issues.Count} issues):\n  " + string.Join("\n  ", Issues);
        }
    }

    /// <summary>
    /// Bundles the observation payload prepared for one player perspective.
    ///
    /// SpatialObservation is the stable Week 3 tensor. GlobalFeatures is Unity-only transfer
    /// metadata and therefore intentionally zero-filled in LegacyGymCompatible mode.
    /// </summary>
    public readonly struct ObservationPackage
    {
        public ObservationPackage(
            Owner playerId,
            ObservationMode mode,
            float[] spatialObservation,
            float[] globalFeatures)
        {
            PlayerId = playerId;
            Mode = mode;
            SpatialObservation = spatialObservation;
            GlobalFeatures = globalFeatures;
        }

        public Owner PlayerId { get; }
        public ObservationMode Mode { get; }
        public float[] SpatialObservation { get; }
        public float[] GlobalFeatures { get; }
    }

    /// <summary>
    /// Builds the Week 3 observation surface for one player perspective.
    ///
    /// This class owns observation semantics only. It does not validate or execute actions.
    /// Any runtime-authoritative action feasibility remains downstream in ActionApplier and
    /// MatchManager.
    /// </summary>
    public class ObservationBuilder
    {
        public const int GlobalFeaturesCount = 7;
        public const int GF_IS_RUNNING = 0;
        public const int GF_IS_TERMINAL = 1;
        public const int GF_IS_WIN = 2;
        public const int GF_IS_LOSS = 3;
        public const int GF_SELF_RESOURCES = 4;
        public const int GF_ENEMY_RESOURCES = 5;
        public const int GF_STEP_NORMALIZED = 6;

        private readonly GridManager _gridManager;
        private readonly UnitRegistry _unitRegistry;
        private readonly ResourceManager _resourceManager;
        private MatchManager _matchManager;

        // Буфер для переиспользования (чтобы не аллоцировать каждый раз)
        private float[] _observationBuffer;
        private float[] _globalFeaturesBuffer;

        // Временные коллекции для итераций
        private Dictionary<GridPosition, UnitRuntime> _unitsByPosition;
        private Dictionary<GridPosition, ResourceNode> _resourcesByPosition;
        private List<UnitRuntime> _allUnits;

        public ObservationBuilder(
            GridManager gridManager,
            UnitRegistry unitRegistry,
            ResourceManager resourceManager)
        {
            _gridManager = gridManager ?? throw new ArgumentNullException(nameof(gridManager));
            _unitRegistry = unitRegistry ?? throw new ArgumentNullException(nameof(unitRegistry));
            _resourceManager = resourceManager ?? throw new ArgumentNullException(nameof(resourceManager));
            _matchManager = MatchManager.Instance;

            // Инициализировать буфер
            _observationBuffer = new float[ObservationContract.TotalFloats];
            _globalFeaturesBuffer = new float[GlobalFeaturesCount];

            _unitsByPosition = new Dictionary<GridPosition, UnitRuntime>();
            _resourcesByPosition = new Dictionary<GridPosition, ResourceNode>();
            _allUnits = new List<UnitRuntime>();
        }

        /// <summary>
        /// Builds the Unity-only global feature vector.
        ///
        /// This method is part of the transfer adapter surface, not the legacy-compatible
        /// contract. In LegacyGymCompatible mode it returns the fixed-size zero buffer to avoid
        /// false parity claims with the reference spatial-only observation.
        /// </summary>
        public float[] BuildGlobalFeatures(Owner playerId, ObservationMode mode = ObservationMode.UnityMvpTransfer)
        {
            Array.Clear(_globalFeaturesBuffer, 0, _globalFeaturesBuffer.Length);

            if (mode != ObservationMode.UnityMvpTransfer)
            {
                return _globalFeaturesBuffer;
            }

            if (playerId == Owner.Neutral)
            {
                return _globalFeaturesBuffer;
            }

            _matchManager ??= MatchManager.Instance;
            if (_matchManager == null)
            {
                return _globalFeaturesBuffer;
            }

            MatchStateSnapshot snapshot = _matchManager.GetMatchState();
            _globalFeaturesBuffer[GF_IS_RUNNING] = snapshot.Phase == MatchPhase.Running ? 1f : 0f;
            _globalFeaturesBuffer[GF_IS_TERMINAL] = snapshot.Phase == MatchPhase.Ended ? 1f : 0f;

            bool isWin = snapshot.Phase == MatchPhase.Ended && snapshot.Winner == playerId;
            bool isLoss = snapshot.Phase == MatchPhase.Ended && snapshot.Winner != Owner.Neutral && snapshot.Winner != playerId;
            _globalFeaturesBuffer[GF_IS_WIN] = isWin ? 1f : 0f;
            _globalFeaturesBuffer[GF_IS_LOSS] = isLoss ? 1f : 0f;

            int selfRes = _matchManager.GetResources(playerId);
            Owner enemyOwner = GetEnemyOwner(playerId);
            int enemyRes = enemyOwner == Owner.Neutral ? 0 : _matchManager.GetResources(enemyOwner);
            _globalFeaturesBuffer[GF_SELF_RESOURCES] = NormalizeResources(selfRes);
            _globalFeaturesBuffer[GF_ENEMY_RESOURCES] = NormalizeResources(enemyRes);

            int maxSteps = snapshot.MaxSteps > 0 ? snapshot.MaxSteps : GameConstants.MaxEpisodeSteps;
            _globalFeaturesBuffer[GF_STEP_NORMALIZED] = maxSteps > 0
                ? Mathf.Clamp01(snapshot.Step / (float)maxSteps)
                : 0f;

            return _globalFeaturesBuffer;
        }

        /// <summary>
        /// Builds the full observation payload for a future policy consumer.
        ///
        /// Spatial observation is always populated. Global features remain meaningful only for
        /// UnityMvpTransfer and are intentionally zero-filled for LegacyGymCompatible.
        /// </summary>
        public ObservationPackage BuildObservationPackage(Owner playerId, ObservationMode mode = ObservationMode.UnityMvpTransfer)
        {
            float[] spatial = BuildObservation(playerId, mode);
            float[] global = BuildGlobalFeatures(playerId, mode);

            return new ObservationPackage(
                playerId,
                mode,
                (float[])spatial.Clone(),
                (float[])global.Clone());
        }

        /// <summary>
        /// Builds the spatial observation tensor for the requested semantic layer.
        ///
        /// This method does not perform runtime action validation. It only serializes current
        /// state into the agreed observation contract.
        /// </summary>
        public float[] BuildObservation(Owner playerId, ObservationMode mode = ObservationMode.LegacyGymCompatible)
        {
            if (playerId == Owner.Neutral)
            {
                Debug.LogWarning("[ObservationBuilder] BuildObservation called with Owner.Neutral. Caching empty observation.");
                Array.Clear(_observationBuffer, 0, _observationBuffer.Length);
                return _observationBuffer;
            }

            // Очистить буфер
            Array.Clear(_observationBuffer, 0, _observationBuffer.Length);

            // MatchManager может появиться позже (инициализация сцены), поэтому периодически резолвим ссылку.
            _matchManager ??= MatchManager.Instance;

            // Собрать снимок состояния
            _unitsByPosition.Clear();
            _resourcesByPosition.Clear();
            _allUnits.Clear();

            CacheSceneState(_allUnits, _unitsByPosition, _resourcesByPosition);

            // Заполнить буфер на основе режима
            switch (mode)
            {
                case ObservationMode.LegacyGymCompatible:
                    FillObservationCompat(playerId, _observationBuffer, _unitsByPosition, _resourcesByPosition);
                    break;

                case ObservationMode.UnityMvpTransfer:
                    FillObservationMvpTransfer(playerId, _observationBuffer, _unitsByPosition, _resourcesByPosition);
                    break;

                default:
                    Debug.LogError($"[ObservationBuilder] Unknown mode {mode}");
                    break;
            }

            return _observationBuffer;
        }

        /// <summary>
        /// Заполнить буфер наблюдений в режиме UnityMvpTransfer.
        /// Отличия от compat-режима:
        /// - owner кодируется как [neutral, friendly, enemy] относительно playerPerspective;
        /// - ресурсный канал дополнительно отражает переносимый ресурс friendly-worker;
        /// - current_action для производящих зданий отражает Produce;
        /// - attack_target используется как tactical enemy-presence сигнал (0/1).
        /// </summary>
        private void FillObservationMvpTransfer(
            Owner playerPerspective,
            float[] obs,
            Dictionary<GridPosition, UnitRuntime> unitsByPos,
            Dictionary<GridPosition, ResourceNode> resourcesByPos)
        {
            for (int row = 0; row < ObservationContract.GridH; row++)
            {
                for (int col = 0; col < ObservationContract.GridW; col++)
                {
                    // Spatial tensor uses row=Y and col=X. Keep this aligned with
                    // GridPosition.ToFlatIndex() and ActionMaskBuilder actor indexing.
                    var pos = new GridPosition(col, row);
                    int baseIndex = ObservationContract.FlatIndex(row, col, 0);

                    unitsByPos.TryGetValue(pos, out var unit);
                    resourcesByPos.TryGetValue(pos, out var resource);

                    // [0] HP
                    if (unit != null && unit.MaxHP > 0)
                    {
                        obs[baseIndex + ObservationContract.CH_HIT_POINTS] = Mathf.Clamp01((float)unit.HP / unit.MaxHP);
                    }
                    else
                    {
                        obs[baseIndex + ObservationContract.CH_HIT_POINTS] = 0f;
                    }

                    // [1] Resources: patch + carried resources for friendly workers.
                    float resourceNormalized = 0f;
                    if (resource != null && resource.MaxResources > 0)
                    {
                        resourceNormalized = Mathf.Clamp01((float)resource.CurrentResources / resource.MaxResources);
                    }

                    if (unit != null
                        && unit.Owner == playerPerspective
                        && unit.Type == UnitType.Worker
                        && GameConstants.MaxCarryCapacity > 0)
                    {
                        float carriedNormalized = Mathf.Clamp01((float)unit.CarriedResources / GameConstants.MaxCarryCapacity);
                        resourceNormalized = Mathf.Max(resourceNormalized, carriedNormalized);
                    }

                    obs[baseIndex + ObservationContract.CH_RESOURCES] = resourceNormalized;

                    // [2-4] Owner as perspective-based one-hot [neutral, friendly, enemy].
                    Owner cellOwner = unit != null ? unit.Owner : Owner.Neutral;
                    int ownerHotIndex = OwnerToPerspectiveOneHotIndex(cellOwner, playerPerspective);
                    ObservationContract.SetOneHot(
                        obs,
                        baseIndex + ObservationContract.CH_OWNER_BASE,
                        ObservationContract.CH_OWNER_COUNT,
                        ownerHotIndex);

                    // [5-11] Unit type
                    int unitTypeHotIndex = unit != null ? ActionContractMappings.UnitTypeToObservationIndex(unit.Type) : -1;
                    ObservationContract.SetOneHot(
                        obs,
                        baseIndex + ObservationContract.CH_UNIT_TYPE_BASE,
                        ObservationContract.CH_UNIT_TYPE_COUNT,
                        unitTypeHotIndex);

                    // [12-17] Current action: берем из последней примененной команды текущего шага.
                    int actionHotIndex = -1;
                    MatchCommand trackedCommand = default;
                    bool hasTrackedCommand = TryGetTrackedCommand(unit, out trackedCommand);
                    if (unit != null)
                    {
                        actionHotIndex = hasTrackedCommand
                            ? ActionContractMappings.UnitActionTypeToObservationIndex(trackedCommand.ActionType)
                            : 0; // NoOp fallback
                    }
                    ObservationContract.SetOneHot(
                        obs,
                        baseIndex + ObservationContract.CH_ACTION_BASE,
                        ObservationContract.CH_ACTION_COUNT,
                        actionHotIndex);

                    // [18-21] Direction: приоритет у направления из примененной команды.
                    int directionHotIndex = -1;
                    if (unit != null)
                    {
                        directionHotIndex = hasTrackedCommand
                            ? ActionContractMappings.DirectionToObservationIndex(trackedCommand.Direction)
                            : ActionContractMappings.DirectionToObservationIndex(unit.Facing);
                    }
                    ObservationContract.SetOneHot(
                        obs,
                        baseIndex + ObservationContract.CH_DIR_BASE,
                        ObservationContract.CH_DIR_COUNT,
                        directionHotIndex);

                    // [22-25] Produce unit type from active queue.
                    int produceHotIndex = -1;
                    if (unit != null && unit.IsBuilding)
                    {
                        if (hasTrackedCommand && trackedCommand.ActionType == UnitActionType.Produce)
                        {
                            produceHotIndex = ActionContractMappings.ProducibleUnitToObservationIndex(trackedCommand.ProduceUnitType);
                        }
                        else if (unit.gameObject != null)
                        {
                            var buildingRuntime = unit.gameObject.GetComponent<BuildingRuntime>();
                            var queue = buildingRuntime != null ? buildingRuntime.GetProductionQueue() : null;
                            if (queue != null && queue.IsProducing && queue.CurrentProducingType.HasValue)
                            {
                                produceHotIndex = ActionContractMappings.UnitTypeToProducibleUnitObservationIndex(queue.CurrentProducingType.Value);
                            }
                        }
                    }
                    ObservationContract.SetOneHot(
                        obs,
                        baseIndex + ObservationContract.CH_PRODUCE_BASE,
                        ObservationContract.CH_PRODUCE_COUNT,
                        produceHotIndex);

                    // [26] Tactical signal: presence of enemy unit in cell (relative to perspective).
                    bool isEnemyCell = unit != null && IsEnemyOwner(unit.Owner, playerPerspective);
                    obs[baseIndex + ObservationContract.CH_ATTACK_TARGET] = isEnemyCell ? 1f : 0f;
                }
            }
        }

        /// <summary>
        /// Заполнить буфер наблюдений в режиме compat.
        /// Итерирует по сетке 24x24, для каждой клетки вычисляет 27 каналов.
        /// </summary>
        private void FillObservationCompat(
            Owner playerPerspective,
            float[] obs,
            Dictionary<GridPosition, UnitRuntime> unitsByPos,
            Dictionary<GridPosition, ResourceNode> resourcesByPos)
        {
            for (int row = 0; row < ObservationContract.GridH; row++)
            {
                for (int col = 0; col < ObservationContract.GridW; col++)
                {
                    // Spatial tensor uses row=Y and col=X. Keep this aligned with
                    // GridPosition.ToFlatIndex() and ActionMaskBuilder actor indexing.
                    var pos = new GridPosition(col, row);
                    int baseIndex = ObservationContract.FlatIndex(row, col, 0);

                    // Прочитать сущности в этой клетке
                    UnitRuntime unit = null;
                    ResourceNode resource = null;

                    unitsByPos.TryGetValue(pos, out unit);
                    resourcesByPos.TryGetValue(pos, out resource);

                    // === Канал [0]: hit_points (нормализованное HP) ===
                    if (unit != null && unit.MaxHP > 0)
                    {
                        float normalized = (float)unit.HP / unit.MaxHP;
                        obs[baseIndex + ObservationContract.CH_HIT_POINTS] = Mathf.Clamp01(normalized);
                    }
                    else
                    {
                        obs[baseIndex + ObservationContract.CH_HIT_POINTS] = 0f;
                    }

                    // === Канал [1]: resources (нормализованные ресурсы) ===
                    if (resource != null && resource.MaxResources > 0)
                    {
                        float normalized = (float)resource.CurrentResources / resource.MaxResources;
                        obs[baseIndex + ObservationContract.CH_RESOURCES] = Mathf.Clamp01(normalized);
                    }
                    else
                    {
                        obs[baseIndex + ObservationContract.CH_RESOURCES] = 0f;
                    }

                    // === Каналы [2–4]: owner (one-hot: neutral, player1, player2) ===
                    Owner cellOwner = Owner.Neutral;
                    if (unit != null) cellOwner = unit.Owner;
                    int ownerHotIndex = OwnerToOneHotIndex(cellOwner);
                    ObservationContract.SetOneHot(obs, baseIndex + ObservationContract.CH_OWNER_BASE,
                        ObservationContract.CH_OWNER_COUNT, ownerHotIndex);

                    // === Каналы [5–11]: unit_type (one-hot по 7 типам) ===
                    int unitTypeHotIndex = -1;
                    if (unit != null)
                    {
                        unitTypeHotIndex = ActionContractMappings.UnitTypeToObservationIndex(unit.Type);
                    }
                    ObservationContract.SetOneHot(obs, baseIndex + ObservationContract.CH_UNIT_TYPE_BASE,
                        ObservationContract.CH_UNIT_TYPE_COUNT, unitTypeHotIndex);

                    // === Каналы [12–17]: current_action (one-hot по 6 типам действий) ===
                    // Заполняется из последней принятой команды текущего шага (если есть), иначе NoOp.
                    int actionHotIndex = 0;
                    MatchCommand trackedCommand = default;
                    bool hasTrackedCommand = TryGetTrackedCommand(unit, out trackedCommand);
                    if (unit != null && unit.Model != null && hasTrackedCommand)
                    {
                        actionHotIndex = ActionContractMappings.UnitActionTypeToObservationIndex(trackedCommand.ActionType);
                    }
                    ObservationContract.SetOneHot(obs, baseIndex + ObservationContract.CH_ACTION_BASE,
                        ObservationContract.CH_ACTION_COUNT, actionHotIndex);

                    // === Каналы [18–21]: action_direction (one-hot по 4 направлениям) ===
                    // Относится к юниту, который выполняет действие.
                    int directionHotIndex = -1; // Нет направления по умолчанию
                    if (unit != null && unit.Model != null)
                    {
                        // Приоритет у направления из текущей команды.
                        directionHotIndex = hasTrackedCommand
                            ? ActionContractMappings.DirectionToObservationIndex(trackedCommand.Direction)
                            : ActionContractMappings.DirectionToObservationIndex(unit.Facing);
                    }
                    ObservationContract.SetOneHot(obs, baseIndex + ObservationContract.CH_DIR_BASE,
                        ObservationContract.CH_DIR_COUNT, directionHotIndex);

                    // === Каналы [22–25]: produce_unit_type (one-hot по 4 типам для производства) ===
                    // Относится к зданиям (Base, Barracks) и их очередям производства.
                    // TODO Week 3: День 2. Получить ProductionQueue из BuildingRuntime component.
                    int produceHotIndex = -1;
                    if (unit != null && unit.IsBuilding && unit.gameObject != null)
                    {
                        if (hasTrackedCommand && trackedCommand.ActionType == UnitActionType.Produce)
                        {
                            produceHotIndex = ActionContractMappings.ProducibleUnitToObservationIndex(trackedCommand.ProduceUnitType);
                        }
                        else
                        {
                            var buildingRuntime = unit.gameObject.GetComponent<BuildingRuntime>();
                            if (buildingRuntime != null)
                            {
                                var productionQueue = buildingRuntime.GetProductionQueue();
                                if (productionQueue != null && productionQueue.IsProducing && productionQueue.CurrentProducingType.HasValue)
                                {
                                    var currentProducing = productionQueue.CurrentProducingType.Value;
                                    produceHotIndex = ActionContractMappings.UnitTypeToProducibleUnitObservationIndex(currentProducing);
                                }
                            }
                        }
                    }
                    ObservationContract.SetOneHot(obs, baseIndex + ObservationContract.CH_PRODUCE_BASE,
                        ObservationContract.CH_PRODUCE_COUNT, produceHotIndex);

                    // === Канал [26]: attack_target (нормализованный индекс цели) ===
                    // Placeholder: 0 для текущей версии.
                    obs[baseIndex + ObservationContract.CH_ATTACK_TARGET] = 0f;
                }
            }
        }

        /// <summary>
        /// Заполнить локальное кэш-состояние из сцены:
        /// - все юниты по их позициям
        /// - все ресурсы по их позициям
        /// </summary>
        private void CacheSceneState(
            List<UnitRuntime> outAllUnits,
            Dictionary<GridPosition, UnitRuntime> outUnitsByPos,
            Dictionary<GridPosition, ResourceNode> outResourcesByPos)
        {
            // Загрузить все юниты
            outAllUnits.AddRange(_unitRegistry.GetAllUnits());

            // Заполнить словарь юнитов по позициям
            foreach (var unit in outAllUnits)
            {
                if (unit != null && unit.GridPos.IsInsideMap())
                {
                    outUnitsByPos[unit.GridPos] = unit;
                }
            }

            // Загрузить все ресурсы
            var allResources = _resourceManager.GetAllResourceNodes();
            foreach (var resource in allResources)
            {
                if (resource != null && resource.GridPosition.IsInsideMap())
                {
                    outResourcesByPos[resource.GridPosition] = resource;
                }
            }
        }

        // ── Вспомогательные методы преобразования ──────────────────────────────

        /// <summary>
        /// Вернуть one-hot индекс для Owner.
        /// neutral=0, player1=1, player2=2, остальное=-1.
        /// </summary>
        private static int OwnerToOneHotIndex(Owner owner)
        {
            switch (owner)
            {
                case Owner.Neutral: return 0;
                case Owner.Player1: return 1;
                case Owner.Player2: return 2;
                default: return -1;
            }
        }

        /// <summary>
        /// Вернуть one-hot индекс owner в MVP-перспективе: neutral/friendly/enemy.
        /// </summary>
        private static int OwnerToPerspectiveOneHotIndex(Owner owner, Owner perspective)
        {
            if (owner == Owner.Neutral) return 0;
            if (owner == perspective) return 1;
            return 2;
        }

        /// <summary>
        /// Проверка, что owner является врагом для выбранной перспективы.
        /// </summary>
        private static bool IsEnemyOwner(Owner owner, Owner perspective)
        {
            return owner != Owner.Neutral && owner != perspective;
        }

        private bool TryGetTrackedCommand(UnitRuntime unit, out MatchCommand command)
        {
            command = default;
            if (_matchManager == null || unit == null)
            {
                return false;
            }

            return _matchManager.TryGetLastAppliedCommand(unit, out command);
        }

        private static Owner GetEnemyOwner(Owner playerId)
        {
            return playerId switch
            {
                Owner.Player1 => Owner.Player2,
                Owner.Player2 => Owner.Player1,
                _ => Owner.Neutral
            };
        }

        private static float NormalizeResources(int resources)
        {
            int scale = Mathf.Max(1, GameConstants.InitialResources * 4);
            return Mathf.Clamp01(resources / (float)scale);
        }

        // ── Валидация и диагностика ───────────────────────────────────────────

        /// <summary>
        /// Валидировать наблюдение: размер, диапазон значений, one-hot корректность.
        /// </summary>
        public ObservationValidationResult ValidateObservation(float[] obs)
        {
            var result = ObservationValidationResult.CreateValid();

            // Проверка размера
            if (obs == null)
            {
                result = ObservationValidationResult.Invalid("Observation is null");
                return result;
            }

            if (obs.Length != ObservationContract.TotalFloats)
            {
                result = ObservationValidationResult.Invalid(
                    $"Observation length {obs.Length} != expected {ObservationContract.TotalFloats}");
                return result;
            }

            // Проверка диапазона значений и one-hot структур
            for (int row = 0; row < ObservationContract.GridH; row++)
            {
                for (int col = 0; col < ObservationContract.GridW; col++)
                {
                    int baseIndex = ObservationContract.FlatIndex(row, col, 0);

                    // Проверить, что скалярные каналы в [0, 1]
                    for (int ch = 0; ch <= 1; ch++)
                    {
                        float val = obs[baseIndex + ch];
                        if (val < 0f || val > 1f)
                        {
                            result.Issues.Add(
                                $"Cell ({row},{col}) channel {ch}: value {val} out of [0,1] range");
                        }
                    }

                    // Проверить one-hot структуры
                    CheckOneHotStructure(obs, baseIndex, ObservationContract.CH_OWNER_BASE,
                        ObservationContract.CH_OWNER_COUNT, "owner", result);
                    CheckOneHotStructure(obs, baseIndex, ObservationContract.CH_UNIT_TYPE_BASE,
                        ObservationContract.CH_UNIT_TYPE_COUNT, "unit_type", result);
                    CheckOneHotStructure(obs, baseIndex, ObservationContract.CH_ACTION_BASE,
                        ObservationContract.CH_ACTION_COUNT, "current_action", result);
                    CheckOneHotStructure(obs, baseIndex, ObservationContract.CH_DIR_BASE,
                        ObservationContract.CH_DIR_COUNT, "action_direction", result);
                    CheckOneHotStructure(obs, baseIndex, ObservationContract.CH_PRODUCE_BASE,
                        ObservationContract.CH_PRODUCE_COUNT, "produce_unit_type", result);

                    // Проверить attack_target в [0, 1]
                    float attackTarget = obs[baseIndex + ObservationContract.CH_ATTACK_TARGET];
                    if (attackTarget < 0f || attackTarget > 1f)
                    {
                        result.Issues.Add(
                            $"Cell ({row},{col}) attack_target: value {attackTarget} out of [0,1] range");
                    }
                }
            }

            result.IsValid = result.Issues.Count == 0;
            return result;
        }

        /// <summary>
        /// Проверить, что one-hot структура корректна: ровно один 1.0 или все 0.0.
        /// </summary>
        private static void CheckOneHotStructure(
            float[] obs,
            int baseIndex,
            int oneHotBase,
            int oneHotCount,
            string fieldName,
            ObservationValidationResult result)
        {
            int oneCount = 0;
            int badCount = 0;

            for (int i = 0; i < oneHotCount; i++)
            {
                float val = obs[baseIndex + oneHotBase + i];
                if (Math.Abs(val - 1.0f) < 0.001f) oneCount++;
                else if (Math.Abs(val - 0.0f) >= 0.001f) badCount++;
            }

            if (badCount > 0)
            {
                int row = (baseIndex / ObservationContract.ChannelsPerCell) / ObservationContract.GridW;
                int col = (baseIndex / ObservationContract.ChannelsPerCell) % ObservationContract.GridW;
                result.Issues.Add(
                    $"Cell ({row},{col}) {fieldName}: contains non-0/1 values (count={badCount})");
            }

            if (!(oneCount == 1 || oneCount == 0))
            {
                int row = (baseIndex / ObservationContract.ChannelsPerCell) / ObservationContract.GridW;
                int col = (baseIndex / ObservationContract.ChannelsPerCell) % ObservationContract.GridW;
                result.Issues.Add(
                    $"Cell ({row},{col}) {fieldName}: not a valid one-hot (ones={oneCount})");
            }
        }

        /// <summary>
        /// Returns a human-readable observation dump for debugging and smoke tests.
        ///
        /// This is intentionally not part of the production policy contract surface.
        /// </summary>
        internal string DumpObservation(float[] obs, bool verbose = false)
        {
            if (obs == null) return "<null observation>";

            var sb = new System.Text.StringBuilder();
            sb.AppendLine($"=== Observation Dump ===");
            sb.AppendLine($"Size: {obs.Length} / {ObservationContract.TotalFloats}");

            if (!verbose)
            {
                // Краткий режим: показать несколько примеров ячеек
                sb.AppendLine("\n--- Sample Cells (first 3x3) ---");
                for (int row = 0; row < Mathf.Min(3, ObservationContract.GridH); row++)
                {
                    for (int col = 0; col < Mathf.Min(3, ObservationContract.GridW); col++)
                    {
                        DumpCell(obs, row, col, sb);
                    }
                }
            }
            else
            {
                // Полный режим: все ячейки
                sb.AppendLine("\n--- Full Grid ---");
                for (int row = 0; row < ObservationContract.GridH; row++)
                {
                    for (int col = 0; col < ObservationContract.GridW; col++)
                    {
                        DumpCell(obs, row, col, sb);
                    }
                }
            }

            return sb.ToString();
        }

        /// <summary>
        /// Вспомогательный метод для вывода одной ячейки.
        /// </summary>
        private static void DumpCell(float[] obs, int row, int col, System.Text.StringBuilder sb)
        {
            int baseIndex = ObservationContract.FlatIndex(row, col, 0);
            sb.Append($"  [{row:D2},{col:D2}] ");

            // HP
            float hp = obs[baseIndex + ObservationContract.CH_HIT_POINTS];
            sb.Append($"HP:{hp:F2} ");

            // Resources
            float res = obs[baseIndex + ObservationContract.CH_RESOURCES];
            sb.Append($"Res:{res:F2} ");

            // Owner one-hot
            string owner = OneHotToString(obs, baseIndex + ObservationContract.CH_OWNER_BASE,
                ObservationContract.CH_OWNER_COUNT, new[] { "Neutral", "P1", "P2" });
            sb.Append($"Own:{owner} ");

            // UnitType one-hot
            string unitType = OneHotToString(obs, baseIndex + ObservationContract.CH_UNIT_TYPE_BASE,
                ObservationContract.CH_UNIT_TYPE_COUNT, 
                new[] { "Res", "Base", "Barracks", "Worker", "Light", "Heavy", "Ranged" });
            sb.Append($"Type:{unitType}");

            sb.AppendLine();
        }

        /// <summary>
        /// Вспомогательный метод для преобразования one-hot в строку.
        /// </summary>
        private static string OneHotToString(float[] obs, int base_, int count, string[] labels)
        {
            for (int i = 0; i < count; i++)
            {
                if (Math.Abs(obs[base_ + i] - 1.0f) < 0.001f)
                {
                    return labels[i];
                }
            }
            return "None";
        }
    }
}
