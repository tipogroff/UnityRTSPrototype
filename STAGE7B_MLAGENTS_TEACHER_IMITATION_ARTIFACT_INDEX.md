# Stage7B ML-Agents Teacher Imitation Artifact Index

## Authoritative Milestones
- Stage7B-8B.7 GO = imitation smoke. Evidence: python/stage7b_teacher_replay/stage7b_8b7_post_kick_action_cycle_report.json (final_status=GO).
- Stage7B-8C.2 GO = ONNX inference single smoke. Evidence: python/stage7b_teacher_replay/stage7b_8c2_padding_warning_fix_report.json (final_decision=GO).
- Stage7B-8D.1 GO = extended inference lifecycle. Evidence: python/stage7b_teacher_replay/stage7b_8d1_decision_scheduling_fix_report.json (final_decision=GO, ready_for_stage7b_9=true).
- Stage7B-9 PARTIAL = PPO fine-tune smoke (wrapper exit code issue). Evidence: python/stage7b_teacher_replay/stage7b_9_ppo_finetune_smoke_report.json (final_decision=PARTIAL).
- **Stage7B-9.1 GO = PPO fine-tune smoke (native exit code confirmation rerun).** Evidence: stage7b_9_1_ppo_finetune_smoke_final_report.md (final_decision=GO, native_exit_code=0, training_steps_completed=2048, ready_for_stage7b_10_evaluation=true).

## Historical Superseded Reports
- Stage7B-8D stale NO-GO is historical and superseded. Do not use as Stage7B-8D.1 evidence: python/stage7b_teacher_replay/stage7b_8d_extended_onnx_inference_report.json (final_decision=NO_GO).

## Current PPO Smoke Result
- **final_decision: GO** (Stage7B-9.1 native exit code verification)
- **ready_for_stage7b_10_evaluation: true**
- training_steps_completed: 2048
- initialization_method: --initialize-from Stage7B_ImitationSmoke_010_PostKickConfirm
- native_trainer_exit_code: 0
- final_onnx: results/Stage7B_PPOFineTuneSmoke_002/Stage7B_RTS_Student.onnx
- run_id: Stage7B_PPOFineTuneSmoke_002
- report: stage7b_9_1_ppo_finetune_smoke_final_report.md
