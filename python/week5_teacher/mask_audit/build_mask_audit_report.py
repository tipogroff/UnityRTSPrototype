#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from mask_audit_utils import DEFAULT_OUTPUT_DIR, read_json_or_none, safe_json_dump, utc_now


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build consolidated Markdown report from mask audit JSON files.")
    p.add_argument("--input-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_DIR / "MASK_AUDIT_REPORT.md")
    p.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_DIR / "MASK_AUDIT_REPORT_SUMMARY.json")
    return p.parse_args()


def load_reports(input_dir: Path) -> Dict[str, Optional[Dict[str, Any]]]:
    return {
        "surface": read_json_or_none(input_dir / "MASK_AUDIT_SURFACE.json"),
        "semantics": read_json_or_none(input_dir / "MASK_AUDIT_SEMANTICS.json"),
        "sampling": read_json_or_none(input_dir / "MASK_AUDIT_SAMPLING.json"),
        "logprob": read_json_or_none(input_dir / "MASK_AUDIT_LOGPROB.json"),
        "argmax": read_json_or_none(input_dir / "MASK_AUDIT_ARGMAX.json"),
        "coverage": read_json_or_none(input_dir / "MASK_COVERAGE_ROLLOUT.json"),
        "comparison": read_json_or_none(input_dir / "MASK_FINGERPRINT_COMPARISON.json"),
    }


def status_of(data: Optional[Dict[str, Any]]) -> str:
    if data is None:
        return "missing"
    return str(data.get("status", "unknown"))


def decide(reports: Dict[str, Optional[Dict[str, Any]]]) -> str:
    surface = reports["surface"]
    semantics = reports["semantics"]
    sampling = reports["sampling"]
    logprob = reports["logprob"]
    argmax = reports["argmax"]

    if surface is None or sampling is None or logprob is None:
        return "INCONCLUSIVE_NEEDS_MANUAL_CHECK"

    if status_of(surface) != "pass":
        return "FAIL_MASK_SHAPE"
    if semantics is not None and status_of(semantics) != "pass":
        return "FAIL_MASK_SEMANTICS"
    if status_of(sampling) != "pass":
        return "FAIL_MASKED_SAMPLING"
    if status_of(logprob) != "pass":
        return "FAIL_PPO_LOGPROB"

    if argmax is not None:
        metrics = argmax.get("metrics", {})
        invalid = int(sum((metrics.get("masked_argmax_invalid", {}) or {}).values()))
        collapse = int(metrics.get("masked_argmax_noop_when_nonnoop_available", 0))
        if invalid > 0:
            return "FAIL_MASKED_SAMPLING"
        if collapse > 0:
            return "PASS_MASK_BUT_POLICY_COLLAPSE"

    return "PASS_FULL_MASK"


def env_section(reports: Dict[str, Optional[Dict[str, Any]]]) -> Dict[str, Any]:
    for key in ["surface", "sampling", "logprob", "coverage"]:
        report = reports.get(key)
        if isinstance(report, dict):
            runtime = report.get("runtime_versions", {})
            environment = report.get("environment", {})
            env_summary = environment.get("env_summary", {})
            return {
                "gym_version": runtime.get("gym_api_version"),
                "gym_api_name": runtime.get("gym_api_name"),
                "microrts_version": runtime.get("microrts_version"),
                "microrts_module_name": runtime.get("microrts_module_name"),
                "env_id": environment.get("env_id"),
                "map_path": environment.get("map_path"),
                "backend_route": env_summary.get("env_backend"),
                "opponent_pool": environment.get("opponent_pool"),
                "python_executable": None,
                "torch_version": runtime.get("torch_version"),
                "sb3_version": runtime.get("stable_baselines3_version"),
            }
    return {}


def findings_lines(reports: Dict[str, Optional[Dict[str, Any]]]) -> List[str]:
    lines: List[str] = []
    for idx, key in enumerate(
        [
            "surface",
            "semantics",
            "sampling",
            "logprob",
            "argmax",
            "coverage",
            "comparison",
        ],
        start=1,
    ):
        item = reports.get(key)
        if item is None:
            lines.append(f"{idx}. {key}: missing")
        else:
            lines.append(f"{idx}. {key}: {item.get('status', 'unknown')}")
    return lines


def build_markdown(decision: str, reports: Dict[str, Optional[Dict[str, Any]]], env: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# MASK_AUDIT_REPORT")
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    lines.append(decision)
    lines.append("")
    lines.append("## Environment")
    lines.append("")
    lines.append(f"- gym version: {env.get('gym_version')}")
    lines.append(f"- gym api: {env.get('gym_api_name')}")
    lines.append(f"- gym_microrts / MicroRTS-Py version: {env.get('microrts_version')} ({env.get('microrts_module_name')})")
    lines.append(f"- env id: {env.get('env_id')}")
    lines.append(f"- map path: {env.get('map_path')}")
    lines.append(f"- backend route: {env.get('backend_route')}")
    lines.append(f"- opponent pool: {env.get('opponent_pool')}")
    lines.append(f"- python executable: {env.get('python_executable')}")
    lines.append(f"- torch version: {env.get('torch_version')}")
    lines.append(f"- sb3/sb3-contrib version: {env.get('sb3_version')}")
    lines.append("")
    lines.append("## Expected contract")
    lines.append("")
    lines.append("- branch layout: [6,4,4,4,4,7,49]")
    lines.append("- expected mask shape: [N,H,W,79]")
    lines.append("")
    lines.append("## Findings")
    lines.append("")
    lines.extend(findings_lines(reports))
    lines.append("")
    lines.append("## Fixes applied")
    lines.append("")
    lines.append("- none")
    lines.append("")
    lines.append("## Next decision")
    lines.append("")
    lines.append("- proceed to scripted BC")
    lines.append("- fix PPO mask integration")
    lines.append("- fix env wrapper")
    lines.append("- compare with legacy pipeline")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- This report does not claim Unity readiness, BC readiness, or student retraining status.")
    lines.append("- If any section is missing or skipped, decision may be INCONCLUSIVE_NEEDS_MANUAL_CHECK.")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    reports = load_reports(args.input_dir)
    decision = decide(reports)
    env = env_section(reports)

    md = build_markdown(decision, reports, env)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(md, encoding="utf-8")

    summary = {
        "generated_at_utc": utc_now(),
        "decision": decision,
        "report_statuses": {k: status_of(v) for k, v in reports.items()},
        "environment": env,
        "input_dir": str(args.input_dir),
        "output_md": str(args.output_md),
    }
    safe_json_dump(args.output_json, summary)

    print(args.output_md)
    print(args.output_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
