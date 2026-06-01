using System;
using RTS.Core;
using RTS.Gameplay;
using RTS.ML;
using UnityEngine;
using UnityEngine.EventSystems;

#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace RTS.Presentation
{
    public enum HumanCommandMode
    {
        Context = 0,
        Move = 1,
        Harvest = 2,
        Return = 3,
        Attack = 4,
        ProduceWorker = 5,
        BuildBarracks = 6,
        ProduceLight = 7,
        ProduceHeavy = 8,
        ProduceRanged = 9,
    }

    [DisallowMultipleComponent]
    public sealed class PlayerCommandController : MonoBehaviour
    {
        [Header("References")]
        [SerializeField] private PlayerSelectionController _selectionController;
        [SerializeField] private Camera _commandCamera;
        [SerializeField] private GridManager _gridManager;
        [SerializeField] private UnitRegistry _unitRegistry;
        [SerializeField] private ResourceManager _resourceManager;
        [SerializeField] private MatchManager _matchManager;
        [SerializeField] private EpisodeController _episodeController;

        [Header("Raycast")]
        [SerializeField] private LayerMask _raycastMask = ~0;
        [SerializeField] private float _raycastDistance = 500f;

        [Header("Diagnostics")]
        [SerializeField] private bool _logCommandDiagnostics = true;

        private Owner _humanSide = Owner.Player1;
        private bool _manualInputEnabled;
        private bool _legacyInputUnavailable;
        private ActionApplier _actionApplier;

        public HumanCommandMode CurrentMode { get; private set; } = HumanCommandMode.Context;
        public string LastCommandStatus { get; private set; } = "No command submitted yet.";
        public bool LastCommandAccepted { get; private set; }
        public string LastCommandRejectedReason { get; private set; } = string.Empty;

        public event Action<string, bool> OnCommandStatusChanged;
        public event Action<GridPosition, Vector2> OnMoveContextRequested;
        public event Action<ResourceNode, Vector2> OnGatherContextRequested;

        private void Awake()
        {
            ResolveReferences();
            EnsureActionApplier();
        }

        private void Update()
        {
            if (!_manualInputEnabled)
            {
                return;
            }

            if (!IsRightClickPressed())
            {
                return;
            }

            bool pointerOverUi = EventSystem.current != null && EventSystem.current.IsPointerOverGameObject();
            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            int selectedCount = _selectionController != null ? _selectionController.SelectedUnits.Count : 0;
            Debug.Log($"[HumanMove3G1R] RMB received pointerOverUi={pointerOverUi} selectedCount={selectedCount} primary={DescribeUnit(selected)} mode={CurrentMode}");
            if (pointerOverUi)
            {
                Debug.Log("[HumanMove3G1R] RMB context menu not opened reason=pointer over UI");
                return;
            }

            if (!TryResolvePointerTarget(out GridPosition targetCell, out UnitRuntime targetUnit, out bool hitAny))
            {
                if (hitAny)
                {
                    SetRejected("Pointer target is invalid for command submission.");
                }

                Debug.Log($"[HumanMove3G1R] RMB context menu not opened reason=pointer target unresolved hitAny={hitAny}");
                return;
            }

            Debug.Log($"[HumanMove3G1R] RMB resolved cell={targetCell} target={(targetUnit == null ? "free" : DescribeUnit(targetUnit))}");

            switch (CurrentMode)
            {
                case HumanCommandMode.Context:
                    HandleContextRightClick(targetCell, targetUnit);
                    break;
                case HumanCommandMode.Move:
                    TryMoveToCell(targetCell);
                    CurrentMode = HumanCommandMode.Context;
                    break;
                case HumanCommandMode.Harvest:
                    TryHarvestToCell(targetCell);
                    CurrentMode = HumanCommandMode.Context;
                    break;
                case HumanCommandMode.Return:
                    TryReturnToCell(targetCell);
                    CurrentMode = HumanCommandMode.Context;
                    break;
                case HumanCommandMode.Attack:
                    TryAttackUnit(targetUnit, targetCell);
                    CurrentMode = HumanCommandMode.Context;
                    break;
                case HumanCommandMode.ProduceWorker:
                    TryProduceWorker();
                    CurrentMode = HumanCommandMode.Context;
                    break;
                case HumanCommandMode.BuildBarracks:
                    TryBuildBarracks();
                    CurrentMode = HumanCommandMode.Context;
                    break;
                case HumanCommandMode.ProduceLight:
                    TryProduceLight();
                    CurrentMode = HumanCommandMode.Context;
                    break;
                case HumanCommandMode.ProduceHeavy:
                    TryProduceHeavy();
                    CurrentMode = HumanCommandMode.Context;
                    break;
                case HumanCommandMode.ProduceRanged:
                    TryProduceRanged();
                    CurrentMode = HumanCommandMode.Context;
                    break;
                default:
                    CurrentMode = HumanCommandMode.Context;
                    break;
            }
        }

        public void SetHumanSide(Owner humanSide)
        {
            _humanSide = humanSide;
        }

        public void SetManualInputEnabled(bool enabled)
        {
            _manualInputEnabled = enabled;
            if (!enabled)
            {
                CurrentMode = HumanCommandMode.Context;
            }
        }

        public void SetCommandMode(HumanCommandMode mode)
        {
            CurrentMode = mode;
            SetStatus($"Command mode set to {mode}.", true, string.Empty);
        }

        public void TryMoveToClickedCell()
        {
            BeginMoveCommandMode();
        }

        public void BeginMoveCommandMode()
        {
            if (RejectIfMultiSelectionActive())
            {
                return;
            }

            CurrentMode = HumanCommandMode.Move;
            SetStatus("Move mode: right-click adjacent empty cell.", true, string.Empty);
        }

        public bool SubmitMoveForUnit(UnitRuntime unit, Direction direction)
        {
            Debug.Log($"[HumanMove3G1R] SubmitMoveForUnit invoked unit={DescribeUnit(unit)} direction={direction} actorPosition={(unit != null ? unit.GridPos.ToString() : "<null>")}");
            if (unit == null)
            {
                SetRejected("Move order unit is missing.");
                return false;
            }

            if (unit.Owner != _humanSide)
            {
                SetRejected($"Move order unit belongs to {unit.Owner}, not {_humanSide}.");
                return false;
            }

            AgentAction action = new AgentAction(
                actorPosition: unit.GridPos,
                actionType: UnitActionType.Move,
                direction: direction,
                produceUnitType: ProducibleUnit.Worker,
                attackTargetPosition: default,
                isValid: true,
                invalidationReason: string.Empty,
                sourceType: ActionSourceType.Debug);

            bool accepted = SubmitAgentAction(action, "Move order step");
            Debug.Log($"[HumanMove3G1R] SubmitMoveForUnit ActionApplier result accepted={accepted} reason={LastCommandRejectedReason}");
            return accepted;
        }

        public bool SubmitHarvestForUnit(UnitRuntime worker, Direction direction, out string reason)
        {
            bool accepted = SubmitWorkerDirectionalAction(worker, UnitActionType.Harvest, direction, "Harvest order step");
            reason = accepted ? string.Empty : LastCommandRejectedReason;
            return accepted;
        }

        public bool SubmitReturnForUnit(UnitRuntime worker, Direction direction, out string reason)
        {
            bool accepted = SubmitWorkerDirectionalAction(worker, UnitActionType.Return, direction, "Return order step");
            reason = accepted ? string.Empty : LastCommandRejectedReason;
            return accepted;
        }

        public void PublishHumanOrderStatus(string message, bool accepted)
        {
            SetStatus(message, accepted, accepted ? string.Empty : message);
        }

        public void TryAttackClickedTarget()
        {
            BeginAttackCommandMode();
        }

        public void BeginAttackCommandMode()
        {
            if (RejectIfMultiSelectionActive())
            {
                return;
            }

            CurrentMode = HumanCommandMode.Attack;
            SetStatus("Attack mode: right click enemy target.", true, string.Empty);
        }

        public void TryHarvestSelected()
        {
            if (RejectIfMultiSelectionActive())
            {
                return;
            }

            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            if (selected == null)
            {
                SetRejected("No selected unit.");
                return;
            }

            foreach (Direction direction in Enum.GetValues(typeof(Direction)))
            {
                GridPosition target = selected.GridPos.Neighbour(direction);
                if (_resourceManager != null && _resourceManager.GetResourceNode(target) != null)
                {
                    SubmitDirectionalAction(UnitActionType.Harvest, direction, "Harvest");
                    return;
                }
            }

            SetRejected("No adjacent resource found for harvest.");
        }

        public void TryReturnSelected()
        {
            if (RejectIfMultiSelectionActive())
            {
                return;
            }

            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            if (selected == null)
            {
                SetRejected("No selected unit.");
                return;
            }

            foreach (Direction direction in Enum.GetValues(typeof(Direction)))
            {
                GridPosition target = selected.GridPos.Neighbour(direction);
                UnitRuntime occupant = _gridManager != null ? _gridManager.GetOccupant(target) : null;
                if (occupant != null && occupant.Type == UnitType.Base && occupant.Owner == _humanSide)
                {
                    SubmitDirectionalAction(UnitActionType.Return, direction, "Return");
                    return;
                }
            }

            SetRejected("No adjacent friendly Base found for return.");
        }

        public void TryProduceWorker()
        {
            TryProduce(ProducibleUnit.Worker, UnitType.Base, "Produce Worker");
        }

        public void TryBuildBarracks()
        {
            // Worker build Barracks uses Produce action with Worker produce slot under existing runtime mapping.
            TryProduce(ProducibleUnit.Worker, UnitType.Worker, "Build Barracks");
        }

        public void TryProduceLight()
        {
            TryProduce(ProducibleUnit.Light, UnitType.Barracks, "Produce Light");
        }

        public void TryProduceHeavy()
        {
            TryProduce(ProducibleUnit.Heavy, UnitType.Barracks, "Produce Heavy");
        }

        public void TryProduceRanged()
        {
            TryProduce(ProducibleUnit.Ranged, UnitType.Barracks, "Produce Ranged");
        }

        private void ResolveReferences()
        {
            if (_selectionController == null)
            {
                _selectionController = FindFirstObjectByType<PlayerSelectionController>();
            }

            if (_commandCamera == null)
            {
                _commandCamera = Camera.main;
                if (_commandCamera == null)
                {
                    _commandCamera = FindFirstObjectByType<Camera>();
                }
            }

            if (_gridManager == null)
            {
                _gridManager = GridManager.Instance;
                if (_gridManager == null)
                {
                    _gridManager = FindFirstObjectByType<GridManager>();
                }
            }

            if (_unitRegistry == null)
            {
                _unitRegistry = UnitRegistry.Instance;
                if (_unitRegistry == null)
                {
                    _unitRegistry = FindFirstObjectByType<UnitRegistry>();
                }
            }

            if (_resourceManager == null)
            {
                _resourceManager = ResourceManager.Instance;
                if (_resourceManager == null)
                {
                    _resourceManager = FindFirstObjectByType<ResourceManager>();
                }
            }

            if (_matchManager == null)
            {
                _matchManager = MatchManager.Instance;
                if (_matchManager == null)
                {
                    _matchManager = FindFirstObjectByType<MatchManager>();
                }
            }

            if (_episodeController == null)
            {
                _episodeController = EpisodeController.Instance;
                if (_episodeController == null)
                {
                    _episodeController = FindFirstObjectByType<EpisodeController>();
                }
            }
        }

        private void EnsureActionApplier()
        {
            ResolveReferences();

            if (_gridManager == null || _unitRegistry == null || _matchManager == null)
            {
                return;
            }

            _actionApplier ??= new ActionApplier(_gridManager, _unitRegistry, _matchManager, _resourceManager);
        }

        private void HandleContextRightClick(GridPosition targetCell, UnitRuntime targetUnit)
        {
            if (RejectIfMultiSelectionActive())
            {
                CurrentMode = HumanCommandMode.Context;
                return;
            }

            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            if (selected == null)
            {
                SetRejected("No selected unit.");
                Debug.Log("[HumanMove3G1R] Context menu not opened reason=no selected unit");
                return;
            }

            if (targetUnit != null && targetUnit.Owner != Owner.Neutral && targetUnit.Owner != _humanSide)
            {
                TryAttackUnit(targetUnit, targetCell);
                return;
            }

            if (selected.Type == UnitType.Worker
                && _resourceManager != null
                && _resourceManager.GetResourceNode(targetCell) is ResourceNode resource)
            {
                if (resource.IsExhausted)
                {
                    SetRejected("Resource is exhausted.");
                    Debug.Log($"[HumanHarvest3G2R] Gather context rejected resourceGrid={resource.GridPosition} reason=Resource is exhausted.");
                    return;
                }

                if (OnGatherContextRequested == null)
                {
                    SetRejected("Gather context menu is unavailable.");
                    return;
                }

                OnGatherContextRequested.Invoke(resource, GetPointerScreenPosition());
                return;
            }

            if (selected.Type == UnitType.Worker
                && selected.CarriedResources > 0
                && targetUnit != null
                && targetUnit.Owner == _humanSide
                && targetUnit.Type == UnitType.Base)
            {
                TryReturnToCell(targetCell);
                return;
            }

            UnitRuntime occupant = _gridManager != null ? _gridManager.GetOccupant(targetCell) : null;
            if (occupant == null)
            {
                if (selected.IsBuilding || selected.Type == UnitType.Resource)
                {
                    SetRejected("Selected object cannot move.");
                    Debug.Log($"[HumanMove3G1R] Context menu not opened reason=selected object cannot move unit={DescribeUnit(selected)}");
                    return;
                }

                if (OnMoveContextRequested == null)
                {
                    SetRejected("Move context menu is unavailable.");
                    Debug.Log("[HumanMove3G1R] Context menu not opened reason=no OnMoveContextRequested subscriber");
                    return;
                }

                Debug.Log($"[HumanMove3G1R] Requesting context menu target={targetCell} selected={DescribeUnit(selected)} occupied=false");
                OnMoveContextRequested.Invoke(targetCell, GetPointerScreenPosition());
                return;
            }

            SetRejected("Context command is not available for this target.");
            Debug.Log($"[HumanMove3G1R] Context menu not opened reason=occupied unsupported target={DescribeUnit(occupant)}");
        }

        private void TryMoveToCell(GridPosition targetCell)
        {
            if (RejectIfMultiSelectionActive())
            {
                return;
            }

            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            if (!TryResolveDirectionFromSelection(selected, targetCell, out Direction direction, out string reason))
            {
                SetRejected(reason);
                return;
            }

            SubmitDirectionalAction(UnitActionType.Move, direction, "Move");
        }

        private void TryHarvestToCell(GridPosition targetCell)
        {
            if (RejectIfMultiSelectionActive())
            {
                return;
            }

            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            if (selected == null || selected.Type != UnitType.Worker)
            {
                SetRejected("Harvest is available only for selected Worker.");
                return;
            }

            if (_resourceManager == null || _resourceManager.GetResourceNode(targetCell) == null)
            {
                SetRejected("Target cell has no resource node.");
                return;
            }

            if (!TryResolveDirectionFromSelection(selected, targetCell, out Direction direction, out string reason))
            {
                SetRejected(reason);
                return;
            }

            SubmitDirectionalAction(UnitActionType.Harvest, direction, "Harvest");
        }

        private void TryReturnToCell(GridPosition targetCell)
        {
            if (RejectIfMultiSelectionActive())
            {
                return;
            }

            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            if (selected == null || selected.Type != UnitType.Worker)
            {
                SetRejected("Return is available only for selected Worker.");
                return;
            }

            if (selected.CarriedResources <= 0)
            {
                SetRejected("Selected Worker carries no resources.");
                return;
            }

            UnitRuntime target = _gridManager != null ? _gridManager.GetOccupant(targetCell) : null;
            if (target == null || target.Type != UnitType.Base || target.Owner != _humanSide)
            {
                SetRejected("Return target must be adjacent friendly Base.");
                return;
            }

            if (!TryResolveDirectionFromSelection(selected, targetCell, out Direction direction, out string reason))
            {
                SetRejected(reason);
                return;
            }

            SubmitDirectionalAction(UnitActionType.Return, direction, "Return");
        }

        private void TryAttackUnit(UnitRuntime targetUnit, GridPosition targetCell)
        {
            if (RejectIfMultiSelectionActive())
            {
                return;
            }

            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            if (selected == null)
            {
                SetRejected("No selected unit.");
                return;
            }

            if (targetUnit == null)
            {
                SetRejected("No attack target under pointer.");
                return;
            }

            if (targetUnit.Owner == _humanSide || targetUnit.Owner == Owner.Neutral)
            {
                SetRejected("Attack target must be enemy unit.");
                return;
            }

            AgentAction action = new AgentAction(
                actorPosition: selected.GridPos,
                actionType: UnitActionType.Attack,
                direction: Direction.North,
                produceUnitType: ProducibleUnit.Worker,
                attackTargetPosition: targetCell,
                isValid: true,
                invalidationReason: string.Empty,
                sourceType: ActionSourceType.Debug);

            SubmitAgentAction(action, "Attack");
        }

        private bool TryResolveDirectionFromSelection(UnitRuntime selected, GridPosition targetCell, out Direction direction, out string reason)
        {
            direction = Direction.North;
            reason = string.Empty;

            if (selected == null)
            {
                reason = "No selected unit.";
                return false;
            }

            int deltaX = targetCell.X - selected.GridPos.X;
            int deltaY = targetCell.Y - selected.GridPos.Y;
            int manhattan = Mathf.Abs(deltaX) + Mathf.Abs(deltaY);

            if (manhattan != 1)
            {
                reason = "Target is not adjacent; command not submitted.";
                return false;
            }

            if (deltaX == 1 && deltaY == 0)
            {
                direction = Direction.East;
                return true;
            }

            if (deltaX == -1 && deltaY == 0)
            {
                direction = Direction.West;
                return true;
            }

            if (deltaX == 0 && deltaY == 1)
            {
                direction = Direction.North;
                return true;
            }

            if (deltaX == 0 && deltaY == -1)
            {
                direction = Direction.South;
                return true;
            }

            reason = "Target is not orthogonally adjacent; command not submitted.";
            return false;
        }

        private void SubmitDirectionalAction(UnitActionType actionType, Direction direction, string title)
        {
            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            if (selected == null)
            {
                SetRejected("No selected unit.");
                return;
            }

            AgentAction action = new AgentAction(
                actorPosition: selected.GridPos,
                actionType: actionType,
                direction: direction,
                produceUnitType: ProducibleUnit.Worker,
                attackTargetPosition: default,
                isValid: true,
                invalidationReason: string.Empty,
                sourceType: ActionSourceType.Debug);

            SubmitAgentAction(action, title);
        }

        private bool SubmitWorkerDirectionalAction(UnitRuntime worker, UnitActionType actionType, Direction direction, string title)
        {
            if (worker == null)
            {
                SetRejected($"{title} worker is missing.");
                return false;
            }

            if (_humanSide != Owner.Player2 || worker.Owner != Owner.Player2 || worker.Type != UnitType.Worker)
            {
                SetRejected($"{title} requires a Player2 Worker.");
                return false;
            }

            AgentAction action = new AgentAction(
                actorPosition: worker.GridPos,
                actionType: actionType,
                direction: direction,
                produceUnitType: ProducibleUnit.Worker,
                attackTargetPosition: default,
                isValid: true,
                invalidationReason: string.Empty,
                sourceType: ActionSourceType.Debug);

            bool accepted = SubmitAgentAction(action, title);
            Debug.Log($"[HumanHarvest3G2] {title} accepted={accepted} worker={DescribeUnit(worker)} direction={direction} reason={LastCommandRejectedReason}");
            return accepted;
        }

        private void TryProduce(ProducibleUnit produceType, UnitType requiredProducer, string title)
        {
            if (RejectIfMultiSelectionActive())
            {
                return;
            }

            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            if (selected == null)
            {
                SetRejected("No selected producer.");
                return;
            }

            if (selected.Type != requiredProducer)
            {
                SetRejected($"{title} requires selected {requiredProducer}.");
                return;
            }

            if (!TryFindFirstFreeAdjacentDirection(selected.GridPos, out Direction direction))
            {
                SetRejected("No adjacent free cell for produce command.");
                return;
            }

            AgentAction action = new AgentAction(
                actorPosition: selected.GridPos,
                actionType: UnitActionType.Produce,
                direction: direction,
                produceUnitType: produceType,
                attackTargetPosition: default,
                isValid: true,
                invalidationReason: string.Empty,
                sourceType: ActionSourceType.Debug);

            SubmitAgentAction(action, title);
        }

        private bool TryFindFirstFreeAdjacentDirection(GridPosition actorPos, out Direction direction)
        {
            foreach (Direction candidate in Enum.GetValues(typeof(Direction)))
            {
                GridPosition target = actorPos.Neighbour(candidate);
                if (_gridManager == null || !_gridManager.IsInside(target))
                {
                    continue;
                }

                if (_gridManager.GetOccupant(target) == null)
                {
                    direction = candidate;
                    return true;
                }
            }

            direction = Direction.North;
            return false;
        }

        private bool TryResolvePointerTarget(out GridPosition targetCell, out UnitRuntime targetUnit, out bool hitAny)
        {
            targetCell = default;
            targetUnit = null;
            hitAny = false;

            ResolveReferences();
            if (_commandCamera == null || _gridManager == null)
            {
                return false;
            }

            if (!TryGetPointerRay(out Ray ray))
            {
                return false;
            }

            if (Physics.Raycast(ray, out RaycastHit hit, _raycastDistance, _raycastMask, QueryTriggerInteraction.Ignore))
            {
                hitAny = true;
                targetUnit = hit.collider != null ? hit.collider.GetComponentInParent<UnitRuntime>() : null;
                targetCell = _gridManager.WorldToCell(hit.point);
                if (targetUnit != null)
                {
                    targetCell = targetUnit.GridPos;
                }

                Debug.Log($"[HumanMove3G1R] Pointer raycast world={hit.point} resolvedCell={targetCell} occupied={targetUnit != null}");
                return _gridManager.IsInside(targetCell);
            }

            if (TryResolveWorldPointOnGround(ray, out Vector3 worldPoint))
            {
                hitAny = true;
                targetCell = _gridManager.WorldToCell(worldPoint);
                if (!_gridManager.IsInside(targetCell))
                {
                    return false;
                }

                targetUnit = _gridManager.GetOccupant(targetCell);
                Debug.Log($"[HumanMove3G1R] Pointer ground world={worldPoint} resolvedCell={targetCell} occupied={targetUnit != null}");
                return true;
            }

            return false;
        }

        private bool TryGetPointerRay(out Ray ray)
        {
            ray = default;
            if (_commandCamera == null)
            {
                return false;
            }

#if ENABLE_INPUT_SYSTEM
            Mouse mouse = Mouse.current;
            if (mouse != null)
            {
                Vector2 pointer = mouse.position.ReadValue();
                ray = _commandCamera.ScreenPointToRay(pointer);
                return true;
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER
            if (_legacyInputUnavailable)
            {
                return false;
            }

            try
            {
                ray = _commandCamera.ScreenPointToRay(Input.mousePosition);
                return true;
            }
            catch (InvalidOperationException)
            {
                _legacyInputUnavailable = true;
                return false;
            }
#else
            return false;
#endif
        }

        private static bool TryResolveWorldPointOnGround(Ray ray, out Vector3 worldPoint)
        {
            Plane ground = new Plane(Vector3.up, Vector3.zero);
            if (ground.Raycast(ray, out float distance))
            {
                worldPoint = ray.GetPoint(distance);
                return true;
            }

            worldPoint = default;
            return false;
        }

        private bool IsRightClickPressed()
        {
#if ENABLE_INPUT_SYSTEM
            Mouse mouse = Mouse.current;
            if (mouse != null)
            {
                return mouse.rightButton.wasPressedThisFrame;
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER
            if (_legacyInputUnavailable)
            {
                return false;
            }

            try
            {
                return Input.GetMouseButtonDown(1);
            }
            catch (InvalidOperationException)
            {
                _legacyInputUnavailable = true;
                return false;
            }
#else
            return false;
#endif
        }

        private bool SubmitAgentAction(AgentAction action, string title)
        {
            EnsureActionApplier();
            if (_actionApplier == null)
            {
                SetRejected("ActionApplier is unavailable; command not submitted.");
                return false;
            }

            if (_matchManager == null || _matchManager.Phase != MatchPhase.Running)
            {
                SetRejected("Match is not running; command not submitted.");
                return false;
            }

            _actionApplier.ResetDiagnostics();
            bool accepted;
            using (HumanPlayCommandSourceDiagnostics.PushSource("Human/PlayerCommandController"))
            {
                accepted = _actionApplier.ApplyAction(action, _humanSide);
            }

            if (accepted)
            {
                SetAccepted($"{title} command accepted.");
                return true;
            }

            string reason = string.Empty;
            InvalidActionAttemptLog? invalidAttempt = _actionApplier.LastInvalidAttempt;
            if (invalidAttempt.HasValue)
            {
                reason = invalidAttempt.Value.RejectionReason;
            }

            if (string.IsNullOrWhiteSpace(reason) && _actionApplier.RejectionReasonsLastStep.Count > 0)
            {
                reason = _actionApplier.RejectionReasonsLastStep[0];
            }

            if (string.IsNullOrWhiteSpace(reason))
            {
                reason = "Command rejected by runtime validation.";
            }

            SetRejected(reason);
            return false;
        }

        private static Vector2 GetPointerScreenPosition()
        {
#if ENABLE_INPUT_SYSTEM
            Mouse mouse = Mouse.current;
            if (mouse != null)
            {
                return mouse.position.ReadValue();
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER
            return Input.mousePosition;
#else
            return Vector2.zero;
#endif
        }

        private static string DescribeUnit(UnitRuntime unit)
        {
            return unit == null
                ? "<null>"
                : $"{unit.name} owner={unit.Owner} type={unit.Type} grid={unit.GridPos}";
        }

        private void SetAccepted(string message)
        {
            SetStatus(message, true, string.Empty);
        }

        private void SetRejected(string reason)
        {
            SetStatus(reason, false, reason);
        }

        private bool RejectIfMultiSelectionActive()
        {
            if (_selectionController == null || !_selectionController.HasMultiSelection)
            {
                return false;
            }

            SetRejected("Group commands require pathfinding/formation; use single selection.");
            return true;
        }

        private void SetStatus(string message, bool accepted, string rejectedReason)
        {
            LastCommandStatus = message;
            LastCommandAccepted = accepted;
            LastCommandRejectedReason = rejectedReason ?? string.Empty;

            if (_logCommandDiagnostics)
            {
                string tag = accepted ? "accepted" : "rejected";
                Debug.Log($"[PlayerCommandController] {tag}: {message}");
            }

            OnCommandStatusChanged?.Invoke(LastCommandStatus, LastCommandAccepted);
        }
    }
}
