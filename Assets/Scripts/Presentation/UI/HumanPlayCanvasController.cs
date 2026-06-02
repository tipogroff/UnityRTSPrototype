using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using RTS.Presentation;
using RTS.Presentation.Orders;
using RTS.Presentation.Selection;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.UI;
#endif

namespace RTS.Presentation.UI
{
    [DisallowMultipleComponent]
    public sealed class HumanPlayCanvasController : MonoBehaviour
    {
        [Header("Sprites")]
        [SerializeField] private Sprite _panelSprite;
        [SerializeField] private Sprite _buttonSprite;
        [SerializeField] private Sprite _buttonPressedSprite;
        [SerializeField] private Sprite _pauseIcon;
        [SerializeField] private Sprite _gearIcon;
        [SerializeField] private Sprite _homeIcon;
        [SerializeField] private Sprite _targetIcon;

        [Header("Refresh")]
        [SerializeField] private float _refreshInterval = 0.2f;

        [Header("Attack Targeting")]
        [SerializeField, Min(0)] private int _attackClickAcquireRadius = 3;
        [SerializeField, Min(0)] private int _attackAreaRadius = 4;

        [Header("Colors")]
        [SerializeField] private Color _panelColor = new Color(0.08f, 0.09f, 0.08f, 0.88f);
        [SerializeField] private Color _buttonColor = new Color(0.78f, 0.67f, 0.48f, 1f);
        [SerializeField] private Color _textColor = new Color(0.96f, 0.92f, 0.82f, 1f);

        private Canvas _canvas;
        private RectTransform _hudRoot;
        private RectTransform _bottomRoot;
        private RectTransform _pauseMenu;
        private RectTransform _settingsPanel;
        private TopResourceBarView _topResourceBar;
        private SelectionInfoPanelView _selectionInfo;
        private CommandPanelView _commandPanel;
        private ProductionPanelView _productionPanel;
        private MetricsPanelView _metricsPanel;
        private SelectionBoxView _selectionBoxView;
        private PanelVisibilityController _hudVisibility;
        private PanelVisibilityController _metricsVisibility;
        private PanelVisibilityController _selectionVisibility;
        private PanelVisibilityController _productionVisibility;
        private HumanPlayModeController _modeController;
        private HumanPlayerController _humanPlayerController;
        private PlayerSelectionController _selectionController;
        private SelectionManager _selectionManager;
        private PlayerCommandController _commandController;
        private GridPathfindingService _pathfindingService;
        private HumanOrderController _orderController;
        private AttackTargetAcquisitionService _attackTargets;
        private GroupOrderPlanner _groupPlanner;
        private GroupOrderReservationService _reservations;
        private ResourceManager _resourceManager;
        private GridManager _gridManager;
        private Camera _commandCamera;
        private ResourceVisualStateController _resourceVisualStateController;
        private ContextActionMenuView _contextMenu;
        private GameSpeedController _speedController;
        private SceneFlowController _sceneFlowController;
        private MatchManager _matchManager;
        private Button _stopButton;
        private Text _gridSettingValue;
        private Text _unitMarkersSettingValue;
        private Text _controlHintsSettingValue;
        private Text _graphicsQualitySettingValue;
        private Text _cameraHeightSettingValue;
        private Text _interfaceScaleSettingValue;
        private Text _settingsStatus;
        private bool _hasObservedManualUiMode;
        private bool _wasPlayer2ManualMode;
        private float _nextRefresh;
        private ResourceNode _hoveredResource;

        public bool IsCameraInputBlocked =>
            (_pauseMenu != null && _pauseMenu.gameObject.activeSelf)
            || (_settingsPanel != null && _settingsPanel.gameObject.activeSelf)
            || (_contextMenu != null && _contextMenu.IsOpen);

        private void Awake()
        {
            ResolveReferences();
            EnsureEventSystem();
            BuildHud();
            Refresh(force: true);
        }

        private void OnDestroy()
        {
            if (_commandController != null)
            {
                _commandController.OnMoveContextRequested -= HandleMoveContextRequested;
                _commandController.OnGatherContextRequested -= HandleGatherContextRequested;
                _commandController.OnAttackContextRequested -= HandleAttackContextRequested;
                _commandController.OnAttackAreaContextRequested -= HandleAttackAreaContextRequested;
            }
        }

        private void Update()
        {
            ResolveReferences();
            HandleHotkeys();

            if (Time.unscaledTime >= _nextRefresh)
            {
                Refresh(force: false);
                _nextRefresh = Time.unscaledTime + Mathf.Max(0.05f, _refreshInterval);
            }
        }

        public void TogglePauseMenu()
        {
            bool next = _pauseMenu == null || !_pauseMenu.gameObject.activeSelf;
            SetPauseMenuVisible(next);
        }

        public void SetPauseMenuVisible(bool visible)
        {
            if (_pauseMenu != null)
            {
                _pauseMenu.gameObject.SetActive(visible);
            }

            if (visible)
            {
                _speedController?.Pause();
            }
            else if (_speedController != null && _speedController.IsPaused)
            {
                _speedController.Resume();
            }

            if (!visible)
            {
                HideHudSettings();
            }
        }

        public void Continue()
        {
            SetPauseMenuVisible(false);
        }

        public void RestartMatch()
        {
            Time.timeScale = 1f;
            if (_modeController != null)
            {
                _modeController.RestartMatch();
            }
            else
            {
                _sceneFlowController?.RestartCurrentScene();
            }

            SetPauseMenuVisible(false);
        }

        public void ReturnToMainMenu()
        {
            Time.timeScale = 1f;
            if (_sceneFlowController != null)
            {
                _sceneFlowController.LoadMainMenu();
            }
            else
            {
                Debug.LogWarning("[HumanPlayCanvasController] SceneFlowController missing; cannot return to main menu.");
            }
        }

        public void Quit()
        {
            _sceneFlowController?.Quit();
        }

