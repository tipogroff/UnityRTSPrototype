using RTS.Gameplay;
using UnityEngine;
using UnityEngine.UI;

namespace RTS.Presentation.UI
{
    public sealed class SelectionInfoPanelView : MonoBehaviour
    {
        private Text _title;
        private Text _body;

        public void Initialize(Text title, Text body)
        {
            _title = title;
            _body = body;
        }

        public void Refresh(UnitRuntime selected)
        {
            if (_title != null)
            {
                _title.text = selected == null ? "Selection" : selected.Owner + " " + selected.Type;
            }

            if (_body == null)
            {
                return;
            }

            if (selected == null)
            {
                _body.text = "No unit selected";
                return;
            }

            _body.text =
                "HP: " + selected.HP + "/" + selected.MaxHP
                + "\nCarry: " + selected.CarriedResources
                + "\nCell: " + selected.GridPos
                + "\nAlive: " + selected.IsAlive;
        }
    }
}
