# Stage7B-6E Bridge Build Path Report

- generated_at_utc: 2026-05-10T02:21:00Z
- stage: Stage7B-6E

## Build path artifacts discovered

- python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/microrts/build.sh
- python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/microrts/.classpath
- python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/microrts/.project
- python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/microrts/.drone.yml
- python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/microrts/.git

## What build.sh expects

- Source dir: ./src
- Dependency dir: ./lib
- Compile: javac -d ./build -cp ./lib/* -sourcepath ./src ...
- Package: jar cvf microrts.jar ...

## What is actually present in installed package

- src/: missing
- lib/: missing
- .git module target from .git file: missing
- Runtime JARs: present (microrts.jar + bot jars)

## Runtime load path (confirmed)

- Active wrapper: python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/envs/vec_env.py
- vec_env.py loads JARs via jpype.addClassPath and starts JVM.
- JVM classpath includes microrts.jar and the 8 bot jars.

## Local rebuild feasibility

- Direct rebuild from installed package: NO (required sources/dependencies are absent).
- Rebuild is possible if original source tree is obtained.
- Decompile-and-recompile patch path is technically possible (javac/jar available), but risk is high.

## Where patched build must be deployed

Option A:
- Replace python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/microrts/microrts.jar

Option B:
- Create patch JAR with modified tests classes and load it before microrts.jar in python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/envs/vec_env.py
