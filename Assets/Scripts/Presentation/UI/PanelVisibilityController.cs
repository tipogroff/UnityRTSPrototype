using UnityEngine;

namespace RTS.Presentation.UI
{
    public sealed class PanelVisibilityController : MonoBehaviour
    {
        [SerializeField] private GameObject _target;
        [SerializeField] private bool _visible = true;

        public bool IsVisible => _target != null ? _target.activeSelf : _visible;

        public void Initialize(GameObject target, bool visible)
        {
            _target = target;
            SetVisible(visible);
        }

        public void Toggle()
        {
            SetVisible(!IsVisible);
        }

        public void SetVisible(bool visible)
        {
            _visible = visible;
            if (_target != null)
            {
                _target.SetActive(visible);
            }
        }
    }
}
