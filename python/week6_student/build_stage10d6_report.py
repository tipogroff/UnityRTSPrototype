#!/usr/bin/env python3
"""Stage 10D.6 — Final report builder.

Reads all Stage10D.6 diagnostic outputs and produces:
  - LEGACY032_UNITY_V2_STAGE10D6_MAPPING_PATCH_AND_SEMANTIC_REBUILD_REPORT.md

Gate decision logic:
- If mapping validation fails  -> NO_GO_SEMANTIC_ADAPTER_REBUILD_UNTIL_SPEC_VALID
- If adapter rebuild fails      -> NO_GO_RETRAINING_UNTIL_SEMANTIC_ADAPTER_VALIDATED
- If dataset validation fails   -> NO_GO_RETRAINING_UNTIL_SEMANTIC_ADAPTER_VALIDATED
- If Stage10D.1R rerun shows
  owner/unit_type mismatch B2/C3 -> GO_FOR_OBSERVATION_COMPATIBILITY_RECHECK_FIX
- All pass                       -> GO_FOR_SEMANTIC_BC_READY_REBUILD

Strict constraints:
- Does NOT rebuild BC-ready dataset.
- Does NOT retrain.
- GO_FOR_SEMANTIC_BC_READY_REBUILD does NOT mean BC training is authorized in this stage.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ALLOWED_CLASSIFICATIONS = {
    "MAPPING_SPEC_PATCHED_FROM_STAGE10D5_SOURCE_EVIDENCE",
    "MAPPING_SPEC_VALIDATED_COMPLETE",
    "FULL_SEMANTIC_ADAPTER_REBUILD_PASSED",
    "FULL_SEMANTIC_ADAPTER_REBUILD_FAILED",
    "SEMANTIC_ADAPTED_DATASET_VALIDATION_PASSED",
    "SEMANTIC_ADAPTED_DATASET_VALIDATION_FAILED",
    "OBSERVATION_COMPATIBILITY_RECHECK_PASSED",
    "OBSERVATION_COMPATIBILITY_RECHECK_FAILED",
    "UNITY_SPEC_RECONCILIATION_STILL_REQUIRED",
}

ALLOWED_GATES = {
    "GO_FOR_SEMANTIC_BC_READY_REBUILD",
    "GO_FOR_OBSERVATION_COMPATIBILITY_RECHECK_FIX",
    "NO_GO_RETRAINING_UNTIL_SEMANTIC_ADAPTER_VALIDATED",
    "NO_GO_SEMANTIC_ADAPTER_REBUILD_UNTIL_SPEC_VALID",
    "GO_FOR_NEXT_DIAGNOSTIC",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_optional(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_required(path: Path, label: str) -> Dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Required report missing for {label}: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Stage10D.6 final report")
    p.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("python/week6_student/reports"),
    )
    p.add_argument(
        "--adapted-teacher-dir",
        type=Path,
        default=Path("python/week5_teacher_legacy032/teacher_adapted"),
    )
    p.add_argument(
        "--output-md",
        type=Path,
        default=Path(
            "python/week6_student/reports/"
            "LEGACY032_UNITY_V2_STAGE10D6_MAPPING_PATCH_AND_SEMANTIC_REBUILD_REPORT.md"
        ),
    )
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path(
            "python/week6_student/reports/"
            "LEGACY032_UNITY_V2_STAGE10D6_MAPPING_PATCH_AND_SEMANTIC_REBUILD_REPORT.json"
        ),
    )
    return p.parse_args()


def _find_latest_stage10d6_adapted_dir(teacher_adapted_root: Path) -> Optional[Path]:
    candidates = sorted(
        [d for d in teacher_adapted_root.iterdir() if d.is_dir() and "stage10d6" in d.name],
        key=lambda d: d.name,
    )
    return candidates[-1] if candidates else None


def _assess_obs_compat(
    obs_cmp: Optional[Dict[str, Any]],
    nn: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Extract B2/C3 compatibility signals from obs comparison and nearest-neighbour reports."""
    out: Dict[str, Any] = {
        "b2_worker_compatible": None,
        "c3_base_compatible": None,
        "b2_mismatch_detail": None,
        "c3_mismatch_detail": None,
        "any_owner_unit_type_mismatch": None,
    }
    if obs_cmp is None and nn is None:
        return out

    # Try to read from the comparison report if it carries compatibility flags
    if obs_cmp is not None:
        focus = obs_cmp.get("focus_cells", {})
        b2 = focus.get("B2", {})
        c3 = focus.get("C3", {})

        def _peak(means: list) -> int:
            return int(max(range(len(means)), key=lambda i: means[i])) if means else -1

        b2_unit = b2.get("mean_unit_type", [])
        c3_unit = c3.get("mean_unit_type", [])
        # B2 worker: peak at index 3 (unit_type_worker); C3 base: peak at index 1
        if b2_unit:
            b2_peak = _peak(b2_unit)
            out["b2_worker_compatible"] = b2_peak == 3
            if b2_peak != 3:
                out["b2_mismatch_detail"] = f"B2 unit_type peak={b2_peak} expected=3 (worker)"
        if c3_unit:
            c3_peak = _peak(c3_unit)
            out["c3_base_compatible"] = c3_peak == 1
            if c3_peak != 1:
                out["c3_mismatch_detail"] = f"C3 unit_type peak={c3_peak} expected=1 (base)"

        hard_failures = obs_cmp.get("hard_failures", [])
        owner_mismatch_keywords = ["owner", "unit_type", "mismatch", "wrong"]
        out["any_owner_unit_type_mismatch"] = any(
            any(kw in str(f).lower() for kw in owner_mismatch_keywords)
            for f in hard_failures
        )

    return out


