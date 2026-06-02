# Stage7B-6E Bridge Source Inventory

- generated_at_utc: 2026-05-10T02:20:00Z
- stage: Stage7B-6E

## Active Wrapper (actually imported)

- gym_microrts module:
  - python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/__init__.py
- vec_env.py:
  - python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/envs/vec_env.py
- Runtime Java class names:
  - tests.JNIGridnetVecClient
  - tests.JNIGridnetClient

## Found Python files (relevant)

- python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/envs/vec_env.py
- python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/envs/global_agent_env.py
- python/week5_teacher_legacy032/scripts/export_replay_ready_teacher_rollout_stage7b.py
- python/week5_teacher_legacy032/scripts/legacy032_policy_action.py
- python/week5_teacher_legacy032/scripts/probe_legacy032_runtime_state_api_stage7b.py

## Found Java sources

- none in searched workspace/venv paths for JNIGridnet bridge

## Found binaries

- JARs (active runtime):
  - python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/microrts/microrts.jar
  - python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/microrts/Coac.jar
  - python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/microrts/Droplet.jar
  - python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/microrts/GRojoA3N.jar
  - python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/microrts/Izanagi.jar
  - python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/microrts/MixedBot.jar
  - python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/microrts/RojoBot.jar
  - python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/microrts/TiamatBot.jar
  - python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/microrts/UMSBot.jar

- On-disk .class files in package tree:
  - none (classes are inside microrts.jar)

## JNI/GameState classes present inside microrts.jar

- tests/JNIGridnetVecClient.class
- tests/JNIGridnetClient.class
- tests/JNIGridnetClientSelfPlay.class
- rts/GameState.class
- rts/PhysicalGameState.class
- rts/units/Unit.class
- rts/Player.class

## Loading model

- vec_env.py adds classpath entries by calling jpype.addClassPath for each JAR.
- JVM is started from Python wrapper.
- Python bridge objects are created from ts package classes loaded out of microrts.jar.

## Source availability conclusion

- JNI bridge source: not found in current workspace/venv.
- Core RTS source: not found in current workspace/venv.
- Binary-only state with decompilable signatures: confirmed.
