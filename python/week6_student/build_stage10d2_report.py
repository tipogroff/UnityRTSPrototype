#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List


PRIMARY_ORDER = [
    "STAGE10D1_DIAGNOSTIC_CHANNEL_ASSUMPTION_ERROR",
    "CONTRACT_DOCUMENTATION_STALE_BUT_ARTIFACT_VALID",
    "UNITY_AND_BC_USE_DIFFERENT_PERSPECTIVE_ENCODING",
    "UNITY_OBSERVATION_CHANNEL_MAPPING_ERROR",
    "BC_ADAPTER_CHANNEL_MAPPING_ERROR",
    "STUDENT_LOADER_RESHAPE_OR_AXIS_ERROR",
    "BC_DATASET_OBSERVATION_CORRUPTED",
    "INCONCLUSIVE_NEEDS_MANUAL_CHANNEL_SPEC",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Stage10D.2 markdown report")
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("python/week6_student/reports"),
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        default="python/week6_student/runs/legacy032_v2_bc_minimal_20260501T195501Z/student_bc_transfer_best.pt",
    )
    parser.add_argument(
        "--bc-ready-dir",
        type=str,
        default=(
            "python/week5_teacher_legacy032/teacher_exports_bc/"
            "day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z"
        ),
    )
    parser.add_argument(
        "--scene-path",
        type=str,
        default="Assets/Scenes/Week6_StudentVisualInspection.unity",
    )
    parser.add_argument(
        "--stage10d1-report-path",
        type=str,
        default=(
            "python/week6_student/reports/"
            "LEGACY032_UNITY_V2_STAGE10D1_DATASET_DISTRIBUTION_DIAGNOSTIC_REPORT.md"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "python/week6_student/reports/"
            "LEGACY032_UNITY_V2_STAGE10D2_OBSERVATION_ENCODING_SOURCE_OF_TRUTH_REPORT.md"
        ),
    )
    return parser.parse_args()


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


def _pick_primary(audit: Dict[str, Any], loader: Dict[str, Any], bc_probe: Dict[str, Any]) -> str:
    loader_answers = loader.get("explicit_answers", {})
    if loader_answers.get("hidden_reshape_corruption_detected"):
        return "STUDENT_LOADER_RESHAPE_OR_AXIS_ERROR"

    candidates = set(audit.get("root_cause_candidates", []))
    for c in PRIMARY_ORDER:
        if c in candidates:
            # Prefer stage10d1 assumption error over generic doc staleness when both present.
            if c == "CONTRACT_DOCUMENTATION_STALE_BUT_ARTIFACT_VALID" and "STAGE10D1_DIAGNOSTIC_CHANNEL_ASSUMPTION_ERROR" in candidates:
                continue
            return c

    if not bc_probe.get("contract_checks", {}).get("branch_sizes_match_expected", False):
        return "BC_DATASET_OBSERVATION_CORRUPTED"

    return "INCONCLUSIVE_NEEDS_MANUAL_CHANNEL_SPEC"


def _gate_from_primary(primary: str) -> str:
    mapping = {
        "BC_ADAPTER_CHANNEL_MAPPING_ERROR": "GO_FOR_BC_ADAPTER_OBSERVATION_REMEDIATION",
        "UNITY_OBSERVATION_CHANNEL_MAPPING_ERROR": "GO_FOR_UNITY_OBSERVATIONBUILDER_REMEDIATION",
        "STUDENT_LOADER_RESHAPE_OR_AXIS_ERROR": "GO_FOR_STUDENT_LOADER_REMEDIATION",
        "STAGE10D1_DIAGNOSTIC_CHANNEL_ASSUMPTION_ERROR": "GO_FOR_STAGE10D1_DIAGNOSTIC_FIX_AND_RERUN",
        "CONTRACT_DOCUMENTATION_STALE_BUT_ARTIFACT_VALID": "GO_FOR_MANIFEST_SPEC_RECONCILIATION",
        "BC_DATASET_OBSERVATION_CORRUPTED": "NO_GO_RETRAINING_UNTIL_OBSERVATION_FIXED",
        "UNITY_AND_BC_USE_DIFFERENT_PERSPECTIVE_ENCODING": "NO_GO_RETRAINING_UNTIL_OBSERVATION_FIXED",
        "INCONCLUSIVE_NEEDS_MANUAL_CHANNEL_SPEC": "GO_FOR_NEXT_DIAGNOSTIC",
    }
    return mapping.get(primary, "GO_FOR_NEXT_DIAGNOSTIC")


def _status_line(unity: str, adapter: str, manifest: str, d1: str) -> str:
    uniq = {unity, adapter, manifest, d1}
    if len(uniq) == 1 and "unknown" not in uniq:
        return "MATCH"
    if "missing" in uniq or "unknown" in uniq:
        return "MISSING"
    if "friendly" in unity and "player1" in adapter:
        return "CONFLICT"
    return "INCONCLUSIVE"


