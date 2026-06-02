using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem.UI;
#endif

namespace RTS.Presentation.UI
{
    [DisallowMultipleComponent]
    public sealed class MainMenuController : MonoBehaviour
    {
        [Header("Flow")]
        [SerializeField] private SceneFlowController _sceneFlowController;

        [Header("Sprites")]
        [SerializeField] private Sprite _panelSprite;
        [SerializeField] private Sprite _buttonSprite;
        [SerializeField] private Sprite _buttonPressedSprite;
        [SerializeField] private Sprite _settingsIcon;
        [SerializeField] private Sprite _quitIcon;

        [Header("Colors")]
        [SerializeField] private Color _backgroundColor = new Color(0.06f, 0.08f, 0.09f, 1f);
        [SerializeField] private Color _panelColor = new Color(0.92f, 0.82f, 0.62f, 0.96f);
        [SerializeField] private Color _buttonColor = new Color(1f, 0.96f, 0.84f, 1f);
        [SerializeField] private Color _textColor = new Color(0.12f, 0.09f, 0.05f, 1f);

        private GameObject _mainPanel;
        private GameObject _modeSelectPanel;
        private GameObject _settingsPanel;
        private Text _gridSettingValue;
        private Text _unitMarkersSettingValue;
        private Text _controlHintsSettingValue;
        private Text _graphicsQualitySettingValue;
        private Text _cameraHeightSettingValue;
        private Text _interfaceScaleSettingValue;
        private Text _settingsStatus;

        private void Awake()
        {
            if (_sceneFlowController == null)
            {
                _sceneFlowController = FindFirstObjectByType<SceneFlowController>();
            }

            EnsureEventSystem();
            BuildMenu();
        }

        private void BuildMenu()
        {
            Canvas canvas = CreateCanvas("MainMenuCanvas");
            RectTransform root = canvas.GetComponent<RectTransform>();

            Image background = CreateImage("Background", root, null, _backgroundColor);
            Stretch(background.rectTransform, Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);

            BuildMainPanel(root);
            BuildModeSelectPanel(root);

            BuildSettingsPanel(root);
            ShowMainPanel();
            _settingsPanel.SetActive(false);
        }

        private void BuildMainPanel(RectTransform root)
        {
            RectTransform panel = CreateCenteredMenuPanel("MenuPanel", root);
            _mainPanel = panel.gameObject;

            Text title = CreateText("Title", panel, "Unity RTS Prototype", 38, FontStyle.Bold, TextAnchor.MiddleCenter);
            SetRect(title.rectTransform, new Vector2(0.5f, 1f), new Vector2(0.5f, 1f), new Vector2(0f, -112f), new Vector2(640f, 120f));

            RectTransform buttons = CreateButtonColumn("MainButtons", panel, new Vector2(0f, -88f), new Vector2(460f, 290f), 26f);
            CreateMenuButton(buttons, "Start", null, ShowModeSelectPanel);
            CreateMenuButton(buttons, "Settings", _settingsIcon, ShowSettings);
            CreateMenuButton(buttons, "Quit", _quitIcon, () => InvokeSafe(() => _sceneFlowController.Quit()));
        }

        private void BuildModeSelectPanel(RectTransform root)
        {
            RectTransform panel = CreateCenteredMenuPanel("ModeSelectPanel", root);
            _modeSelectPanel = panel.gameObject;

            Text title = CreateText("Title", panel, "\u0412\u044b\u0431\u043e\u0440 \u0440\u0435\u0436\u0438\u043c\u0430", 36, FontStyle.Bold, TextAnchor.MiddleCenter);
            SetRect(title.rectTransform, new Vector2(0.5f, 1f), new Vector2(0.5f, 1f), new Vector2(0f, -92f), new Vector2(640f, 90f));

            RectTransform buttons = CreateButtonColumn("ModeButtons", panel, new Vector2(0f, -70f), new Vector2(460f, 360f), 18f);
            CreateMenuButton(buttons, "AI \u043f\u0440\u043e\u0442\u0438\u0432 AI", null, () => InvokeSafe(() => _sceneFlowController.LoadDemoAIvsAI()));
            CreateMenuButton(buttons, "AI \u043f\u0440\u043e\u0442\u0438\u0432 \u0431\u043e\u0442\u0430", null, () => InvokeSafe(() => _sceneFlowController.LoadDemoAIvsBot()));
            CreateMenuButton(buttons, "AI \u043f\u0440\u043e\u0442\u0438\u0432 \u0438\u0433\u0440\u043e\u043a\u0430", null, () => InvokeSafe(() => _sceneFlowController.LoadDemoAIvsPlayer()));
            CreateMenuButton(buttons, "\u041d\u0430\u0437\u0430\u0434", null, ShowMainPanel);
        }

