# Stage7B-6F Buildability Report

Date: 2026-05-10

## Objective

Prove that the legacy032 source checkout can be built without serializer/runtime patches,
without touching the active installed microrts runtime.

## Build Result

- build_success: true
- produced artifact:
  python/week5_teacher_legacy032/third_party/gym_microrts_legacy032_source/build_stage7b_unmodified/microrts.jar

## Verified Classes In Produced Jar

- tests/JNIGridnetClient.class
- tests/JNIGridnetVecClient.class
- tests/JNIGridnetClientSelfPlay.class
- rts/GameState.class
- rts/PhysicalGameState.class
- rts/units/Unit.class
- rts/Player.class

## Toolchain

- java: OpenJDK 17.0.18
- javac: 17.0.18
- jar: 17.0.18

## Build Logs

- stdout: python/week5_teacher_legacy032/reports/stage7b_6f_build_stdout.log
- stderr: python/week5_teacher_legacy032/reports/stage7b_6f_build_stderr.log

## Notes

- Build completed with warnings only (no compile errors).
- The installed package was not used as build source because it lacks src/ and lib/.
- No active runtime replacement or Python wrapper patch was performed.