        private void BuildHud()
        {
            _canvas = GetComponent<Canvas>();
            if (_canvas == null)
            {
                _canvas = gameObject.AddComponent<Canvas>();
            }

            _canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            _canvas.sortingOrder = 10;

            CanvasScaler scaler = GetComponent<CanvasScaler>() ?? gameObject.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            scaler.matchWidthOrHeight = 0.5f;

            if (GetComponent<GraphicRaycaster>() == null)
            {
                gameObject.AddComponent<GraphicRaycaster>();
            }

            _hudRoot = CreateRect("HUDRoot", transform);
            Stretch(_hudRoot, Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);
            _hudVisibility = gameObject.AddComponent<PanelVisibilityController>();
            _hudVisibility.Initialize(_hudRoot.gameObject, true);

            BuildSelectionBoxOverlay();
            BuildContextMenu();
            BuildTopBar(_hudRoot);
            BuildBottomPanels(_hudRoot);
            BuildMetricsPanel(_hudRoot);
            BuildPauseMenu(transform as RectTransform ?? GetComponent<RectTransform>());
            BuildSettingsPanel(transform as RectTransform ?? GetComponent<RectTransform>());
        }

        private void BuildTopBar(RectTransform parent)
        {
            RectTransform bar = CreatePanel("TopResourceBar", parent, new Vector2(0f, 58f));
            bar.anchorMin = new Vector2(0f, 1f);
            bar.anchorMax = new Vector2(1f, 1f);
            bar.offsetMin = new Vector2(16f, -72f);
            bar.offsetMax = new Vector2(-16f, -14f);

            HorizontalLayoutGroup layout = bar.gameObject.AddComponent<HorizontalLayoutGroup>();
            layout.padding = new RectOffset(14, 14, 8, 8);
            layout.spacing = 14f;
            layout.childControlWidth = true;
            layout.childControlHeight = true;
            layout.childForceExpandWidth = false;

            Text p1 = CreateLabel("P1", bar, 18, FontStyle.Bold, TextAnchor.MiddleLeft);
            AddLayout(p1.gameObject, 180f, -1f);
            Text p2 = CreateLabel("P2", bar, 18, FontStyle.Bold, TextAnchor.MiddleLeft);
            AddLayout(p2.gameObject, 200f, -1f);
            Text phase = CreateLabel("Phase", bar, 18, FontStyle.Normal, TextAnchor.MiddleLeft);
            AddLayout(phase.gameObject, 210f, -1f);
            Text step = CreateLabel("Step", bar, 18, FontStyle.Normal, TextAnchor.MiddleLeft);
            AddLayout(step.gameObject, 260f, -1f);

            GameObject spacer = new GameObject("Spacer", typeof(RectTransform), typeof(LayoutElement));
            spacer.transform.SetParent(bar, false);
            spacer.GetComponent<LayoutElement>().flexibleWidth = 1f;

            Button start = CreateButton("StartAIvsPlayer2Button", bar, "Start AI vs P2", _targetIcon, () => _modeController?.StartAIvsPlayer2());
            AddLayout(start.gameObject, 190f, 42f);
            Button pause = CreateButton("PauseButton", bar, "Menu", _pauseIcon, TogglePauseMenu);
            AddLayout(pause.gameObject, 120f, 42f);

            _topResourceBar = bar.gameObject.AddComponent<TopResourceBarView>();
            _topResourceBar.Initialize(p1, p2, phase, step);
        }

        private void BuildBottomPanels(RectTransform parent)
        {
            _bottomRoot = CreateRect("BottomCommandPanel", parent);
            _bottomRoot.anchorMin = new Vector2(0f, 0f);
            _bottomRoot.anchorMax = new Vector2(1f, 0f);
            _bottomRoot.offsetMin = new Vector2(16f, 16f);
            _bottomRoot.offsetMax = new Vector2(-16f, 244f);

            HorizontalLayoutGroup layout = _bottomRoot.gameObject.AddComponent<HorizontalLayoutGroup>();
            layout.spacing = 12f;
            layout.childControlHeight = true;
            layout.childForceExpandHeight = true;

            RectTransform selection = CreatePanel("SelectionInfoPanel", _bottomRoot, new Vector2(300f, 0f));
            AddLayout(selection.gameObject, 320f, -1f);
            Text selectionTitle = CreateHeader(selection, "Selection");
            Text selectionBody = CreateBody(selection, "No unit selected");
            _selectionInfo = selection.gameObject.AddComponent<SelectionInfoPanelView>();
            _selectionInfo.Initialize(selectionTitle, selectionBody);
            _selectionVisibility = selection.gameObject.AddComponent<PanelVisibilityController>();
            _selectionVisibility.Initialize(selection.gameObject, true);

            RectTransform commands = CreatePanel("CommandPanel", _bottomRoot, new Vector2(610f, 0f));
            AddLayout(commands.gameObject, 650f, -1f);
            CreateHeader(commands, "Commands");
            BuildCommandButtons(commands);
            Text commandStatus = CreateBody(commands, "No command submitted.");
            SetRect(commandStatus.rectTransform, new Vector2(0f, 0f), new Vector2(1f, 0f), new Vector2(0f, 44f), new Vector2(-24f, 70f));
            _commandPanel = commands.gameObject.AddComponent<CommandPanelView>();
            _commandPanel.Initialize(commandStatus, _commandController, _orderController);

            RectTransform production = CreatePanel("ProductionPanel", _bottomRoot, new Vector2(360f, 0f));
            AddLayout(production.gameObject, 380f, -1f);
            Text productionTitle = CreateHeader(production, "Production");
            GameObject baseGroup = CreateButtonRow(production, "BaseGroup", 88f);
            Button worker = CreateButton("WorkerButton", baseGroup.transform as RectTransform, "Worker", null, () => _commandController?.TryProduceWorker());
            AddLayout(worker.gameObject, 160f, 44f);
            GameObject barracksGroup = CreateButtonRow(production, "BarracksGroup", 88f);
            Button light = CreateButton("LightButton", barracksGroup.transform as RectTransform, "Light", null, () => _commandController?.TryProduceLight());
            Button heavy = CreateButton("HeavyButton", barracksGroup.transform as RectTransform, "Heavy", null, () => _commandController?.TryProduceHeavy());
            Button ranged = CreateButton("RangedButton", barracksGroup.transform as RectTransform, "Ranged", null, () => _commandController?.TryProduceRanged());
            AddLayout(light.gameObject, 105f, 44f);
            AddLayout(heavy.gameObject, 110f, 44f);
            AddLayout(ranged.gameObject, 120f, 44f);
            Text productionStatus = CreateBody(production, string.Empty);
            SetRect(productionStatus.rectTransform, new Vector2(0f, 0f), new Vector2(1f, 0f), new Vector2(0f, 12f), new Vector2(-24f, 92f));
            _productionPanel = production.gameObject.AddComponent<ProductionPanelView>();
            _productionPanel.Initialize(productionTitle, baseGroup, barracksGroup, productionStatus, worker, light, heavy, ranged);
            _productionVisibility = production.gameObject.AddComponent<PanelVisibilityController>();
            _productionVisibility.Initialize(production.gameObject, true);
        }

