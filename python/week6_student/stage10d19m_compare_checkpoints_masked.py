#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

from stage10d19m_common import load_json, utc_now_iso, write_json


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.19M compare masked probe outputs")
    p.add_argument("--stage10d17-probe", type=Path, required=True)
    p.add_argument("--stage10d19b-probe", type=Path, required=True)
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d19m_checkpoint_mask_comparison.json"),
    )
    return p.parse_args()


def _extract(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "checkpoint": p.get("checkpoint"),
        "b2_c3_preserved": "STAGE10D19M_MASK_PRESERVES_B2_C3_GUARDS" in p.get("labels", []),
        "movement_preserved": "STAGE10D19M_MASK_PRESERVES_MOVEMENT" in p.get("labels", []),
        "masked_valid_move_count": int(p.get("masked_valid_target_moves", 0)),
        "masked_invalid_move_count": int(p.get("masked_occupied_or_invalid_target_moves", 0)),
        "command_build_readiness": float(p.get("masked_estimated_command_build_readiness", 0.0)),
        "masked_off_actor_non_noop": int(p.get("masked_off_actor_non_noop_count", 0)),
        "attack_watch_only": int(p.get("masked_attack_predictions", 0)) == 0,
        "mask_ready_label": "STAGE10D19M_MASK_READY_FOR_UNITY_TOGGLE_PROBE" in p.get("labels", []),
        "production_proxy": p.get("produced_unit_masked_action_distribution", {}),
    }


def main() -> int:
    args = parse_args()
    p17 = load_json(args.stage10d17_probe)
    p19b = load_json(args.stage10d19b_probe)

    m17 = _extract(p17)
    m19 = _extract(p19b)

    selected = "none"
    decision_reason = ""

    if m19["mask_ready_label"] and m19["b2_c3_preserved"] and m19["movement_preserved"]:
        if (
            m19["command_build_readiness"] >= m17["command_build_readiness"]
            and m19["masked_invalid_move_count"] <= m17["masked_invalid_move_count"]
            and m19["masked_off_actor_non_noop"] <= m17["masked_off_actor_non_noop"]
        ):
            selected = "stage10d19b"
            decision_reason = "Stage10D.19B masked probe preserves guards/movement and is not worse on invalid moves, off-actor safety, or readiness."

    if selected == "none" and m17["mask_ready_label"] and m17["b2_c3_preserved"] and m17["movement_preserved"]:
        selected = "stage10d17"
        decision_reason = "Stage10D.17 masked baseline remains the safer ready candidate under current evidence."

    if selected == "none":
        decision_reason = "No checkpoint met masked-ready criteria with guard/movement preservation under current evidence."

    labels = [
        "STAGE10D19M_STAGE10D17_MASKED_BASELINE_EVALUATED",
        "STAGE10D19M_STAGE10D19B_MASKED_EVALUATED",
    ]
    if selected == "stage10d17":
        labels.append("STAGE10D19M_SELECTED_STAGE10D17_FOR_UNITY_MASK_RERUN")
    elif selected == "stage10d19b":
        labels.append("STAGE10D19M_SELECTED_STAGE10D19B_FOR_UNITY_MASK_RERUN")
    else:
        labels.append("STAGE10D19M_NO_CHECKPOINT_READY_FOR_MASK_RERUN")

    out = {
        "stage": "10D.19M",
        "task": "checkpoint_mask_comparison",
        "generated_at_utc": utc_now_iso(),
        "stage10d17": m17,
        "stage10d19b": m19,
        "selected_candidate_for_unity_mask_rerun": selected,
        "decision_reason": decision_reason,
        "labels": labels,
    }

    write_json(args.output_json, out)
    print(Path(args.output_json).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
