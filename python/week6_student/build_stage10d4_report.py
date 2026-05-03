#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List


ALLOWED_CLASSIFICATIONS = {
    "OBSERVATION_SEMANTIC_MAPPING_SPEC_READY",
    "OBSERVATION_SEMANTIC_MAPPING_SPEC_INCOMPLETE",
    "SEMANTIC_ADAPTER_REBUILD_READY",
    "SEMANTIC_ADAPTER_REBUILD_FAILED",
    "UNITY_SPEC_RECONCILIATION_REQUIRED",
    "INCONCLUSIVE_NEEDS_MANUAL_CHANNEL_TRACE",
}

ALLOWED_GATES = {
    "GO_FOR_SEMANTIC_ADAPTED_BC_READY_REBUILD",
    "GO_FOR_SPEC_RECONCILIATION_ONLY",
    "NO_GO_RETRAINING_UNTIL_SEMANTIC_ADAPTER_VALIDATED",
    "GO_FOR_STAGE10D1R_RERUN_ON_SEMANTIC_ADAPTED_DATA",
    "GO_FOR_NEXT_DIAGNOSTIC",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _git_commit(root: Path) -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(root), text=True)
        return out.strip()
    except Exception:
        return "unavailable"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Stage10D.4 observation semantic remediation report")
    p.add_argument(
        "--stage10d3-report",
        type=Path,
        default=Path("python/week6_student/reports/LEGACY032_UNITY_V2_STAGE10D3_GYM_TO_UNITY_OBSERVATION_MAPPING_TRACE_REPORT.md"),
    )
    p.add_argument(
        "--stage10d3-raw-probe",
        type=Path,
        default=Path("python/week6_student/reports/stage10d3_raw_gym_observation_channel_probe.json"),
    )
    p.add_argument(
        "--inferred-semantics",
        type=Path,
        default=Path("python/week6_student/reports/stage10d4_inferred_legacy032_raw_channel_semantics.json"),
    )
    p.add_argument(
        "--mapping-spec",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/observation_semantics/"
            "legacy032_to_unity_v2_observation_mapping.json"
        ),
    )
    p.add_argument(
        "--mapping-validation",
        type=Path,
        default=Path("python/week6_student/reports/stage10d4_mapping_spec_validation.json"),
    )
    p.add_argument(
        "--conversion-report",
        type=Path,
        required=True,
    )
    p.add_argument(
        "--dataset-validation",
        type=Path,
        default=Path("python/week6_student/reports/stage10d4_semantic_adapted_dataset_validation.json"),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path(
            "python/week6_student/reports/"
            "LEGACY032_UNITY_V2_STAGE10D4_OBSERVATION_SEMANTIC_REMEDIATION_REPORT.md"
        ),
    )
    return p.parse_args()


