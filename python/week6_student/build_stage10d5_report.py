#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


ALLOWED_CLASSIFICATIONS = {
    "OWNER_UNIT_MAPPING_RECOVERED_WITH_SOURCE_EVIDENCE",
    "OWNER_UNIT_MAPPING_RECOVERED_WITH_CONTROLLED_PROBE_EVIDENCE",
    "OWNER_UNIT_MAPPING_PARTIAL",
    "OWNER_UNIT_MAPPING_INCONCLUSIVE",
    "RAW_OBSERVATION_LACKS_REQUIRED_SEMANTIC_INFORMATION",
    "REROLLOUT_WITH_AUGMENTED_STATE_EXPORT_REQUIRED",
    "UNITY_SPEC_RECONCILIATION_REQUIRED",
}

ALLOWED_GATES = {
    "GO_FOR_STAGE10D4_MAPPING_SPEC_PATCH",
    "GO_FOR_FULL_SEMANTIC_ADAPTER_REBUILD",
    "NO_GO_RETRAINING_UNTIL_OWNER_UNIT_MAPPING_RESOLVED",
    "GO_FOR_REROLLOUT_WITH_AUGMENTED_STATE_EXPORT",
    "GO_FOR_NEXT_DIAGNOSTIC",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _decision(src: Dict[str, Any], probe: Dict[str, Any], cross: Dict[str, Any], cand: Dict[str, Any], dry: Dict[str, Any]) -> Dict[str, Any]:
    source_ok = src.get("status") == "pass" and bool(src.get("answers", {}).get("which_source_file_defines_27_channel_observation"))
    probe_ok = probe.get("status") == "pass" and bool(probe.get("inferred_owner_channel_candidates")) and bool(probe.get("inferred_unit_type_channel_candidates"))
    cross_ok = cross.get("status") == "pass"
    mapping_complete = bool(cand.get("mapping_complete_for_critical_groups", False))
    dry_pass = dry.get("status") == "pass"

    classifications: List[str] = []
    if source_ok and probe_ok and mapping_complete:
        classifications.append("OWNER_UNIT_MAPPING_RECOVERED_WITH_SOURCE_EVIDENCE")
    elif (not source_ok) and probe_ok and cross_ok and mapping_complete:
        classifications.append("OWNER_UNIT_MAPPING_RECOVERED_WITH_CONTROLLED_PROBE_EVIDENCE")
    elif mapping_complete and not dry_pass:
        classifications.append("OWNER_UNIT_MAPPING_PARTIAL")
    elif not mapping_complete:
        classifications.append("OWNER_UNIT_MAPPING_PARTIAL")
    else:
        classifications.append("OWNER_UNIT_MAPPING_INCONCLUSIVE")

    if not probe_ok and not source_ok:
        classifications.append("RAW_OBSERVATION_LACKS_REQUIRED_SEMANTIC_INFORMATION")

    if source_ok and probe_ok:
        gate = "GO_FOR_STAGE10D4_MAPPING_SPEC_PATCH"
    elif (not source_ok) and probe_ok and cross_ok:
        gate = "GO_FOR_STAGE10D4_MAPPING_SPEC_PATCH"
    elif not probe_ok and not source_ok:
        gate = "GO_FOR_REROLLOUT_WITH_AUGMENTED_STATE_EXPORT"
        classifications.append("REROLLOUT_WITH_AUGMENTED_STATE_EXPORT_REQUIRED")
    elif not mapping_complete:
        gate = "NO_GO_RETRAINING_UNTIL_OWNER_UNIT_MAPPING_RESOLVED"
    else:
        gate = "GO_FOR_NEXT_DIAGNOSTIC"

    # Stage-level strictness: do not authorize full rebuild unless dry-run passes.
    if gate == "GO_FOR_STAGE10D4_MAPPING_SPEC_PATCH" and not dry_pass:
        gate = "GO_FOR_NEXT_DIAGNOSTIC"

    for c in classifications:
        if c not in ALLOWED_CLASSIFICATIONS:
            raise RuntimeError(f"unexpected classification: {c}")
    if gate not in ALLOWED_GATES:
        raise RuntimeError(f"unexpected gate: {gate}")

    return {
        "classifications": classifications,
        "gate": gate,
        "source_ok": source_ok,
        "probe_ok": probe_ok,
        "cross_ok": cross_ok,
        "mapping_complete": mapping_complete,
        "dry_pass": dry_pass,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Stage10D.5 owner/unit mapping recovery report")
    p.add_argument(
        "--stage10d4-report",
        type=Path,
        default=Path("python/week6_student/reports/LEGACY032_UNITY_V2_STAGE10D4_OBSERVATION_SEMANTIC_REMEDIATION_REPORT.md"),
    )
    p.add_argument(
        "--source-audit",
        type=Path,
        default=Path("python/week6_student/reports/stage10d5_legacy032_observation_encoder_source_audit.json"),
    )
    p.add_argument(
        "--controlled-probe",
        type=Path,
        default=Path("python/week6_student/reports/stage10d5_controlled_raw_observation_probe.json"),
    )
    p.add_argument(
        "--rollout-crosscheck",
        type=Path,
        default=Path("python/week6_student/reports/stage10d5_rollout_entity_proxy_crosscheck.json"),
    )
    p.add_argument(
        "--candidate-builder",
        type=Path,
        default=Path("python/week6_student/reports/stage10d5_owner_unit_mapping_candidate.json"),
    )
    p.add_argument(
        "--candidate-mapping",
        type=Path,
        default=Path("python/week5_teacher_legacy032/observation_semantics/legacy032_to_unity_v2_observation_mapping.stage10d5_candidate.json"),
    )
    p.add_argument(
        "--dry-run",
        type=Path,
        default=Path("python/week6_student/reports/stage10d5_candidate_semantic_adapter_dry_run.json"),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/LEGACY032_UNITY_V2_STAGE10D5_OWNER_UNIT_MAPPING_RECOVERY_REPORT.md"),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = _repo_root()

    stage10d4_report = _resolve(root, args.stage10d4_report)
    source_audit = _load(_resolve(root, args.source_audit))
    controlled_probe = _load(_resolve(root, args.controlled_probe))
    rollout_cross = _load(_resolve(root, args.rollout_crosscheck))
    candidate_builder = _load(_resolve(root, args.candidate_builder))
    dry_run = _load(_resolve(root, args.dry_run))
    candidate_mapping = _resolve(root, args.candidate_mapping)

    decision = _decision(source_audit, controlled_probe, rollout_cross, candidate_builder, dry_run)

    owner_cand = candidate_builder.get("owner_candidate") or {}
    unit_cand = candidate_builder.get("unit_type_candidate") or {}

    lines: List[str] = []
    lines.append("# LEGACY032 Unity v2 Stage10D.5 Owner/UnitType Mapping Recovery Report")
    lines.append("")
    lines.append("## 1. Scope")
    lines.append("- Stage10D.5 recovers owner/unit_type mapping using authoritative or semi-authoritative evidence.")
    lines.append("- No retraining, PPO, checkpoint mutation, or ActionApplier/MatchManager changes were performed.")
    lines.append("")
    lines.append("## 2. Stage10D.4 Recap")
    lines.append(f"- Stage10D.4 report: {stage10d4_report.as_posix()}")
    lines.append("- Stage10D.4 ended with critical unavailable owner/unit_type channels and NO_GO gate for retraining.")
    lines.append("")
    lines.append("## 3. Source-code Encoder Audit")
    lines.append(f"- source audit status: {source_audit.get('status')}")
    lines.append(f"- encoder file: {source_audit.get('answers', {}).get('which_source_file_defines_27_channel_observation')}")
    lines.append(f"- channels 0..26 named explicitly: {source_audit.get('answers', {}).get('are_channels_0_to_26_named_anywhere', {}).get('value')}")
    lines.append(f"- owner/unit declared at group-level: {source_audit.get('answers', {}).get('are_owner_unit_type_channels_directly_declared')}")
    lines.append("")
    lines.append("## 4. Controlled Raw Observation Probe")
    lines.append(f"- controlled probe status: {controlled_probe.get('status')}")
    lines.append(f"- env id: {controlled_probe.get('env_id')}")
    lines.append(f"- map path: {controlled_probe.get('map_path')}")
    lines.append(f"- observation shape: {controlled_probe.get('observation_shape')}")
    lines.append(f"- owner candidate: {controlled_probe.get('inferred_owner_channel_candidates')}")
    lines.append(f"- unit_type candidate: {controlled_probe.get('inferred_unit_type_channel_candidates')}")
    lines.append("")
    lines.append("## 5. Rollout Entity Proxy Cross-check")
    lines.append(f"- rollout crosscheck status: {rollout_cross.get('status')}")
    lines.append(f"- top owner window: {(rollout_cross.get('owner_candidate_windows') or [None])[0]}")
    lines.append(f"- top unit_type window: {(rollout_cross.get('unit_type_candidate_windows') or [None])[0]}")
    lines.append("")
    lines.append("## 6. Candidate Owner Mapping")
    lines.append(f"- owner candidate summary: {owner_cand}")
    lines.append("")
    lines.append("## 7. Candidate UnitType Mapping")
    lines.append(f"- unit_type candidate summary: {unit_cand}")
    lines.append(f"- candidate mapping file: {candidate_mapping.as_posix()}")
    lines.append("")
    lines.append("## 8. Candidate Adapter Dry-run")
    lines.append(f"- dry-run status: {dry_run.get('status')}")
    lines.append(f"- worker_harvest_proxy: {dry_run.get('actor_label_proxy_compatibility', {}).get('worker_harvest_proxy')}")
    lines.append(f"- base_produce_proxy: {dry_run.get('actor_label_proxy_compatibility', {}).get('base_produce_proxy')}")
    lines.append(f"- impossible patterns: {dry_run.get('impossible_patterns')}")
    lines.append("")
    lines.append("## 9. Risk Assessment")
    lines.append("- Remaining risk is mostly perspective-specific behavior if rollout perspective changes from player0.")
    lines.append("- If future pipeline introduces self-play perspective switching, owner mapping must be re-validated.")
    lines.append("")
    lines.append("## 10. Gate Decision")
    lines.append(f"- classifications: {decision['classifications']}")
    lines.append(f"- gate: {decision['gate']}")
    lines.append(f"- mapping_complete_for_critical_groups: {decision['mapping_complete']}")
    lines.append(f"- dry_run_pass: {decision['dry_pass']}")
    lines.append("")
    lines.append("## 11. Explicit Non-Claims")
    lines.append("- No claim of semantic parity beyond demonstrated source/probe evidence.")
    lines.append("- No claim that BC-ready full dataset rebuild is authorized in this stage by default.")
    lines.append("- No claim that retraining is authorized before full semantic adapter validation after mapping patch.")

    out_path = _resolve(root, args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
