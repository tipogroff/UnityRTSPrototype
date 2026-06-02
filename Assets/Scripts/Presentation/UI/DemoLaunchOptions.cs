namespace RTS.Presentation.UI
{
    public enum DemoLaunchMode
    {
        AIvsPlayer = 0,
        AIvsBot = 1,
        AIvsAI = 2,
    }

    public static class DemoLaunchOptions
    {
        public static DemoLaunchMode RequestedMode { get; private set; } = DemoLaunchMode.AIvsPlayer;
        public static bool HasExplicitMode { get; private set; }

        public static void SetMode(DemoLaunchMode mode)
        {
            RequestedMode = mode;
            HasExplicitMode = true;
        }

        public static void Clear()
        {
            RequestedMode = DemoLaunchMode.AIvsPlayer;
            HasExplicitMode = false;
        }
    }
}
