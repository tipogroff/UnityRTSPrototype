using RTS.ML;

namespace RTS.MLAgents.Stage7B.TeacherConversion
{
    public sealed class Stage7BObservationStateReconstructor
    {
        public bool TryReconstruct(Stage7BTeacherSample sample, out string diagnostics)
        {
            diagnostics =
                "Offline bc_ready observations/actions do not provide a reliable authoritative runtime reconstruction " +
                "for ActionMaskBuilder-equivalent legal candidate generation in this preflight stage.";
            return false;
        }
    }
}
