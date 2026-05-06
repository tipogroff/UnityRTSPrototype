# STAGE5J Canonical Visual Behavior Rerun Report

Date: 2026-05-06
Stage: Stage5J - Canonical Visual Behavior Rerun after Stage5I

## 1) Commands Used

PowerShell environment setup used before each run:

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
```

Python executable used (reference env):

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe
```

Run A - deterministic:

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week5_teacher_legacy032/scripts/run_legacy032_visual_single_episode.py --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/agent_final.pt --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/model_metadata.json --device cpu --seed 17 --mode deterministic --max-steps 6000 --strict-load --render --run-label stage5j_canonical_deterministic
```

Run B - stochastic:

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week5_teacher_legacy032/scripts/run_legacy032_visual_single_episode.py --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/agent_final.pt --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/model_metadata.json --device cpu --seed 17 --mode stochastic --max-steps 6000 --strict-load --render --run-label stage5j_canonical_stochastic
```

Run C - stochastic second seed (optional):

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week5_teacher_legacy032/scripts/run_legacy032_visual_single_episode.py --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/agent_final.pt --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/model_metadata.json --device cpu --seed 123 --mode stochastic --max-steps 6000 --strict-load --render --run-label stage5j_canonical_stochastic_seed123
```

## 2) Checkpoint and Metadata Paths

- checkpoint: `python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/agent_final.pt`
- metadata: `python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/model_metadata.json`

## 3) Required Console Evidence - Deterministic

- [visual] checkpoint=C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_1m_20260504T231107Z\stage_001000000\agent_final.pt
- [visual] metadata=C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_1m_20260504T231107Z\stage_001000000\model_metadata.json
- [visual] mode=deterministic seed=17
- [visual] mask_source=env.vec_client.getMasks(0)
- [visual] first_step_summary={"all_cell_action_type_counts": {"0": 1148, "1": 0, "2": 2, "3": 0, "4": 2, "5": 0}, "all_cell_action_type_shares": {"0": 0.9965277777777778, "1": 0.0, "2": 0.001736111111111111, "3": 0.0, "4": 0.001736111111111111, "5": 0.0}, "source_valid_action_type_counts": {"0": 0, "1": 0, "2": 2, "3": 0, "4": 2, "5": 0}, "source_valid_action_type_shares": {"0": 0.0, "1": 0.0, "2": 0.5, "3": 0.0, "4": 0.5, "5": 0.0}, "source_valid_non_noop_count": 4, "source_valid_total": 4}
- [visual] first_step_branch_validity={"source_valid_total": 4, "effective_noop_candidate_count": 0}

Key deterministic first-step fields:

- source_valid_total: 4
- source_valid_non_noop_count: 4
- source_valid_action_type_counts: {0:0,1:0,2:2,3:0,4:2,5:0}
- source_valid_action_type_shares: {0:0.0,1:0.0,2:0.5,3:0.0,4:0.5,5:0.0}
- effective_noop_candidate_count: 0
- all_cell_action_type_counts: {0:1148,1:0,2:2,3:0,4:2,5:0}
- all_cell_action_type_shares: {0:0.9965277778,1:0.0,2:0.0017361111,3:0.0,4:0.0017361111,5:0.0}

## 4) Required Console Evidence - Stochastic

- [visual] checkpoint=C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_1m_20260504T231107Z\stage_001000000\agent_final.pt
- [visual] metadata=C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_1m_20260504T231107Z\stage_001000000\model_metadata.json
- [visual] mode=stochastic seed=17
- [visual] mask_source=env.vec_client.getMasks(0)
- [visual] first_step_summary={"all_cell_action_type_counts": {"0": 191, "1": 194, "2": 201, "3": 174, "4": 199, "5": 193}, "all_cell_action_type_shares": {"0": 0.1657986111111111, "1": 0.1684027777777778, "2": 0.17447916666666666, "3": 0.15104166666666666, "4": 0.17274305555555555, "5": 0.1675347222222222}, "source_valid_action_type_counts": {"0": 0, "1": 0, "2": 2, "3": 0, "4": 2, "5": 0}, "source_valid_action_type_shares": {"0": 0.0, "1": 0.0, "2": 0.5, "3": 0.0, "4": 0.5, "5": 0.0}, "source_valid_non_noop_count": 4, "source_valid_total": 4}
- [visual] first_step_branch_validity={"source_valid_total": 4, "effective_noop_candidate_count": 0}

Key stochastic first-step fields (seed 17):

- source_valid_total: 4
- source_valid_non_noop_count: 4
- source_valid_action_type_counts: {0:0,1:0,2:2,3:0,4:2,5:0}
- source_valid_action_type_shares: {0:0.0,1:0.0,2:0.5,3:0.0,4:0.5,5:0.0}
- effective_noop_candidate_count: 0
- all_cell_action_type_counts: {0:191,1:194,2:201,3:174,4:199,5:193}
- all_cell_action_type_shares: {0:0.1657986111,1:0.1684027778,2:0.1744791667,3:0.1510416667,4:0.1727430556,5:0.1675347222}

Optional stochastic seed 123 first-step delta:

- source_valid_total: 4
- source_valid_non_noop_count: 3
- source_valid_action_type_counts: {0:1,1:0,2:2,3:0,4:1,5:0}
- effective_noop_candidate_count: 0

## 5) Episode Outcomes

Deterministic (seed 17):

- status: OK
- total_steps: 6000
- total_reward: 0.0
- terminal_info_keys: [raw_rewards]

Stochastic (seed 17):

- status: OK
- total_steps: 3735
- total_reward: -10.0
- terminal_info_keys: [raw_rewards]

Stochastic (seed 123, optional):

- status: OK
- total_steps: 5515
- total_reward: -10.0
- terminal_info_keys: [raw_rewards]

## 6) Visual Observations (Practical Limitation in This Run Context)

- The canonical runner completed and generated JSON/MD summaries.
- No `frame_*.png` files were written for A/B/C despite `--render`.
- In this terminal-only execution context, there is no persisted visual frame sequence to perform an objective frame-by-frame "by eye" audit after the run.

Given that limitation, direct claims such as "worker visibly moved/harvested/returned resources/produced/attacked" cannot be made from preserved artifacts in this pass.

## 7) Required Binary Questions

- Agent visibly moved: inconclusive (no persisted frames)
- Agent visibly harvested: inconclusive (no persisted frames)
- Agent visibly returned resources: inconclusive (no persisted frames)
- Agent visibly produced units: inconclusive (no persisted frames)
- Agent visibly attacked: inconclusive (no persisted frames)

## 8) Comparison vs Pre-Stage5I Inert Visual Result

- Pre-Stage5I inert result is not trusted due to non-canonical action path.
- Stage5J canonical rerun now shows source-valid non-noop action selection at first step and `effective_noop_candidate_count=0` in deterministic and stochastic modes.
- However, because no persisted render frames were produced, this run does not provide enough evidence to conclusively confirm or deny restored visible behavior.

## 9) Artifacts Produced

Deterministic:

- `python/week5_teacher_legacy032/reports/stage5i_visual_single_episode/stage5j_canonical_deterministic/legacy032_visual_single_episode_20260505T184202Z.json`
- `python/week5_teacher_legacy032/reports/stage5i_visual_single_episode/stage5j_canonical_deterministic/LEGACY032_VISUAL_SINGLE_EPISODE.md`

Stochastic:

- `python/week5_teacher_legacy032/reports/stage5i_visual_single_episode/stage5j_canonical_stochastic/legacy032_visual_single_episode_20260505T184259Z.json`
- `python/week5_teacher_legacy032/reports/stage5i_visual_single_episode/stage5j_canonical_stochastic/LEGACY032_VISUAL_SINGLE_EPISODE.md`

Stochastic seed 123:

- `python/week5_teacher_legacy032/reports/stage5i_visual_single_episode/stage5j_canonical_stochastic_seed123/legacy032_visual_single_episode_20260505T184327Z.json`
- `python/week5_teacher_legacy032/reports/stage5i_visual_single_episode/stage5j_canonical_stochastic_seed123/LEGACY032_VISUAL_SINGLE_EPISODE.md`

Console logs (rerun):

- `python/week5_teacher_legacy032/reports/stage5j_canonical_deterministic_console_rerun.log`
- `python/week5_teacher_legacy032/reports/stage5j_canonical_stochastic_console_rerun.log`
- `python/week5_teacher_legacy032/reports/stage5j_canonical_stochastic_seed123_console_rerun.log`

## 10) Final Classification

`STAGE5J_VISUAL_INCONCLUSIVE`

## 11) Final Recommendation

`RUN_ACCEPTED_COMMAND_EFFECT_TRACE`

Rationale:

- Canonical path now clearly selects source-valid non-noop actions with zero effective-noop candidates.
- Deterministic run reached 6000 steps with reward 0.0; stochastic runs ended with -10.0 (episode end before 6000), indicating trajectory divergence by mode.
- Without persisted visual frames, direct visual verification is incomplete.
- Next best diagnostic is accepted/applied-command tracing to determine if selected actions are being applied and producing state changes.