        private void BuildCommandButtons(RectTransform commands)
        {
            GameObject row2 = CreateButtonRow(commands, "Row2", 58f);
            _stopButton = CreateButton("StopButton", row2.transform as RectTransform, "Stop", null, CancelPrimaryOrder);
            AddLayout(_stopButton.gameObject, 90f, 42f);
            AddLayout(CreateButton("RestartButton", row2.transform as RectTransform, "Restart", null, RestartMatch).gameObject, 120f, 42f);
            AddLayout(CreateButton("MainMenuButton", row2.transform as RectTransform, "Main Menu", _homeIcon, ReturnToMainMenu).gameObject, 150f, 42f);
        }

        private void BuildContextMenu()
        {
            RectTransform overlay = CreateRect("ContextActionMenu", transform);
            _contextMenu = overlay.gameObject.AddComponent<ContextActionMenuView>();
            _contextMenu.Initialize(_canvas, _panelSprite, _buttonSprite, _panelColor, _buttonColor);
        }

        private void BuildSelectionBoxOverlay()
        {
            RectTransform overlay = CreateRect("SelectionBoxOverlay", transform);
            Stretch(overlay, Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);
            _selectionBoxView = overlay.gameObject.AddComponent<SelectionBoxView>();
            _selectionBoxView.Initialize(overlay);
            if (_selectionManager != null)
            {
                _selectionManager.SetSelectionBoxView(_selectionBoxView);
            }
        }

        private void BuildMetricsPanel(RectTransform parent)
        {
            RectTransform panel = CreatePanel("MetricsPanel", parent, new Vector2(420f, 210f));
            panel.anchorMin = new Vector2(1f, 1f);
            panel.anchorMax = new Vector2(1f, 1f);
            panel.anchoredPosition = new Vector2(-226f, -198f);
            CreateHeader(panel, "Metrics");
            Text body = CreateBody(panel, string.Empty);
            _metricsPanel = panel.gameObject.AddComponent<MetricsPanelView>();
            _metricsPanel.Initialize(body);
            _metricsVisibility = panel.gameObject.AddComponent<PanelVisibilityController>();
            _metricsVisibility.Initialize(panel.gameObject, false);
        }

        private void BuildPauseMenu(RectTransform root)
        {
            _pauseMenu = CreatePanel("PauseMenu", root, new Vector2(420f, 500f));
            _pauseMenu.anchorMin = new Vector2(0.5f, 0.5f);
            _pauseMenu.anchorMax = new Vector2(0.5f, 0.5f);
            _pauseMenu.anchoredPosition = Vector2.zero;
            _pauseMenu.gameObject.SetActive(false);

            CreateHeader(_pauseMenu, "Paused");
            CreateVerticalButton(_pauseMenu, "Continue", 96f, Continue);
            CreateVerticalButton(_pauseMenu, "Restart Match", 154f, RestartMatch);
            CreateVerticalButton(_pauseMenu, "Settings", 212f, ShowHudSettings, _gearIcon);
            CreateVerticalButton(_pauseMenu, "Toggle Metrics", 270f, () => _metricsVisibility?.Toggle());
            CreateVerticalButton(_pauseMenu, "Main Menu", 328f, ReturnToMainMenu, _homeIcon);
            CreateVerticalButton(_pauseMenu, "Quit", 386f, Quit);
        }

        private void BuildSettingsPanel(RectTransform root)
        {
            _settingsPanel = CreatePanel("HudSettingsPanel", root, new Vector2(700f, 560f));
            _settingsPanel.anchorMin = new Vector2(0.5f, 0.5f);
            _settingsPanel.anchorMax = new Vector2(0.5f, 0.5f);
            _settingsPanel.anchoredPosition = new Vector2(0f, 20f);
            _settingsPanel.gameObject.SetActive(false);
            CreateHeader(_settingsPanel, "\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438");

            _gridSettingValue = CreateHudSettingsRow("GridRow", "\u041f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0442\u044c \u0441\u0435\u0442\u043a\u0443", 84f, DemoVisualSettings.ToggleGrid);
            _unitMarkersSettingValue = CreateHudSettingsRow("UnitMarkersRow", "\u041f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0442\u044c \u043c\u0430\u0440\u043a\u0435\u0440\u044b \u044e\u043d\u0438\u0442\u043e\u0432", 132f, DemoVisualSettings.ToggleUnitMarkers);
            _controlHintsSettingValue = CreateHudSettingsRow("ControlHintsRow", "\u041f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0442\u044c \u043f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0438 \u0443\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u044f", 180f, DemoVisualSettings.ToggleControlHints);
            _graphicsQualitySettingValue = CreateHudSettingsRow("GraphicsQualityRow", "\u041a\u0430\u0447\u0435\u0441\u0442\u0432\u043e \u0433\u0440\u0430\u0444\u0438\u043a\u0438", 228f, DemoVisualSettings.CycleGraphicsQuality);
            _cameraHeightSettingValue = CreateHudSettingsRow("CameraHeightRow", "\u0412\u044b\u0441\u043e\u0442\u0430 \u043a\u0430\u043c\u0435\u0440\u044b", 276f, DemoVisualSettings.CycleCameraHeight);
            _interfaceScaleSettingValue = CreateHudSettingsRow("InterfaceScaleRow", "\u041c\u0430\u0441\u0448\u0442\u0430\u0431 \u0438\u043d\u0442\u0435\u0440\u0444\u0435\u0439\u0441\u0430", 324f, DemoVisualSettings.CycleInterfaceScale);

            _settingsStatus = CreateLabel("SettingsStatus", _settingsPanel, 18, FontStyle.Bold, TextAnchor.MiddleCenter);
            SetRect(_settingsStatus.rectTransform, new Vector2(0.5f, 1f), new Vector2(0.5f, 1f), new Vector2(0f, -374f), new Vector2(620f, 32f));
            CreateVerticalButton(_settingsPanel, "\u041f\u0440\u0438\u043c\u0435\u043d\u0438\u0442\u044c", 426f, ApplyHudSettings);
            CreateVerticalButton(_settingsPanel, "\u041d\u0430\u0437\u0430\u0434", 484f, HideHudSettings);
            RefreshHudSettingsLabels();
        }

