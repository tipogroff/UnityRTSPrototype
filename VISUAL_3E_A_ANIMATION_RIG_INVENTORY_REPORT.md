# VISUAL_3E_A_ANIMATION_RIG_INVENTORY_REPORT

Generated (UTC): 2026-05-12T03:59:40.3028107Z
Unity: 6000.3.10f1

## Scope
- Stage: Visual-3E-A (inventory/readiness only)
- Runtime animation wiring changes: none
- Gameplay prefab edits: none

## Checked Asset Folders
- Assets/Art/Quaternius/UltimateAnimatedCharacterPack
- Assets/Art/Quaternius/UniversalAnimationLibrary

### Folder: Assets/Art/Quaternius/UltimateAnimatedCharacterPack
- FBX assets: 52
- Standalone AnimationClip assets (.anim): 0
- Avatar assets: 0
- FBX rig type distribution: Generic=52

### Folder: Assets/Art/Quaternius/UniversalAnimationLibrary
- FBX assets: 1
- Standalone AnimationClip assets (.anim): 0
- Avatar assets: 0
- FBX rig type distribution: Generic=1

## Selected Character Model Validation
| Role | Asset | SkinnedMeshRenderer | Bones | Embedded Clips | Rig Type | Humanoid Avatar | Retarget UAL | Import Warnings |
|---|---|---|---|---|---|---|---|---|
| Worker | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Casual_Male.fbx | yes (1) | yes (23) | 17 | Generic | no (unknown) | no | unknown |
| Light | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Viking_Male.fbx | yes (1) | yes (23) | 17 | Generic | no (unknown) | no | unknown |
| Heavy | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Knight_Male.fbx | yes (1) | yes (23) | 17 | Generic | no (unknown) | no | unknown |
| Ranged | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Wizard.fbx | yes (1) | yes (23) | 17 | Generic | no (unknown) | no | unknown |

## Universal Animation Library Inventory
- Primary asset: Assets/Art/Quaternius/UniversalAnimationLibrary/Unity/UAL1_Standard.fbx
- Rig type: Generic
- Humanoid avatar: no (unknown)
- Clip count: 45
- Import warnings: unknown
- Compatibility note: Humanoid retargeting is expected only when both source and target import as humanoid with valid avatars.

### UAL Clip Names
- Armature|A_TPose
- Armature|Crouch_Fwd_Loop
- Armature|Crouch_Idle_Loop
- Armature|Dance_Loop
- Armature|Death01
- Armature|Driving_Loop
- Armature|Fixing_Kneeling
- Armature|Hit_Chest
- Armature|Hit_Head
- Armature|Idle_Loop
- Armature|Idle_Talking_Loop
- Armature|Idle_Torch_Loop
- Armature|Interact
- Armature|Jog_Fwd_Loop
- Armature|Jump_Land
- Armature|Jump_Loop
- Armature|Jump_Start
- Armature|PickUp_Table
- Armature|Pistol_Aim_Down
- Armature|Pistol_Aim_Neutral
- Armature|Pistol_Aim_Up
- Armature|Pistol_Idle_Loop
- Armature|Pistol_Reload
- Armature|Pistol_Shoot
- Armature|Punch_Cross
- Armature|Punch_Jab
- Armature|Push_Loop
- Armature|Roll
- Armature|Roll_RM
- Armature|Sitting_Enter
- Armature|Sitting_Exit
- Armature|Sitting_Idle_Loop
- Armature|Sitting_Talking_Loop
- Armature|Spell_Simple_Enter
- Armature|Spell_Simple_Exit
- Armature|Spell_Simple_Idle_Loop
- Armature|Spell_Simple_Shoot
- Armature|Sprint_Loop
- Armature|Swim_Fwd_Loop
- Armature|Swim_Idle_Loop
- Armature|Sword_Attack
- Armature|Sword_Attack_RM
- Armature|Sword_Idle
- Armature|Walk_Formal_Loop
- Armature|Walk_Loop

