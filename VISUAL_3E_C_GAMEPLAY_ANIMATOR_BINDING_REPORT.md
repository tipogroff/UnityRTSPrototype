# Visual-3E-C Gameplay Animator Binding with Embedded Clips

## Summary
- Embedded clips only were used because Visual-3E-B validated embedded FBX clips and rejected Universal Animation Library generic clips with 0 matching bindings / 0 driven transforms.
- Gameplay-facing Animator Controllers were created for Worker / Light / Heavy / Ranged under Assets/Art/AnimatorControllers/Gameplay.
- Gameplay prefabs were updated only in the visual layer. No gameplay root Animator was added.
- Existing presentation-only UnitVisualAnimator and VisualEventBridge hooks were reused. No gameplay/AI/training/observation/action semantics were changed.

## Controllers
- Worker: Assets/Art/AnimatorControllers/Gameplay/RTS_Worker_Animator.controller
- Light: Assets/Art/AnimatorControllers/Gameplay/RTS_Light_Animator.controller
- Heavy: Assets/Art/AnimatorControllers/Gameplay/RTS_Heavy_Animator.controller
- Ranged: Assets/Art/AnimatorControllers/Gameplay/RTS_Ranged_Animator.controller

## Prefab Binding
- Worker: prefab=Assets/Prefabs/Worker.prefab, animator target=Worker/VisualRoot/Visual_Worker_Casual_Male_Model, team marker stable=YES
- Light: prefab=Assets/Prefabs/Light.prefab, animator target=Light/VisualRoot/Visual_Light_Viking_Male_Model, team marker stable=YES
- Heavy: prefab=Assets/Prefabs/Heavy.prefab, animator target=Heavy/VisualRoot/Visual_Heavy_Knight_Male_Model, team marker stable=YES
- Ranged: prefab=Assets/Prefabs/Ranged.prefab, animator target=Ranged/VisualRoot/Visual_Ranged_Wizard_Model, team marker stable=YES

## Embedded Clip Mapping
- Worker: Idle=CharacterArmature|Idle, Walk=CharacterArmature|Walk, Attack=CharacterArmature|Punch, Harvest=CharacterArmature|PickUp, Death=CharacterArmature|Death
- Light: Idle=CharacterArmature|Idle, Walk=CharacterArmature|Walk, Attack=CharacterArmature|SwordSlash, Harvest=CharacterArmature|PickUp, Death=CharacterArmature|Death
- Heavy: Idle=CharacterArmature|Idle, Walk=CharacterArmature|Walk, Attack=CharacterArmature|SwordSlash, Harvest=CharacterArmature|PickUp, Death=CharacterArmature|Death
- Ranged: Idle=CharacterArmature|Idle, Walk=CharacterArmature|Walk, Attack=CharacterArmature|Shoot_OneHanded, Harvest=CharacterArmature|PickUp, Death=CharacterArmature|Death

## UnitVisualAnimator Integration
- UnitVisualAnimator already exposed SetMoving, PlayAttack, PlayHarvest, PlayDeath and PlayHit.
- VisualEventBridge already calls these presentation-only methods, so gameplay event trigger wiring did not require new runtime hooks in this stage.
- Animator serialized reference on UnitVisualAnimator was assigned on Worker / Light / Heavy / Ranged gameplay prefabs.

## Validation
- Validation result: PASS
- Validation markdown: Assets/Visual3EC_GameplayAnimatorValidation.md
- Validation json: Assets/Visual3EC_GameplayAnimatorValidation.json
- Validation scene: Assets/Scenes/Visual3EC_GameplayAnimatorValidation.unity
- Screenshot targets: Assets/Screenshots/Visual_3E_C_GameplayIdle_Week7.png, Assets/Screenshots/Visual_3E_C_AnimatorPrefabCheck.png, Assets/Screenshots/Visual_3E_C_OwnerColorStillCorrect.png

## Play Mode Smoke
- Validation scene entered Play Mode and screenshots were captured from Main Camera.
- Observed result: idle presentation animators rendered for Worker / Light / Heavy / Ranged without visible T-pose or magenta materials in the captured frame.
- Observed result: owner markers remained blue/red and visually stable at the unit feet in the captured frame.
- Manual attack/harvest trigger forcing was not executed in this pass; existing VisualEventBridge presentation hooks remain available for Visual-3E-D follow-up.

## Changed Files
- Assets/Editor/Visual3ECGameplayAnimatorValidator.cs
- Assets/Art/AnimatorControllers/Gameplay/RTS_Worker_Animator.controller
- Assets/Art/AnimatorControllers/Gameplay/RTS_Light_Animator.controller
- Assets/Art/AnimatorControllers/Gameplay/RTS_Heavy_Animator.controller
- Assets/Art/AnimatorControllers/Gameplay/RTS_Ranged_Animator.controller
- Assets/Prefabs/Worker.prefab
- Assets/Prefabs/Light.prefab
- Assets/Prefabs/Heavy.prefab
- Assets/Prefabs/Ranged.prefab
- Assets/Visual3EC_GameplayAnimatorValidation.md
- Assets/Visual3EC_GameplayAnimatorValidation.json
- VISUAL_3E_C_GAMEPLAY_ANIMATOR_BINDING_REPORT.md

## Guardrails
- Unchanged: MatchManager command semantics, ActionApplier, ActionDecoder, ActionMaskBuilder, ObservationBuilder, GridManager occupancy logic, UnitFactory spawn semantics, UnitRegistry registration semantics, ResourceManager / ResourceNode gameplay semantics, ML-Agents training code, Python BC/PPO scripts, checkpoint paths, inference bridge, map coordinate system, logical map size 24x24, Base/Barracks/Resource prefabs, UnitDef assets, GameConfig assets, owner color sync semantics, and visual scale/proportion compensation values.