        private RectTransform CreateCenteredMenuPanel(string name, RectTransform root)
        {
            RectTransform panel = CreatePanel(name, root, new Vector2(760f, 620f), _panelSprite, _panelColor);
            panel.anchorMin = new Vector2(0.5f, 0.5f);
            panel.anchorMax = new Vector2(0.5f, 0.5f);
            panel.anchoredPosition = Vector2.zero;
            return panel;
        }

        private static RectTransform CreateButtonColumn(string name, RectTransform parent, Vector2 position, Vector2 size, float spacing)
        {
            RectTransform buttons = new GameObject(name, typeof(RectTransform), typeof(VerticalLayoutGroup)).GetComponent<RectTransform>();
            buttons.SetParent(parent, false);
            SetRect(buttons, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), position, size);
            VerticalLayoutGroup layout = buttons.GetComponent<VerticalLayoutGroup>();
            layout.spacing = spacing;
            layout.childAlignment = TextAnchor.MiddleCenter;
            layout.childControlWidth = false;
            layout.childControlHeight = false;
            layout.childForceExpandWidth = false;
            layout.childForceExpandHeight = false;
            return buttons;
        }

        private void ShowMainPanel()
        {
            SetMenuPanelVisibility(showMain: true);
        }

        private void ShowModeSelectPanel()
        {
            SetMenuPanelVisibility(showMain: false);
        }

        private void SetMenuPanelVisibility(bool showMain)
        {
            _mainPanel?.SetActive(showMain);
            _modeSelectPanel?.SetActive(!showMain);
        }

        private void BuildSettingsPanel(RectTransform root)
        {
            RectTransform modalRoot = new GameObject("SettingsModal", typeof(RectTransform), typeof(Image)).GetComponent<RectTransform>();
            modalRoot.SetParent(root, false);
            Stretch(modalRoot, Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);
            Image shade = modalRoot.GetComponent<Image>();
            shade.color = new Color(0f, 0f, 0f, 0.35f);
            _settingsPanel = modalRoot.gameObject;

            RectTransform panel = CreatePanel("SettingsPanel", modalRoot, new Vector2(760f, 700f), _panelSprite, _panelColor);
            panel.anchorMin = new Vector2(0.5f, 0.5f);
            panel.anchorMax = new Vector2(0.5f, 0.5f);
            panel.anchoredPosition = Vector2.zero;

            VerticalLayoutGroup layout = panel.gameObject.AddComponent<VerticalLayoutGroup>();
            layout.padding = new RectOffset(56, 56, 30, 30);
            layout.spacing = 12f;
            layout.childAlignment = TextAnchor.UpperCenter;
            layout.childControlWidth = true;
            layout.childControlHeight = false;
            layout.childForceExpandWidth = true;
            layout.childForceExpandHeight = false;

            Text title = CreateText("Title", panel, "\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438", 30, FontStyle.Bold, TextAnchor.MiddleCenter);
            AddLayout(title.gameObject, -1f, 48f);

            _gridSettingValue = CreateVisualSettingsRow(panel, "GridRow", "\u041f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0442\u044c \u0441\u0435\u0442\u043a\u0443", DemoVisualSettings.ToggleGrid);
            _unitMarkersSettingValue = CreateVisualSettingsRow(panel, "UnitMarkersRow", "\u041f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0442\u044c \u043c\u0430\u0440\u043a\u0435\u0440\u044b \u044e\u043d\u0438\u0442\u043e\u0432", DemoVisualSettings.ToggleUnitMarkers);
            _controlHintsSettingValue = CreateVisualSettingsRow(panel, "ControlHintsRow", "\u041f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0442\u044c \u043f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0438 \u0443\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u044f", DemoVisualSettings.ToggleControlHints);
            _graphicsQualitySettingValue = CreateVisualSettingsRow(panel, "GraphicsQualityRow", "\u041a\u0430\u0447\u0435\u0441\u0442\u0432\u043e \u0433\u0440\u0430\u0444\u0438\u043a\u0438", DemoVisualSettings.CycleGraphicsQuality);
            _cameraHeightSettingValue = CreateVisualSettingsRow(panel, "CameraHeightRow", "\u0412\u044b\u0441\u043e\u0442\u0430 \u043a\u0430\u043c\u0435\u0440\u044b", DemoVisualSettings.CycleCameraHeight);
            _interfaceScaleSettingValue = CreateVisualSettingsRow(panel, "InterfaceScaleRow", "\u041c\u0430\u0441\u0448\u0442\u0430\u0431 \u0438\u043d\u0442\u0435\u0440\u0444\u0435\u0439\u0441\u0430", DemoVisualSettings.CycleInterfaceScale);

            _settingsStatus = CreateText("SettingsStatus", panel, string.Empty, 18, FontStyle.Bold, TextAnchor.MiddleCenter);
            AddLayout(_settingsStatus.gameObject, -1f, 30f);

            Button apply = CreateMenuButton(panel, "\u041f\u0440\u0438\u043c\u0435\u043d\u0438\u0442\u044c", null, ApplySettings);
            AddLayout(apply.gameObject, 280f, 54f);
            Button back = CreateMenuButton(panel, "\u041d\u0430\u0437\u0430\u0434", null, HideSettings);
            AddLayout(back.gameObject, 280f, 54f);
            RefreshSettingsLabels();
        }

