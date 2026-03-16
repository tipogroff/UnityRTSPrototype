// GameConfigCreator.cs — Editor-утилита: создаёт эталонный GameConfig-ассет
// Неделя 1. Запустить один раз через меню: RTS > Create MVP GameConfig
// После выполнения файл появится в Assets/ML/GameConfig_MVP.asset

#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;
using RTS.Core;

namespace RTS.Editor
{
    public static class GameConfigCreator
    {
        [MenuItem("RTS/Create MVP GameConfig")]
        public static void CreateMVPConfig()
        {
            GameConfig config = ScriptableObject.CreateInstance<GameConfig>();
            config.scenarioName    = "MVP_24x24_Symmetric";
            config.scenarioNotes   =
                "Эталонный сценарий недели 1.\n" +
                "24×24 карта, симметричный старт: 1 база + 2 рабочих на каждую сторону.\n" +
                "5 стартовых ресурсов. Лимит: 2000 шагов.";
            config.mapWidth        = 24;
            config.mapHeight       = 24;
            config.startResources  = 5;
            config.maxEpisodeSteps = 2000;

            // unitDefinitions оставляем пустыми на неделю 1 —
            // они будут заполнены при создании UnitDefinition-ассетов на неделю 2.
            config.unitDefinitions = new UnitDefinition[7];

            string path = "Assets/ML/GameConfig_MVP.asset";
            AssetDatabase.CreateAsset(config, path);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            EditorUtility.FocusProjectWindow();
            Selection.activeObject = config;

            Debug.Log($"[RTS] GameConfig создан: {path}");
        }
    }
}
#endif
