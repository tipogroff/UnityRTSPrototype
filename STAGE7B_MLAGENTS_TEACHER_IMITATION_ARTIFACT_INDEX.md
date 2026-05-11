# Stage7B ML-Agents Teacher Imitation Artifact Index

## Authoritative Milestones
- Stage7B-8B.7 GO = imitation smoke. Evidence: python/stage7b_teacher_replay/stage7b_8b7_post_kick_action_cycle_report.json (final_status=GO).
- Stage7B-8C.2 GO = ONNX inference single smoke. Evidence: python/stage7b_teacher_replay/stage7b_8c2_padding_warning_fix_report.json (final_decision=GO).
- Stage7B-8D.1 GO = extended inference lifecycle. Evidence: python/stage7b_teacher_replay/stage7b_8d1_decision_scheduling_fix_report.json (final_decision=GO, ready_for_stage7b_9=true).
- Stage7B-9 PARTIAL = PPO fine-tune smoke. Evidence: python/stage7b_teacher_replay/stage7b_9_ppo_finetune_smoke_report.json.

## Historical Superseded Reports
- Stage7B-8D stale NO-GO is historical and superseded. Do not use as Stage7B-8D.1 evidence: python/stage7b_teacher_replay/stage7b_8d_extended_onnx_inference_report.json (final_decision=NO_GO).

## Current PPO Smoke Result
- final_decision: PARTIAL
- ready_for_stage7b_10_evaluation: false
- training_steps_completed: 2005
- initialization_method: --initialize-from Stage7B_ImitationSmoke_010_PostKickConfirm
- final_onnx: results/Stage7B_PPOFineTuneSmoke_001/Stage7B_RTS_Student.onnx