        private Text CreateHudSettingsRow(string name, string label, float yFromTop, System.Action update)
        {
            RectTransform row = CreateRect(name, _settingsPanel);
            SetRect(row, new Vector2(0f, 1f), new Vector2(1f, 1f), new Vector2(20f, -yFromTop), new Vector2(-40f, 44f));
            Text settingLabel = CreateLabel("Label", row, 18, FontStyle.Normal, TextAnchor.MiddleLeft);
            settingLabel.text = label;
            SetRect(settingLabel.rectTransform, new Vector2(0f, 0.5f), new Vector2(0f, 0.5f), new Vector2(230f, 0f), new Vector2(440f, 38f));
            Button valueButton = CreateButton("ValueButton", row, string.Empty, null, () =>
            {
                update?.Invoke();
                RefreshHudSettingsLabels();
                _settingsStatus.text = string.Empty;
            });
            SetRect(valueButton.transform as RectTransform, new Vector2(1f, 0.5f), new Vector2(1f, 0.5f), new Vector2(-108f, 0f), new Vector2(190f, 42f));
            return valueButton.GetComponentInChildren<Text>();
        }

        private void ShowHudSettings()
        {
            if (_settingsPanel == null)
            {
                return;
            }

            RefreshHudSettingsLabels();
            _settingsStatus.text = string.Empty;
            _settingsPanel.gameObject.SetActive(true);
        }

        private void HideHudSettings()
        {
            _settingsPanel?.gameObject.SetActive(false);
        }

        private void ApplyHudSettings()
        {
            if (_settingsStatus != null)
            {
                _settingsStatus.text = "\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438 \u043f\u0440\u0438\u043c\u0435\u043d\u0435\u043d\u044b";
            }
        }

        private void RefreshHudSettingsLabels()
        {
            SetText(_gridSettingValue, DemoVisualSettings.FormatToggle(DemoVisualSettings.ShowGrid));
            SetText(_unitMarkersSettingValue, DemoVisualSettings.FormatToggle(DemoVisualSettings.ShowUnitMarkers));
            SetText(_controlHintsSettingValue, DemoVisualSettings.FormatToggle(DemoVisualSettings.ShowControlHints));
            SetText(_graphicsQualitySettingValue, DemoVisualSettings.GraphicsQuality.ToString());
            SetText(_cameraHeightSettingValue, DemoVisualSettings.CameraHeight.ToString());
            SetText(_interfaceScaleSettingValue, DemoVisualSettings.InterfaceScale.ToString());
        }

        private void Refresh(bool force)
        {
            UnitRuntime selected = _selectionManager != null
                ? _selectionManager.PrimarySelectedUnit
                : _selectionController != null ? _selectionController.SelectedUnit : null;
            IReadOnlyList<UnitRuntime> selectedUnits = _selectionManager != null
                ? _selectionManager.SelectedUnits
                : _selectionController != null ? _selectionController.SelectedUnits : null;
            int selectionCount = selectedUnits != null ? selectedUnits.Count : (selected != null ? 1 : 0);
            bool hasPlayer2ManualMode = HasPlayer2ManualMode();
            _topResourceBar?.Refresh(_matchManager);
            UpdateHoveredResource();
            _selectionInfo?.Refresh(selectedUnits, selected);
            _commandPanel?.Refresh(_commandController, selectedUnits, selected, _hoveredResource, _modeController, _humanPlayerController);
            if (hasPlayer2ManualMode)
            {
                _productionPanel?.Refresh(selected, selectionCount, _commandController);
            }

            if (!_hasObservedManualUiMode || _wasPlayer2ManualMode != hasPlayer2ManualMode)
            {
                _selectionVisibility?.SetVisible(hasPlayer2ManualMode);
                _wasPlayer2ManualMode = hasPlayer2ManualMode;
                _hasObservedManualUiMode = true;
            }

            _productionVisibility?.SetVisible(hasPlayer2ManualMode && _productionPanel != null && _productionPanel.gameObject.activeSelf);
            if (!hasPlayer2ManualMode)
            {
                _contextMenu?.Hide();
            }

            _metricsPanel?.Refresh(_modeController, _humanPlayerController, _commandController, _speedController);
            if (_stopButton != null)
            {
                _stopButton.interactable = hasPlayer2ManualMode
                    && _humanPlayerController != null
                    && _humanPlayerController.IsHumanControlActive
                    && selectionCount > 0;
            }
        }

        private void HandleHotkeys()
        {
            if (IsUiFieldFocused())
            {
                return;
            }

            if (WasKeyPressed(KeyCode.Escape))
            {
                if (_settingsPanel != null && _settingsPanel.gameObject.activeSelf)
                {
                    HideHudSettings();
                    return;
                }

                if (_contextMenu != null && _contextMenu.IsOpen)
                {
                    _contextMenu.Hide();
                    return;
                }

                TogglePauseMenu();
            }

            if (WasKeyPressed(KeyCode.F1))
            {
                _hudVisibility?.Toggle();
            }

            if (WasKeyPressed(KeyCode.F2))
            {
                _metricsVisibility?.Toggle();
            }

            if (WasKeyPressed(KeyCode.F3))
            {
                if (HasPlayer2ManualMode())
                {
                    _selectionVisibility?.Toggle();
                }
            }

            if (WasKeyPressed(KeyCode.F4))
            {
                if (HasPlayer2ManualMode())
                {
                    _productionVisibility?.Toggle();
                }
            }
        }

        private bool HasPlayer2ManualMode()
        {
            return _modeController != null
                && _modeController.CurrentMode == HumanPlayMode.AIvsPlayer2
                && _modeController.HasHumanSide
                && _modeController.HumanSide == Owner.Player2;
        }

