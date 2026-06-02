using UnityEngine;
using UnityEngine.UI;

namespace RTS.Presentation.Selection
{
    [DisallowMultipleComponent]
    public sealed class SelectionBoxView : MonoBehaviour
    {
        [SerializeField] private Color _fillColor = new Color(0.2f, 0.65f, 1f, 0.18f);
        [SerializeField] private Color _borderColor = new Color(0.55f, 0.85f, 1f, 0.9f);

        private RectTransform _root;
        private RectTransform _box;
        private RectTransform _parentRect;

        public void Initialize(RectTransform parentRect)
        {
            _parentRect = parentRect;
            EnsureBox();
            Hide();
        }

        public void Show(Vector2 startScreen, Vector2 currentScreen)
        {
            EnsureBox();
            if (_parentRect == null)
            {
                _parentRect = transform.parent as RectTransform;
            }

            if (_parentRect == null)
            {
                return;
            }

            RectTransformUtility.ScreenPointToLocalPointInRectangle(_parentRect, startScreen, null, out Vector2 startLocal);
            RectTransformUtility.ScreenPointToLocalPointInRectangle(_parentRect, currentScreen, null, out Vector2 currentLocal);
            Vector2 pivotOffset = new Vector2(
                _parentRect.rect.width * _parentRect.pivot.x,
                _parentRect.rect.height * _parentRect.pivot.y);
            startLocal += pivotOffset;
            currentLocal += pivotOffset;

            Vector2 min = Vector2.Min(startLocal, currentLocal);
            Vector2 max = Vector2.Max(startLocal, currentLocal);
            _box.gameObject.SetActive(true);
            _box.anchoredPosition = min;
            _box.sizeDelta = max - min;
        }

        public void Hide()
        {
            EnsureBox();
            _box.gameObject.SetActive(false);
        }

        private void EnsureBox()
        {
            if (_box != null)
            {
                return;
            }

            _root = GetComponent<RectTransform>();
            if (_root == null)
            {
                _root = gameObject.AddComponent<RectTransform>();
            }

            _parentRect = _parentRect != null ? _parentRect : transform.parent as RectTransform;

            GameObject boxObject = new GameObject("SelectionRectangle", typeof(RectTransform), typeof(Image), typeof(Outline));
            boxObject.transform.SetParent(transform, false);
            _box = boxObject.GetComponent<RectTransform>();
            _box.anchorMin = Vector2.zero;
            _box.anchorMax = Vector2.zero;
            _box.pivot = Vector2.zero;

            Image image = boxObject.GetComponent<Image>();
            image.color = _fillColor;
            image.raycastTarget = false;

            Outline outline = boxObject.GetComponent<Outline>();
            outline.effectColor = _borderColor;
            outline.effectDistance = new Vector2(2f, -2f);
        }
    }
}
