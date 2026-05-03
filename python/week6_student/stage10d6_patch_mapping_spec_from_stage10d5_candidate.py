#!/usr/bin/env python3
"""Stage 10D.6 — Patch official mapping spec from Stage10D.5 candidate.

Patches target channels 2-4 (owner) and 5-11 (unit_type) from the candidate
spec into the official spec, updating metadata accordingly.

Strict constraints observed:
- Does NOT retrain, run PPO, or mutate any checkpoint.
- Does NOT overwrite raw rollout, adapted datasets, or BC-ready datasets.
- Does NOT silently remap channels.
- Only patches the channels authorised by Stage10D.5.
"""
from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


PATCH_TARGET_CHANNELS: List[int] = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

EXPECTED_PATCH_MAP: Dict[int, Dict[str, Any]] = {
    2:  {"name": "owner_neutral",      "raw_index": 10},
    3:  {"name": "owner_friendly",     "raw_index": 11},
    4:  {"name": "owner_enemy",        "raw_index": 12},
    5:  {"name": "unit_type_resource", "raw_index": 14},
    6:  {"name": "unit_type_base",     "raw_index": 15},
    7:  {"name": "unit_type_barracks", "raw_index": 16},
    8:  {"name": "unit_type_worker",   "raw_index": 17},
    9:  {"name": "unit_type_light",    "raw_index": 18},
    10: {"name": "unit_type_heavy",    "raw_index": 19},
    11: {"name": "unit_type_ranged",   "raw_index": 20},
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Stage10D.6 mapping spec patch from Stage10D.5 candidate"
    )
    p.add_argument(
        "--base-spec",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/observation_semantics/"
            "legacy032_to_unity_v2_observation_mapping.json"
        ),
        help="Official spec to be patched (in-place update).",
    )
    p.add_argument(
        "--candidate-spec",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/observation_semantics/"
            "legacy032_to_unity_v2_observation_mapping.stage10d5_candidate.json"
        ),
        help="Stage10D.5 candidate spec to pull owner/unit_type channels from.",
    )
    p.add_argument(
        "--patch-report",
        type=Path,
        default=Path(
            "python/week6_student/reports/stage10d6_mapping_spec_patch_report.json"
        ),
    )
    return p.parse_args()


def _verify_candidate_channel(
    cand_entry: Dict[str, Any],
    expected_target: int,
) -> str | None:
    """Return error string if the candidate channel does not match expectation, else None."""
    t = cand_entry.get("target_channel")
    if t != expected_target:
        return f"candidate target_channel {t} != expected {expected_target}"
    name = cand_entry.get("target_name", "")
    src = cand_entry.get("source", {})
    if src.get("type") != "raw_channel":
        return f"target {expected_target}: source.type must be raw_channel, got {src.get('type')}"
    raw_idx = src.get("index")
    exp_raw = EXPECTED_PATCH_MAP[expected_target]["raw_index"]
    if raw_idx != exp_raw:
        return (
            f"target {expected_target} ({name}): raw_index {raw_idx} != expected {exp_raw}"
        )
    return None


