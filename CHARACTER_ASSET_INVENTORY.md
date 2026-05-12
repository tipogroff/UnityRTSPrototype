# CHARACTER_ASSET_INVENTORY

## 1. Source archive
- Found archive: `C:\Projects\UnityRTSPrototype\UnityRTSPrototype\Ultimate Animated Character Pack - Nov 2019-20260512T001839Z-3-001.zip`
- Size: 76553115 bytes
- Last write time: 2026-05-12 07:19:16
- Secondary archive candidate: `C:\Projects\UnityRTSPrototype\UnityRTSPrototype\drive-download-20260511T185405Z-3-001.zip` (85676622 bytes, 2026-05-12 01:54:30)
- Selected archive reason: name matches Ultimate Animated Character Pack and extracted contents match animated character pack structure.

## 2. Extracted folder
- Target folder: `Assets/Art/Quaternius/UltimateAnimatedCharacterPack`
- Current structure:
  - `FBX/` (52 FBX models)
  - `License/` (1 license text file)
  - `Preview/` (1 preview image)
  - `Materials/` (created, empty)
  - `Textures/` (created, empty)

## 3. Source extract summary
- Extracted: 52 FBX files, 1 license text file, 1 preview image.
- Not extracted by design: 53 OBJ files, 53 MTL files, 53 glTF files, 52 BLEND files.
- Why skipped: FBX already covers the Unity-ready mesh/rig source; OBJ and glTF are duplicate mesh formats; BLEND is heavy source data; MTL is companion source material data rather than a Unity material asset.
- No texture set was present beyond the preview image, so `Textures/` stayed empty.

## 4. Character candidates
- Renderer type is inferred from FBX binary skin/cluster/bind-pose markers because Unity asset tooling exposed the model roots but not the nested mesh renderer component details.
- `Has clips` means embedded animation-stack data exists in the FBX source; Unity did not surface standalone `AnimationClip` assets.
- `Has rig/avatar` means the pack has armature/skinning data; a separate Avatar asset was not surfaced and Humanoid confirmation is not available from the current tooling.

| Model | Path | Renderer type | Has rig/avatar | Has clips | Possible role candidate |
|---|---|---|---|---|---|
| BaseCharacter.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/BaseCharacter.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Neutral/unused candidate |
| BlueSoldier_Female.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/BlueSoldier_Female.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Light candidate |
| BlueSoldier_Male.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/BlueSoldier_Male.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Light candidate |
| Casual_Bald.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Casual_Bald.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Casual_Female.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Casual_Female.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Casual_Male.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Casual_Male.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Casual2_Female.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Casual2_Female.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Casual2_Male.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Casual2_Male.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Casual3_Female.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Casual3_Female.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Casual3_Male.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Casual3_Male.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Chef_Female.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Chef_Female.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Chef_Hat.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Chef_Hat.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Neutral/unused candidate |
| Chef_Male.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Chef_Male.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Cow.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Cow.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Neutral/unused candidate |
| Cowboy_Female.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Cowboy_Female.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Cowboy_Hair.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Cowboy_Hair.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Neutral/unused candidate |
| Cowboy_Male.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Cowboy_Male.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Doctor_Female_Old.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Doctor_Female_Old.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Doctor_Female_Young.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Doctor_Female_Young.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Doctor_Male_Old.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Doctor_Male_Old.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Doctor_Male_Young.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Doctor_Male_Young.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Elf.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Elf.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Ranged candidate |
| Goblin_Female.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Goblin_Female.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Heavy candidate |
| Goblin_Male.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Goblin_Male.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Heavy candidate |
| Kimono_Female.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Kimono_Female.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Kimono_Male.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Kimono_Male.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Knight_Golden_Female.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Knight_Golden_Female.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Heavy candidate |
| Knight_Golden_Male.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Knight_Golden_Male.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Heavy candidate |
| Knight_Male.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Knight_Male.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Heavy candidate |
| Ninja_Female.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Ninja_Female.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Light candidate |
| Ninja_Male.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Ninja_Male.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Light candidate |
| Ninja_Male_Hair.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Ninja_Male_Hair.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Light candidate |
| Ninja_Sand.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Ninja_Sand.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Light candidate |
| Ninja_Sand_Female.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Ninja_Sand_Female.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Light candidate |
| OldClassy_Female.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/OldClassy_Female.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| OldClassy_Male.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/OldClassy_Male.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Pirate_Female.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Pirate_Female.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Heavy candidate |
| Pirate_Male.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Pirate_Male.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Heavy candidate |
| Pug.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Pug.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Neutral/unused candidate |
| Soldier_Female.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Soldier_Female.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Light candidate |
| Soldier_Male.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Soldier_Male.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Light candidate |
| Suit_Female.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Suit_Female.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Suit_Male.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Suit_Male.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Viking_Female.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Viking_Female.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Heavy candidate |
| Viking_Male.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Viking_Male.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Heavy candidate |
| VikingHelmet.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/VikingHelmet.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Neutral/unused candidate |
| Witch.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Witch.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Ranged candidate |
| Wizard.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Wizard.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Ranged candidate |
| Worker_Female.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Worker_Female.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Worker_Male.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Worker_Male.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Worker candidate |
| Zombie_Female.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Zombie_Female.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Neutral/unused candidate |
| Zombie_Male.fbx | Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Zombie_Male.fbx | SkinnedMeshRenderer (inferred) | armature present; Avatar not surfaced | yes (embedded) | Neutral/unused candidate |

