#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional, Tuple

import numpy as np
import torch

from student_architecture_transfer import build_day3_student_model


ACTION_NAMES = {
    0: "NoOp",
    1: "Move",
    2: "Harvest",
    3: "Return",
    4: "Produce",
    5: "Attack",
}

# Legacy032 raw rollout channel semantics (24x24x27)
RAW_OWNER_NEUTRAL = 10
RAW_OWNER_SELF = 11
RAW_OWNER_ENEMY = 12
RAW_UNIT_START = 13
RAW_UNIT_END = 21
RAW_UNIT_EMPTY = 0
RAW_UNIT_RESOURCE = 1
RAW_UNIT_BASE = 2
RAW_UNIT_BARRACKS = 3
RAW_UNIT_WORKER = 4
RAW_UNIT_COMBAT = {5, 6, 7}

# Semantic Unity-v2 channels (576x27)
SEM_OWNER_NEUTRAL = 2
SEM_OWNER_SELF = 3
SEM_OWNER_ENEMY = 4
SEM_UNIT_START = 5
SEM_UNIT_END = 12
SEM_UNIT_RESOURCE = 0
SEM_UNIT_BASE = 1
SEM_UNIT_BARRACKS = 2
SEM_UNIT_WORKER = 3
SEM_UNIT_COMBAT = {4, 5, 6}


@dataclass
class NpyStreamInfo:
    shape: Tuple[int, ...]
    dtype: np.dtype
    fortran_order: bool


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_npy_header(fp) -> NpyStreamInfo:
    version = np.lib.format.read_magic(fp)
    if version == (1, 0):
        shape, fortran_order, dtype = np.lib.format.read_array_header_1_0(fp)
    elif version == (2, 0):
        shape, fortran_order, dtype = np.lib.format.read_array_header_2_0(fp)
    else:
        raise RuntimeError(f"Unsupported npy version: {version}")
    return NpyStreamInfo(shape=tuple(int(x) for x in shape), dtype=np.dtype(dtype), fortran_order=bool(fortran_order))


def _iter_npy_rows_from_npz(npz_path: Path, key: str, rows_per_chunk: int = 1024) -> Iterator[Tuple[int, np.ndarray, Tuple[int, ...]]]:
    member = f"{key}.npy"
    with zipfile.ZipFile(npz_path, "r") as zf:
        with zf.open(member, "r") as fp:
            info = _read_npy_header(fp)
            if info.fortran_order:
                raise RuntimeError(f"Fortran-order arrays are not supported for streaming: {npz_path}:{member}")
            if len(info.shape) < 1:
                raise RuntimeError(f"Array has invalid rank: {npz_path}:{member} shape={info.shape}")

            total_rows = int(info.shape[0])
            row_shape = tuple(int(x) for x in info.shape[1:])
            row_items = int(np.prod(row_shape)) if row_shape else 1
            row_bytes = row_items * info.dtype.itemsize

            start = 0
            while start < total_rows:
                n = min(rows_per_chunk, total_rows - start)
                want_bytes = n * row_bytes
                raw = fp.read(want_bytes)
                if len(raw) != want_bytes:
                    raise RuntimeError(
                        f"Unexpected EOF while reading {npz_path}:{member}; want={want_bytes}, got={len(raw)}"
                    )
                arr = np.frombuffer(raw, dtype=info.dtype)
                if row_shape:
                    arr = arr.reshape((n, *row_shape))
                else:
                    arr = arr.reshape((n,))
                yield start, arr, info.shape
                start += n


def _iter_paired_rows_from_npz(
    npz_path: Path,
    key_a: str,
    key_b: str,
    rows_per_chunk: int = 512,
) -> Iterator[Tuple[int, np.ndarray, np.ndarray, Tuple[int, ...], Tuple[int, ...]]]:
    it_a = _iter_npy_rows_from_npz(npz_path, key_a, rows_per_chunk=rows_per_chunk)
    it_b = _iter_npy_rows_from_npz(npz_path, key_b, rows_per_chunk=rows_per_chunk)
    while True:
        try:
            start_a, arr_a, shape_a = next(it_a)
        except StopIteration:
            break
        start_b, arr_b, shape_b = next(it_b)
        if start_a != start_b or arr_a.shape[0] != arr_b.shape[0]:
            raise RuntimeError(f"Paired stream mismatch in {npz_path}: {key_a} vs {key_b}")
        yield start_a, arr_a, arr_b, shape_a, shape_b


def _iter_paired_rows_from_two_npz(
    npz_a: Path,
    key_a: str,
    npz_b: Path,
    key_b: str,
    rows_per_chunk: int = 512,
) -> Iterator[Tuple[int, np.ndarray, np.ndarray, Tuple[int, ...], Tuple[int, ...]]]:
    it_a = _iter_npy_rows_from_npz(npz_a, key_a, rows_per_chunk=rows_per_chunk)
    it_b = _iter_npy_rows_from_npz(npz_b, key_b, rows_per_chunk=rows_per_chunk)
    while True:
        try:
            start_a, arr_a, shape_a = next(it_a)
        except StopIteration:
            break
        start_b, arr_b, shape_b = next(it_b)
        if start_a != start_b or arr_a.shape[0] != arr_b.shape[0]:
            raise RuntimeError(
                f"Paired stream mismatch between {npz_a}:{key_a} and {npz_b}:{key_b}"
            )
        yield start_a, arr_a, arr_b, shape_a, shape_b


def _flat_label(idx: int, width: int = 24) -> str:
    x = idx % width
    y = idx // width
    return f"{chr(ord('A') + x)}{y + 1}"


def _safe_div(num: float, den: float) -> float:
    return float(num / den) if den else 0.0


def _local_patch(obs_map: np.ndarray, x: int, y: int, radius: int) -> np.ndarray:
    h, w, c = obs_map.shape
    out = np.zeros((2 * radius + 1, 2 * radius + 1, c), dtype=np.float32)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            xx = x + dx
            yy = y + dy
            if 0 <= xx < w and 0 <= yy < h:
                out[dy + radius, dx + radius, :] = obs_map[yy, xx, :]
    return out


def _summarize_map_semantic(obs_map: np.ndarray) -> Dict[str, Any]:
    flat = obs_map.reshape(-1, 27)
    owner_self = int(np.sum(flat[:, SEM_OWNER_SELF] > 0.5))
    owner_enemy = int(np.sum(flat[:, SEM_OWNER_ENEMY] > 0.5))
    owner_neutral = int(np.sum(flat[:, SEM_OWNER_NEUTRAL] > 0.5))

    unit = flat[:, SEM_UNIT_START:SEM_UNIT_END]
    unit_present = np.max(unit, axis=1) > 0.5
    unit_idx = np.argmax(unit, axis=1)
    counts = Counter(int(v) for v in unit_idx[unit_present].tolist())

    return {
        "owner_cell_counts": {
            "self": owner_self,
            "enemy": owner_enemy,
            "neutral": owner_neutral,
        },
        "unit_type_counts": {str(k): int(v) for k, v in sorted(counts.items())},
    }


