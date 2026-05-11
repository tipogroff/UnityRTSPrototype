# ART_ASSET_INVENTORY

## Scope
Inventory for Quaternius assets requested for the visual integration layer.

## Actual Asset Locations (as found in repository)
- Ultimate Fantasy RTS package is currently present as archive: `drive-download-20260511T185405Z-3-001.zip`.
- Universal Animation Library package is currently present as archive: `Universal Animation Library[Standard].zip`.
- `Assets/Art/` was empty before this visual-layer task (no pre-imported Quaternius folders detected).

## Ultimate Fantasy RTS Model Source (archive contents)
Primary model folders inside `drive-download-20260511T185405Z-3-001.zip`:
- `FBX/` (contains .fbx models)
- `glTF/` (contains .gltf models)
- `Blends/` (contains .blend sources)

Representative model entries found:
- `FBX/TownCenter_FirstAge_Level1.fbx`
- `FBX/TownCenter_SecondAge_Level1.fbx`
- `FBX/Barracks_FirstAge_Level1.fbx`
- `FBX/Barracks_SecondAge_Level1.fbx`
- `FBX/Resource_Gold_1.fbx`
- `FBX/Resource_Rock_1.fbx`
- `FBX/Resource_Tree1.fbx`
- `FBX/WatchTower_FirstAge_Level1.fbx`
- `FBX/Wall_FirstAge.fbx`
- `FBX/Farm_FirstAge_Level1.fbx`

## Universal Animation Library Clip Source (archive contents)
Primary animation source inside `Universal Animation Library[Standard].zip`:
- `Universal Animation Library[Standard]/Unity/UAL1_Standard.fbx`

Notes:
- Animation clips are not yet imported as separate `.anim` assets in this repository.
- Candidate clip assignment therefore remains `needs visual check` in Unity after import.

## Model Candidates by Gameplay Role (safe, non-assertive)
- Base:
  - `FBX/TownCenter_FirstAge_Level1.fbx` (suitable candidate)
  - `FBX/TownCenter_SecondAge_Level1.fbx` (suitable candidate)
- Barracks:
  - `FBX/Barracks_FirstAge_Level1.fbx` (suitable candidate)
  - `FBX/Barracks_SecondAge_Level1.fbx` (suitable candidate)
- Worker:
  - No explicit worker character mesh found in scanned archive entries (candidate missing, needs visual check)
- Light:
  - No explicit light infantry mesh found in scanned archive entries (candidate missing, needs visual check)
- Heavy:
  - No explicit heavy infantry mesh found in scanned archive entries (candidate missing, needs visual check)
- Ranged:
  - No explicit ranged unit character mesh found in scanned archive entries (candidate missing, needs visual check)
- ResourceNode:
  - `FBX/Resource_Gold_1.fbx` (suitable candidate)
  - `FBX/Resource_Rock_1.fbx` (suitable candidate)
  - `FBX/Resource_Tree1.fbx` (suitable candidate)
- Environment props:
  - `FBX/Wall_FirstAge.fbx` (candidate)
  - `FBX/WatchTower_FirstAge_Level1.fbx` (candidate)
  - `FBX/Farm_FirstAge_Level1.fbx` (candidate)
  - `FBX/Windmill_FirstAge.fbx` (candidate)
  - `FBX/Mine.fbx` (candidate)

## Animation Candidates by Gameplay Role (from UAL package)
Source: `Universal Animation Library[Standard]/Unity/UAL1_Standard.fbx`

- Idle: suitable candidate, needs visual check after import
- Walk: suitable candidate, needs visual check after import
- Attack: suitable candidate, needs visual check after import
- Harvest: candidate missing as explicit label in repository, needs visual check after import
- Death: suitable candidate, needs visual check after import
- Spawn: candidate missing as explicit label in repository, needs visual check after import

## Import-State Constraint
Quaternius packages were detected as downloaded archives in repository root, not as already-imported Unity assets under `Assets/Art/Quaternius/` during this task.
