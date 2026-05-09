using UnityEngine;

namespace RTS.MLAgents.Stage7B.TeacherConversion
{
    [DisallowMultipleComponent]
    public sealed class Stage7BTeacherConversionPreflightRunner : MonoBehaviour
    {
        [SerializeField] private string _previewJsonlPath =
            "python/stage7b_teacher_conversion/stage7b_teacher_candidate_dataset_preview.jsonl";

        [SerializeField] private bool _runOnStart;

        private readonly Stage7BTeacherSampleLoader _loader = new Stage7BTeacherSampleLoader();
        private readonly Stage7BObservationStateReconstructor _reconstructor = new Stage7BObservationStateReconstructor();

        private void Start()
        {
            if (_runOnStart)
            {
                RunPreflight();
            }
        }

        [ContextMenu("Run Stage7B Teacher Conversion Preflight")]
        public void RunPreflight()
        {
            bool loaded = _loader.TryLoadPreviewJsonLines(_previewJsonlPath, out int sampleCount, out string diagnostics);
            if (!loaded)
            {
                Debug.LogWarning("[Stage7B][TeacherConversion] Unable to load preflight preview: " + diagnostics);
                return;
            }

            bool reconstructionReliable = _reconstructor.TryReconstruct(null, out string reconstructionDiagnostics);
            if (!reconstructionReliable)
            {
                Debug.LogWarning(
                    "[Stage7B][TeacherConversion] Partial preflight only. " +
                    "state_reconstruction_reliable=false; samples=" + sampleCount + "; reason=" + reconstructionDiagnostics);
                return;
            }

            Debug.Log("[Stage7B][TeacherConversion] Preflight completed in full mode. samples=" + sampleCount);
        }
    }
}
