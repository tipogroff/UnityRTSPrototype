#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import numpy as np

# Canonical mapping from Unity enum RTS.Core.UnitActionType.
ACTION_TYPE_NAMES: Dict[int, str] = {
    0: "NoOp",
    1: "Move",
    2: "Harvest",
    3: "Return",
    4: "Produce",
    5: "Attack",
}

OBS_OWNER_SLICE = slice(2, 5)  # Neutral, Player1, Player2
OBS_UNIT_TYPE_SLICE = slice(5, 12)  # Resource, Base, Barracks, Worker, Light, Heavy, Ranged


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze Move signal in pinned Week6 BC-ready lineage. Produces compact JSON and Markdown summaries."
        )
    )
    parser.add_argument(
        "--bc-ready-dir",
        type=Path,
        required=True,
        help="Directory with bc_manifest.json, bc_train.npz, bc_validation.npz.",
    )
    parser.add_argument(
        "--early-max-steps",
        type=int,
        nargs="+",
        default=[20, 50],
        help="Inclusive upper bounds for early-step windows, e.g. 20 50.",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        required=True,
        help="Output JSON report path.",
    )
    parser.add_argument(
        "--report-md",
        type=Path,
        required=True,
        help="Output Markdown report path.",
    )
    return parser.parse_args()


def _hist_from_action_types(action_types: np.ndarray, num_actions: int = 6) -> np.ndarray:
    flat = np.asarray(action_types, dtype=np.int64).reshape(-1)
    if flat.size == 0:
        return np.zeros((num_actions,), dtype=np.int64)
    return np.bincount(flat, minlength=num_actions)[:num_actions]


def _hist_payload(hist: np.ndarray) -> Dict[str, Any]:
    total = int(hist.sum())
    by_name: Dict[str, Dict[str, Any]] = {}
    for idx, count in enumerate(hist.tolist()):
        name = ACTION_TYPE_NAMES.get(idx, f"Unknown_{idx}")
        share = (float(count) / float(total)) if total > 0 else 0.0
        by_name[name] = {
            "action_id": idx,
            "count": int(count),
            "share": share,
            "share_pct": 100.0 * share,
        }
    return {
        "total": total,
        "by_action": by_name,
    }


def _load_split(split_path: Path) -> Dict[str, Any]:
    with np.load(split_path, allow_pickle=True) as data:
        targets = np.asarray(data["target_action_branches"], dtype=np.int16)
        step_id = np.asarray(data["step_id"], dtype=np.int32)
        episode_id = np.asarray(data["episode_id"], dtype=np.int32)
        observation = np.asarray(data["input_tensor"], dtype=np.float32)

    action_type_per_cell = targets[..., 0]  # [samples, 576]
    overall_hist = _hist_from_action_types(action_type_per_cell)

    return {
        "samples": int(targets.shape[0]),
        "cells_per_sample": int(targets.shape[1]),
        "overall_hist": overall_hist,
        "step_id": step_id,
        "episode_id": episode_id,
        "action_type_per_cell": action_type_per_cell,
        "observation": observation,
    }


def _actor_cell_mask(observation: np.ndarray) -> np.ndarray:
    # Approximate meaningful actor cells: owned by Player1/Player2 and non-resource unit type.
    owner_block = observation[..., OBS_OWNER_SLICE]  # [..., 3]
    unit_type_block = observation[..., OBS_UNIT_TYPE_SLICE]  # [..., 7]

    owner_idx = np.argmax(owner_block, axis=-1)  # 0 neutral, 1 p1, 2 p2
    is_owned = (owner_idx == 1) | (owner_idx == 2)

    unit_type_idx = np.argmax(unit_type_block, axis=-1)  # 0 resource, others controllable buildings/units
    unit_presence = np.sum(unit_type_block, axis=-1) > 0.5
    is_non_resource = unit_type_idx != 0

    mask_grid = is_owned & unit_presence & is_non_resource
    return mask_grid.reshape(mask_grid.shape[0], -1)  # [samples, 576]


