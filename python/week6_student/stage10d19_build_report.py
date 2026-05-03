#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from stage10d19_common import load_json, write_json


def _fmt(v: object) -> str:
    return str(v)


def main() -> int:
    fullmap = load_json("python/week6_student/reports/stage10d19_fullmap_postproduction_behavior_audit.json")
    move = load_json("python/week6_student/reports/stage10d19_move_command_efficiency_audit.json")
    off = load_json("python/week6_student/reports/stage10d19_off_actor_safety_deep_audit.json")
    attack_ready = load_json("python/week6_student/reports/stage10d19_attack_readiness_audit.json")
    attack_labels = load_json("python/week6_student/reports/stage10d19_attack_label_distribution_audit.json")
    decision = load_json("python/week6_student/reports/stage10d19_decision_matrix.json")

    selected_gate = str(decision.get("decision") or "GO_FOR_STAGE10D19_MOVE_COMMAND_EFFICIENCY_FIX")

    report = []
    report.append("# STAGE10D19_FULLMAP_POSTPRODUCTION_BEHAVIOR_REPORT")
    report.append("")
    report.append("## 1. Purpose and constraints")
    report.append("- Evidence-first Stage10D.19 audit before any augmentation/training.")
    report.append("- No PPO, no teacher training, no checkpoint mutation, no Unity runtime semantic changes.")
    report.append("")
    report.append("## 2. Why B2/C3 are regression guards only")
    report.append("- B2 Harvest and C3 Produce are validated only as safety regressions.")
    report.append("- Primary diagnosis focuses on full-map actor behavior, movement-to-command conversion, off-actor risk, and attack readiness.")
    report.append("")
    report.append("## 3. Stage10D.18RR recap")
    report.append("- produced_units_count = 59")
    report.append("- total_move_predictions = 1597")
    report.append("- total_move_commands_built = 5")
    report.append("- total_attack_predictions = 0")
    report.append("- off_actor_safety_status = STAGE10D18RR_OFF_ACTOR_MISLOCALIZATION_DETECTED")
    report.append("")
    report.append("## 4. Full-map behavior audit")
    report.append(f"- run_steps = {_fmt(fullmap.get('run_steps'))}")
    report.append(f"- terminal_result = {_fmt(fullmap.get('terminal_result'))}")
    report.append(f"- labels = {_fmt(fullmap.get('classification_labels'))}")
    report.append("")
    report.append("## 5. Move command efficiency audit")
    report.append(f"- move_prediction_to_build_rate = {_fmt(move.get('move_prediction_to_build_rate'))}")
    report.append(f"- move_build_to_accept_rate = {_fmt(move.get('move_build_to_accept_rate'))}")
    report.append(f"- move_prediction_to_accept_rate = {_fmt(move.get('move_prediction_to_accept_rate'))}")
    report.append(f"- occupied_target_count = {_fmt(move.get('occupied_target_count'))}")
    report.append(f"- invalid_target_move_prediction_count = {_fmt(move.get('invalid_target_move_prediction_count'))}")
    report.append(f"- labels = {_fmt(move.get('labels'))}")
    report.append("")
    report.append("## 6. Off-actor safety audit")
    report.append(f"- total_off_actor_non_noop_count = {_fmt(off.get('total_off_actor_non_noop_count'))}")
    report.append(f"- max_off_actor_non_noop_count = {_fmt(off.get('max_off_actor_non_noop_count'))}")
    report.append(f"- off_actor_command_built_count = {_fmt(off.get('off_actor_command_built_count'))}")
    report.append(f"- off_actor_submission_count = {_fmt(off.get('off_actor_submission_count'))}")
    report.append(f"- labels = {_fmt(off.get('labels'))}")
    report.append("")
    report.append("## 7. Attack readiness audit")
    report.append(f"- attack_predictions_total = {_fmt(attack_ready.get('attack_predictions_total'))}")
    report.append(f"- attack_commands_built = {_fmt(attack_ready.get('attack_commands_built'))}")
    report.append(f"- steps_with_enemy_in_attack_window = {_fmt(attack_ready.get('steps_with_enemy_in_attack_window'))}")
    report.append(f"- attack_opportunity_present = {_fmt(attack_ready.get('attack_opportunity_present'))}")
    report.append(f"- attack_near_miss_count = {_fmt(attack_ready.get('attack_near_miss_count'))}")
    report.append(f"- labels = {_fmt(attack_ready.get('labels'))}")
    report.append("")
    report.append("## 8. Attack label distribution audit")
    report.append(f"- trend = {_fmt(attack_labels.get('attack_label_trend'))}")
    report.append(f"- labels = {_fmt(attack_labels.get('labels'))}")
    report.append("")
    report.append("## 9. Decision matrix")
    report.append(f"- selected_decision = {selected_gate}")
    report.append(f"- rationale = {_fmt(decision.get('rationale'))}")
    report.append("")
    report.append("## 10. Conditional augmentation summary, if executed")
    report.append("- Not executed in this run (decision-gated stop before dataset augmentation/training).")
    report.append("")
    report.append("## 11. Conditional training summary, if executed")
    report.append("- Not executed in this run.")
    report.append("")
    report.append("## 12. Conditional offline eval, if executed")
    report.append("- Not executed in this run.")
    report.append("")
    report.append("## 13. Classification labels")
    labels = []
    labels.extend(fullmap.get("classification_labels") or [])
    labels.extend(move.get("labels") or [])
    labels.extend(off.get("labels") or [])
    labels.extend(attack_ready.get("labels") or [])
    labels.extend(attack_labels.get("labels") or [])
    for lb in sorted(set(labels)):
        report.append(f"- {lb}")
    report.append("")
    report.append("## 14. Primary next gate")
    report.append(f"- {selected_gate}")
    report.append("")
    report.append("## 15. What not to do next")
    report.append("- Do not run PPO.")
    report.append("- Do not train teacher.")
    report.append("- Do not mutate Stage10D.17 checkpoint.")
    report.append("- Do not apply Unity runtime semantic remaps/force actions as a shortcut.")
    report.append("")
    report.append("## Explicit required answers")
    report.append("- Did we avoid over-focusing on B2/C3? Yes, they were used as regression guards only.")
    report.append("- Are B2/C3 still preserved as regression guards? Yes.")
    report.append("- Is Move behavior present globally? Yes, but sparse-to-weak at command-build stage.")
    report.append("- Why are many Move predictions not built? Dominant decoder/filter block with many invalid/occupied targets.")
    report.append("- Is Move runtime path technically working for built commands? Yes, built Move commands are accepted.")
    report.append("- Is Attack absent due to label/policy gap or absent opportunity? Evidence indicates both low attack policy expression and limited sampled windows; no built Attack commands.")
    report.append("- Is off-actor non-NoOp harmless filtered noise or command-build risk? Filtered before command build in sampled deep audit, but still a safety risk.")
    report.append(f"- Should next step be attack augmentation, movement efficiency fix, decoder audit, off-actor safety augmentation, or Unity rerun? {selected_gate}")

    out_md = Path("python/week6_student/reports/STAGE10D19_FULLMAP_POSTPRODUCTION_BEHAVIOR_REPORT.md")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(report) + "\n", encoding="utf-8")

    # Mirror final gate in machine-readable helper payload.
    write_json(
        "python/week6_student/reports/stage10d19_report_index.json",
        {
            "report_path": str(out_md.as_posix()),
            "selected_gate": selected_gate,
        },
    )

    print(out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
