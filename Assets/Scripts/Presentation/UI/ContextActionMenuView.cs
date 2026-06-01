using System;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;
using UnityEngine.UI;

namespace RTS.Presentation.UI
{
    [DisallowMultipleComponent]
    public sealed class ContextActionMenuView : MonoBehaviour
    {
        private RectTransform _canvasRect;
        private RectTransform _menu;
        private Action<GridPosition> _moveAction;
        private GridPosition _targetCell;

        public bool IsOpen => gameObject.activeSelf;

        public void Initialize(Canvas canvas, Sprite panelSprite, Sprite buttonSprite, Color panelColor, Color buttonColor)
        {
            _canvasRect = canvas != null ? canvas.transform as RectTransform : null;

            RectTransform overlay = GetComponent<RectTransform>();
            Stretch(overlay, Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);
            Image blocker = gameObject.AddComponent<Image>();
            blocker.color = new Color(0f, 0f, 0f, 0.001f);
            Button outside = gameObject.AddComponent<Button>();
            outside.onClick.AddListener(Hide);

            _menu = CreateRect("MoveContextMenu", transform);
            _menu.sizeDelta = new Vector2(150f, 58f);
            Image panel = _menu.gameObject.AddComponent<Image>();
            panel.sprite = panelSprite;
            panel.type = panelSprite != null ? Image.Type.Sliced : Image.Type.Simple;
            panel.color = panelColor;

            Button move = CreateButton(_menu, "Move", buttonSprite, buttonColor);
            RectTransform moveRect = move.GetComponent<RectTransform>();
            Stretch(moveRect, Vector2.zero, Vector2.one, new Vector2(8f, 8f), new Vector2(-8f, -8f));
            move.onClick.AddListener(HandleMoveClicked);
            gameObject.SetActive(false);
        }

        public void Show(Vector2 screenPosition, GridPosition targetCell, Action<GridPosition> moveAction)
        {
            _targetCell = targetCell;
            _moveAction = moveAction;
            gameObject.SetActive(true);
            transform.SetAsLastSibling();
            Debug.Log($"[HumanMove3G1R] Context menu opened target={targetCell} screen={screenPosition}");

            if (_canvasRect == null || _menu == null)
            {
                return;
            }

            RectTransformUtility.ScreenPointToLocalPointInRectangle(_canvasRect, screenPosition, null, out Vector2 local);
            Vector2 half = _canvasRect.rect.size * 0.5f;
            Vector2 margin = _menu.sizeDelta * 0.5f + new Vector2(8f, 8f);
            local.x = Mathf.Clamp(local.x, -half.x + margin.x, half.x - margin.x);
            local.y = Mathf.Clamp(local.y, -half.y + margin.y, half.y - margin.y);
            _menu.anchoredPosition = local;
        }

        public void Hide()
        {
            _moveAction = null;
            gameObject.SetActive(false);
        }

        private void HandleMoveClicked()
        {
            Action<GridPosition> action = _moveAction;
            GridPosition target = _targetCell;
            Debug.Log($"[HumanMove3G1R] Context menu Move clicked target={target}");
            action?.Invoke(target);
            Hide();
        }

        private static Button CreateButton(RectTransform parent, string label, Sprite sprite, Color color)
        {
            GameObject go = new GameObject("MoveButton", typeof(RectTransform), typeof(Image), typeof(Button));
            go.transform.SetParent(parent, false);
            Image image = go.GetComponent<Image>();
            image.sprite = sprite;
            image.type = sprite != null ? Image.Type.Sliced : Image.Type.Simple;
            image.color = color;

            Text text = new GameObject("Text", typeof(RectTransform), typeof(Text)).GetComponent<Text>();
            text.transform.SetParent(go.transform, false);
            text.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            text.fontSize = 16;
            text.fontStyle = FontStyle.Bold;
            text.alignment = TextAnchor.MiddleCenter;
            text.text = label;
            text.color = new Color(0.12f, 0.09f, 0.05f, 1f);
            text.raycastTarget = false;
            Stretch(text.rectTransform, Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);
            return go.GetComponent<Button>();
        }

        private static RectTransform CreateRect(string name, Transform parent)
        {
            GameObject go = new GameObject(name, typeof(RectTransform));
            go.transform.SetParent(parent, false);
            return go.GetComponent<RectTransform>();
        }

        private static void Stretch(RectTransform rect, Vector2 anchorMin, Vector2 anchorMax, Vector2 offsetMin, Vector2 offsetMax)
        {
            rect.anchorMin = anchorMin;
            rect.anchorMax = anchorMax;
            rect.offsetMin = offsetMin;
            rect.offsetMax = offsetMax;
        }
    }
}
