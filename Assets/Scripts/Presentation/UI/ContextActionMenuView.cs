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
        private Action<GridPosition> _buildBarracksAction;
        private Action<ResourceNode> _gatherAction;
        private Action<UnitRuntime> _attackAction;
        private GridPosition _targetCell;
        private ResourceNode _resource;
        private UnitRuntime _attackTarget;
        private Button _moveButton;
        private Button _buildBarracksButton;
        private Button _gatherButton;
        private Button _attackButton;

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
            _menu.sizeDelta = new Vector2(180f, 58f);
            Image panel = _menu.gameObject.AddComponent<Image>();
            panel.sprite = panelSprite;
            panel.type = panelSprite != null ? Image.Type.Sliced : Image.Type.Simple;
            panel.color = panelColor;

            _moveButton = CreateButton(_menu, "Move", buttonSprite, buttonColor);
            _moveButton.onClick.AddListener(HandleMoveClicked);
            _buildBarracksButton = CreateButton(_menu, "Build Barracks", buttonSprite, buttonColor);
            _buildBarracksButton.onClick.AddListener(HandleBuildBarracksClicked);
            _gatherButton = CreateButton(_menu, "Gather", buttonSprite, buttonColor);
            _gatherButton.onClick.AddListener(HandleGatherClicked);
            _attackButton = CreateButton(_menu, "Attack", buttonSprite, buttonColor);
            _attackButton.onClick.AddListener(HandleAttackClicked);
            gameObject.SetActive(false);
        }

        public void Show(
            Vector2 screenPosition,
            GridPosition targetCell,
            Action<GridPosition> moveAction,
            Action<GridPosition> buildBarracksAction = null)
        {
            ClearPendingActions();
            _targetCell = targetCell;
            _moveAction = moveAction;
            _buildBarracksAction = buildBarracksAction;
            SetVisibleActions(showMove: true, showBuildBarracks: buildBarracksAction != null, showGather: false, showAttack: false);
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

        public void ShowGather(Vector2 screenPosition, ResourceNode resource, Action<ResourceNode> gatherAction)
        {
            ClearPendingActions();
            _resource = resource;
            _gatherAction = gatherAction;
            SetVisibleActions(showMove: false, showBuildBarracks: false, showGather: true, showAttack: false);
            gameObject.SetActive(true);
            transform.SetAsLastSibling();

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

        public void ShowAttack(Vector2 screenPosition, UnitRuntime target, Action<UnitRuntime> attackAction)
        {
            ClearPendingActions();
            _attackTarget = target;
            _attackAction = attackAction;
            SetVisibleActions(showMove: false, showBuildBarracks: false, showGather: false, showAttack: true);
            gameObject.SetActive(true);
            transform.SetAsLastSibling();

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
            ClearPendingActions();
            gameObject.SetActive(false);
        }

        private void ClearPendingActions()
        {
            _moveAction = null;
            _buildBarracksAction = null;
            _gatherAction = null;
            _attackAction = null;
            _resource = null;
            _attackTarget = null;
        }

        private void HandleMoveClicked()
        {
            Action<GridPosition> action = _moveAction;
            GridPosition target = _targetCell;
            Debug.Log($"[HumanMove3G1R] Context menu Move clicked target={target}");
            action?.Invoke(target);
            Hide();
        }

        private void HandleGatherClicked()
        {
            Action<ResourceNode> action = _gatherAction;
            ResourceNode resource = _resource;
            action?.Invoke(resource);
            Hide();
        }

        private void HandleBuildBarracksClicked()
        {
            Action<GridPosition> action = _buildBarracksAction;
            GridPosition target = _targetCell;
            action?.Invoke(target);
            Hide();
        }

        private void HandleAttackClicked()
        {
            Action<UnitRuntime> action = _attackAction;
            UnitRuntime target = _attackTarget;
            action?.Invoke(target);
            Hide();
        }

        private void SetVisibleActions(bool showMove, bool showBuildBarracks, bool showGather, bool showAttack)
        {
            _moveButton?.gameObject.SetActive(showMove);
            _buildBarracksButton?.gameObject.SetActive(showBuildBarracks);
            _gatherButton?.gameObject.SetActive(showGather);
            _attackButton?.gameObject.SetActive(showAttack);

            int count = 0;
            LayoutVisibleButton(_moveButton, showMove, ref count);
            LayoutVisibleButton(_buildBarracksButton, showBuildBarracks, ref count);
            LayoutVisibleButton(_gatherButton, showGather, ref count);
            LayoutVisibleButton(_attackButton, showAttack, ref count);
            if (_menu != null)
            {
                _menu.sizeDelta = new Vector2(180f, count * 42f + 16f);
            }
        }

        private static void LayoutVisibleButton(Button button, bool visible, ref int index)
        {
            if (button == null || !visible)
            {
                return;
            }

            RectTransform rect = button.GetComponent<RectTransform>();
            rect.anchorMin = new Vector2(0f, 1f);
            rect.anchorMax = new Vector2(1f, 1f);
            rect.offsetMin = new Vector2(8f, -8f - (index + 1) * 42f);
            rect.offsetMax = new Vector2(-8f, -8f - index * 42f);
            index++;
        }

        private static Button CreateButton(RectTransform parent, string label, Sprite sprite, Color color)
        {
            GameObject go = new GameObject(label + "Button", typeof(RectTransform), typeof(Image), typeof(Button));
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
