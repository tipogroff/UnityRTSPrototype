#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.4 mapping spec validator")
    p.add_argument(
        "--mapping-json",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/observation_semantics/"
            "legacy032_to_unity_v2_observation_mapping.json"
        ),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d4_mapping_spec_validation.json"),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = _repo_root()
    mapping_path = _resolve(root, args.mapping_json)
    out_path = _resolve(root, args.output)

    if not mapping_path.exists():
        raise RuntimeError(f"Missing mapping file: {mapping_path}")

    spec = json.loads(mapping_path.read_text(encoding="utf-8"))

    hard_failures: List[str] = []
    warnings: List[str] = []

    def fail(msg: str) -> None:
        hard_failures.append(msg)

    required_meta = [
        "mapping_spec_version",
        "observation_semantics_version",
        "source_observation_semantics",
        "target_observation_semantics",
        "owner_mode_target",
        "channels",
        "group_validation",
    ]
    for k in required_meta:
        if k not in spec:
            fail(f"missing top-level field: {k}")

    owner_mode = spec.get("owner_mode_target")
    if owner_mode not in {"perspective_friendly_enemy", "absolute_player_channels"}:
        fail(f"owner_mode_target invalid: {owner_mode}")

    if bool(spec.get("owner_mode_ambiguous", False)):
        fail("owner_mode_ambiguous=true is forbidden")

    channels = spec.get("channels", [])
    if not isinstance(channels, list):
        fail("channels must be a list")
        channels = []

    by_target: Dict[int, Dict[str, Any]] = {}
    for entry in channels:
        if not isinstance(entry, dict):
            fail("channel entry must be object")
            continue
        if "target_channel" not in entry:
            fail("channel entry missing target_channel")
            continue

        t = entry["target_channel"]
        if not isinstance(t, int) or t < 0 or t > 26:
            fail(f"invalid target_channel: {t}")
            continue
        if t in by_target:
            fail(f"duplicate target_channel: {t}")
            continue
        by_target[t] = entry

        for k in ["target_name", "source", "confidence", "validation_rule", "fallback_behavior"]:
            if k not in entry:
                fail(f"target_channel {t} missing field: {k}")

        conf = entry.get("confidence")
        if conf not in {"exact", "empirical", "derived", "unavailable"}:
            fail(f"target_channel {t} invalid confidence: {conf}")

        src = entry.get("source", {})
        if not isinstance(src, dict):
            fail(f"target_channel {t} source must be object")
            src = {}

        has_mapping = False
        st = src.get("type")
        if st in {
            "raw_channel",
            "derived_action_type_one_hot",
            "derived_direction_one_hot",
            "derived_produce_type_one_hot",
            "derived_attack_target_scalar",
            "constant_zero",
        }:
            has_mapping = True
        if st == "unavailable":
            has_mapping = True
            if not str(src.get("reason", "")).strip():
                fail(f"target_channel {t} unavailable mapping requires reason")

        if not has_mapping:
            fail(f"target_channel {t} has no explicit mapping or unavailable reason")

        fallback = str(entry.get("fallback_behavior", "")).strip()
        if not fallback:
            fail(f"target_channel {t} fallback_behavior is empty")
        if "silent" in fallback.lower() or "copy_without_validation" in fallback.lower():
            fail(f"target_channel {t} fallback_behavior implies silent remap")

    expected = set(range(27))
    missing = sorted(expected - set(by_target.keys()))
    if missing:
        fail(f"missing target channels: {missing}")

    group_validation = spec.get("group_validation", {})
    for g in ["owner", "unit_type", "current_action", "direction", "produce"]:
        rec = group_validation.get(g)
        if not isinstance(rec, dict):
            fail(f"group_validation missing group: {g}")
            continue
        if "rule" not in rec or not str(rec.get("rule", "")).strip():
            fail(f"group_validation {g} lacks validation rule")
        if "multi_hot_forbidden" not in rec:
            fail(f"group_validation {g} lacks multi_hot_forbidden flag")

    critical_groups = spec.get(
        "critical_target_groups", ["owner", "unit_type", "current_action", "direction"]
    )
    group_ranges = {
        "owner": [2, 3, 4],
        "unit_type": [5, 6, 7, 8, 9, 10, 11],
        "current_action": [12, 13, 14, 15, 16, 17],
        "direction": [18, 19, 20, 21],
    }

    critical_unavailable: List[int] = []
    for group in critical_groups:
        if group not in group_ranges:
            warnings.append(f"unknown critical group in spec: {group}")
            continue
        for ch in group_ranges[group]:
            entry = by_target.get(ch)
            if not entry:
                continue
            if entry.get("confidence") == "unavailable":
                critical_unavailable.append(ch)

    status = "pass" if not hard_failures else "fail"

    out: Dict[str, Any] = {
        "stage": "10D.4",
        "diagnostic": "mapping_spec_validation",
        "mapping_json": mapping_path.as_posix(),
        "status": status,
        "owner_mode_target": owner_mode,
        "owner_mode_ambiguous": bool(spec.get("owner_mode_ambiguous", False)),
        "channels_present": sorted(by_target.keys()),
        "critical_unavailable_channels": sorted(critical_unavailable),
        "mapping_complete_for_critical_groups": bool(len(critical_unavailable) == 0),
        "hard_failures": hard_failures,
        "warnings": warnings,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=True, indent=2), encoding="utf-8")
    print(out_path.as_posix())

    return 0 if not hard_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
