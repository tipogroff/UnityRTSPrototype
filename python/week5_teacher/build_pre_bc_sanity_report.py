#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build consolidated WEEK5R_PRE_BC_SANITY report.")
    p.add_argument("--mask-summary", type=Path, default=Path("python/week5_teacher/mask_audit/MASK_AUDIT_REPORT_SUMMARY.json"))
    p.add_argument("--reward-report", type=Path, default=Path("python/week5_teacher/reward_audit/REWARD_SANITY_REPORT.json"))
    p.add_argument("--dataset-validation", type=Path, default=Path("python/week5_teacher/scripted_bc_overfit/minimal_scripted_dataset_validation.json"))
    p.add_argument("--overfit-summary", type=Path, default=Path("python/week5_teacher/scripted_bc_overfit/OVERFIT_REPORT_SUMMARY.json"))
    p.add_argument("--output-md", type=Path, default=Path("python/week5_teacher/PRE_BC_SANITY_REPORT.md"))
    p.add_argument("--output-summary", type=Path, default=Path("python/week5_teacher/PRE_BC_SANITY_REPORT_SUMMARY.json"))
    return p.parse_args()


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def write_md(path: Path, lines: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def decide(mask: Dict[str, Any], reward: Dict[str, Any], dataset: Dict[str, Any], overfit: Dict[str, Any]) -> str:
    reward_dec = str(reward.get("decision", "INCONCLUSIVE_NEEDS_MANUAL_CHECK"))
    dataset_dec = str(dataset.get("decision", "INCONCLUSIVE_NEEDS_MANUAL_CHECK"))
    overfit_dec = str(overfit.get("decision", "INCONCLUSIVE_NEEDS_MANUAL_CHECK"))
    mask_dec = str(mask.get("decision", mask.get("summary_decision", "INCONCLUSIVE_NEEDS_MANUAL_CHECK")))

    if reward_dec in {"FAIL_REWARD_ALL_ZERO", "FAIL_REWARD_ENV_ERROR"}:
        return "BLOCKED_REWARD_SANITY"
    if dataset_dec.startswith("FAIL"):
        return "BLOCKED_DATASET"
    if overfit_dec.startswith("FAIL"):
        return "BLOCKED_OVERFIT"

    reward_ok = reward_dec in {"PASS_REWARD_SANITY", "PARTIAL_PASS_REWARD_SANITY"}
    dataset_ok = dataset_dec in {"PASS_DATASET_READY", "PARTIAL_PASS_DATASET_LIMITED_CLASSES"}
    overfit_ok = overfit_dec in {"PASS_SUPERVISED_OVERFIT", "PARTIAL_PASS_OVERFIT_LIMITED_CLASSES"}
    mask_ok = mask_dec in {"PASS_MASK_BUT_POLICY_COLLAPSE", "PASS", "PARTIAL_PASS"}

    if reward_ok and overfit_ok and mask_ok and dataset_dec == "PASS_DATASET_READY":
        return "PASS_READY_FOR_SCRIPTED_BC"

    if (
        reward_ok
        and overfit_ok
        and dataset_dec == "PARTIAL_PASS_DATASET_LIMITED_CLASSES"
        and reward_dec != "FAIL_REWARD_ALL_ZERO"
    ):
        return "PARTIAL_READY_WITH_CAVEATS"

    return "INCONCLUSIVE_NEEDS_MANUAL_CHECK"


def main() -> int:
    args = parse_args()

    mask = load_json(args.mask_summary)
    reward = load_json(args.reward_report)
    dataset = load_json(args.dataset_validation)
    overfit = load_json(args.overfit_summary)

    decision = decide(mask, reward, dataset, overfit)

    can_start_scripted_bc = decision in {"PASS_READY_FOR_SCRIPTED_BC", "PARTIAL_READY_WITH_CAVEATS"}
    dataset_dec = str(dataset.get("decision", "INCONCLUSIVE_NEEDS_MANUAL_CHECK"))
    can_run_full_scripted_bc_training_now = (
        can_start_scripted_bc and dataset_dec in {"PASS_DATASET_READY", "PARTIAL_PASS_DATASET_LIMITED_CLASSES"}
    )
    can_run_ppo_finetune = False

    caveats: List[str] = []
    if str(reward.get("decision", "")).startswith("PARTIAL"):
        caveats.append("Reward sanity is partial: verify scripted vs random policy reward behavior before large scripted export.")
    if str(dataset.get("decision", "")).startswith("PARTIAL"):
        caveats.append("Dataset has limited classes; overfit is still informative but branch coverage is incomplete.")
    if str(overfit.get("decision", "")).startswith("PARTIAL"):
        caveats.append("Overfit gate is partial due to limited class support in minimal dataset.")

    caveats.append(
        "PASS/PARTIAL here means only readiness for teacher-side scripted BC warm-start, not teacher-ready and not Unity-ready."
    )
    caveats.append(
        "PPO fine-tune is blocked until scripted BC checkpoint passes deterministic behavior gate."
    )

    summary = {
        "schema": "week5_pre_bc_sanity_summary.v1",
        "generated_at_utc": utc_now(),
        "decision": decision,
        "inputs": {
            "mask_summary": str(args.mask_summary),
            "reward_report": str(args.reward_report),
            "dataset_validation": str(args.dataset_validation),
            "overfit_summary": str(args.overfit_summary),
        },
        "sub_decisions": {
            "mask_audit": mask.get("decision", mask.get("summary_decision")),
            "reward_sanity": reward.get("decision"),
            "dataset_validation": dataset.get("decision"),
            "overfit": overfit.get("decision"),
        },
        "recommendations": {
            "can_proceed_to_full_scripted_bc_dataset_exporter": bool(can_start_scripted_bc),
            "can_run_full_scripted_bc_training_now": bool(can_run_full_scripted_bc_training_now),
            "can_run_ppo_fine_tune_now": bool(can_run_ppo_finetune),
        },
        "caveats": caveats,
        "decision_vocab": [
            "PASS_READY_FOR_SCRIPTED_BC",
            "PARTIAL_READY_WITH_CAVEATS",
            "BLOCKED_REWARD_SANITY",
            "BLOCKED_OVERFIT",
            "BLOCKED_DATASET",
            "INCONCLUSIVE_NEEDS_MANUAL_CHECK",
        ],
    }

    lines = [
        "# PRE_BC_SANITY_REPORT",
        "",
        f"- Decision: {decision}",
        "",
        "## Sub-decisions",
        f"- mask_audit: {summary['sub_decisions']['mask_audit']}",
        f"- reward_sanity: {summary['sub_decisions']['reward_sanity']}",
        f"- dataset_validation: {summary['sub_decisions']['dataset_validation']}",
        f"- overfit: {summary['sub_decisions']['overfit']}",
        "",
        "## Readiness",
        f"- can_proceed_to_full_scripted_bc_dataset_exporter: {summary['recommendations']['can_proceed_to_full_scripted_bc_dataset_exporter']}",
        f"- can_run_full_scripted_bc_training_now: {summary['recommendations']['can_run_full_scripted_bc_training_now']}",
        f"- can_run_ppo_fine_tune_now: {summary['recommendations']['can_run_ppo_fine_tune_now']}",
        "",
        "## Caveats",
    ]
    for c in caveats:
        lines.append(f"- {c}")

    write_json(args.output_summary, summary)
    write_md(args.output_md, lines)
    print(args.output_md)
    print(args.output_summary)
    return 0 if decision.startswith("PASS") or decision.startswith("PARTIAL") else 2


if __name__ == "__main__":
    raise SystemExit(main())
