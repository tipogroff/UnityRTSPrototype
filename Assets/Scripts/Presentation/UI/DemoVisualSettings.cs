namespace RTS.Presentation.UI
{
    public enum DemoGraphicsQuality
    {
        Low = 0,
        Medium = 1,
        High = 2,
    }

    public enum DemoCameraHeight
    {
        Low = 0,
        Medium = 1,
        High = 2,
    }

    public enum DemoInterfaceScale
    {
        Small = 0,
        Normal = 1,
        Large = 2,
    }

    public static class DemoVisualSettings
    {
        public static bool ShowGrid { get; private set; } = true;
        public static bool ShowUnitMarkers { get; private set; } = true;
        public static bool ShowControlHints { get; private set; } = true;
        public static DemoGraphicsQuality GraphicsQuality { get; private set; } = DemoGraphicsQuality.High;
        public static DemoCameraHeight CameraHeight { get; private set; } = DemoCameraHeight.Medium;
        public static DemoInterfaceScale InterfaceScale { get; private set; } = DemoInterfaceScale.Normal;

        public static void ToggleGrid()
        {
            ShowGrid = !ShowGrid;
        }

        public static void ToggleUnitMarkers()
        {
            ShowUnitMarkers = !ShowUnitMarkers;
        }

        public static void ToggleControlHints()
        {
            ShowControlHints = !ShowControlHints;
        }

        public static void CycleGraphicsQuality()
        {
            GraphicsQuality = (DemoGraphicsQuality)(((int)GraphicsQuality + 1) % 3);
        }

        public static void CycleCameraHeight()
        {
            CameraHeight = (DemoCameraHeight)(((int)CameraHeight + 1) % 3);
        }

        public static void CycleInterfaceScale()
        {
            InterfaceScale = (DemoInterfaceScale)(((int)InterfaceScale + 1) % 3);
        }

        public static string FormatToggle(bool value)
        {
            return value ? "\u0412\u043a\u043b" : "\u0412\u044b\u043a\u043b";
        }
    }
}