        private void ShowSettings()
        {
            if (_settingsPanel != null)
            {
                RefreshSettingsLabels();
                _settingsStatus.text = string.Empty;
                _settingsPanel.SetActive(true);
            }
        }

        private void HideSettings()
        {
            if (_settingsPanel != null)
            {
                _settingsPanel.SetActive(false);
            }
        }

        private Text CreateVisualSettingsRow(RectTransform parent, string name, string label, System.Action update)
        {
            RectTransform row = CreateSettingsRow(parent, name);
            Text settingLabel = CreateText("Label", row, label, 20, FontStyle.Normal, TextAnchor.MiddleLeft);
            AddLayout(settingLabel.gameObject, 430f, 46f);
            Button valueButton = CreateCompactSettingsButton(row, update);
            AddLayout(valueButton.gameObject, 190f, 44f);
            return valueButton.GetComponentInChildren<Text>();
        }

        private Button CreateCompactSettingsButton(RectTransform parent, System.Action update)
        {
            Button button = CreateButton("ValueButton", parent, string.Empty, null, new Vector2(190f, 44f), () =>
            {
                update?.Invoke();
                RefreshSettingsLabels();
                _settingsStatus.text = string.Empty;
            });
            button.image.sprite = _buttonSprite;
            button.image.type = _buttonSprite != null ? Image.Type.Sliced : Image.Type.Simple;
            button.image.color = _buttonColor;
            SpriteState state = button.spriteState;
            state.pressedSprite = _buttonPressedSprite;
            button.spriteState = state;
            return button;
        }

        private void ApplySettings()
        {
            if (_settingsStatus != null)
            {
                _settingsStatus.text = "\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438 \u043f\u0440\u0438\u043c\u0435\u043d\u0435\u043d\u044b";
            }
        }

        private void RefreshSettingsLabels()
        {
            SetText(_gridSettingValue, DemoVisualSettings.FormatToggle(DemoVisualSettings.ShowGrid));
            SetText(_unitMarkersSettingValue, DemoVisualSettings.FormatToggle(DemoVisualSettings.ShowUnitMarkers));
            SetText(_controlHintsSettingValue, DemoVisualSettings.FormatToggle(DemoVisualSettings.ShowControlHints));
            SetText(_graphicsQualitySettingValue, DemoVisualSettings.GraphicsQuality.ToString());
            SetText(_cameraHeightSettingValue, DemoVisualSettings.CameraHeight.ToString());
            SetText(_interfaceScaleSettingValue, DemoVisualSettings.InterfaceScale.ToString());
        }

