#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np


TARGET_OBS_SHAPE = (576, 27)
TARGET_ACTION_SHAPE = (576, 7)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(1024 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _parse_bool(s: str) -> bool:
    v = str(s).strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid bool: {s}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.4 semantic adapter legacy032 -> unity_v2")
    p.add_argument(
        "--raw-rollout-dir",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/teacher_rollouts/"
            "legacy032_3m_unity_v2_rollout_export_20260501T125015Z"
        ),
    )
    p.add_argument(
        "--mapping-json",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/observation_semantics/"
            "legacy032_to_unity_v2_observation_mapping.json"
        ),
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("python/week5_teacher_legacy032/teacher_adapted"),
    )
    p.add_argument("--run-label", type=str, default="legacy032_3m_unity_v2_semantic_adapted")
    p.add_argument("--allow-critical-unavailable", type=_parse_bool, default=True)
    return p.parse_args()


def _json_dump(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _build_direction_expected(actions: np.ndarray) -> np.ndarray:
    action_type = actions[:, :, 0]
    out = np.full(action_type.shape, -1, dtype=np.int16)

    move = action_type == 1
    harvest = action_type == 2
    ret = action_type == 3
    produce = action_type == 4

    out[move] = actions[:, :, 1][move]
    out[harvest] = actions[:, :, 2][harvest]
    out[ret] = actions[:, :, 3][ret]
    out[produce] = actions[:, :, 4][produce]
    return out


def _apply_channel_rule(
    out_obs: np.ndarray,
    target_channel: int,
    rule: Dict[str, Any],
    raw_obs: np.ndarray,
    actions: np.ndarray,
    unavailable_channels: List[int],
) -> Dict[str, Any]:
    source = rule.get("source", {})
    st = source.get("type")

    if st == "raw_channel":
        idx = int(source["index"])
        if idx < 0 or idx > 26:
            raise RuntimeError(f"invalid raw_channel index {idx} for target channel {target_channel}")
        out_obs[:, :, target_channel] = raw_obs[:, :, idx]
        return {"kind": "raw_channel", "raw_channel": idx}

    if st == "derived_action_type_one_hot":
        cls = int(source["class_index"])
        out_obs[:, :, target_channel] = (actions[:, :, 0] == cls).astype(np.float32)
        return {"kind": "derived_action_type_one_hot", "class_index": cls}

    if st == "derived_direction_one_hot":
        cls = int(source["class_index"])
        expected = _build_direction_expected(actions)
        out_obs[:, :, target_channel] = (expected == cls).astype(np.float32)
        return {"kind": "derived_direction_one_hot", "class_index": cls}

    if st == "derived_produce_type_one_hot":
        cls = int(source["class_index"])
        mapping = source.get("raw_produce_to_unity_map", {})
        action_type = actions[:, :, 0]
        produce_branch = actions[:, :, 5]
        mapped = np.full(produce_branch.shape, -1, dtype=np.int16)
        for k, v in mapping.items():
            mapped[produce_branch == int(k)] = int(v)
        mask = (action_type == 4) & (mapped == cls)
        out_obs[:, :, target_channel] = mask.astype(np.float32)
        return {
            "kind": "derived_produce_type_one_hot",
            "class_index": cls,
            "raw_produce_to_unity_map": mapping,
        }

    if st == "derived_attack_target_scalar":
        action_type = actions[:, :, 0]
        attack_local = actions[:, :, 6].astype(np.float32)
        val = np.zeros_like(attack_local, dtype=np.float32)
        atk = action_type == 5
        val[atk] = (attack_local[atk] + 1.0) / 49.0
        np.clip(val, 0.0, 1.0, out=val)
        out_obs[:, :, target_channel] = val
        return {"kind": "derived_attack_target_scalar"}

    if st == "constant_zero":
        out_obs[:, :, target_channel] = 0.0
        return {"kind": "constant_zero"}

    if st == "unavailable":
        out_obs[:, :, target_channel] = 0.0
        unavailable_channels.append(int(target_channel))
        return {"kind": "unavailable", "reason": str(source.get("reason", ""))}

    raise RuntimeError(f"Unsupported mapping source.type '{st}' at target channel {target_channel}")


def _build_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Stage10D.4 Observation Semantic Conversion Report")
    lines.append("")
    lines.append(f"- status: {report['status']}")
    lines.append(f"- output_dir: {report['output_dir']}")
    lines.append(f"- source_rollout_dir: {report['source_rollout_dir']}")
    lines.append(f"- sample_count: {report['sample_count']}")
    lines.append(f"- observation_semantics_version: {report['observation_semantics_version']}")
    lines.append(f"- source_observation_semantics: {report['source_observation_semantics']}")
    lines.append(f"- target_observation_semantics: {report['target_observation_semantics']}")
    lines.append("")
    lines.append("## Shapes")
    lines.append(f"- raw_observation_shape: {report['raw_observation_shape']}")
    lines.append(f"- adapted_observation_shape: {report['adapted_observation_shape']}")
    lines.append(f"- actions_shape: {report['actions_shape']}")
    lines.append("")
    lines.append("## Mapping")
    lines.append(f"- mapping_file: {report['mapping_file']}")
    lines.append(f"- mapping_file_hash: {report['mapping_file_hash']}")
    lines.append(f"- channels_applied: {report['channels_applied_count']}")
    lines.append(f"- unavailable_channels: {report['unavailable_channels']}")
    lines.append(f"- critical_unavailable_channels: {report['critical_unavailable_channels']}")
    lines.append("")
    lines.append("## Data Integrity")
    lines.append(f"- adapted_has_nan: {report['adapted_has_nan']}")
    lines.append(f"- adapted_has_inf: {report['adapted_has_inf']}")
    lines.append(f"- adapted_min: {report['adapted_min']}")
    lines.append(f"- adapted_max: {report['adapted_max']}")
    lines.append("")
    lines.append("## Warnings")
    for w in report["warnings"]:
        lines.append(f"- {w}")
    if not report["warnings"]:
        lines.append("- none")
    lines.append("")
    lines.append("## Hard Failures")
    for h in report["hard_failures"]:
        lines.append(f"- {h}")
    if not report["hard_failures"]:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    root = _repo_root()

    raw_rollout_dir = _resolve(root, args.raw_rollout_dir)
    mapping_json = _resolve(root, args.mapping_json)
    output_root = _resolve(root, args.output_dir)

    run_dir = output_root / f"{args.run_label}_{_now_compact()}"
    run_dir.mkdir(parents=True, exist_ok=False)

    raw_npz = raw_rollout_dir / "teacher_rollout_raw.npz"
    if not raw_npz.exists():
        raise RuntimeError(f"Missing raw rollout npz: {raw_npz}")
    if not mapping_json.exists():
        raise RuntimeError(f"Missing mapping json: {mapping_json}")

    mapping = json.loads(mapping_json.read_text(encoding="utf-8"))
    channels = mapping.get("channels", [])
    by_target: Dict[int, Dict[str, Any]] = {}
    for rec in channels:
        by_target[int(rec["target_channel"])] = rec

    with np.load(raw_npz, allow_pickle=False) as npz:
        raw_obs_hwc = np.asarray(npz["observation_t"], dtype=np.float32)
        actions = np.asarray(npz["per_cell_action_t"], dtype=np.int16)

        episode_id = np.asarray(npz["episode_id"], dtype=np.int32)
        step_id = np.asarray(npz["step_id"], dtype=np.int32)
        reward_t = np.asarray(npz["reward_t"], dtype=np.float32)
        done_t = np.asarray(npz["done_t"], dtype=np.bool_)
        terminated_t = np.asarray(npz["terminated_t"], dtype=np.bool_)
        truncated_t = np.asarray(npz["truncated_t"], dtype=np.bool_)
        action_mask_available_t = np.asarray(npz["action_mask_available_t"], dtype=np.bool_)

    if raw_obs_hwc.ndim != 4 or tuple(raw_obs_hwc.shape[1:]) != (24, 24, 27):
        raise RuntimeError(f"Unexpected raw observation shape: {raw_obs_hwc.shape}")
    if actions.ndim != 3 or tuple(actions.shape[1:]) != TARGET_ACTION_SHAPE:
        raise RuntimeError(f"Unexpected action shape: {actions.shape}")

    n = int(raw_obs_hwc.shape[0])
    raw_obs = raw_obs_hwc.reshape(n, 576, 27)
    adapted_obs = np.zeros((n, 576, 27), dtype=np.float32)

    unavailable_channels: List[int] = []
    channel_application: Dict[str, Any] = {}
    hard_failures: List[str] = []
    warnings: List[str] = []

    for t in range(27):
        if t not in by_target:
            hard_failures.append(f"missing mapping rule for target channel {t}")
            continue
        rec = by_target[t]
        info = _apply_channel_rule(adapted_obs, t, rec, raw_obs, actions, unavailable_channels)
        channel_application[str(t)] = info

    critical_ranges = {
        "owner": [2, 3, 4],
        "unit_type": [5, 6, 7, 8, 9, 10, 11],
        "current_action": [12, 13, 14, 15, 16, 17],
        "direction": [18, 19, 20, 21],
    }
    critical_unavailable = sorted(
        [
            c
            for c in unavailable_channels
            if any(c in r for r in critical_ranges.values())
        ]
    )

    if critical_unavailable and not bool(args.allow_critical_unavailable):
        hard_failures.append(
            "critical channels unavailable and allow-critical-unavailable=false: "
            + str(critical_unavailable)
        )

    has_nan = bool(np.isnan(adapted_obs).any())
    has_inf = bool(np.isinf(adapted_obs).any())
    if has_nan:
        hard_failures.append("adapted observations contain NaN")
    if has_inf:
        hard_failures.append("adapted observations contain Inf")

    adapted_dataset = run_dir / "adapted_dataset.npz"
    np.savez_compressed(
        adapted_dataset,
        observations=adapted_obs,
        actions=actions,
        episode_id=episode_id,
        step_id=step_id,
        reward_t=reward_t,
        done_t=done_t,
        terminated_t=terminated_t,
        truncated_t=truncated_t,
        action_mask_available_t=action_mask_available_t,
    )

    mapping_hash = _sha256(mapping_json)

    manifest = {
        "generated_at_utc": _now_iso(),
        "teacher_lineage": "legacy032",
        "observation_semantics_version": str(mapping.get("observation_semantics_version", "unknown")),
        "source_observation_semantics": "legacy032_raw_empirical",
        "target_observation_semantics": "unity_v2_runtime",
        "mapping_file": str(mapping_json),
        "mapping_file_hash": mapping_hash,
        "conversion_timestamp": _now_iso(),
        "observation_shape_per_sample": [576, 27],
        "action_shape_per_sample": [576, 7],
        "explicit_non_claims": [
            "No claim of exact Gym-microRTS to Unity semantic parity.",
            "No retraining/PPO/checkpoint mutation performed.",
            "No runtime semantic mutation in Unity ActionApplier/MatchManager."
        ],
        "critical_unavailable_channels": critical_unavailable,
        "unavailable_channels": sorted(unavailable_channels),
    }
    _json_dump(run_dir / "adapted_manifest.json", manifest)

    report = {
        "generated_at_utc": _now_iso(),
        "status": "success" if not hard_failures else "partial_success_with_hard_failures",
        "source_rollout_dir": str(raw_rollout_dir),
        "output_dir": str(run_dir),
        "mapping_file": str(mapping_json),
        "mapping_file_hash": mapping_hash,
        "observation_semantics_version": manifest["observation_semantics_version"],
        "source_observation_semantics": manifest["source_observation_semantics"],
        "target_observation_semantics": manifest["target_observation_semantics"],
        "sample_count": int(n),
        "raw_observation_shape": [int(x) for x in raw_obs_hwc.shape],
        "adapted_observation_shape": [int(x) for x in adapted_obs.shape],
        "actions_shape": [int(x) for x in actions.shape],
        "channels_applied_count": int(len(channel_application)),
        "channel_application": channel_application,
        "unavailable_channels": sorted(unavailable_channels),
        "critical_unavailable_channels": critical_unavailable,
        "adapted_has_nan": has_nan,
        "adapted_has_inf": has_inf,
        "adapted_min": float(np.min(adapted_obs)),
        "adapted_max": float(np.max(adapted_obs)),
        "warnings": warnings,
        "hard_failures": hard_failures,
    }

    _json_dump(run_dir / "observation_semantic_conversion_report.json", report)
    (run_dir / "observation_semantic_conversion_report.md").write_text(
        _build_markdown(report), encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "status": report["status"],
                "output_dir": str(run_dir),
                "adapted_dataset": str(adapted_dataset),
                "conversion_report_json": str(run_dir / "observation_semantic_conversion_report.json"),
                "conversion_report_md": str(run_dir / "observation_semantic_conversion_report.md"),
                "adapted_manifest": str(run_dir / "adapted_manifest.json"),
                "critical_unavailable_channels": critical_unavailable,
                "hard_failures_count": len(hard_failures),
            },
            ensure_ascii=True,
            indent=2,
        )
    )

    return 0 if not hard_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
