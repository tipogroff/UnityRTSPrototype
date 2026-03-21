// ExperimentLogger.cs — логирование метрик эксперимента в CSV
// Технический контракт MVP. Неделя 1.
//
// Метрики (из раздела 4 IMPLEMENTATION_PLAN.md):
//   - Win rate
//   - Time-to-win (steps)
//   - Episode reward (mean/std — считать внешним скриптом по CSV)
//   - Invalid action rate
//   - Harvest speed proxy (ресурсы, добытые к шагу T_ref)
//   - Build count (постройки к шагу T_ref)

using System;
using System.Globalization;
using System.IO;
using UnityEngine;

namespace RTS.Logging
{
    /// <summary>
    /// Компонент-синглтон. Добавить на один GameObject на сцену.
    /// Ведёт CSV-файл в Application.persistentDataPath/Logs/.
    /// </summary>
    public class ExperimentLogger : MonoBehaviour
    {
        // ── Публичные поля ────────────────────────────────────────────────────
        [Header("Настройки")]
        [Tooltip("Имя сценария — записывается в каждую строку CSV")]
        public string scenarioName = "MVP_24x24_Symmetric";

        [Tooltip("Название эксперимента (e.g. 'transfer' или 'from_scratch')")]
        public string runName = "baseline";

        [Tooltip("Шаг, на котором фиксируются ресурсы и постройки (proxy-метрика)")]
        public int referenceStep = 500;

        // ── Внутреннее состояние ──────────────────────────────────────────────
        private StreamWriter _writer;
        private string       _filePath;

        // Счётчики на текущий эпизод
        private int   _episodeIndex;
        private int   _stepCount;
        private float _episodeReward;
        private int   _invalidActions;
        private int   _totalActions;
        private int   _resourcesP1AtRef;
        private int   _resourcesP2AtRef;
        private int   _buildsP1AtRef;
        private int   _buildsP2AtRef;

        // ── Жизненный цикл MonoBehaviour ─────────────────────────────────────

        void Awake()
        {
            EnsureWriterInitialized();
        }

        private void EnsureWriterInitialized()
        {
            if (_writer != null)
            {
                return;
            }

            string dir = Path.Combine(Application.persistentDataPath, "Logs");
            Directory.CreateDirectory(dir);

            string timestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
            _filePath = Path.Combine(dir,
                $"{scenarioName}_{runName}_{timestamp}.csv");

            _writer = new StreamWriter(_filePath, append: false);
            _writer.WriteLine(
                "episode,steps,reward,win,invalid_rate," +
                "resources_p1_at_ref,resources_p2_at_ref," +
                "builds_p1_at_ref,builds_p2_at_ref,timestamp_utc");
            _writer.Flush();

            Debug.Log($"[ExperimentLogger] Лог открыт: {_filePath}");
        }

        void OnDestroy()
        {
            _writer?.Flush();
            _writer?.Close();
        }

        // ── Public API (вызывается из игровой логики) ─────────────────────────

        /// <summary>
        /// Сбросить счётчики в начале нового эпизода.
        /// </summary>
        public void OnEpisodeBegin()
        {
            _stepCount       = 0;
            _episodeReward   = 0f;
            _invalidActions  = 0;
            _totalActions    = 0;
            _resourcesP1AtRef = 0;
            _resourcesP2AtRef = 0;
            _buildsP1AtRef    = 0;
            _buildsP2AtRef    = 0;
        }

        /// <summary>
        /// New API alias used by EpisodeController.
        /// </summary>
        public void BeginEpisode()
        {
            OnEpisodeBegin();
        }

        /// <summary>
        /// Вызывать каждый шаг агента, передавая инкрементальную награду.
        /// </summary>
        public void OnStep(
            float rewardDelta,
            bool wasActionInvalid,
            int currentResourcesP1,
            int currentResourcesP2,
            int currentBuildsP1,
            int currentBuildsP2)
        {
            _stepCount++;
            _episodeReward += rewardDelta;
            _totalActions++;
            if (wasActionInvalid) _invalidActions++;

            if (_stepCount == referenceStep)
            {
                _resourcesP1AtRef = currentResourcesP1;
                _resourcesP2AtRef = currentResourcesP2;
                _buildsP1AtRef    = currentBuildsP1;
                _buildsP2AtRef    = currentBuildsP2;
            }
        }

        /// <summary>
        /// Зафиксировать итог эпизода: win=true если агент победил.
        /// </summary>
        public void OnEpisodeEnd(bool win)
        {
            EnsureWriterInitialized();

            float invalidRate = _totalActions > 0
                ? (float)_invalidActions / _totalActions
                : 0f;

            string line = string.Join(",",
                _episodeIndex,
                _stepCount,
                _episodeReward.ToString("F4", CultureInfo.InvariantCulture),
                win ? 1 : 0,
                invalidRate.ToString("F4", CultureInfo.InvariantCulture),
                _resourcesP1AtRef,
                _resourcesP2AtRef,
                _buildsP1AtRef,
                _buildsP2AtRef,
                DateTime.UtcNow.ToString("o"));

            _writer.WriteLine(line);
            _writer.Flush();

            _episodeIndex++;
        }

        /// <summary>
        /// New API alias used by EpisodeController.
        /// </summary>
        public void EndEpisode(bool win)
        {
            OnEpisodeEnd(win);
        }

        // ── Дополнительные утилиты ────────────────────────────────────────────

        /// <summary>
        /// Путь до CSV-файла (для отображения в UI или редакторе).
        /// </summary>
        public string FilePath => _filePath;
    }
}