def _compute_early_windows(split_data: Dict[str, Any], early_max_steps: list[int]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    step_id = split_data["step_id"]
    action_type_per_cell = split_data["action_type_per_cell"]

    for max_step in early_max_steps:
        keep = step_id <= int(max_step)
        kept_samples = int(np.count_nonzero(keep))
        if kept_samples == 0:
            hist = np.zeros((6,), dtype=np.int64)
        else:
            hist = _hist_from_action_types(action_type_per_cell[keep])

        out[f"step_0_to_{int(max_step)}"] = {
            "kept_samples": kept_samples,
            "distribution": _hist_payload(hist),
        }

    return out


def _compute_actor_subset(split_data: Dict[str, Any]) -> Dict[str, Any]:
    obs = split_data["observation"]
    action_type_per_cell = split_data["action_type_per_cell"]

    mask = _actor_cell_mask(obs)
    selected = action_type_per_cell[mask]
    hist = _hist_from_action_types(selected)

    total_candidate_cells = int(mask.size)
    selected_cells = int(np.count_nonzero(mask))

    if selected_cells == 0:
        return {
            "available": False,
            "reason": (
                "Could not recover reliable owned controllable actor cells from BC-ready input_tensor encoding "
                "using strict one-hot assumptions; subset analysis skipped to avoid heuristic distortion."
            ),
            "selected_cells": 0,
            "candidate_cells": total_candidate_cells,
        }

    return {
        "available": True,
        "subset_name": "owned_non_resource_actor_cells",
        "subset_note": (
            "Approximate subset built from observation channels: owner in {Player1, Player2} and unit_type != Resource."
        ),
        "selected_cells": selected_cells,
        "candidate_cells": total_candidate_cells,
        "selected_cell_share": (float(selected_cells) / float(total_candidate_cells)) if total_candidate_cells > 0 else 0.0,
        "distribution": _hist_payload(hist),
    }


def _load_adaptation_histograms(bc_manifest_path: Path) -> Dict[str, Any]:
    manifest = json.loads(bc_manifest_path.read_text(encoding="utf-8"))
    source = manifest.get("source", {})
    conversion_report_path = source.get("conversion_report")
    if not conversion_report_path:
        return {
            "available": False,
            "reason": "bc_manifest.json missing source.conversion_report",
        }

    report_path = Path(conversion_report_path)
    if not report_path.exists():
        return {
            "available": False,
            "reason": f"conversion_report.json not found at {report_path}",
        }

    conversion_report = json.loads(report_path.read_text(encoding="utf-8"))
    action_hist = conversion_report.get("action_histograms", {})
    input_hist_dict = {int(k): int(v) for k, v in action_hist.get("input_action_type", {}).items()}
    output_hist_dict = {int(k): int(v) for k, v in action_hist.get("output_action_type", {}).items()}

    input_hist = np.array([input_hist_dict.get(i, 0) for i in range(6)], dtype=np.int64)
    output_hist = np.array([output_hist_dict.get(i, 0) for i in range(6)], dtype=np.int64)

    return {
        "available": True,
        "conversion_report_path": str(report_path),
        "input_teacher_side": _hist_payload(input_hist),
        "output_adapted_side": _hist_payload(output_hist),
        "delta_output_minus_input": {
            ACTION_TYPE_NAMES[i]: int(output_hist[i] - input_hist[i]) for i in range(6)
        },
    }


def _move_share_summary(train_hist: np.ndarray, val_hist: np.ndarray) -> Dict[str, Any]:
    train_total = int(train_hist.sum())
    val_total = int(val_hist.sum())
    train_move = int(train_hist[1])
    val_move = int(val_hist[1])

    return {
        "train_move_count": train_move,
        "train_move_share": (float(train_move) / float(train_total)) if train_total > 0 else 0.0,
        "val_move_count": val_move,
        "val_move_share": (float(val_move) / float(val_total)) if val_total > 0 else 0.0,
    }


def _contrast_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    by_action = payload["by_action"]
    move = by_action["Move"]
    produce = by_action["Produce"]
    ratio = (float(produce["count"]) / float(move["count"])) if move["count"] > 0 else None
    return {
        "move_count": int(move["count"]),
        "move_share": float(move["share"]),
        "produce_count": int(produce["count"]),
        "produce_share": float(produce["share"]),
        "produce_to_move_ratio": ratio,
    }


def build_report(args: argparse.Namespace) -> Dict[str, Any]:
    bc_ready_dir = args.bc_ready_dir
    manifest_path = bc_ready_dir / "bc_manifest.json"
    train_path = bc_ready_dir / "bc_train.npz"
    val_path = bc_ready_dir / "bc_validation.npz"

    train = _load_split(train_path)
    val = _load_split(val_path)

    train_payload = _hist_payload(train["overall_hist"])
    val_payload = _hist_payload(val["overall_hist"])

    action_mapping = {
        str(action_id): name for action_id, name in ACTION_TYPE_NAMES.items()
    }

    report: Dict[str, Any] = {
        "analysis_scope": {
            "bc_ready_dir": str(bc_ready_dir),
            "uses_pinned_bc_ready_as_primary": True,
            "analysis_type": "offline_dataset_diagnostics_only",
        },
        "action_type_mapping": {
            "source_of_truth": "Assets/Scripts/Core/UnitType.cs (RTS.Core.UnitActionType)",
            "mapping": action_mapping,
        },
        "bc_ready_distribution": {
            "train": train_payload,
            "validation": val_payload,
            "train_vs_validation_delta_count": {
                ACTION_TYPE_NAMES[i]: int(train["overall_hist"][i] - val["overall_hist"][i]) for i in range(6)
            },
        },
        "move_share_summary": _move_share_summary(train["overall_hist"], val["overall_hist"]),
        "produce_vs_move_contrast": {
            "train": _contrast_summary(train_payload),
            "validation": _contrast_summary(val_payload),
        },
        "early_step_distribution": {
            "train": _compute_early_windows(train, args.early_max_steps),
            "validation": _compute_early_windows(val, args.early_max_steps),
            "uses_step_metadata_from_bc_ready": True,
        },
        "actor_subset_distribution": {
            "train": _compute_actor_subset(train),
            "validation": _compute_actor_subset(val),
        },
        "adaptation_input_vs_output": _load_adaptation_histograms(manifest_path),
    }

    return report


def _fmt_pct(x: float) -> str:
    return f"{100.0 * x:.3f}%"


def _md_table_from_dist(dist: Dict[str, Any]) -> str:
    lines = [
        "| Action | ID | Count | Share |",
        "|---|---:|---:|---:|",
    ]
    for action_name in ("NoOp", "Move", "Harvest", "Return", "Produce", "Attack"):
        row = dist["by_action"][action_name]
        lines.append(
            f"| {action_name} | {row['action_id']} | {row['count']} | {_fmt_pct(row['share'])} |"
        )
    lines.append(f"| TOTAL | - | {dist['total']} | 100.000% |")
    return "\n".join(lines)


def _build_markdown(report: Dict[str, Any]) -> str:
    mapping_lines = []
    for action_id in range(6):
        mapping_lines.append(f"- {action_id} -> {ACTION_TYPE_NAMES[action_id]}")

    train = report["bc_ready_distribution"]["train"]
    val = report["bc_ready_distribution"]["validation"]
    move_summary = report["move_share_summary"]

    lines: list[str] = []
    lines.append("# Week 6 Move Signal Analysis")
    lines.append("")
    lines.append("## Scope")
    lines.append(f"- Primary source: {report['analysis_scope']['bc_ready_dir']}")
    lines.append("- Offline data diagnostics only. No Unity run, no replay, no retraining.")
    lines.append("")
    lines.append("## Canonical action_type mapping")
    lines.extend(mapping_lines)
    lines.append("")
    lines.append("## BC-ready overall action distribution: train")
    lines.append(_md_table_from_dist(train))
    lines.append("")
    lines.append("## BC-ready overall action distribution: validation")
    lines.append(_md_table_from_dist(val))
    lines.append("")
    lines.append("## Move share summary")
    lines.append(f"- Train Move: {move_summary['train_move_count']} ({_fmt_pct(move_summary['train_move_share'])})")
    lines.append(f"- Validation Move: {move_summary['val_move_count']} ({_fmt_pct(move_summary['val_move_share'])})")
    lines.append("")

    contrast_train = report["produce_vs_move_contrast"]["train"]
    contrast_val = report["produce_vs_move_contrast"]["validation"]
    lines.append("## Produce vs Move contrast")
    lines.append(
        f"- Train Produce/Move ratio: {contrast_train['produce_to_move_ratio']:.3f}"
        if contrast_train["produce_to_move_ratio"] is not None
        else "- Train Produce/Move ratio: undefined"
    )
    lines.append(
        f"- Validation Produce/Move ratio: {contrast_val['produce_to_move_ratio']:.3f}"
        if contrast_val["produce_to_move_ratio"] is not None
        else "- Validation Produce/Move ratio: undefined"
    )
    lines.append("")

    lines.append("## Early-step distribution")
    for split_name in ("train", "validation"):
        lines.append(f"### {split_name.capitalize()}")
        early_payload = report["early_step_distribution"][split_name]
        for window_name, window_payload in early_payload.items():
            lines.append(f"- Window {window_name}, kept_samples={window_payload['kept_samples']}")
            move = window_payload["distribution"]["by_action"]["Move"]
            produce = window_payload["distribution"]["by_action"]["Produce"]
            lines.append(
                f"  Move={move['count']} ({_fmt_pct(move['share'])}), Produce={produce['count']} ({_fmt_pct(produce['share'])})"
            )
    lines.append("")

    lines.append("## Adaptation input vs output")
    adaptation = report["adaptation_input_vs_output"]
    if adaptation.get("available"):
        lines.append(f"- conversion_report: {adaptation['conversion_report_path']}")
        in_move = adaptation["input_teacher_side"]["by_action"]["Move"]
        out_move = adaptation["output_adapted_side"]["by_action"]["Move"]
        lines.append(
            f"- Move teacher_input -> adapted_output: {in_move['count']} ({_fmt_pct(in_move['share'])}) -> "
            f"{out_move['count']} ({_fmt_pct(out_move['share'])})"
        )
    else:
        lines.append(f"- Not available: {adaptation.get('reason', 'unknown reason')}")
    lines.append("")

    lines.append("## Approximate meaningful actor-cell subset")
    for split_name in ("train", "validation"):
        payload = report["actor_subset_distribution"][split_name]
        if not payload.get("available", False):
            lines.append(
                f"- {split_name}: unavailable ({payload.get('reason', 'subset reconstruction not reliable')})"
            )
        else:
            dist = payload["distribution"]
            move = dist["by_action"]["Move"]
            produce = dist["by_action"]["Produce"]
            lines.append(
                f"- {split_name}: selected_cells={payload['selected_cells']} "
                f"({payload['selected_cell_share']:.3%} of all cells), "
                f"Move={move['count']} ({_fmt_pct(move['share'])}), "
                f"Produce={produce['count']} ({_fmt_pct(produce['share'])})"
            )
    lines.append("")

    lines.append("## Conclusion")
    train_move_share = move_summary["train_move_share"]
    val_move_share = move_summary["val_move_share"]
    if train_move_share > 0.05 and val_move_share > 0.05:
        lines.append(
            "- Move signal is clearly present in BC-ready supervision; issue is more likely downstream "
            "(student policy behavior/training dynamics) than complete absence of Move labels."
        )
    elif train_move_share > 0.0 or val_move_share > 0.0:
        lines.append(
            "- Move signal exists but is weak; this may bias policy toward dominant actions and requires deeper training-side analysis."
        )
    else:
        lines.append(
            "- Move signal is absent in BC-ready labels; investigate upstream lineage before training-focused conclusions."
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    report = build_report(args)

    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_md.parent.mkdir(parents=True, exist_ok=True)

    args.report_json.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    args.report_md.write_text(_build_markdown(report), encoding="utf-8")

    print(json.dumps(
        {
            "status": "ok",
            "report_json": str(args.report_json),
            "report_md": str(args.report_md),
            "bc_ready_dir": str(args.bc_ready_dir),
        },
        ensure_ascii=True,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
