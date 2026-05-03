#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage10D.2 observation source-of-truth audit")
    parser.add_argument(
        "--observation-contract-cs",
        type=Path,
        default=Path("Assets/Scripts/ML/ObservationContract.cs"),
    )
    parser.add_argument(
        "--observation-builder-cs",
        type=Path,
        default=Path("Assets/Scripts/ML/ObservationBuilder.cs"),
    )
    parser.add_argument(
        "--stage10r-snapshot",
        type=Path,
        default=Path("python/week6_student/reports/stage10r_noop_collapse_snapshot_step0001.json"),
    )
    parser.add_argument(
        "--adapter-py",
        type=Path,
        default=Path("python/week6_student/student_inference_adapter.py"),
    )
    parser.add_argument(
        "--loader-py",
        type=Path,
        default=Path("python/week6_student/student_bc_loader.py"),
    )
    parser.add_argument(
        "--stage10d1-channel-script",
        type=Path,
        default=Path("python/week6_student/stage10d1_observation_channel_comparison.py"),
    )
    parser.add_argument(
        "--stage10d1-distribution-script",
        type=Path,
        default=Path("python/week6_student/stage10d1_dataset_action_distribution.py"),
    )
    parser.add_argument(
        "--bc-manifest",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/teacher_exports_bc/"
            "day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z/bc_manifest.json"
        ),
    )
    parser.add_argument(
        "--adapted-manifest",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/teacher_adapted/"
            "legacy032_3m_unity_v2_adapted_20260501T161820Z/adapted_manifest.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d2_observation_source_of_truth_audit.json"),
    )
    return parser.parse_args()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (repo_root / path)


def _parse_contract_map(contract_text: str) -> Dict[str, Any]:
    idx: Dict[str, int] = {}
    for key in (
        "CH_HIT_POINTS",
        "CH_RESOURCES",
        "CH_OWNER_BASE",
        "CH_OWNER_COUNT",
        "CH_UNIT_TYPE_BASE",
        "CH_UNIT_TYPE_COUNT",
        "CH_ACTION_BASE",
        "CH_ACTION_COUNT",
        "CH_DIR_BASE",
        "CH_DIR_COUNT",
        "CH_PRODUCE_BASE",
        "CH_PRODUCE_COUNT",
        "CH_ATTACK_TARGET",
    ):
        m = re.search(rf"{re.escape(key)}\s*=\s*(\d+)", contract_text)
        if m:
            idx[key] = int(m.group(1))

    def rng(base_key: str, count_key: str) -> List[int]:
        b = idx.get(base_key)
        c = idx.get(count_key)
        if b is None or c is None:
            return []
        return [b, b + c - 1]

    return {
        "scalar": {
            "hit_points": idx.get("CH_HIT_POINTS"),
            "resources": idx.get("CH_RESOURCES"),
            "attack_target": idx.get("CH_ATTACK_TARGET"),
        },
        "groups": {
            "owner": {
                "range": rng("CH_OWNER_BASE", "CH_OWNER_COUNT"),
                "declared_semantics": "neutral, player1, player2",
            },
            "unit_type": {
                "range": rng("CH_UNIT_TYPE_BASE", "CH_UNIT_TYPE_COUNT"),
                "declared_semantics": "resource, base, barracks, worker, light, heavy, ranged",
            },
            "current_action": {
                "range": rng("CH_ACTION_BASE", "CH_ACTION_COUNT"),
                "declared_semantics": "noop, move, harvest, return, produce, attack",
            },
            "direction": {
                "range": rng("CH_DIR_BASE", "CH_DIR_COUNT"),
                "declared_semantics": "north, east, south, west",
            },
            "produce_type": {
                "range": rng("CH_PRODUCE_BASE", "CH_PRODUCE_COUNT"),
                "declared_semantics": "worker, light, heavy, ranged",
            },
        },
    }


def _parse_builder_owner_semantics(builder_text: str) -> Dict[str, Any]:
    mvp_perspective = "[neutral, friendly, enemy]" in builder_text
    compat_absolute = "owner (one-hot: neutral, player1, player2)" in builder_text
    return {
        "unity_mvp_transfer_owner_semantics": "neutral, friendly, enemy" if mvp_perspective else "unknown",
        "legacy_compat_owner_semantics": "neutral, player1, player2" if compat_absolute else "unknown",
        "mixed_semantics_detected": bool(mvp_perspective and compat_absolute),
    }


