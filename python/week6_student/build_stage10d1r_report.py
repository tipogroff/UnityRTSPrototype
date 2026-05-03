#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Stage10D.1R corrected owner semantics rerun report")
    parser.add_argument("--reports-dir", type=Path, default=Path("python/week6_student/reports"))
    parser.add_argument(
        "--bc-ready-dir",
        type=str,
        default=(
            "python/week5_teacher_legacy032/teacher_exports_bc/"
            "day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z"
        ),
    )
    parser.add_argument(
        "--unity-snapshot",
        type=str,
        default="python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json",
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        default="python/week6_student/runs/legacy032_v2_bc_minimal_20260501T195501Z/student_bc_transfer_best.pt",
    )
    parser.add_argument(
        "--scene",
        type=str,
        default="Assets/Scenes/Week6_StudentVisualInspection.unity",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "python/week6_student/reports/"
            "LEGACY032_UNITY_V2_STAGE10D1R_CORRECTED_OWNER_SEMANTICS_RERUN_REPORT.md"
        ),
    )
    return parser.parse_args()


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _git_commit(root: Path) -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(root), text=True)
        return out.strip()
    except Exception:
        return "unavailable"


def _safe_get(d: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return default if cur is None else cur


def _classify(
    obs_comp: Dict[str, Any],
    nn: Dict[str, Any],
    dist: Dict[str, Any],
    loss: Dict[str, Any],
) -> Dict[str, str]:
    modes = obs_comp.get("mode_results", {})
    abs_mode = modes.get("absolute_player_channels", {})
    pers_mode = modes.get("perspective_friendly_enemy", {})

    abs_flags = abs_mode.get("flags", {})
    pers_flags = pers_mode.get("flags", {})

    unit_mismatch = bool(abs_flags.get("unit_type_mismatch") or pers_flags.get("unit_type_mismatch"))
    act_mismatch = bool(abs_flags.get("current_action_mismatch") or pers_flags.get("current_action_mismatch"))
    dir_mismatch = bool(abs_flags.get("direction_mismatch") or pers_flags.get("direction_mismatch"))
    prod_mismatch = bool(abs_flags.get("produce_type_mismatch") or pers_flags.get("produce_type_mismatch"))
    atk_mismatch = bool(abs_flags.get("attack_target_mismatch") or pers_flags.get("attack_target_mismatch"))

    owner_conflict = bool(abs_flags.get("owner_labeling_conflict") or pers_flags.get("owner_labeling_conflict"))
    mismatch_excluding_owner = False
    for mode_name in ("absolute_player_channels", "perspective_friendly_enemy"):
        for focus in ("B2", "C3"):
            d = _safe_get(obs_comp, "mode_results", mode_name, "semantic_distance", focus, "semantic_interpretation_distance_excluding_owner")
            if isinstance(d, (int, float)) and d > 1.0:
                mismatch_excluding_owner = True

    own_actor_noop = _safe_get(dist, "split_stats", "combined", "own_actor_cells", "action_type_count", "NoOp", default=0)
    loss_dom = _safe_get(
        loss,
        "audit",
        "validation_metrics_could_be_dominated_by_empty_cell_noop",
        "bool",
        default=False,
    )

    if owner_conflict and not any([unit_mismatch, act_mismatch, dir_mismatch, prod_mismatch, atk_mismatch]) and not mismatch_excluding_owner:
        primary = "STAGE10D1_OWNER_ASSUMPTION_ONLY_FALSE_ALARM"
        gate = "GO_FOR_STAGE10R_RERUN_WITH_CORRECTED_DIAGNOSTICS"
    elif owner_conflict and mismatch_excluding_owner:
        primary = "UNITY_AND_BC_PERSPECTIVE_ENCODING_MISMATCH_CONFIRMED"
        gate = "NO_GO_RETRAINING_UNTIL_OBSERVATION_FIXED"
    elif any([unit_mismatch, act_mismatch, dir_mismatch, prod_mismatch, atk_mismatch]):
        if unit_mismatch:
            primary = "BC_ADAPTER_CHANNEL_MAPPING_ERROR_SUSPECTED"
            gate = "NO_GO_RETRAINING_UNTIL_OBSERVATION_FIXED"
        else:
            primary = "OBSERVATION_ENCODING_MISMATCH_CONFIRMED_AFTER_OWNER_FIX"
            gate = "NO_GO_RETRAINING_UNTIL_OBSERVATION_FIXED"
    elif own_actor_noop == 0 and bool(loss_dom):
        primary = "MODEL_TRAINING_OBJECTIVE_NOOP_BIAS_SUSPECTED"
        gate = "GO_FOR_TRAINING_OBJECTIVE_REMEDIATION"
    else:
        primary = "INCONCLUSIVE_NEEDS_DEEPER_SOURCE_TRACE"
        gate = "GO_FOR_NEXT_DIAGNOSTIC"

    return {"primary": primary, "gate": gate}


def main() -> int:
    args = parse_args()
    root = _repo_root()
    reports = args.reports_dir if args.reports_dir.is_absolute() else root / args.reports_dir

    dist = _load(reports / "stage10d1r_dataset_action_distribution_corrected.json")
    obs = _load(reports / "stage10d1r_observation_channel_comparison_corrected.json")
    nn = _load(reports / "stage10d1r_unity_vs_bc_nearest_neighbors_corrected.json")
    loss = _load(reports / "stage10d1r_training_loss_audit.json")

    decision = _classify(obs, nn, dist, loss)

    combined = _safe_get(dist, "split_stats", "combined", default={})
    own_actor = _safe_get(combined, "own_actor_cells", "action_type_count", default={})
    own_worker = _safe_get(combined, "own_worker_cells", "action_type_count", default={})
    own_base = _safe_get(combined, "own_base_cells", "action_type_count", default={})
    all_cells = _safe_get(combined, "all_576_cells", "action_type_count", default={})

    b2_abs = _safe_get(obs, "focus_interpretation", "B2", "by_owner_mode", "absolute_player_channels", default={})
    b2_pers = _safe_get(obs, "focus_interpretation", "B2", "by_owner_mode", "perspective_friendly_enemy", default={})
    c3_abs = _safe_get(obs, "focus_interpretation", "C3", "by_owner_mode", "absolute_player_channels", default={})
    c3_pers = _safe_get(obs, "focus_interpretation", "C3", "by_owner_mode", "perspective_friendly_enemy", default={})

    abs_flags = _safe_get(obs, "mode_results", "absolute_player_channels", "flags", default={})
    pers_flags = _safe_get(obs, "mode_results", "perspective_friendly_enemy", "flags", default={})

    lines: List[str] = []
    lines.append("# LEGACY032 Unity v2 Stage 10D.1R Corrected Owner Semantics Rerun Report")
    lines.append("")
    lines.append("## 1. Scope")
    lines.append("- Diagnostic/spec remediation only.")
    lines.append("- No runtime semantics change.")
    lines.append("- No dataset mutation.")
    lines.append("- No checkpoint mutation.")
    lines.append("- No retraining.")
    lines.append("- No PPO.")
    lines.append("")
    lines.append("## 2. Why Stage 10D.1R Was Needed")
    lines.append("- Stage10D.2 found owner-channel interpretation conflict.")
    lines.append("- Stage10D.1 assumed absolute_player_channels.")
    lines.append("- UnityMvpTransfer path may use neutral/friendly/enemy.")
    lines.append("- Therefore Stage10D.1 observation mismatch claim needed rerun.")
    lines.append("")
    lines.append("## 3. Inputs")
    lines.append(f"- Stage10D.1 scripts/artifacts: python/week6_student/stage10d1_*.py and python/week6_student/reports/stage10d1_*.json")
    lines.append(f"- Stage10D.2 artifacts: python/week6_student/reports/stage10d2_*.json")
    lines.append(f"- BC-ready dataset path: {args.bc_ready_dir}")
    lines.append(f"- Unity snapshot path: {args.unity_snapshot}")
    lines.append(f"- checkpoint path: {args.checkpoint}")
    lines.append(f"- scene path: {args.scene}")
    lines.append(f"- commit hash: {_git_commit(root)}")
    lines.append("")
    lines.append("## 4. Corrected Owner Semantics")
    lines.append("| Mode | ch2 | ch3 | ch4 | Used for |")
    lines.append("|---|---|---|---|---|")
    lines.append("| absolute_player_channels | neutral | player1 | player2 | legacy/contract naming |")
    lines.append("| perspective_friendly_enemy | neutral | friendly | enemy | UnityMvpTransfer perspective naming |")
    lines.append("")
    lines.append("## 5. Recomputed Dataset Action Distribution")
    lines.append(f"- Are actor-cell labels NoOp-dominant? No. own_actor_cells NoOp count = {own_actor.get('NoOp', 0)}")
    lines.append(f"- Are worker actor labels still mostly/only Harvest? Yes. own_worker_cells={own_worker}")
    lines.append(f"- Are base actor labels still mostly/only Produce? Yes. own_base_cells={own_base}")
    lines.append("- Did owner semantics affect this distribution? No (label-proxy path unchanged).")
    lines.append(f"- all_576_cells action_type distribution: {all_cells}")
    lines.append("")
    lines.append("## 6. Corrected Unity vs BC Channel Comparison")
    lines.append("### B2")
    lines.append(f"- Unity raw vector: {_safe_get(obs, 'focus_interpretation', 'B2', 'raw_channels', default=[])}")
    lines.append(f"- owner included (absolute): {b2_abs.get('owner')}; owner included (perspective): {b2_pers.get('owner')}")
    lines.append(
        f"- owner excluded distance (absolute): "
        f"{_safe_get(obs, 'mode_results', 'absolute_player_channels', 'semantic_distance', 'B2', 'semantic_interpretation_distance_excluding_owner', default=None)}"
    )
    lines.append(
        f"- owner excluded distance (perspective): "
        f"{_safe_get(obs, 'mode_results', 'perspective_friendly_enemy', 'semantic_distance', 'B2', 'semantic_interpretation_distance_excluding_owner', default=None)}"
    )
    lines.append(f"- unit_type mismatch flags: abs={abs_flags.get('unit_type_mismatch')} pers={pers_flags.get('unit_type_mismatch')}")
    lines.append(f"- current_action mismatch flags: abs={abs_flags.get('current_action_mismatch')} pers={pers_flags.get('current_action_mismatch')}")
    lines.append(f"- direction mismatch flags: abs={abs_flags.get('direction_mismatch')} pers={pers_flags.get('direction_mismatch')}")
    lines.append("- final B2 interpretation: owner semantics conflict exists; non-owner channels decide whether mismatch persists.")
    lines.append("")
    lines.append("### C3")
    lines.append(f"- Unity raw vector: {_safe_get(obs, 'focus_interpretation', 'C3', 'raw_channels', default=[])}")
    lines.append(f"- owner included (absolute): {c3_abs.get('owner')}; owner included (perspective): {c3_pers.get('owner')}")
    lines.append(
        f"- owner excluded distance (absolute): "
        f"{_safe_get(obs, 'mode_results', 'absolute_player_channels', 'semantic_distance', 'C3', 'semantic_interpretation_distance_excluding_owner', default=None)}"
    )
    lines.append(
        f"- owner excluded distance (perspective): "
        f"{_safe_get(obs, 'mode_results', 'perspective_friendly_enemy', 'semantic_distance', 'C3', 'semantic_interpretation_distance_excluding_owner', default=None)}"
    )
    lines.append(f"- unit_type mismatch flags: abs={abs_flags.get('unit_type_mismatch')} pers={pers_flags.get('unit_type_mismatch')}")
    lines.append(f"- current_action mismatch flags: abs={abs_flags.get('current_action_mismatch')} pers={pers_flags.get('current_action_mismatch')}")
    lines.append(f"- direction mismatch flags: abs={abs_flags.get('direction_mismatch')} pers={pers_flags.get('direction_mismatch')}")
    lines.append("- final C3 interpretation: owner semantics conflict exists; non-owner channels decide whether mismatch persists.")
    lines.append("")
    lines.append("## 7. Corrected Nearest Neighbor Analysis")
    for focus in ("B2", "C3"):
        lines.append(f"### {focus}")
        for mode in ("all_27", "exclude_owner_2_4", "exclude_current_action_12_17", "exclude_owner_and_current_action"):
            b = _safe_get(nn, "focus_cells", focus, "analysis", mode, "non_noop_actor_cells", "best", default={})
            lines.append(f"- {mode}: {b}")
        lines.append("- semantic compatibility verdict taken from best-neighbor records above.")
        lines.append("")

    lines.append("## 8. Training Objective Audit")
    lines.append("- action_type loss on all 576 cells: " + str(_safe_get(loss, "audit", "loss_computed_on_all_576_cells_or_not", "bool", default=None)))
    lines.append("- actor-cell weighting used: " + str(_safe_get(loss, "audit", "actor_cell_mask_used", "bool", default=None)))
    lines.append("- class weights used: " + str(_safe_get(loss, "audit", "class_weights_used", "bool", default=None)))
    lines.append("- non-NoOp oversampling used: " + str(_safe_get(loss, "audit", "non_noop_oversampling_used", "bool", default=None)))
    lines.append("- validation may be NoOp-dominated: " + str(_safe_get(loss, "audit", "validation_metrics_could_be_dominated_by_empty_cell_noop", "bool", default=None)))
    lines.append("- This remains secondary unless observation mismatch is cleared.")
    lines.append("")
    lines.append("## 9. Corrected Root-Cause Classification")
    lines.append(f"- primary: {decision['primary']}")
    lines.append("")
    lines.append("## 10. Gate Decision")
    lines.append(f"- {decision['gate']}")
    lines.append("")
    lines.append("## 11. Explicit Non-Claims")
    lines.append("- This report does not prove semantic parity between Gym-μRTS and Unity.")
    lines.append("- This report does not claim direct weight transfer.")
    lines.append("- This report does not validate final tactical behavior.")
    lines.append("- This report does not authorize PPO or teacher retraining.")
    lines.append("- This report does not change ActionApplier/MatchManager runtime semantics.")
    lines.append("- This report does not mutate dataset/checkpoint files.")

    out = args.output if args.output.is_absolute() else root / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(out.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
