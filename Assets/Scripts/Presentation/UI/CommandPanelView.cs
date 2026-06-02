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
            Refresh(commandController, selectedUnits, primary, hoveredResource, null, null);
        }

        public void Refresh(
            PlayerCommandController commandController,
            IReadOnlyList<UnitRuntime> selectedUnits,
            UnitRuntime primary,
            ResourceNode hoveredResource,
            HumanPlayModeController modeController,
            HumanPlayerController humanPlayerController)
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
            string modeStatus = BuildModeStatus(modeController, humanPlayerController);
            if (!HasPlayer2ManualMode(modeController))
            {
                _status.text = modeStatus
                    + "\nHuman control inactive"
                    + "\n\u0420\u0443\u0447\u043d\u043e\u0435 \u0443\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u0442\u043e\u043b\u044c\u043a\u043e \u0432 \u0440\u0435\u0436\u0438\u043c\u0435 AI \u043f\u0440\u043e\u0442\u0438\u0432 \u0438\u0433\u0440\u043e\u043a\u0430"
                    + "\n" + resourceLine;
                return;
            }

            _status.text = modeStatus
                + "\n" + BuildContextLine(selectionCount, primary)
                + "\nLast: " + _commandController.LastCommandStatus
                + "\nResult: " + result
                + "\n" + orderLine
                + "\n" + resourceLine
                + "\n" + BuildControlHints(selectionCount);
        }

        private static string BuildModeStatus(HumanPlayModeController modeController, HumanPlayerController humanPlayerController)
        {
            if (modeController == null)
            {
                return "\u0420\u0435\u0436\u0438\u043c: \u043d\u0435 \u043e\u043f\u0440\u0435\u0434\u0435\u043b\u0451\u043d";
            }

            return modeController.CurrentMode switch
            {
                HumanPlayMode.AIvsPlayer2 =>
                    "\u0420\u0435\u0436\u0438\u043c: AI \u043f\u0440\u043e\u0442\u0438\u0432 \u0438\u0433\u0440\u043e\u043a\u0430"
                    + "\n\u0418\u0433\u0440\u043e\u043a: Player2"
                    + "\n\u0423\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435: "
                    + (humanPlayerController != null && humanPlayerController.IsHumanControlActive
                        ? "\u0430\u043a\u0442\u0438\u0432\u043d\u043e"
                        : "\u043e\u0436\u0438\u0434\u0430\u043d\u0438\u0435 \u0441\u0442\u0430\u0440\u0442\u0430 \u043c\u0430\u0442\u0447\u0430"),
                HumanPlayMode.AIvsBot =>
                    "\u0420\u0435\u0436\u0438\u043c: AI \u043f\u0440\u043e\u0442\u0438\u0432 \u0431\u043e\u0442\u0430"
                    + "\n\u0423\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435: \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e",
                HumanPlayMode.AIvsAI =>
                    "\u0420\u0435\u0436\u0438\u043c: AI \u043f\u0440\u043e\u0442\u0438\u0432 AI"
                    + "\n\u0423\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435: \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e",
                _ => "\u0420\u0435\u0436\u0438\u043c: " + modeController.CurrentMode,
            };
        }

        private static bool HasPlayer2ManualMode(HumanPlayModeController modeController)
        {
            return modeController != null
                && modeController.CurrentMode == HumanPlayMode.AIvsPlayer2
                && modeController.HasHumanSide
                && modeController.HumanSide == Owner.Player2;
        }

        private static string BuildContextLine(int selectionCount, UnitRuntime primary)
        {
            if (selectionCount <= 0 || primary == null)
            {
                return "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u044e\u043d\u0438\u0442 Player2 \u0434\u043b\u044f \u043e\u0442\u0434\u0430\u0447\u0438 \u043f\u0440\u0438\u043a\u0430\u0437\u0430";
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
