# VISUAL_2R_REPAIR_REPORT

Date: 2026-05-12
Project: UnityRTSPrototype
Stage: Visual-2R repair pass (presentation layer only)

## 1) Root cause of invisibility

Observed on both gameplay prefabs:
- Assets/Prefabs/Base.prefab
- Assets/Prefabs/Barracks.prefab

Root cause was twofold:
1. Fallback primitive root MeshRenderer had been disabled, so there was no guaranteed visible fallback.
2. Quaternius replacement was initially too small for scene readability (import scale/pivot mismatch), so visual child could appear effectively invisible in preview/scene.

## 2) What was repaired

### Gameplay prefab repair

For Assets/Prefabs/Base.prefab:
- VisualRoot exists and remains in place.
- Visual child now bound as FBX prefab instance under VisualRoot:
  - child name: Visual_TownCenter_Model
  - source: Assets/Art/Quaternius/UltimateFantasyRTS/FBX/TownCenter_FirstAge_Level1.fbx
- Child transform adjusted (visual-only):
  - localPosition: (0, 0, 0)
  - localRotation: (0, 0, 0)
  - localScale: (120, 120, 120)
- Root fallback MeshRenderer: ENABLED (safety fallback).

For Assets/Prefabs/Barracks.prefab:
- VisualRoot exists and remains in place.
- Visual child now bound as FBX prefab instance under VisualRoot:
  - child name: Visual_Barracks_Model
  - source: Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Barracks_FirstAge_Level1.fbx
- Child transform adjusted (visual-only):
  - localPosition: (0, 0, 0)
  - localRotation: (0, 0, 0)
  - localScale: (120, 120, 120)
- Root fallback MeshRenderer: ENABLED (safety fallback).

### Visual-only prefab repair

Updated visual-only prefabs to use FBX prefab-instance children (not fragile hand-built single mesh hookup), no gameplay scripts/colliders:
- Assets/Art/Prefabs/Visuals/Visual_Base_TownCenter.prefab
  - child: Model_TownCenter, scale (120,120,120)
- Assets/Art/Prefabs/Visuals/Visual_Barracks.prefab
  - child: Model_Barracks, scale (120,120,120)
- Assets/Art/Prefabs/Visuals/Visual_Resource_Gold.prefab
  - child: Model_Gold, scale (140,140,140)
- Assets/Art/Prefabs/Visuals/Visual_Resource_Rock.prefab
  - child: Model_Rock, scale (140,140,140)
- Assets/Art/Prefabs/Visuals/Visual_Resource_Tree.prefab
  - child: Model_Tree, scale (130,130,130)

## 3) Renderer diagnostics summary

Gameplay prefabs:
- Base:
  - VisualRoot found: yes
  - Quaternius child found: yes
  - Renderer under Quaternius child: present and enabled
  - Mesh assignment: present (shared mesh not null)
  - Materials: present (shared materials not null)
  - Child activeSelf: true
- Barracks:
  - VisualRoot found: yes
  - Quaternius child found: yes
  - Renderer under Quaternius child: present and enabled
  - Mesh assignment: present (shared mesh not null)
  - Materials: present (shared materials not null)
  - Child activeSelf: true

Visual-only prefabs:
- All 5 visual-only prefabs have active renderer + non-null mesh + non-null materials.
- No gameplay scripts added.
- No gameplay colliders added.

## 4) Fallback status (explicit)

- Base root MeshRenderer: ENABLED
- Barracks root MeshRenderer: ENABLED

Policy applied:
- Fallback primitive remains enabled until Quaternius visibility is confidently validated in dedicated visual checks.

## 5) VisualPreview scene

Created:
- Assets/Scenes/VisualPreview.unity

Scene content includes:
- Visual_Base_TownCenter
- Visual_Barracks
- Visual_Resource_Gold
- Visual_Resource_Rock
- Visual_Resource_Tree
- Base instance (for gameplay prefab visual-layer check)
- Barracks instance (for gameplay prefab visual-layer check)

## 6) Validation results

- Unity compile check: requested and completed without script compile errors.
- Prefab hierarchy check: passed for Base/Barracks (VisualRoot + visual child present).
- Visual renderer presence check: passed for gameplay and visual-only prefabs.
- Play mode smoke: entered play mode and exited successfully; no gameplay/AI contract changes were introduced.
- Console note observed: transient MCP websocket warning during tool reconnect after play toggle (editor tooling warning, not gameplay/runtime regression).

## 7) Hard safety guarantees kept

Not changed:
- MatchManager
- ActionApplier
- ActionDecoder
- ActionMaskBuilder
- ObservationBuilder
- GridManager occupancy logic
- UnitFactory spawn semantics
- UnitRegistry registration semantics
- ML-Agents/Python training code
- inference bridge/runtime command semantics
- gameplay colliders/occupancy behavior
- gameplay root scripts on Base/Barracks

## 8) Changed files

- Assets/Prefabs/Base.prefab
- Assets/Prefabs/Barracks.prefab
- Assets/Art/Prefabs/Visuals/Visual_Base_TownCenter.prefab
- Assets/Art/Prefabs/Visuals/Visual_Barracks.prefab
- Assets/Art/Prefabs/Visuals/Visual_Resource_Gold.prefab
- Assets/Art/Prefabs/Visuals/Visual_Resource_Rock.prefab
- Assets/Art/Prefabs/Visuals/Visual_Resource_Tree.prefab
- Assets/Scenes/VisualPreview.unity
- Assets/Scripts/Editor/Visual2RRepairPassMenu.cs
- VISUAL_2R_REPAIR_REPORT.md
