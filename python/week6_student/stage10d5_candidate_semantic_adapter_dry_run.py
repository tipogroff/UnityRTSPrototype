#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np


TARGET_ACTION_SHAPE = (576, 7)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


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


def _apply_channel_rule(out_obs: np.ndarray, t: int, rule: Dict[str, Any], raw_obs: np.ndarray, actions: np.ndarray) -> None:
    source = rule.get("source", {})
    st = source.get("type")

    if st == "raw_channel":
        out_obs[:, :, t] = raw_obs[:, :, int(source["index"])]
        return

    if st == "derived_action_type_one_hot":
        cls = int(source["class_index"])
        out_obs[:, :, t] = (actions[:, :, 0] == cls).astype(np.float32)
        return

    if st == "derived_direction_one_hot":
        cls = int(source["class_index"])
        out_obs[:, :, t] = (_build_direction_expected(actions) == cls).astype(np.float32)
        return

    if st == "derived_produce_type_one_hot":
        cls = int(source["class_index"])
        mapping = source.get("raw_produce_to_unity_map", {})
        action_type = actions[:, :, 0]
        produce_branch = actions[:, :, 5]
        mapped = np.full(produce_branch.shape, -1, dtype=np.int16)
        for k, v in mapping.items():
            mapped[produce_branch == int(k)] = int(v)
        out_obs[:, :, t] = ((action_type == 4) & (mapped == cls)).astype(np.float32)
        return

    if st == "derived_attack_target_scalar":
        action_type = actions[:, :, 0]
        attack_local = actions[:, :, 6].astype(np.float32)
        val = np.zeros_like(attack_local, dtype=np.float32)
        atk = action_type == 5
        val[atk] = (attack_local[atk] + 1.0) / 49.0
        np.clip(val, 0.0, 1.0, out=val)
        out_obs[:, :, t] = val
        return

    # unavailable or unknown -> explicit zero in dry-run
    out_obs[:, :, t] = 0.0


def _group_metrics(obs: np.ndarray, start: int, end: int) -> Dict[str, Any]:
    grp = obs[:, :, start:end]
    sums = np.sum(grp, axis=2)
    return {
        "sum_min": float(np.min(sums)),
        "sum_max": float(np.max(sums)),
        "share_sum_eq_1": float(np.mean(np.isclose(sums, 1.0))),
        "share_sum_eq_0": float(np.mean(np.isclose(sums, 0.0))),
        "share_sum_le_1": float(np.mean(sums <= 1.0 + 1e-6)),
        "binary_values_only": bool(np.all((grp == 0.0) | (grp == 1.0))),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.5 candidate semantic adapter dry-run")
    p.add_argument(
        "--raw-rollout-dir",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/teacher_rollouts/"
            "legacy032_3m_unity_v2_rollout_export_20260501T125015Z"
        ),
    )
    p.add_argument(
        "--candidate-mapping",
        type=Path,
        default=Path("python/week5_teacher_legacy032/observation_semantics/legacy032_to_unity_v2_observation_mapping.stage10d5_candidate.json"),
    )
    p.add_argument("--sample-count", type=int, default=4096)
    p.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d5_candidate_semantic_adapter_dry_run.json"),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = _repo_root()
    raw_dir = _resolve(root, args.raw_rollout_dir)
    mapping_path = _resolve(root, args.candidate_mapping)
    out_path = _resolve(root, args.output)

    npz_path = raw_dir / "teacher_rollout_raw.npz"
    if not npz_path.exists():
        raise RuntimeError(f"missing rollout npz: {npz_path}")
    if not mapping_path.exists():
        raise RuntimeError(f"missing candidate mapping: {mapping_path}")

    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    by_target = {int(rec["target_channel"]): rec for rec in mapping.get("channels", [])}

    with np.load(npz_path, allow_pickle=False) as npz:
        obs_hwc = np.asarray(npz["observation_t"], dtype=np.float32)
        actions = np.asarray(npz["per_cell_action_t"], dtype=np.int16)

    n = min(int(args.sample_count), int(obs_hwc.shape[0]))
    raw_obs = obs_hwc[:n].reshape(n, 576, 27)
    actions = actions[:n]

    if actions.ndim != 3 or tuple(actions.shape[1:]) != TARGET_ACTION_SHAPE:
        raise RuntimeError(f"unexpected action shape: {actions.shape}")

    adapted = np.zeros((n, 576, 27), dtype=np.float32)
    for t in range(27):
        rule = by_target.get(t)
        if rule is None:
            continue
        _apply_channel_rule(adapted, t, rule, raw_obs, actions)

    owner = _group_metrics(adapted, 2, 5)
    unit = _group_metrics(adapted, 5, 12)

    action_type = actions[:, :, 0]
    worker_mask = action_type == 2  # harvest proxy
    base_mask = action_type == 4    # produce proxy

    unit_grp = adapted[:, :, 5:12]

    worker_mean = np.mean(unit_grp[worker_mask], axis=0) if np.any(worker_mask) else np.zeros((7,), dtype=np.float32)
    base_mean = np.mean(unit_grp[base_mask], axis=0) if np.any(base_mask) else np.zeros((7,), dtype=np.float32)

    worker_peak = int(np.argmax(worker_mean)) if np.any(worker_mean) else -1
    base_peak = int(np.argmax(base_mean)) if np.any(base_mean) else -1

    resource_ranged_multihot = np.logical_and(np.isclose(unit_grp[:, :, 0], 1.0), np.isclose(unit_grp[:, :, 6], 1.0))
    impossible_share = float(np.mean(resource_ranged_multihot))

    checks = {
        "owner_one_hot_or_zero": bool(owner["share_sum_le_1"] >= 0.999999),
        "unit_type_one_hot_or_zero": bool(unit["share_sum_le_1"] >= 0.999999),
        "worker_harvest_proxy_peak_at_unity_worker_index3": bool(worker_peak == 3),
        "base_produce_proxy_peak_at_unity_base_index1_or_barracks_index2": bool(base_peak in {1, 2}),
        "no_resource_plus_ranged_multihot": bool(impossible_share == 0.0),
    }

    status = "pass" if all(checks.values()) else "fail"

    out: Dict[str, Any] = {
        "stage": "10D.5",
        "diagnostic": "candidate_semantic_adapter_dry_run",
        "status": status,
        "sample_count": int(n),
        "candidate_mapping": mapping_path.as_posix(),
        "group_metrics": {
            "owner": owner,
            "unit_type": unit,
        },
        "actor_label_proxy_compatibility": {
            "worker_harvest_proxy": {
                "count": int(np.count_nonzero(worker_mask)),
                "unit_type_mean": [float(v) for v in worker_mean.tolist()],
                "expected_unity_peak_index": 3,
                "peak_index": worker_peak,
                "compatible": bool(worker_peak == 3),
            },
            "base_produce_proxy": {
                "count": int(np.count_nonzero(base_mask)),
                "unit_type_mean": [float(v) for v in base_mean.tolist()],
                "expected_unity_peak_index": 1,
                "peak_index": base_peak,
                "compatible": bool(base_peak in {1, 2}),
            },
        },
        "impossible_patterns": {
            "resource_plus_ranged_multihot_share": impossible_share,
        },
        "checks": checks,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=True, indent=2), encoding="utf-8")
    print(out_path.as_posix())
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