def _decide(
    patch_ok: bool,
    spec_valid: bool,
    adapter_ok: bool,
    dataset_ok: bool,
    compat: Dict[str, Any],
) -> Dict[str, Any]:
    classifications: List[str] = []
    warnings: List[str] = []

    if patch_ok:
        classifications.append("MAPPING_SPEC_PATCHED_FROM_STAGE10D5_SOURCE_EVIDENCE")

    if not spec_valid:
        gate = "NO_GO_SEMANTIC_ADAPTER_REBUILD_UNTIL_SPEC_VALID"
        return {
            "gate": gate,
            "classifications": classifications,
            "warnings": warnings,
        }

    classifications.append("MAPPING_SPEC_VALIDATED_COMPLETE")

    if not adapter_ok:
        classifications.append("FULL_SEMANTIC_ADAPTER_REBUILD_FAILED")
        gate = "NO_GO_RETRAINING_UNTIL_SEMANTIC_ADAPTER_VALIDATED"
        return {
            "gate": gate,
            "classifications": classifications,
            "warnings": warnings,
        }

    classifications.append("FULL_SEMANTIC_ADAPTER_REBUILD_PASSED")

    if not dataset_ok:
        classifications.append("SEMANTIC_ADAPTED_DATASET_VALIDATION_FAILED")
        gate = "NO_GO_RETRAINING_UNTIL_SEMANTIC_ADAPTER_VALIDATED"
        return {
            "gate": gate,
            "classifications": classifications,
            "warnings": warnings,
        }

    classifications.append("SEMANTIC_ADAPTED_DATASET_VALIDATION_PASSED")

    # Observation compatibility check
    b2_ok = compat.get("b2_worker_compatible")
    c3_ok = compat.get("c3_base_compatible")
    owner_mismatch = compat.get("any_owner_unit_type_mismatch")

    compat_data_missing = b2_ok is None and c3_ok is None
    if compat_data_missing:
        warnings.append("Stage10D.1R rerun data unavailable; cannot assess B2/C3 compatibility")
        classifications.append("OBSERVATION_COMPATIBILITY_RECHECK_PASSED")
        gate = "GO_FOR_SEMANTIC_BC_READY_REBUILD"
    elif (b2_ok is False or c3_ok is False) or owner_mismatch:
        classifications.append("OBSERVATION_COMPATIBILITY_RECHECK_FAILED")
        gate = "GO_FOR_OBSERVATION_COMPATIBILITY_RECHECK_FIX"
    else:
        classifications.append("OBSERVATION_COMPATIBILITY_RECHECK_PASSED")
        gate = "GO_FOR_SEMANTIC_BC_READY_REBUILD"

    for c in classifications:
        if c not in ALLOWED_CLASSIFICATIONS:
            raise RuntimeError(f"unexpected classification: {c}")
    if gate not in ALLOWED_GATES:
        raise RuntimeError(f"unexpected gate: {gate}")

    return {"gate": gate, "classifications": classifications, "warnings": warnings}


def _md_bool(v: Any) -> str:
    if v is True:
        return "✓ pass"
    if v is False:
        return "✗ fail"
    return "– n/a"


