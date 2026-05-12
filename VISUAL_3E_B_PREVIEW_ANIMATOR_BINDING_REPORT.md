# VISUAL_3E_B_PREVIEW_ANIMATOR_BINDING_REPORT

Generated (UTC): 2026-05-12T06:31:01.8389168Z

## Scope
- Stage: Visual-3E-B (preview-only animator binding test)
- Gameplay prefab edits: none
- Runtime gameplay wiring edits: none

## Preview Assets Created
- Controllers:
  - Assets/Art/AnimatorControllers/Preview/Preview_Worker_Animator.controller
  - Assets/Art/AnimatorControllers/Preview/Preview_Light_Animator.controller
  - Assets/Art/AnimatorControllers/Preview/Preview_Heavy_Animator.controller
  - Assets/Art/AnimatorControllers/Preview/Preview_Ranged_Animator.controller
- Preview prefabs:
  - Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Worker_Casual_Male.prefab
  - Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Light_Viking_Male.prefab
  - Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Heavy_Knight_Male.prefab
  - Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Ranged_Wizard.prefab
- Preview scene: Assets/Scenes/AnimationPreview.unity

## Embedded Clip Inventory
### Worker - Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Casual_Male.fbx
| Clip | Length | Loop | Plausible Mapping |
|---|---|---|---|
| CharacterArmature|Death | 2.292 | no | Death |
| CharacterArmature|Defeat | 2.500 | no | Other |
| CharacterArmature|Idle | 4.167 | no | Idle |
| CharacterArmature|Jump | 1.042 | no | Other |
| CharacterArmature|PickUp | 1.250 | no | Harvest/Work-like |
| CharacterArmature|Punch | 0.750 | no | Attack |
| CharacterArmature|RecieveHit | 0.625 | no | Hit |
| CharacterArmature|Roll | 0.917 | no | Other |
| CharacterArmature|Run | 0.875 | no | Walk |
| CharacterArmature|Run_Carry | 0.875 | no | Walk |
| CharacterArmature|Shoot_OneHanded | 0.542 | no | Attack |
| CharacterArmature|SitDown | 0.958 | no | Other |
| CharacterArmature|StandUp | 1.292 | no | Other |
| CharacterArmature|SwordSlash | 1.042 | no | Attack |
| CharacterArmature|Victory | 1.875 | no | Other |
| CharacterArmature|Walk | 1.250 | no | Walk |
| CharacterArmature|Walk_Carry | 1.250 | no | Walk |

| Tested State | Source Clip | Result | Changed Transforms | Matching Bindings | Notes |
|---|---|---|---|---|---|
| Attack | CharacterArmature|Punch | WORK | 20 | 24 | Driven transforms detected and renderer/material state remained stable. |
| Death | CharacterArmature|Death | WORK | 18 | 24 | Driven transforms detected and renderer/material state remained stable. |
| HarvestFallback | CharacterArmature|PickUp | WORK | 18 | 24 | Driven transforms detected and renderer/material state remained stable. |
| Idle | CharacterArmature|Idle | WORK | 18 | 24 | Driven transforms detected and renderer/material state remained stable. |
| Walk | CharacterArmature|Walk | WORK | 17 | 24 | Driven transforms detected and renderer/material state remained stable. |

### Light - Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Viking_Male.fbx
| Clip | Length | Loop | Plausible Mapping |
|---|---|---|---|
| CharacterArmature|Death | 2.292 | no | Death |
| CharacterArmature|Defeat | 2.500 | no | Other |
| CharacterArmature|Idle | 4.167 | no | Idle |
| CharacterArmature|Jump | 1.042 | no | Other |
| CharacterArmature|PickUp | 1.250 | no | Harvest/Work-like |
| CharacterArmature|Punch | 0.750 | no | Attack |
| CharacterArmature|RecieveHit | 0.625 | no | Hit |
| CharacterArmature|Roll | 0.917 | no | Other |
| CharacterArmature|Run | 0.875 | no | Walk |
| CharacterArmature|Run_Carry | 0.875 | no | Walk |
| CharacterArmature|Shoot_OneHanded | 0.542 | no | Attack |
| CharacterArmature|SitDown | 0.958 | no | Other |
| CharacterArmature|StandUp | 1.292 | no | Other |
| CharacterArmature|SwordSlash | 1.042 | no | Attack |
| CharacterArmature|Victory | 1.875 | no | Other |
| CharacterArmature|Walk | 1.250 | no | Walk |
| CharacterArmature|Walk_Carry | 1.250 | no | Walk |