        private static void SetText(Text label, string value)
        {
            if (label != null)
            {
                label.text = value;
            }
        }

        private Button CreateMenuButton(RectTransform parent, string label, Sprite icon, UnityEngine.Events.UnityAction onClick)
        {
            Button button = CreateButton(label + "Button", parent, label, icon, new Vector2(440f, 70f), onClick);
            button.image.sprite = _buttonSprite;
            button.image.type = _buttonSprite != null ? Image.Type.Sliced : Image.Type.Simple;
            button.image.color = _buttonColor;
            SpriteState state = button.spriteState;
            state.pressedSprite = _buttonPressedSprite;
            button.spriteState = state;
            AddLayout(button.gameObject, 440f, 70f);
            return button;
        }

        private static Canvas CreateCanvas(string name)
        {
            GameObject go = new GameObject(name, typeof(RectTransform), typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            Canvas canvas = go.GetComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 0;
            CanvasScaler scaler = go.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            scaler.matchWidthOrHeight = 0.5f;
            return canvas;
        }

        private RectTransform CreatePanel(string name, RectTransform parent, Vector2 size, Sprite sprite, Color color)
        {
            Image image = CreateImage(name, parent, sprite, color);
            image.type = sprite != null ? Image.Type.Sliced : Image.Type.Simple;
            image.rectTransform.sizeDelta = size;
            return image.rectTransform;
        }

        private Image CreateImage(string name, RectTransform parent, Sprite sprite, Color color)
        {
            GameObject go = new GameObject(name, typeof(RectTransform), typeof(Image));
            go.transform.SetParent(parent, false);
            Image image = go.GetComponent<Image>();
            image.sprite = sprite;
            image.color = color;
            return image;
        }

        private Text CreateText(string name, RectTransform parent, string text, int size, FontStyle style, TextAnchor anchor)
        {
            GameObject go = new GameObject(name, typeof(RectTransform), typeof(Text));
            go.transform.SetParent(parent, false);
            Text label = go.GetComponent<Text>();
            label.text = text;
            label.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            label.fontSize = size;
            label.fontStyle = style;
            label.alignment = anchor;
            label.color = _textColor;
            label.horizontalOverflow = HorizontalWrapMode.Wrap;
            label.verticalOverflow = VerticalWrapMode.Truncate;
            return label;
        }

        private Button CreateButton(string name, RectTransform parent, string label, Sprite icon, Vector2 size, UnityEngine.Events.UnityAction onClick)
        {
            GameObject go = new GameObject(name, typeof(RectTransform), typeof(Image), typeof(Button));
            go.transform.SetParent(parent, false);
            RectTransform rect = go.GetComponent<RectTransform>();
            rect.sizeDelta = size;
            Button button = go.GetComponent<Button>();
            button.onClick.AddListener(onClick);

            if (icon != null)
            {
                Image iconImage = CreateImage("Icon", rect, icon, Color.white);
                SetRect(iconImage.rectTransform, new Vector2(0f, 0.5f), new Vector2(0f, 0.5f), new Vector2(36f, 0f), new Vector2(24f, 24f));
            }

            Text text = CreateText("Text", rect, label, 20, FontStyle.Bold, TextAnchor.MiddleCenter);
            Stretch(text.rectTransform, Vector2.zero, Vector2.one, new Vector2(16f, 0f), new Vector2(-16f, 0f));
            return button;
        }

        private Toggle CreateToggle(RectTransform parent, string label, Vector2 anchoredPosition, bool value)
        {
            GameObject go = new GameObject(label + "Toggle", typeof(RectTransform), typeof(Toggle));
            go.transform.SetParent(parent, false);
            RectTransform rect = go.GetComponent<RectTransform>();
            rect.sizeDelta = new Vector2(260f, 36f);
            rect.anchoredPosition = anchoredPosition;

            Image box = CreateImage("Box", rect, _buttonSprite, _buttonColor);
            SetRect(box.rectTransform, new Vector2(0f, 0.5f), new Vector2(0f, 0.5f), new Vector2(18f, 0f), new Vector2(28f, 28f));
            Image check = CreateImage("Checkmark", box.rectTransform, null, Color.green);
            Stretch(check.rectTransform, Vector2.zero, Vector2.one, new Vector2(7f, 7f), new Vector2(-7f, -7f));
            Text text = CreateText("Label", rect, label, 18, FontStyle.Normal, TextAnchor.MiddleLeft);
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
            rect.sizeDelta = new Vector2(250f, 28f);
            rect.anchoredPosition = anchoredPosition;

            Image background = CreateImage("Background", rect, _buttonSprite, new Color(0.3f, 0.24f, 0.14f, 0.8f));
            Stretch(background.rectTransform, Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);
            RectTransform fillArea = new GameObject("Fill Area", typeof(RectTransform)).GetComponent<RectTransform>();
            fillArea.SetParent(rect, false);
            Stretch(fillArea, Vector2.zero, Vector2.one, new Vector2(6f, 6f), new Vector2(-6f, -6f));
            Image fill = CreateImage("Fill", fillArea, null, new Color(0.23f, 0.56f, 0.36f, 1f));
            Stretch(fill.rectTransform, Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);

            Slider slider = go.GetComponent<Slider>();
            slider.minValue = 0f;
            slider.maxValue = 1f;
            slider.value = Mathf.Clamp01(value);
            slider.fillRect = fill.rectTransform;
            slider.targetGraphic = background;
            return slider;
        }

        private RectTransform CreateSettingsRow(RectTransform parent, string name)
        {
            RectTransform row = new GameObject(name, typeof(RectTransform), typeof(HorizontalLayoutGroup)).GetComponent<RectTransform>();
            row.SetParent(parent, false);
            AddLayout(row.gameObject, -1f, 52f);
            HorizontalLayoutGroup layout = row.GetComponent<HorizontalLayoutGroup>();
            layout.spacing = 24f;
            layout.childAlignment = TextAnchor.MiddleLeft;
            layout.childControlWidth = false;
            layout.childControlHeight = false;
            layout.childForceExpandWidth = false;
            layout.childForceExpandHeight = false;
            return row;
        }

        private Toggle CreateToggleBox(RectTransform parent, bool value)
        {
            GameObject go = new GameObject("FullscreenToggle", typeof(RectTransform), typeof(Toggle));
            go.transform.SetParent(parent, false);
            RectTransform rect = go.GetComponent<RectTransform>();
            rect.sizeDelta = new Vector2(42f, 42f);

            Image box = CreateImage("Box", rect, _buttonSprite, _buttonColor);
            Stretch(box.rectTransform, Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);
            box.type = _buttonSprite != null ? Image.Type.Sliced : Image.Type.Simple;

            Image check = CreateImage("Checkmark", box.rectTransform, null, new Color(0.18f, 0.58f, 0.26f, 1f));
            Stretch(check.rectTransform, Vector2.zero, Vector2.one, new Vector2(10f, 10f), new Vector2(-10f, -10f));

            Toggle toggle = go.GetComponent<Toggle>();
            toggle.targetGraphic = box;
            toggle.graphic = check;
            toggle.isOn = value;
            return toggle;
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

        private static void SetRect(RectTransform rect, Vector2 anchorMin, Vector2 anchorMax, Vector2 anchoredPosition, Vector2 size)
        {
            rect.anchorMin = anchorMin;
            rect.anchorMax = anchorMax;
            rect.anchoredPosition = anchoredPosition;
            rect.sizeDelta = size;
        }

        private static void Stretch(RectTransform rect, Vector2 anchorMin, Vector2 anchorMax, Vector2 offsetMin, Vector2 offsetMax)
        {
            rect.anchorMin = anchorMin;
            rect.anchorMax = anchorMax;
            rect.offsetMin = offsetMin;
            rect.offsetMax = offsetMax;
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
            DontDestroyOnLoad(go);
        }

        private static void InvokeSafe(System.Action action)
        {
            if (action == null)
            {
                return;
            }

            try
            {
                action();
            }
            catch (System.Exception ex)
            {
                Debug.LogWarning("[MainMenuController] Action failed: " + ex.Message);
            }
        }
    }
}
