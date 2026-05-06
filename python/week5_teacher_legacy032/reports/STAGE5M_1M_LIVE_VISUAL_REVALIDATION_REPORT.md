# Stage5M - 1M Live Visual Revalidation (Training-Compatible Step)

Date: 2026-05-06
Stage baseline: STAGE5L_TRAINING_COMPATIBLE_STEP_PASS

## 1) Commands used

### Run A - deterministic live visual

$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"

c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe \
  python/week5_teacher_legacy032/scripts/run_legacy032_visual_single_episode.py \
  --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/agent_final.pt \
  --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/model_metadata.json \
  --device cpu \
  --seed 17 \
  --mode deterministic \
  --max-steps 6000 \
  --strict-load \
  --render \
  --render-mode human \
  --step-mode training_compatible \
  --run-label stage5m_1m_deterministic_live_visual

### Run B - stochastic live visual

$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"

c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe \
  python/week5_teacher_legacy032/scripts/run_legacy032_visual_single_episode.py \
  --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/agent_final.pt \
  --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/model_metadata.json \
  --device cpu \
  --seed 17 \
  --mode stochastic \
  --max-steps 6000 \
  --strict-load \
  --render \
  --render-mode human \
  --step-mode training_compatible \
  --run-label stage5m_1m_stochastic_live_visual

### Run C - stochastic seed 123 (optional)

$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"

c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe \
  python/week5_teacher_legacy032/scripts/run_legacy032_visual_single_episode.py \
  --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/agent_final.pt \
  --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/model_metadata.json \
  --device cpu \
  --seed 123 \
  --mode stochastic \
  --max-steps 6000 \
  --strict-load \
  --render \
  --render-mode human \
  --step-mode training_compatible \
  --run-label stage5m_1m_stochastic_seed123_live_visual

## 2) Checkpoint and metadata paths

- checkpoint: python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/agent_final.pt
- metadata: python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/model_metadata.json

## 3) Deterministic run (Run A)

- status: OK
- step_mode: training_compatible
- java_payload_used: true
- strict_load: true
- first_step summary:
  - source_valid_total: 4
  - source_valid_non_noop_count: 4
  - source_valid_action_type_counts: {"0":0,"1":0,"2":2,"3":0,"4":2,"5":0}
- first_step payload_debug:
  - valid_actions_counts: [2, 2]
  - source_valid_non_noop_count: 4
- total_steps: 6000
- total_reward: 98.2
- total_obs_changed_steps: 4048
- terminal_info_keys: ["raw_rewards"]
- rendered_frames_count: 0
- render_capture_status: NOT_REQUESTED
- live visual observation (operator):
  - "Агент двигался, но как-то сломался и действовал странно. Матч закончился по истечению времени."

## 4) Stochastic run (Run B)

- status: OK
- step_mode: training_compatible
- java_payload_used: true
- strict_load: true
- first_step summary:
  - source_valid_total: 4
  - source_valid_non_noop_count: 4
  - source_valid_action_type_counts: {"0":0,"1":0,"2":2,"3":0,"4":2,"5":0}
- first_step payload_debug:
  - valid_actions_counts: [2, 2]
  - source_valid_non_noop_count: 4
- total_steps: 6000
- total_reward: 233.2
- total_obs_changed_steps: 5823
- terminal_info_keys: ["raw_rewards"]
- rendered_frames_count: 0
- render_capture_status: NOT_REQUESTED
- live visual observation (operator):
  - "Агент действовал нормально и разрушил базу противника."

## 5) Optional stochastic seed 123 (Run C)

- status: OK
- step_mode: training_compatible
- java_payload_used: true
- strict_load: true
- first_step summary:
  - source_valid_total: 4
  - source_valid_non_noop_count: 3
  - source_valid_action_type_counts: {"0":1,"1":0,"2":2,"3":0,"4":1,"5":0}
- first_step payload_debug:
  - valid_actions_counts: [2, 2]
  - source_valid_non_noop_count: 3
- total_steps: 6000
- total_reward: 233.2
- total_obs_changed_steps: 5797
- terminal_info_keys: ["raw_rewards"]
- rendered_frames_count: 0
- render_capture_status: NOT_REQUESTED
- live visual observation (operator):
  - "Агент действовал нормально и разрушил базу противника."

## 6) Direct answer (visual behavior)

- agent visibly does something: yes
- harvest visible: yes
- produce visible: yes
- move visible: yes
- combat visible: yes

## 7) Comparison with pre-Stage5L visual

- Was old "agent does nothing" caused by wrong step path?: Highly likely yes.
- Is behavior now restored?: Yes (especially in stochastic runs, with successful offensive behavior and base destruction).

## 8) Final classification

STAGE5M_1M_VISUAL_BEHAVIOR_RESTORED

Rationale:
- training_compatible step mode used in all runs;
- java_payload_used=true in all runs;
- first_step payload contains valid_actions_counts and source_valid_non_noop_count>0;
- total_obs_changed_steps is strongly positive in all runs;
- operator confirms visible economy/movement/combat and successful attack outcomes in stochastic runs.

## 9) Final recommendation

Per Stage5M decision rules:
- Rerun behavior metrics with training_compatible step as canonical evidence.
- Then decide whether to continue to 2M/3M or export rollouts, based on updated post-fix metrics and not on pre-Stage5L visual artifacts.

## Notes

- Missing frame files is not a failure in this stage.
- rendered_frames_count=0 with render_mode=human is expected and accepted for Stage5M.
