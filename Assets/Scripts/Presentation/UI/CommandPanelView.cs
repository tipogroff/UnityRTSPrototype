using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using RTS.Presentation;
using RTS.Presentation.Orders;
using UnityEngine;
using UnityEngine.UI;

namespace RTS.Presentation.UI
{
    public sealed class CommandPanelView : MonoBehaviour
    {
        private Text _status;
        private PlayerCommandController _commandController;
        private HumanOrderController _orderController;

        public void Initialize(Text status, PlayerCommandController commandController, HumanOrderController orderController = null)
        {
            _status = status;
            _commandController = commandController;
            _orderController = orderController;
        }

        public void Refresh(PlayerCommandController commandController)
        {
            Refresh(commandController, null, null);
        }

        public void Refresh(
            PlayerCommandController commandController,
            IReadOnlyList<UnitRuntime> selectedUnits,
            UnitRuntime primary,
            ResourceNode hoveredResource = null)
        {
            if (commandController != null)
            {
                _commandController = commandController;
            }

            int selectionCount = selectedUnits != null ? selectedUnits.Count : (primary != null ? 1 : 0);

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
            HumanUnitOrder order = _orderController != null ? _orderController.GetOrderStatus(primary) : null;
            string orderLine = order != null ? order.StatusText : "Order: none";
            string resourceLine = hoveredResource != null
                ? "Hover resource: " + hoveredResource.CurrentResources + " remaining (" + (hoveredResource.IsExhausted ? "Exhausted" : "Active") + ")"
                : "Hover resource: none";
            _status.text = BuildContextLine(selectionCount, primary)
                + "\nMode: " + _commandController.CurrentMode
                + "\nLast: " + _commandController.LastCommandStatus
                + "\nResult: " + result
                + "\n" + orderLine
                + "\n" + resourceLine
                + "\n" + BuildControlHints(selectionCount);
        }

        private static string BuildContextLine(int selectionCount, UnitRuntime primary)
        {
            if (selectionCount <= 0 || primary == null)
            {
                return "Select a unit or building.";
            }

            if (selectionCount > 1)
            {
                return $"Group selected: {selectionCount} mobile units. Use RMB for Move Group / Attack Area.";
            }

            return primary.Type switch
            {
                UnitType.Worker => "Worker selected: use RMB for Move, Gather, Attack, Build Barracks.",
                UnitType.Base => "Base selected: use Production to make Workers.",
                UnitType.Barracks => "Barracks selected: use Production to make combat units.",
                UnitType.Light or UnitType.Heavy or UnitType.Ranged => "Combat unit selected: use RMB for Move / Attack.",
                _ => "No contextual commands available."
            };
        }

        private static string BuildControlHints(int selectionCount)
        {
            if (selectionCount > 1)
            {
                return "Controls: LMB select, Drag units, RMB empty=Group Move, RMB enemy area=Group Attack, Stop=cancel selected.";
            }

            return "Controls: LMB select, Drag units, RMB empty=Move, RMB resource=Gather, RMB enemy=Attack, RMB free with Worker=Build, Stop=cancel selected.";
        }
    }
}
