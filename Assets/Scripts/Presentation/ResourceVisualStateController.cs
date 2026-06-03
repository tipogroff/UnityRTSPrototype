using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.Presentation
{
    [DisallowMultipleComponent]
    public sealed class ResourceVisualStateController : MonoBehaviour
    {
        [SerializeField, Min(0.05f)] private float _refreshInterval = 0.25f;
        [SerializeField] private Color _activeColor = Color.white;
        [SerializeField] private Color _exhaustedColor = new Color(0.45f, 0.45f, 0.45f, 1f);
        [SerializeField] private string _exhaustedLabelText = "Exhausted";
        [SerializeField] private Vector3 _labelOffset = new Vector3(0f, 1.6f, 0f);

        private readonly List<UnitRuntime> _scratchResources = new List<UnitRuntime>();
        private MaterialPropertyBlock _materialPropertyBlock;

        private UnitRegistry _unitRegistry;
        private ResourceManager _resourceManager;
        private float _nextRefreshTime;

        private static readonly int ColorPropertyId = Shader.PropertyToID("_Color");

        private void OnEnable()
        {
            ResolveReferences();
            EnsurePropertyBlock();
            RefreshVisualStates();
        }

        private void Update()
        {
            if (Time.unscaledTime < _nextRefreshTime)
            {
                return;
            }

            _nextRefreshTime = Time.unscaledTime + _refreshInterval;
            RefreshVisualStates();
        }

        private void RefreshVisualStates()
        {
            ResolveReferences();
            if (_unitRegistry == null || _resourceManager == null)
            {
                return;
            }

            _scratchResources.Clear();
            IReadOnlyList<UnitRuntime> allUnits = _unitRegistry.GetAllUnitsReadOnly();
            for (int i = 0; i < allUnits.Count; i++)
            {
                UnitRuntime unit = allUnits[i];
                if (unit == null || unit.Type != UnitType.Resource || !unit.gameObject.activeInHierarchy)
                {
                    continue;
                }

                _scratchResources.Add(unit);
            }

            for (int i = 0; i < _scratchResources.Count; i++)
            {
                UnitRuntime resourceUnit = _scratchResources[i];
                ResourceNode node = _resourceManager.GetResourceNode(resourceUnit.GridPos);
                bool exhausted = node != null && node.IsExhausted;
                ApplyResourceTint(resourceUnit, exhausted ? _exhaustedColor : _activeColor);
                ApplyResourceLabel(resourceUnit, exhausted);
            }
        }

        private void ApplyResourceTint(UnitRuntime resourceUnit, Color tint)
        {
            EnsurePropertyBlock();
            Renderer[] renderers = resourceUnit.GetComponentsInChildren<Renderer>(includeInactive: false);
            for (int i = 0; i < renderers.Length; i++)
            {
                Renderer renderer = renderers[i];
                if (renderer == null)
                {
                    continue;
                }

                renderer.GetPropertyBlock(_materialPropertyBlock);
                _materialPropertyBlock.SetColor(ColorPropertyId, tint);
                renderer.SetPropertyBlock(_materialPropertyBlock);
            }
        }

        private void EnsurePropertyBlock()
        {
            _materialPropertyBlock ??= new MaterialPropertyBlock();
        }

        private void ApplyResourceLabel(UnitRuntime resourceUnit, bool exhausted)
        {
            Transform labelTransform = resourceUnit.transform.Find("ExhaustedLabel");
            TextMesh label = labelTransform != null ? labelTransform.GetComponent<TextMesh>() : null;
            if (label == null)
            {
                GameObject labelObject = new GameObject("ExhaustedLabel");
                labelObject.transform.SetParent(resourceUnit.transform, false);
                labelObject.transform.localPosition = _labelOffset;
                label = labelObject.AddComponent<TextMesh>();
                label.anchor = TextAnchor.MiddleCenter;
                label.alignment = TextAlignment.Center;
                label.characterSize = 0.12f;
                label.fontSize = 32;
                label.color = new Color(1f, 0.88f, 0.55f, 1f);
            }

            label.gameObject.SetActive(exhausted);
            if (!exhausted)
            {
                return;
            }

            label.text = _exhaustedLabelText;
        }

        private void ResolveReferences()
        {
            _unitRegistry ??= UnitRegistry.Instance != null ? UnitRegistry.Instance : FindFirstObjectByType<UnitRegistry>();
            _resourceManager ??= ResourceManager.Instance != null ? ResourceManager.Instance : FindFirstObjectByType<ResourceManager>();
        }
    }
}