## Candidate Mapping (Idle/Walk/Attack/Harvest/Death)
| Gameplay state | Candidate clips | Source asset | Confidence |
|---|---|---|---|
| Idle | UAL:Armature|Crouch_Idle_Loop; UAL:Armature|Idle_Loop; UAL:Armature|Idle_Talking_Loop; UAL:Armature|Idle_Torch_Loop; UAL:Armature|Pistol_Idle_Loop; UAL:Armature|Sitting_Idle_Loop; UAL:Armature|Spell_Simple_Idle_Loop; UAL:Armature|Swim_Idle_Loop | UAL | high |
- Notes (Idle): Keyword-based candidate list; verify exact semantics in Visual-3E-B preview pass.
| Walk | UAL:Armature|Jog_Fwd_Loop; UAL:Armature|Walk_Formal_Loop; UAL:Armature|Walk_Loop; CharacterPack:CharacterArmature|Run; CharacterPack:CharacterArmature|Run_Carry; CharacterPack:CharacterArmature|Walk; CharacterPack:CharacterArmature|Walk_Carry | UAL + CharacterPack | high |
- Notes (Walk): Keyword-based candidate list; verify exact semantics in Visual-3E-B preview pass.
| Attack | UAL:Armature|Hit_Chest; UAL:Armature|Hit_Head; UAL:Armature|Pistol_Shoot; UAL:Armature|Spell_Simple_Shoot; UAL:Armature|Sword_Attack; UAL:Armature|Sword_Attack_RM; CharacterPack:CharacterArmature|RecieveHit; CharacterPack:CharacterArmature|Shoot_OneHanded | UAL + CharacterPack | high |
- Notes (Attack): Keyword-based candidate list; verify exact semantics in Visual-3E-B preview pass.
| Harvest | (none) | none detected | low |
- Notes (Harvest): No explicit harvest clip keyword detected. Fallback candidate for Visual-3E-B: reuse melee/work-like clip or procedural/VFX visual placeholder.
| Death | UAL:Armature|Death01; CharacterPack:CharacterArmature|Death | UAL + CharacterPack | medium |
- Notes (Death): Keyword-based candidate list; verify exact semantics in Visual-3E-B preview pass.

## Visual-3E-B Options
### Option A: Use embedded clips from Ultimate Animated Character Pack.
- Pros:
  - Asset locality per character can simplify authoring.
  - Potential style consistency between mesh and source clip set.
- Risks:
  - Clip coverage may vary per FBX and produce uneven gameplay-state mapping.
  - Cross-character timing/style drift can increase blend tuning effort.
- Import settings to review in Visual-3E-B:
  - Verify Import Animation is enabled for selected character FBX files.
  - Standardize loop settings for locomotion clips where needed.
  - Confirm consistent rig type across selected role models.
- Gameplay prefabs expected to be touched in Visual-3E-B:
  - Worker.prefab
  - Light.prefab
  - Heavy.prefab
  - Ranged.prefab
### Option B: Use Universal Animation Library clips through humanoid retargeting.
- Pros:
  - Centralized clip library may improve consistency and maintenance.
  - Easier to extend with additional states from one source.
- Risks:
  - Requires strict humanoid avatar compatibility on all target models.
  - Retargeting artifacts may require per-character pose/mask adjustments.
- Import settings to review in Visual-3E-B:
  - Ensure selected characters and UAL source import as Humanoid with valid avatars.
  - Set Avatar Definition strategy (Create From This Model / Copy From Other Avatar) consistently.
  - Tune loop settings and root transform options for locomotion/action clips.
- Gameplay prefabs expected to be touched in Visual-3E-B:
  - Worker.prefab
  - Light.prefab
  - Heavy.prefab
  - Ranged.prefab
### Option C: Hybrid approach: Idle/Walk from UAL, Attack/Death from character pack, Harvest fallback procedural or work-like clip.
- Pros:
  - Balances broad coverage with role-specific attacks/deaths.
  - Allows staged integration when harvest-specific clips are missing.
- Risks:
  - Mixed sources can create style mismatch between states.
  - Controller graph complexity increases due to heterogeneous clip provenance.
- Import settings to review in Visual-3E-B:
  - Keep UAL and selected characters humanoid-compatible for shared locomotion.
  - Normalize attack/death clip loop and transition timing from character pack.
  - Define temporary harvest fallback policy before full bespoke gather animations.
- Gameplay prefabs expected to be touched in Visual-3E-B:
  - Worker.prefab
  - Light.prefab
  - Heavy.prefab
  - Ranged.prefab

## Recommended Path For Visual-3E-B
- Recommended option: Option C
- Rationale: Current imports are Generic with no humanoid avatars, so pure humanoid retargeting is not ready; hybrid adoption minimizes import churn while enabling immediate Idle/Walk/Attack/Death coverage and a controlled Harvest fallback.

## Non-changed Guardrails
- MatchManager not modified.
- ActionApplier not modified.
- ActionDecoder not modified.
- ActionMaskBuilder not modified.
- ObservationBuilder not modified.
- GridManager occupancy logic not modified.
- UnitFactory spawn semantics not modified.
- UnitRegistry registration semantics not modified.
- ResourceManager and ResourceNode gameplay semantics not modified.
- ML-Agents and Python training scripts not modified.
- Checkpoint paths and inference bridge not modified.
- Map coordinates and logical map size 24x24 not modified.
- Gameplay prefabs and UnitDef/GameConfig assets not modified.
- VisualEventBridge/UnitVisualAnimator/UnitFactory runtime wiring not modified in this stage.

## Changed Files
- Assets/Editor/Visual3EAAnimationRigInventory.cs
- Assets/Visual3EA_AnimationRigInventory.json
- VISUAL_3E_A_ANIMATION_RIG_INVENTORY_REPORT.md