#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_REPORT_JSON = Path("python/stage7b_teacher_replay/stage7b_teacher_replay_prep_report.json")
DEFAULT_REPORT_MD = Path("python/stage7b_teacher_replay/stage7b_teacher_replay_prep_report.md")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build markdown report for Stage7B teacher replay prep.")
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing report json: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_md(report: dict[str, Any]) -> str:
    metrics = report.get("metrics", {})
    contract = report.get("contract", {})

    lines: list[str] = []
    lines.append("# Stage7B Teacher Replay Prep Report")
    lines.append("")
    lines.append("## Status")
    lines.append("")
    lines.append(f"- stage: {report.get('stage')}")
    lines.append(f"- status: {report.get('status')}")
    lines.append(f"- generated_at_utc: {report.get('generated_at_utc')}")
    lines.append(f"- summary: {report.get('summary')}")
    lines.append("")
    lines.append("## Source Selection")
    lines.append("")
    lines.append(f"- selected_source_path: {report.get('selected_source_path')}")
    lines.append(f"- selected_source_format: {report.get('selected_source_format')}")
    lines.append(f"- source_inventory: {metrics.get('source_inventory')}")
    lines.append("")
    lines.append("## Contract")
    lines.append("")
    lines.append(f"- candidate_branch_size: {contract.get('candidate_branch_size')}")
    lines.append(f"- candidate_noop_index: {contract.get('candidate_noop_index')}")
    lines.append(f"- attack_target_size: {contract.get('attack_target_size')}")
    lines.append(f"- attack_target_center_index: {contract.get('attack_target_center_index')}")
    lines.append(f"- branch_sizes: {contract.get('branch_sizes')}")
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    ordered_keys = [
        "episodes_scanned",
        "episodes_replay_attempted",
        "steps_total",
        "steps_replay_attempted",
        "teacher_commands_total",
        "teacher_nonnoop_commands_total",
        "state_sync_success_count",
        "state_sync_failed_count",
        "pre_observation_match_count",
        "pre_observation_mismatch_count",
        "candidate_count_min",
        "candidate_count_mean",
        "candidate_count_max",
        "candidate_overflow_count",
        "candidate_match_count",
        "candidate_drop_count",
        "candidate_match_rate",
        "nonoop_candidate_match_count",
        "nonoop_candidate_match_rate",
        "runtime_apply_attempted_count",
        "runtime_apply_accepted_count",
        "runtime_apply_rejected_count",
        "runtime_apply_accept_rate",
        "post_state_match_count",
        "post_state_mismatch_count",
        "terminal_match_count",
        "terminal_mismatch_count",
        "demo_recording_ready",
    ]
    for key in ordered_keys:
        lines.append(f"- {key}: {metrics.get(key)}")

    lines.append("")
    lines.append("## Drop Reasons")
    lines.append("")
    drop_hist = metrics.get("drop_reason_histogram", {})
    if drop_hist:
        for k in sorted(drop_hist.keys()):
            lines.append(f"- {k}: {drop_hist[k]}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## Action Breakdown")
    lines.append("")
    lines.append("### match_by_action_type")
    mba = metrics.get("match_by_action_type", {})
    if mba:
        for k in sorted(mba.keys()):
            lines.append(f"- {k}: {mba[k]}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("### drop_by_action_type")
    dba = metrics.get("drop_by_action_type", {})
    if dba:
        for k in sorted(dba.keys()):
            lines.append(f"- {k}: {dba[k]}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## NO-GO Reasons")
    lines.append("")
    no_go = report.get("no_go_reasons", [])
    if no_go:
        for reason in no_go:
            lines.append(f"- {reason}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    for note in report.get("notes", []):
        lines.append(f"- {note}")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    report_json = resolve(args.report_json)
    report_md = resolve(args.report_md)

    report = load_json(report_json)
    markdown = build_md(report)

    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text(markdown, encoding="utf-8")

    print(f"[Stage7B][TeacherReplay] Markdown report written: {report_md.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