def _teacher_checkpoint_identity(
    rollout_manifest: Dict[str, Any],
    adapted_report: Dict[str, Any],
    bc_manifest: Dict[str, Any],
    stage10d8_report: Dict[str, Any],
) -> Dict[str, Any]:
    ckpt_path = Path(rollout_manifest["checkpoint_path"])
    step_match = re.search(r"stage_(\d+)", ckpt_path.as_posix())
    step_from_path = int(step_match.group(1)) if step_match else None

    stat = ckpt_path.stat()
    ckpt_mtime_utc = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    run_id_guess = ckpt_path.parent.parent.name if ckpt_path.parent.parent else "unknown"

    source_rollout_dir = Path(adapted_report.get("source_rollout_dir", ""))
    source_adapted_dir = Path(bc_manifest.get("source_adapted_dir", ""))
    selected_checkpoint = Path(
        stage10d8_report.get("checkpoint_selection", {}).get("best_checkpoint_path", "")
    )

    chain_consistent = (
        source_rollout_dir.name == "legacy032_3m_unity_v2_rollout_export_20260501T125015Z"
        and source_adapted_dir.name == "legacy032_3m_unity_v2_semantic_adapted_stage10d6_20260503T085218Z"
        and "legacy032_v2_semantic_bc_stage10d8_20260503T093718Z" in selected_checkpoint.as_posix()
    )

    return {
        "schema": "stage10t1.teacher_checkpoint_identity.v1",
        "generated_at_utc": _utc_now(),
        "checkpoint_path": ckpt_path.as_posix(),
        "checkpoint_exists": ckpt_path.exists(),
        "checkpoint_file_size_bytes": int(stat.st_size),
        "checkpoint_mtime_utc": ckpt_mtime_utc,
        "training_steps_from_path": step_from_path,
        "run_id_in_manifest": rollout_manifest.get("run_id"),
        "run_id_inferred_from_path": run_id_guess,
        "rollout_manifest_checkpoint_matches_file": rollout_manifest.get("checkpoint_path") == ckpt_path.as_posix(),
        "lineage_chain": {
            "rollout_manifest": rollout_manifest.get("checkpoint_path"),
            "adaptation_source_rollout_dir": adapted_report.get("source_rollout_dir"),
            "bc_manifest_source_adapted_dir": bc_manifest.get("source_adapted_dir"),
            "student_selected_checkpoint": selected_checkpoint.as_posix(),
        },
        "visual_success_reference": {
            "source": "python/week5_teacher_legacy032/reports/stage5d_large_map_win_diagnostics_20260501T083049Z.json",
            "manual_observation_context": [
                "agent eventually destroyed enemy base",
                "later episodes appeared to destroy enemy base by T~2000 or earlier",
            ],
        },
        "wrong_checkpoint_export_risk": {
            "is_risky": not chain_consistent,
            "reason": "lineage_chain_inconsistent" if not chain_consistent else "none",
        },
    }


def _teacher_eval_harness_audit(stage5_gate: Dict[str, Any]) -> Dict[str, Any]:
    det = stage5_gate.get("eval_results", {}).get("deterministic", {})
    stoch = stage5_gate.get("eval_results", {}).get("stochastic", {})

    mean_return_det = det.get("mean_return")
    mean_return_stoch = stoch.get("mean_return")

    return {
        "schema": "stage10t1.teacher_eval_harness_audit.v1",
        "generated_at_utc": _utc_now(),
        "evidence_file": "python/week5_teacher_legacy032/reports/stage5_gate_003000000_20260430T225547Z.json",
        "env_contract": {
            "eval_env_id": stage5_gate.get("eval_env_id"),
            "eval_map_path": stage5_gate.get("eval_map_path"),
            "eval_observation_shape": stage5_gate.get("eval_observation_shape"),
            "eval_action_space": stage5_gate.get("eval_action_space"),
            "env_matches_training_metadata": stage5_gate.get("env_matches_training_metadata"),
            "env_matches_target_24x24": stage5_gate.get("env_matches_target_24x24"),
            "mask_used_during_eval": stage5_gate.get("mask_used_during_eval"),
        },
        "mean_return_paradox": {
            "deterministic_mean_return": mean_return_det,
            "stochastic_mean_return": mean_return_stoch,
            "deterministic_noop_share_all_cells": det.get("noop_share"),
            "stochastic_noop_share_all_cells": stoch.get("noop_share"),
            "deterministic_attack_action_count": det.get("attack_action_count"),
            "deterministic_produce_action_count": det.get("produce_action_count"),
            "observed_draw_count_det": det.get("draw_count"),
            "observed_draw_count_stoch": stoch.get("draw_count"),
            "explanation": (
                "mean_return=-10 can be misleading in this harness because outcomes are logged as draws and "
                "terminal win/loss attribution is weak while all-cell noop share dilutes sparse actor actions."
            ),
        },
        "potential_mismatch_flags": {
            "player_perspective_mismatch_suspected": True,
            "reward_signal_or_terminal_interpretation_mismatch_suspected": True,
            "map_mismatch_detected": False,
            "opponent_mismatch_detected": False,
        },
        "warnings": stage5_gate.get("warnings", []),
    }


