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
        private int   _resourcesAtRef;
        private int   _buildCountAtRef;

        // ── Жизненный цикл MonoBehaviour ─────────────────────────────────────

        void Awake()
        {
            string dir = Path.Combine(Application.persistentDataPath, "Logs");
            Directory.CreateDirectory(dir);

            string timestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
            _filePath = Path.Combine(dir,
                $"{scenarioName}_{runName}_{timestamp}.csv");

            _writer = new StreamWriter(_filePath, append: false);
            _writer.WriteLine(
                "episode,steps,reward,win,invalid_rate," +
                "resources_at_ref,builds_at_ref,timestamp_utc");
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
            _resourcesAtRef  = 0;
            _buildCountAtRef = 0;
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
        public void OnStep(float rewardDelta, bool wasActionInvalid,
                           int currentResources, int currentBuilds)
        {
            _stepCount++;
            _episodeReward += rewardDelta;
            _totalActions++;
            if (wasActionInvalid) _invalidActions++;

            if (_stepCount == referenceStep)
            {
                _resourcesAtRef  = currentResources;
                _buildCountAtRef = currentBuilds;
            }
        }

        /// <summary>
        /// Зафиксировать итог эпизода: win=true если агент победил.
        /// </summary>
        public void OnEpisodeEnd(bool win)
        {
            float invalidRate = _totalActions > 0
                ? (float)_invalidActions / _totalActions
                : 0f;

            string line = string.Join(",",
                _episodeIndex,
                _stepCount,
                _episodeReward.ToString("F4"),
                win ? 1 : 0,
                invalidRate.ToString("F4"),
                _resourcesAtRef,
                _buildCountAtRef,
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