        private void ResolveReferences()
        {
            _modeController ??= FindFirstObjectByType<HumanPlayModeController>();
            _humanPlayerController ??= FindFirstObjectByType<HumanPlayerController>();
            _selectionController ??= FindFirstObjectByType<PlayerSelectionController>();
            _selectionManager ??= FindFirstObjectByType<SelectionManager>();
            if (_selectionManager != null && _selectionBoxView != null)
            {
                _selectionManager.SetSelectionBoxView(_selectionBoxView);
            }

            _commandController ??= FindFirstObjectByType<PlayerCommandController>();
            _attackTargets ??= FindFirstObjectByType<AttackTargetAcquisitionService>();
            if (_attackTargets == null)
            {
                _attackTargets = gameObject.AddComponent<AttackTargetAcquisitionService>();
            }

            _pathfindingService ??= FindFirstObjectByType<GridPathfindingService>();
            if (_pathfindingService == null)
            {
                _pathfindingService = gameObject.AddComponent<GridPathfindingService>();
            }

            _groupPlanner ??= FindFirstObjectByType<GroupOrderPlanner>();
            if (_groupPlanner == null)
            {
                _groupPlanner = gameObject.AddComponent<GroupOrderPlanner>();
            }

            _reservations ??= FindFirstObjectByType<GroupOrderReservationService>();
            if (_reservations == null)
            {
                _reservations = gameObject.AddComponent<GroupOrderReservationService>();
            }

            _resourceManager ??= ResourceManager.Instance != null ? ResourceManager.Instance : FindFirstObjectByType<ResourceManager>();
            _gridManager ??= GridManager.Instance != null ? GridManager.Instance : FindFirstObjectByType<GridManager>();
            _commandCamera ??= Camera.main != null ? Camera.main : FindFirstObjectByType<Camera>();
            _resourceVisualStateController ??= FindFirstObjectByType<ResourceVisualStateController>();
            if (_resourceVisualStateController == null)
            {
                _resourceVisualStateController = gameObject.AddComponent<ResourceVisualStateController>();
            }

            _orderController ??= FindFirstObjectByType<HumanOrderController>();
            if (_orderController == null)
            {
                _orderController = gameObject.AddComponent<HumanOrderController>();
            }

            _speedController ??= FindFirstObjectByType<GameSpeedController>();
            _sceneFlowController ??= FindFirstObjectByType<SceneFlowController>();
            _matchManager ??= MatchManager.Instance != null ? MatchManager.Instance : FindFirstObjectByType<MatchManager>();
            _orderController.Configure(_pathfindingService, _commandController, _selectionController, _matchManager);
            if (_commandController != null)
            {
                _commandController.OnMoveContextRequested -= HandleMoveContextRequested;
                _commandController.OnMoveContextRequested += HandleMoveContextRequested;
                _commandController.OnGatherContextRequested -= HandleGatherContextRequested;
                _commandController.OnGatherContextRequested += HandleGatherContextRequested;
                _commandController.OnAttackContextRequested -= HandleAttackContextRequested;
                _commandController.OnAttackContextRequested += HandleAttackContextRequested;
                _commandController.OnAttackAreaContextRequested -= HandleAttackAreaContextRequested;
                _commandController.OnAttackAreaContextRequested += HandleAttackAreaContextRequested;
                _commandController.SetAttackAcquireRadii(_attackClickAcquireRadius, _attackAreaRadius);
            }
        }

        private void HandleMoveContextRequested(GridPosition targetCell, Vector2 screenPosition)
        {
            if (!EnsurePlayer2ManualCommandsAvailable())
            {
                return;
            }

            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            Debug.Log($"[HumanMove3G1R] Canvas HandleMoveContextRequested target={targetCell} screen={screenPosition} selected={DescribeUnit(selected)} selectedCount={_selectionController?.SelectedUnits.Count ?? 0}");
            if (_selectionController != null && _selectionController.HasMultiSelection)
            {
                _contextMenu?.Show(
                    screenPosition,
                    targetCell,
                    IssueGroupMoveOrder,
                    moveLabel: "Move Group",
                    hint: "Group move order. Use RMB enemy area for group attack.");
                return;
            }

            if (selected == null)
            {
                _commandController?.PublishHumanOrderStatus("Select a unit first.", false);
                return;
            }

            if (selected.IsBuilding || selected.Type == UnitType.Resource)
            {
                _commandController?.PublishHumanOrderStatus("Selected object cannot move.", false);
                return;
            }

            _contextMenu?.Show(
                screenPosition,
                targetCell,
                IssueMoveOrder,
                selected.Owner == Owner.Player2 && selected.Type == UnitType.Worker ? IssueBuildBarracksOrder : null,
                hint: selected.Owner == Owner.Player2 && selected.Type == UnitType.Worker
                    ? "Move or Build Barracks on this free cell."
                    : "Move order.");
        }

        private void IssueGroupMoveOrder(GridPosition targetCell)
        {
            if (!EnsurePlayer2ManualCommandsAvailable())
            {
                return;
            }

            string reason = "Group move order controller is unavailable.";
            int issued = _orderController != null
                ? _orderController.IssueGroupMove(GetSelectedUnits(), targetCell, out reason)
                : 0;
            _commandController?.PublishHumanOrderStatus(issued > 0 ? $"Group move: {issued} units." : reason, issued > 0);
            Refresh(force: true);
        }

        private void IssueMoveOrder(GridPosition targetCell)
        {
            if (!EnsurePlayer2ManualCommandsAvailable())
            {
                return;
            }

            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            Debug.Log($"[HumanMove3G1R] Canvas IssueMove target={targetCell} selected={DescribeUnit(selected)}");
            bool accepted = _orderController != null && _orderController.IssueMove(selected, targetCell);
            HumanUnitOrder order = _orderController != null ? _orderController.GetOrderStatus(selected) : null;
            _commandController?.PublishHumanOrderStatus(order != null ? order.StatusText : "Move order unavailable.", accepted);
            Refresh(force: true);
        }

        private void IssueBuildBarracksOrder(GridPosition buildCell)
        {
            if (!EnsurePlayer2ManualCommandsAvailable())
            {
                return;
            }

            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            string reason = "Build Barracks order controller is unavailable.";
            bool accepted = _orderController != null && _orderController.IssueBuildBarracks(selected, buildCell, out reason);
            HumanUnitOrder order = _orderController != null ? _orderController.GetOrderStatus(selected) : null;
            string status = order != null ? order.StatusText : reason;
            _commandController?.PublishHumanOrderStatus(status, accepted);
            Refresh(force: true);
        }

