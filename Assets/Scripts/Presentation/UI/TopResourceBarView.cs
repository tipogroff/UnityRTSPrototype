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
        private int _lastStep = int.MinValue;
        private int _lastMaxSteps = int.MinValue;
        private bool _lastPaused;
        private float _lastSpeed = -1f;
        private bool _hasState;

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
                int step = matchManager != null ? matchManager.Step : -1;
                int maxSteps = matchManager != null ? matchManager.MaxSteps : -1;
                if (step != _lastStep || maxSteps != _lastMaxSteps)
                {
                    _lastStep = step;
                    _lastMaxSteps = maxSteps;
                    _step.text = matchManager != null ? "Step " + step + " / " + maxSteps : "Step n/a";
                }
            }

            if (_state != null)
            {
                bool paused = speedController != null && speedController.IsPaused;
                if (!_hasState || paused != _lastPaused)
                {
                    _hasState = true;
                    _lastPaused = paused;
                    _state.text = paused ? "Paused" : "Running";
                }
            }

            if (_speed != null)
            {
                float speed = speedController != null ? speedController.CurrentSpeed : 1f;
                if (!Mathf.Approximately(speed, _lastSpeed))
                {
                    _lastSpeed = speed;
                    _speed.text = "Speed x" + speed.ToString("0.##");
                }
            }
        }
    }
}
