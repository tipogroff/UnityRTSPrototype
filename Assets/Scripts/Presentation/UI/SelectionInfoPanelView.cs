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

        public void Initialize(Text title, Text body)
        {
            _title = title;
            _body = body;
        }

        public void Refresh(UnitRuntime selected)
        {
            Refresh(selected != null ? new[] { selected } : null, selected);
        }

        public void Refresh(IReadOnlyList<UnitRuntime> selectedUnits, UnitRuntime primary)
        {
            int selectedCount = selectedUnits != null ? selectedUnits.Count : 0;
            if (_title != null)
            {
                _title.text = selectedCount <= 0 ? "Selection" : BuildTitle(selectedCount, primary);
            }

            if (_body == null)
            {
                return;
            }

            if (selectedCount <= 0 || primary == null)
            {
                _body.text = "No unit selected";
                return;
            }

            if (selectedCount > 1)
            {
                _body.text = BuildMultiSelectionText(selectedUnits, primary);
                return;
            }

            UnitRuntime selected = primary;
            _body.text =
                "Type: " + selected.Type
                + "\nOwner: " + selected.Owner
                + "\nHP: " + selected.HP + "/" + selected.MaxHP
                + (selected.Type == UnitType.Worker ? "\nCarry: " + selected.CarriedResources : string.Empty)
                + "\nCell: " + selected.GridPos
                + "\nFacing: " + selected.Facing
                + "\nState: " + (selected.IsAlive ? "Ready" : "Destroyed");
        }

        private static string BuildTitle(int selectedCount, UnitRuntime primary)
        {
            if (selectedCount <= 1)
            {
                return primary != null ? primary.Owner + " " + primary.Type : "Selection";
            }

            return "Selection (" + selectedCount + ")";
        }

        private static string BuildMultiSelectionText(IReadOnlyList<UnitRuntime> selectedUnits, UnitRuntime primary)
        {
            Dictionary<UnitType, int> counts = new Dictionary<UnitType, int>();
            int mobileCount = 0;
            int buildingCount = 0;
            for (int i = 0; i < selectedUnits.Count; i++)
            {
                UnitRuntime unit = selectedUnits[i];
                if (unit == null)
                {
                    continue;
                }

                counts.TryGetValue(unit.Type, out int count);
                counts[unit.Type] = count + 1;
                if (unit.IsBuilding)
                {
                    buildingCount++;
                }
                else
                {
                    mobileCount++;
                }
            }

            StringBuilder builder = new StringBuilder();
            builder.Append("Selected: ").Append(selectedUnits.Count);
            builder.Append("\nMobile: ").Append(mobileCount).Append("  Buildings: ").Append(buildingCount);
            builder.Append("\nPrimary: ");
            builder.Append(primary != null ? primary.Type + " " + primary.GridPos.ToString() : "None");
            builder.Append("\nTypes:");
            foreach (KeyValuePair<UnitType, int> pair in counts)
            {
                builder.Append("\n- ").Append(pair.Key).Append(": ").Append(pair.Value);
            }

            return builder.ToString();
        }
    }
}
