using System.Collections.Generic;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.Presentation.Selection
{
    [DisallowMultipleComponent]
    public sealed class SelectionMarkerController : MonoBehaviour
    {
        [SerializeField] private Color _markerColor = new Color(0.1f, 0.9f, 0.2f, 0.55f);
        [SerializeField] private Color _primaryMarkerColor = new Color(1f, 0.85f, 0.2f, 0.7f);
        [SerializeField] private Vector3 _markerScale = new Vector3(0.85f, 0.035f, 0.85f);
        [SerializeField] private Vector3 _primaryMarkerScale = new Vector3(1.08f, 0.04f, 1.08f);
        [SerializeField] private float _markerYOffset = 0.035f;

        private readonly Dictionary<UnitRuntime, GameObject> _markers = new Dictionary<UnitRuntime, GameObject>();
        private Material _markerMaterial;
        private Material _primaryMarkerMaterial;

        public void SetSelection(IReadOnlyList<UnitRuntime> selectedUnits, UnitRuntime primary)
        {
            HashSet<UnitRuntime> wanted = new HashSet<UnitRuntime>();
            if (selectedUnits != null)
            {
                for (int i = 0; i < selectedUnits.Count; i++)
                {
                    UnitRuntime unit = selectedUnits[i];
                    if (unit == null)
                    {
                        continue;
                    }

                    wanted.Add(unit);
                    GameObject marker = EnsureMarker(unit);
                    ApplyMarkerVisual(marker, unit == primary);
                    SetPresenterState(unit, selected: true, primary: unit == primary);
                }
            }

            List<UnitRuntime> toRemove = new List<UnitRuntime>();
            foreach (KeyValuePair<UnitRuntime, GameObject> pair in _markers)
            {
                if (pair.Key == null || !wanted.Contains(pair.Key))
                {
                    toRemove.Add(pair.Key);
                }
            }

            for (int i = 0; i < toRemove.Count; i++)
            {
                RemoveMarker(toRemove[i]);
            }
        }

        public void Clear()
        {
            List<UnitRuntime> units = new List<UnitRuntime>(_markers.Keys);
            for (int i = 0; i < units.Count; i++)
            {
                RemoveMarker(units[i]);
            }
        }

        private void LateUpdate()
        {
            List<UnitRuntime> invalid = null;
            foreach (KeyValuePair<UnitRuntime, GameObject> pair in _markers)
            {
                UnitRuntime unit = pair.Key;
                GameObject marker = pair.Value;
                if (unit == null || marker == null || !unit.IsAlive)
                {
                    invalid ??= new List<UnitRuntime>();
                    invalid.Add(unit);
                    continue;
                }

                Vector3 position = unit.transform.position;
                position.y += _markerYOffset;
                marker.transform.position = position;
            }

            if (invalid == null)
            {
                return;
            }

            for (int i = 0; i < invalid.Count; i++)
            {
                RemoveMarker(invalid[i]);
            }
        }

        private GameObject EnsureMarker(UnitRuntime unit)
        {
            if (_markers.TryGetValue(unit, out GameObject existing) && existing != null)
            {
                return existing;
            }

            GameObject marker = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            marker.name = "SelectionMarker_" + unit.name;
            marker.transform.SetParent(transform, false);
            int ignoreRaycastLayer = LayerMask.NameToLayer("Ignore Raycast");
            if (ignoreRaycastLayer >= 0)
            {
                marker.layer = ignoreRaycastLayer;
            }

            Collider markerCollider = marker.GetComponent<Collider>();
            if (markerCollider != null)
            {
                markerCollider.enabled = false;
            }

            _markers[unit] = marker;
            return marker;
        }

        private void ApplyMarkerVisual(GameObject marker, bool primary)
        {
            marker.transform.localScale = primary ? _primaryMarkerScale : _markerScale;
            Renderer markerRenderer = marker.GetComponent<Renderer>();
            if (markerRenderer == null)
            {
                return;
            }

            markerRenderer.sharedMaterial = primary ? GetPrimaryMaterial() : GetMarkerMaterial();
        }

        private Material GetMarkerMaterial()
        {
            if (_markerMaterial == null)
            {
                _markerMaterial = CreateMarkerMaterial(_markerColor);
            }

            return _markerMaterial;
        }

        private Material GetPrimaryMaterial()
        {
            if (_primaryMarkerMaterial == null)
            {
                _primaryMarkerMaterial = CreateMarkerMaterial(_primaryMarkerColor);
            }

            return _primaryMarkerMaterial;
        }

        private static Material CreateMarkerMaterial(Color color)
        {
            Material material = new Material(Shader.Find("Standard"));
            material.color = color;
            return material;
        }

        private void RemoveMarker(UnitRuntime unit)
        {
            if (unit != null)
            {
                SetPresenterState(unit, selected: false, primary: false);
            }

            if (_markers.TryGetValue(unit, out GameObject marker) && marker != null)
            {
                Destroy(marker);
            }

            _markers.Remove(unit);
        }

        private static void SetPresenterState(UnitRuntime unit, bool selected, bool primary)
        {
            if (unit == null)
            {
                return;
            }

            SelectableUnitPresenter presenter = unit.GetComponent<SelectableUnitPresenter>();
            if (presenter == null)
            {
                presenter = unit.gameObject.AddComponent<SelectableUnitPresenter>();
            }

            presenter.SetSelectionState(selected, primary);
        }

        private void OnDestroy()
        {
            Clear();
            if (_markerMaterial != null)
            {
                Destroy(_markerMaterial);
            }

            if (_primaryMarkerMaterial != null)
            {
                Destroy(_primaryMarkerMaterial);
            }
        }
    }
}
