#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

import numpy as np


@dataclass
class MapUnit:
    unit_type: str
    player: int
    x: int
    y: int


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(root: Path, p: Path) -> Path:
    return p if p.is_absolute() else (root / p)


def _flat_index(x: int, y: int, width: int) -> int:
    return y * width + x


def _safe_reset(env: Any, seed: int) -> Any:
    try:
        return env.reset(seed=seed)
    except TypeError:
        return env.reset()


def _parse_map_units(map_path: Path) -> Tuple[int, int, List[MapUnit]]:
    root = ET.fromstring(map_path.read_text(encoding="utf-8"))
    width = int(root.attrib["width"])
    height = int(root.attrib["height"])
    units: List[MapUnit] = []
    units_el = root.find("units")
    if units_el is not None:
        for unit_el in units_el:
            units.append(
                MapUnit(
                    unit_type=str(unit_el.attrib.get("type", "")),
                    player=int(unit_el.attrib.get("player", "-999")),
                    x=int(unit_el.attrib.get("x", "0")),
                    y=int(unit_el.attrib.get("y", "0")),
                )
            )
    return width, height, units


def _cell_vector(obs0: np.ndarray, x: int, y: int) -> np.ndarray:
    return np.asarray(obs0[y, x, :], dtype=np.float32)


def _active_channels(vec: np.ndarray, thr: float = 0.5) -> List[int]:
    return [int(i) for i in np.where(vec > thr)[0].tolist()]


def _score_owner_candidates(obs0: np.ndarray, units: List[MapUnit]) -> Dict[str, Any]:
    # owner group is expected to be width=3 in encoded grid features.
    # We infer candidate windows by separability across neutral/player0/player1 known cells.
    neutral_cells = [(u.x, u.y) for u in units if u.player == -1]
    p0_cells = [(u.x, u.y) for u in units if u.player == 0]
    p1_cells = [(u.x, u.y) for u in units if u.player == 1]

    rows = []
    for start in range(0, 27 - 3 + 1):
        end = start + 3

        def _mean(cells: List[Tuple[int, int]]) -> np.ndarray:
            if not cells:
                return np.zeros((3,), dtype=np.float32)
            return np.mean(np.asarray([obs0[y, x, start:end] for x, y in cells], dtype=np.float32), axis=0)

        n = _mean(neutral_cells)
        a = _mean(p0_cells)
        b = _mean(p1_cells)

        n_idx = int(np.argmax(n))
        a_idx = int(np.argmax(a))
        b_idx = int(np.argmax(b))

        distinct = len({n_idx, a_idx, b_idx}) == 3
        margin = float((np.max(n) - np.partition(n, -2)[-2]) + (np.max(a) - np.partition(a, -2)[-2]) + (np.max(b) - np.partition(b, -2)[-2]))
        score = float((1.0 if distinct else 0.0) + margin)

        rows.append(
            {
                "window": [int(start), int(end - 1)],
                "neutral_argmax_local": n_idx,
                "player0_argmax_local": a_idx,
                "player1_argmax_local": b_idx,
                "distinct_triplet": bool(distinct),
                "separation_margin_sum": margin,
                "score": score,
                "means": {
                    "neutral": [float(v) for v in n.tolist()],
                    "player0": [float(v) for v in a.tolist()],
                    "player1": [float(v) for v in b.tolist()],
                },
            }
        )

    rows.sort(key=lambda x: (x["distinct_triplet"], x["score"]), reverse=True)
    top = rows[0] if rows else None

    inferred = None
    if top is not None:
        ws = int(top["window"][0])
        inferred = {
            "owner_neutral_channel": int(ws + top["neutral_argmax_local"]),
            "owner_player0_channel": int(ws + top["player0_argmax_local"]),
            "owner_player1_channel": int(ws + top["player1_argmax_local"]),
            "confidence": "high" if top["distinct_triplet"] else "medium",
        }

    return {
        "top_windows": rows[:8],
        "best": top,
        "inferred": inferred,
    }