## 5. Candidate grouping
- Worker candidate: Casual_Bald.fbx, Casual_Female.fbx, Casual_Male.fbx, Casual2_Female.fbx, Casual2_Male.fbx, Casual3_Female.fbx, Casual3_Male.fbx, Chef_Female.fbx, Chef_Male.fbx, Cowboy_Female.fbx, Cowboy_Male.fbx, Doctor_Female_Old.fbx, Doctor_Female_Young.fbx, Doctor_Male_Old.fbx, Doctor_Male_Young.fbx, Kimono_Female.fbx, Kimono_Male.fbx, OldClassy_Female.fbx, OldClassy_Male.fbx, Suit_Female.fbx, Suit_Male.fbx, Worker_Female.fbx, Worker_Male.fbx
- Light candidate: BlueSoldier_Female.fbx, BlueSoldier_Male.fbx, Ninja_Female.fbx, Ninja_Male.fbx, Ninja_Male_Hair.fbx, Ninja_Sand.fbx, Ninja_Sand_Female.fbx, Soldier_Female.fbx, Soldier_Male.fbx
- Heavy candidate: Goblin_Female.fbx, Goblin_Male.fbx, Knight_Golden_Female.fbx, Knight_Golden_Male.fbx, Knight_Male.fbx, Pirate_Female.fbx, Pirate_Male.fbx, Viking_Female.fbx, Viking_Male.fbx
- Ranged candidate: Elf.fbx, Witch.fbx, Wizard.fbx
- Neutral/unused candidate: BaseCharacter.fbx, Chef_Hat.fbx, Cow.fbx, Cowboy_Hair.fbx, Pug.fbx, VikingHelmet.fbx, Zombie_Female.fbx, Zombie_Male.fbx
- Needs visual check: none

## 6. Animation readiness
- Embedded animation clips are present in the FBX source data (AnimationStack, AnimationLayer, MultiTake, and named takes such as Idle, Walk, Run, Jump, Death, Victory, Punch, Shoot_OneHanded).
- Separate AnimationClip assets were not imported because Unity did not surface any clip sub-assets in this folder.
- A separate Avatar asset was not surfaced by Unity search, so Humanoid retarget readiness remains unconfirmed.
- Built-in pack clips should be usable directly for visual prototyping; Universal Animation Library remains optional for broader animation coverage or retarget comparison.

## 7. Import warnings
- No standalone Texture2D assets were imported from the pack folder, so any material wiring will need a manual pass later if textures are added.
- No standalone Material assets were imported; model previews may show default material behavior until materials are assigned later.
- Unity exposed the models as imported GameObjects, but nested renderer details were not surfaced by the current asset tool, so renderer classification here is inferred.
- Accessory-only or non-role models (BaseCharacter, Chef_Hat, Cowboy_Hair, VikingHelmet, Cow, Pug, Zombie_Female, Zombie_Male) should be visually checked before any role assignment.
