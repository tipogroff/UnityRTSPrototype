# Stage7B-6F Source Checkout Report

Date: 2026-05-10

## Scope

This stage only covers source acquisition, provenance lock, and buildability proof preparation.
No runtime patching was performed.

## Provenance Discovery

- Package identified: gym-microrts 0.3.2 (reference venv).
- METADATA and package README content point to: https://github.com/vwxyzjn/gym-microrts
- Internal versioneer file reports:
  - version: v0.3.2
  - full revision: 32e0da83c5b279800c27ca0bb2544ed660458b9f
- direct_url.json not present.
- Editable install indicators absent (no egg-link, no easy-install.pth).
- Installed microrts has a .git marker file, but referenced gitdir is not present locally.

Interpretation:
- Provenance is inferable with strong evidence (not direct pip direct_url pin).
- Installed package alone is not rebuildable (missing src/ and lib/ while build.sh requires both).

## Controlled Checkout

- Checkout path:
  python/week5_teacher_legacy032/third_party/gym_microrts_legacy032_source
- Acquisition:
  git clone --recursive https://github.com/vwxyzjn/gym-microrts.git ...
- Pinning:
  - root commit: 32e0da83c5b279800c27ca0bb2544ed660458b9f
  - root describe/tag: v0.3.2
  - microrts submodule commit: 59d6ff014d1522396c112c161f98be40d4b453e3

## Source Inventory

Found required Java sources:
- src/tests/JNIGridnetClient.java
- src/tests/JNIGridnetVecClient.java
- src/tests/JNIGridnetClientSelfPlay.java
- src/rts/GameState.java
- src/rts/PhysicalGameState.java
- src/rts/units/Unit.java
- src/rts/Player.java

Build descriptors found:
- setup.py
- gym_microrts/microrts/build.sh

## Status

- source_provenance_status: inferred_with_strong_evidence
- source_checkout_status: success
- java_source_found: true
- build_descriptor_found: true
- source_contains_required_classes: true