#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class BatchSnapshot:
    label: str
    batch_dir: Path
    strict: Dict[str, Any]
    quality: Dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare two Day 5 validation outputs (old meaningful baseline vs new stronger candidate) "
            "and generate comparative markdown/json artifacts."
        )
    )
    parser.add_argument("--old-batch-dir", type=Path, required=True)
    parser.add_argument("--new-batch-dir", type=Path, required=True)
    parser.add_argument("--old-label", default="old_meaningful")
    parser.add_argument("--new-label", default="new_stronger")
    parser.add_argument("--output-md", type=Path, default=None)
    parser.add_argument("--output-json", type=Path, default=None)
    return parser.parse_args()


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def pct(value: float) -> str:
    return f"{value * 100.0:.2f}%"


def num(value: float) -> str:
    if isinstance(value, int):
        return str(value)
    return f"{value:.6f}" if abs(value) < 10 else f"{value:.4f}"


def extract_snapshot(batch_dir: Path, label: str) -> BatchSnapshot:
    strict_path = batch_dir / "strict_validation_day5.json"
    quality_path = batch_dir / "quality_report_day5.json"
    if not strict_path.exists() or not quality_path.exists():
        missing: List[str] = []
        if not strict_path.exists():
            missing.append(str(strict_path))
        if not quality_path.exists():
            missing.append(str(quality_path))
        raise FileNotFoundError("Missing required Day5 artifacts: " + ", ".join(missing))

    return BatchSnapshot(
        label=label,
        batch_dir=batch_dir.resolve(),
        strict=read_json(strict_path),
        quality=read_json(quality_path),
    )


def get_metric(snapshot: BatchSnapshot, key: str) -> float:
    q = snapshot.quality.get("quality", {})
    s = snapshot.quality.get("sanity", {})

    if key == "validation_status_pass":
        status = str(snapshot.strict.get("validation", {}).get("status", "")).strip().lower()
        return 1.0 if status == "pass" else 0.0
    if key == "hard_failures_count":
        return float(len(snapshot.strict.get("validation", {}).get("hard_failures", [])))
    if key == "warnings_count":
        return float(len(snapshot.strict.get("validation", {}).get("warnings", [])))
    if key == "warnings_per_episode":
        warnings_count = float(len(snapshot.strict.get("validation", {}).get("warnings", [])))
        episodes = float(snapshot.quality.get("sanity", {}).get("episodes_scanned", 0.0))
        return warnings_count / episodes if episodes > 0.0 else warnings_count

    if key == "usable_samples":
        return float(q.get("usable_samples", 0.0))
    if key == "dropped_samples":
        return float(q.get("dropped_samples", 0.0))
    if key == "conversion_loss_share":
        return float(q.get("conversion_loss_share", 0.0))
    if key == "remap_to_noop_share":
        return float(q.get("remap_to_noop_share", 0.0))
    if key == "semantic_weakening_share":
        return float(q.get("semantic_weakening_share", 0.0))
    if key == "observation_signal_loss_share":
        return float(q.get("observation_signal_loss_share", 0.0))
    if key == "production_actions_survived_share":
        return float(q.get("production_actions_survived_share", 0.0))
    if key == "class_imbalance_ratio":
        return float(q.get("class_imbalance", {}).get("imbalance_ratio_max_to_min_nonzero", 0.0))
    if key == "inactive_branch_anomaly_share":
        return float(q.get("inactive_branch_anomalies", {}).get("inactive_branch_anomaly_share", 0.0))
    if key == "attack_action_share":
        return float(s.get("attack_local_target_cases", {}).get("attack_action_share", 0.0))
    if key == "produce_action_share":
        return float(s.get("produce_cases", {}).get("produce_action_share", 0.0))

    raise KeyError(f"Unknown metric key: {key}")


def get_severity(snapshot: BatchSnapshot) -> str:
    return str(
        snapshot.quality.get("quality", {})
        .get("inactive_branch_anomalies", {})
        .get("inactive_branch_warning_severity", "unknown")
    )


def get_action_distribution_shares(snapshot: BatchSnapshot) -> Dict[str, float]:
    dist = snapshot.quality.get("sanity", {}).get("action_type_distribution", {})
    total = float(sum(float(v) for v in dist.values()))
    if total <= 0.0:
        return {}
    return {k: float(v) / total for k, v in sorted(dist.items(), key=lambda kv: int(kv[0]))}


def warning_check_types(snapshot: BatchSnapshot) -> List[str]:
    warnings = snapshot.strict.get("validation", {}).get("warnings", [])
    checks = sorted({str(item.get("check", "unknown")) for item in warnings})
    return checks


