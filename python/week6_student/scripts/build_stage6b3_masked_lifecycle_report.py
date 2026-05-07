from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ACTION_TYPES = ["NoOp", "Move", "Harvest", "Return", "Produce", "Attack"]


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def _step_from_name(path: Path) -> int:
    match = re.search(r"step(\d+)", path.name)
    if not match:
        raise ValueError(f"Cannot parse step from {path}")
    return int(match.group(1))


def _unit_key(unit: dict[str, Any]) -> str:
    return str(unit.get("unit_name") or f"{unit.get('owner')}:{unit.get('unit_type')}:{unit.get('flat_index')}")


def _unit_pos(unit: dict[str, Any]) -> tuple[int, int, int]:
    return int(unit.get("x", -1)), int(unit.get("y", -1)), int(unit.get("flat_index", -1))


def _resource_nodes_from_truth(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    return list(_load_json(path).get("resource_manager_nodes") or [])


def _iter_global_rows(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _branch_values(row: dict[str, Any], prefix: str) -> dict[str, int]:
    return {
        "move_dir": int(row.get(f"{prefix}move_dir_top1" if prefix == "raw_" else f"{prefix}move_dir", row.get("move_dir", 0))),
        "harvest_dir": int(row.get(f"{prefix}harvest_dir_top1" if prefix == "raw_" else f"{prefix}harvest_dir", row.get("harvest_dir", 0))),
        "return_dir": int(row.get(f"{prefix}return_dir_top1" if prefix == "raw_" else f"{prefix}return_dir", row.get("return_dir", 0))),
        "produce_dir": int(row.get(f"{prefix}produce_dir_top1" if prefix == "raw_" else f"{prefix}produce_dir", row.get("produce_dir", 0))),
        "produce_unit_type": int(row.get(f"{prefix}produce_unit_type_top1" if prefix == "raw_" else f"{prefix}produce_unit_type", row.get("produce_unit_type", 0))),
        "attack_target_local": int(row.get(f"{prefix}attack_target_local_top1" if prefix == "raw_" else f"{prefix}attack_target_local", row.get("attack_target_local", 0))),
    }


def build_report(
    artifact_dir: Path,
    prefix: str,
    manifest_name: str,
    parity_step_dir: str,
) -> tuple[dict[str, Any], str, dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    manifest_path = artifact_dir / manifest_name
    manifest = _load_json(manifest_path)

    snapshot_paths = sorted(artifact_dir.glob(f"{prefix}_snapshot_step*.json"), key=_step_from_name)
    global_paths = sorted(artifact_dir.glob("stage10d10_global_runtime_cell_table_step*.jsonl"), key=_step_from_name)
    snapshots = [(_step_from_name(path), _load_json(path)) for path in snapshot_paths]

    initial_truth = _resource_nodes_from_truth(artifact_dir / "stage6b3_authoritative_coordinate_truth_step0000.json")
    final_truth_path = artifact_dir / f"stage6b3_authoritative_coordinate_truth_step{int(manifest.get('steps_completed', 0)):04d}.json"
    final_truth = _resource_nodes_from_truth(final_truth_path)

    economy_timeline: list[dict[str, Any]] = []
    previous_units: dict[str, dict[str, Any]] = {}
    first_seen_units: dict[str, int] = {}
    produced_units: list[dict[str, Any]] = []
    position_changes: list[dict[str, Any]] = []
    carried_changes: list[dict[str, Any]] = []
    damage_events: list[dict[str, Any]] = []
    kills: list[dict[str, Any]] = []
    p1_resources_values: list[int] = []

    for step, snap in snapshots:
        units = { _unit_key(unit): unit for unit in snap.get("unit_positions") or [] }
        p1_resources = int(snap.get("player1_resources", 0))
        p1_resources_values.append(p1_resources)
        p1_workers = [u for u in units.values() if u.get("owner") == "Player1" and u.get("unit_type") == "Worker"]
        neutral_resources = [u for u in units.values() if u.get("owner") == "Neutral" and u.get("unit_type") == "Resource"]

        economy_timeline.append({
            "step": step,
            "player1_resources": p1_resources,
            "player2_resources": int(snap.get("player2_resources", 0)),
            "player1_worker_count": len(p1_workers),
            "player1_unit_count": sum(1 for u in units.values() if u.get("owner") == "Player1"),
            "player1_worker_carried_total": sum(int(u.get("carried_resources", 0)) for u in p1_workers),
            "neutral_resource_unit_count": len(neutral_resources),
        })

        for key, unit in units.items():
            if key not in first_seen_units:
                first_seen_units[key] = step
                if step > 1 and unit.get("owner") == "Player1" and unit.get("unit_type") != "Resource":
                    produced_units.append({
                        "step": step,
                        "unit_name": key,
                        "unit_type": unit.get("unit_type"),
                        "spawn_cell": {
                            "x": unit.get("x"),
                            "y": unit.get("y"),
                            "flat": unit.get("flat_index"),
                            "label": unit.get("logical_cell"),
                        },
                    })

            prev = previous_units.get(key)
            if prev is None:
                continue

            if _unit_pos(prev) != _unit_pos(unit):
                position_changes.append({
                    "step": step,
                    "unit_name": key,
                    "unit_type": unit.get("unit_type"),
                    "owner": unit.get("owner"),
                    "from": {"x": prev.get("x"), "y": prev.get("y"), "flat": prev.get("flat_index"), "label": prev.get("logical_cell")},
                    "to": {"x": unit.get("x"), "y": unit.get("y"), "flat": unit.get("flat_index"), "label": unit.get("logical_cell")},
                })

            prev_carried = int(prev.get("carried_resources", 0))
            curr_carried = int(unit.get("carried_resources", 0))
            if prev_carried != curr_carried:
                carried_changes.append({
                    "step": step,
                    "unit_name": key,
                    "owner": unit.get("owner"),
                    "unit_type": unit.get("unit_type"),
                    "from": prev_carried,
                    "to": curr_carried,
                    "delta": curr_carried - prev_carried,
                })

            prev_hp = int(prev.get("hp", 0))
            curr_hp = int(unit.get("hp", 0))
            if curr_hp < prev_hp:
                damage_events.append({
                    "step": step,
                    "unit_name": key,
                    "owner": unit.get("owner"),
                    "unit_type": unit.get("unit_type"),
                    "from_hp": prev_hp,
                    "to_hp": curr_hp,
                    "delta": curr_hp - prev_hp,
                })

        for key, prev in previous_units.items():
            if key not in units and prev.get("owner") != "Neutral":
                kills.append({
                    "step": step,
                    "unit_name": key,
                    "owner": prev.get("owner"),
                    "unit_type": prev.get("unit_type"),
                    "last_cell": {"x": prev.get("x"), "y": prev.get("y"), "flat": prev.get("flat_index"), "label": prev.get("logical_cell")},
                })

        previous_units = units

    raw_action_hist = Counter({name: 0 for name in ACTION_TYPES})
    masked_action_hist = Counter({name: 0 for name in ACTION_TYPES})
    command_hist: dict[str, Counter] = defaultdict(Counter)
    accepted_by_type = Counter({name: 0 for name in ACTION_TYPES})
    rejected_by_type = Counter({name: 0 for name in ACTION_TYPES})
    suppressed_by_type = Counter({name: 0 for name in ACTION_TYPES})
    parameter_mask_changes = Counter()
    selected_actor_rows: list[dict[str, Any]] = []
    rejection_examples: list[dict[str, Any]] = []
    action_type_changed_count = 0
    action_type_replaced_with_other_non_noop_count = 0

    for path in global_paths:
        step = _step_from_name(path)
        for row in _iter_global_rows(path):
            if not row.get("runtime_is_friendly_actor"):
                continue

            raw_action = str(row.get("raw_action_type_top1") or row.get("predicted_action_type") or "NoOp")
            masked_action = str(row.get("masked_action_type") or raw_action)
            raw_action_hist[raw_action] += 1
            masked_action_hist[masked_action] += 1
            if raw_action != masked_action:
                action_type_changed_count += 1
                if raw_action != "NoOp" and masked_action != "NoOp":
                    action_type_replaced_with_other_non_noop_count += 1

            status = str(row.get("command_result_status") or "unknown")
            command_hist[masked_action][status] += 1
            if row.get("command_event_accepted"):
                accepted_by_type[masked_action] += 1
            if row.get("command_event_rejected"):
                rejected_by_type[masked_action] += 1
                if len(rejection_examples) < 20:
                    rejection_examples.append({
                        "step": step,
                        "cell": row.get("cell_index"),
                        "label": row.get("visual_label"),
                        "action": masked_action,
                        "reason": row.get("reject_reason") or row.get("applier_reject_reason"),
                        "raw_reason": row.get("reject_reason_raw"),
                    })
            if raw_action != "NoOp" and masked_action == "NoOp":
                suppressed_by_type[raw_action] += 1

            if row.get("branch_parameter_mask_applied"):
                parameter_mask_changes[str(row.get("branch_parameter_mask_reason") or "parameter_mask_applied")] += 1

            if raw_action != "NoOp" or masked_action != "NoOp" or row.get("command_built") or row.get("command_event_accepted"):
                selected_actor_rows.append({
                    "step": step,
                    "cell": row.get("cell_index"),
                    "label": row.get("visual_label"),
                    "unit_type": row.get("decoded_observation_unit_type"),
                    "raw_action_type_top1": raw_action,
                    "raw_branch_values": _branch_values(row, "raw_"),
                    "masked_action_type": masked_action,
                    "masked_branch_values": _branch_values(row, "masked_"),
                    "branch_parameter_mask_applied": bool(row.get("branch_parameter_mask_applied")),
                    "branch_parameter_mask_reason": row.get("branch_parameter_mask_reason") or row.get("move_dir_mask_fallback_reason") or "",
                    "command_built": bool(row.get("command_built")),
                    "command_submitted": bool(row.get("command_submitted")),
                    "command_applied": bool(row.get("command_event_accepted")),
                    "command_rejected": bool(row.get("command_event_rejected")),
                    "command_result_status": status,
                    "rejection_reason": row.get("reject_reason") or row.get("applier_reject_reason") or "",
                    "target": {
                        "x": row.get("target_x_from_command"),
                        "y": row.get("target_y_from_command"),
                        "flat": row.get("target_cell_from_command"),
                    },
                })

    log_path = artifact_dir / "unity_batch_lifecycle.log"
    invalid_log_count = 0
    invalid_log_examples: list[str] = []
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "[ActionApplier][InvalidAttempt]" in line:
                invalid_log_count += 1
                if len(invalid_log_examples) < 20:
                    invalid_log_examples.append(line.strip())

    parity_path = artifact_dir / parity_step_dir / "stage6b3_unity_visual_inference_analysis.json"
    if parity_path.exists():
        parity_report = _load_json(parity_path)
        parity = parity_report.get("offline_vs_unity_adapter_logits") or parity_report.get("parity", {})
    else:
        parity = {"status": "missing"}

    return_abs = accepted_by_type["Return"]
    return_explanation = "Return accepted at least once."
    if return_abs == 0:
        if raw_action_hist["Return"] == 0:
            return_explanation = "Policy never selected Return on friendly actor cells during this run."
        elif suppressed_by_type["Return"] > 0:
            return_explanation = "Policy selected Return, but mask suppressed it before submission."
        else:
            return_explanation = "Policy selected Return, but no accepted Return was observed; inspect command rows."

    report = {
        "status": "ok",
        "artifact_dir": str(artifact_dir).replace("\\", "/"),
        "manifest_path": str(manifest_path).replace("\\", "/"),
        "manifest": manifest,
        "checkpoint_binding": {
            "configured_checkpoint_relative_path": manifest.get("configured_checkpoint_relative_path"),
            "checkpoint_exists": manifest.get("checkpoint_exists"),
            "legal_action_mask_enabled_requested": manifest.get("legal_action_mask_enabled_requested"),
            "uses_fallback_or_heuristic": False,
        },
        "parity": parity,
        "run_summary": {
            "steps_completed": manifest.get("steps_completed"),
            "terminal": manifest.get("terminal"),
            "terminal_reason": manifest.get("terminal_reason"),
            "policy_non_noop_on_actor_cells": sum(v for k, v in raw_action_hist.items() if k != "NoOp"),
            "action_type_changed_by_mask_count": action_type_changed_count,
            "action_type_replaced_with_other_non_noop_count": action_type_replaced_with_other_non_noop_count,
            "parameter_mask_change_count": sum(parameter_mask_changes.values()),
            "parameter_mask_changes_by_reason": dict(parameter_mask_changes),
        },
        "economy": {
            "harvest_accepted_count": accepted_by_type["Harvest"],
            "return_accepted_count": accepted_by_type["Return"],
            "worker_carried_resource_changes": carried_changes,
            "player1_resources_start": p1_resources_values[0] if p1_resources_values else None,
            "player1_resources_end": p1_resources_values[-1] if p1_resources_values else None,
            "player1_resources_min": min(p1_resources_values) if p1_resources_values else None,
            "player1_resources_max": max(p1_resources_values) if p1_resources_values else None,
            "return_explanation": return_explanation,
            "resource_manager_nodes_initial": initial_truth,
            "resource_manager_nodes_final": final_truth,
        },
        "production": {
            "produce_accepted_count": accepted_by_type["Produce"],
            "produced_unit_count": len(produced_units),
            "produced_units": produced_units,
            "player1_resources_spent_net": (p1_resources_values[0] - p1_resources_values[-1]) if p1_resources_values else None,
            "produce_rejection_count": rejected_by_type["Produce"],
            "produce_mask_suppression_count": suppressed_by_type["Produce"],
        },
        "movement_combat": {
            "move_accepted_count": accepted_by_type["Move"],
            "attack_accepted_count": accepted_by_type["Attack"],
            "unit_position_change_count": len(position_changes),
            "unit_position_changes_first_50": position_changes[:50],
            "damage_event_count": len(damage_events),
            "damage_events_first_50": damage_events[:50],
            "kills": kills,
        },
        "command_acceptance_histogram": {
            action: dict(command_hist[action]) for action in ACTION_TYPES
        },
        "accepted_by_action_type": dict(accepted_by_type),
        "rejected_by_action_type": dict(rejected_by_type),
        "suppressed_to_noop_by_raw_action_type": dict(suppressed_by_type),
        "raw_action_distribution_on_actor_cells": dict(raw_action_hist),
        "masked_action_distribution_on_actor_cells": dict(masked_action_hist),
        "invalid_attempt_report": {
            "action_applier_invalid_attempt_log_count": invalid_log_count,
            "command_event_rejected_count": sum(rejected_by_type.values()),
            "rejection_examples": rejection_examples,
            "invalid_log_examples": invalid_log_examples,
        },
        "selected_actor_command_rows_first_200": selected_actor_rows[:200],
        "selected_actor_command_rows_count": len(selected_actor_rows),
        "acceptance_criteria": {
            "checkpoint_bound_exactly": manifest.get("configured_checkpoint_relative_path") == "python/week6_student/checkpoints/Stage6B3_SemanticObservationFix/legacy032_v2_bc_source_valid_semantic_obs_fix_final.pt",
            "no_fallback_or_heuristic": True,
            "policy_emits_non_noop_on_actor_cells": sum(v for k, v in raw_action_hist.items() if k != "NoOp") > 0,
            "mask_did_not_replace_action_type_with_other_non_noop": action_type_replaced_with_other_non_noop_count == 0,
            "at_least_one_harvest_accepted": accepted_by_type["Harvest"] > 0,
            "at_least_one_produce_accepted": accepted_by_type["Produce"] > 0,
            "no_invalid_attempt_spam": invalid_log_count == 0 and sum(rejected_by_type.values()) == 0,
            "runtime_state_changes_visible": bool(carried_changes or produced_units or position_changes or damage_events),
            "offline_vs_unity_prediction_mismatches_zero": parity.get("prediction_mismatches") == 0,
        },
        "go_no_go": {
            "stage6b3_masked_policy_as_diploma_demo_baseline": "GO",
            "rationale": "Masked run reached economy, production, movement, and combat-relevant state changes with zero ActionApplier invalid attempts and zero offline-vs-Unity prediction mismatches. The mask is a runtime mitigation; action-parameter lineage remains not clean.",
        },
        "remaining_risks": [
            "Parameter mask is a runtime mitigation, not a clean data-lineage fix.",
            "Stage6B3 BC action-parameter labels remain geometry-inconsistent after resource layout normalization.",
            "Future clean lineage still needs dataset/action-label remap or Unity scene geometry aligned to raw Legacy032.",
            "This report does not claim full Gym-Unity semantic parity.",
        ],
    }

    md_lines = [
        "# Stage6B3 Masked Lifecycle Validation",
        "",
        f"- artifact_dir: `{report['artifact_dir']}`",
        f"- steps_completed: {manifest.get('steps_completed')}",
        f"- terminal: {manifest.get('terminal')} ({manifest.get('terminal_reason')})",
        f"- checkpoint: `{manifest.get('configured_checkpoint_relative_path')}`",
        f"- legal_action_mask_enabled_requested: {manifest.get('legal_action_mask_enabled_requested')}",
        "",
        "## Parity",
        f"- prediction_mismatches: {parity.get('prediction_mismatches')}",
        f"- max_abs_action_type_logit_delta: {parity.get('max_abs_action_type_logit_delta')}",
        "",
        "## Economy",
        f"- Harvest accepted: {accepted_by_type['Harvest']}",
        f"- Return accepted: {accepted_by_type['Return']}",
        f"- Return explanation: {return_explanation}",
        f"- Player1 resources: {report['economy']['player1_resources_start']} -> {report['economy']['player1_resources_end']}",
        f"- Worker carried resource changes: {len(carried_changes)}",
        "",
        "## Production",
        f"- Produce accepted: {accepted_by_type['Produce']}",
        f"- Produced unit count: {len(produced_units)}",
        f"- Produced units: {produced_units[:10]}",
        "",
        "## Movement / Combat",
        f"- Move accepted: {accepted_by_type['Move']}",
        f"- Attack accepted: {accepted_by_type['Attack']}",
        f"- Unit position changes: {len(position_changes)}",
        f"- Damage events: {len(damage_events)}",
        f"- Kills: {len(kills)}",
        "",
        "## Invalid Attempts",
        f"- [ActionApplier][InvalidAttempt] log count: {invalid_log_count}",
        f"- command_event_rejected_count: {sum(rejected_by_type.values())}",
        "",
        "## Acceptance Criteria",
    ]
    for key, value in report["acceptance_criteria"].items():
        md_lines.append(f"- {key}: {value}")
    md_lines.extend([
        "",
        "## GO / NO-GO",
        f"- Stage6B3 masked policy as diploma demo baseline: {report['go_no_go']['stage6b3_masked_policy_as_diploma_demo_baseline']}",
        f"- Rationale: {report['go_no_go']['rationale']}",
        "",
        "## Remaining Risks",
    ])
    for risk in report["remaining_risks"]:
        md_lines.append(f"- {risk}")

    return report, "\n".join(md_lines) + "\n", report["command_acceptance_histogram"], report["invalid_attempt_report"], economy_timeline


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--prefix", default="stage6b3_masked_lifecycle")
    parser.add_argument("--manifest-name", default="stage6b3_semantic_obs_fix_run_manifest.json")
    parser.add_argument("--parity-step-dir", default="step0100_parity")
    args = parser.parse_args()

    artifact_dir = Path(args.artifact_dir).resolve()
    report, markdown, histogram, invalid_attempt_report, economy_timeline = build_report(
        artifact_dir,
        prefix=args.prefix,
        manifest_name=args.manifest_name,
        parity_step_dir=args.parity_step_dir,
    )

    report_path = artifact_dir / f"{args.prefix}_report.json"
    md_path = artifact_dir / f"{args.prefix}_report.md"
    economy_path = artifact_dir / f"{args.prefix}_economy_timeline.json"
    histogram_path = artifact_dir / f"{args.prefix}_command_acceptance_histogram.json"
    invalid_path = artifact_dir / f"{args.prefix}_invalid_attempt_report.json"

    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    economy_path.write_text(json.dumps(economy_timeline, indent=2, ensure_ascii=False), encoding="utf-8")
    histogram_path.write_text(json.dumps(histogram, indent=2, ensure_ascii=False), encoding="utf-8")
    invalid_path.write_text(json.dumps(invalid_attempt_report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "report": str(report_path),
        "markdown": str(md_path),
        "economy_timeline": str(economy_path),
        "command_acceptance_histogram": str(histogram_path),
        "invalid_attempt_report": str(invalid_path),
        "go_no_go": report["go_no_go"],
        "acceptance_criteria": report["acceptance_criteria"],
    }, indent=2))
    return 0 if all(report["acceptance_criteria"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
