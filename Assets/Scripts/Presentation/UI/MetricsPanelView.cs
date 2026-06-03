using RTS.Core;
using RTS.Presentation;
using UnityEngine;
using UnityEngine.UI;

namespace RTS.Presentation.UI
{
    public sealed class MetricsPanelView : MonoBehaviour
    {
        private Text _body;
        private string _lastBody = string.Empty;

        public void Initialize(Text body)
        {
            _body = body;
        }

        public void Refresh(
            HumanPlayModeController modeController,
            HumanPlayerController humanPlayerController,
            PlayerCommandController commandController,
            GameSpeedController speedController)
        {
            if (_body == null)
            {
                return;
            }

            string mode = modeController != null ? modeController.CurrentMode.ToString() : "n/a";
            string humanSide = modeController != null && modeController.HasHumanSide ? modeController.HumanSide.ToString() : Owner.Neutral.ToString();
            string control = humanPlayerController != null && humanPlayerController.IsHumanControlActive ? "active" : "inactive";
            string speed = speedController != null ? (speedController.IsPaused ? "paused" : speedController.CurrentStepsPerSecond.ToString("0.##") + " steps/sec") : "n/a";
            string status = commandController != null ? commandController.LastCommandStatus : "PlayerCommandController missing.";
            string rejection = commandController != null && !string.IsNullOrWhiteSpace(commandController.LastCommandRejectedReason)
                ? commandController.LastCommandRejectedReason
                : "n/a";
            string diagnostics = modeController != null ? modeController.LastDiagnostics : "HumanPlayModeController missing.";

            string body = "Mode: " + mode
                + "\nHuman side: " + humanSide + " (" + control + ")"
                + "\nAI/fallback: " + diagnostics
                + "\nSpeed: " + speed
                + "\nLast command: " + status
                + "\nLast rejection: " + rejection;
            if (_lastBody != body)
            {
                _lastBody = body;
                _body.text = body;
            }
        }
    }
}