def _parse_adapter_channel_names(adapter_text: str) -> List[str]:
    m = re.search(r"OBS_CHANNEL_NAMES\s*:\s*tuple\[str,\s*\.\.\.\]\s*=\s*\((.*?)\)\n\n", adapter_text, re.S)
    if not m:
        return []
    body = m.group(1)
    names = re.findall(r'"([^"]+)"', body)
    return names


def _parse_stage10d1_assumptions(stage10d1_channel_text: str, stage10d1_distribution_text: str) -> Dict[str, Any]:
    groups: Dict[str, List[int]] = {}
    m = re.search(r"CHANNEL_GROUPS\s*=\s*\{(.*?)\}\n\n", stage10d1_channel_text, re.S)
    if m:
        body = m.group(1)
        for name, start, end in re.findall(r'"([^"]+)"\s*:\s*\((\d+)\s*,\s*(\d+)\)', body):
            groups[name] = [int(start), int(end) - 1]

    owner_player1_index = 3 if "owner_player1" in stage10d1_distribution_text else None
    owner_mode = "absolute_player_channels" if owner_player1_index is not None else "unknown"
    return {
        "group_ranges": groups,
        "owner_interpretation": {
            "mode": owner_mode,
            "owner_neutral_index": 2,
            "owner_player1_index": owner_player1_index,
            "owner_player2_index": 4,
        },
    }


def _manifest_channel_map(bc_manifest: Dict[str, Any], adapted_manifest: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "bc_ready": {
            "observation_shape_per_sample": bc_manifest.get("observation_shape_per_sample"),
            "action_shape_per_sample": bc_manifest.get("action_shape_per_sample"),
            "branch_sizes": bc_manifest.get("branch_sizes"),
            "flatten_order": bc_manifest.get("flatten_order"),
            "flat_cell_index_formula": bc_manifest.get("flat_cell_index_formula"),
            "channel_names_present": False,
        },
        "adapted": {
            "observation_shape_per_sample": adapted_manifest.get("observation_shape_per_sample"),
            "action_shape_per_sample": adapted_manifest.get("action_shape_per_sample"),
            "branch_sizes": adapted_manifest.get("branch_sizes"),
            "flatten_order": adapted_manifest.get("flatten_order"),
            "flat_cell_index_formula": adapted_manifest.get("flat_cell_index_formula"),
            "channel_names_present": False,
        },
    }


