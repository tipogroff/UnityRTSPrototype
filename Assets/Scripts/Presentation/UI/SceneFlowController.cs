using UnityEngine;
using UnityEngine.SceneManagement;

namespace RTS.Presentation.UI
{
    [DisallowMultipleComponent]
    public sealed class SceneFlowController : MonoBehaviour
    {
        [SerializeField] private string _mainMenuSceneName = "MainMenu";
        [SerializeField] private string _demoSceneName = "HumanPlay_Demo_PlayerVsAI";

        public string MainMenuSceneName => _mainMenuSceneName;
        public string DemoSceneName => _demoSceneName;

        public void LoadDemo()
        {
            LoadScene(_demoSceneName);
        }

        public void LoadMainMenu()
        {
            LoadScene(_mainMenuSceneName);
        }

        public void RestartCurrentScene()
        {
            Time.timeScale = 1f;
            Scene active = SceneManager.GetActiveScene();
            SceneManager.LoadScene(active.name);
        }

        public void Quit()
        {
            Time.timeScale = 1f;
#if UNITY_EDITOR
            Debug.Log("[SceneFlowController] Quit requested in editor.");
            UnityEditor.EditorApplication.isPlaying = false;
#else
            Application.Quit();
#endif
        }

        private static void LoadScene(string sceneName)
        {
            if (string.IsNullOrWhiteSpace(sceneName))
            {
                Debug.LogWarning("[SceneFlowController] Scene name is empty.");
                return;
            }

            Time.timeScale = 1f;
            SceneManager.LoadScene(sceneName);
        }
    }
}