def _score_unit_type_candidates(obs0: np.ndarray, units: List[MapUnit]) -> Dict[str, Any]:
    # unit_type group expected width=7 usable types (+1 unknown/none in source table).
    by_type: Dict[str, List[Tuple[int, int]]] = {}
    for u in units:
        by_type.setdefault(u.unit_type, []).append((u.x, u.y))

    tracked_types = ["Resource", "Base", "Barracks", "Worker", "Light", "Heavy", "Ranged"]

    rows: List[Dict[str, Any]] = []
    for start in range(0, 27 - 7 + 1):
        end = start + 7
        score = 0.0
        inferred_local: Dict[str, int] = {}
        means: Dict[str, List[float]] = {}

        for t in tracked_types:
            cells = by_type.get(t, [])
            if not cells:
                continue
            m = np.mean(np.asarray([obs0[y, x, start:end] for x, y in cells], dtype=np.float32), axis=0)
            idx = int(np.argmax(m))
            inferred_local[t] = idx
            means[t] = [float(v) for v in m.tolist()]
            score += float(np.max(m) - np.partition(m, -2)[-2])

        # Penalize collisions among observed type argmax indices.
        if inferred_local:
            uniq = len(set(inferred_local.values()))
            collisions = len(inferred_local) - uniq
            score -= 0.5 * collisions

        rows.append(
            {
                "window": [int(start), int(end - 1)],
                "score": float(score),
                "observed_type_to_local_index": inferred_local,
                "means": means,
            }
        )

    rows.sort(key=lambda x: x["score"], reverse=True)
    best = rows[0] if rows else None

    inferred = None
    if best is not None:
        ws = int(best["window"][0])
        inferred_map = {
            k: int(ws + int(v)) for k, v in best["observed_type_to_local_index"].items()
        }
        inferred = {
            "unit_type_observed_raw_channels": inferred_map,
            "confidence": "high" if best["score"] >= 1.5 else "medium",
        }

    return {
        "top_windows": rows[:8],
        "best": best,
        "inferred": inferred,
        "tracked_types": tracked_types,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stage10D.5 controlled raw observation probe")
    p.add_argument(
        "--model-metadata",
        type=Path,
        default=Path(
            "python/week5_teacher_legacy032/teacher_models/"
            "legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/model_metadata.json"
        ),
    )
    p.add_argument("--seed", type=int, default=17)
    p.add_argument(
        "--output",
        type=Path,
        default=Path("python/week6_student/reports/stage10d5_controlled_raw_observation_probe.json"),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = _repo_root()
    out_path = _resolve(root, args.output)
    metadata_path = _resolve(root, args.model_metadata)

    hard_failures: List[str] = []
    warnings: List[str] = []

    if not metadata_path.exists():
        hard_failures.append(f"missing model metadata: {metadata_path.as_posix()}")

    metadata: Dict[str, Any] = {}
    map_path_rel = "maps/24x24/basesWorkers24x24.xml"
    num_selfplay = 0
    num_bot = 6
    max_steps = 6000
    if not hard_failures:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        md_args = metadata.get("args", {}) if isinstance(metadata.get("args"), dict) else {}
        map_path_rel = str(md_args.get("map_path", metadata.get("map_path", map_path_rel)))
        num_selfplay = int(md_args.get("num_selfplay_envs", 0))
        num_bot = int(md_args.get("num_bot_envs", 6))
        max_steps = int(md_args.get("max_steps", metadata.get("max_steps", 6000)))

    map_path = root / "python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/microrts" / map_path_rel
    if not map_path.exists():
        # fallback to project-relative microrts path from other env layout
        alt = root / map_path_rel
        if alt.exists():
            map_path = alt
        else:
            hard_failures.append(f"map file not found: {map_path.as_posix()}")

    width = 24
    height = 24
    units: List[MapUnit] = []
    if not hard_failures:
        width, height, units = _parse_map_units(map_path)

    env_id = str(metadata.get("env_id", metadata.get("gym_id", "MicrortsDefeatCoacAIShaped-v3")))
    obs0 = np.zeros((24, 24, 27), dtype=np.float32)
    obs_shape: List[int] = [24, 24, 27]
    utt_unit_types: List[str] = []
    env_init_error: Optional[str] = None

    try:
        from gym_microrts.envs.vec_env import MicroRTSGridModeVecEnv
        from gym_microrts import microrts_ai

        ai2s = [microrts_ai.coacAI for _ in range(max(0, num_bot - 6))] + [
            microrts_ai.randomBiasedAI for _ in range(min(num_bot, 2))
        ] + [microrts_ai.lightRushAI for _ in range(min(num_bot, 2))] + [
            microrts_ai.workerRushAI for _ in range(min(num_bot, 2))
        ]
        if len(ai2s) < num_bot:
            ai2s += [microrts_ai.coacAI for _ in range(num_bot - len(ai2s))]

        env = MicroRTSGridModeVecEnv(
            num_selfplay_envs=num_selfplay,
            num_bot_envs=num_bot,
            max_steps=max_steps,
            render_theme=2,
            ai2s=ai2s[:num_bot],
            map_path=map_path_rel,
            reward_weight=np.array([10.0, 1.0, 1.0, 0.2, 1.0, 4.0]),
        )
        try:
            obs = _safe_reset(env, seed=int(args.seed))
            if isinstance(obs, tuple):
                obs = obs[0]
            obs = np.asarray(obs, dtype=np.float32)
            if obs.ndim != 4:
                raise RuntimeError(f"unexpected reset obs shape: {list(obs.shape)}")
            obs0 = np.asarray(obs[0], dtype=np.float32)
            obs_shape = [int(v) for v in obs0.shape]
            utt_unit_types = [str(u.get("name", "")) for u in env.utt.get("unitTypes", [])]
        finally:
            env.close()
    except Exception as exc:
        env_init_error = str(exc)
        hard_failures.append(f"failed to initialize controlled env probe: {exc}")

    cell_records: List[Dict[str, Any]] = []
    if obs0.size > 0 and units:
        occupied = {(u.x, u.y) for u in units}
        # Include map-defined cells and one empty probe cell.
        probe_cells = [(u.unit_type, u.player, u.x, u.y) for u in units]
        empty_xy = (12, 12)
        if empty_xy in occupied:
            for yy in range(height):
                found = False
                for xx in range(width):
                    if (xx, yy) not in occupied:
                        empty_xy = (xx, yy)
                        found = True
                        break
                if found:
                    break
        probe_cells.append(("Empty", -999, int(empty_xy[0]), int(empty_xy[1])))

        for unit_type, player, x, y in probe_cells:
            vec = _cell_vector(obs0, x, y)
            cell_records.append(
                {
                    "entity_type": unit_type,
                    "player": int(player),
                    "x": int(x),
                    "y": int(y),
                    "flat_index": int(_flat_index(x, y, width)),
                    "active_channels_gt_0_5": _active_channels(vec, thr=0.5),
                    "vector": [float(v) for v in vec.tolist()],
                }
            )

    owner_inference = _score_owner_candidates(obs0, units) if units else {"top_windows": [], "best": None, "inferred": None}
    unit_type_inference = _score_unit_type_candidates(obs0, units) if units else {"top_windows": [], "best": None, "inferred": None}

    inferred_owner = owner_inference.get("inferred") or {}
    inferred_unit = unit_type_inference.get("inferred") or {}

    out: Dict[str, Any] = {
        "stage": "10D.5",
        "diagnostic": "controlled_raw_observation_probe",
        "status": "pass" if not hard_failures else "fail",
        "env_id": env_id,
        "map_path": map_path.as_posix(),
        "seed": int(args.seed),
        "observation_shape": obs_shape,
        "env_num_selfplay_envs": int(num_selfplay),
        "env_num_bot_envs": int(num_bot),
        "utt_unit_types": utt_unit_types,
        "candidate_raw_vectors_for_known_cells": cell_records,
        "inferred_owner_channel_candidates": {
            **({} if not inferred_owner else inferred_owner),
            "full_analysis": owner_inference,
        },
        "inferred_unit_type_channel_candidates": {
            **({} if not inferred_unit else inferred_unit),
            "full_analysis": unit_type_inference,
        },
        "confidence_per_candidate": {
            "owner": str((inferred_owner or {}).get("confidence", "low")),
            "unit_type": str((inferred_unit or {}).get("confidence", "low")),
        },
        "controlled_probe_runtime_error": env_init_error,
        "hard_failures": hard_failures,
        "warnings": warnings,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=True, indent=2), encoding="utf-8")
    print(out_path.as_posix())
    return 0 if not hard_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
