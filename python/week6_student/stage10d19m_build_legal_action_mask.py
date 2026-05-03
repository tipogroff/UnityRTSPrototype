#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from stage10d19m_common import (
    ACTION_TYPE_ATTACK,
    ACTION_TYPE_HARVEST,
    ACTION_TYPE_MOVE,
    ACTION_TYPE_PRODUCE,
    ACTION_TYPE_RETURN,
    N_CELLS,
    StepMaskBundle,
    build_step_mask_from_cell_rows,
    read_jsonl,
    step_from_filename,
    utc_now_iso,
    validate_mask_sanity,
    write_json,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.19M build legal action masks from Stage10D.18RR runtime cell tables")
    p.add_argument("--snapshot-json", action="append", default=[], help="Optional snapshot json path(s); used for provenance and availability checks")
    p.add_argument("--cell-table-jsonl", action="append", required=True, help="Cell table jsonl path(s) for mask construction")
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path("python/week6_student/reports"),
        help="Output directory or json path for per-step reports",
    )
    p.add_argument("--output-npz", type=Path, default=None, help="Optional consolidated NPZ with built masks")
    return p.parse_args()


def _output_path(base: Path, step: int) -> Path:
    if base.suffix.lower() == ".json":
        return base.with_name(f"{base.stem}_step{step:04d}.json")
    return base / f"stage10d19m_mask_build_step{step:04d}.json"


