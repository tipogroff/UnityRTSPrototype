// ObservationBuilderSmokeTest.cs — простой тест ObservationBuilder
// Неделя 3, День 2: Проверка базовой функциональности.

using UnityEngine;
using RTS.Core;
using RTS.Gameplay;

namespace RTS.ML
{
    /// <summary>
    /// Простой smoke-test для ObservationBuilder.
    /// Закрепляется в сцене для ручной проверки в Play Mode.
    /// </summary>
    public class ObservationBuilderSmokeTest : MonoBehaviour
    {
        [SerializeField] private bool runOnAwake = false;

        private ObservationBuilder _builder;

        private void Awake()
        {
            if (!runOnAwake) return;
            RunTest();
        }

        private void RunTest()
        {
            Debug.Log("[ObservationBuilderSmokeTest] === Starting Smoke Test ===");

            // Получить синглтоны
            var gridManager = GridManager.Instance;
            var unitRegistry = UnitRegistry.Instance;
            var resourceManager = ResourceManager.Instance;

            if (gridManager == null || unitRegistry == null || resourceManager == null)
            {
                Debug.LogError("[ObservationBuilderSmokeTest] Some managers not found!");
                return;
            }

            // Создать builder
            _builder = new ObservationBuilder(gridManager, unitRegistry, resourceManager);
            Debug.Log("[ObservationBuilderSmokeTest] ObservationBuilder created successfully");

            // Тест 1: Сборка наблюдения для Player1 (compat-режим)
            Debug.Log("[ObservationBuilderSmokeTest] Test 1: Building observation for Player1 (compat mode)...");
            var obsCompat = _builder.BuildObservation(Owner.Player1, ObservationMode.LegacyGymCompatible);
            Debug.Log($"[ObservationBuilderSmokeTest] ✓ Observation built: {obsCompat.Length} floats");

            // Тест 2: Валидация
            Debug.Log("[ObservationBuilderSmokeTest] Test 2: Validating observation...");
            var validationResult = _builder.ValidateObservation(obsCompat);
            Debug.Log($"[ObservationBuilderSmokeTest] {validationResult}");

            if (!validationResult.IsValid)
            {
                foreach (var issue in validationResult.Issues)
                {
                    Debug.LogWarning($"  - {issue}");
                }
            }

            // Тест 3: Дамп (краткий режим)
            Debug.Log("[ObservationBuilderSmokeTest] Test 3: Dumping observation (brief mode)...");
            string dump = _builder.DumpObservation(obsCompat, verbose: false);
            Debug.Log($"[ObservationBuilderSmokeTest] Dump:\n{dump}");

            // Тест 4: Сборка наблюдения для Player2 (MVP-режим)
            Debug.Log("[ObservationBuilderSmokeTest] Test 4: Building observation for Player2 (MVP mode)...");
            var obsMvp = _builder.BuildObservation(Owner.Player2, ObservationMode.UnityMvpTransfer);
            Debug.Log($"[ObservationBuilderSmokeTest] ✓ Observation built: {obsMvp.Length} floats");

            // Тест 5: Проверка размеров
            Debug.Log("[ObservationBuilderSmokeTest] Test 5: Size validation...");
            Debug.Log($"  Expected: {ObservationContract.TotalFloats}");
            Debug.Log($"  compat:   {obsCompat.Length} (✓)" + (obsCompat.Length == ObservationContract.TotalFloats ? "" : " (✗)"));
            Debug.Log($"  MVP:      {obsMvp.Length} (✓)" + (obsMvp.Length == ObservationContract.TotalFloats ? "" : " (✗)"));

            // Тест 6: Global features для Player1
            Debug.Log("[ObservationBuilderSmokeTest] Test 6: Building global features for Player1...");
            var gfP1 = _builder.BuildGlobalFeatures(Owner.Player1, ObservationMode.UnityMvpTransfer);
            Debug.Log($"[ObservationBuilderSmokeTest] ✓ Global features P1: {gfP1.Length} floats");

            // Тест 7: Global features для Player2
            Debug.Log("[ObservationBuilderSmokeTest] Test 7: Building global features for Player2...");
            var gfP2 = _builder.BuildGlobalFeatures(Owner.Player2, ObservationMode.UnityMvpTransfer);
            Debug.Log($"[ObservationBuilderSmokeTest] ✓ Global features P2: {gfP2.Length} floats");

            Debug.Log($"[ObservationBuilderSmokeTest]  GF expected: {ObservationBuilder.GlobalFeaturesCount}");
            Debug.Log($"[ObservationBuilderSmokeTest]  GF P1 size: {gfP1.Length}" + (gfP1.Length == ObservationBuilder.GlobalFeaturesCount ? " (✓)" : " (✗)"));
            Debug.Log($"[ObservationBuilderSmokeTest]  GF P2 size: {gfP2.Length}" + (gfP2.Length == ObservationBuilder.GlobalFeaturesCount ? " (✓)" : " (✗)"));

            // Тест 8: Observation package
            Debug.Log("[ObservationBuilderSmokeTest] Test 8: Building full observation package...");
            var package = _builder.BuildObservationPackage(Owner.Player1, ObservationMode.UnityMvpTransfer);
            Debug.Log($"[ObservationBuilderSmokeTest] ✓ Package built: mode={package.Mode}, player={package.PlayerId}");
            Debug.Log($"[ObservationBuilderSmokeTest]  Package spatial size: {package.SpatialObservation.Length}" + (package.SpatialObservation.Length == ObservationContract.TotalFloats ? " (✓)" : " (✗)"));
            Debug.Log($"[ObservationBuilderSmokeTest]  Package global size: {package.GlobalFeatures.Length}" + (package.GlobalFeatures.Length == ObservationBuilder.GlobalFeaturesCount ? " (✓)" : " (✗)"));

            Debug.Log("[ObservationBuilderSmokeTest] === Smoke Test Complete ===");
        }

        /// <summary>
        /// Вызваться из Editor меню для ручного теста.
        /// </summary>
        [ContextMenu("Run Smoke Test")]
        public void ManualTest()
        {
            RunTest();
        }
    }
}