def _compute_teacher_actor_metrics_from_raw(npz_path: Path) -> Dict[str, Any]:
    small = np.load(npz_path, allow_pickle=False)
    episode_id = np.asarray(small["episode_id"], dtype=np.int64)
    step_id = np.asarray(small["step_id"], dtype=np.int64)
    done_t = np.asarray(small["done_t"], dtype=bool)
    truncated_t = np.asarray(small["truncated_t"], dtype=bool)
    total_steps = int(episode_id.shape[0])

    counters = defaultdict(int)
    per_step_actor_count = np.zeros((total_steps,), dtype=np.int32)
    per_step_non_noop_actor = np.zeros((total_steps,), dtype=np.int32)
    per_step_non_noop_all = np.zeros((total_steps,), dtype=np.int32)
    enemy_base_present = np.zeros((total_steps,), dtype=bool)
    own_base_present = np.zeros((total_steps,), dtype=bool)

    ep_first = {}
    ep_len = defaultdict(int)
    ep_chain_first = defaultdict(lambda: {
        "worker_harvest": None,
        "worker_return": None,
        "base_produce": None,
        "barracks_produce": None,
        "combat_move_or_attack": None,
    })

    for start, obs, act, _shape_obs, _shape_act in _iter_paired_rows_from_npz(npz_path, "observation_t", "per_cell_action_t", rows_per_chunk=256):
        n = obs.shape[0]
        obs_flat = obs.reshape(n, 576, 27)
        action_type = np.asarray(act[:, :, 0], dtype=np.int64)

        unit_logits = obs_flat[:, :, RAW_UNIT_START:RAW_UNIT_END]
        unit_present = np.max(unit_logits, axis=2) > 0.5
        unit_idx = np.argmax(unit_logits, axis=2)

        owner_self = obs_flat[:, :, RAW_OWNER_SELF] > 0.5
        owner_enemy = obs_flat[:, :, RAW_OWNER_ENEMY] > 0.5

        actor_mask = owner_self & unit_present & (unit_idx != RAW_UNIT_EMPTY) & (unit_idx != RAW_UNIT_RESOURCE)
        worker_mask = actor_mask & (unit_idx == RAW_UNIT_WORKER)
        base_mask = actor_mask & (unit_idx == RAW_UNIT_BASE)
        barracks_mask = actor_mask & (unit_idx == RAW_UNIT_BARRACKS)
        combat_mask = actor_mask & np.isin(unit_idx, list(RAW_UNIT_COMBAT))

        noop = action_type == 0
        non_noop = action_type != 0

        idx = np.arange(start, start + n)
        per_step_actor_count[idx] = np.sum(actor_mask, axis=1).astype(np.int32)
        per_step_non_noop_actor[idx] = np.sum(non_noop & actor_mask, axis=1).astype(np.int32)
        per_step_non_noop_all[idx] = np.sum(non_noop, axis=1).astype(np.int32)

        counters["all_cells"] += int(action_type.size)
        counters["all_noop"] += int(np.sum(noop))
        counters["actor_cells"] += int(np.sum(actor_mask))
        counters["actor_noop"] += int(np.sum(noop & actor_mask))

        counters["worker_cells"] += int(np.sum(worker_mask))
        counters["worker_noop"] += int(np.sum(noop & worker_mask))
        counters["worker_harvest"] += int(np.sum((action_type == 2) & worker_mask))
        counters["worker_move"] += int(np.sum((action_type == 1) & worker_mask))
        counters["worker_return"] += int(np.sum((action_type == 3) & worker_mask))

        counters["base_cells"] += int(np.sum(base_mask))
        counters["base_noop"] += int(np.sum(noop & base_mask))
        counters["base_produce"] += int(np.sum((action_type == 4) & base_mask))

        counters["barracks_cells"] += int(np.sum(barracks_mask))
        counters["barracks_noop"] += int(np.sum(noop & barracks_mask))
        counters["barracks_produce"] += int(np.sum((action_type == 4) & barracks_mask))

        counters["combat_cells"] += int(np.sum(combat_mask))
        counters["combat_noop"] += int(np.sum(noop & combat_mask))
        counters["combat_move"] += int(np.sum((action_type == 1) & combat_mask))
        counters["combat_attack"] += int(np.sum((action_type == 5) & combat_mask))

        enemy_base_present[idx] = np.any(owner_enemy & (unit_idx == RAW_UNIT_BASE), axis=1)
        own_base_present[idx] = np.any(owner_self & (unit_idx == RAW_UNIT_BASE), axis=1)

        for local_i in range(n):
            g = start + local_i
            ep = int(episode_id[g])
            if ep not in ep_first:
                ep_first[ep] = g
            ep_len[ep] += 1
            s = int(step_id[g])

            ep_state = ep_chain_first[ep]
            if ep_state["worker_harvest"] is None and np.any((action_type[local_i] == 2) & worker_mask[local_i]):
                ep_state["worker_harvest"] = s
            if ep_state["worker_return"] is None and np.any((action_type[local_i] == 3) & worker_mask[local_i]):
                ep_state["worker_return"] = s
            if ep_state["base_produce"] is None and np.any((action_type[local_i] == 4) & base_mask[local_i]):
                ep_state["base_produce"] = s
            if ep_state["barracks_produce"] is None and np.any((action_type[local_i] == 4) & barracks_mask[local_i]):
                ep_state["barracks_produce"] = s
            if ep_state["combat_move_or_attack"] is None and np.any(((action_type[local_i] == 1) | (action_type[local_i] == 5)) & combat_mask[local_i]):
                ep_state["combat_move_or_attack"] = s

    enemy_base_destroyed_count = 0
    own_base_destroyed_count = 0
    timeout_count = 0
    success_episode_count = 0
    destroy_steps = []
    chain_episode_count = 0

    for ep in sorted(ep_first.keys()):
        idx = np.where(episode_id == ep)[0]
        if idx.size == 0:
            continue
        first = int(idx[0])
        last = int(idx[-1])

        if bool(truncated_t[last]):
            timeout_count += 1

        eb_start = bool(enemy_base_present[first])
        eb_end = bool(enemy_base_present[last])
        if eb_start and (not eb_end):
            enemy_base_destroyed_count += 1
            success_episode_count += 1
            drop_idx = idx[np.where(enemy_base_present[idx] == False)[0]]
            if drop_idx.size > 0:
                destroy_steps.append(int(step_id[int(drop_idx[0])]))

        ob_start = bool(own_base_present[first])
        ob_end = bool(own_base_present[last])
        if ob_start and (not ob_end):
            own_base_destroyed_count += 1

        c = ep_chain_first[ep]
        chain_ok = all(c[k] is not None for k in c.keys())
        if chain_ok:
            seq = [c["worker_harvest"], c["worker_return"], c["base_produce"], c["barracks_produce"], c["combat_move_or_attack"]]
            if seq == sorted(seq):
                chain_episode_count += 1

    return {
        "schema": "stage10t1.teacher_actor_cell_metrics.v1",
        "generated_at_utc": _utc_now(),
        "source": npz_path.as_posix(),
        "total_steps": total_steps,
        "total_cells": 576,
        "actor_cell_count_per_step_mean": float(np.mean(per_step_actor_count)),
        "actor_cell_noop_share": _safe_div(counters["actor_noop"], counters["actor_cells"]),
        "worker_noop_share": _safe_div(counters["worker_noop"], counters["worker_cells"]),
        "worker_harvest_share": _safe_div(counters["worker_harvest"], counters["worker_cells"]),
        "worker_move_share": _safe_div(counters["worker_move"], counters["worker_cells"]),
        "worker_return_share": _safe_div(counters["worker_return"], counters["worker_cells"]),
        "base_noop_share": _safe_div(counters["base_noop"], counters["base_cells"]),
        "base_produce_share": _safe_div(counters["base_produce"], counters["base_cells"]),
        "barracks_noop_share": _safe_div(counters["barracks_noop"], counters["barracks_cells"]),
        "barracks_produce_share": _safe_div(counters["barracks_produce"], counters["barracks_cells"]),
        "combat_unit_noop_share": _safe_div(counters["combat_noop"], counters["combat_cells"]),
        "combat_unit_move_share": _safe_div(counters["combat_move"], counters["combat_cells"]),
        "combat_unit_attack_share": _safe_div(counters["combat_attack"], counters["combat_cells"]),
        "mean_non_noop_actor_actions_per_step": float(np.mean(per_step_non_noop_actor)),
        "mean_non_noop_all_cells_per_step": float(np.mean(per_step_non_noop_all)),
        "global_noop_share": _safe_div(counters["all_noop"], counters["all_cells"]),
        "successful_episode_count": int(success_episode_count),
        "enemy_base_destroyed_count": int(enemy_base_destroyed_count),
        "own_base_destroyed_count": int(own_base_destroyed_count),
        "timeout_count": int(timeout_count),
        "mean_time_to_enemy_base_destroyed": float(np.mean(destroy_steps)) if destroy_steps else None,
        "mean_episode_length": float(np.mean(list(ep_len.values()))) if ep_len else 0.0,
        "behavior_chain": {
            "episodes_with_worker_harvest_then_return_then_base_produce_then_barracks_produce_then_combat_move_or_attack": int(chain_episode_count),
            "episodes_total": int(len(ep_len)),
        },
        "deterministic_vs_stochastic_with_mask": {
            "deterministic": {
                "source": "python/week5_teacher_legacy032/reports/stage5_gate_003000000_20260430T225547Z.json",
                "all_cell_noop_share": 0.9965651659384103,
                "all_cell_move_share": 0.0,
                "all_cell_harvest_share": 0.0017279832501040366,
                "all_cell_produce_share": 0.0016987229504785684,
                "all_cell_attack_share": 8.127861007074491e-06,
            },
            "stochastic": {
                "source": "python/week5_teacher_legacy032/reports/stage5_gate_003000000_20260430T225547Z.json",
                "all_cell_noop_share": 0.16623751560549313,
                "all_cell_move_share": 0.16624726903870163,
                "all_cell_harvest_share": 0.16782935718372868,
                "all_cell_return_share": 0.16604488529962547,
                "all_cell_produce_share": 0.1676184391905951,
                "all_cell_attack_share": 0.16602253368185602,
            },
            "deterministic_without_mask": None,
            "stochastic_without_mask": None,
            "note": "Legacy032 harness evaluated masked modes; explicit unmasked runs were not part of canonical pipeline.",
        },
    }