def _gate_and_classification(
    mapping_validation: Dict[str, Any],
    conversion: Dict[str, Any],
    dataset_validation: Dict[str, Any],
) -> Dict[str, Any]:
    classes: List[str] = []

    mapping_complete = bool(mapping_validation.get("mapping_complete_for_critical_groups", False))
    if mapping_complete and mapping_validation.get("status") == "pass":
        classes.append("OBSERVATION_SEMANTIC_MAPPING_SPEC_READY")
    else:
        classes.append("OBSERVATION_SEMANTIC_MAPPING_SPEC_INCOMPLETE")

    if conversion.get("status") == "success":
        classes.append("SEMANTIC_ADAPTER_REBUILD_READY")
    else:
        classes.append("SEMANTIC_ADAPTER_REBUILD_FAILED")

    if mapping_validation.get("owner_mode_target") == "perspective_friendly_enemy":
        classes.append("UNITY_SPEC_RECONCILIATION_REQUIRED")

    for c in classes:
        if c not in ALLOWED_CLASSIFICATIONS:
            raise RuntimeError(f"Unexpected classification: {c}")

    critical_unknown = bool(mapping_validation.get("critical_unavailable_channels"))
    dataset_pass = dataset_validation.get("status") == "pass"
    proxy = dataset_validation.get("actor_label_proxy_compatibility", {})
    proxy_ok = bool(
        proxy.get("worker_harvest_proxy", {}).get("compatible", False)
        and proxy.get("base_produce_proxy", {}).get("compatible", False)
    )

    if critical_unknown:
        gate = "NO_GO_RETRAINING_UNTIL_SEMANTIC_ADAPTER_VALIDATED"
    elif dataset_pass and proxy_ok:
        gate = "GO_FOR_SEMANTIC_ADAPTED_BC_READY_REBUILD"
    elif dataset_pass and not proxy_ok:
        gate = "GO_FOR_STAGE10D1R_RERUN_ON_SEMANTIC_ADAPTED_DATA"
    elif "UNITY_SPEC_RECONCILIATION_REQUIRED" in classes and conversion.get("status") == "success":
        gate = "GO_FOR_SPEC_RECONCILIATION_ONLY"
    else:
        gate = "GO_FOR_NEXT_DIAGNOSTIC"

    if gate not in ALLOWED_GATES:
        raise RuntimeError(f"Unexpected gate: {gate}")

    return {
        "classifications": classes,
        "gate": gate,
        "mapping_complete": mapping_complete,
        "critical_unknown": critical_unknown,
        "dataset_pass": dataset_pass,
        "proxy_ok": proxy_ok,
    }


