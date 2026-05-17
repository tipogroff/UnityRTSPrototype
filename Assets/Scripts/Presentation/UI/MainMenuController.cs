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

        private GameObject _settingsPanel;

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

            RectTransform panel = CreatePanel("MenuPanel", root, new Vector2(520f, 440f), _panelSprite, _panelColor);
            panel.anchorMin = new Vector2(0.5f, 0.5f);
            panel.anchorMax = new Vector2(0.5f, 0.5f);
            panel.anchoredPosition = Vector2.zero;

            Text title = CreateText("Title", panel, "Unity RTS Prototype\nAgent vs Player Demo", 30, FontStyle.Bold, TextAnchor.MiddleCenter);
            SetRect(title.rectTransform, new Vector2(0.5f, 1f), new Vector2(0.5f, 1f), new Vector2(0f, -82f), new Vector2(440f, 92f));

            CreateMenuButton(panel, "Start Demo", null, new Vector2(0f, -170f), () => InvokeSafe(() => _sceneFlowController.LoadDemo()));
            CreateMenuButton(panel, "Settings", _settingsIcon, new Vector2(0f, -238f), ShowSettings);
            CreateMenuButton(panel, "Quit", _quitIcon, new Vector2(0f, -306f), () => InvokeSafe(() => _sceneFlowController.Quit()));

            BuildSettingsPanel(root);
            _settingsPanel.SetActive(false);
        }

        private void BuildSettingsPanel(RectTransform root)
        {
            RectTransform panel = CreatePanel("SettingsPanel", root, new Vector2(460f, 320f), _panelSprite, _panelColor);
            panel.anchorMin = new Vector2(0.5f, 0.5f);
            panel.anchorMax = new Vector2(0.5f, 0.5f);
            panel.anchoredPosition = Vector2.zero;
            _settingsPanel = panel.gameObject;

            Text title = CreateText("Title", panel, "Settings", 26, FontStyle.Bold, TextAnchor.MiddleCenter);
            SetRect(title.rectTransform, new Vector2(0.5f, 1f), new Vector2(0.5f, 1f), new Vector2(0f, -48f), new Vector2(380f, 50f));

            Toggle fullscreen = CreateToggle(panel, "Fullscreen", new Vector2(-140f, -108f), Screen.fullScreen);
            fullscreen.onValueChanged.AddListener(value => Screen.fullScreen = value);

            Text volumeLabel = CreateText("VolumeLabel", panel, "Volume", 18, FontStyle.Normal, TextAnchor.MiddleLeft);
            SetRect(volumeLabel.rectTransform, new Vector2(0.5f, 1f), new Vector2(0.5f, 1f), new Vector2(-145f, -166f), new Vector2(130f, 34f));

            Slider volume = CreateSlider(panel, new Vector2(70f, -166f), AudioListener.volume);
            volume.onValueChanged.AddListener(value => AudioListener.volume = value);

            CreateMenuButton(panel, "Back", null, new Vector2(0f, -250f), HideSettings);
        }

        private void ShowSettings()
        {
            if (_settingsPanel != null)
            {
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

        private Button CreateMenuButton(RectTransform parent, string label, Sprite icon, Vector2 anchoredPosition, UnityEngine.Events.UnityAction onClick)
        {
            Button button = CreateButton(label + "Button", parent, label, icon, new Vector2(300f, 52f), onClick);
            button.image.sprite = _buttonSprite;
            button.image.type = _buttonSprite != null ? Image.Type.Sliced : Image.Type.Simple;
            button.image.color = _buttonColor;
            SpriteState state = button.spriteState;
            state.pressedSprite = _buttonPressedSprite;
            button.spriteState = state;
            button.GetComponent<RectTransform>().anchoredPosition = anchoredPosition;
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