def warning_comparability(old: BatchSnapshot, new: BatchSnapshot) -> Dict[str, Any]:
    old_episodes = int(old.quality.get("sanity", {}).get("episodes_scanned", 0) or 0)
    new_episodes = int(new.quality.get("sanity", {}).get("episodes_scanned", 0) or 0)

    old_checks = warning_check_types(old)
    new_checks = warning_check_types(new)
    same_categories = old_checks == new_checks
    episode_count_differs = old_episodes != new_episodes

    comparable = not (episode_count_differs and same_categories)
    reason = "comparable"
    if not comparable:
        reason = "episode_count_differs_and_warning_categories_identical"

    old_warnings = float(len(old.strict.get("validation", {}).get("warnings", [])))
    new_warnings = float(len(new.strict.get("validation", {}).get("warnings", [])))

    return {
        "comparable": comparable,
        "reason": reason,
        "old_episodes": old_episodes,
        "new_episodes": new_episodes,
        "old_warning_check_types": old_checks,
        "new_warning_check_types": new_checks,
        "old_warnings_per_episode": (old_warnings / old_episodes) if old_episodes > 0 else old_warnings,
        "new_warnings_per_episode": (new_warnings / new_episodes) if new_episodes > 0 else new_warnings,
    }


def compute_decision(old: BatchSnapshot, new: BatchSnapshot) -> Dict[str, Any]:
    # Positive score means new batch is better.
    score = 0
    improved: List[str] = []
    worsened: List[str] = []

    warning_cmp = warning_comparability(old, new)

    better_when_lower = {
        "hard_failures_count": 3,
        "conversion_loss_share": 2,
        "remap_to_noop_share": 2,
        "semantic_weakening_share": 1,
        "observation_signal_loss_share": 1,
        "class_imbalance_ratio": 1,
        "inactive_branch_anomaly_share": 2,
    }
    if warning_cmp.get("comparable", True):
        better_when_lower["warnings_count"] = 1
    better_when_higher = {
        "validation_status_pass": 2,
        "usable_samples": 1,
        "production_actions_survived_share": 2,
    }

    for metric, weight in better_when_lower.items():
        old_v = get_metric(old, metric)
        new_v = get_metric(new, metric)
        if new_v < old_v:
            score += weight
            improved.append(metric)
        elif new_v > old_v:
            score -= weight
            worsened.append(metric)

    for metric, weight in better_when_higher.items():
        old_v = get_metric(old, metric)
        new_v = get_metric(new, metric)
        if new_v > old_v:
            score += weight
            improved.append(metric)
        elif new_v < old_v:
            score -= weight
            worsened.append(metric)

    if score >= 3:
        result = "better"
    elif score <= -3:
        result = "not_better"
    else:
        result = "mixed"

    preferred = new.label if result == "better" else (old.label if result == "not_better" else "mixed_decision")

    return {
        "comparison_result": result,
        "preferred_bc_candidate_batch": preferred,
        "score": score,
        "improved_metrics": improved,
        "worsened_metrics": worsened,
        "warning_count_comparability": warning_cmp,
    }


def metric_rows(old: BatchSnapshot, new: BatchSnapshot) -> List[Tuple[str, str, str, str, str]]:
    rows: List[Tuple[str, str, str, str, str]] = []

    spec = [
        ("validation_status_pass", "Validation pass", "higher"),
        ("hard_failures_count", "Hard failures", "lower"),
        ("warnings_count", "Warnings", "lower"),
        ("warnings_per_episode", "Warnings per episode", "lower"),
        ("usable_samples", "Usable samples", "higher"),
        ("dropped_samples", "Dropped samples", "lower"),
        ("conversion_loss_share", "Conversion loss share", "lower_pct"),
        ("remap_to_noop_share", "remap_to_noop_share", "lower_pct"),
        ("semantic_weakening_share", "semantic_weakening_share", "lower_pct"),
        ("observation_signal_loss_share", "observation_signal_loss_share", "lower_pct"),
        ("production_actions_survived_share", "production_actions_survived_share", "higher_pct"),
        ("class_imbalance_ratio", "class imbalance ratio", "lower"),
        ("inactive_branch_anomaly_share", "inactive_branch_anomaly_share", "lower_pct"),
        ("attack_action_share", "attack/local-target share", "higher_pct"),
        ("produce_action_share", "produce action share", "higher_pct"),
    ]

    for key, label, kind in spec:
        old_v = get_metric(old, key)
        new_v = get_metric(new, key)
        delta = new_v - old_v

        if kind.endswith("pct"):
            old_s = pct(old_v)
            new_s = pct(new_v)
            delta_s = pct(delta)
        else:
            old_s = num(old_v)
            new_s = num(new_v)
            delta_s = num(delta)

        if kind.startswith("higher"):
            trend = "improved" if delta > 0 else ("worsened" if delta < 0 else "same")
        else:
            trend = "improved" if delta < 0 else ("worsened" if delta > 0 else "same")

        rows.append((label, old_s, new_s, delta_s, trend))

    return rows