| Tested State | Source Clip | Result | Changed Transforms | Matching Bindings | Notes |
|---|---|---|---|---|---|
| Attack | CharacterArmature|SwordSlash | WORK | 17 | 24 | Driven transforms detected and renderer/material state remained stable. |
| Death | CharacterArmature|Death | WORK | 18 | 24 | Driven transforms detected and renderer/material state remained stable. |
| HarvestFallback | CharacterArmature|PickUp | WORK | 18 | 24 | Driven transforms detected and renderer/material state remained stable. |
| Idle | CharacterArmature|Idle | WORK | 18 | 24 | Driven transforms detected and renderer/material state remained stable. |
| Walk | CharacterArmature|Walk | WORK | 17 | 24 | Driven transforms detected and renderer/material state remained stable. |

### Heavy - Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Knight_Male.fbx
| Clip | Length | Loop | Plausible Mapping |
|---|---|---|---|
| CharacterArmature|Death | 2.292 | no | Death |
| CharacterArmature|Defeat | 2.500 | no | Other |
| CharacterArmature|Idle | 4.167 | no | Idle |
| CharacterArmature|Jump | 1.042 | no | Other |
| CharacterArmature|PickUp | 1.250 | no | Harvest/Work-like |
| CharacterArmature|Punch | 0.750 | no | Attack |
| CharacterArmature|RecieveHit | 0.625 | no | Hit |
| CharacterArmature|Roll | 0.917 | no | Other |
| CharacterArmature|Run | 0.875 | no | Walk |
| CharacterArmature|Run_Carry | 0.875 | no | Walk |
| CharacterArmature|Shoot_OneHanded | 0.542 | no | Attack |
| CharacterArmature|SitDown | 0.958 | no | Other |
| CharacterArmature|StandUp | 1.292 | no | Other |
| CharacterArmature|SwordSlash | 1.042 | no | Attack |
| CharacterArmature|Victory | 1.875 | no | Other |
| CharacterArmature|Walk | 1.250 | no | Walk |
| CharacterArmature|Walk_Carry | 1.250 | no | Walk |

| Tested State | Source Clip | Result | Changed Transforms | Matching Bindings | Notes |
|---|---|---|---|---|---|
| Attack | CharacterArmature|SwordSlash | WORK | 17 | 24 | Driven transforms detected and renderer/material state remained stable. |
| Death | CharacterArmature|Death | WORK | 18 | 24 | Driven transforms detected and renderer/material state remained stable. |
| HarvestFallback | CharacterArmature|PickUp | WORK | 18 | 24 | Driven transforms detected and renderer/material state remained stable. |
| Idle | CharacterArmature|Idle | WORK | 18 | 24 | Driven transforms detected and renderer/material state remained stable. |
| Walk | CharacterArmature|Walk | WORK | 17 | 24 | Driven transforms detected and renderer/material state remained stable. |

### Ranged - Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Wizard.fbx
| Clip | Length | Loop | Plausible Mapping |
|---|---|---|---|
| CharacterArmature|Death | 2.292 | no | Death |
| CharacterArmature|Defeat | 2.500 | no | Other |
| CharacterArmature|Idle | 4.167 | no | Idle |
| CharacterArmature|Jump | 1.042 | no | Other |
| CharacterArmature|PickUp | 1.250 | no | Harvest/Work-like |
| CharacterArmature|Punch | 0.750 | no | Attack |
| CharacterArmature|RecieveHit | 0.625 | no | Hit |
| CharacterArmature|Roll | 0.917 | no | Other |
| CharacterArmature|Run | 0.875 | no | Walk |
| CharacterArmature|Run_Carry | 0.875 | no | Walk |
| CharacterArmature|Shoot_OneHanded | 0.542 | no | Attack |
| CharacterArmature|SitDown | 0.958 | no | Other |
| CharacterArmature|StandUp | 1.292 | no | Other |
| CharacterArmature|SwordSlash | 1.042 | no | Attack |
| CharacterArmature|Victory | 1.875 | no | Other |
| CharacterArmature|Walk | 1.250 | no | Walk |
| CharacterArmature|Walk_Carry | 1.250 | no | Walk |

