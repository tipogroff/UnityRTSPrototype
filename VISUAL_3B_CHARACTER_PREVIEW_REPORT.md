# VISUAL_3B_CHARACTER_PREVIEW_REPORT

## Scope and safety
- Stage completed as visual-only candidate preview for character selection.
- No final role assignment was made.
- No changes were made to gameplay prefabs:
  - Assets/Prefabs/Worker.prefab
  - Assets/Prefabs/Heavy.prefab
  - Assets/Prefabs/Ranged.prefab
  - Assets/Prefabs/Base.prefab
  - Assets/Prefabs/Barracks.prefab
  - Assets/Prefabs/Resource.prefab
- No gameplay/AI/runtime/training/Python/checkpoint/inference code paths were edited by this stage.

## Created candidate preview prefabs
### Worker
- Assets/Art/Prefabs/Visuals/Characters/Preview_Worker_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Worker_Female.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Casual_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Casual_Female.prefab

### Light
- Assets/Art/Prefabs/Visuals/Characters/Preview_Soldier_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Soldier_Female.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_BlueSoldier_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Ninja_Male.prefab

### Heavy
- Assets/Art/Prefabs/Visuals/Characters/Preview_Knight_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Knight_Golden_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Viking_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Goblin_Male.prefab

### Ranged
- Assets/Art/Prefabs/Visuals/Characters/Preview_Wizard.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Witch.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Elf.prefab

## FBX source mapping + final transform
All candidate preview prefabs reference FBX models from:
- Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/

| Group | FBX | Preview prefab | Final visual scale (x,y,z) | Final visual rotation (x,y,z) |
|---|---|---|---|---|
| Worker | Worker_Male.fbx | Preview_Worker_Male.prefab | 0.457, 0.457, 0.457 | 0, 180, 0 |
| Worker | Worker_Female.fbx | Preview_Worker_Female.prefab | 0.445, 0.445, 0.445 | 0, 180, 0 |
| Worker | Casual_Male.fbx | Preview_Casual_Male.prefab | 0.458, 0.458, 0.458 | 0, 180, 0 |
| Worker | Casual_Female.fbx | Preview_Casual_Female.prefab | 0.458, 0.458, 0.458 | 0, 180, 0 |
| Light | Soldier_Male.fbx | Preview_Soldier_Male.prefab | 0.461, 0.461, 0.461 | 0, 180, 0 |
| Light | Soldier_Female.fbx | Preview_Soldier_Female.prefab | 0.461, 0.461, 0.461 | 0, 180, 0 |
| Light | BlueSoldier_Male.fbx | Preview_BlueSoldier_Male.prefab | 0.461, 0.461, 0.461 | 0, 180, 0 |
| Light | Ninja_Male.fbx | Preview_Ninja_Male.prefab | 0.387, 0.387, 0.387 | 0, 180, 0 |
| Heavy | Knight_Male.fbx | Preview_Knight_Male.prefab | 0.428, 0.428, 0.428 | 0, 180, 0 |
| Heavy | Knight_Golden_Male.fbx | Preview_Knight_Golden_Male.prefab | 0.475, 0.475, 0.475 | 0, 180, 0 |
| Heavy | Viking_Male.fbx | Preview_Viking_Male.prefab | 0.377, 0.377, 0.377 | 0, 180, 0 |
| Heavy | Goblin_Male.fbx | Preview_Goblin_Male.prefab | 0.487, 0.487, 0.487 | 0, 180, 0 |
| Ranged | Wizard.fbx | Preview_Wizard.prefab | 0.373, 0.373, 0.373 | 0, 180, 0 |
| Ranged | Witch.fbx | Preview_Witch.prefab | 0.356, 0.356, 0.356 | 0, 180, 0 |
| Ranged | Elf.fbx | Preview_Elf.prefab | 0.373, 0.373, 0.373 | 0, 180, 0 |

## Renderer/visibility validation
- All 15 candidate prefabs were created successfully and are present in project.
- For each candidate, renderer+material validation passed during generation (renderer present, material assigned).
- No magenta/material breakage detected in generated pass.
- A URP-compatible fallback material was created for safety:
  - Assets/Art/Materials/Preview_URP_Lit_Default.mat
- Objects were normalized for preview visibility and footprint consistency.

## Scene integration (VisualPreview only)
Scene updated:
- Assets/Scenes/VisualPreview.unity

Added parent hierarchy:
- CharacterCandidatePreview
  - WorkerCandidates
  - LightCandidates
  - HeavyCandidates
  - RangedCandidates

