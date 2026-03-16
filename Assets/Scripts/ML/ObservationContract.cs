// ObservationContract.cs — точная спецификация пространства наблюдений
// Технический контракт MVP. Неделя 1.
//
// ФОРМАТ: Тензор [MapHeight, MapWidth, ChannelsPerCell]
//         При передаче в ML-Agents — ПЛОСКИЙ вектор длиной
//         MapHeight * MapWidth * ChannelsPerCell = 24 * 24 * 27 = 15552 float32.
//
// СОВМЕСТИМОСТЬ: структура каналов выровнена с Gym-µRTS v0.6.1
// (до добавления terrain/walls-каналов в более версиях репозитория).
// При интеграции BC-политики из Gym-µRTS необходимо сверять
// (a) порядок каналов, (b) нормализацию, (c) форму тензора.

namespace RTS.ML
{
    /// <summary>
    /// Единственный источник истины для раскладки каналов наблюдения.
    /// Используется как в Unity-коде (сбор наблюдений), так и
    /// является зеркалом Python-константы OBS_CHANNELS в teacher pipeline.
    ///
    /// Каждая ячейка сетки 24×24 описывается вектором из 27 float32 в диапазоне [0, 1].
    ///
    /// Индексный диапазон     Название              Описание
    /// ─────────────────────────────────────────────────────────────────────────
    /// [0]                    hit_points            Нормализованное HP: hp / MaxHitPoints
    /// [1]                    resources             Нормализованные ресурсы: r / MaxResourcesPerPatch
    /// [2–4]                  owner                 One-hot: [neutral, player1, player2]
    /// [5–11]                 unit_type             One-hot по UnitType enum (Resource=5..Ranged=11)
    /// [12–17]                current_action        One-hot по UnitActionType (NoOp=12..Attack=17)
    /// [18–21]                action_direction      One-hot по Direction (North=18..West=21)
    /// [22–25]                produce_unit_type     One-hot по ProducibleUnit (Worker=22..Ranged=25)
    /// [26]                   attack_target         Нормализованный индекс цели в зоне атаки [0..1]
    /// ─────────────────────────────────────────────────────────────────────────
    /// ИТОГО: 2 + 3 + 7 + 6 + 4 + 4 + 1 = 27 каналов на клетку.
    /// </summary>
    public static class ObservationContract
    {
        // ── Размеры тензора ───────────────────────────────────────────────────
        public const int GridH           = RTS.Core.GameConstants.MapHeight;    // 24
        public const int GridW           = RTS.Core.GameConstants.MapWidth;     // 24
        public const int ChannelsPerCell = 27;
        public const int TotalFloats     = GridH * GridW * ChannelsPerCell;     // 15552

        // ── Скалярные каналы ──────────────────────────────────────────────────
        public const int CH_HIT_POINTS = 0;   // float [0..1]
        public const int CH_RESOURCES  = 1;   // float [0..1]

        // ── Owner one-hot (3 канала: 2..4) ────────────────────────────────────
        public const int CH_OWNER_BASE    = 2;   // neutral = CH_OWNER_BASE + 0
        // player1  = CH_OWNER_BASE + 1
        // player2  = CH_OWNER_BASE + 2
        public const int CH_OWNER_COUNT   = 3;

        // ── UnitType one-hot (7 каналов: 5..11) ──────────────────────────────
        public const int CH_UNIT_TYPE_BASE  = 5;   // Resource = CH_UNIT_TYPE_BASE + 0
        // Base     = CH_UNIT_TYPE_BASE + 1
        // Barracks = CH_UNIT_TYPE_BASE + 2
        // Worker   = CH_UNIT_TYPE_BASE + 3
        // Light    = CH_UNIT_TYPE_BASE + 4
        // Heavy    = CH_UNIT_TYPE_BASE + 5
        // Ranged   = CH_UNIT_TYPE_BASE + 6
        public const int CH_UNIT_TYPE_COUNT = 7;

        // ── CurrentAction one-hot (6 каналов: 12..17) ────────────────────────
        public const int CH_ACTION_BASE  = 12;  // NoOp    = CH_ACTION_BASE + 0
        // Move    = CH_ACTION_BASE + 1
        // Harvest = CH_ACTION_BASE + 2
        // Return  = CH_ACTION_BASE + 3
        // Produce = CH_ACTION_BASE + 4
        // Attack  = CH_ACTION_BASE + 5
        public const int CH_ACTION_COUNT = 6;

        // ── ActionDirection one-hot (4 канала: 18..21) ───────────────────────
        public const int CH_DIR_BASE  = 18;   // North = CH_DIR_BASE + 0
        // East  = CH_DIR_BASE + 1
        // South = CH_DIR_BASE + 2
        // West  = CH_DIR_BASE + 3
        public const int CH_DIR_COUNT = 4;

        // ── ProduceUnitType one-hot (4 канала: 22..25) ───────────────────────
        public const int CH_PRODUCE_BASE  = 22;  // Worker = CH_PRODUCE_BASE + 0
        // Light  = CH_PRODUCE_BASE + 1
        // Heavy  = CH_PRODUCE_BASE + 2
        // Ranged = CH_PRODUCE_BASE + 3
        public const int CH_PRODUCE_COUNT = 4;

        // ── AttackTarget scalar (1 канал: 26) ────────────────────────────────
        public const int CH_ATTACK_TARGET = 26;  // нормализованный индекс цели [0..1]

        // ── Вспомогательные методы ────────────────────────────────────────────

        /// <summary>
        /// Вернуть плоский индекс в буфере длиной TotalFloats
        /// для ячейки (row, col) и канала ch.
        /// </summary>
        public static int FlatIndex(int row, int col, int ch)
            => (row * GridW + col) * ChannelsPerCell + ch;

        /// <summary>
        /// Заполнить срез obs[base..base+count] нулём, затем
        /// установить obs[base + hotIndex] = 1f (one-hot).
        /// </summary>
        public static void SetOneHot(float[] obs, int baseIndex, int count, int hotIndex)
        {
            for (int i = 0; i < count; i++) obs[baseIndex + i] = 0f;
            if (hotIndex >= 0 && hotIndex < count)
                obs[baseIndex + hotIndex] = 1f;
        }
    }
}
