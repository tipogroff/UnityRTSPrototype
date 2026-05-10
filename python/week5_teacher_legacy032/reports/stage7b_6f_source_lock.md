# Stage7B-6F Source Lock

Date: 2026-05-10

## Locked Upstream

- Root repository: https://github.com/vwxyzjn/gym-microrts.git
- Root commit: 32e0da83c5b279800c27ca0bb2544ed660458b9f
- Root describe/tag: v0.3.2

- Submodule path: gym_microrts/microrts
- Submodule repository: https://github.com/Farama-Foundation/MicroRTS.git
- Submodule commit: 59d6ff014d1522396c112c161f98be40d4b453e3
- Submodule describe/tag: 59d6ff0

## Acquisition Commands

1. git clone --recursive https://github.com/vwxyzjn/gym-microrts.git python/week5_teacher_legacy032/third_party/gym_microrts_legacy032_source
2. git -C python/week5_teacher_legacy032/third_party/gym_microrts_legacy032_source checkout 32e0da83c5b279800c27ca0bb2544ed660458b9f
3. git -C python/week5_teacher_legacy032/third_party/gym_microrts_legacy032_source submodule update --init --recursive

## Lock Integrity Notes

- Root working tree is clean except untracked build output directory: build_stage7b_unmodified/
- Submodule working tree is clean.
- No changes were applied to active reference venv package.
- No replacement of active microrts.jar was performed in this stage.