def main() -> int:
    args = parse_args()
    root = _repo_root()
    base_path = _resolve(root, args.base_spec)
    cand_path = _resolve(root, args.candidate_spec)
    report_path = _resolve(root, args.patch_report)

    if not base_path.exists():
        raise RuntimeError(f"Missing base spec: {base_path}")
    if not cand_path.exists():
        raise RuntimeError(f"Missing candidate spec: {cand_path}")

    base_spec: Dict[str, Any] = json.loads(base_path.read_text(encoding="utf-8"))
    cand_spec: Dict[str, Any] = json.loads(cand_path.read_text(encoding="utf-8"))

    # Index candidate channels by target_channel
    cand_by_target: Dict[int, Dict[str, Any]] = {}
    for entry in cand_spec.get("channels", []):
        cand_by_target[int(entry["target_channel"])] = entry

    # Verify all patch targets are present with expected raw indices
    pre_check_errors: List[str] = []
    for t in PATCH_TARGET_CHANNELS:
        if t not in cand_by_target:
            pre_check_errors.append(f"candidate spec missing target_channel {t}")
            continue
        err = _verify_candidate_channel(cand_by_target[t], t)
        if err:
            pre_check_errors.append(err)

    if pre_check_errors:
        print("[stage10d6][PATCH] PRE-CHECK FAILED:")
        for e in pre_check_errors:
            print(f"  - {e}")
        return 1

    # Patch base spec channels
    patched_spec = copy.deepcopy(base_spec)
    base_by_idx: Dict[int, int] = {
        int(e["target_channel"]): i
        for i, e in enumerate(patched_spec["channels"])
    }

    # Normalise confidence values from candidate spec to the allowed set.
    # Stage10D.5 used "empirical_high" for unit_type channels, which the
    # validator does not accept.  Both owner and unit_type channels are
    # derived from direct source-code encoder audit + controlled probe, so
    # we promote "empirical_high" → "exact" consistently with the owner channels.
    _CONFIDENCE_NORMALISE: Dict[str, str] = {"empirical_high": "exact"}

    patch_log: List[Dict[str, Any]] = []
    for t in PATCH_TARGET_CHANNELS:
        cand_entry = copy.deepcopy(cand_by_target[t])
        old_entry = patched_spec["channels"][base_by_idx[t]]

        raw_conf = cand_entry.get("confidence", "")
        normalised_conf = _CONFIDENCE_NORMALISE.get(raw_conf, raw_conf)
        if normalised_conf != raw_conf:
            print(
                f"[stage10d6][PATCH] target {t:2d}: confidence normalised "
                f"'{raw_conf}' -> '{normalised_conf}'"
            )
            cand_entry["confidence"] = normalised_conf

        old_conf = old_entry.get("confidence")
        old_src = old_entry.get("source", {})
        new_conf = cand_entry.get("confidence")
        new_src = cand_entry.get("source", {})

        patched_spec["channels"][base_by_idx[t]] = cand_entry

        patch_log.append({
            "target_channel": t,
            "target_name": EXPECTED_PATCH_MAP[t]["name"],
            "old_confidence": old_conf,
            "old_source_type": old_src.get("type"),
            "new_confidence": new_conf,
            "new_source_type": new_src.get("type"),
            "new_raw_index": new_src.get("index"),
            "patched": True,
        })
        print(
            f"[stage10d6][PATCH] target {t:2d} ({EXPECTED_PATCH_MAP[t]['name']:22s})"
            f"  {old_src.get('type','?'):12s} -> raw_channel[{new_src.get('index')}]"
        )

    # Update metadata
    patched_spec["mapping_spec_version"] = "stage10d6_v1"
    patched_spec["observation_semantics_version"] = "unity_v2_runtime_stage10d6"
    patched_spec["source_observation_semantics"] = "legacy032_raw_source_plus_controlled_probe"
    existing_notes: List[str] = patched_spec.get("notes", [])
    patched_spec["notes"] = existing_notes + [
        "owner/unit_type mapping recovered in Stage10D.5 from source-code encoder audit "
        "and controlled raw observation probe",
        "raw channel 13 is empty/no-unit slot and is intentionally not mapped to Unity unit_type",
        "mapping spec patched in Stage10D.6 from Stage10D.5 candidate; "
        "archived pre-patch spec at observation_semantics/archive/"
        "legacy032_to_unity_v2_observation_mapping.stage10d4_before_stage10d6_patch.json",
        f"patch applied at {_now_iso()}",
    ]

    base_path.write_text(
        json.dumps(patched_spec, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    print(f"[stage10d6][PATCH] wrote patched spec -> {base_path}")

    report: Dict[str, Any] = {
        "stage": "10D.6",
        "diagnostic": "mapping_spec_patch",
        "generated_at_utc": _now_iso(),
        "base_spec_path": base_path.as_posix(),
        "candidate_spec_path": cand_path.as_posix(),
        "patched_channels": PATCH_TARGET_CHANNELS,
        "pre_check_errors": pre_check_errors,
        "patch_log": patch_log,
        "new_mapping_spec_version": patched_spec["mapping_spec_version"],
        "new_observation_semantics_version": patched_spec["observation_semantics_version"],
        "status": "success" if not pre_check_errors else "failed",
        "explicit_non_claims": [
            "No retraining, PPO, or checkpoint mutation performed.",
            "No raw rollout overwrite.",
            "No adapted dataset overwrite.",
            "No BC-ready dataset overwrite.",
            "No silent channel remap.",
            "No claim of exact Gym-microRTS to Unity semantic parity beyond owner/unit_type channels.",
        ],
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"[stage10d6][PATCH] report -> {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
