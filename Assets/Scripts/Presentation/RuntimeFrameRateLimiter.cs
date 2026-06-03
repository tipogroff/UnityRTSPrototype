using UnityEngine;

namespace RTS.Presentation
{
    public static class RuntimeFrameRateLimiter
    {
        public const int DefaultTargetFrameRate = 60;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        private static void ApplyOnStartup()
        {
            ApplyDefault();
        }

        public static void ApplyDefault()
        {
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = DefaultTargetFrameRate;
        }
    }
}
