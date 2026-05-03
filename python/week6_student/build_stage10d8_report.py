#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


ALLOWED_CLASSIFICATIONS = {
    "SEMANTIC_BC_TRAINING_COMPLETED",
    "SEMANTIC_BC_TRAINING_FAILED",
    "ACTOR_CELL_METRICS_PASSED",
    "ACTOR_CELL_METRICS_FAILED",
    "CHECKPOINT_INFERENCE_DRY_RUN_PASSED",
    "CHECKPOINT_INFERENCE_DRY_RUN_FAILED",
    "UNITY_SNAPSHOT_PROBE_PASSED",
    "UNITY_SNAPSHOT_PROBE_FAILED",
    "UNITY_SNAPSHOT_PROBE_SKIPPED",
    "READY_FOR_UNITY_STAGE10R_RERUN",
    "NOT_READY_FOR_UNITY_STAGE10R_RERUN",
}

ALLOWED_GATES = {
    "GO_FOR_UNITY_STAGE10R_RERUN",
    "GO_FOR_BC_OBJECTIVE_REWEIGHTING_OR_SAMPLING_FIX",
    "GO_FOR_CHECKPOINT_INFERENCE_FIX",
    "GO_FOR_NEXT_DIAGNOSTIC",
    "NO_GO_UNITY_RERUN_UNTIL_TRAINING_VALIDATED",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _to_rel(root: Path, p: Optional[Path]) -> Optional[str]:
    if p is None:
        return None
    try:
        return str(p.resolve().relative_to(root.resolve())).replace("\\", "/")
    except Exception:
        return p.as_posix()


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _latest_stage10d8_run(runs_root: Path) -> Optional[Path]:
    if not runs_root.exists():
        return None
    candidates = sorted(
        [p for p in runs_root.glob("legacy032_v2_semantic_bc_stage10d8_*") if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _decide(
    *,
    training_ok: bool,
    actor_ok: bool,
    ckpt_infer_ok: bool,
    snapshot_status: str,
) -> Dict[str, Any]:
    cls: List[str] = []

    cls.append("SEMANTIC_BC_TRAINING_COMPLETED" if training_ok else "SEMANTIC_BC_TRAINING_FAILED")
    cls.append("ACTOR_CELL_METRICS_PASSED" if actor_ok else "ACTOR_CELL_METRICS_FAILED")
    cls.append("CHECKPOINT_INFERENCE_DRY_RUN_PASSED" if ckpt_infer_ok else "CHECKPOINT_INFERENCE_DRY_RUN_FAILED")

    if snapshot_status == "pass":
        cls.append("UNITY_SNAPSHOT_PROBE_PASSED")
    elif snapshot_status == "fail":
        cls.append("UNITY_SNAPSHOT_PROBE_FAILED")
    else:
        cls.append("UNITY_SNAPSHOT_PROBE_SKIPPED")

    if not training_ok:
        gate = "NO_GO_UNITY_RERUN_UNTIL_TRAINING_VALIDATED"
        cls.append("NOT_READY_FOR_UNITY_STAGE10R_RERUN")
    elif not actor_ok:
        gate = "GO_FOR_BC_OBJECTIVE_REWEIGHTING_OR_SAMPLING_FIX"
        cls.append("NOT_READY_FOR_UNITY_STAGE10R_RERUN")
    elif not ckpt_infer_ok:
        gate = "GO_FOR_CHECKPOINT_INFERENCE_FIX"
        cls.append("NOT_READY_FOR_UNITY_STAGE10R_RERUN")
    else:
        gate = "GO_FOR_UNITY_STAGE10R_RERUN"
        cls.append("READY_FOR_UNITY_STAGE10R_RERUN")

    for c in cls:
        if c not in ALLOWED_CLASSIFICATIONS:
            raise RuntimeError(f"invalid classification: {c}")
    if gate not in ALLOWED_GATES:
        raise RuntimeError(f"invalid gate decision: {gate}")

    return {
        "classifications": cls,
        "gate_decision": gate,
        "unity_stage10r_rerun_authorized": gate == "GO_FOR_UNITY_STAGE10R_RERUN",
    }


def _md(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# LEGACY032 UNITY V2 STAGE10D8 SEMANTIC BC RETRAINING REPORT")
    lines.append("")
    lines.append(f"- generated_at_utc: {report['generated_at_utc']}")
    lines.append(f"- gate_decision: {report['gate_decision']}")
    lines.append("")

    lines.append("## 1. Scope")
    for item in report.get("scope", []):
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## 2. Stage10D.7 Recap")
    recap = report.get("stage10d7_recap", {})
    for k, v in recap.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## 3. Training Configuration")
    cfg = report.get("training_configuration", {})
    for k, v in cfg.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## 4. Training History")
    hist = report.get("training_history", {})
    for k, v in hist.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## 5. Validation Metrics")
    vm = report.get("validation_metrics", {})
    for k, v in vm.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## 6. Actor-cell / Non-NoOp Metrics")
    am = report.get("actor_cell_metrics", {})
    for k, v in am.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## 7. Checkpoint Selection")
    cs = report.get("checkpoint_selection", {})
    for k, v in cs.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## 8. Checkpoint Inference Dry-run")
    ckd = report.get("checkpoint_inference_dry_run", {})
    for k, v in ckd.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## 9. Unity Snapshot Probe")
    usp = report.get("unity_snapshot_probe", {})
    for k, v in usp.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## 10. Remaining Risks")
    for item in report.get("remaining_risks", []):
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## 11. Gate Decision")
    lines.append(f"- gate_decision: {report['gate_decision']}")
    lines.append(f"- unity_stage10r_rerun_authorized: {report['unity_stage10r_rerun_authorized']}")
    lines.append("")

    lines.append("## 12. Explicit Non-Claims")
    for item in report.get("explicit_non_claims", []):
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## Primary Classifications")
    for c in report.get("primary_classifications", []):
        lines.append(f"- {c}")
    lines.append("")

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Stage10D.8 final report")
    p.add_argument("--run-dir", type=Path, default=None)
    p.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("python/week6_student/reports"),
    )
    p.add_argument(
        "--checkpoint-inference-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d8_checkpoint_inference_dry_run.json"),
    )
    p.add_argument(
        "--unity-snapshot-probe-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d8_unity_snapshot_checkpoint_probe.json"),
    )
    p.add_argument(
        "--output-md",
        type=Path,
        default=Path(
            "python/week6_student/reports/"
            "LEGACY032_UNITY_V2_STAGE10D8_SEMANTIC_BC_RETRAINING_REPORT.md"
        ),
    )
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path(
            "python/week6_student/reports/"
            "LEGACY032_UNITY_V2_STAGE10D8_SEMANTIC_BC_RETRAINING_REPORT.json"
        ),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = _repo_root()

    reports_dir = _resolve(root, args.reports_dir).resolve()
    runs_root = (root / "python/week6_student/runs").resolve()

    run_dir = _resolve(root, args.run_dir).resolve() if args.run_dir is not None else _latest_stage10d8_run(runs_root)
    if run_dir is None:
        raise RuntimeError("No Stage10D.8 run directory found")

    output_md = _resolve(root, args.output_md).resolve()
    output_json = _resolve(root, args.output_json).resolve()

    training_cfg = _read_json(run_dir / "training_config.json") or {}
    training_hist = _read_json(run_dir / "training_history.json") or {}
    validation_metrics = _read_json(run_dir / "validation_metrics.json") or {}
    selection = _read_json(run_dir / "checkpoint_selection_report.json") or {}
    stage10d8_training = _read_json(run_dir / "stage10d8_training_report.json") or {}

    checkpoint_dry_run = _read_json(_resolve(root, args.checkpoint_inference_json)) or {}
    snapshot_probe = _read_json(_resolve(root, args.unity_snapshot_probe_json)) or {"status": "skipped"}

    manifest_summary = training_cfg.get("dataset_manifest_summary", {}) if isinstance(training_cfg, dict) else {}
    cfg_raw = (training_cfg.get("config", {}) if isinstance(training_cfg, dict) else {})
    best_val = validation_metrics.get("best_validation_metrics", {}) if isinstance(validation_metrics, dict) else {}
    history_rows = training_hist.get("history", []) if isinstance(training_hist, dict) else []

    training_ok = bool((run_dir / "student_bc_semantic_best.pt").exists() and (run_dir / "student_bc_semantic_last.pt").exists())
    actor_ok = bool(selection.get("actor_metrics_pass", False))
    ckpt_infer_ok = checkpoint_dry_run.get("status") == "pass"
    snapshot_status = str(snapshot_probe.get("status", "skipped"))

    decision = _decide(
        training_ok=training_ok,
        actor_ok=actor_ok,
        ckpt_infer_ok=ckpt_infer_ok,
        snapshot_status=snapshot_status,
    )

    remaining_risks: List[str] = []
    if not training_ok:
        remaining_risks.append("Stage10D.8 training artifacts missing or incomplete.")
    if training_ok and not actor_ok:
        remaining_risks.append("Actor-cell metrics below thresholds; global loss alone is not acceptable.")
    if training_ok and actor_ok and not ckpt_infer_ok:
        remaining_risks.append("Checkpoint inference dry-run failed; investigate checkpoint loading or logits outputs.")
    if snapshot_status == "fail":
        remaining_risks.append("Unity snapshot probe still indicates potential NoOp dominance on focus cells.")
    if snapshot_status == "skipped":
        remaining_risks.append("Unity snapshot probe unavailable; B2/C3 offline checkpoint probe not executed.")
    if not remaining_risks:
        remaining_risks.append(
            "Even with Stage10D.8 pass, Unity runtime behavior is not proven until Stage10R rerun in Unity visual inspection scene."
        )

    actor_cell_metrics = {
        "val_actor_cell_count": best_val.get("val_actor_cell_count"),
        "val_actor_cell_action_type_accuracy": best_val.get("val_actor_cell_action_type_accuracy"),
        "val_actor_cell_non_noop_recall": best_val.get("val_actor_cell_non_noop_recall"),
        "val_actor_cell_noop_pred_share": best_val.get("val_actor_cell_noop_pred_share"),
        "val_worker_harvest_proxy_accuracy": best_val.get("val_worker_harvest_proxy_accuracy"),
        "val_base_produce_proxy_accuracy": best_val.get("val_base_produce_proxy_accuracy"),
        "val_attack_proxy_accuracy": best_val.get("val_attack_proxy_accuracy"),
        "thresholds": selection.get("thresholds", {}),
        "thresholds_pass": selection.get("actor_metrics_pass"),
    }

    report: Dict[str, Any] = {
        "stage": "10D.8",
        "generated_at_utc": _iso_now(),
        "inputs": {
            "run_dir": _to_rel(root, run_dir),
            "training_config": _to_rel(root, run_dir / "training_config.json"),
            "training_history": _to_rel(root, run_dir / "training_history.json"),
            "validation_metrics": _to_rel(root, run_dir / "validation_metrics.json"),
            "checkpoint_selection_report": _to_rel(root, run_dir / "checkpoint_selection_report.json"),
            "stage10d8_training_report": _to_rel(root, run_dir / "stage10d8_training_report.json"),
            "checkpoint_inference_dry_run": _to_rel(root, _resolve(root, args.checkpoint_inference_json)),
            "unity_snapshot_probe": _to_rel(root, _resolve(root, args.unity_snapshot_probe_json)),
        },
        "scope": [
            "Supervised BC retraining only (Stage10D.8).",
            "No PPO run.",
            "No teacher training continuation.",
            "No checkpoint overwrite of previous runs.",
            "No Unity runtime behavior mutation.",
            "No ActionApplier/MatchManager modifications.",
        ],
        "stage10d7_recap": {
            "schema_version": manifest_summary.get("schema_version"),
            "dataset_kind": manifest_summary.get("dataset_kind"),
            "source_stage": manifest_summary.get("source_stage"),
            "source_adapted_dataset_stage": manifest_summary.get("source_adapted_dataset_stage"),
            "mapping_spec_version": manifest_summary.get("mapping_spec_version"),
            "observation_semantics_version": manifest_summary.get("observation_semantics_version"),
            "observation_shape": manifest_summary.get("observation_shape"),
            "action_shape": manifest_summary.get("action_shape"),
            "branch_sizes": manifest_summary.get("branch_sizes"),
            "num_train": manifest_summary.get("num_train"),
            "num_validation": manifest_summary.get("num_validation"),
            "num_debug": manifest_summary.get("num_debug"),
        },
        "training_configuration": {
            "bc_ready_dir": cfg_raw.get("bc_ready_dir"),
            "run_dir": cfg_raw.get("run_dir"),
            "epochs": cfg_raw.get("epochs"),
            "batch_size": cfg_raw.get("batch_size"),
            "learning_rate": cfg_raw.get("learning_rate"),
            "device": cfg_raw.get("device"),
            "seed": cfg_raw.get("seed"),
            "gradient_clip_norm": cfg_raw.get("gradient_clip_norm"),
            "actor_cell_loss_weight": cfg_raw.get("actor_cell_loss_weight"),
            "actor_weighting_used": stage10d8_training.get("actor_weighting", {}).get("used"),
            "comparable_with_previous_stage7": stage10d8_training.get("actor_weighting", {}).get("comparable_with_stage7"),
        },
        "training_history": {
            "epochs_completed": len(history_rows) if isinstance(history_rows, list) else 0,
            "best_epoch": validation_metrics.get("best_epoch"),
            "last_epoch": history_rows[-1].get("epoch") if isinstance(history_rows, list) and history_rows else None,
        },
        "validation_metrics": {
            "best_val_total_loss": best_val.get("val_total_loss"),
            "best_val_action_type_loss": best_val.get("val_action_type_loss"),
            "best_val_action_type_accuracy_all_cells": best_val.get("val_action_type_accuracy_all_cells"),
            "best_val_noop_share_pred_all_cells": best_val.get("val_noop_share_pred_all_cells"),
            "best_val_noop_share_target_all_cells": best_val.get("val_noop_share_target_all_cells"),
        },
        "actor_cell_metrics": actor_cell_metrics,
        "checkpoint_selection": {
            "selected_epoch": selection.get("selected_epoch"),
            "selection_rule": selection.get("selection_rule"),
            "composite_score": selection.get("composite_score"),
            "actor_metrics_pass": selection.get("actor_metrics_pass"),
            "best_checkpoint_path": _to_rel(root, run_dir / "student_bc_semantic_best.pt"),
            "last_checkpoint_path": _to_rel(root, run_dir / "student_bc_semantic_last.pt"),
        },
        "checkpoint_inference_dry_run": {
            "status": checkpoint_dry_run.get("status", "missing"),
            "hard_failures_count": len(checkpoint_dry_run.get("hard_failures", []) or []),
            "details": checkpoint_dry_run.get("details", {}),
        },
        "unity_snapshot_probe": {
            "status": snapshot_status,
            "hard_failures_count": len(snapshot_probe.get("hard_failures", []) or []),
            "details": snapshot_probe.get("details", {}),
        },
        "remaining_risks": remaining_risks,
        "primary_classifications": decision["classifications"],
        "gate_decision": decision["gate_decision"],
        "unity_stage10r_rerun_authorized": decision["unity_stage10r_rerun_authorized"],
        "explicit_non_claims": [
            "No Unity runtime behavior changes were made in Stage10D.8.",
            "No ActionApplier or MatchManager changes were made in Stage10D.8.",
            "No forced non-NoOp fallback was introduced.",
            "No semantic parity claim between Gym-microRTS and Unity is made.",
            "Policy-level Unity success is not claimed until Stage10R/Stage10V rerun passes.",
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