def build_markdown(old: BatchSnapshot, new: BatchSnapshot, decision: Dict[str, Any]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = metric_rows(old, new)

    old_severity = get_severity(old)
    new_severity = get_severity(new)

    old_dist = get_action_distribution_shares(old)
    new_dist = get_action_distribution_shares(new)

    lines: List[str] = []
    lines.append("# Day 5 Comparative Report: meaningful vs stronger teacher batch")
    lines.append("")
    lines.append(f"Generated at (UTC): {now}")
    lines.append("")
    lines.append("## Batches")
    lines.append(f"- old_meaningful_batch: {old.batch_dir}")
    lines.append(f"- new_stronger_batch: {new.batch_dir}")
    lines.append("")

    lines.append("## Contract / Validation outcome")
    lines.append("")
    lines.append("| Metric | old meaningful | new stronger | delta (new-old) | trend |")
    lines.append("|---|---:|---:|---:|---|")
    for label, old_s, new_s, delta_s, trend in rows[:4]:
        lines.append(f"| {label} | {old_s} | {new_s} | {delta_s} | {trend} |")
    warning_cmp = decision.get("warning_count_comparability", {})
    if not warning_cmp.get("comparable", True):
        lines.append(
            "- warning_count_not_comparable_when_episode_count_differs: true "
            f"(reason={warning_cmp.get('reason', 'unknown')})"
        )
        lines.append(
            f"- warning_check_types (old/new): {warning_cmp.get('old_warning_check_types', [])} / "
            f"{warning_cmp.get('new_warning_check_types', [])}"
        )
    lines.append("")

    lines.append("## Quality metrics")
    lines.append("")
    lines.append("| Metric | old meaningful | new stronger | delta (new-old) | trend |")
    lines.append("|---|---:|---:|---:|---|")
    for label, old_s, new_s, delta_s, trend in rows[4:13]:
        lines.append(f"| {label} | {old_s} | {new_s} | {delta_s} | {trend} |")
    lines.append(f"- inactive_branch_warning_severity: old={old_severity}, new={new_severity}")
    lines.append("")

    lines.append("## Sanity metrics")
    lines.append("")
    lines.append("| Metric | old meaningful | new stronger | delta (new-old) | trend |")
    lines.append("|---|---:|---:|---:|---|")
    for label, old_s, new_s, delta_s, trend in rows[13:]:
        lines.append(f"| {label} | {old_s} | {new_s} | {delta_s} | {trend} |")
    lines.append("")

    lines.append("Action type distribution shares (old -> new):")
    all_keys = sorted(set(old_dist.keys()) | set(new_dist.keys()), key=int)
    for key in all_keys:
        lines.append(
            f"- action_type={key}: {pct(old_dist.get(key, 0.0))} -> {pct(new_dist.get(key, 0.0))}"
        )
    lines.append("")

    lines.append("Weak spots detected:")
    old_weak = old.quality.get("quality", {}).get("main_weak_spots_detected", [])
    new_weak = new.quality.get("quality", {}).get("main_weak_spots_detected", [])
    lines.append("- old meaningful:")
    for item in old_weak:
        lines.append(f"  - {item}")
    lines.append("- new stronger:")
    for item in new_weak:
        lines.append(f"  - {item}")
    lines.append("")

    lines.append("## Recommendation")
    lines.append("")
    lines.append(f"- preferred_bc_candidate_batch: {decision['preferred_bc_candidate_batch']}")
    lines.append(f"- comparison_result: {decision['comparison_result']}")
    lines.append("- reasoning:")

    improved = decision.get("improved_metrics", [])
    worsened = decision.get("worsened_metrics", [])
    if improved:
        lines.append(f"  - Improved metrics: {', '.join(improved)}")
    else:
        lines.append("  - Improved metrics: none")

    if worsened:
        lines.append(f"  - Worsened metrics: {', '.join(worsened)}")
    else:
        lines.append("  - Worsened metrics: none")

    lines.append(
        "  - Decision is based only on adapted/validated data-level outcomes, not on teacher training duration or checkpoint origin."
    )
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()

    old_snapshot = extract_snapshot(args.old_batch_dir.resolve(), args.old_label)
    new_snapshot = extract_snapshot(args.new_batch_dir.resolve(), args.new_label)

    decision = compute_decision(old_snapshot, new_snapshot)

    md_text = build_markdown(old_snapshot, new_snapshot, decision)

    output_md = args.output_md.resolve() if args.output_md else (new_snapshot.batch_dir.parent / "COMPARE_TEACHER_BATCHES_DAY5.md")
    output_json = (
        args.output_json.resolve()
        if args.output_json
        else (new_snapshot.batch_dir.parent / "COMPARE_TEACHER_BATCHES_DAY5.json")
    )

    output_md.write_text(md_text, encoding="utf-8")

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "old": {
            "label": old_snapshot.label,
            "batch_dir": str(old_snapshot.batch_dir),
        },
        "new": {
            "label": new_snapshot.label,
            "batch_dir": str(new_snapshot.batch_dir),
        },
        "decision": decision,
    }
    output_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"Comparison markdown: {output_md}")
    print(f"Comparison json: {output_json}")
    print(f"comparison_result: {decision['comparison_result']}")
    print(f"preferred_bc_candidate_batch: {decision['preferred_bc_candidate_batch']}")


if __name__ == "__main__":
    main()
