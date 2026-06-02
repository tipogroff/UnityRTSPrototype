# VISUAL_3C_CHARACTER_BINDING_REPORT

## Scope
Visual-3C выполнен как presentation-only слой:
- привязка выбранных character visuals к существующим gameplay prefab через VisualRoot;
- подготовка отдельной линейки final visual prefab;
- без изменений gameplay/AI/runtime/training semantics.

## Final Role Mapping
- Worker -> Preview_Casual_Male -> FBX Casual_Male
- Light -> Preview_Viking_Male -> FBX Viking_Male
- Heavy -> Preview_Knight_Male -> FBX Knight_Male
- Ranged -> Preview_Wizard -> FBX Wizard

## Final Visual Prefabs Created
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Worker_Casual_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Light_Viking_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Heavy_Knight_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Ranged_Wizard.prefab

All final prefabs are visual-only prefab roots with FBX visual child instance. They do not include UnitRuntime, MatchManager, GridManager refs, Rigidbody, gameplay colliders, or AI components.

## Final Transform Snapshot
Values inherited from Visual-3B selection and preserved in final prefabs via FBX child overrides.

- Worker / Casual_Male:
  - child local scale: 0.4575965, 0.4575965, 0.4575965
  - child local rotation: 0, 180, 0 (quaternion y=1, w~0)
- Light / Viking_Male:
  - child local scale: 0.37704855, 0.37704855, 0.37704855
  - child local rotation: 0, 180, 0
- Heavy / Knight_Male:
  - child local scale: 0.42839837, 0.42839837, 0.42839837
  - child local rotation: 0, 180, 0
- Ranged / Wizard:
  - child local scale: 0.37262064, 0.37262064, 0.37262064
  - child local rotation: 0, 180, 0

## Gameplay Prefab Binding Changes
### Worker
- Modified: Assets/Prefabs/Worker.prefab
- Existing VisualRoot reused.
- Added child visual instance under VisualRoot:
  - Visual_Worker_Casual_Male_Model
  - source: Visual_Worker_Casual_Male.prefab
- Root placeholder MeshRenderer disabled after binding wiring:
  - Worker root MeshRenderer m_Enabled: 1 -> 0
- Root transform, root colliders, and gameplay components preserved.

### Heavy
- Modified: Assets/Prefabs/Heavy.prefab
- Existing VisualRoot reused.
- Added child visual instance under VisualRoot:
  - Visual_Heavy_Knight_Male_Model
  - source: Visual_Heavy_Knight_Male.prefab
- Root placeholder MeshRenderer disabled:
  - Heavy root MeshRenderer m_Enabled: 1 -> 0
- Root transform, root colliders, and gameplay components preserved.

### Ranged
- Modified: Assets/Prefabs/Ranged.prefab
- Existing VisualRoot reused.
- Added child visual instance under VisualRoot:
  - Visual_Ranged_Wizard_Model
  - source: Visual_Ranged_Wizard.prefab
- Root placeholder MeshRenderer disabled:
  - Ranged root MeshRenderer m_Enabled: 1 -> 0
- Root transform, root colliders, and gameplay components preserved.

### Light (Safe Handling)
- Check result: Assets/Prefabs/Light.prefab is missing.
- No gameplay Light prefab was created.
- Final Light visual prefab was prepared only:
  - Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Light_Viking_Male.prefab
- Explicit status:
  - Light gameplay prefab is missing; final Light visual prepared but gameplay binding skipped.

## Owner Material Readiness
- UnitVisualAnimator exists in codebase (Assets/Scripts/Presentation/UnitVisualAnimator.cs).
- On modified gameplay prefabs (Worker/Heavy/Ranged), UnitVisualAnimator is not present.
- No new UnitVisualAnimator was injected in Visual-3C to avoid introducing runtime presentation behavior changes in this stage.
- Materials confirmed present:
  - Assets/Art/Materials/Player1_Blue.mat
  - Assets/Art/Materials/Player2_Red.mat
- Limitation:
  - owner recolor wiring for these bound visuals remains pending until/if UnitVisualAnimator is attached via an agreed presentation pass.

## VisualPreview Update
- Modified: Assets/Scenes/VisualPreview.unity
- Added new root group:
  - FinalCharacterSelection
- Added instances:
  - Final_Worker_Casual_Male
  - Final_Light_Viking_Male
  - Final_Heavy_Knight_Male
  - Final_Ranged_Wizard
- Group placed near scene preview area for scale comparison.

## Validation
- Unity refresh + compile request: executed.
- Console error check after refresh: 0 errors.
- Play Mode smoke: enter successful, stop state confirmed.
- Prefab hierarchy checks:
  - Worker/Heavy/Ranged contain VisualRoot child visual instance.
  - Root placeholder MeshRenderer disabled on Worker/Heavy/Ranged.
- Light check:
  - gameplay binding skipped (missing Light.prefab), final visual prepared.
- Collider and root safety checks:
  - no new gameplay colliders added under visual children.
  - root colliders preserved.
  - root transforms preserved.
- Renderer/material visibility status:
  - final visuals are FBX-driven visual prefab instances with assigned renderer materials from imported assets.
  - no console errors indicating missing materials/shaders.
- No-magenta check:
  - no magenta artifacts observed in captured validation images.

## Validation Screenshots
- Assets/Screenshots/Visual_3C_FinalCharacterSelection_01.png
- Assets/Screenshots/Visual_3C_FinalCharacterSelection_02_framed.png
- Assets/Screenshots/Visual_3C_Week7_Gameplay_01.png

## Changed Files
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Worker_Casual_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Worker_Casual_Male.prefab.meta
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Light_Viking_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Light_Viking_Male.prefab.meta
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Heavy_Knight_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Heavy_Knight_Male.prefab.meta
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Ranged_Wizard.prefab
- Assets/Art/Prefabs/Visuals/Characters/Final/Visual_Ranged_Wizard.prefab.meta
- Assets/Prefabs/Worker.prefab
- Assets/Prefabs/Heavy.prefab
- Assets/Prefabs/Ranged.prefab
- Assets/Scenes/VisualPreview.unity
- Assets/Screenshots/Visual_3C_FinalCharacterSelection_01.png
- Assets/Screenshots/Visual_3C_FinalCharacterSelection_02_framed.png
- Assets/Screenshots/Visual_3C_Week7_Gameplay_01.png

## Non-Changes Confirmation
The following were not modified in this stage:
- MatchManager
- ActionApplier
- ActionDecoder
- ActionMaskBuilder
- ObservationBuilder
- GridManager occupancy logic
- UnitFactory spawn semantics
- UnitRegistry registration semantics
- ResourceManager / ResourceNode gameplay semantics
- ML-Agents training code
- Python BC/PPO/training scripts
- checkpoint paths / inference bridge / runtime command semantics
- map coordinate system and logical map size 24x24
- Base.prefab
- Barracks.prefab
- Resource.prefab
