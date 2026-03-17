// MatchManager.cs — хранит текущее состояние матча (ресурсы, шаги, фаза).
// Неделя 2, Этап Match.
// Получает управление от MatchBootstrap и передаёт сигналы EpisodeController.

using UnityEngine;
using RTS.Core;

namespace RTS.Gameplay
{
    /// <summary>
    /// Фаза матча (используется как state machine).
    /// </summary>
    public enum MatchPhase
    {
        Idle,       // до BeginMatch()
        Running,    // матч идёт
        Ended       // победитель определён
    }

    /// <summary>
    /// Singleton MonoBehaviour.
    /// Хранит мutable-состояние текущего матча:
    /// — ресурсы игроков;
    /// — текущий шаг эпизода;
    /// — фазу матча и победителя.
    ///
    /// Не содержит игровой логики — только данные и события.
    /// VictoryResolver и EpisodeController реагируют на эти данные.
    /// </summary>
    public class MatchManager : MonoBehaviour
    {
        // ── Singleton ─────────────────────────────────────────────────────────

        public static MatchManager Instance { get; private set; }

        // ── Состояние ─────────────────────────────────────────────────────────

        public MatchPhase Phase    { get; private set; } = MatchPhase.Idle;
        public int        Step     { get; private set; }
        public int        MaxSteps { get; private set; }
        public Owner      Winner   { get; private set; } = Owner.Neutral;

        // Ресурсы: индекс 0 → Player1, 1 → Player2
        private int[] _resources = new int[2];

        // ── Events ────────────────────────────────────────────────────────────

        /// <summary>Вызывается при завершении матча. Параметр — победитель.</summary>
        public System.Action<Owner> OnMatchEnded;

        /// <summary>Вызывается каждый шаг симуляции.</summary>
        public System.Action<int> OnStepAdvanced;

        // ── Unity lifecycle ───────────────────────────────────────────────────

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
        }

        private void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        // ── Жизненный цикл матча ──────────────────────────────────────────────

        /// <summary>
        /// Инициализирует состояние матча. Вызывается из MatchBootstrap.Setup().
        /// </summary>
        public void BeginMatch(int startResourcesPerPlayer, int maxSteps)
        {
            _resources[0] = startResourcesPerPlayer;
            _resources[1] = startResourcesPerPlayer;
            MaxSteps = maxSteps;
            Step     = 0;
            Winner   = Owner.Neutral;
            Phase    = MatchPhase.Running;
        }

        /// <summary>
        /// Сброс до состояния Idle (вызывается из EpisodeController.ResetEpisode).
        /// </summary>
        public void ResetMatch()
        {
            Phase    = MatchPhase.Idle;
            Step     = 0;
            Winner   = Owner.Neutral;
            _resources[0] = 0;
            _resources[1] = 0;
        }

        // ── Шаги ─────────────────────────────────────────────────────────────

        /// <summary>
        /// Продвигает счётчик шагов на +1.
        /// Вызывается из EpisodeController в конце каждого игрового тика.
        /// </summary>
        public void AdvanceStep()
        {
            if (Phase != MatchPhase.Running) return;
            Step++;
            OnStepAdvanced?.Invoke(Step);
        }

        // ── Ресурсы ───────────────────────────────────────────────────────────

        /// <summary>Возвращает запас ресурсов игрока.</summary>
        public int GetResources(Owner owner)
            => owner == Owner.Player1 ? _resources[0] :
               owner == Owner.Player2 ? _resources[1] : 0;

        /// <summary>Добавляет ресурсы игроку (amount может быть отрицательным).</summary>
        public void AddResources(Owner owner, int amount)
        {
            if (owner == Owner.Player1) _resources[0] = Mathf.Max(0, _resources[0] + amount);
            else if (owner == Owner.Player2) _resources[1] = Mathf.Max(0, _resources[1] + amount);
        }

        /// <summary>
        /// True если у игрока достаточно ресурсов для покупки.
        /// </summary>
        public bool CanAfford(Owner owner, int cost)
            => GetResources(owner) >= cost;

        // ── Победа/поражение ──────────────────────────────────────────────────

        /// <summary>
        /// Объявляет победителя и переводит матч в фазу Ended.
        /// Вызывается VictoryResolver.
        /// </summary>
        public void DeclareWinner(Owner winner)
        {
            if (Phase != MatchPhase.Running) return;
            Winner = winner;
            Phase  = MatchPhase.Ended;
            Debug.Log($"[MatchManager] Матч завершён. Победитель: {winner}. Шаги: {Step}");
            OnMatchEnded?.Invoke(winner);
        }
    }
}
