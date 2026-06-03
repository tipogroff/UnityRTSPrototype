#if UNITY_EDITOR
using RTS.Presentation.DebugTools;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace RTS.Editor.Presentation
{
    public static class DebugPauseValidationMenu
    {
        private const string ScenePath = "Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity";

        [MenuItem("RTS/Debug/Pause Validation/Run All Modes")]
        public static void RunAllModes()
        {
            EditorPrefs.SetBool(DebugPauseValidationRunner.EnabledKey, true);
            EditorPrefs.SetString(DebugPauseValidationRunner.SceneNameKey, "HumanPlay_Demo_PlayerVsAI");
            EditorPrefs.SetString(DebugPauseValidationRunner.ReportPathKey, "GAME_SPEED_PAUSE_VALIDATION_RUNTIME_REPORT.md");

            if (!EditorApplication.isPlaying)
            {
                if (EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo())
                {
                    EditorSceneManager.OpenScene(ScenePath);
                    EditorApplication.isPlaying = true;
                }
                else
                {
                    Debug.LogWarning("[PauseValidation] Run cancelled because modified scenes were not saved.");
                }
                return;
            }

            Debug.Log("[PauseValidation] Validation flag set. Reload Play Mode or current scene to start runner.");
        }

        [MenuItem("RTS/Debug/Pause Validation/Clear Pending Run")]
        public static void ClearPendingRun()
        {
            EditorPrefs.SetBool(DebugPauseValidationRunner.EnabledKey, false);
            Debug.Log("[PauseValidation] Pending run cleared.");
        }
    }
}
#endif