def _classify_candidates(
    unity_contract: Dict[str, Any],
    unity_builder: Dict[str, Any],
    adapter_channels: List[str],
    stage10d1_assumptions: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    conflicts: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []
    candidates: List[str] = []

    adapter_owner = adapter_channels[2:5] if len(adapter_channels) >= 5 else []
    contract_owner = unity_contract["groups"].get("owner", {}).get("declared_semantics", "unknown")
    builder_owner_mvp = unity_builder.get("unity_mvp_transfer_owner_semantics", "unknown")

    if adapter_owner == ["owner_neutral", "owner_player1", "owner_player2"] and builder_owner_mvp == "neutral, friendly, enemy":
        conflicts.append(
            {
                "area": "owner_channels_2_4",
                "unity_contract": contract_owner,
                "unity_builder_mvp": builder_owner_mvp,
                "adapter_or_bridge_names": adapter_owner,
                "status": "CONFLICT",
                "note": "Runtime builder (UnityMvpTransfer) semantics differ from bridge/diagnostic naming.",
            }
        )
        candidates.extend(
            [
                "STAGE10D1_DIAGNOSTIC_CHANNEL_ASSUMPTION_ERROR",
                "CONTRACT_DOCUMENTATION_STALE_BUT_ARTIFACT_VALID",
                "UNITY_OBSERVATION_CHANNEL_MAPPING_ERROR",
            ]
        )

    if not adapter_channels:
        missing.append(
            {
                "area": "adapter_channel_names",
                "status": "MISSING",
                "note": "Failed to parse OBS_CHANNEL_NAMES from student_inference_adapter.py",
            }
        )

    if not stage10d1_assumptions.get("group_ranges"):
        missing.append(
            {
                "area": "stage10d1_group_ranges",
                "status": "MISSING",
                "note": "Failed to parse CHANNEL_GROUPS from Stage10D.1 script",
            }
        )

    if not candidates:
        candidates.append("INCONCLUSIVE_NEEDS_MANUAL_CHANNEL_SPEC")

    # Keep deterministic ordering with likely primary first.
    ordered = [
        "STAGE10D1_DIAGNOSTIC_CHANNEL_ASSUMPTION_ERROR",
        "CONTRACT_DOCUMENTATION_STALE_BUT_ARTIFACT_VALID",
        "UNITY_OBSERVATION_CHANNEL_MAPPING_ERROR",
        "BC_ADAPTER_CHANNEL_MAPPING_ERROR",
        "STUDENT_LOADER_RESHAPE_OR_AXIS_ERROR",
        "BC_DATASET_OBSERVATION_CORRUPTED",
        "UNITY_AND_BC_USE_DIFFERENT_PERSPECTIVE_ENCODING",
        "INCONCLUSIVE_NEEDS_MANUAL_CHANNEL_SPEC",
    ]
    candidates = [c for c in ordered if c in set(candidates)]
    return conflicts, missing, candidates


def main() -> int:
    args = parse_args()
    repo_root = _repo_root()

    contract_path = _resolve(repo_root, args.observation_contract_cs)
    builder_path = _resolve(repo_root, args.observation_builder_cs)
    snapshot_path = _resolve(repo_root, args.stage10r_snapshot)
    adapter_path = _resolve(repo_root, args.adapter_py)
    loader_path = _resolve(repo_root, args.loader_py)
    d1_channel_path = _resolve(repo_root, args.stage10d1_channel_script)
    d1_dist_path = _resolve(repo_root, args.stage10d1_distribution_script)
    bc_manifest_path = _resolve(repo_root, args.bc_manifest)
    adapted_manifest_path = _resolve(repo_root, args.adapted_manifest)
    out_path = _resolve(repo_root, args.output)

    source_files_examined: List[str] = []
    for p in (
        contract_path,
        builder_path,
        adapter_path,
        loader_path,
        d1_channel_path,
        d1_dist_path,
        bc_manifest_path,
        adapted_manifest_path,
    ):
        if p.exists():
            source_files_examined.append(str(p.relative_to(repo_root)).replace("\\", "/"))

    contract_text = _read_text(contract_path)
    builder_text = _read_text(builder_path)
    adapter_text = _read_text(adapter_path)
    d1_channel_text = _read_text(d1_channel_path)
    d1_distribution_text = _read_text(d1_dist_path)

    bc_manifest = _load_json(bc_manifest_path)
    adapted_manifest = _load_json(adapted_manifest_path)

    unity_contract = _parse_contract_map(contract_text)
    unity_builder = _parse_builder_owner_semantics(builder_text)
    adapter_channels = _parse_adapter_channel_names(adapter_text)
    d1_assumptions = _parse_stage10d1_assumptions(d1_channel_text, d1_distribution_text)
    manifest_map = _manifest_channel_map(bc_manifest, adapted_manifest)

    stage10r_owner_mode = None
    if snapshot_path.exists():
        snapshot = _load_json(snapshot_path)
        stage10r_owner_mode = snapshot.get("owner_encoding_mode")
        source_files_examined.append(str(snapshot_path.relative_to(repo_root)).replace("\\", "/"))

    conflicts, missing, candidates = _classify_candidates(unity_contract, unity_builder, adapter_channels, d1_assumptions)

    payload: Dict[str, Any] = {
        "stage": "10D.2",
        "diagnostic": "observation_source_of_truth_audit",
        "discovered_unity_channel_map": {
            "contract": unity_contract,
            "builder": unity_builder,
            "stage10r_snapshot_owner_encoding_mode": stage10r_owner_mode,
        },
        "discovered_adapter_channel_map": {
            "student_inference_adapter_obs_channel_names": adapter_channels,
            "owner_indices_2_4": adapter_channels[2:5] if len(adapter_channels) >= 5 else [],
        },
        "discovered_manifest_channel_map": manifest_map,
        "discovered_stage10d1_assumed_channel_map": d1_assumptions,
        "channel_map_conflicts": conflicts,
        "missing_or_ambiguous_channels": missing,
        "source_files_examined": source_files_examined,
        "root_cause_candidates": candidates,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
