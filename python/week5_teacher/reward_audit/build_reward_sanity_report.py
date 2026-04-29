#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from reward_audit_utils import DEFAULT_OUTPUT_DIR, utc_now, write_json, write_md


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build markdown/json reward sanity report from raw runs.")
    p.add_argument("--input-raw", type=Path, default=DEFAULT_OUTPUT_DIR / "REWARD_SANITY_RAW.json")
    p.add_argument("--input-report", type=Path, default=DEFAULT_OUTPUT_DIR / "REWARD_SANITY_REPORT.json")
    p.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_DIR / "REWARD_SANITY_REPORT.json")
    p.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_DIR / "REWARD_SANITY_REPORT.md")
    return p.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def decide(runs_by_mode: Dict[str, Any]) -> str:
    if not isinstance(runs_by_mode, dict) or not runs_by_mode:
        return "INCONCLUSIVE_NEEDS_MANUAL_CHECK"

    def _status(mode: str) -> str:
        payload = runs_by_mode.get(mode, {})
        if not isinstance(payload, dict):
            return "missing"
        return str(payload.get("status", "missing"))

    def _reward(mode: str) -> float:
        payload = runs_by_mode.get(mode, {})
        if not isinstance(payload, dict):
            return 0.0
        return float((payload.get("summary") or {}).get("reward_total", 0.0))

    def _nonzero(mode: str) -> int:
        payload = runs_by_mode.get(mode, {})
        if not isinstance(payload, dict):
            return 0
        return int((payload.get("summary") or {}).get("reward_nonzero_steps", 0))

    def _invalid(mode: str) -> int:
        payload = runs_by_mode.get(mode, {})
        if not isinstance(payload, dict):
            return 0
        return int((payload.get("summary") or {}).get("invalid_action_attempts", 0))

    mode_names = ["noop", "random_valid"]
    probe_names = ["scripted_probe", "economy_probe", "production_probe", "combat_probe", "mixed_probe"]
    for mode in [*mode_names, *probe_names]:
        if _status(mode) == "env_error":
            return "FAIL_REWARD_ENV_ERROR"

    missing_modes = [m for m in mode_names if m not in runs_by_mode]
    scripted_diff = _reward("scripted_probe") != _reward("noop")
    random_diff = _reward("random_valid") != _reward("noop")
    probe_nonzero = sum(_nonzero(name) for name in probe_names)
    probe_diff = any(_reward(name) != _reward("noop") for name in probe_names if name in runs_by_mode)
    nonzero = (probe_nonzero > 0) or (_nonzero("random_valid") > 0)

    if not missing_modes and (not nonzero) and (not scripted_diff) and (not random_diff) and (not probe_diff):
        return "FAIL_REWARD_ALL_ZERO"

    if missing_modes:
        if nonzero or scripted_diff or random_diff or probe_diff:
            return "PARTIAL_PASS_REWARD_SANITY"
        return "INCONCLUSIVE_NEEDS_MANUAL_CHECK"

    invalid_sum = sum(_invalid(mode) for mode in [*mode_names, *probe_names] if mode in runs_by_mode)
    if invalid_sum > 0:
        return "PARTIAL_PASS_REWARD_SANITY"

    if nonzero or scripted_diff or random_diff or probe_diff:
        return "PASS_REWARD_SANITY"

    return "INCONCLUSIVE_NEEDS_MANUAL_CHECK"


def main() -> int:
    args = parse_args()
    raw_payload = load_json(args.input_raw)
    old_report = load_json(args.input_report)

    runs_by_mode = raw_payload.get("runs_by_mode", {}) if isinstance(raw_payload, dict) else {}
    decision = decide(runs_by_mode)

    mode_summary: Dict[str, Any] = {}
    for mode, payload in sorted(runs_by_mode.items() if isinstance(runs_by_mode, dict) else []):
        if not isinstance(payload, dict):
            continue
        sm = payload.get("summary", {}) or {}
        mode_summary[mode] = {
            "status": payload.get("status", "missing"),
            "reward_total": float(sm.get("reward_total", 0.0)),
            "reward_nonzero_steps": int(sm.get("reward_nonzero_steps", 0)),
            "done_count": int(sm.get("done_count", 0)),
            "terminal_count": int(sm.get("terminal_count", 0)),
            "timeout_count": int(sm.get("timeout_count", 0)),
            "invalid_action_attempts": int(sm.get("invalid_action_attempts", 0)),
            "probe_diagnostics": dict(sm.get("probe_diagnostics", {})),
        }

    report = {
        "schema": "week5_reward_sanity_report.v1",
        "generated_at_utc": utc_now(),
        "decision": decision,
        "modes_present": sorted(list(mode_summary.keys())),
        "runs_by_mode_summary": mode_summary,
        "warnings": old_report.get("warnings", []) if isinstance(old_report, dict) else [],
        "errors": old_report.get("errors", []) if isinstance(old_report, dict) else [],
    }

    lines = [
        "# REWARD_SANITY_REPORT",
        "",
        f"- Decision: {decision}",
        f"- Modes present: {', '.join(report['modes_present']) if report['modes_present'] else 'none'}",
        "",
        "## Mode Summary",
    ]
    for mode, sm in sorted(mode_summary.items()):
        lines.append(
            f"- {mode}: status={sm['status']}, reward_total={sm['reward_total']:.6f}, "
            f"reward_nonzero_steps={sm['reward_nonzero_steps']}, done={sm['done_count']}, "
            f"terminal={sm['terminal_count']}, timeout={sm['timeout_count']}, "
            f"invalid_action_attempts={sm['invalid_action_attempts']}"
        )
        diag = sm.get("probe_diagnostics", {})
        if isinstance(diag, dict) and diag:
            lines.append(f"  probe_diagnostics={diag}")

    lines.extend(
        [
            "",
            "## Decision Vocabulary",
            "- PASS_REWARD_SANITY",
            "- PARTIAL_PASS_REWARD_SANITY",
            "- FAIL_REWARD_ALL_ZERO",
            "- FAIL_REWARD_ENV_ERROR",
            "- INCONCLUSIVE_NEEDS_MANUAL_CHECK",
        ]
    )

    write_json(args.output_report, report)
    write_md(args.output_md, lines)
    print(args.output_report)
    print(args.output_md)
    return 0 if decision.startswith("PASS") or decision.startswith("PARTIAL_PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
