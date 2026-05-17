using RTS.Presentation;
using UnityEngine;
using UnityEngine.UI;

namespace RTS.Presentation.UI
{
    public sealed class CommandPanelView : MonoBehaviour
    {
        private Text _status;
        private PlayerCommandController _commandController;

        public void Initialize(Text status, PlayerCommandController commandController)
        {
            _status = status;
            _commandController = commandController;
        }

        public void Refresh(PlayerCommandController commandController)
        {
            if (commandController != null)
            {
                _commandController = commandController;
            }

            if (_status == null)
            {
                return;
            }

            if (_commandController == null)
            {
                _status.text = "Commands unavailable: PlayerCommandController missing.";
                return;
            }

            string result = _commandController.LastCommandAccepted ? "accepted" : "rejected";
            _status.text = "Mode: " + _commandController.CurrentMode
                + "\nLast: " + _commandController.LastCommandStatus
                + "\nResult: " + result;
        }
    }
}
