using RTS.Core;
using RTS.Gameplay;
using UnityEngine;
using UnityEngine.UI;

namespace RTS.Presentation.UI
{
    public sealed class ProductionPanelView : MonoBehaviour
    {
        private Text _title;
        private GameObject _baseGroup;
        private GameObject _barracksGroup;

        public void Initialize(Text title, GameObject baseGroup, GameObject barracksGroup)
        {
            _title = title;
            _baseGroup = baseGroup;
            _barracksGroup = barracksGroup;
        }

        public void Refresh(UnitRuntime selected)
        {
            bool isBase = selected != null && selected.Type == UnitType.Base;
            bool isBarracks = selected != null && selected.Type == UnitType.Barracks;

            if (_title != null)
            {
                _title.text = isBase ? "Base Production" : (isBarracks ? "Barracks Production" : "Production");
            }

            if (_baseGroup != null)
            {
                _baseGroup.SetActive(isBase);
            }

            if (_barracksGroup != null)
            {
                _barracksGroup.SetActive(isBarracks);
            }
        }
    }
}