def main() -> int:
    args = parse_args()
    root = _repo_root()

    stage10d3_report = _resolve(root, args.stage10d3_report)
    stage10d3_raw_probe = _resolve(root, args.stage10d3_raw_probe)
    inferred = _resolve(root, args.inferred_semantics)
    mapping_spec = _resolve(root, args.mapping_spec)
    mapping_validation = _resolve(root, args.mapping_validation)
    conversion_report = _resolve(root, args.conversion_report)
    dataset_validation = _resolve(root, args.dataset_validation)
    output = _resolve(root, args.output)

    raw_probe_json = _load(stage10d3_raw_probe)
    inferred_json = _load(inferred)
    mapping_spec_json = _load(mapping_spec)
    mapping_validation_json = _load(mapping_validation)
    conversion_json = _load(conversion_report)
    dataset_json = _load(dataset_validation)

    decision = _gate_and_classification(mapping_validation_json, conversion_json, dataset_json)

    d3_decl = raw_probe_json.get("empirical_channel_map_inference", {}).get("declared_group_checks", {})

    lines: List[str] = []
    lines.append("# LEGACY032 Unity v2 Stage10D.4 Observation Semantic Remediation Report")
    lines.append("")
    lines.append("## 1. Scope")
    lines.append("- Stage10D.4 defines a versioned canonical observation semantic contract and explicit adapter remediation workflow.")
    lines.append("- No retraining, PPO, checkpoint mutation, or in-place dataset mutation were performed.")
    lines.append("- Adapter output is written to a new directory only.")
    lines.append("")
    lines.append("## 2. Stage10D.3 Recap")
    lines.append(f"- Stage10D.3 report: {stage10d3_report.as_posix()}")
    lines.append(f"- raw shape: {raw_probe_json.get('observations', {}).get('shape')}")
    lines.append(f"- owner [2..4] share(sum==1): {d3_decl.get('owner_2_4', {}).get('share_sum_eq_1')}")
    lines.append(f"- unit_type [5..11] share(sum==1): {d3_decl.get('unit_type_5_11', {}).get('share_sum_eq_1')}")
    lines.append(f"- current_action [12..17] share(sum==1): {d3_decl.get('current_action_12_17', {}).get('share_sum_eq_1')}")
    lines.append(f"- direction [18..21] share(sum==1): {d3_decl.get('direction_18_21', {}).get('share_sum_eq_1')}")
    lines.append("")
    lines.append("## 3. Canonical Target Observation Semantics")
    lines.append("- Canonical target selected: Unity v2 runtime semantics.")
    lines.append(f"- owner_mode_target: {mapping_spec_json.get('owner_mode_target')}")
    lines.append("- Rationale: student BC inference executes in Unity, so Unity runtime semantics are canonical deployment semantics.")
    lines.append("")
    lines.append("## 4. Legacy032 Raw Observation Semantics")
    lines.append(f"- Inference output: {inferred.as_posix()}")
    lines.append("- Legacy032 raw semantics are empirical and partially unresolved for owner/unit_type channel identities.")
    lines.append("- Stage10D.4 preserves explicit uncertainty instead of implicit remap.")
    lines.append("")
    lines.append("## 5. Mapping Spec")
    lines.append(f"- mapping file: {mapping_spec.as_posix()}")
    lines.append(f"- mapping_spec_version: {mapping_spec_json.get('mapping_spec_version')}")
    lines.append(f"- observation_semantics_version: {mapping_spec_json.get('observation_semantics_version')}")
    lines.append("- Current_action/direction/produce/attack_target use explicit derived rules.")
    lines.append("- Unknown owner/unit_type channels are explicit unavailable mappings with zero-fill fallback and audit flags.")
    lines.append("")
    lines.append("## 6. Mapping Spec Validation")
    lines.append(f"- validation file: {mapping_validation.as_posix()}")
    lines.append(f"- status: {mapping_validation_json.get('status')}")
    lines.append(f"- mapping_complete_for_critical_groups: {mapping_validation_json.get('mapping_complete_for_critical_groups')}")
    lines.append(f"- critical_unavailable_channels: {mapping_validation_json.get('critical_unavailable_channels')}")
    lines.append("")
    lines.append("## 7. Semantic Adapter Output")
    lines.append(f"- conversion report: {conversion_report.as_posix()}")
    lines.append(f"- status: {conversion_json.get('status')}")
    lines.append(f"- output_dir: {conversion_json.get('output_dir')}")
    lines.append(f"- unavailable_channels: {conversion_json.get('unavailable_channels')}")
    lines.append(f"- critical_unavailable_channels: {conversion_json.get('critical_unavailable_channels')}")
    lines.append("")
    lines.append("## 8. Semantic Adapted Dataset Validation")
    lines.append(f"- validation report: {dataset_validation.as_posix()}")
    lines.append(f"- status: {dataset_json.get('status')}")
    lines.append(
        "- worker proxy compatible: "
        + str(dataset_json.get("actor_label_proxy_compatibility", {}).get("worker_harvest_proxy", {}).get("compatible"))
    )
    lines.append(
        "- base proxy compatible: "
        + str(dataset_json.get("actor_label_proxy_compatibility", {}).get("base_produce_proxy", {}).get("compatible"))
    )
    lines.append("")
    lines.append("## 9. Remaining Gaps")
    lines.append("- Owner channel mapping from legacy032 raw to Unity perspective owner remains unresolved.")
    lines.append("- Unit_type channel mapping from legacy032 raw to Unity unit_type one-hot remains unresolved.")
    lines.append("- Spec reconciliation is still required between ObservationContract absolute-owner docs and UnityMvpTransfer runtime owner semantics.")
    lines.append("")
    lines.append("## 10. Gate Decision")
    lines.append(f"- classifications: {decision['classifications']}")
    lines.append(f"- gate: {decision['gate']}")
    lines.append("")
    lines.append("## 11. Explicit Non-Claims")
    lines.append("- No claim of exact semantic parity between Gym-microRTS raw observations and Unity runtime observations.")
    lines.append("- No claim that retraining is authorized in Stage10D.4.")
    lines.append("- No runtime mutation in ActionApplier or MatchManager.")
    lines.append("")
    lines.append("## Metadata")
    lines.append(f"- commit: {_git_commit(root)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
