#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ALLOWED_CLASSIFICATIONS = {
    "SEMANTIC_BC_READY_DATASET_BUILT",
    "SEMANTIC_BC_READY_DATASET_BUILD_FAILED",
    "SEMANTIC_BC_READY_VALIDATION_PASSED",
    "SEMANTIC_BC_READY_VALIDATION_FAILED",
    "STUDENT_LOADER_DRY_RUN_PASSED",
    "STUDENT_LOADER_DRY_RUN_FAILED",
    "STUDENT_FORWARD_DRY_RUN_PASSED",
    "STUDENT_FORWARD_DRY_RUN_FAILED",
    "READY_FOR_SEMANTIC_BC_RETRAINING",
    "NOT_READY_FOR_SEMANTIC_BC_RETRAINING",
}

ALLOWED_GATES = {
    "GO_FOR_SEMANTIC_BC_RETRAINING",
    "NO_GO_RETRAINING_UNTIL_BC_READY_VALIDATED",
    "GO_FOR_LOADER_FIX",
    "GO_FOR_FORWARD_DRY_RUN_FIX",
    "GO_FOR_NEXT_DIAGNOSTIC",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_optional(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _decide(
    build_ok: bool,
    validation_ok: bool,
    loader_ok: bool,
    forward_ok: bool,
) -> Dict[str, Any]:
    cls: List[str] = []

    if build_ok:
        cls.append("SEMANTIC_BC_READY_DATASET_BUILT")
    else:
        cls.append("SEMANTIC_BC_READY_DATASET_BUILD_FAILED")

    if validation_ok:
        cls.append("SEMANTIC_BC_READY_VALIDATION_PASSED")
    else:
        cls.append("SEMANTIC_BC_READY_VALIDATION_FAILED")

    if loader_ok:
        cls.append("STUDENT_LOADER_DRY_RUN_PASSED")
    else:
        cls.append("STUDENT_LOADER_DRY_RUN_FAILED")

    if forward_ok:
        cls.append("STUDENT_FORWARD_DRY_RUN_PASSED")
    else:
        cls.append("STUDENT_FORWARD_DRY_RUN_FAILED")

    if not build_ok:
        gate = "NO_GO_RETRAINING_UNTIL_BC_READY_VALIDATED"
        cls.append("NOT_READY_FOR_SEMANTIC_BC_RETRAINING")
    elif not validation_ok:
        gate = "NO_GO_RETRAINING_UNTIL_BC_READY_VALIDATED"
        cls.append("NOT_READY_FOR_SEMANTIC_BC_RETRAINING")
    elif not loader_ok:
        gate = "GO_FOR_LOADER_FIX"
        cls.append("NOT_READY_FOR_SEMANTIC_BC_RETRAINING")
    elif not forward_ok:
        gate = "GO_FOR_FORWARD_DRY_RUN_FIX"
        cls.append("NOT_READY_FOR_SEMANTIC_BC_RETRAINING")
    else:
        gate = "GO_FOR_SEMANTIC_BC_RETRAINING"
        cls.append("READY_FOR_SEMANTIC_BC_RETRAINING")

    for item in cls:
        if item not in ALLOWED_CLASSIFICATIONS:
            raise RuntimeError(f"unexpected classification: {item}")
    if gate not in ALLOWED_GATES:
        raise RuntimeError(f"unexpected gate: {gate}")

    return {
        "classifications": cls,
        "gate_decision": gate,
        "semantic_bc_retraining_authorized": gate == "GO_FOR_SEMANTIC_BC_RETRAINING",
    }


def _to_rel(root: Path, p: Optional[Path]) -> Optional[str]:
    if p is None:
        return None
    try:
        return p.resolve().relative_to(root).as_posix()
    except Exception:
        return p.as_posix()


def _md(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# LEGACY032 UNITY V2 Stage10D.7 Semantic BC-ready and Loader Dry-run Report")
    lines.append("")
    lines.append(f"- generated_at_utc: {report['generated_at_utc']}")
    lines.append(f"- gate_decision: {report['gate_decision']}")
    lines.append("")

    lines.append("## 1. Scope")
    lines.append("- Stage10D.7 only builds and validates semantic BC-ready artifacts and runs loader/forward dry-runs.")
    lines.append("- No retraining/PPO/checkpoint mutation is performed in this stage.")
    lines.append("")

    lines.append("## 2. Stage10D.6 Recap")
    recap = report.get("stage10d6_recap", {})
    for k, v in recap.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## 3. Semantic BC-ready Build")
    build = report.get("semantic_bc_ready_build", {})
    lines.append(f"- status: {build.get('status')}")
    lines.append(f"- output_dir: {build.get('output_dir')}")
    lines.append(f"- sample_count: {build.get('sample_count')}")
    lines.append("")

    lines.append("## 4. BC-ready Manifest")
    manifest = report.get("bc_manifest_summary", {})
    for k, v in manifest.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## 5. BC-ready Validation")
    validation = report.get("semantic_bc_ready_validation", {})
    lines.append(f"- status: {validation.get('status')}")
    lines.append(f"- hard_failures_count: {validation.get('hard_failures_count')}")
    lines.append("")

    lines.append("## 6. Student Loader Dry-run")
    loader = report.get("student_loader_dry_run", {})
    lines.append(f"- status: {loader.get('status')}")
    lines.append(f"- hard_failures_count: {loader.get('hard_failures_count')}")
    lines.append("")

    lines.append("## 7. Student Forward Dry-run")
    forward = report.get("student_forward_dry_run", {})
    lines.append(f"- status: {forward.get('status')}")
    lines.append(f"- hard_failures_count: {forward.get('hard_failures_count')}")
    lines.append(f"- dry_run_supervised_loss: {forward.get('dry_run_supervised_loss')}")
    lines.append("")

    lines.append("## 8. Remaining Risks")
    for item in report.get("remaining_risks", []):
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## 9. Gate Decision")
    lines.append(f"- gate_decision: {report['gate_decision']}")
    lines.append(f"- semantic_bc_retraining_authorized: {report['semantic_bc_retraining_authorized']}")
    lines.append("")

    lines.append("## 10. Explicit Non-Claims")
    for item in report.get("explicit_non_claims", []):
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## Primary Classifications")
    for c in report.get("primary_classifications", []):
        lines.append(f"- {c}")
    lines.append("")

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Stage10D.7 final report")
    p.add_argument("--bc-ready-dir", type=Path, required=True)
    p.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("python/week6_student/reports"),
    )
    p.add_argument(
        "--output-md",
        type=Path,
        default=Path(
            "python/week6_student/reports/"
            "LEGACY032_UNITY_V2_STAGE10D7_SEMANTIC_BC_READY_AND_LOADER_DRY_RUN_REPORT.md"
        ),
    )
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path(
            "python/week6_student/reports/"
            "LEGACY032_UNITY_V2_STAGE10D7_SEMANTIC_BC_READY_AND_LOADER_DRY_RUN_REPORT.json"
        ),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = _repo_root()
    bc_ready_dir = _resolve(root, args.bc_ready_dir).resolve()
    reports_dir = _resolve(root, args.reports_dir).resolve()
    output_md = _resolve(root, args.output_md).resolve()
    output_json = _resolve(root, args.output_json).resolve()

    build_report_path = bc_ready_dir / "stage10d7_bc_ready_build_report.json"
    bc_manifest_path = bc_ready_dir / "bc_manifest.json"
    stage10d6_report_path = reports_dir / "LEGACY032_UNITY_V2_STAGE10D6_MAPPING_PATCH_AND_SEMANTIC_REBUILD_REPORT.json"
    validation_report_path = reports_dir / "stage10d7_semantic_bc_ready_validation.json"
    loader_report_path = reports_dir / "stage10d7_student_loader_dry_run.json"
    forward_report_path = reports_dir / "stage10d7_student_forward_dry_run.json"

    build_report = _load_optional(build_report_path) or {}
    bc_manifest = _load_optional(bc_manifest_path) or {}
    stage10d6_report = _load_optional(stage10d6_report_path) or {}
    validation_report = _load_optional(validation_report_path) or {}
    loader_report = _load_optional(loader_report_path) or {}
    forward_report = _load_optional(forward_report_path) or {}

    build_ok = build_report.get("status") == "pass"
    validation_ok = validation_report.get("status") == "pass"
    loader_ok = loader_report.get("status") == "pass"
    forward_ok = forward_report.get("status") == "pass"

    decision = _decide(
        build_ok=bool(build_ok),
        validation_ok=bool(validation_ok),
        loader_ok=bool(loader_ok),
        forward_ok=bool(forward_ok),
    )

    remaining_risks: List[str] = []
    if not build_ok:
        remaining_risks.append("Semantic BC-ready build failed; split artifacts are not trustworthy.")
    if not validation_ok:
        remaining_risks.append("BC-ready contract/semantic validation failed; retraining must remain blocked.")
    if not loader_ok:
        remaining_risks.append("Student loader dry-run failed; training stack cannot reliably consume dataset.")
    if not forward_ok:
        remaining_risks.append("Student forward dry-run failed; model I/O contract still inconsistent.")
    if not remaining_risks:
        remaining_risks.append(
            "Semantic compatibility is structural only and does not prove policy-level behavior in Unity matches."
        )

    forward_loss = None
    if isinstance(forward_report.get("details"), dict):
        forward_loss = forward_report["details"].get("dry_run_supervised_loss")

    report: Dict[str, Any] = {
        "stage": "10D.7",
        "generated_at_utc": _iso_now(),
        "inputs": {
            "bc_ready_dir": _to_rel(root, bc_ready_dir),
            "build_report": _to_rel(root, build_report_path),
            "bc_manifest": _to_rel(root, bc_manifest_path),
            "stage10d6_report": _to_rel(root, stage10d6_report_path),
            "validation_report": _to_rel(root, validation_report_path),
            "loader_report": _to_rel(root, loader_report_path),
            "forward_report": _to_rel(root, forward_report_path),
        },
        "stage10d6_recap": {
            "stage10d6_gate": stage10d6_report.get("gate_decision"),
            "mapping_spec_version": bc_manifest.get("mapping_spec_version"),
            "observation_semantics_version": bc_manifest.get("observation_semantics_version"),
            "source_adapted_dataset_stage": bc_manifest.get("source_adapted_dataset_stage"),
            "source_adapted_dir": bc_manifest.get("source_adapted_dir"),
        },
        "semantic_bc_ready_build": {
            "status": build_report.get("status", "missing"),
            "output_dir": build_report.get("output_dir", bc_ready_dir.as_posix()),
            "sample_count": build_report.get("sample_count"),
            "hard_failures_count": len(build_report.get("hard_failures", [])),
        },
        "bc_manifest_summary": {
            "schema_version": bc_manifest.get("schema_version"),
            "dataset_kind": bc_manifest.get("dataset_kind"),
            "source_stage": bc_manifest.get("source_stage"),
            "source_adapted_dataset_stage": bc_manifest.get("source_adapted_dataset_stage"),
            "mapping_spec_version": bc_manifest.get("mapping_spec_version"),
            "observation_semantics_version": bc_manifest.get("observation_semantics_version"),
            "observation_shape": bc_manifest.get("observation_shape"),
            "action_shape": bc_manifest.get("action_shape"),
            "branch_sizes": bc_manifest.get("branch_sizes"),
            "num_train": bc_manifest.get("num_train"),
            "num_validation": bc_manifest.get("num_validation"),
            "num_debug": bc_manifest.get("num_debug"),
            "dtype": bc_manifest.get("dtype"),
            "checks": bc_manifest.get("checks"),
        },
        "semantic_bc_ready_validation": {
            "status": validation_report.get("status", "missing"),
            "hard_failures_count": len(validation_report.get("hard_failures", [])),
        },
        "student_loader_dry_run": {
            "status": loader_report.get("status", "missing"),
            "hard_failures_count": len(loader_report.get("hard_failures", [])),
        },
        "student_forward_dry_run": {
            "status": forward_report.get("status", "missing"),
            "hard_failures_count": len(forward_report.get("hard_failures", [])),
            "dry_run_supervised_loss": forward_loss,
        },
        "remaining_risks": remaining_risks,
        "primary_classifications": decision["classifications"],
        "gate_decision": decision["gate_decision"],
        "semantic_bc_retraining_authorized": decision["semantic_bc_retraining_authorized"],
        "explicit_non_claims": [
            "No retraining performed in Stage10D.7.",
            "No PPO performed in Stage10D.7.",
            "No checkpoint mutation performed in Stage10D.7.",
            "No Unity runtime behavior mutation performed in Stage10D.7.",
            "Semantic observation compatibility does not prove policy-level behavior.",
        ],
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(_md(report), encoding="utf-8")

    print(output_json.as_posix())
    print(output_md.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
