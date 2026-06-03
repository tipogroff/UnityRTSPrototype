using System.Collections.Generic;
using System.Text;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;
using UnityEngine.UI;

namespace RTS.Presentation.UI
{
    public sealed class SelectionInfoPanelView : MonoBehaviour
    {
        private Text _title;
        private Text _body;
        private Text _status;
        private readonly UnitRuntime[] _singleSelection = new UnitRuntime[1];
        private readonly Dictionary<UnitType, int> _typeCounts = new Dictionary<UnitType, int>();
        private readonly StringBuilder _builder = new StringBuilder(256);
        private string _lastTitle = string.Empty;
        private string _lastBody = string.Empty;
        private string _lastStatus = string.Empty;

        public void Initialize(Text title, Text body)
        {
            Initialize(title, body, null);
        }

        public void Initialize(Text title, Text body, Text status)
        {
            _title = title;
            _body = body;
            _status = status;
        }

        public void Refresh(UnitRuntime selected)
        {
            _singleSelection[0] = selected;
            Refresh(selected != null ? _singleSelection : null, selected);
        }

        public void Refresh(IReadOnlyList<UnitRuntime> selectedUnits, UnitRuntime primary)
        {
            Refresh(selectedUnits, primary, null);
        }

        public void Refresh(IReadOnlyList<UnitRuntime> selectedUnits, UnitRuntime primary, PlayerCommandController commandController)
        {
            int selectedCount = selectedUnits != null ? selectedUnits.Count : 0;
            if (_title != null)
            {
                SetTitle(selectedCount <= 0 ? "Selection" : BuildTitle(selectedCount, primary));
            }

            if (_body == null)
            {
                return;
            }

            if (selectedCount <= 0 || primary == null)
            {
                SetBody("No unit selected");
                SetCommandStatus(commandController, false);
                return;
            }

            if (selectedCount > 1)
            {
                SetBody(BuildMultiSelectionText(selectedUnits, primary));
                SetCommandStatus(commandController, true);
                return;
            }

            UnitRuntime selected = primary;
            SetBody(
                "Type: " + selected.Type
                + "\nOwner: " + selected.Owner
                + "\nHP: " + selected.HP + "/" + selected.MaxHP
                + (selected.Type == UnitType.Worker ? "\nCarry: " + selected.CarriedResources : string.Empty)
                + "\nCell: " + selected.GridPos
                + "\nFacing: " + selected.Facing
                + "\nState: " + (selected.IsAlive ? "Ready" : "Destroyed"));
            SetCommandStatus(commandController, true);
        }

        private void SetCommandStatus(PlayerCommandController commandController, bool hasSelection)
        {
            if (_status == null)
            {
                return;
            }

            if (!hasSelection)
            {
                SetStatus(string.Empty);
                return;
            }

            SetStatus(commandController != null
                ? "Last: " + commandController.LastCommandStatus
                : "Orders unavailable");
        }

        private static string BuildTitle(int selectedCount, UnitRuntime primary)
        {
            if (selectedCount <= 1)
            {
                return primary != null ? primary.Owner + " " + primary.Type : "Selection";
            }

            return "Selection (" + selectedCount + ")";
        }

        private string BuildMultiSelectionText(IReadOnlyList<UnitRuntime> selectedUnits, UnitRuntime primary)
        {
            _typeCounts.Clear();
            int mobileCount = 0;
            for (int i = 0; i < selectedUnits.Count; i++)
            {
                UnitRuntime unit = selectedUnits[i];
                if (unit == null)
                {
                    continue;
                }

                _typeCounts.TryGetValue(unit.Type, out int count);
                _typeCounts[unit.Type] = count + 1;
                if (unit.IsBuilding)
                {
                    continue;
                }

                mobileCount++;
            }

            _builder.Clear();
            _builder.Append("Selected: ").Append(selectedUnits.Count);
            _builder.Append("\nMobile units: ").Append(mobileCount);
            _builder.Append("\nPrimary: ");
            if (primary != null)
            {
                _builder.Append(primary.Type).Append(' ').Append(primary.GridPos);
            }
            else
            {
                _builder.Append("None");
            }
            _builder.Append("\nTypes:");
            foreach (KeyValuePair<UnitType, int> pair in _typeCounts)
            {
                _builder.Append("\n- ").Append(pair.Key).Append(": ").Append(pair.Value);
            }

            return _builder.ToString();
        }

        private void SetTitle(string value)
        {
            if (_title != null && _lastTitle != value)
            {
                _lastTitle = value;
                _title.text = value;
            }
        }

        private void SetBody(string value)
        {
            if (_body != null && _lastBody != value)
            {
                _lastBody = value;
                _body.text = value;
            }
        }

        private void SetStatus(string value)
        {
            if (_status != null && _lastStatus != value)
            {
                _lastStatus = value;
                _status.text = value;
            }
        }
    }
}
