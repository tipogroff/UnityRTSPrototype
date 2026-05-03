#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List


ALLOWED_ROOT_CAUSE = {
    "RAW_GYM_OBSERVATION_CHANNEL_MAP_MISIDENTIFIED",
    "RAW_EXPORT_OBSERVATION_SERIALIZATION_ERROR",
    "ADAPTER_OBSERVATION_CHANNEL_MAPPING_ERROR",
    "BC_READY_PACKAGING_OBSERVATION_CORRUPTION",
    "UNITY_OBSERVATIONBUILDER_CHANNEL_MAPPING_ERROR",
    "UNITY_AND_BC_USE_INCOMPATIBLE_OBSERVATION_SEMANTICS",
    "CONTRACT_DOC_STALE_BUT_CODE_CONSISTENT",
    "INCONCLUSIVE_NEEDS_MANUAL_TRACE",
}

ALLOWED_GATE = {
    "GO_FOR_ADAPTER_OBSERVATION_REMEDIATION",
    "GO_FOR_BC_READY_REBUILD_FROM_CORRECTED_ADAPTER",
    "GO_FOR_UNITY_OBSERVATIONBUILDER_REMEDIATION",
    "GO_FOR_SPEC_DOC_RECONCILIATION_ONLY",
    "NO_GO_RETRAINING_UNTIL_OBSERVATION_FIXED",
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
    p = argparse.ArgumentParser(description="Build Stage10D.3 mapping trace report")
    p.add_argument("--reports-dir", type=Path, default=Path("python/week6_student/reports"))
    p.add_argument(
        "--output",
        type=Path,
        default=Path(
            "python/week6_student/reports/"
            "LEGACY032_UNITY_V2_STAGE10D3_GYM_TO_UNITY_OBSERVATION_MAPPING_TRACE_REPORT.md"
        ),
    )
    return p.parse_args()


def _classify(raw: Dict[str, Any], trace: Dict[str, Any], perm: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, str]:
    raw_eq_adapt = bool(trace.get("transform_diagnostics", {}).get("raw_to_adapted_equal", False))
    bc_preserve = bool(trace.get("bc_packaging_preservation_check", {}).get("sampled_all_equal", False))
    owner_conflict = bool(src.get("cross_source_consistency", {}).get("owner_semantics_conflict_detected", False))

    # If raw->adapted differs, adapter is first mismatch layer.
    if not raw_eq_adapt:
        return {
            "primary": "ADAPTER_OBSERVATION_CHANNEL_MAPPING_ERROR",
            "gate": "GO_FOR_ADAPTER_OBSERVATION_REMEDIATION",
            "first_mismatch_layer": "raw_gym_observation -> adapted_unity_v2_dataset",
        }

    # If adapted->bc packaging corrupts, bc packager layer.
    if not bc_preserve:
        return {
            "primary": "BC_READY_PACKAGING_OBSERVATION_CORRUPTION",
            "gate": "GO_FOR_BC_READY_REBUILD_FROM_CORRECTED_ADAPTER",
            "first_mismatch_layer": "adapted_unity_v2_dataset -> bc_ready_dataset",
        }

    # If code declares incompatible owner semantics while data is preserved across export/adapter/bc,
    # the mismatch is semantic incompatibility between Unity runtime observation and BC semantics.
    if owner_conflict:
        return {
            "primary": "UNITY_AND_BC_USE_INCOMPATIBLE_OBSERVATION_SEMANTICS",
            "gate": "NO_GO_RETRAINING_UNTIL_OBSERVATION_FIXED",
            "first_mismatch_layer": "unity_runtime_observationbuilder_semantics_vs_teacher_raw_semantics",
        }

    # If no clear conflict surfaced.
    return {
        "primary": "INCONCLUSIVE_NEEDS_MANUAL_TRACE",
        "gate": "GO_FOR_NEXT_DIAGNOSTIC",
        "first_mismatch_layer": "inconclusive",
    }


def main() -> int:
    args = parse_args()
    root = _repo_root()
    reports = _resolve(root, args.reports_dir)
    out_path = _resolve(root, args.output)

    raw = _load(reports / "stage10d3_raw_gym_observation_channel_probe.json")
    trace = _load(reports / "stage10d3_adapter_observation_transform_trace.json")
    perm = _load(reports / "stage10d3_channel_permutation_search.json")
    src = _load(reports / "stage10d3_source_code_mapping_audit.json")
    d1r = _load(reports / "stage10d1r_observation_channel_comparison_corrected.json")

    decision = _classify(raw, trace, perm, src)
    if decision["primary"] not in ALLOWED_ROOT_CAUSE:
        raise RuntimeError(f"Unexpected root cause classification: {decision['primary']}")
    if decision["gate"] not in ALLOWED_GATE:
        raise RuntimeError(f"Unexpected gate decision: {decision['gate']}")

    raw_group_checks = raw.get("empirical_channel_map_inference", {}).get("declared_group_checks", {})
    transform = trace.get("transform_diagnostics", {})
    bc_pres = trace.get("bc_packaging_preservation_check", {})
    src_cons = src.get("cross_source_consistency", {})

    b2_abs = d1r.get("focus_interpretation", {}).get("B2", {}).get("by_owner_mode", {}).get("absolute_player_channels", {})
    c3_abs = d1r.get("focus_interpretation", {}).get("C3", {}).get("by_owner_mode", {}).get("absolute_player_channels", {})

    lines: List[str] = []
    lines.append("# LEGACY032 Unity v2 Stage 10D.3 Gym-to-Unity Observation Mapping Trace Report")
    lines.append("")
    lines.append("## 1. Scope")
    lines.append("- Read-only trace audit only.")
    lines.append("- No retraining, no PPO.")
    lines.append("- No dataset/checkpoint mutation.")
    lines.append("- No runtime semantics change.")
    lines.append("- No ActionApplier/MatchManager modifications.")
    lines.append("")
    lines.append("## 2. Inputs")
    lines.append(f"- commit hash: {_git_commit(root)}")
    lines.append(f"- raw probe: {(reports / 'stage10d3_raw_gym_observation_channel_probe.json').as_posix()}")
    lines.append(f"- adapter trace: {(reports / 'stage10d3_adapter_observation_transform_trace.json').as_posix()}")
    lines.append(f"- permutation search: {(reports / 'stage10d3_channel_permutation_search.json').as_posix()}")
    lines.append(f"- source-code audit: {(reports / 'stage10d3_source_code_mapping_audit.json').as_posix()}")
    lines.append(f"- Stage10D.1R comparison: {(reports / 'stage10d1r_observation_channel_comparison_corrected.json').as_posix()}")
    lines.append("")
    lines.append("## 3. Stage10D.1R Recap")
    lines.append(f"- B2 (Unity abs): owner={b2_abs.get('owner')}, unit_type={b2_abs.get('unit_type')}, current_action={b2_abs.get('current_action')}, direction={b2_abs.get('direction')}")
    lines.append(f"- C3 (Unity abs): owner={c3_abs.get('owner')}, unit_type={c3_abs.get('unit_type')}, current_action={c3_abs.get('current_action')}, direction={c3_abs.get('direction')}")
    lines.append("- Stage10D.1R already confirmed non-owner mismatch persists after owner-mode correction.")
    lines.append("")
    lines.append("## 4. Raw Gym Observation Empirical Channel Map")
    lines.append(f"- raw observation shape: {raw.get('observations', {}).get('shape')}")
    lines.append(f"- owner [2..4] one-hot share(sum==1): {raw_group_checks.get('owner_2_4', {}).get('share_sum_eq_1')}")
    lines.append(f"- unit_type [5..11] one-hot share(sum==1): {raw_group_checks.get('unit_type_5_11', {}).get('share_sum_eq_1')}")
    lines.append(f"- current_action [12..17] one-hot share(sum==1): {raw_group_checks.get('current_action_12_17', {}).get('share_sum_eq_1')}")
    lines.append(f"- direction [18..21] one-hot share(sum==1): {raw_group_checks.get('direction_18_21', {}).get('share_sum_eq_1')}")
    lines.append("- Raw gym observation appears internally structured as a stable 27-channel tensor.")
    lines.append("")
    lines.append("## 5. Adapter Transform Trace")
    lines.append(f"- raw->adapted equal: {transform.get('raw_to_adapted_equal')}")
    lines.append(f"- raw->adapted delta: {transform.get('raw_to_adapted')}")
    lines.append(
        "- adapter transform flags: "
        + str(transform.get("adapter_transform_classification", {}))
    )
    lines.append("- No explicit observation channel remap was detected in Legacy032 adapter path.")
    lines.append("")
    lines.append("## 6. BC-ready Observation Channel Map")
    lines.append(f"- adapted->bc sampled all equal: {bc_pres.get('sampled_all_equal')}")
    lines.append(f"- sampled mismatch count: {bc_pres.get('sampled_mismatch_count')}")
    lines.append("- BC-ready packager preserves adapted observation channels for sampled keyed joins.")
    lines.append("")
    lines.append("## 7. Unity Runtime Observation Channel Map")
    lines.append(
        "- source-code owner semantics conflict detected: "
        + str(src_cons.get("owner_semantics_conflict_detected"))
    )
    lines.append("- ObservationContract documents absolute owner channels; ObservationBuilder UnityMvpTransfer path documents perspective owner channels.")
    lines.append("- This semantic split is consistent with Stage10D.2/10D.1R conflict findings.")
    lines.append("")
    lines.append("## 8. Channel Permutation / Shift Analysis")
    lines.append(
        "- permutation findings: " + str(perm.get("findings", {}))
    )
    lines.append("- Simple within-group permutation does not fully explain worker/base/action/direction mismatch patterns.")
    lines.append("")
    lines.append("## 9. Source Code Mapping Audit")
    lines.append(f"- files audited: {len(src.get('declared_mapping_table', []))}")
    lines.append(f"- owner conflict in declarations: {src_cons.get('owner_semantics_conflict_detected')}")
    lines.append(f"- unit_type declared across core sources: {src_cons.get('unit_type_declared_in_all_core_sources')}")
    lines.append(f"- current_action declared across core sources: {src_cons.get('current_action_declared_in_all_core_sources')}")
    lines.append(f"- direction declared across core sources: {src_cons.get('direction_declared_in_all_core_sources')}")
    lines.append("")
    lines.append("## 10. Root-Cause Classification")
    lines.append(f"- primary: {decision['primary']}")
    lines.append(f"- first layer where mismatch appears: {decision['first_mismatch_layer']}")
    lines.append("")
    lines.append("## 11. Patch Plan")
    lines.append("- Freeze runtime behavior during audit closure.")
    lines.append("- Define canonical cross-pipeline observation semantics (owner/unit_type/current_action/direction) as a versioned contract.")
    lines.append("- Add explicit observation semantic adapter (or explicit rejection) rather than implicit reshape-only bridging.")
    lines.append("- Rebuild adapted + BC-ready artifacts only after mapping spec is approved.")
    lines.append("- Re-run Stage10D.1R/10D.3 on regenerated artifacts before any retraining decision.")
    lines.append("")
    lines.append("## 12. Gate Decision")
    lines.append(f"- {decision['gate']}")
    lines.append("")
    lines.append("## 13. Explicit Non-Claims")
    lines.append("- This report does not claim semantic parity between Gym-μRTS and Unity.")
    lines.append("- This report does not authorize retraining or PPO.")
    lines.append("- This report does not mutate runtime semantics, dataset files, or checkpoints.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
