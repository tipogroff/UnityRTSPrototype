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
    attack_index_to_offset,
    flat_to_xy,
    in_bounds,
    move_target,
    read_jsonl,
    step_from_filename,
    utc_now_iso,
    write_json,
    xy_to_flat,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.19M validate legal mask semantics")
    p.add_argument("--mask-build-json", action="append", required=True, help="Mask build report(s)")
    p.add_argument("--cell-table-jsonl", action="append", required=True, help="Cell table(s) used for validation")
    p.add_argument(
        "--output-json",
        type=Path,
        default=Path("python/week6_student/reports/stage10d19m_mask_semantics_validation.json"),
    )
    return p.parse_args()


def _arr2(x: Any) -> np.ndarray:
    return np.asarray(x, dtype=bool)


def main() -> int:
    args = parse_args()

    table_by_step: Dict[int, Path] = {step_from_filename(p): Path(p) for p in args.cell_table_jsonl}

    total_cells = 0
    off_actor_violations = 0
    move_mask_violations = 0
    harvest_mask_violations = 0
    produce_mask_violations = 0
    attack_mask_violations = 0
    branch_mask_violations = 0
    approximation_count = 0

    step_summaries: Dict[str, Any] = {}

    for mask_path in args.mask_build_json:
        m = Path(mask_path)
        step = step_from_filename(m)
        payload = __import__("json").loads(m.read_text(encoding="utf-8"))

        action = _arr2(payload["action_type_mask"])
        move = _arr2(payload["move_dir_mask"])
        harvest = _arr2(payload["harvest_dir_mask"])
        ret = _arr2(payload["return_dir_mask"])
        produce_dir = _arr2(payload["produce_dir_mask"])
        produce_type = _arr2(payload["produce_unit_type_mask"])
        attack = _arr2(payload["attack_target_local_mask"])

        rows = read_jsonl(table_by_step[step])
        by_cell = {int(r.get("cell_index", -1)): r for r in rows if int(r.get("cell_index", -1)) >= 0}

        local = {
            "off_actor_violations": 0,
            "move_mask_violations": 0,
            "harvest_mask_violations": 0,
            "produce_mask_violations": 0,
            "attack_mask_violations": 0,
            "branch_mask_violations": 0,
            "total_cells_checked": N_CELLS,
        }

        for flat in range(N_CELLS):
            total_cells += 1
            row = by_cell.get(flat)
            is_actor = bool(row.get("runtime_is_friendly_actor", False)) if row is not None else False
            unit = str(row.get("decoded_observation_unit_type") or "") if row is not None else ""

            if not is_actor:
                if bool(np.any(action[flat, 1:])):
                    off_actor_violations += 1
                    local["off_actor_violations"] += 1

            # Move checks.
            if action[flat, ACTION_TYPE_MOVE]:
                if not bool(np.any(move[flat])):
                    move_mask_violations += 1
                    local["move_mask_violations"] += 1
            for d, legal in enumerate(move[flat]):
                if not legal:
                    continue
                tgt, ok = move_target(flat, d)
                if (not ok) or tgt is None:
                    move_mask_violations += 1
                    local["move_mask_violations"] += 1
                    continue
                trow = by_cell.get(tgt)
                if trow is None:
                    move_mask_violations += 1
                    local["move_mask_violations"] += 1
                else:
                    if not bool(trow.get("runtime_is_empty", False)):
                        move_mask_violations += 1
                        local["move_mask_violations"] += 1

            # Harvest checks.
            if np.any(harvest[flat]):
                if unit != "Worker":
                    harvest_mask_violations += 1
                    local["harvest_mask_violations"] += 1
                x, y = flat_to_xy(flat)
                for d, legal in enumerate(harvest[flat]):
                    if not legal:
                        continue
                    dx, dy = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}[d]
                    nx, ny = x + dx, y + dy
                    if not in_bounds(nx, ny):
                        harvest_mask_violations += 1
                        local["harvest_mask_violations"] += 1
                        continue
                    nrow = by_cell.get(xy_to_flat(nx, ny))
                    if nrow is None or not bool(nrow.get("runtime_is_resource", False)):
                        harvest_mask_violations += 1
                        local["harvest_mask_violations"] += 1

            # Produce checks.
            if action[flat, ACTION_TYPE_PRODUCE]:
                if unit not in {"Base", "Barracks"}:
                    produce_mask_violations += 1
                    local["produce_mask_violations"] += 1
                if not np.any(produce_dir[flat]) or not np.any(produce_type[flat]):
                    produce_mask_violations += 1
                    local["produce_mask_violations"] += 1
            if np.any(produce_dir[flat]):
                x, y = flat_to_xy(flat)
                for d, legal in enumerate(produce_dir[flat]):
                    if not legal:
                        continue
                    dx, dy = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}[d]
                    nx, ny = x + dx, y + dy
                    if not in_bounds(nx, ny):
                        produce_mask_violations += 1
                        local["produce_mask_violations"] += 1
                        continue
                    nrow = by_cell.get(xy_to_flat(nx, ny))
                    if nrow is None or not bool(nrow.get("runtime_is_empty", False)):
                        produce_mask_violations += 1
                        local["produce_mask_violations"] += 1

            # Attack checks.
            if action[flat, ACTION_TYPE_ATTACK]:
                if unit not in {"Worker", "Light", "Heavy", "Ranged"}:
                    attack_mask_violations += 1
                    local["attack_mask_violations"] += 1
                if not np.any(attack[flat]):
                    attack_mask_violations += 1
                    local["attack_mask_violations"] += 1
            for idx, legal in enumerate(attack[flat]):
                if not legal:
                    continue
                dx, dy = attack_index_to_offset(idx)
                x, y = flat_to_xy(flat)
                tx, ty = x + dx, y + dy
                if not in_bounds(tx, ty):
                    attack_mask_violations += 1
                    local["attack_mask_violations"] += 1
                    continue
                trow = by_cell.get(xy_to_flat(tx, ty))
                if trow is None or not bool(trow.get("runtime_is_enemy", False)):
                    attack_mask_violations += 1
                    local["attack_mask_violations"] += 1

            # Branch non-empty only when corresponding action is legal.
            if np.any(move[flat]) and not action[flat, ACTION_TYPE_MOVE]:
                branch_mask_violations += 1
                local["branch_mask_violations"] += 1
            if np.any(harvest[flat]) and not action[flat, ACTION_TYPE_HARVEST]:
                branch_mask_violations += 1
                local["branch_mask_violations"] += 1
            if np.any(ret[flat]) and not action[flat, ACTION_TYPE_RETURN]:
                branch_mask_violations += 1
                local["branch_mask_violations"] += 1
            if np.any(produce_dir[flat]) and not action[flat, ACTION_TYPE_PRODUCE]:
                branch_mask_violations += 1
                local["branch_mask_violations"] += 1
            if np.any(produce_type[flat]) and not action[flat, ACTION_TYPE_PRODUCE]:
                branch_mask_violations += 1
                local["branch_mask_violations"] += 1
            if np.any(attack[flat]) and not action[flat, ACTION_TYPE_ATTACK]:
                branch_mask_violations += 1
                local["branch_mask_violations"] += 1

        approximation_count += len(payload.get("approximation_notes", []))
        step_summaries[str(step)] = local

    valid = all(v == 0 for v in [
        off_actor_violations,
        move_mask_violations,
        harvest_mask_violations,
        produce_mask_violations,
        attack_mask_violations,
        branch_mask_violations,
    ])

    labels = [
        "STAGE10D19M_MASK_SEMANTICS_VALID" if valid else "STAGE10D19M_MASK_SEMANTICS_INVALID",
        "STAGE10D19M_MASK_OFF_ACTOR_SAFE" if off_actor_violations == 0 else "STAGE10D19M_MASK_SEMANTICS_INVALID",
        "STAGE10D19M_MASK_MOVE_TARGETS_SAFE" if move_mask_violations == 0 else "STAGE10D19M_MASK_SEMANTICS_INVALID",
        "STAGE10D19M_MASK_ATTACK_TARGETS_SAFE" if attack_mask_violations == 0 else "STAGE10D19M_MASK_SEMANTICS_INVALID",
    ]

    out = {
        "stage": "10D.19M",
        "task": "validate_mask_semantics",
        "generated_at_utc": utc_now_iso(),
        "total_cells_checked": int(total_cells),
        "off_actor_violations": int(off_actor_violations),
        "move_mask_violations": int(move_mask_violations),
        "harvest_mask_violations": int(harvest_mask_violations),
        "produce_mask_violations": int(produce_mask_violations),
        "attack_mask_violations": int(attack_mask_violations),
        "branch_mask_violations": int(branch_mask_violations),
        "approximation_count": int(approximation_count),
        "per_step": step_summaries,
        "labels": labels,
        "gate": "GO_FOR_STAGE10D19M_MASKED_SELECTION_PROBE" if valid else "GO_FOR_STAGE10D19M_MASK_BUILDER_FIX",
        "runtime_authority_note": "Mask modifies selection legality only; ActionDecoder/ActionApplier/MatchManager remain authoritative.",
    }
    write_json(args.output_json, out)
    print(Path(args.output_json).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