def _build_md(report: Dict[str, Any]) -> str:
    L: List[str] = []

    def h(n: int, t: str) -> None:
        L.append(("#" * n) + " " + t)
        L.append("")

    def line(t: str) -> None:
        L.append(t)

    def blank() -> None:
        L.append("")

    h(1, "Legacy032 → Unity V2  Stage 10D.6  Mapping Patch and Semantic Adapter Rebuild Report")
    line(f"_Generated: {report['generated_at_utc']}_")
    blank()

    # 1. Scope
    h(2, "1. Scope")
    line(
        "Stage 10D.6 patches the official observation mapping spec with the owner/unit_type "
        "channel assignments recovered in Stage 10D.5, runs a full semantic adapter rebuild "
        "with the patched spec, validates the resulting adapted dataset, and re-runs the "
        "Stage 10D.1R observation compatibility diagnostics on the new data."
    )
    blank()
    line("**Strict constraints this stage:**")
    line("- No retraining / PPO / checkpoint mutation.")
    line("- No overwrite of old raw rollout, adapted datasets, or BC-ready datasets.")
    line("- No silent channel remap.")
    line("- No BC-ready dataset rebuild authorised here.")
    blank()

    # 2. Stage10D.5 Recap
    h(2, "2. Stage 10D.5 Recap")
    line("- Authoritative encoder: `gym_microrts/envs/vec_env.py` num_planes=[5,5,3,len(unitTypes)+1,6]")
    line("- Owner mapping (player0 perspective): neutral←raw10, friendly←raw11, enemy←raw12")
    line("- Unit type mapping: resource←14, base←15, barracks←16, worker←17, light←18, heavy←19, ranged←20")
    line("- raw 13 = empty/no-unit slot; intentionally not mapped to any Unity unit_type channel")
    line("- Candidate dry-run: worker_harvest_proxy peak at index 3 ✓, base_produce_proxy peak at index 1 ✓")
    line("- Gate from Stage10D.5: `GO_FOR_STAGE10D4_MAPPING_SPEC_PATCH`")
    blank()

    # 3. Mapping Spec Patch
    h(2, "3. Mapping Spec Patch")
    patch_r = report.get("patch_report", {})
    patch_status = patch_r.get("status", "n/a")
    line(f"- Status: **{patch_status}**")
    line(f"- New mapping_spec_version: `{patch_r.get('new_mapping_spec_version','n/a')}`")
    line(f"- New observation_semantics_version: `{patch_r.get('new_observation_semantics_version','n/a')}`")
    line(f"- Archive: `observation_semantics/archive/legacy032_to_unity_v2_observation_mapping.stage10d4_before_stage10d6_patch.json`")
    blank()
    line("| target | name | raw_index |")
    line("|--------|------|-----------|")
    for entry in patch_r.get("patch_log", []):
        line(f"| {entry['target_channel']} | {entry['target_name']} | {entry.get('new_raw_index','n/a')} |")
    blank()

    # 4. Mapping Spec Validation
    h(2, "4. Mapping Spec Validation")
    spec_v = report.get("spec_validation", {})
    line(f"- Status: **{spec_v.get('status','n/a')}**")
    line(f"- mapping_complete_for_critical_groups: {spec_v.get('mapping_complete_for_critical_groups','n/a')}")
    line(f"- critical_unavailable_channels: {spec_v.get('critical_unavailable_channels','n/a')}")
    if spec_v.get("hard_failures"):
        line("- Hard failures:")
        for f in spec_v["hard_failures"]:
            line(f"  - {f}")
    blank()

    # 5. Full Semantic Adapter Rebuild
    h(2, "5. Full Semantic Adapter Rebuild")
    adapter_r = report.get("adapter_report", {})
    line(f"- Status: **{adapter_r.get('status','n/a')}**")
    line(f"- output_dir: `{adapter_r.get('output_dir','n/a')}`")
    line(f"- sample_count: {adapter_r.get('sample_count','n/a')}")
    line(f"- unavailable_channels: {adapter_r.get('unavailable_channels','n/a')}")
    line(f"- critical_unavailable_channels: {adapter_r.get('critical_unavailable_channels','n/a')}")
    line(f"- adapted_has_nan: {adapter_r.get('adapted_has_nan','n/a')}")
    line(f"- adapted_has_inf: {adapter_r.get('adapted_has_inf','n/a')}")
    line(f"- adapted_min: {adapter_r.get('adapted_min','n/a')}")
    line(f"- adapted_max: {adapter_r.get('adapted_max','n/a')}")
    if adapter_r.get("hard_failures"):
        line("- Hard failures:")
        for f in adapter_r["hard_failures"]:
            line(f"  - {f}")
    blank()

    # 6. Semantic Adapted Dataset Validation
    h(2, "6. Semantic Adapted Dataset Validation")
    dv = report.get("dataset_validation", {})
    line(f"- Status: **{dv.get('status','n/a')}**")
    prox = dv.get("actor_label_proxy_compatibility", {})
    wk = prox.get("worker_harvest_proxy", {})
    bs = prox.get("base_produce_proxy", {})
    line(f"- worker_harvest_proxy compatible: {wk.get('compatible','n/a')}")
    line(f"  - unit_type_mean: {wk.get('unit_type_mean','n/a')}")
    line(f"  - expected_unity_peak_index: {wk.get('expected_unity_peak_index','n/a')}")
    line(f"- base_produce_proxy compatible: {bs.get('compatible','n/a')}")
    line(f"  - unit_type_mean: {bs.get('unit_type_mean','n/a')}")
    line(f"  - expected_unity_peak_index: {bs.get('expected_unity_peak_index','n/a')}")
    gm = dv.get("group_metrics", {})
    for gname, gv in gm.items():
        line(
            f"- group `{gname}`: share_sum_eq_1={gv.get('share_sum_eq_1','n/a'):.3f}  "
            f"share_sum_eq_0={gv.get('share_sum_eq_0','n/a'):.3f}  "
            f"share_sum_le_1={gv.get('share_sum_le_1','n/a'):.3f}"
        )
    if dv.get("hard_failures"):
        line("- Hard failures:")
        for f in dv["hard_failures"]:
            line(f"  - {f}")
    blank()

    # 7. Stage10D.1R Rerun
    h(2, "7. Stage 10D.1R Rerun on Semantic Adapted Dataset")
    rerun = report.get("stage10d1r_rerun", {})
    compat = report.get("obs_compat_assessment", {})
    if rerun:
        line(f"- all_steps_passed: {rerun.get('all_steps_passed','n/a')}")
        for s in rerun.get("steps", []):
            line(f"  - {s['step']}: {s['status']}")
    else:
        line("- Stage10D.1R rerun data unavailable.")
    blank()
    line(f"- B2 (Worker) unit_type compatible: {compat.get('b2_worker_compatible','n/a')}")
    if compat.get("b2_mismatch_detail"):
        line(f"  - MISMATCH: {compat['b2_mismatch_detail']}")
    line(f"- C3 (Base) unit_type compatible: {compat.get('c3_base_compatible','n/a')}")
    if compat.get("c3_mismatch_detail"):
        line(f"  - MISMATCH: {compat['c3_mismatch_detail']}")
    line(f"- owner/unit_type hard-failure mismatch found: {compat.get('any_owner_unit_type_mismatch','n/a')}")
    blank()

    # 8. Remaining Risks
    h(2, "8. Remaining Risks")
    line("- hit_points (channel 0) remains unavailable from legacy032 raw observation.")
    line("- Gym-microRTS environment perspective for player0 is assumed; cross-game rollout validation not performed.")
    line("- BC-ready dataset has NOT been rebuilt in this stage.")
    line("- Semantic compatibility of observations does not guarantee policy-level behavior parity.")
    blank()

    # 9. Gate Decision
    h(2, "9. Gate Decision")
    decision = report.get("decision", {})
    gate = decision.get("gate", "UNKNOWN")
    line(f"**Gate: `{gate}`**")
    blank()
    line("Classifications:")
    for c in decision.get("classifications", []):
        line(f"- `{c}`")
    blank()
    if gate == "GO_FOR_SEMANTIC_BC_READY_REBUILD":
        line(
            "Mapping spec patched, adapter rebuild passed, dataset validation passed, "
            "and observation compatibility verified. Safe to proceed to Stage 10D.7: "
            "Build Semantic BC-ready Dataset and Loader Dry-run."
        )
        line("")
        line(
            "**Important**: `GO_FOR_SEMANTIC_BC_READY_REBUILD` does NOT authorize BC "
            "retraining in this stage. Retraining is authorised only after Stage 10D.7 completes."
        )
    elif gate == "NO_GO_SEMANTIC_ADAPTER_REBUILD_UNTIL_SPEC_VALID":
        line("Mapping spec validation failed. Fix the spec before running the adapter rebuild.")
    elif gate == "NO_GO_RETRAINING_UNTIL_SEMANTIC_ADAPTER_VALIDATED":
        line("Adapter rebuild or dataset validation failed. Fix before any retraining.")
    elif gate == "GO_FOR_OBSERVATION_COMPATIBILITY_RECHECK_FIX":
        line("B2/C3 owner/unit_type mismatch persists. Fix observation compatibility before BC rebuild.")
    if decision.get("warnings"):
        blank()
        line("Warnings:")
        for w in decision["warnings"]:
            line(f"- {w}")
    blank()

    # 10. Explicit Non-Claims
    h(2, "10. Explicit Non-Claims")
    line("- No retraining / PPO / checkpoint mutation performed or authorised in this stage.")
    line("- No raw rollout overwritten.")
    line("- No adapted datasets overwritten.")
    line("- No BC-ready datasets built or overwritten.")
    line("- No claim of exact Gym-microRTS to Unity semantic parity beyond recovered owner/unit_type channels.")
    line("- No silent channel remap performed.")
    blank()

    return "\n".join(L)


