#!/usr/bin/env python3
from __future__ import annotations

from stage10d19_common import load_json, write_json


def main() -> int:
    fullmap = load_json("python/week6_student/reports/stage10d19_fullmap_postproduction_behavior_audit.json")
    move = load_json("python/week6_student/reports/stage10d19_move_command_efficiency_audit.json")
    off = load_json("python/week6_student/reports/stage10d19_off_actor_safety_deep_audit.json")
    attack_ready = load_json("python/week6_student/reports/stage10d19_attack_readiness_audit.json")
    attack_labels = load_json("python/week6_student/reports/stage10d19_attack_label_distribution_audit.json")

    pred_to_build = float(move.get("move_prediction_to_build_rate") or 0.0)
    valid_targets = int(move.get("valid_target_move_prediction_count") or 0)
    invalid_targets = int(move.get("invalid_target_move_prediction_count") or 0)

    off_build = int(off.get("off_actor_command_built_count") or 0)
    off_submit = int(off.get("off_actor_submission_count") or 0)
    attack_opp = bool(attack_ready.get("attack_opportunity_present"))
    attack_pred = int(attack_ready.get("attack_predictions_total") or 0)
    attack_cmd_built = int(attack_ready.get("attack_commands_built") or 0)

    label_set = set(attack_labels.get("labels") or [])
    attack_under = ("ATTACK_LABELS_ABSENT" in label_set) or ("ATTACK_LABELS_UNDERREPRESENTED" in label_set)

    branch = "GO_FOR_STAGE10D19_MOVE_COMMAND_EFFICIENCY_FIX_OR_AUGMENTATION"
    rationale = []

    if off_build > 0 or off_submit > 0:
        branch = "GO_FOR_STAGE10D19_RUNTIME_SAFETY_FIX"
        rationale.append("Off-actor non-NoOp reached command build/submission path.")
    elif attack_pred > 0 and attack_cmd_built == 0:
        branch = "GO_FOR_STAGE10D19_ATTACK_DECODER_AUDIT"
        rationale.append("Attack predictions exist but command build failed.")
    elif pred_to_build < 0.15 and valid_targets > max(1, invalid_targets):
        branch = "GO_FOR_STAGE10D19_MOVE_BRANCH_DECODER_AUDIT"
        rationale.append("Many valid-target Move predictions are still blocked before command build.")
    elif pred_to_build < 0.15 and invalid_targets >= valid_targets:
        branch = "GO_FOR_STAGE10D19_MOVE_COMMAND_EFFICIENCY_FIX_OR_AUGMENTATION"
        rationale.append("Move predictions are mostly invalid-target/occupied before decoder build.")
    elif attack_under and attack_opp and off_build == 0 and off_submit == 0:
        branch = "GO_FOR_STAGE10D19_ATTACK_AUGMENTATION_DATASET_BUILD"
        rationale.append("Attack opportunity present with absent/underrepresented attack labels.")
    elif "STAGE10D19_OFF_ACTOR_NEGATIVE_CONTROLS_REQUIRED" in (off.get("labels") or []):
        branch = "GO_FOR_STAGE10D19_OFF_ACTOR_NEGATIVE_CONTROL_AUGMENTATION"
        rationale.append("Off-actor non-NoOp is filtered but high enough for negative-control hardening.")
    else:
        branch = "GO_FOR_STAGE10D20_EXTENDED_TACTICAL_EVALUATION"
        rationale.append("No primary runtime blocker detected for attack/move path in current evidence.")

    payload = {
        "inputs": {
            "fullmap_audit": "python/week6_student/reports/stage10d19_fullmap_postproduction_behavior_audit.json",
            "move_efficiency_audit": "python/week6_student/reports/stage10d19_move_command_efficiency_audit.json",
            "off_actor_safety_audit": "python/week6_student/reports/stage10d19_off_actor_safety_deep_audit.json",
            "attack_readiness_audit": "python/week6_student/reports/stage10d19_attack_readiness_audit.json",
            "attack_label_distribution_audit": "python/week6_student/reports/stage10d19_attack_label_distribution_audit.json",
        },
        "decision": branch,
        "rationale": rationale,
        "key_signals": {
            "move_prediction_to_build_rate": pred_to_build,
            "valid_target_move_prediction_count": valid_targets,
            "invalid_target_move_prediction_count": invalid_targets,
            "off_actor_command_built_count": off_build,
            "off_actor_submission_count": off_submit,
            "attack_opportunity_present": attack_opp,
            "attack_predictions_total": attack_pred,
            "attack_commands_built": attack_cmd_built,
            "attack_labels_underrepresented_or_absent": attack_under,
        },
    }

    out = write_json("python/week6_student/reports/stage10d19_decision_matrix.json", payload)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
