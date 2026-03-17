// ResourceManager.cs — управление ресурсными узлами на карте.
// Этап 3: Экономика. Неделя 2.

using System.Collections.Generic;
using UnityEngine;
using RTS.Core;

namespace RTS.Gameplay
{
    /// <summary>
    /// Центральный реестр всех ресурсных узлов (ResourceNode) на карте.
    /// Позволяет быстро найти ресурс по позиции и отслеживать исчерпанные патчи.
    /// </summary>
    public class ResourceManager : MonoBehaviour
    {
        // ── Singleton ─────────────────────────────────────────────────────────

        public static ResourceManager Instance { get; private set; }

        // ── Состояние ─────────────────────────────────────────────────────────

        /// <summary>Словарь: позиция → ResourceNode.</summary>
        private Dictionary<GridPosition, ResourceNode> _resourceNodes = new();

        // ── Events ────────────────────────────────────────────────────────────

        /// <summary>Вызывается, когда ресурсный патч полностью исчерпан.</summary>
        public System.Action<GridPosition> OnResourceExhausted;

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

        // ── Управление ────────────────────────────────────────────────────────

        /// <summary>
        /// Регистрирует новый ресурсный узел на карте.
        /// </summary>
        public void RegisterResourceNode(ResourceNode node)
        {
            if (node == null) return;

            GridPosition pos = node.GridPosition;

            if (_resourceNodes.ContainsKey(pos))
            {
                Debug.LogWarning($"[ResourceManager] Ресурсный узел уже существует at {pos}. Перезаписываем.");
            }

            _resourceNodes[pos] = node;

            // Подписываемся на событие исчерпания
            node.OnResourceExhausted += HandleResourceExhausted;
        }

        /// <summary>
        /// Удаляет ресурсный узел из реестра.
        /// </summary>
        public void UnregisterResourceNode(GridPosition pos)
        {
            if (_resourceNodes.TryGetValue(pos, out var node))
            {
                node.OnResourceExhausted -= HandleResourceExhausted;
                _resourceNodes.Remove(pos);
            }
        }

        // ── Запросы ───────────────────────────────────────────────────────────

        /// <summary>
        /// Получить ресурсный узел по позиции (или null если нет).
        /// </summary>
        public ResourceNode GetResourceNode(GridPosition pos)
        {
            _resourceNodes.TryGetValue(pos, out var node);
            return node;
        }

        /// <summary>
        /// Получить все ресурсные узлы.
        /// </summary>
        public IEnumerable<ResourceNode> GetAllResourceNodes()
        {
            return _resourceNodes.Values;
        }

        /// <summary>
        /// Получить количество активных (не исчерпанных) ресурсных узлов.
        /// </summary>
        public int GetActiveResourceCount()
        {
            int count = 0;
            foreach (var node in _resourceNodes.Values)
            {
                if (!node.IsExhausted) count++;
            }
            return count;
        }

        /// <summary>
        /// Получить объединённое количество ресурсов во всех узлах.
        /// </summary>
        public int GetTotalAvailableResources()
        {
            int total = 0;
            foreach (var node in _resourceNodes.Values)
            {
                total += node.CurrentResources;
            }
            return total;
        }

        // ── Обработчики событий ──────────────────────────────────────────────

        private void HandleResourceExhausted(GridPosition pos)
        {
            OnResourceExhausted?.Invoke(pos);
        }

        // ── Reset ──────────────────────────────────────────────────────────────

        /// <summary>
        /// Сбрасывает все ресурсные узлы к исходному состоянию (для reset эпизода).
        /// </summary>
        public void ResetForEpisode()
        {
            foreach (var node in _resourceNodes.Values)
            {
                node.ResetForEpisode();
            }
        }

        /// <summary>
        /// Очищает все ресурсные узлы из реестра (вызывается перед полной перезагрузкой сцены).
        /// </summary>
        public void Clear()
        {
            foreach (var node in _resourceNodes.Values)
            {
                node.OnResourceExhausted -= HandleResourceExhausted;
            }
            _resourceNodes.Clear();
        }
    }
}