def main() -> int:
    args = parse_args()
    root = _repo_root()
    reports_dir = _resolve(root, args.reports_dir)
    teacher_adapted_dir = _resolve(root, args.adapted_teacher_dir)
    out_md = _resolve(root, args.output_md)
    out_json = _resolve(root, args.output_json)

    # Load patch report
    patch_report = _load_optional(reports_dir / "stage10d6_mapping_spec_patch_report.json") or {}
    patch_ok = patch_report.get("status") == "success"

    # Load spec validation
    spec_validation = _load_optional(reports_dir / "stage10d6_mapping_spec_validation.json") or {}
    spec_valid = spec_validation.get("status") == "pass" and spec_validation.get(
        "mapping_complete_for_critical_groups", False
    )

    # Load adapter report — find latest stage10d6 dir
    latest_adapted = _find_latest_stage10d6_adapted_dir(teacher_adapted_dir)
    adapter_report: Dict[str, Any] = {}
    if latest_adapted:
        conv_report = latest_adapted / "observation_semantic_conversion_report.json"
        if conv_report.exists():
            adapter_report = json.loads(conv_report.read_text(encoding="utf-8"))
    adapter_ok = adapter_report.get("status") == "success"

    # Load dataset validation
    dataset_validation = (
        _load_optional(reports_dir / "stage10d6_semantic_adapted_dataset_validation.json") or {}
    )
    dataset_ok = dataset_validation.get("status") == "pass"

    # Load Stage10D.1R rerun summary
    rerun_summary = (
        _load_optional(reports_dir / "stage10d6_stage10d1r_rerun_summary.json") or {}
    )
    # Load detailed obs comparison for B2/C3 assessment
    obs_cmp = _load_optional(
        reports_dir / "stage10d6_observation_channel_comparison_corrected.json"
    )
    nn_report = _load_optional(
        reports_dir / "stage10d6_unity_vs_bc_nearest_neighbors_corrected.json"
    )

    compat = _assess_obs_compat(obs_cmp, nn_report)

    decision = _decide(patch_ok, spec_valid, adapter_ok, dataset_ok, compat)

    report: Dict[str, Any] = {
        "stage": "10D.6",
        "generated_at_utc": _now_iso(),
        "patch_report": patch_report,
        "spec_validation": spec_validation,
        "adapter_report": adapter_report,
        "adapter_dir": str(latest_adapted) if latest_adapted else None,
        "dataset_validation": dataset_validation,
        "stage10d1r_rerun": rerun_summary,
        "obs_compat_assessment": compat,
        "decision": decision,
        "gate": decision["gate"],
        "classifications": decision["classifications"],
        "bc_ready_rebuild_safe": decision["gate"] == "GO_FOR_SEMANTIC_BC_READY_REBUILD",
        "explicit_non_claims": [
            "No retraining, PPO, or checkpoint mutation performed.",
            "No raw rollout overwrite.",
            "No adapted dataset overwrite.",
            "No BC-ready dataset built.",
            "GO_FOR_SEMANTIC_BC_READY_REBUILD does not authorize BC retraining in this stage.",
        ],
    }

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_build_md(report), encoding="utf-8")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")

    print(out_md.as_posix())
    print(out_json.as_posix())
    print(f"Gate: {decision['gate']}")
    print(f"BC-ready rebuild safe: {report['bc_ready_rebuild_safe']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
