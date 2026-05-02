#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Stage10D.1 markdown report from diagnostic JSON files")
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("python/week6_student/reports"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "python/week6_student/reports/"
            "LEGACY032_UNITY_V2_STAGE10D1_DATASET_DISTRIBUTION_DIAGNOSTIC_REPORT.md"
        ),
    )
    return parser.parse_args()


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.6f}"
    return str(v)


def _decide_classification(
    dataset_stats: Dict[str, Any],
    channel_comp: Dict[str, Any],
    loss_audit: Dict[str, Any],
    nn_diag: Dict[str, Any],
) -> Dict[str, Any]:
    combined = dataset_stats["split_stats"]["combined"]
    own_actor_noop_share = combined["own_actor_cells"]["action_type_share"]["NoOp"]
    own_worker_noop_share = combined["own_worker_cells"]["action_type_share"]["NoOp"]
    own_base_noop_share = combined["own_base_cells"]["action_type_share"]["NoOp"]

    flags = channel_comp.get("flags", {})
    encoding_mismatch = bool(flags.get("owner_relative_vs_absolute_encoding_mismatch_suspected"))

    loss_dom = bool(
        loss_audit.get("audit", {})
        .get("validation_metrics_could_be_dominated_by_empty_cell_noop", {})
        .get("bool")
    )

    b2_l2_train = nn_diag["focus_cells"]["B2"]["neighbors"]["l2"]["train"]
    c3_l2_train = nn_diag["focus_cells"]["C3"]["neighbors"]["l2"]["train"]

    primary = "INCONCLUSIVE_NEEDS_NEXT_DIAGNOSTIC"
    gate = "GO_FOR_NEXT_DIAGNOSTIC"
    secondary: List[str] = []

    if encoding_mismatch:
        primary = "OBSERVATION_ENCODING_MISMATCH"
        gate = "GO_FOR_OBSERVATION_ENCODING_REMEDIATION"
    elif loss_dom:
        primary = "TRAINING_OBJECTIVE_DOMINATED_BY_GRID_NOOP"
        gate = "GO_FOR_ACTOR_CELL_WEIGHTED_LOSS"
        if own_actor_noop_share > 0.95:
            secondary.append("DATASET_ACTOR_CELL_NOOP_DOMINANCE")
            gate = "GO_FOR_DATASET_REBALANCING"
    elif own_worker_noop_share > 0.95 and own_base_noop_share > 0.95:
        primary = "DATASET_ACTOR_CELL_NOOP_DOMINANCE"
        gate = "GO_FOR_DATASET_REBALANCING"
    elif b2_l2_train and c3_l2_train:
        primary = "MODEL_GENERALIZATION_FAILURE"
        gate = "GO_FOR_MODEL_LOSS_REMEDIATION"
    else:
        primary = "INCONCLUSIVE_NEEDS_NEXT_DIAGNOSTIC"
        gate = "GO_FOR_NEXT_DIAGNOSTIC"

    return {
        "primary_classification": primary,
        "secondary_classifications": secondary,
        "gate_decision": gate,
    }


def main() -> int:
    args = parse_args()

    dataset_json = _load(args.reports_dir / "stage10d1_dataset_action_distribution.json")
    nn_json = _load(args.reports_dir / "stage10d1_unity_vs_bc_nearest_neighbors.json")
    channel_json = _load(args.reports_dir / "stage10d1_observation_channel_comparison.json")
    loss_json = _load(args.reports_dir / "stage10d1_training_loss_audit.json")

    decision = _decide_classification(dataset_json, channel_json, loss_json, nn_json)

    combined = dataset_json["split_stats"]["combined"]
    b2_detect = channel_json["focus_detection"]["B2_detected_as_own_worker"]
    c3_detect = channel_json["focus_detection"]["C3_detected_as_own_base"]

    lines: List[str] = []
    lines.append("# LEGACY032 UNITY V2 STAGE10D1 DATASET DISTRIBUTION DIAGNOSTIC REPORT")
    lines.append("")
    lines.append("## Scope")
    lines.append("- Read-only diagnostic only.")
    lines.append("- No behavior fix, no retraining, no PPO, no checkpoint/dataset/contract mutation.")
    lines.append("- Runtime authority remains ActionApplier/MatchManager.")
    lines.append("")

    lines.append("## Contract Compatibility")
    cc = dataset_json["contract_check"]
    lines.append(f"- target_action_contract: {_fmt(cc.get('target_action_contract'))}")
    lines.append(f"- branch_sizes: {_fmt(cc.get('branch_sizes'))}")
    lines.append(f"- observation_shape_per_sample: {_fmt(cc.get('observation_shape_per_sample'))}")
    lines.append(f"- action_shape_per_sample: {_fmt(cc.get('action_shape_per_sample'))}")
    lines.append(f"- unity_v2_compatible: {_fmt(cc.get('unity_v2_compatible'))}")
    lines.append("")

    lines.append("## Dataset Action-Type Distribution (Combined)")
    lines.append("| Group | Total | NoOp | Move | Harvest | Return | Produce | Attack |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for group_name, payload in combined.items():
        c = payload["action_type_count"]
        lines.append(
            "| "
            + group_name
            + f" | {payload['total_count']} | {c['NoOp']} | {c['Move']} | {c['Harvest']} | {c['Return']} | {c['Produce']} | {c['Attack']} |"
        )
    lines.append("")

    lines.append("## Unity Focus Cell Detection")
    lines.append(f"- B2 detected as own Worker: {b2_detect}")
    lines.append(f"- C3 detected as own Base: {c3_detect}")
    lines.append("")

    lines.append("## Observation Comparison Flags")
    for k, v in channel_json.get("flags", {}).items():
        lines.append(f"- {k}: {_fmt(v)}")
    lines.append("")

    lines.append("## Nearest Neighbors Summary")
    for focus in ("B2", "C3"):
        lines.append(f"### {focus}")
        for metric in ("l2", "cosine"):
            for split in ("train", "validation"):
                rows = nn_json["focus_cells"][focus]["neighbors"][metric][split]
                top = rows[0] if rows else None
                if top is None:
                    lines.append(f"- {metric}/{split}: no candidates")
                else:
                    lines.append(
                        f"- {metric}/{split}: best distance={top['distance']:.6f}, "
                        f"action_type={top['action_type_label']['name']}, "
                        f"owner={top['detected_owner']}, unit={top['detected_unit_type']}"
                    )
        lines.append("")

    lines.append("## Training Objective Audit")
    for k, v in loss_json.get("audit", {}).items():
        lines.append(f"- {k}: {_fmt(v.get('bool'))}; evidence={_fmt(v.get('evidence'))}")
    lines.append("")

    lines.append("## Root-Cause Classification")
    lines.append(f"- primary: {decision['primary_classification']}")
    if decision["secondary_classifications"]:
        lines.append(f"- secondary: {', '.join(decision['secondary_classifications'])}")
    else:
        lines.append("- secondary: none")
    lines.append("")

    lines.append("## Gate Decision")
    lines.append(f"- {decision['gate_decision']}")
    lines.append("")

    lines.append("## Honesty Notes")
    lines.append("- High aggregate NoOp share over all 576 cells is expected in sparse RTS grids and is not, by itself, a failure signal.")
    lines.append("- Target condition is actor-cell NoOp collapse on Unity own actor cells (B2/C3 context).")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(args.output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
