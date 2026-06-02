# Visual-3G Animation Showcase Scene Report

## Purpose
Visual-3G adds a dedicated animation-only scene so the Worker, Light, Heavy, and Ranged animations can be demonstrated outside the Week7 gameplay loop, AI, movement, and training runtime. The showcase scene is intentionally isolated from MatchManager, GridManager, UnitFactory gameplay semantics, ML-Agents training code, and the rest of the combat loop.

## Scene
Created: [Assets/Scenes/AnimationShowcase.unity](Assets/Scenes/AnimationShowcase.unity)

The scene contains:
- a simple ground/floor surface;
- a directional light;
- a single camera framing all four characters;
- four visible demo characters arranged left to right:
  - Worker
  - Light
  - Heavy
  - Ranged
- a scene-level showcase controller for hotkeys, auto-cycle, overlay text, and reset.

The scene uses the validated preview-only animated prefabs already prepared earlier in the pipeline. That keeps the showcase visual-only and avoids changing gameplay/runtime semantics. Separate showcase-prefab copies were also generated under [Assets/Art/Prefabs/Visuals/Characters/Showcase/](Assets/Art/Prefabs/Visuals/Characters/Showcase/) as drop-in visual-only variants.

## Controller Wiring
Scene-level controller:
- [Assets/Scripts/Presentation/AnimationShowcaseController.cs](Assets/Scripts/Presentation/AnimationShowcaseController.cs)

Per-character controller base:
- [Assets/Scripts/Presentation/AnimationPreviewController.cs](Assets/Scripts/Presentation/AnimationPreviewController.cs)

Each demo character keeps the embedded clip-backed animator/controller setup already validated earlier. The showcase controller discovers all four preview controllers in the scene, disables local keyboard handling and local auto-cycle, then drives the shared state across all characters.

## Controls
Hotkeys:
- `1` = Idle
- `2` = Walk
- `3` = Attack
- `4` = Harvest
- `5` = Death
- `R` = Reset
- `A` = Toggle AutoCycle
- `Space` = Next state

Overlay:
- current state
- auto-cycle status
- selector index
- per-character normalizedTime readout
- hotkey hints

The controller also exposes a serialized selector field for deterministic editor-driven validation when screenshots need to be captured state-by-state.

## Reset Behavior
Reset restores each character to its original cached transform, clears local control flags, rebinds the animator, and returns the unit to Idle.

That keeps the showcase reusable after Death or any other state without touching gameplay lifecycle or runtime semantics.

## States Validated
Validated showcase states:
- Idle
- Walk
- Attack
- Harvest
- Death

The controller applies the selected state to all four characters together, and the overlay/logging path reports animator normalizedTime so state advancement is not just a static pose binding.

## Evidence
Captured screenshots:
- [Assets/Screenshots/Visual_3G_Showcase_Idle.png](Assets/Screenshots/Visual_3G_Showcase_Idle.png)
- [Assets/Screenshots/Visual_3G_Showcase_Walk.png](Assets/Screenshots/Visual_3G_Showcase_Walk.png)
- [Assets/Screenshots/Visual_3G_Showcase_Attack.png](Assets/Screenshots/Visual_3G_Showcase_Attack.png)
- [Assets/Screenshots/Visual_3G_Showcase_Harvest.png](Assets/Screenshots/Visual_3G_Showcase_Harvest.png)
- [Assets/Screenshots/Visual_3G_Showcase_Death.png](Assets/Screenshots/Visual_3G_Showcase_Death.png)

Validation summary:
- the scene loads successfully in Unity as [AnimationShowcase](Assets/Scenes/AnimationShowcase.unity);
- the live hierarchy contains the ground, light, camera, four demo characters, and the showcase controller root;
- all four demo characters have Animator components through the preview controller setup;
- the final Play Mode run completed without new console errors after the input-system fix;
- no magenta or T-pose regressions were introduced in the captured showcase flow.

## Changed Files
Primary changes:
- [Assets/Scenes/AnimationShowcase.unity](Assets/Scenes/AnimationShowcase.unity)
- [Assets/Scripts/Presentation/AnimationShowcaseController.cs](Assets/Scripts/Presentation/AnimationShowcaseController.cs)
- [Assets/Scripts/Presentation/AnimationPreviewController.cs](Assets/Scripts/Presentation/AnimationPreviewController.cs)
- [VISUAL_3G_ANIMATION_SHOWCASE_SCENE_REPORT.md](VISUAL_3G_ANIMATION_SHOWCASE_SCENE_REPORT.md)

Additional generated showcase assets:
- [Assets/Art/Prefabs/Visuals/Characters/Showcase/](Assets/Art/Prefabs/Visuals/Characters/Showcase/)

## Guardrails
Not changed:
- MatchManager
- ActionApplier
- ActionDecoder
- ActionMaskBuilder
- ObservationBuilder
- GridManager occupancy logic
- UnitFactory gameplay semantics
- UnitRegistry semantics
- ResourceManager / ResourceNode semantics
- ML-Agents training code
- Python BC/PPO/training scripts
- checkpoint paths
- inference bridge
- reward/terminal semantics
- UnitDef/GameConfig assets
- Week7 gameplay scene behavior
- owner color sync semantics
- existing character scale/proportion choices
- Base/Barracks/Resource gameplay prefabs