        private void HandleGatherContextRequested(ResourceNode resource, Vector2 screenPosition)
        {
            if (!EnsurePlayer2ManualCommandsAvailable())
            {
                return;
            }

            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            if (_selectionController != null && _selectionController.HasMultiSelection)
            {
                _commandController?.PublishHumanOrderStatus("Gather requires a single selected Worker.", false);
                return;
            }

            if (selected == null || selected.Owner != Owner.Player2 || selected.Type != UnitType.Worker)
            {
                _commandController?.PublishHumanOrderStatus("Gather requires a selected Player2 Worker.", false);
                return;
            }

            if (resource == null || resource.IsExhausted)
            {
                _commandController?.PublishHumanOrderStatus("Resource is exhausted.", false);
                _contextMenu?.ShowInfo(screenPosition, "Resource is exhausted.");
                return;
            }

            _contextMenu?.ShowGather(
                screenPosition,
                resource,
                IssueHarvestLoop,
                hint: "Worker will gather and return automatically.");
        }

        private void IssueHarvestLoop(ResourceNode resource)
        {
            if (!EnsurePlayer2ManualCommandsAvailable())
            {
                return;
            }

            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            string reason = "Gather order controller is unavailable.";
            bool accepted = _orderController != null && _orderController.IssueHarvestLoop(selected, resource, out reason);
            HumanUnitOrder order = _orderController != null ? _orderController.GetOrderStatus(selected) : null;
            string status = order != null ? order.StatusText : reason;
            _commandController?.PublishHumanOrderStatus(status, accepted);
            Refresh(force: true);
        }

        private void HandleAttackContextRequested(UnitRuntime target, Vector2 screenPosition)
        {
            if (!EnsurePlayer2ManualCommandsAvailable())
            {
                return;
            }

            if (target == null)
            {
                _commandController?.PublishHumanOrderStatus("No enemy target in attack area.", false);
                return;
            }

            HandleAttackAreaContextRequested(target.GridPos, screenPosition);
        }

        private void IssueAttackOrder(UnitRuntime target)
        {
            if (!EnsurePlayer2ManualCommandsAvailable())
            {
                return;
            }

            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            string reason = "Attack order controller is unavailable.";
            bool accepted = _orderController != null && _orderController.IssueAttack(selected, target, out reason);
            HumanUnitOrder order = _orderController != null ? _orderController.GetOrderStatus(selected) : null;
            string status = order != null ? order.StatusText : reason;
            _commandController?.PublishHumanOrderStatus(status, accepted);
            Refresh(force: true);
        }

        private void HandleAttackAreaContextRequested(GridPosition areaCell, Vector2 screenPosition)
        {
            if (!EnsurePlayer2ManualCommandsAvailable())
            {
                return;
            }

            IReadOnlyList<UnitRuntime> selectedUnits = GetSelectedUnits();
            int attackCapableCount = CountAttackCapableUnits(selectedUnits);
            if (attackCapableCount <= 0)
            {
                _commandController?.PublishHumanOrderStatus(
                    selectedUnits != null && selectedUnits.Count > 1
                        ? "No selected units can attack."
                        : "Selected unit cannot attack.",
                    false);
                return;
            }

            int radius = selectedUnits.Count > 1 ? _attackAreaRadius : _attackClickAcquireRadius;
            List<UnitRuntime> targets = _attackTargets != null
                ? _attackTargets.FindEnemiesInArea(Owner.Player2, areaCell, radius)
                : new List<UnitRuntime>();
            if (targets.Count == 0)
            {
                _commandController?.PublishHumanOrderStatus("No enemy target in attack area.", false);
                return;
            }

            string label = selectedUnits.Count > 1
                ? $"Attack Area ({targets.Count})"
                : "Attack " + targets[0].Type;
            _commandController?.PublishHumanOrderStatus(
                selectedUnits.Count > 1
                    ? $"Attack area: {targets.Count} targets, {attackCapableCount} attackers."
                    : "Attack target acquired: " + targets[0].Type + ".",
                true);
            _contextMenu?.ShowAttackArea(
                screenPosition,
                areaCell,
                label,
                IssueAttackAreaOrder,
                hint: selectedUnits.Count > 1
                    ? "Attack Area: selected units attack enemies in this area."
                    : "Attack selected enemy target.");
        }

        private void IssueAttackAreaOrder(GridPosition areaCell)
        {
            if (!EnsurePlayer2ManualCommandsAvailable())
            {
                return;
            }

            IReadOnlyList<UnitRuntime> selectedUnits = GetSelectedUnits();
            string reason = "Attack order controller is unavailable.";
            int issued = _orderController != null
                ? _orderController.IssueAttackArea(
                    selectedUnits,
                    areaCell,
                    selectedUnits.Count > 1 ? _attackAreaRadius : _attackClickAcquireRadius,
                    out reason)
                : 0;
            _commandController?.PublishHumanOrderStatus(
                reason,
                issued > 0);
            Refresh(force: true);
        }

        private IReadOnlyList<UnitRuntime> GetSelectedUnits()
        {
            return _selectionManager != null
                ? _selectionManager.SelectedUnits
                : _selectionController != null ? _selectionController.SelectedUnits : System.Array.Empty<UnitRuntime>();
        }

        private int CountAttackCapableUnits(IReadOnlyList<UnitRuntime> units)
        {
            if (_pathfindingService == null || units == null)
            {
                return 0;
            }

            int count = 0;
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit != null
                    && unit.IsAlive
                    && unit.Owner == Owner.Player2
                    && _pathfindingService.CanUnitAttack(unit, out _))
                {
                    count++;
                }
            }

