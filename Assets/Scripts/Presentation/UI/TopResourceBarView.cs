using RTS.Gameplay;
using RTS.Presentation;
using UnityEngine;
using UnityEngine.UI;

namespace RTS.Presentation.UI
{
    public sealed class TopResourceBarView : MonoBehaviour
    {
        private Text _step;
        private Text _state;
        private Text _speed;

        public void Initialize(Text step, Text state, Text speed)
        {
            _step = step;
            _state = state;
            _speed = speed;
        }

        public void Refresh(MatchManager matchManager)
        {
            Refresh(matchManager, null);
        }

        public void Refresh(MatchManager matchManager, GameSpeedController speedController)
        {
            if (_step != null)
            {
                string step = matchManager != null ? matchManager.Step + " / " + matchManager.MaxSteps : "n/a";
                _step.text = "Step " + step;
            }

            if (_state != null)
            {
                _state.text = speedController != null && speedController.IsPaused ? "Paused" : "Running";
            }

            if (_speed != null)
            {
                float speed = speedController != null ? speedController.CurrentSpeed : 1f;
                _speed.text = "Speed x" + speed.ToString("0.##");
            }
        }
    }
}