| Tested State | Source Clip | Result | Changed Transforms | Matching Bindings | Notes |
|---|---|---|---|---|---|
| Attack | CharacterArmature|Shoot_OneHanded | WORK | 16 | 24 | Driven transforms detected and renderer/material state remained stable. |
| Death | CharacterArmature|Death | WORK | 18 | 24 | Driven transforms detected and renderer/material state remained stable. |
| HarvestFallback | CharacterArmature|PickUp | WORK | 18 | 24 | Driven transforms detected and renderer/material state remained stable. |
| Idle | CharacterArmature|Idle | WORK | 18 | 24 | Driven transforms detected and renderer/material state remained stable. |
| Walk | CharacterArmature|Walk | WORK | 17 | 24 | Driven transforms detected and renderer/material state remained stable. |

## UAL Candidate Clips Tested
| State | UAL Clip | Result | Changed Transforms | Matching Bindings | Notes |
|---|---|---|---|---|---|
| Attack | Armature|Sword_Attack | FAIL | 0 | 0 | No compatible binding paths detected. No driven transforms detected during sampling. |
| Death | Armature|Death01 | FAIL | 0 | 0 | No compatible binding paths detected. No driven transforms detected during sampling. |
| HarvestFallback | Armature|Fixing_Kneeling | FAIL | 0 | 0 | No compatible binding paths detected. No driven transforms detected during sampling. |
| Idle | Armature|Idle_Loop | FAIL | 0 | 0 | No compatible binding paths detected. No driven transforms detected during sampling. |
| Walk | Armature|Walk_Loop | FAIL | 0 | 0 | No compatible binding paths detected. No driven transforms detected during sampling. |

## UAL Generic Compatibility Result
- Target tested: Worker preview visual root (Casual_Male) as representative selected model.
- Result: FAIL
- Interpretation: no import setting changes were made; compatibility is evaluated strictly under current Generic rig/binding paths.

## Recommended Path For Visual-3E-C
- Recommended path: embedded clips only
- Rationale: embedded clips bind and animate on current preview models; UAL generic clips do not meet compatibility threshold under current import settings, so they are not safe for direct runtime use in 3E-C.

## Scene and Screenshot Evidence
- Scene: Assets/Scenes/AnimationPreview.unity
- Screenshots:
  - Assets/Screenshots/Visual_3E_B_AnimationPreview_IdleWalk.png
  - Assets/Screenshots/Visual_3E_B_AnimationPreview_AttackDeath.png
  - Assets/Screenshots/Visual_3E_B_AnimationPreview_AllCharacters.png
- Motion proof note: screenshots are pose snapshots; work/fail classification is backed by sampled transform deltas and binding-path compatibility checks.

## Changed Files
- Assets/Scripts/Presentation/AnimationPreviewController.cs
- Assets/Editor/Visual3EBPreviewAnimatorBindingBuilder.cs
- Assets/Art/AnimatorControllers/Preview/Preview_Worker_Animator.controller
- Assets/Art/AnimatorControllers/Preview/Preview_Light_Animator.controller
- Assets/Art/AnimatorControllers/Preview/Preview_Heavy_Animator.controller
- Assets/Art/AnimatorControllers/Preview/Preview_Ranged_Animator.controller
- Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Worker_Casual_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Light_Viking_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Heavy_Knight_Male.prefab
- Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Ranged_Wizard.prefab
- Assets/Scenes/AnimationPreview.unity
- Assets/Screenshots/Visual_3E_B_AnimationPreview_IdleWalk.png
- Assets/Screenshots/Visual_3E_B_AnimationPreview_AttackDeath.png
- Assets/Screenshots/Visual_3E_B_AnimationPreview_AllCharacters.png
- VISUAL_3E_B_PREVIEW_ANIMATOR_BINDING_REPORT.md

## Non-changed Guardrails
- MatchManager not modified.
- ActionApplier not modified.
- ActionDecoder not modified.
- ActionMaskBuilder not modified.
- ObservationBuilder not modified.
- GridManager occupancy logic not modified.
- UnitFactory / UnitRegistry not modified.
- ResourceManager / ResourceNode not modified.
- Gameplay prefabs Worker/Light/Heavy/Ranged not modified.
- UnitDef/GameConfig assets not modified.
- VisualEventBridge / UnitVisualAnimator / UnitFactory runtime wiring not modified.
- ML-Agents, Python training scripts, checkpoints and inference bridge not modified.