using RTS.Core;
using RTS.Gameplay;
using UnityEngine;
using UnityEngine.UI;

namespace RTS.Presentation.UI
{
    public sealed class ProductionPanelView : MonoBehaviour
    {
        private Text _title;
        private GameObject _baseGroup;
        private GameObject _barracksGroup;
        private Text _status;
        private Button _workerButton;
        private Button _lightButton;
        private Button _heavyButton;
        private Button _rangedButton;
        private ProductionQueue _lastQueue;
        private bool _wasProducing;
        private string _completionStatus = string.Empty;

        public void Initialize(
            Text title,
            GameObject baseGroup,
            GameObject barracksGroup,
            Text status,
            Button workerButton,
            Button lightButton,
            Button heavyButton,
            Button rangedButton)
        {
            _title = title;
            _baseGroup = baseGroup;
            _barracksGroup = barracksGroup;
            _status = status;
            _workerButton = workerButton;
            _lightButton = lightButton;
            _heavyButton = heavyButton;
            _rangedButton = rangedButton;
        }

        public void Refresh(UnitRuntime selected)
        {
            Refresh(selected, selected != null ? 1 : 0, null);
        }

        public void Refresh(UnitRuntime selected, int selectionCount)
        {
            Refresh(selected, selectionCount, null);
        }

        public void Refresh(UnitRuntime selected, int selectionCount, PlayerCommandController commandController)
        {
            bool single = selected != null && selectionCount == 1;
            bool isBase = single && selected.Type == UnitType.Base;
            bool isBarracks = single && selected.Type == UnitType.Barracks;
            bool visible = isBase || isBarracks;
            gameObject.SetActive(visible);
            if (!visible)
            {
                return;
            }

            if (_title != null)
            {
                _title.text = isBase ? "Base Production" : isBarracks ? "Barracks Production" : "Production";
            }

            if (_baseGroup != null)
            {
                _baseGroup.SetActive(isBase);
            }

            if (_barracksGroup != null)
            {
                _barracksGroup.SetActive(isBarracks);
            }

            BuildingRuntime building = selected.GetComponent<BuildingRuntime>();
            ProductionQueue queue = building != null ? building.GetProductionQueue() : null;
            bool producing = queue != null && queue.IsProducing;
            if (_lastQueue == queue && _wasProducing && !producing)
            {
                _completionStatus = "Production completed";
            }
            else if (producing)
            {
                _completionStatus = string.Empty;
            }

            _lastQueue = queue;
            _wasProducing = producing;
            SetInteractable(!producing);

            if (_status != null)
            {
                int resources = MatchManager.Instance != null ? MatchManager.Instance.GetResources(Owner.Player2) : 0;
                string queueStatus = "idle";
                if (producing)
                {
                    int progress = Mathf.RoundToInt(queue.ProductionProgress * 100f);
                    queueStatus = $"producing {queue.CurrentProducingType}: {progress}%";
                }

                string commandStatus = !string.IsNullOrEmpty(_completionStatus)
                    ? _completionStatus
                    : commandController != null ? commandController.LastProductionCommandStatus : "No production command submitted yet.";
                _status.text =
                    "Resources: " + resources
                    + "\nQueue: " + queueStatus
                    + "\nLast: " + commandStatus;
            }
        }

        private void SetInteractable(bool interactable)
        {
            SetInteractable(_workerButton, interactable);
            SetInteractable(_lightButton, interactable);
            SetInteractable(_heavyButton, interactable);
            SetInteractable(_rangedButton, interactable);
        }

        private static void SetInteractable(Button button, bool interactable)
        {
            if (button != null)
            {
                button.interactable = interactable;
            }
        }
    }
}
