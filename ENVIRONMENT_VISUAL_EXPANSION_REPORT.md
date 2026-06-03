# Environment Visual Expansion Report

## Found Floor

- Scene: `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`.
- Current visual floor object: `Ground_Stylized_Grass_24x24`.
- Material reference: `{fileID: 2100000, guid: d2add40b26be7f34bbb73cadbb5112fb, type: 2}`.
- Mesh: Unity built-in plane mesh `{fileID: 10209, guid: 0000000000000000e000000000000000, type: 0}`.
- Original transform: centered at `(11.5, -0.05, 11.5)` with scale `(4, 1, 4)`.
- The grid overlay object `Ground_Grid_Overlay_24x24` remains separate and unchanged at scale `(2.4, 1, 2.4)`.

## Visual Ground Expansion

- Added parent object `EnvironmentDecorations`.
- Moved `Ground_Stylized_Grass_24x24` under `EnvironmentDecorations/DecorativeGround`.
- Expanded the visual grass plane to scale `(12, 1, 12)`, keeping it centered at `(11.5, -0.05, 11.5)`.
- Gameplay grid/map size was not changed.

## Environment Props

Used models from `Assets/Art/Quaternius/UltimateFantasyRTS/FBX`:

- `Resource_Tree1.fbx`
- `Resource_Tree2.fbx`
- `Resource_PineTree.fbx`
- `Rock.fbx`
- `Resource_Rock_1.fbx`
- `Resource_Rock_2.fbx`

## Placement

- Trees are grouped under `EnvironmentDecorations/Trees`.
- Rocks are grouped under `EnvironmentDecorations/Rocks`.
- Corner props are grouped under `EnvironmentDecorations/Props`.
- Objects are placed outside the active gameplay grid range `0..23` on at least one axis:
  - north: z around `28..34`;
  - south: z around `-10..-7`;
  - west: x around `-13..-9`;
  - east: x around `30..36`;
  - corners: `(-16, 31)` and `(38, -11)`.

## Gameplay Safety

- Did not modify `GridManager`, map size, pathfinding, occupancy, resources, spawn points, `MatchManager`, `EpisodeController`, ML assets, or command pipeline.
- Decorative objects were instantiated as visual model instances only.
- Colliders were removed from decorative instances by the scene builder before save.
- `EnvironmentDecorations`, `Trees`, `Rocks`, and `Props` are on Unity layer `Ignore Raycast`, so they do not participate in normal selection/grid raycasts.
- No `ResourceNode`, `UnitRuntime`, or selectable gameplay components were added to decorative objects.

## Camera Check

- Camera controller logic was not changed for this task.
- Existing camera settings remain in the scene, including WASD movement, wheel zoom, middle mouse drag, and match-start focus fields.
- Expanded visual ground is intended to cover normal camera bounds without exposing the Unity grey background.

## Console Check

- Unity refresh and script compilation were requested after removing the temporary scene builder.
- Compilation completed.
- Automated MCP console read after refresh returned 0 error entries.
- Full manual play-mode flow through `MainMenu -> Start` was not run in this session.

## Changed Files

- `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`
- `ENVIRONMENT_VISUAL_EXPANSION_REPORT.md`
