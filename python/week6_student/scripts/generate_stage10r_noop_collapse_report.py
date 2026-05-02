from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Stage10R NoOp collapse markdown report from a snapshot JSON.")
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=None,
        help="Path to stage10r_noop_collapse_snapshot_stepXXXX.json (defaults to latest in reports dir)",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("python/week6_student/reports"),
        help="Reports directory for snapshot discovery and output.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/LEGACY032_UNITY_V2_STAGE10R_NOOP_COLLAPSE_ANALYSIS_REPORT.md"),
        help="Output markdown report path.",
    )
    return parser.parse_args()


def find_latest_snapshot(reports_dir: Path) -> Path:
    candidates = sorted(
        reports_dir.glob("stage10r_noop_collapse_snapshot_step*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            f"No Stage10R snapshots found in {reports_dir}. Expected stage10r_noop_collapse_snapshot_step*.json"
        )
    return candidates[0]


def fmt_prob(value: Any) -> str:
    try:
        return f"{float(value):.4f}"
    except Exception:
        return "n/a"


def action_top3_text(top3: list[dict[str, Any]] | None) -> str:
    if not top3:
        return "unavailable"
    parts: list[str] = []
    for item in top3[:3]:
        if not isinstance(item, dict):
            continue
        name = item.get("class_name", "?")
        cid = item.get("class_id", "?")
        prob = fmt_prob(item.get("probability"))
        parts.append(f"{name}({cid}, p={prob})")
    return " > ".join(parts) if parts else "unavailable"


def summarize_channels(channels: list[float] | None, names: list[str] | None) -> list[str]:
    if not channels or not names or len(channels) != len(names):
        return ["channel slice unavailable"]
    lines: list[str] = []
    for idx, name in enumerate(names):
        value = channels[idx]
        if abs(float(value)) > 1e-6:
            lines.append(f"- {idx:02d} {name}: {float(value):.6f}")
    if not lines:
        lines.append("- all channels are zero")
    return lines


def main() -> int:
    args = parse_args()
    reports_dir = args.reports_dir.resolve()
    snapshot_path = args.snapshot.resolve() if args.snapshot else find_latest_snapshot(reports_dir)
    output_path = args.output.resolve()

    payload = json.loads(snapshot_path.read_text(encoding="utf-8-sig"))

    focus_rows: list[dict[str, Any]] = payload.get("focus_cell_diagnostics", []) or []
    focus_map = {row.get("logical_label", ""): row for row in focus_rows if isinstance(row, dict)}
    b2 = focus_map.get("B2", {})
    c3 = focus_map.get("C3", {})

    flatten_checks = payload.get("flatten_alignment_checks", []) or []
    obs_vs_bc = payload.get("observation_vs_bc_expectation", []) or []
    own_actor_summary = payload.get("own_actor_summary", []) or []

    root = payload.get("root_cause_classification", "INCONCLUSIVE_NEEDS_MORE_LOGITS")
    decision = payload.get("decision", "GO_FOR_NEXT_DIAGNOSTIC")

    lines: list[str] = []
    lines.append("# LEGACY032 UNITY V2 STAGE10R NOOP COLLAPSE ANALYSIS REPORT")
    lines.append("")
    lines.append(f"Generated at: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"Snapshot source: {snapshot_path.as_posix()}")
    lines.append("")

    lines.append("## 1) Scope")
    lines.append("- NoOp collapse analysis only.")
    lines.append("- No training.")
    lines.append("- No PPO.")
    lines.append("- No checkpoint changes.")
    lines.append("- No dataset changes.")
    lines.append("- No runtime semantic changes.")
    lines.append("")

    lines.append("## 2) Input context")
    lines.append("- Scene path: Assets/Scenes/Week6_StudentVisualInspection.unity")
    lines.append(f"- Checkpoint path: {payload.get('checkpoint', 'n/a')}")
    lines.append(f"- Controlled player: {payload.get('controlled_player', 'n/a')}")
    lines.append("- Focus cells: B2 (flat 25), C3 (flat 50)")
    lines.append("- Contract branch sizes: [6,4,4,4,4,7,49]")
    lines.append("")

    lines.append("## 3) Bridge diagnostic extension")
    lines.append("- Added debug payload with focus-cell action_type logits/probabilities/top3 and branch argmax values.")
    lines.append("- Added own-actor action_type summary with top1/top2 and NoOp margin.")
    lines.append("- Added focus-cell 27-channel observation slices.")
    lines.append("- Added flatten and observation-vs-BC expectation checks.")
    lines.append("- Inference behavior changed: no (argmax path unchanged).")
    lines.append("")

    lines.append("## 4) Focus cell diagnostics")
    lines.append("| Cell | GridPosition | Flat | Unit | Owner | Eligible | Predicted | Top-3 | NoOp p | Best non-NoOp p | NoOp margin | Command built | Reason |")
    lines.append("|---|---|---:|---|---|---|---|---|---:|---:|---:|---|---|")
    for label in ("B2", "C3"):
        row = focus_map.get(label, {})
        grid = row.get("grid_position", ["?", "?"])
        grid_text = f"({grid[0]},{grid[1]})" if isinstance(grid, list) and len(grid) == 2 else "(?,?)"
        lines.append(
            "| "
            + label
            + " | "
            + grid_text
            + f" | {row.get('flat_index', 'n/a')} | {row.get('unit_type', 'n/a')} | {row.get('owner', 'n/a')} | {row.get('eligible_actor', 'n/a')} | {row.get('predicted_action_type', 'n/a')} | "
            + action_top3_text(row.get("action_type_top3"))
            + f" | {fmt_prob(row.get('noop_probability'))} | {fmt_prob(row.get('best_non_noop_probability'))} | {fmt_prob(row.get('noop_margin'))} | {row.get('command_built', 'n/a')} | {row.get('command_not_built_reason', 'n/a')} |"
        )
    lines.append("")

    lines.append("## 5) Observation channel verification")
    for label in ("B2", "C3"):
        row = focus_map.get(label, {})
        lines.append(f"### {label}")
        lines.extend(summarize_channels(row.get("cell_observation_channels"), row.get("observation_channel_names")))
    lines.append("")

    lines.append("## 6) Flatten/cell alignment check")
    lines.append("- Formula: row * 24 + col")
    if flatten_checks:
        for item in flatten_checks:
            lines.append(f"- {item}")
    else:
        lines.append("- flatten checks unavailable")
    lines.append("")

    lines.append("## 7) Offline/bridge consistency check")
    lines.append(f"- status: {payload.get('offline_bridge_consistency', 'not_implemented')}")
    lines.append("")

    lines.append("## 8) Root cause classification")
    lines.append(f"- {root}")
    lines.append("")

    lines.append("## 9) Interpretation")
    lines.append("- This report evaluates observation->logits->action_type argmax diagnostics only.")
    lines.append("- It does not claim transfer success, semantic parity proof, or behavior quality proof.")
    if obs_vs_bc:
        lines.append("- Observation-vs-BC expectation summary:")
        for item in obs_vs_bc:
            lines.append(f"  - {item}")
    if own_actor_summary:
        lines.append("- Own actor summary:")
        for item in own_actor_summary:
            lines.append(f"  - {item}")
    lines.append("")

    lines.append("## 10) Decision")
    lines.append(f"- {decision}")
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(output_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