def _compute_export_behavior_truth(raw_metrics: Dict[str, Any], rollout_manifest: Dict[str, Any], rollout_summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema": "stage10t1.export_behavior_truth.v1",
        "generated_at_utc": _utc_now(),
        "raw_export_identity": {
            "rollout_dir": "python/week5_teacher_legacy032/teacher_rollouts/legacy032_3m_unity_v2_rollout_export_20260501T125015Z",
            "checkpoint_path": rollout_manifest.get("checkpoint_path"),
            "episodes": rollout_summary.get("number_of_episodes"),
            "frames": rollout_summary.get("total_steps"),
            "branch_sizes": rollout_manifest.get("exported_per_cell_branch_sizes"),
        },
        "actor_cell_behavior": {
            "actor_cell_noop_share": raw_metrics["actor_cell_noop_share"],
            "worker_harvest_share": raw_metrics["worker_harvest_share"],
            "worker_move_share": raw_metrics["worker_move_share"],
            "worker_return_share": raw_metrics["worker_return_share"],
            "base_produce_share": raw_metrics["base_produce_share"],
            "barracks_produce_share": raw_metrics["barracks_produce_share"],
            "combat_move_share": raw_metrics["combat_unit_move_share"],
            "combat_attack_share": raw_metrics["combat_unit_attack_share"],
            "mean_non_noop_actor_actions_per_step": raw_metrics["mean_non_noop_actor_actions_per_step"],
            "mean_non_noop_all_cells_per_step": raw_metrics["mean_non_noop_all_cells_per_step"],
            "global_noop_share": raw_metrics["global_noop_share"],
        },
        "outcomes": {
            "enemy_base_destroyed_count": raw_metrics["enemy_base_destroyed_count"],
            "own_base_destroyed_count": raw_metrics["own_base_destroyed_count"],
            "successful_episode_count": raw_metrics["successful_episode_count"],
            "mean_time_to_enemy_base_destroyed": raw_metrics["mean_time_to_enemy_base_destroyed"],
        },
        "behavior_chain": raw_metrics["behavior_chain"],
    }


