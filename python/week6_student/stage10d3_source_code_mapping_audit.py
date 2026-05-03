#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List


FILES_TO_AUDIT = [
    "Assets/Scripts/ML/ObservationContract.cs",
    "Assets/Scripts/ML/ObservationBuilder.cs",
    "python/week5_teacher_legacy032/scripts/export_teacher_rollout_legacy032.py",
    "python/week5_teacher_legacy032/scripts/adapt_legacy032_to_unity_v2.py",
    "python/week5_teacher_legacy032/scripts/build_bc_ready_dataset_legacy032_v2.py",
    "python/week6_student/student_bc_loader.py",
    "python/week6_student/stage10d1_observation_channel_comparison.py",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, rel: str) -> Path:
    return root / rel


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.3 source code mapping audit")
    p.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d3_source_code_mapping_audit.json"),
    )
    return p.parse_args()


def _extract_line_matches(lines: List[str], patterns: List[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i, line in enumerate(lines, start=1):
        for pat in patterns:
            if re.search(pat, line):
                out.append({"line": int(i), "text": line.rstrip("\n")})
                break
    return out


def _classify_mapping(lines: List[str], path: str) -> Dict[str, Any]:
    text = "\n".join(lines)
    owner_abs = bool(re.search(r"neutral,\s*player1,\s*player2|OwnerToOneHotIndex", text, flags=re.IGNORECASE))
    owner_persp = bool(re.search(r"neutral,\s*friendly,\s*enemy|OwnerToPerspectiveOneHotIndex", text, flags=re.IGNORECASE))

    unit_decl = bool(re.search(r"unit_type|CH_UNIT_TYPE_BASE|\[5-11\]|\[13:21\]", text, flags=re.IGNORECASE))
    act_decl = bool(re.search(r"current_action|CH_ACTION_BASE|\[12-17\]|\[21:27\]", text, flags=re.IGNORECASE))
    dir_decl = bool(re.search(r"direction|CH_DIR_BASE|\[18-21\]", text, flags=re.IGNORECASE))

    flatten_row_major = bool(re.search(r"row\s*\*\s*24\s*\+\s*col|row-major|reshape\(.*576,\s*27\)", text, flags=re.IGNORECASE))

    return {
        "file": path,
        "owner_semantics_declared": {
            "absolute_player_channels": owner_abs,
            "perspective_friendly_enemy": owner_persp,
        },
        "group_declarations_present": {
            "unit_type": unit_decl,
            "current_action": act_decl,
            "direction": dir_decl,
        },
        "flatten_row_major_declared": flatten_row_major,
    }


def main() -> int:
    args = parse_args()
    root = _repo_root()
    out_path = args.output if args.output.is_absolute() else (root / args.output)

    pattern_bank = [
        r"\[2-4\]|owner|OwnerToOneHotIndex|OwnerToPerspectiveOneHotIndex|friendly|enemy|player1|player2",
        r"\[5-11\]|unit_type|CH_UNIT_TYPE_BASE|\[13:21\]",
        r"\[12-17\]|current_action|CH_ACTION_BASE|\[21:27\]",
        r"\[18-21\]|direction|CH_DIR_BASE",
        r"row\s*\*\s*24\s*\+\s*col|row-major|reshape\(.*576,\s*27\)",
    ]

    per_file: List[Dict[str, Any]] = []
    table_rows: List[Dict[str, Any]] = []

    for rel in FILES_TO_AUDIT:
        fp = _resolve(root, rel)
        if not fp.exists():
            per_file.append({"file": rel, "exists": False, "matches": []})
            table_rows.append(
                {
                    "source": rel,
                    "owner_declared": "missing",
                    "unit_type_declared": "missing",
                    "current_action_declared": "missing",
                    "direction_declared": "missing",
                    "flattening_declared": "missing",
                }
            )
            continue

        lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
        matches = _extract_line_matches(lines, pattern_bank)
        cls = _classify_mapping(lines, rel)

        owner_abs = cls["owner_semantics_declared"]["absolute_player_channels"]
        owner_persp = cls["owner_semantics_declared"]["perspective_friendly_enemy"]
        if owner_abs and owner_persp:
            owner_label = "mixed(abs+perspective)"
        elif owner_abs:
            owner_label = "absolute_player_channels"
        elif owner_persp:
            owner_label = "perspective_friendly_enemy"
        else:
            owner_label = "not_explicit"

        table_rows.append(
            {
                "source": rel,
                "owner_declared": owner_label,
                "unit_type_declared": bool(cls["group_declarations_present"]["unit_type"]),
                "current_action_declared": bool(cls["group_declarations_present"]["current_action"]),
                "direction_declared": bool(cls["group_declarations_present"]["direction"]),
                "flattening_declared": bool(cls["flatten_row_major_declared"]),
            }
        )

        per_file.append(
            {
                "file": rel,
                "exists": True,
                "line_count": int(len(lines)),
                "matches": matches[:80],
                "classification": cls,
            }
        )

    # Derive audit-level conflicts.
    owner_labels = [r["owner_declared"] for r in table_rows if isinstance(r.get("owner_declared"), str)]
    has_abs = any("absolute" in x or "mixed" in x for x in owner_labels)
    has_persp = any("perspective" in x or "mixed" in x for x in owner_labels)

    out: Dict[str, Any] = {
        "stage": "10D.3",
        "diagnostic": "source_code_mapping_audit",
        "audited_files": per_file,
        "declared_mapping_table": table_rows,
        "cross_source_consistency": {
            "owner_semantics_conflict_detected": bool(has_abs and has_persp),
            "unit_type_declared_in_all_core_sources": bool(
                all(bool(r.get("unit_type_declared")) for r in table_rows if r.get("unit_type_declared") != "missing")
            ),
            "current_action_declared_in_all_core_sources": bool(
                all(bool(r.get("current_action_declared")) for r in table_rows if r.get("current_action_declared") != "missing")
            ),
            "direction_declared_in_all_core_sources": bool(
                all(bool(r.get("direction_declared")) for r in table_rows if r.get("direction_declared") != "missing")
            ),
            "flattening_row_major_declared_somewhere": bool(
                any(bool(r.get("flattening_declared")) for r in table_rows if r.get("flattening_declared") != "missing")
            ),
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=True, indent=2), encoding="utf-8")
    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
