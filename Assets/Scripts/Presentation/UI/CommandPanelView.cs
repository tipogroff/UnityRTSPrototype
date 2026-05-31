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
        private Button _moveButton;
        private Button _attackButton;
        private Button _harvestButton;
        private Button _returnButton;
        private Button _buildBarracksButton;

        public void Initialize(Text status, PlayerCommandController commandController, HumanOrderController orderController = null)
        {
            _status = status;
            _commandController = commandController;
            _orderController = orderController;
        }

        public void SetContextButtons(
            Button moveButton,
            Button attackButton,
            Button harvestButton,
            Button returnButton,
            Button buildBarracksButton)
        {
            _moveButton = moveButton;
            _attackButton = attackButton;
            _harvestButton = harvestButton;
            _returnButton = returnButton;
            _buildBarracksButton = buildBarracksButton;
        }

        public void Refresh(PlayerCommandController commandController)
        {
            Refresh(commandController, null, null);
        }

        public void Refresh(PlayerCommandController commandController, IReadOnlyList<UnitRuntime> selectedUnits, UnitRuntime primary)
        {
            if (commandController != null)
            {
                _commandController = commandController;
            }

            int selectionCount = selectedUnits != null ? selectedUnits.Count : (primary != null ? 1 : 0);
            RefreshButtons(selectionCount, primary);

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
            _status.text = BuildContextLine(selectionCount, primary)
                + "\nMode: " + _commandController.CurrentMode
                + "\nLast: " + _commandController.LastCommandStatus
                + "\nResult: " + result
                + "\n" + orderLine;
        }

        private void RefreshButtons(int selectionCount, UnitRuntime primary)
        {
            SetButton(_moveButton, false, false);
            SetButton(_attackButton, false, false);
            SetButton(_harvestButton, false, false);
            SetButton(_returnButton, false, false);
            SetButton(_buildBarracksButton, false, false);

            if (primary == null || selectionCount <= 0)
            {
                return;
            }

            if (selectionCount > 1)
            {
                bool hasMobile = ContainsMobile(primary);
                SetButton(_moveButton, hasMobile, false);
                SetButton(_attackButton, hasMobile, false);
                return;
            }

            switch (primary.Type)
            {
                case UnitType.Worker:
                    SetButton(_moveButton, true, true);
                    SetButton(_harvestButton, true, true);
                    SetButton(_returnButton, true, true);
                    SetButton(_buildBarracksButton, true, true);
                    break;
                case UnitType.Light:
                case UnitType.Heavy:
                case UnitType.Ranged:
                    SetButton(_moveButton, true, true);
                    SetButton(_attackButton, true, true);
                    break;
                case UnitType.Base:
                case UnitType.Barracks:
                    break;
            }
        }

        private static bool ContainsMobile(UnitRuntime primary)
        {
            return primary != null && !primary.IsBuilding;
        }

        private static void SetButton(Button button, bool visible, bool interactable)
        {
            if (button == null)
            {
                return;
            }

            button.gameObject.SetActive(visible);
            button.interactable = interactable;
        }

        private static string BuildContextLine(int selectionCount, UnitRuntime primary)
        {
            if (selectionCount <= 0 || primary == null)
            {
                return "Select a unit or building.";
            }

            if (selectionCount > 1)
            {
                return "Group selected: commands are limited. Group move requires pathfinding/formation; use single selection.";
            }

            return primary.Type switch
            {
                UnitType.Worker => "Worker commands: Move, Harvest, Return, Build Barracks.",
                UnitType.Base => "Base selected: use Production to make Workers.",
                UnitType.Barracks => "Barracks selected: use Production to make combat units.",
                UnitType.Light or UnitType.Heavy or UnitType.Ranged => "Combat commands: Move or Attack.",
                _ => "No contextual commands available."
            };
        }
    }
}
