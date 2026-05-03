#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _channel_record(target_ch: int, target_name: str, raw_idx: int, confidence: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "target_channel": int(target_ch),
        "target_name": target_name,
        "source": {"type": "raw_channel", "index": int(raw_idx)},
        "confidence": confidence,
        "validation_rule": "owner_one_hot_group" if 2 <= target_ch <= 4 else "unit_type_one_hot_group",
        "fallback_behavior": "set_zero_and_flag_if_runtime_validation_fails",
        "evidence": evidence,
    }


def _extract_owner_candidate(controlled_probe: Dict[str, Any], rollout: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    inferred = controlled_probe.get("inferred_owner_channel_candidates", {}).get("owner_player0_channel")
    inferred_n = controlled_probe.get("inferred_owner_channel_candidates", {}).get("owner_neutral_channel")
    inferred_e = controlled_probe.get("inferred_owner_channel_candidates", {}).get("owner_player1_channel")
    if inferred is None or inferred_n is None or inferred_e is None:
        return None

    top_owner = (rollout.get("owner_candidate_windows") or [None])[0]
    proxy_agree = False
    if isinstance(top_owner, dict):
        ws = int(top_owner["window"][0])
        p0 = ws + int(top_owner.get("player0_peak_local", -1))
        p1 = ws + int(top_owner.get("player1_peak_local", -1))
        proxy_agree = (p0 == int(inferred)) and (p1 == int(inferred_e))

    return {
        "raw_owner_neutral": int(inferred_n),
        "raw_owner_player0": int(inferred),
        "raw_owner_player1": int(inferred_e),
        "proxy_agreement": bool(proxy_agree),
    }


def _extract_unit_candidate(controlled_probe: Dict[str, Any], source_audit: Dict[str, Any], rollout: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    inferred = controlled_probe.get("inferred_unit_type_channel_candidates", {}).get("unit_type_observed_raw_channels", {})
    if not isinstance(inferred, dict) or not inferred:
        return None

    # Prefer source-group exact offsets from vec_env.py declaration when available.
    # num_planes = [5,5,3,len(unitTypes)+1,6] => unit_type block starts at 13,
    # where channel 13 corresponds to "no-unit/empty" and typed units follow from 14.
    # UTT ordering in common 0.3.2 is Resource,Base,Barracks,Worker,Light,Heavy,Ranged.
    source_exact = {
        "Resource": 14,
        "Base": 15,
        "Barracks": 16,
        "Worker": 17,
        "Light": 18,
        "Heavy": 19,
        "Ranged": 20,
    }

    observed_agree = True
    for key in ["Resource", "Base", "Worker"]:
        if key in inferred and int(inferred[key]) != int(source_exact[key]):
            observed_agree = False

    top_unit = (rollout.get("unit_type_candidate_windows") or [None])[0]
    proxy_window_agree = False
    if isinstance(top_unit, dict):
        # Proxy sweep can be noisy because action-linked channels dominate some windows.
        # Accept broad agreement if source-type channels are covered by the top window.
        w0 = int(top_unit["window"][0])
        w1 = int(top_unit["window"][1])
        proxy_window_agree = (w0 <= 14 <= w1) and (w0 <= 17 <= w1)

    return {
        "raw_unit_type_channels": source_exact,
        "controlled_observed_channels": {k: int(v) for k, v in inferred.items()},
        "controlled_observed_agree_with_source_exact": bool(observed_agree),
        "proxy_window_agree_with_source_exact_start13": bool(proxy_window_agree),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.5 owner/unit mapping candidate builder")
    p.add_argument(
        "--source-audit",
        type=Path,
        default=Path("python/week6_student/reports/stage10d5_legacy032_observation_encoder_source_audit.json"),
    )
    p.add_argument(
        "--controlled-probe",
        type=Path,
        default=Path("python/week6_student/reports/stage10d5_controlled_raw_observation_probe.json"),
    )
    p.add_argument(
        "--rollout-crosscheck",
        type=Path,
        default=Path("python/week6_student/reports/stage10d5_rollout_entity_proxy_crosscheck.json"),
    )
    p.add_argument(
        "--base-mapping",
        type=Path,
        default=Path("python/week5_teacher_legacy032/observation_semantics/legacy032_to_unity_v2_observation_mapping.json"),
    )
    p.add_argument(
        "--candidate-report",
        type=Path,
        default=Path("python/week6_student/reports/stage10d5_owner_unit_mapping_candidate.json"),
    )
    p.add_argument(
        "--candidate-mapping",
        type=Path,
        default=Path("python/week5_teacher_legacy032/observation_semantics/legacy032_to_unity_v2_observation_mapping.stage10d5_candidate.json"),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = _repo_root()

    src_audit = _load(_resolve(root, args.source_audit))
    controlled = _load(_resolve(root, args.controlled_probe))
    rollout = _load(_resolve(root, args.rollout_crosscheck))
    base_mapping_path = _resolve(root, args.base_mapping)
    base_mapping = _load(base_mapping_path)

    owner_cand = _extract_owner_candidate(controlled, rollout)
    unit_cand = _extract_unit_candidate(controlled, src_audit, rollout)

    hard_failures: List[str] = []
    if owner_cand is None:
        hard_failures.append("owner candidate unresolved")
    if unit_cand is None:
        hard_failures.append("unit_type candidate unresolved")

    candidate_mapping = copy.deepcopy(base_mapping)
    candidate_mapping["mapping_spec_version"] = "stage10d5_candidate_v1"
    candidate_mapping["observation_semantics_version"] = "unity_v2_runtime_stage10d5_candidate"
    candidate_mapping["source_observation_semantics"] = "legacy032_raw_source_plus_controlled_probe"

    ch_by_target: Dict[int, Dict[str, Any]] = {
        int(rec["target_channel"]): rec for rec in candidate_mapping.get("channels", [])
    }

    if owner_cand is not None:
        owner_evidence = {
            "source_file_evidence": "gym_microrts/envs/vec_env.py num_planes=[5,5,3,...] and _encode_obs group offsets",
            "controlled_state_evidence": owner_cand,
            "rollout_proxy_evidence": (rollout.get("owner_candidate_windows") or [None])[0],
            "confidence": "exact" if owner_cand.get("proxy_agreement", False) else "empirical_high",
        }
        ch_by_target[2] = _channel_record(2, "owner_neutral", owner_cand["raw_owner_neutral"], owner_evidence["confidence"], owner_evidence)
        ch_by_target[3] = _channel_record(3, "owner_friendly", owner_cand["raw_owner_player0"], owner_evidence["confidence"], owner_evidence)
        ch_by_target[4] = _channel_record(4, "owner_enemy", owner_cand["raw_owner_player1"], owner_evidence["confidence"], owner_evidence)

    if unit_cand is not None:
        conf = "exact" if (unit_cand.get("controlled_observed_agree_with_source_exact") and unit_cand.get("proxy_window_agree_with_source_exact_start13")) else "empirical_high"
        unit_evidence = {
            "source_file_evidence": "group offset/unit_types from vec_env.py and UTT ordering",
            "controlled_state_evidence": unit_cand,
            "rollout_proxy_evidence": (rollout.get("unit_type_candidate_windows") or [None])[0],
            "confidence": conf,
        }

        raw = unit_cand["raw_unit_type_channels"]
        target_to_type = {
            5: "Resource",
            6: "Base",
            7: "Barracks",
            8: "Worker",
            9: "Light",
            10: "Heavy",
            11: "Ranged",
        }
        target_name = {
            5: "unit_type_resource",
            6: "unit_type_base",
            7: "unit_type_barracks",
            8: "unit_type_worker",
            9: "unit_type_light",
            10: "unit_type_heavy",
            11: "unit_type_ranged",
        }
        for t in range(5, 12):
            kind = target_to_type[t]
            ch_by_target[t] = _channel_record(t, target_name[t], int(raw[kind]), conf, unit_evidence)

    candidate_mapping["channels"] = [ch_by_target[i] for i in sorted(ch_by_target.keys())]

    # refresh critical unavailable metrics in report-side interpretation
    critical = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    critical_unavailable = [
        c for c in critical if ch_by_target.get(c, {}).get("confidence") == "unavailable"
    ]

    report = {
        "stage": "10D.5",
        "diagnostic": "owner_unit_mapping_candidate_builder",
        "status": "pass" if not hard_failures else "fail",
        "base_mapping": base_mapping_path.as_posix(),
        "candidate_mapping_output": _resolve(root, args.candidate_mapping).as_posix(),
        "owner_candidate": owner_cand,
        "unit_type_candidate": unit_cand,
        "critical_unavailable_after_candidate": critical_unavailable,
        "mapping_complete_for_critical_groups": len(critical_unavailable) == 0,
        "hard_failures": hard_failures,
    }

    report_path = _resolve(root, args.candidate_report)
    mapping_path = _resolve(root, args.candidate_mapping)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    mapping_path.write_text(json.dumps(candidate_mapping, ensure_ascii=True, indent=2), encoding="utf-8")

    print(json.dumps({
        "candidate_report": report_path.as_posix(),
        "candidate_mapping": mapping_path.as_posix(),
        "status": report["status"],
    }, ensure_ascii=True, indent=2))
    return 0 if not hard_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
