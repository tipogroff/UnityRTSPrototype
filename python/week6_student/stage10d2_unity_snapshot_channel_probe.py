#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


FOCUS = {
    "B2": 25,
    "C3": 50,
    "A1": 0,
    "A2": 24,
    "B1": 1,
    "V22": 525,
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage10D.2 Unity snapshot channel probe")
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("python/week6_student/reports"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d2_unity_snapshot_channel_probe.json"),
    )
    return parser.parse_args()


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _collect_snapshot_paths(reports_dir: Path) -> List[Path]:
    patterns = [
        "stage10r_noop_collapse_snapshot_step*.json",
        "stage10v_visual_snapshot_step*.json",
        "*snapshot*step*.json",
    ]
    found: List[Path] = []
    seen = set()
    for pat in patterns:
        for p in sorted(reports_dir.glob(pat)):
            r = str(p.resolve())
            if r not in seen:
                seen.add(r)
                found.append(p)
    return found


def _extract_cells(snapshot: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    by_flat: Dict[int, Dict[str, Any]] = {}
    for section in ("focus_cell_diagnostics", "actor_cells"):
        rows = snapshot.get(section, [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            flat = row.get("flat_index")
            channels = row.get("cell_observation_channels")
            if isinstance(flat, int) and isinstance(channels, list) and len(channels) == 27:
                by_flat[flat] = {
                    "logical_label": row.get("logical_label") or row.get("logical_cell"),
                    "flat_index": flat,
                    "grid_position": row.get("grid_position"),
                    "unit_type": row.get("unit_type"),
                    "owner": row.get("owner"),
                    "channels": [float(x) for x in channels],
                    "observation_channel_names": row.get("observation_channel_names"),
                }
    return by_flat


def _interpret(ch: List[float], owner_mode: str) -> Dict[str, Any]:
    owner = ch[2:5]
    unit = ch[5:12]
    action = ch[12:18]
    direction = ch[18:22]
    produce = ch[22:26]
    owner_labels = ["neutral", "player1", "player2"]
    if owner_mode == "perspective_friendly_enemy":
        owner_labels = ["neutral", "friendly", "enemy"]

    return {
        "owner_values": owner,
        "owner_argmax": owner_labels[int(max(range(3), key=lambda i: owner[i]))],
        "unit_type_argmax": int(max(range(7), key=lambda i: unit[i])),
        "current_action_argmax": int(max(range(6), key=lambda i: action[i])),
        "direction_argmax": int(max(range(4), key=lambda i: direction[i])),
        "produce_argmax": int(max(range(4), key=lambda i: produce[i])),
        "attack_target": float(ch[26]),
    }


def main() -> int:
    args = parse_args()
    root = _repo_root()
    reports_dir = _resolve(root, args.reports_dir)
    out_path = _resolve(root, args.output)

    expected_search_locations = [
        str((reports_dir / "stage10r_noop_collapse_snapshot_step0001.json").relative_to(root)).replace("\\", "/"),
        str((reports_dir / "stage10v_visual_snapshot_step0001.json").relative_to(root)).replace("\\", "/"),
        str((reports_dir / "*snapshot*step*.json").relative_to(root)).replace("\\", "/"),
    ]

    if not reports_dir.exists():
        payload = {
            "stage": "10D.2",
            "diagnostic": "unity_snapshot_channel_probe",
            "status": "SNAPSHOT_NOT_FOUND",
            "searched_locations": expected_search_locations,
            "details": "Reports directory is missing.",
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(out_path.as_posix())
        return 0

    snapshots = _collect_snapshot_paths(reports_dir)
    if not snapshots:
        payload = {
            "stage": "10D.2",
            "diagnostic": "unity_snapshot_channel_probe",
            "status": "SNAPSHOT_NOT_FOUND",
            "searched_locations": expected_search_locations,
            "details": "No snapshot files matched expected patterns.",
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(out_path.as_posix())
        return 0

    all_snaps: List[Dict[str, Any]] = []
    merged_focus: Dict[str, Any] = {}
    missing_focus: Dict[str, List[str]] = {}

    for p in snapshots:
        snap = _load_json(p)
        by_flat = _extract_cells(snap)
        owner_mode_raw = str(snap.get("owner_encoding_mode", "")).strip()
        owner_mode = "perspective_friendly_enemy" if owner_mode_raw == "friendly_enemy" else "absolute_player_channels"

        rel = str(p.relative_to(root)).replace("\\", "/")
        found_labels: List[str] = []
        missing_labels: List[str] = []
        cells_payload: Dict[str, Any] = {}

        for lbl, flat in FOCUS.items():
            row = by_flat.get(flat)
            if row is None:
                missing_labels.append(lbl)
                continue
            found_labels.append(lbl)
            cells_payload[lbl] = {
                "flat_index": flat,
                "grid_position": row.get("grid_position"),
                "unit_type": row.get("unit_type"),
                "owner": row.get("owner"),
                "raw_channels_27": row.get("channels"),
                "interpretation_unity_source_map": _interpret(row.get("channels", []), owner_mode="perspective_friendly_enemy"),
                "interpretation_stage10d1_assumption": _interpret(row.get("channels", []), owner_mode="absolute_player_channels"),
                "mismatch_note": (
                    "Owner channel meaning may diverge between friendly/enemy and player1/player2 naming."
                    if row.get("channels")
                    else "No channels."
                ),
            }

            if lbl in ("B2", "C3") and lbl not in merged_focus:
                merged_focus[lbl] = cells_payload[lbl]

        all_snaps.append(
            {
                "snapshot_file": rel,
                "owner_encoding_mode": owner_mode_raw,
                "found_focus_labels": found_labels,
                "missing_focus_labels": missing_labels,
                "cells": cells_payload,
            }
        )
        if missing_labels:
            missing_focus[rel] = missing_labels

    payload = {
        "stage": "10D.2",
        "diagnostic": "unity_snapshot_channel_probe",
        "status": "OK",
        "searched_locations": expected_search_locations,
        "snapshots_examined": [str(p.relative_to(root)).replace("\\", "/") for p in snapshots],
        "focus_cells_merged": merged_focus,
        "snapshot_details": all_snaps,
        "missing_focus_by_snapshot": missing_focus,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
