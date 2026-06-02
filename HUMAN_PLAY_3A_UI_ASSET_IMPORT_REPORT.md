# HumanPlay-3A UI Asset Import Report

Date: 2026-05-17

## Imported Archives

- `kenney_ui-pack-rpg-expansion.zip`
  - Target: `Assets/Art/UI/Kenney/UI_Pack_RPG_Expansion/`
  - Preserved: `license.txt`, `preview.png`, `sample.png`, spritesheet XML, vector source files.
  - Import settings: PNG textures set to `Sprite (2D and UI)`, single sprite mode for individual PNGs, 100 pixels per unit, alpha transparency enabled, mipmaps disabled.

- `kenney_game-icons.zip`
  - Target: `Assets/Art/UI/Kenney/Game_Icons/`
  - Preserved: `license.txt`, `preview.png`, spritesheet XML, vector source files.
  - Import settings: PNG textures set to `Sprite (2D and UI)`, single sprite mode for individual PNGs, 100 pixels per unit, alpha transparency enabled, mipmaps disabled.

Original zip files remain in the project root.

## Sprite Usage

- Main menu buttons: `UI_Pack_RPG_Expansion/PNG/buttonLong_beige.png`, pressed state `buttonLong_beige_pressed.png`.
- Main menu and HUD panels: `UI_Pack_RPG_Expansion/PNG/panel_brown.png`.
- HUD command buttons: `buttonLong_beige.png`, pressed state `buttonLong_beige_pressed.png`.
- Pause/menu icons: `Game_Icons/PNG/White/2x/pause.png`, `gear.png`, `home.png`, `target.png`, `power.png`.
- Resource/status display currently uses styled text fields; no dedicated resource icon was required for this pass.

## 9-Slice Notes

Panel sprites receive 18 px borders. Long and square button sprites receive 12 px borders. This is configured by `Assets/Scripts/Editor/Presentation/HumanPlay3UiCameraMenuSetup.cs`.