            return count;
        }

        private void CancelPrimaryOrder()
        {
            if (!EnsurePlayer2ManualCommandsAvailable())
            {
                return;
            }

            int cancelled = _orderController != null ? _orderController.CancelAllSelectedOrders() : 0;
            _commandController?.PublishHumanOrderStatus($"Cancelled orders: {cancelled}", true);
            Refresh(force: true);
        }

        private bool EnsurePlayer2ManualCommandsAvailable()
        {
            if (HasPlayer2ManualMode())
            {
                return true;
            }

            _contextMenu?.Hide();
            _commandController?.PublishHumanOrderStatus(
                "\u0420\u0443\u0447\u043d\u043e\u0435 \u0443\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u0442\u043e\u043b\u044c\u043a\u043e \u0432 \u0440\u0435\u0436\u0438\u043c\u0435 AI \u043f\u0440\u043e\u0442\u0438\u0432 \u0438\u0433\u0440\u043e\u043a\u0430",
                false);
            return false;
        }

        private static string DescribeUnit(UnitRuntime unit)
        {
            return unit == null
                ? "<null>"
                : $"{unit.name} owner={unit.Owner} type={unit.Type} grid={unit.GridPos}";
        }

        private void UpdateHoveredResource()
        {
            _hoveredResource = null;
            if (_resourceManager == null || _gridManager == null || _commandCamera == null || IsUiFieldFocused())
            {
                return;
            }

            if (!TryGetPointerRay(out Ray ray))
            {
                return;
            }

            GridPosition cell;
            if (Physics.Raycast(ray, out RaycastHit hit, 500f, ~0, QueryTriggerInteraction.Ignore))
            {
                UnitRuntime hitUnit = hit.collider != null ? hit.collider.GetComponentInParent<UnitRuntime>() : null;
                cell = hitUnit != null && hitUnit.Type == UnitType.Resource
                    ? hitUnit.GridPos
                    : _gridManager.WorldToCell(hit.point);
            }
            else if (TryResolveWorldPointOnGround(ray, out Vector3 worldPoint))
            {
                cell = _gridManager.WorldToCell(worldPoint);
            }
            else
            {
                return;
            }

            if (!_gridManager.IsInside(cell))
            {
                return;
            }

            _hoveredResource = _resourceManager.GetResourceNode(cell);
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
                ray = _commandCamera.ScreenPointToRay(mouse.position.ReadValue());
                return true;
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER && !ENABLE_INPUT_SYSTEM
            ray = _commandCamera.ScreenPointToRay(Input.mousePosition);
            return true;
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

        private Button CreateVerticalButton(RectTransform parent, string label, float yFromTop, UnityEngine.Events.UnityAction onClick, Sprite icon = null)
        {
            Button button = CreateButton(label.Replace(" ", string.Empty) + "Button", parent, label, icon, onClick);
            SetRect(button.GetComponent<RectTransform>(), new Vector2(0.5f, 1f), new Vector2(0.5f, 1f), new Vector2(0f, -yFromTop), new Vector2(270f, 44f));
            return button;
        }

        private RectTransform CreatePanel(string name, Transform parent, Vector2 size)
        {
            GameObject go = new GameObject(name, typeof(RectTransform), typeof(Image));
            go.transform.SetParent(parent, false);
            RectTransform rect = go.GetComponent<RectTransform>();
            rect.sizeDelta = size;
            Image image = go.GetComponent<Image>();
            image.sprite = _panelSprite;
            image.type = _panelSprite != null ? Image.Type.Sliced : Image.Type.Simple;
            image.color = _panelColor;
            return rect;
        }

        private Text CreateHeader(RectTransform parent, string text)
        {
            Text header = CreateLabel("Header", parent, 20, FontStyle.Bold, TextAnchor.MiddleLeft);
            header.text = text;
            SetRect(header.rectTransform, new Vector2(0f, 1f), new Vector2(1f, 1f), new Vector2(14f, -26f), new Vector2(-28f, 34f));
            return header;
        }

        private Text CreateBody(RectTransform parent, string text)
        {
            Text body = CreateLabel("Body", parent, 16, FontStyle.Normal, TextAnchor.UpperLeft);
            body.text = text;
            body.lineSpacing = 1.05f;
            Stretch(body.rectTransform, Vector2.zero, Vector2.one, new Vector2(14f, 12f), new Vector2(-14f, -54f));
            return body;
        }

        private GameObject CreateButtonRow(RectTransform parent, string name, float yFromTop)
        {
            RectTransform row = CreateRect(name, parent);
            SetRect(row, new Vector2(0f, 1f), new Vector2(1f, 1f), new Vector2(14f, -yFromTop), new Vector2(-28f, 48f));
            HorizontalLayoutGroup layout = row.gameObject.AddComponent<HorizontalLayoutGroup>();
            layout.spacing = 8f;
            layout.childControlWidth = false;
            layout.childControlHeight = true;
            return row.gameObject;
        }

        private Button CreateButton(string name, RectTransform parent, string label, Sprite icon, UnityEngine.Events.UnityAction onClick)
        {
            GameObject go = new GameObject(name, typeof(RectTransform), typeof(Image), typeof(Button));
            go.transform.SetParent(parent, false);
            Image image = go.GetComponent<Image>();
            image.sprite = _buttonSprite;
            image.type = _buttonSprite != null ? Image.Type.Sliced : Image.Type.Simple;
            image.color = _buttonColor;
            Button button = go.GetComponent<Button>();
            button.onClick.AddListener(onClick);
            SpriteState state = button.spriteState;
            state.pressedSprite = _buttonPressedSprite;
            button.spriteState = state;

            if (icon != null)
            {
                Image iconImage = CreateIcon(go.transform as RectTransform, icon);
                SetRect(iconImage.rectTransform, new Vector2(0f, 0.5f), new Vector2(0f, 0.5f), new Vector2(25f, 0f), new Vector2(22f, 22f));
            }

            Text text = CreateLabel("Text", go.transform as RectTransform, 16, FontStyle.Bold, TextAnchor.MiddleCenter);
            text.text = label;
            text.color = new Color(0.12f, 0.09f, 0.05f, 1f);
            Stretch(text.rectTransform, Vector2.zero, Vector2.one, new Vector2(8f, 0f), new Vector2(-8f, 0f));
            return button;
        }

        private Image CreateIcon(RectTransform parent, Sprite sprite)
        {
            GameObject go = new GameObject("Icon", typeof(RectTransform), typeof(Image));
            go.transform.SetParent(parent, false);
            Image image = go.GetComponent<Image>();
            image.sprite = sprite;
            image.color = Color.white;
            image.raycastTarget = false;
            return image;
        }

        private Toggle CreateToggle(RectTransform parent, string label, Vector2 anchoredPosition, bool value)
        {
            GameObject go = new GameObject(label + "Toggle", typeof(RectTransform), typeof(Toggle));
            go.transform.SetParent(parent, false);
            RectTransform rect = go.GetComponent<RectTransform>();
            SetRect(rect, new Vector2(0f, 1f), new Vector2(0f, 1f), anchoredPosition, new Vector2(250f, 36f));
            Image box = CreateIcon(rect, _buttonSprite);
            box.color = _buttonColor;
            SetRect(box.rectTransform, new Vector2(0f, 0.5f), new Vector2(0f, 0.5f), new Vector2(18f, 0f), new Vector2(28f, 28f));
            Image check = CreateIcon(box.rectTransform, null);
            check.color = Color.green;
            Stretch(check.rectTransform, Vector2.zero, Vector2.one, new Vector2(7f, 7f), new Vector2(-7f, -7f));
            Text text = CreateLabel("Label", rect, 18, FontStyle.Normal, TextAnchor.MiddleLeft);
            text.text = label;
            SetRect(text.rectTransform, new Vector2(0f, 0.5f), new Vector2(1f, 0.5f), new Vector2(150f, 0f), new Vector2(210f, 32f));
            Toggle toggle = go.GetComponent<Toggle>();
            toggle.targetGraphic = box;
            toggle.graphic = check;
            toggle.isOn = value;
            return toggle;
        }

        private Slider CreateSlider(RectTransform parent, Vector2 anchoredPosition, float value)
        {
            GameObject go = new GameObject("VolumeSlider", typeof(RectTransform), typeof(Slider));
            go.transform.SetParent(parent, false);
            RectTransform rect = go.GetComponent<RectTransform>();
            SetRect(rect, new Vector2(0f, 1f), new Vector2(0f, 1f), anchoredPosition, new Vector2(250f, 28f));
            Image background = CreateIcon(rect, _buttonSprite);
            background.color = new Color(0.3f, 0.24f, 0.14f, 0.9f);
            Stretch(background.rectTransform, Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);
            RectTransform fillArea = CreateRect("Fill Area", rect);
            Stretch(fillArea, Vector2.zero, Vector2.one, new Vector2(6f, 6f), new Vector2(-6f, -6f));
            Image fill = CreateIcon(fillArea, null);
            fill.color = new Color(0.23f, 0.56f, 0.36f, 1f);
            Stretch(fill.rectTransform, Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);
            Slider slider = go.GetComponent<Slider>();
            slider.minValue = 0f;
            slider.maxValue = 1f;
            slider.value = Mathf.Clamp01(value);
            slider.fillRect = fill.rectTransform;
            slider.targetGraphic = background;
            return slider;
        }

        private Text CreateLabel(string name, RectTransform parent, int fontSize, FontStyle style, TextAnchor anchor)
        {
            GameObject go = new GameObject(name, typeof(RectTransform), typeof(Text));
            go.transform.SetParent(parent, false);
            Text label = go.GetComponent<Text>();
            label.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            label.fontSize = fontSize;
            label.fontStyle = style;
            label.alignment = anchor;
            label.color = _textColor;
            label.horizontalOverflow = HorizontalWrapMode.Wrap;
            label.verticalOverflow = VerticalWrapMode.Truncate;
            label.raycastTarget = false;
            return label;
        }

        private static RectTransform CreateRect(string name, Transform parent)
        {
            GameObject go = new GameObject(name, typeof(RectTransform));
            go.transform.SetParent(parent, false);
            return go.GetComponent<RectTransform>();
        }

        private static void AddLayout(GameObject go, float preferredWidth, float preferredHeight)
        {
            LayoutElement layout = go.GetComponent<LayoutElement>() ?? go.AddComponent<LayoutElement>();
            if (preferredWidth >= 0f)
            {
                layout.preferredWidth = preferredWidth;
            }

            if (preferredHeight >= 0f)
            {
                layout.preferredHeight = preferredHeight;
            }
        }

        private static void SetText(Text label, string value)
        {
            if (label != null)
            {
                label.text = value;
            }
        }

        private static void SetRect(RectTransform rect, Vector2 anchorMin, Vector2 anchorMax, Vector2 anchoredPosition, Vector2 sizeDelta)
        {
            rect.anchorMin = anchorMin;
            rect.anchorMax = anchorMax;
            rect.anchoredPosition = anchoredPosition;
            rect.sizeDelta = sizeDelta;
        }

        private static void Stretch(RectTransform rect, Vector2 anchorMin, Vector2 anchorMax, Vector2 offsetMin, Vector2 offsetMax)
        {
            rect.anchorMin = anchorMin;
            rect.anchorMax = anchorMax;
            rect.offsetMin = offsetMin;
            rect.offsetMax = offsetMax;
        }

        private static bool IsUiFieldFocused()
        {
            EventSystem eventSystem = EventSystem.current;
            if (eventSystem == null || eventSystem.currentSelectedGameObject == null)
            {
                return false;
            }

            return eventSystem.currentSelectedGameObject.GetComponent<InputField>() != null;
        }

        private static bool WasKeyPressed(KeyCode key)
        {
#if ENABLE_INPUT_SYSTEM
            Keyboard keyboard = Keyboard.current;
            if (keyboard != null)
            {
                switch (key)
                {
                    case KeyCode.Escape:
                        return keyboard.escapeKey.wasPressedThisFrame;
                    case KeyCode.F1:
                        return keyboard.f1Key.wasPressedThisFrame;
                    case KeyCode.F2:
                        return keyboard.f2Key.wasPressedThisFrame;
                    case KeyCode.F3:
                        return keyboard.f3Key.wasPressedThisFrame;
                    case KeyCode.F4:
                        return keyboard.f4Key.wasPressedThisFrame;
                }
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER && !ENABLE_INPUT_SYSTEM
            return Input.GetKeyDown(key);
#else
            return false;
#endif
        }

        private static void EnsureEventSystem()
        {
            if (EventSystem.current != null)
            {
                return;
            }

            GameObject go = new GameObject("EventSystem", typeof(EventSystem));
#if ENABLE_INPUT_SYSTEM
            go.AddComponent<InputSystemUIInputModule>();
#else
            go.AddComponent<StandaloneInputModule>();
#endif
        }
    }
}
