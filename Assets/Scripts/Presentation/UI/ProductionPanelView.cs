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
        private UnitRuntime _lastSelected;
        private BuildingRuntime _lastBuilding;
        private bool _wasProducing;
        private string _completionStatus = string.Empty;
        private string _lastTitle = string.Empty;
        private string _lastStatus = string.Empty;
        private bool _lastVisible;
        private bool _lastBaseGroupVisible;
        private bool _lastBarracksGroupVisible;
        private bool _lastInteractable = true;

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
            SetActiveIfChanged(gameObject, visible, ref _lastVisible);
            if (!visible)
            {
                return;
            }

            if (_title != null)
            {
                SetTitle(isBase ? "Base Production" : isBarracks ? "Barracks Production" : "Production");
            }

            if (_baseGroup != null)
            {
                SetActiveIfChanged(_baseGroup, isBase, ref _lastBaseGroupVisible);
            }

            if (_barracksGroup != null)
            {
                SetActiveIfChanged(_barracksGroup, isBarracks, ref _lastBarracksGroupVisible);
            }

            BuildingRuntime building = GetSelectedBuilding(selected);
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
            SetInteractableIfChanged(!producing);

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
                SetStatus(
                    "Resources: " + resources
                    + "\nQueue: " + queueStatus
                    + "\nLast: " + commandStatus);
            }
        }

        private BuildingRuntime GetSelectedBuilding(UnitRuntime selected)
        {
            if (_lastSelected != selected)
            {
                _lastSelected = selected;
                _lastBuilding = selected != null ? selected.GetComponent<BuildingRuntime>() : null;
            }

            return _lastBuilding;
        }

        private void SetTitle(string value)
        {
            if (_title != null && _lastTitle != value)
            {
                _lastTitle = value;
                _title.text = value;
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

        private void SetInteractableIfChanged(bool interactable)
        {
            if (_lastInteractable == interactable)
            {
                return;
            }

            _lastInteractable = interactable;
            SetInteractable(interactable);
        }

        private static void SetActiveIfChanged(GameObject target, bool active, ref bool lastValue)
        {
            if (target == null)
            {
                return;
            }

            lastValue = active;
            if (target.activeSelf != active)
            {
                target.SetActive(active);
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
