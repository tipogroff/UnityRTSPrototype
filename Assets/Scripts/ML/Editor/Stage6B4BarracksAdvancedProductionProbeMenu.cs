using RTS.ML;
using UnityEditor;
using UnityEngine;

namespace RTS.ML.Editor
{
    public static class Stage6B4BarracksAdvancedProductionProbeMenu
    {
        [MenuItem("RTS/Week6/Stage6B4/Run Barracks Advanced Production Probe")]
        public static void RunProbe()
        {
            if (!Application.isPlaying)
            {
                Debug.LogWarning("[Stage6B4] Enter Play Mode before running the Barracks advanced production probe.");
                return;
            }

            Stage6B4_BarracksAdvancedProductionProbe probe =
                Object.FindFirstObjectByType<Stage6B4_BarracksAdvancedProductionProbe>();

            if (probe == null)
            {
                var host = new GameObject("Stage6B4_BarracksAdvancedProductionProbe_Runtime");
                probe = host.AddComponent<Stage6B4_BarracksAdvancedProductionProbe>();
            }

            probe.RunForcedProbeFromContextMenu();
        }

        [MenuItem("RTS/Week6/Stage6B4/Write Barracks Advanced Production Report")]
        public static void WriteReport()
        {
            Stage6B4_BarracksAdvancedProductionProbe probe =
                Object.FindFirstObjectByType<Stage6B4_BarracksAdvancedProductionProbe>();

            if (probe == null)
            {
                Debug.LogWarning("[Stage6B4] Stage6B4_BarracksAdvancedProductionProbe not found.");
                return;
            }

            probe.WriteReportFromContextMenu();
        }
    }
}
