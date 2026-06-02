using RTS.Core;
using RTS.Gameplay;
using UnityEngine;
using UnityEngine.UI;

namespace RTS.Presentation.UI
{
    public sealed class TopResourceBarView : MonoBehaviour
    {
        private Text _player1;
        private Text _player2;
        private Text _phase;
        private Text _step;

        public void Initialize(Text player1, Text player2, Text phase, Text step)
        {
            _player1 = player1;
            _player2 = player2;
            _phase = phase;
            _step = step;
        }

        public void Refresh(MatchManager matchManager)
        {
            if (_player1 != null)
            {
                int value = matchManager != null ? matchManager.GetResources(Owner.Player1) : 0;
                _player1.text = "P1 AI: " + value;
            }

            if (_player2 != null)
            {
                int value = matchManager != null ? matchManager.GetResources(Owner.Player2) : 0;
                _player2.text = "P2 Human Resources: " + value;
            }

            if (_phase != null)
            {
                _phase.text = "Phase: " + (matchManager != null ? matchManager.Phase.ToString() : "n/a");
            }

            if (_step != null)
            {
                string step = matchManager != null ? matchManager.Step + " / " + matchManager.MaxSteps : "n/a";
                _step.text = "Step: " + step;
            }
        }
    }
}