Notes:
- Candidate objects are grouped in rows for side-by-side visual comparison.
- Grouping is visual-only and isolated to VisualPreview scene.
- No candidate characters were added to Week7 gameplay scene.

## Rig/avatar/clip observations
- This stage does not modify source FBX import assets.
- Candidate prefabs are visual wrappers around imported model assets.
- From prior import inventory context, no standalone Avatar/AnimationClip assets were introduced as separate files in this folder; any rig/animation data remains embedded in FBX importer context.
- No runtime animation wiring changes were made in gameplay prefabs.

## Recommendations for final role selection (visual)
- Worker shortlist:
  - Preferred: Worker_Male, Worker_Female
  - Alternate style: Casual_Male, Casual_Female
- Light shortlist:
  - Preferred: Soldier_Male, Soldier_Female
  - Alternate style: BlueSoldier_Male, Ninja_Male
- Heavy shortlist:
  - Preferred: Knight_Male, Knight_Golden_Male
  - Alternate style: Viking_Male, Goblin_Male
- Ranged shortlist:
  - Preferred: Wizard, Elf
  - Alternate style: Witch

## Validation screenshots
- Assets/Screenshots/Visual_3B_CharacterPreview_AllCandidates.png
- Assets/Screenshots/Visual_3B_CharacterPreview_WorkerLight.png
- Assets/Screenshots/Visual_3B_CharacterPreview_HeavyRanged.png

## Changed files (Visual-3B)
- Assets/Editor/Visual3BCharacterPreviewBuilder.cs
- Assets/Editor/Visual3BCharacterPreviewBuilder.cs.meta
- Assets/Art/Prefabs/Visuals/Characters.meta
- Assets/Art/Prefabs/Visuals/Characters/Preview_Worker_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Worker_Male.prefab.meta
- Assets/Art/Prefabs/Visuals/Characters/Preview_Worker_Female.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Worker_Female.prefab.meta
- Assets/Art/Prefabs/Visuals/Characters/Preview_Casual_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Casual_Male.prefab.meta
- Assets/Art/Prefabs/Visuals/Characters/Preview_Casual_Female.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Casual_Female.prefab.meta
- Assets/Art/Prefabs/Visuals/Characters/Preview_Soldier_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Soldier_Male.prefab.meta
- Assets/Art/Prefabs/Visuals/Characters/Preview_Soldier_Female.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Soldier_Female.prefab.meta
- Assets/Art/Prefabs/Visuals/Characters/Preview_BlueSoldier_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_BlueSoldier_Male.prefab.meta
- Assets/Art/Prefabs/Visuals/Characters/Preview_Ninja_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Ninja_Male.prefab.meta
- Assets/Art/Prefabs/Visuals/Characters/Preview_Knight_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Knight_Male.prefab.meta
- Assets/Art/Prefabs/Visuals/Characters/Preview_Knight_Golden_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Knight_Golden_Male.prefab.meta
- Assets/Art/Prefabs/Visuals/Characters/Preview_Viking_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Viking_Male.prefab.meta
- Assets/Art/Prefabs/Visuals/Characters/Preview_Goblin_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Goblin_Male.prefab.meta
- Assets/Art/Prefabs/Visuals/Characters/Preview_Wizard.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Wizard.prefab.meta
- Assets/Art/Prefabs/Visuals/Characters/Preview_Witch.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Witch.prefab.meta
- Assets/Art/Prefabs/Visuals/Characters/Preview_Elf.prefab
- Assets/Art/Prefabs/Visuals/Characters/Preview_Elf.prefab.meta
- Assets/Art/Materials/Preview_URP_Lit_Default.mat
- Assets/Art/Materials/Preview_URP_Lit_Default.mat.meta
- Assets/Scenes/VisualPreview.unity
- Assets/Screenshots/Visual_3B_CharacterPreview_AllCandidates.png
- Assets/Screenshots/Visual_3B_CharacterPreview_AllCandidates.png.meta
- Assets/Screenshots/Visual_3B_CharacterPreview_WorkerLight.png
- Assets/Screenshots/Visual_3B_CharacterPreview_WorkerLight.png.meta
- Assets/Screenshots/Visual_3B_CharacterPreview_HeavyRanged.png
- Assets/Screenshots/Visual_3B_CharacterPreview_HeavyRanged.png.meta
- VISUAL_3B_CHARACTER_PREVIEW_AUTOGEN_SUMMARY.md
- VISUAL_3B_CHARACTER_PREVIEW_REPORT.md
