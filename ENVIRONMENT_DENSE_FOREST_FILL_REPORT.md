# Environment Dense Forest Fill Report

## Summary

- Replaced the sparse edge decoration with a deterministic dense forest layout.
- Scene updated: `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`.
- Parent structure now uses:
  - `EnvironmentDecorations/DecorativeGround`
  - `EnvironmentDecorations/DenseForest`
  - `EnvironmentDecorations/Rocks`

## Counts

- Trees added: `135`
- Rocks added: `26`
- Previous sparse/microscopic `DenseForest`, `Rocks`, `Trees`, and `Props` groups were removed and regenerated as visible scene objects.

## Models Used

Trees:

- `Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Resource_Tree1.fbx`
- `Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Resource_Tree2.fbx`
- `Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Resource_PineTree.fbx`

Rocks:

- `Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Rock.fbx`
- `Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Resource_Rock_1.fbx`
- `Assets/Art/Quaternius/UltimateFantasyRTS/FBX/Resource_Rock_2.fbx`

## Placement

- Generated with fixed seed `914207`.
- Filled the broad non-gameplay area around the map, not just a perimeter row.
- Covered north, south, west, east, corner, and intermediate zones between the gameplay grid and the expanded visual ground edge.
- Gameplay grid kept clear: no generated decoration is placed inside `x: 0..23` and `z: 0..23`.
- Tree transform scale variation: `450..700`, with `-90` degrees X rotation to make the imported FBX trees stand visibly in the scene.
- Rock transform scale variation: `240..380`.
- Randomized Y rotation per instance.

## Gameplay Safety

- Gameplay grid/map size was not changed; scene camera controller still has `_mapWidth: 24` and `_mapHeight: 24`.
- Did not modify `GridManager`, `MatchManager`, `EpisodeController`, `ActionDecoder`, `ActionApplier`, ML/training/checkpoints, or Week7 scene.
- Decorative objects were instantiated as visual model instances only.
- All generated decorations are under `EnvironmentDecorations` on `Ignore Raycast`.
- Colliders were removed from generated decorative instances before saving the scene.
- No `ResourceNode`, `UnitRuntime`, pathfinding, occupancy, or selectable gameplay components were added.

## Verification

- Unity refresh and script compilation completed after removing the temporary builder.
- Active demo-scene Play Mode smoke check completed.
- Console after smoke check: `0` error entries.
- Camera logic was not changed; the expanded floor from the previous pass remains at scale `(12, 1, 12)`.
- The previously tiny FBX instances were removed and regenerated with visible scene-scale transforms.
- Full manual `MainMenu -> Start -> AI против игрока`, `AI против бота`, and `AI против AI` flow was not manually exercised in this session.

## Changed Files

- `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`
- `ENVIRONMENT_DENSE_FOREST_FILL_REPORT.md`