def _step_stats(bundle: StepMaskBundle, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_cell = {int(r.get("cell_index", -1)): r for r in rows if int(r.get("cell_index", -1)) >= 0}

    friendly_actor_count = 0
    off_actor_count = 0
    movable_actor_count = 0
    for flat in range(N_CELLS):
        row = by_cell.get(flat)
        is_actor = bool(row.get("runtime_is_friendly_actor", False)) if row is not None else False
        if is_actor:
            friendly_actor_count += 1
            unit = str(row.get("decoded_observation_unit_type") or "")
            if unit in {"Worker", "Light", "Heavy", "Ranged"}:
                movable_actor_count += 1
        else:
            off_actor_count += 1

    legal_move_dist = {
        "north": int(np.sum(bundle.move_dir_mask[:, 0])),
        "east": int(np.sum(bundle.move_dir_mask[:, 1])),
        "south": int(np.sum(bundle.move_dir_mask[:, 2])),
        "west": int(np.sum(bundle.move_dir_mask[:, 3])),
    }

    return {
        "friendly_actor_count": int(friendly_actor_count),
        "off_actor_count": int(off_actor_count),
        "movable_actor_count": int(movable_actor_count),
        "cells_with_legal_move": int(np.sum(bundle.action_type_mask[:, ACTION_TYPE_MOVE])),
        "cells_with_legal_harvest": int(np.sum(bundle.action_type_mask[:, ACTION_TYPE_HARVEST])),
        "cells_with_legal_return": int(np.sum(bundle.action_type_mask[:, ACTION_TYPE_RETURN])),
        "cells_with_legal_produce": int(np.sum(bundle.action_type_mask[:, ACTION_TYPE_PRODUCE])),
        "cells_with_legal_attack": int(np.sum(bundle.action_type_mask[:, ACTION_TYPE_ATTACK])),
        "legal_move_direction_distribution": legal_move_dist,
        "legal_attack_target_count": int(np.sum(bundle.attack_target_local_mask)),
    }


def _bundle_to_payload(bundle: StepMaskBundle) -> Dict[str, Any]:
    return {
        "action_type_mask": bundle.action_type_mask.astype(np.int8).tolist(),
        "move_dir_mask": bundle.move_dir_mask.astype(np.int8).tolist(),
        "harvest_dir_mask": bundle.harvest_dir_mask.astype(np.int8).tolist(),
        "return_dir_mask": bundle.return_dir_mask.astype(np.int8).tolist(),
        "produce_dir_mask": bundle.produce_dir_mask.astype(np.int8).tolist(),
        "produce_unit_type_mask": bundle.produce_unit_type_mask.astype(np.int8).tolist(),
        "attack_target_local_mask": bundle.attack_target_local_mask.astype(np.int8).tolist(),
    }


def main() -> int:
    args = parse_args()

    snapshots_by_step: Dict[int, Path] = {}
    for p in args.snapshot_json:
        pp = Path(p)
        snapshots_by_step[step_from_filename(pp)] = pp

    reports: List[Path] = []
    npz_payload: Dict[str, np.ndarray] = {}

    for p in args.cell_table_jsonl:
        cell_path = Path(p)
        step = step_from_filename(cell_path)
        rows = read_jsonl(cell_path)
        bundle = build_step_mask_from_cell_rows(rows)
        if bundle.step == 0:
            bundle = StepMaskBundle(
                step=step,
                action_type_mask=bundle.action_type_mask,
                move_dir_mask=bundle.move_dir_mask,
                harvest_dir_mask=bundle.harvest_dir_mask,
                return_dir_mask=bundle.return_dir_mask,
                produce_dir_mask=bundle.produce_dir_mask,
                produce_unit_type_mask=bundle.produce_unit_type_mask,
                attack_target_local_mask=bundle.attack_target_local_mask,
                approximation_notes=bundle.approximation_notes,
            )

        sanity = validate_mask_sanity(bundle, rows)
        stats = _step_stats(bundle, rows)

        insufficient = False
        missing_fields = []
        probe_fields = [
            "runtime_is_friendly_actor",
            "runtime_is_enemy",
            "runtime_is_resource",
            "runtime_is_empty",
            "decoded_observation_unit_type",
        ]
        if rows:
            for k in probe_fields:
                if k not in rows[0]:
                    missing_fields.append(k)
        if missing_fields:
            insufficient = True

        labels = [
            "STAGE10D19M_MASK_BUILDER_COMPLETED",
            "STAGE10D19M_MASK_SHAPES_VALID" if sanity["violations"]["shape"] == 0 else "STAGE10D19M_INSUFFICIENT_RUNTIME_STATE_FOR_FULL_MASK",
            "STAGE10D19M_OFF_ACTOR_MASK_VALID" if sanity["violations"]["off_actor_only_noop"] == 0 else "STAGE10D19M_INSUFFICIENT_RUNTIME_STATE_FOR_FULL_MASK",
            "STAGE10D19M_MOVE_MASK_VALID" if (sanity["violations"]["move_rule"] + sanity["violations"]["move_dir_rule"]) == 0 else "STAGE10D19M_INSUFFICIENT_RUNTIME_STATE_FOR_FULL_MASK",
            "STAGE10D19M_ATTACK_MASK_VALID" if sanity["violations"]["attack_rule"] == 0 else "STAGE10D19M_INSUFFICIENT_RUNTIME_STATE_FOR_FULL_MASK",
            "STAGE10D19M_MASK_APPROXIMATION_USED",
        ]
        if insufficient:
            labels.append("STAGE10D19M_INSUFFICIENT_RUNTIME_STATE_FOR_FULL_MASK")

        payload = {
            "stage": "10D.19M",
            "task": "build_legal_action_mask",
            "generated_at_utc": utc_now_iso(),
            "step": int(bundle.step),
            "snapshot_json": str(snapshots_by_step.get(step, "")),
            "cell_table_jsonl": str(cell_path.as_posix()),
            "mask_shapes": {
                "action_type_mask": [576, 6],
                "move_dir_mask": [576, 4],
                "harvest_dir_mask": [576, 4],
                "return_dir_mask": [576, 4],
                "produce_dir_mask": [576, 4],
                "produce_unit_type_mask": [576, 7],
                "attack_target_local_mask": [576, 49],
            },
            **stats,
            "approximation_notes": bundle.approximation_notes,
            "missing_required_fields": missing_fields,
            "sanity": sanity,
            "labels": labels,
            **_bundle_to_payload(bundle),
        }

        out_path = _output_path(Path(args.output_json), int(bundle.step))
        write_json(out_path, payload)
        reports.append(out_path)

        # Optional consolidated npz.
        key = f"step{int(bundle.step):04d}"
        npz_payload[f"{key}_action_type_mask"] = bundle.action_type_mask.astype(np.int8)
        npz_payload[f"{key}_move_dir_mask"] = bundle.move_dir_mask.astype(np.int8)
        npz_payload[f"{key}_harvest_dir_mask"] = bundle.harvest_dir_mask.astype(np.int8)
        npz_payload[f"{key}_return_dir_mask"] = bundle.return_dir_mask.astype(np.int8)
        npz_payload[f"{key}_produce_dir_mask"] = bundle.produce_dir_mask.astype(np.int8)
        npz_payload[f"{key}_produce_unit_type_mask"] = bundle.produce_unit_type_mask.astype(np.int8)
        npz_payload[f"{key}_attack_target_local_mask"] = bundle.attack_target_local_mask.astype(np.int8)

    if args.output_npz is not None:
        out_npz = Path(args.output_npz)
        out_npz.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(out_npz, **npz_payload)

    print("\n".join(p.as_posix() for p in reports))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
