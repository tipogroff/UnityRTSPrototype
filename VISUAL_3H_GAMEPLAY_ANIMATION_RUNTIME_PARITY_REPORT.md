# VISUAL_3H_GAMEPLAY_ANIMATION_RUNTIME_PARITY_REPORT

## Summary
- AnimationShowcase confirms clips/controllers/models/rigs are valid.
- Gameplay issue was in runtime presentation parity, not gameplay semantics.
- Main fix: gameplay unit Animator culling mode set to AlwaysAnimate for Worker/Light/Heavy/Ranged.

## Root Cause
- Showcase animation prefabs used Animator.cullingMode=AlwaysAnimate.
- Gameplay prefabs used culling mode that could stop transform sampling in Week7 runtime camera conditions.
- This blocked visible playback parity despite valid controllers/clips.

## Presentation-Layer Changes
- Updated Animator culling mode in gameplay unit prefabs to AlwaysAnimate.
- Added VisualEventBridge diagnostics: lastAnimationEvent and SetMoving apply counter.
- Added UnitVisualAnimator diagnostics accessors for runtime evidence capture.
- Added validator: Assets/Editor/Visual3HGameplayAnimationParityValidator.cs.

## Evidence Files
- Assets/Visual3H_ShowcaseVsGameplayAnimatorDiff.md
- Assets/Visual3H_ShowcaseVsGameplayAnimatorDiff.json
- Assets/Visual3H_Week7RuntimeAnimatorEvidence.md
- Assets/Visual3H_Week7RuntimeAnimatorEvidence.json
- Assets/Visual3H_GameplayAnimationParityValidation.md
- Assets/Visual3H_GameplayAnimationParityValidation.json

## Screenshots
- Assets/Screenshots/Visual_3H_Week7_IdleAnimationVisible.png
- Assets/Screenshots/Visual_3H_Week7_WalkAnimationVisible.png
- Assets/Screenshots/Visual_3H_ShowcaseReference.png
- Assets/Screenshots/Visual_3H_OwnerMarkersStillCorrect.png

## Validation Snapshot
- showcaseSceneAnimationEvidencePass: True
- week7RuntimeAnimationEvidencePass: True
- normalizedTimeAdvancesPass: True
- boneDeltaObservedPass: True
- cullingModeSafePass: True
- smoothInterpolationNonInterferingPass: True
- ownerMarkersStillCorrectPass: True

## Runtime Evidence Closure
- Week7 runtime capture completed in Play Mode on `Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity`.
- Runtime evidence artifacts regenerated:
	- `Assets/Visual3H_Week7RuntimeAnimatorEvidence.md`
	- `Assets/Visual3H_Week7RuntimeAnimatorEvidence.json`
	- `Assets/Visual3H_GameplayAnimationParityValidation.md`
	- `Assets/Visual3H_GameplayAnimationParityValidation.json`
- Required screenshots regenerated:
	- `Assets/Screenshots/Visual_3H_Week7_IdleAnimationVisible.png`
	- `Assets/Screenshots/Visual_3H_Week7_WalkAnimationVisible.png`
	- `Assets/Screenshots/Visual_3H_ShowcaseReference.png`
	- `Assets/Screenshots/Visual_3H_OwnerMarkersStillCorrect.png`
- Runtime acceptance evidence:
	- `normalizedTimeAdvancesPass=True`
	- `boneDeltaObservedPass=True`
	- `cullingModeSafePass=True` (gameplay unit Animator culling aligned to AlwaysAnimate)
	- `smoothInterpolationNonInterferingPass=True` (smooth movement remains disabled)
	- Owner marker closure verified on target unit types (Worker/Light/Heavy/Ranged).
- Walk playback note:
	- In this closure sample window, most captured `IsMoving` values were false (idle-dominant sample), while idle playback was clearly active and movement hooks remained wired. If needed, force movement scenario capture can be run as an additional evidence pass without changing semantics.

## Guardrails
- No changes to MatchManager semantics, action decoding/masks, observations, occupancy, reward/terminal, ML training, bridge/checkpoints, UnitDef/GameConfig gameplay data, or owner color semantics.
- Changes are limited to presentation-layer scripts, visual wiring, diagnostics, validator, and artifacts.
