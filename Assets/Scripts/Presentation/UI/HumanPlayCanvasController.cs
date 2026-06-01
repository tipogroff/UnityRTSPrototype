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
        private ContextActionMenuView _contextMenu;
        private GameSpeedController _speedController;
        private SceneFlowController _sceneFlowController;
        private MatchManager _matchManager;
        private Button _moveButton;
        private Button _attackButton;
        private Button _harvestButton;
        private Button _returnButton;
        private Button _buildBarracksButton;
        private Button _stopButton;
        private float _nextRefresh;

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
            _commandPanel.SetContextButtons(_moveButton, _attackButton, _harvestButton, _returnButton, _buildBarracksButton);

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
            GameObject row1 = CreateButtonRow(commands, "Row1", 58f);
            _moveButton = CreateButton("MoveButton", row1.transform as RectTransform, "Move", null, () => _commandController?.BeginMoveCommandMode());
            AddLayout(_moveButton.gameObject, 110f, 42f);
            _attackButton = CreateButton("AttackButton", row1.transform as RectTransform, "Attack", null, () => _commandController?.BeginAttackCommandMode());
            AddLayout(_attackButton.gameObject, 120f, 42f);
            _harvestButton = CreateButton("HarvestButton", row1.transform as RectTransform, "Harvest", null, () => _commandController?.TryHarvestSelected());
            AddLayout(_harvestButton.gameObject, 130f, 42f);
            _returnButton = CreateButton("ReturnButton", row1.transform as RectTransform, "Return", null, () => _commandController?.TryReturnSelected());
            AddLayout(_returnButton.gameObject, 120f, 42f);

            GameObject row2 = CreateButtonRow(commands, "Row2", 110f);
            _buildBarracksButton = CreateButton("BuildBarracksButton", row2.transform as RectTransform, "Build Barracks", null, () => _commandController?.TryBuildBarracks());
            AddLayout(_buildBarracksButton.gameObject, 180f, 42f);
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
            CreateVerticalButton(_pauseMenu, "Settings", 212f, () => _settingsPanel?.gameObject.SetActive(true), _gearIcon);
            CreateVerticalButton(_pauseMenu, "Toggle Metrics", 270f, () => _metricsVisibility?.Toggle());
            CreateVerticalButton(_pauseMenu, "Main Menu", 328f, ReturnToMainMenu, _homeIcon);
            CreateVerticalButton(_pauseMenu, "Quit", 386f, Quit);
        }

        private void BuildSettingsPanel(RectTransform root)
        {
            _settingsPanel = CreatePanel("HudSettingsPanel", root, new Vector2(430f, 300f));
            _settingsPanel.anchorMin = new Vector2(0.5f, 0.5f);
            _settingsPanel.anchorMax = new Vector2(0.5f, 0.5f);
            _settingsPanel.anchoredPosition = new Vector2(0f, 20f);
            _settingsPanel.gameObject.SetActive(false);
            CreateHeader(_settingsPanel, "Settings");

            Toggle fullscreen = CreateToggle(_settingsPanel, "Fullscreen", new Vector2(-120f, -100f), Screen.fullScreen);
            fullscreen.onValueChanged.AddListener(value => Screen.fullScreen = value);

            Text volumeLabel = CreateLabel("VolumeLabel", _settingsPanel, 18, FontStyle.Normal, TextAnchor.MiddleLeft);
            volumeLabel.text = "Volume";
            SetRect(volumeLabel.rectTransform, new Vector2(0f, 1f), new Vector2(0f, 1f), new Vector2(104f, -154f), new Vector2(130f, 32f));

            Slider volume = CreateSlider(_settingsPanel, new Vector2(88f, -154f), AudioListener.volume);
            volume.onValueChanged.AddListener(value => AudioListener.volume = value);
            CreateVerticalButton(_settingsPanel, "Back", 232f, () => _settingsPanel.gameObject.SetActive(false));
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
            _topResourceBar?.Refresh(_matchManager);
            _selectionInfo?.Refresh(selectedUnits, selected);
            _commandPanel?.Refresh(_commandController, selectedUnits, selected);
            _productionPanel?.Refresh(selected, selectionCount, _commandController);
            _metricsPanel?.Refresh(_modeController, _humanPlayerController, _commandController, _speedController);
        }

        private void HandleHotkeys()
        {
            if (IsUiFieldFocused())
            {
                return;
            }

            if (WasKeyPressed(KeyCode.Escape))
            {
                if (_contextMenu != null && _contextMenu.IsOpen)
                {
                    _contextMenu.Hide();
                    return;
                }

                SetPauseMenuVisible(true);
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
                _selectionVisibility?.Toggle();
            }

            if (WasKeyPressed(KeyCode.F4))
            {
                _productionVisibility?.Toggle();
            }
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
            _pathfindingService ??= FindFirstObjectByType<GridPathfindingService>();
            if (_pathfindingService == null)
            {
                _pathfindingService = gameObject.AddComponent<GridPathfindingService>();
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
            }
        }

        private void HandleMoveContextRequested(GridPosition targetCell, Vector2 screenPosition)
        {
            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            Debug.Log($"[HumanMove3G1R] Canvas HandleMoveContextRequested target={targetCell} screen={screenPosition} selected={DescribeUnit(selected)} selectedCount={_selectionController?.SelectedUnits.Count ?? 0}");
            if (_selectionController != null && _selectionController.HasMultiSelection)
            {
                _commandController?.PublishHumanOrderStatus("Group movement requires pathfinding/formation; use single selection.", false);
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

            _contextMenu?.Show(screenPosition, targetCell, IssueMoveOrder);
        }

        private void IssueMoveOrder(GridPosition targetCell)
        {
            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            Debug.Log($"[HumanMove3G1R] Canvas IssueMove target={targetCell} selected={DescribeUnit(selected)}");
            bool accepted = _orderController != null && _orderController.IssueMove(selected, targetCell);
            HumanUnitOrder order = _orderController != null ? _orderController.GetOrderStatus(selected) : null;
            _commandController?.PublishHumanOrderStatus(order != null ? order.StatusText : "Move order unavailable.", accepted);
            Refresh(force: true);
        }

        private void HandleGatherContextRequested(ResourceNode resource, Vector2 screenPosition)
        {
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
                return;
            }

            _contextMenu?.ShowGather(screenPosition, resource, IssueHarvestLoop);
        }

        private void IssueHarvestLoop(ResourceNode resource)
        {
            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            string reason = "Gather order controller is unavailable.";
            bool accepted = _orderController != null && _orderController.IssueHarvestLoop(selected, resource, out reason);
            HumanUnitOrder order = _orderController != null ? _orderController.GetOrderStatus(selected) : null;
            string status = order != null ? order.StatusText : reason;
            _commandController?.PublishHumanOrderStatus(status, accepted);
            Refresh(force: true);
        }

        private void CancelPrimaryOrder()
        {
            UnitRuntime selected = _selectionController != null ? _selectionController.SelectedUnit : null;
            _orderController?.CancelOrder(selected);
            HumanUnitOrder order = _orderController != null ? _orderController.GetOrderStatus(selected) : null;
            _commandController?.PublishHumanOrderStatus(order != null ? order.StatusText : "No active order.", true);
            Refresh(force: true);
        }

        private static string DescribeUnit(UnitRuntime unit)
        {
            return unit == null
                ? "<null>"
                : $"{unit.name} owner={unit.Owner} type={unit.Type} grid={unit.GridPos}";
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