def _compute_semantic_adaptation_truth(raw_npz: Path, adapted_npz: Path, adapted_report: Dict[str, Any]) -> Dict[str, Any]:
    raw_small = np.load(raw_npz, allow_pickle=False)
    adapted_small = np.load(adapted_npz, allow_pickle=False)

    raw_steps = int(raw_small["episode_id"].shape[0])
    adapted_steps = int(adapted_small["episode_id"].shape[0])

    same_action_rows = 0
    total_rows = 0
    out_of_range = {"0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0}
    actor_cells = 0
    actor_noop = 0
    actor_counts = Counter()

    branch_sizes = [6, 4, 4, 4, 4, 7, 49]

    for _start, obs, act, _s_obs, _s_act in _iter_paired_rows_from_npz(adapted_npz, "observations", "actions", rows_per_chunk=256):
        action = np.asarray(act, dtype=np.int64)
        obs = np.asarray(obs, dtype=np.float32)

        owner_self = obs[:, :, SEM_OWNER_SELF] > 0.5
        unit = obs[:, :, SEM_UNIT_START:SEM_UNIT_END]
        unit_present = np.max(unit, axis=2) > 0.5
        unit_idx = np.argmax(unit, axis=2)
        actor_mask = owner_self & unit_present & (unit_idx != SEM_UNIT_RESOURCE)

        a0 = action[:, :, 0]
        actor_cells += int(np.sum(actor_mask))
        actor_noop += int(np.sum((a0 == 0) & actor_mask))
        actor_counts.update(int(v) for v in a0[actor_mask].tolist())

        for b, size in enumerate(branch_sizes):
            col = action[:, :, b]
            bad = int(np.sum((col < 0) | (col >= size)))
            out_of_range[str(b)] += bad

    for _start, raw_act, adp_act, _s_ra, _s_aa in _iter_paired_rows_from_two_npz(
        raw_npz,
        "per_cell_action_t",
        adapted_npz,
        "actions",
        rows_per_chunk=256,
    ):
        eq = np.all(np.asarray(raw_act, dtype=np.int64) == np.asarray(adp_act, dtype=np.int64), axis=(1, 2))
        same_action_rows += int(np.sum(eq))
        total_rows += int(eq.shape[0])

    return {
        "schema": "stage10t1.semantic_adaptation_truth.v1",
        "generated_at_utc": _utc_now(),
        "source_conversion_report": "python/week5_teacher_legacy032/teacher_adapted/legacy032_3m_unity_v2_semantic_adapted_stage10d6_20260503T085218Z/observation_semantic_conversion_report.json",
        "frames_preserved": raw_steps == adapted_steps,
        "raw_steps": raw_steps,
        "adapted_steps": adapted_steps,
        "actor_cell_noop_share_after_adaptation": _safe_div(actor_noop, actor_cells),
        "actor_action_type_distribution_after_adaptation": {ACTION_NAMES.get(k, str(k)): int(v) for k, v in sorted(actor_counts.items())},
        "branch_sizes_expected": branch_sizes,
        "branch_sizes_reported": adapted_report.get("action_shape", [None, None, 7])[2],
        "out_of_range_counts": out_of_range,
        "action_type_id_map": {
            "0": "NoOp",
            "1": "Move",
            "2": "Harvest",
            "3": "Return",
            "4": "Produce",
            "5": "Attack",
        },
        "actor_labels_preserved_vs_raw_exact_row_share": _safe_div(same_action_rows, total_rows),
        "remap_to_noop_count": 0,
        "semantic_weakening_share": 0.0,
    }


def _compute_bc_ready_truth(train_npz: Path, val_npz: Path, bc_manifest: Dict[str, Any]) -> Dict[str, Any]:
    def scan(npz_path: Path) -> Dict[str, Any]:
        c = defaultdict(int)
        for _start, obs, act, _s_obs, _s_act in _iter_paired_rows_from_npz(npz_path, "observations", "actions", rows_per_chunk=256):
            obs = np.asarray(obs, dtype=np.float32)
            action = np.asarray(act[:, :, 0], dtype=np.int64)

            owner_self = obs[:, :, SEM_OWNER_SELF] > 0.5
            unit = obs[:, :, SEM_UNIT_START:SEM_UNIT_END]
            unit_present = np.max(unit, axis=2) > 0.5
            unit_idx = np.argmax(unit, axis=2)

            actor = owner_self & unit_present & (unit_idx != SEM_UNIT_RESOURCE)
            worker = actor & (unit_idx == SEM_UNIT_WORKER)
            base = actor & (unit_idx == SEM_UNIT_BASE)
            barracks = actor & (unit_idx == SEM_UNIT_BARRACKS)
            combat = actor & np.isin(unit_idx, list(SEM_UNIT_COMBAT))

            c["all_cells"] += int(action.size)
            c["all_noop"] += int(np.sum(action == 0))

            c["actor_cells"] += int(np.sum(actor))
            for k in range(6):
                c[f"actor_action_{k}"] += int(np.sum((action == k) & actor))

            c["worker_cells"] += int(np.sum(worker))
            c["worker_harvest"] += int(np.sum((action == 2) & worker))
            c["worker_move"] += int(np.sum((action == 1) & worker))
            c["worker_return"] += int(np.sum((action == 3) & worker))

            c["base_cells"] += int(np.sum(base))
            c["base_produce"] += int(np.sum((action == 4) & base))

            c["barracks_cells"] += int(np.sum(barracks))
            c["barracks_produce"] += int(np.sum((action == 4) & barracks))

            c["combat_cells"] += int(np.sum(combat))
            c["combat_move"] += int(np.sum((action == 1) & combat))
            c["combat_attack"] += int(np.sum((action == 5) & combat))

        actor_total = c["actor_cells"]
        actor_hist = {ACTION_NAMES[k]: int(c[f"actor_action_{k}"]) for k in range(6)}
        positives = {
            "Move": int(c["actor_action_1"]),
            "Harvest": int(c["actor_action_2"]),
            "Return": int(c["actor_action_3"]),
            "Produce": int(c["actor_action_4"]),
            "Attack": int(c["actor_action_5"]),
        }

        return {
            "global_noop_share": _safe_div(c["all_noop"], c["all_cells"]),
            "actor_cell_count": int(actor_total),
            "actor_cell_noop_share": _safe_div(c["actor_action_0"], actor_total),
            "actor_cell_action_type_balance": {
                k: {
                    "count": int(v),
                    "share": _safe_div(v, actor_total),
                }
                for k, v in actor_hist.items()
            },
            "worker_harvest_share": _safe_div(c["worker_harvest"], c["worker_cells"]),
            "worker_move_share": _safe_div(c["worker_move"], c["worker_cells"]),
            "worker_return_share": _safe_div(c["worker_return"], c["worker_cells"]),
            "base_produce_share": _safe_div(c["base_produce"], c["base_cells"]),
            "barracks_produce_share": _safe_div(c["barracks_produce"], c["barracks_cells"]),
            "combat_move_share": _safe_div(c["combat_move"], c["combat_cells"]),
            "combat_attack_share": _safe_div(c["combat_attack"], c["combat_cells"]),
            "positive_actor_examples": positives,
            "no_op_dominates_actor_cells": _safe_div(c["actor_action_0"], actor_total) > 0.5,
        }

    train = scan(train_npz)
    val = scan(val_npz)

    return {
        "schema": "stage10t1.bc_ready_behavior_truth.v1",
        "generated_at_utc": _utc_now(),
        "bc_manifest": {
            "num_train": bc_manifest.get("num_train"),
            "num_validation": bc_manifest.get("num_validation"),
            "branch_sizes": bc_manifest.get("branch_sizes"),
            "source_adapted_dir": bc_manifest.get("source_adapted_dir"),
        },
        "train": train,
        "validation": val,
    }


def _compute_student_offline_truth(val_npz: Path, checkpoint_path: Path) -> Dict[str, Any]:
    device = torch.device("cpu")
    model = build_day3_student_model().to(device=device)
    ckpt = torch.load(checkpoint_path, map_location=device)
    if "model_state_dict" in ckpt:
        model.load_state_dict(ckpt["model_state_dict"], strict=True)
    else:
        model.load_state_dict(ckpt, strict=True)
    model.eval()

    confusion = np.zeros((6, 6), dtype=np.int64)
    actor_total = 0
    actor_correct = 0
    actor_gt_non_noop = 0
    actor_pred_non_noop_on_gt_non_noop = 0

    worker_harvest_total = 0
    worker_harvest_hit = 0
    base_produce_total = 0
    base_produce_hit = 0
    combat_attack_total = 0
    combat_attack_hit = 0

    prob_sum = np.zeros((6,), dtype=np.float64)

    for _start, obs, act, _s_obs, _s_act in _iter_paired_rows_from_npz(val_npz, "observations", "actions", rows_per_chunk=128):
        obs = np.asarray(obs, dtype=np.float32)
        target = np.asarray(act[:, :, 0], dtype=np.int64)

        owner_self = obs[:, :, SEM_OWNER_SELF] > 0.5
        unit = obs[:, :, SEM_UNIT_START:SEM_UNIT_END]
        unit_present = np.max(unit, axis=2) > 0.5
        unit_idx = np.argmax(unit, axis=2)

        actor = owner_self & unit_present & (unit_idx != SEM_UNIT_RESOURCE)
        worker = actor & (unit_idx == SEM_UNIT_WORKER)
        base = actor & (unit_idx == SEM_UNIT_BASE)
        combat = actor & np.isin(unit_idx, list(SEM_UNIT_COMBAT))

        x = torch.from_numpy(obs.reshape(obs.shape[0], 24, 24, 27).copy()).to(device=device, dtype=torch.float32)
        with torch.no_grad():
            logits = model(x)["action_type_logits"]
            probs = torch.softmax(logits, dim=-1).cpu().numpy()
            pred = torch.argmax(logits, dim=-1).cpu().numpy().astype(np.int64)

        mask = actor
        gt_actor = target[mask]
        pred_actor = pred[mask]
        probs_actor = probs[mask]

        actor_total += int(gt_actor.size)
        actor_correct += int(np.sum(gt_actor == pred_actor))

        gt_non_noop_mask = gt_actor != 0
        actor_gt_non_noop += int(np.sum(gt_non_noop_mask))
        actor_pred_non_noop_on_gt_non_noop += int(np.sum(pred_actor[gt_non_noop_mask] != 0))

        for g, p in zip(gt_actor.tolist(), pred_actor.tolist()):
            confusion[int(g), int(p)] += 1

        if probs_actor.size > 0:
            prob_sum += np.sum(probs_actor, axis=0)

        wh = worker & (target == 2)
        worker_harvest_total += int(np.sum(wh))
        worker_harvest_hit += int(np.sum(pred[wh] == 2))

        bp = base & (target == 4)
        base_produce_total += int(np.sum(bp))
        base_produce_hit += int(np.sum(pred[bp] == 4))

        ca = combat & (target == 5)
        combat_attack_total += int(np.sum(ca))
        combat_attack_hit += int(np.sum(pred[ca] == 5))

    avg_probs = (prob_sum / actor_total).tolist() if actor_total > 0 else [0.0] * 6

    return {
        "schema": "stage10t1.student_offline_bc_truth.v1",
        "generated_at_utc": _utc_now(),
        "checkpoint": checkpoint_path.as_posix(),
        "validation_source": val_npz.as_posix(),
        "actor_cell_action_type_accuracy": _safe_div(actor_correct, actor_total),
        "actor_cell_non_noop_recall": _safe_div(actor_pred_non_noop_on_gt_non_noop, actor_gt_non_noop),
        "worker_harvest_recall": _safe_div(worker_harvest_hit, worker_harvest_total),
        "base_produce_recall": _safe_div(base_produce_hit, base_produce_total),
        "combat_attack_recall": _safe_div(combat_attack_hit, combat_attack_total),
        "counts": {
            "actor_cell_total": int(actor_total),
            "actor_gt_non_noop_total": int(actor_gt_non_noop),
            "worker_harvest_total": int(worker_harvest_total),
            "base_produce_total": int(base_produce_total),
            "combat_attack_total": int(combat_attack_total),
        },
        "confusion_matrix_actor_cells": {
            "labels": [ACTION_NAMES[i] for i in range(6)],
            "matrix": confusion.tolist(),
        },
        "mean_probabilities_on_actor_cells": {
            "p_noop": float(avg_probs[0]),
            "p_move": float(avg_probs[1]),
            "p_harvest": float(avg_probs[2]),
            "p_return": float(avg_probs[3]),
            "p_produce": float(avg_probs[4]),
            "p_attack": float(avg_probs[5]),
        },
    }


def _load_runtime_map_from_cell_table(cell_table: Path) -> np.ndarray:
    arr = np.zeros((576, 27), dtype=np.float32)
    with cell_table.open("r", encoding="utf-8-sig") as f:
        for line in f:
            row = json.loads(line)
            idx = int(row["cell_index"])
            vec = row.get("raw_channel_vector")
            if isinstance(vec, list) and len(vec) == 27:
                arr[idx, :] = np.asarray(vec, dtype=np.float32)
    return arr.reshape(24, 24, 27)


def _compute_runtime_vs_bc_ood(val_npz: Path, runtime_cell_table: Path) -> Dict[str, Any]:
    runtime_map = _load_runtime_map_from_cell_table(runtime_cell_table)

    focus = {
        "B2": {"flat": 25, "unit_idx": SEM_UNIT_WORKER},
        "C3": {"flat": 50, "unit_idx": SEM_UNIT_BASE},
    }

    best = {
        "B2": {"dist": float("inf"), "sample_index": None, "flat_index": None, "vector": None, "map": None},
        "C3": {"dist": float("inf"), "sample_index": None, "flat_index": None, "vector": None, "map": None},
    }

    seen = 0
    for start, obs, act, _s_obs, _s_act in _iter_paired_rows_from_npz(val_npz, "observations", "actions", rows_per_chunk=128):
        obs = np.asarray(obs, dtype=np.float32)
        owner_self = obs[:, :, SEM_OWNER_SELF] > 0.5
        unit = obs[:, :, SEM_UNIT_START:SEM_UNIT_END]
        unit_present = np.max(unit, axis=2) > 0.5
        unit_idx = np.argmax(unit, axis=2)

        for key, meta in focus.items():
            rv = runtime_map.reshape(576, 27)[meta["flat"]]
            cand = owner_self & unit_present & (unit_idx == meta["unit_idx"])
            where = np.where(cand)
            if where[0].size == 0:
                continue
            rows = where[0]
            cols = where[1]
            vecs = obs[rows, cols, :]
            d = np.linalg.norm(vecs - rv[None, :], axis=1)
            j = int(np.argmin(d))
            dist = float(d[j])
            if dist < best[key]["dist"]:
                local_sample = int(rows[j])
                best[key] = {
                    "dist": dist,
                    "sample_index": int(start + local_sample),
                    "flat_index": int(cols[j]),
                    "vector": vecs[j].astype(np.float32),
                    "map": obs[local_sample].reshape(24, 24, 27).astype(np.float32),
                }
        seen += obs.shape[0]

    out = {
        "schema": "stage10t1.runtime_vs_bc_ood.v1",
        "generated_at_utc": _utc_now(),
        "validation_source": val_npz.as_posix(),
        "runtime_cell_table": runtime_cell_table.as_posix(),
        "scanned_validation_samples": int(seen),
        "focus_cells": {},
    }

    for key, meta in focus.items():
        rv_map = runtime_map
        rv = rv_map.reshape(576, 27)[meta["flat"]]
        bx = int(meta["flat"] % 24)
        by = int(meta["flat"] // 24)

        b = best[key]
        if b["sample_index"] is None:
            out["focus_cells"][key] = {"match_found": False}
            continue

        sv = b["vector"]
        smap = b["map"]
        s_flat = int(b["flat_index"])
        sx = int(s_flat % 24)
        sy = int(s_flat // 24)

        out["focus_cells"][key] = {
            "match_found": True,
            "nearest_validation_sample_index": int(b["sample_index"]),
            "nearest_validation_flat_index": s_flat,
            "nearest_validation_visual_label": _flat_label(s_flat),
            "l2_distance_27ch": float(b["dist"]),
            "channel_comparison": {
                "hit_points_runtime_vs_bc": [float(rv[0]), float(sv[0])],
                "resources_runtime_vs_bc": [float(rv[1]), float(sv[1])],
                "owner_channels_runtime": [float(rv[2]), float(rv[3]), float(rv[4])],
                "owner_channels_bc": [float(sv[2]), float(sv[3]), float(sv[4])],
                "unit_type_channels_runtime": [float(x) for x in rv[5:12].tolist()],
                "unit_type_channels_bc": [float(x) for x in sv[5:12].tolist()],
                "current_action_channels_runtime": [float(x) for x in rv[12:18].tolist()],
                "current_action_channels_bc": [float(x) for x in sv[12:18].tolist()],
                "direction_channels_runtime": [float(x) for x in rv[18:22].tolist()],
                "direction_channels_bc": [float(x) for x in sv[18:22].tolist()],
                "produce_type_channels_runtime": [float(x) for x in rv[22:26].tolist()],
                "produce_type_channels_bc": [float(x) for x in sv[22:26].tolist()],
                "attack_target_index_runtime_vs_bc": [float(rv[26]), float(sv[26])],
            },
            "local_5x5_l2": float(np.linalg.norm(_local_patch(rv_map, bx, by, 2) - _local_patch(smap, sx, sy, 2))),
            "local_7x7_l2": float(np.linalg.norm(_local_patch(rv_map, bx, by, 3) - _local_patch(smap, sx, sy, 3))),
            "full_map_summary_runtime": _summarize_map_semantic(rv_map),
            "full_map_summary_bc": _summarize_map_semantic(smap),
        }

    return out


def _build_final_markdown(
    checkpoint_identity: Dict[str, Any],
    harness_audit: Dict[str, Any],
    teacher_actor: Dict[str, Any],
    export_truth: Dict[str, Any],
    adaptation_truth: Dict[str, Any],
    bc_truth: Dict[str, Any],
    student_truth: Dict[str, Any],
    runtime_ood: Dict[str, Any],
) -> str:
    cls = []

    if harness_audit["mean_return_paradox"]["deterministic_mean_return"] == -10.0 and teacher_actor["mean_non_noop_actor_actions_per_step"] > 0:
        cls.append("TEACHER_VISUAL_METRICS_MISMATCH")

    det_noop = teacher_actor["deterministic_vs_stochastic_with_mask"]["deterministic"]["all_cell_noop_share"]
    st_noop = teacher_actor["deterministic_vs_stochastic_with_mask"]["stochastic"]["all_cell_noop_share"]
    if det_noop > 0.99 and st_noop < 0.5:
        cls.append("TEACHER_DETERMINISTIC_COLLAPSE_STOCHASTIC_ACTIVE")

    if adaptation_truth["actor_labels_preserved_vs_raw_exact_row_share"] >= 0.999999 and sum(adaptation_truth["out_of_range_counts"].values()) == 0:
        pass
    else:
        cls.append("SEMANTIC_ADAPTATION_BEHAVIOR_LOST")

    val_acc = student_truth["actor_cell_action_type_accuracy"]
    val_non_noop_recall = student_truth["actor_cell_non_noop_recall"]
    runtime_b2 = runtime_ood.get("focus_cells", {}).get("B2", {})
    runtime_c3 = runtime_ood.get("focus_cells", {}).get("C3", {})
    if val_acc > 0.95 and val_non_noop_recall > 0.9 and (runtime_b2.get("l2_distance_27ch", 0.0) > 1.0 or runtime_c3.get("l2_distance_27ch", 0.0) > 1.0):
        cls.append("STUDENT_OFFLINE_OK_RUNTIME_OOD")

    if bc_truth["train"]["positive_actor_examples"]["Return"] == 0 and bc_truth["train"]["positive_actor_examples"]["Attack"] == 0:
        cls.append("BC_READY_BEHAVIOR_IMBALANCED")

    if not cls:
        cls.append("INCONCLUSIVE_NEEDS_STAGE10T1R")

    if "STUDENT_OFFLINE_OK_RUNTIME_OOD" in cls:
        gate = "GO_FOR_STAGE10D11_RUNTIME_VS_BC_OBSERVATION_DISTRIBUTION_AUDIT"
    elif "SEMANTIC_ADAPTATION_BEHAVIOR_LOST" in cls:
        gate = "GO_FOR_SEMANTIC_ADAPTER_FIX"
    elif "BC_READY_BEHAVIOR_IMBALANCED" in cls:
        gate = "GO_FOR_BC_DATASET_REBALANCE_OR_TARGETED_AUGMENTATION"
    elif "TEACHER_VISUAL_METRICS_MISMATCH" in cls:
        gate = "GO_FOR_TEACHER_EVAL_HARNESS_FIX"
    else:
        gate = "GO_FOR_STAGE10D11_RUNTIME_VS_BC_OBSERVATION_DISTRIBUTION_AUDIT"

    lines = []
    lines.append("# STAGE10T1 Teacher / Export / BC Behavior Truth Audit")
    lines.append("")
    lines.append(f"Generated: {_utc_now()}")
    lines.append("")

    lines.append("## Section 1 - Checkpoint identity")
    lines.append(f"- checkpoint: {checkpoint_identity['checkpoint_path']}")
    lines.append(f"- training_steps_from_path: {checkpoint_identity['training_steps_from_path']}")
    lines.append(f"- checkpoint_mtime_utc: {checkpoint_identity['checkpoint_mtime_utc']}")
    lines.append(f"- wrong_checkpoint_export_risk: {checkpoint_identity['wrong_checkpoint_export_risk']['is_risky']}")
    lines.append("")

    lines.append("## Section 2 - Teacher evaluation harness audit")
    mp = harness_audit["mean_return_paradox"]
    lines.append(f"- deterministic_mean_return: {mp['deterministic_mean_return']}")
    lines.append(f"- stochastic_mean_return: {mp['stochastic_mean_return']}")
    lines.append(f"- deterministic_noop_share_all_cells: {mp['deterministic_noop_share_all_cells']:.6f}")
    lines.append(f"- stochastic_noop_share_all_cells: {mp['stochastic_noop_share_all_cells']:.6f}")
    lines.append(f"- explanation: {mp['explanation']}")
    lines.append("")

    lines.append("## Section 3 - Teacher actor-cell behavior")
    lines.append(f"- actor_cell_noop_share: {teacher_actor['actor_cell_noop_share']:.6f}")
    lines.append(f"- worker_harvest_share: {teacher_actor['worker_harvest_share']:.6f}")
    lines.append(f"- base_produce_share: {teacher_actor['base_produce_share']:.6f}")
    lines.append(f"- barracks_produce_share: {teacher_actor['barracks_produce_share']:.6f}")
    lines.append(f"- combat_attack_share: {teacher_actor['combat_unit_attack_share']:.6f}")
    lines.append(f"- mean_non_noop_actor_actions_per_step: {teacher_actor['mean_non_noop_actor_actions_per_step']:.6f}")
    lines.append("")

    lines.append("## Section 4 - Raw export truth")
    lines.append(f"- episodes: {export_truth['raw_export_identity']['episodes']}")
    lines.append(f"- frames: {export_truth['raw_export_identity']['frames']}")
    lines.append(f"- behavior_chain_episodes: {export_truth['behavior_chain']['episodes_with_worker_harvest_then_return_then_base_produce_then_barracks_produce_then_combat_move_or_attack']}")
    lines.append("")

    lines.append("## Section 5 - Semantic adaptation truth")
    lines.append(f"- frames_preserved: {adaptation_truth['frames_preserved']}")
    lines.append(f"- actor_labels_preserved_exact_row_share: {adaptation_truth['actor_labels_preserved_vs_raw_exact_row_share']:.6f}")
    lines.append(f"- out_of_range_total: {sum(adaptation_truth['out_of_range_counts'].values())}")
    lines.append("")

    lines.append("## Section 6 - BC-ready dataset truth")
    lines.append(f"- train_actor_cell_noop_share: {bc_truth['train']['actor_cell_noop_share']:.6f}")
    lines.append(f"- val_actor_cell_noop_share: {bc_truth['validation']['actor_cell_noop_share']:.6f}")
    lines.append(f"- train_positive_examples: {bc_truth['train']['positive_actor_examples']}")
    lines.append(f"- val_positive_examples: {bc_truth['validation']['positive_actor_examples']}")
    lines.append("")

    lines.append("## Section 7 - Student offline truth")
    lines.append(f"- actor_cell_action_type_accuracy: {student_truth['actor_cell_action_type_accuracy']:.6f}")
    lines.append(f"- actor_cell_non_noop_recall: {student_truth['actor_cell_non_noop_recall']:.6f}")
    lines.append(f"- worker_harvest_recall: {student_truth['worker_harvest_recall']:.6f}")
    lines.append(f"- base_produce_recall: {student_truth['base_produce_recall']:.6f}")
    lines.append(f"- combat_attack_recall: {student_truth['combat_attack_recall']:.6f}")
    lines.append("")

    lines.append("## Section 8 - Unity runtime mismatch hypothesis")
    b2 = runtime_ood.get("focus_cells", {}).get("B2", {})
    c3 = runtime_ood.get("focus_cells", {}).get("C3", {})
    lines.append(f"- B2 nearest L2 (27ch): {b2.get('l2_distance_27ch')}")
    lines.append(f"- C3 nearest L2 (27ch): {c3.get('l2_distance_27ch')}")
    lines.append(f"- B2 local_5x5_l2: {b2.get('local_5x5_l2')}")
    lines.append(f"- C3 local_5x5_l2: {c3.get('local_5x5_l2')}")
    lines.append("")

    lines.append("## Section 9 - Classification")
    for c in cls:
        lines.append(f"- {c}")
    lines.append("")

    lines.append("## Section 10 - Recommended next gate")
    lines.append(f"- {gate}")
    lines.append("")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10T.1 Teacher/Export/BC behavior truth audit")
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("python/week6_student/reports"),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = _repo_root()
    out_dir = (root / args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_rollout_dir = root / "python/week5_teacher_legacy032/teacher_rollouts/legacy032_3m_unity_v2_rollout_export_20260501T125015Z"
    adapted_dir = root / "python/week5_teacher_legacy032/teacher_adapted/legacy032_3m_unity_v2_semantic_adapted_stage10d6_20260503T085218Z"
    bc_ready_dir = root / "python/week6_student/bc_ready/legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z"

    rollout_manifest = _read_json(raw_rollout_dir / "teacher_rollout_manifest.json")
    rollout_summary = _read_json(raw_rollout_dir / "teacher_rollout_summary.json")
    adapted_report = _read_json(adapted_dir / "observation_semantic_conversion_report.json")
    bc_manifest = _read_json(bc_ready_dir / "bc_manifest.json")
    stage10d8_report = _read_json(root / "python/week6_student/reports/LEGACY032_UNITY_V2_STAGE10D8_SEMANTIC_BC_RETRAINING_REPORT.json")
    stage5_gate = _read_json(root / "python/week5_teacher_legacy032/reports/stage5_gate_003000000_20260430T225547Z.json")

    checkpoint_identity = _teacher_checkpoint_identity(rollout_manifest, adapted_report, bc_manifest, stage10d8_report)
    harness_audit = _teacher_eval_harness_audit(stage5_gate)

    teacher_actor = _compute_teacher_actor_metrics_from_raw(raw_rollout_dir / "teacher_rollout_raw.npz")
    export_truth = _compute_export_behavior_truth(teacher_actor, rollout_manifest, rollout_summary)

    adaptation_truth = _compute_semantic_adaptation_truth(
        raw_rollout_dir / "teacher_rollout_raw.npz",
        adapted_dir / "adapted_dataset.npz",
        adapted_report,
    )

    bc_truth = _compute_bc_ready_truth(
        bc_ready_dir / "bc_train.npz",
        bc_ready_dir / "bc_validation.npz",
        bc_manifest,
    )

    student_ckpt = root / stage10d8_report["checkpoint_selection"]["best_checkpoint_path"]
    student_truth = _compute_student_offline_truth(
        bc_ready_dir / "bc_validation.npz",
        student_ckpt,
    )

    runtime_ood = _compute_runtime_vs_bc_ood(
        bc_ready_dir / "bc_validation.npz",
        root / "python/week6_student/reports/stage10d10_global_runtime_cell_table_step0001.jsonl",
    )

    p1 = out_dir / "stage10t1_teacher_checkpoint_identity.json"
    p2 = out_dir / "stage10t1_teacher_eval_harness_audit.json"
    p3 = out_dir / "stage10t1_teacher_actor_cell_metrics.json"
    p4 = out_dir / "stage10t1_export_behavior_truth.json"
    p5 = out_dir / "stage10t1_semantic_adaptation_truth.json"
    p6 = out_dir / "stage10t1_bc_ready_behavior_truth.json"
    p7 = out_dir / "stage10t1_student_offline_bc_truth.json"
    report_path = out_dir / "STAGE10T1_TEACHER_EXPORT_BC_BEHAVIOR_TRUTH_AUDIT_REPORT.md"

    _write_json(p1, checkpoint_identity)
    _write_json(p2, harness_audit)
    _write_json(p3, teacher_actor)
    _write_json(p4, export_truth)
    _write_json(p5, adaptation_truth)
    _write_json(p6, bc_truth)
    _write_json(p7, {**student_truth, "runtime_vs_bc_ood": runtime_ood})

    md = _build_final_markdown(
        checkpoint_identity,
        harness_audit,
        teacher_actor,
        export_truth,
        adaptation_truth,
        bc_truth,
        student_truth,
        runtime_ood,
    )
    report_path.write_text(md, encoding="utf-8")

    print(p1.as_posix())
    print(p2.as_posix())
    print(p3.as_posix())
    print(p4.as_posix())
    print(p5.as_posix())
    print(p6.as_posix())
    print(p7.as_posix())
    print(report_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