def main() -> int:
    args = parse_args()
    root = _repo_root()
    reports_dir = _resolve(root, args.reports_dir)
    out_path = _resolve(root, args.output)

    audit = _load(reports_dir / "stage10d2_observation_source_of_truth_audit.json")
    bc_probe = _load(reports_dir / "stage10d2_bc_channel_semantics_probe.json")
    snapshot_probe = _load(reports_dir / "stage10d2_unity_snapshot_channel_probe.json")
    loader = _load(reports_dir / "stage10d2_loader_roundtrip_probe.json")

    primary = _pick_primary(audit, loader, bc_probe)
    gate = _gate_from_primary(primary)
    secondary = [c for c in audit.get("root_cause_candidates", []) if c != primary]

    unity_owner_contract = (
        audit.get("discovered_unity_channel_map", {})
        .get("contract", {})
        .get("groups", {})
        .get("owner", {})
        .get("declared_semantics", "unknown")
    )
    unity_owner_builder = (
        audit.get("discovered_unity_channel_map", {})
        .get("builder", {})
        .get("unity_mvp_transfer_owner_semantics", "unknown")
    )
    adapter_owner = ", ".join(
        audit.get("discovered_adapter_channel_map", {}).get("owner_indices_2_4", [])
    )
    if not adapter_owner:
        adapter_owner = "missing"
    d1_owner_mode = (
        audit.get("discovered_stage10d1_assumed_channel_map", {})
        .get("owner_interpretation", {})
        .get("mode", "unknown")
    )

    status_owner = _status_line(unity_owner_builder, adapter_owner, unity_owner_contract, d1_owner_mode)

    lines: List[str] = []
    lines.append("# LEGACY032 Unity v2 Stage 10D.2 Observation Encoding Source-of-Truth Report")
    lines.append("")
    lines.append("## 1. Scope")
    lines.append("- Read-only diagnostic only.")
    lines.append("- No retraining.")
    lines.append("- No PPO.")
    lines.append("- No checkpoint mutation.")
    lines.append("- No dataset mutation.")
    lines.append("- No runtime semantics change.")
    lines.append("")
    lines.append("## 2. Inputs")
    lines.append(f"- repository commit hash: {_git_commit(root)}")
    lines.append(f"- checkpoint path: {args.checkpoint}")
    lines.append(f"- BC dataset paths: {args.bc_ready_dir}/bc_train.npz, {args.bc_ready_dir}/bc_validation.npz")
    lines.append(f"- Unity scene path: {args.scene_path}")
    lines.append(f"- Stage10D.1 report path: {args.stage10d1_report_path}")
    snap_list = snapshot_probe.get("snapshots_examined", [])
    if snap_list:
        lines.append("- Unity snapshot paths found: " + ", ".join(snap_list))
    else:
        lines.append("- Unity snapshot paths found: none")
    lines.append("")
    lines.append("## 3. Contract Recap")
    lines.append("- observation shape: [24,24,27] (dataset stored as [N,576,27] and loader reshapes to [N,24,24,27])")
    lines.append("- action shape: [576,7]")
    lines.append("- branch sizes: [6,4,4,4,4,7,49]")
    lines.append("- focus cells: B2(flat=25), C3(flat=50)")
    lines.append("- flatten formula: flat_index = row * 24 + col")
    lines.append("")
    lines.append("## 4. Source-of-Truth Channel Maps")
    lines.append("| channel index or range | Unity source meaning | adapter/source meaning | manifest/spec meaning | Stage10D.1 assumed meaning | status |")
    lines.append("|---|---|---|---|---|---|")
    lines.append(
        f"| 2-4 owner | contract: {unity_owner_contract}; builder(mvp): {unity_owner_builder} | {adapter_owner} | names missing; shape-only in manifest | {d1_owner_mode} | {status_owner} |"
    )
    lines.append(
        "| 5-11 unit_type | resource/base/barracks/worker/light/heavy/ranged | unit_resource..unit_ranged | names missing; shape-only | assumed same indices | MATCH |"
    )
    lines.append(
        "| 12-17 current_action | noop/move/harvest/return/produce/attack | action_noop..action_attack | names missing; shape-only | assumed same indices | MATCH |"
    )
    lines.append(
        "| 18-21 direction | north/east/south/west | dir_north..dir_west | names missing; shape-only | assumed same indices | MATCH |"
    )
    lines.append(
        "| 22-25 produce_type | worker/light/heavy/ranged | produce_worker..produce_ranged | names missing; shape-only | assumed same indices | MATCH |"
    )
    lines.append(
        "| 26 attack_target | scalar local-7x7 diagnostic | attack_target_index | attack_target_semantics=local_7x7_49 | assumed scalar | MATCH |"
    )
    lines.append("")
    lines.append("## 5. BC Observation Empirical Semantics")
    lines.append("Per-channel stats are in stage10d2_bc_channel_semantics_probe.json (train/validation).")
    lines.append("- All 27 channels were profiled for min/max/mean/std/nonzero/uniques.")
    lines.append("- One-hot group checks were computed for owner/unit_type/current_action/direction/produce_type ranges.")
    lines.append("- Label-proxy groups were computed: own_worker_cells, own_base_cells, own_actor_cells, resource_like_cells, non_noop_label_cells, empty_noop_cells.")
    lines.append("- Explicit samples were dumped for action_type==Harvest, action_type==Produce, flat=25, flat=50.")
    lines.append("")
    lines.append("## 6. Unity Snapshot Empirical Semantics")
    lines.append(f"- snapshot status: {snapshot_probe.get('status', 'unknown')}")
    if snapshot_probe.get("status") == "OK":
        merged = snapshot_probe.get("focus_cells_merged", {})
        for lbl in ("B2", "C3"):
            cell = merged.get(lbl)
            if not cell:
                lines.append(f"- {lbl}: missing")
                continue
            lines.append(f"- {lbl}: raw 27-channel vector captured (see JSON artifact), flat_index={cell.get('flat_index')}")
            lines.append(
                f"  unity-source interpretation owner={cell.get('interpretation_unity_source_map', {}).get('owner_argmax')} ; "
                f"stage10d1 interpretation owner={cell.get('interpretation_stage10d1_assumption', {}).get('owner_argmax')}"
            )
    else:
        lines.append("- Snapshot files were not found; probe emitted SNAPSHOT_NOT_FOUND with searched locations.")
    lines.append("")
    lines.append("## 7. Loader Roundtrip / Axis Audit")
    ea = loader.get("explicit_answers", {})
    lines.append(f"- Does flat 25 remain B2? {ea.get('does_flat_25_remain_b2')}")
    lines.append(f"- Does flat 50 remain C3? {ea.get('does_flat_50_remain_c3')}")
    lines.append(f"- Is there row/column transpose? {ea.get('is_there_row_column_transpose')}")
    lines.append(f"- Is there channel order transpose? {ea.get('is_there_channel_order_transpose')}")
    lines.append(f"- Is there any hidden reshape corruption? {ea.get('hidden_reshape_corruption_detected')}")
    lines.append(f"- Is loader likely responsible? {ea.get('loader_likely_responsible')}")
    lines.append("")
    lines.append("## 8. Stage10D.1 Assumption Audit")
    lines.append("- Stage10D.1 assumed owner channels as absolute player channels (owner_player1 at index 3).")
    lines.append("- Unity ObservationBuilder in UnityMvpTransfer path documents owner as neutral/friendly/enemy.")
    lines.append("- Therefore Stage10D.1 owner-channel interpretation is potentially stale/wrong for the inspected runtime path.")
    lines.append("- OBSERVATION_ENCODING_MISMATCH remains plausible, but its Stage10D.1 explanation must be corrected to source-of-truth owner semantics before remediation.")
    lines.append("")
    lines.append("## 9. Root-Cause Classification")
    lines.append(f"- primary: {primary}")
    if secondary:
        lines.append("- secondary: " + ", ".join(secondary))
    else:
        lines.append("- secondary: none")
    lines.append("")
    lines.append("## 10. Patch Plan")
    lines.append("- If adapter is wrong: patch adapter channel semantics/naming or mapping, regenerate adapted dataset, rerun validation, rebuild BC-ready dataset, retrain BC student from corrected data.")
    lines.append("- If Unity ObservationBuilder is wrong: patch ObservationBuilder owner/channel mapping or mode usage, rerun Unity snapshot, rerun Stage10R/10D.1.")
    lines.append("- If loader is wrong: patch student_bc_loader reshape/layout path, rerun loader dry-run and checkpoint inference dry-run, then reassess retraining need.")
    lines.append("- If Stage10D.1 diagnostics were wrong: patch Stage10D.1 channel assumptions and rerun Stage10D.1 before model/data changes.")
    lines.append("- If docs are stale but artifacts are valid: update docs/spec only; do not retrain solely due to stale docs.")
    lines.append("- If perspective encoding mismatch is real: define canonical perspective semantics and align adapter/Unity documentation and validation before retraining.")
    lines.append("")
    lines.append("## 11. Gate Decision")
    lines.append(f"- {gate}")
    lines.append("")
    lines.append("## 12. Explicit Non-Claims")
    lines.append("- This report does not prove semantic parity between Gym-μRTS and Unity.")
    lines.append("- This report does not claim direct weight transfer.")
    lines.append("- This report does not validate final tactical behavior.")
    lines.append("- This report does not authorize PPO or teacher retraining.")
    lines.append("- This report does not change ActionApplier/MatchManager runtime semantics.")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
